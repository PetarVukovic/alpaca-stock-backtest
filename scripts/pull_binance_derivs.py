"""Pull Binance USD-M perp derivatives data (funding, open interest, long/short, taker ratio). GET only, no keys.

Why: the crypto day-trading research needs regime features (funding, OI, taker flow) over several years; the REST
/futures/data endpoints keep only ~30 days, so the 5-minute `metrics` come from the public archive instead.
Output: data/derivs/{SYM}_funding.csv, data/derivs/{SYM}_metrics_5m.csv and
reports/data/2026-10-14_binance_derivs_manifest.json. Timestamps are UTC, in the exchange's own clock (no shifting).
Research input only: no orders, no account endpoints.
"""

import hashlib
import io
import json
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = "https://data.binance.vision/data/futures/um/daily/metrics"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
SEARCH_START = date(2020, 9, 1)  # earliest BTC metrics file; ETH/SOL start later and are probed
METRICS_COLS = {
    "create_time": "ts",
    "sum_open_interest": "oi",
    "sum_open_interest_value": "oi_value",
    "count_toptrader_long_short_ratio": "top_ls_count",
    "sum_toptrader_long_short_ratio": "top_ls_sum",
    "count_long_short_ratio": "ls_count",
    "sum_taker_long_short_vol_ratio": "taker_ls_vol",
}


def fetch_day(symbol: str, day: date) -> pd.DataFrame | None:
    """Download one daily metrics zip; None when the archive has no file for that day (404)."""
    url = f"{ARCHIVE}/{symbol}/{symbol}-metrics-{day.isoformat()}.zip"
    for attempt in range(4):
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                with archive.open(archive.namelist()[0]) as handle:
                    return pd.read_csv(handle)
        except requests.RequestException:
            time.sleep(2**attempt)  # transient archive/network errors; the last attempt re-raises below
    raise RuntimeError(f"metrics download failed after retries: {url}")


def first_day(symbol: str, last: date) -> date:
    """Find the first day with a file by bisection (the archive is contiguous once a symbol starts)."""
    low, high = SEARCH_START, last
    while low < high:
        mid = low + (high - low) // 2
        if fetch_day(symbol, mid) is None:
            low = mid + timedelta(days=1)
        else:
            high = mid
    return low


def pull_metrics(symbol: str) -> pd.DataFrame:
    """Daily archive files concatenated into one 5-minute table; the current UTC day is excluded (incomplete)."""
    last = datetime.now(UTC).date() - timedelta(days=1)
    start = first_day(symbol, last)
    days = [start + timedelta(days=n) for n in range((last - start).days + 1)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        parts = [p for p in pool.map(lambda d: fetch_day(symbol, d), days) if p is not None]
    frame = pd.concat(parts, ignore_index=True).drop_duplicates("create_time")
    frame = frame.rename(columns=METRICS_COLS)[list(METRICS_COLS.values())]
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.sort_values("ts").reset_index(drop=True)


def pull_funding(symbol: str) -> pd.DataFrame:
    """Full funding history via REST pages of 1000 rows, walking forward from 2019-09."""
    cursor = int(datetime(2019, 9, 1, tzinfo=UTC).timestamp() * 1000)
    rows: list[dict] = []
    while True:
        response = requests.get(
            FUNDING_URL, params={"symbol": symbol, "startTime": cursor, "limit": 1000}, timeout=60
        )
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        rows.extend(page)
        cursor = page[-1]["fundingTime"] + 1
        if len(page) < 1000:
            break
        time.sleep(0.3)  # shared 500 requests / 5 min limit
    frame = pd.DataFrame(rows).drop_duplicates("fundingTime")
    out = pd.DataFrame(
        {
            "ts": pd.to_datetime(frame["fundingTime"], unit="ms", utc=True).dt.floor("s").dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "funding_rate": frame["fundingRate"].astype(float),
        }
    )
    return out.sort_values("ts").reset_index(drop=True)


def save(out: pd.DataFrame, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return {
        "rows": len(out),
        "first": str(out["ts"].iloc[0]),
        "last": str(out["ts"].iloc[-1]),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    manifest = {
        "pulled_at": datetime.now(UTC).isoformat(),
        "source": "data.binance.vision futures/um/daily/metrics + fapi/v1/fundingRate (public, read-only)",
        "files": {},
    }
    for symbol in SYMBOLS:
        for kind, builder, name in (
            ("funding", pull_funding, f"{symbol}_funding.csv"),
            ("metrics_5m", pull_metrics, f"{symbol}_metrics_5m.csv"),
        ):
            info = save(builder(symbol), ROOT / "data/derivs" / name)
            manifest["files"][f"{symbol}_{kind}"] = info
            print(symbol, kind, info, flush=True)
    path = ROOT / "reports/data/2026-10-14_binance_derivs_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
