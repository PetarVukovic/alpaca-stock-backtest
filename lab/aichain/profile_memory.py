"""Behaviour profile for the memory segment (MU, WDC, STX) from raw daily CSVs.

Read-only on data. Run: .venv/bin/python -m lab.aichain.profile_memory
Writes stats JSON + CSV (numbers only); Croatian narrative is merged by a later step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "AICHAIN_20261014" / "segments" / "memory"
UNIVERSE = ROOT / "reports" / "research" / "AICHAIN_20261014" / "universe.json"
AI_START = pd.Timestamp("2023-01-01")
HORIZONS = (1, 5, 10, 20)


def load(ticker: str, end: pd.Timestamp) -> pd.DataFrame:
    df = pd.read_csv(
        ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", index_col=0, parse_dates=True
    )
    return df.loc[:end].sort_index()


def r4(x: Any) -> Any:
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return x
    return None if np.isnan(xf) else round(xf, 4)


def drawdowns(close: pd.Series, top: int = 5) -> list[dict[str, Any]]:
    peak = close.cummax()
    dd = close / peak - 1
    eps: list[dict[str, Any]] = []
    i, n = 0, len(close)
    while i < n:
        if dd.iloc[i] < 0:
            j = i
            while j < n and dd.iloc[j] < 0:
                j += 1
            seg = dd.iloc[i:j]
            start = close.index[i - 1] if i > 0 else close.index[i]
            eps.append(
                {
                    "start": str(start.date()),
                    "bottom": str(seg.idxmin().date()),
                    "recovery": str(close.index[j].date()) if j < n else None,
                    "depth": r4(seg.min()),
                }
            )
            i = j
        else:
            i += 1
    return sorted(eps, key=lambda e: e["depth"])[:top]


def autocorr(ret: pd.Series) -> dict[str, float]:
    return {f"lag{k}": r4(ret.autocorr(k)) for k in range(1, 6)}


def variance_ratio(close: pd.Series, q: int) -> float:
    lr = np.log(close).diff().dropna()
    var1 = lr.var()
    rq = np.log(close).diff(q).dropna()
    return r4(rq.var() / (q * var1))


def forward(
    close: pd.Series, mask: pd.Series, uncond_mask: pd.Series
) -> dict[str, Any]:
    out: dict[str, Any] = {"n_days": int(mask.sum())}
    # greedy non-overlapping (20-day) event count: honest sample size
    idx = np.flatnonzero(mask.values)
    indep, last = 0, -999
    for k in idx:
        if k - last >= 20:
            indep += 1
            last = k
    out["n_independent_20d"] = indep
    for h in HORIZONS:
        fr = close.shift(-h) / close - 1
        e = fr[mask].dropna()
        u = fr[uncond_mask].dropna()
        out[f"h{h}"] = {
            "n": int(len(e)),
            "mean": r4(e.mean()),
            "median": r4(e.median()),
            "hit": r4((e > 0).mean()) if len(e) else None,
            "uncond_mean": r4(u.mean()),
            "uncond_hit": r4((u > 0).mean()),
            "edge_mean": r4(e.mean() - u.mean()) if len(e) else None,
        }
    return out


def seasonality(close: pd.Series) -> dict[str, Any]:
    m = close.resample("ME").last().pct_change().dropna()
    res: dict[str, Any] = {}
    for mo in range(1, 13):
        s = m[m.index.month == mo]
        res[str(mo)] = {
            "n_years": int(len(s)),
            "mean": r4(s.mean()),
            "hit": r4((s > 0).mean()) if len(s) else None,
        }
    return res


def concentration(close: pd.Series, ret: pd.Series) -> dict[str, Any]:
    lr = np.log(close).diff().dropna()
    best = lr.nlargest(10)
    tot = lr.sum()
    return {
        "total_return": r4(close.iloc[-1] / close.iloc[0] - 1),
        "log_share_top10_days": r4(best.sum() / tot) if tot > 0 else None,
        "log_share_note": "share above 1 or null means the total log return is tiny or negative; read total_return_without_top10 instead",
        "total_return_without_top10": r4(np.exp(tot - best.sum()) - 1),
        "top10_dates": [str(d.date()) for d in best.index],
    }


def gaps(df: pd.DataFrame) -> list[dict[str, Any]]:
    g = df["open"] / df["close"].shift(1) - 1
    big = g.reindex(g.abs().nlargest(5).index)
    return [{"date": str(d.date()), "gap": r4(v)} for d, v in big.items()]


def leadlag(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    """corr(x_t, y_{t+k}); k<0 means y moved earlier than x."""
    df = pd.concat([x, y], axis=1, keys=["x", "y"], sort=True).dropna()
    res = {f"k{k:+d}": r4(df["x"].corr(df["y"].shift(-k))) for k in range(-3, 4)}
    res["y_leads_x"] = r4(df["x"].corr(df["y"].shift(1)))  # y yesterday -> x today
    res["x_leads_y"] = r4(df["y"].corr(df["x"].shift(1)))  # x yesterday -> y today
    return res


def support_resistance(
    df: pd.DataFrame,
    w: int = 5,
    tol: float = 0.015,
    look: int = 60,
    conf: int = 5,
    swing_only: bool = True,
) -> dict[str, Any]:
    """Swing low/high = extreme over +-w bars, usable only after w bars of confirmation (no lookahead).
    Touch = first bar within tol of the level (coming from outside). Hold = no close beyond tol in next `conf` bars."""
    out: dict[str, Any] = {}
    for kind in ("support", "resistance"):
        col = "low" if kind == "support" else "high"
        s = df[col].values
        c = df["close"].values
        n = len(df)
        touches = holds = 0
        for i in range(w, n - w - look - conf):
            win = s[i - w : i + w + 1]
            is_sw = s[i] == (win.min() if kind == "support" else win.max())
            if swing_only and not is_sw:
                continue
            L = s[i]
            for t in range(i + w + 1, min(i + w + 1 + look, n - conf)):
                if kind == "support":
                    broken = c[t] < L * (1 - tol)
                    touch = s[t] <= L * (1 + tol) and s[t] >= L * (1 - tol)
                else:
                    broken = c[t] > L * (1 + tol)
                    touch = s[t] >= L * (1 - tol) and s[t] <= L * (1 + tol)
                if broken:
                    break
                if touch:
                    nxt = c[t : t + conf + 1]
                    brk = (
                        (nxt < L * (1 - tol)).any()
                        if kind == "support"
                        else (nxt > L * (1 + tol)).any()
                    )
                    touches += 1
                    holds += 0 if brk else 1
                    break
        out[kind] = {
            "touches": touches,
            "hold_rate": r4(holds / touches) if touches else None,
        }
    return out


def profile(
    df: pd.DataFrame,
    smh: pd.Series,
    ndx: pd.Series,
    peers: dict[str, pd.Series],
    start: pd.Timestamp | None,
) -> dict[str, Any]:
    d = df.copy()
    close = d["close"]
    ret_full = close.pct_change()
    sma200 = close.rolling(200).mean()  # computed on full history, then window cut
    drop5 = close / close.shift(5) - 1
    cond_drop = (drop5 <= -0.05) & (close > sma200)
    hi52 = close >= close.shift(1).rolling(252).max()
    up = ret_full > 0
    up3 = up & up.shift(1, fill_value=False) & up.shift(2, fill_value=False)
    if start is not None:
        sel = close.index >= start
    else:
        sel = np.ones(len(close), dtype=bool)
    sel_s = pd.Series(sel, index=close.index)
    valid = sel_s & sma200.notna()
    c = close[sel_s]
    d_w = d[sel_s]
    ret = ret_full[sel_s].dropna()
    smh_r, ndx_r = smh.pct_change(), ndx.pct_change()
    res: dict[str, Any] = {
        "bars": int(len(c)),
        "from": str(c.index[0].date()),
        "to": str(c.index[-1].date()),
    }
    res["ann_vol"] = r4(ret.std() * np.sqrt(252))
    res["ann_return_cagr"] = r4((c.iloc[-1] / c.iloc[0]) ** (252 / len(c)) - 1)
    for nm, b in (("SMH", smh_r), ("NDX", ndx_r)):
        j = pd.concat([ret, b], axis=1, keys=["a", "b"], sort=True).dropna()
        res[f"beta_{nm}"] = r4(j["a"].cov(j["b"]) / j["b"].var())
        res[f"corr_{nm}"] = r4(j["a"].corr(j["b"]))
    res["drawdowns"] = drawdowns(c)
    res["autocorr"] = autocorr(ret)
    res["variance_ratio_5"] = variance_ratio(c, 5)
    res["variance_ratio_20"] = variance_ratio(c, 20)
    res["after_5d_drop_above_sma200"] = forward(close, cond_drop & valid, valid)
    res["after_52w_high"] = forward(close, hi52 & valid, valid)
    res["after_3_up_days"] = forward(close, up3 & valid, valid)
    res["seasonality_month"] = seasonality(c)
    res["largest_gaps"] = gaps(d_w)
    res["concentration"] = concentration(c, ret)
    res["leadlag_vs_SMH"] = leadlag(ret, smh_r.reindex(ret.index))
    res["leadlag_vs_peers"] = {
        k: leadlag(ret, v.pct_change().reindex(ret.index)) for k, v in peers.items()
    }
    res["sma200_distance"] = sma_dist_window(close, sma200, sel_s)
    res["support_resistance"] = support_resistance(d_w)
    res["support_resistance_control_any_bar"] = support_resistance(
        d_w, swing_only=False
    )
    return res


def sma_dist_window(close: pd.Series, sma: pd.Series, sel: pd.Series) -> dict[str, Any]:
    d = (close / sma - 1)[sel].dropna()
    fr = (close.shift(-20) / close - 1).reindex(d.index)
    labels = ["<0", "0-20%", "20-50%", ">50%"]
    cat = pd.cut(d, bins=[-9, 0, 0.2, 0.5, 9], labels=labels)
    buck = {}
    for lab in labels:
        s = fr[cat == lab].dropna()
        buck[lab] = {
            "share_days": r4((cat == lab).mean()),
            "n": int(len(s)),
            "fwd20_mean": r4(s.mean()),
            "fwd20_hit": r4((s > 0).mean()) if len(s) else None,
        }
    return {
        "current": r4(d.iloc[-1]),
        "mean": r4(d.mean()),
        "p10": r4(d.quantile(0.1)),
        "p90": r4(d.quantile(0.9)),
        "min": r4(d.min()),
        "max": r4(d.max()),
        "buckets": buck,
    }


def main() -> None:
    uni = json.loads(UNIVERSE.read_text())
    end = pd.Timestamp(uni["common_end"])
    tick = [t["ticker"] for t in uni["segments"]["memory"]["tickers"] if t["usable"]]
    data = {t: load(t, end) for t in tick}
    smh = load("SMH", end)["close"]
    ndx = load("NDX", end)[
        "close"
    ]  # close only (OHLC flagged inconsistent in universe.json)
    result: dict[str, Any] = {
        "common_end": uni["common_end"],
        "tickers": tick,
        "stats": {},
    }
    rows = []
    for t in tick:
        peers = {p: data[p]["close"] for p in tick if p != t}
        result["stats"][t] = {}
        for per, start, stop in (
            ("ai_era_2023plus", AI_START, None),
            ("context_2016_2022", None, AI_START),
        ):
            df = data[t]
            if stop is not None:
                # compute on full history, cut window afterwards (SMA200 warm-up uses earlier bars only)
                pass
            st = (
                profile(df, smh, ndx, peers, start)
                if stop is None
                else profile_pre(df, smh, ndx, peers, stop)
            )
            result["stats"][t][per] = st
            f = lambda k: st["after_5d_drop_above_sma200"][k]
            rows.append(
                {
                    "ticker": t,
                    "period": per,
                    "from": st["from"],
                    "to": st["to"],
                    "bars": st["bars"],
                    "ann_vol": st["ann_vol"],
                    "cagr": st["ann_return_cagr"],
                    "beta_SMH": st["beta_SMH"],
                    "corr_SMH": st["corr_SMH"],
                    "beta_NDX": st["beta_NDX"],
                    "corr_NDX": st["corr_NDX"],
                    "ac_lag1": st["autocorr"]["lag1"],
                    "ac_lag2": st["autocorr"]["lag2"],
                    "vr5": st["variance_ratio_5"],
                    "vr20": st["variance_ratio_20"],
                    "worst_dd": st["drawdowns"][0]["depth"],
                    "drop5_n_days": f("n_days"),
                    "drop5_n_indep": f("n_independent_20d"),
                    "drop5_h5_mean": f("h5")["mean"],
                    "drop5_h5_hit": f("h5")["hit"],
                    "drop5_h5_edge": f("h5")["edge_mean"],
                    "drop5_h20_mean": f("h20")["mean"],
                    "drop5_h20_hit": f("h20")["hit"],
                    "drop5_h20_edge": f("h20")["edge_mean"],
                    "hi52_h20_edge": st["after_52w_high"]["h20"]["edge_mean"],
                    "hi52_h20_hit": st["after_52w_high"]["h20"]["hit"],
                    "up3_h5_edge": st["after_3_up_days"]["h5"]["edge_mean"],
                    "up3_h5_hit": st["after_3_up_days"]["h5"]["hit"],
                    "top10_share_log": st["concentration"]["log_share_top10_days"],
                    "total_without_top10": st["concentration"][
                        "total_return_without_top10"
                    ],
                    "sma200_now": st["sma200_distance"]["current"],
                    "support_touches": st["support_resistance"]["support"]["touches"],
                    "support_hold": st["support_resistance"]["support"]["hold_rate"],
                    "resist_touches": st["support_resistance"]["resistance"]["touches"],
                    "resist_hold": st["support_resistance"]["resistance"]["hold_rate"],
                    "support_hold_control": st["support_resistance_control_any_bar"][
                        "support"
                    ]["hold_rate"],
                    "resist_hold_control": st["support_resistance_control_any_bar"][
                        "resistance"
                    ]["hold_rate"],
                }
            )
    (OUT / "_stats_raw.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False)
    )
    pd.DataFrame(rows).to_csv(OUT / "profile_stats.csv", index=False)
    print(pd.DataFrame(rows).T.to_string())


def profile_pre(
    df: pd.DataFrame,
    smh: pd.Series,
    ndx: pd.Series,
    peers: dict[str, pd.Series],
    stop: pd.Timestamp,
) -> dict[str, Any]:
    cut = stop - pd.Timedelta(days=1)
    return profile(
        df.loc[:cut],
        smh.loc[:cut],
        ndx.loc[:cut],
        {k: v.loc[:cut] for k, v in peers.items()},
        None,
    )


if __name__ == "__main__":
    main()
