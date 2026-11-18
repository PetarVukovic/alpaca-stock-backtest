"""Red-team audit runner: reproduce lane A trades independently and write redteam_audit.json.

Run: .venv/bin/python -m lab.research.redteam.audit
Reads frozen specs, reports/backtest/*_critic_inputs.json, *_audit.json and the canonical CSVs.
Writes reports/research/redteam_audit.json and reports/research/redteam_numbers.json (evidence).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from lab.research.redteam import probes
from lab.research.redteam.reimpl import (
    ROOT,
    CostModel,
    hourly,
    run_basket,
    run_rotation,
    run_single,
)

TOL_PP = 0.01  # tolerance in percentage points per trade
BACKTEST = ROOT / "reports/backtest"
OUT = ROOT / "reports/research"


# Findings from this audit; evidence numbers are in reports/research/redteam_numbers.json.
FINDINGS = [
    {
        "severity": "high",
        "open": True,
        "text": (
            "Holdout contamination (process, lane C, not engine): H5A/H5B were chosen from "
            "reports/research/day_behaviour.md, whose WDC 'first 30 min -> rest of day' test pooled all 2701 days "
            "incl. 2024+ and selected it because the sign held in IS, WF AND HO (r HO -0.085); H4A cites the same "
            "study (MU gap r HO 0.072). HO is therefore not untouched for H5A/H5B/H4A; Critic checks 5 and 13 "
            "must treat their HO as seen."
        ),
    },
    {
        "severity": "high",
        "open": True,
        "text": (
            "Boom/concentration: every dip/trend result depends on a handful of trades. Removing the 5 best WF "
            "trades per ticker makes WF mean negative for all 22 ticker rows of B2, C13A/B/C, C14A/B, C20A "
            "(e.g. C13C STX +4.95 -> -3.61 %/trade, C13A STX +2.81 -> -0.17, B2 STX +2.99 -> -4.30). Pooled over "
            "IS+WF+HO, ex-top-10 is negative everywhere except C13A (MU +0.06, WDC +0.34, STX +0.67 %/trade); "
            "WF ex-top-3 stays positive only for C13A WDC (+0.03) and STX (+0.76). "
            "Not an engine bug; it changes how 'Istrazivacki kandidat' rows must be read."
        ),
    },
    {
        "severity": "medium",
        "open": True,
        "text": (
            "LEAGUE_TABLE (lab/run_all.py:511-540, explanation() at :87-101): 'WF prosjek' is mean return PER "
            "TRADE and is ranked across rows where B1/B3 have one 3-year trade (MU 11.56 %, STX 42.53 %) and day "
            "trades have 169-753 trades. H4B shows -0.07..-0.14 %/trade while its WF account fell -42 % (MU), "
            "-54 % (STX), -65 % (WDC). Benchmarks get the label 'Premalo provjera ... prava prednost nije "
            "dokazana', which is the wrong message for a benchmark. Expected: column named 'po trgovini', plus "
            "WF total account change, time in market and same-period buy-and-hold total; B1/B3 rows labelled "
            "as benchmark; basket/rotation sleeves (B3 MU/WDC/STX, C16 per-ticker) marked as sleeves."
        ),
    },
    {
        "severity": "medium",
        "open": True,
        "text": (
            "Label fragility (lab/run_all.py:93-100): 'Istrazivacki kandidat' vs 'nije bolji od kupi-i-drzi' "
            "flips on WF Sharpe vs buy-and-hold Sharpe only. B2_TREND200 WDC and C20A WDC have identical trades "
            "(n=12, win 25 %, mean 0.856 %) but Sharpe 0.192 vs 0.251 against BH 0.216, so one is 'kandidat' "
            "and the other is not. A beginner can read 'kandidat' as a promising edge."
        ),
    },
    {
        "severity": "medium",
        "open": True,
        "text": (
            "Hourly half-day sessions: data/hourly/*_1h_clean.csv labels 13:00-16:00 ET bars on early-close days "
            "as 'regular' (e.g. MU 2019-11-29 14:00 bar 13 prints, 15:00 bar 3 prints). lab/engine.py:137-140 "
            "closes day trades at the 15:00 bar close, i.e. an after-hours print, and missing_session_close never "
            "fires. Affected: H4A MU/WDC/STX 5/3/3 trades, H4B 21/8/11. fill_violations (run_all.py:427) reports 0 "
            "for these. Expected: hourly session_end from the official calendar (the 5-min CSV already has a "
            "correct session_end at 12:55) and exit at the real close."
        ),
    },
    {
        "severity": "medium",
        "open": True,
        "text": (
            "Rule vs hypothesis mismatch for hourly day trades: registry.py:228-230 measures the 'gap' from the "
            "first REGULAR hourly bar open = 10:00 ET (09:30-10:00 is open_mixed and excluded), not the 09:30 "
            "opening print; median |10:00 open - 09:00 bar open| is 0.92 % and >0.5 % on 70 % of MU days, so "
            "H4A tests 'price at 10:00 >= 1 % over yesterday's close', not 'opened >= 1 % higher'. H4B "
            "(last_hour, registry.py:225) buys every day with no direction filter, although its hypothesis is "
            "'continuation of the day's direction', and trades the 15:00-16:00 bar while the text says 14-15 ET. "
            "No lookahead, but a FAIL/PASS would not answer the stated hypothesis."
        ),
    },
    {
        "severity": "medium",
        "open": True,
        "text": (
            "Price-only data, no dividends (flag price_only_no_dividends, not shown in LEAGUE_TABLE): buy-and-hold "
            "of dividend payers (notably STX) is understated vs strategies that are in the market 8-60 % of the "
            "time. The size was not quantified because dividends are not in local data."
        ),
    },
    {
        "severity": "medium",
        "open": True,
        "text": (
            "Selection/survivorship: the universe MU/WDC/STX was chosen in 2026 knowing they were the memory "
            "winners (MU ~74x since 2016). Every result is conditional on that hindsight choice. Cannot be fixed "
            "in the engine; must be stated next to results."
        ),
    },
    {
        "severity": "low",
        "open": True,
        "text": (
            "buy_hold enters at the open of the SECOND bar of each period (signal on bar 1 close -> next open; "
            "registry.py:150 + engine t+1). WF buy-and-hold is therefore WDC -0.55 % (close-to-close would be "
            "-5.45 %), STX +42.6 % (vs +37.3 %), MU +11.6 % (vs +13.5 %). Consistent with the rule, but the "
            "benchmark is not the conventional one; document it."
        ),
    },
    {
        "severity": "low",
        "open": True,
        "text": (
            "Stop/target anchor is the cost-inclusive entry fill (engine.py:115), not the raw open; README does not "
            "define the anchor. Effect ~2.5 bps + 1 tick per trade; document it in lab/strategies/README.md."
        ),
    },
    {
        "severity": "low",
        "open": True,
        "text": (
            "K differs across Critic packages: 19 packages have k=65, H5A/H5B have k=67 (selected run). The Critic "
            "should use the current ledger K, not the per-package value."
        ),
    },
    {
        "severity": "low",
        "open": True,
        "text": (
            "ROTATION buy_hold_sharpe is MU only (flag benchmark_first_universe_ticker); a fair benchmark for a "
            "3-stock rotation is the equal basket over the same dates."
        ),
    },
    {
        "severity": "low",
        "open": False,
        "text": (
            "Lookahead hunt: no leak found. Independent probes on the engine pass: entry at t+1 open with exact "
            "cost, trailing uses previous-bar peak, stop beats target in the same bar, gap through stop fills at "
            "the open, hold_bars counts the entry bar, vol sizing ignores the entry bar, period boundary closes at "
            "the last close and does not carry signals, x7 corrupted future at 16 extra cuts (C13A/C15A/C17A/C18A "
            "on STX) leaves earlier signals and closed trades unchanged. WDC spin-off applied once (ratio "
            "0.681320 +-1e-8 before 2025-02-24, 1.0 after); hourly vs daily close differ <0.03 % median, no day "
            ">2 %; data hashes in all packages still match the CSVs."
        ),
    },
]


def frozen_specs() -> dict[str, dict]:
    specs = {}
    for path in sorted((ROOT / "strategies/frozen").glob("2026-10-05_*.json")):
        spec = json.loads(path.read_text())
        spec["_path"] = str(path.relative_to(ROOT))
        specs[spec["id"]] = spec
    return specs


def compare(engine: list[float], mine: list[float]) -> dict:
    same_n = len(engine) == len(mine)
    diff = (
        float(np.max(np.abs(np.array(engine) - np.array(mine))))
        if same_n and engine
        else 0.0
    )
    return {
        "n_engine": len(engine),
        "n_mine": len(mine),
        "n_match": same_n,
        "max_abs_diff_pp": diff if same_n else None,
    }


def reproduce(spec: dict, package: dict, stress: float = 1.0) -> dict:
    key = "returns" if stress == 1.0 else "stressed_returns"
    cost = CostModel(stress=stress)
    rows = {}
    for ticker in spec["universe"]:
        books = run_single(spec, ticker, cost=cost)
        for period, book in books.items():
            mine = [t.net * 100 for t in book.trades]
            rows[f"{ticker}/{period}"] = compare(package[key][ticker][period], mine)
    if spec["entry"]["type"] == "relative_strength" and stress == 1.0:
        for period, book in run_rotation(spec, cost).items():
            mine = [t.net * 100 for t in book.trades]
            rows[f"ROTATION/{period}"] = compare(
                package["portfolio_returns"]["ROTATION"][period], mine
            )
    if spec["entry"]["type"] == "equal_basket" and stress == 1.0:
        basket, _ = run_basket(spec)
        for period, values in basket.items():
            rows[f"BASKET/{period}"] = compare(
                package["portfolio_returns"]["BASKET"][period],
                [v * 100 for v in values],
            )
    return rows


def vol_size_check(spec: dict) -> dict:
    """C20A: compare per-trade notional (sizing) with the engine audit trades."""
    out = {}
    for ticker in spec["universe"]:
        audit = json.loads((BACKTEST / f"{spec['id']}_{ticker}_audit.json").read_text())
        books = run_single(spec, ticker)
        for period, book in books.items():
            eng = [t["notional_usd"] for t in audit[period]["trades"]]
            mine = [t.notional for t in book.trades]
            out[f"{ticker}/{period}"] = (
                float(np.max(np.abs(np.array(eng) - np.array(mine))))
                if len(eng) == len(mine) and eng
                else None
            )
    return out


def boom_effect(package: dict, universe: list[str]) -> dict:
    """Mean per-trade return with the 5 and 10 best trades per ticker removed (all periods pooled + WF)."""
    out = {}
    for ticker in universe:
        pooled = sorted(
            v for p in ("IS", "WF", "HO") for v in package["returns"][ticker][p]
        )
        wf = sorted(package["returns"][ticker]["WF"])
        row = {
            "n_all": len(pooled),
            "mean_all": float(np.mean(pooled)) if pooled else None,
            "n_wf": len(wf),
            "mean_wf": float(np.mean(wf)) if wf else None,
        }
        for k in (3, 5, 10):
            row[f"mean_all_ex{k}"] = (
                float(np.mean(pooled[:-k])) if len(pooled) > k else None
            )
            row[f"mean_wf_ex{k}"] = float(np.mean(wf[:-k])) if len(wf) > k else None
        out[ticker] = row
    return out


def period_totals(strategy_id: str, ticker: str) -> dict:
    """Final equity / 500 - 1 per period and fraction of bars invested, from the engine audit file."""
    audit = json.loads((BACKTEST / f"{strategy_id}_{ticker}_audit.json").read_text())
    out = {}
    for p in ("IS", "WF", "HO"):
        eq = audit[p]["equity"]
        trades = audit[p]["trades"]
        total = eq[-1]["usd"] / 500 - 1 if eq else None
        days = pd.DatetimeIndex([e["timestamp"] for e in eq])
        invested = 0
        for t in trades:
            invested += (
                (days >= pd.Timestamp(t["entry_time"]))
                & (days <= pd.Timestamp(t["exit_time"]))
            ).sum()
        out[p] = {
            "total_pct": None if total is None else total * 100,
            "exposure": invested / len(days) if len(days) else None,
        }
    return out


def league_check(specs: dict) -> dict:
    """Parse LEAGUE_TABLE.md and compare rows with the BacktestResult JSON and with B&H WF totals."""
    text = (BACKTEST / "LEAGUE_TABLE.md").read_text()
    rows = re.findall(
        r"^\| (\S+) \| (\S+) \| (\d+) \| (nema|-?[\d.]+ %) \| (.+?) \|$",
        text,
        re.MULTILINE,
    )
    mismatch, compared = [], []
    bh = {
        t: period_totals("B1_BUY_HOLD", t)["WF"]["total_pct"]
        for t in ("MU", "WDC", "STX", "SMH")
    }
    for sid, ticker, n, mean, label in rows:
        res = json.loads((BACKTEST / f"{sid}_{ticker}.json").read_text())
        wf = res["periods"]["WF"]
        shown = None if mean == "nema" else float(mean.split()[0])
        if wf["n"] != int(n) or (
            shown is not None and abs(round(wf["mean_pct"], 3) - shown) > 1e-9
        ):
            mismatch.append([sid, ticker])
        if ticker in bh and not sid.startswith("B1") and not sid.startswith("B3"):
            tot = period_totals(sid, ticker)["WF"]
            compared.append(
                {
                    "id": sid,
                    "ticker": ticker,
                    "wf_mean_per_trade_pct": shown,
                    "label": label,
                    "wf_total_pct": tot["total_pct"],
                    "wf_exposure": tot["exposure"],
                    "bh_wf_total_pct": bh[ticker],
                }
            )
    return {
        "rows": len(rows),
        "mismatches": mismatch,
        "vs_buy_hold": compared,
        "bh_wf_total_pct": bh,
    }


def _sharpe(changes: pd.Series) -> float | None:
    x = changes.dropna()
    if len(x) < 2 or x.std(ddof=1) == 0:
        return None
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


def metrics_check() -> dict:
    """Recompute PeriodStats from the engine audit (trades + equity) and compare with BacktestResult."""
    worst: dict[str, float] = defaultdict(float)
    checked = 0
    for res_path in BACKTEST.glob("*_*.json"):
        if res_path.name.endswith(("_audit.json", "_critic_inputs.json")):
            continue
        audit_path = res_path.with_name(res_path.stem + "_audit.json")
        if not audit_path.exists():
            continue
        res = json.loads(res_path.read_text())
        audit = json.loads(audit_path.read_text())
        for p, stats in res["periods"].items():
            trades = audit[p]["trades"]
            eq = pd.Series(
                [e["usd"] for e in audit[p]["equity"]],
                index=pd.DatetimeIndex([e["timestamp"] for e in audit[p]["equity"]]),
            )
            r = np.array([t["net_return"] for t in trades])
            day = eq.groupby(eq.index.strftime("%Y-%m-%d")).last()
            ch = day.pct_change()
            if len(ch):
                ch.iloc[0] = day.iloc[0] / 500 - 1
            mine = {
                "n": len(r),
                "mean_pct": r.mean() * 100 if len(r) else None,
                "win_rate": (r > 0).mean() if len(r) else None,
                "sharpe": _sharpe(ch),
                "max_dd_pct": float((eq / eq.cummax().clip(lower=500) - 1).min() * 100)
                if len(eq)
                else None,
            }
            for k, v in mine.items():
                if v is None or stats.get(k) is None:
                    if (v is None) != (stats.get(k) is None):
                        worst[k] = float("inf")
                    continue
                worst[k] = max(worst[k], abs(float(v) - float(stats[k])))
        checked += 1
    return {"results_checked": checked, "max_abs_diff": dict(worst)}


def provenance_check() -> dict:
    """Do the data hashes recorded at run time still match the CSVs on disk?"""
    stale = {}
    for path in BACKTEST.glob("*_critic_inputs.json"):
        prov = json.loads(path.read_text())["provenance"]
        folder = {"daily": ("ohlcv", "1d")}
        for ticker, digest in prov["data_sha256"].items():
            for sub, suf in [
                folder["daily"],
                ("hourly", "1h_clean"),
                ("intraday", "5m_clean"),
            ]:
                f = ROOT / f"data/{sub}/{ticker}_{suf}.csv"
                if f.exists() and hashlib.sha256(f.read_bytes()).hexdigest() == digest:
                    break
            else:
                stale.setdefault(prov["freeze_file"], []).append(ticker)
    return stale


def half_day_fills() -> dict:
    """Hourly day trades that filled on 13:00-16:00 ET bars of half-day sessions (after-hours prints)."""
    out = {}
    for sid in ("H4A_GAP_UP_CONT", "H4B_LAST_HOUR"):
        for ticker in ("MU", "WDC", "STX"):
            h = hourly(ticker)
            thin_days = set(h[(h.ny_hour >= 13) & (h.trades < 1000)].day)
            audit = json.loads((BACKTEST / f"{sid}_{ticker}_audit.json").read_text())
            hits = []
            for p in ("IS", "WF", "HO"):
                for t in audit[p]["trades"]:
                    ts = pd.Timestamp(t["exit_time"]).tz_convert("America/New_York")
                    if ts.strftime("%Y-%m-%d") in thin_days and ts.hour >= 13:
                        hits.append(
                            [
                                p,
                                ts.strftime("%Y-%m-%d"),
                                round(t["net_return"] * 100, 3),
                            ]
                        )
            out[f"{sid}/{ticker}"] = {"n": len(hits), "examples": hits[:5]}
    return out


def main() -> None:
    specs = frozen_specs()
    numbers: dict = {
        "reproduction": {},
        "stressed": {},
        "boom": {},
        "missing_engine_output": [],
    }
    by_type: dict[str, list] = defaultdict(list)
    for sid, spec in specs.items():
        pkg_path = BACKTEST / f"{sid}_critic_inputs.json"
        if not pkg_path.exists():
            numbers["missing_engine_output"].append(sid)
            continue
        package = json.loads(pkg_path.read_text())
        rows = reproduce(spec, package)
        numbers["reproduction"][sid] = rows
        numbers["stressed"][sid] = reproduce(spec, package, stress=2.0)
        label_entry = spec["entry"]["type"]
        if label_entry == "day_trade":
            label_entry = f"day_trade:{spec['entry'].get('mode')}"
        for key in {label_entry, f"exit:{spec['exit']['type']}"}:
            by_type[key].append((sid, rows, numbers["stressed"][sid]))
        if spec["entry"]["type"] in {"dip_in_trend", "trend"}:
            numbers["boom"][sid] = boom_effect(package, spec["universe"])
        if "size_vol_target" in spec["entry"]:
            numbers["vol_size_notional_max_diff_usd"] = vol_size_check(spec)
    numbers["league"] = league_check(specs)
    numbers["metrics"] = metrics_check()
    numbers["stale_data_hashes"] = provenance_check()
    numbers["half_day_fills"] = half_day_fills()
    numbers["probes"] = probes.run_all()
    numbers["wdc_spinoff"] = probes.wdc_spinoff()
    numbers["daily_vs_hourly"] = probes.daily_vs_hourly()

    rule_types = {}
    ordered = sorted(by_type.items(), key=lambda kv: (kv[0].startswith("exit:"), kv[0]))
    for key, entries in ordered:
        diffs, n_ok, notes = [], True, []
        for sid, rows, stressed in entries:
            for cell, r in {
                **rows,
                **{f"2x:{k}": v for k, v in stressed.items()},
            }.items():
                n_ok &= r["n_match"]
                if r["max_abs_diff_pp"] is not None:
                    diffs.append(r["max_abs_diff_pp"])
                if not r["n_match"]:
                    notes.append(f"{sid} {cell}: n {r['n_engine']} vs {r['n_mine']}")
        worst = max(diffs) if diffs else 0.0
        ids = sorted({e[0] for e in entries})
        name = key.removeprefix("exit:")
        if key.startswith("exit:") and name in rule_types:
            name = f"exit_{name}"
        rule_types[name] = {
            "reproduced": bool(n_ok and worst <= TOL_PP),
            "max_abs_diff_pct": worst,
            "n_trades_match": bool(n_ok),
            "notes": (
                f"{'exit' if key.startswith('exit:') else 'entry'} type; ids {', '.join(ids)}; "
                f"cost 1x and 2x, all tickers/periods"
                + ("" if n_ok else "; " + "; ".join(notes[:5]))
            ),
        }
    numbers["rule_types"] = rule_types
    (OUT / "redteam_numbers.json").write_text(
        json.dumps(numbers, indent=2, default=str)
    )
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule_types": rule_types,
        "engine_findings": FINDINGS,
    }
    (OUT / "redteam_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n"
    )
    ml1_path = OUT / "redteam_ml1.json"
    if ml1_path.exists():  # keep the ML1 section written by lab.research.redteam.ml1
        from lab.research.redteam.ml1 import merge_audit

        merge_audit(json.loads(ml1_path.read_text()))
    print(json.dumps(rule_types, indent=2))


if __name__ == "__main__":
    main()
