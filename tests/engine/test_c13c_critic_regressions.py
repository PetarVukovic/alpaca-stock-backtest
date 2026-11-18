"""Holdout/provenance regressions; synthetic fixtures and temporary reports only."""
from copy import deepcopy
from dataclasses import replace
import json

import numpy as np
import pytest

from lab.critic import checks as c
from lab.critic import runner
from lab.critic.verdict import run_critic
from tests.critic.test_critic import make_inputs, make_returns, make_trials, make_trials_metadata
from tests.critic.test_runner import write_package


def test_holdout_cannot_change_any_pre_holdout_check():
    returns = make_returns(2.5, seed=5)
    first = run_critic("AUDIT", make_inputs(returns, edge=2.5))
    changed = deepcopy(returns)
    for periods in changed.values():
        periods["HO"] = np.array([-99.0])
    second = run_critic("AUDIT", make_inputs(changed, edge=2.5))
    assert first.checks[:13] == second.checks[:13]
    assert first.checks[13].passed
    assert not second.checks[13].passed
    assert "n=135" in first.checks[10].detail


def test_pre_holdout_checks_do_not_even_convert_holdout_returns():
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError("holdout accessed early")
    returns = make_returns(2.5, seed=5)
    for periods in returns.values():
        periods["HO"] = Forbidden()
    cfg = c.CriticConfig()
    c.check_3_same_sign(returns)
    c.check_4_min_sample(returns, cfg)
    c.check_7_cost_stress(returns, c.Costs(), cfg)
    c.check_8_regime_concentration(returns, cfg)
    c.check_10_dsr_pbo(returns, 46, make_trials(2.5), cfg, make_trials_metadata())
    c.check_11_monte_carlo(returns, cfg)


@pytest.mark.parametrize("defect", ["missing", "holdout", "date", "duplicate", "unsorted", "shape", "columns", "nan", "units"])
def test_pbo_rejects_unverified_or_leaking_matrix(defect):
    matrix = make_trials(2.5)
    metadata = make_trials_metadata()
    if defect == "missing": metadata = None
    elif defect == "holdout": metadata["holdout_excluded"] = False
    elif defect == "date": metadata["timestamps"][-1] = "2024-01-01"
    elif defect == "duplicate": metadata["timestamps"][-1] = metadata["timestamps"][-2]
    elif defect == "unsorted": metadata["timestamps"] = metadata["timestamps"][::-1]
    elif defect == "shape": metadata["timestamps"].pop()
    elif defect == "columns": metadata["columns"][-1] = metadata["columns"][0]
    elif defect == "nan": matrix[0, 0] = np.nan
    elif defect == "units": metadata["units"] = "trade_return_percent"
    assert c.validate_trials_matrix(matrix, metadata) is not None
    result = c.check_10_dsr_pbo(make_returns(2.5, seed=5), 46, matrix, c.CriticConfig(), metadata)
    assert not result.passed
    assert "PBO nije izračunljiv" in result.detail


def test_valid_pbo_dates_and_shape_are_accepted():
    assert c.validate_trials_matrix(make_trials(2.5), make_trials_metadata()) is None


@pytest.mark.parametrize("evidence", [None, False])
def test_frozen_file_does_not_prove_theory_only_parameters(tmp_path, evidence):
    sid = "C99A_TEST"
    write_package(tmp_path, sid, 2.5)
    path = tmp_path / f"reports/backtest/{sid}_critic_inputs.json"
    pkg = json.loads(path.read_text())
    if evidence is None:
        pkg.pop("no_fitted_parameters")
    else:
        pkg["no_fitted_parameters"] = evidence
    path.write_text(json.dumps(pkg))
    inputs, _ = runner.build_inputs(tmp_path, sid, None)
    assert inputs.no_fitted_parameters is evidence
    assert not c.check_5_purge_embargo(inputs.no_fitted_parameters, True).passed


def test_legacy_package_missing_pbo_metadata_fails_closed(tmp_path):
    sid = "C99A_TEST"
    write_package(tmp_path, sid, 2.5)
    path = tmp_path / f"reports/backtest/{sid}_critic_inputs.json"
    pkg = json.loads(path.read_text())
    pkg.pop("trials_matrix_metadata")
    path.write_text(json.dumps(pkg))
    inputs, _ = runner.build_inputs(tmp_path, sid, None)
    verdict = run_critic(sid, inputs)
    assert not verdict.checks[10].passed


def test_optional_pbo_does_not_accept_a_contaminated_supplied_matrix():
    inputs = make_inputs(make_returns(2.5, seed=5), edge=2.5)
    metadata = make_trials_metadata()
    metadata["timestamps"][-1] = "2025-01-01"
    inputs = replace(inputs, trials_matrix_metadata=metadata)
    verdict = run_critic("AUDIT", inputs, c.CriticConfig(pbo_required=False))
    assert not verdict.checks[10].passed
