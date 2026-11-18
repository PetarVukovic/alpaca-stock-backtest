"""Predeclared C28 gates: a favorable headline cannot mask a failed risk/stress check."""
from copy import deepcopy
import numpy as np
import json
import pandas as pd
import pytest
from scripts.run_recovery_reentry import interest_checks, assert_baseline_parity


def inputs():
    base={p:{'return_pct':10.,'max_drawdown_pct':20.} for p in ('IS','WF','HO_SEEN')}
    candidate=deepcopy(base);candidate['WF']['return_pct']=11.
    stress={name:{'WF':{'return_pct':12.,'usd_cash_benchmark':{'return_pct':11.}}} for name in ('COST3','EXIT100BPS')}
    return {'SMALL_600EUR_ALL':{'baseline':base,'candidate':candidate}}, {'SMALL_600EUR_ALL':{'candidate':stress}}


def test_interest_pass_is_never_approval():
    result=interest_checks(*inputs())
    assert result['research_interest']=='PASS'
    assert not result['critic_approval'] and not result['activation']


def test_exit_stress_equal_cash_fails_even_with_high_headline():
    results,stresses=inputs()
    results['SMALL_600EUR_ALL']['candidate']['HO_SEEN']['return_pct']=1000.
    stresses['SMALL_600EUR_ALL']['candidate']['EXIT100BPS']['WF']['return_pct']=11.
    result=interest_checks(results,stresses)
    assert result['research_interest']=='FAIL'
    assert not result['checks']['WF_exit100bps_above_USD_cash']


def test_baseline_parity_requires_whole_path_not_only_endpoint():
    baseline={'curve':pd.Series([100.,90.,110.]),'trades':[],'events':[],'skipped':[],'open_position':None}
    changed=deepcopy(baseline);changed['curve'].iloc[1]=95.
    with pytest.raises(ValueError,match='equity'):
        assert_baseline_parity(changed,baseline)


def test_numpy_comparison_flags_are_serializable_native_booleans():
    results,stresses=inputs()
    results["SMALL_600EUR_ALL"]["candidate"]["WF"]["return_pct"]=np.float64(12.)
    result=interest_checks(results,stresses)
    assert all(type(v) is bool for v in result["checks"].values())
    json.dumps(result)
