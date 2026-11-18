"""Gold/silver held only in a weak-dollar or falling-rates regime; research only."""
import pandas as pd

ID = "TOP_N3_GOLD_USD_REGIME"
HYPOTHESIS = (
    "Gold and silver pay no yield, so they tend to do well when the dollar weakens or when bond prices rise "
    "(falling real rates). UUP is the dollar proxy and TLT the long-bond proxy; both are signal-only. "
    "Requiring the metal itself to be in an uptrend avoids catching a falling knife when the macro regime "
    "looks friendly but the metal is not responding. Holding only the stronger of GLD/SLV concentrates on the metal "
    "the market is currently rewarding."
)
RULES = [
    "At each daily close the macro regime is ON if UUP close < its SMA(trend) OR TLT close > its SMA(trend).",
    "A metal (GLD or SLV) qualifies if its close > its own SMA(trend).",
    "If the regime is ON, hold the qualifying metal with the higher rs_lookback-day return, 100 percent. Only one metal at a time; no equal split.",
    "If the regime is OFF or no metal qualifies, hold cash. No shorts, no leverage. Decide at the close, fill at the next open.",
    "UUP and TLT are signal-only and never receive weight. Missing data means cash.",
]
UNIVERSE = ["GLD", "SLV", "UUP", "TLT"]
PARAMS = {"trend": 100, "rs_lookback": 63}
SPLIT_KIND = "equity"
TIMEFRAME = "1d"


def weights(pan, params):
    close = pan["close"]
    n = int(params["trend"])
    rs = int(params["rs_lookback"])
    sma = close.rolling(n, min_periods=n).mean()
    dollar_down = close["UUP"] < sma["UUP"]
    bonds_up = close["TLT"] > sma["TLT"]
    regime = (dollar_down | bonds_up).fillna(False)

    metals = ["GLD", "SLV"]
    above = close[metals] > sma[metals]
    momentum = close[metals] / close[metals].shift(rs) - 1
    score = momentum.where(above & regime.to_numpy()[:, None])
    gld, slv = score["GLD"], score["SLV"]
    pick_gld = gld.notna() & (slv.isna() | (gld >= slv))
    pick_slv = slv.notna() & ~pick_gld

    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    w.loc[pick_gld, "GLD"] = 1.0
    w.loc[pick_slv, "SLV"] = 1.0
    return w
