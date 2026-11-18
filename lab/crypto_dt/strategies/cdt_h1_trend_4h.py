"""Slow long-only Donchian trend on 4h crypto bars with volatility sizing; research only."""

from lab.crypto_dt import features

ID = "CDT_H1_TREND_4H"
HYPOTHESIS = (
    "Crypto trends persist for days, and slow trend rules are the only family with published net-of-cost evidence "
    "(Zarattini, Pagani, Barbon 2025). A three-speed Donchian ensemble on 4h bars keeps turnover low enough to survive "
    "10 bps per side, and volatility sizing caps the exposure of the noisier alts. The open question is whether the "
    "long-only half of the effect survives after 2022."
)
RULES = [
    "4h bars are built from 1h bars (open at 00/04/08/12/16/20 UTC); buckets with a missing hour are dropped.",
    "Per asset and per speed N in (20, 40, 80) bars: enter long on a close above the highest high of the prior N bars; leave on a close below the lowest low of the prior N/2 bars.",
    "Asset score = mean of the three speed states (0, 1/3, 2/3, 1).",
    "Weight = score * clip(0.5 / annualised realised vol of the last 90 bars, 0, 1) / 3 per asset; unused capital stays in cash.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {"n_fast": 20, "n_mid": 40, "n_slow": 80, "exit_ratio": 0.5, "vol_window": 90, "sigma_target": 0.5}
SPLIT_KIND = "crypto"
TIMEFRAME = "4h"
BARS_PER_YEAR = 6 * 365


def weights(pan, params):
    return features.trend_weights(pan, params, BARS_PER_YEAR)
