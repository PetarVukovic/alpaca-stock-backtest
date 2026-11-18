"""Behaviour profile statistics for one AI-chain segment, computed only from raw daily CSVs.

Read-only on data. Windows: AI era (>= 2023-01-01, main) and pre-2023 (context), both cut at the
common end date from universe.json. Usage:
    .venv/bin/python -m lab.aichain.profile_stats equipment
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
AI_START = pd.Timestamp("2023-01-01")
HORIZONS = (1, 5, 10, 20)
PIVOT_K = 5  # bars on each side that define a swing low/high
SR_BAND = 0.015  # 1.5 percent touch / break band
SR_LOOKAHEAD = 5  # bars after the touch used to judge hold vs break
SR_MAX_AGE = 120  # level is ignored when older than this many bars
THIN_GAP = 10  # min bars between events when thinning overlapping events


def load_close_frame(ticker: str) -> pd.DataFrame:
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv")
    d["date"] = pd.to_datetime(d["date"].astype(str).str[:10])
    d = d.drop_duplicates("date").sort_values("date").set_index("date")
    return d[["open", "high", "low", "close"]].astype(float)


def windows(idx: pd.DatetimeIndex) -> dict[str, pd.Series]:
    ai = pd.Series(idx >= AI_START, index=idx)
    return {"ai_era": ai, "pre_2023": ~ai}


def _r(x: float | int | None, nd: int = 4) -> float | None:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


def drawdowns(close: pd.Series, top: int = 5) -> list[dict[str, Any]]:
    """Top non-overlapping drawdown episodes (peak -> bottom -> recovery) inside the series."""
    peak_val = close.iloc[0]
    peak_date = close.index[0]
    eps: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for dt, px in close.items():
        if px >= peak_val:
            if cur is not None:
                cur["recovery"] = dt
                eps.append(cur)
                cur = None
            peak_val, peak_date = px, dt
        else:
            dd = px / peak_val - 1
            if cur is None:
                cur = {"start": peak_date, "bottom": dt, "depth": dd, "recovery": None}
            elif dd < cur["depth"]:
                cur["bottom"], cur["depth"] = dt, dd
    if cur is not None:
        eps.append(cur)
    eps.sort(key=lambda e: e["depth"])
    out = []
    for e in eps[:top]:
        out.append(
            {
                "start": e["start"].strftime("%Y-%m-%d"),
                "bottom": e["bottom"].strftime("%Y-%m-%d"),
                "recovery": e["recovery"].strftime("%Y-%m-%d")
                if e["recovery"] is not None
                else None,
                "depth_pct": _r(e["depth"] * 100, 1),
            }
        )
    return out


def variance_ratio(r: pd.Series, k: int) -> float:
    """Overlapping k-day variance ratio of daily log returns; >1 trending, <1 mean reverting."""
    lr = np.log1p(r.dropna())
    if len(lr) < 5 * k:
        return float("nan")
    rk = lr.rolling(k).sum().dropna()
    return float(rk.var(ddof=1) / (k * lr.var(ddof=1)))


def thin(mask: pd.Series, gap: int = THIN_GAP) -> list[int]:
    """Positions of events keeping only the first one inside any `gap`-bar span."""
    pos = np.flatnonzero(mask.to_numpy())
    kept: list[int] = []
    for p in pos:
        if not kept or p - kept[-1] >= gap:
            kept.append(int(p))
    return kept


def forward_table(close: pd.Series, pos: list[int], sel: np.ndarray) -> dict[str, Any]:
    """Mean forward return / hit rate after events vs the unconditional distribution in the same window."""
    out: dict[str, Any] = {"n_events": len(pos)}
    for h in HORIZONS:
        fwd = close.shift(-h) / close - 1
        uncond = fwd[sel].dropna()
        ev = fwd.iloc[pos].dropna() if pos else pd.Series(dtype=float)
        ev = ev[sel[[close.index.get_loc(i) for i in ev.index]]] if len(ev) else ev
        row: dict[str, Any] = {
            "n": int(len(ev)),
            "uncond_mean_pct": _r(uncond.mean() * 100, 2),
            "uncond_hit_pct": _r((uncond > 0).mean() * 100, 1),
        }
        if len(ev) >= 1:
            row["mean_pct"] = _r(ev.mean() * 100, 2)
            row["median_pct"] = _r(ev.median() * 100, 2)
            row["hit_pct"] = _r((ev > 0).mean() * 100, 1)
            if len(ev) >= 5 and ev.std(ddof=1) > 0:
                row["t_vs_uncond"] = _r(
                    (ev.mean() - uncond.mean()) / (ev.std(ddof=1) / np.sqrt(len(ev))), 2
                )
        out[f"fwd_{h}d"] = row
    return out


def pivots(
    low: np.ndarray, high: np.ndarray, k: int = PIVOT_K
) -> tuple[list[int], list[int]]:
    lows, highs = [], []
    for i in range(k, len(low) - k):
        if low[i] == low[i - k : i + k + 1].min():
            lows.append(i)
        if high[i] == high[i - k : i + k + 1].max():
            highs.append(i)
    return lows, highs


def sr_events(df: pd.DataFrame, placebo_shift: int = 0) -> list[dict[str, Any]]:
    """First touch of each confirmed swing level, outcome judged over the next SR_LOOKAHEAD closes.

    A pivot at i is only known from bar i+PIVOT_K (no lookahead). placebo_shift moves the level to
    an arbitrary non-pivot bar (i+shift) as a control. Support: price comes down from above the band.
    """
    c, lo, hi = df["close"].to_numpy(), df["low"].to_numpy(), df["high"].to_numpy()
    n = len(c)
    plows, phighs = pivots(lo, hi)
    ev: list[dict[str, Any]] = []
    for kind, plist in (("support", plows), ("resistance", phighs)):
        for p in plist:
            q = p + placebo_shift
            if q >= n:
                continue
            lvl = (
                (lo[q] if kind == "support" else hi[q])
                if placebo_shift
                else (lo[p] if kind == "support" else hi[p])
            )
            start = max(p + PIVOT_K, q) + 1
            for t in range(start, min(n - SR_LOOKAHEAD - 1, p + SR_MAX_AGE)):
                if kind == "support":
                    if c[t] < lvl * (
                        1 - SR_BAND
                    ):  # broken before any touch: level dead
                        break
                    if lo[t] <= lvl * (1 + SR_BAND) and c[t - 1] > lvl * (1 + SR_BAND):
                        fut = c[t : t + SR_LOOKAHEAD + 1]
                        broke = bool((fut < lvl * (1 - SR_BAND)).any())
                        ev.append(
                            {
                                "t": t,
                                "kind": kind,
                                "broke": broke,
                                "fwd5": c[t + SR_LOOKAHEAD] / c[t] - 1,
                            }
                        )
                        break
                else:
                    if c[t] > lvl * (1 + SR_BAND):
                        break
                    if hi[t] >= lvl * (1 - SR_BAND) and c[t - 1] < lvl * (1 - SR_BAND):
                        fut = c[t : t + SR_LOOKAHEAD + 1]
                        broke = bool((fut > lvl * (1 + SR_BAND)).any())
                        ev.append(
                            {
                                "t": t,
                                "kind": kind,
                                "broke": broke,
                                "fwd5": c[t + SR_LOOKAHEAD] / c[t] - 1,
                            }
                        )
                        break
    return ev


def sr_summary(
    ev: list[dict[str, Any]], idx: pd.DatetimeIndex, sel: np.ndarray
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind in ("support", "resistance"):
        e = [x for x in ev if x["kind"] == kind and sel[x["t"]]]
        out[kind] = {
            "n_touches": len(e),
            "hold_pct": _r(100 * np.mean([not x["broke"] for x in e]), 1)
            if e
            else None,
            "break_pct": _r(100 * np.mean([x["broke"] for x in e]), 1) if e else None,
            "mean_fwd5_pct": _r(100 * np.mean([x["fwd5"] for x in e]), 2)
            if e
            else None,
        }
    return out


def profile_ticker(
    tk: str, smh: pd.Series, ndx: pd.Series, peers: pd.DataFrame, end: pd.Timestamp
) -> dict[str, Any]:
    df = load_close_frame(tk)
    df = df[df.index <= end]
    close = df["close"]
    ret = close.pct_change()
    idx = close.index
    sma200 = close.rolling(200).mean()
    dist = close / sma200 - 1
    hi252 = close.rolling(252).max().shift(1)
    new_high = close > hi252
    up = ret > 0
    up3 = up & up.shift(1, fill_value=False) & up.shift(2, fill_value=False)
    ret5 = close / close.shift(5) - 1
    c13 = (ret5 <= -0.05) & (close > sma200)
    gap = df["open"] / close.shift(1) - 1
    peer_ret = peers.drop(columns=[tk], errors="ignore").mean(axis=1)
    sr_real = sr_events(df)
    sr_fake = sr_events(df, placebo_shift=7)
    result: dict[str, Any] = {
        "first_date": idx[0].strftime("%Y-%m-%d"),
        "last_date": idx[-1].strftime("%Y-%m-%d"),
    }
    for wname, wsel in windows(idx).items():
        sel = wsel.to_numpy()
        r = ret[sel].dropna()
        if len(r) < 60:
            result[wname] = {"skipped": f"premalo podataka ({len(r)} dana)"}
            continue
        w: dict[str, Any] = {
            "days": int(len(r)),
            "from": r.index[0].strftime("%Y-%m-%d"),
            "to": r.index[-1].strftime("%Y-%m-%d"),
        }
        w["ann_vol_pct"] = _r(r.std(ddof=1) * np.sqrt(252) * 100, 1)
        w["total_return_pct"] = _r(((1 + r).prod() - 1) * 100, 1)
        w["cagr_pct"] = _r(((1 + r).prod() ** (252 / len(r)) - 1) * 100, 1)
        for name, ref in (("smh", smh), ("ndx", ndx)):
            j = pd.concat([r, ref.pct_change()], axis=1, join="inner").dropna()
            j.columns = ["a", "b"]
            w[f"corr_{name}"] = _r(j["a"].corr(j["b"]), 3)
            w[f"beta_{name}"] = _r(j["a"].cov(j["b"]) / j["b"].var(), 2)
        w["drawdowns"] = drawdowns(close[sel])
        w["autocorr_lag1_5"] = [_r(r.autocorr(k), 3) for k in range(1, 6)]
        w["var_ratio_5d"] = _r(variance_ratio(r, 5), 2)
        w["var_ratio_20d"] = _r(variance_ratio(r, 20), 2)
        # C13C premise, new 52-week high, three up days
        for key, mask in (
            ("after_5d_drop_ge5pct_above_sma200", c13),
            ("after_new_52w_high", new_high),
            ("after_3_up_days", up3),
        ):
            m = mask & wsel
            pos_all = list(np.flatnonzero(m.to_numpy()))
            pos_thin = thin(m)
            t_all = forward_table(close, pos_all, sel)
            t_thin = forward_table(close, pos_thin, sel)
            w[key] = {"all_events": t_all, "thinned_events_10d_apart": t_thin}
        # seasonality
        mret = close.resample("ME").last().pct_change().dropna()
        mret = mret[mret.index <= idx[-1]]  # drop the unfinished last month
        mret = mret[(mret.index >= AI_START) == (wname == "ai_era")]
        seas = {}
        for mth in range(1, 13):
            x = mret[mret.index.month == mth]
            seas[str(mth)] = {
                "n": int(len(x)),
                "mean_pct": _r(x.mean() * 100, 1) if len(x) else None,
                "pos_share_pct": _r((x > 0).mean() * 100, 0) if len(x) else None,
            }
        w["seasonality"] = seas
        w["seasonality_warning"] = (
            (
                f"po mjesecu je samo {int(mret.groupby(mret.index.month).size().max())} opažanja po kalendarskom mjesecu: "
                "premalo za zaključak, samo opis"
            )
            if len(mret)
            else "nema podataka"
        )
        # gaps and concentration
        g = gap[sel].dropna()
        top_g = g.reindex(g.abs().sort_values(ascending=False).index[:5])
        w["largest_gaps"] = [
            {"date": d.strftime("%Y-%m-%d"), "gap_pct": _r(v * 100, 1)}
            for d, v in top_g.items()
        ]
        lr = np.log1p(r)
        best10 = lr.nlargest(10)
        w["top10_best_days"] = {
            "dates": [d.strftime("%Y-%m-%d") for d in best10.index],
            "sum_logret_share_of_total_pct": _r(best10.sum() / lr.sum() * 100, 0)
            if lr.sum() > 0
            else None,
            "total_return_without_best10_pct": _r(
                (np.exp(lr.sum() - best10.sum()) - 1) * 100, 1
            ),
        }
        # lead / lag: corr(r_tk[t], ref[t-k]) = ref leads; corr(ref[t], r_tk[t-k]) = tk leads
        ll: dict[str, Any] = {}
        for name, ref in (("smh", smh.pct_change()), ("peers", peer_ret)):
            j = pd.concat([ret, ref], axis=1, join="inner")
            j.columns = ["a", "b"]
            j = j[sel[[idx.get_loc(i) for i in j.index]]] if len(j) else j
            row = {"corr_same_day": _r(j["a"].corr(j["b"]), 3)}
            for k in (1, 2, 3):
                row[f"ref_leads_lag{k}"] = _r(j["a"].corr(j["b"].shift(k)), 3)
                row[f"tk_leads_lag{k}"] = _r(j["b"].corr(j["a"].shift(k)), 3)
            lead = np.nanmean([row["tk_leads_lag1"], row["tk_leads_lag2"]])
            foll = np.nanmean([row["ref_leads_lag1"], row["ref_leads_lag2"]])
            row["verdict"] = (
                "vodi"
                if lead - foll > 0.03
                else "slijedi"
                if foll - lead > 0.03
                else "istodobno (bez jasnog vodstva)"
            )
            ll[name] = row
        w["lead_lag"] = ll
        # distance from SMA200
        d_ = dist[sel].dropna()
        buckets = [
            (-9, 0, "ispod SMA200"),
            (0, 0.10, "0-10% iznad"),
            (0.10, 0.25, "10-25% iznad"),
            (0.25, 9, ">25% iznad"),
        ]
        f20 = (close.shift(-20) / close - 1)[sel]
        bk = []
        for lo_, hi_, lab in buckets:
            m = (d_ > lo_) & (d_ <= hi_)
            fw = f20.reindex(d_.index)[m].dropna()
            bk.append(
                {
                    "bucket": lab,
                    "share_of_days_pct": _r(m.mean() * 100, 1),
                    "n_fwd": int(len(fw)),
                    "mean_fwd20_pct": _r(fw.mean() * 100, 2) if len(fw) else None,
                    "hit_fwd20_pct": _r((fw > 0).mean() * 100, 1) if len(fw) else None,
                }
            )
        w["sma200_distance"] = {
            "median_pct": _r(d_.median() * 100, 1),
            "p10_pct": _r(d_.quantile(0.1) * 100, 1),
            "p90_pct": _r(d_.quantile(0.9) * 100, 1),
            "max_pct": _r(d_.max() * 100, 1),
            "share_above_sma200_pct": _r((d_ > 0).mean() * 100, 1),
            "buckets": bk,
        }
        w["support_resistance"] = {
            "real_pivots": sr_summary(sr_real, idx, sel),
            "placebo_arbitrary_levels": sr_summary(sr_fake, idx, sel),
        }
        result[wname] = w
    return result


def flat_rows(tk: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for wname in ("ai_era", "pre_2023"):
        w = p.get(wname, {})
        if "days" not in w:
            continue
        c13 = w["after_5d_drop_ge5pct_above_sma200"]["thinned_events_10d_apart"]
        row = {
            "ticker": tk,
            "window": wname,
            "days": w["days"],
            "ann_vol_pct": w["ann_vol_pct"],
            "total_return_pct": w["total_return_pct"],
            "corr_smh": w["corr_smh"],
            "beta_smh": w["beta_smh"],
            "corr_ndx": w["corr_ndx"],
            "beta_ndx": w["beta_ndx"],
            "worst_dd_pct": w["drawdowns"][0]["depth_pct"] if w["drawdowns"] else None,
            "ac1": w["autocorr_lag1_5"][0],
            "ac2": w["autocorr_lag1_5"][1],
            "ac3": w["autocorr_lag1_5"][2],
            "ac4": w["autocorr_lag1_5"][3],
            "ac5": w["autocorr_lag1_5"][4],
            "vr5": w["var_ratio_5d"],
            "vr20": w["var_ratio_20d"],
            "c13_n_thinned": c13["n_events"],
        }
        for h in HORIZONS:
            f = c13[f"fwd_{h}d"]
            row[f"c13_mean_fwd{h}_pct"] = f.get("mean_pct")
            row[f"c13_hit_fwd{h}_pct"] = f.get("hit_pct")
            row[f"uncond_mean_fwd{h}_pct"] = f["uncond_mean_pct"]
            row[f"uncond_hit_fwd{h}_pct"] = f["uncond_hit_pct"]
        h52 = w["after_new_52w_high"]["thinned_events_10d_apart"]
        row["high52_n_thinned"] = h52["n_events"]
        row["high52_mean_fwd20_pct"] = h52["fwd_20d"].get("mean_pct")
        u3 = w["after_3_up_days"]["thinned_events_10d_apart"]
        row["up3_n_thinned"] = u3["n_events"]
        row["up3_mean_fwd5_pct"] = u3["fwd_5d"].get("mean_pct")
        row["top10_share_pct"] = w["top10_best_days"]["sum_logret_share_of_total_pct"]
        row["return_without_best10_pct"] = w["top10_best_days"][
            "total_return_without_best10_pct"
        ]
        row["leadlag_vs_smh"] = w["lead_lag"]["smh"]["verdict"]
        row["leadlag_vs_peers"] = w["lead_lag"]["peers"]["verdict"]
        row["sma200_median_dist_pct"] = w["sma200_distance"]["median_pct"]
        sr = w["support_resistance"]
        row["support_n"] = sr["real_pivots"]["support"]["n_touches"]
        row["support_hold_pct"] = sr["real_pivots"]["support"]["hold_pct"]
        row["support_hold_placebo_pct"] = sr["placebo_arbitrary_levels"]["support"][
            "hold_pct"
        ]
        row["resist_n"] = sr["real_pivots"]["resistance"]["n_touches"]
        row["resist_hold_pct"] = sr["real_pivots"]["resistance"]["hold_pct"]
        row["resist_hold_placebo_pct"] = sr["placebo_arbitrary_levels"]["resistance"][
            "hold_pct"
        ]
        rows.append(row)
    return rows


def pooled_c13(profiles: dict[str, Any], segment_tickers: list[str]) -> dict[str, Any]:
    """Pool thinned C13C-premise events across tickers (AI era): mean forward return vs pooled unconditional."""
    out: dict[str, Any] = {}
    for h in HORIZONS:
        ev_means, ev_n, hits, un_means, un_hits = [], [], [], [], []
        for tk in segment_tickers:
            w = profiles[tk].get("ai_era", {})
            if "days" not in w:
                continue
            f = w["after_5d_drop_ge5pct_above_sma200"]["thinned_events_10d_apart"][
                f"fwd_{h}d"
            ]
            if f.get("mean_pct") is None:
                continue
            ev_means.append(f["mean_pct"] * f["n"])
            ev_n.append(f["n"])
            hits.append(f["hit_pct"] * f["n"])
            un_means.append(f["uncond_mean_pct"])
            un_hits.append(f["uncond_hit_pct"])
        n = sum(ev_n)
        out[f"fwd_{h}d"] = {
            "n_events_pooled": int(n),
            "mean_pct": _r(sum(ev_means) / n, 2) if n else None,
            "hit_pct": _r(sum(hits) / n, 1) if n else None,
            "uncond_mean_pct_avg_of_tickers": _r(float(np.mean(un_means)), 2)
            if un_means
            else None,
            "uncond_hit_pct_avg_of_tickers": _r(float(np.mean(un_hits)), 1)
            if un_hits
            else None,
        }
    return out


def run(segment: str) -> dict[str, Any]:
    uni = json.load(open(OUT_BASE / "universe.json"))
    end = pd.Timestamp(uni["common_end"])
    tickers = [t["ticker"] for t in uni["segments"][segment]["tickers"] if t["usable"]]
    excluded = [
        {"ticker": t["ticker"], "reason": t.get("exclude_reason")}
        for t in uni["segments"][segment]["tickers"]
        if not t["usable"]
    ]
    smh = load_close_frame("SMH")["close"]
    ndx = load_close_frame("NDX")["close"]
    peers = pd.DataFrame(
        {tk: load_close_frame(tk)["close"].pct_change() for tk in tickers}
    )
    peers = peers[peers.index <= end]
    profiles = {tk: profile_ticker(tk, smh, ndx, peers, end) for tk in tickers}
    rows = [r for tk in tickers for r in flat_rows(tk, profiles[tk])]
    out_dir = OUT_BASE / "segments" / segment
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "profile_stats.csv", index=False)
    return {
        "common_end": uni["common_end"],
        "tickers_used": tickers,
        "excluded": excluded,
        "stats": profiles,
        "pooled_c13_premise_ai_era": pooled_c13(profiles, tickers),
    }


if __name__ == "__main__":
    seg = sys.argv[1] if len(sys.argv) > 1 else "equipment"
    res = run(seg)
    tmp = OUT_BASE / "segments" / seg / "_stats_raw.json"
    json.dump(res, open(tmp, "w"), ensure_ascii=False, indent=1)
    print("ok", tmp)
