"""Market-mechanics engine: pivots, structure, BOS / market shift, swing range, liquidity, FVG, zones.

Research only: it never places orders. Every function here is lookahead-free by construction:

- A swing pivot at bar ``p`` needs ``k`` lower (higher) bars on each side, so it is *usable* only from bar
  ``p + k`` (its ``confirm`` index). Everything derived from pivots uses ``confirm <= t`` for decision time ``t``.
- Functions that return per-bar arrays only look at bars ``<= t`` for the value at ``t`` (tests truncate the
  data and require identical results on the common prefix).
- Weekly bars are built from daily bars; a weekly bar is *known* only from the first daily bar after its
  period ended (see ``weekly_bars``).

The vocabulary comes from a discretionary teaching style (swing structure, break of structure, liquidity sweep,
demand zone, fair value gap). Here each term is a strict, testable rule; nothing is assumed to work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

K_PIVOT = 5
ATR_N = 14
EQUAL_TOL = 0.003  # equal highs / lows: within 0.3 percent
IMPULSE_ATR = 2.0
IMPULSE_BARS = 3
SWEEP_MAX_AGE = 60


@dataclass(frozen=True)
class Pivot:
    idx: int  # bar index of the extreme
    confirm: int  # first bar index at which it is usable (idx + k)
    kind: str  # "H" or "L"
    price: float


def atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = ATR_N
) -> np.ndarray:
    """Wilder ATR (causal; NaN until ``n`` true ranges exist)."""
    prev = np.r_[np.nan, close[:-1]]
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    return (
        pd.Series(tr).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean().to_numpy()
    )


def find_pivots(high: np.ndarray, low: np.ndarray, k: int = K_PIVOT) -> list[Pivot]:
    """All swing pivots (strictly higher / lower than ``k`` bars on each side), sorted by confirm index."""
    n = len(high)
    out: list[Pivot] = []
    if n < 2 * k + 1:
        return out
    hs, ls = pd.Series(high), pd.Series(low)
    left_h = hs.shift(1).rolling(k).max().to_numpy()
    right_h = hs[::-1].shift(1).rolling(k).max()[::-1].to_numpy()
    left_l = ls.shift(1).rolling(k).min().to_numpy()
    right_l = ls[::-1].shift(1).rolling(k).min()[::-1].to_numpy()
    with np.errstate(invalid="ignore"):
        is_h = (high > left_h) & (high > right_h)
        is_l = (low < left_l) & (low < right_l)
    for p in np.flatnonzero(is_h | is_l):
        if is_h[p]:
            out.append(Pivot(int(p), int(p) + k, "H", float(high[p])))
        if is_l[p]:
            out.append(Pivot(int(p), int(p) + k, "L", float(low[p])))
    out.sort(key=lambda x: (x.confirm, x.kind))
    return out


def pivots_asof(pivots: list[Pivot], t: int) -> list[Pivot]:
    """Pivots usable at decision bar ``t`` (confirm <= t)."""
    return [p for p in pivots if p.confirm <= t]


def last_pivot_price(pivots: list[Pivot], n: int, kind: str) -> np.ndarray:
    """Per bar: price of the latest usable pivot of ``kind`` (NaN before the first)."""
    arr = np.full(n, np.nan)
    for p in pivots:
        if p.kind == kind and p.confirm < n:
            arr[p.confirm] = p.price
    return pd.Series(arr).ffill().to_numpy()


@dataclass
class Structure:
    """Per-bar market structure plus the list of break events."""

    bias: np.ndarray  # +1 bullish, -1 bearish, 0 range (per bar)
    events: list[dict] = field(
        default_factory=list
    )  # kind: bos / shift, dir, idx, level, level_idx

    def last(self, kind: str, t: int) -> dict | None:
        best = None
        for e in self.events:
            if e["kind"] == kind and e["idx"] <= t:
                best = e
        return best


def pivot_trend(highs: list[Pivot], lows: list[Pivot]) -> int:
    """Bullish = higher high and higher low; bearish = lower high and lower low; else range."""
    if len(highs) < 2 or len(lows) < 2:
        return 0
    hh = highs[-1].price > highs[-2].price
    lh = highs[-1].price < highs[-2].price
    hl = lows[-1].price > lows[-2].price
    ll = lows[-1].price < lows[-2].price
    if hh and hl:
        return 1
    if lh and ll:
        return -1
    return 0


def market_structure(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, k: int = K_PIVOT
) -> Structure:
    """Bias, break of structure (BOS) and market shift, replayed bar by bar.

    - bias comes from the last two usable pivot highs and lows; it is only updated by pivots that formed
      *after* the latest shift (older pivots are already priced in by the shift).
    - A usable pivot level can be broken once, by a close beyond it.
    - In a bullish bias a close above the last pivot high is a BOS (continuation); in a bearish bias a close
      above the last pivot high (the last lower high) is a bullish market shift, and bias flips at once.
      Mirror for lows. In a range (bias 0) a break is not classified.
    """
    n = len(close)
    pivots = find_pivots(high, low, k)
    by_confirm: dict[int, list[Pivot]] = {}
    for p in pivots:
        by_confirm.setdefault(p.confirm, []).append(p)
    highs: list[Pivot] = []
    lows: list[Pivot] = []
    broken_h: set[int] = set()
    broken_l: set[int] = set()
    bias = 0
    last_shift_idx = -1
    out = np.zeros(n, dtype=int)
    events: list[dict] = []
    for t in range(n):
        changed = False
        for p in by_confirm.get(t, []):
            (highs if p.kind == "H" else lows).append(p)
            if p.idx > last_shift_idx:
                changed = True
        if changed:
            pt = pivot_trend(highs, lows)
            if pt != 0:
                bias = pt
        if highs and highs[-1].idx not in broken_h and close[t] > highs[-1].price:
            broken_h.add(highs[-1].idx)
            if bias == 1:
                events.append(_event("bos", 1, t, highs[-1]))
            elif bias == -1:
                events.append(_event("shift", 1, t, highs[-1]))
                bias, last_shift_idx = 1, t
        elif lows and lows[-1].idx not in broken_l and close[t] < lows[-1].price:
            broken_l.add(lows[-1].idx)
            if bias == -1:
                events.append(_event("bos", -1, t, lows[-1]))
            elif bias == 1:
                events.append(_event("shift", -1, t, lows[-1]))
                bias, last_shift_idx = -1, t
        out[t] = bias
    return Structure(out, events)


def _event(kind: str, direction: int, t: int, level: Pivot) -> dict:
    return {
        "kind": kind,
        "dir": direction,
        "idx": t,
        "level": level.price,
        "level_idx": level.idx,
    }


def swing_range_series(
    pivots: list[Pivot], n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per bar: price and index of the last usable swing low and swing high (NaN / -1 before the first)."""
    lo_p = last_pivot_price(pivots, n, "L")
    hi_p = last_pivot_price(pivots, n, "H")
    lo_i = np.full(n, -1.0)
    hi_i = np.full(n, -1.0)
    for p in pivots:
        if p.confirm < n:
            (lo_i if p.kind == "L" else hi_i)[p.confirm] = p.idx
    lo_i = pd.Series(np.where(lo_i < 0, np.nan, lo_i)).ffill().fillna(-1).to_numpy()
    hi_i = pd.Series(np.where(hi_i < 0, np.nan, hi_i)).ffill().fillna(-1).to_numpy()
    return lo_p, hi_p, lo_i, hi_i


def range_position(close: np.ndarray, lo_p: np.ndarray, hi_p: np.ndarray) -> np.ndarray:
    """Position inside the swing range as a fraction (0 = swing low, 1 = swing high; <0 / >1 outside)."""
    width = hi_p - lo_p
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(width > 0, (close - lo_p) / width, np.nan)


# --- liquidity ---------------------------------------------------------------------------------------------


def equal_pools(
    pivots: list[Pivot],
    high: np.ndarray,
    low: np.ndarray,
    t: int,
    lookback: int = 250,
    tol: float = EQUAL_TOL,
) -> dict[str, list[dict]]:
    """Unswept equal-high (above) / equal-low (below) liquidity pools usable at bar ``t``.

    Pivots of one kind within ``tol`` of each other form a pool (2+ members). The pool level is the extreme
    member (stops sit beyond it). It stays *unswept* while no later bar traded beyond the level.
    """
    out: dict[str, list[dict]] = {"above": [], "below": []}
    for kind, key in (("H", "above"), ("L", "below")):
        ps = sorted(
            (
                p
                for p in pivots
                if p.kind == kind and p.confirm <= t and p.idx >= t - lookback
            ),
            key=lambda p: p.price,
        )
        groups: list[list[Pivot]] = []
        for p in ps:
            if groups and p.price <= groups[-1][0].price * (1 + tol):
                groups[-1].append(p)
            else:
                groups.append([p])
        for g in groups:
            if len(g) < 2:
                continue
            level = max(p.price for p in g) if kind == "H" else min(p.price for p in g)
            last_i = max(p.idx for p in g)
            after = (high if kind == "H" else low)[last_i + 1 : t + 1]
            swept = bool(
                (after > level).any() if kind == "H" else (after < level).any()
            )
            if not swept:
                out[key].append(
                    {
                        "level": float(level),
                        "members": len(g),
                        "first_idx": min(p.idx for p in g),
                        "last_idx": last_i,
                    }
                )
    return out


def sweeps(
    pivots: list[Pivot],
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k: int = K_PIVOT,
    max_age: int = SWEEP_MAX_AGE,
) -> list[dict]:
    """Liquidity sweeps: the first bar after a pivot became usable that trades beyond it.

    Bullish sweep of a pivot low L: low < L and close > L (wick through, close back inside). If the first bar
    beyond the pivot closes beyond it, the pivot is simply broken (no sweep). A pivot older than ``max_age``
    bars is ignored. Each event carries ``idx`` (the sweep bar), ``dir`` (+1 sweep of lows, -1 of highs).
    """
    n = len(close)
    out: list[dict] = []
    for p in pivots:
        start = p.confirm + 1
        if start >= n:
            continue
        end = min(n, p.idx + max_age + 1)
        if end <= start:
            continue
        if p.kind == "L":
            hit = np.flatnonzero(low[start:end] < p.price)
            if len(hit):
                s = start + int(hit[0])
                if close[s] > p.price:
                    out.append(
                        {"idx": s, "dir": 1, "level": p.price, "pivot_idx": p.idx}
                    )
        else:
            hit = np.flatnonzero(high[start:end] > p.price)
            if len(hit):
                s = start + int(hit[0])
                if close[s] < p.price:
                    out.append(
                        {"idx": s, "dir": -1, "level": p.price, "pivot_idx": p.idx}
                    )
    out.sort(key=lambda e: e["idx"])
    return out


# --- fair value gaps and zones -----------------------------------------------------------------------------


def fair_value_gaps(
    high: np.ndarray, low: np.ndarray, atr_arr: np.ndarray, t: int, lookback: int = 120
) -> dict[str, list[dict]]:
    """Open (untouched) fair value gaps usable at bar ``t``.

    Bullish: three-candle gap with high[i-2] < low[i] (known at bar i). Open until a later bar trades into it
    (low <= gap top). Bearish mirror: low[i-2] > high[i], open until a later high >= gap bottom.
    """
    out: dict[str, list[dict]] = {"bull": [], "bear": []}
    for i in range(max(2, t - lookback), t + 1):
        if high[i - 2] < low[i]:
            lo_g, hi_g = high[i - 2], low[i]
            later = low[i + 1 : t + 1]
            if not (later <= hi_g).any():
                out["bull"].append(_fvg(i, lo_g, hi_g, atr_arr[i]))
        if low[i - 2] > high[i]:
            lo_g, hi_g = high[i], low[i - 2]
            later = high[i + 1 : t + 1]
            if not (later >= lo_g).any():
                out["bear"].append(_fvg(i, lo_g, hi_g, atr_arr[i]))
    return out


def _fvg(i: int, lo_g: float, hi_g: float, a: float) -> dict:
    return {
        "idx": i,
        "bottom": float(lo_g),
        "top": float(hi_g),
        "size_atr": float((hi_g - lo_g) / a) if a and not np.isnan(a) else None,
    }


def find_zones(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    pivots: list[Pivot],
    atr_arr: np.ndarray,
) -> list[dict]:
    """Demand / supply zones (order blocks), each with the bar from which it is known.

    Demand: the last down candle ``j`` before an impulse: at bar ``m`` (1..3 bars later) the close is at least
    2 ATR14(j) above close[j] AND above the last pivot high usable at ``j`` (the impulse broke a swing high).
    Known from bar ``m``. Zone = high-low range of candle j; ``body`` = open-close range (the order block core).
    Supply is the mirror (last up candle, impulse down through a swing low).
    ``first_return`` = first bar after ``m`` that trades back into the zone (None while fresh);
    ``broken`` = first bar after ``m`` that closes through the far side.
    """
    n = len(close)
    ph = last_pivot_price(pivots, n, "H")
    pl = last_pivot_price(pivots, n, "L")
    zones: list[dict] = []
    used_d: set[int] = set()
    used_s: set[int] = set()
    for m in range(1, n):
        for j in range(m - 1, max(m - IMPULSE_BARS, 0) - 1, -1):
            a = atr_arr[j]
            if np.isnan(a):
                continue
            if (
                close[j] < open_[j]
                and j not in used_d
                and close[m] - close[j] >= IMPULSE_ATR * a
                and close[m] > ph[j]
            ):
                used_d.add(j)
                zones.append(_zone("demand", j, m, open_, high, low, close))
                break
        for j in range(m - 1, max(m - IMPULSE_BARS, 0) - 1, -1):
            a = atr_arr[j]
            if np.isnan(a):
                continue
            if (
                close[j] > open_[j]
                and j not in used_s
                and close[j] - close[m] >= IMPULSE_ATR * a
                and close[m] < pl[j]
            ):
                used_s.add(j)
                zones.append(_zone("supply", j, m, open_, high, low, close))
                break
    for z in zones:
        m = z["known"]
        if z["kind"] == "demand":
            ret = np.flatnonzero(low[m + 1 :] <= z["hi"])
            brk = np.flatnonzero(close[m + 1 :] < z["lo"])
        else:
            ret = np.flatnonzero(high[m + 1 :] >= z["lo"])
            brk = np.flatnonzero(close[m + 1 :] > z["hi"])
        z["first_return"] = m + 1 + int(ret[0]) if len(ret) else None
        z["broken"] = m + 1 + int(brk[0]) if len(brk) else None
    return zones


def _zone(
    kind: str,
    j: int,
    m: int,
    o: np.ndarray,
    h: np.ndarray,
    lo: np.ndarray,
    c: np.ndarray,
) -> dict:
    return {
        "kind": kind,
        "base": j,
        "known": m,
        "lo": float(lo[j]),
        "hi": float(h[j]),
        "body_lo": float(min(o[j], c[j])),
        "body_hi": float(max(o[j], c[j])),
    }


def fresh_zones(zones: list[dict], t: int) -> list[dict]:
    """Zones known at ``t`` that price has not yet returned into and that are not broken."""
    out = []
    for z in zones:
        if z["known"] > t:
            continue
        if z["first_return"] is not None and z["first_return"] <= t:
            continue
        if z["broken"] is not None and z["broken"] <= t:
            continue
        out.append(z)
    return out


# --- weekly bars -------------------------------------------------------------------------------------------


@dataclass
class Weekly:
    """Weekly OHLC built from daily bars plus ``known_at``: the daily bar index from which each week is usable."""

    end: pd.DatetimeIndex  # last daily date inside each week
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    known_at: (
        np.ndarray
    )  # first daily index whose date is after the week's period end (n if none yet)
    complete: np.ndarray


def weekly_bars(
    dates: pd.DatetimeIndex,
    o: np.ndarray,
    h: np.ndarray,
    lo: np.ndarray,
    c: np.ndarray,
    rule: str = "W-FRI",
) -> Weekly:
    """Weekly bars from daily ones (``W-SUN`` for 7-day markets such as crypto).

    A weekly bar is *complete* only if a later daily bar exists after the period end, or the last daily date
    reaches the period end. ``known_at[w]`` is the first daily bar index strictly after the period end, so a
    daily decision at bar ``t`` may use weeks with ``known_at <= t`` only.
    """
    df = pd.DataFrame({"o": o, "h": h, "l": lo, "c": c}, index=dates)
    g = df.groupby(df.index.to_period(rule))
    agg = g.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
    last_date = g.apply(lambda x: x.index[-1])
    ends = pd.DatetimeIndex(last_date.to_numpy())
    period_end = agg.index.to_timestamp(how="end").normalize()
    known = np.searchsorted(
        dates.values, period_end.values.astype("datetime64[ns]"), side="right"
    )
    n = len(dates)
    complete = (known < n) | (dates[-1] >= period_end[-1])
    return Weekly(
        ends,
        agg["o"].to_numpy(float),
        agg["h"].to_numpy(float),
        agg["l"].to_numpy(float),
        agg["c"].to_numpy(float),
        known.astype(int),
        np.asarray(complete),
    )


def weekly_bias_daily(
    w: Weekly, n_daily: int, k: int = K_PIVOT
) -> tuple[np.ndarray, Structure]:
    """Weekly structure bias mapped to every daily bar using only completed weeks (lookahead-free).

    The weekly structure is computed on weeks that are complete; for a daily bar ``t`` the latest week with
    ``known_at <= t`` supplies the value. Structure at weekly bar ``w`` only uses weekly bars ``<= w``.
    """
    mask = w.complete
    idx = np.flatnonzero(mask)
    st = market_structure(w.high[idx], w.low[idx], w.close[idx], k)
    out = np.zeros(n_daily, dtype=int)
    known = w.known_at[idx]
    pos = np.searchsorted(known, np.arange(n_daily), side="right") - 1
    ok = pos >= 0
    out[ok] = st.bias[pos[ok]]
    return out, st
