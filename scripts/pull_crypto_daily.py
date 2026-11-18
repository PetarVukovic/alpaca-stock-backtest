"""Pull crypto bars (daily for all pairs; hourly for all; 5-minute for BTC/ETH) from Alpaca (read-only market data) into data/ohlcv/{SYMBOL}_1d.csv.

Usage: .venv/bin/python scripts/pull_crypto_daily.py [--start 2016-01-01]
Writes a manifest to reports/data/2026-10-14_crypto_manifest.json. Needs no API keys for crypto data,
but uses ALPACA_API_KEY / ALPACA_SECRET_KEY from the environment when present.
"""

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
    "SOL/USD": "SOLUSD",
    "XRP/USD": "XRPUSD",
    "LTC/USD": "LTCUSD",
    "LINK/USD": "LINKUSD",
    "DOGE/USD": "DOGEUSD",
    "AVAX/USD": "AVAXUSD",
}
INTRADAY_5M = {"BTCUSD", "ETHUSD", "SOLUSD"}
FRAMES = {
    "1d": (TimeFrame.Day, "data/ohlcv/{n}_1d.csv"),
    "1h": (TimeFrame.Hour, "data/hourly/{n}_1h_clean.csv"),
    "5m": (TimeFrame(5, TimeFrameUnit.Minute), "data/intraday/{n}_5m_clean.csv"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--intraday-start", default="2024-01-01")
    parser.add_argument("--frames", default="1d,1h,5m", help="comma list of 1d,1h,5m")
    args = parser.parse_args()
    client = CryptoHistoricalDataClient(
        os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    )
    manifest = {
        "pulled_at": datetime.now(UTC).isoformat(),
        "source": "alpaca crypto bars 1Day",
        "files": {},
    }

    def job(pair, name, label, frame_tf, template):
        start = datetime.fromisoformat(
            args.intraday_start if label == "5m" else args.start
        ).replace(tzinfo=UTC)
        request = CryptoBarsRequest(
            symbol_or_symbols=pair, timeframe=frame_tf, start=start
        )
        frame = client.get_crypto_bars(request).df.reset_index()
        stamp = pd.to_datetime(frame["timestamp"], utc=True)
        if label == "1d":
            frame.insert(0, "date", stamp.dt.strftime("%Y-%m-%d"))
            key = "date"
        else:
            frame.insert(0, "ts", stamp.dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
            key = "ts"
        frame = frame[
            [key, "open", "high", "low", "close", "volume", "vwap", "trade_count"]
        ]
        frame = (
            frame.rename(columns={"trade_count": "trades"})
            .drop_duplicates(key)
            .sort_values(key)
        )
        path = ROOT / template.format(n=name)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
        return f"{name}_{label}", {
            "rows": len(frame),
            "first": str(frame[key].iloc[0]),
            "last": str(frame[key].iloc[-1]),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    jobs = [
        (pair, name, label, tf, template)
        for pair, name in PAIRS.items()
        for label, (tf, template) in FRAMES.items()
        if label in args.frames.split(",") and (label != "5m" or name in INTRADAY_5M)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(job, *j): j for j in jobs}
        for future in as_completed(futures):
            key, info = future.result()
            manifest["files"][key] = info
            print(key, info, flush=True)
    out = ROOT / "reports/data/2026-10-14_crypto_manifest.json"
    out.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
