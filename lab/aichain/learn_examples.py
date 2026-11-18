"""Real worked examples for the teaching page "Momentum, potpora i otpor, mehanika trzista".

Research only: it never places orders and never runs a new hypothesis test. It reuses the loader, bar repair
rules, rules (W2, W5) and event definitions (E1, E2, E4, E5) that already produced the swing results, and only
*picks* illustrations from them by a fixed, disclosed rule:

- Event days are the decision days of the registered rules or tests, in the AI era (2023-01-01 onward).
- Outcome r10 = close 10 bars after the decision day divided by the open of the next day, minus one
  (the same measurement as the event study in ``levels_study``).
- A "clean" example is the first event (tickers tried in a fixed order) with r10 >= +5 percent; a "failed"
  example is the first with r10 <= -5 percent. Nothing is picked for looks.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import levels as lv
from lab.aichain import levels_study as ls
from lab.aichain import mechanics as mx
from lab.aichain.contenders import swing_levels
from lab.aichain.sim import AI_ERA_START, ROOT, Bars, load_bars
from lab.aichain.swing import make_rule, run_swing_sleeve

SWING = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing"
CLEAN_MIN = 0.05
FAIL_MAX = -0.05
H = 10
MIN_RANGE_PCT = 0.10
BEFORE = 60  # bars of context a chart needs before the event
AFTER = 30  # bars of outcome a chart needs after the event
PRIMARY_ORDER = ("MU", "WDC", "STX")
CONCEPT_FIRST = {
    "momentum": ("MU", "NVDA", "AMD"),
    "sr_flip": ("MU", "NVDA", "AMD"),
    "bos": ("MU", "NVDA", "AMD"),
    "sweep": ("MU", "NVDA", "AMD"),
    "zone": ("MU", "NVDA", "AMD"),
    "discount": ("NVDA", "AMD", "AVGO"),
    "topdown": ("WDC", "STX", "MU"),
}


# premium/discount reuses the E1 days of the sweep section, so MU (and the top-down tickers WDC, STX) are skipped there
EXCLUDE = {"discount": ("MU", "WDC", "STX")}


@dataclass
class Ctx:
    """One ticker prepared once: bars, structure, zones, sweeps, weekly bias and decision-day flags."""

    ticker: str
    P: lv.Prepared
    flags: dict[str, np.ndarray]
    fr: np.ndarray  # r10 per decision day (NaN beyond the data)
    ai0: int

    @property
    def n(self) -> int:
        return len(self.P.bars)


@dataclass
class Example:
    concept: str
    kind: str  # "clean" | "failed"
    ticker: str
    t: int  # decision day (signal at the close)
    r10: float
    extra: dict[str, Any] = field(default_factory=dict)


@functools.cache
def stock_universe() -> tuple[str, ...]:
    """The 43 stock tickers of the swing test, in the order used by the registered run."""
    s = json.loads((SWING / "summary.json").read_text())
    return tuple(s["groups"]["stocks_all"]["tickers"])


@functools.cache
def ctx(ticker: str) -> Ctx:
    """Prepare one ticker through the shared loader (common end 2026-10-05) and the E-event flags."""
    b = load_bars(ticker)
    P = lv.prepare_from_bars(b, lv.load_volume(ticker, b.dates))
    n = len(b)
    flags = ls.event_flags(P, n - 1)
    fr = ls.forward_returns(P, n - 1)[H]
    ai0 = int(
        np.searchsorted(b.dates.values, np.datetime64(pd.Timestamp(AI_ERA_START)))
    )
    return Ctx(ticker, P, flags, fr, ai0)


def _usable(c: Ctx, t: int) -> bool:
    return t >= max(c.ai0, BEFORE) and t + AFTER < c.n and not np.isnan(c.fr[t])


def _flag_events(c: Ctx, name: str) -> list[int]:
    return [int(t) for t in np.flatnonzero(c.flags[name]) if _usable(c, int(t))]


def _trade_events(c: Ctx, cid: str) -> tuple[list[int], dict[int, dict[str, Any]], Any]:
    """Decision days that became real trades of rule ``cid`` in the AI era (entry open = day t+1)."""
    rule = make_rule(cid)
    res = run_swing_sleeve(c.P.bars, rule, AI_ERA_START, "2026-10-05")
    out: list[int] = []
    info: dict[int, dict[str, Any]] = {}
    if res is None:
        return out, info, rule
    pos = {str(d.date()): i for i, d in enumerate(c.P.bars.dates)}
    for tr in res.trades:
        i = pos.get(tr["entry_date"])
        if i is None or i == 0:
            continue
        t = i - 1
        if _usable(c, t):
            out.append(t)
            info[t] = tr
    return out, info, rule


def _events(concept: str, c: Ctx) -> tuple[list[int], dict[str, Any]]:
    """Event days for a concept plus helper data the charts need."""
    if concept == "momentum":
        ev, info, _ = _trade_events(c, "W2_MOM_BREAK_20")
        return ev, {"trades": info}
    if concept == "sr_flip":
        ev, info, rule = _trade_events(c, "W5_SR_BREAKOUT_RETEST")
        return ev, {"trades": info, "levels": rule.level}
    if concept == "bos":
        return _flag_events(c, "E5_bos_trend"), {}
    if concept == "sweep":
        return _flag_events(c, "E1_sweep_shift_discount"), {}
    if concept == "discount":
        # same E1 days, but only where the swing range is at least 10 percent of the close (readable picture)
        ev = []
        for t in _flag_events(c, "E1_sweep_shift_discount"):
            x = _sweep_context(c, t)
            if (x["range_hi"] - x["range_lo"]) >= MIN_RANGE_PCT * float(
                c.P.bars.close[t]
            ):
                ev.append(t)
        return ev, {}
    if concept == "zone":
        return _flag_events(c, "E4_demand_zone_retest"), {}
    if concept == "topdown":
        return _flag_events(c, "E2_sweep_shift_discount_weekly"), {}
    raise ValueError(f"unknown concept {concept!r}")


def _first(c: Ctx, events: list[int], kind: str) -> int | None:
    for t in events:
        r = c.fr[t]
        if (kind == "clean" and r >= CLEAN_MIN) or (kind == "failed" and r <= FAIL_MAX):
            return t
    return None


def _build(concept: str, c: Ctx, t: int, kind: str, helper: dict[str, Any]) -> Example:
    extra: dict[str, Any] = {}
    P = c.P
    if concept == "momentum":
        extra["trade"] = helper["trades"][t]
    elif concept == "sr_flip":
        extra["trade"] = helper["trades"][t]
        extra.update(_flip_context(c, t, float(helper["levels"][t])))
    elif concept == "bos":
        ev = [e for e in P.struct.events if e["idx"] == t and e["kind"] == "bos"]
        extra["event"] = ev[0]
    elif concept in ("sweep", "discount", "topdown"):
        extra.update(_sweep_context(c, t))
    elif concept == "zone":
        zs = [z for z in P.zones if z["kind"] == "demand" and z["first_return"] == t]
        extra["zone"] = zs[0]
    return Example(concept, kind, c.ticker, t, float(c.fr[t]), extra)


def _flip_context(c: Ctx, t: int, level: float) -> dict[str, Any]:
    """Break bar and cluster members of the resistance that became support (W5 retest at day ``t``)."""
    b = c.P.bars
    _, res = swing_levels(b.high, b.low, 5)
    brk = t - 1
    while brk > 0 and not (
        b.close[brk] > level
        and b.close[brk - 1] <= level
        and abs(res[brk] - level) < 1e-9
    ):
        brk -= 1
        if t - brk > 45:
            break
    close_t = float(b.close[t])
    cl = lv.cluster_levels(c.P.pivots, t, float(c.P.atr[t]), close_t)
    near = min(cl, key=lambda L: abs(L.price - level)) if cl else None
    members = [] if near is None else [p for p in near.members if p.kind == "H"]
    return {"level": level, "break_i": brk, "members": members}


def _sweep_context(c: Ctx, t: int) -> dict[str, Any]:
    """Sweep bar, shift event and swing range of an E1 decision day ``t``."""
    P = c.P
    sweeps = [
        e
        for e in P.sweeps
        if e["dir"] == 1
        and t - 15 <= e["idx"] <= t
        and P.pos[e["idx"]] == P.pos[e["idx"]]
        and P.pos[e["idx"]] < 0.5
    ]
    sw = sweeps[-1]
    shift = next(e for e in P.struct.events if e["idx"] == t and e["kind"] == "shift")
    s = sw["idx"]
    return {
        "sweep": sw,
        "shift": shift,
        "range_lo": float(P.lo_p[s]),
        "range_hi": float(P.hi_p[s]),
        "range_lo_i": int(P.lo_i[s]),
        "range_hi_i": int(P.hi_i[s]),
    }


def pick(concept: str) -> dict[str, Example | None]:
    """Clean and failed example for one concept, by the disclosed rule (ticker order fixed in advance)."""
    skip = EXCLUDE.get(concept, ())
    order = [t for t in CONCEPT_FIRST[concept] if t not in skip] + [
        t for t in stock_universe() if t not in CONCEPT_FIRST[concept] and t not in skip
    ]
    found: dict[str, Example | None] = {"clean": None, "failed": None}
    partial: dict[str, Example] = {}
    for tk in order:
        c = ctx(tk)
        events, helper = _events(concept, c)
        got = {k: _first(c, events, k) for k in ("clean", "failed")}
        if got["clean"] is not None and got["failed"] is not None:
            return {
                k: _build(concept, c, got[k], k, helper) for k in ("clean", "failed")
            }  # type: ignore[arg-type]
        for k, t in got.items():
            if t is not None and k not in partial:
                partial[k] = _build(concept, c, t, k, helper)
    for k, ex in partial.items():
        found[k] = ex
    return found


# ----------------------------------------------------------------------------- other fixed illustrations


def equal_lows_example(
    tickers: tuple[str, ...] = ("MU", "NVDA", "AMD", "WDC"),
) -> dict[str, Any] | None:
    """First AI-era case where two confirmed lows within 0.3 percent were swept (low through, close back above).

    Purely an illustration of the vocabulary: equal lows are not tested separately in the swing study.
    """
    for tk in tickers:
        c = ctx(tk)
        P = c.P
        b = P.bars
        for t in range(max(c.ai0, BEFORE), c.n - AFTER):
            pools = mx.equal_pools(P.pivots, b.high, b.low, t)["below"]
            for pool in pools:
                lvl = pool["level"]
                # a later bar (within 25 bars) trades below it and closes back above
                for j in range(t + 1, min(c.n, t + 26)):
                    if b.low[j] < lvl:
                        if b.close[j] > lvl:
                            members = [
                                p
                                for p in P.pivots
                                if p.kind == "L"
                                and p.confirm <= t
                                and abs(p.price - lvl) / lvl <= mx.EQUAL_TOL
                            ]
                            return {
                                "ticker": tk,
                                "t_known": t,
                                "sweep_i": j,
                                "level": lvl,
                                "members": members,
                            }
                        break
    return None


def structure_window(ticker: str = "MU") -> dict[str, Any]:
    """Fixed window for the structure anatomy chart (2023-06-01 to 2024-03-31)."""
    c = ctx(ticker)
    d = c.P.bars.dates
    s = int(np.searchsorted(d.values, np.datetime64(pd.Timestamp("2023-06-01"))))
    e = int(
        np.searchsorted(
            d.values, np.datetime64(pd.Timestamp("2024-03-31")), side="right"
        )
    )
    return {"ticker": ticker, "s": s, "e": e}


def euro_result(c: Ctx, t: int, capital: float = 1000.0) -> dict[str, float]:
    """Euro result of buying ``capital`` at the open of t+1 and holding to the close of t+10, costs 2.5 bps/side."""
    b: Bars = c.P.bars
    buy = float(b.open[t + 1]) * 1.00025
    sell = float(b.close[t + H]) * (1 - 0.00025)
    units = capital / buy
    return {
        "entry": float(b.open[t + 1]),
        "exit": float(b.close[t + H]),
        "units": units,
        "value": units * sell,
        "pnl": units * sell - capital,
    }
