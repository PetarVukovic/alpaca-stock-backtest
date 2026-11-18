"""Canonical CSV loading; never adjust existing prices."""

from pathlib import Path
import re

import numpy as np
import pandas as pd

from lab.contracts import PERIODS

ROOT = Path(__file__).resolve().parents[1]
WDC_FACTOR = 0.68132
WATCH_ONLY = {"DRAM", "SKHY", "SNDK"}


def period_for(day):
    day = str(day)[:10]
    return next((p for p, (start, end) in PERIODS.items() if start <= day <= end), None)


def validate_frame(frame):
    required = {"open", "high", "low", "close", "volume", "date"}
    if not required <= set(frame):
        raise ValueError("Missing OHLCV/date columns")
    px = frame[["open", "high", "low", "close"]]
    if not np.isfinite(px.to_numpy()).all() or (px <= 0).any().any():
        raise ValueError("Invalid prices")
    if ((frame.high < px.max(axis=1)) | (frame.low > px.min(axis=1))).any():
        raise ValueError("OHLC outside range")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Duplicate or unsorted bars")
    if (frame.volume.dropna() < 0).any():
        raise ValueError("Negative volume")
    return frame


def check_wdc(frame, root=ROOT):
    raw_path = Path(root) / "data/ohlcv/WDC_1d.raw_unadjusted_spinoff.csv"
    if raw_path.exists() and frame.attrs.get("timeframe") == "daily":
        raw = pd.read_csv(raw_path).set_index("date")
        before = frame[frame.date < "2025-02-24"].set_index("date")
        shared = before.index.intersection(raw.index)
        if len(shared):
            ratios = before.loc[shared, "close"] / raw.loc[shared, "close"]
            if not np.allclose(ratios, WDC_FACTOR, rtol=1e-5):
                raise ValueError("WDC adjustment missing or applied twice")
    elif frame.attrs.get("timeframe") != "daily":
        daily_path = Path(root) / "data/ohlcv/WDC_1d.csv"
        if daily_path.exists():
            daily = pd.read_csv(daily_path).set_index("date").close
            last = frame.groupby("date").close.last()
            shared = last.index.intersection(daily.index)
            if (
                len(shared)
                and (last.loc[shared] / daily.loc[shared] - 1).abs().median() > 0.05
            ):
                raise ValueError("WDC intraday/daily adjustment mismatch")


def load_bars(ticker, timeframe="daily", root=ROOT, through=None):
    from datetime import date
    cutoff = date.fromisoformat(str(through)).isoformat() if through is not None else None
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]*", ticker):
        raise ValueError("Invalid ticker")
    paths = {
        "daily": ("ohlcv", "1d"),
        "hourly": ("hourly", "1h_clean"),
        "5min": ("intraday", "5m_clean"),
    }
    folder, suffix = paths[timeframe]
    frame = pd.read_csv(Path(root) / f"data/{folder}/{ticker}_{suffix}.csv")
    if timeframe == "daily":
        frame["date"] = frame["date"].astype(str).str[:10]
        frame.index = pd.to_datetime(frame.date, utc=True)
        if cutoff is not None:
            frame = frame.loc[frame.date <= cutoff].copy()
    else:
        stamps = pd.to_datetime(frame.ts, utc=True)
        frame.index = stamps
        frame["date"] = (
            stamps.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d").to_numpy()
        )
        if cutoff is not None:
            frame = frame.loc[frame.date <= cutoff].copy()
        frame = frame.loc[frame.session == "regular"].copy()
        if timeframe == "hourly":
            calendar_path = Path(root) / f"data/intraday/{ticker}_5m_clean.csv"
            if calendar_path.exists():
                calendar = pd.read_csv(calendar_path, usecols=["ts", "session_end"])
                ends = calendar[
                    calendar.session_end.astype(str).str.lower().isin(["true", "1"])
                ]
                closing = pd.to_datetime(ends.ts, utc=True) + pd.Timedelta(minutes=5)
                end_by_day = dict(
                    zip(
                        closing.dt.tz_convert("America/New_York").dt.strftime(
                            "%Y-%m-%d"
                        ),
                        closing,
                    )
                )
                close_at = pd.to_datetime(frame.date.map(end_by_day), utc=True)
                if close_at.isna().any():
                    raise ValueError(
                        "Missing official session end evidence for hourly day"
                    )
                early = close_at.dt.tz_convert("America/New_York").dt.hour < 16
                removed = frame.index >= close_at
                counts = frame.loc[removed].groupby("date").size().to_dict()
                frame["early_close"] = early.to_numpy()
                frame["session_end"] = (
                    frame.index + pd.Timedelta(hours=1) == close_at
                ).to_numpy()
                frame = frame.loc[~removed].copy()
                frame.attrs["excluded_after_close_by_date"] = counts
            elif ticker in {"MU", "WDC", "STX"}:
                raise ValueError("Hourly primary requires session calendar evidence")
        good = frame.volume_ok.astype(str).str.lower().isin(["true", "1"])
        frame.loc[~good, "volume"] = np.nan
    if cutoff is not None:
        frame.attrs["through"] = cutoff
    if ticker == "DRAM":
        frame = frame.loc[frame.date >= "2026-04-02"].copy()
    frame.attrs.update(ticker=ticker, timeframe=timeframe)
    validate_frame(frame)
    if ticker == "WDC":
        check_wdc(frame, root)
    return frame


def split_periods(frame):
    return {
        p: frame.loc[frame.date.between(start, end)].copy()
        for p, (start, end) in PERIODS.items()
    }
