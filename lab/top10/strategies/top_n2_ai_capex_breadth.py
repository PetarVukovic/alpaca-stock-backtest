"""AI capex breadth: hyperscaler trend breadth gates memory/storage exposure; research only."""
import pandas as pd

ID = "TOP_N2_AI_CAPEX_BREADTH"
HYPOTHESIS = (
    "Hyperscaler capex is the largest demand source for memory and storage. When most of the four big "
    "cloud spenders (MSFT GOOGL AMZN META) trade above their medium-term trend, the market is pricing "
    "continued AI spending, which should lift expectations for memory and storage demand. Holding the "
    "memory names that are individually in an uptrend only while this breadth is high ties the exposure "
    "to the demand driver and keeps the book in cash when capex sentiment breaks."
)
RULES = [
    "At each daily close, a hyperscaler (MSFT GOOGL AMZN META) is 'on' when its close is above its 100-day simple moving average.",
    "Breadth gate is open when at least 3 of the 4 hyperscalers are on; hyperscalers are signal-only and never held.",
    "When the gate is open, each memory name (MU WDC STX RMBS SIMO) whose own close is above its own 100-day SMA gets a weight of 1/5 (equal weight per name slot).",
    "Gate closed, or a name below its trend, or insufficient history: that slot stays in cash. Long-only, no leverage, sum of weights <= 1.",
    "Decide at the close, fill at the next open; no stops, no minimum holding period.",
]
UNIVERSE = ["MSFT", "GOOGL", "AMZN", "META", "MU", "WDC", "STX", "RMBS", "SIMO"]
PARAMS = {"trend": 100, "min_on": 3}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"

HYPERSCALERS = ["MSFT", "GOOGL", "AMZN", "META"]
MEMORY = ["MU", "WDC", "STX", "RMBS", "SIMO"]


def weights(pan, params):
    close = pan["close"]
    n = int(params["trend"])
    above = close > close.rolling(n, min_periods=n).mean()
    breadth = above[HYPERSCALERS].sum(axis=1)
    gate = breadth >= int(params["min_on"])
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for ticker in MEMORY:
        w[ticker] = (above[ticker] & gate).astype(float) / len(MEMORY)
    return w
