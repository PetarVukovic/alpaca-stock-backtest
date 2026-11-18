"""Causal vectorized entry and exit rule registry. Signals are at bar close."""

import numpy as np
import pandas as pd

ENTRY_TYPES = {
    "ml_logit",
    "buy_hold",
    "equal_basket",
    "trend",
    "dip_in_trend",
    "breakout",
    "relative_strength",
    "leader",
    "earnings",
    "event",
    "volatility_breakout",
    "volatility_shock",
    "day_trade",
    "open_reversal",
}
EXIT_TYPES = {"hold", "risk", "trend", "trailing", "time", "rule"}
CLOSED_IDS = {"MEM_CYCLE_MR_V1", "MEM_RS_RECLAIM_V1", "HN2proxy", "H-N3"}
CLOSED_IDS |= {
    "IDX_REL_MOM_V1",
    "IDX_PULL_V1",
    "MEM_TREND_PB_V1",
    "MEM_ABS_DD_V1",
    "MULTI_DIP_TREND_V1",
    "MULTI_BRK_V1",
    "METAL_DIP_V1",
    "ENERGY_BRK_V1",
    "CRYPTO_DIP_V1",
    "LIT_TS_MOM_V1",
    "LIT_ST_REV_V1",
    "SWING_DONCHIAN_V1",
    "SWING_EMA_PB_V1",
    "MEM_DIP_BULL_V1",
    "MEM_BRK_SWING_V1",
    "MEM_REAL_DIP_V1",
    "MEM_AI_BOOM_REGIME_V1",
}
CLOSED_IDS |= {f"C{i}" for i in range(1, 13)} | {"C10b", "H1", "H2", "H3"}


def is_closed(strategy):
    prefix = strategy.id.split("_")[0]
    return (
        strategy.id in CLOSED_IDS
        or prefix in CLOSED_IDS
        or "RSI" in strategy.id.upper()
        or "RSI" in strategy.family.upper()
    )


def validate_strategy(strategy):
    if is_closed(strategy):
        raise ValueError("Closed strategy family")
    if (
        strategy.entry.get("type") not in ENTRY_TYPES
        or strategy.exit.get("type") not in EXIT_TYPES
    ):
        raise ValueError("Unknown entry/exit rule type")
    if not 0 < strategy.max_notional_usd <= 500 or strategy.max_positions != 1:
        raise ValueError("One long position and <=500 USD required")
    for key in ("lookback", "trend_window", "hold_bars", "vol_window"):
        value = (strategy.entry | strategy.exit).get(key)
        if value is not None and (not isinstance(value, int) or value < 1):
            raise ValueError(f"Invalid {key}")
    for key in ("stop_pct", "target_pct", "trailing_pct"):
        value = strategy.exit.get(key)
        if value is not None and not 0 < value < 1:
            raise ValueError(f"{key} must be a fraction in (0,1)")
    allowed_entry = {
        "type",
        "lookback",
        "trend_window",
        "dip_bars",
        "dip_pct",
        "leaders",
        "min_return",
        "event_type",
        "vol_window",
        "compression",
        "shock_multiplier",
        "mode",
        "gap_pct",
        "size_vol_target",
        "drop_pct",
    }
    allowed_exit = {
        "type",
        "trend_window",
        "stop_pct",
        "target_pct",
        "trailing_pct",
        "hold_bars",
    }
    if set(strategy.entry) - allowed_entry or set(strategy.exit) - allowed_exit:
        raise ValueError("Unknown rule parameter")
    if any(
        not isinstance(strategy.entry.get(key, 1), int)
        or strategy.entry.get(key, 1) < 1
        for key in ("dip_bars",)
    ):
        raise ValueError("Invalid dip_bars")
    if (
        strategy.entry.get("dip_pct", 0.05) <= 0
        or strategy.entry.get("dip_pct", 0.05) >= 1
    ):
        raise ValueError("dip_pct must be a fraction")
    if strategy.exit["type"] == "risk" and not any(
        k in strategy.exit for k in ("stop_pct", "target_pct", "hold_bars")
    ):
        raise ValueError("Empty risk exit")
    if strategy.exit["type"] == "trailing" and "trailing_pct" not in strategy.exit:
        raise ValueError("Missing trailing_pct")
    if strategy.exit["type"] == "time" and "hold_bars" not in strategy.exit:
        raise ValueError("Missing hold_bars")
    if strategy.entry["type"] == "equal_basket" and set(strategy.universe) != {
        "MU",
        "WDC",
        "STX",
    }:
        raise ValueError("Basket requires MU/WDC/STX")
    if strategy.entry["type"] == "ml_logit" and (
        strategy.timeframe != "daily"
        or set(strategy.universe) != {"MU", "WDC", "STX"}
        or strategy.entry != {"type": "ml_logit"}
    ):
        raise ValueError("ML baseline requires fixed daily MU/WDC/STX specification")
    return strategy


def aligned_context(frame, context, symbols):
    if not symbols or any(s not in context for s in symbols):
        raise ValueError("Missing context price series")
    # Close is available only at the same timeframe bar close, never later.
    return pd.concat(
        {s: context[s].close.reindex(frame.index, method="ffill") for s in symbols},
        axis=1,
    )


def signals(frame, strategy, context=None, events=None):
    validate_strategy(strategy)
    context = context or {}
    rule = strategy.entry
    kind = rule["type"]
    close = frame.close
    n = rule.get("lookback", 63)
    window = rule.get("trend_window", 200)
    average = close.rolling(window).mean()
    above = close > average
    result = pd.Series(False, index=frame.index)
    if kind == "ml_logit":
        from lab.strategies.ml_logit import predictions

        probability, metadata = predictions(frame)
        frame.attrs["ml_diagnostics"] = metadata
        result = probability > 0.55
    elif kind in {"buy_hold", "equal_basket"}:
        result[:] = True
    elif kind == "trend":
        result = above
    elif kind == "dip_in_trend":
        result = above & (
            close.pct_change(rule.get("dip_bars", 5)) <= -rule.get("dip_pct", 0.05)
        )
    elif kind == "breakout":
        result = close > frame.high.shift(1).rolling(n).max()
    elif kind == "relative_strength":
        peers = aligned_context(frame, context, strategy.universe)
        momentum = peers.pct_change(n, fill_method=None)
        winner = momentum.fillna(-np.inf).idxmax(axis=1)
        result = (winner == frame.attrs["ticker"]) & (momentum.max(axis=1) > 0)
    elif kind == "leader":
        leaders = aligned_context(
            frame, context, rule.get("leaders", ["AMAT", "LRCX", "KLAC"])
        )
        result = (
            leaders.pct_change(n, fill_method=None).mean(axis=1)
            > rule.get("min_return", 0)
        ) & above
    elif kind in {"event", "earnings"}:
        if events is None or kind == "event" and not rule.get("event_type"):
            raise ValueError("Event source and predeclared type required")
        selected = events.loc[
            events.type == ("earnings_MU" if kind == "earnings" else rule["event_type"])
        ]
        selected = selected[
            selected.tickers.str.split("|", regex=False).apply(
                lambda xs: frame.attrs["ticker"] in xs
            )
        ]
        selected = selected[selected.verified == "yes"]
        # Reaction-day close only. Announcement calendar is not proof of prior public scheduling.
        result = frame.date.isin(selected.us_reaction_date)
    elif kind.startswith("volatility"):
        vol = close.pct_change().rolling(rule.get("vol_window", 20)).std()
        historical = vol.shift(1).rolling(n).mean()
        if kind == "volatility_breakout":
            result = (vol.shift(1) < historical * rule.get("compression", 0.8)) & (
                close > frame.high.shift(1).rolling(n).max()
            )
        else:
            result = (
                (vol > historical * rule.get("shock_multiplier", 2))
                & (close.pct_change() < 0)
                & above
            )
    elif kind == "open_reversal":
        if strategy.timeframe != "5min":
            raise ValueError(
                "Opening 30 minutes require 5min bars, hourly open_mixed is unavailable"
            )
        if frame.attrs.get("ticker") not in {"WDC", "STX"}:
            raise ValueError("open_reversal restricted to WDC/STX")
        local = frame.index.tz_convert("America/New_York")
        minute = pd.Series(local.hour * 60 + local.minute, index=frame.index)
        first = frame.open.where(minute == 570).groupby(frame.date).first()
        opening_return = close / frame.date.map(first) - 1
        # 09:55 bar closes at 10:00. Six complete bars are mandatory.
        opening_count = ((minute >= 570) & (minute <= 595)).groupby(frame.date).cumsum()
        result = (
            (minute == 595)
            & (opening_count == 6)
            & (opening_return <= -rule.get("drop_pct", 0.005))
        )
    elif kind == "day_trade":
        if strategy.timeframe == "daily":
            raise ValueError("Day trade requires intraday data")
        hours = frame.index.tz_convert("America/New_York").hour
        mode = rule.get("mode", "first_hour")
        if mode not in {"first_hour", "last_hour", "gap"}:
            raise ValueError("Unknown day_trade mode")
        result = pd.Series(
            hours == (14 if mode == "last_hour" else 10), index=frame.index
        )
        if mode == "gap":
            previous = close.groupby(frame.date).last().shift(1)
            first_open = frame.open.groupby(frame.date).first()
            gap = first_open / previous - 1
            result &= frame.date.map(gap) >= rule.get("gap_pct", 0.01)
    exit_rule = strategy.exit
    exit_signal = pd.Series(False, index=frame.index)
    if exit_rule["type"] in {"trend", "rule"}:
        if kind == "relative_strength":
            exit_signal = ~result
        else:
            exit_signal = (
                close < close.rolling(exit_rule.get("trend_window", window)).mean()
            )
    return result.fillna(False).astype(bool), exit_signal.fillna(False).astype(bool)
