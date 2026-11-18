"""Swing-frequency contenders: simulator parity, partial exit, causality and metrics on synthetic bars."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd
import pytest

from lab.aichain import contenders as C
from lab.aichain import swing as S
from lab.aichain.sim import Bars, Cost, run_sleeve


def _walk(
    n: int = 900, seed: int = 7, vol: float = 0.02, start: str = "2018-01-01"
) -> Bars:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, vol, n))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)))
    return Bars("T", pd.bdate_range(start, periods=n), open_, high, low, close)


def _bars(o: list[float], h: list[float], lo: list[float], c: list[float]) -> Bars:
    dates = pd.bdate_range("2024-01-01", periods=len(o))
    return Bars("T", dates, *(np.array(x, float) for x in (o, h, lo, c)))


def _trade_key(t: dict[str, Any]) -> tuple[Any, ...]:
    return (
        t["entry_date"],
        t["exit_date"],
        round(t["entry_price"], 9),
        round(t["exit_price"], 9),
        t["reason"],
    )


@pytest.mark.parametrize(
    "make",
    [
        lambda: C.C13C(),
        lambda: C.BreakoutRetest(),
        lambda: C.SupportResistance(),
        lambda: C.BuyHold(),
    ],
)
def test_swing_runner_equals_sim_runner_without_partial_exit(make: Any) -> None:
    bars = _walk(1500, vol=0.025)
    a = run_sleeve(bars, make(), "2020-01-01", "2030-01-01", Cost(bps=2.5))
    b = S.run_swing_sleeve(bars, make(), "2020-01-01", "2030-01-01", Cost(bps=2.5))
    assert a is not None and b is not None
    np.testing.assert_allclose(a.equity, b.equity, rtol=1e-12)
    assert [_trade_key(t) for t in a.trades] == [_trade_key(t) for t in b.trades]
    assert a.decisions == b.decisions


def test_partial_exit_sells_half_at_target_and_blends_the_return() -> None:
    class Half(S.SwingRule):
        id = "H"
        DEFAULTS: ClassVar[dict[str, Any]] = {"max_bars": 99}

        def prepare(self, bars: Bars) -> None:
            self.entry_arr = np.array([True] + [False] * (len(bars) - 1))

        def on_fill(self, i: int, pos: Any) -> None:
            pos.target = 120.0
            pos.stop = 80.0
            pos.extra["partial"] = 0.5

    # bar1 fills at 100; bar2 high 125 hits the target (half sold at 120); bar3 low 79 stops the rest at 80
    b = _bars(
        [100, 100, 110, 100],
        [100, 105, 125, 101],
        [100, 99, 105, 79],
        [100, 102, 115, 90],
    )
    res = S.run_swing_sleeve(b, Half(), "2024-01-01", "2030-01-01", Cost(bps=0))
    assert res is not None and len(res.trades) == 1
    t = res.trades[0]
    assert t["partial"] and t["reason"] == "stop"
    assert t["return"] == pytest.approx((0.5 * 120 + 0.5 * 80) / 100 - 1)
    assert res.equity[-1] == pytest.approx(1000 * (0.5 * 1.2 + 0.5 * 0.8))
    assert t["pnl_eur"] == pytest.approx(0.0)


def test_pivots_are_usable_only_k_bars_after_they_formed() -> None:
    low = np.array([5, 5, 5, 5, 5, 1, 5, 5, 5, 5, 5, 5.0])
    highs, lows = S.pivot_lists(low + 1, low, 5)
    assert lows == [(10, 5, 1.0)] and highs == []


def test_weekly_sma_uses_only_completed_weeks_and_current_close() -> None:
    bars = _walk(120)
    full = S.weekly_sma(bars, 10)
    part = S.weekly_sma(bars.cut(bars.dates[70]), 10)
    np.testing.assert_allclose(part, full[:71], rtol=1e-12, equal_nan=True)


def test_ibs_entry_and_exit_flags() -> None:
    n = 260
    close = np.linspace(100, 160, n)
    low = close - 2
    high = close + 2
    close = close.copy()
    close[240] = low[240] + 0.1  # IBS ~ 0.025 inside an uptrend
    b = Bars("T", pd.bdate_range("2020-01-01", periods=n), close, high, low, close)
    r = S.IbsRevert()
    r.prepare(b)
    assert r.entry_arr[240] and r.entry_arr.sum() == 1


def test_mom_break_stop_is_eight_percent_under_raw_entry() -> None:
    bars = _walk(400, seed=3, vol=0.03)
    res = S.run_swing_sleeve(
        bars, S.make_rule("W2_MOM_BREAK_20"), "2019-06-01", "2030-01-01", Cost(bps=0)
    )
    assert res is not None
    stops = [t for t in res.trades if t["reason"] == "stop"]
    for t in stops:
        if t["detail"] == "stop":
            assert t["raw_exit"] == pytest.approx(t["raw_entry"] * 0.92)
        else:
            assert t["raw_exit"] < t["raw_entry"] * 0.92


def test_rank_weekly_decides_only_on_decision_weekday_and_ranks_by_return() -> None:
    dates = pd.bdate_range("2021-01-01", periods=200)

    def mk(t: str, drift: float) -> Bars:
        c = 100 * np.cumprod(1 + np.full(200, drift))
        return Bars(t, dates, c, c * 1.01, c * 0.99, c)

    peers = {"A": mk("A", 0.003), "B": mk("B", 0.001), "C": mk("C", -0.001)}
    rule = S.make_rule("W3_MOM_RANK_WEEKLY", peers=peers)
    rule.prepare(peers["A"])
    assert rule.decision_arr.sum() > 0
    assert all(
        peers["A"].dates[i].weekday() == 4 for i in np.nonzero(rule.decision_arr)[0]
    )
    ok = ~np.isnan(rule.rank_arr)
    assert (rule.rank_arr[ok] == 1).all() and (rule.count_arr[ok] == 3).all()
    warm = ok & (np.arange(200) >= 60)
    assert rule.entry_arr[warm].all()
    loser = S.make_rule("W3_MOM_RANK_WEEKLY", peers=peers)
    loser.prepare(peers["C"])
    ok = ~np.isnan(loser.rank_arr)
    assert (
        (loser.rank_arr[ok] == 3).all()
        and loser.exit_arr[ok].all()
        and not loser.entry_arr[ok].any()
    )


def _arrays(rule: Any) -> dict[str, np.ndarray]:
    return {
        k: v for k, v in vars(rule).items() if isinstance(v, np.ndarray) and v.ndim == 1
    }


@pytest.mark.parametrize("cid", S.SINGLE_IDS)
def test_every_contender_is_causal_on_truncated_data(cid: str) -> None:
    bars = _walk(1200, seed=11, vol=0.025)
    peers = {"A": bars, "B": _walk(1200, seed=12), "C": _walk(1200, seed=13)}
    full = S.make_rule(cid, peers=peers)
    full.prepare(bars)
    fa = _arrays(full)
    for cut in (400, 650, 900, 1100):
        part_bars = bars.cut(bars.dates[cut])
        part = S.make_rule(cid, peers=peers)
        part.prepare(part_bars)
        m = len(part_bars)
        for name, arr in _arrays(part).items():
            ref = fa[name]
            if len(ref) != len(bars):
                continue
            assert np.allclose(arr, ref[:m], rtol=1e-12, atol=0, equal_nan=True), (
                cid,
                name,
                cut,
            )


def test_causality_check_would_catch_a_peek() -> None:
    bars = _walk(600)
    base = S.MomBreak()
    base.prepare(bars)
    first = int(np.nonzero(base.entry_arr)[0][0])

    class Peek(S.MomBreak):
        def prepare(self, b: Bars) -> None:
            super().prepare(b)
            self.entry_arr = np.r_[self.entry_arr[1:], False]

    full, part = Peek(), Peek()
    full.prepare(bars)
    part.prepare(bars.cut(bars.dates[first - 1]))
    assert not np.array_equal(part.entry_arr, full.entry_arr[:first])


def test_contenders_produce_trades_on_a_noisy_series() -> None:
    bars = _walk(2500, seed=21, vol=0.03)
    peers = {"A": bars, "B": _walk(2500, seed=22, vol=0.03)}
    counts = {}
    for cid in S.SINGLE_IDS:
        res = S.run_swing_sleeve(
            bars, S.make_rule(cid, peers=peers), "2018-06-01", "2030-01-01"
        )
        assert res is not None
        counts[cid] = len(res.trades)
    assert counts["W2_MOM_BREAK_20"] > 0 and counts["W8_IBS_REVERT"] > 0
    assert sum(1 for v in counts.values() if v > 0) >= 6, counts


def test_perturbations_cover_every_threshold_and_are_distinct() -> None:
    for cid in S.SINGLE_IDS:
        keys = S.CONTENDERS[cid]["perturb"]
        got = S.perturbed(cid)
        assert {k for k, _, _ in got} <= set(keys)
        base = S.CONTENDERS[cid]["cls"].DEFAULTS
        assert all(v != base[k] for k, _, v in got)


def test_trade_metrics_basic_values() -> None:
    def tr(entry: str, exit_: str, ret: float) -> dict[str, Any]:
        return {"entry_date": entry, "exit_date": exit_, "return": ret}

    trades = [
        tr("2024-01-01", "2024-01-05", 0.10),
        tr("2024-01-06", "2024-01-10", -0.05),
        tr("2024-01-11", "2024-01-21", -0.05),
        tr("2024-01-22", "2024-01-26", 0.05),
    ]
    m = S.trade_metrics(trades, months=2.0, sleeve_years=0.5)
    assert m["trades"] == 4 and m["trades_per_month"] == pytest.approx(2.0)
    assert m["trades_per_ticker_year"] == pytest.approx(8.0)
    assert m["hit_rate"] == 0.5
    assert m["expectancy_eur"] == pytest.approx(25.0 * 0.5 * 0 + 1000 * 0.0125)
    assert m["profit_factor"] == pytest.approx(0.15 / 0.10)
    assert m["longest_losing_streak"] == 2
    assert m["median_hold_days"] == pytest.approx(4.0)
    assert m["top5_profit_share"] == pytest.approx(
        1.0
    )  # all four trades, net 50 EUR; top5 sum equals net total
    assert S.trade_metrics([], 1.0, 1.0)["expectancy_eur"] is None
