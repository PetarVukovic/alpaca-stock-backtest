import itertools
import json

import numpy as np
import pandas as pd
import pytest

from lab.contracts import Costs, FrozenStrategy
from lab.costs import effective_costs, fill_price
from lab.data import load_bars, split_periods
from lab.engine import backtest, simulate
from lab.ledger import current_k, log_trial
from lab.strategies.registry import ENTRY_TYPES, signals


def strategy(kind="buy_hold", **kwargs):
    return FrozenStrategy(
        id="TEST_NEW",
        created="2026-10-05",
        family="other",
        hypothesis="test",
        mechanism="test",
        persistence="test",
        universe=["MU"],
        entry={"type": kind, **kwargs},
        exit={"type": "hold"},
    )


def bars(n=300):
    index = pd.date_range("2019-01-01", periods=n, freq="B", tz="UTC")
    close = 100 + np.arange(n) * 0.1 + np.sin(np.arange(n))
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1000,
            "date": index.strftime("%Y-%m-%d"),
        },
        index=index,
    )
    frame.attrs.update(ticker="MU", timeframe="daily")
    return frame


def test_costs():
    assert fill_price(100, "buy", Costs()) == pytest.approx(100.035)
    assert fill_price(100, "sell", Costs()) == pytest.approx(99.965)
    assert effective_costs(Costs(), "MRAM").stress_multiplier == 2
    assert effective_costs(Costs(stress_multiplier=2), "MRAM").stress_multiplier == 4
    with pytest.raises(ValueError):
        effective_costs(Costs(round_trip_bps=0), "MU")


def test_next_open_and_cap():
    frame = bars(4)
    spec = strategy()
    result, details = backtest(frame, spec)
    trade = details["IS"].trades[0]
    assert trade["entry_time"] == frame.index[1].isoformat()
    assert trade["notional_usd"] <= 500
    assert result.periods["IS"].n == 1


@pytest.mark.parametrize(
    "kind",
    sorted(
        ENTRY_TYPES
        - {"equal_basket", "day_trade", "event", "earnings", "open_reversal", "ml_logit"}
    ),
)
def test_truncation(kind):
    frame = bars()
    contexts = {s: frame.copy() for s in ["MU", "AMAT", "LRCX", "KLAC"]}
    spec = strategy(kind, trend_window=20, lookback=10)
    full = signals(frame, spec, contexts)
    short = signals(
        frame.iloc[:180], spec, {s: f.iloc[:180] for s, f in contexts.items()}
    )
    for a, b in zip(full, short):
        pd.testing.assert_series_equal(a.iloc[:180], b)
    full_sim = simulate(frame, *full, spec)
    short_sim = simulate(frame.iloc[:180], *short, spec)
    pd.testing.assert_series_equal(
        full_sim.equity.iloc[:179], short_sim.equity.iloc[:179]
    )


def test_stop_wins_and_gap():
    frame = bars(4)
    spec = strategy()
    spec.exit = {"type": "risk", "stop_pct": 0.05, "target_pct": 0.05}
    frame.iloc[1, frame.columns.get_loc("low")] = 90
    frame.iloc[1, frame.columns.get_loc("high")] = 110
    sim = simulate(frame, *signals(frame, spec), spec)
    assert sim.trades[0]["reason"] == "stop"
    frame.iloc[1, frame.columns.get_loc("low")] = frame.low.iloc[0]
    frame.iloc[1, frame.columns.get_loc("high")] = frame.high.iloc[0]
    frame.iloc[2, frame.columns.get_loc("open")] = 80
    frame.iloc[2, frame.columns.get_loc("low")] = 79
    sim = simulate(frame, *signals(frame, spec), spec)
    assert sim.trades[0]["reason"] == "stop_gap"
    assert sim.trades[0]["exit_price"] < 80


def test_splits():
    frame = bars(3)
    frame["date"] = ["2020-12-31", "2021-01-01", "2024-01-01"]
    parts = split_periods(frame)
    assert [len(parts[p]) for p in ["IS", "WF", "HO"]] == [1, 1, 1]


def test_determinism():
    frame, spec = bars(), strategy("trend", trend_window=20)
    a, x = backtest(frame, spec, run_at=pd.Timestamp("2026-01-01", tz="UTC"))
    b, y = backtest(frame, spec, run_at=pd.Timestamp("2026-01-01", tz="UTC"))
    assert a == b
    assert x["IS"].trades == y["IS"].trades


def test_ledger(tmp_path):
    path = tmp_path / "trials.jsonl"
    assert current_k(path) == 0
    assert log_trial("X", "MU", "hash", path) == 1
    assert log_trial("X", "MU", "hash", path) == 2
    assert len([json.loads(s) for s in path.read_text().splitlines()]) == 2


def test_real_data():
    for symbol in ["MU", "WDC", "STX"]:
        for timeframe in ["daily", "hourly"]:
            frame = load_bars(symbol, timeframe)
            assert len(frame) > 100
            if timeframe == "hourly":
                assert (frame.session == "regular").all()
    # Double adjustment must be caught.
    from lab.data import check_wdc

    frame = load_bars("WDC")
    frame.loc[frame.date < "2025-02-24", "close"] *= 0.68132
    with pytest.raises(ValueError):
        check_wdc(frame)


@pytest.mark.parametrize("kind", ["event", "earnings"])
def test_events_are_reaction_date_only(kind):
    frame = bars(40)
    event = pd.DataFrame(
        {
            "type": ["earnings_MU"],
            "tickers": ["MU"],
            "verified": ["yes"],
            "us_reaction_date": [frame.date.iloc[20]],
            "future_return": [999],
        }
    )
    spec = strategy(kind, event_type="earnings_MU")
    a, _b = signals(frame, spec, events=event)
    assert a.sum() == 1 and a.iloc[20]
    x, _y = signals(frame.iloc[:25], spec, events=event)
    pd.testing.assert_series_equal(a.iloc[:25], x)
    changed = event.copy()
    changed["future_return"] = -999
    pd.testing.assert_series_equal(a, signals(frame, spec, events=changed)[0])


def test_intraday_session_and_truncation():
    from lab.contracts import FrozenStrategy

    index = pd.date_range("2021-01-04 15:00", periods=6, freq="h", tz="UTC")
    frame = bars(6)
    frame.index = index
    frame["date"] = "2021-01-04"
    frame.attrs.update(timeframe="hourly")
    spec = FrozenStrategy.model_validate(
        strategy("day_trade").model_dump() | {"timeframe": "hourly"}
    )
    a, b = signals(frame, spec)
    sim = simulate(frame, a, b, spec)
    assert sim.trades[0]["entry_time"] == index[1].isoformat()
    assert sim.trades[0]["reason"] == "session_close"
    assert sim.trades[0]["exit_time"] == index[-1].isoformat()
    short = frame.iloc[:4]
    x, y = signals(short, spec)
    pd.testing.assert_series_equal(a.iloc[:4], x)
    pd.testing.assert_series_equal(
        sim.equity.iloc[:3], simulate(short, x, y, spec).equity.iloc[:3]
    )


def test_closed_and_invalid_rules():
    from lab.strategies.registry import validate_strategy

    for name in ["C10_RSI_MR", "C10b_NEW", "MEM_CYCLE_MR_V1", "C11_NEW"]:
        spec = strategy()
        spec.id = name
        with pytest.raises(ValueError):
            validate_strategy(spec)
    spec = strategy()
    spec.max_notional_usd = 501
    with pytest.raises(ValueError):
        validate_strategy(spec)


def test_no_broker_calls():
    import ast
    from pathlib import Path

    for path in [Path("lab/engine.py"), Path("scripts/pull_alpaca.py")]:
        tree = ast.parse(path.read_text())
        forbidden = {
            "post",
            "put",
            "delete",
            "patch",
            "place",
            "submit_order",
            "cancel_all",
        }
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in forbidden
            for n in ast.walk(tree)
        )


def test_pull_clean_and_no_overwrite(tmp_path, monkeypatch):
    from scripts import pull_alpaca as pull

    rows = [
        {
            "t": "2025-02-21T15:00:00Z",
            "o": 70,
            "h": 72,
            "l": 69,
            "c": 71,
            "v": 100,
            "vw": 70,
            "n": 10,
        },
        {
            "t": "2025-02-24T15:00:00Z",
            "o": 49,
            "h": 51,
            "l": 48,
            "c": 50,
            "v": 100,
            "vw": 49,
            "n": 10,
        },
    ]
    calendar = {
        d: {"open": "09:30", "close": "16:00"} for d in ["2025-02-21", "2025-02-24"]
    }
    frame = pull.clean(rows, "WDC", "1Hour", calendar)
    assert (frame.session == "regular").all()
    assert frame.close.iloc[0] == pytest.approx(71 * 0.68132)
    assert frame.close.iloc[1] == 50
    assert frame.ts_zagreb.notna().all()
    path = tmp_path / "data/hourly/WDC_1h_clean.csv"
    path.parent.mkdir(parents=True)
    path.write_text("existing")
    monkeypatch.setattr(
        pull, "fetch_bars", lambda *a: pytest.fail("Existing file must skip GET")
    )
    assert (
        pull.pull("WDC", "1Hour", "2016-01-01", "2026-01-01", {}, calendar, tmp_path)
        == "existing"
    )
    assert path.read_text() == "existing"


def test_run_basket_and_reports(tmp_path):
    from lab.run_all import run_basket, write_report

    frame = bars()
    spec = strategy("equal_basket")
    spec.universe = ["MU", "WDC", "STX"]
    context = {s: frame.copy() for s in spec.universe}
    result, details = run_basket(spec, context, 47)
    assert result.ticker == "BASKET"
    assert details["IS"].trades[0]["notional_usd"] == pytest.approx(500)
    assert details["IS"].equity.iloc[-1] == pytest.approx(
        backtest(frame, strategy())[1]["IS"].equity.iloc[-1]
    )
    write_report(result, details, tmp_path)
    from lab.contracts import BacktestResult

    reread = BacktestResult.model_validate_json(
        (tmp_path / "TEST_NEW_BASKET.json").read_text()
    )
    assert reread == result
    assert "Critic PASS" in (tmp_path / "TEST_NEW_BASKET.md").read_text()


def test_rotation_single_position_and_truncation():
    from lab.engine import backtest_rotation

    spec = strategy("relative_strength", lookback=5)
    spec.universe = ["MU", "WDC", "STX"]
    base = bars(90)
    context = {s: base.copy() for s in spec.universe}
    for i, s in enumerate(spec.universe):
        for col in ["open", "high", "low", "close"]:
            context[s][col] *= np.exp(np.sin(np.arange(90) / 12 + i) * 0.15)
        context[s].attrs["ticker"] = s
    result, details = backtest_rotation(context, spec)
    trades = details["IS"].trades
    assert result.ticker == "ROTATION"
    assert len(trades) > 1
    assert all(t["notional_usd"] <= 500 for t in trades)
    assert all(a["exit_time"] <= b["entry_time"] for a, b in itertools.pairwise(trades))
    _, short = backtest_rotation({s: f.iloc[:50] for s, f in context.items()}, spec)
    pd.testing.assert_series_equal(
        details["IS"].equity.iloc[:49], short["IS"].equity.iloc[:49]
    )


def test_stress_costs_reduce_ending_equity():
    frame, spec = bars(60), strategy()
    _, a = backtest(frame, spec)
    spec.costs.stress_multiplier = 3
    _, b = backtest(frame, spec)
    assert b["IS"].equity.iloc[-1] < a["IS"].equity.iloc[-1]


def test_trailing_peak_only_applies_next_bar():
    frame = bars(4)
    spec = strategy()
    spec.exit = {"type": "trailing", "trailing_pct": 0.1}
    frame.iloc[1, frame.columns.get_loc("high")] = 200
    # Low=98 is above old trailing=90, below new trailing=180.
    sim = simulate(frame, *signals(frame, spec), spec)
    assert sim.trades[0]["exit_time"] == frame.index[2].isoformat()
    assert sim.trades[0]["reason"] == "stop_gap"


def test_invalid_data_rejected():
    from lab.data import validate_frame

    frame = bars(3)
    frame.iloc[0, frame.columns.get_loc("close")] = np.nan
    with pytest.raises(ValueError):
        validate_frame(frame)
    with pytest.raises(ValueError):
        validate_frame(bars(3).iloc[::-1])


def test_ledger_concurrent_writers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "trials.jsonl"
    with ThreadPoolExecutor(max_workers=4) as pool:
        numbers = list(
            pool.map(lambda i: log_trial("X", "MU", str(i), path), range(10))
        )
    assert sorted(numbers) == list(range(1, 11))
    assert current_k(path) == 10


def test_run_all_data_gate_stops_before_trial(tmp_path, monkeypatch):
    import subprocess

    from lab import run_all

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(run_all.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        run_all.run_all(tmp_path)
    assert not (tmp_path / "reports/ledger/trials.jsonl").exists()


def test_open_reversal_enters_exactly_1000_and_flattens():
    frame = bars(12)
    frame.index = pd.date_range("2021-01-04 14:30", periods=12, freq="5min", tz="UTC")
    frame["date"] = "2021-01-04"
    for column in ["open", "high", "low", "close"]:
        frame[column] = frame[column].astype(float)
    frame["open"] = 100.0
    frame["high"] = 101.0
    frame["low"] = 98.0
    frame["close"] = 99.0
    frame["session_end"] = False
    frame.iloc[-1, frame.columns.get_loc("session_end")] = True
    frame.attrs.update(ticker="WDC", timeframe="5min")
    spec = strategy("open_reversal", drop_pct=0.005)
    spec.timeframe = "5min"
    spec.universe = ["WDC"]
    spec.exit = {"type": "risk", "stop_pct": 0.05}
    entry, exit_signal = signals(frame, spec)
    assert entry.sum() == 1 and entry.iloc[5]
    sim = simulate(frame, entry, exit_signal, spec)
    assert sim.trades[0]["entry_time"] == frame.index[6].isoformat()
    assert sim.trades[0]["reason"] == "session_close"
    short = frame.iloc[:9]
    a, b = signals(short, spec)
    pd.testing.assert_series_equal(entry.iloc[:9], a)
    pd.testing.assert_series_equal(
        sim.equity.iloc[:8], simulate(short, a, b, spec).equity.iloc[:8]
    )
    spec.timeframe = "hourly"
    with pytest.raises(ValueError):
        signals(frame, spec)


def test_one_trial_per_frozen_id(tmp_path):
    from lab.ledger import register_strategy

    path = tmp_path / "trials.jsonl"
    assert register_strategy("NEW", "hash", path) == 1
    assert register_strategy("NEW", "hash", path) == 1
    assert current_k(path) == 1
    with pytest.raises(ValueError):
        register_strategy("NEW", "different", path)


def test_intraday_drawdown_uses_all_bars():
    from lab.metrics import summarize

    index = pd.date_range("2021-01-04 15:00", periods=3, freq="h", tz="UTC")
    equity = pd.Series([500.0, 400.0, 500.0], index=index)
    stats, _ = summarize([], equity, pd.Series([100.0, 80.0, 100.0], index=index))
    assert stats.max_dd_pct == pytest.approx(-20)


def test_selected_frozen_ids_exclude_previous_campaign(tmp_path):
    from lab.run_all import select_frozen_files
    for sid in ["B1_BUY_HOLD","H5A_OPEN_REVERSAL_05","H5B_OPEN_REVERSAL_10"]:
        (tmp_path/f"2026-10-05_{sid}.json").write_text("{}")
    selected = select_frozen_files(tmp_path,["H5A_OPEN_REVERSAL_05","H5B_OPEN_REVERSAL_10"])
    assert [p.name for p in selected] == [
        "2026-10-05_H5A_OPEN_REVERSAL_05.json","2026-10-05_H5B_OPEN_REVERSAL_10.json"]
    assert len(select_frozen_files(tmp_path)) == 3
    with pytest.raises(ValueError):
        select_frozen_files(tmp_path,["MISSING"])
    with pytest.raises(ValueError):
        select_frozen_files(tmp_path,[])
