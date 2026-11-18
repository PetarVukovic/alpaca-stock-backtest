import numpy as np
import pandas as pd

from lab.strategies.ml_logit import features, predictions


def sample():
    index = pd.bdate_range("2016-01-04", "2025-12-31", tz="UTC")
    rng = np.random.default_rng(12)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.018, len(index))))
    return pd.DataFrame(
        {"close": close, "date": index.strftime("%Y-%m-%d")}, index=index
    )


def test_future_prices_cannot_change_predictions_and_training_is_purged():
    frame = sample()
    full, metadata = predictions(frame)
    cutoff = 1800
    short, _ = predictions(frame.iloc[:cutoff].copy())
    corrupted = frame.copy()
    corrupted.iloc[cutoff:, corrupted.columns.get_loc("close")] *= 7
    altered, _ = predictions(corrupted)
    pd.testing.assert_series_equal(full.iloc[:cutoff], short)
    pd.testing.assert_series_equal(full.iloc[:cutoff], altered.iloc[:cutoff])
    final = metadata["models"][-1]
    assert final["status"] == "fitted"
    assert pd.Timestamp(final["label_last"]) < pd.Timestamp("2021-01-01", tz="UTC")
    assert full.loc["2024"].notna().all()


def test_features_ignore_current_bar_and_failed_fit_is_idle():
    frame = sample()
    original = features(frame)
    changed = frame.copy()
    changed.iloc[400, changed.columns.get_loc("close")] *= 2
    pd.testing.assert_frame_equal(original.iloc[:401], features(changed).iloc[:401])
    probability, metadata = predictions(frame.iloc[:220])
    assert probability.isna().all()
    assert metadata["classification"]["HO"]["n"] == 0
