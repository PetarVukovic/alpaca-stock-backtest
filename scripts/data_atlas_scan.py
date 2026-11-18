#!/usr/bin/env python3
"""Scan every local price file once and write the inventory used by the data atlas page. Read-only on data.

Output: reports/research/DATA_ATLAS_20261014/inventory.json
Run:    .venv/bin/python scripts/data_atlas_scan.py
Nothing is downloaded and no order is sent. Source labels come from the pull scripts and manifests in
reports/data/ (see SOURCE_RULES), not from the file contents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "research" / "DATA_ATLAS_20261014"
DATA = ROOT / "data"

CRYPTO_USDT = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "LTCUSDT", "XRPUSDT", "LINKUSDT", "DOGEUSDT", "SOLUSDT", "AVAXUSDT"}
CRYPTO_USD = {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "LTCUSD", "LINKUSD", "DOGEUSD", "AVAXUSD"}
FOREX = {"EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "USDJPY"}
INDEX = {"SPX", "NDX", "VIX"}
IBKR_EU = {"PHAU", "PHAG", "IGLN_LSE", "ISLN_LSE"}

CLASS_OF: dict[str, list[str]] = {
    "Memorija i pohrana": "MU WDC STX RMBS SIMO SNDK DRAM SKHY MRAM ACMR NTAP PSTG".split(),
    "Oprema za čipove": "AMAT LRCX KLAC ASML ONTO MKSI ENTG FORM TER".split(),
    "AI čipovi i logika": "NVDA AMD AVGO MRVL TSM INTC ARM TXN MCHP ON QCOM".split(),
    "Mreže i serveri": "ANET CRDO ALAB COHR LITE SMCI DELL HPE VRT".split(),
    "Cloud": "MSFT AMZN GOOGL META ORCL NBIS CRWV".split(),
    "ETF-ovi poluvodiča": "SMH SOXX SOXL XLK EWY".split(),
    "Zlato, srebro, rudari (SAD)": "GLD SLV IAU SGOL PPLT CPER GDX GDXJ SIL SILJ NEM GOLD PAAS WPM FCX".split(),
    "Zlato i srebro (EU, IBKR)": ["PHAU", "PHAG", "IGLN_LSE", "ISLN_LSE"],
    "Energija i roba": "USO UNG DBC".split(),
    "Kripto (USDT, Binance)": sorted(CRYPTO_USDT),
    "Kripto (USD, Alpaca)": sorted(CRYPTO_USD),
    "Kripto dionice i ETF": "IBIT ETHA MSTR COIN MARA".split(),
    "Široko tržište i kamate": "SPY QQQ IWM DIA UUP TLT IEF HYG".split(),
    "Indeksi (IBKR)": ["SPX", "NDX", "VIX"],
    "Forex (IBKR)": sorted(FOREX),
}
CLASS_BY_TICKER = {t: c for c, ts in CLASS_OF.items() for t in ts}


def source_of(ticker: str) -> str:
    base = ticker.split("_")[0] if ticker not in IBKR_EU else ticker
    if ticker in CRYPTO_USDT:
        return "Binance spot (data.binance.vision), USDT"
    if ticker in CRYPTO_USD:
        return "Alpaca crypto (USD)"
    if ticker in FOREX:
        return "IBKR MidPoint (forex)"
    if ticker in INDEX:
        return "IBKR (indeks, Last)"
    if ticker in IBKR_EU:
        return "IBKR (EU ETC / UCITS)"
    del base
    return "Alpaca SIP, split-adjusted"


def read_times(path: Path) -> tuple[pd.DatetimeIndex, pd.DataFrame] | None:
    head = pd.read_csv(path, nrows=0).columns.tolist()
    tcol = next((c for c in ("ts", "timestamp", "date") if c in head), None)
    if tcol is None:
        return None
    use = [c for c in (tcol, "open", "high", "low", "close", "volume") if c in head]
    df = pd.read_csv(path, usecols=use)
    ts = pd.to_datetime(df[tcol], utc=True, errors="coerce", format="mixed")
    df = df.drop(columns=[tcol])
    df.index = pd.DatetimeIndex(ts)
    return df.index, df


def scan_file(path: Path, timeframe: str, kind: str) -> dict[str, Any] | None:
    got = read_times(path)
    if got is None:
        return None
    idx, df = got
    idx = idx[~idx.isna()]
    if len(idx) == 0:
        return None
    ticker = path.name.split(f"_{timeframe}")[0] if f"_{timeframe}" in path.name else path.stem
    steps = pd.Series(idx).diff().dropna()
    bad_ohlc = 0
    if {"open", "high", "low", "close"} <= set(df.columns):
        hi, lo = df["high"], df["low"]
        bad_ohlc = int(((hi < lo) | (df["close"] > hi + 1e-9) | (df["close"] < lo - 1e-9) | (df["open"] > hi + 1e-9) | (df["open"] < lo - 1e-9)).sum())
    zero_vol = int((df["volume"].fillna(0) == 0).sum()) if "volume" in df.columns else None
    has_vol = "volume" in df.columns and df["volume"].notna().any()
    big_gap_days = float((steps.dt.total_seconds() / 86400).max()) if len(steps) else 0.0
    return {
        "path": str(path.relative_to(ROOT)),
        "kind": kind,
        "timeframe": timeframe,
        "ticker": ticker,
        "class": CLASS_BY_TICKER.get(ticker.split("_20")[0], "Terminski ugovori (IBKR)" if kind == "futures" else "Ostalo"),
        "source": "IBKR (terminski ugovor, Last)" if kind == "futures" else source_of(ticker),
        "rows": int(len(idx)),
        "first": str(idx.min())[:19],
        "last": str(idx.max())[:19],
        "median_step_s": float(steps.dt.total_seconds().median()) if len(steps) else None,
        "max_gap_days": round(big_gap_days, 2),
        "dup_ts": int(idx.duplicated().sum()),
        "bad_ohlc_rows": bad_ohlc,
        "zero_volume_rows": zero_vol,
        "has_volume": bool(has_vol),
        "size_mb": round(path.stat().st_size / 1048576, 3),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    jobs: list[tuple[Path, str, str]] = []
    for p in sorted((DATA / "ohlcv").glob("*_1d.csv")):
        if "raw_unadjusted" in p.name:
            continue
        jobs.append((p, "1d", "daily"))
    for p in sorted((DATA / "ohlcv").glob("*_1h.csv")):
        jobs.append((p, "1h", "raw_hourly"))
    for p in sorted((DATA / "hourly").glob("*_1h_clean.csv")):
        jobs.append((p, "1h", "hourly"))
    for p in sorted((DATA / "intraday").glob("*_5m_clean.csv")):
        jobs.append((p, "5m", "intraday"))
    for p in sorted((DATA / "intraday").glob("*_1m_clean.csv")):
        jobs.append((p, "1m", "intraday"))
    for p in sorted((DATA / "archive" / "ibkr_contracts").glob("*.csv")):
        tf = "1d" if p.name.endswith("_1d.csv") else ("1h" if "_1h_" in p.name else "5m")
        jobs.append((p, tf, "futures"))
    for i, (p, tf, kind) in enumerate(jobs):
        row = scan_file(p, tf, kind)
        if row is not None:
            items.append(row)
        if i % 40 == 0:
            print(i, "/", len(jobs), flush=True)
    derivs = []
    for p in sorted((DATA / "derivs").glob("*.csv")):
        df = pd.read_csv(p)
        t = pd.to_datetime(df["ts"], utc=True, errors="coerce", format="mixed").dropna()
        derivs.append(
            {
                "path": str(p.relative_to(ROOT)),
                "symbol": p.name.split("_")[0],
                "what": "funding" if "funding" in p.name else "metrics_5m",
                "rows": int(len(df)),
                "first": str(t.min())[:19],
                "last": str(t.max())[:19],
                "columns": [c for c in df.columns if c != "ts"],
                "size_mb": round(p.stat().st_size / 1048576, 2),
            }
        )
    news: dict[str, Any] = {}
    for p in sorted((DATA / "news").rglob("*")):
        if p.is_file():
            n = sum(1 for _ in p.open("rb")) if p.suffix in {".jsonl", ".csv"} else None
            news[str(p.relative_to(ROOT))] = {"lines": n, "size_mb": round(p.stat().st_size / 1048576, 3)}
    arch = {}
    for p in sorted((DATA / "archive").iterdir()):
        files = [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else [p]
        arch[p.name] = {"files": len(files), "size_mb": round(sum(f.stat().st_size for f in files) / 1048576, 2)}
    (OUT / "inventory.json").write_text(json.dumps({"files": items, "derivs": derivs, "news": news, "archive": arch}, indent=1))
    print(len(items), "files scanned")


if __name__ == "__main__":
    main()
