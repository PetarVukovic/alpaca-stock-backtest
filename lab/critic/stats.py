"""Statistics used by the Critic: DSR, PBO (CSCV), Monte Carlo drawdown, concentration.

Everything is deterministic given a seed and never invents a number: when an input is
insufficient the result says so (`computable=False`) instead of returning a fake value.
Trade returns are in percent per trade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329
PERCENTILES = (5, 25, 50, 75, 95)


@dataclass(frozen=True)
class DSRResult:
    computable: bool
    n: int
    sharpe: float | None = None  # per-trade (non-annualized) Sharpe
    sr0: float | None = None  # expected max Sharpe of K noise trials
    dsr: float | None = None  # P(true SR > 0 | K trials)
    p_value: float | None = None  # 1 - dsr
    reason: str = ""


@dataclass(frozen=True)
class PBOResult:
    computable: bool
    pbo: float | None = None
    n_combinations: int = 0
    reason: str = ""


@dataclass(frozen=True)
class MonteCarloResult:
    n_sims: int
    block_len: int
    simple_dd_pct: dict[int, float]  # percentile -> max drawdown magnitude (%)
    block_dd_pct: dict[int, float]
    historical_dd_pct: float


def trade_sharpe(returns: np.ndarray) -> float:
    """Per-trade Sharpe (mean / sample std); 0.0 when the std is zero or n < 2."""
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return 0.0
    sd = r.std(ddof=1)
    return 0.0 if sd == 0 else float(r.mean() / sd)


def expected_max_sharpe(k: int, sr_variance: float) -> float:
    """Expected maximum Sharpe among `k` independent noise trials (Bailey & Lopez de Prado).

    Returns 0.0 for k <= 1 (a single trial has no selection bias).
    """
    if k <= 1:
        return 0.0
    sd = math.sqrt(max(sr_variance, 0.0))
    z1 = norm.ppf(1.0 - 1.0 / k)
    z2 = norm.ppf(1.0 - 1.0 / (k * math.e))
    return float(sd * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(
    returns: np.ndarray,
    k: int,
    trial_sharpes: np.ndarray | None = None,
) -> DSRResult:
    """Deflated Sharpe Ratio of `returns` given `k` trials tried to find it.

    The cross-trial Sharpe variance comes from `trial_sharpes` when supplied; otherwise
    the null sampling variance of a Sharpe estimate on n trades is used (documented
    approximation: 1/(n-1)). The per-trade Sharpe and its skew/kurtosis correction use
    the observed returns. DSR is monotone non-decreasing as k falls.
    """
    r = np.asarray(returns, dtype=float)
    n = int(r.size)
    if n < 3:
        return DSRResult(False, n, reason=f"n={n} < 3")
    sr = trade_sharpe(r)
    if trial_sharpes is not None and len(trial_sharpes) >= 2:
        var = float(np.var(np.asarray(trial_sharpes, dtype=float), ddof=1))
    else:
        var = 1.0 / (n - 1)
    sr0 = expected_max_sharpe(k, var)
    mu, sd = r.mean(), r.std(ddof=0)
    if sd == 0:
        return DSRResult(False, n, reason="zero variance")
    z = (r - mu) / sd
    skew = float((z**3).mean())
    kurt = float((z**4).mean())
    denom_sq = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2
    if denom_sq <= 0:
        return DSRResult(False, n, sharpe=sr, sr0=sr0, reason="non-positive variance term")
    stat = (sr - sr0) * math.sqrt(n - 1) / math.sqrt(denom_sq)
    dsr = float(norm.cdf(stat))
    return DSRResult(True, n, sharpe=sr, sr0=sr0, dsr=dsr, p_value=1.0 - dsr)


def pbo_cscv(trials_matrix: np.ndarray | None, n_splits: int = 8) -> PBOResult:
    """Probability of backtest overfitting via CSCV (Bailey et al.).

    `trials_matrix` is (T observations x N strategy variants) of returns on a common
    time axis. Needs N >= 2 and T >= 2*n_splits; otherwise reports not computable.
    """
    if trials_matrix is None:
        return PBOResult(False, reason="no trials matrix supplied")
    m = np.asarray(trials_matrix, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        return PBOResult(False, reason="need at least 2 strategy variants (N >= 2)")
    t, n_strat = m.shape
    if n_splits % 2 or t < 2 * n_splits:
        return PBOResult(False, reason=f"T={t} too short for {n_splits} splits")
    chunks = np.array_split(np.arange(t), n_splits)
    logits: list[float] = []
    for is_ids in combinations(range(n_splits), n_splits // 2):
        oos_ids = [i for i in range(n_splits) if i not in is_ids]
        is_rows = np.concatenate([chunks[i] for i in is_ids])
        oos_rows = np.concatenate([chunks[i] for i in oos_ids])
        is_sr = np.array([trade_sharpe(m[is_rows, j]) for j in range(n_strat)])
        oos_sr = np.array([trade_sharpe(m[oos_rows, j]) for j in range(n_strat)])
        best = int(np.argmax(is_sr))
        rank = (oos_sr < oos_sr[best]).sum() + 0.5 * ((oos_sr == oos_sr[best]).sum() - 1)
        omega = (rank + 1.0) / (n_strat + 1.0)
        logits.append(math.log(omega / (1.0 - omega)))
    pbo = float(np.mean(np.array(logits) <= 0.0))
    return PBOResult(True, pbo=pbo, n_combinations=len(logits))


def max_drawdown_pct(returns_pct: np.ndarray) -> float:
    """Max drawdown magnitude (%) of sequentially compounded trades (full allocation)."""
    r = np.clip(np.asarray(returns_pct, dtype=float), -99.99, None) / 100.0
    eq = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    peak = np.maximum.accumulate(eq)
    return float(((peak - eq) / peak).max() * 100.0)


def _batch_max_dd(paths_pct: np.ndarray) -> np.ndarray:
    r = np.clip(paths_pct, -99.99, None) / 100.0
    eq = np.cumprod(1.0 + r, axis=1)
    eq = np.concatenate([np.ones((eq.shape[0], 1)), eq], axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    return ((peak - eq) / peak).max(axis=1) * 100.0


def monte_carlo_drawdown(
    returns_pct: np.ndarray,
    n_sims: int = 2000,
    block_len: int = 5,
    seed: int = 0,
) -> MonteCarloResult:
    """Simple and circular-block bootstrap of trade sequences -> max drawdown percentiles."""
    r = np.asarray(returns_pct, dtype=float)
    n = r.size
    if n < 2:
        raise ValueError(f"need at least 2 trades for Monte Carlo, got {n}")
    rng = np.random.default_rng(seed)
    simple = r[rng.integers(0, n, size=(n_sims, n))]
    b = max(1, min(block_len, n))
    n_blocks = math.ceil(n / b)
    starts = rng.integers(0, n, size=(n_sims, n_blocks))
    idx = (starts[:, :, None] + np.arange(b)) % n
    block = r[idx.reshape(n_sims, -1)[:, :n]]
    return MonteCarloResult(
        n_sims=n_sims,
        block_len=b,
        simple_dd_pct={p: float(np.percentile(_batch_max_dd(simple), p)) for p in PERCENTILES},
        block_dd_pct={p: float(np.percentile(_batch_max_dd(block), p)) for p in PERCENTILES},
        historical_dd_pct=max_drawdown_pct(r),
    )


def top_n_concentration(returns_pct: np.ndarray, n_top: int = 3) -> tuple[float | None, float | None]:
    """Return (mean without the top-n trades, share of total profit from top-n trades).

    Both None when there are not more than `n_top` trades; share is None if total <= 0.
    """
    r = np.sort(np.asarray(returns_pct, dtype=float))[::-1]
    if r.size <= n_top:
        return None, None
    ex_mean = float(r[n_top:].mean())
    total = float(r.sum())
    share = float(r[:n_top].sum() / total) if total > 0 else None
    return ex_mean, share
