import importlib.util
from pathlib import Path
import sys
import json

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location('forex_fx1', Path(__file__).resolve().parents[2]/'scripts/backtest_forex_fx1.py')
fx = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fx
SPEC.loader.exec_module(fx)


def synthetic(n=500):
    close = 1.5-np.arange(n)*.0005
    return pd.DataFrame(dict(date=pd.bdate_range('2019-01-01',periods=n).strftime('%Y-%m-%d'),
                             open=close+.0002, high=close+.001, low=close-.001,close=close))


@pytest.mark.parametrize('cutoff',[250,320,410])
def test_prefix_and_future_corruption(cutoff):
    data = synthetic()
    end = data.date.iloc[cutoff]
    full,trades = fx.simulate(data,data.date.iloc[0],end,liquidate=False)
    short,short_trades = fx.simulate(data.iloc[:cutoff+1],data.date.iloc[0],end,liquidate=False)
    corrupt = data.copy()
    corrupt.loc[cutoff+1:,['open','high','low','close']] *= 40
    changed,changed_trades = fx.simulate(corrupt,data.date.iloc[0],end,liquidate=False)
    pd.testing.assert_frame_equal(full,short)
    pd.testing.assert_frame_equal(full,changed)
    pd.testing.assert_frame_equal(trades,short_trades)
    pd.testing.assert_frame_equal(trades,changed_trades)


def test_cash_conservation_and_costs():
    data = synthetic()
    daily,trades = fx.simulate(data,data.date.iloc[210],data.date.iloc[400])
    assert len(trades)>0
    assert (daily[['eur_cash','usd_cash']]>=0).all().all()
    np.testing.assert_allclose(daily.equity_eur,daily.eur_cash+daily.usd_cash/daily.midpoint)
    assert daily.usd_cash.iloc[-1] == 0
    assert daily.equity_eur.iloc[-1] == pytest.approx(1000+trades.net_eur.sum())
    for _,t in trades.iterrows():
        assert t.net_eur == pytest.approx(t.units_eur*t.entry_bid/t.exit_ask-t.units_eur-t.entry_fee_eur-t.exit_fee_eur)
        assert t.units_eur <= .95*t.entry_equity
        assert t.entry_fee_eur == pytest.approx(max(2,t.units_eur*t.entry_bid*.00002)/t.entry_midpoint)
        stop_loss = t.units_eur*(1-t.entry_bid/(t.stop_midpoint+.0001))+t.entry_fee_eur+fx.fee_eur(t.units_eur*t.entry_bid,t.stop_midpoint,fx.Params())
        assert stop_loss <= .005*t.entry_equity+1e-9


def test_entry_day_stop_and_gap():
    data = synthetic(300)
    start = data.date.iloc[210]
    # First entry is fold bar 5 = global bar 215.
    data.loc[215,'high'] = data.loc[215,'open']+.02
    _,trades = fx.simulate(data,start,data.date.iloc[218])
    assert trades.iloc[0].reason == 'entry_day_stop'
    assert trades.iloc[0].net_eur >= -5.0000001
    data = synthetic(300)
    data.loc[216,['open','high','low','close']] = [1.5,1.502,1.498,1.5]
    _,trades = fx.simulate(data,start,data.date.iloc[218])
    assert trades.iloc[0].reason == 'stop_gap'
    assert trades.iloc[0].exit_ask == pytest.approx(1.5001)
    assert trades.iloc[0].net_eur < -5  # Stops do not cap gap losses.


def test_no_trades_when_fixed_fees_exceed_risk_budget():
    data = synthetic(300)
    daily,trades = fx.simulate(data,data.date.iloc[210],data.date.iloc[290],initial=100)
    assert trades.empty
    assert (daily.equity_eur == 100).all()


def test_loader_rejects_invalid_and_filters_future(tmp_path):
    data = synthetic(5)
    data.loc[4,'close'] = -1
    path=tmp_path/'prices.csv'
    data.to_csv(path,index=False)
    assert len(fx.load_data(path,through=data.date.iloc[3])) == 4
    with pytest.raises(ValueError,match='Invalid prices'):
        fx.load_data(path)


def test_maxhold_and_embargo():
    data=synthetic()
    _,trades=fx.simulate(data,data.date.iloc[210],data.date.iloc[400])
    assert trades.iloc[0].entry_date == data.date.iloc[215]
    assert trades.iloc[0].exit_date == data.date.iloc[275]
    assert trades.iloc[0].reason == 'max_hold'
    assert trades.iloc[0].held_bars == 60


def test_preflight_blocks_changed_csv_before_subprocess(tmp_path,monkeypatch):
    folder=tmp_path/'reports/data'
    folder.mkdir(parents=True)
    checks={k:True for k in ('equal_arrays','sorted','unique','positive_finite','ohlc_range','no_large_gaps')}
    (folder/'2026-10-13_forex_validation.json').write_text(json.dumps(dict(checks=checks,csv_sha256='old')))
    (folder/'2026-10-13_forex_registration.json').write_text('{}')
    data=tmp_path/'data.csv'
    data.write_text('changed')
    monkeypatch.setattr(fx.subprocess,'run',lambda *a,**k:pytest.fail('Must block before external validation'))
    with pytest.raises(ValueError,match='CSV hash mismatch'):
        fx.preflight(data,b'{}',{},tmp_path)


def test_distinct_holiday_timestamps_are_retained(tmp_path):
    data=synthetic(300)
    data['timestamp']=pd.to_datetime(data.date,utc=True).dt.strftime('%Y-%m-%dT07:00:00Z')
    extra=data.iloc[[215]].copy()
    extra['timestamp']=extra.date+'T23:00:00Z'
    extra[['open','high','low','close']] -= .0003
    data=pd.concat([data.iloc[:216],extra,data.iloc[216:]],ignore_index=True)
    path=tmp_path/'holiday.csv'
    data.to_csv(path,index=False)
    loaded=fx.load_data(path)
    assert len(loaded)==301
    assert loaded.date.duplicated().sum()==1
    daily,trades=fx.simulate(loaded,loaded.date.iloc[210],loaded.date.iloc[290])
    assert daily.timestamp.is_unique
    assert len(daily[daily.date==extra.date.iloc[0]])==2
    assert trades.iloc[0].entry_timestamp==data.timestamp.iloc[215]
    data.loc[216,'timestamp']=data.loc[215,'timestamp']
    data.to_csv(path,index=False)
    with pytest.raises(ValueError,match='duplicate.*timestamps'):
        fx.load_data(path)
    data.drop(columns='timestamp').to_csv(path,index=False)
    with pytest.raises(ValueError,match='Duplicate dates'):
        fx.load_data(path)
