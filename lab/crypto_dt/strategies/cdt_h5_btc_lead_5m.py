"""Falsification of a BTC -> ETH/SOL lead-lag at 5 minutes; research only."""

import numpy as np
import pandas as pd

ID = "CDT_H5_BTC_LEAD_5M"
HYPOTHESIS = (
    "Altcoins may react to a BTC impulse a few minutes late. The literature puts the lag at seconds to minutes with "
    "a disputed direction, so the expectation is that nothing is left after 20 bps round trip. The test shows whether "
    "anything survives inside 15 minutes behind a 5-minute BTC jump."
)
RULES = [
    "5m bars, log returns. sigma = standard deviation of the last 288 bar returns (including the closed bar), per asset.",
    "Trigger for ETH or SOL at a bar close: BTC return >= 2.0 sigma_BTC AND the asset's own return in that bar < 0.5 sigma_asset.",
    "Hold the asset for the next 3 bars (overlapping triggers extend the hold), weight 0.5 per asset; BTC itself is never held.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {"btc_sigma": 2.0, "asset_sigma": 0.5, "sigma_bars": 288, "hold_bars": 3, "weight": 0.5}
SPLIT_KIND = "crypto"
TIMEFRAME = "5m"


def weights(pan, params):
    close = pan["close"]
    ret = np.log(close / close.shift(1))
    bars = int(params["sigma_bars"])
    sigma = ret.rolling(bars, min_periods=bars).std()
    jump = ret["BTCUSDT"] >= float(params["btc_sigma"]) * sigma["BTCUSDT"]
    out = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    share = min(float(params["weight"]), 0.5)  # two traded assets: the sum can never exceed 1
    for asset in ("ETHUSDT", "SOLUSDT"):
        lagging = ret[asset] < float(params["asset_sigma"]) * sigma[asset]
        trigger = (jump & lagging).astype(float)
        out[asset] = trigger.rolling(int(params["hold_bars"]), min_periods=1).max() * share
    return out
