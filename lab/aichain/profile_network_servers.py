"""Behaviour profile statistics for the network_servers segment (description only, not a strategy).

Everything is computed from raw daily CSVs in data/ohlcv. No orders, no signals.
Run:
    .venv/bin/python -m lab.aichain.profile_network_servers
Writes segments/network_servers/profile_stats.csv and profile_numbers.json (numbers only);
the Croatian narrative is merged in by lab.aichain.profile_network_servers_build.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SEGMENT = "network_servers"
AI_START = pd.Timestamp("2023-01-01")
ANN = 252
HORIZONS = (1, 5, 10, 20)
COOLDOWN = 20  # de-clustering gap so overlapping forward windows are not double counted
SR_PIVOT = (
    5  # swing pivot needs 5 bars each side; confirmed 5 bars later (no lookahead)
)
SR_ZONE = 0.015
SR_LOOKBACK = 120
SR_HOLD_DAYS = 5
MIN_EVENTS_WARN = 20


def load_ohlc(ticker: str, end: pd.Timestamp, start: str | None = None) -> pd.DataFrame:
    """Load daily OHLC by header names, cut at the common end date and the effective start."""
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv")
    d["date"] = pd.to_datetime(d["date"].astype(str).str[:10])
    d = d.sort_values("date").drop_duplicates("date").set_index("date")
    d = d[d.index <= end]
    if start:
        d = d[d.index >= pd.Timestamp(start)]
    return d


def window_mask(idx: pd.DatetimeIndex, window: str) -> np.ndarray:
    return (
        np.asarray(idx >= AI_START)
        if window == "ai_era"
        else np.asarray(idx < AI_START)
    )


def drawdown_episodes(close: pd.Series, top: int = 5) -> list[dict[str, Any]]:
    """Worst drawdown episodes (peak, trough, recovery to the old peak) on one close series."""
    dd = close / close.cummax() - 1.0
    episodes: list[dict[str, Any]] = []
    start: pd.Timestamp | None = None
    for i, (dt, v) in enumerate(dd.items()):
        if v < 0 and start is None:
            start = close.index[i - 1] if i > 0 else dt
        if start is not None and v == 0:
            seg = dd.loc[start:dt]
            episodes.append(
                {
                    "start": start,
                    "bottom": seg.idxmin(),
                    "recovery": dt,
                    "depth": float(seg.min()),
                }
            )
            start = None
    if start is not None:
        seg = dd.loc[start:]
        episodes.append(
            {
                "start": start,
                "bottom": seg.idxmin(),
                "recovery": None,
                "depth": float(seg.min()),
            }
        )
    episodes.sort(key=lambda e: e["depth"])
    out = []
    for e in episodes[:top]:
        rec = e["recovery"]
        out.append(
            {
                "start": e["start"].strftime("%Y-%m-%d"),
                "bottom": e["bottom"].strftime("%Y-%m-%d"),
                "recovery": rec.strftime("%Y-%m-%d") if rec is not None else None,
                "depth_pct": round(e["depth"] * 100, 1),
                "days_to_bottom": int((e["bottom"] - e["start"]).days),
                "days_to_recover": int((rec - e["bottom"]).days)
                if rec is not None
                else None,
            }
        )
    return out


def variance_ratio(logret: pd.Series, q: int) -> float | None:
    """Overlapping variance ratio Var(q-day return) / (q * Var(1-day return)); None if sample is short."""
    r = logret.dropna()
    if len(r) < q * 8:
        return None
    v1 = r.var()
    return float(r.rolling(q).sum().dropna().var() / (q * v1)) if v1 > 0 else None


def declustered(mask: pd.Series, gap: int = COOLDOWN) -> list[int]:
    """Positions of event days, keeping only events at least `gap` bars after the previous kept one."""
    kept: list[int] = []
    last = -(10**9)
    for pos in np.flatnonzero(mask.to_numpy()):
        if pos - last >= gap:
            kept.append(int(pos))
            last = int(pos)
    return kept


def forward_table(
    close: pd.Series, in_win: np.ndarray, cond: pd.Series, label: str
) -> dict[str, Any]:
    """Forward returns (close t to close t+h) after an event day t vs unconditional, inside a window."""
    cond = cond.fillna(False) & pd.Series(in_win, index=close.index)
    pos_list = declustered(cond)
    res: dict[str, Any] = {
        "event": label,
        "raw_event_days": int(cond.sum()),
        "independent_events": len(pos_list),
        "small_sample_warning": len(pos_list) < MIN_EVENTS_WARN,
    }
    for h in HORIZONS:
        fwd = close.shift(-h) / close - 1.0
        base = fwd[in_win].dropna()
        ev = fwd.iloc[pos_list].dropna() if pos_list else pd.Series(dtype=float)
        res[f"fwd{h}"] = {
            "n": int(len(ev)),
            "mean_pct": round(float(ev.mean() * 100), 2) if len(ev) else None,
            "median_pct": round(float(ev.median() * 100), 2) if len(ev) else None,
            "hit_rate_pct": round(float((ev > 0).mean() * 100), 1) if len(ev) else None,
            "uncond_mean_pct": round(float(base.mean() * 100), 2)
            if len(base)
            else None,
            "uncond_hit_rate_pct": round(float((base > 0).mean() * 100), 1)
            if len(base)
            else None,
        }
    return res


def seasonality(close: pd.Series, in_win: np.ndarray) -> dict[str, Any]:
    """Calendar-month returns from month-end closes; every month carries its sample count."""
    me = close[in_win].resample("ME").last().dropna()
    mret = me.pct_change().dropna()
    out: dict[str, Any] = {}
    for m in range(1, 13):
        s = mret[mret.index.month == m]
        out[str(m)] = {
            "n_months": int(len(s)),
            "mean_pct": round(float(s.mean() * 100), 1) if len(s) else None,
            "hit_rate_pct": round(float((s > 0).mean() * 100), 0) if len(s) else None,
            "small_sample_warning": len(s) < 8,
        }
    return out


def gaps_and_concentration(df: pd.DataFrame, in_win: np.ndarray) -> dict[str, Any]:
    d = df[in_win]
    gap = (d["open"] / d["close"].shift(1) - 1.0).dropna()
    big = gap.reindex(gap.abs().sort_values(ascending=False).index)[:5]
    logret = np.log1p(d["close"].pct_change().dropna())
    total_log = float(logret.sum())
    top10 = logret.sort_values(ascending=False)[:10]
    share = float(top10.sum() / total_log) if total_log > 0 else None
    return {
        "largest_gaps": [
            {"date": i.strftime("%Y-%m-%d"), "gap_pct": round(float(v * 100), 1)}
            for i, v in big.items()
        ],
        "total_return_pct": round(float(np.expm1(total_log) * 100), 1),
        "top10_days_log_share_pct": round(share * 100, 1)
        if share is not None
        else None,
        "return_without_10_best_days_pct": round(
            float(np.expm1(logret.drop(top10.index).sum()) * 100), 1
        ),
        "best_10_days": [
            {
                "date": i.strftime("%Y-%m-%d"),
                "ret_pct": round(float(np.expm1(v) * 100), 1),
            }
            for i, v in top10.items()
        ],
    }


def lead_lag(r: pd.Series, ref: pd.Series, in_win: np.ndarray) -> dict[str, Any]:
    """corr(r_t, ref_{t-k}) for k in -3..3. k>0: ref moved earlier (ref leads); k<0: ticker leads ref."""
    msk = pd.Series(in_win, index=r.index)
    full = pd.concat([r, ref], axis=1, keys=["r", "ref"], sort=True)
    n = int(full.dropna()[msk.reindex(full.dropna().index).fillna(False)].shape[0])
    out: dict[str, Any] = {
        "n_days": n,
        "noise_band_2se": round(2 / np.sqrt(n), 3) if n else None,
    }
    if n < 60:
        out["verdict"] = "nema dovoljno podataka"
        return out
    for k in range(-3, 4):
        pair = pd.concat([full["r"], full["ref"].shift(k)], axis=1).dropna()
        pair = pair[msk.reindex(pair.index).fillna(False)]
        out[f"k{k:+d}"] = (
            round(float(pair.iloc[:, 0].corr(pair.iloc[:, 1])), 3)
            if len(pair) > 30
            else None
        )
    lead, lag, band = out.get("k+1"), out.get("k-1"), out["noise_band_2se"]
    if lead is None or lag is None:
        out["verdict"] = "nema dovoljno podataka"
    elif lead > band and lead > lag + 0.03:
        out["verdict"] = "slijedi referencu (reagira dan nakon nje)"
    elif lag > band and lag > lead + 0.03:
        out["verdict"] = "vodi referencu (pomice se dan prije nje)"
    else:
        out["verdict"] = "nema jasnog vodstva (istodobno kretanje)"
    return out


def sma200_behaviour(close: pd.Series, in_win: np.ndarray) -> dict[str, Any]:
    dist = close / close.rolling(200).mean() - 1.0
    fwd20 = close.shift(-20) / close - 1.0
    w = pd.Series(in_win, index=close.index) & dist.notna()
    dd = dist[w]
    out: dict[str, Any] = {
        "pct_days_above_sma200": round(float((dd > 0).mean() * 100), 1)
        if len(dd)
        else None
    }
    if len(dd) == 0:
        return out
    out["dist_percentiles_pct"] = {
        str(p): round(float(dd.quantile(p / 100) * 100), 1) for p in (5, 25, 50, 75, 95)
    }
    rows = []
    for name, lo, hi in (
        ("ispod SMA200", -9.0, 0.0),
        ("0-20% iznad", 0.0, 0.2),
        ("20-50% iznad", 0.2, 0.5),
        (">50% iznad", 0.5, 99.0),
    ):
        sel = (dist > lo) & (dist <= hi) & w & fwd20.notna()
        f = fwd20[sel]
        rows.append(
            {
                "bucket": name,
                "days": int(len(f)),
                "fwd20_mean_pct": round(float(f.mean() * 100), 2) if len(f) else None,
                "fwd20_hit_rate_pct": round(float((f > 0).mean() * 100), 1)
                if len(f)
                else None,
            }
        )
    out["fwd20_by_distance"] = rows
    last = dist.dropna()
    out["latest_dist_pct"] = round(float(last.iloc[-1] * 100), 1) if len(last) else None
    return out


def pivots(df: pd.DataFrame, k: int = SR_PIVOT) -> list[tuple[int, int, str, float]]:
    """Swing pivots on low/high as (index, confirm_index, kind, level); known only at confirm_index."""
    lo, hi = df["low"].to_numpy(), df["high"].to_numpy()
    rows: list[tuple[int, int, str, float]] = []
    for i in range(k, len(df) - k):
        if lo[i] == lo[i - k : i + k + 1].min():
            rows.append((i, i + k, "low", float(lo[i])))
        if hi[i] == hi[i - k : i + k + 1].max():
            rows.append((i, i + k, "high", float(hi[i])))
    return rows


def support_resistance(df: pd.DataFrame, in_win: np.ndarray) -> dict[str, Any]:
    """First touch of a confirmed swing level (+-1.5%): hold (no close beyond zone in 5 days) or break.

    Support: price arrives from above and the low enters the zone. Resistance: mirror image.
    """
    close, low, high = (
        df["close"].to_numpy(),
        df["low"].to_numpy(),
        df["high"].to_numpy(),
    )
    n = len(df)
    acc = {
        "support": {"hold": 0, "break": 0, "nxt": []},
        "resistance": {"hold": 0, "break": 0, "nxt": []},
    }
    for idx, c0, kind, lvl in pivots(df):
        end = min(n - SR_HOLD_DAYS - 1, idx + SR_LOOKBACK)
        for t in range(c0 + 1, end + 1):
            if kind == "low":
                if close[t - 1] > lvl * (1 + SR_ZONE) and low[t] <= lvl * (1 + SR_ZONE):
                    if in_win[t]:
                        broke = bool(
                            (
                                close[t : t + SR_HOLD_DAYS + 1] < lvl * (1 - SR_ZONE)
                            ).any()
                        )
                        a = acc["support"]
                        a["break" if broke else "hold"] += 1
                        a["nxt"].append(close[t + SR_HOLD_DAYS] / close[t] - 1)
                    break
                if close[t] < lvl * (1 - SR_ZONE):
                    break  # level already broken before any first touch
            else:
                if close[t - 1] < lvl * (1 - SR_ZONE) and high[t] >= lvl * (
                    1 - SR_ZONE
                ):
                    if in_win[t]:
                        broke = bool(
                            (
                                close[t : t + SR_HOLD_DAYS + 1] > lvl * (1 + SR_ZONE)
                            ).any()
                        )
                        a = acc["resistance"]
                        a["break" if broke else "hold"] += 1
                        a["nxt"].append(close[t + SR_HOLD_DAYS] / close[t] - 1)
                    break
                if close[t] > lvl * (1 + SR_ZONE):
                    break
    out: dict[str, Any] = {}
    for k, a in acc.items():
        tch = a["hold"] + a["break"]
        out[k] = {
            "touches": tch,
            "hold": a["hold"],
            "break": a["break"],
            "hold_rate_pct": round(a["hold"] / tch * 100, 1) if tch else None,
            "next5_mean_pct": round(float(np.mean(a["nxt"]) * 100), 2)
            if a["nxt"]
            else None,
            "small_sample_warning": tch < MIN_EVENTS_WARN,
        }
    return out


def ticker_profile(
    t: str,
    df: pd.DataFrame,
    smh: pd.Series,
    ndx: pd.Series,
    peers: pd.Series,
    window: str,
) -> dict[str, Any] | None:
    close = df["close"]
    in_win = window_mask(close.index, window)
    nbars = int(in_win.sum())
    if nbars < 120:
        return None
    ret = close.pct_change()
    logret = np.log(close).diff()
    cw = close[in_win]
    prof: dict[str, Any] = {
        "ticker": t,
        "window": window,
        "bars": nbars,
        "start": cw.index[0].strftime("%Y-%m-%d"),
        "end": cw.index[-1].strftime("%Y-%m-%d"),
    }
    prof["ann_vol_pct"] = round(
        float(ret[in_win].dropna().std() * np.sqrt(ANN) * 100), 1
    )
    prof["cagr_pct"] = round(
        float(((cw.iloc[-1] / cw.iloc[0]) ** (ANN / max(nbars - 1, 1)) - 1) * 100), 1
    )
    for name, ref in (("smh", smh), ("ndx", ndx)):
        pair = pd.concat(
            [ret, ref.pct_change()], axis=1, keys=["a", "b"], sort=True
        ).dropna()
        pair = pair[window_mask(pair.index, window)]
        if len(pair) > 60:
            prof[f"beta_{name}"] = round(
                float(pair["a"].cov(pair["b"]) / pair["b"].var()), 2
            )
            prof[f"corr_{name}"] = round(float(pair["a"].corr(pair["b"])), 2)
        else:
            prof[f"beta_{name}"] = prof[f"corr_{name}"] = None
    prof["worst_drawdowns"] = drawdown_episodes(cw)
    lw = logret[in_win].dropna()
    prof["autocorr_lag1_5"] = {
        str(k): round(float(lw.autocorr(k)), 3) for k in range(1, 6)
    }
    prof["autocorr_noise_band_2se"] = round(2 / np.sqrt(len(lw)), 3)
    vr5, vr20 = variance_ratio(lw, 5), variance_ratio(lw, 20)
    prof["variance_ratio_5"] = None if vr5 is None else round(vr5, 2)
    prof["variance_ratio_20"] = None if vr20 is None else round(vr20, 2)
    if vr20 is None:
        prof["character"] = "nedovoljno podataka"
    elif vr20 > 1.15:
        prof["character"] = "sklon nastavljanju smjera (trend)"
    elif vr20 < 0.85:
        prof["character"] = "sklon vracanju (reverzija)"
    else:
        prof["character"] = "blizu slucajnog hoda"
    sma200 = close.rolling(200).mean()
    drop5 = close / close.shift(5) - 1.0
    prof["after_5d_drop_ge5pct_above_sma200"] = forward_table(
        close,
        in_win,
        (drop5 <= -0.05) & (close > sma200),
        "pad >=5% u 5 dana, a zatvaranje iznad SMA200",
    )
    prof["after_5d_drop_ge5pct_all"] = forward_table(
        close, in_win, drop5 <= -0.05, "pad >=5% u 5 dana (bez filtra)"
    )
    prof["after_new_52w_high"] = forward_table(
        close,
        in_win,
        close > close.shift(1).rolling(252).max(),
        "novi 52-tjedni vrh (zatvaranje)",
    )
    up = ret > 0
    prof["after_3_up_days"] = forward_table(
        close,
        in_win,
        up & up.shift(1, fill_value=False) & up.shift(2, fill_value=False),
        "tri uzastopna rastuca dana",
    )
    prof["seasonality_month"] = seasonality(close, in_win)
    prof.update(gaps_and_concentration(df, in_win))
    prof["lead_lag_vs_smh"] = lead_lag(ret, smh.pct_change(), in_win)
    prof["lead_lag_vs_peers"] = lead_lag(ret, peers, in_win)
    prof["sma200"] = sma200_behaviour(close, in_win)
    prof["support_resistance"] = support_resistance(df, in_win)
    return prof


def flat_row(p: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        k: p.get(k)
        for k in (
            "ticker",
            "window",
            "start",
            "end",
            "bars",
            "ann_vol_pct",
            "cagr_pct",
            "beta_smh",
            "corr_smh",
            "beta_ndx",
            "corr_ndx",
        )
    }
    row["worst_dd_pct"] = (
        p["worst_drawdowns"][0]["depth_pct"] if p["worst_drawdowns"] else None
    )
    for k in range(1, 6):
        row[f"ac{k}"] = p["autocorr_lag1_5"][str(k)]
    row["vr5"], row["vr20"], row["character"] = (
        p["variance_ratio_5"],
        p["variance_ratio_20"],
        p["character"],
    )
    for name, key in (
        ("drop5", "after_5d_drop_ge5pct_above_sma200"),
        ("hi52", "after_new_52w_high"),
        ("up3", "after_3_up_days"),
    ):
        tab = p[key]
        row[f"{name}_events"] = tab["independent_events"]
        for h in (5, 20):
            row[f"{name}_fwd{h}_mean"] = tab[f"fwd{h}"]["mean_pct"]
            row[f"{name}_fwd{h}_hit"] = tab[f"fwd{h}"]["hit_rate_pct"]
            row[f"{name}_fwd{h}_uncond_mean"] = tab[f"fwd{h}"]["uncond_mean_pct"]
            row[f"{name}_fwd{h}_uncond_hit"] = tab[f"fwd{h}"]["uncond_hit_rate_pct"]
    row["top10_share_pct"] = p["top10_days_log_share_pct"]
    row["ret_without_top10_pct"] = p["return_without_10_best_days_pct"]
    row["total_return_pct"] = p["total_return_pct"]
    row["largest_gap_pct"] = (
        p["largest_gaps"][0]["gap_pct"] if p["largest_gaps"] else None
    )
    row["leadlag_smh"] = p["lead_lag_vs_smh"].get("verdict")
    row["leadlag_peers"] = p["lead_lag_vs_peers"].get("verdict")
    row["pct_above_sma200"] = p["sma200"].get("pct_days_above_sma200")
    sr = p["support_resistance"]
    row["support_touch"], row["support_hold_pct"] = (
        sr["support"]["touches"],
        sr["support"]["hold_rate_pct"],
    )
    row["resist_touch"], row["resist_hold_pct"] = (
        sr["resistance"]["touches"],
        sr["resistance"]["hold_rate_pct"],
    )
    return row


def main() -> None:
    uni = json.loads((OUT_BASE / "universe.json").read_text())
    end = pd.Timestamp(uni["common_end"])
    seg = uni["segments"][SEGMENT]
    skipped = [
        {"ticker": t["ticker"], "reason": t.get("exclude_reason", "nije usable")}
        for t in seg["tickers"]
        if not t["usable"]
    ]
    frames: dict[str, pd.DataFrame] = {}
    for t in (x for x in seg["tickers"] if x["usable"]):
        d = load_ohlc(t["ticker"], end, t["effective_start"])
        if (
            t["ticker"] == "SMCI"
        ):  # first bar after the halt carries a +72% resume jump: drop it
            d = d[d.index > pd.Timestamp(t["effective_start"])]
        frames[t["ticker"]] = d
    smh = load_ohlc("SMH", end)["close"]
    ndx = load_ohlc("NDX", end)[
        "close"
    ]  # NDX: close only (intraday OHLC inconsistent per universe audit)
    rets = pd.DataFrame({k: v["close"].pct_change() for k, v in frames.items()})
    profiles = []
    for t, df in frames.items():
        peers = rets.drop(columns=[t]).mean(axis=1, skipna=True)
        for w in ("ai_era", "pre_2023"):
            p = ticker_profile(t, df, smh, ndx, peers, w)
            if p:
                profiles.append(p)
    out_dir = OUT_BASE / "segments" / SEGMENT
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([flat_row(p) for p in profiles]).to_csv(
        out_dir / "profile_stats.csv", index=False
    )
    (out_dir / "profile_numbers.json").write_text(
        json.dumps(
            {
                "common_end": uni["common_end"],
                "ai_era_start": uni["ai_era_start"],
                "segment": SEGMENT,
                "skipped": skipped,
                "profiles": profiles,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    print(f"{len(profiles)} profiles written; skipped={skipped}")


if __name__ == "__main__":
    main()
