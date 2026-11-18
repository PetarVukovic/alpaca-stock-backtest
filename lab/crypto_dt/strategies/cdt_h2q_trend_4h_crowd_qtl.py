"""CDT_H2 with the crowd gate implemented exactly as pre-registered (value vs trailing quantile); research only."""

import pandas as pd

from lab.crypto_dt import data, features

ID = "CDT_H2Q_TREND_4H_CROWD_QTL"
HYPOTHESIS = (
    "Same idea as CDT_H2_TREND_4H_CROWD: stand aside from the slow 4h trend while funding AND open-interest growth are "
    "both extreme (crowded longs). CDT_H2 compared a percentile RANK with 0.95 / 0.90, which differs from the "
    "pre-registered 'value >= 95th / 90th percentile of the trailing window' when values repeat (funding often sits at "
    "its 0.01% baseline). This ID implements the registered text literally; see "
    "docs/research/CRYPTO_DT_PREREGISTRATION_AMENDMENT_1.md."
)
RULES = [
    "Trend score and sizing exactly as CDT_H1_TREND_4H.",
    "Gate per asset at each 4h close: latest settled funding rate >= the 95th percentile (pandas linear interpolation) of its trailing 270 settlements AND the 42-bar open-interest change >= the 90th percentile of its trailing 180 days (window includes the current value).",
    "While the gate is true the asset weight is 0. While history is too short for either percentile the gate is inactive.",
    "A 5-minute metrics snapshot stamped ts is usable from ts + 5 min and only if it is at most 15 min old at that point; funding from its settlement time.",
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
OI_TOLERANCE = features.METRICS_TOLERANCE - features.METRICS_LAG  # counted from ts + lag, so the raw snapshot age is <= 15 min


def crowd_gate_quantile(index, symbols, params, bar_hours=BAR_HOURS):
    """True where funding and OI growth are both at or above their trailing value quantiles at the bar close."""
    decision = index + pd.Timedelta(hours=bar_hours)
    funding_win = int(params["funding_win"])
    oi_win = int(round(float(params["oi_win_days"]) * 24 / bar_hours))
    out = pd.DataFrame(False, index=index, columns=symbols)
    for symbol in symbols:
        funding = data.load_funding(symbol)
        limit = funding.rolling(funding_win, min_periods=funding_win).quantile(min(float(params["funding_pct"]), 0.999))
        flag = (funding >= limit).astype(float).where(limit.notna())
        funding_crowded = features.known_asof(flag, decision, pd.Timedelta(0), features.FUNDING_TOLERANCE) == 1.0
        oi = features.known_asof(data.load_metrics(symbol)["oi"], decision, features.METRICS_LAG, OI_TOLERANCE)
        change = oi / oi.shift(int(params["oi_chg_bars"])) - 1.0
        threshold = change.rolling(oi_win, min_periods=oi_win).quantile(min(float(params["oi_pct"]), 0.999))
        out[symbol] = (funding_crowded & (change >= threshold)).to_numpy(dtype=bool)  # NaN compares False
    return out


def weights(pan, params):
    close = pan["close"]
    gate = crowd_gate_quantile(close.index, list(close.columns), params)
    return features.trend_weights(pan, params, BARS_PER_YEAR, gate=gate)


def diagnostics(pan, params):
    """Share of 4h bars per asset where the gate is true (how often the filter acts)."""
    close = pan["close"]
    gate = crowd_gate_quantile(close.index, list(close.columns), params)
    return {"gate_true_share": {c: float(gate[c].mean()) for c in gate.columns}}
