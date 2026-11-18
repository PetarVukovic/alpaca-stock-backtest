"""Runner: `python -m lab.top10.run <module> [--dry]`.

--dry   evaluate and print only (use while developing; nothing is written, no trial is logged).
default freeze the rule (strategies/frozen), register ONE trial in the ledger (K+1), write results and charts to
        reports/research/TOP10_20261014/{ID}/. After this the strategy file is frozen: editing it raises an error.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from datetime import date
from pathlib import Path

from lab import ledger
from lab.top10 import core
from lab.top10.charts import make_charts

ROOT = core.ROOT
OUT = ROOT / "reports/research/TOP10_20261014"
REQUIRED = ["ID", "HYPOTHESIS", "RULES", "UNIVERSE", "PARAMS", "SPLIT_KIND", "weights"]


def _sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--agent", default="unknown")
    args = parser.parse_args(argv)
    module = importlib.import_module(f"lab.top10.strategies.{args.module}")
    missing = [n for n in REQUIRED if not hasattr(module, n)]
    if missing:
        raise SystemExit(f"strategy module is missing: {missing}")
    k = ledger.current_k() + 1
    if args.dry:
        summary, _ = core.evaluate(module, k)
        print(json.dumps(summary, indent=1, default=str))
        return 0
    frozen = ROOT / f"strategies/frozen/{date.today().isoformat()}_{module.ID}.json"
    existing = sorted((ROOT / "strategies/frozen").glob(f"*_{module.ID}.json"))
    if existing:
        frozen = existing[0]
    freeze = {
        "id": module.ID,
        "hypothesis": module.HYPOTHESIS,
        "rules": module.RULES,
        "universe": module.UNIVERSE,
        "params": module.PARAMS,
        "split_kind": module.SPLIT_KIND,
        "splits": core.SPLITS[module.SPLIT_KIND],
        "costs_rt_bps": core.COST_RT_BPS,
        "execution": "decide at close, fill at next open, long-only, no leverage",
        "code_file": f"lab/top10/strategies/{args.module}.py",
        "code_sha256": _sha(module.__file__),
        "timeframe": getattr(module, "TIMEFRAME", "1d"),
        "data_sha256": {
            t: _sha(core.data_path(t, getattr(module, "TIMEFRAME", "1d")))
            for t in module.UNIVERSE
        },
        "status": "research only; not a lab Critic PASS",
    }
    text = json.dumps(freeze, indent=2, sort_keys=True)
    if (
        frozen.exists()
        and json.loads(frozen.read_text()).get("code_sha256") != freeze["code_sha256"]
    ):
        raise SystemExit(
            "strategy code changed after freeze: use a NEW ID (frozen strategies are immutable)"
        )
    if not frozen.exists():
        frozen.write_text(text)
    k = ledger.register_strategy(
        module.ID,
        _sha(frozen),
        agent=args.agent,
        purpose="TOP10 research set 2026-10-14; not Critic",
        unit="frozen_strategy_id",
    )
    summary, bundle = core.evaluate(module, k)
    folder = OUT / module.ID
    folder.mkdir(parents=True, exist_ok=True)
    summary["charts"] = make_charts(summary, bundle, folder)
    summary.update(
        {
            "hypothesis": module.HYPOTHESIS,
            "rules": module.RULES,
            "params": module.PARAMS,
            "freeze_file": str(frozen.relative_to(ROOT)),
        }
    )
    (folder / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print(
        f"{module.ID}: rating={summary['rating']} K={k} trades={summary['trades']['n']} flags={summary['flags']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
