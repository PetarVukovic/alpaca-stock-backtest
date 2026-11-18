"""Adversarial invariants for the frozen research-only C29/C30 extensions."""
import numpy as np
import pandas as pd
import pytest
from lab.research import regime_swing as engine
from lab.research.memory_swing import replay as baseline


def frame(n=280):
    idx=pd.date_range('2020-01-01',periods=n,freq='B',tz='UTC')
    close=np.linspace(70,120,n)
    return pd.DataFrame(dict(open=close,high=close+1,low=close-1,close=close,volume=100000),index=idx)


def set_signal(monkeypatch, day):
    monkeypatch.setattr(engine,'entry_signals',lambda f,*args:pd.Series(f.index==day,index=f.index))


def test_disabled_matches_original_real_dip():
    f=frame();f.loc[f.index[210:215],['open','high','low','close']]*=.93
    start,end=str(f.index[0].date()),str(f.index[-1].date())
    a=engine.replay({'MU':f},start,end,600,mode='baseline',sizing='all')
    b=baseline({'MU':f},start,end,600,sizing='all')
    assert a['events'] and a['events']==b['events']
    pd.testing.assert_series_equal(a['curve'],b['curve'])


def test_entry_stop_and_future_high_cannot_rescue_stop(monkeypatch):
    f=frame();signal=f.index[210];entry=f.index[211]
    set_signal(monkeypatch,signal)
    f.loc[entry,'high']=250
    f.loc[entry,'low']=70
    r=engine.replay({'MU':f},str(signal.date()),str(f.index[-1].date()),10000,mode='atr')
    assert r['trades'][0]['entry_date']==str(entry.date())
    assert r['trades'][0]['exit_date']==str(entry.date())
    assert r['trades'][0]['raw_exit']<f.loc[entry,'open']
    assert r['trades'][0]['raw_exit']>70


def test_atr_shock_never_lowers_protective_stop(monkeypatch):
    f=frame();signal=f.index[210];set_signal(monkeypatch,signal)
    f.loc[f.index[215],'high']=200
    # Keep low above the old stop, but make ATR rise sharply.
    r=engine.replay({'MU':f},str(signal.date()),str(f.index[-1].date()),10000,mode='atr')
    for _,g in pd.DataFrame(r['stop_history']).groupby(['ticker','entry_date']):
        assert (g.stop.diff().dropna()>=0).all()


def test_gap_filter_uses_previous_atr_not_same_day_extreme(monkeypatch):
    f=frame();signal=f.index[210];set_signal(monkeypatch,signal)
    prior=float(f.loc[f.index[209],'close'])
    f.loc[signal,['open','low']]=[prior-3,prior-4]
    f.loc[signal,'high']=300  # would inflate same-day ATR and hide the shock
    r=engine.replay({'MU':f},str(signal.date()),str(f.index[-1].date()),10000,mode='gap')
    assert r['events']==[]


@pytest.mark.parametrize('mode',['atr','gap'])
def test_future_corruption_and_truncation(monkeypatch,mode):
    f=frame();signal=f.index[210];set_signal(monkeypatch,signal)
    start=str(signal.date());cut=str(f.index[235].date());end=str(f.index[-1].date())
    full=engine.replay({'MU':f},start,end,10000,mode=mode)
    short=engine.replay({'MU':f.loc[:cut]},start,cut,10000,mode=mode)
    changed=f.copy();changed.loc[changed.index>pd.Timestamp(cut,tz='UTC'),['open','high','low','close']]*=7
    other=engine.replay({'MU':changed},start,end,10000,mode=mode)
    pd.testing.assert_series_equal(full['curve'].loc[:cut],short['curve'])
    pd.testing.assert_series_equal(full['curve'].loc[:cut],other['curve'].loc[:cut])


def test_atr_wilder_seed():
    f=frame(30)
    f[['open','close']]=100
    f['high']=101; f['low']=99
    atr=engine.wilder_atr(f,20)
    assert atr.iloc[:19].isna().all()
    assert atr.iloc[19]==pytest.approx(2)
    assert atr.iloc[-1]==pytest.approx(2)


def test_atr_cannot_silently_use_old_percent_risk_budget():
    f=frame()
    with pytest.raises(ValueError,match='risk2'):
        engine.replay({'MU':f},str(f.index[0].date()),str(f.index[-1].date()),600,mode='atr',sizing='risk2')
