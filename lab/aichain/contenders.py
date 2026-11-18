"""Pre-registered contenders for the AI-chain tournament. Parameters are FIXED; nothing is tuned.

Each rule class implements the ``Rule`` hooks from ``lab.aichain.sim``. All indicators are causal:
the value at index ``i`` only uses bars ``0..i`` (the lookahead test in ``run.py`` verifies this).
K6 is cross-sectional and therefore lives in ``Rotation``/``momentum_picker``.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from lab.aichain.sim import Bars, Position

NAN = float("nan")


def trail_stop(peak: float, pct: float) -> float:
    """Original C13C stop: decimal ``peak * (1 - pct)`` rounded half-even to whole cents."""
    value = Decimal(str(peak)) * (Decimal(1) - Decimal(str(pct)))
    return float(value.quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN))


def _sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).mean().to_numpy()


def _gt(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.where(np.isnan(a) | np.isnan(b), False, a > b)


def swing_levels(
    high: np.ndarray, low: np.ndarray, k: int = 5
) -> tuple[np.ndarray, np.ndarray]:
    """Latest confirmed swing low / swing high at every bar.

    A pivot at bar p needs k lower (higher) bars on each side, so it is usable only from bar p + k.
    """
    n = len(low)
    sup = np.full(n, NAN)
    res = np.full(n, NAN)
    for p in range(k, n - k):
        window_l = np.r_[low[p - k : p], low[p + 1 : p + k + 1]]
        window_h = np.r_[high[p - k : p], high[p + 1 : p + k + 1]]
        if low[p] < window_l.min():
            sup[p + k] = low[p]
        if high[p] > window_h.max():
            res[p + k] = high[p]
    return (
        pd.Series(sup).ffill().to_numpy(),
        pd.Series(res).ffill().to_numpy(),
    )


class BaseRule:
    """Shared defaults: no extra exit, no stop, entry from a precomputed boolean array."""

    id = "BASE"
    enter_at_first_bar = False

    def __init__(self, **params: Any) -> None:
        self.params = {**self.DEFAULTS, **params}
        self.entry_arr = np.zeros(0, dtype=bool)

    DEFAULTS: ClassVar[dict[str, Any]] = {}

    def prepare(self, bars: Bars) -> None:
        raise NotImplementedError

    def entry(self, i: int) -> bool:
        return bool(self.entry_arr[i])

    def on_fill(self, i: int, pos: Position) -> None:
        return None

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return None

    def after_bar(self, i: int, pos: Position) -> None:
        return None

    def on_exit(self, i: int, reason: str) -> None:
        return None


class BuyHold(BaseRule):
    id = "B0_BUYHOLD"
    enter_at_first_bar = True

    def prepare(self, bars: Bars) -> None:
        self.entry_arr = np.ones(len(bars), dtype=bool)


class C13C(BaseRule):
    """K1 original C13C; with ``reentry=True`` it is K7 (own hypothesis, labelled extension)."""

    id = "K1_C13C_ORIG"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "sma": 200,
        "dip_bars": 5,
        "dip": 0.05,
        "trail": 0.10,
        "reentry": False,
        "mean": 20,
    }

    def prepare(self, bars: Bars) -> None:
        p = self.params
        close = pd.Series(bars.close)
        sma = close.rolling(p["sma"]).mean()
        # Same expressions as lab.research.memory_swing.entry_signals so that floats compare identically.
        base = (close > sma) & (close / close.shift(p["dip_bars"]) - 1 <= -p["dip"])
        self.base = base.fillna(False).to_numpy(bool)
        self.close_above_sma = (close > sma).fillna(False).to_numpy(bool)
        self.close_above_mean = (
            (close > close.rolling(p["mean"]).mean()).fillna(False).to_numpy(bool)
        )
        self.armed = False

    def entry(self, i: int) -> bool:
        if self.base[i]:
            return True
        return bool(
            self.params["reentry"]
            and self.armed
            and self.close_above_sma[i]
            and self.close_above_mean[i]
        )

    def on_fill(self, i: int, pos: Position) -> None:
        self.armed = False
        pos.stop = trail_stop(pos.peak, self.params["trail"])

    def after_bar(self, i: int, pos: Position) -> None:
        pos.stop = max(pos.stop or 0.0, trail_stop(pos.peak, self.params["trail"]))

    def on_exit(self, i: int, reason: str) -> None:
        if reason == "stop":
            self.armed = True


class C13CReentry(C13C):
    id = "K7_C13C_PLUS_TREND_REENTRY"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "reentry": True}


class Sma200Trend(BaseRule):
    id = "K2_SMA200_TREND"
    DEFAULTS: ClassVar[dict[str, Any]] = {"sma": 200}

    def prepare(self, bars: Bars) -> None:
        sma = _sma(bars.close, self.params["sma"])
        self.entry_arr = _gt(bars.close, sma)
        with np.errstate(invalid="ignore"):
            self.exit_arr = np.where(np.isnan(sma), False, bars.close < sma)

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "close below SMA" if self.exit_arr[i] else None


class Donchian(BaseRule):
    id = "K3_DONCHIAN_55_20"
    DEFAULTS: ClassVar[dict[str, Any]] = {"entry_n": 55, "exit_n": 20}

    def prepare(self, bars: Bars) -> None:
        p = self.params
        hi = pd.Series(bars.high).shift(1).rolling(p["entry_n"]).max().to_numpy()
        lo = pd.Series(bars.low).shift(1).rolling(p["exit_n"]).min().to_numpy()
        self.entry_arr = _gt(bars.close, hi)
        with np.errstate(invalid="ignore"):
            self.exit_arr = np.where(np.isnan(lo), False, bars.close < lo)

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "close below prior low" if self.exit_arr[i] else None


class Tsmom(BaseRule):
    id = "K4_TSMOM_126"
    DEFAULTS: ClassVar[dict[str, Any]] = {"lookback": 126}

    def prepare(self, bars: Bars) -> None:
        close = pd.Series(bars.close)
        ret = (close / close.shift(self.params["lookback"]) - 1).to_numpy()
        self.entry_arr = np.where(np.isnan(ret), False, ret > 0)
        self.exit_arr = np.where(np.isnan(ret), False, ret <= 0)

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "momentum turned non-positive" if self.exit_arr[i] else None


class SupportResistance(BaseRule):
    """K5 classic support bounce in an uptrend; target = last confirmed swing high."""

    id = "K5_SUPPORT_RESISTANCE"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "sma": 200,
        "pivot": 5,
        "prox": 0.015,
        "stop": 0.03,
        "max_bars": 30,
    }

    def prepare(self, bars: Bars) -> None:
        p = self.params
        self.sup, self.res = swing_levels(bars.high, bars.low, p["pivot"])
        sma = _sma(bars.close, p["sma"])
        ok = ~(np.isnan(self.sup) | np.isnan(self.res) | np.isnan(sma))
        with np.errstate(invalid="ignore"):
            self.entry_arr = (
                ok
                & (bars.close > sma)
                & (bars.low <= self.sup * (1 + p["prox"]))
                & (bars.close > self.sup)
                & (self.res > bars.close)
            )

    def on_fill(self, i: int, pos: Position) -> None:
        pos.stop = float(self.sup[i - 1] * (1 - self.params["stop"]))
        pos.target = float(self.res[i - 1])

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "time exit" if pos.bars >= self.params["max_bars"] else None


class BreakoutRetest(BaseRule):
    """K5b close above resistance, then first pullback to the level that closes above it."""

    id = "K5B_SR_BREAKOUT_RETEST"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "pivot": 5,
        "prox": 0.015,
        "stop": 0.03,
        "sma_exit": 50,
        "expiry": 40,
    }

    def prepare(self, bars: Bars) -> None:
        p = self.params
        _, res = swing_levels(bars.high, bars.low, p["pivot"])
        n = len(bars)
        entry = np.zeros(n, dtype=bool)
        level = np.full(n, NAN)
        armed_level, armed_i = NAN, -1
        for i in range(n):
            c = bars.close[i]
            if not math.isnan(armed_level):
                if c < armed_level or i - armed_i > p["expiry"]:
                    armed_level = NAN
                elif (
                    i > armed_i
                    and bars.low[i] <= armed_level * (1 + p["prox"])
                    and c > armed_level
                ):
                    entry[i] = True
                    level[i] = armed_level
                    armed_level = NAN
            can_arm = (
                math.isnan(armed_level) and not entry[i] and not math.isnan(res[i])
            )
            if can_arm and c > res[i] and (i == 0 or bars.close[i - 1] <= res[i]):
                armed_level, armed_i = float(res[i]), i
        self.entry_arr, self.level = entry, level
        sma = _sma(bars.close, p["sma_exit"])
        with np.errstate(invalid="ignore"):
            self.exit_arr = np.where(np.isnan(sma), False, bars.close < sma)

    def on_fill(self, i: int, pos: Position) -> None:
        pos.stop = float(self.level[i - 1] * (1 - self.params["stop"]))

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "close below SMA50" if self.exit_arr[i] else None


def momentum_picker(lookback: int = 126, skip: int = 5, stale_days: int = 5) -> Any:
    """K6 target weights: better half by ``lookback``-day return (skipping ``skip`` days), negatives to cash."""

    def pick(prior_day: pd.Timestamp, data: dict[str, Bars]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for ticker, b in data.items():
            j = (
                int(
                    np.searchsorted(
                        b.dates.values, np.datetime64(prior_day), side="right"
                    )
                )
                - 1
            )
            if j - skip - lookback < 0 or (prior_day - b.dates[j]).days > stale_days:
                continue
            scores[ticker] = b.close[j - skip] / b.close[j - skip - lookback] - 1.0
        if not scores:
            return {}
        keep = max(1, math.ceil(len(scores) / 2))
        ranked = sorted(scores, key=lambda t: scores[t], reverse=True)[:keep]
        return {t: 1.0 / keep for t in ranked if scores[t] > 0}

    return pick


CONTENDERS: dict[str, dict[str, Any]] = {
    "B0_BUYHOLD": {
        "cls": BuyHold,
        "rules": [
            "Buy at the first open of the window and hold to the end. Benchmark, not a strategy."
        ],
    },
    "K1_C13C_ORIG": {
        "cls": C13C,
        "rules": [
            "Signal at close: close > SMA200 and 5-day return <= -5 percent; buy at the next open.",
            "Trailing stop = max(previous stop, 0.90 * known peak), rounded to cents, never lowered.",
            "Intraday stop if low <= stop: exit at the stop price, or at the open if the bar gapped below.",
            "A new high raises the stop only from the next session. No take-profit, no time exit.",
        ],
    },
    "K2_SMA200_TREND": {
        "cls": Sma200Trend,
        "rules": [
            "Hold while close > SMA200; exit at the next open after a close below SMA200."
        ],
    },
    "K3_DONCHIAN_55_20": {
        "cls": Donchian,
        "rules": [
            "Enter on a close above the prior 55-day high (previous bars only).",
            "Exit at the next open after a close below the prior 20-day low.",
        ],
    },
    "K4_TSMOM_126": {
        "cls": Tsmom,
        "rules": [
            "Hold while the 126-day return is positive; exit at the next open once it is <= 0."
        ],
    },
    "K5_SUPPORT_RESISTANCE": {
        "cls": SupportResistance,
        "rules": [
            "Pivot = bar whose low (high) is strictly below (above) the 5 bars on each side; usable 5 bars later.",
            "Entry: close > SMA200, bar low <= support * 1.015, close > support, last swing high above the close.",
            "Stop 3 percent below the support; target = last confirmed swing high; time exit after 30 bars.",
            "If stop and target are both touched in one bar the stop is assumed first (conservative).",
        ],
    },
    "K5B_SR_BREAKOUT_RETEST": {
        "cls": BreakoutRetest,
        "rules": [
            "Break: first close above the latest confirmed swing high (the level).",
            "Retest: first later bar with low <= level * 1.015 that closes above the level; buy at the next open.",
            "Armed break expires after 40 bars or when a close falls below the level (completion of the spec).",
            "Stop 3 percent below the level; exit at the next open after a close below SMA50.",
        ],
    },
    "K6_MOMENTUM_CS": {
        "cls": None,
        "rules": [
            (
                "Segment-level only. At the first open of each month rank the segment's tickers by the "
                "126-day return (skipping the latest 5 days, data up to the previous close)."
            ),
            "Hold the better half (rounded up), equal weight per slot; slots of tickers with a negative return stay cash.",
            "Rebalance to targets at that open, cost on every traded amount.",
        ],
    },
    "K7_C13C_PLUS_TREND_REENTRY": {
        "cls": C13CReentry,
        "rules": [
            "NEW hypothesis, extension of K1 (own freeze id).",
            (
                "Same entry, stop and exit as K1. After a stop-out, re-enter at the next open as soon as "
                "close > SMA200 and close > 20-day mean, even without a new 5 percent dip."
            ),
        ],
    },
}


def make_rule(contender: str, **overrides: Any) -> Any:
    cls = CONTENDERS[contender]["cls"]
    return cls(**overrides)
