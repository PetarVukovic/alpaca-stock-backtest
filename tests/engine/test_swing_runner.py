"""Research runner regressions; synthetic files only, no canonical report writes."""
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from lab.contracts import FrozenStrategy
from lab.data import load_bars
from lab.critic.checks import CriticConfig, check_13_holdout
from lab import run_all as runner


def spec():
    return FrozenStrategy.model_validate({
        "id": "C13C_TEST", "created": "2026-10-06", "family": "pullback",
        "universe": ["MU"], "timeframe": "daily",
        "hypothesis": "Synthetic test", "mechanism": "Synthetic test", "persistence": "Synthetic test",
        "entry": {"type": "dip_in_trend", "trend_window": 200, "dip_bars": 5, "dip_pct": .05},
        "exit": {"type": "trailing", "trailing_pct": .1},
        "max_notional_usd": 500, "max_positions": 1,
        "costs": {"round_trip_bps": 5, "tick_per_side": 1, "stress_multiplier": 1},
    })


def test_sensitivity_varies_exactly_one_parameter_and_preserves_freeze():
    original = spec()
    before = original.model_dump_json()
    variants = runner.sensitivity_variants(original)
    assert len(variants) == 8
    for label, (candidate, change) in variants.items():
        differences = [(group, key) for group in ("entry", "exit")
                       for key, value in getattr(original, group).items()
                       if getattr(candidate, group)[key] != value]
        assert len(differences) == 1
        group, key = differences[0]
        assert label.startswith(f"{group}.{key}.")
        assert list(change) == [f"{group}.{key}"]
        assert candidate.costs == original.costs
    assert original.model_dump_json() == before
    assert variants["entry.trend_window.minus20"][0].entry["trend_window"] == 160
    assert variants["entry.trend_window.plus20"][0].entry["trend_window"] == 240


def test_cutoff_excludes_bad_future_daily_prices_before_validation(tmp_path):
    path = tmp_path / "data/ohlcv/MU_1d.csv"
    path.parent.mkdir(parents=True)
    path.write_text("date,open,high,low,close,volume\n2023-12-29,100,101,99,100,10000\n2024-01-02,-1,2,-3,-1,10000\n")
    frame = load_bars("MU", root=tmp_path, through=date(2023, 12, 29))
    assert frame.date.tolist() == ["2023-12-29"]
    assert frame.attrs["through"] == "2023-12-29"
    with pytest.raises(ValueError, match="Invalid prices"):
        load_bars("MU", root=tmp_path)


def test_hourly_cutoff_precedes_future_session_calendar_requirements(tmp_path):
    hourly = tmp_path / "data/hourly/MU_1h_clean.csv"
    calendar = tmp_path / "data/intraday/MU_5m_clean.csv"
    hourly.parent.mkdir(parents=True)
    calendar.parent.mkdir(parents=True)
    hourly.write_text("ts,open,high,low,close,volume,volume_ok,session\n2023-12-29T20:00:00Z,100,101,99,100,10000,true,regular\n2024-01-02T20:00:00Z,100,101,99,100,10000,true,regular\n")
    calendar.write_text("ts,session_end\n2023-12-29T20:55:00Z,true\n")
    frame = load_bars("MU", "hourly", root=tmp_path, through="2023-12-29")
    assert frame.date.tolist() == ["2023-12-29"]
    assert bool(frame.iloc[0].session_end)
    with pytest.raises(ValueError, match="Missing official session end"):
        load_bars("MU", "hourly", root=tmp_path)


def test_runner_diagnostics_receive_only_pre_holdout_and_record_cutoff(tmp_path, monkeypatch):
    # Never invokes the real validator or writes to the repository.
    frozen = tmp_path / "strategies/frozen/2026-10-06_C13C_TEST.json"
    frozen.parent.mkdir(parents=True)
    frozen.write_text(spec().model_dump_json())
    news = tmp_path / "data/news/events_calendar.csv"
    news.parent.mkdir(parents=True)
    news.write_text("us_reaction_date,event_type,ticker\n")
    prices = tmp_path / "data/ohlcv/MU_1d.csv"
    prices.parent.mkdir(parents=True)
    dates = pd.bdate_range("2022-01-03", "2024-02-01")
    close = 100 + np.arange(len(dates)) * .1 + np.sin(np.arange(len(dates)) / 7) * 8
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "open": close, "high": close+1,
                  "low": close-1, "close": close, "volume": 100000}).to_csv(prices, index=False)
    validations = []
    monkeypatch.setattr(runner.subprocess, "run", lambda args, **kw: validations.append(args))
    evaluated = []
    actual_evaluate = runner.evaluate
    def evaluate(strategy, context, events, k):
        evaluated.append((strategy.costs.stress_multiplier, max(f.date.max() for f in context.values())))
        return actual_evaluate(strategy, context, events, k)
    monkeypatch.setattr(runner, "evaluate", evaluate)
    causal_dates = []
    def causality(strategy, context, events, k):
        causal_dates.extend(f.date.max() for f in context.values())
        return {"truncation_ok": True, "corrupt_future_ok": True, "terminal_bar_excluded": True}
    monkeypatch.setattr(runner, "causality_evidence", causality)
    _, skipped = runner.run_all(tmp_path, strategy_ids=["C13C_TEST"], through="2024-01-15")
    assert not skipped
    assert validations[0][-2:] == ["--through", "2024-01-15"]
    assert evaluated[0][1] == "2024-01-15"
    assert len(evaluated) == 10  # base, 2x costs, eight one-parameter diagnostics
    assert all(last < "2024-01-01" for _, last in evaluated[1:])
    assert all(last < "2024-01-01" for last in causal_dates)
    pkg = json.loads((tmp_path / "reports/backtest/C13C_TEST_critic_inputs.json").read_text())
    assert pkg["data_through"] == pkg["provenance"]["data_through"] == "2024-01-15"
    assert pkg["diagnostic_holdout_excluded"] is True
    assert pkg["no_fitted_parameters"] is None
    assert pkg["holdout_fill_violations"] == 0
    assert len(pkg["sensitivity"]) == 8
    assert all(not periods["HO"] for periods in pkg["stressed_returns"].values())
    assert all(t < "2024-01-01" for t in pkg["trials_matrix_metadata"]["timestamps"])


def test_holdout_execution_evidence_is_required_at_final_holdout_check():
    returns = {"MU": {"WF": np.arange(1, 16), "HO": np.arange(1, 16)}}
    assert check_13_holdout(returns, CriticConfig(), 0).passed
    assert not check_13_holdout(returns, CriticConfig(), 1).passed
    assert not check_13_holdout(returns, CriticConfig(), None).passed
