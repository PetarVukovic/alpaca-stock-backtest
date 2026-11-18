"""Shared loaders and helpers for the descriptive studies (read-only on data/)."""
from __future__ import annotations

from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "reports" / "research"

SPLITS = {"IS": ("2016-01-01", "2020-12-31"), "WF": ("2021-01-01", "2023-12-31"), "HO": ("2024-01-01", "2100-01-01")}
COST_BPS_RT = 5.0  # default MU round-trip cost from AGENTS.md


def split_of(d) -> str:
    d = pd.Timestamp(d)
    for k, (a, b) in SPLITS.items():
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return k
    return "NA"


@cache
def daily(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df


@cache
def hourly_regular(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / "hourly" / f"{ticker}_1h_clean.csv")
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["ts_et"] = df["ts"].dt.tz_convert("America/New_York")
    df["date_et"] = pd.to_datetime(df["date_et"])
    return df[df.session == "regular"].copy()


def close_panel(tickers) -> pd.DataFrame:
    return pd.concat({t: daily(t)["close"] for t in tickers}, axis=1).dropna()


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for idx, row in df.astype(object).iterrows():
        cells = [str(idx)]
        for v in row:
            if isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else floatfmt.format(v).replace(".", ","))
            elif isinstance(v, (int, np.integer)):
                cells.append(str(v))
            else:
                cells.append("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text, encoding="utf-8")
    print("wrote", OUT / name)


def pct(x: float, nd: int = 1) -> str:
    return f"{x:+.{nd}f} %".replace(".", ",")


def num(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", ",")
