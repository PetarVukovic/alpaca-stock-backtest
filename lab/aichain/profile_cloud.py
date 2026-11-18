"""Behaviour statistics (descriptive only) for the AI-chain segment "cloud".

Read-only on raw data. Every number is computed from data/ohlcv/{TICKER}_1d.csv.
Nothing here is a signal, a strategy or a Critic result. Step 1 of 2: this module
writes the raw statistics; lab.aichain.cloud_text adds the Croatian text and writes
profile.json / profile_stats.csv.

Run:
    .venv/bin/python -m lab.aichain.cloud_text
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "reports" / "research" / "AICHAIN_20261014"
AI_START = pd.Timestamp("2023-01-01")
HORIZONS = (1, 5, 10, 20)
MIN_N = 30  # below this many independent episodes an event sample is flagged as small
PIVOT_K = 5  # bars on each side that define a swing pivot
TOUCH_TOL = 0.015  # 1.5 percent band around a prior swing level
LEVEL_MAX_AGE = 120  # trading days a swing level stays relevant
BREAK_WINDOW = (
    3  # days after a touch in which a close beyond the band counts as a break
)


def load_daily(ticker: str) -> pd.DataFrame:
    """Load raw daily bars indexed by date (sorted, de-duplicated)."""
    df = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date").set_index("date")
    return df[["open", "high", "low", "close"]].astype(float)


def clean(v: Any) -> Any:
    """Convert numpy/pandas scalars to JSON-safe python values (NaN becomes None)."""
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 6)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    return v


def window_mask(
    index: pd.DatetimeIndex, window: str, start: pd.Timestamp, end: pd.Timestamp
) -> np.ndarray:
    """Boolean mask for the 'ai' (2023+) or 'ctx' (before 2023) window."""
    if window == "ai":
        return np.asarray((index >= max(AI_START, start)) & (index <= end))
    return np.asarray((index >= start) & (index < AI_START))


def drawdown_episodes(close: pd.Series, top: int = 5) -> list[dict[str, Any]]:
    """Worst non-overlapping drawdown episodes (peak, bottom, recovery) inside the series."""
    peak_val, peak_date = close.iloc[0], close.index[0]
    bottom_val, bottom_date = peak_val, peak_date
    eps: list[dict[str, Any]] = []
    for d, v in close.items():
        if v >= peak_val:
            if bottom_val < peak_val:
                eps.append(
                    {
                        "start": peak_date,
                        "bottom": bottom_date,
                        "recovery": d,
                        "depth": bottom_val / peak_val - 1.0,
                    }
                )
            peak_val, peak_date, bottom_val, bottom_date = v, d, v, d
        elif v < bottom_val:
            bottom_val, bottom_date = v, d
    if bottom_val < peak_val:
        eps.append(
            {
                "start": peak_date,
                "bottom": bottom_date,
                "recovery": None,
                "depth": bottom_val / peak_val - 1.0,
            }
        )
    eps.sort(key=lambda e: e["depth"])
    out = []
    for e in eps[:top]:
        e = dict(e)
        e["trading_days_to_bottom"] = int(
            close.index.get_loc(e["bottom"]) - close.index.get_loc(e["start"])
        )
        e["trading_days_to_recovery"] = (
            int(close.index.get_loc(e["recovery"]) - close.index.get_loc(e["bottom"]))
            if e["recovery"] is not None
            else None
        )
        out.append(e)
    return out


def variance_ratio(logret: pd.Series, q: int) -> dict[str, float]:
    """Lo-MacKinlay variance ratio (overlapping q-day sums) with the homoskedastic z statistic."""
    r = logret.dropna()
    t = len(r)
    if t < q * 10:
        return {"vr": np.nan, "z": np.nan}
    vr = r.rolling(q).sum().dropna().var(ddof=1) / (q * r.var(ddof=1))
    se = np.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * t))
    return {"vr": float(vr), "z": float((vr - 1) / se)}


def forward_returns(close: pd.Series) -> pd.DataFrame:
    """Forward simple returns over HORIZONS (NaN near the end of the series)."""
    return pd.DataFrame({f"f{h}": close.shift(-h) / close - 1.0 for h in HORIZONS})


def event_summary(
    fwd: pd.DataFrame, flag: pd.Series, base: pd.Series, decluster: int = 10
) -> dict[str, Any]:
    """Forward return and hit rate after flagged days versus the baseline day set `base`.

    Events closer than `decluster` bars to the previous kept event are folded into one
    episode, so one selloff is not counted many times.
    """
    ev_idx = fwd.index[flag.reindex(fwd.index).fillna(False).to_numpy()]
    episodes: list[pd.Timestamp] = []
    last = -(10**9)
    for p, d in zip(fwd.index.get_indexer(ev_idx), ev_idx):
        if p - last >= decluster:
            episodes.append(d)
            last = p
    out: dict[str, Any] = {
        "n_events": int(len(ev_idx)),
        "n_episodes": int(len(episodes)),
        "small_sample": bool(len(episodes) < MIN_N),
    }
    base_f = fwd.loc[base.reindex(fwd.index).fillna(False).to_numpy()]
    for h in HORIZONS:
        col = f"f{h}"
        ev = fwd.loc[ev_idx, col].dropna()
        dc = fwd.loc[episodes, col].dropna() if episodes else pd.Series(dtype=float)
        b = base_f[col].dropna()
        out[col] = {
            "mean": ev.mean() if len(ev) else np.nan,
            "median": ev.median() if len(ev) else np.nan,
            "hit": float((ev > 0).mean()) if len(ev) else np.nan,
            "n": int(len(ev)),
            "episodes_mean": dc.mean() if len(dc) else np.nan,
            "episodes_hit": float((dc > 0).mean()) if len(dc) else np.nan,
            "episodes_n": int(len(dc)),
            "base_mean": b.mean(),
            "base_hit": float((b > 0).mean()),
            "base_n": int(len(b)),
        }
    return out


def monthly_seasonality(close: pd.Series) -> dict[str, Any]:
    """Calendar-month returns (month-end to month-end close), grouped by month of the year."""
    r = close.resample("ME").last().pct_change().dropna()
    res: dict[str, Any] = {}
    for m in range(1, 13):
        x = r[r.index.month == m]
        res[str(m)] = {
            "n": int(len(x)),
            "mean": x.mean() if len(x) else np.nan,
            "hit": float((x > 0).mean()) if len(x) else np.nan,
            "small_sample": bool(len(x) < 8),
        }
    return res


def swing_reaction(df: pd.DataFrame, mask: np.ndarray) -> dict[str, Any]:
    """First touch of a confirmed swing low/high within a 1.5 percent band: hold vs break.

    A pivot is confirmed PIVOT_K bars after it formed, so there is no lookahead. Each
    level is counted once (first touch within LEVEL_MAX_AGE bars). Support: touch means
    low <= level*(1+tol); break means any close below level*(1-tol) on the touch day or
    the next BREAK_WINDOW days; hold otherwise. Resistance is the mirror image.
    """
    low, high, close = (
        df["low"].to_numpy(),
        df["high"].to_numpy(),
        df["close"].to_numpy(),
    )
    n = len(df)
    res: dict[str, Any] = {}
    for kind in ("support", "resistance"):
        hold = brk = 0
        f5_hold: list[float] = []
        f5_brk: list[float] = []
        for p in range(PIVOT_K, n - PIVOT_K):
            if kind == "support":
                if low[p] != low[p - PIVOT_K : p + PIVOT_K + 1].min():
                    continue
                lvl = low[p]
            else:
                if high[p] != high[p - PIVOT_K : p + PIVOT_K + 1].max():
                    continue
                lvl = high[p]
            c = p + PIVOT_K
            if kind == "support" and close[c] <= lvl * (1 + TOUCH_TOL):
                continue  # level must sit clearly below price when it becomes known
            if kind == "resistance" and close[c] >= lvl * (1 - TOUCH_TOL):
                continue
            for t in range(c + 1, min(n, c + 1 + LEVEL_MAX_AGE)):
                if kind == "support":
                    touched = low[t] <= lvl * (1 + TOUCH_TOL)
                else:
                    touched = high[t] >= lvl * (1 - TOUCH_TOL)
                if not touched:
                    continue
                win_c = close[t : t + BREAK_WINDOW + 1]
                if kind == "support":
                    broke = bool((win_c < lvl * (1 - TOUCH_TOL)).any())
                else:
                    broke = bool((win_c > lvl * (1 + TOUCH_TOL)).any())
                if mask[t]:
                    f5 = close[t + 5] / close[t] - 1 if t + 5 < n else np.nan
                    if broke:
                        brk += 1
                        f5_brk.append(f5)
                    else:
                        hold += 1
                        f5_hold.append(f5)
                break
        tot = hold + brk
        res[kind] = {
            "touches": tot,
            "hold": hold,
            "break": brk,
            "hold_rate": hold / tot if tot else np.nan,
            "fwd5_mean_after_hold": float(np.nanmean(f5_hold))
            if np.isfinite(f5_hold).any()
            else np.nan,
            "fwd5_mean_after_break": float(np.nanmean(f5_brk))
            if np.isfinite(f5_brk).any()
            else np.nan,
            "small_sample": bool(tot < MIN_N),
        }
    return res


def lead_lag(
    x: pd.Series, ref: pd.Series, mask: pd.Series, max_lag: int = 5
) -> dict[str, Any]:
    """corr(x[t], ref[t+k]); k>0 means x moves first (leads ref), k<0 means x follows ref."""
    df = pd.concat([x, ref], axis=1, keys=["x", "r"], sort=True).dropna()
    df = df[mask.reindex(df.index).fillna(False).to_numpy()]
    out: dict[str, Any] = {"n": int(len(df))}
    lags = {
        str(k): float(df["x"].corr(df["r"].shift(-k))) if len(df) > 30 else np.nan
        for k in range(-max_lag, max_lag + 1)
    }
    out["corr_by_lag"] = lags
    if len(df) > 30:
        band = 2 / np.sqrt(len(df))
        lead, follow = lags["1"], lags["-1"]
        out.update(
            {"noise_band_2se": band, "lead_corr_k+1": lead, "follow_corr_k-1": follow}
        )
        if abs(lead) < band and abs(follow) < band:
            out["verdict"] = "simultaneous"
        else:
            out["verdict"] = "follows" if abs(follow) > abs(lead) else "leads"
    return out


def sma_distance_behaviour(
    close: pd.Series, sma200: pd.Series, fwd: pd.DataFrame, mask: pd.Series
) -> dict[str, Any]:
    """Distance of close from SMA200 and the 20-day forward return by distance bucket."""
    dist = close / sma200 - 1.0
    m = mask & dist.notna()
    d = dist[m]
    res: dict[str, Any] = {
        "days": int(len(d)),
        "share_days_above": float((d > 0).mean()) if len(d) else np.nan,
        "mean": d.mean(),
        "p10": d.quantile(0.1),
        "p50": d.median(),
        "p90": d.quantile(0.9),
        "latest_overall": float(dist.iloc[-1])
        if np.isfinite(dist.iloc[-1])
        else np.nan,
    }
    bk: dict[str, Any] = {}
    for lo, hi, name in [
        (-9, 0, "below_sma200"),
        (0, 0.10, "0_to_10pct_above"),
        (0.10, 0.25, "10_to_25pct_above"),
        (0.25, 9, "over_25pct_above"),
    ]:
        sel = m & (dist > lo) & (dist <= hi)
        f = fwd.loc[sel, "f20"].dropna()
        bk[name] = {
            "n_days": int(sel.sum()),
            "fwd20_mean": f.mean() if len(f) else np.nan,
            "fwd20_hit": float((f > 0).mean()) if len(f) else np.nan,
        }
    res["buckets"] = bk
    return res


def profile_ticker(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    refs: dict[str, pd.Series],
    peers: pd.Series,
) -> dict[str, Any]:
    """Compute every statistic for one ticker over the AI-era and the context window."""
    df = df.loc[(df.index >= start) & (df.index <= end)]
    close = df["close"]
    ret = close.pct_change()
    logret = np.log(close).diff()
    sma200 = close.rolling(
        200
    ).mean()  # computed on full history so early-window days are valid
    fwd = forward_returns(close)
    ev_drop = (close / close.shift(5) - 1.0 <= -0.05) & (close > sma200)
    ev_high = close >= close.shift(1).rolling(252).max()
    ev_up3 = (ret > 0) & (ret.shift(1) > 0) & (ret.shift(2) > 0)
    above = close > sma200
    gap = df["open"] / close.shift(1) - 1.0
    out: dict[str, Any] = {
        "first_date": close.index[0],
        "last_date": close.index[-1],
        "windows": {},
    }
    for w in ("ai", "ctx"):
        mk = pd.Series(window_mask(close.index, w, start, end), index=close.index)
        if mk.sum() < 100:
            out["windows"][w] = {"available": False, "bars": int(mk.sum())}
            continue
        r = ret[mk].dropna()
        lr = logret[mk].dropna()
        best = r.nlargest(10)
        total_log = float(lr.sum())
        g = gap[mk].dropna()
        stats: dict[str, Any] = {
            "available": True,
            "bars": int(mk.sum()),
            "start": close.index[mk.to_numpy()][0],
            "end": close.index[mk.to_numpy()][-1],
            "ann_vol": float(r.std(ddof=1) * np.sqrt(252)),
            "total_return": float(np.exp(total_log) - 1),
            "market": {},
            "drawdowns": drawdown_episodes(close[mk]),
            "character": {
                "autocorr": {str(k): float(lr.autocorr(k)) for k in range(1, 6)},
                "autocorr_2se": float(2 / np.sqrt(len(lr))),
                "vr5": variance_ratio(logret[mk], 5),
                "vr20": variance_ratio(logret[mk], 20),
            },
            "after_drop5_above_sma200": event_summary(fwd, ev_drop & mk, above & mk),
            "after_52w_high": event_summary(fwd, ev_high & mk, mk),
            "after_3_up_days": event_summary(fwd, ev_up3 & mk, mk),
            "seasonality": monthly_seasonality(close[mk]),
            "gaps": {
                "largest": [
                    {"date": d, "gap": float(g[d])} for d in g.abs().nlargest(5).index
                ]
            },
            "concentration": {
                "best10_days": [{"date": d, "ret": float(v)} for d, v in best.items()],
                "total_return": float(np.exp(total_log) - 1),
                "total_return_without_best10": float(
                    np.exp(lr.drop(best.index).sum()) - 1
                ),
                "best10_log_share_of_total": (
                    float(np.log1p(best).sum() / total_log)
                    if total_log > 0.3
                    else np.nan
                ),
            },
            "sma200": sma_distance_behaviour(close, sma200, fwd, mk),
            "swing": swing_reaction(df, mk.to_numpy()),
            "lead_lag": {},
        }
        for name, ref in refs.items():
            j = pd.concat([r, ref.reindex(r.index)], axis=1, keys=["x", "m"]).dropna()
            if len(j) > 60:
                stats["market"][name] = {
                    "corr": float(j["x"].corr(j["m"])),
                    "beta": float(j["x"].cov(j["m"]) / j["m"].var()),
                    "n": int(len(j)),
                }
            stats["lead_lag"][name] = lead_lag(ret, ref, mk)
        stats["lead_lag"]["peers"] = lead_lag(ret, peers, mk)
        out["windows"][w] = stats
    return out


def compute(segment: str = "cloud") -> dict[str, Any]:
    """Compute raw statistics for all usable tickers of the segment (ends at universe common_end)."""
    uni = json.loads((OUT_ROOT / "universe.json").read_text())
    end = pd.Timestamp(uni["common_end"])
    seg = uni["segments"][segment]
    usable = [t for t in seg["tickers"] if t["usable"]]
    excluded = [
        {"ticker": t["ticker"], "reason": t.get("exclude_reason")}
        for t in seg["tickers"]
        if not t["usable"]
    ]
    data = {t["ticker"]: load_daily(t["ticker"]) for t in usable}
    starts = {t["ticker"]: pd.Timestamp(t["effective_start"]) for t in usable}
    refs = {
        "SMH": load_daily("SMH")["close"].pct_change(),
        "NDX": load_daily("NDX")["close"].pct_change(),
    }  # NDX OHLC inconsistent: close only
    rets = {
        k: v["close"].pct_change().loc[(v.index >= starts[k]) & (v.index <= end)]
        for k, v in data.items()
    }
    result: dict[str, Any] = {
        "segment": segment,
        "segment_name": seg["name"],
        "common_end": end,
        "ai_era_start": AI_START,
        "excluded": excluded,
        "tickers": {},
    }
    for tk, df in data.items():
        peers = pd.concat([rets[o] for o in rets if o != tk], axis=1, sort=True).mean(
            axis=1, skipna=True
        )
        result["tickers"][tk] = profile_ticker(df, starts[tk], end, refs, peers)
    return clean(result)
