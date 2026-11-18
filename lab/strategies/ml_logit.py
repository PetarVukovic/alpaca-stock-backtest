"""Predeclared causal logistic baseline; fitted parameters use IS only."""

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

FEATURES = ["ret_1d", "ret_5d", "ret_20d", "vol_ratio", "sma_distance"]


def features(frame):
    close = frame.close
    returns = close.pct_change(fill_method=None)
    return (
        pd.DataFrame(
            {
                "ret_1d": returns,
                "ret_5d": close.pct_change(5, fill_method=None),
                "ret_20d": close.pct_change(20, fill_method=None),
                "vol_ratio": returns.rolling(10).std() / returns.rolling(60).std(),
                "sma_distance": close / close.rolling(200).mean() - 1,
            }
        )
        .shift(1)
        .replace([np.inf, -np.inf], np.nan)
    )


def predictions(frame):
    """Annual expanding IS fits; model ending 2020 frozen throughout WF/HO.

    Training labels must finish strictly before the scoring boundary (5-bar purge).
    Missing/failed fits produce no signals, never an alternative model search.
    """
    x = features(frame)
    forward = frame.close.shift(-5) / frame.close - 1
    y = (forward > 0).astype(float).where(forward.notna())
    label_end = pd.Series(frame.index, index=frame.index).shift(-5)
    probability = pd.Series(np.nan, index=frame.index, name="probability")
    models = []
    dates = pd.to_datetime(frame.date)
    for year in range(2017, 2022):
        boundary = pd.Timestamp(f"{year}-01-01", tz=frame.index.tz)
        train = (
            (dates >= "2016-01-04") & (frame.index < boundary) & (label_end < boundary)
        )
        train &= x.notna().all(axis=1) & y.notna()
        score = (dates.dt.year == year) if year < 2021 else (dates >= "2021-01-01")
        score &= x.notna().all(axis=1)
        if not score.any():
            continue
        info = {
            "scoring_start": str(boundary),
            "train_n": int(train.sum()),
            "status": "insufficient_training",
        }
        models.append(info)
        if train.sum() < 100 or y[train].nunique() < 2:
            continue
        mean, scale = x[train].mean(), x[train].std(ddof=0)
        if (scale <= 0).any():
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                fit = sm.Logit(
                    y[train],
                    sm.add_constant((x[train] - mean) / scale, has_constant="add"),
                ).fit(disp=False, maxiter=100)
            if not fit.mle_retvals["converged"]:
                info["status"] = "nonconverged"
                continue
            probability.loc[score] = fit.predict(
                sm.add_constant((x[score] - mean) / scale, has_constant="add")
            )
            info.update(
                status="fitted",
                train_last=str(frame.index[train][-1]),
                label_last=str(label_end[train].max()),
                coefficients=fit.params.to_dict(),
                mean=mean.to_dict(),
                scale=scale.to_dict(),
            )
        except (ValueError, np.linalg.LinAlgError, Warning):
            info["status"] = "fit_failed"
    diagnostics = {}
    for period, start, end in [
        ("IS", "2016-01-04", "2020-12-31"),
        ("WF", "2021-01-01", "2023-12-31"),
        ("HO", "2024-01-01", "2099-12-31"),
    ]:
        eligible = (
            (dates >= start)
            & (dates <= end)
            & probability.notna()
            & y.notna()
            & (label_end <= pd.Timestamp(end, tz=frame.index.tz))
        )
        n = int(eligible.sum())
        diagnostics[period] = {
            "n": n,
            "accuracy": float(
                ((probability[eligible] > 0.5).astype(float) == y[eligible]).mean()
            )
            if n
            else None,
            "always_up_accuracy": float(y[eligible].mean()) if n else None,
        }
    return probability, {
        "models": models,
        "classification": diagnostics,
        "features": FEATURES,
        "purge_bars": 5,
        "feature_lag_bars": 1,
        "threshold": 0.55,
    }
