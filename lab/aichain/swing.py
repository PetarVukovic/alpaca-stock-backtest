"""Swing-frequency test: pre-registered contenders W1..W8 (+ B0), a partial-exit simulator and trade metrics.

Research only: agents never place orders. Conventions are identical to ``lab.aichain.sim``:
decision at the close of day t, fill at the open of t+1, long-only, fractional units, intraday stops at the
stop price or at the open when gapped, stop checked before target. The only addition is a partial exit
(``pos.extra["partial"]``) that W6 needs; ``run_swing_sleeve`` is verified equal to ``sim.run_sleeve`` for
rules without a partial exit (tests/aichain/test_swing.py).

All indicators are causal: the value at index ``i`` only uses bars ``0..i``. Pivots (k bars each side) are
usable only k bars after they formed.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from lab.aichain.contenders import C13C, BaseRule, BreakoutRetest, BuyHold
from lab.aichain.sim import (
    DEFAULT_COST,
    START_CAPITAL,
    Bars,
    Cost,
    Position,
    SleeveResult,
)

NAN = float("nan")
Pivot = tuple[int, int, float]  # (confirm_bar, pivot_bar, value)


# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
def pivot_lists(
    high: np.ndarray, low: np.ndarray, k: int
) -> tuple[list[Pivot], list[Pivot]]:
    """Confirmed swing highs and lows, sorted by confirmation bar (pivot bar + k).

    Same definition as ``contenders.swing_levels``: strictly above (below) the k bars on each side.
    """
    n = len(low)
    highs: list[Pivot] = []
    lows: list[Pivot] = []
    if n < 2 * k + 1:
        return highs, lows
    wl = sliding_window_view(low, 2 * k + 1)
    wh = sliding_window_view(high, 2 * k + 1)
    is_low = wl[:, k] < np.minimum(wl[:, :k].min(1), wl[:, k + 1 :].min(1))
    is_high = wh[:, k] > np.maximum(wh[:, :k].max(1), wh[:, k + 1 :].max(1))
    for q in np.nonzero(is_low)[0]:
        p = int(q) + k
        lows.append((p + k, p, float(low[p])))
    for q in np.nonzero(is_high)[0]:
        p = int(q) + k
        highs.append((p + k, p, float(high[p])))
    return highs, lows


def atr(bars: Bars, n: int) -> np.ndarray:
    """Average true range as a simple mean of the true range over ``n`` bars (NaN while warming up)."""
    prev = pd.Series(bars.close).shift(1)
    h, lo = pd.Series(bars.high), pd.Series(bars.low)
    tr = pd.concat([h - lo, (h - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


def weekly_sma(bars: Bars, n: int) -> np.ndarray:
    """Weekly SMA of the week-to-date close: mean of the last ``n - 1`` COMPLETED weekly closes plus today's close.

    Weekly bars are built from the daily bars by ISO week. Only completed weeks and the close of the current
    bar are used, so the value at bar i never depends on later bars.
    """
    iso = bars.dates.isocalendar()
    week = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    n_bars = len(bars)
    change = np.r_[True, week[1:] != week[:-1]]
    week_no = np.cumsum(change) - 1  # 0-based week sequence number per bar
    last_close = pd.Series(bars.close).groupby(week_no).last().to_numpy()
    csum = np.r_[0.0, np.cumsum(last_close)]
    out = np.full(n_bars, NAN)
    for i in range(n_bars):
        u = int(week_no[i])
        if u >= n - 1:
            out[i] = (csum[u] - csum[u - (n - 1)] + bars.close[i]) / n
    return out


def target_swing_high(
    highs: list[Pivot], upto: int, close: float, t: int, lookback: int, nearest: bool
) -> float:
    """Swing high above ``close`` among the first ``upto`` confirmed highs, looking back ``lookback`` bars.

    ``nearest=False``: the latest confirmed swing high if it lies above the close, else the nearest above.
    ``nearest=True``: always the nearest swing high above the close. NaN when there is none.
    """
    cands = [v for (_, p, v) in highs[:upto] if v > close and p >= t - lookback]
    if not cands:
        return NAN
    if not nearest and upto > 0 and highs[upto - 1][2] > close:
        return highs[upto - 1][2]
    return min(cands)


def _lt(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.where(np.isnan(a) | np.isnan(b), False, a < b)


def _ceil(x: float) -> int:
    return math.ceil(x - 1e-9)


class SwingRule(BaseRule):
    """Base for arrays-driven rules with a per-entry stop/target and a time exit."""

    FIXED: ClassVar[
        tuple[str, ...]
    ] = ()  # DEFAULTS keys that are not thresholds (no +-20 percent test)

    def __init__(self, **params: Any) -> None:
        super().__init__(**params)
        self.stop_arr = np.zeros(0)
        self.target_arr = np.zeros(0)

    def on_fill(self, i: int, pos: Position) -> None:
        if len(self.stop_arr) and not math.isnan(self.stop_arr[i - 1]):
            pos.stop = float(self.stop_arr[i - 1])
        if len(self.target_arr) and not math.isnan(self.target_arr[i - 1]):
            pos.target = float(self.target_arr[i - 1])

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "time exit" if pos.bars >= self.params["max_bars"] else None


# --------------------------------------------------------------------------------------------------
# W1 / W5 / B0 reuse the existing rule classes unchanged
# --------------------------------------------------------------------------------------------------
class W1C13C(C13C):
    id = "W1_C13C_ORIG"


class W5Retest(BreakoutRetest):
    id = "W5_SR_BREAKOUT_RETEST"


class W0BuyHold(BuyHold):
    id = "B0_BUYHOLD"


# --------------------------------------------------------------------------------------------------
# W2 momentum breakout
# --------------------------------------------------------------------------------------------------
class MomBreak(SwingRule):
    id = "W2_MOM_BREAK_20"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "high_n": 20,
        "ret_n": 60,
        "sma": 50,
        "exit_n": 10,
        "max_bars": 15,
        "stop": 0.08,
    }

    def prepare(self, bars: Bars) -> None:
        p = self.params
        close, low = pd.Series(bars.close), pd.Series(bars.low)
        hh = close.rolling(int(p["high_n"])).max()
        ret = close / close.shift(int(p["ret_n"])) - 1
        sma = close.rolling(int(p["sma"])).mean()
        self.entry_arr = ((close >= hh) & (ret > 0) & (close > sma)).to_numpy(bool)
        prior_low = low.shift(1).rolling(int(p["exit_n"])).min().to_numpy()
        self.exit_arr = _lt(bars.close, prior_low)

    def on_fill(self, i: int, pos: Position) -> None:
        pos.stop = float(pos.raw_entry * (1 - self.params["stop"]))

    def exit_signal(self, i: int, pos: Position) -> str | None:
        if pos.bars >= self.params["max_bars"]:
            return "time exit"
        return "close below prior low" if self.exit_arr[i] else None


# --------------------------------------------------------------------------------------------------
# W3 weekly relative-strength rank inside the group
# --------------------------------------------------------------------------------------------------
class MomRankWeekly(SwingRule):
    """Rank by 20-day return inside the group at the last bar of each week; fill at the first open of the next.

    The weekly decision day is Friday (``weekday`` 4) for exchange-traded names and Sunday (6) for crypto.
    A week whose decision weekday is a market holiday has no decision (the previous state carries over).
    Held name: kept while it stays in the top half; entry: top third and close > SMA50.
    """

    id = "W3_MOM_RANK_WEEKLY"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "ret_n": 20,
        "sma": 50,
        "top_frac": 1 / 3,
        "keep_frac": 1 / 2,
        "weekday": 4,
        "stale_days": 5,
    }
    FIXED: ClassVar[tuple[str, ...]] = ("weekday", "stale_days")

    def __init__(self, **params: Any) -> None:
        super().__init__(**params)
        self.peers: dict[str, Bars] = {}

    def prepare(self, bars: Bars) -> None:
        p = self.params
        n = len(bars)
        last = bars.dates[-1]
        peers = {t: b.cut(last) for t, b in self.peers.items()}
        peers[bars.ticker] = bars
        ret_n = int(p["ret_n"])
        scores: dict[str, np.ndarray] = {}
        for t, b in peers.items():
            c = pd.Series(b.close)
            scores[t] = (c / c.shift(ret_n) - 1).to_numpy()
        own = scores[bars.ticker]
        sma = pd.Series(bars.close).rolling(int(p["sma"])).mean().to_numpy()
        entry = np.zeros(n, dtype=bool)
        exit_ = np.zeros(n, dtype=bool)
        decision = np.zeros(n, dtype=bool)
        rank_arr = np.full(n, NAN)
        count_arr = np.full(n, NAN)
        for i in range(n):
            d = bars.dates[i]
            if d.weekday() != int(p["weekday"]) or math.isnan(own[i]):
                continue
            valid: list[float] = []
            for t, b in peers.items():
                j = (
                    int(np.searchsorted(b.dates.values, np.datetime64(d), side="right"))
                    - 1
                )
                if j < 0 or (d - b.dates[j]).days > p["stale_days"]:
                    continue
                s = scores[t][j]
                if not math.isnan(s):
                    valid.append(float(s))
            m = len(valid)
            rank = 1 + sum(1 for s in valid if s > own[i])
            decision[i] = True
            rank_arr[i], count_arr[i] = rank, m
            k_top = max(1, _ceil(m * p["top_frac"]))
            k_keep = max(1, _ceil(m * p["keep_frac"]))
            entry[i] = bool(rank <= k_top and bars.close[i] > sma[i])
            exit_[i] = bool(rank > k_keep)
        self.entry_arr, self.exit_arr = entry, exit_
        self.decision_arr, self.rank_arr, self.count_arr = decision, rank_arr, count_arr

    def exit_signal(self, i: int, pos: Position) -> str | None:
        return "dropped out of top half" if self.exit_arr[i] else None


# --------------------------------------------------------------------------------------------------
# W4 support bounce v2
# --------------------------------------------------------------------------------------------------
class SrBounceV2(SwingRule):
    id = "W4_SR_BOUNCE_V2"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "pivot": 5,
        "zone": 0.01,
        "min_touches": 2,
        "touch_lookback": 250,
        "touch_gap": 3,
        "confirm_bars": 3,
        "sma": 50,
        "atr_n": 14,
        "atr_mult": 1.0,
        "broken": 0.02,
        "zone_life": 250,
        "target_lookback": 250,
        "max_bars": 15,
    }
    FIXED: ClassVar[tuple[str, ...]] = ()

    def prepare(self, bars: Bars) -> None:
        p = self.params
        n = len(bars)
        k = int(p["pivot"])
        highs, lows = pivot_lists(bars.high, bars.low, k)
        a = atr(bars, int(p["atr_n"]))
        sma = pd.Series(bars.close).rolling(int(p["sma"])).mean().to_numpy()
        entry = np.zeros(n, dtype=bool)
        stop = np.full(n, NAN)
        target = np.full(n, NAN)
        zone = float(p["zone"])
        zones: list[dict[str, float]] = []
        # a zone is born when its swing low is confirmed and at least ``min_touches`` distinct earlier touches exist
        born: dict[int, list[dict[str, float]]] = {}
        for conf, pb, level in lows:
            lo_b = max(0, pb - int(p["touch_lookback"]))
            seg = bars.low[lo_b:pb]
            hit = np.nonzero((seg >= level * (1 - zone)) & (seg <= level * (1 + zone)))[
                0
            ]
            touches, last_hit = 0, -(10**9)
            for h in hit:
                if h - last_hit > p["touch_gap"]:
                    touches += 1
                last_hit = int(h)
            if touches >= p["min_touches"]:
                born.setdefault(conf, []).append({"level": level, "born": conf})
        hi_ptr = 0
        armed: dict[str, float] | None = None
        for t in range(n):
            while hi_ptr < len(highs) and highs[hi_ptr][0] <= t:
                hi_ptr += 1
            zones.extend(born.get(t, []))
            zones = [
                z
                for z in zones
                if t - z["born"] <= p["zone_life"]
                and bars.close[t] >= z["level"] * (1 - p["broken"])
            ]
            if armed is not None:
                if bars.close[t] < armed["level"] * (1 - p["broken"]):
                    armed = None
                elif t > armed["t"]:
                    if (
                        bars.close[t] > armed["high"]
                        and not math.isnan(sma[t])
                        and bars.close[t] > sma[t]
                    ):
                        tgt = target_swing_high(
                            highs,
                            hi_ptr,
                            bars.close[t],
                            t,
                            int(p["target_lookback"]),
                            True,
                        )
                        stp = armed["level"] * (1 - zone) - p["atr_mult"] * a[t]
                        if (
                            not math.isnan(tgt)
                            and not math.isnan(stp)
                            and stp < bars.close[t]
                        ):
                            entry[t], stop[t], target[t] = True, stp, tgt
                        armed = None
                    elif t >= armed["t"] + p["confirm_bars"]:
                        armed = None
            if armed is None:
                for z in sorted(zones, key=lambda z: -z["level"]):
                    if bars.low[t] <= z["level"] * (1 + zone) and bars.close[t] >= z[
                        "level"
                    ] * (1 - zone):
                        armed = {
                            "t": t,
                            "level": z["level"],
                            "high": float(bars.high[t]),
                        }
                        break
        self.entry_arr, self.stop_arr, self.target_arr = entry, stop, target


# --------------------------------------------------------------------------------------------------
# W6 market mechanics: liquidity sweep then market shift
# --------------------------------------------------------------------------------------------------
class MmSweepShift(SwingRule):
    id = "W6_MM_SWEEP_SHIFT"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "pivot": 5,
        "weekly_n": 10,
        "discount": 0.5,
        "sweep_window": 5,
        "sweep_levels": 3,
        "atr_n": 14,
        "atr_mult": 0.5,
        "partial": 0.5,
        "exit_n": 10,
        "target_lookback": 250,
        "max_bars": 20,
    }
    FIXED: ClassVar[tuple[str, ...]] = ("sweep_levels",)

    def prepare(self, bars: Bars) -> None:
        p = self.params
        n = len(bars)
        highs, lows = pivot_lists(bars.high, bars.low, int(p["pivot"]))
        a = atr(bars, int(p["atr_n"]))
        wsma = weekly_sma(bars, int(p["weekly_n"]))
        entry = np.zeros(n, dtype=bool)
        stop = np.full(n, NAN)
        target = np.full(n, NAN)
        hi_ptr = lo_ptr = 0
        sweeps: list[tuple[int, float]] = []
        for t in range(n):
            if (
                lo_ptr > 0 and hi_ptr > 0
            ):  # sweep of a swing low confirmed before this bar, in discount
                recent = lows[max(0, lo_ptr - int(p["sweep_levels"])) : lo_ptr]
                sh, sl = highs[hi_ptr - 1][2], lows[lo_ptr - 1][2]
                if (
                    sh > sl
                    and bars.close[t] < sl + p["discount"] * (sh - sl)
                    and any(
                        bars.low[t] < v and bars.close[t] > v for (_, _, v) in recent
                    )
                ):
                    sweeps.append((t, float(bars.low[t])))
            while hi_ptr < len(highs) and highs[hi_ptr][0] <= t:
                hi_ptr += 1
            while lo_ptr < len(lows) and lows[lo_ptr][0] <= t:
                lo_ptr += 1
            if not sweeps or t < 1 or t - sweeps[-1][0] > p["sweep_window"] - 1:
                continue
            if math.isnan(wsma[t]) or bars.close[t] <= wsma[t] or math.isnan(a[t]):
                continue
            lower_high = NAN
            for j in range(hi_ptr - 1, 0, -1):
                if highs[j][2] < highs[j - 1][2]:
                    lower_high = highs[j][2]
                    break
            if math.isnan(lower_high) or not (
                bars.close[t] > lower_high and bars.close[t - 1] <= lower_high
            ):
                continue
            tgt = target_swing_high(
                highs, hi_ptr, bars.close[t], t, int(p["target_lookback"]), False
            )
            stp = sweeps[-1][1] - p["atr_mult"] * a[t]
            if not math.isnan(tgt) and stp < bars.close[t]:
                entry[t], stop[t], target[t] = True, stp, tgt
        self.entry_arr, self.stop_arr, self.target_arr = entry, stop, target
        prior_low = (
            pd.Series(bars.low).shift(1).rolling(int(p["exit_n"])).min().to_numpy()
        )
        self.exit_arr = _lt(bars.close, prior_low)
        self.wsma_arr = wsma

    def on_fill(self, i: int, pos: Position) -> None:
        super().on_fill(i, pos)
        pos.extra["partial"] = float(self.params["partial"])

    def exit_signal(self, i: int, pos: Position) -> str | None:
        if pos.bars >= self.params["max_bars"]:
            return "time exit"
        if pos.extra.get("tp_done") and self.exit_arr[i]:
            return "trail: close below prior low"
        return None


# --------------------------------------------------------------------------------------------------
# W7 fresh demand zone / order block retest
# --------------------------------------------------------------------------------------------------
class MmDemandRetest(SwingRule):
    id = "W7_MM_DEMAND_RETEST"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "pivot": 5,
        "atr_n": 14,
        "impulse_atr": 2.0,
        "impulse_bars": 3,
        "discount": 0.5,
        "zone_life": 120,
        "target_lookback": 250,
        "max_bars": 20,
    }
    FIXED: ClassVar[tuple[str, ...]] = ()

    def prepare(self, bars: Bars) -> None:
        p = self.params
        n = len(bars)
        highs, lows = pivot_lists(bars.high, bars.low, int(p["pivot"]))
        a = atr(bars, int(p["atr_n"]))
        entry = np.zeros(n, dtype=bool)
        stop = np.full(n, NAN)
        target = np.full(n, NAN)
        hi_ptr = lo_ptr = 0
        hi_at = np.full(n, NAN)  # latest confirmed swing high value at each bar
        # latest confirmed swing high as of each bar (for the "broke a swing high" test)
        ptr = 0
        cur = NAN
        for t in range(n):
            while ptr < len(highs) and highs[ptr][0] <= t:
                cur = highs[ptr][2]
                ptr += 1
            hi_at[t] = cur
        zones: list[dict[str, float]] = []
        created: set[int] = set()
        for t in range(n):
            while hi_ptr < len(highs) and highs[hi_ptr][0] <= t:
                hi_ptr += 1
            while lo_ptr < len(lows) and lows[lo_ptr][0] <= t:
                lo_ptr += 1
            keep: list[dict[str, float]] = []
            for z in zones:  # a zone is fresh until price first returns into it
                if t - z["born"] > p["zone_life"]:
                    continue
                if bars.low[t] > z["hi"]:
                    keep.append(z)
                    continue
                if entry[t] or hi_ptr < 2 or lo_ptr < 2:
                    continue
                sh, sl = highs[hi_ptr - 1][2], lows[lo_ptr - 1][2]
                bullish = highs[hi_ptr - 1][2] > highs[hi_ptr - 2][2] and (
                    lows[lo_ptr - 1][2] > lows[lo_ptr - 2][2]
                )
                mid = (z["lo"] + z["hi"]) / 2
                in_discount = sh > sl and bars.close[t] < sl + p["discount"] * (sh - sl)
                if bullish and in_discount and bars.close[t] > mid:
                    tgt = target_swing_high(
                        highs,
                        hi_ptr,
                        bars.close[t],
                        t,
                        int(p["target_lookback"]),
                        False,
                    )
                    if not math.isnan(tgt) and z["lo"] < bars.close[t]:
                        entry[t], stop[t], target[t] = True, z["lo"], tgt
            zones = keep
            for m in range(max(1, t - int(p["impulse_bars"])), t):
                if m in created or math.isnan(a[m]) or math.isnan(hi_at[m]):
                    continue
                if (
                    bars.close[m] < bars.open[m]
                    and bars.close[m + 1] > bars.open[m + 1]
                    and bars.close[t] - bars.close[m] >= p["impulse_atr"] * a[m]
                    and bars.close[t] > hi_at[m]
                ):
                    created.add(m)
                    zones.append(
                        {"lo": float(bars.low[m]), "hi": float(bars.high[m]), "born": t}
                    )
        self.entry_arr, self.stop_arr, self.target_arr = entry, stop, target


# --------------------------------------------------------------------------------------------------
# W8 internal bar strength reversion
# --------------------------------------------------------------------------------------------------
class IbsRevert(SwingRule):
    id = "W8_IBS_REVERT"
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "ibs_in": 0.2,
        "sma": 200,
        "ibs_out": 0.8,
        "max_bars": 5,
    }

    def prepare(self, bars: Bars) -> None:
        p = self.params
        rng = bars.high - bars.low
        with np.errstate(invalid="ignore", divide="ignore"):
            ibs = np.where(rng > 0, (bars.close - bars.low) / rng, NAN)
        sma = pd.Series(bars.close).rolling(int(p["sma"])).mean().to_numpy()
        with np.errstate(invalid="ignore"):
            self.entry_arr = np.where(
                np.isnan(ibs) | np.isnan(sma),
                False,
                (ibs < p["ibs_in"]) & (bars.close > sma),
            )
            self.exit_arr = np.where(np.isnan(ibs), False, ibs > p["ibs_out"])
        self.ibs_arr = ibs

    def exit_signal(self, i: int, pos: Position) -> str | None:
        if pos.bars >= self.params["max_bars"]:
            return "time exit"
        return "IBS recovered" if self.exit_arr[i] else None


# --------------------------------------------------------------------------------------------------
# registry (pre-registered; parameters are fixed, nothing is tuned)
# --------------------------------------------------------------------------------------------------
CONTENDERS: dict[str, dict[str, Any]] = {
    "W1_C13C_ORIG": {
        "cls": W1C13C,
        "perturb": ["sma", "dip_bars", "dip", "trail"],
        "rules": [
            "The user's C13C algorithm, K1 logic reused unchanged from lab/aichain/contenders.py.",
            "Close > SMA200 and 5-day return <= -5 percent: buy at the next open; trailing stop 10 percent under the known peak.",
        ],
    },
    "W2_MOM_BREAK_20": {
        "cls": MomBreak,
        "perturb": ["high_n", "ret_n", "sma", "exit_n", "max_bars", "stop"],
        "rules": [
            "Buy at the next open when the close is a 20-day closing high (including today), the 60-day return is > 0 and close > SMA50.",
            "Exit at the next open when close < the lowest low of the prior 10 bars, or after 15 bars (time exit); stop 8 percent under the raw entry open.",
        ],
    },
    "W3_MOM_RANK_WEEKLY": {
        "cls": MomRankWeekly,
        "perturb": ["ret_n", "sma", "top_frac", "keep_frac"],
        "rules": [
            "At the last bar of each week (Friday close; Sunday close for crypto) rank the names of the group by 20-day return (data up to that close).",
            "Buy at the next open (first bar of the week) a name in the top third (rounded up, at least 1) with close > SMA50; each name has its own 1.000 EUR sleeve.",
            "Exit at the next open when the held name is no longer in the top half (rounded up).",
        ],
    },
    "W4_SR_BOUNCE_V2": {
        "cls": SrBounceV2,
        "perturb": [
            "pivot",
            "zone",
            "min_touches",
            "touch_lookback",
            "touch_gap",
            "confirm_bars",
            "sma",
            "atr_n",
            "atr_mult",
            "broken",
            "zone_life",
            "target_lookback",
            "max_bars",
        ],
        "rules": [
            "Demand level = confirmed swing low (5 bars each side) with at least 2 distinct earlier touches (bar lows within +-1 percent, touches > 3 bars apart, 250 bars back).",
            "Trigger: a bar touches the zone (low <= level*1.01 and close >= level*0.99); the first of the NEXT 3 closes above the touch bar high with close > SMA50 is the signal.",
            "Stop = 1 ATR14 under the zone lower edge (level*0.99); target = nearest confirmed swing high above the close; time exit after 15 bars.",
            "A zone dies when a close falls 2 percent under the level or after 250 bars.",
        ],
    },
    "W5_SR_BREAKOUT_RETEST": {
        "cls": W5Retest,
        "perturb": ["pivot", "prox", "stop", "sma_exit", "expiry"],
        "rules": [
            "K5b rules reused unchanged from lab/aichain/contenders.py (break of swing high, retest within 1.5 percent that closes above, stop 3 percent under the level, exit below SMA50)."
        ],
    },
    "W6_MM_SWEEP_SHIFT": {
        "cls": MmSweepShift,
        "perturb": [
            "pivot",
            "weekly_n",
            "discount",
            "sweep_window",
            "atr_n",
            "atr_mult",
            "partial",
            "exit_n",
            "target_lookback",
            "max_bars",
        ],
        "rules": [
            "Weekly bias not bearish: week-to-date close > weekly SMA10 (9 completed weeks plus the current close).",
            "Daily price in discount: the close of the sweep bar is below 50 percent of the range between the latest confirmed swing low and swing high.",
            "Liquidity sweep in the last 5 bars: low through one of the last 3 confirmed swing lows and close back above it.",
            "Trigger: close above the last confirmed lower high (first such close); buy at the next open.",
            "Stop = sweep low - 0.5 ATR14. Target = the latest swing high if above the close, else the nearest confirmed swing high above. Sell half at the target, trail the rest under the prior 10-bar low. Time exit after 20 bars.",
        ],
    },
    "W7_MM_DEMAND_RETEST": {
        "cls": MmDemandRetest,
        "perturb": [
            "pivot",
            "atr_n",
            "impulse_atr",
            "impulse_bars",
            "discount",
            "zone_life",
            "target_lookback",
            "max_bars",
        ],
        "rules": [
            "Zone = high-low range of the last down candle before an up move of >= 2 ATR14 (close to close, within 3 bars) whose close broke the latest confirmed swing high.",
            "Fresh until price first trades back into it. At that first return buy at the next open only if: structure bullish (last two confirmed swing highs and lows both rising), close in discount (< 50 percent of the swing range) and close > zone midpoint.",
            "Stop = zone low; target = latest swing high above the close (else the nearest above); time exit after 20 bars. A zone expires after 120 bars.",
        ],
    },
    "W8_IBS_REVERT": {
        "cls": IbsRevert,
        "perturb": ["ibs_in", "sma", "ibs_out", "max_bars"],
        "rules": [
            "IBS = (close-low)/(high-low). Buy at the next open when IBS < 0.2 and close > SMA200; exit when IBS > 0.8 or after 5 bars."
        ],
    },
    "B0_BUYHOLD": {
        "cls": W0BuyHold,
        "perturb": [],
        "rules": [
            "Buy at the first open of the window and hold to the end. Benchmark, not a strategy."
        ],
    },
}
SINGLE_IDS = [c for c in CONTENDERS if c != "B0_BUYHOLD"]


def make_rule(cid: str, peers: dict[str, Bars] | None = None, **overrides: Any) -> Any:
    rule = CONTENDERS[cid]["cls"](**overrides)
    if isinstance(rule, MomRankWeekly):
        rule.peers = peers or {}
    return rule


def perturbed(cid: str) -> list[tuple[str, float, Any]]:
    """One-at-a-time +-20 percent variants of every threshold (ints rounded, at least 1; duplicates dropped)."""
    cls = CONTENDERS[cid]["cls"]
    out: list[tuple[str, float, Any]] = []
    for key in CONTENDERS[cid]["perturb"]:
        base = cls.DEFAULTS[key]
        seen = {base}
        for f in (0.8, 1.2):
            nv = max(1, round(base * f)) if isinstance(base, int) else base * f
            if nv in seen:
                continue
            seen.add(nv)
            out.append((key, f, nv))
    return out


# --------------------------------------------------------------------------------------------------
# simulator with partial exit
# --------------------------------------------------------------------------------------------------
def run_swing_sleeve(
    bars: Bars,
    rule: Any,
    start: str,
    end: str,
    cost: Cost = DEFAULT_COST,
    capital: float = START_CAPITAL,
) -> SleeveResult | None:
    """Same loop as ``sim.run_sleeve`` plus an optional partial exit at the target (``pos.extra["partial"]``).

    A trade is the whole position: its return is total sale proceeds over the entry cost, legs are listed.
    """
    bars = bars.cut(end)
    if len(bars) == 0:
        return None
    rule.prepare(bars)
    idx = np.nonzero(bars.dates.values >= np.datetime64(pd.Timestamp(start)))[0]
    if len(idx) == 0:
        return None
    i0 = int(idx[0])
    n = len(bars)
    cash = capital
    pos: Position | None = None
    pending_exit: str | None = None
    pending_entry = (
        bool(rule.enter_at_first_bar) if i0 == 0 else bool(rule.entry(i0 - 1))
    )
    equity = np.empty(n - i0)
    exposure = np.zeros(n - i0)
    trades: list[dict[str, Any]] = []
    decisions: list[tuple[str, bool]] = []

    def record(
        i: int, reason: str, detail: str, raw_exit: float, final_sell: float
    ) -> None:
        assert pos is not None
        proceeds = pos.extra.get("proceeds", 0.0) + pos.units * final_sell
        invested = pos.extra["units0"] * pos.entry_price
        ret = proceeds / invested - 1.0
        trades.append(
            {
                "entry_date": str(bars.dates[pos.entry_i].date()),
                "entry_price": pos.entry_price,
                "raw_entry": pos.raw_entry,
                "exit_date": str(bars.dates[i].date()),
                "exit_price": final_sell,
                "raw_exit": raw_exit,
                "reason": reason,
                "detail": detail,
                "return": ret,
                "pnl_eur": ret * START_CAPITAL,
                "bars_held": i - pos.entry_i + 1,
                "partial": bool(pos.extra.get("tp_done")),
            }
        )

    def close_pos(i: int, raw_exit: float, reason: str, detail: str = "") -> None:
        nonlocal cash, pos
        assert pos is not None
        sell = cost.sell(raw_exit)
        cash += pos.units * sell
        record(i, reason, detail, raw_exit, sell)
        rule.on_exit(i, reason)
        pos = None

    for i in range(i0, n):
        o, h, lo, c = bars.open[i], bars.high[i], bars.low[i], bars.close[i]
        if pending_exit is not None and pos is not None:
            close_pos(i, o, "signal", pending_exit)
        pending_exit = None
        if pending_entry and pos is None:
            buy = cost.buy(o)
            pos = Position(i, buy, o, cash / buy, buy)
            pos.extra["units0"] = pos.units
            cash = 0.0
            rule.on_fill(i, pos)
        pending_entry = False
        if pos is not None:
            pos.bars += 1
            if pos.stop is not None and lo <= pos.stop:
                gap = o < pos.stop
                close_pos(i, min(o, pos.stop), "stop", "gap_stop" if gap else "stop")
            elif pos.target is not None and h >= pos.target:
                raw = max(o, pos.target)
                frac = float(pos.extra.get("partial", 0.0))
                if 0.0 < frac < 1.0 and not pos.extra.get("tp_done"):
                    sold = pos.units * frac
                    sell = cost.sell(raw)
                    cash += sold * sell
                    pos.extra["proceeds"] = pos.extra.get("proceeds", 0.0) + sold * sell
                    pos.units -= sold
                    pos.extra["tp_done"] = True
                    pos.target = None
                else:
                    close_pos(i, raw, "target", "target")
            else:
                pos.peak = max(pos.peak, h)
                rule.after_bar(i, pos)
        equity[i - i0] = cash + (pos.units * c if pos is not None else 0.0)
        exposure[i - i0] = (pos.units * c) / equity[i - i0] if pos is not None else 0.0
        if i == n - 1 and pos is not None:
            equity[i - i0] = cash + pos.units * cost.sell(c)
        if pos is not None:
            reason = rule.exit_signal(i, pos)
            if reason is not None:
                pending_exit = reason
            decisions.append((str(bars.dates[i].date()), False))
        else:
            take = bool(rule.entry(i))
            pending_entry = take
            decisions.append((str(bars.dates[i].date()), take))
    if pos is not None:
        last = n - 1
        record(
            last,
            "end",
            "liquidated at last close, exit cost paid",
            float(bars.close[last]),
            cost.sell(float(bars.close[last])),
        )
    return SleeveResult(
        bars.ticker, bars.dates[i0:], equity, exposure, trades, decisions
    )


# --------------------------------------------------------------------------------------------------
# trade metrics
# --------------------------------------------------------------------------------------------------
def trade_metrics(
    trades: list[dict[str, Any]], months: float, sleeve_years: float
) -> dict[str, Any]:
    """What a swing trader feels: frequency, hit rate, expectancy in EUR on 1.000 EUR per trade, streaks.

    ``expectancy_eur`` is the mean trade return times 1.000 (a trade always invests one full 1.000 EUR sleeve
    in this normalisation, so trades are comparable and do not compound).
    """
    n = len(trades)
    out: dict[str, Any] = {
        "trades": n,
        "trades_per_month": n / months if months > 0 else None,
        "trades_per_ticker_year": n / sleeve_years if sleeve_years > 0 else None,
    }
    keys = [
        "hit_rate",
        "avg_win_pct",
        "avg_loss_pct",
        "avg_win_eur",
        "avg_loss_eur",
        "expectancy_eur",
        "profit_factor",
        "median_hold_days",
        "mean_hold_days",
        "longest_losing_streak",
        "top5_profit_share",
    ]
    if n == 0:
        out.update({k: None for k in keys})
        return out
    ordered = sorted(trades, key=lambda t: (t["exit_date"], t["entry_date"]))
    rets = np.array([t["return"] for t in ordered], dtype=float)
    pnl = rets * START_CAPITAL
    wins = rets > 0
    gross_win, gross_loss = float(rets[wins].sum()), float(-rets[~wins].sum())
    hold = np.array(
        [
            (pd.Timestamp(t["exit_date"]) - pd.Timestamp(t["entry_date"])).days
            for t in ordered
        ],
        dtype=float,
    )
    streak = best = 0
    for w in wins:
        streak = 0 if w else streak + 1
        best = max(best, streak)
    total = float(pnl.sum())
    top5 = float(np.sort(pnl)[::-1][:5].sum())
    out.update(
        {
            "hit_rate": float(wins.mean()),
            "avg_win_pct": float(rets[wins].mean()) if wins.any() else None,
            "avg_loss_pct": float(rets[~wins].mean()) if (~wins).any() else None,
            "avg_win_eur": float(pnl[wins].mean()) if wins.any() else None,
            "avg_loss_eur": float(pnl[~wins].mean()) if (~wins).any() else None,
            "expectancy_eur": float(pnl.mean()),
            "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
            "median_hold_days": float(np.median(hold)),
            "mean_hold_days": float(hold.mean()),
            "longest_losing_streak": int(best),
            "top5_profit_share": top5 / total if total > 0 else None,
        }
    )
    return out
