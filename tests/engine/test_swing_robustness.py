"""Frozen selection and regime/FX diagnostics; synthetic data, no broker calls."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from scripts.run_swing_robustness import select_pre_holdout, regime_labels, regime_attribution, block_bootstrap_account


def cases():
    row = dict(return_pct=20., usd_cash_benchmark={'return_pct':10.}, n_closed=20,
               max_drawdown_pct=25., sharpe=.5)
    return {name:{p:deepcopy(row) for p in ('IS','WF')} for name in ('BASE','CANDIDATE')}


def test_fx_only_profit_is_not_selected():
    results = cases()
    for variant in results.values():
        variant['WF']['return_pct'] = 7
    assert select_pre_holdout(results, 'BASE')['selected'] is None


def test_ranking_uses_pre_holdout_only():
    results = cases()
    results['CANDIDATE']['WF']['sharpe'] = .6
    results['BASE']['HO'] = {'return_pct':1e9}
    results['CANDIDATE']['HO'] = {'return_pct':-99.9}
    assert select_pre_holdout(results,'BASE')['selected'] == 'CANDIDATE'
    results['CANDIDATE']['WF']['max_drawdown_pct'] = 25.1
    assert select_pre_holdout(results,'BASE')['selected'] == 'BASE'


def test_regime_cannot_use_entry_days_price_and_high_vol_takes_precedence():
    index = pd.bdate_range('2020-01-01', periods=250, tz='UTC')
    frame = pd.DataFrame({'close':100+np.arange(250)*.1},index=index)
    labels = regime_labels(frame)
    changed = frame.copy()
    changed.loc[index[230]:,'close'] *= 100
    assert regime_labels(changed).loc[:index[230]].equals(labels.loc[:index[230]])
    highvol = frame.copy()
    highvol.iloc[205:230,0] = np.resize([80.,130.],25)
    assert regime_labels(highvol).loc[index[230]] == 'HIGH_VOL'
    assert labels.iloc[199] == 'UNKNOWN'
    assert labels.iloc[200] == 'UP'


def test_attribution_does_not_claim_open_positions_as_closed_trades():
    labels = pd.Series(['UP'],index=pd.to_datetime(['2023-01-03'],utc=True))
    trade = {'entry_date':'2023-01-03','pnl_usd':5.,'return_pct':1.}
    assert regime_attribution([trade],labels)['UP']['n_closed'] == 1
    assert regime_attribution([],labels) == {}


def test_account_bootstrap_deterministic_and_does_not_compound_trade_percentages():
    daily = np.array([.01,-.005,0.,.002,-.01]*8)
    a=block_bootstrap_account(daily,n_sims=200,block_len=5)
    b=block_bootstrap_account(daily,n_sims=200,block_len=5)
    assert a == b
    assert a['n_days'] == 40
    assert 0 <= a['drawdown_p50_pct'] <= a['drawdown_p95_pct'] <= 100
    with pytest.raises(ValueError): block_bootstrap_account([-1.,.01])
