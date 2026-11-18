"""C28 synthetic state-machine tests; future reclaim information never changes entry timing."""
from pathlib import Path
import hashlib
import pandas as pd
import pytest
from lab.research.memory_swing import replay as baseline
from lab.research.reentry_swing import replay
from lab.data import load_bars
from tests.engine.test_memory_swing import synthetic,append

ROOT=Path(__file__).parents[2]
BASELINE_SHA='96cbc9dca31a5fbc22675ed90f5ac6eb609853008fb05230f89731a75a3f1d8f'


def scenario():
    frames={'MU':synthetic()['MU']}
    append(frames,'2023-01-09',100,120,95,115)
    # Gap stop uses yesterday's 120 peak, never today's high 200.
    append(frames,'2023-01-10',100,200,95,130)
    append(frames,'2023-01-11',130,132,120,121)
    append(frames,'2023-01-12',122,125,115,124)
    return frames


def without_tags(position):
    return {k:v for k,v in position.items() if k not in {'entry_reason','reentry_anchor','signal_date'}} if position else None


def assert_baseline_fields(base,new):
    pd.testing.assert_series_equal(base['curve'],new['curve'],check_exact=True)
    for key,value in base.items():
        if key=='curve':continue
        if key=='trades':assert value==[without_tags(t) for t in new[key]]
        elif key=='open_position':assert value==without_tags(new[key])
        else:assert value==new[key]


def test_pre_exit_anchor_and_strict_later_close_then_next_open():
    frames=scenario()
    result=replay(frames,'2023-01-09','2023-01-12',1000,reentry_enabled=True)
    buys=[event for event in result['events'] if event[1]=='buy']
    assert [event[0] for event in buys]==['2023-01-09','2023-01-12']
    assert result['entry_tags'][1]['entry_reason']=='reentry_reclaim'
    assert result['entry_tags'][1]['reentry_anchor']==120
    assert result['entry_tags'][1]['signal_date']=='2023-01-11'
    assert result['trades'][0]['reason']=='gap_stop'
    assert result['reentry_anchors']=={}
    cut=replay(frames,'2023-01-09','2023-01-11',1000,reentry_enabled=True)
    assert cut['reentry_anchors']['MU']=={'peak':120,'exit_date':'2023-01-10'}
    assert cut['entry_tags']==result['entry_tags'][:1]


def test_enabled_no_reclaim_path_matches_copied_baseline_not_only_delegation():
    frames={'MU':synthetic()['MU']}
    append(frames,'2023-01-09',100,110,95,105)
    append(frames,'2023-01-10',105,115,100,110)
    for sizing in ['one','all','risk2','volatility']:
        base=baseline(frames,'2023-01-09','2023-01-10',10000,sizing=sizing)
        new=replay(frames,'2023-01-09','2023-01-10',10000,sizing=sizing,reentry_enabled=True)
        assert_baseline_fields(base,new)


def test_failed_affordability_does_not_consume_anchor():
    frames=scenario()
    frames['MU'].loc[pd.Timestamp('2023-01-12',tz='UTC')]=[200,205,180,202,100000]
    skipped=replay(frames,'2023-01-09','2023-01-12',150,reentry_enabled=True)
    assert skipped['skipped'][0]['entry_reason']=='reentry_reclaim'
    assert skipped['reentry_anchors']['MU']['peak']==120
    append(frames,'2023-01-13',125,130,120,128)
    resumed=replay(frames,'2023-01-09','2023-01-13',150,reentry_enabled=True)
    assert resumed['entry_tags'][-1]['entry_date']=='2023-01-13'
    assert resumed['reentry_anchors']=={}


def test_normal_dip_may_schedule_on_stop_day_and_entry_day_stop_replaces_anchor():
    frames={'MU':synthetic()['MU']}
    append(frames,'2023-01-09',100,110,80,100)
    append(frames,'2023-01-10',100,110,80,100)
    result=replay(frames,'2023-01-09','2023-01-10',1000,reentry_enabled=True)
    assert_baseline_fields(baseline(frames,'2023-01-09','2023-01-10',1000),result)
    assert len(result['trades'])==2
    assert all(t['sessions_held']==1 for t in result['trades'])
    assert result['entry_tags'][1]['entry_reason']=='normal_dip'
    assert result['entry_tags'][1]['signal_date']=='2023-01-09'
    assert result['reentry_anchors']['MU']['exit_date']=='2023-01-10'
    assert result['reentry_anchors']['MU']['peak']==pytest.approx(100.035)


def test_buying_other_symbol_preserves_anchor_and_future_data_is_causal():
    frames=scenario()
    frames['MU'].loc[pd.Timestamp('2023-01-11',tz='UTC')]=[118,120,115,119,100000]
    peer=frames['MU'].copy()
    peer.loc[:'2023-01-06',['open','high','low','close']]=70
    peer.iloc[-9:-4,peer.columns.get_indexer(['open','high','low','close'])]=100
    peer.loc[pd.Timestamp('2023-01-09',tz='UTC')]=[100,110,95,100,100000]
    peer.loc[pd.Timestamp('2023-01-10',tz='UTC')]=[100,110,95,100,100000]
    peer.loc[pd.Timestamp('2023-01-11',tz='UTC')]=[90,95,85,90,100000]
    peer.loc[pd.Timestamp('2023-01-12',tz='UTC')]=[90,100,85,95,100000]
    frames['WDC']=peer
    result=replay(frames,'2023-01-09','2023-01-12',1000,reentry_enabled=True)
    assert result['entry_tags'][-1]['ticker']=='WDC'
    assert result['reentry_anchors']['MU']['peak']==120
    future={s:f.copy() for s,f in frames.items()}
    append(future,'2023-01-13',1000,2000,1,1500)
    again=replay(future,'2023-01-09','2023-01-12',1000,reentry_enabled=True)
    pd.testing.assert_series_equal(result['curve'],again['curve'],check_exact=True)
    assert result['entry_tags']==again['entry_tags']


@pytest.mark.parametrize('sizing,capital',[('one',100000),('one',660),('risk2',660),('all',660),('volatility',660)])
def test_disabled_real_core_all_history_exact_baseline(sizing,capital):
    frames={s:load_bars(s,through='2026-10-02') for s in ['MU','WDC','STX']}
    base=baseline(frames,'2016-01-04','2026-10-02',capital,sizing=sizing)
    new=replay(frames,'2016-01-04','2026-10-02',capital,sizing=sizing,reentry_enabled=False)
    assert_baseline_fields(base,new)
    assert hashlib.sha256((ROOT/'lab/research/memory_swing.py').read_bytes()).hexdigest()==BASELINE_SHA


def test_equal_anchor_close_does_not_trigger_reclaim():
    frames=scenario()
    frames['MU'].loc[pd.Timestamp('2023-01-11',tz='UTC')]=[120,130,115,120,100000]
    result=replay(frames,'2023-01-09','2023-01-12',1000,reentry_enabled=True)
    assert len(result['entry_tags'])==1
    assert result['reentry_anchors']['MU']['peak']==120


def test_priority_chooses_mu_reclaim_before_wdc_normal_dip():
    from lab.research.memory_swing import entry_signals
    frames=scenario()
    peer=frames['MU'].copy()
    peer.loc[:'2023-01-06',['open','high','low','close']]=70
    peer.iloc[-9:-4,peer.columns.get_indexer(['open','high','low','close'])]=100
    peer.loc[pd.Timestamp('2023-01-09',tz='UTC')]=[100,110,95,100,100000]
    peer.loc[pd.Timestamp('2023-01-10',tz='UTC')]=[100,110,95,100,100000]
    peer.loc[pd.Timestamp('2023-01-11',tz='UTC')]=[90,95,85,90,100000]
    peer.loc[pd.Timestamp('2023-01-12',tz='UTC')]=[90,100,85,95,100000]
    assert entry_signals(peer).loc[pd.Timestamp('2023-01-11',tz='UTC')]
    result=replay({'WDC':peer,'MU':frames['MU']},'2023-01-09','2023-01-12',1000,reentry_enabled=True)
    assert result['entry_tags'][-1]['ticker']=='MU'
    assert result['entry_tags'][-1]['entry_reason']=='reentry_reclaim'
