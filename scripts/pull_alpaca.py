"""GET-only canonical SIP download; existing files are never overwritten."""

import argparse
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.data import WDC_FACTOR, validate_frame

EXPANSION = [
    "NVDA",
    "AMD",
    "AVGO",
    "TSM",
    "ASML",
    "INTC",
    "MRVL",
    "NTAP",
    "SMCI",
    "ONTO",
    "ENTG",
    "MKSI",
    "FORM",
    "SOXX",
    "SOXL",
    "QQQ",
    "SPY",
    "EWY",
]
INTRADAY = ["MU", "WDC", "STX", "SMH"]
RATE_LOCK = threading.Lock()
LAST_REQUEST = 0.0
DATA = "https://data.alpaca.markets"
PAPER = "https://paper-api.alpaca.markets"


def get_json(url, headers, params):
    if not (url.startswith(DATA + "/v2/stocks/") or url == PAPER + "/v2/calendar"):
        raise ValueError("Endpoint outside GET data allowlist")
    global LAST_REQUEST
    for attempt in range(8):
        with RATE_LOCK:
            delay = 0.36 - (time.monotonic() - LAST_REQUEST)
            if delay > 0:
                time.sleep(delay)
            LAST_REQUEST = time.monotonic()
        response = requests.get(url, headers=headers, params=params, timeout=45)
        if response.status_code == 200:
            return response.json()
        if response.status_code not in {429, 500, 502, 503, 504}:
            raise RuntimeError(f"GET failed HTTP {response.status_code}")
        time.sleep(min(30, max(2**attempt, 10 if response.status_code == 429 else 0)))
    raise RuntimeError("GET retry limit reached")


def fetch_bars(symbol, timeframe, start, end, headers, feed="sip"):
    if symbol == "DRAM":
        start = max(start, "2026-04-02")
    rows, token, seen = [], None, set()
    for page in range(10000):
        params = {
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "feed": feed,
            "adjustment": "split",
            "sort": "asc",
            "limit": 10000,
        }
        if token:
            params["page_token"] = token
        body = get_json(f"{DATA}/v2/stocks/{symbol}/bars", headers, params)
        rows.extend(body.get("bars") or [])
        token = body.get("next_page_token")
        if not token:
            return rows
        if token in seen:
            raise RuntimeError("Repeated pagination token")
        seen.add(token)
        if page % 25 == 24:
            print(f"{symbol} {timeframe}: {len(rows)} barova dohvaćeno", flush=True)
        time.sleep(0.05)
    raise RuntimeError("Pagination limit reached")


def clean(rows, symbol, timeframe, calendar):
    if not rows:
        raise ValueError("Empty SIP response")
    frame = pd.DataFrame(rows).rename(
        columns={
            "t": "ts",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "trades",
        }
    )
    stamps = pd.to_datetime(frame.ts, utc=True)
    local = stamps.dt.tz_convert("America/New_York")
    frame["date"] = local.dt.strftime("%Y-%m-%d")
    if symbol == "DRAM":
        frame = frame[frame.date >= "2026-04-02"].copy()
        stamps = pd.to_datetime(frame.ts, utc=True)
        local = stamps.dt.tz_convert("America/New_York")
    frame[["open", "high", "low", "close", "vwap"]] = frame[
        ["open", "high", "low", "close", "vwap"]
    ].astype(float)
    if symbol == "WDC":
        frame.loc[
            frame.date < "2025-02-24", ["open", "high", "low", "close", "vwap"]
        ] *= WDC_FACTOR
    frame.index = pd.DatetimeIndex(stamps)
    if timeframe != "1Day":
        minutes = pd.Series(
            (local.dt.hour * 60 + local.dt.minute).to_numpy(), index=frame.index
        )
        opens = frame.date.map(
            {
                d: int(v["open"].split(":")[0]) * 60 + int(v["open"].split(":")[1])
                for d, v in calendar.items()
            }
        )
        closes = frame.date.map(
            {
                d: int(v["close"].split(":")[0]) * 60 + int(v["close"].split(":")[1])
                for d, v in calendar.items()
            }
        )
        duration = 60 if timeframe == "1Hour" else 5
        frame["session"] = "extended"
        frame.loc[(minutes < opens) & (minutes + duration > opens), "session"] = (
            "open_mixed"
        )
        frame.loc[(minutes >= opens) & (minutes + duration <= closes), "session"] = (
            "regular"
        )
        frame["session_end"] = minutes + duration == closes
        frame["feed"], frame["volume_ok"] = "sip", True
        frame["date_et"] = frame.date
        frame["ts_zagreb"] = (
            stamps.dt.tz_convert("Europe/Zagreb")
            .dt.strftime("%Y-%m-%d %H:%M")
            .to_numpy()
        )
    validate_frame(frame)
    return frame.drop(columns=["ts"]) if timeframe == "1Day" else frame


def pull(symbol, timeframe, start, end, headers, calendar, root=ROOT, feed="sip"):
    folder, suffix = {
        "1Day": ("ohlcv", "1d"),
        "1Hour": ("hourly", "1h_clean"),
        "5Min": ("intraday", "5m_clean"),
    }[timeframe]
    path = Path(root) / f"data/{folder}/{symbol}_{suffix}.csv"
    if path.exists():
        print(f"{symbol} {timeframe}: postojeća datoteka ostaje netaknuta", flush=True)
        return "existing"
    rows = fetch_bars(symbol, timeframe, start, end, headers, feed=feed) if feed != "sip" else fetch_bars(symbol, timeframe, start, end, headers)

    def utc_stamp(value):
        stamp = pd.Timestamp(value)
        return (
            stamp.tz_localize("UTC")
            if stamp.tzinfo is None
            else stamp.tz_convert("UTC")
        )

    start_stamp, end_stamp = utc_stamp(start), utc_stamp(end)
    duration = pd.Timedelta({"1Day": "1d", "1Hour": "1h", "5Min": "5min"}[timeframe])
    # Daily midnight-ET bars are available only after the session close; omit current unfinished day.
    selected = []
    for row in rows:
        stamp = utc_stamp(row["t"])
        completion = stamp + duration
        if timeframe == "1Day":
            day = stamp.tz_convert("America/New_York").strftime("%Y-%m-%d")
            if day in calendar:
                completion = pd.Timestamp(
                    day + " " + calendar[day]["close"], tz="America/New_York"
                ).tz_convert("UTC")
        if start_stamp <= stamp and completion <= end_stamp:
            selected.append(row)
    frame = clean(selected, symbol, timeframe, calendar)
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL prevents overwriting even if another lane creates the file during GET.
    with path.open("x") as stream:
        frame.to_csv(stream, index=False)
    print(f"{symbol} {timeframe}: spremljeno {len(frame)} barova", flush=True)
    return len(frame)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--timeframes", nargs="+", choices=["1Day", "1Hour", "5Min"])
    parser.add_argument("--feed", choices=["iex", "sip"], default="sip")
    args = parser.parse_args()
    if args.symbols and any(not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]*", symbol) for symbol in args.symbols):
        parser.error("Invalid stock symbol")
    if args.feed == "iex" and args.timeframes != ["1Day"]:
        parser.error("IEX is supported for explicit daily downloads only")
    load_dotenv(ROOT / ".env", override=True)
    key = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        print("Nedostaju lokalni API ključevi; ništa nije poslano.")
        return 1
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    end = args.end or (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
    calendar = {
        x["date"]: x
        for x in get_json(
            PAPER + "/v2/calendar", headers, {"start": args.start[:10], "end": end[:10]}
        )
    }
    jobs = [
        (s, tf)
        for s in (args.symbols or EXPANSION)
        for tf in (args.timeframes or ["1Day", "1Hour"])
    ]
    if not args.symbols and not args.timeframes:
        jobs += [(s, "5Min") for s in INTRADAY]
    failed = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(pull, symbol, tf, args.start, end, headers, calendar): (
                symbol,
                tf,
            )
            for symbol, tf in jobs
        }
        for future in as_completed(futures):
            symbol, tf = futures[future]
            try:
                future.result()
            except (
                ValueError,
                RuntimeError,
                OSError,
                requests.RequestException,
            ) as error:
                print(f"{symbol} {tf}: neuspjeh ({type(error).__name__})", flush=True)
                failed.append((symbol, tf))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
