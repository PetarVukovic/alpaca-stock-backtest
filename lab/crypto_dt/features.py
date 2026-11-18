"""Causal features for the CDT_* strategies: a value at row t uses only information known at the close of bar t."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from lab.crypto_dt import data

METRICS_LAG = pd.Timedelta(minutes=5)  # a snapshot stamped ts is usable only from ts + 5 min
METRICS_TOLERANCE = pd.Timedelta(minutes=15)  # never carry a snapshot across a longer gap
FUNDING_TOLERANCE = pd.Timedelta(hours=9)  # 8h cadence plus slack


def known_asof(
    series: pd.Series,
    decision_times: pd.DatetimeIndex,
    lag: pd.Timedelta,
    tolerance: pd.Timedelta,
) -> pd.Series:
    """Latest observation with `ts + lag <= decision time`; NaN when it is older than `tolerance`.

    The single place where derivative data is aligned to bars, so causality is tested once.
    """
    shifted = series.dropna().sort_index()
    shifted = shifted[~shifted.index.duplicated(keep="last")]
    shifted.index = shifted.index + lag
    return shifted.reindex(decision_times, method="ffill", tolerance=tolerance)


def realized_vol(close: pd.DataFrame, window: int, bars_per_year: float) -> pd.DataFrame:
    """Annualised standard deviation of log returns over the last `window` bars (NaN during warm-up)."""
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window, min_periods=window).std() * np.sqrt(bars_per_year)


def donchian_state(
    high: pd.DataFrame,
    low: pd.DataFrame,
    close: pd.DataFrame,
    n_entry: int,
    n_exit: int,
) -> pd.DataFrame:
    """1.0 while in a long: enter on a close above the prior `n_entry` highs, leave below the prior `n_exit` lows.

    Both windows exclude the current bar. Entry and exit cannot fire together because the exit
    window's minimum low sits below the entry window's maximum high.
    """
    entry = close > high.rolling(n_entry, min_periods=n_entry).max().shift(1)
    leave = close < low.rolling(n_exit, min_periods=n_exit).min().shift(1)
    state = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    state[entry] = 1.0
    state[leave] = 0.0
    return state.ffill().fillna(0.0)


def trend_weights(
    pan: dict[str, pd.DataFrame],
    params: dict[str, Any],
    bars_per_year: float,
    gate: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Donchian ensemble (three speeds) with optional volatility sizing and an optional flat-gate.

    `sigma_target=None` switches vol sizing off. Weights are shares of capital, each asset capped at 1/n.
    """
    close, high, low = pan["close"], pan["high"], pan["low"]
    ratio = float(params["exit_ratio"])
    speeds = [int(params[k]) for k in ("n_fast", "n_mid", "n_slow")]
    score = sum(
        donchian_state(high, low, close, n, max(1, int(round(n * ratio)))) for n in speeds
    ) / len(speeds)
    if params.get("sigma_target"):
        vol = realized_vol(close, int(params["vol_window"]), bars_per_year)
        score = score * (float(params["sigma_target"]) / vol).clip(0.0, 1.0).fillna(0.0)
    weights = score / len(close.columns)
    if gate is not None:
        weights = weights.where(~gate, 0.0)
    return weights


def crowd_gate(
    index: pd.DatetimeIndex, symbols: list[str], params: dict[str, Any], bar_hours: int
) -> pd.DataFrame:
    """True where funding AND open-interest growth are both extreme, evaluated at each bar's close.

    Funding: percentile rank of the latest settled rate within its trailing `funding_win` settlements.
    OI: percentile rank of the `oi_chg_bars` change within the trailing `oi_win_days`. While history is
    too short for either percentile the gate stays False (inactive), never True.
    """
    decision = index + pd.Timedelta(hours=bar_hours)
    funding_win = int(params["funding_win"])
    oi_win = int(round(float(params["oi_win_days"]) * 24 / bar_hours))
    funding_pct = min(float(params["funding_pct"]), 0.999)
    oi_pct = min(float(params["oi_pct"]), 0.999)
    out = pd.DataFrame(False, index=index, columns=symbols)
    for symbol in symbols:
        rank = data.load_funding(symbol).rolling(funding_win, min_periods=funding_win).rank(pct=True)
        funding_known = known_asof(rank, decision, pd.Timedelta(0), FUNDING_TOLERANCE)
        oi = known_asof(data.load_metrics(symbol)["oi"], decision, METRICS_LAG, METRICS_TOLERANCE)
        change = oi / oi.shift(int(params["oi_chg_bars"])) - 1.0
        oi_rank = change.rolling(oi_win, min_periods=oi_win).rank(pct=True)
        crowded = (funding_known >= funding_pct) & (oi_rank >= oi_pct)  # NaN compares False
        out[symbol] = crowded.to_numpy(dtype=bool)
    return out


def window_returns(open_: pd.DataFrame, start_hour: int, hours: int) -> pd.DataFrame:
    """Open-to-open return of the window [start_hour, start_hour + hours) per UTC date, from hourly bars.

    The value for date d is complete (known) at d + start_hour + hours; NaN if either end bar is missing.
    """
    starts = open_.index[open_.index.hour == start_hour]
    begin = open_.reindex(starts).to_numpy()
    end = open_.reindex(starts + pd.Timedelta(hours=hours)).to_numpy()
    return pd.DataFrame(end / begin - 1.0, index=starts.normalize(), columns=open_.columns)


def previous_day(daily: pd.DataFrame | pd.Series, dates: pd.DatetimeIndex) -> pd.DataFrame | pd.Series:
    """Value of a per-date table on the calendar day before each date (NaN where that day is missing)."""
    shifted = daily.reindex(dates - pd.Timedelta(days=1))
    shifted.index = dates
    return shifted


def hour_rows(index: pd.DatetimeIndex, hours: tuple[int, ...]) -> np.ndarray:
    """Boolean mask of bars whose open hour is in `hours`."""
    return np.isin(index.hour, hours)
