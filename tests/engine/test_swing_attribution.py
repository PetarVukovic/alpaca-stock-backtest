"""Retrospective diagnostics must not invent future coverage or trading decisions."""
import pandas as pd
import pytest
from scripts.analyze_swing_attribution import forward_excursions,attribute,flat_spells


def frame():
    return pd.DataFrame({'open':[100,100,90,110],'high':[1000,110,100,120],'low':[1,90,80,100],'close':[100,105,95,115],'volume':[100]*4},index=pd.bdate_range('2023-01-02',periods=4,tz='UTC'))


def test_forward_excludes_exit_bar_and_marks_incomplete_horizon():
    rows=forward_excursions(frame(),'2023-01-02',100,[2,5])
    assert rows[0]['terminal_return_pct']==pytest.approx(-5)
    assert rows[0]['favorable_excursion_pct']==pytest.approx(10)
    assert rows[0]['adverse_excursion_pct']==pytest.approx(-20)
    assert not rows[0]['censored']
    assert rows[1]['censored'] and rows[1]['observed_sessions']==3
    assert rows[1]['terminal_return_pct']==pytest.approx(15)


def test_exit_at_last_day_is_fully_censored_not_zero_return():
    rows=forward_excursions(frame(),'2023-01-05',100,[5])
    assert rows[0]['censored'] and rows[0]['observed_sessions']==0
    assert rows[0]['terminal_return_pct'] is None


def test_flat_spells_are_contiguous_and_do_not_sum_stock_returns():
    rows=[{'date':d,'flat_at_close':flat} for d,flat in [('2023-01-02',True),('2023-01-03',True),('2023-01-04',False),('2023-01-05',True)]]
    spells=flat_spells(rows,{'MU':frame(),'WDC':frame(),'STX':frame()})
    assert [s['flat_closes'] for s in spells]==[2,1]
    assert spells[0]['mean_stock_price_return_pct']==pytest.approx(5)
    assert spells[1]['mean_stock_price_return_pct']==0


def test_waits_censor_unseen_signal_and_record_actual_other_ticker_entry():
    frames={s:frame() for s in ['MU','WDC','STX']}
    result={'curve':pd.Series([100]*4,index=frame().index),'trades':[{'ticker':'MU','exit_date':'2023-01-02','raw_exit':100,'pnl_usd':0}],
            'events':[('2023-01-02','sell','MU',1,100),('2023-01-04','buy','WDC',1,90)]}
    rows=attribute(frames,result,'2023-01-02','2023-01-05')
    wait=rows['waits'][0]
    assert wait['signal_wait_censored'] and wait['next_same_ticker_signal'] is None
    assert wait['next_portfolio_ticker']=='WDC' and wait['portfolio_entry_wait_sessions']==2
    assert rows['daily'][2]['held_at_close']=='WDC'


def test_collisions_count_only_flat_decisions_not_held_signals():
    from tests.engine.test_memory_swing import synthetic,append
    frames=append(synthetic(),'2023-01-09',100,110,95,100)
    dates=pd.DatetimeIndex([pd.Timestamp('2023-01-06',tz='UTC'),pd.Timestamp('2023-01-09',tz='UTC')])
    result={'curve':pd.Series([660,660],index=dates),'trades':[], 'events':[('2023-01-09','buy','MU',1,100)]}
    rows=attribute(frames,result,'2023-01-06','2023-01-09')
    assert len(rows['collisions'])==1
    assert rows['collisions'][0]['chosen']=='MU' and rows['collisions'][0]['suppressed']=='WDC,STX'
    assert rows['daily'][1]['other_signals_while_held']=='WDC,STX'
