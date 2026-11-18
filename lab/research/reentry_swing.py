"""C28 isolated research candidate: reclaim the pre-stop peak after a completed later day.

Execution core copied from memory_swing.py SHA256 96cbc9dca31a5fbc22675ed90f5ac6eb609853008fb05230f89731a75a3f1d8f.
The baseline file is deliberately untouched. Disabled mode delegates to that exact API.
No broker adapters, credentials, settings or orders. No Critic approval.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from app.backend.strategies.c13c import stop_for, TICKERS
from lab.research.memory_swing import replay as baseline_replay, metrics, benchmark


def entry_signals(frame, trend=200, bars=5, dip=.05):
    return ((frame.close > frame.close.rolling(trend).mean()) &
            (frame.close / frame.close.shift(bars) - 1 <= -dip)).fillna(False)


def replay(frames, start, end, capital, sizing="one", cap=1200,
           trend=200, bars=5, dip=.05, trail=.1, stress=1,
           entry_delay_sessions=1, extra_entry_bps=0, extra_exit_bps=0, market_filter=None,
           reentry_enabled=False):
    """One shared position; first signalling symbol has deterministic priority.

    Previous completed close can schedule the first requested day's open.
    Final holdings remain marked at close, matching the app replay convention.
    Diagnostic delays count shared trading sessions from the signal close. A queued
    entry retains its original signal and cannot be replaced by newer signals.
    Additional basis points are execution friction, never modified market bars.
    An optional UTC-indexed Boolean market filter gates only the signal date.
    Volatility sizing targets 1.5% daily volatility from the prior 20 daily returns,
    capped at available cash; it adds no leverage or guarantee against gap losses.
    These options are offline research and never update the live application's settings.
    """
    if not reentry_enabled:
        return baseline_replay(frames, start, end, capital, sizing=sizing, cap=cap,
            trend=trend, bars=bars, dip=dip, trail=trail, stress=stress,
            entry_delay_sessions=entry_delay_sessions, extra_entry_bps=extra_entry_bps,
            extra_exit_bps=extra_exit_bps, market_filter=market_filter)
    numeric = (capital, cap, trend, bars, dip, trail, stress, entry_delay_sessions, extra_entry_bps, extra_exit_bps)
    if not all(math.isfinite(value) for value in numeric):
        raise ValueError("Non-finite replay configuration")
    if capital <= 0 or cap <= 0 or sizing not in {"one", "risk2", "all", "volatility"} or stress < 1:
        raise ValueError("Invalid replay configuration")
    if not 0 < trail < 1 or trend < 1 or bars < 1 or int(trend) != trend or int(bars) != bars or not 0 < dip < 1:
        raise ValueError("Invalid rule")
    if entry_delay_sessions < 1 or int(entry_delay_sessions) != entry_delay_sessions or extra_entry_bps < 0 or extra_exit_bps < 0:
        raise ValueError("Invalid execution diagnostics")
    if market_filter is not None and (not isinstance(market_filter, pd.Series) or market_filter.index.has_duplicates):
        raise ValueError("Market filter must be a uniquely indexed Series")
    start_at, end_at = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    if start_at > end_at:
        raise ValueError("Reversed replay interval")
    clean = {}
    for symbol, frame in frames.items():
        if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
            raise ValueError("Timezone-aware daily dates required")
        frame = frame.loc[frame.index <= end_at].copy()
        if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
            raise ValueError("Duplicate or unsorted daily dates")
        required = ["open", "high", "low", "close", "volume"]
        if not set(required) <= set(frame):
            raise ValueError("Missing OHLCV columns")
        values = frame[required].to_numpy(float)
        if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
            raise ValueError("Invalid OHLCV values")
        if ((frame.high < frame[["open", "low", "close"]].max(axis=1)) |
                (frame.low > frame[["open", "high", "close"]].min(axis=1))).any():
            raise ValueError("OHLC outside range")
        clean[symbol] = frame
    frames = clean
    if not frames or any(frame.empty for frame in frames.values()):
        return None
    common = None
    for f in frames.values():
        common = f.index if common is None else common.intersection(f.index)
    if common is None or common.empty:
        return None
    # Missing dates inside a requested common history must not be silently aligned away.
    available_start = max(f.index[0] for f in frames.values())
    available_end = min(f.index[-1] for f in frames.values())
    for f in frames.values():
        sample = f.loc[available_start:available_end]
        if not sample.index.equals(common):
            raise ValueError("Different calendars inside common history")
    dates = common[(common >= pd.Timestamp(start, tz="UTC")) &
                   (common <= pd.Timestamp(end, tz="UTC"))]
    if dates.empty:
        return None
    signals = {s: entry_signals(f, trend, bars, dip) for s, f in frames.items()}
    arrays = {s: f.reindex(dates)[["open", "high", "low", "close", "volume"]].to_numpy(float)
              for s, f in frames.items()}
    priority = [s for s in TICKERS if s in frames] + [s for s in frames if s not in TICKERS]
    averages = {s:f.close.rolling(trend).mean() for s,f in frames.items()}
    anchors = {}
    entry_tags = []
    cash = float(capital)
    position = None
    pending = None
    pending_due = None
    trades, equity, exposure, skipped, events = [], [], [], [], []
    collisions = 0
    cost_total = 0.
    max_participation = 0.
    fill_violations = 0

    def candidate(day):
        nonlocal collisions
        if market_filter is not None:
            allowed = market_filter.get(day, False)
            if not isinstance(allowed, (bool, np.bool_)):
                raise ValueError("Market filter values must be booleans on completed signal dates")
            if not allowed:
                return None
        candidates = []
        for symbol in priority:
            if day not in signals[symbol].index:
                continue
            anchor = anchors.get(symbol)
            normal = bool(signals[symbol].loc[day])
            reclaim = bool(anchor and day > anchor['exit_day'] and
                frames[symbol].loc[day, 'close'] > anchor['peak'] and
                frames[symbol].loc[day, 'close'] > averages[symbol].loc[day])
            if normal or reclaim:
                candidates.append(dict(ticker=symbol, entry_reason='normal_dip' if normal else 'reentry_reclaim',
                    reentry_anchor=anchor['peak'] if reclaim and not normal else None,
                    signal_date=str(day.date())))
        collisions += len(candidates) > 1
        return candidates[0] if candidates else None

    prior = common[common < dates[0]]
    if len(prior):
        pending = candidate(prior[-1])
        pending_due = int(entry_delay_sessions) - 1 if pending else None
    for i, day in enumerate(dates):
        if pending and position is None and i >= pending_due:
            symbol = pending["ticker"]
            raw, high, low, close, volume = arrays[symbol][i]
            price = raw + stress * (raw * .00025 + .01) + raw * extra_entry_bps / 10000
            if sizing == "one":
                quantity = 1 if price <= min(cash, cap) else 0
            elif sizing == "all":
                # Offline research only: spend available cash on whole shares without leverage.
                # The protective stop remains active; a gap can exceed its modeled loss.
                quantity = math.floor(min(cash, cap) / price)
            elif sizing == "volatility":
                # Entry-day opening prices never enter the volatility estimate.
                history = frames[symbol].loc[frames[symbol].index < day, "close"].tail(21)
                past_returns = history.pct_change().dropna()
                vol = float(past_returns.std(ddof=1)) if len(past_returns) == 20 else None
                weight = min(1., .015 / vol) if vol and vol > 0 else (1. if vol == 0 else 0.)
                quantity = math.floor(min(cash * weight, cap) / price)
            else:
                # 2% modeled initial-stop loss including exit costs and cent rounding.
                # This is not a loss guarantee: a gap can execute below that stop.
                initial_stop = stop_for(price) if trail == .1 else _rounded_stop(price, trail)
                modeled_exit = max(0., initial_stop - stress * (initial_stop * .00025 + .01) - initial_stop * extra_exit_bps / 10000)
                per_share_risk = price - modeled_exit
                quantity = min(math.floor(cash * .02 / per_share_risk),
                               math.floor(min(cash, cap) / price))
            if quantity > 0:
                cash -= quantity * price
                cost_total += quantity * (price - raw)
                max_participation = max(max_participation, quantity / volume if volume > 0 else float("inf"))
                fill_violations += int(volume <= 0 or not low <= raw <= high)
                position = dict(ticker=symbol, entry_date=str(day.date()), entry_price=price,
                                raw_entry=raw, quantity=quantity, peak=price, entry_i=i,
                                entry_reason=pending['entry_reason'], reentry_anchor=pending['reentry_anchor'],
                                signal_date=pending['signal_date'])
                entry_tags.append(dict(entry_date=str(day.date()), **pending))
                anchors.pop(symbol, None)  # Only a successful buy consumes this symbol's anchor.
                events.append((str(day.date()), "buy", symbol, quantity, price))
            else:
                skipped.append(dict(date=str(day.date()), ticker=symbol,
                                    reason="cash_or_whole_share_risk_budget", price=price, cash=cash,
                                    entry_reason=pending['entry_reason'], reentry_anchor=pending['reentry_anchor']))
            pending = None
            pending_due = None
        if position is not None:
            symbol = position["ticker"]
            raw_open, high, low, close, volume = arrays[symbol][i]
            # The app rule uses explicit decimal cent rounding. Diagnostics retain it.
            stop = stop_for(position["peak"]) if trail == .1 else _rounded_stop(position["peak"], trail)
            if low <= stop:
                raw_exit = min(raw_open, stop)
                price = max(0., raw_exit - stress * (raw_exit * .00025 + .01) - raw_exit * extra_exit_bps / 10000)
                quantity = position["quantity"]
                cash += quantity * price
                cost_total += quantity * (raw_exit - price)
                max_participation = max(max_participation, quantity / volume if volume > 0 else float("inf"))
                fill_violations += int(volume <= 0 or not low - 1e-8 <= raw_exit <= high + 1e-8)
                trades.append({**position, "exit_date":str(day.date()), "exit_price":price,
                               "raw_exit":raw_exit, "pnl_usd":quantity * (price-position["entry_price"]),
                               "return_pct":100*(price/position["entry_price"]-1),
                               "sessions_held":i-position["entry_i"]+1,
                               "reason":"gap_stop" if raw_open < stop else "stop"})
                events.append((str(day.date()), "sell", symbol, quantity, price))
                # Store the old peak that determined today's stop, before reading today's high.
                anchors[symbol] = dict(peak=position['peak'], exit_day=day)
                position = None
            else:
                position["peak"] = max(position["peak"], high)
        value = position["quantity"] * arrays[position["ticker"]][i,3] if position else 0.
        equity.append(cash+value)
        exposure.append(value/(cash+value))
        if position is None and pending is None:
            pending = candidate(day)
            pending_due = i + int(entry_delay_sessions) if pending else None
    curve = pd.Series(equity, index=dates, name="equity_usd")
    return dict(curve=curve, trades=trades, skipped=skipped, events=events,
                open_position=position, costs_usd=cost_total,
                mean_exposure_pct=100*float(np.mean(exposure)), collision_days=collisions,
                fill_violations=fill_violations, max_daily_volume_fraction=max_participation,
                entry_tags=entry_tags, reentry_enabled=True,
                reentry_anchors={symbol:dict(peak=value['peak'],exit_date=str(value['exit_day'].date()))
                                 for symbol,value in anchors.items()})


def _rounded_stop(peak, trail):
    from app.backend.money import cents, decimal
    return float(cents(decimal(peak)*(1-decimal(trail))))

