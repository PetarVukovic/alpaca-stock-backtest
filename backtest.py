"""Fetch daily stock bars and simulate a long-only moving-average strategy."""
import argparse
from collections import deque
from datetime import date, datetime, time, timedelta
import json
from math import isfinite
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL = "https://data.alpaca.markets/v2/stocks/bars"
MARKET_TZ = ZoneInfo("America/New_York")


def fetch_bars(symbol, start, end, feed, headers):
    query = {
        "symbols": symbol, "timeframe": "1Day", "adjustment": "split",
        "feed": feed, "limit": 10000,
        "start": datetime.combine(start, time.min, MARKET_TZ).isoformat(),
        "end": datetime.combine(end + timedelta(days=1), time.min, MARKET_TZ).isoformat(),
    }
    bars = []
    seen_tokens = set()
    while True:
        with urlopen(Request(URL + "?" + urlencode(query), headers=headers), timeout=30) as response:
            page = json.load(response)
        for bar in (page.get("bars") or {}).get(symbol, []):
            session = datetime.fromisoformat(bar["t"]).astimezone(MARKET_TZ).date()
            if start <= session <= end:
                bars.append((session, float(bar["o"]), float(bar["c"])))
        token = page.get("next_page_token")
        if not token:
            return validate_bars(bars)
        if token in seen_tokens:
            raise ValueError("Alpaca returned a repeated page token")
        seen_tokens.add(token)
        query["page_token"] = token


def validate_bars(bars):
    bars = sorted(bars)
    seen = set()
    for session, opening, closing in bars:
        if session in seen or not all(isfinite(p) and p > 0 for p in (opening, closing)):
            raise ValueError(f"Duplicate or invalid bar for {session}")
        seen.add(session)
    return bars


def simulate(bars, fast, slow, cost_bps):
    if len(bars) <= slow:
        raise ValueError(f"Need at least {slow + 1} daily bars, received {len(bars)}")
    cash = peak = 1.0
    shares = drawdown = 0.0
    target = False
    fills = 0
    cost = cost_bps / 10000
    closes = deque(maxlen=slow)
    for _, opening, closing in bars:
        if target and not shares:
            shares = cash / (opening * (1 + cost))
            cash = 0.0
            fills += 1
        elif not target and shares:
            cash = shares * opening * (1 - cost)
            shares = 0.0
            fills += 1
        equity = cash + shares * closing
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
        closes.append(closing)
        if len(closes) == slow:
            target = sum(list(closes)[-fast:]) / fast > sum(closes) / slow
    return {
        "bars": len(bars), "first_session": str(bars[0][0]),
        "last_session": str(bars[-1][0]), "fills": fills,
        "open_position": bool(shares), "return_pct": (equity - 1) * 100,
        "max_close_drawdown_pct": drawdown * 100,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="+", type=str.upper)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--feed", choices=("iex", "sip"), default="iex")
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=50)
    parser.add_argument("--cost-bps", type=float, default=5)
    args = parser.parse_args()
    if args.start > args.end or args.end >= datetime.now(MARKET_TZ).date():
        parser.error("Use an ordered date range ending before today's New York session.")
    if not 0 < args.fast < args.slow or not 0 <= args.cost_bps < 10000:
        parser.error("Require 0 < fast < slow and 0 <= cost-bps < 10000.")
    if any(not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]*", symbol) for symbol in args.symbols):
        parser.error("Provide one US equity ticker per argument.")
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        parser.error("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    results = {}
    for symbol in dict.fromkeys(args.symbols):
        try:
            bars = fetch_bars(symbol, args.start, args.end, args.feed, headers)
            results[symbol] = simulate(bars, args.fast, args.slow, args.cost_bps)
        except HTTPError as exc:
            parser.exit(1, f"{symbol}: Alpaca HTTP {exc.code}. Check credentials, feed and plan.\n")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.exit(1, f"{symbol}: {exc}\n")
    print(json.dumps({
        "feed": args.feed, "adjustment": "split", "fast": args.fast, "slow": args.slow,
        "cost_bps_per_side": args.cost_bps, "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
