"""Predeclared range-position reversion in an established uptrend; no RSI."""

ID = "TOP_C3_IBS_REVERT"
HYPOTHESIS = (
    "Short-lived liquidity demand and end-of-day selling can temporarily depress diversified "
    "instruments within an established uptrend. Buying a weak close may earn compensation "
    "for supplying liquidity to urgent sellers, provided selling is temporary rather than "
    "new fundamental information. The long-term trend filter and short holding limit constrain exposure."
)
RULES = [
    "Use daily bars on the common equity-session calendar for all five instruments.",
    "IBS = (close-low)/(high-low). A zero-range bar generates neither an entry nor an IBS exit; the holding-time exit still applies.",
    "When flat, enter after close is strictly above its trend-bar simple moving average and IBS is at or below entry_ibs. The average includes today's close and requires the full window.",
    "Fill at next open; assign one fixed equal slot of 1 / universe size. Inactive slots stay in cash; no shorts or leverage.",
    "While held, exit after IBS is at or above exit_ibs or hold sessions have completed, counting the fill day as session one; execute at next open.",
    "The trend filter is for entry only. No same-close reentry after an exit. The engine restores target slots daily and charges drift turnover.",
    "Defaults trend=200, entry_ibs=0.20, exit_ibs=0.70 and hold=5 are predeclared simple daily reversion rules, not chosen from results.",
]
UNIVERSE = ["SPY", "QQQ", "SMH", "GLD", "SLV"]
PARAMS = {"trend": 200, "entry_ibs": 0.2, "exit_ibs": 0.7, "hold": 5}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"

import numpy as np
import pandas as pd


def weights(pan, params):
    close = pan["close"]
    ranges = pan["high"] - pan["low"]
    ibs = (close - pan["low"]) / ranges.where(ranges > 0)
    trend = close.rolling(params["trend"]).mean()
    entry = close.gt(trend) & ibs.le(params["entry_ibs"])
    exit_signal = ibs.ge(params["exit_ibs"])
    result = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for ticker in close.columns:
        entries, exits = entry[ticker].to_numpy(), exit_signal[ticker].to_numpy()
        active, age = False, 0
        values = np.zeros(len(close))
        for i in range(len(close)):
            if active:
                age += 1
                if exits[i] or age >= params["hold"]:
                    active = False
            elif entries[i]:
                active, age = True, 0
            values[i] = (1.0 / len(UNIVERSE)) if active else 0.0
        result[ticker] = values
    return result
