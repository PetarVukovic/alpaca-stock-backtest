"""Intraday momentum: a positive first four hours of the UTC day on high volume predicts the 22:00-24:00 window."""

import pandas as pd

from lab.crypto_dt import features

ID = "CDT_H4_ID_MOM_VOL"
HYPOTHESIS = (
    "Shen, Urquhart and Wang (2022) report that the first period of the day predicts the last period for Bitcoin, "
    "more strongly with high volume. Replication after 2022 is unknown. A 2-hour holding period at 20 bps round trip "
    "is cost-hostile, so this is included mainly as a falsification."
)
RULES = [
    "Hourly bars, day = UTC date. First period = open 00:00 to open 04:00; its volume = sum of the four hourly volumes.",
    "At the close of the 21:00 bar trade only if the first-period return > 0 AND its volume ranks >= 80th percentile among the last 60 days (including today).",
    "If so hold for the bars opening at 22:00 and 23:00 (exit at the 00:00 open), weight 1/3 per asset.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {"vol_pct": 0.8, "vol_days": 60}
STRUCTURE = {"first_hours": 4, "entry_decision_hour": 21, "hold_hours": 2}
SPLIT_KIND = "crypto"
TIMEFRAME = "1h"


def weights(pan, params):
    open_, volume = pan["open"], pan["volume"]
    index = open_.index
    first = STRUCTURE["first_hours"]
    first_ret = features.window_returns(open_, 0, first)
    early = index.hour < first
    first_volume = volume.loc[early].groupby(index[early].normalize()).sum(min_count=first)
    vol_days = int(params["vol_days"])
    rank = first_volume.rolling(vol_days, min_periods=vol_days).rank(pct=True)
    ok = (first_ret > 0) & (rank.reindex(first_ret.index) >= min(float(params["vol_pct"]), 0.999))
    decision = STRUCTURE["entry_decision_hour"]
    rows = features.hour_rows(index, tuple(range(decision, decision + STRUCTURE["hold_hours"])))
    dates = index[rows].normalize()
    out = pd.DataFrame(0.0, index=index, columns=open_.columns)
    out.loc[rows] = ok.reindex(dates).fillna(False).to_numpy(dtype=float) / len(open_.columns)
    return out
