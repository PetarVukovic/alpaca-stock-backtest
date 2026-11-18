"""Critic tests on synthetic data: noise fails, a consistent edge passes, each gate bites."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from lab.contracts import Verdict
from lab.critic import (
    CriticConfig,
    CriticInputs,
    SensitivityResult,
    render_verdict_md,
    run_critic,
    stats,
    update_approved_list,
)

TICKERS = ["MU", "WDC", "STX"]
GOOD_AUDIT = {
    "rule_types": {
        "dip_in_trend": {"reproduced": True, "max_abs_diff_pct": 0.0, "n_trades_match": True, "notes": ""},
        "risk": {"reproduced": True, "max_abs_diff_pct": 0.0, "n_trades_match": True, "notes": ""},
    },
    "engine_findings": [{"severity": "high", "open": False, "text": "closed"}],
}
N_PER = {"IS": 25, "WF": 20, "HO": 15}


def make_returns(mean: float, sd: float = 3.0, seed: int = 0, n=None) -> dict:
    rng = np.random.default_rng(seed)
    n = n or N_PER
    return {t: {p: rng.normal(mean, sd, n[p]) for p in n} for t in TICKERS}


def make_trials(edge: float, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    means = np.array([edge, edge * 0.3, edge * 0.1, 0.0])
    return rng.normal(means, 3.0, size=(240, 4))


def make_trials_metadata():
    return {
        "columns": ["A", "B", "C", "D"],
        "timestamps": [(date(2021, 1, 1) + timedelta(days=i)).isoformat() for i in range(240)],
        "units": "daily_return_fraction", "periods": ["IS", "WF"], "holdout_excluded": True,
    }


def make_inputs(returns: dict, k: int = 46, edge: float = 0.0) -> CriticInputs:
    return CriticInputs(
        returns=returns, k=k,
        data_check_exit_code=0, wdc_spinoff_adjusted_once=True,
        lookahead_truncation_ok=True, lookahead_corrupt_future_ok=True,
        freeze_matches=True, no_fitted_parameters=True, period_boundary_liquidation=True,
        sensitivity={"rsi_in": SensitivityResult(1.2, False)},
        ledger_complete=True, trials_matrix=make_trials(edge),
        trials_matrix_metadata=make_trials_metadata(),
        fill_violations=0, holdout_fill_violations=0, rule_types=["dip_in_trend", "risk"], lookahead_evidence_ok=True,
        audit=GOOD_AUDIT,
    )


def failed_numbers(v) -> set[int]:
    return {c.number for c in v.checks if not c.passed}


def test_noise_strategy_with_k46_fails():
    v = run_critic("NOISE", make_inputs(make_returns(0.0, seed=3)), today=date(2026, 10, 6))
    assert v.verdict == Verdict.FAIL
    assert v.reasons


def test_consistent_edge_passes():
    v = run_critic("EDGE", make_inputs(make_returns(2.5, seed=5), edge=2.5))
    assert v.verdict == Verdict.PASS, v.reasons
    assert len(v.checks) == 15
    assert [c.number for c in v.checks] == list(range(15))


def test_small_n_fails():
    r = make_returns(2.5, seed=5, n={"IS": 3, "WF": 3, "HO": 3})
    v = run_critic("TINY", make_inputs(r, edge=2.5))
    assert 4 in failed_numbers(v)
    assert v.verdict == Verdict.FAIL


def test_sign_flip_is_to_wf_fails():
    r = make_returns(2.5, seed=5)
    rng = np.random.default_rng(9)
    for t in TICKERS:
        r[t]["WF"] = rng.normal(-2.0, 3.0, N_PER["WF"])
    v = run_critic("FLIP", make_inputs(r, edge=2.5))
    assert 3 in failed_numbers(v)
    assert v.verdict == Verdict.FAIL


def test_double_cost_kills_edge():
    r = make_returns(0.0, sd=0.5, seed=2)
    for t in TICKERS:
        for p in r[t]:
            r[t][p] = r[t][p] + 0.04  # thinner than the extra 0.05% round-trip cost
    v = run_critic("THIN", make_inputs(r, edge=1.0))
    assert 7 in failed_numbers(v)
    assert v.verdict == Verdict.FAIL


def test_single_ticker_edge_fails_concentration():
    r = make_returns(2.5, seed=5)
    rng = np.random.default_rng(11)
    for t in ("WDC", "STX"):
        for p in r[t]:
            r[t][p] = rng.normal(-1.0, 3.0, N_PER[p])
    v = run_critic("MU_ONLY", make_inputs(r, edge=2.5))
    assert 8 in failed_numbers(v)


def test_missing_evidence_fails_closed():
    inp = replace(make_inputs(make_returns(2.5, seed=5), edge=2.5), lookahead_truncation_ok=None,
                  fill_violations=None, trials_matrix=None)
    v = run_critic("GAPS", inp)
    assert {1, 10, 12} <= failed_numbers(v)
    assert 14 in failed_numbers(v)


def test_pbo_not_required_is_configurable():
    inp = replace(make_inputs(make_returns(2.5, seed=5), edge=2.5), trials_matrix=None)
    v = run_critic("NOPBO", inp, CriticConfig(pbo_required=False))
    assert v.verdict == Verdict.PASS, v.reasons


def test_dsr_monotone_in_k():
    r = np.random.default_rng(4).normal(1.0, 3.0, 120)
    ps = [stats.deflated_sharpe(r, k).p_value for k in (1, 5, 20, 46, 200)]
    assert ps == sorted(ps)
    assert ps[-1] > ps[0]


def test_pbo_noise_vs_real_and_not_computable():
    rng = np.random.default_rng(0)
    noise_pbo = np.mean([stats.pbo_cscv(rng.normal(0, 1, (240, 10))).pbo for _ in range(30)])  # single draws are noisy
    real = stats.pbo_cscv(make_trials(2.5))
    assert real.computable
    assert real.pbo < 0.1 and 0.3 < noise_pbo < 0.7
    assert not stats.pbo_cscv(None).computable
    assert not stats.pbo_cscv(rng.normal(0, 1, (240, 1))).computable


def test_monte_carlo_deterministic_and_percentiles():
    r = np.random.default_rng(1).normal(0.5, 3.0, 60)
    a = stats.monte_carlo_drawdown(r, seed=7)
    b = stats.monte_carlo_drawdown(r, seed=7)
    c = stats.monte_carlo_drawdown(r, seed=8)
    assert a == b and a != c
    assert a.n_sims >= 2000
    assert list(a.simple_dd_pct) == [5, 25, 50, 75, 95]
    assert a.simple_dd_pct[5] <= a.simple_dd_pct[50] <= a.simple_dd_pct[95]


def test_top3_concentration():
    ex, share = stats.top_n_concentration(np.array([10.0, 9.0, 8.0, 0.1, -0.1, 0.0]), 3)
    assert ex == pytest.approx(0.0)
    assert share == pytest.approx(27.0 / 27.0)
    assert stats.top_n_concentration(np.array([1.0, 2.0]), 3) == (None, None)


def test_run_is_deterministic():
    inp = make_inputs(make_returns(2.5, seed=5), edge=2.5)
    a = run_critic("D", inp, today=date(2026, 10, 6))
    b = run_critic("D", inp, today=date(2026, 10, 6))
    assert a == b


def test_render_md_has_template_sections():
    v = run_critic("NOISE", make_inputs(make_returns(0.0, seed=3)), today=date(2026, 10, 6))
    md = render_verdict_md(v, name="TEST")
    assert md.startswith("# NOISE TEST — Critic VERDICT")
    assert "**FAIL** (fail closed). Eligible for approved_list: ne." in md
    assert "Campaign K: 46" in md
    assert "## Ordered checks" in md and "14. Završni audit" in md
    assert "## Verdict" in md and "Laički:" in md


def test_approved_list_only_adds_pass(tmp_path):
    good = run_critic("EDGE", make_inputs(make_returns(2.5, seed=5), edge=2.5), today=date(2026, 10, 6))
    bad = run_critic("NOISE", make_inputs(make_returns(0.0, seed=3)), today=date(2026, 10, 6))
    assert update_approved_list(bad, tmp_path, "x_VERDICT.md") is False
    assert not (tmp_path / "approved_list.json").exists()
    assert update_approved_list(good, tmp_path, "2026-10-06_EDGE_VERDICT.md") is True
    assert update_approved_list(good, tmp_path, "2026-10-06_EDGE_VERDICT.md") is False  # no duplicate
    data = json.loads((tmp_path / "approved_list.json").read_text())
    assert [s["strategy_id"] for s in data["strategies"]] == ["EDGE"]
    forged = good.model_copy(update={"checks": [c.model_copy(update={"passed": False}) if c.number == 3 else c for c in good.checks]})
    with pytest.raises(ValueError):
        update_approved_list(forged, tmp_path, "f_VERDICT.md")
