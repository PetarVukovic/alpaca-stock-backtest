"""Independent checks for the offline shared-account research replay."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.backend.portfolio_replay import simulate_portfolio
from app.backend.strategies.c13c import Bar, TICKERS, stop_for
from lab.data import load_bars
from lab.research.memory_swing import replay

ROOT = Path(__file__).parents[2]


def synthetic(price=100.0):
    dates = pd.bdate_range(end='2023-01-06', periods=200, tz='UTC')
    closes = np.array([price * .5] * 194 + [price * 1.1] + [price * 1.08,price * 1.07,price * 1.06,price * 1.05,price])
    frame = pd.DataFrame(dict(open=closes,high=closes*1.01,low=closes*.99,close=closes,volume=100000),index=dates)
    return {s:frame.copy() for s in TICKERS}


def append(frames, day, o,h,l,c):
    for frame in frames.values(): frame.loc[pd.Timestamp(day,tz='UTC')] = [o,h,l,c,100000]
    return frames


def test_completed_real_core_fixed_one_matches_app_through_2023():
    frames = {s:load_bars(s,'daily',root=ROOT).loc[:'2023-12-31'] for s in TICKERS}
    app_bars = {s:[Bar(str(day.date()),r.open,r.high,r.low,r.close) for day,r in frame.iterrows()] for s,frame in frames.items()}
    expected = simulate_portfolio(app_bars,'2021-01-01','2023-12-31','100000')
    actual = replay(frames,'2021-01-01','2023-12-31',100000)
    np.testing.assert_allclose(actual['curve'].to_numpy(),[float(r['equity_usd']) for r in expected['curve']],rtol=0,atol=1e-7)
    assert len(actual['trades']) == len(expected['trades']) > 0
    for a,e in zip(actual['trades'],expected['trades']):
        assert (a['ticker'],a['entry_date'],a['exit_date'],a['quantity']) == (e['ticker'],e['entry_date'],e['exit_date'],e['qty'])
        assert a['entry_price'] == pytest.approx(float(e['entry_price']),abs=1e-10)
        assert a['exit_price'] == pytest.approx(float(e['exit_price']),abs=1e-10)


def test_causal_prefix_and_later_high_cannot_stop_entry_day():
    frames = append(synthetic(),'2023-01-09',100,150,95,140)
    first = replay(frames,'2023-01-09','2023-01-09',100000)
    future = append(frames,'2023-01-10',1000,2000,1,1500)
    second = replay(future,'2023-01-09','2023-01-09',100000)
    pd.testing.assert_series_equal(first['curve'],second['curve'])
    assert first['trades'] == second['trades'] == []
    assert first['open_position']['peak'] == 150


def test_gap_stop_and_entry_day_stop_match_adverse_execution():
    frames = append(synthetic(),'2023-01-09',100,120,95,115)
    append(frames,'2023-01-10',80,90,70,85)
    result = replay(frames,'2023-01-09','2023-01-10',100000)
    trade, = result['trades']
    assert trade['reason'] == 'gap_stop'
    assert trade['raw_exit'] == 80
    assert trade['exit_price'] == pytest.approx(79.97)
    assert result['curve'].iloc[-1] == pytest.approx(100000 + trade['pnl_usd'])
    entry_stop = replay(append(synthetic(),'2023-01-09',100,120,80,95),'2023-01-09','2023-01-09',100000)
    assert len(entry_stop['trades']) == 1
    assert entry_stop['trades'][0]['entry_date'] == entry_stop['trades'][0]['exit_date']


def test_small_account_risk_budget_blocks_one_share_when_stop_too_large():
    frames = append(synthetic(200),'2023-01-09',200,210,195,205)
    result = replay(frames,'2023-01-09','2023-01-09',660,sizing='risk2')
    assert result['open_position'] is None and len(result['skipped']) == 1
    assert result['curve'].iloc[-1] == 660
    allowed = replay(frames,'2023-01-09','2023-01-09',660,sizing='one')
    assert allowed['open_position']['quantity'] == 1


def test_whole_share_risk_sizing_never_exceeds_cash_or_cap():
    frames = append(synthetic(10),'2023-01-09',10,10.5,9.5,10.2)
    result = replay(frames,'2023-01-09','2023-01-09',660,sizing='risk2',cap=100)
    pos = result['open_position']
    assert isinstance(pos['quantity'],int) and pos['quantity'] > 0
    assert pos['quantity'] * pos['entry_price'] <= min(100,660)
    stop = stop_for(pos['entry_price'])
    modeled_exit = stop - (stop * .00025 + .01)
    assert pos['quantity'] * (pos['entry_price'] - modeled_exit) <= 660 * .02


def test_interior_calendar_gap_is_not_silently_intersected():
    frames = append(synthetic(),'2023-01-09',100,120,95,115)
    append(frames,'2023-01-10',100,120,95,115)
    frames['WDC'] = frames['WDC'].drop(pd.Timestamp('2023-01-09',tz='UTC'))
    with pytest.raises(ValueError,match='calendars'): replay(frames,'2023-01-09','2023-01-10',100000)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1])
def test_invalid_capital_is_rejected(value):
    with pytest.raises(ValueError): replay(synthetic(),'2023-01-02','2023-01-06',value)


def test_duplicate_bar_and_nonfinite_ohlc_are_rejected():
    frames = synthetic()
    frames['MU'] = pd.concat([frames['MU'],frames['MU'].iloc[[-1]]])
    with pytest.raises(ValueError): replay(frames,'2023-01-02','2023-01-06',100000)
    frames = synthetic()
    frames['MU'].iloc[-1,0] = np.nan
    with pytest.raises(ValueError): replay(frames,'2023-01-02','2023-01-06',100000)


def test_before_listing_is_explicitly_unavailable_not_crash():
    assert replay(synthetic(),'2016-01-04','2020-12-31',100000) is None


def test_reversed_interval_is_rejected():
    with pytest.raises(ValueError,match='Reversed'): replay(synthetic(),'2023-01-06','2023-01-02',100000)


def test_zero_volume_fill_is_counted_as_violation():
    frames = append(synthetic(),'2023-01-09',100,120,95,115)
    for frame in frames.values(): frame.iloc[-1,frame.columns.get_loc('volume')] = 0
    result = replay(frames,'2023-01-09','2023-01-09',100000)
    assert result['fill_violations'] == 1
    assert np.isinf(result['max_daily_volume_fraction'])


def test_negative_and_nonfinite_volume_rejected():
    for value in [-1,float('nan'),float('inf')]:
        frames = synthetic()
        frames['MU']['volume'] = frames['MU']['volume'].astype(float)
        frames['MU'].iloc[-1,frames['MU'].columns.get_loc('volume')] = value
        with pytest.raises(ValueError): replay(frames,'2023-01-02','2023-01-06',100000)


def test_all_cash_research_uses_whole_shares_and_leaves_residual():
    frames = append(synthetic(100),'2023-01-09',100,110,95,105)
    result = replay(frames,'2023-01-09','2023-01-09',660,sizing='all',cap=1e12)
    position = result['open_position']
    assert position['quantity'] == 6
    spent = position['quantity'] * position['entry_price']
    assert spent <= 660 and 0 <= 660-spent < position['entry_price']
    assert result['curve'].iloc[-1] == pytest.approx(660-spent + 6*105)
    capped = replay(frames,'2023-01-09','2023-01-09',660,sizing='all',cap=250)
    assert capped['open_position']['quantity'] == 2


def test_all_cash_research_still_skips_unaffordable_whole_share():
    frames = append(synthetic(800),'2023-01-09',800,810,790,805)
    result = replay(frames,'2023-01-09','2023-01-09',660,sizing='all',cap=1e12)
    assert result['open_position'] is None and len(result['skipped']) == 1
    assert result['curve'].iloc[-1] == 660


def test_all_cash_research_retains_stop_and_gap_can_lose_more_than_ten_percent():
    frames = append(synthetic(),'2023-01-09',100,110,95,105)
    append(frames,'2023-01-10',50,60,40,55)
    result = replay(frames,'2023-01-09','2023-01-10',660,sizing='all',cap=1e12)
    trade, = result['trades']
    assert trade['quantity'] == 6 and trade['reason'] == 'gap_stop'
    assert trade['raw_exit'] == 50
    assert result['curve'].iloc[-1] < 660*.9
    assert result['curve'].iloc[-1] >= 0


def test_default_execution_diagnostics_preserve_baseline_exactly():
    frames = append(synthetic(),'2023-01-09',100,120,95,115)
    append(frames,'2023-01-10',80,90,70,85)
    base = replay(frames,'2023-01-09','2023-01-10',660,sizing='all')
    explicit = replay(frames,'2023-01-09','2023-01-10',660,sizing='all',entry_delay_sessions=1,extra_entry_bps=0,extra_exit_bps=0,market_filter=None)
    pd.testing.assert_series_equal(base['curve'],explicit['curve'],check_exact=True)
    assert base['events'] == explicit['events']


def test_second_session_delay_keeps_original_queue_and_entry_stop():
    frames = append(synthetic(),'2023-01-09',100,110,95,100)
    append(frames,'2023-01-10',100,110,80,100)
    result = replay(frames,'2023-01-09','2023-01-10',660,entry_delay_sessions=2)
    trade, = result['trades']
    assert trade['entry_date'] == trade['exit_date'] == '2023-01-10'
    assert result['curve'].iloc[0] == 660
    assert trade['ticker'] == 'MU'


def test_filter_is_used_on_signal_day_not_future_entry_day():
    frames = append(synthetic(),'2023-01-09',100,110,95,105)
    denied = pd.Series(False,index=frames['MU'].index)
    blocked = replay(frames,'2023-01-09','2023-01-09',660,market_filter=denied)
    assert blocked['events'] == [] and blocked['curve'].iloc[-1] == 660
    allowed = denied.copy()
    allowed.loc[pd.Timestamp('2023-01-06',tz='UTC')] = True
    result = replay(frames,'2023-01-09','2023-01-09',660,market_filter=allowed)
    assert result['open_position']['quantity'] == 1


def test_extra_exit_one_basis_point_costs_one_cent_at_raw_100():
    frames = append(synthetic(),'2023-01-09',100,120,95,115)
    append(frames,'2023-01-10',100,110,90,105)
    base = replay(frames,'2023-01-09','2023-01-10',660)
    adverse = replay(frames,'2023-01-09','2023-01-10',660,extra_exit_bps=1)
    a,b = base['trades'][0],adverse['trades'][0]
    assert a['raw_exit'] == b['raw_exit'] == 100
    assert a['exit_price']-b['exit_price'] == pytest.approx(.01)
    assert adverse['fill_violations'] == 0
    assert adverse['costs_usd']-base['costs_usd'] == pytest.approx(.01)


def test_extra_entry_cost_is_friction_not_fabricated_raw_fill():
    frames = append(synthetic(),'2023-01-09',100,110,95,105)
    base = replay(frames,'2023-01-09','2023-01-09',660)
    adverse = replay(frames,'2023-01-09','2023-01-09',660,extra_entry_bps=10)
    assert adverse['open_position']['raw_entry'] == 100
    assert adverse['open_position']['entry_price']-base['open_position']['entry_price'] == pytest.approx(.1)
    assert adverse['fill_violations'] == 0


def test_volatility_uses_twenty_prior_returns_without_entry_day_or_future():
    frames = append(synthetic(10),'2023-01-09',10,11,9.5,10.5)
    previous = frames['MU'].loc[:'2023-01-06'].close.tail(21).pct_change().dropna()
    expected_weight = min(1,.015/previous.std(ddof=1))
    result = replay(frames,'2023-01-09','2023-01-09',6600,sizing='volatility',cap=1e12)
    pos = result['open_position']
    assert pos['quantity'] == int((6600*expected_weight)//pos['entry_price']) > 0
    assert pos['quantity']*pos['entry_price'] <= 6600
    # An enormous same-day closing/high price changes marking but cannot resize an opening fill.
    altered = {symbol:frame.copy() for symbol,frame in frames.items()}
    for frame in altered.values(): frame.loc[pd.Timestamp('2023-01-09',tz='UTC'),['high','close']] = [2000,1500]
    changed = replay(altered,'2023-01-09','2023-01-09',6600,sizing='volatility',cap=1e12)
    assert changed['open_position']['quantity'] == pos['quantity']
    append(altered,'2023-01-10',1000,2000,1,1500)
    prefix = replay(altered,'2023-01-09','2023-01-09',6600,sizing='volatility',cap=1e12)
    assert prefix['events'] == changed['events']


@pytest.mark.parametrize('options',[{'entry_delay_sessions':0},{'entry_delay_sessions':1.5},{'extra_entry_bps':-1},{'extra_exit_bps':float('nan')}])
def test_invalid_execution_diagnostics_rejected(options):
    with pytest.raises(ValueError): replay(synthetic(),'2023-01-02','2023-01-06',660,**options)
