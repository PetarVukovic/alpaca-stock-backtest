"""Chip-equipment leaders confirm an uptrend before memory names are held; research only."""
import pandas as pd

ID = "TOP_N1_SEMI_LEADLAG"
HYPOTHESIS = (
    "Chip-equipment makers (AMAT, LRCX, KLAC) and the SMH semiconductor ETF react to capex plans before memory "
    "demand shows up in memory-maker prices. When most of these leaders trade above their own long trend, "
    "memory names (MU, WDC, STX) that are also above their own trend should keep rising for days to weeks. "
    "When the leaders lose their trend, capex expectations are weakening and the memory names are left in cash."
)
RULES = [
    "At each daily close, a leader (AMAT, LRCX, KLAC, SMH) is 'in uptrend' if its close is above its trailing leader_trend-bar simple average (current close included).",
    "The leader basket is 'confirmed' when at least min_leaders of the 4 leaders are in uptrend.",
    "A memory name (MU, WDC, STX) is eligible when the basket is confirmed AND its close is above its own stock_trend-bar simple average.",
    "Sizing: each eligible memory name gets an equal 1/3 of capital; non-eligible slots stay in cash. Leaders are signal-only (weight 0). No shorts, no leverage.",
    "Decide at the close, fill at the next open. No hysteresis or minimum holding period.",
]
UNIVERSE = ["MU", "WDC", "STX", "AMAT", "LRCX", "KLAC", "SMH"]
PARAMS = {"leader_trend": 100, "stock_trend": 50, "min_leaders": 3}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"

LEADERS = ["AMAT", "LRCX", "KLAC", "SMH"]
MEMORY = ["MU", "WDC", "STX"]


def weights(pan, params):
    close = pan["close"]
    lt, st = int(params["leader_trend"]), int(params["stock_trend"])
    leaders = close[LEADERS]
    up = (leaders > leaders.rolling(lt, min_periods=lt).mean()).sum(axis=1)
    confirmed = up >= int(params["min_leaders"])
    mem = close[MEMORY]
    above = mem > mem.rolling(st, min_periods=st).mean()
    eligible = above.mul(confirmed, axis=0)
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    w[MEMORY] = eligible.astype(float) / len(MEMORY)
    return w
