#!/usr/bin/env python3
"""Generate docs/research/DATA_INVENTORY.md: what price, news and event data the lab actually has.

Read-only on data. Run:  .venv/bin/python scripts/data_inventory.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "research" / "DATA_INVENTORY.md"
TICKERS = ["MU", "WDC", "STX", "SMH", "AMAT", "LRCX", "KLAC", "SIMO", "RMBS", "MRAM", "ACMR", "SNDK", "DRAM", "SKHY"]
ROLE = {"MU": "primary", "WDC": "primary", "STX": "primary", "SMH": "context (ETF)", "AMAT": "context", "LRCX": "context",
        "KLAC": "context", "SIMO": "context", "RMBS": "context", "MRAM": "side-check", "ACMR": "side-check",
        "SNDK": "watch only", "DRAM": "watch only (ETF)", "SKHY": "watch only (ADR)"}


def daily_row(t: str) -> dict:
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv")
    d["date"] = d["date"].astype(str).str[:10]
    c = d["close"].to_numpy()
    r = pd.Series(c).pct_change().dropna()
    dd = (pd.Series(c) / pd.Series(c).cummax() - 1).min()
    return {"t": t, "role": ROLE[t], "rows": len(d), "first": d["date"].iloc[0], "last": d["date"].iloc[-1],
            "c0": c[0], "c1": c[-1], "mult": c[-1] / c[0], "vol": r.std() * np.sqrt(252), "dd": dd,
            "avgvol": d["volume"].tail(250).mean(), "last_px": c[-1]}


def hourly_row(t: str) -> dict | None:
    p = ROOT / "data" / "hourly" / f"{t}_1h_clean.csv"
    if not p.exists():
        return None
    h = pd.read_csv(p, usecols=["ts", "session", "feed"])
    return {"t": t, "rows": len(h), "reg": int((h["session"] == "regular").sum()), "first": str(h["ts"].iloc[0])[:10],
            "last": str(h["ts"].iloc[-1])[:10]}


def news_stats() -> tuple[Counter, dict, dict, int, tuple[str, str]]:
    seen, per_t, focused, per_year = set(), Counter(), Counter(), defaultdict(Counter)
    lo, hi = "9999", "0000"
    for f in sorted((ROOT / "data" / "news" / "archive").glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            ts = r["created_at"][:10]
            lo, hi = min(lo, ts), max(hi, ts)
            syms = r.get("symbols", [])
            for t in TICKERS:
                if t in syms:
                    per_t[t] += 1
                    per_year[t][ts[:4]] += 1
                    if len(syms) <= 3:
                        focused[t] += 1
    return per_t, focused, per_year, len(seen), (lo, hi)


def main() -> None:
    drows = [daily_row(t) for t in TICKERS]
    hrows = [x for x in (hourly_row(t) for t in TICKERS) if x]
    per_t, focused, per_year, total, (nlo, nhi) = news_stats()
    ev = pd.read_csv(ROOT / "data" / "news" / "events_calendar.csv")
    er = pd.read_csv(ROOT / "data" / "news" / "MU_earnings_dates.csv")
    L = ["# Inventar podataka", "",
         f"Generirano {datetime.now().astimezone().isoformat(timespec='seconds')} skriptom `scripts/data_inventory.py` (samo čitanje).", "",
         "Što lab **stvarno ima** lokalno. Što Alpaca nudi povrh toga: [ALPACA_CAPABILITIES.md](ALPACA_CAPABILITIES.md).", "",
         "## Dnevne cijene (`data/ohlcv/*_1d.csv`)", "",
         "| Dionica | Uloga | Dana | Od | Do | Prvo zatvaranje | Zadnje | Rast | Dnevno kolebanje (god.) | Najveći pad | Prosj. dnevni volumen (zadnjih 250 d) |",
         "|---------|-------|------|----|----|-----------------|--------|------|-------------------------|-------------|---------------------------------------|"]
    for r in drows:
        L.append(f"| {r['t']} | {r['role']} | {r['rows']} | {r['first']} | {r['last']} | {r['c0']:.2f} | {r['c1']:.2f} | ×{r['mult']:.1f} | {r['vol']:.0%} | {r['dd']:.0%} | {r['avgvol']:,.0f} |")
    L += ["", "Napomena: za dionice s kratkom poviješću (SNDK, DRAM, SKHY) i za MRAM/ACMR (kasniji početak) rast nije usporediv s ostalima. "
          "WDC je prilagođen za SanDisk spin-off (×0.68132 prije 2025-02-24).", "",
          "## Satne cijene (`data/hourly/*_1h_clean.csv`)", "",
          "| Dionica | Satnih barova | Od toga regular | Od | Do |", "|---------|---------------|-----------------|----|----|"]
    for r in hrows:
        L.append(f"| {r['t']} | {r['rows']:,} | {r['reg']:,} | {r['first']} | {r['last']} |")
    L += ["", "Satni podaci postoje za 9 dionica (nema ih za SMH, AMAT, LRCX, KLAC, SNDK). Feed je SIP, `adjustment=split`; za testove `session == regular`.", "",
          "## Vijesti (`data/news/archive/*.jsonl`)", "",
          f"Ukupno **{total:,}** jedinstvenih članaka, od {nlo} do {nhi}. Izvor Alpaca / Benzinga, samo naslov i metapodaci (bez punog teksta).", "",
          "| Dionica | Članaka koji je spominju | Od toga fokusirani (≤ 3 simbola) | Po godinama (od najstarije) |", "|---------|--------------------------|----------------------------------|-----------------------------|"]
    for t in TICKERS:
        yrs = " ".join(f"{y[2:]}:{per_year[t][y]}" for y in sorted(per_year[t]))
        L.append(f"| {t} | {per_t[t]:,} | {focused[t]:,} | {yrs or '-'} |")
    L += ["", "Pokrivenost vijestima je neujednačena: mnogo za MU, malo za mali MRAM/ACMR. Prije studije događaja provjeri broj po godini.", "",
          "## Kalendar događaja i zarade", "",
          f"- `events_calendar.csv`: {len(ev)} događaja, tipovi: " + ", ".join(f"{k} ({v})" for k, v in ev["type"].value_counts().items()) + ".",
          f"- `MU_earnings_dates.csv`: {len(er)} Micron izvještaja ({er.iloc[0, 0]} do {er.iloc[-1, 0]}) s gapom otvaranja, reakcijom dana, +5 i +20 dana.", "",
          "## Što lokalno NEMA", "",
          "- Društvene mreže (Reddit/X): nema izvora.",
          "- Puni tekst vijesti i transkripti poziva: nema.",
          "- Fundamentalni podaci (prihodi, marže, zalihe, cijene DRAM/NAND): nema.",
          "- Opcije, kripto, forex: nema (ne trebaju za sada).",
          "- Šira memorijska i poluvodička sfera (npr. NVDA, AMD, AVGO, TSM, INTC, NTAP, PSTG, NLST): nije povučena. Dostupnost se provjerava preko Alpaca asset liste.",
          "- Korejski i japanski memorijski lideri (Samsung, SK hynix na KRX, Kioxia): nisu na Alpaci, SK hynix samo kao ADR SKHY od 2026-07.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("written", OUT.relative_to(ROOT), "| tickers", len(drows), "| news", total)


if __name__ == "__main__":
    main()
