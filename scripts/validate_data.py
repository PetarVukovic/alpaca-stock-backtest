#!/usr/bin/env python3
"""Data gate for Memory Lab. Exit code 1 means: NO backtest.

Checks daily (data/ohlcv/*_1d.csv) and hourly (data/hourly/*_1h_clean.csv) price files and writes
reports/data/DATA_CHECK.md. Read-only on data. Never places orders.

Run:  .venv/bin/python scripts/validate_data.py
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "data" / "ohlcv"
HOURLY_DIR = ROOT / "data" / "hourly"
REPORT = ROOT / "reports" / "data" / "DATA_CHECK.md"
KNOWN_REAL = DAILY_DIR / "known_real_moves.csv"

# Primary + context tickers must be clean. Side-check and watch tickers are thin or short: big moves only warn.
STRICT = ["MU", "WDC", "STX", "SMH", "AMAT", "LRCX", "KLAC", "SIMO", "RMBS"]
LENIENT = ["MRAM", "ACMR", "DRAM", "SKHY", "SNDK"]
BIG_MOVE = 0.25
WDC_SPINOFF_DATE = "2025-02-24"
WDC_SPINOFF_MAX_MOVE = 0.10
SESSIONS = {"regular", "open_mixed", "extended"}
DAILY_COLS = ["date", "open", "high", "low", "close", "volume"]
HOURLY_COLS = ["ts", "open", "high", "low", "close", "volume", "feed", "session", "volume_ok"]


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def load_known_real() -> set[tuple[str, str]]:
    if not KNOWN_REAL.exists():
        return set()
    k = pd.read_csv(KNOWN_REAL, dtype=str)
    return {(r.ticker, r.date) for r in k.itertuples()}


def daily_completion_issue(last_day: str, source_mtime: datetime, as_of: datetime) -> str | None:
    """Negative evidence only: a recent copy timestamp cannot certify finality.

    16:00 New York is conservative on early-close sessions. A future ingestion
    manifest should carry the actual exchange close and provider retrieval time.
    """
    if source_mtime.tzinfo is None or as_of.tzinfo is None:
        raise ValueError("Completion evidence timestamps must include a timezone")
    close = datetime.combine(date.fromisoformat(last_day), time(16), ZoneInfo("America/New_York"))
    if as_of < close:
        return f"session {last_day} has not reached conservative 16:00 New York close"
    if source_mtime < close:
        return f"source mtime predates {last_day} session close; latest bar may be incomplete"
    return None


def check_daily(ticker: str, f: Findings, known: set[tuple[str, str]], stats: list[dict],
                *, through: str | None = None, as_of: datetime | None = None) -> pd.DataFrame | None:
    path = DAILY_DIR / f"{ticker}_1d.csv"
    if not path.exists():
        f.error(f"{ticker} daily: file missing ({path.name})")
        return None
    d = pd.read_csv(path)
    missing = [c for c in DAILY_COLS if c not in d.columns]
    if missing:
        f.error(f"{ticker} daily: missing columns {missing}")
        return None
    d["date"] = d["date"].astype(str).str[:10]
    try:
        pd.to_datetime(d["date"], format="%Y-%m-%d", errors="raise")
    except (ValueError, TypeError):
        f.error(f"{ticker} daily: invalid dates")
        return None
    if through is not None:
        excluded = int((d["date"] > through).sum())
        d = d.loc[d["date"] <= through].copy()
        if excluded:
            f.info.append(f"{ticker} daily: excluded {excluded} rows after explicit cutoff {through}")
    if d.empty:
        f.error(f"{ticker} daily: no bars in requested sample")
        return None
    issue = daily_completion_issue(str(d["date"].iloc[-1]),
                                   datetime.fromtimestamp(path.stat().st_mtime, timezone.utc),
                                   as_of or datetime.now(timezone.utc))
    if issue:
        f.error(f"{ticker} daily: {issue}; refetch completed data or use an explicit earlier --through")
    if d["date"].duplicated().any():
        f.error(f"{ticker} daily: {int(d['date'].duplicated().sum())} duplicate dates")
    if not d["date"].is_monotonic_increasing:
        f.error(f"{ticker} daily: dates not sorted ascending")
    if d[DAILY_COLS[1:]].isna().any().any():
        f.error(f"{ticker} daily: NaN values in OHLCV")
    px = d[["open", "high", "low", "close"]]
    if (px <= 0).any().any():
        f.error(f"{ticker} daily: non-positive prices")
    bad = ((d["low"] > px[["open", "close"]].min(axis=1) + 1e-6) | (d["high"] < px[["open", "close"]].max(axis=1) - 1e-6)).sum()
    if bad:
        f.error(f"{ticker} daily: {int(bad)} bars where open/close lie outside the low-high range")
    if (d["volume"] < 0).any():
        f.error(f"{ticker} daily: negative volume")
    dt = pd.to_datetime(d["date"])
    gaps = dt.diff().dt.days
    long_gaps = d.loc[gaps > 5, "date"].tolist()
    if long_gaps:
        f.warn(f"{ticker} daily: gaps longer than 5 calendar days before {long_gaps[:5]}")
    r = d["close"].pct_change()
    for i in d.index[r.abs() > BIG_MOVE]:
        day, mv = d.at[i, "date"], r.at[i]
        if (ticker, day) in known:
            continue
        msg = f"{ticker} daily: {mv:+.1%} move on {day} not in known_real_moves.csv"
        (f.error if ticker in STRICT else f.warn)(msg)
    if ticker == "WDC":
        row = d[d["date"] == WDC_SPINOFF_DATE]
        if row.empty:
            f.error("WDC daily: spin-off date row missing")
        else:
            mv = r.at[row.index[0]]
            if abs(mv) > WDC_SPINOFF_MAX_MOVE:
                f.error(f"WDC daily: {mv:+.1%} on {WDC_SPINOFF_DATE}: spin-off adjustment missing or applied twice")
    stats.append({"ticker": ticker, "kind": "daily", "rows": len(d), "first": d["date"].iloc[0], "last": d["date"].iloc[-1]})
    return d


def check_hourly(ticker: str, f: Findings, daily: pd.DataFrame | None, stats: list[dict],
                 *, through: str | None = None) -> None:
    path = HOURLY_DIR / f"{ticker}_1h_clean.csv"
    if not path.exists():
        return
    h = pd.read_csv(path)
    missing = [c for c in HOURLY_COLS if c not in h.columns]
    if missing:
        f.error(f"{ticker} hourly: missing columns {missing}")
        return
    if through is not None:
        session_dates = pd.to_datetime(h["ts"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        h = h.loc[session_dates <= through].copy()
    if h.empty:
        f.warn(f"{ticker} hourly: no bars in requested sample")
        return
    if h["ts"].duplicated().any():
        f.error(f"{ticker} hourly: {int(h['ts'].duplicated().sum())} duplicate timestamps")
    if not h["ts"].is_monotonic_increasing:
        f.error(f"{ticker} hourly: timestamps not sorted")
    if h[["open", "high", "low", "close"]].isna().any().any():
        f.error(f"{ticker} hourly: NaN prices")
    if (h[["open", "high", "low", "close"]] <= 0).any().any():
        f.error(f"{ticker} hourly: non-positive prices")
    if (h["high"] < h["low"] - 1e-9).any():
        f.error(f"{ticker} hourly: high below low")
    badses = set(h["session"].unique()) - SESSIONS
    if badses:
        f.error(f"{ticker} hourly: unknown session values {sorted(badses)}")
    nonsip = int((h["feed"] != "sip").sum())
    if nonsip:
        f.warn(f"{ticker} hourly: {nonsip} rows not from SIP")
    vol_bad = int((~h["volume_ok"].astype(bool)).sum())
    if vol_bad:
        f.warn(f"{ticker} hourly: {vol_bad} rows with volume_ok=False (do not use their volume)")
    if daily is not None and "date_et" in h.columns:
        reg = h[h["session"] == "regular"]
        last = reg.groupby("date_et")["close"].last()
        dd = daily.assign(date=daily["date"].str[:10]).set_index("date")["close"]
        j = pd.concat([last, dd], axis=1, join="inner", keys=["h", "d"])
        if len(j):
            med = ((j["h"] / j["d"]) - 1).abs().median()
            if med > 0.01:
                f.warn(f"{ticker} hourly vs daily: median close difference {med:.2%}, check adjustment")
    stats.append({"ticker": ticker, "kind": "hourly", "rows": len(h), "first": str(h["ts"].iloc[0])[:10], "last": str(h["ts"].iloc[-1])[:10]})


def write_report(f: Findings, stats: list[dict], *, report: Path = REPORT) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    verdict = "FAIL (NO backtest)" if f.errors else "OK"
    lines = [
        "# DATA_CHECK",
        "",
        f"Generated {datetime.now().astimezone().isoformat(timespec='seconds')} by `scripts/validate_data.py`.",
        "",
        f"**Result: {verdict}** · errors {len(f.errors)} · warnings {len(f.warnings)}",
        "",
        "## Files checked",
        "",
        "| Ticker | Kind | Rows | First | Last |",
        "|--------|------|------|-------|------|",
    ]
    lines += [f"| {s['ticker']} | {s['kind']} | {s['rows']} | {s['first']} | {s['last']} |" for s in stats]
    lines += ["", "## Errors", ""] + ([f"- {e}" for e in f.errors] or ["none"])
    lines += ["", "## Warnings", ""] + ([f"- {w}" for w in f.warnings] or ["none"])
    lines += ["", "## Scope and completion evidence", ""] + [f"- {item}" for item in f.info]
    lines += ["", "Rules: `docs/architecture/data.md`. Big-move allowlist: `data/ohlcv/known_real_moves.csv`.", ""]
    report.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", type=date.fromisoformat, help="Validate only sessions through YYYY-MM-DD (inclusive); backtest must use the same cutoff")
    parser.add_argument("--report", type=Path, default=REPORT, help="Write validation report here")
    parser.add_argument("--daily-symbols", nargs="+", help="Validate only the listed daily files")
    args = parser.parse_args(argv)
    if args.daily_symbols and any(not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]*", symbol) for symbol in args.daily_symbols):
        parser.error("Invalid stock symbol")
    through = args.through.isoformat() if args.through else None
    f, stats, known = Findings(), [], load_known_real()
    f.info.append(f"Validated sample cutoff: {through or 'all available rows'}. Consumers must apply this same cutoff.")
    f.warn("Daily completion uses conservative 16:00 America/New_York (including early-close days). File mtime before close is negative evidence; mtime after close is NOT proof of provider finality, especially after copies or transformations. No immutable fetch provenance is available.")
    for t in args.daily_symbols or STRICT + LENIENT:
        daily = check_daily(t, f, known, stats, through=through)
        if not args.daily_symbols:
            check_hourly(t, f, daily, stats, through=through)
    write_report(f, stats, report=args.report)
    print(f"DATA CHECK: {'FAIL' if f.errors else 'OK'} | errors={len(f.errors)} warnings={len(f.warnings)} | {args.report}")
    for e in f.errors:
        print("ERROR:", e)
    return 1 if f.errors else 0


if __name__ == "__main__":
    sys.exit(main())
