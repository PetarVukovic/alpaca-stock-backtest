"""One pure function per ordered Critic check (numbers 0-14 in CRITIC_CRITERIA.md).

Each returns a `CriticCheck` whose `detail` carries the real numbers (Croatian text, since it
lands in the verdict .md). Fail closed: evidence that is missing (None) means the check fails.
Returns are percent per trade. Period keys are "IS", "WF", "HO".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from lab.contracts import PRIMARY, Costs, CriticCheck
from lab.critic import stats

ReturnsByPeriod = dict[str, np.ndarray]


@dataclass(frozen=True)
class CriticConfig:
    """All provisional (P) thresholds in one place; the researcher edits only this object."""

    min_n_per_period: int = 10
    cost_stress_multiplier: float = 2.0
    pbo_max: float = 0.5
    dsr_p_max: float = 0.05
    pbo_required: bool = True  # PBO not computable -> FAIL (cannot prove it is not overfit)
    min_tickers_same_sign: int = 2
    top_n_trades: int = 3
    mc_sims: int = 2000
    mc_block_len: int = 5
    mc_max_dd_p95_pct: float = 50.0  # pessimistic (95th pct) max drawdown allowed
    ho_wf_ratio_max: float = 5.0  # HO mean > ratio * WF mean smells like boom (C11)
    seed: int = 42


@dataclass(frozen=True)
class SensitivityResult:
    """Outcome of one +/-20% parameter shift, produced by the engine lane."""

    wf_mean_pct: float | None  # None: no WF trades in the diagnostic -> no evidence
    edge_crushed: bool


@dataclass
class CriticInputs:
    """Plain inputs of a Critic run. None means 'no evidence' and fails the check."""

    returns: dict[str, ReturnsByPeriod]  # ticker -> period -> trade returns (%)
    costs: Costs = field(default_factory=Costs)
    k: int = 0
    stressed_returns: dict[str, ReturnsByPeriod] | None = None  # engine run at 2x costs
    data_check_exit_code: int | None = None
    wdc_spinoff_adjusted_once: bool | None = None
    lookahead_truncation_ok: bool | None = None
    lookahead_corrupt_future_ok: bool | None = None
    freeze_matches: bool | None = None
    no_fitted_parameters: bool | None = None
    period_boundary_liquidation: bool | None = None
    portfolio_returns: dict[str, ReturnsByPeriod] | None = None  # ROTATION/BASKET joint trades
    sensitivity: dict[str, SensitivityResult] | None = None
    ledger_complete: bool | None = None
    trials_matrix: np.ndarray | None = None  # T x N variant returns, common time axis
    trials_matrix_metadata: dict | None = None  # dates, columns and pre-holdout provenance
    holdout_fill_violations: int | None = None
    fill_violations: int | None = None
    audit: dict | None = None  # reports/research/redteam_audit.json (None = not delivered)
    rule_types: list[str] = field(default_factory=list)  # entry.type + exit.type of the freeze
    lookahead_evidence_ok: bool | None = None


def pool(returns: dict[str, ReturnsByPeriod], periods: tuple[str, ...]) -> np.ndarray:
    """Concatenate trade returns of all tickers over the given periods."""
    parts = [np.asarray(per[p], dtype=float) for per in returns.values() for p in periods if p in per]
    return np.concatenate(parts) if parts else np.array([], dtype=float)


def _mean(x: np.ndarray) -> float | None:
    return float(x.mean()) if x.size else None


def _fmt(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}"


def _check(number: int, name: str, passed: bool, detail: str) -> CriticCheck:
    return CriticCheck(number=number, name=name, passed=bool(passed), detail=detail)


def check_0_data(exit_code: int | None, wdc_ok: bool | None) -> CriticCheck:
    ok = exit_code == 0 and wdc_ok is not False
    detail = f"validate_data exit={exit_code}, WDC spin-off prilagođen jednom={wdc_ok}."
    if exit_code is None:
        detail += " Provjera podataka nije pokrenuta, nema dokaza."
    return _check(0, "Podaci", ok, detail)


def check_1_lookahead(truncation_ok: bool | None, corrupt_ok: bool | None) -> CriticCheck:
    ok = truncation_ok is True and corrupt_ok is True
    return _check(
        1, "Lookahead", ok,
        f"truncation test={truncation_ok}, test s pokvarenim budućim podacima={corrupt_ok} "
        "(None znači da nije pokrenut).",
    )


def check_2_freeze(freeze_matches: bool | None) -> CriticCheck:
    return _check(2, "Freeze integritet", freeze_matches is True,
                  f"pokrenuto pravilo identično zamrznutom={freeze_matches}.")


def check_3_same_sign(returns: dict[str, ReturnsByPeriod]) -> CriticCheck:
    """IS and WF must both be positive here; HO sign is judged last, in check 13."""
    stats_ = {p: (int(pool(returns, (p,)).size), _mean(pool(returns, (p,)))) for p in ("IS", "WF")}
    ok = all(m is not None and m > 0 for _, m in stats_.values())
    detail = f"IS (n, srednji %)={_fmt_pair(stats_['IS'])}, WF={_fmt_pair(stats_['WF'])}; HO se gleda zadnji (provjera 13)."
    return _check(3, "Isti predznak WF", ok, detail)


def _fmt_pair(p: tuple[int, float | None]) -> str:
    return f"({p[0]}, {_fmt(p[1])})"


def check_4_min_sample(returns: dict[str, ReturnsByPeriod], config: CriticConfig) -> CriticCheck:
    ns = {p: int(pool(returns, (p,)).size) for p in ("IS", "WF")}
    ok = all(n >= config.min_n_per_period for n in ns.values())
    return _check(4, "Minimalni uzorak", ok,
                  f"n po razdoblju={ns}, minimum {config.min_n_per_period} (P); HO se provjerava tek u 13.")


def check_5_purge_embargo(
    no_fitted_parameters: bool | None, boundary_liquidation: bool | None
) -> CriticCheck:
    """PASS only if no parameter was fitted AND no trade spans an IS/WF/HO boundary."""
    ok = no_fitted_parameters is True and boundary_liquidation is True
    return _check(
        5, "Purge / embargo", ok,
        f"svi parametri zamrznuti iz teorije (nijedan prilagođen podacima)={no_fitted_parameters}, "
        f"nijedna trgovina ne prelazi granicu IS/WF/HO (period_boundary_liquidation)={boundary_liquidation}.",
    )


def check_6_sensitivity(sensitivity: dict[str, SensitivityResult] | None) -> CriticCheck:
    if not sensitivity:
        return _check(6, "Osjetljivost ±20 %", False, "Nema rezultata osjetljivosti, nema dokaza.")
    no_evidence = sorted(k for k, v in sensitivity.items() if v.wf_mean_pct is None)
    crushed = sorted(k for k, v in sensitivity.items() if v.edge_crushed or v.wf_mean_pct is None)
    detail = (f"parametara testirano={len(sensitivity)}, edge_crushed ili bez dokaza={crushed or 'nijedan'}, "
              f"bez WF trgovina={no_evidence or 'nijedan'}, "
              f"WF srednji % po pomaku={ {k: None if v.wf_mean_pct is None else round(v.wf_mean_pct, 3) for k, v in sensitivity.items()} }.")
    return _check(6, "Osjetljivost ±20 %", not crushed, detail)


def stress_returns(
    returns: dict[str, ReturnsByPeriod], costs: Costs, multiplier: float
) -> dict[str, ReturnsByPeriod]:
    """Fallback stress: subtract the extra round-trip bps only (tick cost is NOT modelled)."""
    extra_pct = (multiplier - 1.0) * costs.round_trip_bps / 100.0
    return {t: {p: np.asarray(per[p], dtype=float) - extra_pct for p in ("IS", "WF") if p in per}
            for t, per in returns.items()}


def check_7_cost_stress(
    returns: dict[str, ReturnsByPeriod],
    costs: Costs,
    config: CriticConfig,
    stressed: dict[str, ReturnsByPeriod] | None = None,
) -> CriticCheck:
    source = "engine (2x trošak)"
    if stressed is None:
        stressed = stress_returns(returns, costs, config.cost_stress_multiplier)
        source = "aproksimacija: oduzet samo dodatni round-trip bps, tick nije modeliran"
    base = pool(returns, ("WF",))
    wf = pool(stressed, ("WF",))
    m = _mean(wf)
    ok = m is not None and m > 0
    return _check(7, "Stres troškova", ok,
                  f"WF srednji % pri 1x={_fmt(_mean(base), 3)}, pri {config.cost_stress_multiplier}x={_fmt(m, 3)} "
                  f"(n={wf.size}); izvor: {source}.")


def check_8_regime_concentration(returns: dict[str, ReturnsByPeriod], config: CriticConfig) -> CriticCheck:
    """Same sign on enough primary tickers and profit not carried by top-n trades (IS+WF only)."""
    per_ticker = {t: _mean(pool({t: returns[t]}, ("IS", "WF"))) for t in PRIMARY if t in returns}
    positive = [t for t, m in per_ticker.items() if m is not None and m > 0]
    ex_mean, share = stats.top_n_concentration(pool(returns, ("IS", "WF")), config.top_n_trades)
    ok = len(positive) >= config.min_tickers_same_sign and ex_mean is not None and ex_mean > 0
    detail = (f"srednji % po primary tickeru (IS+WF)={ {t: None if m is None else round(m, 3) for t, m in per_ticker.items()} }, "
              f"pozitivnih {len(positive)}/{len(PRIMARY)} (treba >= {config.min_tickers_same_sign}); "
              f"bez top-{config.top_n_trades} trgovina srednji={_fmt(ex_mean, 3)}, "
              f"udio top-{config.top_n_trades} u ukupnoj zaradi={_fmt(share)}.")
    return _check(8, "Režim i koncentracija", ok, detail)


def check_9_multiple_testing(k: int, ledger_complete: bool | None) -> CriticCheck:
    ok = k >= 1 and ledger_complete is True
    return _check(9, "Višestruko testiranje", ok,
                  f"K={k} iz ledgera, svi pokušaji upisani={ledger_complete}.")


def validate_trials_matrix(matrix: np.ndarray | None, metadata: dict | None) -> str | None:
    """Reject unverifiable/holdout PBO inputs, rather than trusting a producer flag."""
    if matrix is None:
        return "nema matrice varijanti"
    if not isinstance(metadata, dict):
        return "nedostaje vremensko podrijetlo PBO matrice"
    if (metadata.get("holdout_excluded") is not True
            or metadata.get("periods") != ["IS", "WF"]
            or metadata.get("units") != "daily_return_fraction"):
        return "PBO mora koristiti samo IS+WF dnevne prinose"
    try:
        m = np.asarray(matrix, dtype=float)
        dates = [datetime.fromisoformat(t.replace("Z", "+00:00"))
                 for t in metadata["timestamps"]]
        columns = metadata["columns"]
        if (m.ndim != 2 or len(dates) != m.shape[0] or len(columns) != m.shape[1]
                or not all(isinstance(c, str) and c for c in columns)
                or len(set(columns)) != len(columns) or not np.isfinite(m).all()):
            return "PBO dimenzije, stupci ili vrijednosti nisu valjani"
        dates = [d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC) for d in dates]
        if (not dates or any(d < datetime(2016, 1, 1, tzinfo=UTC)
                            or d >= datetime(2024, 1, 1, tzinfo=UTC) for d in dates)
                or any(a >= b for a, b in zip(dates, dates[1:]))):
            return "PBO datumi nisu rastući, jedinstveni ili su izvan IS+WF"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "nečitljivi podaci o PBO matrici"
    return None


def check_10_dsr_pbo(
    returns: dict[str, ReturnsByPeriod],
    k: int,
    trials_matrix: np.ndarray | None,
    config: CriticConfig,
    trials_matrix_metadata: dict | None = None,
) -> CriticCheck:
    pooled = pool(returns, ("IS", "WF"))
    dsr = stats.deflated_sharpe(pooled, k)
    matrix_error = validate_trials_matrix(trials_matrix, trials_matrix_metadata)
    pbo = stats.pbo_cscv(trials_matrix if matrix_error is None else None)
    dsr_ok = dsr.computable and dsr.p_value is not None and dsr.p_value < config.dsr_p_max
    if pbo.computable and pbo.pbo is not None:
        pbo_ok = pbo.pbo < config.pbo_max
        pbo_txt = f"PBO={pbo.pbo:.3f} ({pbo.n_combinations} CSCV kombinacija, granica {config.pbo_max})"
    else:
        pbo_ok = not config.pbo_required and trials_matrix is None
        pbo_txt = (f"PBO nije izračunljiv ({matrix_error or pbo.reason}); obavezan={config.pbo_required}. "
                   "Za PBO trebaju barem dvije zamrznute varijante iste obitelji na zajedničkoj vremenskoj osi")
    dsr_txt = (f"Sharpe po trgovini={_fmt(dsr.sharpe, 3)}, SR0 (K={k})={_fmt(dsr.sr0, 3)}, "
               f"DSR={_fmt(dsr.dsr, 3)}, p={_fmt(dsr.p_value, 4)} (granica {config.dsr_p_max}), n={dsr.n}"
               if dsr.computable else f"DSR nije izračunljiv ({dsr.reason})")
    return _check(10, "Deflated Sharpe i PBO", dsr_ok and pbo_ok, f"DSR koristi samo IS+WF; {dsr_txt}; {pbo_txt}.")


def check_11_monte_carlo(returns: dict[str, ReturnsByPeriod], config: CriticConfig) -> CriticCheck:
    pooled = pool(returns, ("IS", "WF"))  # HO stays untouched until check 13
    if pooled.size < 2:
        return _check(11, "Monte Carlo drawdowna", False, "Premalo trgovina za Monte Carlo.")
    mc = stats.monte_carlo_drawdown(pooled, config.mc_sims, config.mc_block_len, config.seed)
    worst = max(mc.simple_dd_pct[95], mc.block_dd_pct[95])
    fmt = lambda d: {p: round(v, 1) for p, v in d.items()}
    return _check(11, "Monte Carlo drawdowna", worst <= config.mc_max_dd_p95_pct,
                  f"{mc.n_sims} simulacija, max pad % (percentili 5/25/50/75/95): obični={fmt(mc.simple_dd_pct)}, "
                  f"blokovi (duljina {mc.block_len})={fmt(mc.block_dd_pct)}; povijesni={mc.historical_dd_pct:.1f}; "
                  f"pesimistični p95={worst:.1f} (granica {config.mc_max_dd_p95_pct}).")


def check_12_fills(fill_violations: int | None) -> CriticCheck:
    return _check(12, "Izvedivost fillova", fill_violations == 0,
                  f"nemogućih fillova={fill_violations} (None znači da nije provjereno).")


def check_13_holdout(returns: dict[str, ReturnsByPeriod], config: CriticConfig,
                     holdout_fill_violations: int | None = None) -> CriticCheck:
    """Holdout, evaluated last: positive mean and not wildly stronger than WF (boom suspicion)."""
    ho = pool(returns, ("HO",))
    wf = pool(returns, ("WF",))
    ho_m, wf_m = _mean(ho), _mean(wf)
    ex_mean, _ = stats.top_n_concentration(ho, config.top_n_trades)
    boom = bool(ho_m is not None and wf_m is not None and wf_m > 0 and ho_m > config.ho_wf_ratio_max * wf_m)
    ok = (holdout_fill_violations == 0 and ho.size >= config.min_n_per_period and ho_m is not None and ho_m > 0
          and not boom and ex_mean is not None and ex_mean > 0)
    return _check(13, "Holdout zadnji", ok,
                  f"HO nemogućih fillova={holdout_fill_violations}; HO (n, srednji %)=({ho.size}, {_fmt(ho_m)}), minimum n={config.min_n_per_period}, WF srednji={_fmt(wf_m)}, "
                  f"HO bez top-{config.top_n_trades}={_fmt(ex_mean)}, sumnja na boom (HO > {config.ho_wf_ratio_max}x WF)={boom}.")


def _audit_entry(rule_types: dict, rule_type: str) -> dict | None:
    for key, val in rule_types.items():
        if key == rule_type or key.endswith((":" + rule_type, "." + rule_type, "/" + rule_type)):
            return val
    return None


def check_14_final_audit(
    previous: list[CriticCheck],
    audit: dict | None,
    rule_types: list[str],
    lookahead_evidence_ok: bool | None,
) -> CriticCheck:
    """Red-team audit: every rule type reproduced, no open high finding, lookahead evidence ok."""
    failed = [x.number for x in previous if not x.passed]
    if audit is None:
        return _check(14, "Završni audit", False, "audit nije dostavljen "
                      f"(reports/research/redteam_audit.json); provjere koje nisu prošle={failed or 'nijedna'}.")
    types = audit.get("rule_types", {})
    per_type = {}
    for t in rule_types:
        e = _audit_entry(types, t)
        per_type[t] = None if e is None else (bool(e.get("reproduced")), e.get("max_abs_diff_pct"))
    bad_types = [t for t, v in per_type.items() if v is None or not v[0]]
    open_high = [f.get("text", "") for f in audit.get("engine_findings", [])
                 if f.get("severity") == "high" and f.get("open")]
    ok = not failed and not bad_types and not open_high and lookahead_evidence_ok is True
    return _check(14, "Završni audit", ok,
                  f"tipovi pravila (reproducirano, max razlika %)={per_type}, nereproducirani={bad_types or 'nijedan'}, "
                  f"otvoreni high nalazi={len(open_high)}, lookahead dokaz={lookahead_evidence_ok}, "
                  f"provjere koje nisu prošle={failed or 'nijedna'}.")
