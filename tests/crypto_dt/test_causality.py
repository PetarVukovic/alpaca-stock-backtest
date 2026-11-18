"""Causality tests for lab.crypto_dt: truncating the future must never change a past value."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lab.crypto_dt import data, features


def synthetic_hourly(days: int = 400, seed: int = 0, tickers=("AAAUSDT", "BBBUSDT")) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2022-01-01", periods=days * 24, freq="h")
    frames = {}
    for t in tickers:
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, len(index))))
        open_ = np.concatenate([[close[0]], close[:-1]])
        frames[t] = pd.DataFrame(
            {
                "open": open_,
                "high": np.maximum(open_, close) * 1.002,
                "low": np.minimum(open_, close) * 0.998,
                "close": close,
                "volume": rng.uniform(1, 10, len(index)),
            },
            index=index,
        )
    return frames


def panel_of(frames):
    return {f: pd.DataFrame({t: fr[f] for t, fr in frames.items()}) for f in ("open", "high", "low", "close", "volume")}


def test_resample_drops_incomplete_buckets_and_keeps_ohlc():
    frame = synthetic_hourly(days=3, tickers=("AAAUSDT",))["AAAUSDT"]
    frame = frame.drop(frame.index[5])  # hour 05:00 missing -> the 04:00 bucket is incomplete
    out = data.resample_ohlcv(frame, 4)
    assert pd.Timestamp("2022-01-01 04:00") not in out.index
    first = out.loc[pd.Timestamp("2022-01-01 00:00")]
    block = frame.iloc[:4]
    assert first["open"] == block["open"].iloc[0]
    assert first["close"] == block["close"].iloc[-1]
    assert first["high"] == block["high"].max()
    assert first["low"] == block["low"].min()
    assert first["volume"] == pytest.approx(block["volume"].sum())


def test_known_asof_respects_lag_and_gap_tolerance():
    series = pd.Series([1.0, 2.0], index=pd.to_datetime(["2022-01-01 10:00", "2022-01-01 10:05"]))
    decision = pd.DatetimeIndex(["2022-01-01 10:00", "2022-01-01 10:05", "2022-01-01 10:09", "2022-01-01 11:00"])
    got = features.known_asof(series, decision, features.METRICS_LAG, features.METRICS_TOLERANCE)
    assert np.isnan(got.iloc[0])  # the 10:00 snapshot is not usable at 10:00
    assert got.iloc[1] == 1.0  # usable from 10:05
    assert got.iloc[2] == 1.0  # 10:05 snapshot only from 10:10
    assert np.isnan(got.iloc[3])  # older than tolerance -> no carry across the gap


def test_donchian_state_ignores_future_bars():
    pan = panel_of(synthetic_hourly(days=60))
    full = features.donchian_state(pan["high"], pan["low"], pan["close"], 20, 10)
    cut = pan["close"].index[700]
    part = features.donchian_state(
        pan["high"].loc[:cut], pan["low"].loc[:cut], pan["close"].loc[:cut], 20, 10
    )
    pd.testing.assert_frame_equal(part, full.loc[:cut])


def test_donchian_enters_on_breakout_and_exits_below_prior_lows():
    index = pd.date_range("2022-01-01", periods=8, freq="4h")
    close = pd.DataFrame({"X": [10, 10, 10, 12, 12, 12, 7, 7.0]}, index=index)
    high, low = close * 1.0, close * 1.0
    state = features.donchian_state(high, low, close, 3, 2)
    assert state["X"].tolist() == [0, 0, 0, 1, 1, 1, 0, 0]


def test_trend_weights_are_long_only_capped_and_causal():
    pan = panel_of(synthetic_hourly(days=120))
    params = dict(n_fast=20, n_mid=40, n_slow=80, exit_ratio=0.5, vol_window=90, sigma_target=0.5)
    full = features.trend_weights(pan, params, 8760)
    assert (full >= 0).all().all() and (full.sum(axis=1) <= 1 + 1e-9).all()
    cut = pan["close"].index[1500]
    trimmed = {k: v.loc[:cut] for k, v in pan.items()}
    pd.testing.assert_frame_equal(features.trend_weights(trimmed, params, 8760), full.loc[:cut])


def test_window_returns_known_only_after_window_ends():
    frames = synthetic_hourly(days=5, tickers=("AAAUSDT",))
    open_ = panel_of(frames)["open"]
    got = features.window_returns(open_, 21, 2)
    day = pd.Timestamp("2022-01-02")
    expected = open_.loc[day + pd.Timedelta(hours=23), "AAAUSDT"] / open_.loc[day + pd.Timedelta(hours=21), "AAAUSDT"] - 1
    assert got.loc[day, "AAAUSDT"] == pytest.approx(expected)


def patch_derivs(monkeypatch, funding, metrics, cut=None):
    f = funding if cut is None else funding.loc[:cut]
    m = metrics if cut is None else metrics.loc[:cut]
    monkeypatch.setattr(data, "load_funding", lambda s: f)
    monkeypatch.setattr(data, "load_metrics", lambda s: m)


def synthetic_derivs(days: int = 400, seed: int = 1):
    rng = np.random.default_rng(seed)
    f_index = pd.date_range("2022-01-01", periods=days * 3, freq="8h")
    funding = pd.Series(rng.normal(0.0001, 0.0002, len(f_index)), index=f_index)
    m_index = pd.date_range("2022-01-01", periods=days * 288, freq="5min")
    oi = pd.Series(1e5 * np.exp(np.cumsum(rng.normal(0, 0.0015, len(m_index)))), index=m_index)
    return funding, pd.DataFrame({"oi": oi, "oi_value": oi})


PARAMS = dict(funding_win=30, funding_pct=0.9, oi_chg_bars=6, oi_pct=0.8, oi_win_days=20)


def test_crowd_gate_never_uses_future_derivatives(monkeypatch):
    funding, metrics = synthetic_derivs()
    index = pd.date_range("2022-01-01", periods=400 * 6, freq="4h")
    patch_derivs(monkeypatch, funding, metrics)
    full = features.crowd_gate(index, ["X"], PARAMS, 4)
    assert full["X"].any(), "test data must exercise the gate"
    cut = index[1800]
    patch_derivs(monkeypatch, funding, metrics, cut=cut + pd.Timedelta(hours=4))  # derivs end at the decision time
    part = features.crowd_gate(index[index <= cut], ["X"], PARAMS, 4)
    pd.testing.assert_frame_equal(part, full.loc[:cut])


def test_crowd_gate_is_inactive_without_history(monkeypatch):
    funding, metrics = synthetic_derivs(days=10)
    index = pd.date_range("2022-01-01", periods=10 * 6, freq="4h")
    patch_derivs(monkeypatch, funding, metrics)
    short = dict(PARAMS, oi_win_days=400)
    assert not features.crowd_gate(index, ["X"], short, 4)["X"].any()


def strategy_panel(days: int = 300):
    return panel_of(synthetic_hourly(days=days, tickers=("BTCUSDT", "ETHUSDT", "SOLUSDT")))


@pytest.mark.parametrize("module_name", ["cdt_h3_utc2123_cond", "cdt_h4_id_mom_vol"])
def test_hourly_window_strategies_are_causal_and_only_hold_their_hours(module_name):
    import importlib

    module = importlib.import_module(f"lab.crypto_dt.strategies.{module_name}")
    pan = strategy_panel()
    params = dict(module.PARAMS, min_trailing_bps=-1e6) if "min_trailing_bps" in module.PARAMS else dict(module.PARAMS, vol_pct=0.0)
    full = module.weights(pan, params)
    assert full.sum().sum() > 0, "test data must exercise the rule"
    assert (full.sum(axis=1) <= 1 + 1e-9).all() and (full >= 0).all().all()
    held_hours = set(full.index[full.sum(axis=1) > 0].hour)
    expected = {20, 21} if module_name == "cdt_h3_utc2123_cond" else {21, 22}
    assert held_hours <= expected
    cut = pan["close"].index[24 * 200 + 5]
    trimmed = {k: v.loc[:cut] for k, v in pan.items()}
    pd.testing.assert_frame_equal(module.weights(trimmed, params), full.loc[:cut])


def test_lead_lag_holds_exactly_three_bars_and_never_holds_btc():
    from lab.crypto_dt.strategies import cdt_h5_btc_lead_5m as h5

    index = pd.date_range("2022-01-01", periods=1200, freq="5min")
    rng = np.random.default_rng(3)
    base = np.exp(np.cumsum(rng.normal(0, 0.001, (len(index), 3)), axis=0)) * 100
    close = pd.DataFrame(base, index=index, columns=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    close.iloc[700, 0] = close.iloc[699, 0] * 1.05  # one big BTC jump, alts flat
    close.iloc[700, 1:] = close.iloc[699, 1:].to_numpy()
    pan = {"close": close, "open": close, "high": close, "low": close, "volume": close * 0 + 1}
    w = h5.weights(pan, h5.PARAMS)
    assert (w["BTCUSDT"] == 0).all()
    on = w["ETHUSDT"][w["ETHUSDT"] > 0].index
    assert len(on) >= 3 and w["ETHUSDT"].loc[index[700]] == 0.5
    assert w.sum(axis=1).max() <= 1 + 1e-9
    assert w["ETHUSDT"].loc[index[700] : index[702]].eq(0.5).all()
    cut = index[800]
    pd.testing.assert_frame_equal(h5.weights({k: v.loc[:cut] for k, v in pan.items()}, h5.PARAMS), w.loc[:cut])


def test_engine_charges_costs_and_fills_at_next_open():
    from lab.top10 import core

    index = pd.date_range("2022-01-01", periods=6, freq="4h")
    opens = pd.DataFrame({"BTCUSDT": [100.0, 100, 100, 110, 110, 110]}, index=index)
    pan = {"open": opens, "close": opens, "high": opens, "low": opens, "volume": opens * 0 + 1}
    w = pd.DataFrame({"BTCUSDT": [0.0, 1.0, 0, 0, 0, 0]}, index=index)  # decided at the close of bar 1
    bt = core.backtest(w, pan, 1.0)
    assert bt["gross"].iloc[1] == 0  # the decision bar itself earns nothing
    assert bt["gross"].iloc[2] == pytest.approx(0.10)  # bought at the open of bar 2, earns open3/open2 - 1
    assert bt["net"].sum() < bt["gross"].sum()  # costs are charged


def test_runner_plumbing_on_synthetic_data(tmp_path):
    """evaluate + prereg block + charts run end to end on random walks (no real data, no ledger, no freeze)."""
    from unittest import mock

    from lab.crypto_dt import run
    from lab.crypto_dt.strategies import cdt_h1_trend_4h as h1
    from lab.top10 import core
    from lab.top10.charts import make_charts

    rng = np.random.default_rng(5)
    index = pd.date_range("2020-09-01", "2026-10-09", freq="4h")
    frames = {}
    for t in h1.UNIVERSE:
        close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(index))))
        open_ = np.concatenate([[close[0]], close[:-1]])
        frames[t] = pd.DataFrame(
            {"open": open_, "high": np.maximum(open_, close) * 1.003, "low": np.minimum(open_, close) * 0.997,
             "close": close, "volume": rng.uniform(1, 9, len(index))},
            index=index,
        )
    with mock.patch.object(core, "load_frames", lambda tickers, cutoff=core.CUTOFF, timeframe="1d": frames):
        summary, bundle = core.evaluate(h1, 518)
    block = run.prereg_block(h1, summary, bundle)
    assert block["verdict"] in {"ZELENO", "ŽUTO", "CRVENO"}
    assert set(block["trade_counts"]) == {"IS", "WF", "HO"}
    assert len(block["neighbours"]) == 2 * len(run._numeric_keys(h1.PARAMS))
    summary["charts"] = make_charts(summary, bundle, tmp_path)
    assert list(tmp_path.glob("*.png"))


def test_quantile_gate_fires_on_tied_funding_and_is_causal(monkeypatch):
    """Codex finding: with all-equal funding the value equals its 95th percentile (gate true), a rank would not."""
    from lab.crypto_dt.strategies import cdt_h2q_trend_4h_crowd_qtl as h2q

    funding, metrics = synthetic_derivs()
    funding = funding * 0 + 0.0001  # every settlement identical
    index = pd.date_range("2022-01-01", periods=400 * 6, freq="4h")
    patch_derivs(monkeypatch, funding, metrics)
    full = h2q.crowd_gate_quantile(index, ["X"], PARAMS)
    rank_based = features.crowd_gate(index, ["X"], PARAMS, 4)
    assert full["X"].sum() > 0 and rank_based["X"].sum() == 0
    cut = index[1800]
    patch_derivs(monkeypatch, funding, metrics, cut=cut + pd.Timedelta(hours=4))
    part = h2q.crowd_gate_quantile(index[index <= cut], ["X"], PARAMS)
    pd.testing.assert_frame_equal(part, full.loc[:cut])


def test_oi_snapshot_older_than_15_minutes_is_not_used():
    from lab.crypto_dt.strategies import cdt_h2q_trend_4h_crowd_qtl as h2q

    series = pd.Series([1.0], index=pd.to_datetime(["2022-01-01 10:00"]))
    got = features.known_asof(series, pd.DatetimeIndex(["2022-01-01 10:15", "2022-01-01 10:20"]), features.METRICS_LAG, h2q.OI_TOLERANCE)
    assert got.iloc[0] == 1.0  # raw age 15 min: still allowed
    assert np.isnan(got.iloc[1])  # raw age 20 min: rejected (the original gate allowed it)
