"""Pull long crypto history from the public Binance archive (data.binance.vision, no keys, GET only).

Why: Alpaca crypto starts 2021-01-01; this archive goes back to 2017 and has 1m/5m/1h/1d bars.
Prices are USDT pairs (not USD like IBKR/Alpaca), so treat them as the same market with a small basis, not identical.
Output: data/ohlcv/{SYM}_1d.csv, data/hourly/{SYM}_1h_clean.csv, data/intraday/{SYM}_{5m,1m}_clean.csv and
reports/data/2026-10-14_binance_manifest.json. Existing files are overwritten with the same deterministic export.
"""

import hashlib
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://data.binance.vision/data/spot"
SYMBOLS = {
    "BTCUSDT": "2017-08",
    "ETHUSDT": "2017-08",
    "BNBUSDT": "2017-11",
    "LTCUSDT": "2017-12",
    "XRPUSDT": "2018-05",
    "LINKUSDT": "2019-01",
    "DOGEUSDT": "2019-07",
    "SOLUSDT": "2020-08",
    "AVAXUSDT": "2020-09",
}
PLAN = {  # interval -> (output template, symbols, first month override)
    "1d": ("data/ohlcv/{s}_1d.csv", list(SYMBOLS), None),
    "1h": ("data/hourly/{s}_1h_clean.csv", list(SYMBOLS), None),
    "5m": ("data/intraday/{s}_5m_clean.csv", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], None),
    "1m": ("data/intraday/{s}_1m_clean.csv", ["BTCUSDT", "ETHUSDT"], "2023-01"),
}
COLS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "tb_base",
    "tb_quote",
    "ignore",
]


def fetch(url):
    response = requests.get(url, timeout=60)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        with archive.open(archive.namelist()[0]) as handle:
            return pd.read_csv(handle, header=None, names=COLS)


def months(first, last):
    y, m = map(int, first.split("-"))
    while (y, m) <= (last.year, last.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def pull(symbol, interval, first_month):
    today = datetime.now(UTC).date()
    parts = []
    urls = []
    this_month = (today.year, today.month)
    for y, m in months(first_month, today):
        if (y, m) < this_month:
            urls.append(
                f"{BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{y}-{m:02d}.zip"
            )
    day = date(today.year, today.month, 1)
    while day < today:
        urls.append(
            f"{BASE}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{day.isoformat()}.zip"
        )
        day += timedelta(days=1)
    for url in urls:
        frame = fetch(url)
        if frame is not None and len(frame):
            parts.append(frame)
    frame = (
        pd.concat(parts, ignore_index=True)
        .drop_duplicates("open_time")
        .sort_values("open_time")
    )
    opened = frame["open_time"].astype("int64")
    opened = opened.where(
        opened < 10**14, opened // 1000
    )  # 2025+ archives use microseconds
    stamp = pd.to_datetime(opened, unit="ms", utc=True)
    out = pd.DataFrame(
        {
            "open": frame["open"],
            "high": frame["high"],
            "low": frame["low"],
            "close": frame["close"],
            "volume": frame["volume"],
        }
    )
    out["vwap"] = (
        frame["quote_volume"] / frame["volume"].where(frame["volume"] > 0)
    ).round(8)
    out["trades"] = frame["trades"]
    if interval == "1d":
        out.insert(0, "date", stamp.dt.strftime("%Y-%m-%d"))
    else:
        out.insert(0, "ts", stamp.dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return out


def job(args):
    symbol, interval, template, first_month = args
    out = pull(symbol, interval, first_month or SYMBOLS[symbol])
    path = ROOT / template.format(s=symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    key = out.columns[0]
    return f"{symbol}_{interval}", {
        "rows": len(out),
        "first": str(out[key].iloc[0]),
        "last": str(out[key].iloc[-1]),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main():
    jobs = [
        (s, interval, template, first)
        for interval, (template, symbols, first) in PLAN.items()
        for s in symbols
    ]
    manifest = {
        "pulled_at": datetime.now(UTC).isoformat(),
        "source": "data.binance.vision spot klines (USDT pairs)",
        "files": {},
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, info in pool.map(job, jobs):
            manifest["files"][key] = info
            print(key, info, flush=True)
    (ROOT / "reports/data/2026-10-14_binance_manifest.json").write_text(
        json.dumps(manifest, indent=2)
    )


if __name__ == "__main__":
    main()
