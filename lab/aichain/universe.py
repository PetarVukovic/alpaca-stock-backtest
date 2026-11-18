"""Build the AI-chain tournament universe: audit every daily file, write universe.json.

Read-only on raw data. Never modifies a CSV. Run:
    .venv/bin/python -m lab.aichain.universe
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lab.data import validate_frame

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "reports" / "research" / "AICHAIN_20261014"
AI_ERA_START = "2023-01-01"
MIN_BARS_PRE_2026 = 250
MIN_BARS_AI_ERA = 120
GAP_DAYS = 5
BIG_MOVE = 0.40

SEGMENTS: dict[str, dict[str, Any]] = {
    "memory": {"name": "Memorija", "tickers": ["MU", "SNDK", "WDC", "STX"]},
    "mem_interface_storage": {
        "name": "Sučelja memorije i pohrana",
        "tickers": ["RMBS", "SIMO", "MRAM", "NTAP", "PSTG"],
    },
    "equipment": {
        "name": "Oprema za proizvodnju čipova",
        "tickers": [
            "AMAT",
            "LRCX",
            "KLAC",
            "ASML",
            "ONTO",
            "MKSI",
            "ENTG",
            "ACMR",
            "FORM",
            "TER",
        ],
    },
    "ai_chips_logic": {
        "name": "AI čipovi i logika",
        "tickers": [
            "NVDA",
            "AMD",
            "AVGO",
            "MRVL",
            "TSM",
            "INTC",
            "ARM",
            "TXN",
            "MCHP",
            "ON",
            "QCOM",
        ],
    },
    "network_servers": {
        "name": "Mreže i serveri",
        "tickers": ["ANET", "CRDO", "ALAB", "COHR", "LITE", "SMCI", "DELL", "HPE"],
    },
    "cloud": {
        "name": "Oblak i podatkovni centri",
        "tickers": ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "CRWV", "NBIS", "VRT"],
    },
}
SIGNAL_ONLY = ["SMH", "SOXX", "XLK", "NDX", "VIX"]

# Public-record corporate actions (2016-2026): ticker -> (date, kind, ratio as price multiplier on the day).
# Ratio is the raw price factor (10:1 split = 0.1). Used only to test that the series has NO such jump.
KNOWN_ACTIONS: dict[str, list[tuple[str, str, float]]] = {
    "NVDA": [("2021-07-20", "split 4:1", 0.25), ("2024-06-10", "split 10:1", 0.1)],
    "AVGO": [("2024-07-15", "split 10:1", 0.1)],
    "SMCI": [("2024-10-01", "split 10:1", 0.1)],
    "AMZN": [("2022-06-06", "split 20:1", 0.05)],
    "GOOGL": [("2022-07-18", "split 20:1", 0.05)],
    "LRCX": [("2024-10-03", "split 10:1", 0.1)],
    "ANET": [("2021-11-18", "split 4:1", 0.25), ("2024-12-04", "split 4:1", 0.25)],
    "MCHP": [("2021-10-01", "split 2:1", 0.5)],
    "WDC": [("2025-02-24", "spin-off SanDisk (factor 0.68132)", 0.68132)],
    "SNDK": [("2025-02-24", "spin-off listing from WDC", 1.0)],
    "DELL": [("2021-11-01", "VMware spin-off", 1.0)],
    "SOXX": [("2024-03-01", "split 3:1 (approximate date, search window)", 1 / 3)],
    "ASML": [],
    "TSM": [],
    "ARM": [],
    "AMD": [],
    "MU": [],
    "STX": [],
}


def load_raw(ticker: str) -> pd.DataFrame | None:
    path = ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv"
    if not path.exists():
        return None
    d = pd.read_csv(path)
    d["date"] = d["date"].astype(str).str[:10]
    return d


def audit_ticker(ticker: str) -> dict[str, Any]:
    """Run every check for one ticker and return a flat record."""
    rec: dict[str, Any] = {"ticker": ticker, "issues": [], "notes": [], "usable": False}
    d = load_raw(ticker)
    if d is None:
        rec.update(first_date=None, last_date=None, bars=0, bars_ai_era=0)
        rec["issues"].append("datoteka ne postoji")
        return rec
    rec["bars"] = len(d)
    rec["first_date"] = d["date"].iloc[0] if len(d) else None
    rec["last_date"] = d["date"].iloc[-1] if len(d) else None
    # Halt / delisting stretches show up as runs of zero-volume flat bars: history is only trusted after the last run.
    eff = effective_start(d)
    rec["effective_start"] = eff
    rec["bars_ai_era_raw"] = int((d["date"] >= AI_ERA_START).sum())
    live = d[(d["date"] >= eff) & (d["volume"] > 0)]
    rec["bars_ai_era"] = int((live["date"] >= AI_ERA_START).sum())
    rec["bars_pre_2026"] = int((live["date"] < "2026-01-01").sum())
    if eff != rec["first_date"]:
        rec["issues"].append(
            f"serija prije {eff} je zaustavljena trgovina (nulti volumen, ravne cijene); koristi se samo od {eff}"
        )
    hard: list[str] = []
    if d["date"].duplicated().any():
        hard.append(f"{int(d['date'].duplicated().sum())} duplikata datuma")
    if not d["date"].is_monotonic_increasing:
        hard.append("datumi nisu sortirani")
    work = d.drop_duplicates("date").sort_values("date")
    frame = work.set_index(pd.to_datetime(work["date"], utc=True), drop=False)
    try:
        validate_frame(frame)
    except ValueError as exc:
        hard.append(f"validate_frame: {exc}")
    px = frame[["open", "high", "low", "close"]]
    if (px <= 0).any().any():
        hard.append("cijene <= 0")
    bad_ohlc = int(
        (
            (frame.low > px[["open", "close"]].min(axis=1) + 1e-6)
            | (frame.high < px[["open", "close"]].max(axis=1) - 1e-6)
        ).sum()
    )
    if bad_ohlc:
        hard.append(f"{bad_ohlc} redaka s OHLC izvan low-high")
    zero_vol = int((frame["volume"] == 0).sum())
    rec["zero_volume_days"] = zero_vol
    if zero_vol:
        rec["notes"].append(f"{zero_vol} dana s volumenom 0")
    dt = pd.to_datetime(frame["date"])
    gaps = dt.diff().dt.days
    # >5 trading days ~ >7 calendar days; also record the stricter >5 calendar-day list for transparency.
    long_gaps = frame.loc[(gaps > 7) & (frame["date"] >= eff), "date"].tolist()
    rec["gaps_gt_5_trading_days"] = long_gaps
    if long_gaps:
        rec["issues"].append(
            f"razmaci duži od 5 trgovačkih dana prije: {long_gaps[:6]}"
        )
    ret = frame["close"].pct_change()
    big = frame.loc[ret.abs() > BIG_MOVE, "date"]
    rec["big_moves"] = [
        {"date": x, "ret": round(float(ret.loc[i]), 4)} for i, x in zip(big.index, big)
    ]
    if rec["big_moves"]:
        rec["issues"].append(
            "dnevni pomak > 40%: "
            + ", ".join(f"{m['date']} {m['ret']:+.1%}" for m in rec["big_moves"])
        )
    rec["corporate_actions"] = check_actions(ticker, frame, ret)
    if ticker == "WDC":
        rec["corporate_actions"].append(check_wdc_ratio(frame))
    rec["hard_errors"] = hard
    rec["issues"] = hard + rec["issues"]
    return rec


def effective_start(d: pd.DataFrame, min_run: int = 5) -> str:
    """First date after the last run of >= min_run consecutive zero-volume bars (or the first date)."""
    zero = (d["volume"] == 0).to_numpy()
    dates = d["date"].tolist()
    start = dates[0]
    i = 0
    n = len(zero)
    while i < n:
        if zero[i]:
            j = i
            while j < n and zero[j]:
                j += 1
            if j - i >= min_run and j < n:
                start = dates[j]
            i = j
        else:
            i += 1
    return start


def check_actions(
    ticker: str, frame: pd.DataFrame, ret: pd.Series
) -> list[dict[str, Any]]:
    """For each known action: look +-3 sessions for a jump equal to the raw ratio (would mean unadjusted)."""
    out: list[dict[str, Any]] = []
    for date, kind, ratio in KNOWN_ACTIONS.get(ticker, []):
        if str(frame["date"].iloc[0]) > date:
            out.append(
                {
                    "date": date,
                    "kind": kind,
                    "result": "izvan povijesti datoteke (nema podataka prije akcije)",
                }
            )
            continue
        win = frame.loc[
            (frame["date"] >= _shift(date, -5)) & (frame["date"] <= _shift(date, 5))
        ]
        wr = ret.loc[win.index]
        worst = float(wr.abs().max()) if len(wr) else float("nan")
        jump = float(wr.loc[wr.abs().idxmax()]) if len(wr) else float("nan")
        target = ratio - 1.0
        unadjusted = ratio < 0.95 and abs(jump - target) < 0.08
        res = (
            "NEPRILAGOĐENO (skok jednak omjeru)"
            if unadjusted
            else "kontinuirano (nema skoka omjera)"
        )
        out.append(
            {
                "date": date,
                "kind": kind,
                "max_abs_move_window": round(worst, 4),
                "move_at_max": round(jump, 4),
                "result": res,
            }
        )
    # generic split-like detector over the whole series, any ticker
    for i in ret.index[ret.abs() > 0.25]:
        r = float(ret.loc[i])
        for k in (2, 3, 4, 5, 10, 20):
            if abs((1 + r) - 1 / k) < 0.04 or abs((1 + r) - k) < 0.04 * k:
                out.append(
                    {
                        "date": str(frame.loc[i, "date"]),
                        "kind": "generički detektor",
                        "result": f"pomak {r:+.1%} sliči omjeru {k}:1, provjeriti",
                    }
                )
    return out


def check_wdc_ratio(frame: pd.DataFrame) -> dict[str, Any]:
    raw = pd.read_csv(ROOT / "data" / "ohlcv" / "WDC_1d.raw_unadjusted_spinoff.csv")
    raw["date"] = raw["date"].astype(str).str[:10]
    pre = frame[frame["date"] < "2025-02-24"].set_index("date")["close"]
    shared = pre.index.intersection(raw.set_index("date").index)
    ratio = pre.loc[shared] / raw.set_index("date").loc[shared, "close"]
    ok = bool(np.allclose(ratio, 0.68132, rtol=1e-5))
    return {
        "date": "2025-02-24",
        "kind": "WDC provjera omjera prema raw datoteci",
        "result": ("omjer 0.68132 potvrđen na " if ok else "OMJER NE ODGOVARA na ")
        + f"{len(shared)} dana",
    }


def _shift(date: str, days: int) -> str:
    return (pd.Timestamp(date) + pd.Timedelta(days=days)).strftime("%Y-%m-%d")


def decide_usable(rec: dict[str, Any]) -> None:
    """Apply the lab rules: data errors exclude; short history is watch only."""
    reasons: list[str] = []
    if rec["bars"] == 0:
        rec["exclude_reason"] = "datoteka ne postoji ili je prazna"
        return
    if rec["hard_errors"]:
        reasons.append("neispravni podaci: " + "; ".join(rec["hard_errors"]))
    if rec["bars_pre_2026"] < MIN_BARS_PRE_2026 or rec["bars_ai_era"] < MIN_BARS_AI_ERA:
        reasons.append(
            f"prekratka povijest ({rec['bars_pre_2026']} barova prije 2026, {rec['bars_ai_era']} u AI eri)"
        )
    unadj = [
        a for a in rec["corporate_actions"] if "NEPRILAGOĐENO" in a.get("result", "")
    ]
    if unadj:
        reasons.append(
            "korporativna akcija nije prilagođena: "
            + ", ".join(a["date"] for a in unadj)
        )
    rec["usable"] = not reasons
    if reasons:
        rec["exclude_reason"] = " | ".join(reasons)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seg_out: dict[str, Any] = {}
    excluded: list[dict[str, str]] = []
    all_recs: dict[str, dict[str, Any]] = {}
    for key, seg in SEGMENTS.items():
        rows = []
        for t in seg["tickers"]:
            rec = audit_ticker(t)
            decide_usable(rec)
            all_recs[t] = rec
            rows.append(rec)
            if not rec["usable"]:
                excluded.append(
                    {"ticker": t, "reason": rec.get("exclude_reason", "nepoznato")}
                )
        seg_out[key] = {"name": seg["name"], "tickers": rows}
    signal_recs = []
    for t in SIGNAL_ONLY:
        rec = audit_ticker(t)
        decide_usable(rec)
        signal_recs.append(rec)
    med_last = pd.to_datetime(
        pd.Series([r["last_date"] for r in all_recs.values() if r["bars"]])
    ).median()
    for t, r in all_recs.items():
        if r["usable"] and pd.Timestamp(r["last_date"]) < med_last - pd.Timedelta(
            days=14
        ):
            r["usable"] = False
            r["exclude_reason"] = (
                f"zastarjeli podaci (zadnji datum {r['last_date']}, ostali oko {med_last.date()})"
            )
            r["issues"].append(r["exclude_reason"])
            excluded.append({"ticker": t, "reason": r["exclude_reason"]})
    for r in signal_recs:
        r["close_only"] = bool(r["hard_errors"]) and all(
            "OHLC" in e for e in r["hard_errors"]
        )
        if r["close_only"]:
            r["usable"] = True
            r["notes"].append("koristiti samo close (OHLC unutar dana nije dosljedan)")
    usable_last = [r["last_date"] for r in all_recs.values() if r["usable"]]
    common_end = min(usable_last)
    # keep a per-ticker view of how far each usable ticker is from the common end
    uni = {
        "common_end": common_end,
        "ai_era_start": AI_ERA_START,
        "segments": seg_out,
        "signal_only": signal_recs,
        "excluded": excluded,
    }
    (OUT_DIR / "universe.json").write_text(
        json.dumps(uni, indent=2, ensure_ascii=False, default=str)
    )
    lasts = pd.Series({t: r["last_date"] for t, r in all_recs.items() if r["usable"]})
    print("common_end", common_end)
    print(lasts.value_counts().sort_index().to_string())
    print("excluded", excluded)


if __name__ == "__main__":
    main()
