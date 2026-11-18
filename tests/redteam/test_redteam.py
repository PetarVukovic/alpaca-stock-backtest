"""Lane C red-team: sanity of the independent reimplementation and of the audit JSON schema."""

import json

import pandas as pd

from lab.research.redteam.reimpl import ROOT, CostModel, simulate_single


def _frame(rows):
    idx = pd.date_range("2021-03-01", periods=len(rows), freq="B")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["day"] = idx.strftime("%Y-%m-%d")
    return df


def _flags(df, at):
    s = pd.Series(False, index=df.index)
    s.iloc[at] = True
    return s


def test_cost_per_side():
    cost = CostModel()
    assert abs(cost.buy(100) - 100.035) < 1e-12
    assert abs(cost.sell(100) - 99.965) < 1e-12
    assert abs(CostModel().for_ticker("MRAM").buy(100) - 100.07) < 1e-12


def test_entry_next_open_and_period_end():
    df = _frame([(100, 100, 100, 100), (110, 110, 110, 110), (120, 120, 120, 121)])
    book = simulate_single(
        df, _flags(df, [0]), _flags(df, []), {"type": "hold"}, CostModel()
    )
    (trade,) = book.trades
    assert trade.entry_ts == df.index[1] and trade.reason == "period_end"
    assert abs(trade.entry_fill - CostModel().buy(110)) < 1e-12
    assert abs(trade.exit_fill - CostModel().sell(121)) < 1e-12


def test_trailing_peak_from_previous_bars():
    df = _frame(
        [
            (100, 100, 100, 100),
            (110, 110, 110, 110),
            (110, 130, 116, 125),
            (125, 126, 124, 125),
        ]
    )
    rule = {"type": "trailing", "trailing_pct": 0.1}
    book = simulate_single(df, _flags(df, [0]), _flags(df, []), rule, CostModel())
    assert [t.reason for t in book.trades] == ["period_end"]


def test_audit_json_schema():
    path = ROOT / "reports/research/redteam_audit.json"
    data = json.loads(path.read_text())
    assert set(data) == {"generated_at", "rule_types", "engine_findings"}
    for row in data["rule_types"].values():
        assert set(row) == {"reproduced", "max_abs_diff_pct", "n_trades_match", "notes"}
    for f in data["engine_findings"]:
        assert f["severity"] in {"high", "medium", "low"} and isinstance(
            f["open"], bool
        )


def test_ml1_features_use_only_previous_bar():
    import numpy as np

    from lab.research.redteam.ml1 import make_features

    close = 100 * np.cumprod(1 + np.random.default_rng(1).normal(0, 0.02, 300))
    bumped = close.copy()
    bumped[250] *= 1.5
    a, b = make_features(close), make_features(bumped)
    assert np.array_equal(a[250], b[250], equal_nan=True)
    assert not np.array_equal(a[251], b[251], equal_nan=True)


def test_ml1_logit_matches_known_solution():
    import numpy as np
    import statsmodels.api as sm

    from lab.research.redteam.ml1 import fit_logit

    rng = np.random.default_rng(3)
    x = rng.normal(size=(500, 2))
    y = (rng.random(500) < 1 / (1 + np.exp(-(0.3 + x @ [1.0, -0.5])))).astype(float)
    ref = sm.Logit(y, sm.add_constant(x)).fit(disp=False).params
    assert np.allclose(fit_logit(x, y), ref, atol=1e-8)
