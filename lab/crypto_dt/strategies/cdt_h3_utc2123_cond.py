"""Conditional 21:00-23:00 UTC long window on hourly crypto bars; research only."""

import numpy as np
import pandas as pd

from lab.crypto_dt import features

ID = "CDT_H3_UTC2123_COND"
HYPOTHESIS = (
    "Buying BTC at 21:00 UTC and selling at 23:00 UTC showed 33-41% a year gross in practitioner studies (no costs, "
    "contested by a seven-exchange study). Unconditionally it cannot pay 20 bps round trip, so it is traded only on days "
    "when the window's own trailing mean return already exceeds the 30 bps cost hurdle and the daily trend is up."
)
RULES = [
    "Hourly bars. Window return for a UTC date = open of 23:00 / open of 21:00 - 1.",
    "At the close of the 20:00 bar of date d trade only if BOTH hold: (a) the mean window return over the previous 60 dates >= 30 bps; (b) the daily close (23:00 bar close) of date d-1 is above the SMA(50) of daily closes.",
    "If so hold the asset for the bars opening at 21:00 and 22:00 (exit at the 23:00 open), weight 1/3 per asset.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {"min_trailing_bps": 30.0, "trailing_days": 60, "sma_days": 50}
STRUCTURE = {"window_start_hour": 21, "window_hours": 2}
SPLIT_KIND = "crypto"
TIMEFRAME = "1h"


def weights(pan, params):
    open_, close = pan["open"], pan["close"]
    index = open_.index
    start, hours = STRUCTURE["window_start_hour"], STRUCTURE["window_hours"]
    trailing_days = int(params["trailing_days"])
    window = features.window_returns(open_, start, hours)
    trailing = window.shift(1).rolling(trailing_days, min_periods=trailing_days).mean()
    last_bar = index.hour == 23
    daily_close = close.loc[last_bar].set_axis(index[last_bar].normalize())
    sma = daily_close.rolling(int(params["sma_days"]), min_periods=int(params["sma_days"])).mean()
    above = (daily_close > sma).astype(float).where(sma.notna())
    prev_above = features.previous_day(above, window.index) == 1.0
    ok = (trailing >= float(params["min_trailing_bps"]) / 1e4) & prev_above
    entry_rows = features.hour_rows(index, (start - 1, start))
    dates = index[entry_rows].normalize()
    out = pd.DataFrame(0.0, index=index, columns=open_.columns)
    out.loc[entry_rows] = ok.reindex(dates).fillna(False).to_numpy(dtype=float) / len(open_.columns)
    return out
