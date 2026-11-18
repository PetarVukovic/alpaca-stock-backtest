"""Render DATA_QUALITY.md (Croatian) from universe.json. Run after lab.aichain.universe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "reports" / "research" / "AICHAIN_20261014"

REAL_MOVE_NOTES: dict[str, str] = {
    "SIMO 2026-04-29": "dokumentirano u data/ohlcv/known_real_moves.csv (zarade)",
    "ARM 2024-02-08": "volumen višestruko iznad prosjeka, nastavak trenda; izgleda kao stvarni skok nakon zarada (nepotvrđeno vanjskim izvorom)",
    "CRDO 2023-02-15": "volumen oko 6x iznad prosjeka, bez povrata sljedeći dan; izgleda kao stvarni pad nakon objave (nije split 2:1, cijena se nastavlja na novoj razini, nepotvrđeno vanjskim izvorom)",
    "CRDO 2024-12-03": "visok volumen, izgleda kao stvaran skok (nepotvrđeno)",
    "MRAM 2021-11-12": "volumen 92 mil. naspram oko 0,1 mil. dan prije: spekulativni skok tankog papira, stvaran",
    "MRAM 2020-05-08": "volumen 21 mil. naspram oko 0,1 mil.: spekulativni skok tankog papira, stvaran",
    "MRAM 2026-05-11": "volumen 28 mil. nakon niza visokih dana: nastavak ekstremnog trenda tankog papira",
    "ACMR 2024-02-28": "volumen oko 3x iznad prosjeka; skok na zaradama, nastavak sljedeći dan",
    "ACMR 2018-03-06": "rani tanki papir, volumen 7x; stvaran skok, prije AI ere",
    "AMD 2016-04-22": "zarade 2016., stvaran skok, daleko prije AI ere",
    "NBIS 2025-09-09": "veliki volumen (88 mil.), stvaran skok na vijesti o ugovoru; nastavak sljedeći dan",
    "NBIS 2022-02-24": "povijest prije 2024-10-21 je zaustavljena trgovina (druga tvrtka, Yandex); ne koristi se",
    "SMCI 2020-01-14": "kraj razdoblja nelikvidnosti (nulti volumen prije); ne koristi se prije tog datuma",
    "CRWV 2025-04-01": "tjedni nakon izlaska na burzu, stvaran početni skok; papir ionako prekratak",
}


def fmt_issue_moves(r: dict[str, Any]) -> str:
    parts = []
    for m in r.get("big_moves", []):
        key = f"{r['ticker']} {m['date']}"
        parts.append(
            f"{m['date']} {m['ret']:+.1%} ({REAL_MOVE_NOTES.get(key, 'nije objašnjeno, provjeriti')})"
        )
    return "; ".join(parts) if parts else "nema"


def fmt_actions(r: dict[str, Any]) -> str:
    acts = r.get("corporate_actions", [])
    if not acts:
        return "nema poznatih u 2016-2026; generički detektor ne nalazi omjer"
    return "; ".join(f"{a['date']} {a['kind']}: {a['result']}" for a in acts)


def main() -> None:
    u = json.loads((OUT_DIR / "universe.json").read_text())
    L: list[str] = []
    L += [
        "# Kvaliteta podataka: AI lanac (turnir)",
        "",
        "Generirano iz `reports/research/AICHAIN_20261014/universe.json` skriptama `lab/aichain/universe.py` i "
        "`lab/aichain/quality_report.py`. Sve provjere su pokrenute ispočetka (raniji djelomični rezultati su "
        "odbačeni). Sirove CSV datoteke nisu mijenjane. Nikakvi nalozi.",
        "",
        f"**Zajednički završetak podataka (common_end): {u['common_end']}.** Turnir koristi podatke do tog datuma.",
        "",
        "## Što je provjereno i što to znači",
        "",
        "- **Datoteka postoji** (`data/ohlcv/{TICKER}_1d.csv`) i **validate_frame**: cijene su konačni pozitivni brojevi, "
        "unutar svakog dana vrijedi low <= open, close <= high, nema duplikata ni obrnutog redoslijeda datuma, volumen nije negativan.",
        "- **Dani s volumenom 0**: dan bez trgovanja. Niz od 5 ili više takvih dana znači zaustavljenu trgovinu ili delisting; "
        "povijest se tada koristi tek od prvog dana nakon niza (`effective_start`).",
        "- **Razmaci dulji od 5 trgovačkih dana** (više od 7 kalendarskih dana): rupe u podacima.",
        "- **Dnevni pomak veći od 40 %**: može biti stvaran (zarade, vijest) ili greška (split, loš podatak). "
        "Svaki je pregledan prema volumenu i ponašanju sljedećih dana; ništa nije tiho popravljeno. Primjer: ako 1.000 EUR "
        "u dionici preko noći postane 1.450 EUR, to je pomak od +45 %.",
        "- **Korporativne akcije**: split 10:1 znači da se jedna dionica pretvara u deset, pa sirova cijena padne na desetinu, "
        "iako the researcher ne gubi ništa (1.000 EUR ostaje 1.000 EUR). Serija je ispravna ako je već prilagođena, tj. nema skoka "
        "jednakog omjeru. Provjereno za poznate akcije 2016-2026 i generičkim detektorom za svaki pomak veći od 25 %. "
        "Cijene su prilagođene samo za splitove (Alpaca `adjustment=split`); isplaćene dividende nisu uračunate, pa je to "
        "cjenovni, a ne ukupni prinos (utjecaj na te dionice je malen, nepotvrđeno brojkom).",
        "- **Prag upotrebljivosti**: najmanje 250 barova prije 2026. i najmanje 120 barova u AI eri (od 2023-01-01), brojeno "
        "samo od `effective_start` i samo dana s volumenom iznad 0. Papiri ispod praga su samo **za praćenje** (prekratka povijest).",
        "- **Zastarjelost**: datoteka čiji je zadnji datum više od 14 dana iza ostalih isključuje se (nije dopušteno dodavati ni "
        "mijenjati sirove podatke).",
        "",
        "## Isključeni ili samo za praćenje",
        "",
    ]
    L += ["| Ticker | Razlog |", "|---|---|"]
    for e in u["excluded"]:
        r = e["reason"]
        L.append(f"| {e['ticker']} | {r} |")
    L += [
        "",
        "SNDK i CRWV ostaju u izvještaju kao **samo za praćenje**, ali ne ulaze u rang liste. PSTG je isključen jer su lokalni "
        "podaci stali 2026-04-16 (Alpaca povlačenje nije ponovno pokretano po uputi).",
        "",
    ]
    for key, seg in u["segments"].items():
        L += [f"## {seg['name']} (`{key}`)", ""]
        L += [
            "| Ticker | Prvi datum | Početak korištenja | Zadnji datum | Barova | Barova AI era (od 2023) | Upotrebljiv | Napomene |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in seg["tickers"]:
            note = []
            if r.get("zero_volume_days"):
                note.append(f"{r['zero_volume_days']} dana nulti volumen")
            if r.get("gaps_gt_5_trading_days"):
                note.append("razmak " + ", ".join(r["gaps_gt_5_trading_days"][:3]))
            if r.get("big_moves"):
                note.append(f"{len(r['big_moves'])} pomaka >40%")
            if not r["usable"]:
                note.append(r.get("exclude_reason", ""))
            L.append(
                f"| {r['ticker']} | {r['first_date']} | {r['effective_start']} | {r['last_date']} | {r['bars']} | "
                f"{r['bars_ai_era']} | {'da' if r['usable'] else 'ne'} | {'; '.join(note) or '-'} |"
            )
        L += ["", "Pomaci veći od 40 % i korporativne akcije:", ""]
        for r in seg["tickers"]:
            L.append(
                f"- **{r['ticker']}**: pomaci: {fmt_issue_moves(r)}. Akcije: {fmt_actions(r)}."
            )
        L.append("")
    L += [
        "## Samo signal (nikad se ne trguje)",
        "",
        "| Ticker | Prvi datum | Zadnji datum | Barova | Upotrebljiv kao signal | Napomena |",
        "|---|---|---|---|---|---|",
    ]
    for r in u["signal_only"]:
        note = "; ".join(r.get("notes", [])) or (
            "; ".join(r["hard_errors"]) if r["hard_errors"] else "-"
        )
        if r["ticker"] in ("NDX", "VIX"):
            note = f"{len(r['hard_errors'])} upozorenja: {note}; indeks, bez volumena"
        L.append(
            f"| {r['ticker']} | {r['first_date']} | {r['last_date']} | {r['bars']} | {'da' if r['usable'] else 'ne'} | {note} |"
        )
    L += [
        "",
        "SMH, SOXX i XLK su američki ETF-ovi: služe samo kao signal. **the researcher ih ne može pouzdano kupiti** (za EU male ulagače često "
        "nema KID dokumenta); dostupnost je nepotvrđena. NDX i VIX su indeksi i ne mogu se kupiti. Za NDX i VIX unutar-dnevni "
        "low/high nisu dosljedni (zatvaranje izvan raspona), zato se koristi samo zatvaranje (close).",
        "",
        "## Napomene o povijesti",
        "",
        "- **WDC**: povijest prije 2025-02-24 već je pomnožena s 0,68132 (spin-off SanDisk-a). Omjer prema raw datoteci provjeren; "
        "ne prilagođavati ponovno. Kretanje na dan odvajanja iznosi +4,7 %, bez lažnog skoka.",
        "- **NBIS**: povijest do 2022 je Yandex N.V., zatim zaustavljena trgovina do 2024-10-21; koristi se samo od 2024-10-21 "
        "(oko 500 stvarnih barova, to je i cijela AI era koja se računa).",
        "- **SMCI**: 2018-2020 delisting, ravne cijene s volumenom 0 do 2020-01-13; koristi se od 2020-01-14. Split 10:1 iz 2024. "
        "nema skoka omjera.",
        "- **Kratka povijest** (ARM od 2023-09, ALAB od 2024-03, CRDO od 2022-01): zadovoljavaju prag, ali manje barova znači "
        "nesigurnije zaključke.",
        "- Dnevni podaci svježe povučenih papira (20 njih) završavaju 2026-10-13, ostali 2026-10-05 do 2026-10-09; zato je zajednički "
        "kraj 2026-10-05.",
    ]
    (OUT_DIR / "DATA_QUALITY.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
