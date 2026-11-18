"""Predeclared long-only Donchian breakout with a close-tested initial ATR stop."""

ID = "TOP_C2_DONCHIAN_TURTLE"
HYPOTHESIS = (
    "A close beyond a long-established price range can reflect new information and persistent "
    "institutional demand. Investors anchored to the old range and slow hedgers supply the "
    "other side. A few sustained moves may pay for repeated failed breakouts; crowded trends "
    "and price gaps can defeat the mechanism."
)
RULES = [
    "On the shared equity-session calendar, enter after a close strictly above the highest high of the preceding entry bars, excluding the current bar.",
    "Fill at the next open. At that fill fix the protective threshold at entry open minus stop_atr times the signal-day Wilder ATR(atr).",
    "ATR uses true range, an initial arithmetic mean of atr observations, then Wilder smoothing; the protective threshold never moves during a trade.",
    "While held, exit after a close strictly below the lowest low of the preceding exit bars or at/below the fixed protective threshold. Execute at the following open, not at the threshold.",
    "No pyramiding or same-close reentry after an exit. Give every asset one fixed equal slot of 1 / universe size; unused slots are cash.",
    "The engine restores target slots at every next open and charges drift turnover. All lengths count shared equity-session bars, also for crypto.",
    "Defaults 55/20 bars and two 20-bar ATR units are declared classic Turtle-style choices; no short side, leverage or original Turtle pyramiding.",
]
UNIVERSE = ["MU", "WDC", "STX", "GLD", "SLV", "BTCUSDT", "ETHUSDT"]
PARAMS = {"entry": 55, "exit": 20, "atr": 20, "stop_atr": 2.0}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"

import numpy as np
import pandas as pd


def weights(pan, params):
    close, high, low = pan["close"], pan["high"], pan["low"]
    upper = high.rolling(params["entry"]).max().shift(1)
    lower = low.rolling(params["exit"]).min().shift(1)
    result = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for ticker in close.columns:
        prev = close[ticker].shift(1)
        tr = pd.concat([high[ticker] - low[ticker], (high[ticker] - prev).abs(), (low[ticker] - prev).abs()], axis=1).max(axis=1)
        seed = tr.rolling(params["atr"]).mean()
        ready = seed.first_valid_index()
        if ready is None:
            continue
        seeded = tr.copy()
        seeded.loc[:ready] = np.nan
        seeded.loc[ready] = seed.loc[ready]
        atr = seeded.ewm(alpha=1 / params["atr"], adjust=False).mean().to_numpy()
        c, o = close[ticker].to_numpy(), pan["open"][ticker].to_numpy()
        hi, lo = upper[ticker].to_numpy(), lower[ticker].to_numpy()
        active, awaiting_fill, stop = False, False, np.nan
        values = np.zeros(len(close))
        for i in range(len(close)):
            if active:
                if awaiting_fill:
                    stop = o[i] - params["stop_atr"] * atr[i - 1]
                    awaiting_fill = False
                if c[i] < lo[i] or c[i] <= stop:
                    active = False
            elif np.isfinite(atr[i]) and c[i] > hi[i]:
                active, awaiting_fill = True, True
            values[i] = (1.0 / len(UNIVERSE)) if active else 0.0
        result[ticker] = values
    return result
