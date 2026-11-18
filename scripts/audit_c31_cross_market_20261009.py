"""Audit saved TradingView MCP C31 exports. Read-only market/broker access: none."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/research/C31_CROSS_MARKET_20261009"
SYMBOLS = ["EURUSD", "GBPUSD", "BTCUSDT_PERP"]
CASES = ["BASE_ALL", "BASE_WF", "BASE_HO_SEEN", "STRESS_ALL"]


def unpack(value):
    return json.loads(next(c["text"] for c in value["content"] if c["type"] == "text"))


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()


def round_tick(value, tick):
    return math.floor(value / tick + .5 + 1e-9) * tick


def parse_case(path):
    raw = json.loads(path.read_text())
    tables = unpack(raw["tables"])["studies"][0]["tables"]
    lines = tables[0]["rows"][0].strip().splitlines()
    head = lines[0].split("|")
    fields = {}
    for line in lines[1:3]:
        parts = line.split("|")
        fields.update(dict(zip(parts[::2], parts[1::2])))
    trades, opened = [], None
    for line in tables[1]["rows"][1:]:
        parts = line.split("|")
        if parts[0] == "OPEN":
            opened = dict(entry_ms=int(parts[1]), entry=float(parts[2]), qty=float(parts[3]))
        else:
            trades.append(dict(index=int(parts[0]), entry_ms=int(parts[1]), exit_ms=int(parts[2]),
                               entry=float(parts[3]), exit=float(parts[4]), qty=float(parts[5]),
                               pnl=float(parts[6]), commission=float(parts[7])))
    plot = unpack(raw["plot"])["result"]
    inputs = plot["inputs"]
    start, cutoff = inputs["in_0"] / 1000, int(fields["cutoff_ms"]) / 1000
    curve = [r for r in plot["plots"] if start <= r[0] < cutoff]
    assert curve and len(curve) == int(fields["bars"]), (path.name, len(curve), fields)
    assert len(trades) == int(fields["closed"])
    assert bool(opened) == bool(int(fields["open"]))
    assert inputs["in_2"] == 10000 and inputs["in_4"] == 90
    assert inputs["in_12"] == inputs["in_13"] == 100
    fee = .001 if "STRESS" in path.name else .0005
    assert abs(inputs["in_7"] / 100 - fee) < 1e-12
    peak, dd = 10000., 0.
    for row in curve:
        peak = max(peak, row[3])
        dd = max(dd, 100 * (1 - row[3] / peak))
    assert abs(curve[-1][3] - float(fields["equity"])) < 1e-6
    assert abs(dd - float(fields["dd_close_pct"])) < 1e-6
    end_years = {int(s.split("|")[0]): float(s.split("|")[1]) for s in lines[4:]}
    annual, previous = {}, 10000.
    for year, value in end_years.items():
        if not math.isfinite(value):
            continue
        annual[year] = (value / previous - 1) * 100
        previous = value
    return dict(symbol=head[1], currency=head[2], pointvalue=float(head[3]), tick=float(head[4]),
                fields=fields, inputs=inputs, start=start, cutoff=cutoff, curve=curve,
                trades=trades, opened=opened, fee=fee, final=curve[-1][3], drawdown=dd,
                annual=annual, native=unpack(raw["metrics"])["metrics"])


def audit_case(case, bars):
    by_time = {r[0]: r for r in bars}
    bar_index = {r[0]: i for i, r in enumerate(bars)}
    signals = []
    for i, bar in enumerate(bars):
        if i < 199 or not (case["start"] <= bar[0] < case["cutoff"]):
            continue
        ma = sum(r[4] for r in bars[i - 199:i + 1]) / 200
        if bar[4] > ma and bar[4] / bars[i - 5][4] - 1 <= -.05:
            signals.append(bar[0])
    assert len(signals) == int(case["fields"]["signals"])
    entries, exits = defaultdict(list), defaultdict(list)
    all_trades = list(case["trades"])
    if case["opened"]:
        all_trades.append(case["opened"])
    signal_failures, stop_failures, volume_flags = [], [], []
    raw_exit_errors, pnl_errors = [], []
    for trade in all_trades:
        entry_t = trade["entry_ms"] / 1000
        entries[entry_t].append(trade)
        i = bar_index[entry_t]
        if bars[i - 1][0] not in signals:
            signal_failures.append(trade)
        if abs(trade["entry"] - round_tick(bars[i][1] + case["tick"], case["tick"])) > case["tick"] / 10:
            signal_failures.append({"entry_price_mismatch": trade})
        if "exit_ms" not in trade:
            continue
        exit_t = trade["exit_ms"] / 1000
        exits[exit_t].append(trade)
        pnl_errors.append(abs(trade["qty"] * (trade["exit"] - trade["entry"]) - trade["commission"] - trade["pnl"]))
        j = bar_index[exit_t]
        peak = (trade["entry"] - case["tick"]) * (1 + case["fee"]) + case["tick"]
        stop = math.floor(peak * .9 / case["tick"] + .5) * case["tick"]
        for k in range(i, j + 1):
            bar = bars[k]
            touched = bar[3] <= stop
            if touched:
                expected = round_tick(min(bar[1], stop) - case["tick"], case["tick"])
                if k != j:
                    stop_failures.append({"trade": trade["index"], "early_touch": iso(bar[0]), "exit": iso(exit_t)})
                raw_exit_errors.append(abs(expected - trade["exit"]))
                break
            if k == j:
                stop_failures.append({"trade": trade["index"], "exit_not_touched": iso(exit_t), "stop": stop})
            peak = max(peak, bar[2])
            stop = max(stop, math.floor(peak * .9 / case["tick"] + .5) * case["tick"])
        for k in [i, j]:
            vol = bars[k][5]
            if not vol or trade["qty"] / vol > .01:
                volume_flags.append({"trade": trade["index"], "time": iso(bars[k][0]), "volume": vol})
    cash, qty, max_difference = 10000., 0., 0.
    equity_outside_tick_rounding = []
    for row in case["curve"]:
        stamp = row[0]
        for trade in entries[stamp]:
            assert qty == 0
            qty = trade["qty"]
            cash -= qty * trade["entry"] * (1 + case["fee"])
        for trade in exits[stamp]:
            assert abs(qty - trade["qty"]) < 1e-9
            cash += qty * trade["exit"] * (1 - case["fee"])
            qty = 0.
        equity = cash + qty * by_time[stamp][4]
        max_difference = max(max_difference, abs(equity - row[3]))
        if abs(equity - row[3]) > abs(qty) * case["tick"] / 2 + 1e-6:
            equity_outside_tick_rounding.append(dict(time=iso(stamp), difference=equity-row[3]))
    return dict(signals=len(signals), checked_closed_trades=len(case["trades"]),
                reconstructed_equity_max_abs_difference=max_difference,
                trade_pnl_max_abs_difference=max(pnl_errors, default=0),
                stop_exit_price_max_abs_difference=max(raw_exit_errors, default=0),
                entry_failures=signal_failures, stop_failures=stop_failures, volume_flags=volume_flags,
                equity_outside_half_tick_tolerance=equity_outside_tick_rounding,
                final_equity_difference=abs(equity - case["final"]))


def main():
    results, audits, data_checks, curves = {}, {}, {}, {}
    for symbol in SYMBOLS:
        rows = [r["value"] for r in json.loads((OUT / f"RAW_{symbol}.json").read_text())["result"]["rows"]]
        failures = []
        for i, r in enumerate(rows):
            if any(not math.isfinite(x) or x <= 0 for x in r[1:5]) or r[2] < max(r[1], r[4]) or r[3] > min(r[1], r[4]) or (i and r[0] <= rows[i - 1][0]):
                failures.append(r)
        warmup = sum(r[0] < 1609459200 for r in rows)
        assert not failures and warmup >= 200
        data_checks[symbol] = dict(rows=len(rows), warmup_before_2021=warmup, errors=failures,
                                   first=iso(rows[0][0]), last_open=iso(rows[-1][0]),
                                   volume_type="exchange reported" if symbol.startswith("BTC") else "tick volume, not consolidated traded volume")
        for variant in CASES:
            name = f"{symbol}_{variant}"
            case = parse_case(OUT / f"{name}.json")
            audit = audit_case(case, rows)
            assert not audit["entry_failures"] and not audit["stop_failures"]
            assert not audit["volume_flags"] and not audit["equity_outside_half_tick_tolerance"]
            assert audit["trade_pnl_max_abs_difference"] < 1e-6
            assert audit["stop_exit_price_max_abs_difference"] < 1e-6
            audits[name] = audit
            curves[name] = case["curve"]
            years = (case["cutoff"] - case["start"]) / (86400 * 365.2425)
            result = {k: case[k] for k in ["symbol", "currency", "final", "drawdown", "annual", "native"]}
            result.update(return_pct=(case["final"] / 10000 - 1) * 100,
                          cagr_pct=((case["final"] / 10000) ** (1 / years) - 1) * 100,
                          closed_trades=len(case["trades"]), open_trades=int(case["fields"]["open"]),
                          signals=int(case["fields"]["signals"]), cutoff=iso(case["cutoff"]), bars=len(case["curve"]))
            startbar = next(r for r in rows if r[0] >= case["start"])
            endbar = next(r for r in reversed(rows) if r[0] < case["cutoff"])
            result["underlying_price_return_pct_before_any_cost"] = (endbar[4] / startbar[1] - 1) * 100
            results[name] = result
            with (OUT / f"{name}_equity.csv").open("w") as handle:
                writer = csv.writer(handle); writer.writerow(["bar_open_utc", "equity", "max_drawdown_pct"])
                writer.writerows((iso(r[0]), r[3], r[4]) for r in case["curve"])
            with (OUT / f"{name}_trades.csv").open("w") as handle:
                keys = ["index", "entry_ms", "exit_ms", "entry", "exit", "qty", "pnl", "commission"]
                writer = csv.DictWriter(handle, fieldnames=keys); writer.writeheader(); writer.writerows(case["trades"])
    truncations = {}
    for symbol in SYMBOLS:
        full = {r[0]: r[3] for r in curves[f"{symbol}_BASE_ALL"]}
        short = curves[f"{symbol}_BASE_WF"]
        diffs = [abs(r[3] - full[r[0]]) for r in short]
        truncations[symbol] = dict(cutoff="2024-01-01T00:00:00Z", compared_bars=len(diffs), max_equity_difference=max(diffs))
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in list(OUT.glob("RAW_*.json")) + list(OUT.glob("*_BASE_*.json")) + list(OUT.glob("*_STRESS_ALL.json"))
                + [ROOT / "strategies/frozen/2026-10-09_C31_C13C_CROSS_MARKET.json", Path(__file__),
                   ROOT / "scripts/tradingview/C31_C13C_cross_market_replica.pine",
                   ROOT / "scripts/tradingview/C31_C13C_cross_market_stress_replica.pine"]}
    output = dict(results=results, audit=audits, data=data_checks, truncation=truncations, sha256=manifest,
                  limitations=["Future-corruption of TradingView market feed not performed", "No tick path, bid/ask history, depth or real-fill reconciliation", "Funding and swap excluded", "Native contract rounding not verified against exchange/broker minimum trade sizes", "Daily close drawdown differs from native TradingView drawdown method", "Original 2016-2020 IS missing; no approval"])
    (OUT / "SUMMARY.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cases": len(results), "audits": {k: {x: len(y) if isinstance(y, list) else y for x, y in a.items()} for k, a in audits.items()}, "truncation": truncations}, indent=2))


if __name__ == "__main__":
    main()
