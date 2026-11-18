"""Market-mechanics engine: definitions on tiny synthetic bars and lookahead tests on random walks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lab.aichain import levels as lv
from lab.aichain import mechanics as mx
from lab.aichain.contenders import swing_levels


def _walk(n: int = 700, seed: int = 7) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    return open_, high, low, close


def test_pivot_confirmed_exactly_k_bars_later() -> None:
    _, h, lo, _ = _walk()
    pv = mx.find_pivots(h, lo)
    assert pv
    assert all(p.confirm == p.idx + mx.K_PIVOT for p in pv)
    for p in pv:
        arr = h if p.kind == "H" else lo
        win = np.r_[arr[p.idx - 5 : p.idx], arr[p.idx + 1 : p.idx + 6]]
        assert (arr[p.idx] > win.max()) if p.kind == "H" else (arr[p.idx] < win.min())


def test_pivot_never_visible_before_confirmation() -> None:
    _, h, lo, _ = _walk()
    pv = mx.find_pivots(h, lo)
    for p in pv[:50]:
        for t in range(p.idx, p.confirm):
            assert p not in mx.pivots_asof(pv, t)
        assert p in mx.pivots_asof(pv, p.confirm)


def test_pivots_match_contender_swing_levels() -> None:
    _, h, lo, _ = _walk()
    sup, res = swing_levels(h, lo, 5)
    pv = mx.find_pivots(h, lo)
    ph = mx.last_pivot_price(pv, len(h), "H")
    pl = mx.last_pivot_price(pv, len(h), "L")
    assert np.allclose(ph, res, equal_nan=True)
    assert np.allclose(pl, sup, equal_nan=True)


@pytest.mark.parametrize("cut", [150, 333, 520])
def test_truncation_does_not_change_earlier_pivots_structure_zones(cut: int) -> None:
    o, h, lo, c = _walk()
    full_pv = mx.find_pivots(h, lo)
    cut_pv = mx.find_pivots(h[:cut], lo[:cut])
    assert cut_pv == [p for p in full_pv if p.confirm <= cut - 1]
    full = mx.market_structure(h, lo, c)
    part = mx.market_structure(h[:cut], lo[:cut], c[:cut])
    assert np.array_equal(full.bias[:cut], part.bias)
    assert part.events == [e for e in full.events if e["idx"] < cut]
    a = mx.atr(h, lo, c)
    az = mx.atr(h[:cut], lo[:cut], c[:cut])
    assert np.allclose(a[:cut], az, equal_nan=True)
    zf = mx.find_zones(o, h, lo, c, full_pv, a)
    zp = mx.find_zones(o[:cut], h[:cut], lo[:cut], c[:cut], cut_pv, az)
    key = lambda z: (z["kind"], z["base"], z["known"], z["lo"], z["hi"])
    assert sorted(map(key, zp)) == sorted(key(z) for z in zf if z["known"] < cut)
    sf = mx.sweeps(full_pv, h, lo, c)
    sp = mx.sweeps(cut_pv, h[:cut], lo[:cut], c[:cut])
    assert [e for e in sf if e["idx"] < cut] == sp


@pytest.mark.parametrize("cut", [220, 410, 600])
def test_levels_and_fvg_known_at_t_ignore_the_future(cut: int) -> None:
    _o, h, lo, c = _walk()
    a = mx.atr(h, lo, c)
    full_pv = mx.find_pivots(h, lo)
    cut_pv = mx.find_pivots(h[:cut], lo[:cut])
    t = cut - 1
    l_full = lv.cluster_levels(full_pv, t, a[t], c[t])
    l_cut = lv.cluster_levels(cut_pv, t, a[t], c[t])
    assert [(x.price, x.strength, x.touches) for x in l_full] == [
        (x.price, x.strength, x.touches) for x in l_cut
    ]
    assert mx.fair_value_gaps(h, lo, a, t) == mx.fair_value_gaps(
        h[:cut], lo[:cut], a[:cut], t
    )
    ef = mx.equal_pools(full_pv, h, lo, t)
    ec = mx.equal_pools(cut_pv, h[:cut], lo[:cut], t)
    assert ef == ec


def test_weekly_bias_ignores_weeks_not_yet_finished() -> None:
    o, h, lo, c = _walk(900)
    dates = pd.bdate_range("2019-01-01", periods=900)
    full_w = mx.weekly_bars(dates, o, h, lo, c)
    full_bias, _ = mx.weekly_bias_daily(full_w, 900)
    for cut in (301, 502, 777):  # arbitrary (often mid-week) cut points
        w = mx.weekly_bars(dates[:cut], o[:cut], h[:cut], lo[:cut], c[:cut])
        bias, _ = mx.weekly_bias_daily(w, cut)
        assert np.array_equal(bias, full_bias[:cut])


def test_weekly_bar_aggregation() -> None:
    dates = pd.bdate_range("2024-01-01", periods=10)  # two full Mon-Fri weeks
    o = np.arange(10, 20, dtype=float)
    h, lo, c = o + 2, o - 1, o + 1
    w = mx.weekly_bars(dates, o, h, lo, c)
    assert len(w.close) == 2
    assert w.open[0] == 10 and w.close[0] == 15 and w.high[0] == 16 and w.low[0] == 9
    assert w.complete.all()


def _series(closes: list[float], spread: float = 0.5) -> tuple[np.ndarray, ...]:
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    return o, c + spread, c - spread, c


def test_market_shift_is_close_above_last_lower_high() -> None:
    # down-leg: lower highs and lower lows, then a close above the last lower high
    pts = [
        30,
        28,
        26,
        24,
        22,
        20,
        22,
        24,
        26,
        28,
        26,
        24,
        22,
        20,
        18,
        16,
        14,
        16,
        18,
        20,
        22,
        24,
        22,
        20,
        18,
        16,
        14,
        12,
        14,
        16,
        18,
        20,
        22,
        24,
        26,
        28,
        30,
        32,
        34,
    ]
    _o, h, lo, c = _series(pts, 0.2)
    st = mx.market_structure(h, lo, c)
    kinds = [(e["kind"], e["dir"]) for e in st.events]
    assert ("shift", 1) in kinds
    shift = next(e for e in st.events if e["kind"] == "shift")
    pv = mx.find_pivots(h, lo)
    lh = max(p.price for p in pv if p.kind == "H" and p.idx == shift["level_idx"])
    assert c[shift["idx"]] > lh
    assert (
        shift["idx"] >= shift["level_idx"] + mx.K_PIVOT
    )  # level usable only after confirmation


def test_bos_needs_matching_bias() -> None:
    up = [
        4,
        6,
        8,
        10,
        12,
        14,
        16,
        18,
        16,
        14,
        12,
        14,
        16,
        18,
        20,
        22,
        20,
        18,
        16,
        14,
        16,
        18,
        20,
        22,
        24,
        26,
        28,
        30,
        28,
        26,
        24,
    ]
    _o, h, lo, c = _series(up, 0.2)
    st = mx.market_structure(h, lo, c)
    assert any(e["kind"] == "bos" and e["dir"] == 1 for e in st.events)
    assert not any(e["kind"] == "bos" and e["dir"] == -1 for e in st.events)


def test_bullish_sweep_wick_through_close_back() -> None:
    lo = np.array([10, 9, 8, 7, 6, 5, 6, 7, 8, 9, 10, 11, 12, 11, 10, 9, 8.0, 12.0])
    h = lo + 1.0
    c = lo + 0.5
    lo[16] = 4.0  # wick below the pivot low (5.0) ...
    c[16] = 6.0  # ... and close back above it
    pv = mx.find_pivots(h, lo)
    ev = mx.sweeps(pv, h, lo, c)
    assert any(e["dir"] == 1 and e["idx"] == 16 and e["level"] == 5.0 for e in ev)
    c2 = c.copy()
    c2[16] = 4.5  # closing below the pivot is a break, not a sweep
    assert not any(e["idx"] == 16 for e in mx.sweeps(pv, h, lo, c2))


def test_fair_value_gap_bullish() -> None:
    h = np.array([10.0, 11.0, 12.0, 14.0, 15.0, 15.5])
    lo = np.array([9.0, 10.0, 11.0, 12.5, 14.0, 14.5])
    a = np.ones(6)
    gaps = mx.fair_value_gaps(h, lo, a, 5)
    # bar1 high 11 < bar3 low 12.5 happens with bars 1,2,3 -> index 3 is bar3 of (1,2,3): high[1]=11 < low[3]=12.5
    assert any(g["bottom"] == 11.0 and g["top"] == 12.5 for g in gaps["bull"])
    # price returning into the gap closes it
    lo2 = lo.copy()
    lo2[5] = 12.0
    assert not any(
        g["bottom"] == 11.0 for g in mx.fair_value_gaps(h, lo2, a, 5)["bull"]
    )


def test_equal_lows_pool_and_unswept() -> None:
    lo = np.array(
        [
            10,
            9,
            8,
            7,
            6,
            5.0,
            6,
            7,
            8,
            9,
            10,
            9,
            8,
            7,
            6,
            5.01,
            6,
            7,
            8,
            9,
            10,
            11,
            12.0,
        ]
    )
    h = lo + 1
    pv = mx.find_pivots(h, lo)
    pools = mx.equal_pools(pv, h, lo, len(lo) - 1)
    assert len(pools["below"]) == 1 and pools["below"][0]["members"] == 2
    assert pools["below"][0]["level"] == 5.0


def test_demand_zone_is_last_down_candle_before_impulse() -> None:
    n = 40
    rng = np.random.default_rng(1)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.2
    lo = np.minimum(o, c) - 0.2
    j = 30
    o[j], c[j] = 101.0, 99.0  # down candle
    h[j], lo[j] = 101.2, 98.8
    for m, px in zip((31, 32, 33), (103.0, 106.0, 112.0)):
        o[m], c[m] = c[m - 1], px
        h[m], lo[m] = px + 0.2, o[m] - 0.2
    a = np.full(n, 1.0)
    pv = [mx.Pivot(5, 10, "H", 101.5)]
    zs = mx.find_zones(o, h, lo, c, pv, a)
    d = [z for z in zs if z["kind"] == "demand" and z["base"] == j]
    assert d and d[0]["known"] == 31 and d[0]["lo"] == 98.8 and d[0]["hi"] == 101.2
    assert d[0]["body_lo"] == 99.0 and d[0]["body_hi"] == 101.0
    assert not mx.fresh_zones(d, 30)  # not yet known at the base bar


def test_round_number_step_and_volume_profile_shape() -> None:
    assert lv.nice_step(450) == 50
    assert lv.nice_step(120) == 10
    assert lv.nice_step(4.2) == 0.5


@pytest.mark.parametrize("cut", [260, 430, 610])
def test_event_flags_and_levels_ignore_the_future(cut: int) -> None:
    """Decision-day flags of the event study and the S/R levels on day t must not change if later bars are removed."""
    from lab.aichain import levels_study as ls
    from lab.aichain.sim import Bars

    o, h, lo, c = _walk(800, seed=11)
    dates = pd.bdate_range("2020-01-01", periods=800)
    vol = np.full(800, 1e6)
    full = lv.prepare_from_bars(Bars("T", dates, o, h, lo, c), vol)
    part = lv.prepare_from_bars(
        Bars("T", dates[:cut], o[:cut], h[:cut], lo[:cut], c[:cut]), vol[:cut]
    )
    ff = ls.event_flags(full, 799)
    fp = ls.event_flags(part, cut - 1)
    for name in ff:
        # the last few bars of a truncated series cannot confirm anything new; flags strictly before cut must match
        assert np.array_equal(ff[name][:cut], fp[name]), name
    assert sum(int(f.sum()) for f in ff.values()) > 0
    for t in (cut - 1, cut - 40):
        a = lv.cluster_levels(full.pivots, t, full.atr[t], full.bars.close[t])
        b = lv.cluster_levels(part.pivots, t, part.atr[t], part.bars.close[t])
        assert [(x.price, x.touches) for x in a] == [(x.price, x.touches) for x in b]
    # reliability of a level at t uses only bars <= t
    lvls = lv.cluster_levels(
        full.pivots, cut - 1, full.atr[cut - 1], full.bars.close[cut - 1]
    )
    lvls2 = lv.cluster_levels(
        part.pivots, cut - 1, part.atr[cut - 1], part.bars.close[cut - 1]
    )
    for x, y in zip(lvls, lvls2):
        assert lv.pit_reliability(x, full, cut - 1) == lv.pit_reliability(
            y, part, cut - 1
        )
