"""Honesty tests: S/R placebo test and the market-mechanics event study (research only, no orders).

S/R placebo: at every month-end of the AI era, the levels known then are compared with control levels over the
next 20 bars (touch rate, bounce vs break). Mechanics: forward returns after a sweep + shift in discount, after a
fresh demand-zone retest and after a BOS in the trend direction, against all days and random days.
Everything uses ``Prepared`` series (lookahead-free). Cluster bootstrap by calendar month: levels or events of
different tickers in the same month are not independent, so whole months are resampled.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import levels as lv
from lab.aichain.sim import AI_ERA_START

SEED = 20261014
HORIZON = 20  # bars after the month-end in which a touch is looked for
RANGE_BARS = 120  # "recent range" used for random placebo levels
MIN_DIST_ATR = 0.5  # levels closer than this to the close are trivially touched: excluded everywhere
SHIFT = 0.03
BOOT = 2000
VARIANTS = ("real", "rand", "up", "dn", "match")


def month_end_indices(dates: pd.DatetimeIndex, start: str, last_ok: int) -> list[int]:
    """Index of the last trading bar of every calendar month from ``start`` whose index is <= ``last_ok``."""
    s = pd.Series(np.arange(len(dates)), index=dates)
    s = s[s.index >= pd.Timestamp(start)]
    ends = s.groupby([s.index.year, s.index.month]).last()
    return [int(i) for i in ends if i <= last_ok]


def _eval_level(
    P: lv.Prepared, m: int, level: float, a: float, last: int
) -> tuple[int, int, int, int]:
    """(valid, touched, bounce, break) of one level over bars m+1..m+20; outcome window may reach m+30."""
    b = P.bars
    s = lv.first_touch(level, a, m + 1, m + HORIZON, b.high, b.low)
    if s is None:
        return 1, 0, 0, 0
    side = 1 if level < b.close[m] else -1
    o = lv.outcome_after_touch(side, level, a, s, b.high, b.low, b.close, last)
    return 1, 1, int(o == "bounce"), int(o == "break")


MATCH_DELTA_ATR = 1.0


def _paired_controls(level: float, close: float, a: float) -> list[float]:
    """Two controls on the same side, 1 ATR closer to and 1 ATR farther from the close than the real level.

    Averaged, they match the real level's distance to first order (touch probability falls with distance)
    and its side (in a rising market most pivots sit below the close and price drifts up), while staying
    1 ATR away from the pivot itself (the touch band is only 0.25 ATR wide). Only defined when the closer
    control is still >= 0.5 ATR from the close, i.e. the real level is >= 1.5 ATR away.
    """
    d = abs(level - close)
    if d < (MIN_DIST_ATR + MATCH_DELTA_ATR) * a:
        return []
    sign = 1.0 if level > close else -1.0
    return [
        close + sign * (d - MATCH_DELTA_ATR * a),
        close + sign * (d + MATCH_DELTA_ATR * a),
    ]


def sr_placebo_rows(
    preps: dict[str, tuple[lv.Prepared, str, int]], rng: np.random.Generator
) -> pd.DataFrame:
    """One row per real level and month-end, with the outcome of the real level and of four control levels.

    Controls: ``rand`` uniform random price in the last-120-bar range; ``up`` / ``dn`` the level shifted by
    +3 / -3 percent; ``match`` two same-side controls 1 ATR closer and 1 ATR farther (``_paired_controls``). Controls closer than
    0.5 ATR to the close are marked invalid (the real levels are filtered the same way).
    """
    rows: list[dict[str, Any]] = []
    for ticker, (P, group, cut) in preps.items():
        b = P.bars
        for m in month_end_indices(
            b.dates, AI_ERA_START, cut - (HORIZON + lv.OUT_BARS)
        ):
            a = float(P.atr[m])
            if np.isnan(a) or m < RANGE_BARS:
                continue
            c = float(b.close[m])
            r_lo = float(b.low[m - RANGE_BARS + 1 : m + 1].min())
            r_hi = float(b.high[m - RANGE_BARS + 1 : m + 1].max())
            last = m + HORIZON + lv.OUT_BARS
            for L in lv.cluster_levels(P.pivots, m, a, c):
                if not (r_lo <= L.price <= r_hi) or abs(L.price - c) < MIN_DIST_ATR * a:
                    continue
                row: dict[str, Any] = {
                    "ticker": ticker,
                    "group": group,
                    "month": str(b.dates[m].to_period("M")),
                    "strength": L.strength,
                    "touches": L.touches,
                }
                cands: dict[str, list[float]] = {"real": [L.price]}
                x = None
                for _ in range(20):
                    x = float(rng.uniform(r_lo, r_hi))
                    if abs(x - c) >= MIN_DIST_ATR * a:
                        break
                    x = None
                cands["rand"] = [] if x is None else [x]
                cands["up"] = [L.price * (1 + SHIFT)]
                cands["dn"] = [L.price * (1 - SHIFT)]
                cands["match"] = _paired_controls(L.price, c, a)
                for v in VARIANTS:
                    tot = [0, 0, 0, 0]
                    for px in cands[v]:
                        if px > 0 and abs(px - c) >= MIN_DIST_ATR * a:
                            tot = [
                                u + w
                                for u, w in zip(tot, _eval_level(P, m, px, a, last))
                            ]
                    for name, val in zip(("n", "t", "b", "k"), tot):
                        row[f"{v}_{name}"] = val
                rows.append(row)
    return pd.DataFrame(rows)


def _sums_by_month(df: pd.DataFrame, cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    g = df.groupby("month")[cols].sum()
    return g.index.to_numpy(), g.to_numpy(float)


def _rates(s: np.ndarray, cols: list[str], v: str) -> tuple[float, float, float]:
    n, t, b, k = (s[cols.index(f"{v}_{x}")] for x in ("n", "t", "b", "k"))
    touch = t / n if n else np.nan
    bounce = b / t if t else np.nan
    brk = k / t if t else np.nan
    return touch, bounce, brk


def compare(df: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any]:
    """Real vs control rates for one subset of levels with cluster-bootstrap 95 percent intervals.

    For every control the differences (real minus control) are reported for the touch rate, the bounce rate
    given a touch and the break rate given a touch. ``up`` and ``dn`` are pooled into one shifted control.
    """
    if df.empty:
        return {"n_levels": 0}
    df = df.copy()
    for x in ("n", "t", "b", "k"):
        df[f"shift_{x}"] = df[f"up_{x}"] + df[f"dn_{x}"]
    for x in ("n", "t", "b", "k"):
        # the paired control exists only for levels >= 1.5 ATR away: compare it with that same subset of real levels
        df[f"mreal_{x}"] = np.where(df["match_n"] > 0, df[f"real_{x}"], 0)
    cols = [
        f"{v}_{x}"
        for v in ("real", "rand", "shift", "match", "mreal")
        for x in ("n", "t", "b", "k")
    ]
    _, sums = _sums_by_month(df, cols)
    total = sums.sum(axis=0)
    out: dict[str, Any] = {"n_levels": len(df), "n_months": len(sums)}
    for v in ("real", "rand", "shift", "match", "mreal"):
        t, bo, br = _rates(total, cols, v)
        out[v] = {
            "n": int(total[cols.index(f"{v}_n")]),
            "touch_rate": t,
            "bounce_rate": bo,
            "break_rate": br,
        }
    boot = []
    for _ in range(BOOT):
        pick = rng.integers(0, len(sums), len(sums))
        s = sums[pick].sum(axis=0)
        boot.append(
            [_rates(s, cols, v) for v in ("real", "rand", "shift", "match", "mreal")]
        )
    boot_arr = np.array(boot)  # (B, 5 variants, 3 metrics)
    names = ("touch_rate", "bounce_rate", "break_rate")
    for j, v in enumerate(("rand", "shift", "match"), start=1):
        diff = {}
        ref_j, ref = (4, "mreal") if v == "match" else (0, "real")
        for q, name in enumerate(names):
            d = boot_arr[:, ref_j, q] - boot_arr[:, j, q]
            point = out[ref][name] - out[v][name]
            diff[name] = {
                "diff": point,
                "ci95": [
                    float(np.nanpercentile(d, 2.5)),
                    float(np.nanpercentile(d, 97.5)),
                ],
            }
        out[f"diff_vs_{v}"] = diff
    return out


def sr_summary(df: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any]:
    out: dict[str, Any] = {
        "all": compare(df, rng),
        "by_group": {},
        "by_strength": {},
        "by_touches": {},
    }
    for g, sub in df.groupby("group"):
        out["by_group"][g] = compare(sub, rng)
    q1, q2 = df["strength"].quantile([1 / 3, 2 / 3])
    out["strength_cuts"] = [float(q1), float(q2)]
    bins = {
        "slabo (donja trećina)": df["strength"] <= q1,
        "srednje": (df["strength"] > q1) & (df["strength"] <= q2),
        "jako (gornja trećina)": df["strength"] > q2,
    }
    for name, mask in bins.items():
        out["by_strength"][name] = compare(df[mask], rng)
    tb = {
        "1 okret": df["touches"] == 1,
        "2 okreta": df["touches"] == 2,
        "3 okreta": df["touches"] == 3,
        "4+ okreta": df["touches"] >= 4,
    }
    for name, mask in tb.items():
        out["by_touches"][name] = compare(df[mask], rng)
    return out


# --- market-mechanics event study --------------------------------------------------------------------------

HORIZONS = (5, 10, 20)
SPACING = 10  # events of one ticker closer than this many bars to the previous kept event are dropped
RT_COST = 0.0005  # 5 bps round trip, the tournament default (2.5 bps per side)
EVENT_NAMES = {
    "E1_sweep_shift_discount": "likvidnostni sweep + promjena karaktera u diskontu",
    "E2_sweep_shift_discount_weekly": "isto, uz bikovski tjedni trend",
    "E3_sweep_shift_discount_weekly_zone": "isto, uz dodir svježe zone potražnje",
    "E4_demand_zone_retest": "prvi povratak u svježu zonu potražnje (zona je držala)",
    "E5_bos_trend": "proboj strukture (BOS) u smjeru bikovskog trenda",
}


def event_flags(P: lv.Prepared, cut: int) -> dict[str, np.ndarray]:
    """Boolean decision-day flags per event type (decision at the close of day t, fill at the open of t+1)."""
    n = len(P.bars)
    b = P.bars
    flags = {k: np.zeros(n, bool) for k in EVENT_NAMES}
    bull_sweeps = [e for e in P.sweeps if e["dir"] == 1]
    sweep_bars = np.zeros(n, bool)
    for e in bull_sweeps:
        # discount means below 50 percent of the swing range known on the sweep bar itself
        if P.pos[e["idx"]] == P.pos[e["idx"]] and P.pos[e["idx"]] < 0.5:
            sweep_bars[e["idx"]] = True
    touch_bars = np.zeros(n, bool)
    for z in P.zones:
        if z["kind"] == "demand" and z["first_return"] is not None:
            touch_bars[z["first_return"]] = True
    for e in P.struct.events:
        t = e["idx"]
        if (
            e["kind"] == "shift"
            and e["dir"] == 1
            and sweep_bars[max(0, t - 15) : t + 1].any()
        ):
            flags["E1_sweep_shift_discount"][t] = True
            if P.wbias[t] == 1:
                flags["E2_sweep_shift_discount_weekly"][t] = True
                if touch_bars[max(0, t - 20) : t + 1].any():
                    flags["E3_sweep_shift_discount_weekly_zone"][t] = True
        if e["kind"] == "bos" and e["dir"] == 1:
            flags["E5_bos_trend"][t] = True
    for z in P.zones:
        u = z["first_return"]
        if z["kind"] != "demand" or u is None or u - z["known"] > 120:
            continue
        if b.close[u] >= z["lo"] and (z["broken"] is None or z["broken"] > u):
            flags["E4_demand_zone_retest"][u] = True
    return flags


def forward_returns(P: lv.Prepared, cut: int) -> dict[int, np.ndarray]:
    """Return from the next open to the close ``h`` bars after the decision day (NaN when beyond ``cut``)."""
    b = P.bars
    n = len(b)
    out: dict[int, np.ndarray] = {}
    for h in HORIZONS:
        r = np.full(n, np.nan)
        for t in range(n):
            if t + h <= cut and t + 1 < n:
                r[t] = b.close[t + h] / b.open[t + 1] - 1.0
        out[h] = r
    return out


def declustered(flag: np.ndarray, valid: np.ndarray) -> np.ndarray:
    keep = []
    last = -(10**9)
    for t in np.flatnonzero(flag & valid):
        if t - last >= SPACING:
            keep.append(t)
            last = t
    return np.array(keep, dtype=int)


def event_table(
    preps: dict[str, tuple[lv.Prepared, str, int]],
    period: tuple[str, str],
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Event study over one period for every event type and horizon."""
    start, end = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    recs: dict[str, list[dict[str, Any]]] = {k: [] for k in EVENT_NAMES}
    base: list[dict[str, Any]] = []
    per_ticker_valid: dict[str, dict[int, np.ndarray]] = {}
    for ticker, (P, group, cut) in preps.items():
        d = P.bars.dates
        valid = np.asarray((d >= start) & (d <= end)) & (
            np.arange(len(d)) + 1 + max(HORIZONS) <= cut
        )
        if not valid.any():
            continue
        fr = forward_returns(P, cut)
        month = d.to_period("M").astype(str).to_numpy()
        per_ticker_valid[ticker] = {h: fr[h][valid] for h in HORIZONS}
        mean_h = {h: float(np.nanmean(fr[h][valid])) for h in HORIZONS}
        for t in np.flatnonzero(valid):
            base.append(
                {
                    "ticker": ticker,
                    "group": group,
                    "month": month[t],
                    **{f"r{h}": fr[h][t] for h in HORIZONS},
                }
            )
        flags = event_flags(P, cut)
        for name, flag in flags.items():
            for t in declustered(flag, valid):
                recs[name].append(
                    {
                        "ticker": ticker,
                        "group": group,
                        "month": month[t],
                        **{f"r{h}": fr[h][t] for h in HORIZONS},
                        **{f"m{h}": mean_h[h] for h in HORIZONS},
                    }
                )
    out: dict[str, Any] = {"period": list(period), "all_days": {}, "events": {}}
    bdf = pd.DataFrame(base)
    for h in HORIZONS:
        r = bdf[f"r{h}"].to_numpy()
        out["all_days"][str(h)] = {
            "n": len(r),
            "mean": float(np.mean(r)),
            "median": float(np.median(r)),
            "hit_rate": float(np.mean(r > 0)),
        }
    for name, rows in recs.items():
        df = pd.DataFrame(rows)
        entry: dict[str, Any] = {"label": EVENT_NAMES[name], "n": len(df)}
        if df.empty:
            out["events"][name] = entry
            continue
        entry["n_tickers"] = int(df["ticker"].nunique())
        entry["by_h"] = {}
        for h in HORIZONS:
            entry["by_h"][str(h)] = _event_stats(df, h, per_ticker_valid, rng)
        entry["by_group_h10"] = {
            g: {
                "n": len(sub),
                "mean_excess": float((sub["r10"] - sub["m10"]).mean()),
            }
            for g, sub in df.groupby("group")
        }
        out["events"][name] = entry
    return out


def _event_stats(
    df: pd.DataFrame,
    h: int,
    valid_r: dict[str, dict[int, np.ndarray]],
    rng: np.random.Generator,
) -> dict[str, Any]:
    r = df[f"r{h}"].to_numpy()
    ex = r - df[f"m{h}"].to_numpy()
    months = df["month"].to_numpy()
    uniq, inv = np.unique(months, return_inverse=True)
    cnt = np.bincount(inv, minlength=len(uniq)).astype(float)
    s_r = np.bincount(inv, weights=r, minlength=len(uniq))
    s_e = np.bincount(inv, weights=ex, minlength=len(uniq))
    s_h = np.bincount(inv, weights=(r > 0).astype(float), minlength=len(uniq))
    bm, be, bh = [], [], []
    for _ in range(BOOT):
        pick = rng.integers(0, len(uniq), len(uniq))
        c = cnt[pick].sum()
        bm.append(s_r[pick].sum() / c)
        be.append(s_e[pick].sum() / c)
        bh.append(s_h[pick].sum() / c)
    # random days: same number of days per ticker, drawn uniformly from that ticker's valid days
    counts = df.groupby("ticker").size()
    rand_means = []
    for _ in range(1000):
        tot = 0.0
        for tk, k in counts.items():
            pool = valid_r[tk][h]
            tot += pool[rng.integers(0, len(pool), k)].sum()
        rand_means.append(tot / counts.sum())
    rm = np.array(rand_means)
    mean = float(r.mean())
    return {
        "n": len(r),
        "mean": mean,
        "mean_net_of_5bps": mean - RT_COST,
        "median": float(np.median(r)),
        "hit_rate": float(np.mean(r > 0)),
        "mean_ci95": [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))],
        "hit_ci95": [float(np.percentile(bh, 2.5)), float(np.percentile(bh, 97.5))],
        "mean_excess_vs_ticker_avg": float(ex.mean()),
        "excess_ci95": [float(np.percentile(be, 2.5)), float(np.percentile(be, 97.5))],
        "random_days_mean": float(rm.mean()),
        "random_days_range95": [
            float(np.percentile(rm, 2.5)),
            float(np.percentile(rm, 97.5)),
        ],
        "p_random_ge": float(np.mean(rm >= mean)),
    }
