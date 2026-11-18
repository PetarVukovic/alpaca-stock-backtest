"""Engine for the C13C notebook: C13C, buy-and-hold and the pre-registered variants on all 43 chip stocks.

Research only: nothing here places orders or writes to the ledger (variants were registered by
``c13c_variants.register`` before this module was first run). Re-uses the swing simulator unchanged, so the
C13C numbers must equal ``swing/summary.json`` (checked in ``check_against_summary``).

    .venv/bin/python -m lab.aichain.c13c_nb_run   # writes results.json and sleeves.pkl in OUT
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import swing as S
from lab.aichain import swing_run as R
from lab.aichain.c13c_variants import ACCEPTANCE, VARIANTS, X4MomConfirm
from lab.aichain.contenders import C13CReentry
from lab.aichain.sim import (
    BASE_BPS,
    COMMON_END,
    START_CAPITAL,
    Bars,
    Cost,
    SleeveResult,
    stats,
    sum_sleeves,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "C13C_NOTEBOOK_20261014"
STOCK_GROUPS = [
    "memory",
    "mem_interface_storage",
    "equipment",
    "ai_chips_logic",
    "network_servers",
    "cloud",
]
WINDOWS: dict[str, tuple[str, str]] = {
    "ai_era": ("2023-01-01", COMMON_END),
    "h1": ("2023-01-01", "2024-12-31"),
    "h2": ("2025-01-01", COMMON_END),
    "y2016_2020": ("2016-01-01", "2020-12-31"),
    "y2021_2022": ("2021-01-01", "2022-12-31"),
    "full": ("2016-01-01", COMMON_END),
}
COST_MULT = {"1x": 1.0, "2x": 2.0}
MEMORY_CORE = ["MU", "WDC", "STX"]
MEMORY_WIDE = ["MU", "WDC", "STX", "RMBS", "SIMO", "MRAM", "NTAP"]
CONFIGS = ["C13C", "HOLD", *VARIANTS.keys(), "K7_REENTRY"]


def months_of(window: str) -> float:
    start, end = WINDOWS[window]
    return (pd.Timestamp(end) - pd.Timestamp(start)).days / 30.4375


class NbRunner:
    """Caches one sleeve per (config, ticker, window, cost multiple)."""

    def __init__(self) -> None:
        self.groups = R.peer_groups()
        self.segment_of = {t: g for g in STOCK_GROUPS for t in self.groups[g]}
        self.tickers = [t for g in STOCK_GROUPS for t in self.groups[g]]
        self.runner = R.Runner(self.groups)
        self.cache: dict[tuple[str, str, str, str], SleeveResult | None] = {}

    def bars(self, ticker: str) -> Bars:
        return self.runner.bars[ticker]

    def _rule(self, config: str, ticker: str) -> Any:
        if config == "C13C":
            return S.make_rule("W1_C13C_ORIG")
        if config == "HOLD":
            return S.make_rule("B0_BUYHOLD")
        if config == "K7_REENTRY":
            return C13CReentry()
        rule = VARIANTS[config]["cls"]()
        if isinstance(rule, X4MomConfirm):
            seg = self.groups[self.segment_of[ticker]]
            rule.peers = {t: self.bars(t) for t in seg}
        return rule

    def sleeve(
        self, config: str, ticker: str, window: str, mult: str = "1x"
    ) -> SleeveResult | None:
        key = (config, ticker, window, mult)
        if key not in self.cache:
            start, end = WINDOWS[window]
            cost = Cost(bps=BASE_BPS * COST_MULT[mult])
            self.cache[key] = S.run_swing_sleeve(
                self.bars(ticker), self._rule(config, ticker), start, end, cost
            )
        return self.cache[key]

    def sleeves(
        self, config: str, tickers: list[str], window: str, mult: str = "1x"
    ) -> list[SleeveResult]:
        got = [self.sleeve(config, t, window, mult) for t in tickers]
        return [g for g in got if g is not None]


def pooled(
    parts: list[SleeveResult], window: str
) -> dict[str, Any]:
    """Pooled result of equal 1.000 EUR sleeves: money curve statistics plus the swing trader's trade feel."""
    if not parts:
        return {"sleeves": 0}
    agg = sum_sleeves(parts)
    st = stats(agg, START_CAPITAL * len(parts))
    years = sum(max((p.dates[-1] - p.dates[0]).days, 1) / 365.25 for p in parts)
    trades = [t for p in parts for t in p.trades]
    tm = S.trade_metrics(trades, months_of(window), years)
    return {
        "sleeves": len(parts),
        "total_return": st["total_return"],
        "sharpe": st["sharpe"],
        "max_drawdown": st["max_drawdown"],
        "exposure_pct": st["exposure_pct"],
        "end_value_per_1000": st["end_value"] / len(parts),
        **tm,
    }


def one_ticker(res: SleeveResult | None) -> dict[str, Any] | None:
    if res is None:
        return None
    st = stats(res, START_CAPITAL)
    tm = S.trade_metrics(
        res.trades, 12.0, max((res.dates[-1] - res.dates[0]).days, 1) / 365.25
    )
    return {
        "first_bar": str(res.dates[0].date()),
        "last_bar": str(res.dates[-1].date()),
        "total_return": st["total_return"],
        "max_drawdown": st["max_drawdown"],
        "sharpe": st["sharpe"],
        "exposure_pct": st["exposure_pct"],
        "end_value": st["end_value"],
        "trades": len(res.trades),
        "hit_rate": tm["hit_rate"],
        "profit_factor": tm["profit_factor"],
        "expectancy_eur": tm["expectancy_eur"],
        "median_hold_days": tm["median_hold_days"],
        "avg_win_pct": tm["avg_win_pct"],
        "avg_loss_pct": tm["avg_loss_pct"],
    }


def dataset_table(nb: NbRunner) -> list[dict[str, Any]]:
    """One row per ticker: which CSV, how many bars, what range is used, in which segment."""
    rows = []
    for t in nb.tickers:
        b = nb.bars(t)
        rows.append(
            {
                "ticker": t,
                "segment": nb.segment_of[t],
                "csv": f"data/ohlcv/{t}_1d.csv",
                "first_bar": str(b.dates[0].date()),
                "last_bar": str(b.dates[-1].date()),
                "bars": len(b),
                "repairs": len(b.repairs),
            }
        )
    return rows


def check_against_summary(nb: NbRunner) -> dict[str, Any]:
    """The pooled C13C numbers must equal ``swing/summary.json`` (W1, stocks_all, ai_era)."""
    summ = json.loads((R.OUT / "summary.json").read_text())
    ref = summ["groups"]["stocks_all"]["per_contender"]["W1_C13C_ORIG"]
    mine = pooled(nb.sleeves("C13C", nb.tickers, "ai_era"), "ai_era")
    keys = ["trades", "total_return", "sharpe", "max_drawdown", "profit_factor", "expectancy_eur"]
    diffs = {k: abs(float(mine[k]) - float(ref[k])) for k in keys}
    return {"max_abs_diff": max(diffs.values()), "diffs": diffs, "ref": {k: ref[k] for k in keys}}


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    nb = NbRunner()
    result: dict[str, Any] = {
        "common_end": COMMON_END,
        "cost_bps_per_side": BASE_BPS,
        "acceptance_rule": ACCEPTANCE,
        "datasets": dataset_table(nb),
        "segments": {g: nb.groups[g] for g in STOCK_GROUPS},
        "check": check_against_summary(nb),
        "per_ticker": {},
        "pooled": {},
        "variants": {},
    }
    for t in nb.tickers:
        result["per_ticker"][t] = {
            cfg: {w: one_ticker(nb.sleeve(cfg, t, w)) for w in WINDOWS}
            for cfg in ("C13C", "HOLD")
        }
    scopes = {
        "stocks_all": nb.tickers,
        "memory_core": MEMORY_CORE,
        "memory_wide": MEMORY_WIDE,
        **{g: nb.groups[g] for g in STOCK_GROUPS},
    }
    for scope, tickers in scopes.items():
        result["pooled"][scope] = {
            cfg: {w: pooled(nb.sleeves(cfg, tickers, w), w) for w in WINDOWS}
            for cfg in ("C13C", "HOLD")
        }
        result["pooled"][scope]["C13C_2x"] = {
            w: pooled(nb.sleeves("C13C", tickers, w, "2x"), w) for w in WINDOWS
        }
    for scope in ("stocks_all", "memory_core", "memory_wide"):
        tickers = scopes[scope]
        result["variants"][scope] = {
            cfg: {
                **{w: pooled(nb.sleeves(cfg, tickers, w), w) for w in WINDOWS},
                "ai_era_2x": pooled(nb.sleeves(cfg, tickers, "ai_era", "2x"), "ai_era"),
                "h1_2x": pooled(nb.sleeves(cfg, tickers, "h1", "2x"), "h1"),
                "h2_2x": pooled(nb.sleeves(cfg, tickers, "h2", "2x"), "h2"),
            }
            for cfg in ["C13C", *VARIANTS.keys(), "K7_REENTRY"]
        }
    (OUT / "results.json").write_text(json.dumps(result, indent=1, default=float))
    keep = {
        (cfg, t, w, m): r
        for (cfg, t, w, m), r in nb.cache.items()
        if r is not None and (w in ("ai_era", "full", "y2021_2022", "y2016_2020") and m == "1x")
    }
    with (OUT / "sleeves.pkl").open("wb") as fh:
        pickle.dump({k: (r.dates, r.equity, r.exposure, r.trades) for k, r in keep.items()}, fh)
    np.save(OUT / "_done.npy", np.array([1]))
    return result


if __name__ == "__main__":
    out = run()
    print("check max abs diff vs summary.json:", out["check"]["max_abs_diff"])
