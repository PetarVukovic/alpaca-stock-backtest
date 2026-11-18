"""Skip historical parity checks when their local research inputs are absent."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MU = "data/ohlcv/MU_1d.csv"
GLD = "data/ohlcv/GLD_1d.csv"
LOCAL_INPUTS = {
    "test_k1_matches_original": [MU, "data/ohlcv/WDC_1d.csv", "data/ohlcv/STX_1d.csv"],
    "test_halted_history_is_not_loaded": ["data/ohlcv/SMCI_1d.csv"],
    "test_real_data": [MU],
    "test_completed_real_core_fixed_one_matches_app_through_2023": [MU],
    "test_half_day_hourly_excludes_after_close_and_flattens": ["data/hourly/MU_1h_clean.csv"],
    "test_rotation_benchmark_uses_equal_basket_shared_dates": [MU, "data/ohlcv/WDC_1d.csv", "data/ohlcv/STX_1d.csv"],
    "test_benchmark_label_is_not_candidate": ["reports/backtest/B2_TREND200_WDC.json"],
    "test_disabled_real_core_all_history_exact_baseline": [MU],
    "test_audit_json_schema": ["reports/research/redteam_audit.json"],
    "test_honest_strategy_passes_lookahead_and_runs": [GLD],
    "test_cheating_strategy_is_caught": [GLD],
    "test_leverage_is_rejected": [GLD],
    "test_costs_reduce_returns_and_fill_is_next_open": [GLD],
}


def pytest_collection_modifyitems(items):
    for item in items:
        missing = [
            name for name in LOCAL_INPUTS.get(item.originalname, [])
            if not (ROOT / name).is_file()
        ]
        if missing:
            item.add_marker(pytest.mark.skip(reason="Local research inputs: " + ", ".join(missing)))
