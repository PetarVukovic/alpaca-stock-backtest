import pandas as pd
from lab.research.c34_accounts import replay


def fixture():
    dates=pd.bdate_range('2024-01-01',periods=212,tz='UTC')
    close=[80.]*200+[110.]*5+[100.]*7
    f=pd.DataFrame({'open':close,'high':close,'low':close,'close':close,'volume':100000},index=dates)
    return dates,f


def test_fractional_affordability_and_fees():
    dates,f=fixture()
    a=replay({'MU':f},dates,50,fractional=True)
    b=replay({'MU':f},dates,50,fractional=False)
    assert a['events'][0]['side']=='buy' and 0<a['events'][0]['qty']<1
    assert a['events'][0]['fee']==1
    assert not b['events']


def test_signal_executes_next_open_and_gap_exits_at_open():
    dates,f=fixture()
    f.loc[dates[207],['open','high','low','close']]=70.
    a=replay({'MU':f},dates,600,fractional=True)
    assert a['events'][0]['date']==str(dates[206].date())
    t=a['trades'][0]
    assert t['raw_exit']==70 and t['reason']=='gap_stop'
    assert abs(t['exit_price']-69.99)<1e-8


def test_entry_bar_high_does_not_retroactively_raise_stop():
    dates,f=fixture()
    f.loc[dates[206],'high']=150
    f.loc[dates[206],'low']=95
    a=replay({'MU':f},dates[:207],600)
    assert a['open_position'] is not None and not a['trades']


def test_no_trading_before_200_bars():
    dates,f=fixture()
    a=replay({'SNDK':f.iloc[200:]},dates,600,fractional=True)
    assert not a['events']
