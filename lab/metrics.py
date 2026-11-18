"""Daily marked-to-market risk statistics (fractions converted to percent)."""

import numpy as np
import pandas as pd

from lab.contracts import PeriodStats


def sharpe(returns):
    values = pd.Series(returns, dtype=float).dropna()
    if len(values) < 2 or values.std(ddof=1) == 0:
        return None
    return float(values.mean() / values.std(ddof=1) * np.sqrt(252))


def summarize(trades, equity, benchmark):
    returns = pd.Series([t["net_return"] for t in trades], dtype=float)
    daily = equity.resample("D").last().dropna()
    # Resample to observed trading dates only; first return includes initial capital.
    changes = daily.pct_change()
    if len(daily):
        changes.iloc[0] = daily.iloc[0] / 500 - 1
    peaks = equity.cummax().clip(lower=500)
    dd = float((equity / peaks - 1).min() * 100) if len(equity) else None
    stats = PeriodStats(
        n=len(returns),
        mean_pct=float(returns.mean() * 100) if len(returns) else None,
        win_rate=float((returns > 0).mean()) if len(returns) else None,
        sharpe=sharpe(changes),
        max_dd_pct=dd,
        buy_hold_sharpe=sharpe(benchmark.resample("D").last().dropna().pct_change()),
    )
    flags = []
    if len(returns) < 10:
        flags.append("n_lt_10")
    positive = returns[returns > 0]
    if len(positive) and positive.nlargest(3).sum() / positive.sum() > 0.5:
        flags.append("top3_concentration")
    return stats, flags
