"""Append-only, process-locked trial ledger."""

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path

LEGACY_K = 0
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "reports/ledger/trials.jsonl"


def read_trials(path=DEFAULT_PATH):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def current_k(path=DEFAULT_PATH):
    return LEGACY_K + len(read_trials(path))


def log_trial(strategy, ticker, freeze_hash, path=DEFAULT_PATH, **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        rows = [json.loads(line) for line in stream if line.strip()]
        row = dict(
            k=LEGACY_K + len(rows) + 1,
            strategy_id=strategy,
            ticker=ticker,
            freeze_hash=freeze_hash,
            run_at=datetime.now(timezone.utc).isoformat(),
            **metadata,
        )
        stream.seek(0, 2)
        stream.write(json.dumps(row, sort_keys=True) + "\n")
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)
    return row["k"]


def register_strategy(strategy_id, freeze_hash, path=DEFAULT_PATH, **metadata):
    """One campaign trial per immutable ID, including its predefined diagnostics."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        rows = [json.loads(line) for line in stream if line.strip()]
        existing = [r for r in rows if r["strategy_id"] == strategy_id]
        if existing:
            if any(r["freeze_hash"] != freeze_hash for r in existing):
                raise ValueError("Frozen ID changed after registration")
            return existing[0]["k"]
        row = {
            "k": LEGACY_K + len(rows) + 1,
            "strategy_id": strategy_id,
            "freeze_hash": freeze_hash,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "unit": "frozen_strategy_id",
            **metadata,
        }
        stream.seek(0, 2)
        stream.write(json.dumps(row, sort_keys=True) + "\n")
        stream.flush()
        return row["k"]
