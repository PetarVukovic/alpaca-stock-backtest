"""Black-box lookahead/execution probes against lane A's engine (the subject under test).

Unlike reimpl.py this module DOES call lab.engine, on purpose: each probe builds a tiny synthetic
price path where a leak or an off-by-one would produce a different, checkable number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lab.contracts import FrozenStrategy
from lab.engine import backtest, simulate
from lab.research.redteam.reimpl import ROOT, daily, hourly


def _strategy(entry: dict, exit_rule: dict, timeframe: str = "daily") -> FrozenStrategy:
    return FrozenStrategy(
        id="RT_PROBE",
        created="2026-10-05",
        family="other",
        hypothesis="probe",
        mechanism="probe",
        persistence="probe",
        universe=["MU"],
        timeframe=timeframe,
        entry=entry,
        exit=exit_rule,
    )


def _frame(
    rows: list[tuple], start: str = "2021-03-01", freq: str = "B"
) -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1e6
    df["date"] = idx.strftime("%Y-%m-%d")
    df.attrs.update(ticker="MU", timeframe="daily")
    return df


def _sig(df: pd.DataFrame, true_at: list[int]) -> pd.Series:
    s = pd.Series(False, index=df.index)
    s.iloc[true_at] = True
    return s


def probe_entry_next_open() -> dict:
    df = _frame(
        [
            (100, 101, 99, 100),
            (110, 111, 109, 110),
            (120, 121, 119, 120),
            (130, 131, 129, 130),
        ]
    )
    sim = simulate(
        df, _sig(df, [0]), _sig(df, []), _strategy({"type": "trend"}, {"type": "hold"})
    )
    t = sim.trades[0]
    expected = 110 + 110 * 5 / 20000 + 0.01
    ok = (
        t["entry_time"].startswith(str(df.index[1].date()))
        and abs(t["entry_price"] - expected) < 1e-9
    )
    return {
        "ok": bool(ok),
        "entry_time": t["entry_time"],
        "entry_price": t["entry_price"],
        "expected": expected,
    }


def probe_trailing_uses_prior_peak() -> dict:
    # Bar 2 makes a new high 130 and dips to 116: new trail would be 117 (10 %), old trail 99 (peak 110).
    df = _frame(
        [
            (100, 100, 100, 100),
            (110, 110, 110, 110),
            (110, 130, 116, 125),
            (125, 126, 124, 125),
        ]
    )
    sim = simulate(
        df,
        _sig(df, [0]),
        _sig(df, []),
        _strategy({"type": "trend"}, {"type": "trailing", "trailing_pct": 0.1}),
    )
    reasons = [t["reason"] for t in sim.trades]
    return {"ok": reasons == ["period_end"], "reasons": reasons}


def probe_stop_beats_target_same_bar() -> dict:
    df = _frame(
        [
            (100, 100, 100, 100),
            (100, 100, 100, 100),
            (100, 120, 80, 100),
            (100, 100, 100, 100),
        ]
    )
    sim = simulate(
        df,
        _sig(df, [0]),
        _sig(df, []),
        _strategy(
            {"type": "trend"}, {"type": "risk", "stop_pct": 0.1, "target_pct": 0.1}
        ),
    )
    return {"ok": sim.trades[0]["reason"] == "stop", "reason": sim.trades[0]["reason"]}


def probe_gap_through_stop() -> dict:
    df = _frame(
        [(100, 100, 100, 100), (100, 100, 100, 100), (80, 85, 79, 84), (84, 84, 84, 84)]
    )
    sim = simulate(
        df,
        _sig(df, [0]),
        _sig(df, []),
        _strategy({"type": "trend"}, {"type": "risk", "stop_pct": 0.1}),
    )
    t = sim.trades[0]
    expected = 80 - 80 * 5 / 20000 - 0.01
    return {
        "ok": t["reason"] == "stop_gap" and abs(t["exit_price"] - expected) < 1e-9,
        "reason": t["reason"],
        "exit_price": t["exit_price"],
    }


def probe_hold_bars_count() -> dict:
    rows = [(100 + i, 100 + i, 100 + i, 100 + i) for i in range(8)]
    df = _frame(rows)
    sim = simulate(
        df,
        _sig(df, [0]),
        _sig(df, []),
        _strategy({"type": "trend"}, {"type": "risk", "hold_bars": 3}),
    )
    t = sim.trades[0]
    # Entry at open of bar 1, held bars 1,2,3, exit at open of bar 4.
    return {
        "ok": t["exit_time"].startswith(str(df.index[4].date())),
        "exit_time": t["exit_time"],
    }


def probe_vol_size_ignores_entry_bar() -> dict:
    rng = np.random.default_rng(7)
    closes = 100 * np.cumprod(1 + rng.normal(0, 0.03, 40))
    rows = [(c, c * 1.01, c * 0.99, c) for c in closes]
    df = _frame(rows)
    strat = _strategy({"type": "trend", "size_vol_target": 0.01}, {"type": "hold"})
    a = simulate(df, _sig(df, [30]), _sig(df, []), strat).trades[0]["notional_usd"]
    df2 = df.copy()
    df2.iloc[31:, df2.columns.get_indexer(["close", "high"])] *= (
        3  # entry bar close and later
    )
    b = simulate(df2, _sig(df2, [30]), _sig(df2, []), strat).trades[0]["notional_usd"]
    return {
        "ok": bool(abs(a - b) < 1e-9),
        "notional_original": a,
        "notional_future_tampered": b,
    }


def probe_period_boundary() -> dict:
    """Signal on the last IS bar must not open a WF trade; IS position is closed at the IS close."""
    idx = pd.to_datetime(
        ["2020-12-29", "2020-12-30", "2020-12-31", "2021-01-04", "2021-01-05"], utc=True
    )
    df = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [100, 101, 102, 103, 104],
            "low": [100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104],
            "volume": 1e6,
        },
        index=idx,
        dtype=float,
    )
    df["date"] = idx.strftime("%Y-%m-%d")
    df.attrs.update(ticker="MU", timeframe="daily")
    strat = _strategy({"type": "buy_hold"}, {"type": "hold"})
    _, sims = backtest(df, strat, "MU")
    is_t, wf_t = sims["IS"].trades, sims["WF"].trades
    ok = (
        len(is_t) == 1
        and is_t[0]["exit_time"].startswith("2020-12-31")
        and is_t[0]["reason"] == "period_end"
        and len(wf_t) == 1
        and wf_t[0]["entry_time"].startswith("2021-01-05")
    )
    return {
        "ok": bool(ok),
        "is": [(t["entry_time"][:10], t["exit_time"][:10]) for t in is_t],
        "wf": [(t["entry_time"][:10], t["exit_time"][:10]) for t in wf_t],
        "note": "buy_hold enters at the open of the 2nd bar of each period (first day skipped).",
    }


def _closed_before(sims: dict, cut: str) -> list:
    limit = pd.Timestamp(cut, tz="UTC")
    return [
        (t["entry_time"], round(t["net_return"], 12))
        for p in sims.values()
        for t in p.trades
        if pd.Timestamp(t["exit_time"]) < limit
    ]


def probe_corrupt_future_real_data() -> dict:
    """Independent cuts (not lane A's two): x7 OHLC after cut must not change trades closed before it."""
    from lab.strategies.registry import signals  # subject under test, black box

    results = []
    specs = {
        "C13A": (
            {
                "type": "dip_in_trend",
                "trend_window": 200,
                "dip_bars": 5,
                "dip_pct": 0.05,
            },
            {"type": "risk", "stop_pct": 0.08, "hold_bars": 10},
        ),
        "C15A": (
            {"type": "breakout", "lookback": 20},
            {"type": "trailing", "trailing_pct": 0.1},
        ),
        "C17A": (
            {
                "type": "volatility_breakout",
                "vol_window": 20,
                "lookback": 63,
                "compression": 0.8,
            },
            {"type": "trailing", "trailing_pct": 0.12},
        ),
        "C18A": (
            {
                "type": "volatility_shock",
                "vol_window": 20,
                "lookback": 63,
                "shock_multiplier": 2,
                "trend_window": 200,
            },
            {"type": "risk", "stop_pct": 0.1, "hold_bars": 10},
        ),
    }
    base = daily("STX").copy()
    frame = base.drop(columns=["day"]).assign(date=base["day"])
    frame.index = frame.index.tz_localize("UTC")
    frame.attrs.update(ticker="STX", timeframe="daily")
    for name, (entry, exit_rule) in specs.items():
        strat = _strategy(entry, exit_rule)
        for cut in ("2018-06-01", "2020-03-16", "2022-10-03", "2025-04-07"):
            bad = frame.copy()
            mask = bad.index >= pd.Timestamp(cut, tz="UTC")
            bad.loc[mask, ["open", "high", "low", "close"]] *= 7
            bad.attrs.update(frame.attrs)
            e1, x1 = signals(frame, strat)
            e2, x2 = signals(bad, strat)
            sig_ok = e1[~mask].equals(e2[~mask]) and x1[~mask].equals(x2[~mask])
            _, s1 = backtest(frame, strat, "STX")
            _, s2 = backtest(bad, strat, "STX")
            results.append(
                {
                    "rule": name,
                    "cut": cut,
                    "signals_ok": bool(sig_ok),
                    "closed_trades_ok": _closed_before(s1, cut)
                    == _closed_before(s2, cut),
                }
            )
    return {
        "ok": all(r["signals_ok"] and r["closed_trades_ok"] for r in results),
        "cases": results,
    }


def probe_hourly_gap_reference() -> dict:
    """Which open does the hourly 'gap' use? The 09:30 open is not in the regular hourly feed."""
    h = hourly("MU")
    first_hour = h.groupby("day")["ny_hour"].first().value_counts().to_dict()
    raw = pd.read_csv(ROOT / "data/hourly/MU_1h_clean.csv")
    mixed = raw[raw.session == "open_mixed"].set_index("date_et")["open"]
    first_reg = h.groupby("day")["open"].first()
    shared = first_reg.index.intersection(mixed.index)
    diff = (first_reg.loc[shared] / mixed.loc[shared] - 1).abs()
    return {
        "first_regular_bar_ny_hour_counts": {
            int(k): int(v) for k, v in first_hour.items()
        },
        "median_abs_diff_10h_open_vs_9h_bar_open_pct": float(diff.median() * 100),
        "share_days_diff_gt_0_5pct": float((diff > 0.005).mean()),
    }


def wdc_spinoff() -> dict:
    d = daily("WDC").set_index("day")
    raw = pd.read_csv(ROOT / "data/ohlcv/WDC_1d.raw_unadjusted_spinoff.csv")
    raw["day"] = raw["date"].astype(str).str[:10]
    raw = raw.set_index("day")
    pre = d.index[d.index < "2025-02-24"].intersection(raw.index)
    ratio = d.loc[pre, "close"] / raw.loc[pre, "close"]
    post = d.index[d.index >= "2025-02-24"].intersection(raw.index)
    post_ratio = (
        (d.loc[post, "close"] / raw.loc[post, "close"])
        if len(post)
        else pd.Series(dtype=float)
    )
    ret = d["close"].pct_change()
    return {
        "pre_ratio_min": float(ratio.min()),
        "pre_ratio_max": float(ratio.max()),
        "post_ratio_median": float(post_ratio.median()) if len(post_ratio) else None,
        "ret_2025_02_24_pct": float(ret.loc["2025-02-24"] * 100),
    }


def daily_vs_hourly() -> dict:
    out = {}
    for t in ("MU", "WDC", "STX"):
        h = hourly(t)
        last = h[h.ny_hour == 15].groupby("day")["close"].last()
        d = daily(t).set_index("day")["close"]
        shared = last.index.intersection(d.index)
        rel = (last.loc[shared] / d.loc[shared] - 1).abs()
        years = rel.groupby(rel.index.str[:4]).median().mul(100).round(4).to_dict()
        out[t] = {
            "median_abs_diff_pct_by_year": years,
            "days_gt_2pct": int((rel > 0.02).sum()),
            "worst_days": rel.nlargest(3).mul(100).round(3).to_dict(),
        }
    return out


def run_all() -> dict:
    probes = [
        probe_entry_next_open,
        probe_trailing_uses_prior_peak,
        probe_stop_beats_target_same_bar,
        probe_gap_through_stop,
        probe_hold_bars_count,
        probe_vol_size_ignores_entry_bar,
        probe_period_boundary,
        probe_corrupt_future_real_data,
        probe_hourly_gap_reference,
    ]
    return {p.__name__: p() for p in probes}
