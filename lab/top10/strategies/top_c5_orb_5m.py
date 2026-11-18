"""Confirmed opening-range breakout with next-open fills and no overnight risk."""
import numpy as np
import pandas as pd

ID = "TOP_C5_ORB_5M"
HYPOTHESIS = (
    "The first half hour aggregates overnight information. A confirmed break above "
    "that range while above session VWAP may identify persistent intraday buying "
    "in liquid memory stocks, without relying on overnight price changes."
)
RULES = [
    "Use UTC five-minute timestamps converted to America/New_York; regular session only, 09:30 to 16:00.",
    "Build the opening high and low from the first six consecutive five-minute bars starting at 09:30; incomplete opening ranges cannot trade.",
    "After that range, enter at the next open on a close above both its high and session cumulative typical-price VWAP, provided the current low stays above the range low.",
    "One entry per ticker per session. Once held, a bar low at or below the opening low triggers exit at the NEXT open, not a guaranteed stop fill at the range low.",
    "Reserve one equal capital slot per universe member; unused slots remain cash. No leverage or short positions.",
    "Set weights to zero at 15:50 and later, so next-open liquidation is at 15:55; weights are also zero outside regular hours and on a new session until an entry.",
    "Conservatively liquidate at 12:55 on July 2/3, December 24, and the Friday after the fourth Thursday of November; signal zero at 12:50. This also shortens some full sessions, by design, without reading future bars.",
    "Use positive observed volume for VWAP; missing opening bars or zero-volume opening bars invalidate the opening range. No use of full-day counts or future last-bar detection.",
]
UNIVERSE = ["MU", "WDC", "STX"]
PARAMS = {"opening_bars": 6, "max_entries": 1, "flat_time": "15:55", "early_flat_time": "12:55"}
SPLIT_KIND = "equity"
TIMEFRAME = "5m"


def _minute(clock):
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def weights(pan, params):
    close = pan["close"]
    index = close.index
    local = (index.tz_localize("UTC") if index.tz is None else index).tz_convert("America/New_York")
    minute = np.asarray(local.hour * 60 + local.minute)
    day = np.asarray(local.strftime("%Y-%m-%d"))
    # Fixed conservative calendar policy, known before observing any price outcome.
    early = ((local.month == 7) & np.isin(local.day, [2, 3])) | ((local.month == 12) & (local.day == 24)) | (
        (local.month == 11) & (local.weekday == 4) & (local.day >= 23) & (local.day <= 29)
    )
    deadline = np.where(early, _minute(params["early_flat_time"]), _minute(params["flat_time"])) - 5
    n = int(params["opening_bars"])
    out = np.zeros(close.shape, dtype=float)
    highs, lows = pan["high"].to_numpy(), pan["low"].to_numpy()
    closes, volumes = close.to_numpy(), pan["volume"].to_numpy()
    for j, ticker in enumerate(close.columns):
        if ticker not in UNIVERSE:
            continue
        previous_day = None
        for i in range(len(index)):
            if day[i] != previous_day:
                previous_day = day[i]
                range_high, range_low = -np.inf, np.inf
                count, entries, held = 0, 0, False
                pv, volume_sum, opening_valid = 0.0, 0.0, True
            m = minute[i]
            if m < 570 or m >= 960:
                held = False
                continue
            h, l, c, v = highs[i, j], lows[i, j], closes[i, j], volumes[i, j]
            valid = np.isfinite([h, l, c, v]).all() and v > 0 and l > 0 and h >= l
            if valid:
                pv += ((h + l + c) / 3.0) * v
                volume_sum += v
            if m < 570 + 5 * n:
                if m != 570 + 5 * count or not valid:
                    opening_valid = False
                count += 1
                if valid:
                    range_high, range_low = max(range_high, h), min(range_low, l)
                continue
            if m >= deadline[i]:
                held = False
                continue
            if held:
                if not valid or l <= range_low:
                    held = False
            elif opening_valid and count == n and valid and entries < int(params["max_entries"]):
                if c > range_high and volume_sum > 0 and c > pv / volume_sum and l > range_low:
                    held = True
                    entries += 1
            if held:
                out[i, j] = 1.0 / len(UNIVERSE)
    return pd.DataFrame(out, index=index, columns=close.columns)
