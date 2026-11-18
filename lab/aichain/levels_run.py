"""Run the levels / structure study: S/R placebo test, mechanics event study, per-ticker maps and charts.

    .venv/bin/python -m lab.aichain.levels_run [--no-charts]

Read-only on data; writes only under reports/research/AICHAIN_20261014/swing/. Research only: no orders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from lab.aichain import levels as lv
from lab.aichain import levels_map as lm
from lab.aichain import levels_study as ls
from lab.aichain.sim import COMMON_END
from lab.aichain.universe import audit_ticker

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing"
UNIVERSE = ROOT / "reports" / "research" / "AICHAIN_20261014" / "universe.json"

GROUPS: dict[str, list[str]] = {
    "memory": ["MU", "WDC", "STX"],
    "mem_interface_storage": ["RMBS", "SIMO", "MRAM", "NTAP"],
    "equipment": [
        "AMAT",
        "LRCX",
        "KLAC",
        "ASML",
        "ONTO",
        "MKSI",
        "ENTG",
        "ACMR",
        "FORM",
        "TER",
    ],
    "ai_chips_logic": [
        "NVDA",
        "AMD",
        "AVGO",
        "MRVL",
        "TSM",
        "INTC",
        "ARM",
        "TXN",
        "MCHP",
        "ON",
        "QCOM",
    ],
    "network_servers": ["ANET", "CRDO", "ALAB", "COHR", "LITE", "SMCI", "DELL", "HPE"],
    "cloud": ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "NBIS", "VRT"],
    "crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "metals_indices": [
        "GLD",
        "SLV",
        "GDX",
        "PHAU",
        "PHAG",
        "IGLN_LSE",
        "SPX",
        "NDX",
        "SMH",
        "SOXX",
    ],
}
GROUP_HR = {
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja memorije i pohrana",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Oblak i podatkovni centri",
    "crypto": "Kripto",
    "metals_indices": "Metali, indeksi i ETF-ovi (referentno)",
}
STOCK_GROUPS = {
    "memory",
    "mem_interface_storage",
    "equipment",
    "ai_chips_logic",
    "network_servers",
    "cloud",
}


def select_universe() -> tuple[dict[str, str], dict[str, str]]:
    """Tickers that pass the data rules (ticker -> group) and those skipped (ticker -> reason)."""
    uni = json.loads(UNIVERSE.read_text())
    excluded = {
        t["ticker"]: t.get("exclude_reason", "isključen u universe.json")
        for seg in uni["segments"].values()
        for t in seg["tickers"]
        if not t.get("usable", True)
    }
    use: dict[str, str] = {}
    skipped: dict[str, str] = {}
    for g, tickers in GROUPS.items():
        for tk in tickers:
            if tk in excluded:
                skipped[tk] = excluded[tk]
                continue
            rec = audit_ticker(tk)
            if rec["bars"] == 0:
                skipped[tk] = "CSV ne postoji"
            elif rec["hard_errors"]:
                skipped[tk] = "ne prolazi pravila podataka: " + "; ".join(
                    rec["hard_errors"]
                )
            elif rec["bars"] < 250:
                skipped[tk] = "prekratka povijest"
            else:
                use[tk] = g
    return use, skipped


def verdict_short(sr: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """One-line Croatian verdict for the map pages, derived from the pooled comparison (no spin).

    "Better" = bounce rate CI above 0 or break rate CI below 0 against a control (given a touch). The touch
    rate alone is not evidence of a useful level: a level can be touched often and still break.
    """
    al = sr["all"]
    better, worse, parts = [], [], {}
    for v in ("match", "shift", "rand"):
        dd = al[f"diff_vs_{v}"]
        sign = {}
        for q in ("touch_rate", "bounce_rate", "break_rate"):
            lo, hi = dd[q]["ci95"]
            sign[q] = "plus" if lo > 0 else "minus" if hi < 0 else "nula"
        parts[v] = sign
        if sign["bounce_rate"] == "plus" or sign["break_rate"] == "minus":
            better.append(v)
        if sign["bounce_rate"] == "minus" or sign["break_rate"] == "plus":
            worse.append(v)
    if len(better) == 3 and not worse:
        text = "Test lažnih razina: potvrđene razine se odbijaju češće od lažnih."
    elif better:
        text = "Test lažnih razina: mješovit rezultat, vidi PLACEBO.md."
    elif worse:
        text = "Test lažnih razina: potvrđene razine se ponašaju lošije od lažnih."
    else:
        text = "Test lažnih razina: potvrđene razine se ne ponašaju bolje od nasumičnih (isto odbijanje i probijanje)."
    return text, {k: json.dumps(v) for k, v in parts.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-charts", action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "map").mkdir(exist_ok=True)
    use, skipped = select_universe()
    preps: dict[str, tuple[lv.Prepared, str, int]] = {}
    for tk, g in use.items():
        P = lv.prepare(tk, crypto=g == "crypto")
        n = len(P.bars)
        if g in STOCK_GROUPS:
            cut = (
                int(
                    np.searchsorted(
                        P.bars.dates.values, np.datetime64(COMMON_END), side="right"
                    )
                )
                - 1
            )
        else:
            cut = n - 1
        preps[tk] = (P, g, cut)
        print(
            f"{tk}: {n} bars, last {P.bars.dates[-1].date()}, test cut {P.bars.dates[cut].date()}",
            flush=True,
        )

    rng = np.random.default_rng(ls.SEED)
    df = ls.sr_placebo_rows(preps, rng)
    sr = ls.sr_summary(df, rng)
    ai = ls.event_table(preps, ("2023-01-01", COMMON_END), rng)
    pre = ls.event_table(preps, ("2017-01-01", "2022-12-31"), rng)
    short, parts = verdict_short(sr)
    placebo = {
        "seed": ls.SEED,
        "config": {
            "month_ends": "AI era 2023-01 onward; month-end needs 30 later bars",
            "touch_band_atr": lv.BAND_ATR,
            "bounce_atr": lv.BOUNCE_ATR,
            "break_atr": lv.BREAK_ATR,
            "outcome_bars": lv.OUT_BARS,
            "horizon_bars": ls.HORIZON,
            "min_distance_atr": ls.MIN_DIST_ATR,
            "shift": ls.SHIFT,
            "range_bars": ls.RANGE_BARS,
            "bootstrap": ls.BOOT,
            "bootstrap_unit": "calendar month (all tickers of a month resampled together)",
            "event_spacing_bars": ls.SPACING,
        },
        "universe": {"used": use, "skipped": skipped},
        "context": {
            "median_atr14_pct": float(
                np.median(
                    [
                        float(P.atr[-1] / P.bars.close[-1] * 100)
                        for P, _, _ in preps.values()
                    ]
                )
            ),
            "last_dates": {
                tk: str(P.bars.dates[-1].date()) for tk, (P, _, _) in preps.items()
            },
            "test_cut_dates": {
                tk: str(P.bars.dates[cut].date()) for tk, (P, _, cut) in preps.items()
            },
        },
        "sr": sr,
        "sr_verdict_short": short,
        "sr_ci_signs": parts,
        "mechanics_ai_era": ai,
        "mechanics_pre_ai_context": pre,
    }
    (OUT / "placebo.json").write_text(
        json.dumps(lm.clean(placebo), ensure_ascii=False, indent=1)
    )
    from lab.aichain.levels_report import write_placebo_md

    write_placebo_md(placebo, OUT / "PLACEBO.md", GROUP_HR)

    from lab.aichain import levels_charts as lc

    for tk, (P, g, cut) in preps.items():
        note = "ZADNJI DATUM: " + (
            f"zajednički kraj {COMMON_END} nije primijenjen na kartu; karta koristi zadnji datum tog papira"
            if g in STOCK_GROUPS
            else "zadnji datum tog papira"
        )
        mp = lm.build_map(P, g, short, note)
        (OUT / "map" / f"{tk}.json").write_text(
            json.dumps(lm.clean(mp), ensure_ascii=False, indent=1)
        )
        if not args.no_charts:
            lc.draw(
                P,
                mp,
                OUT / "map" / f"{tk}.png",
                short
                + " Razine su smjernice, a ne zajamčeni odbijanja; nikakvi nalozi.",
            )
        print("map", tk, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
