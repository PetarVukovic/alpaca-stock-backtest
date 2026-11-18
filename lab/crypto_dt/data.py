"""Bars and derivative series for the CDT_* research; every index is naive UTC, like `lab.top10.core`."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from lab.top10 import core

DERIVS = core.ROOT / "data/derivs"
BAR_HOURS = {"1h": 1, "4h": 4}
_load_frames = core.load_frames  # the runner patches core.load_frames to call load_bars; keep the original


def resample_ohlcv(frame: pd.DataFrame, hours: int) -> pd.DataFrame:
    """Aggregate hourly bars to `hours`-hour bars labelled by their open time.

    Buckets that lack any constituent hour (exchange gaps) are dropped rather than built from partial
    data, so a 4h bar never silently covers less than 4 hours.
    """
    grouped = frame.resample(f"{hours}h", label="left", closed="left")
    out = pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "volume": grouped["volume"].sum(),
        }
    )
    return out[grouped["close"].count() == hours]


def load_bars(
    tickers: Sequence[str], timeframe: str, cutoff: str = core.CUTOFF
) -> dict[str, pd.DataFrame]:
    """OHLCV per ticker for 5m / 1h (straight from the lab files) or 4h (built from 1h)."""
    if timeframe == "4h":
        hourly = _load_frames(tickers, cutoff, "1h")
        return {t: resample_ohlcv(f, 4) for t, f in hourly.items()}
    return _load_frames(tickers, cutoff, timeframe)


def load_funding(symbol: str) -> pd.Series:
    """Settled 8h funding rate indexed by funding time; known from that timestamp on."""
    raw = pd.read_csv(DERIVS / f"{symbol}_funding.csv")
    index = pd.to_datetime(raw["ts"], utc=True).dt.tz_localize(None)
    return pd.Series(raw["funding_rate"].to_numpy(), index=index, name="funding").sort_index()


def load_metrics(symbol: str) -> pd.DataFrame:
    """5-minute open interest and flow ratios; `oi == 0` rows are exchange glitches and become NaN."""
    raw = pd.read_csv(DERIVS / f"{symbol}_metrics_5m.csv")
    raw.index = pd.to_datetime(raw.pop("ts"), utc=True).dt.tz_localize(None)
    raw = raw[~raw.index.duplicated()].sort_index()
    raw.loc[raw["oi"] <= 0, ["oi", "oi_value"]] = float("nan")
    return raw
