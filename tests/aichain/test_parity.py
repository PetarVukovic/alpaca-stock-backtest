"""Parity of the AI-chain simulator (K1) with the original C13C replay in lab/research/memory_swing.py."""

from __future__ import annotations

import pandas as pd
import pytest

import lab  # noqa: F401  (installs the app.backend alias used by the original)
from lab.aichain.contenders import make_rule
from lab.aichain.sim import COMMON_END, Cost, load_bars, run_sleeve
from lab.research.memory_swing import replay

WINDOWS = [
    ("2016-01-01", COMMON_END),
    ("2023-01-01", COMMON_END),
    ("2021-03-01", "2022-12-31"),
]


def _frame(ticker: str) -> pd.DataFrame:
    raw = pd.read_csv(f"data/ohlcv/{ticker}_1d.csv", parse_dates=["date"])
    frame = raw.set_index("date")[["open", "high", "low", "close", "volume"]]
    frame.index = frame.index.tz_localize("UTC")
    return frame.loc[:COMMON_END]


@pytest.mark.parametrize("ticker", ["MU", "WDC", "STX"])
@pytest.mark.parametrize("start,end", WINDOWS)
def test_k1_matches_original(ticker: str, start: str, end: str) -> None:
    original = replay(
        {ticker: _frame(ticker)}, start, end, capital=1e9, sizing="one", cap=1e9
    )
    mine = run_sleeve(
        load_bars(ticker),
        make_rule("K1_C13C_ORIG"),
        start,
        end,
        Cost(bps=2.5, tick=0.01),
    )
    assert original is not None and mine is not None
    closed = [t for t in mine.trades if t["reason"] != "end"]
    assert len(closed) == len(original["trades"])
    for a, b in zip(closed, original["trades"], strict=True):
        assert a["entry_date"] == b["entry_date"]
        assert a["exit_date"] == b["exit_date"]
        assert a["entry_price"] == pytest.approx(b["entry_price"], abs=1e-9)
        assert a["exit_price"] == pytest.approx(b["exit_price"], abs=1e-9)
        assert a["raw_exit"] == pytest.approx(b["raw_exit"], abs=1e-9)
        assert a["detail"] == b["reason"]  # stop or gap_stop
    open_mine = [t for t in mine.trades if t["reason"] == "end"]
    open_orig = original["open_position"]
    assert len(open_mine) == (1 if open_orig else 0)
    if open_orig:
        assert open_mine[0]["entry_date"] == open_orig["entry_date"]
        assert open_mine[0]["entry_price"] == pytest.approx(
            open_orig["entry_price"], abs=1e-9
        )
    assert len(mine.trades) >= 1
