"""Catalog every local price file by asset class and timeframe, with quality checks. Read-only.

Usage: .venv/bin/python scripts/data_catalog.py
Writes docs/research/DATA_CATALOG.md (Croatian): coverage, gaps, zero-volume bars, broken OHLC rows, staleness,
which TOP10 strategies already use each ticker, and which strategy families fit each asset class.
"""

import importlib
import pkgutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FOLDERS = {
    "1d": ("data/ohlcv", "_1d.csv"),
    "1h": ("data/hourly", "_1h_clean.csv"),
    "5m": ("data/intraday", "_5m_clean.csv"),
    "1m": ("data/intraday", "_1m_clean.csv"),
}
CLASSES = {
    "Memorija i pohrana (primarno)": "MU WDC STX RMBS SIMO SNDK DRAM SKHY MRAM ACMR NTAP PSTG",
    "Poluvodiči i oprema": "NVDA AMD AVGO TSM ASML AMAT LRCX KLAC INTC MRVL ENTG FORM MKSI ONTO SMCI QCOM TXN MCHP ON SOXX SOXL SMH EWY",
    "Veliki tehnološki (AI potražnja)": "MSFT GOOGL AMZN META ORCL DELL XLK QQQ",
    "Zlato i srebro (ETF)": "GLD SLV IAU SGOL PHAG PHAU PPLT CPER",
    "Rudari metala": "GDX GDXJ SIL SILJ NEM GOLD PAAS WPM FCX",
    "Energija i roba": "USO UNG DBC",
    "Kripto USD (Alpaca)": "BTCUSD ETHUSD SOLUSD XRPUSD LTCUSD LINKUSD DOGEUSD AVAXUSD",
    "Kripto USDT (Binance, duga povijest)": "BTCUSDT ETHUSDT BNBUSDT LTCUSDT XRPUSDT LINKUSDT DOGEUSDT SOLUSDT AVAXUSDT",
    "Kripto dionice i ETF-ovi": "IBIT ETHA MSTR COIN MARA",
    "Širi indeksi, kamate, dolar": "SPY IWM DIA UUP TLT IEF HYG EURUSD",
}
FAMILIES = {
    "Memorija i pohrana (primarno)": "trend s filtrom, vodeći-pratitelj (oprema vodi memoriju), rotacija po relativnoj snazi, događaji (zarade), proboj nakon smirivanja volatilnosti",
    "Poluvodiči i oprema": "vodeći signal za memoriju, ciklus potražnje, relativna snaga unutar sektora, trend",
    "Veliki tehnološki (AI potražnja)": "širina trenda kao signal za AI potražnju, makro filtar rizika",
    "Zlato i srebro (ETF)": "trend uz filtar dolara i kamata, omjer zlato/srebro, rotacija zlato-srebro-novac",
    "Rudari metala": "polugu na metal (rudari prate metal s pojačanjem), omjer rudari/metal kao signal raspoloženja",
    "Energija i roba": "trend i makro filtar, kontekst inflacije",
    "Kripto USD (Alpaca)": "ista pravila kao USDT, ali kraća povijest (od 2021.); odgovara cijenama na IBKR-u",
    "Kripto USDT (Binance, duga povijest)": "trend, proboj nakon smirivanja volatilnosti, satni trend uz filtar režima, jednodnevni obrasci (dan u tjednu, sat u danu)",
    "Kripto dionice i ETF-ovi": "razlika između ETF-a i spota, rizik-on signal, trend",
    "Širi indeksi, kamate, dolar": "makro filtri (dolar, obveznice, kreditni rizik) za ostale klase",
}


def used_by():
    """Map ticker -> TOP10 strategy IDs whose UNIVERSE contains it."""
    mapping = {}
    package = importlib.import_module("lab.top10.strategies")
    for info in pkgutil.iter_modules(package.__path__):
        try:
            module = importlib.import_module(f"lab.top10.strategies.{info.name}")
        except Exception as error:  # a broken strategy module must not stop the catalog
            print(f"skipped {info.name}: {error}")
            continue
        for ticker in getattr(module, "UNIVERSE", []):
            mapping.setdefault(ticker, []).append(module.ID.replace("TOP_", ""))
    return mapping


def inspect(path, timeframe, is_crypto=False):
    frame = pd.read_csv(path)
    key = "date" if timeframe == "1d" else "ts"
    stamp = pd.to_datetime(frame[key], utc=True)
    n = len(frame)
    broken = int(
        (
            (frame["high"] < frame["low"])
            | (frame["close"] > frame["high"] * 1.0001)
            | (frame["close"] < frame["low"] * 0.9999)
            | (frame["open"] <= 0)
        ).sum()
    )
    zero_volume = (
        float((frame["volume"] <= 0).mean()) if "volume" in frame else float("nan")
    )
    if timeframe == "1d":
        days = stamp.dt.normalize().drop_duplicates()
        gaps = max(0, len(pd.bdate_range(days.iloc[0], days.iloc[-1])) - len(days))
    else:
        step = {
            "1h": pd.Timedelta("1h"),
            "5m": pd.Timedelta("5min"),
            "1m": pd.Timedelta("1min"),
        }[timeframe]
        jump = stamp.diff()
        gaps = int(
            (
                (jump > step * 3)
                & (jump < pd.Timedelta("6h") if not is_crypto else True)
            ).sum()
        )  # stock nights are not gaps
    return {
        "rows": n,
        "first": str(stamp.iloc[0].date()),
        "last": str(stamp.iloc[-1].date()),
        "gaps": gaps,
        "broken": broken,
        "zero_volume": zero_volume,
        "duplicates": int(stamp.duplicated().sum()),
    }


def main():
    usage = used_by()
    out = [
        "# Katalog podataka",
        "",
        f"Generirano {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} skriptom `scripts/data_catalog.py` (samo čitanje).",
        "",
        "Cilj: imati što više kvalitetnih podataka za buduće backtestove, po klasi imovine i razini (dnevno, satno, 5 i 1 minuta).",
        "Stupac **Rupe** broji propuštene radne dane (dnevno) ili prekide dulje od 3 koraka (intraday). Kod dionica to uglavnom su blagdani,",
        "kod kripta (trguje 24/7) rupa je prava praznina. **Loši redovi** su barovi s nemogućim cijenama (high ispod low i slično).",
        "Najnoviji datum kod većine dionica je 8. do 9. listopada: datoteke se ne dopunjavaju same, treba novi pull.",
        "",
    ]
    total_rows = 0
    for klass, tickers in CLASSES.items():
        out += [
            f"## {klass}",
            "",
            f"Porodice strategija koje tu imaju smisla: {FAMILIES[klass]}.",
            "",
            "| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for ticker in tickers.split():
            for timeframe, (folder, suffix) in FOLDERS.items():
                path = ROOT / folder / f"{ticker}{suffix}"
                if not path.exists():
                    continue
                info = inspect(path, timeframe, ticker.endswith(("USD", "USDT")))
                total_rows += info["rows"]
                vol = (
                    "–"
                    if info["zero_volume"] != info["zero_volume"]
                    else f"{info['zero_volume'] * 100:.1f} %"
                )
                used = (
                    ", ".join(usage.get(ticker, []))
                    if timeframe in ("1d", "1h", "5m")
                    else ""
                )
                rows_text = f"{info['rows']:,}".replace(",", ".")
                out.append(
                    f"| {ticker} | {timeframe} | {rows_text} | {info['first']} | {info['last']} | {info['gaps']} | "
                    f"{info['broken']} | {vol} | {used} |"
                )
        out.append("")
    out += [
        "## Ukupno",
        "",
        f"Redaka u svim katalogiziranim datotekama: {total_rows:,}.".replace(",", "."),
        "",
        "## Što dalje za kvalitetu podataka",
        "",
        "- Dopuna do danas: `pull_alpaca.py` ne prepisuje postojeće datoteke, pa treba skripta koja dopisuje samo nove barove.",
        "- Kripto USD na satnoj i 5-minutnoj razini nije povučen (Alpaca API je spor); Binance USDT to pokriva dublje.",
        "- Fizičko zlato/srebro i futures (XAU, GC, SI) nisu u Alpaci; moguće preko IBKR-a kasnije.",
        "- Prije svakog backtesta i dalje vrijedi `scripts/validate_data.py` (izlaz 1 znači: bez backtesta).",
    ]
    target = ROOT / "docs/research/DATA_CATALOG.md"
    target.write_text("\n".join(out) + "\n")
    print("written", target, "rows", total_rows)


if __name__ == "__main__":
    main()
