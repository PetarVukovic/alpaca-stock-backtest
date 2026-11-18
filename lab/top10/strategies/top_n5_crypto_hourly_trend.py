"""Hourly crypto trend with a realized-volatility regime filter; research only."""
import numpy as np
import pandas as pd

ID = "TOP_N5_CRYPTO_HOURLY_TREND"
HYPOTHESIS = (
    "Crypto trends persist for hours to days because flows are herd-like and the market never closes. "
    "A fast hourly EMA above a slow one captures that drift, but it fails in two regimes: calm chop "
    "(no trend to ride, costs eat the signal) and panic spikes (gaps and reversals). Trading only when "
    "one-week realized volatility sits in the middle band of its own trailing 90-day distribution should "
    "keep the trend edge and skip the regimes where it historically breaks."
)
RULES = [
    "Every hourly bar close, per asset: fast EMA (24 bars) above slow EMA (96 bars) means an up-trend.",
    "Realized volatility = standard deviation of hourly log returns over the last 168 bars (one week).",
    "Regime filter: volatility must lie between its trailing 25th and 75th percentile over the last 2160 bars (90 days); calm chop and panic spikes are skipped.",
    "Hold the asset (weight 1/3 of capital per asset, unused slots stay in cash) while up-trend AND middle-band volatility are both true; otherwise flat.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage. Periods are hourly bars (24/7), not days.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {"fast": 24, "slow": 96, "vol_window": 168, "regime_window": 2160, "q_low": 0.25, "q_high": 0.75}
SPLIT_KIND = "equity"
TIMEFRAME = "1h"


def weights(pan, params):
    close = pan["close"]
    fast, slow = int(params["fast"]), int(params["slow"])
    vol_window, regime_window = int(params["vol_window"]), int(params["regime_window"])
    q_low, q_high = min(float(params["q_low"]), 0.49), min(float(params["q_high"]), 0.99)
    trend = close.ewm(span=fast, adjust=False, min_periods=fast).mean() > close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    vol = np.log(close / close.shift(1)).rolling(vol_window, min_periods=vol_window).std()
    lo = vol.rolling(regime_window, min_periods=regime_window).quantile(q_low)
    hi = vol.rolling(regime_window, min_periods=regime_window).quantile(max(q_high, q_low))
    middle = (vol >= lo) & (vol <= hi)
    on = (trend & middle).fillna(False)
    return on.astype(float) / len(close.columns)
