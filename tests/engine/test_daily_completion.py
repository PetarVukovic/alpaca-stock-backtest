from datetime import datetime
import os

import pandas as pd
import pytest

from scripts import validate_data as validator


@pytest.mark.parametrize("day,close", [("2026-10-05", "2026-10-05T20:00:00+00:00"),
                                      ("2026-01-05", "2026-01-05T21:00:00+00:00")])
def test_completion_respects_new_york_dst(day, close):
    end = datetime.fromisoformat(close)
    assert validator.daily_completion_issue(day, end, end) is None
    before = end.replace(minute=0, hour=end.hour - 1)
    assert "mtime" in validator.daily_completion_issue(day, before, end)
    assert "not reached" in validator.daily_completion_issue(day, end, before)


def test_completion_requires_timezone_and_is_conservative_on_early_close():
    with pytest.raises(ValueError):
        validator.daily_completion_issue("2026-10-05", datetime(2026, 10, 6), datetime(2026, 10, 6))
    early = datetime.fromisoformat("2025-11-28T18:30:00+00:00")
    later = datetime.fromisoformat("2025-11-29T00:00:00+00:00")
    assert "mtime" in validator.daily_completion_issue("2025-11-28", early, later)


def test_cutoff_excludes_unfinished_bar_without_mutating_source(tmp_path, monkeypatch):
    path = tmp_path / "MU_1d.csv"
    pd.DataFrame({"date": ["2026-10-02", "2026-10-05"], "open": [100, 100],
                  "high": [101, 101], "low": [99, 99], "close": [100, 100],
                  "volume": [1000, 1000]}).to_csv(path, index=False)
    timestamp = datetime.fromisoformat("2026-10-05T16:49:20+00:00").timestamp()
    os.utime(path, (timestamp, timestamp))
    original = path.read_bytes()
    monkeypatch.setattr(validator, "DAILY_DIR", tmp_path)
    now = datetime.fromisoformat("2026-10-06T21:00:00+00:00")
    full = validator.Findings()
    validator.check_daily("MU", full, set(), [], as_of=now)
    assert any("mtime" in e for e in full.errors)
    safe = validator.Findings()
    frame = validator.check_daily("MU", safe, set(), [], through="2026-10-02", as_of=now)
    assert not safe.errors
    assert frame.date.tolist() == ["2026-10-02"]
    assert safe.info
    assert path.read_bytes() == original


def test_empty_cutoff_is_error_not_index_crash(tmp_path, monkeypatch):
    pd.DataFrame(columns=validator.DAILY_COLS).to_csv(tmp_path / "MU_1d.csv", index=False)
    monkeypatch.setattr(validator, "DAILY_DIR", tmp_path)
    findings = validator.Findings()
    assert validator.check_daily("MU", findings, set(), []) is None
    assert "no bars" in findings.errors[0]
