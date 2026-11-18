"""Shared daily backtest core: decide at the close of day t, fill at the open of day t+1, long-only, no leverage."""

from __future__ import annotations

from collections.abc import Sequence
from functools import reduce
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
CUTOFF = "2026-10-09"
CRYPTO = {"BTCUSD", "ETHUSD"}
FX = {"EURUSD"}
COST_RT_BPS = {"equity": 5.0, "crypto": 20.0, "fx": 2.0}
SPLITS = {
    "equity": {
        "IS": ("2016-01-01", "2020-12-31"),
        "WF": ("2021-01-01", "2023-12-31"),
        "HO": ("2024-01-01", CUTOFF),
    },
    "crypto": {
        "IS": ("2021-01-01", "2022-12-31"),
        "WF": ("2023-01-01", "2024-12-31"),
        "HO": ("2025-01-01", CUTOFF),
    },
}
FIELDS = ["open", "high", "low", "close", "volume"]


def asset_class(ticker: str) -> str:
    if ticker in FX:
        return "fx"
    return (
        "crypto" if ticker in CRYPTO or ticker.endswith(("USD", "USDT")) else "equity"
    )


def data_path(ticker: str, timeframe: str = "1d") -> Path:
    folder = {
        "1d": f"data/ohlcv/{ticker}_1d.csv",
        "1h": f"data/hourly/{ticker}_1h_clean.csv",
        "5m": f"data/intraday/{ticker}_5m_clean.csv",
        "1m": f"data/intraday/{ticker}_1m_clean.csv",
    }
    return ROOT / folder[timeframe]


def load_frames(
    tickers: Sequence[str], cutoff: str = CUTOFF, timeframe: str = "1d"
) -> dict[str, pd.DataFrame]:
    """Bars per ticker. Intraday stock files keep regular-session bars only; timestamps are naive UTC."""
    frames = {}
    for ticker in tickers:
        raw = pd.read_csv(data_path(ticker, timeframe))
        if timeframe == "1d":
            raw["index"] = pd.to_datetime(raw["date"])
        else:
            if "session" in raw.columns:
                raw = raw[raw["session"] == "regular"]
            raw["index"] = pd.to_datetime(raw["ts"], utc=True).dt.tz_localize(None)
        frame = (
            raw.set_index("index").sort_index().reindex(columns=FIELDS).astype(float)
        )
        frame = frame[~frame.index.duplicated()]
        frames[ticker] = frame.loc[
            : cutoff if timeframe == "1d" else cutoff + " 23:59:59"
        ]
    return frames


def panel(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Field -> DataFrame on the days every non-crypto ticker has a real bar (common history, no stale fills).

    Crypto trades 24/7, so it is sampled on those days. With crypto only, the common crypto days are used.
    """
    groups = [f.index for t, f in frames.items() if asset_class(t) != "crypto"] or [
        f.index for f in frames.values()
    ]
    calendar = reduce(lambda a, b: a.intersection(b), groups).sort_values()
    out = {}
    for field in FIELDS:
        data = pd.DataFrame({t: f[field].reindex(calendar) for t, f in frames.items()})
        out[field] = data.fillna(0.0) if field == "volume" else data.ffill()
    return out


def _side_cost(columns: Sequence[str], mult: float) -> pd.Series:
    return pd.Series({t: COST_RT_BPS[asset_class(t)] / 2 / 1e4 * mult for t in columns})


def backtest(
    weights: pd.DataFrame, pan: dict[str, pd.DataFrame], cost_mult: float = 1.0
) -> dict[str, Any]:
    opens = pan["open"]
    cal, cols = opens.index, opens.columns
    w = weights.reindex(index=cal, columns=cols).fillna(0.0).clip(lower=0.0)
    if (w.sum(axis=1) > 1 + 1e-9).any():
        raise ValueError("weights sum above 1: leverage is not allowed")
    valid = opens.notna()
    ret_oo = (opens.shift(-1) / opens - 1).where(valid).fillna(0.0)
    pos = w.shift(1).fillna(0.0).where(valid, 0.0)
    gross = (pos * ret_oo).sum(axis=1)
    side = _side_cost(cols, cost_mult)
    # Weights drift with prices during a bar; getting back to the target at the next open is real turnover.
    drifted = (pos * (1 + ret_oo)).div(1 + gross, axis=0).shift(1).fillna(0.0)
    cost = ((pos - drifted).abs() * side).sum(axis=1)
    net = gross - cost
    bench = ret_oo.where(valid).mean(axis=1).fillna(0.0)
    return {
        "net": net,
        "gross": gross,
        "bench": bench,
        "pos": pos,
        "ret_oo": ret_oo,
        "side": side,
    }


def trades_from(
    bt: dict[str, Any], pan: dict[str, pd.DataFrame]
) -> list[dict[str, Any]]:
    out = []
    opens = pan["open"]
    for ticker in bt["pos"].columns:
        held = (bt["pos"][ticker] > 0).to_numpy()
        idx = bt["pos"].index
        i = 0
        while i < len(held):
            if held[i]:
                j = i
                while j + 1 < len(held) and held[j + 1]:
                    j += 1
                growth = float((1 + bt["ret_oo"][ticker].iloc[i : j + 1]).prod())
                still_open = j + 1 >= len(
                    idx
                )  # never closed inside the data: mark to the last open, no exit cost
                ret = growth - 1 - (1 if still_open else 2) * float(bt["side"][ticker])
                exit_i = len(idx) - 1 if still_open else j + 1
                out.append(
                    {
                        "ticker": ticker,
                        "entry": idx[i],
                        "exit": idx[exit_i],
                        "ret": ret,
                        "open": still_open,
                        "entry_px": float(opens[ticker].iloc[i]),
                        "exit_px": float(opens[ticker].iloc[exit_i]),
                    }
                )
                i = j + 1
            else:
                i += 1
    return out


def metrics(r: pd.Series) -> dict[str, float] | None:
    r = r.dropna()
    if len(r) < 20:
        return None
    years = max((r.index[-1] - r.index[0]).days / 365.25, 1 / 365.25)
    equity = (1 + r).cumprod()
    total = float(equity.iloc[-1] - 1)
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity.to_numpy()]))[
        1:
    ]  # start capital counts as a peak
    ppy = len(r) / years
    sd = float(r.std())
    return {
        "total": total,
        "cagr": float((1 + total) ** (1 / years) - 1) if total > -1 else -1.0,
        "sharpe": float(r.mean() / sd * np.sqrt(ppy)) if sd > 0 else 0.0,
        "vol": sd * float(np.sqrt(ppy)),
        "maxdd": float((equity.to_numpy() / peak - 1).min()),
        "days": len(r),
    }


def window(r: pd.Series, bounds: tuple[str, str]) -> pd.Series:
    return r.loc[bounds[0] : bounds[1]]


def deflated_sharpe(r: pd.Series, k: int) -> float | None:
    """Bailey / Lopez de Prado deflated Sharpe probability (approximation, daily units)."""
    r = r.dropna()
    n = len(r)
    if n < 50 or r.std() == 0:
        return None
    sr = float(r.mean() / r.std())
    var = (
        1 - stats.skew(r) * sr + (stats.kurtosis(r, fisher=False) - 1) / 4 * sr**2
    ) / (n - 1)
    gamma = 0.5772156649
    emax = (1 - gamma) * stats.norm.ppf(1 - 1 / k) + gamma * stats.norm.ppf(
        1 - 1 / (k * np.e)
    )
    sr0 = np.sqrt(var) * emax
    return float(stats.norm.cdf((sr - sr0) / np.sqrt(var)))


def lookahead_check(
    module: Any, frames: dict[str, pd.DataFrame], cuts: tuple[float, ...] = (0.6, 0.85)
) -> tuple[bool, str | None]:
    """Weights on truncated data must equal the same dates computed on the full data."""
    full = module.weights(panel(frames), module.PARAMS)
    index = panel(frames)["open"].index
    for share in cuts:
        cut = index[int(len(index) * share)]
        trimmed = {t: f.loc[:cut] for t, f in frames.items()}
        part = module.weights(panel(trimmed), module.PARAMS)
        a = part.reindex(columns=full.columns).fillna(0.0).loc[:cut]
        b = full.reindex(index=a.index).fillna(0.0)
        if not np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-9):
            return False, str(cut.date())
    return True, None


def _scaled(params: dict[str, Any], factor: float) -> dict[str, Any]:
    out = {}
    for key, value in params.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            out[key] = value
        elif isinstance(value, int):
            out[key] = max(1, int(round(value * factor)))
        else:
            out[key] = value * factor
    return out


AI_ERA_START = "2023-01-01"  # ChatGPT (Nov 2022) changed the regime: recent data weighs more than 2016-2020.


def psr(r: pd.Series) -> float | None:
    """Probabilistic Sharpe ratio against zero (Bailey / Lopez de Prado), daily units."""
    r = r.dropna()
    n = len(r)
    if n < 50 or r.std() == 0:
        return None
    sr = float(r.mean() / r.std())
    denom = 1 - stats.skew(r) * sr + (stats.kurtosis(r, fisher=False) - 1) / 4 * sr**2
    return float(stats.norm.cdf(sr * np.sqrt(n - 1) / np.sqrt(max(denom, 1e-9))))


def pbo_cscv(variants: dict[str, pd.Series], blocks: int = 8) -> float | None:
    """Probability of backtest overfitting via CSCV over the predeclared parameter variants."""
    from itertools import combinations

    frame = pd.DataFrame(variants).dropna()
    if frame.shape[1] < 2 or len(frame) < blocks * 10:
        return None
    parts = np.array_split(np.arange(len(frame)), blocks)
    below = total = 0
    for chosen in combinations(range(blocks), blocks // 2):
        ins = np.concatenate([parts[i] for i in chosen])
        out = np.concatenate([parts[i] for i in range(blocks) if i not in chosen])
        sr_in = frame.iloc[ins].mean() / frame.iloc[ins].std().replace(0, np.nan)
        sr_out = frame.iloc[out].mean() / frame.iloc[out].std().replace(0, np.nan)
        if sr_in.isna().all() or sr_out.isna().all():
            continue
        best = sr_in.idxmax()
        rank = sr_out.rank(pct=True)[best]
        below += rank <= 0.5
        total += 1
    return float(below / total) if total else None


def critic(summary: dict[str, Any]) -> tuple[str, list[str]]:
    """Lenient Critic: rating from the AI era (2023+), with flags for regime change, tuning and fragility."""
    ai, pre = summary["eras"]["ai_era"], summary["eras"]["pre_ai"]
    flags = []
    if not summary["lookahead_ok"]:
        return "CRVENO", ["lookahead: signal se mijenja kad se dodaju budući podaci"]
    if not ai:
        return "CRVENO", ["premalo podataka u AI eri"]
    if pre and pre["sharpe"] > 0.5 and ai["sharpe"] <= 0:
        flags.append("radilo samo prije 2022., u AI eri ne radi (promjena režima)")
    if pre and pre["sharpe"] <= 0 < ai["sharpe"]:
        flags.append(
            "radi samo u AI eri; prije 2022. nije radilo (novi režim, manje dokaza)"
        )
    sens = [v for k, v in summary["sensitivity"].items() if k != "base"]
    fragile = any(v is None or v < 0 for v in sens) or (
        summary["sensitivity"].get("base")
        and min(v for v in sens if v is not None) < 0.5 * summary["sensitivity"]["base"]
        if all(v is not None for v in sens)
        else True
    )
    if fragile:
        flags.append(
            "osjetljivo na parametre (±20 % mijenja ishod): moguće prilagođeno"
        )
    pbo = summary.get("pbo")
    if pbo is not None and pbo > 0.5:
        flags.append(
            f"PBO {pbo:.0%}: varijanta koja je najbolja u uzorku često je loša izvan uzorka"
        )
    if summary["trades"]["n"] < 30:
        flags.append(
            f"malo trgovina ({summary['trades']['n']}): rezultat je statistički slab"
        )
    dsr = summary.get("deflated_sharpe_prob")
    if dsr is not None and dsr < 0.5:
        flags.append(
            f"deflated Sharpe {dsr:.0%} uz K={summary['k']}: informativno, ne blokira ocjenu"
        )
    cost2 = summary["cost_stress"]["2x"]["wf_ho_total"]
    cost_ok = cost2 is not None and cost2 > 0
    if not cost_ok:
        flags.append("uz dvostruke troškove WF+HO je u minusu")
    if ai["sharpe"] > 0.5 and cost_ok and not fragile and (pbo is None or pbo <= 0.5):
        return "ZELENO", flags
    if ai["sharpe"] > 0 and cost_ok:
        return "ŽUTO", flags
    return "CRVENO", flags


def evaluate(module: Any, k: int) -> tuple[dict[str, Any], dict[str, Any]]:
    frames = load_frames(module.UNIVERSE, timeframe=getattr(module, "TIMEFRAME", "1d"))
    pan = panel(frames)
    ok, bad_cut = lookahead_check(module, frames)
    weights = module.weights(pan, module.PARAMS)
    bt = backtest(weights, pan, 1.0)
    bounds = SPLITS[module.SPLIT_KIND]
    start = bounds["IS"][0]
    net, bench = bt["net"].loc[start:], bt["bench"].loc[start:]
    summary = {
        "id": module.ID,
        "universe": module.UNIVERSE,
        "split_kind": module.SPLIT_KIND,
        "lookahead_ok": ok,
        "lookahead_bad_cut": bad_cut,
        "k": k,
        "data_range": {
            t: [str(f.index[0].date()), str(f.index[-1].date())]
            for t, f in frames.items()
        },
        "splits": {},
        "benchmark_splits": {},
    }
    for name, b in bounds.items():
        summary["splits"][name] = metrics(window(bt["net"], b))
        summary["benchmark_splits"][name] = metrics(window(bt["bench"], b))
    summary["full"], summary["benchmark_full"] = metrics(net), metrics(bench)
    summary["eras"] = {
        "pre_ai": metrics(net.loc[:"2022-12-31"]),
        "ai_era": metrics(net.loc[AI_ERA_START:]),
        "benchmark_pre_ai": metrics(bench.loc[:"2022-12-31"]),
        "benchmark_ai_era": metrics(bench.loc[AI_ERA_START:]),
    }
    ai_window = (AI_ERA_START, bounds["HO"][1])
    summary["cost_stress"] = {}
    for label, mult in (("1x", 1.0), ("2x", 2.0), ("3x", 3.0)):
        m = metrics(window(backtest(weights, pan, mult)["net"], ai_window))
        summary["cost_stress"][label] = {
            "wf_ho_total": m["total"] if m else None,
            "wf_ho_sharpe": m["sharpe"] if m else None,
        }
    variants = {"base": net}
    summary["sensitivity"] = {}
    for label, factor in (("minus20", 0.8), ("plus20", 1.2)):
        try:
            variants[label] = backtest(
                module.weights(pan, _scaled(module.PARAMS, factor)), pan, 1.0
            )["net"].loc[start:]
            m = metrics(window(variants[label], ai_window))
            summary["sensitivity"][label] = m["sharpe"] if m else None
        except Exception:
            summary["sensitivity"][label] = None
    m = metrics(window(net, ai_window))
    summary["sensitivity"]["base"] = m["sharpe"] if m else None
    summary["pbo"] = pbo_cscv(variants)
    trades = trades_from(bt, pan)
    rets = np.array([t["ret"] for t in trades]) if trades else np.array([])
    summary["trades"] = {
        "n": len(trades),
        "win_rate": float((rets > 0).mean()) if len(rets) else None,
        "avg": float(rets.mean()) if len(rets) else None,
        "median": float(np.median(rets)) if len(rets) else None,
        "best": float(rets.max()) if len(rets) else None,
        "worst": float(rets.min()) if len(rets) else None,
    }
    summary["exposure"] = float((bt["pos"].sum(axis=1) > 0).mean())
    summary["deflated_sharpe_prob"] = deflated_sharpe(net, k)
    summary["psr_ai_era"] = psr(net.loc[AI_ERA_START:])
    summary["rating"], summary["flags"] = critic(summary)
    yearly = (1 + net).groupby(net.index.year).prod() - 1
    bench_y = (1 + bench).groupby(bench.index.year).prod() - 1
    summary["yearly"] = {
        int(y): {"strategy": float(v), "benchmark": float(bench_y.get(y, np.nan))}
        for y, v in yearly.items()
    }
    bundle = {
        "bt": bt,
        "pan": pan,
        "trades": trades,
        "bounds": bounds,
        "variants": variants,
    }
    return summary, bundle
