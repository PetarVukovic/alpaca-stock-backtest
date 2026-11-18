"""Export read-only IBKR MCP history responses; never connects to a broker.

Collection on 2026-10-14 used ONLY search_contracts, search_futures and
get_price_history from the Interactive Brokers (IBKR) plugin. Exact arguments,
errors and response hashes are written to the manifest. The MCP exposes no
end-date pagination or whatToShow parameter: MidPoint/Last must be confirmed
from each response's source field, never assumed from the requested instrument.

Run with the project's .venv/bin/python:
  scripts/pull_ibkr_history.py --input-prefix /tmp/ibkr-codex-b-01a139c7-save
Use --checkpoint to write CSVs without finalizing the manifest. Identical files
from a previous checkpoint are verified, not rewritten. All other collisions
are preserved and reported. This script contains no order or account API code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/data/2026-10-14_ibkr_manifest.json"
TF_SECONDS = {"1d": 86400, "1h": 3600, "5m": 300}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_time(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Provider timestamp is not timezone-aware")
    return stamp.astimezone(timezone.utc)


def error_of(call):
    response = call.get("response") or {}
    if response.get("time"):
        return None
    return response.get("error") or response.get("error_code") or json.dumps(response, ensure_ascii=False)


def relative_destination(call):
    tf, symbol = call["timeframe"], call.get("output_symbol", call["symbol"])
    args = call["args"]
    if args["security_type"] == "FUT":
        month = call["contract"]["contract_month"]
        suffix = f"{tf}.csv" if tf == "1d" else f"{tf}_clean.csv"
        return Path("data/archive/ibkr_contracts") / f"{symbol}_{month}_{args['contract_id']}_{suffix}"
    if args["security_type"] == "CRYPTO":
        symbol = f"{symbol}_IBKR_{args.get('exchange', 'UNKNOWN')}"
    folder, suffix = {"1d": ("ohlcv", "1d"), "1h": ("hourly", "1h_clean"), "5m": ("intraday", "5m_clean")}[tf]
    return Path("data") / folder / f"{symbol}_{suffix}.csv"


def serialize(call, now):
    response, args, tf = call["response"], call["args"], call["timeframe"]
    kind, source = args["security_type"], response.get("source")
    expected = "MidPoint" if kind in {"CASH", "CMDTY"} else "Last"
    if source != expected:
        raise ValueError(f"Required source {expected}; provider returned {source!r}")
    data_type = "MIDPOINT" if source == "MidPoint" else "INDEX_VALUE" if kind == "IND" else "TRADES"
    stamps = response["time"]
    for key in ("open", "high", "low", "close"):
        if len(response.get(key, [])) != len(stamps):
            raise ValueError(f"Array length mismatch: {key}")
    volumes = response.get("volume")
    if volumes is not None and len(volumes) != len(stamps):
        raise ValueError("Array length mismatch: volume")
    rows, duplicates, incomplete, missing_volume = {}, 0, 0, 0
    ohlc_issues = []
    for i, raw_stamp in enumerate(stamps):
        stamp = parse_time(raw_stamp)
        if tf == "1d" and kind == "IND":
            unfinished = stamp.date() >= now.date()
        else:
            unfinished = stamp + timedelta(seconds=TF_SECONDS[tf]) > now
        if unfinished:
            incomplete += 1
            continue
        prices = [response[key][i] for key in ("open", "high", "low", "close")]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in prices):
            raise ValueError(f"Nonfinite OHLC at {raw_stamp}")
        op, high, low, close = prices
        if high < max(op, low, close) or low > min(op, high, close):
            ohlc_issues.append({"source_ts": raw_stamp, "ohlc": prices})
        volume = ""
        if kind not in {"CASH", "CMDTY", "IND"} and volumes is not None:
            v = volumes[i]
            if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0:
                volume = v
        if volume == "":
            missing_volume += 1
        if tf == "1d" and kind == "CASH":
            # Evening UTC bar starts belong to the next FX session; holiday
            # midnight/early-morning labels already name that session date.
            # This mapping removes date-only collisions without changing prices.
            label = (stamp + timedelta(hours=12)).date().isoformat()
        else:
            label = stamp.date().isoformat() if tf == "1d" else stamp.isoformat().replace("+00:00", "Z")
        row = [label, *prices, volume]
        if label in rows:
            if rows[label] != row:
                raise ValueError(f"Conflicting duplicate timestamp: {label}")
            duplicates += 1
        rows[label] = row
    if not rows:
        raise ValueError("No complete validated bars remain")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["date" if tf == "1d" else "ts", "open", "high", "low", "close", "volume"])
    writer.writerows(rows[key] for key in sorted(rows))
    info = {"data_type": data_type, "provider_source": source, "rows": len(rows),
            "first": min(rows), "last": max(rows), "raw_rows": len(stamps),
            "raw_first": min(stamps), "raw_last": max(stamps),
            "incomplete_bars_excluded": incomplete, "identical_duplicates_removed": duplicates,
            "empty_volume_rows": missing_volume, "ohlc_range_violation_count": len(ohlc_issues),
            "ohlc_range_violations": ohlc_issues,
            "backtest_ready": False,
            "quality_status": "requires_review_ohlc_range" if ohlc_issues else "structural_checks_only",
            "date_mapping": "UTC source timestamp plus 12h, then calendar date; evening FX starts map to next session" if tf == "1d" and kind == "CASH" else "UTC source calendar date" if tf == "1d" else "UTC source timestamp"}
    return stream.getvalue().encode(), info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-prefix", required=True)
    parser.add_argument("--checkpoint", action="store_true")
    args = parser.parse_args()
    prefix = Path(args.input_prefix)
    parts = sorted(prefix.parent.glob(prefix.name + "-[0-9][0-9].json"))
    calls = [call for part in parts for call in json.loads(part.read_text())]
    metadata = json.loads(Path(str(prefix) + "-metadata.json").read_text())
    now = datetime.now(timezone.utc)
    if not args.checkpoint and MANIFEST.exists():
        raise SystemExit(f"Refusing to overwrite {MANIFEST}")
    grouped = defaultdict(list)
    attempts = []
    for number, call in enumerate(calls):
        if call.get("tool") != "get_price_history":
            raise ValueError("Unexpected tool in history payload")
        key = (call["symbol"], call["args"]["contract_id"], call["timeframe"])
        grouped[key].append((number, call))
        response = call.get("response") or {}
        attempts.append({"id": number, "tool": call["tool"], "symbol": call["symbol"],
                         "timeframe": call["timeframe"], "args": call["args"], "error": error_of(call),
                         "rows_returned": len(response.get("time", [])),
                         "response_metadata": {k: v for k, v in response.items() if k not in {"time", "open", "high", "low", "close", "volume", "content"}},
                         "response_sha256": sha(json.dumps(response, sort_keys=True).encode())})
    datasets = []
    for (symbol, contract_id, tf), versions in grouped.items():
        good = [(i, c) for i, c in versions if c.get("response", {}).get("time")]
        latest = versions[-1][1]
        limits = sorted({str(error_of(c)) for _, c in versions if error_of(c)})
        entry = {"symbol": symbol, "timeframe": tf, "contract_spec": latest.get("contract") or {
            "contract_id": contract_id, "exchange": latest["args"].get("exchange"), "security_type": latest["args"]["security_type"]},
                 "contract_id": contract_id, "security_type": latest["args"]["security_type"],
                 "data_type": "MIDPOINT" if latest["args"]["security_type"] in {"CASH", "CMDTY"} else "INDEX_VALUE" if latest["args"]["security_type"] == "IND" else "TRADES",
                 "rows": 0, "first": None, "last": None, "sha256": None,
                 "limits_hit": limits, "attempt_ids": [i for i, _ in versions]}
        if not good:
            entry.update(status="unavailable", path=None, data_type_verified=False)
        else:
            number, call = max(good, key=lambda pair: (len(pair[1]["response"]["time"]), pair[0]))
            entry["selected_attempt_id"] = number
            try:
                content, info = serialize(call, now)
                relative = relative_destination(call)
                target = ROOT / relative
                digest = sha(content)
                if target.exists():
                    if sha(target.read_bytes()) != digest:
                        raise FileExistsError(f"Existing file preserved: {relative}")
                    status = "verified_existing_identical"
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as handle:
                        handle.write(content)
                    status = "written"
                entry.update(info, path=str(relative), sha256=digest, status=status, data_type_verified=True)
                response = call["response"]
                conflicts = []
                for key, bound, direction in (("chart_start", info["raw_first"], "after"), ("chart_end", info["raw_last"], "before")):
                    if response.get(key):
                        meta_stamp, data_stamp = parse_time(response[key]), parse_time(bound)
                        if (direction == "after" and meta_stamp > data_stamp) or (direction == "before" and meta_stamp < data_stamp):
                            conflicts.append({"field": key, "reported": response[key], "actual_bound": bound})
                entry["provider_metadata_conflicts"] = conflicts
                if conflicts:
                    entry["limits_hit"].append("Provider chart metadata disagrees with actual timestamp-array bounds.")
                if call["args"]["security_type"] == "CASH" and tf == "1d":
                    entry["source_timestamps_utc"] = response["time"]
                if tf != "1d":
                    entry["limits_hit"].append("Recent window only; tool has no end-date/cursor pagination.")
                if len(call["response"]["time"]) >= call["args"].get("step_count", 10**9):
                    entry["limits_hit"].append("Requested bar-count window reached; response count may exceed request through provider boundary rounding.")
            except (ValueError, FileExistsError) as exc:
                entry.update(status="validation_or_collision_blocked", path=None)
                entry["limits_hit"].append(str(exc))
        datasets.append(entry)
    manifest = {
        "created_utc": now.isoformat().replace("+00:00", "Z"), "agent": "codex-b", "project": "memory-chips-lab",
        "collection_status": "saved_after_user_resumed", "read_only_tools_called": metadata["read_only_tools_called"],
        "tool_inventory": metadata["tool_inventory"], "requested_symbols": metadata["requested_symbols"],
        "daily_date_convention": "FX: calendar date of source timestamp + 12h; observed 21:15/22:15/22:00/23:00 UTC starts map to next session, 00:00/07:00 labels keep their date. Mapping eliminates 18 false date-only duplicates per FX series and matches chart_start session date; formal exchange-calendar review is pending. All other daily data uses UTC calendar date of provider timestamp, NOT exchange session date. Futures often carry previous-civil-day labels.",
        "completion_filter": "Intraday: timestamp + bar duration <= export UTC time. Daily FX/futures: conservative timestamp + 24h <= export UTC time. Daily indices: exclude current UTC civil date. Exact exchange-calendar validation remains pending.",
        "data_type_policy": "No whatToShow selector exists in this MCP. Export requires source=MidPoint for FX/spot, source=Last for futures/crypto; Last index values are marked INDEX_VALUE, not traded volume. MIDPOINT/index volume stays empty.",
        "futures_policy": "Per-contract only in data/archive/ibkr_contracts; no continuous series, roll, back-adjustment or lookahead-based contract choice. Three nearest nonexpired expiries per root plus available tested expired contracts. Catalog depth is not proof of historical coverage. Micro SIL resolved from nonrepresentative SI ladder; provider exposes no multiplier/currency fields here.",
        "global_limits": ["step_count above 3500 rejected; some requests, explicitly DX/VIX, cap step_count at 1000. FIVE_YEARS can return more daily bars than the count cap.",
                          "No end-date or pagination argument; cannot backfill arbitrary older intraday windows.",
                          "No explicit pacing-limit response observed. Internal error / INVALID_ARGUMENT occurred; attribution to pacing is unproven. Sequential smaller requests often succeeded.",
                          "No account/subscription API called; only explicit market-data permission errors identify unavailable access.",
                          "No vwap/trades arrays provided by this tool; not synthesized. No filling gaps, resampling or price adjustment. OHLC range violations are preserved and enumerated; close may reflect settlement/official-close conventions, but that cause is unverified. Flagged data requires review before backtesting.",
                          "Provider chart_start/chart_end can disagree with actual time arrays; file coverage is taken from validated individual timestamps, never chart metadata.",
                          "DXY exact lookup did not resolve; NYBOT DX index was probed as an explicitly labeled alternative and denied market-data permissions.",
                          "Research data only; no backtest validation or Critic approval performed."],
        "preserved_existing": ["data/ohlcv/EURUSD_1d.csv", "data/ohlcv/BTCUSD_1d.csv", "data/ohlcv/ETHUSD_1d.csv", "data/ohlcv/SIL_1d.csv", "data/hourly/SIL_1h_clean.csv"],
        "datasets": datasets, "attempts": attempts, "discovery": {"searches": metadata["searches"], "futures_ladders": metadata["ladders"]},
        "raw_response_parts": [str(p) for p in parts], "raw_response_parts_sha256": {str(p): sha(p.read_bytes()) for p in parts},
    }
    manifest["availability_summary"] = {
        symbol: {tf: {"files": sum(d["symbol"] == symbol and d["timeframe"] == tf and d.get("path") is not None for d in datasets),
                      "rows": sum(d["rows"] for d in datasets if d["symbol"] == symbol and d["timeframe"] == tf)}
                 for tf in TF_SECONDS}
        for symbol in metadata["requested_symbols"]
    }
    if not args.checkpoint:
        with MANIFEST.open("x") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    exported = [d for d in datasets if d["status"] in {"written", "verified_existing_identical"}]
    blocked = [d for d in datasets if d["status"] == "validation_or_collision_blocked"]
    print(json.dumps({"files": len(exported), "rows": sum(d["rows"] for d in exported),
                      "blocked": blocked, "manifest": None if args.checkpoint else str(MANIFEST)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
