"""Volatility-compression breakout on Binance BTC/ETH daily bars; research only."""
import numpy as np
import pandas as pd

ID = "TOP_N4_BTC_VOL_COMPRESSION"
HYPOTHESIS = (
    "Volatility clusters: quiet stretches tend to be followed by large moves. When realized volatility has been "
    "unusually low relative to the last year and price then closes above its recent range, the compression often "
    "resolves upward into a trend. Holding the breakout with a volatility-scaled trailing stop lets winners run "
    "while a trend average exit ends trades that lose their trend."
)
RULES = [
    "Realized volatility = rolling std (population, ddof=0) of daily log returns over vol_window bars. Its percentile is the share of the last pct_window "
    "values (including itself) that are <= the current value. The percentile is read as of the PREVIOUS bar, so the breakout bar itself cannot create the compression signal.",
    "Entry (flat asset): close > highest high of the previous breakout bars, AND previous-bar volatility percentile <= pct_max, AND close > SMA(trend).",
    "Exit (held asset): close <= highest close since entry minus atr_mult * ATR(atr_n) (close-based trailing stop, only moves up), OR close < SMA(trend).",
    "Sizing: one equal slot per asset (1/2 of capital each for BTCUSDT and ETHUSDT); an idle slot stays in cash. No shorts, no leverage. Decide at the close, fill at the next open.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT"]
PARAMS = {"breakout": 20, "vol_window": 20, "pct_window": 250, "pct_max": 0.3, "atr_n": 14, "atr_mult": 3.0, "trend": 100}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"


def _asset_weights(open_, high, low, close, p):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(int(p["atr_n"]), min_periods=int(p["atr_n"])).mean()
    vol = np.log(close / prev_close).rolling(int(p["vol_window"]), min_periods=int(p["vol_window"])).std(ddof=0)
    pw = int(p["pct_window"])
    pct = vol.rolling(pw, min_periods=pw).apply(lambda x: float((x <= x[-1]).mean()), raw=True).shift(1)
    sma = close.rolling(int(p["trend"]), min_periods=int(p["trend"])).mean()
    n = int(p["breakout"])
    prior_high = high.rolling(n, min_periods=n).max().shift(1)
    enter = ((close > prior_high) & (pct <= float(p["pct_max"])) & (close > sma)).fillna(False).to_numpy()
    c, a, s = close.to_numpy(), atr.to_numpy(), sma.to_numpy()
    held = np.zeros(len(c))
    in_pos, peak = False, np.nan
    for i in range(len(c)):
        if in_pos:
            peak = max(peak, c[i])
            stop = peak - float(p["atr_mult"]) * a[i]
            if np.isnan(a[i]) or np.isnan(s[i]) or c[i] <= stop or c[i] < s[i]:
                in_pos = False
        elif enter[i]:
            in_pos, peak = True, c[i]
        held[i] = 1.0 if in_pos else 0.0
    return pd.Series(held, index=close.index)


def weights(pan, params):
    out = pd.DataFrame(0.0, index=pan["close"].index, columns=pan["close"].columns)
    slot = 1.0 / len(UNIVERSE)
    for ticker in UNIVERSE:
        out[ticker] = slot * _asset_weights(pan["open"][ticker], pan["high"][ticker], pan["low"][ticker],
                                            pan["close"][ticker], params)
    return out
