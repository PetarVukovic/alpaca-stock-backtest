"""CLI that turns Codex packages into real verdict files: `python -m lab.critic.runner`.

Reads reports/backtest/{ID}_critic_inputs.json + freeze + ledger + red-team audit, runs the
fail-closed gate with default `CriticConfig`, writes reports/gate/{date}_{ID}_VERDICT.md, and
adds a strategy to approved_list.json only via `update_approved_list` on PASS (never B*).
Idempotent: rerunning overwrites the same verdict files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from lab.contracts import Costs, Verdict
from lab.critic.checks import CriticConfig, CriticInputs, SensitivityResult
from lab.critic.verdict import render_verdict_md, run_critic, update_approved_list

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PREFIX = "B"  # B1/B2/B3 baselines are benchmarks, never candidates


def is_benchmark(strategy_id: str) -> bool:
    return strategy_id[:1] == BENCHMARK_PREFIX and strategy_id[1:2].isdigit()


def _arrays(nested: dict | None) -> dict | None:
    if not nested:
        return None
    return {t: {p: np.asarray(v, dtype=float) for p, v in per.items()} for t, per in nested.items()}


def ledger_k(ledger: Path) -> int | None:
    """Highest K in the trials ledger (None if the file is missing or has no K)."""
    if not ledger.exists():
        return None
    ks = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ks.append(int(json.loads(line).get("k", 0)))
    return max(ks) if ks else None


def load_audit(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _flags_by_part(root: Path, strategy_id: str) -> dict[str, list[str]]:
    """flags of each BacktestResult file ({ID}_{TICKER|ROTATION|BASKET}.json)."""
    out: dict[str, list[str]] = {}
    for f in sorted((root / "reports/backtest").glob(f"{strategy_id}_*.json")):
        if f.name.endswith(("_audit.json", "_critic_inputs.json")):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("strategy_id") == strategy_id and "flags" in d:
            out[d["ticker"]] = d["flags"]
    return out


def find_freeze(root: Path, strategy_id: str) -> Path | None:
    hits = sorted((root / "strategies/frozen").glob(f"*_{strategy_id}.json"))
    return hits[-1] if hits else None


def build_inputs(root: Path, strategy_id: str, audit: dict | None) -> tuple[CriticInputs, str | None]:
    """Map a Codex package to CriticInputs. Returns (inputs, relative freeze path)."""
    pkg = json.loads((root / f"reports/backtest/{strategy_id}_critic_inputs.json").read_text(encoding="utf-8"))
    freeze = find_freeze(root, strategy_id)
    freeze_rel = str(freeze.relative_to(root)) if freeze else None
    freeze_ok = bool(pkg.get("freeze_matches"))
    rule_types: list[str] = []
    if freeze:
        frozen = json.loads(freeze.read_text(encoding="utf-8"))
        rule_types = [frozen["entry"]["type"], frozen["exit"]["type"]]
        # independent check: file on disk must still hash to what the package recorded
        recorded = pkg.get("provenance", {}).get("freeze_sha256")
        freeze_ok = freeze_ok and recorded == hashlib.sha256(freeze.read_bytes()).hexdigest()
    else:
        freeze_ok = False
    flags = _flags_by_part(root, strategy_id)
    boundary = bool(flags) and all("period_boundary_liquidation" in f for f in flags.values())
    ev = pkg.get("lookahead_evidence") or {}
    evidence_ok = (ev.get("truncation_ok") is True and ev.get("corrupt_future_ok") is True
                   and ev.get("terminal_bar_excluded") is True)
    sens = {
        name: SensitivityResult(wf_mean_pct=v.get("wf_mean_pct"), edge_crushed=bool(v.get("edge_crushed")))
        for name, v in (pkg.get("sensitivity") or {}).items()
    } or None
    matrix = pkg.get("trials_matrix")
    k = ledger_k(root / "reports/ledger/trials.jsonl") or pkg["k"]
    inputs = CriticInputs(
        returns=_arrays(pkg["returns"]) or {},
        portfolio_returns=_arrays(pkg.get("portfolio_returns")),
        stressed_returns=_arrays(pkg.get("stressed_returns")),
        costs=Costs(**pkg["costs"]),
        k=k,
        data_check_exit_code=pkg.get("data_check_exit_code"),
        wdc_spinoff_adjusted_once=pkg.get("wdc_spinoff_adjusted_once"),
        lookahead_truncation_ok=pkg.get("lookahead_truncation_ok"),
        lookahead_corrupt_future_ok=pkg.get("lookahead_corrupt_future_ok"),
        freeze_matches=freeze_ok,
        # A frozen file proves immutability, not that parameters were never fitted.
        no_fitted_parameters=pkg.get("no_fitted_parameters") if freeze_ok else None,
        period_boundary_liquidation=boundary,
        sensitivity=sens,
        ledger_complete=pkg.get("ledger_complete"),
        trials_matrix=np.asarray(matrix, dtype=float) if matrix else None,
        trials_matrix_metadata=pkg.get("trials_matrix_metadata"),
        fill_violations=pkg.get("fill_violations"),
        holdout_fill_violations=pkg.get("holdout_fill_violations"),
        audit=audit,
        rule_types=rule_types,
        lookahead_evidence_ok=evidence_ok,
    )
    return inputs, freeze_rel


def process(
    root: Path, strategy_id: str, audit: dict | None, today: date,
    config: CriticConfig | None = None, write: bool = True,
):
    """Run one ID; write the verdict .md and (PASS, non-benchmark only) update approved_list."""
    inputs, freeze_rel = build_inputs(root, strategy_id, audit)
    verdict = run_critic(strategy_id, inputs, config or CriticConfig(), today)
    bench = is_benchmark(strategy_id)
    name = ""
    if freeze_rel:
        name = json.loads((root / freeze_rel).read_text(encoding="utf-8")).get("family", "")
    md = render_verdict_md(verdict, name=name, freeze_file=freeze_rel, benchmark=bench)
    gate = root / "reports/gate"
    fname = f"{today.isoformat()}_{strategy_id}_VERDICT.md"
    if write:
        gate.mkdir(parents=True, exist_ok=True)
        (gate / fname).write_text(md, encoding="utf-8")
        if verdict.verdict == Verdict.PASS and not bench:
            update_approved_list(verdict, gate, f"reports/gate/{fname}", today)
    return verdict, fname


def package_ids(root: Path) -> list[str]:
    suffix = "_critic_inputs.json"
    return sorted(f.name[: -len(suffix)] for f in (root / "reports/backtest").glob(f"*{suffix}"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write Critic verdicts from Codex packages.")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="every ID with a critic_inputs package")
    grp.add_argument("--id", help="a single strategy ID")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--date", type=date.fromisoformat, default=datetime.now(UTC).date())
    args = ap.parse_args(argv)
    ids = package_ids(args.root) if args.all else [args.id]
    audit = load_audit(args.root / "reports/research/redteam_audit.json")
    print(f"audit: {'dostavljen' if audit else 'NIJE dostavljen (provjera 14 pada)'}; K iz ledgera")
    for sid in ids:
        v, fname = process(args.root, sid, audit, args.date)
        failed = [c.number for c in v.checks if not c.passed]
        print(f"{sid}\t{v.verdict.value}\tK={v.k}\tfail={failed}\t{fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
