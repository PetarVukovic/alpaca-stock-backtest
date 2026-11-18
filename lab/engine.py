"""Long-only event-driven simulation; no broker interface or network calls."""

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from lab.contracts import BacktestResult
from lab.costs import effective_costs, fill_price
from lab.data import split_periods
from lab.metrics import summarize
from lab.strategies.registry import signals, validate_strategy


@dataclass
class Simulation:
    trades: list
    equity: pd.Series


def simulate(
    frame, entry, exit_signal, strategy, costs=None, assets=None, choices=None
):
    validate_strategy(strategy)
    costs = costs or effective_costs(strategy.costs, frame.attrs.get("ticker", "MU"))
    entry = entry.reindex(frame.index, fill_value=False)
    exit_signal = exit_signal.reindex(frame.index, fill_value=False)
    cash, position, trades, equity = 500.0, None, [], []
    rule = strategy.exit
    intraday = frame.attrs.get("timeframe", strategy.timeframe) != "daily"
    day_trade = strategy.entry["type"] in {"day_trade", "open_reversal"}
    trailing = rule.get("trailing_pct")
    pending_entry = pending_exit = False
    pending_date = None
    pending_symbol = None
    base_costs = costs
    for i, (ts, bar) in enumerate(frame.iterrows()):
        if assets is not None and position is not None:
            old_bar = assets[position["symbol"]].loc[ts]
            costs = effective_costs(strategy.costs, position["symbol"])
            bar = old_bar
            if pending_symbol != position["symbol"]:
                pending_exit = True
                pending_entry = pending_symbol is not None

        def liquidate(raw, reason, timestamp=ts):
            nonlocal cash, position
            sale_costs = (
                effective_costs(strategy.costs, position["symbol"])
                if assets is not None
                else base_costs
            )
            price = fill_price(float(raw), "sell", sale_costs)
            cash += position["quantity"] * price
            trades.append(
                {
                    "entry_time": position["entry_time"],
                    "exit_time": timestamp.isoformat(),
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "quantity": position["quantity"],
                    "notional_usd": position["notional"],
                    "net_return": price / position["entry_price"] - 1,
                    "reason": reason,
                    "ticker": position.get("symbol", frame.attrs.get("ticker")),
                }
            )
            position = None

        if day_trade and position is not None and position["entry_date"] != bar.date:
            liquidate(bar.open, "missing_session_close")
            pending_exit = False
        # Pending close-t signals are executed at open t+1.
        if position is not None and pending_exit:
            liquidate(bar.open, "rule")
        if (
            position is None
            and pending_entry
            and (not day_trade or pending_date == bar.date)
        ):
            if assets is not None:
                bar = assets[pending_symbol].loc[ts]
                costs = effective_costs(strategy.costs, pending_symbol)
            price = fill_price(float(bar.open), "buy", costs)
            notional = min(strategy.max_notional_usd, cash)
            # Optional volatility sizing uses prior bars only and can only reduce exposure.
            target_vol = strategy.entry.get("size_vol_target")
            if target_vol is not None:
                if target_vol <= 0:
                    raise ValueError("size_vol_target must be positive")
                sizing_frame = (
                    assets[pending_symbol].reindex(frame.index)
                    if assets is not None
                    else frame
                )
                realized = (
                    sizing_frame.close.iloc[max(0, i - 21) : i].pct_change().std()
                )
                if pd.notna(realized) and realized > 0:
                    notional *= min(1.0, target_vol / realized)
            if notional > 0:
                position = {
                    "entry_time": ts.isoformat(),
                    "entry_price": price,
                    "quantity": notional / price,
                    "notional": notional,
                    "entry_index": i,
                    "peak": float(bar.open),
                }
                position["entry_date"] = bar.date
                position["symbol"] = pending_symbol or frame.attrs.get("ticker")
                cash -= notional
        pending_entry = pending_exit = False
        if position is not None:
            anchor = position["entry_price"]
            stop = anchor * (1 - rule["stop_pct"]) if "stop_pct" in rule else None
            if trailing:
                trail = position["peak"] * (1 - trailing)
                stop = max(stop, trail) if stop is not None else trail
            target = anchor * (1 + rule["target_pct"]) if "target_pct" in rule else None
            # Gaps fill at open. If both levels touched, stop wins (conservative ambiguity).
            if stop is not None and bar.open <= stop:
                liquidate(bar.open, "stop_gap")
            elif target is not None and bar.open >= target:
                liquidate(bar.open, "target_gap")
            elif stop is not None and bar.low <= stop:
                liquidate(stop, "stop")
            elif target is not None and bar.high >= target:
                liquidate(target, "target")
            if position is not None:
                position["peak"] = max(position["peak"], float(bar.high))
                duration = i - position["entry_index"] + 1
                pending_exit = bool(exit_signal.iloc[i]) or duration >= rule.get(
                    "hold_bars", float("inf")
                )
                hour = ts.tz_convert("America/New_York").hour if intraday else None
                session_end = bool(bar.get("session_end", False)) or (
                    "session_end" not in frame.columns
                    and intraday
                    and frame.attrs.get("timeframe", strategy.timeframe) == "hourly"
                    and hour == 15
                )
                if day_trade and session_end:
                    liquidate(bar.close, "session_close")
                    pending_exit = False
        if assets is not None:
            pending_symbol = choices.iloc[i] if pd.notna(choices.iloc[i]) else None
            pending_entry = pending_symbol is not None and (
                position is None or pending_symbol != position["symbol"]
            )
        if assets is None and position is None and bool(entry.iloc[i]):
            pending_entry = True
            pending_date = bar.date
            if (
                day_trade
                and intraday
                and (
                    bool(bar.get("session_end", False))
                    or ts.tz_convert("America/New_York").hour >= 16
                )
            ):
                pending_entry = False
        # The period boundary closes inventory; it is reported as a forced research liquidation.
        if i == len(frame) - 1 and position is not None:
            liquidate(bar.close, "period_end")
        value = cash + (
            position["quantity"] * float(bar.close) if position is not None else 0
        )
        equity.append(value)
    return Simulation(trades, pd.Series(equity, index=frame.index, dtype=float))


def backtest(
    frame, strategy, ticker=None, context=None, events=None, k_at_run=46, run_at=None
):
    validate_strategy(strategy)
    ticker = ticker or frame.attrs.get("ticker", "MU")
    costs = effective_costs(strategy.costs, ticker)
    entries, exits = signals(frame, strategy, context, events)
    results, stats, flags = (
        {},
        {},
        ["research_only", "period_boundary_liquidation", "price_only_no_dividends"],
    )
    for period, sample in split_periods(frame).items():
        simulation = simulate(sample, entries, exits, strategy, costs)
        if strategy.entry["type"] == "day_trade":
            early_days = sample.loc[
                sample.get("early_close", pd.Series(False, index=sample.index)), "date"
            ].nunique()
            excluded = frame.attrs.get("excluded_after_close_by_date", {})
            removed = sum(
                n
                for d, n in excluded.items()
                if len(sample) and sample.date.min() <= d <= sample.date.max()
            )
            flags.extend(
                [
                    f"{period}:early_close_days={early_days}",
                    f"{period}:excluded_after_close_bars={removed}",
                ]
            )
        results[period] = simulation
        if any(t["reason"] == "missing_session_close" for t in simulation.trades):
            flags.append(f"{period}:missing_session_close")
        summary, warnings = summarize(
            simulation.trades, simulation.equity, sample.close
        )
        stats[period] = summary
        flags.extend(f"{period}:{w}" for w in warnings)
    means = [s.mean_pct for s in stats.values() if s.mean_pct is not None]
    if means and min(means) < 0 < max(means):
        flags.append("period_sign_change")
    if ticker in {"SNDK", "DRAM", "SKHY"}:
        flags.append("watch_only_short_history")
    if strategy.entry["type"] == "relative_strength":
        flags.append("ticker_sleeve_not_combined_rotation_portfolio")
    return BacktestResult(
        strategy_id=strategy.id,
        ticker=ticker,
        run_at=run_at or datetime.now(timezone.utc),
        costs=costs,
        k_at_run=k_at_run,
        periods=stats,
        flags=flags,
    ), results


def backtest_rotation(context, strategy, k_at_run=46):
    """One shared cash account and at most one selected ticker."""
    validate_strategy(strategy)
    if strategy.entry["type"] != "relative_strength":
        raise ValueError("Rotation requires relative_strength")
    frames = {s: context[s] for s in strategy.universe}
    shared = next(iter(frames.values())).index
    for frame in frames.values():
        shared = shared.intersection(frame.index)
    frames = {s: f.loc[shared].copy() for s, f in frames.items()}
    reference = next(iter(frames.values()))
    prices = pd.concat({s: f.close for s, f in frames.items()}, axis=1)
    momentum = prices.pct_change(strategy.entry.get("lookback", 63), fill_method=None)
    choices = momentum.fillna(-float("inf")).idxmax(axis=1)
    choices = choices.where(momentum.max(axis=1) > 0)
    stats, details, flags = (
        {},
        {},
        [
            "research_only",
            "single_position_rotation",
            "period_boundary_liquidation",
            "price_only_no_dividends",
        ],
    )
    for period, sample in split_periods(reference).items():
        entry = pd.Series(False, index=sample.index)
        exits = pd.Series(False, index=sample.index)
        sim = simulate(
            sample,
            entry,
            exits,
            strategy,
            assets=frames,
            choices=choices.reindex(sample.index),
        )
        summary, warnings = summarize(sim.trades, sim.equity, sample.close)
        if len(sample):
            from lab.metrics import sharpe

            period_prices = prices.loc[sample.index]
            benchmark = period_prices.div(period_prices.iloc[0]).mean(axis=1)
            summary.buy_hold_sharpe = sharpe(benchmark.pct_change())
        stats[period], details[period] = summary, sim
        flags.extend(f"{period}:{w}" for w in warnings)
    means = [s.mean_pct for s in stats.values() if s.mean_pct is not None]
    if means and min(means) < 0 < max(means):
        flags.append("period_sign_change")
    flags.append("benchmark_equal_basket_same_dates")
    return BacktestResult(
        strategy_id=strategy.id,
        ticker="ROTATION",
        run_at=datetime.now(timezone.utc),
        costs=strategy.costs,
        k_at_run=k_at_run,
        periods=stats,
        flags=flags,
    ), details
