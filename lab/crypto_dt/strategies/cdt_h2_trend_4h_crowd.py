"""CDT_H1 plus a flat-gate for crowded longs (extreme funding and fast open-interest growth); research only."""

from lab.crypto_dt import features

ID = "CDT_H2_TREND_4H_CROWD"
HYPOTHESIS = (
    "Extremely positive funding together with fast open-interest growth marks crowded long positioning, and such "
    "peaks tend to end in liquidation cascades. Standing aside from the trend while both are extreme should cut "
    "drawdowns. Evidence is anecdotal (K33, BitMEX reports), so this is original work with a high overfitting risk."
)
RULES = [
    "Trend score and sizing exactly as CDT_H1_TREND_4H.",
    "Gate per asset at each 4h close: funding percentile rank (latest settled rate within the last 270 settlements) >= 0.95 AND open-interest 42-bar change percentile rank (within the last 180 days) >= 0.90.",
    "While the gate is true the asset weight is 0. While history is too short for either percentile the gate is inactive.",
    "Derivatives are aligned causally: a 5-minute metrics snapshot stamped ts is usable from ts + 5 min, funding from its settlement time.",
    "Decide at the bar close, fill at the next bar open, long-only, no leverage.",
]
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PARAMS = {
    "n_fast": 20, "n_mid": 40, "n_slow": 80, "exit_ratio": 0.5, "vol_window": 90, "sigma_target": 0.5,
    "funding_win": 270, "funding_pct": 0.95, "oi_chg_bars": 42, "oi_pct": 0.90, "oi_win_days": 180,
}
SPLIT_KIND = "crypto"
TIMEFRAME = "4h"
BARS_PER_YEAR = 6 * 365
BAR_HOURS = 4


def weights(pan, params):
    close = pan["close"]
    gate = features.crowd_gate(close.index, list(close.columns), params, BAR_HOURS)
    return features.trend_weights(pan, params, BARS_PER_YEAR, gate=gate)


def diagnostics(pan, params):
    """Share of 4h bars per asset where the gate is true (how often the filter acts)."""
    close = pan["close"]
    gate = features.crowd_gate(close.index, list(close.columns), params, BAR_HOURS)
    return {"gate_true_share": {c: float(gate[c].mean()) for c in gate.columns}}
