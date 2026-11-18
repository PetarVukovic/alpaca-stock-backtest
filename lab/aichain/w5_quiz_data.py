"""Real W5 (breakout + retest) and C13C situations for the quiz page. Research only; agents never place orders.

``w5_events`` replays the state machine of ``contenders.BreakoutRetest.prepare`` and records every arm, cancel,
expiry and entry, so the quiz can show the days BEFORE a decision and the real outcome after it. The entries are
verified equal to the engine's ``entry_arr`` (``verify_events``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import swing as S
from lab.aichain.contenders import swing_levels
from lab.aichain.sim import AI_ERA_START, COMMON_END, Bars, Cost, load_bars

PIVOT, PROX, STOP, SMA_EXIT, EXPIRY = 5, 0.015, 0.03, 50, 40


@dataclass
class Event:
    kind: str  # arm | cancel | expire | entry
    i: int
    level: float
    armed_i: int


def w5_events(bars: Bars) -> tuple[list[Event], np.ndarray]:
    """All state changes of the W5 rule, with the same logic as ``BreakoutRetest.prepare``."""
    _, res = swing_levels(bars.high, bars.low, PIVOT)
    n = len(bars)
    out: list[Event] = []
    entry = np.zeros(n, dtype=bool)
    armed_level, armed_i = math.nan, -1
    for i in range(n):
        c = bars.close[i]
        took_entry = False
        if not math.isnan(armed_level):
            if c < armed_level:
                out.append(Event("cancel", i, armed_level, armed_i))
                armed_level = math.nan
            elif i - armed_i > EXPIRY:
                out.append(Event("expire", i, armed_level, armed_i))
                armed_level = math.nan
            elif i > armed_i and bars.low[i] <= armed_level * (1 + PROX) and c > armed_level:
                entry[i] = True
                took_entry = True
                out.append(Event("entry", i, armed_level, armed_i))
                armed_level = math.nan
        can_arm = math.isnan(armed_level) and not took_entry and not math.isnan(res[i])
        if can_arm and c > res[i] and (i == 0 or bars.close[i - 1] <= res[i]):
            armed_level, armed_i = float(res[i]), i
            out.append(Event("arm", i, armed_level, armed_i))
    return out, entry


def verify_events(bars: Bars) -> bool:
    rule = S.make_rule("W5_SR_BREAKOUT_RETEST")
    rule.prepare(bars)
    _, entry = w5_events(bars)
    return bool(np.array_equal(rule.entry_arr.astype(bool), entry))


def sleeve_trades(bars: Bars, cid: str) -> list[dict[str, Any]]:
    res = S.run_swing_sleeve(bars, S.make_rule(cid), AI_ERA_START, COMMON_END, Cost())
    return [] if res is None else list(res.trades)


def c13c_signal_days(bars: Bars) -> pd.DataFrame:
    close = pd.Series(bars.close, index=bars.dates)
    sma = close.rolling(200).mean()
    chg = close / close.shift(5) - 1
    return pd.DataFrame({"close": close, "sma200": sma, "chg5": chg, "signal": (close > sma) & (chg <= -0.05)})
