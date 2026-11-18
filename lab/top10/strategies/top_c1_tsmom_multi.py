"""Predeclared 12-minus-1-month momentum; research only."""

ID = "TOP_C1_TSMOM_MULTI"
HYPOTHESIS = (
    "Investors incorporate persistent macro and earnings news gradually; slow institutional "
    "allocation and investors selling winners too early can sustain trends across assets. "
    "A positive prior-year return excluding the latest month may capture this persistence, "
    "while avoiding some short-lived reversal. Crowding and abrupt regime changes can erase it."
)
RULES = [
    "Use the shared equity-session calendar, including for BTCUSDT and ETHUSDT; no weekend decisions.",
    "At the close of the first available session of each ISO week, compute close[t-skip] / close[t-lookback] - 1.",
    "Hold each asset whose return is strictly above threshold and whose full lookback is available; otherwise hold cash.",
    "Divide all capital equally among eligible assets; zero eligible assets means all cash. No leverage or shorts.",
    "Keep target weights unchanged until the next weekly decision. The engine restores these targets at each next open and charges drift turnover.",
    "Lookback 252 and skip 21 are conventional equity-session approximations of a year and a month, declared before evaluation.",
]
UNIVERSE = ["GLD", "SLV", "BTCUSDT", "ETHUSDT", "MU", "WDC", "STX", "SMH"]
PARAMS = {"lookback": 252, "skip": 21, "threshold": 0.0}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"


def weights(pan, params):
    close = pan["close"]
    momentum = close.shift(params["skip"]) / close.shift(params["lookback"]) - 1
    eligible = momentum.gt(params["threshold"]) & close.notna()
    targets = eligible.astype(float).div(eligible.sum(axis=1).replace(0, 1), axis=0)
    weeks = close.index.to_series().dt.to_period("W-SUN")
    decision = weeks.ne(weeks.shift(1))
    return targets.where(decision, axis=0).ffill().fillna(0.0)
