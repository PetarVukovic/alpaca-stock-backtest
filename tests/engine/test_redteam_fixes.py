import pandas as pd
import pytest

from lab.contracts import BacktestResult, FrozenStrategy
from lab.data import ROOT, load_bars
from lab.engine import backtest, backtest_rotation
from lab.metrics import sharpe
from lab.run_all import explanation


def test_half_day_hourly_excludes_after_close_and_flattens():
    frame = load_bars("MU", "hourly")
    day = frame[frame.date == "2019-11-29"].copy()
    assert day.index.tz_convert("America/New_York").hour.max() == 12
    assert day.iloc[-1].session_end
    assert day.early_close.all()
    assert frame.attrs["excluded_after_close_by_date"]["2019-11-29"] > 0
    spec = (
        FrozenStrategy.model_validate_json(
            (ROOT / "strategies/frozen/2026-10-05_H4A_GAP.json").read_text()
        )
        if (ROOT / "strategies/frozen/2026-10-05_H4A_GAP.json").exists()
        else FrozenStrategy.model_validate_json(
            next((ROOT / "strategies/frozen").glob("*_H4A_*.json")).read_text()
        )
    )
    spec.entry = {"type": "day_trade", "mode": "first_hour"}
    spec.exit = {"type": "hold"}
    result, details = backtest(day, spec, "MU")
    trade = details["IS"].trades[0]
    assert trade["reason"] == "session_close"
    assert pd.Timestamp(trade["exit_time"]).tz_convert("America/New_York").hour == 12
    assert "IS:early_close_days=1" in result.flags


def test_rotation_benchmark_uses_equal_basket_shared_dates():
    spec = FrozenStrategy.model_validate_json(
        next((ROOT / "strategies/frozen").glob("*_C16A_*.json")).read_text()
    )
    context = {s: load_bars(s) for s in spec.universe}
    result, _ = backtest_rotation(context, spec)
    prices = (
        pd.concat({s: f.set_index("date").close for s, f in context.items()}, axis=1)
        .dropna()
        .loc["2021-01-01":"2023-12-31"]
    )
    benchmark = prices.div(prices.iloc[0]).mean(axis=1)
    assert result.periods["WF"].buy_hold_sharpe == pytest.approx(
        sharpe(benchmark.pct_change())
    )
    assert "benchmark_first_universe_ticker" not in result.flags


def test_benchmark_label_is_not_candidate():
    folder = ROOT / "reports/backtest"
    baseline = BacktestResult.model_validate_json(
        (folder / "B2_TREND200_WDC.json").read_text()
    )
    assert explanation(baseline).startswith("MJERILO")
