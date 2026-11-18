#!/usr/bin/env python3
"""Merge archived completed Alpaca daily bars and document the exact data cut.

Offline only: no network, credentials, orders, or strategy execution.
The raw API responses were fetched separately using read-only GET requests.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/archive/c13c_20261009"
OUT = ROOT / "reports/research/C13C_20261009"
SYMBOLS = ["MU", "WDC", "STX", "SIMO", "RMBS", "SMH", "AMAT", "LRCX", "KLAC", "MRAM", "ACMR", "SNDK", "SKHY", "DRAM"]
FIELDS = {"date": "t", "open": "o", "high": "h", "low": "l", "close": "c", "volume": "v", "vwap": "vw", "trades": "n"}
REFRESH_FROM = "2026-10-05"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_payload(name: str) -> dict:
    payload = json.loads((ARCHIVE / f"{name}.json").read_text())
    if payload["http_status"] != 200:
        raise ValueError(f"Unsuccessful API response: {name}")
    return payload


def main() -> None:
    clock = read_payload("clock")
    now = datetime.fromisoformat(clock["body"]["timestamp"])
    calendar = read_payload("calendar")
    completed = [row["date"] for row in calendar["body"] if datetime.fromisoformat(row["date"] + "T" + row["close"]).replace(tzinfo=ZoneInfo("America/New_York")) < now]
    cutoff = max(completed)
    if cutoff != "2026-10-08":
        raise ValueError("Unexpected cutoff; review instead of silently changing study dates")
    raw = read_payload("daily_sip")
    if raw["body"].get("next_page_token"):
        raise ValueError("Incomplete API pagination")
    corporate = read_payload("corporate_actions")
    actions = corporate["body"].get("corporate_actions", {})
    if any(rows for kind, rows in actions.items() if kind != "cash_dividends"):
        raise ValueError("New non-dividend corporate action needs manual review")
    if corporate["body"].get("next_page_token"):
        raise ValueError("Incomplete corporate-action pagination")
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "cutoff": cutoff, "clock": clock["body"], "last_completed_session": cutoff,
        "refresh_from": REFRESH_FROM, "feed_new_rows": "sip", "adjustment": "split",
        "source": "Alpaca REST API GET; hosted MCP clock failed with timeout",
        "intraday_excluded": "2026-10-09", "corporate_actions": actions,
        "archive": str(ARCHIVE.relative_to(ROOT)), "symbols": {},
        "limitations": ["Same-provider refetch, not independent external confirmation.", "Historical daily files have inherited mixed SIP/IEX provenance; historical rows were not silently replaced.", "Current-symbol universe is selected retrospectively, not survivorship-bias-free.", "Price series excludes dividends; WDC existing manual spin-off adjustment retained exactly once.", "Hourly data not refreshed and must not be presented as current to the daily cutoff."]}
    OUT.mkdir(parents=True, exist_ok=True)
    backup = ARCHIVE / "originals"
    backup.mkdir(exist_ok=True)
    for ticker in SYMBOLS:
        path = ROOT / f"data/ohlcv/{ticker}_1d.csv"
        old_bytes = path.read_bytes()
        old_lines = old_bytes.decode().splitlines(keepends=True)
        old = pd.read_csv(io.BytesIO(old_bytes)).set_index("date")
        bars = raw["body"]["bars"][ticker]
        valid = {bar["t"][:10]: bar for bar in bars if bar["t"][:10] <= cutoff}
        expected = {day for day in completed if REFRESH_FROM <= day <= cutoff}
        if not expected.issubset(valid):
            raise ValueError(f"{ticker}: missing fresh completed session")
        overlaps = 0
        for day, bar in valid.items():
            if day in old.index and day < REFRESH_FROM:
                for col in ("open", "high", "low", "close", "volume"):
                    if not np.isclose(float(old.at[day, col]), float(bar[FIELDS[col]]), rtol=0, atol=1e-8):
                        raise ValueError(f"{ticker}: historical overlap differs {day} {col}")
                overlaps += 1
        for day in expected:
            bar = valid[day]
            if not (0 < bar["l"] <= min(bar["o"], bar["c"]) <= max(bar["o"], bar["c"]) <= bar["h"] and bar["v"] >= 0):
                raise ValueError(f"{ticker}: invalid fresh bar {day}")
        preserved = [old_lines[0]] + [line for line in old_lines[1:] if line.split(",", 1)[0] < REFRESH_FROM]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(FIELDS), lineterminator="\n")
        for day in sorted(expected):
            writer.writerow({col: day if col == "date" else valid[day][key] for col, key in FIELDS.items()})
        new_bytes = ("".join(preserved) + stream.getvalue()).encode()
        original = backup / path.name
        if not original.exists():
            shutil.copy2(path, original)
        path.write_bytes(new_bytes)
        d = pd.read_csv(path)
        post_preserved = [line for line in path.read_bytes().decode().splitlines(keepends=True)[1:] if line.split(",", 1)[0] < REFRESH_FROM]
        assert post_preserved == preserved[1:], "Pre-refresh history changed"
        first = str(d.date.iloc[0])
        actual = set(d.date)
        expected_history = {day for day in completed if max("2021-01-01", first) <= day <= cutoff}
        gap = sorted(expected_history - actual)
        if gap:
            raise ValueError(f"{ticker}: missing calendar sessions: {gap}")
        corrections = {}
        source_original = pd.read_csv(original).set_index("date")
        for day in expected & set(source_original.index):
            diff = {col: {"old": float(source_original.at[day, col]), "new": valid[day][FIELDS[col]]} for col in list(FIELDS)[1:] if not np.isclose(float(source_original.at[day, col]), float(valid[day][FIELDS[col]]), rtol=0, atol=1e-8)}
            if diff:
                corrections[day] = diff
        manifest["symbols"][ticker] = {
            "path": str(path.relative_to(ROOT)), "rows": len(d), "first": first, "last": str(d.date.iloc[-1]),
            "last_close": float(d.close.iloc[-1]), "rows_from_2022": int((d.date >= "2022-01-01").sum()),
            "warmup_before_2022": int((d.date < "2022-01-01").sum()),
            "warmup_200_available_at_2022": int((d.date < "2022-01-01").sum()) >= 200,
            "watch_only": ticker in {"SNDK", "SKHY", "DRAM"},
            "original_sha256": sha(original.read_bytes()), "current_sha256": sha(new_bytes),
            "preserved_history_sha256": sha("".join(preserved[1:]).encode()),
            "overlap_ohlcv_matching_sessions": overlaps, "calendar_missing_sessions": gap,
            "completed_partial_corrections": corrections,
            "new_rows": sorted(expected - set(source_original.index)),
            "discarded_api_dates": sorted({b["t"][:10] for b in bars if b["t"][:10] > cutoff})}
    wdc = pd.read_csv(ROOT / "data/ohlcv/WDC_1d.csv").set_index("date")
    original_wdc = pd.read_csv(ROOT / "data/ohlcv/WDC_1d.raw_unadjusted_spinoff.csv").set_index("date")
    shared = wdc.loc[wdc.index < "2025-02-24"].index.intersection(original_wdc.index)
    ratios = wdc.loc[shared, "close"] / original_wdc.loc[shared, "close"]
    assert np.allclose(ratios, 0.68132, rtol=1e-5)
    manifest["wdc_adjustment_check"] = {"factor": 0.68132, "compared_pre_spinoff_rows": len(shared), "min_ratio": float(ratios.min()), "max_ratio": float(ratios.max()), "pass": True, "applied_again": False}
    manifest["raw_payload_sha256"] = {name: sha((ARCHIVE / f"{name}.json").read_bytes()) for name in ["clock", "calendar", "daily_sip", "corporate_actions"]}
    (OUT / "DATA.json").write_text(json.dumps(manifest, indent=2) + "\n")
    lines = ["# Podaci C13C — provjera i dovršene sjednice", "", f"Presjek: **{cutoff}**, posljednja završena američka sjednica pri dohvaćanju. Alpaca clock: `{clock['body']['timestamp']}`, tržište otvoreno. Današnji 9. listopada nije završen.", "", "## Dohvat i promjene", "", "Alpaca MCP clock vratio je timeout. Izravni Alpaca REST GET uspješno je vratio sat, kalendar, SIP dnevne cijene (`adjustment=split`) i korporativne akcije. Nema naloga. Kalendar obuhvaća 2021–2026; svi odgovori, parametri i vremena dohvaćanja spremljeni su u arhivi bez vjerodajnica.", "", "API je zbog uključive granice vratio i današnju svijeću 2026-10-09. Izričito je odbačena. Svi prethodni redovi do uključivo 2026-10-02 sačuvani su bez promjene. Nepotpuni redak 2026-10-05 zamijenjen je dovršenim; dodani su 6., 7. i 8. listopada. Izvorne datoteke i njihove vremenske oznake sačuvane su u `data/archive/c13c_20261009/originals/`.", "", "WDC prije 2025-02-24 ostaje prilagođen točno jednom faktorom 0.68132. Nije ponovno prilagođavan. Provjeren je omjer sa sirovom izvornom datotekom. Nove akcije u odgovoru bile su samo isplate dividendi STX/SKHY, ne splitovi.", "", "## Pokrivenost", "", "| Simbol | Početak | Kraj | Redova od 2022. | Zagrijavanje prije 2022. | Uloga |", "|---|---|---|---:|---:|---|"]
    for ticker, info in manifest["symbols"].items():
        role = "samo praćenje, kratka povijest" if info["watch_only"] else ("sekundarno, veći trošak" if ticker in {"MRAM", "ACMR"} else "istraživanje / kontekst")
        lines.append(f"| {ticker} | {info['first']} | {info['last']} | {info['rows_from_2022']} | {info['warmup_before_2022']} | {role} |")
    lines += ["", "Nema nedostajućih burzovnih sjednica između 2021. (ili početka instrumenta) i presjeka. Za dugopovijesne instrumente postoji više od 200 dana zagrijavanja prije 2022. SNDK, SKHY i DRAM ne smiju se predstavljati kao usporediv test od 2022.; SKHY i DRAM nemaju ni 200 dnevnih opažanja do presjeka.", "", "## Provjere i granice dokaza", "", "- Svih 5 preklopljenih dovršenih sjednica od 28. rujna do 2. listopada podudara se u OHLCV za svih 14 simbola (70 uspoređenih svijeća). To je ponovni dohvat od istog pružatelja, nije neovisna potvrda.", "- SHA-256 izvornih, konačnih i nepromijenjenih povijesnih dijelova nalazi se u DATA.json. Sirovi dohvat također ima hash.", "- Povijest dnevnih podataka ima naslijeđeno podrijetlo SIP/IEX; ne tvrdi se da je sva povijest iz jednog homogenog feeda. Svježa četiri dana jesu SIP.", "- Današnji izbor kompanija ima pristranost odabira; ovo nije povijesni univerzum koji uključuje propale i izlistane kompanije.", "- Cijene su split-adjusted; dividende nisu uključene u ukupni prinos. WDC ručna prilagodba je dokumentirana iznimka.", "- Satni podaci nisu osvježavani i nisu osnova ovog dnevnog istraživanja.", "- Popis vijesti i reakcija nije neovisno provjeren kao potpuna baza point-in-time podataka; ne koristiti buduće ishode iz njega za odluke.", "", "## Validator", "", "Pokrenuti `scripts/validate_data.py --through 2026-10-08 --report reports/research/C13C_20261009/DATA_CHECK.md` i evidentirati rezultat prije backtesta. Ovaj dokument sam nije Critic PASS.", ""]
    (OUT / "DATA.md").write_text("\n".join(lines))
    print(json.dumps({"cutoff": cutoff, "tickers": len(SYMBOLS), "refreshed_days": 4, "report": str(OUT / "DATA.md")}))


if __name__ == "__main__":
    main()
