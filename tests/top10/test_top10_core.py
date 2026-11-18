import types

import numpy as np
import pandas as pd
import pytest

from lab.top10 import core


def _module(fn, universe=("GLD",), params=None):
    return types.SimpleNamespace(ID="TEST", UNIVERSE=list(universe), PARAMS=params or {"n": 50}, SPLIT_KIND="equity", weights=fn)


def honest(pan, params):
    close = pan["close"]
    return (close > close.rolling(params["n"]).mean()).astype(float)


def cheating(pan, params):
    close = pan["close"]
    return (close.shift(-1) > close).astype(float)  # peeks at tomorrow


def test_honest_strategy_passes_lookahead_and_runs():
    mod = _module(honest)
    summary, _ = core.evaluate(mod, k=500)
    assert summary["lookahead_ok"] is True
    assert summary["trades"]["n"] > 10
    assert summary["rating"] in {"ZELENO", "ŽUTO", "CRVENO"}


def test_cheating_strategy_is_caught():
    frames = core.load_frames(["GLD"])
    ok, cut = core.lookahead_check(_module(cheating), frames)
    assert ok is False and cut


def test_leverage_is_rejected():
    frames = core.load_frames(["GLD", "SLV"])
    pan = core.panel(frames)
    too_much = pd.DataFrame(1.0, index=pan["open"].index, columns=["GLD", "SLV"])
    with pytest.raises(ValueError):
        core.backtest(too_much, pan)


def test_costs_reduce_returns_and_fill_is_next_open():
    frames = core.load_frames(["GLD"])
    pan = core.panel(frames)
    always = pd.DataFrame(1.0, index=pan["open"].index, columns=["GLD"])
    cheap, dear = core.backtest(always, pan, 1.0), core.backtest(always, pan, 3.0)
    assert dear["net"].sum() < cheap["net"].sum()
    # decided at close t, earned from open t+1: first day can never earn anything
    assert cheap["gross"].iloc[0] == 0.0
    opens = pan["open"]["GLD"]
    expected = opens.iloc[2] / opens.iloc[1] - 1
    assert cheap["gross"].iloc[1] == pytest.approx(expected)


def test_cost_includes_rebalancing_back_to_target_after_drift():
    index = pd.date_range("2020-01-01", periods=5, freq="B")
    opens = pd.DataFrame({"A": [100.0, 100, 200, 200, 200], "B": [100.0, 100, 100, 100, 100]}, index=index)
    pan = {k: opens.copy() for k in ("open", "high", "low", "close")}
    pan["volume"] = opens * 0
    target = pd.DataFrame(0.5, index=index, columns=["A", "B"])
    bt = core.backtest(target, pan)
    # A doubles between open 1 and open 2: 50/50 drifts to 66.7/33.3, rebalancing must cost something
    assert bt["net"].iloc[2] < bt["gross"].iloc[2]


def test_max_drawdown_counts_the_start_capital_as_a_peak():
    r = pd.Series([-0.10] + [0.0] * 19, index=pd.date_range("2020-01-01", periods=20, freq="B"))
    assert core.metrics(r)["maxdd"] == pytest.approx(-0.10)


def test_trade_still_open_at_the_end_is_marked_open_without_exit_cost():
    index = pd.date_range("2020-01-01", periods=6, freq="B")
    opens = pd.DataFrame({"A": [100.0, 101, 102, 103, 104, 105]}, index=index)
    pan = {k: opens.copy() for k in ("open", "high", "low", "close")}
    pan["volume"] = opens * 0
    held = pd.DataFrame(1.0, index=index, columns=["A"])
    bt = core.backtest(held, pan)
    trade = core.trades_from(bt, pan)[0]
    assert trade["open"] is True and trade["exit"] == index[-1]


def test_calendar_only_has_days_where_every_stock_has_a_real_bar():
    index = pd.date_range("2024-01-01", periods=5, freq="B")
    a = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=index)
    b = a.drop(index[2])  # B has no bar on day 2
    pan = core.panel({"AAA": a, "BBB": b})
    assert index[2] not in pan["open"].index
    assert len(pan["open"]) == 4
