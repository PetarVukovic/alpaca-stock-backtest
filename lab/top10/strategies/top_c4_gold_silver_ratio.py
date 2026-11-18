"""Relative metal valuation using a trailing ETF-price ratio; research only."""
import pandas as pd

ID = "TOP_C4_GOLD_SILVER_RATIO"
HYPOTHESIS = (
    "Gold and silver share monetary demand but their relative prices sometimes diverge. "
    "A trailing gold/silver ETF-price ratio may identify the temporarily cheaper metal; "
    "holding only that metal during extreme deviations tests relative-value mean reversion."
)
RULES = [
    "At each daily close compute GLD close / SLV close and its trailing 60-bar z-score, including the current close; population standard deviation.",
    "If z >= 2 hold SLV; if z <= -2 hold GLD; otherwise hold cash. No hysteresis or minimum holding period.",
    "Allocate 100 percent to the selected ETF, with no shorts or leverage; missing/zero dispersion means cash.",
    "Decide at the close and fill at the next open. ETF-price ratio is a proxy, not an ounce-price ratio or a hedged pair trade.",
]
UNIVERSE = ["GLD", "SLV"]
PARAMS = {"lookback": 60, "threshold": 2.0}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"


def weights(pan, params):
    close = pan["close"]
    ratio = close["GLD"] / close["SLV"].where(close["SLV"] > 0)
    rolling = ratio.rolling(int(params["lookback"]), min_periods=int(params["lookback"]))
    deviation = rolling.std(ddof=0)
    z = (ratio - rolling.mean()) / deviation.where(deviation > 0)
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    w.loc[z >= float(params["threshold"]), "SLV"] = 1.0
    w.loc[z <= -float(params["threshold"]), "GLD"] = 1.0
    return w
