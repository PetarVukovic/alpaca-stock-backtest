"""Support / resistance levels from confirmed pivots, plus per-ticker market-state preparation.

Research only: it never places orders. Reuses ``lab.aichain.sim.load_bars`` (data rules and bad-tick repair)
and ``lab.aichain.mechanics`` (lookahead-free pivots and structure). A level known at bar ``t`` uses only
pivots with ``confirm <= t``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lab.aichain import mechanics as mx
from lab.aichain.sim import ROOT, Bars, load_bars

CLUSTER_PCT = 0.01
CLUSTER_ATR = 0.5
HALF_LIFE = 250.0
LOOKBACK = 1000
BAND_ATR = 0.25  # a bar "touches" a level when its range comes within 0.25 ATR of it
BOUNCE_ATR = 1.5
BREAK_ATR = 1.0
OUT_BARS = 10
MIN_TOUCHES_FOR_VERDICT = 5


@dataclass
class Level:
    price: float
    members: list[mx.Pivot]
    strength: float

    @property
    def touches(self) -> int:
        return len(self.members)

    @property
    def last_pivot_idx(self) -> int:
        return max(p.idx for p in self.members)


@dataclass
class Prepared:
    """Everything the map and the tests need for one ticker, computed once."""

    ticker: str
    bars: Bars
    volume: np.ndarray
    atr: np.ndarray
    pivots: list[mx.Pivot]
    struct: mx.Structure
    lo_p: np.ndarray
    hi_p: np.ndarray
    lo_i: np.ndarray
    hi_i: np.ndarray
    pos: np.ndarray
    zones: list[dict]
    sweeps: list[dict]
    weekly: mx.Weekly
    wbias: np.ndarray
    wstruct: mx.Structure
    notes: list[str] = field(default_factory=list)


def load_volume(ticker: str, dates: pd.DatetimeIndex) -> np.ndarray:
    raw = pd.read_csv(
        ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"]
    )
    raw = raw.drop_duplicates("date").set_index("date")
    return raw["volume"].reindex(dates).to_numpy(float)


def prepare(ticker: str, end: str = "2099-12-31", crypto: bool = False) -> Prepared:
    """Load a ticker through the shared loader and compute pivots, structure, zones, sweeps and weekly bias."""
    b = load_bars(ticker, end)
    return prepare_from_bars(b, load_volume(ticker, b.dates), crypto)


def prepare_from_bars(b: Bars, volume: np.ndarray, crypto: bool = False) -> Prepared:
    """Same as ``prepare`` for bars already in memory (used by the lookahead tests on synthetic data)."""
    a = mx.atr(b.high, b.low, b.close)
    pv = mx.find_pivots(b.high, b.low)
    st = mx.market_structure(b.high, b.low, b.close)
    lo_p, hi_p, lo_i, hi_i = mx.swing_range_series(pv, len(b))
    pos = mx.range_position(b.close, lo_p, hi_p)
    zones = mx.find_zones(b.open, b.high, b.low, b.close, pv, a)
    sw = mx.sweeps(pv, b.high, b.low, b.close)
    wk = mx.weekly_bars(
        b.dates, b.open, b.high, b.low, b.close, "W-SUN" if crypto else "W-FRI"
    )
    wbias, wst = mx.weekly_bias_daily(wk, len(b))
    return Prepared(
        b.ticker,
        b,
        volume,
        a,
        pv,
        st,
        lo_p,
        hi_p,
        lo_i,
        hi_i,
        pos,
        zones,
        sw,
        wk,
        wbias,
        wst,
        list(b.repairs),
    )


# --- clustering --------------------------------------------------------------------------------------------


def cluster_levels(
    pivots: list[mx.Pivot],
    t: int,
    atr_t: float,
    close_t: float,
    lookback: int = LOOKBACK,
    half_life: float = HALF_LIFE,
) -> list[Level]:
    """Cluster pivots usable at ``t`` (highs and lows together: a broken support often becomes resistance).

    Tolerance = max(1 percent of the close, 0.5 ATR14). Pivots are sorted by price and joined greedily to the
    running cluster while within tolerance of its mean. Level price = recency-weighted mean (half-life 250
    bars); strength = sum of the recency weights.
    """
    known = [p for p in pivots if p.confirm <= t and p.idx >= t - lookback]
    if not known:
        return []
    tol = max(CLUSTER_PCT * close_t, CLUSTER_ATR * (0.0 if np.isnan(atr_t) else atr_t))
    known.sort(key=lambda p: p.price)
    groups: list[list[mx.Pivot]] = [[known[0]]]
    for p in known[1:]:
        mean = float(np.mean([q.price for q in groups[-1]]))
        if p.price - mean <= tol:
            groups[-1].append(p)
        else:
            groups.append([p])
    out = []
    for g in groups:
        w = np.array([0.5 ** ((t - p.idx) / half_life) for p in g])
        price = float(np.average([p.price for p in g], weights=w))
        out.append(Level(price, sorted(g, key=lambda p: p.idx), float(w.sum())))
    return out


# --- touches and outcomes ----------------------------------------------------------------------------------


def outcome_after_touch(
    side: int,
    level: float,
    a: float,
    s: int,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    last: int,
) -> str:
    """Classify what follows a touch at bar ``s``: bounce, break or neither.

    ``side`` +1 = support (price came from above, a bounce is up), -1 = resistance. A break is a close more
    than 1 ATR beyond the level (checked on the touch bar and every later bar). A bounce is a high (low) at
    least 1.5 ATR away from the level, counted only on bars after the touch bar (the touch bar itself began
    on the approach side, so its own range proves nothing). Within one bar the break is checked first
    (conservative). Window: the touch bar plus the next 10 bars, capped at ``last``.
    """
    for j in range(s, min(s + OUT_BARS, last) + 1):
        if side == 1:
            if close[j] < level - BREAK_ATR * a:
                return "break"
            if j > s and high[j] >= level + BOUNCE_ATR * a:
                return "bounce"
        else:
            if close[j] > level + BREAK_ATR * a:
                return "break"
            if j > s and low[j] <= level - BOUNCE_ATR * a:
                return "bounce"
    return "neither"


def first_touch(
    level: float,
    a: float,
    start: int,
    stop: int,
    high: np.ndarray,
    low: np.ndarray,
) -> int | None:
    """First bar in ``[start, stop]`` whose range comes within the touch band of ``level``."""
    b = BAND_ATR * a
    hit = np.flatnonzero(
        (low[start : stop + 1] <= level + b) & (high[start : stop + 1] >= level - b)
    )
    return start + int(hit[0]) if len(hit) else None


def pit_reliability(level: Level, P: Prepared, t: int) -> dict:
    """Out-of-sample reliability of a level: outcome of every past touch, using the level as known then.

    At bar ``s`` the level price is the mean of the member pivots usable before ``s`` (so the pivot that
    created the level is never counted as a bounce of itself). A touch episode starts at a bar whose range is
    within the touch band while none of the 3 bars before it were; the side comes from the previous close.
    Only episodes whose 10-bar outcome window ended by ``t`` are counted.
    Success = price moved >= 1.5 ATR away before closing > 1 ATR beyond the level.
    """
    h, lo, c, a = P.bars.high, P.bars.low, P.bars.close, P.atr
    members = sorted(level.members, key=lambda p: p.confirm)
    n_ep = {"bounce": 0, "break": 0, "neither": 0}
    first = members[0].confirm + 1
    last_start = t - OUT_BARS
    if first > last_start:
        return {"n": 0, **n_ep, "rate": None}
    conf = np.array([m.confirm for m in members])
    prices = np.array([m.price for m in members])
    cum = np.cumsum(prices) / np.arange(1, len(prices) + 1)
    idxs = np.arange(first, last_start + 1)
    k = np.searchsorted(conf, idxs, side="left")  # members with confirm < s
    lvl = cum[np.maximum(k - 1, 0)]
    band = BAND_ATR * a[idxs]
    touch = (lo[idxs] <= lvl + band) & (h[idxs] >= lvl - band) & ~np.isnan(a[idxs])
    last_touch = -10
    for q, s in enumerate(idxs):
        if not touch[q]:
            continue
        if s - last_touch <= 3:
            last_touch = s
            continue
        last_touch = s
        side = 1 if c[s - 1] > lvl[q] else -1
        n_ep[
            outcome_after_touch(side, float(lvl[q]), float(a[s]), int(s), h, lo, c, t)
        ] += 1
    n = sum(n_ep.values())
    return {"n": n, **n_ep, "rate": (n_ep["bounce"] / n) if n else None}


def last_touch_idx(level_price: float, P: Prepared, t: int) -> int | None:
    h, lo, a = P.bars.high, P.bars.low, P.atr
    b = BAND_ATR * np.nan_to_num(a[: t + 1])
    hit = np.flatnonzero(
        (lo[: t + 1] <= level_price + b) & (h[: t + 1] >= level_price - b)
    )
    return int(hit[-1]) if len(hit) else None


# --- round numbers, 52 weeks, volume profile ---------------------------------------------------------------


def nice_step(price: float) -> float:
    """Round-number step: the 1-2-5 x 10^k value closest (in log terms) to 10 percent of ``price``."""
    target = 0.1 * price
    best = min(
        (m * 10.0**e for e in range(-4, 7) for m in (1, 2, 5)),
        key=lambda v: abs(np.log(v / target)),
    )
    return float(best)


def round_number_test(pivots: list[mx.Pivot], t: int, close_t: float) -> dict:
    """Do confirmed pivots cluster at round numbers more than chance? One-sided normal test on the excess.

    For each pivot the step is the nice number nearest 10 percent of its own price; "near" = within 0.5 percent
    of a multiple of the step. Under a uniform price the chance is 2 x 0.5 percent x price / step per pivot.
    """
    known = [p for p in pivots if p.confirm <= t and p.idx >= t - LOOKBACK]
    obs = 0
    exp = 0.0
    var = 0.0
    for p in known:
        step = nice_step(p.price)
        d = abs(p.price - round(p.price / step) * step)
        w = 0.005 * p.price
        prob = min(1.0, 2 * w / step)
        obs += int(d <= w)
        exp += prob
        var += prob * (1 - prob)
    z = (obs - exp) / np.sqrt(var) if var > 0 else 0.0
    step = nice_step(close_t)
    below = np.floor(close_t / step) * step
    cands = [below, below + step]
    near_counts = []
    for r in cands:
        cnt = sum(1 for p in known if abs(p.price - r) <= 0.005 * r)
        near_counts.append({"price": float(r), "pivots_within_0.5pct": cnt})
    return {
        "n_pivots": len(known),
        "near_round": obs,
        "expected_by_chance": round(exp, 2),
        "z": round(float(z), 2),
        "clusters": bool(obs >= 3 and z >= 1.64),
        "step": step,
        "nearest_round": near_counts,
    }


def volume_profile(
    P: Prepared, t: int, window: int = 250, bins: int = 40
) -> dict | None:
    """High-volume nodes of the last ``window`` bars: each bar's volume is spread evenly over the bins its range covers.

    Returns the point of control and up to 3 high-volume nodes (local peaks above 1.25 x the mean bin volume).
    ``volume_available`` is False (equal weights) for series without volume such as indices.
    """
    s = max(0, t - window + 1)
    h, lo = P.bars.high[s : t + 1], P.bars.low[s : t + 1]
    vol = P.volume[s : t + 1]
    have = bool(np.isfinite(vol).all() and vol.sum() > 0)
    if not have:
        vol = np.ones_like(h)
    edges = np.linspace(lo.min(), h.max(), bins + 1)
    hist = np.zeros(bins)
    for hi_b, lo_b, v in zip(h, lo, vol):
        left = np.maximum(edges[:-1], lo_b)
        right = np.minimum(edges[1:], hi_b)
        ov = np.clip(right - left, 0, None)
        tot = ov.sum()
        if tot > 0:
            hist += v * ov / tot
        else:
            hist[
                min(int(np.searchsorted(edges, lo_b, side="right")) - 1, bins - 1)
            ] += v
    centers = (edges[:-1] + edges[1:]) / 2
    mean = hist.mean()
    peaks = [
        i
        for i in range(bins)
        if hist[i] >= hist[max(i - 2, 0) : i + 3].max() and hist[i] >= 1.25 * mean
    ]
    peaks.sort(key=lambda i: -hist[i])
    return {
        "volume_available": have,
        "poc": float(centers[int(hist.argmax())]),
        "nodes": [
            {"price": float(centers[i]), "share_of_volume": float(hist[i] / hist.sum())}
            for i in peaks[:3]
        ],
    }
