"""Independent re-computation of selected swing / placebo / map numbers (audit, research only).

This module deliberately does NOT import ``lab.aichain``: it re-implements the data loader, the simulator and the
rules (W2, W3, W5, W6, W8), the S/R placebo (real, shifted and paired controls) and the nearest support /
resistance straight from ``data/ohlcv/{T}_1d.csv`` and compares them with the stored JSON results.

    .venv/bin/python -m lab.aichain.audit_independent

Output: reports/research/AICHAIN_20261014/swing/audit_independent.json (agents never place orders).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing"
COMMON_END = "2026-10-05"
AI_START = "2023-01-01"
CAPITAL = 1000.0
TOL = 1e-6


# --------------------------------------------------------------------------------------------------
# data loading (re-implemented rules: effective start after a >=5-bar zero-volume run, bad-tick clamp)
# --------------------------------------------------------------------------------------------------
def load(ticker: str, end: str | None = COMMON_END) -> pd.DataFrame:
    """Daily bars from the CSV with the shared data rules, optionally cut at ``end``."""
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"])
    d = d.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    if end is not None:
        d = d[d["date"] <= pd.Timestamp(end)].reset_index(drop=True)
    zero = (d["volume"] == 0).to_numpy()
    start = d["date"].iloc[0]
    i = 0
    while i < len(d):
        if zero[i]:
            j = i
            while j < len(d) and zero[j]:
                j += 1
            if j - i >= 5 and j < len(d):
                start = d["date"].iloc[j]
            i = j
        else:
            i += 1
    d = d[d["date"] >= start].reset_index(drop=True)
    ref = pd.concat(
        [d["open"], d["close"], d["close"].shift(1), d["close"].shift(-1)], axis=1
    )
    hi_ref, lo_ref = ref.max(axis=1), ref.min(axis=1)
    hi_bad = d["high"] > hi_ref * 1.25
    lo_bad = d["low"] < lo_ref / 1.25
    d.loc[hi_bad, "high"] = hi_ref[hi_bad]
    d.loc[lo_bad, "low"] = lo_ref[lo_bad]
    return d


def _arr(d: pd.DataFrame) -> tuple[np.ndarray, ...]:
    return tuple(d[x].to_numpy(float) for x in ("open", "high", "low", "close"))


def pivots(h: np.ndarray, lo: np.ndarray, k: int = 5) -> tuple[list, list]:
    """Strict pivots as (confirm_bar, bar, price) lists for highs and lows."""
    highs, lows = [], []
    for p in range(k, len(h) - k):
        if h[p] > max(h[p - k : p].max(), h[p + 1 : p + k + 1].max()):
            highs.append((p + k, p, h[p]))
        if lo[p] < min(lo[p - k : p].min(), lo[p + 1 : p + k + 1].min()):
            lows.append((p + k, p, lo[p]))
    return highs, lows


def simple_atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    prev = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - lo, np.abs(h - prev), np.abs(lo - prev)])
    return pd.Series(tr).rolling(n).mean().to_numpy()


# --------------------------------------------------------------------------------------------------
# signals
# --------------------------------------------------------------------------------------------------
def sig_w8(d: pd.DataFrame) -> dict[str, Any]:
    _, h, lo, c = _arr(d)
    rng = h - lo
    ibs = np.where(rng > 0, (c - lo) / np.where(rng > 0, rng, 1.0), np.nan)
    sma = pd.Series(c).rolling(200).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        entry = ~np.isnan(ibs) & ~np.isnan(sma) & (ibs < 0.2) & (c > sma)
        ex = ~np.isnan(ibs) & (ibs > 0.8)
    return {"entry": entry, "exit": ex, "max_bars": 5}


def sig_w2(d: pd.DataFrame) -> dict[str, Any]:
    _, _, lo, _ = _arr(d)
    c = d["close"]
    entry = (
        (c >= c.rolling(20).max())
        & (c / c.shift(60) - 1 > 0)
        & (c > c.rolling(50).mean())
    ).to_numpy(bool)
    prior_low = pd.Series(lo).shift(1).rolling(10).min().to_numpy()
    with np.errstate(invalid="ignore"):
        ex = np.where(np.isnan(prior_low), False, c.to_numpy() < prior_low)
    return {"entry": entry, "exit": ex, "max_bars": 15, "stop_pct": 0.08}


def sig_w5(d: pd.DataFrame) -> dict[str, Any]:
    _, h, lo, c = _arr(d)
    n = len(d)
    res = np.full(n, np.nan)
    for _, p, v in pivots(h, lo)[0]:
        res[p + 5] = v
    res = pd.Series(res).ffill().to_numpy()
    entry = np.zeros(n, bool)
    level = np.full(n, np.nan)
    armed, armed_i = math.nan, -1
    for i in range(n):
        if not math.isnan(armed):
            if c[i] < armed or i - armed_i > 40:
                armed = math.nan
            elif i > armed_i and lo[i] <= armed * 1.015 and c[i] > armed:
                entry[i], level[i], armed = True, armed, math.nan
        if (
            math.isnan(armed)
            and not entry[i]
            and not math.isnan(res[i])
            and c[i] > res[i]
            and (i == 0 or c[i - 1] <= res[i])
        ):
            armed, armed_i = res[i], i
    sma = pd.Series(c).rolling(50).mean().to_numpy()
    ex = np.where(np.isnan(sma), False, c < sma)
    return {"entry": entry, "exit": ex, "stop_level": level, "stop_pct": 0.03}


def sig_w6(d: pd.DataFrame) -> dict[str, Any]:
    """Liquidity sweep then market shift, weekly SMA10 bias, partial exit at the target."""
    _, h, lo, c = _arr(d)
    n = len(d)
    atr = simple_atr(h, lo, c)
    iso = d["date"].dt.isocalendar()
    wid = (iso["year"] * 100 + iso["week"]).to_numpy()
    wlast = pd.Series(c).groupby(wid).last()
    pos_of = {w: k for k, w in enumerate(wlast.index)}
    wsma = np.full(n, np.nan)
    for i in range(n):
        j = pos_of[wid[i]]
        if j >= 9:
            wsma[i] = (wlast.iloc[j - 9 : j].sum() + c[i]) / 10
    highs, lows = pivots(h, lo)
    entry = np.zeros(n, bool)
    stop = np.full(n, np.nan)
    target = np.full(n, np.nan)
    sweeps: list[tuple[int, float]] = []
    for t in range(n):
        hb = [x for x in highs if x[0] <= t - 1]
        lb = [x for x in lows if x[0] <= t - 1]
        if hb and lb:
            sh, sl = hb[-1][2], lb[-1][2]
            recent = [x[2] for x in lb[-3:]]
            if (
                sh > sl
                and c[t] < sl + 0.5 * (sh - sl)
                and any(lo[t] < v and c[t] > v for v in recent)
            ):
                sweeps.append((t, lo[t]))
        hc = [x for x in highs if x[0] <= t]
        if not sweeps or t - sweeps[-1][0] > 4 or t < 1:
            continue
        if math.isnan(wsma[t]) or c[t] <= wsma[t] or math.isnan(atr[t]):
            continue
        lower_high = math.nan
        for j in range(len(hc) - 1, 0, -1):
            if hc[j][2] < hc[j - 1][2]:
                lower_high = hc[j][2]
                break
        if math.isnan(lower_high) or not (c[t] > lower_high and c[t - 1] <= lower_high):
            continue
        cands = [x[2] for x in hc if x[2] > c[t] and x[1] >= t - 250]
        if not cands:
            continue
        tgt = hc[-1][2] if hc[-1][2] > c[t] else min(cands)
        stp = sweeps[-1][1] - 0.5 * atr[t]
        if stp < c[t]:
            entry[t], stop[t], target[t] = True, stp, tgt
    prior_low = pd.Series(lo).shift(1).rolling(10).min().to_numpy()
    with np.errstate(invalid="ignore"):
        ex = np.where(np.isnan(prior_low), False, c < prior_low)
    return {
        "entry": entry,
        "exit": ex,
        "stop_arr": stop,
        "target_arr": target,
        "max_bars": 20,
        "partial": 0.5,
    }


# --------------------------------------------------------------------------------------------------
# simulator: decide at close t, fill at open t+1, stop before target, cost on every sale
# --------------------------------------------------------------------------------------------------
def simulate(d: pd.DataFrame, sig: dict[str, Any], bps: float = 2.5) -> np.ndarray:
    """Trade returns (1.000 EUR per trade) over the AI era with an empty account at 2023-01-01."""
    cc = bps / 1e4
    o, h, lo, c = _arr(d)
    n = len(d)
    i0 = int(np.nonzero(d["date"].to_numpy() >= np.datetime64(AI_START))[0][0])
    entry, ex = sig["entry"], sig["exit"]
    max_bars = sig.get("max_bars", 10**9)
    frac = sig.get("partial", 0.0)
    pend_e, pend_x, pos = bool(entry[i0 - 1]), False, None
    out: list[float] = []

    def finish(price: float) -> None:
        nonlocal pos
        out.append((pos["proc"] + pos["u"] * price * (1 - cc)) / pos["inv"] - 1)
        pos = None

    for i in range(i0, n):
        if pend_x and pos is not None:
            finish(o[i])
        pend_x = False
        if pend_e and pos is None:
            buy = o[i] * (1 + cc)
            stop = None
            if "stop_pct" in sig and "stop_level" not in sig:
                stop = o[i] * (1 - sig["stop_pct"])
            elif "stop_level" in sig:
                stop = sig["stop_level"][i - 1] * (1 - sig["stop_pct"])
            elif "stop_arr" in sig:
                stop = sig["stop_arr"][i - 1]
            tgt = sig["target_arr"][i - 1] if "target_arr" in sig else None
            pos = {
                "u": CAPITAL / buy,
                "inv": CAPITAL,
                "proc": 0.0,
                "bars": 0,
                "stop": stop,
                "tgt": tgt,
                "tp": False,
            }
        pend_e = False
        if pos is not None:
            pos["bars"] += 1
            if pos["stop"] is not None and lo[i] <= pos["stop"]:
                finish(min(o[i], pos["stop"]))
            elif (
                frac and not pos["tp"] and pos["tgt"] is not None and h[i] >= pos["tgt"]
            ):
                sold = pos["u"] * frac
                pos["proc"] += sold * max(o[i], pos["tgt"]) * (1 - cc)
                pos["u"] -= sold
                pos["tp"] = True
        if pos is not None:
            if i == n - 1:
                finish(c[i])
            else:
                trail = pos["tp"] and ex[i] if frac else ex[i]
                if pos["bars"] >= max_bars or trail:
                    pend_x = True
        else:
            pend_e = bool(entry[i])
    return np.array(out)


def summarize(r: np.ndarray) -> dict[str, float]:
    w = r > 0
    return {
        "trades": len(r),
        "expectancy_eur": float(r.mean() * CAPITAL),
        "profit_factor": float(r[w].sum() / -r[~w].sum()) if (~w).any() else math.nan,
    }


def sim_w3_memory(tickers: list[str]) -> dict[str, dict[str, float]]:
    """W3 weekly rank: Friday close, rank by 20-day return inside the group, top third in, top half held."""
    data = {t: load(t) for t in tickers}
    ret = {
        t: pd.Series(data[t]["close"].to_numpy(), index=data[t]["date"])
        / pd.Series(data[t]["close"].to_numpy(), index=data[t]["date"]).shift(20)
        - 1
        for t in tickers
    }
    out: dict[str, dict[str, float]] = {}
    for t in tickers:
        d = data[t]
        c = d["close"].to_numpy(float)
        sma = pd.Series(c).rolling(50).mean().to_numpy()
        n = len(d)
        entry, ex = np.zeros(n, bool), np.zeros(n, bool)
        for i in range(n):
            dt = d["date"].iloc[i]
            if dt.weekday() != 4 or math.isnan(ret[t].iloc[i]):
                continue
            vals = []
            for u in tickers:
                s = ret[u][:dt]
                if (
                    len(s)
                    and (dt - s.index[-1]).days <= 5
                    and not math.isnan(s.iloc[-1])
                ):
                    vals.append(float(s.iloc[-1]))
            own = float(ret[t].iloc[i])
            rank = 1 + sum(v > own for v in vals)
            entry[i] = rank <= max(1, math.ceil(len(vals) / 3 - 1e-9)) and c[i] > sma[i]
            ex[i] = rank > max(1, math.ceil(len(vals) / 2 - 1e-9))
        out[t] = summarize(simulate(d, {"entry": entry, "exit": ex}))
    return out


# --------------------------------------------------------------------------------------------------
# S/R placebo (deterministic controls only: real, +-3 percent shift, paired match)
# --------------------------------------------------------------------------------------------------
def _eval_level(
    d: tuple[np.ndarray, ...], atr: float, m: int, level: float
) -> np.ndarray:
    _, h, lo, c = d
    band = 0.25 * atr
    hit = np.nonzero(
        (lo[m + 1 : m + 21] <= level + band) & (h[m + 1 : m + 21] >= level - band)
    )[0]
    if len(hit) == 0:
        return np.array([1, 0, 0, 0])
    s = m + 1 + int(hit[0])
    side = 1 if level < c[m] else -1
    res = "neither"
    for j in range(s, min(s + 10, m + 30) + 1):
        if side == 1:
            if c[j] < level - atr:
                res = "break"
                break
            if j > s and h[j] >= level + 1.5 * atr:
                res = "bounce"
                break
        else:
            if c[j] > level + atr:
                res = "break"
                break
            if j > s and lo[j] <= level - 1.5 * atr:
                res = "bounce"
                break
    return np.array([1, 1, res == "bounce", res == "break"])


def clustered_levels(
    pv: list, t: int, atr: float, close: float, lookback: int = 1000
) -> list[tuple[float, int]]:
    """Greedy price clusters of pivots usable at ``t``: (recency-weighted price, member count)."""
    known = sorted(
        [q for q in pv if q[0] <= t and q[1] >= t - lookback], key=lambda q: q[2]
    )
    if not known:
        return []
    tol = max(0.01 * close, 0.5 * (0.0 if math.isnan(atr) else atr))
    groups = [[known[0]]]
    for q in known[1:]:
        if q[2] - np.mean([x[2] for x in groups[-1]]) <= tol:
            groups[-1].append(q)
        else:
            groups.append([q])
    out = []
    for g in groups:
        w = np.array([0.5 ** ((t - q[1]) / 250.0) for q in g])
        out.append((float(np.average([q[2] for q in g], weights=w)), len(g)))
    return out


def wilder_atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> np.ndarray:
    prev = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - lo, np.fmax(np.abs(h - prev), np.abs(lo - prev)))
    tr[0] = h[0] - lo[0]
    return (
        pd.Series(tr).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean().to_numpy()
    )


def placebo_deterministic(placebo: dict[str, Any]) -> dict[str, dict[str, float]]:
    used = placebo["universe"]["used"]
    cuts = placebo["context"]["test_cut_dates"]
    tot = {v: np.zeros(4) for v in ("real", "up", "dn", "match")}
    for tk in used:
        d = load(tk, end=None)
        arrs = _arr(d)
        _, h, lo, c = arrs
        atr = wilder_atr(h, lo, c)
        highs, lows = pivots(h, lo)
        pv = highs + lows
        cut = int(np.nonzero(d["date"].to_numpy() == np.datetime64(cuts[tk]))[0][0])
        s = pd.Series(np.arange(len(d)), index=d["date"])
        s = s[s.index >= pd.Timestamp(AI_START)]
        ends = [
            int(i)
            for i in s.groupby([s.index.year, s.index.month]).last()
            if i <= cut - 30
        ]
        for m in ends:
            a = atr[m]
            if math.isnan(a) or m < 120:
                continue
            cl = c[m]
            r_lo, r_hi = lo[m - 119 : m + 1].min(), h[m - 119 : m + 1].max()
            for price, _ in clustered_levels(pv, m, a, cl):
                if not (r_lo <= price <= r_hi) or abs(price - cl) < 0.5 * a:
                    continue
                tot["real"] += _eval_level(arrs, a, m, price)
                for name, px in (("up", price * 1.03), ("dn", price * 0.97)):
                    if px > 0 and abs(px - cl) >= 0.5 * a:
                        tot[name] += _eval_level(arrs, a, m, px)
                dist = abs(price - cl)
                if dist >= 1.5 * a:
                    sign = 1.0 if price > cl else -1.0
                    for px in (cl + sign * (dist - a), cl + sign * (dist + a)):
                        if px > 0 and abs(px - cl) >= 0.5 * a:
                            tot["match"] += _eval_level(arrs, a, m, px)

    def rates(x: np.ndarray) -> dict[str, float]:
        return {
            "n": int(x[0]),
            "touch_rate": float(x[1] / x[0]),
            "bounce_rate": float(x[2] / x[1]),
            "break_rate": float(x[3] / x[1]),
        }

    return {
        "real": rates(tot["real"]),
        "shift": rates(tot["up"] + tot["dn"]),
        "match": rates(tot["match"]),
    }


def nearest_levels(ticker: str) -> dict[str, Any]:
    """Nearest two supports and resistances at the ticker's own last bar, from raw pivots."""
    d = load(ticker, end=None)
    _, h, lo, c = _arr(d)
    t = len(d) - 1
    a = float(wilder_atr(h, lo, c)[t])
    highs, lows = pivots(h, lo)
    lv = clustered_levels(highs + lows, t, a, float(c[t]))
    near = [x for x in lv if abs(x[0] / c[t] - 1) <= 0.4]
    sup = sorted([x for x in near if x[0] < c[t]], key=lambda x: -x[0])[:2]
    res = sorted([x for x in near if x[0] >= c[t]], key=lambda x: x[0])[:2]
    return {
        "last_date": str(d["date"].iloc[-1].date()),
        "supports": sup,
        "resistances": res,
    }


# --------------------------------------------------------------------------------------------------
# comparison against the stored results
# --------------------------------------------------------------------------------------------------
def stored_per_ticker(cid: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in (OUT / "results").glob("*.json"):
        if f.stem == "stocks_all":
            continue
        grp = json.loads(f.read_text())
        pt = grp["contenders"][cid]["ai_era"].get("per_ticker", {})
        for t, v in pt.items():
            if v:
                out.setdefault(t, v)
    return out


def close_enough(a: float, b: float) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(b))


def main() -> int:
    rows: list[dict[str, Any]] = []

    def swing_row(
        cid: str, ticker: str, mine: dict[str, float], stored: dict[str, Any]
    ) -> None:
        ok = (
            mine["trades"] == stored["trades"]
            and close_enough(mine["expectancy_eur"], stored["expectancy_eur"])
            and close_enough(mine["profit_factor"], stored["profit_factor"])
        )
        rows.append(
            {
                "kind": "swing",
                "contender": cid,
                "ticker": ticker,
                "independent": mine,
                "stored": {
                    k: stored[k] for k in ("trades", "expectancy_eur", "profit_factor")
                },
                "match": bool(ok),
            }
        )

    plan = [
        ("W8_IBS_REVERT", sig_w8, ["MU", "WDC", "STX"]),
        ("W2_MOM_BREAK_20", sig_w2, ["MU", "WDC", "STX"]),
        ("W5_SR_BREAKOUT_RETEST", sig_w5, ["MU", "LITE"]),
        ("W6_MM_SWEEP_SHIFT", sig_w6, ["MU", "NVDA"]),
    ]
    for cid, fn, tickers in plan:
        stored = stored_per_ticker(cid)
        for t in tickers:
            d = load(t)
            swing_row(cid, t, summarize(simulate(d, fn(d))), stored[t])
    stored3 = stored_per_ticker("W3_MOM_RANK_WEEKLY")
    for t, mine in sim_w3_memory(["MU", "WDC", "STX"]).items():
        swing_row("W3_MOM_RANK_WEEKLY", t, mine, stored3[t])

    placebo = json.loads((OUT / "placebo.json").read_text())
    mine_p = placebo_deterministic(placebo)
    sr_all = placebo["sr"]["all"]
    for v in ("real", "shift", "match"):
        ok = mine_p[v]["n"] == sr_all[v]["n"] and all(
            close_enough(mine_p[v][k], sr_all[v][k])
            for k in ("touch_rate", "bounce_rate", "break_rate")
        )
        rows.append(
            {
                "kind": "placebo",
                "variant": v,
                "independent": mine_p[v],
                "stored": {
                    k: sr_all[v][k]
                    for k in ("n", "touch_rate", "bounce_rate", "break_rate")
                },
                "match": bool(ok),
            }
        )
    for t in ("MU", "NVDA", "BTCUSDT", "LITE"):
        mine_m = nearest_levels(t)
        stored_m = json.loads((OUT / "map" / f"{t}.json").read_text())
        ok = mine_m["last_date"] == stored_m["last_date"]
        for key, name in (
            ("supports", "nearest_supports"),
            ("resistances", "nearest_resistances"),
        ):
            theirs = [(x["price"], x["turning_points"]) for x in stored_m[name]]
            ok &= len(theirs) == len(mine_m[key]) and all(
                close_enough(p, q) and k1 == k2
                for (p, k1), (q, k2) in zip(mine_m[key], theirs)
            )
        rows.append(
            {"kind": "map", "ticker": t, "independent": mine_m, "match": bool(ok)}
        )
    report = {
        "checks": len(rows),
        "all_match": all(r["match"] for r in rows),
        "rows": rows,
    }
    (OUT / "audit_independent.json").write_text(
        json.dumps(report, indent=1, default=float)
    )
    print(f"{len(rows)} checks, all match: {report['all_match']}")
    return 0 if report["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
