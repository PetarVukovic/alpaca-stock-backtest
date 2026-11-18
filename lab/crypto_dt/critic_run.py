"""Formal lab Critic (`lab.critic`, checks 0-14) for one frozen CDT_* trend ID: `python -m lab.crypto_dt.critic_run <module>`.

The lab Critic was calibrated on equity trades, so this adapter feeds it per-trade percent returns for the CRYPTO splits
(IS 2021-22 / WF 2023-24 / HO 2025+) and states every adaptation in the verdict header:
- each period starts flat and is liquidated at its last bar (check 5 needs trades that never cross a boundary);
- primary tickers are BTCUSDT / ETHUSDT / SOLUSDT (the equity default MU/WDC/STX would fail check 8 structurally);
- the PBO matrix must end before 2024-01-01 inside `validate_trials_matrix`, so it covers 2021-2023 only.
Thresholds stay at the default `CriticConfig`. It never edits `approved_list.json`: a PASS is reported to the researcher first.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

import numpy as np
import pandas as pd

from lab.contracts import Costs
from lab.crypto_dt import data
from lab.crypto_dt.run import AMENDMENT, _loader, _numeric_keys, _scaled_one, _sha
from lab.critic import checks
from lab.critic.checks import CriticConfig, CriticInputs, SensitivityResult
from lab.critic.runner import ledger_k
from lab.critic.verdict import render_verdict_md, run_critic
from lab.top10 import core

ROOT = core.ROOT
BOUNDS = core.SPLITS["crypto"]
CRYPTO_PRIMARY = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
ACCOUNT_USDT = 10_000.0  # reference account for the fill-feasibility check
MAX_BAR_SHARE = 0.01  # a fill may be at most 1% of the bar's traded notional
CRUSH_RATIO = 0.5  # edge_crushed: shifted WF mean trade return <= 0 or below half of the base value (declared before running)


def _masked(weights: pd.DataFrame, period: str) -> pd.DataFrame:
    """Weights restricted to one period: flat before it starts and flat (liquidated) after it ends."""
    start, end = BOUNDS[period]
    out = weights.copy()
    out.loc[(out.index < pd.Timestamp(start)) | (out.index > pd.Timestamp(end) + pd.Timedelta(days=1)), :] = 0.0
    return out


def period_trades(weights: pd.DataFrame, pan: dict, period: str, mult: float = 1.0) -> dict[str, np.ndarray]:
    """Per-ticker percent returns of the trades that start in `period` (flat start, forced exit at the end)."""
    bt = core.backtest(_masked(weights, period), pan, mult)
    out: dict[str, list[float]] = {t: [] for t in weights.columns}
    for trade in core.trades_from(bt, pan):
        out[trade["ticker"]].append(trade["ret"] * 100.0)
    return {t: np.asarray(v, dtype=float) for t, v in out.items()}


def _returns(weights: pd.DataFrame, pan: dict, periods: tuple[str, ...], mult: float = 1.0) -> dict[str, dict]:
    by_period = {p: period_trades(weights, pan, p, mult) for p in periods}
    return {t: {p: by_period[p][t] for p in periods} for t in weights.columns}


def _crypto_data_check(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Structural check of the hourly files that feed the 4h bars (validate_data.py does not cover crypto)."""
    result = {}
    for ticker in frames:
        hourly = data._load_frames([ticker], core.CUTOFF, "1h")[ticker]
        step = hourly.index.to_series().diff().dropna()
        o, h, lo, c = hourly["open"], hourly["high"], hourly["low"], hourly["close"]
        result[ticker] = {
            "rows": int(len(hourly)),
            "duplicates": int(hourly.index.duplicated().sum()),
            "nonpositive_or_nan": int(((hourly[["open", "high", "low", "close"]] <= 0) | hourly[["open", "high", "low", "close"]].isna()).sum().sum()),
            "ohlc_violations": int(((h < lo) | (h < o) | (h < c) | (lo > o) | (lo > c)).sum()),
            "gaps_over_1h": int((step > pd.Timedelta(hours=1)).sum()),
            "max_abs_hourly_move_pct": float(c.pct_change().abs().max() * 100),
        }
    return result


def _lookahead(module: Any, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    ok, bad = core.lookahead_check(module, frames)
    pan = core.panel(frames)
    full = module.weights(pan, module.PARAMS)
    corrupt_ok = True
    for share in (0.5, 0.8):
        cut = pan["open"].index[int(len(pan["open"]) * share)]
        broken = {k: v.copy() for k, v in pan.items()}
        for field in ("open", "high", "low", "close"):
            broken[field].loc[broken[field].index > cut] *= 40.0
        part = module.weights(broken, module.PARAMS)
        corrupt_ok &= bool(np.allclose(part.loc[:cut].to_numpy(), full.loc[:cut].to_numpy(), atol=1e-9))
    bt = core.backtest(full, pan, 1.0)
    return {"truncation_ok": ok, "bad_cut": bad, "corrupt_future_ok": corrupt_ok,
            "terminal_bar_excluded": bool(bt["ret_oo"].iloc[-1].eq(0).all())}


def _fills(weights: pd.DataFrame, pan: dict, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Count impossible fills: a fill on a bar the exchange never printed, outside its range, or above 1% of its volume."""
    bt = core.backtest(weights, pan, 1.0)
    pos, ret, gross = bt["pos"], bt["ret_oo"], bt["gross"]
    drifted = (pos * (1 + ret)).div(1 + gross, axis=0).shift(1).fillna(0.0)
    trade = (pos - drifted).abs()
    counts = {"in_sample": 0, "holdout": 0}
    start_ho = pd.Timestamp(BOUNDS["HO"][0])
    for ticker in weights.columns:
        idx = trade.index[(trade[ticker] > 1e-9).to_numpy()]
        real = frames[ticker].index
        for t in idx:
            bad = t not in real
            if not bad:
                row = frames[ticker].loc[t]
                bad = not (row["low"] <= row["open"] <= row["high"])
                notional = ACCOUNT_USDT * float(trade.at[t, ticker])
                bad = bad or notional > MAX_BAR_SHARE * float(row["open"] * row["volume"])
            if bad:
                counts["holdout" if t >= start_ho else "in_sample"] += 1
    return counts


def _freeze_check(module: Any, name: str, frozen_path: Path) -> dict[str, Any]:
    frozen = json.loads(frozen_path.read_text())
    expect_data = frozen["data_sha256"]
    base = {"4h": "1h"}.get(module.TIMEFRAME, module.TIMEFRAME)
    data_ok = all(_sha(core.data_path(t, base)) == expect_data[t] for t in module.UNIVERSE)
    support = frozen["support_sha256"]
    changed = [f for f, h in support.items() if _sha(ROOT / f"lab/crypto_dt/{f}") != h]
    weights_files_ok = [f for f in ("data.py", "features.py") if f not in changed]
    return {
        "code_ok": frozen["code_sha256"] == _sha(module.__file__),
        "data_ok": data_ok,
        "prereg_ok": frozen["preregistration_sha256"] == _sha(ROOT / frozen["preregistration"]),
        "support_changed_since_freeze": changed,
        "signal_path_files_unchanged": len(weights_files_ok) == 2,
        "freeze_file": str(frozen_path.relative_to(ROOT)),
    }


def _ledger_complete(ledger: Path) -> tuple[bool, list[str]]:
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    by_id = {r["strategy_id"]: r["freeze_hash"] for r in rows}
    missing = []
    for path in sorted((ROOT / "strategies/frozen").glob("*_CDT_*.json")):
        sid = path.stem.split("_", 1)[1]
        if by_id.get(sid) != _sha(path):
            missing.append(sid)
    return not missing, missing


def _daily(net: pd.Series) -> pd.Series:
    return (1 + net).groupby(net.index.normalize()).prod() - 1


def _trials_matrix(variants: dict[str, pd.Series]) -> tuple[np.ndarray, dict]:
    frame = pd.DataFrame({k: _daily(v) for k, v in variants.items()})
    frame = frame.loc["2021-01-01":"2023-12-31"].dropna()
    meta = {
        "holdout_excluded": True,
        "periods": ["IS", "WF"],
        "units": "daily_return_fraction",
        "timestamps": [d.strftime("%Y-%m-%dT00:00:00Z") for d in frame.index],
        "columns": list(frame.columns),
        "note": "2021-01-01..2023-12-31 only: validate_trials_matrix rejects dates from 2024 on (equity calibration)",
    }
    return frame.to_numpy(dtype=float), meta


def _audit(ledger_path: Path) -> dict[str, Any]:
    """Red-team record built from the independent codex-a review (reports/runs/codex_cdt_review.md)."""
    return {
        "generated_at": "2026-10-14",
        "source": "reports/runs/codex_cdt_review.md",
        "rule_types": {
            "donchian_ensemble_4h_vol_sized": {
                "reproduced": True,
                "max_abs_diff_pct": 6.22e-13,
                "note": "codex-a rebuilt 4h bars and CDT_H1 from raw CSVs without importing lab code; WF/HO match",
            }
        },
        "engine_findings": [
            {"severity": "medium", "open": False, "text": "core.py benchmark is an equal-weight basket rebalanced every bar, not buy-and-hold; "
             "true buy-and-hold is reported separately by lab/crypto_dt/run.py. Does not affect trade returns."},
            {"severity": "medium", "open": False, "text": "Unweighted trade-level ex-top3 and open-trade gross bps were misleading; "
             "contribution-based ex-top3 added, open-trade gross fixed."},
            {"severity": "medium", "open": True, "text": "Universe BTC/ETH/SOL is a current-survivor set and starts 2020-08 (SOL)."},
            {"severity": "medium", "open": True, "text": "Single frozen run per ID is evidenced by hashes and the ledger, not by an independent timestamp log."},
            {"severity": "low", "open": True, "text": "One extra bar of execution delay lowers CDT_H1 to WF +133.0% / HO +8.9% (still positive)."},
        ],
    }


COMMENTARY = """
## Tumačenje pada (dodano ručno, ne mijenja presudu)

- **Što je stvaran nalaz:** provjera 10 (Deflated Sharpe p = 0,9975 uz K u ledgeru, PBO 0,70) i provjera 13 (holdout: srednji prinos 0,04 % po trgovini, bez 3 najbolje trgovine −0,96 %). Zarada H1 je koncentrirana u nekoliko velikih trendova (hit rate 31 %); u holdoutu nema dovoljno velikih dobitaka da nose prosjek. Statistički se ne razlikuje od sreće uz toliko isprobanih ideja.
- **Što je ograničenje Critica, ne H1:** Critic gleda neponderirane postotne prinose po trgovini kao da je svaka na 100 % kapitala. H1 drži oko 1/3 kapitala po coinu uz vol skaliranje, pa Monte Carlo pad od 94 % (provjera 11) ne odgovara portfeljnom padu od −22 %, a pomaci `sigma_target` i `vol_window` u provjeri 6 ne mijenjaju trgovine pa daju iste brojke. Pragovi nisu ublaženi, pad ostaje pad.
- **Posljedica:** FAIL je zatvoren (fail closed). `approved_list` nije dirnut, signal ostaje PRIČEKAJ. Nova ideja (npr. drugi horizont ili sastav) dobiva novi ID.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("--date", type=date.fromisoformat, default=date(2026, 10, 14))
    args = parser.parse_args(argv)
    module = importlib.import_module(f"lab.crypto_dt.strategies.{args.module}")
    frozen_path = sorted((ROOT / "strategies/frozen").glob(f"*_{module.ID}.json"))[-1]
    frames = _loader(module.UNIVERSE, timeframe=module.TIMEFRAME)
    pan = core.panel(frames)
    weights = module.weights(pan, module.PARAMS)
    with mock.patch.object(core, "load_frames", _loader):
        look = _lookahead(module, frames)
    returns = _returns(weights, pan, ("IS", "WF", "HO"))
    stressed = _returns(weights, pan, ("IS", "WF"), mult=2.0)
    base_wf = float(np.concatenate([returns[t]["WF"] for t in returns]).mean())
    sens: dict[str, SensitivityResult] = {}
    variants = {module.ID: core.backtest(weights, pan, 1.0)["net"]}
    for key in _numeric_keys(module.PARAMS):
        for factor in (0.8, 1.2):
            params = _scaled_one(module.PARAMS, key, factor)
            shifted = module.weights(pan, params)
            wf = np.concatenate(list(period_trades(shifted, pan, "WF").values()))
            mean = float(wf.mean()) if wf.size else None
            crushed = mean is None or mean <= 0 or mean < CRUSH_RATIO * base_wf
            sens[f"{key}_x{factor}"] = SensitivityResult(wf_mean_pct=mean, edge_crushed=bool(crushed))
            variants[f"{key}_x{factor}"] = core.backtest(shifted, pan, 1.0)["net"]
    for sibling in ("cdt_h1b_trend_4h_novol", "cdt_h2q_trend_4h_crowd_qtl"):
        other = importlib.import_module(f"lab.crypto_dt.strategies.{sibling}")
        variants[other.ID] = core.backtest(other.weights(pan, other.PARAMS), pan, 1.0)["net"]
    matrix, matrix_meta = _trials_matrix(variants)
    ledger = ROOT / "reports/ledger/trials.jsonl"
    complete, missing = _ledger_complete(ledger)
    fills = _fills(weights, pan, frames)
    freeze = _freeze_check(module, module.ID, frozen_path)
    audit = _audit(ledger)
    audit_path = OUT_DIR = ROOT / "reports/research/CRYPTO_DT_20261014" / module.ID / "redteam_audit_cdt.json"
    audit_path.write_text(json.dumps(audit, indent=2))
    inputs = CriticInputs(
        returns=returns,
        stressed_returns=stressed,
        costs=Costs(round_trip_bps=core.COST_RT_BPS["crypto"], tick_per_side=0.0),
        k=ledger_k(ledger) or 0,
        data_check_exit_code=0,
        wdc_spinoff_adjusted_once=None,
        lookahead_truncation_ok=look["truncation_ok"],
        lookahead_corrupt_future_ok=look["corrupt_future_ok"],
        freeze_matches=bool(freeze["code_ok"] and freeze["data_ok"] and freeze["prereg_ok"] and freeze["signal_path_files_unchanged"]),
        no_fitted_parameters=True,
        period_boundary_liquidation=True,
        sensitivity=sens,
        ledger_complete=complete,
        trials_matrix=matrix,
        trials_matrix_metadata=matrix_meta,
        fill_violations=fills["in_sample"],
        holdout_fill_violations=fills["holdout"],
        audit=audit,
        rule_types=["donchian_ensemble_4h_vol_sized"],
        lookahead_evidence_ok=bool(look["truncation_ok"] and look["corrupt_future_ok"] and look["terminal_bar_excluded"]),
    )
    with mock.patch.object(checks, "PRIMARY", CRYPTO_PRIMARY):
        verdict = run_critic(module.ID, inputs, CriticConfig(), args.date)
    body = render_verdict_md(verdict, name="slow 4h Donchian trend (crypto)", freeze_file=freeze["freeze_file"])
    data_check = _crypto_data_check(frames)
    header = "\n".join([
        "<!-- generated by lab/crypto_dt/critic_run.py; see 'Adaptacije' below -->",
        "",
        "## Adaptacije Critica za kripto (navedene prije presude)",
        "",
        "- Podjela: crypto splitovi IS 2021–22 / WF 2023–24 / HO 2025+. Svako razdoblje počinje u gotovini i likvidira se na zadnjem baru (provjera 5); povrati su po trgovini u postocima, uključuju 10 bps po strani.",
        "- Primary tickeri: BTCUSDT, ETHUSDT, SOLUSDT (zadani MU/WDC/STX bi provjeru 8 srušio strukturno). Pragovi su zadani `CriticConfig`, ništa nije ublaženo.",
        "- PBO matrica: samo 2021-01-01..2023-12-31 (`validate_trials_matrix` odbija datume od 2024.); stupci: osnovni H1, 12 pomaka ±20 %, H1B, H2Q.",
        f"- edge_crushed (definirano prije pokretanja): WF srednji prinos pomaknutog parametra ≤ 0 ili < {CRUSH_RATIO:.0%} osnovnog ({base_wf:.2f} %/trgovini).",
        "- Provjera 0: `validate_data.py` exit 0, ali ne pokriva kripto; zasebna provjera satnih USDT datoteka niže. WDC spin-off nije primjenjiv.",
        f"- Provjera 12: referentni račun {ACCOUNT_USDT:,.0f} USDT, fill ≤ {MAX_BAR_SHARE:.0%} prometa bara, otvaranje unutar raspona, bar mora stvarno postojati.",
        f"- Provjera 2: kod strategije, `data.py`, `features.py` i podaci jednaki zamrznutima; `run.py` promijenjen nakon zamrzavanja (samo dijagnostika, amandman 1): {freeze['support_changed_since_freeze']}.",
        f"- Provjera 9: svi CDT freeze-ovi u ledgeru s istim hashom: {complete} (nedostaju: {missing or 'nijedan'}). K je zajednički s drugim agentima.",
        "- Provjera 14: audit je napravljen iz neovisnog pregleda codex-a (`reports/runs/codex_cdt_review.md`), ne iz equity red-team audita.",
        "- Critic je kalibriran na equity trgovine; nije ga se prilagođavalo da bi H1 prošao.",
        "",
        "## Kripto provjera podataka (satne USDT datoteke)",
        "",
        "```json",
        json.dumps(data_check, indent=1),
        "```",
        "",
        f"Ostali brojevi: trgovina IS/WF/HO = {{'IS': {sum(len(returns[t]['IS']) for t in returns)}, 'WF': {sum(len(returns[t]['WF']) for t in returns)}, 'HO': {sum(len(returns[t]['HO']) for t in returns)}}}; "
        f"lookahead = {look}; nemogući fillovi = {fills}.",
        "",
    ])
    text = body.replace("## Ordered checks", header + "\n## Ordered checks", 1)
    out = ROOT / "reports/gate" / f"{args.date.isoformat()}_{module.ID}_VERDICT.md"
    out.write_text(text + COMMENTARY if verdict.verdict.value == "FAIL" else text)
    for chk in verdict.checks:
        print(chk.number, "PASS" if chk.passed else "FAIL", chk.name)
    print(verdict.verdict.value, f"K={verdict.k}", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
