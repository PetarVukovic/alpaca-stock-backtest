import numpy as np
import pandas as pd
import pytest
from scripts.audit_random_swing import calibrated_probabilities, random_pattern, patched_signals, distribution
from lab.research import memory_swing as engine


def frame():
    dates=pd.bdate_range('2016-01-04','2024-12-31',tz='UTC')
    close=100+np.arange(len(dates))*.08+10*np.sin(np.arange(len(dates))*.35)
    result=pd.DataFrame({'close':close},index=dates);result.attrs['symbol']='MU'
    return result


def test_calibration_ignores_future_and_random_is_prefix_stable():
    data=frame();calibration,eligible,trend=calibrated_probabilities(data)
    changed=data.copy();changed.loc['2021':,'close']*=100
    assert calibrated_probabilities(changed)[0]==calibration
    pattern=random_pattern(data,'MU',20261006,'trend_conditional',calibration)
    prefix=random_pattern(data.iloc[:1500],'MU',20261006,'trend_conditional',calibration)
    assert pattern.iloc[:1500].equals(prefix)
    assert not pattern.iloc[:199].any()
    assert not (pattern & ~trend).any()
    assert not pattern.equals(random_pattern(data,'MU',20261007,'trend_conditional',calibration))
    assert not pattern.equals(random_pattern(data,'WDC',20261006,'trend_conditional',calibration))


def test_signal_patch_restores_after_exception():
    data=frame();original=engine.entry_signals
    patterns={'MU':pd.Series(False,index=data.index)}
    with pytest.raises(RuntimeError):
        with patched_signals(patterns):
            assert not engine.entry_signals(data.copy()).any()
            raise RuntimeError('synthetic')
    assert engine.entry_signals is original


def test_rank_ties_and_smoothed_tail():
    stats=distribution([1,2,2,3],2)
    assert stats['observed_percentile']==50
    assert stats['smoothed_upper_tail']==.8
