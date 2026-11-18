#!/usr/bin/env python3
"""Compare saved TradingView MCP captures with saved fixed-one-share Python runs.

Read-only on all research inputs. No new backtest, UI interaction or network.
Re-run safely as more TRADINGVIEW_BATCH_NN.json files become available.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/research/C13C_20261009"
BACKTEST = ROOT / "reports/backtest/C29_C30_REGIMES_20261009"
TICKERS = ["MU", "WDC", "STX", "SIMO", "RMBS"]
MODES = ["BASE", "C29_ATR_TRAIL", "C30_GAP_SHOCK"]
PERIODS = ["SINCE_2022", "POST_CHATGPT"]
STARTS = {"SINCE_2022": 1640995200000, "POST_CHATGPT": 1669852800000}


def rounded_cent(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cutoff_table(record):
    """Require the custom table and exact mode, never use native current open PnL."""
    texts = []
    for study in record.get("tables", {}).get("studies", []):
        for table in study.get("tables", []):
            texts.extend(x for x in table.get("rows", []) if isinstance(x, str))
    for text in texts:
        if not text.startswith(record["mode"] + " | 1 share / 10000 USD"):
            continue
        match = re.search(r"Cutoff equity:\s*([0-9]+(?:\.[0-9]+)?)\s+USD", text)
        if match:
            return float(match.group(1)), text
    return None, None


def local_actions(ticker, mode, period, local_result):
    name = f"TV_{ticker}__{mode}" if period == "SINCE_2022" else f"TV_POST__{ticker}__{mode}"
    path = BACKTEST / f"{name}_trades.csv"
    actions = []
    with path.open() as handle:
        for trade in csv.DictReader(handle):
            actions.append({"entry": True, "side": "buy", "date": trade["entry_date"],
                            "price_without_commission": float(trade["raw_entry"]) + 0.01,
                            "qty": float(trade["quantity"])})
            actions.append({"entry": False, "side": "sell", "date": trade["exit_date"],
                            "price_without_commission": float(trade["raw_exit"]) - 0.01,
                            "qty": float(trade["quantity"])})
    position = local_result.get("open_position")
    if position:
        actions.append({"entry": True, "side": "buy", "date": position["entry_date"],
                        "price_without_commission": position["raw_entry"] + 0.01,
                        "qty": float(position["quantity"])})
    return actions


def compare_tail(record, actions):
    returned = record.get("trades", {}).get("trades", [])
    if not returned:
        return {"status": "NO_RETURNED_ACTIONS", "dates_status": "UNAVAILABLE"}
    if len(returned) > len(actions):
        return {"status": "MORE_TV_ACTIONS_THAN_LOCAL", "dates_status": "UNAVAILABLE"}
    tail = actions[-len(returned):]
    comparisons = []
    for tv, py in zip(returned, tail):
        date = tv.get("date") or tv.get("trade_date")
        # `time_index` from this connector is ordinal, not a timestamp or date.
        if date is not None:
            date = str(date)[:10]
        comparisons.append({"entry_matches": tv.get("entry") == py["entry"],
                            "side_matches": tv.get("side") == py["side"],
                            "quantity_matches": float(tv.get("qty", -1)) == py["qty"],
                            "price_delta_usd": float(tv["price"]) - py["price_without_commission"],
                            "local_date": py["date"], "tv_date": date,
                            "date_matches": None if date is None else date == py["date"]})
    structural = all(x["entry_matches"] and x["side_matches"] and x["quantity_matches"] for x in comparisons)
    return {"status": "SEQUENCE_MATCH" if structural else "SEQUENCE_MISMATCH",
            "n_actions_compared": len(comparisons),
            "max_abs_price_delta_usd": max(abs(x["price_delta_usd"]) for x in comparisons),
            "dates_status": "UNAVAILABLE_NO_TV_DATES" if all(x["tv_date"] is None for x in comparisons) else "PARTIAL_OR_AVAILABLE",
            "comparisons": comparisons,
            "note": "Tail-order sequence only; ordinal time_index cannot certify the calendar dates."}


def run():
    summary_path = BACKTEST / "summary.json"
    post_path = BACKTEST / "TV_POST_CHATGPT_PYTHON.json"
    summary = json.loads(summary_path.read_text())
    post = json.loads(post_path.read_text())
    inputs = [REPORTS / "TRADINGVIEW_RAW.json"] + sorted(REPORTS.glob("TRADINGVIEW_BATCH_*.json"))
    records, rejected, input_hashes, input_errors = [], [], {}, []
    for path in inputs:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            input_errors.append({"source": path.name, "error": str(error)})
            continue
        if not isinstance(payload, list):
            input_errors.append({"source": path.name, "error": "Expected list of captures"})
            continue
        input_hashes[path.name] = sha(path)
        for index, record in enumerate(payload):
            record = dict(record, source=path.name, source_row=index)
            reason = None
            if record.get("ticker") not in TICKERS or record.get("mode") not in MODES or record.get("period") not in PERIODS:
                reason = "Unexpected ticker/mode/period"
            else:
                cutoff, table = cutoff_table(record)
                record["parsed_cutoff_equity"] = cutoff
                record["parsed_table"] = table
                metrics = record.get("metrics", {})
                updated = record.get("change", {}).get("updated_inputs", {})
                if cutoff is None:
                    reason = "Missing custom cutoff table with matching mode"
                elif not metrics.get("success") or metrics.get("currency") != "USD":
                    reason = "Missing successful USD metrics"
                elif metrics.get("strategy") != "C13C research · BASE / C29 / C30":
                    reason = "Unexpected strategy title"
                elif "in_0" in updated and updated["in_0"] != record["mode"]:
                    reason = "Changed mode does not match record"
                elif "in_1" in updated and updated["in_1"] != STARTS[record["period"]]:
                    reason = "Changed start date does not match period"
            if reason:
                rejected.append({k: record.get(k) for k in ("source", "source_row", "ticker", "mode", "period", "captured_utc")} | {"reason": reason})
            else:
                records.append(record)
    records.sort(key=lambda r: (r.get("captured_utc", ""), r["source"], r["source_row"]))
    latest = {}
    for record in records:
        latest[(record["ticker"], record["mode"], record["period"])] = record
    comparisons, missing = [], []
    for ticker in TICKERS:
        for period in PERIODS:
            for mode in MODES:
                key = (ticker, mode, period)
                if key not in latest:
                    missing.append({"ticker": ticker, "mode": mode, "period": period})
                    continue
                record = latest[key]
                local = summary["tv_python"][f"TV_{ticker}__{mode}"] if period == "SINCE_2022" else post["results"][f"{ticker}__{mode}"]
                native = record["metrics"]["metrics"]
                tv_equity, py_equity = record["parsed_cutoff_equity"], float(local["final"])
                tv_closed, py_closed = int(native["total_trades"]), int(local["n_closed"])
                actions = local_actions(ticker, mode, period, local)
                tail = compare_tail(record, actions)
                comparisons.append({"ticker": ticker, "mode": mode, "period": period,
                    "source": record["source"], "source_row": record["source_row"], "captured_utc": record.get("captured_utc"),
                    "tv_closed": tv_closed, "python_closed": py_closed, "closed_count_equal": tv_closed == py_closed,
                    "tv_cutoff_equity_usd": tv_equity, "python_cutoff_equity_usd": py_equity,
                    "python_cutoff_rounded_usd": rounded_cent(py_equity), "delta_usd": tv_equity - py_equity,
                    "rounded_cent_equal": rounded_cent(tv_equity) == rounded_cent(py_equity),
                    "absolute_delta_le_10c": abs(tv_equity - py_equity) <= .10,
                    "tail_actions": tail,
                    "native_total_orders": record.get("trades", {}).get("total_orders"),
                    "local_total_actions": len(actions),
                    "total_action_count_equal": record.get("trades", {}).get("total_orders") == len(actions),
                    "native_open_pnl_used_for_comparison": False})
    result = {"generated_utc": datetime.now(timezone.utc).isoformat(), "expected_cases": 30,
              "completed_valid_cases": len(comparisons), "raw_valid_captures": len(records),
              "superseded_valid_captures": len(records) - len(comparisons), "missing": missing,
              "rejected_captures": rejected, "input_errors": input_errors, "cases": comparisons,
              "source_hashes": input_hashes | {"summary.json": sha(summary_path), "TV_POST_CHATGPT_PYTHON.json": sha(post_path)},
              "limitations": ["No new backtest; comparison reads saved outputs only.",
                  "Cutoff equity is parsed from Pine table, never live native open_pl.",
                  "Ticker is attributed by capture metadata; table/metrics do not themselves expose ticker.",
                  "time_index is not a calendar date. Current connector returns only last20order actions.",
                  "10-cent difference flag is a transparent diagnostic scale, not exact parity or Critic approval."]}
    path = REPORTS / "TRADINGVIEW_COMPARISON.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    all_closed = sum(x["closed_count_equal"] for x in comparisons)
    exact = sum(x["rounded_cent_equal"] for x in comparisons)
    small = sum(x["absolute_delta_le_10c"] for x in comparisons)
    lines = ["# TradingView MCP — neovisna usporedba spremljenih rezultata", "",
             f"Ažurirano UTC: {result['generated_utc']}. Valjanih slučajeva **{len(comparisons)}/30**. Skripta ne pokreće novi backtest.", "",
             "Uspoređuju se pojedinačne dionice, jedna dionica po ulazu, početnih 10.000 USD, presjek do 8. listopada 2026. To nije račun od 600 EUR niti višedionički portfelj.", "",
             f"Broj zatvorenih trgovina jednak je u **{all_closed}/{len(comparisons)}** slučajeva. Isti zaokruženi cent: **{exact}/{len(comparisons)}**. Apsolutna razlika najviše 0,10 USD: **{small}/{len(comparisons)}**. Zadnja vrijednost je dijagnostička skala, ne tvrdnja potpune jednakosti.", "",
             "Saldo na presjeku čita se iz Pine tablice `Cutoff equity`. Izvorni `open_pl` može uključivati današnju cijenu i nije korišten. `metrics.total_trades` je broj zatvorenih trgovina; `trades.trade_count` je broj dohvaćenih redaka naloga, pa se ne smiju zamijeniti.", "",
             "| Dionica | Početak | Pravilo | Zatvorene TV / Python | TV saldo USD | Python saldo USD | Razlika USD | Isti cent |", "|---|---|---|---:|---:|---:|---:|---|"]
    for row in comparisons:
        start = "2022-01-01" if row["period"] == "SINCE_2022" else "2022-12-01"
        lines.append(f"| {row['ticker']} | {start} | {row['mode']} | {row['tv_closed']} / {row['python_closed']} | {row['tv_cutoff_equity_usd']:.2f} | {row['python_cutoff_equity_usd']:.5f} | {row['delta_usd']:+.5f} | {'da' if row['rounded_cent_equal'] else 'ne'} |")
    lines += ["", "## Datumi i redoslijed trgovina", "",
              "Dostupni MCP izvodi sadrže posljednjih 20 kupnji/prodaja; i zahtjev max_trades=300 vratio je samo 20. `time_index` je redni indeks; nije dokaz kalendarskog datuma. Skripta uspoređuje redoslijed kupnji/prodaja, količine i izvršene cijene bez provizije s istim završnim nizom lokalnih akcija. Bez eksplicitnih datuma iz TV-a ne tvrdi se podudaranje datuma. Detaljne razlike cijena i statusi su u JSON-u.", "",
              "## Obuhvat i nevaljana snimanja", "",
              f"Nedostaje {len(missing)} slučajeva. Odbačeno je {len(rejected)} snimanja bez potpune ili dosljedne tablice/metrika. Pri ponovljenim valjanim snimanjima koristi se najnovije prema vremenu; prethodna se ne brišu."]
    for rejected_row in rejected:
        lines.append(f"- {rejected_row['source']} redak {rejected_row['source_row']}: {rejected_row['ticker']} / {rejected_row['mode']} / {rejected_row['period']}: {rejected_row['reason']}.")
    if missing:
        lines += ["", "Još nedostaju: " + "; ".join(f"{x['ticker']} {x['mode']} {x['period']}" for x in missing) + "."]
    lines += ["", "## Granica zaključka", "",
              "Mali centni nesklad može potjecati od cijene zaokružene na tick, provizijske osnovice ili ulaznih podataka; uzrok nije dokazan samom malom razlikom. Veće razlike WDC salda ostaju nerazriješene; razlike pružatelja i prilagodbi korporativnih akcija mogući su uzroci, ne potvrđeni zaključak. Jednak broj trgovina nije dokaz jednakosti njihovih cijena. Native broker-emulator i lokalni OHLC model nisu isti. Dobro slaganje potvrđuje tehničku reprodukciju, a ne buduću profitabilnost. C29 i C30 ostaju FAIL.", "",
              "Ponovno osvježavanje nakon novih batch datoteka: `.venv/bin/python scripts/compare_c13c_tradingview_20261009.py`.", ""]
    (REPORTS / "TRADINGVIEW_COMPARISON.md").write_text("\n".join(lines))
    print(json.dumps({"valid": len(comparisons), "expected": 30, "closed_equal": all_closed,
                      "cent_equal": exact, "within_10c": small, "rejected_captures": len(rejected), "input_errors": input_errors}))


if __name__ == "__main__":
    run()
