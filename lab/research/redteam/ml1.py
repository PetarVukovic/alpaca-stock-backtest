"""Red-team audit of ML1_LOGIT_5D: independent numpy logit, trade comparison and leakage probes.

Run: .venv/bin/python -m lab.research.redteam.ml1
The reimplementation (features, labels, purge, scaling, Newton-IRLS logit, trades) does not import
lab.strategies.ml_logit or lab.engine. Only the leakage probes call lane A's `predictions` as a
black box. Writes reports/research/redteam_ml1.json and merges `ml_logit` into redteam_audit.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from lab.research.redteam.reimpl import (
    ROOT,
    CostModel,
    daily,
    period_slices,
    simulate_single,
)

HORIZON = 5
THRESHOLD = 0.55
BACKTEST = ROOT / "reports/backtest"
OUT = ROOT / "reports/research"
TICKERS = ["MU", "WDC", "STX"]


def make_features(close: np.ndarray) -> np.ndarray:
    """Five features known at the close of bar t-1, stored on row t (one-bar lag, as frozen)."""
    n = len(close)
    out = np.full((n, 5), np.nan)
    ret = np.full(n, np.nan)
    ret[1:] = close[1:] / close[:-1] - 1
    for i in range(1, n):
        j = i - 1  # information up to and including bar t-1
        out[i, 0] = ret[j]
        out[i, 1] = close[j] / close[j - 5] - 1 if j >= 5 else np.nan
        out[i, 2] = close[j] / close[j - 20] - 1 if j >= 20 else np.nan
        if j >= 60:
            out[i, 3] = np.std(ret[j - 9 : j + 1], ddof=1) / np.std(
                ret[j - 59 : j + 1], ddof=1
            )
        if j >= 199:
            out[i, 4] = close[j] / close[j - 199 : j + 1].mean() - 1
    return out


def fit_logit(x: np.ndarray, y: np.ndarray, iters: int = 100) -> np.ndarray:
    """Plain Newton-IRLS maximum likelihood with an intercept column."""
    a = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(a.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-a @ beta))
        grad = a.T @ (y - p)
        hess = (a * (p * (1 - p))[:, None]).T @ a
        step = np.linalg.solve(hess, grad)
        beta += step
        if np.max(np.abs(step)) < 1e-12:
            break
    return beta


def probabilities(
    df: pd.DataFrame, labels: np.ndarray | None = None
) -> tuple[pd.Series, list]:
    """Annual expanding fits 2018-2020 (scored on that year), final 2016-2020 fit for 2021+."""
    close = df["close"].to_numpy(float)
    days = df["day"].to_numpy()
    x = make_features(close)
    n = len(close)
    if labels is None:
        fwd = np.full(n, np.nan)
        fwd[:-HORIZON] = close[HORIZON:] / close[:-HORIZON] - 1
        labels = np.where(np.isnan(fwd), np.nan, (fwd > 0).astype(float))
    label_day = np.array(
        [days[i + HORIZON] if i + HORIZON < n else "9999" for i in range(n)]
    )
    ok_x = ~np.isnan(x).any(axis=1)
    prob = np.full(n, np.nan)
    models = []
    for year in range(2017, 2022):
        cut = f"{year}-01-01"
        train = (
            (days >= "2016-01-04")
            & (days < cut)
            & (label_day < cut)
            & ok_x
            & ~np.isnan(labels)
        )
        score = (
            np.char.startswith(days.astype(str), str(year))
            if year < 2021
            else days >= "2021-01-01"
        ) & ok_x
        if train.sum() < 100:
            models.append(
                {"year": year, "train_n": int(train.sum()), "status": "insufficient"}
            )
            continue
        mu, sd = x[train].mean(axis=0), x[train].std(axis=0, ddof=0)
        beta = fit_logit((x[train] - mu) / sd, labels[train])
        z = np.column_stack([np.ones(score.sum()), (x[score] - mu) / sd]) @ beta
        prob[score] = 1 / (1 + np.exp(-z))
        models.append(
            {
                "year": year,
                "train_n": int(train.sum()),
                "beta": beta.tolist(),
                "mean": mu.tolist(),
                "scale": sd.tolist(),
                "label_last": str(max(label_day[train])),
            }
        )
    return pd.Series(prob, index=df.index), models


def trades(df: pd.DataFrame, prob: pd.Series, stress: float = 1.0) -> dict:
    entry = (prob > THRESHOLD).fillna(False)
    none = pd.Series(False, index=df.index)
    out = {}
    for p, idx in period_slices(df["day"].to_numpy()).items():
        book = simulate_single(
            df.iloc[idx],
            entry.iloc[idx],
            none.iloc[idx],
            {"type": "time", "hold_bars": HORIZON},
            CostModel(stress=stress),
        )
        out[p] = [t.net * 100 for t in book.trades]
    return out


def compare_trades(engine: dict, mine: dict) -> dict:
    rows = {}
    for p in ("IS", "WF", "HO"):
        a, b = engine[p], mine[p]
        same = len(a) == len(b)
        rows[p] = {
            "n_engine": len(a),
            "n_mine": len(b),
            "n_match": same,
            "max_abs_diff_pp": float(np.max(np.abs(np.subtract(a, b))))
            if same and a
            else (0.0 if same else None),
        }
    return rows


def lane_a_frame(ticker: str) -> pd.DataFrame:
    base = daily(ticker)
    frame = base.drop(columns=["day"]).assign(date=base["day"])
    frame.index = frame.index.tz_localize("UTC")
    frame.attrs.update(ticker=ticker, timeframe="daily")
    return frame


def leakage_probes(ticker: str, lane_prob: pd.Series) -> dict:
    """Black-box probes on lane A's predictions()."""
    from lab.strategies.ml_logit import features, predictions

    frame = lane_a_frame(ticker)
    out = {"corrupt_future": [], "truncation": []}
    for cut in ("2019-06-03", "2020-12-24", "2021-06-01", "2024-06-03"):
        limit = pd.Timestamp(cut, tz="UTC")
        bad = frame.copy()
        bad.loc[bad.index >= limit, ["open", "high", "low", "close"]] *= 7
        bad.attrs.update(frame.attrs)
        p_bad, _ = predictions(bad)
        before = frame.index < limit
        out["corrupt_future"].append(
            {
                "cut": cut,
                "max_abs_diff_before_cut": float(
                    np.nanmax(np.abs(p_bad[before] - lane_prob[before]))
                    if lane_prob[before].notna().any()
                    else 0.0
                ),
            }
        )
        short = frame[frame.index < limit].copy()
        short.attrs.update(frame.attrs)
        p_short, _ = predictions(short)
        out["truncation"].append(
            {
                "cut": cut,
                "max_abs_diff": float(
                    np.nanmax(np.abs(p_short - lane_prob[before]))
                    if p_short.notna().any()
                    else 0.0
                ),
            }
        )
    # Feature at t must not change when only bar t (and later) changes.
    f0 = features(frame)
    t = frame.index.get_loc(pd.Timestamp("2022-03-01", tz="UTC"))
    bumped = frame.copy()
    bumped.iloc[t, bumped.columns.get_loc("close")] *= 1.5
    f1 = features(bumped)
    out["feature_row_t_unchanged_when_close_t_changes"] = bool(
        f0.iloc[t].equals(f1.iloc[t])
    )
    out["feature_row_t_plus_1_changes"] = bool(
        not f0.iloc[t + 1].equals(f1.iloc[t + 1])
    )
    return out


def label_shuffle(df: pd.DataFrame, rng: np.random.Generator, runs: int = 200) -> dict:
    """(a) Shuffle labels after 2020: must change nothing. (b) Shuffle IS labels: does HO survive?"""
    close = df["close"].to_numpy(float)
    days = df["day"].to_numpy()
    fwd = np.full(len(close), np.nan)
    fwd[:-HORIZON] = close[HORIZON:] / close[:-HORIZON] - 1
    y = np.where(np.isnan(fwd), np.nan, (fwd > 0).astype(float))
    base_prob, _ = probabilities(df, y)
    late = np.where((days >= "2021-01-01") & ~np.isnan(y))[0]
    y_late = y.copy()
    y_late[late] = rng.permutation(y[late])
    prob_late, _ = probabilities(df, y_late)
    real = trades(df, base_prob)
    early = np.where((days < "2021-01-01") & ~np.isnan(y))[0]
    ho_means, ho_counts = [], []
    for _ in range(runs):
        ys = y.copy()
        ys[early] = rng.permutation(y[early])
        p, _ = probabilities(df, ys)
        tr = trades(df, p)["HO"]
        ho_counts.append(len(tr))
        ho_means.append(float(np.mean(tr)) if tr else np.nan)
    ho = np.array(ho_means)
    real_ho = float(np.mean(real["HO"]))
    return {
        "post2020_shuffle_max_prob_change": float(
            np.nanmax(np.abs(prob_late - base_prob))
        ),
        "real_ho_mean_pct": real_ho,
        "shuffled_is_runs": runs,
        "shuffled_ho_mean_median_pct": float(np.nanmedian(ho)),
        "shuffled_ho_mean_p10_p90_pct": [
            float(np.nanpercentile(ho, 10)),
            float(np.nanpercentile(ho, 90)),
        ],
        "share_shuffled_ge_real": float(np.mean(ho[~np.isnan(ho)] >= real_ho)),
        "shuffled_runs_without_ho_trades": int(np.sum(np.array(ho_counts) == 0)),
    }


def baseline_random_entry(df: pd.DataFrame, prob: pd.Series) -> dict:
    """Enter on every day the model scores (2018+), same 5-bar exit and costs: pure market drift."""
    always = prob.notna().astype(float)
    return {
        p: {"n": len(v), "mean_pct": float(np.mean(v))}
        for p, v in trades(df, always).items()
    }


def top5(values: list[float]) -> dict:
    v = np.sort(np.array(values))[::-1]
    total = v.sum()
    return {
        "n": len(v),
        "mean_pct": float(v.mean()),
        "sum_pct": float(total),
        "top5_sum_pct": float(v[:5].sum()),
        "top5_share_of_net_sum": float(v[:5].sum() / total) if total else None,
        "mean_ex_top5_pct": float(v[5:].mean()) if len(v) > 5 else None,
        "win_rate": float((v > 0).mean()),
    }


def main() -> None:
    from lab.strategies.ml_logit import (
        predictions,  # black box, only for probability comparison
    )

    package = json.loads((BACKTEST / "ML1_LOGIT_5D_critic_inputs.json").read_text())
    diag = json.loads((BACKTEST / "ML1_LOGIT_5D_model_diagnostics.json").read_text())
    rng = np.random.default_rng(20261006)
    result = {"tickers": {}}
    worst_trade, worst_prob, n_ok = 0.0, 0.0, True
    for ticker in TICKERS:
        df = daily(ticker)
        prob, models = probabilities(df)
        lane_prob_utc, _ = predictions(lane_a_frame(ticker))
        lane_prob = lane_prob_utc.set_axis(df.index)
        prob_diff = float(np.nanmax(np.abs(prob - lane_prob)))
        nan_same = bool((prob.isna() == lane_prob.isna()).all())
        cmp1 = compare_trades(package["returns"][ticker], trades(df, prob))
        cmp2 = compare_trades(
            package["stressed_returns"][ticker], trades(df, prob, stress=2.0)
        )
        lane_models = [m for m in diag[ticker]["models"] if m["status"] == "fitted"]
        scaling_diff = max(
            max(
                abs(a - b)
                for a, b in zip(mine["mean"], lm["mean"].values(), strict=True)
            )
            for mine, lm in zip(
                [m for m in models if "beta" in m], lane_models, strict=True
            )
        )
        purge_ok = all(
            m["label_last"] < f"{int(m['scoring_start'][:4])}-01-01"
            for m in lane_models
        )
        for c in list(cmp1.values()) + [v for k, v in cmp2.items() if k != "HO"]:
            n_ok &= c["n_match"]
            worst_trade = max(worst_trade, c["max_abs_diff_pp"] or 0.0)
        worst_prob = max(worst_prob, prob_diff)
        result["tickers"][ticker] = {
            "prob_max_abs_diff": prob_diff,
            "prob_missing_pattern_same": nan_same,
            "trades": cmp1,
            "trades_2x": cmp2,
            "scaling_mean_max_abs_diff": scaling_diff,
            "lane_purge_label_last_before_scoring": purge_ok,
            "signal_share_p_gt_055": {
                p: float((prob.iloc[idx] > THRESHOLD).mean())
                for p, idx in period_slices(df["day"].to_numpy()).items()
            },
            "first_prediction_day": str(df["day"][prob.notna()].iloc[0]),
            "probes": leakage_probes(ticker, lane_prob_utc),
            "label_shuffle": label_shuffle(df, rng),
            "every_day_baseline": baseline_random_entry(df, prob),
            "top5": {
                p: top5(package["returns"][ticker][p]) for p in ("IS", "WF", "HO")
            },
        }
    result["reproduced"] = bool(n_ok and worst_trade <= 0.01 and worst_prob <= 1e-6)
    result["max_abs_diff_pp"] = worst_trade
    result["max_prob_diff"] = worst_prob
    (OUT / "redteam_ml1.json").write_text(json.dumps(result, indent=2))
    merge_audit(result)
    print(
        json.dumps(
            {k: result[k] for k in ("reproduced", "max_abs_diff_pp", "max_prob_diff")}
        )
    )


ML1_FINDINGS = [
    {
        "severity": "medium",
        "open": True,
        "text": (
            "ML1 HO profit is market drift, not model skill (no leak, but the HO result is no evidence of an "
            "edge). The frozen 2020 logit intercept is 0.25 (MU) / 0.28 (STX), i.e. p~0.56-0.57 at average "
            "features, so it buys on 52-53 % of HO days; WDC intercept 0.008 buys on 35 %. Entering on every "
            "scored day with the same 5-bar exit and costs gives HO +1.91/+1.87/+1.91 %/trade (MU/WDC/STX) vs model "
            "+2.04/+4.44/+2.01; in IS 2018-2020 that naive entry gives +0.66/-0.04/+0.34 vs model -0.43/-0.99/-0.24. "
            "200 models trained on shuffled IS labels reach >= the real HO mean in 64.5 % (MU), 19 % (WDC), "
            "24 % (STX) of runs. HO top-5 trades are 68 % (MU), 50 % (WDC), 44 % (STX) of summed HO net return. "
            "HO 2024+ is the memory boom (always-up 58.7-64.3 %)."
        ),
    },
    {
        "severity": "low",
        "open": True,
        "text": (
            "ML1 'IS' is not 2016-2020: features need 200+1 bars and the 2017 fit has only 47 rows "
            "(insufficient), so predictions start 2018-01-02; IS = 2018-2020 out-of-sample annual refits. "
            "Label is close(t)->close(t+5) while the trade is open(t+1)->open(t+6); features are lagged one "
            "extra bar (close t-1). Sensitivity varies only hold_bars 4/6, not the 0.55 threshold; WDC WF has n=9."
        ),
    },
    {
        "severity": "low",
        "open": False,
        "text": (
            "ML1 leakage hunt: none found. Independent numpy Newton logit reproduces lane A probabilities "
            "(max diff 3e-15) and every trade (0 pp, IS/WF/HO 1x, IS/WF 2x); label_last < scoring boundary for "
            "every fit (5-bar purge holds); scaling uses training rows only (mean diff 2e-15); corrupting prices "
            "x7 after 4 cuts (2019-06-03, 2020-12-24, 2021-06-01, 2024-06-03) or truncating leaves earlier "
            "probabilities unchanged; changing close t leaves feature row t unchanged; shuffling labels after "
            "2020 changes no probability (labels after 2020 are never used)."
        ),
    },
]


def merge_audit(result: dict) -> None:
    path = OUT / "redteam_audit.json"
    audit = json.loads(path.read_text())
    audit["generated_at"] = datetime.now(timezone.utc).isoformat()
    audit["rule_types"]["ml_logit"] = {
        "reproduced": result["reproduced"],
        "max_abs_diff_pct": result["max_abs_diff_pp"],
        "n_trades_match": all(
            r["n_match"]
            for t in result["tickers"].values()
            for r in t["trades"].values()
        ),
        "notes": (
            f"ML1_LOGIT_5D MU/WDC/STX IS/WF/HO 1x and IS/WF 2x; own numpy Newton logit, max probability "
            f"diff {result['max_prob_diff']:.2e} vs lane A statsmodels; exit time hold_bars=5"
        ),
    }
    kept = [f for f in audit["engine_findings"] if not f["text"].startswith("ML1")]
    audit["engine_findings"] = kept + ML1_FINDINGS
    path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
