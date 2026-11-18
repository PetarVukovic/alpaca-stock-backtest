"""Read-only engine access for the MASTER teaching charts.

Re-runs ``lab.aichain.swing`` sleeves through the same ``Runner`` that produced ``swing/summary.json`` (no ledger
writes, no new trials). ``verify_against_summary`` proves the re-run equals the published numbers before any chart
uses them.
"""

from __future__ import annotations

from functools import cache
from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import swing as S
from lab.aichain import swing_run as R
from lab.aichain.master_common import SWING, load_json
from lab.aichain.sim import START_CAPITAL, SleeveResult, stats, sum_sleeves

STOCK_GROUPS = [
    "memory",
    "mem_interface_storage",
    "equipment",
    "ai_chips_logic",
    "network_servers",
    "cloud",
]


@cache
def groups() -> dict[str, list[str]]:
    return R.peer_groups()


@cache
def runner() -> R.Runner:
    return R.Runner(groups())


@cache
def summary() -> dict[str, Any]:
    return load_json(SWING / "summary.json")


def stock_tickers() -> list[str]:
    """The pooled stock universe (43 sleeves) in group order, as in ``stocks_all``."""
    g = groups()
    return [t for name in STOCK_GROUPS for t in g[name]]


def sleeve(
    ticker: str, cid: str, window: str = "ai_era", mult: str = "1x"
) -> SleeveResult | None:
    return runner().sleeve(ticker, cid, window, mult)


def pooled_trades(
    cid: str, window: str = "ai_era", tickers: list[str] | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tickers or stock_tickers():
        r = sleeve(t, cid, window)
        if r is not None:
            out += [{**x, "ticker": t} for x in r.trades]
    return out


def group_equity(cid: str, tickers: list[str], window: str) -> pd.Series:
    """Average value per 1.000 EUR sleeve (sum of sleeves divided by their number)."""
    parts = [sleeve(t, cid, window) for t in tickers]
    parts = [p for p in parts if p is not None]
    agg = sum_sleeves(parts)
    return pd.Series(agg.equity / len(parts), index=agg.dates)


def verify_against_summary() -> dict[str, Any]:
    """Re-run key group numbers and compare with summary.json; raises on any mismatch beyond 1e-9."""
    sm = summary()
    report: dict[str, Any] = {}
    checks = [
        ("memory", "W1_C13C_ORIG"),
        ("memory", "W5_SR_BREAKOUT_RETEST"),
        ("memory", "W3_MOM_RANK_WEEKLY"),
        ("memory", "B0_BUYHOLD"),
        ("stocks_all", "W1_C13C_ORIG"),
        ("stocks_all", "W5_SR_BREAKOUT_RETEST"),
        ("stocks_all", "W8_IBS_REVERT"),
    ]
    for g, cid in checks:
        tick = stock_tickers() if g == "stocks_all" else groups()[g]
        parts = runner().sleeves(tick, cid, "ai_era", "1x")
        agg = sum_sleeves(parts)
        st = stats(agg, START_CAPITAL * len(parts))
        ref = sm["groups"][g]["per_contender"][cid]
        n = len(R.all_trades(parts))
        ok = n == ref["trades"] and abs(st["total_return"] - ref["total_return"]) < 1e-9
        report[f"{g}/{cid}"] = {
            "trades": n,
            "ref_trades": ref["trades"],
            "total_return": st["total_return"],
            "ref": ref["total_return"],
            "ok": ok,
        }
        if not ok:
            raise AssertionError(
                f"engine re-run differs from summary.json for {g}/{cid}: {report[f'{g}/{cid}']}"
            )
    return report


def rule_for(ticker: str, cid: str) -> Any:
    """A prepared rule instance for ``ticker`` on its full history (arrays are causal)."""
    rule = runner().rule(ticker, cid, {})
    rule.prepare(runner().bars[ticker])
    return rule


def ret_after_cost(trade: dict[str, Any]) -> float:
    return float(trade["return"])


def trail_stop_series(
    bars_high: np.ndarray,
    entry_i: int,
    exit_i: int,
    entry_open: float,
    trail: float = 0.10,
) -> np.ndarray:
    """C13C stop level at each bar from entry to exit, rebuilt from the known peak (same rule as ``contenders.C13C``)."""
    from lab.aichain.contenders import trail_stop

    peak = entry_open
    stop = trail_stop(peak, trail)
    out = []
    for i in range(entry_i, exit_i + 1):
        out.append(
            stop
        )  # the stop that is live during bar i (set or raised on earlier bars)
        peak = max(peak, float(bars_high[i]))
        stop = max(stop, trail_stop(peak, trail))
    return np.array(out)


__all__ = [
    "R",
    "S",
    "group_equity",
    "groups",
    "pooled_trades",
    "rule_for",
    "runner",
    "sleeve",
    "summary",
    "trail_stop_series",
    "verify_against_summary",
]
