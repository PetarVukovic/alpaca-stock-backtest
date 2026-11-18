#!/usr/bin/env python3
"""Read-only layout checker for Memory Lab. Mirrors docs/architecture/layout.md.

Reports files in the wrong place or with the wrong name. Never moves or deletes anything.
Exit 1 on errors (unknown top-level entries, misnamed verdicts/freeze files), warnings do not fail.

Run:  .venv/bin/python scripts/check_layout.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".DS_Store", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules", ".git", ".playwright-mcp",
           ".herdr-web-ui"}
TOP_FILES = {".gitignore", ".ignore", ".env", ".mcp.json", "AGENTS.md", "CLAUDE.md", "README.md", "PRIOR_ART.md",
             "STRATEGY_CANDIDATES.md", "requirements.txt", "requirements-dev.txt", "render.yaml"}
TOP_DIRS = {".claude", "PROMPTS", "data", "docs", "graft", "lab", "reports", "scripts", "strategies", "tests"}
LEGACY = {"memory-chips-lab": "nested copy of the 2026-09 zip", "gate": "older duplicate of reports/gate",
          "gate_bundle.tgz": "duplicate archive of gate/"}
DOC_DIRS = {"architecture", "critic", "guides", "research", "news", "team"}
DATE = r"\d{4}-\d{2}-\d{2}"
RULES = {  # directory -> (regex of allowed file names, explanation)
    "data/ohlcv": (r"[A-Z]+_1d\.csv|[A-Z]+_1d\.raw_unadjusted_spinoff\.csv|[A-Z]+_1h\.csv|DATA_NOTES\.txt|HOURLY_NOTES\.txt|README\.md|known_real_moves\.csv", "{TICKER}_1d.csv"),
    "data/hourly": (r"[A-Z]+_1h_clean\.csv|DATA_NOTES\.txt|README\.md", "{TICKER}_1h_clean.csv"),
    "data/intraday": (r"[A-Z]+_(?:5m|1m)_clean\.csv|DATA_NOTES\.txt|README\.md", "{TICKER}_5m_clean.csv"),
    "data/derivs": (r"[A-Z]+_(?:funding|metrics_5m)\.csv|DATA_NOTES\.txt|README\.md", "{SYMBOL}_funding.csv, {SYMBOL}_metrics_5m.csv"),
    "reports/gate": (rf"{DATE}_.+_VERDICT\.md|approved_list\.json|README\.md", "{YYYY-MM-DD}_{ID}_VERDICT.md"),
    "strategies/frozen": (rf"{DATE}_.+\.(json|md)|mu_down5_hold10\.(md|yaml)|README\.md", "{YYYY-MM-DD}_{ID}.json|.md"),
    "reports/data": (r"(?:DATA_CHECK\.md|2026-10-12_RMBS_SIMO_CHECK\.md|2026-10-12_RMBS_SIMO_alpaca\.json|2026-10-12_ecb\.xml|2026-10-13_forex_[a-z_]+\.(?:json|md)|2026-10-14_(?:crypto|binance|binance_derivs|ibkr)_manifest\.json)", "DATA_CHECK.md or registered RMBS/SIMO, forex and crypto provenance"),
}


def check() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    for p in sorted(ROOT.iterdir()):
        n = p.name
        if n in IGNORED:
            continue
        if n in LEGACY:
            warns.append(f"legacy duplicate '{n}' ({LEGACY[n]}); safe to delete once nothing unique remains")
        elif p.is_file() and n not in TOP_FILES:
            errors.append(f"unexpected top-level file '{n}' (see docs/architecture/layout.md)")
        elif p.is_dir() and n not in TOP_DIRS:
            errors.append(f"unexpected top-level directory '{n}/' (see docs/architecture/layout.md)")
    for rel, (pattern, hint) in RULES.items():
        d = ROOT / rel
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.name in IGNORED or f.is_dir():
                continue
            if not re.fullmatch(pattern, f.name):
                errors.append(f"{rel}/{f.name}: name does not match {hint}")
    docs = ROOT / "docs"
    index = (docs / "README.md").read_text(encoding="utf-8") if (docs / "README.md").exists() else ""
    for sub in sorted(p for p in docs.iterdir() if p.is_dir()) if docs.is_dir() else []:
        if sub.name not in DOC_DIRS:
            errors.append(f"docs/{sub.name}/ is not an allowed docs folder {sorted(DOC_DIRS)}")
            continue
        for f in sorted(sub.glob("*.md")):
            if f.name not in index:
                warns.append(f"docs/{sub.name}/{f.name} is not listed in docs/README.md")
    sidx = (ROOT / "scripts" / "README.md").read_text(encoding="utf-8") if (ROOT / "scripts" / "README.md").exists() else ""
    for f in sorted((ROOT / "scripts").glob("*")):
        if f.suffix in {".py", ".sh"} and f.name not in sidx:
            warns.append(f"scripts/{f.name} is not described in scripts/README.md")
    for d in ("data", "strategies", "scripts", "reports", "PROMPTS", "docs"):
        if (ROOT / d).is_dir() and not (ROOT / d / "README.md").exists():
            warns.append(f"{d}/ has no README.md")
    return errors, warns


def main() -> int:
    errors, warns = check()
    for e in errors:
        print("ERROR:", e)
    for w in warns:
        print("WARN: ", w)
    print(f"LAYOUT CHECK: {'FAIL' if errors else 'OK'} | errors={len(errors)} warnings={len(warns)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
