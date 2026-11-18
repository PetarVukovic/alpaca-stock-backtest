"""Runner and audit/embargo gates on temp dirs; the real reports/gate is never touched."""
from __future__ import annotations

import hashlib
import json
from datetime import date

import numpy as np

from lab.contracts import Verdict
from lab.critic import checks as c
from lab.critic import runner
from tests.critic.test_critic import GOOD_AUDIT, make_returns, make_trials, make_trials_metadata

TODAY = date(2026, 10, 6)


def write_package(root, sid: str, edge: float, boundary: bool = True) -> None:
    (root / "reports/backtest").mkdir(parents=True, exist_ok=True)
    (root / "reports/ledger").mkdir(parents=True, exist_ok=True)
    (root / "strategies/frozen").mkdir(parents=True, exist_ok=True)
    (root / "reports/ledger/trials.jsonl").write_text(json.dumps({"k": 46, "strategy_id": "x"}) + "\n")
    freeze = root / f"strategies/frozen/2026-10-05_{sid}.json"
    freeze.write_text(json.dumps({"id": sid, "family": "trend", "entry": {"type": "dip_in_trend"},
                                  "exit": {"type": "risk"}}))
    ret = {t: {p: v.tolist() for p, v in per.items()} for t, per in make_returns(edge, seed=5).items()}
    pkg = {
        "returns": ret, "portfolio_returns": {}, "stressed_returns": ret,
        "costs": {"round_trip_bps": 5.0, "tick_per_side": 1.0, "stress_multiplier": 1.0},
        "k": 46, "data_check_exit_code": 0, "wdc_spinoff_adjusted_once": True, "freeze_matches": True,
        "lookahead_truncation_ok": True, "lookahead_corrupt_future_ok": True,
        "lookahead_evidence": {"truncation_ok": True, "corrupt_future_ok": True, "terminal_bar_excluded": True},
        "sensitivity": {"minus20": {"wf_mean_pct": 1.0, "edge_crushed": False}},
        "ledger_complete": True, "fill_violations": 0, "holdout_fill_violations": 0,
        "provenance": {"freeze_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest()},
        "trials_matrix": make_trials(edge).tolist(),
        "trials_matrix_metadata": make_trials_metadata(),
        "no_fitted_parameters": True,
    }
    (root / f"reports/backtest/{sid}_critic_inputs.json").write_text(json.dumps(pkg))
    flags = ["period_boundary_liquidation"] if boundary else []
    (root / f"reports/backtest/{sid}_MU.json").write_text(
        json.dumps({"strategy_id": sid, "ticker": "MU", "flags": flags}))


def test_runner_pass_writes_verdict_and_approved(tmp_path):
    write_package(tmp_path, "C99A_TEST", 2.5)
    v, fname = runner.process(tmp_path, "C99A_TEST", GOOD_AUDIT, TODAY)
    assert v.verdict == Verdict.PASS, v.reasons
    assert (tmp_path / "reports/gate" / fname).read_text().startswith("# C99A_TEST trend")
    approved = json.loads((tmp_path / "reports/gate/approved_list.json").read_text())
    assert [s["strategy_id"] for s in approved["strategies"]] == ["C99A_TEST"]


def test_missing_audit_fails_closed(tmp_path):
    write_package(tmp_path, "C99A_TEST", 2.5)
    v, _ = runner.process(tmp_path, "C99A_TEST", None, TODAY)
    assert v.verdict == Verdict.FAIL
    assert "audit nije dostavljen" in v.checks[14].detail
    assert not (tmp_path / "reports/gate/approved_list.json").exists()


def test_no_boundary_flag_fails_check5(tmp_path):
    write_package(tmp_path, "C99A_TEST", 2.5, boundary=False)
    v, _ = runner.process(tmp_path, "C99A_TEST", GOOD_AUDIT, TODAY)
    assert not v.checks[5].passed


def test_benchmark_never_approved(tmp_path):
    write_package(tmp_path, "B9_TEST", 2.5)
    v, fname = runner.process(tmp_path, "B9_TEST", GOOD_AUDIT, TODAY)
    assert "MJERILO" in (tmp_path / "reports/gate" / fname).read_text()
    assert not (tmp_path / "reports/gate/approved_list.json").exists()
    assert v.verdict == Verdict.PASS  # gate numbers still shown, but never eligible


def test_cli_all_rerunnable(tmp_path, capsys):
    write_package(tmp_path, "C99A_TEST", 0.0)
    assert runner.main(["--all", "--root", str(tmp_path), "--date", "2026-10-06"]) == 0
    assert runner.main(["--all", "--root", str(tmp_path), "--date", "2026-10-06"]) == 0
    assert "C99A_TEST\tFAIL" in capsys.readouterr().out


def test_check14_unreproduced_type_and_open_high():
    ok = c.check_14_final_audit([], GOOD_AUDIT, ["dip_in_trend", "risk"], True)
    assert ok.passed
    bad = {"rule_types": {"dip_in_trend": {"reproduced": False}},
           "engine_findings": [{"severity": "high", "open": True, "text": "bug"}]}
    r = c.check_14_final_audit([], bad, ["dip_in_trend", "risk"], True)
    assert not r.passed and "risk" in r.detail
    assert not c.check_14_final_audit([], GOOD_AUDIT, ["risk"], False).passed


def test_check5_requires_both():
    assert c.check_5_purge_embargo(True, True).passed
    assert not c.check_5_purge_embargo(True, False).passed
    assert not c.check_5_purge_embargo(None, True).passed


def test_none_wf_mean_in_sensitivity_is_no_evidence():
    r = c.check_6_sensitivity({"minus20": c.SensitivityResult(None, False)})
    assert not r.passed
    assert np.isfinite(1.0)
