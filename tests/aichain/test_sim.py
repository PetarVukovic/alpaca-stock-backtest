"""Mechanics of the AI-chain simulator on tiny synthetic bars."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lab.aichain.contenders import BuyHold, make_rule, swing_levels
from lab.aichain.sim import Bars, Cost, repair_bad_ticks, run_sleeve


def _bars(o: list[float], h: list[float], lo: list[float], c: list[float]) -> Bars:
    dates = pd.bdate_range("2024-01-01", periods=len(o))
    return Bars("T", dates, *(np.array(x, float) for x in (o, h, lo, c)))


def test_buy_hold_fills_first_open_with_cost() -> None:
    b = _bars([10, 11, 12], [11, 12, 13], [9, 10, 11], [10.5, 11.5, 12.5])
    res = run_sleeve(b, BuyHold(), "2024-01-01", "2024-12-31", Cost(bps=10))
    assert res is not None
    assert res.trades[0]["entry_price"] == pytest.approx(10 * 1.001)
    # forced liquidation at the last close pays the exit cost too
    assert res.equity[-1] == pytest.approx(1000 / (10 * 1.001) * 12.5 * 0.999)
    assert res.trades[0]["reason"] == "end"
    assert res.trades[0]["exit_price"] == pytest.approx(12.5 * 0.999)


def test_gap_stop_exits_at_open() -> None:
    class Once(BuyHold):
        def on_fill(self, i, pos):  # type: ignore[no-untyped-def]
            pos.stop = 9.0

    b = _bars([10, 10, 8, 8], [10, 10, 8.5, 8.5], [10, 9.5, 7.5, 7.5], [10, 10, 8, 8])
    res = run_sleeve(b, Once(), "2024-01-01", "2024-12-31", Cost(bps=0))
    stop = res.trades[0]
    assert stop["reason"] == "stop" and stop["detail"] == "gap_stop"
    assert stop["raw_exit"] == 8.0 and stop["exit_date"] == "2024-01-03"


def test_swing_levels_usable_only_after_confirmation() -> None:
    low = np.array([5, 5, 5, 5, 5, 1, 5, 5, 5, 5, 5, 5.0])
    high = low + 1
    sup, _ = swing_levels(high, low, 5)
    assert np.isnan(sup[9]) and sup[10] == 1.0


def test_signal_decisions_do_not_change_when_future_is_cut() -> None:
    rng = np.random.default_rng(1)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.02, 400))
    b = _bars(list(c), list(c * 1.01), list(c * 0.99), list(c))
    for cid in (
        "K2_SMA200_TREND",
        "K3_DONCHIAN_55_20",
        "K4_TSMOM_126",
        "K5_SUPPORT_RESISTANCE",
    ):
        full = run_sleeve(b, make_rule(cid), "2024-01-01", "2030-01-01")
        part = run_sleeve(
            b.cut(b.dates[300]), make_rule(cid), "2024-01-01", "2030-01-01"
        )
        assert part.decisions == full.decisions[: len(part.decisions)]


def test_bad_tick_high_is_clamped_not_dropped() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-06-06", periods=5),
            "open": [100, 101, 102, 103, 104.0],
            "high": [101, 102, 190, 104, 105.0],  # 190 is a print far outside all neighbours
            "low": [99, 100, 101, 102, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
        }
    )
    fixed, notes = repair_bad_ticks(frame)
    assert len(fixed) == 5 and len(notes) == 1 and "high 190" in notes[0]
    assert fixed["high"][2] == pytest.approx(103.5)  # next close is the highest reference
    assert fixed["high"].drop(2).tolist() == frame["high"].drop(2).tolist()


def test_halted_history_is_not_loaded() -> None:
    from lab.aichain.sim import load_bars

    smci = load_bars("SMCI")
    assert str(smci.dates[0].date()) == "2020-01-14"
    nbis = load_bars("NBIS")
    assert str(nbis.dates[0].date()) == "2024-10-21"
    nvda = load_bars("NVDA")
    k = int(np.nonzero(nvda.dates == pd.Timestamp("2024-06-10"))[0][0])
    assert nvda.high[k] < 130 and len(nvda.repairs) == 1


def test_trailing_stop_is_not_raised_by_the_same_bar_high() -> None:
    """A new high only lifts the stop from the next bar, so a same-bar spike cannot stop the position out."""
    from lab.aichain.contenders import trail_stop

    class Trail(BuyHold):
        def on_fill(self, i, pos):  # type: ignore[no-untyped-def]
            pos.stop = trail_stop(pos.peak, 0.10)

        def after_bar(self, i, pos):  # type: ignore[no-untyped-def]
            pos.stop = max(pos.stop, trail_stop(pos.peak, 0.10))

    # bar 1: high 130, low 99 (stop is still 90, not 117) -> held; bar 2: low 95 <= 117 -> stopped at 117, open gap 100 < 117
    b = _bars([100, 100, 100, 100], [100, 130, 100, 100], [100, 99, 95, 95], [100, 100, 98, 98])
    res = run_sleeve(b, Trail(), "2024-01-01", "2030-01-01", Cost(bps=0))
    assert res is not None
    t = res.trades[0]
    assert t["exit_date"] == "2024-01-03" and t["detail"] == "gap_stop"
    assert t["raw_exit"] == 100.0  # open of bar 2, below the 117 stop


def test_array_lookahead_check_catches_a_one_bar_peek() -> None:
    """The strengthened lookahead test must flag a rule whose signal array peeks one bar ahead."""
    from lab.aichain import contenders as C
    from lab.aichain.run import _rule_arrays

    rng = np.random.default_rng(3)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.02, 400))
    b = _bars(list(c), list(c * 1.01), list(c * 0.99), list(c))

    class Peek(C.Tsmom):
        def prepare(self, bars):  # type: ignore[no-untyped-def]
            super().prepare(bars)
            self.entry_arr = np.r_[self.entry_arr[1:], False]

    def differs(cls: type) -> bool:
        full, part = cls(), cls()
        full.prepare(b)
        part.prepare(b.cut(b.dates[300]))
        m = len(b.cut(b.dates[300]))
        return any(
            not np.array_equal(a, _rule_arrays(full)[k][:m])
            for k, a in _rule_arrays(part).items()
        )

    assert not differs(C.Tsmom)
    assert differs(Peek)
