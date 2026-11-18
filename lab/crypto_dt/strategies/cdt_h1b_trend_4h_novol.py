"""CDT_H1 without volatility sizing, to isolate what the sizing contributes; research only."""

from lab.crypto_dt import features

ID = "CDT_H1B_TREND_4H_NOVOL"
HYPOTHESIS = (
    "Same slow 4h Donchian trend as CDT_H1_TREND_4H but every asset gets a flat 1/3 weight while its score is on. "
    "Comparing it with H1 shows whether volatility sizing helps or hurts crypto (the literature suspects that vol "
    "targeting can hurt BTC because its volatility and returns are positively linked)."
)
RULES = [
    "Identical to CDT_H1_TREND_4H (4h bars, three Donchian speeds 20/40/80 with exit at N/2, score = mean of the states).",
    "Weight = score / 3 per asset, with no volatility factor.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {"n_fast": 20, "n_mid": 40, "n_slow": 80, "exit_ratio": 0.5, "sigma_target": None}
SPLIT_KIND = "crypto"
TIMEFRAME = "4h"
BARS_PER_YEAR = 6 * 365


def weights(pan, params):
    return features.trend_weights(pan, params, BARS_PER_YEAR)
