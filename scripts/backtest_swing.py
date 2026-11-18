#!/usr/bin/env python3
"""Swing backtests for MU/WDC/STX memory chips lab.

Paper research only. Never places orders.
Writes reports/leaderboard.md (Croatian) with computed metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ohlcv"
REPORTS = ROOT / "reports"
SYMBOLS = ["MU", "WDC", "STX"]
NOTIONAL = 500.0


@dataclass
class Trade:
    symbol: str
    entry_i: int
    exit_i: int
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_px: float
    exit_px: float
    ret: float
    reason: str


def load_symbol(sym: str) -> pd.DataFrame:
    path = DATA / f"{sym}_1d.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    df["ret_1d"] = df["close"].pct_change()
    df["high_20"] = df["high"].rolling(20, min_periods=20).max()
    return df


def max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak == 0, np.nan, peak)
    return float(np.nanmin(dd)) if len(dd) else 0.0


def summarize(trades: list[Trade], label: str, symbol: str) -> dict:
    n = len(trades)
    if n == 0:
        return {
            "label": label,
            "symbol": symbol,
            "n": 0,
            "win_pct": 0.0,
            "mean_ret": 0.0,
            "median_ret": 0.0,
            "max_dd": 0.0,
            "sum_ret": 0.0,
            "avg_hold": 0.0,
        }
    rets = np.array([t.ret for t in trades], dtype=float)
    wins = (rets > 0).sum()
    # sequential equity on trade returns (compounded unit equity)
    eq = np.cumprod(1.0 + rets)
    holds = np.array([t.exit_i - t.entry_i for t in trades], dtype=float)
    return {
        "label": label,
        "symbol": symbol,
        "n": n,
        "win_pct": 100.0 * wins / n,
        "mean_ret": float(rets.mean()),
        "median_ret": float(np.median(rets)),
        "max_dd": max_drawdown(eq),
        "sum_ret": float(rets.sum()),
        "avg_hold": float(holds.mean()),
    }


def backtest_dip_hold(
    df: pd.DataFrame,
    symbol: str,
    threshold: float,
    hold: int,
) -> list[Trade]:
    """Enter next open after close-to-close return <= threshold; hold N trading days; max 1 pos."""
    trades: list[Trade] = []
    i = 1
    n = len(df)
    while i < n - 1:
        r = df.at[i, "ret_1d"]
        if pd.isna(r) or r > threshold:
            i += 1
            continue
        entry_i = i + 1  # next bar open
        if entry_i >= n:
            break
        exit_i = min(entry_i + hold, n - 1)
        entry_px = float(df.at[entry_i, "open"])
        exit_px = float(df.at[exit_i, "close"])
        if entry_px <= 0:
            i = entry_i + 1
            continue
        ret = exit_px / entry_px - 1.0
        trades.append(
            Trade(
                symbol=symbol,
                entry_i=entry_i,
                exit_i=exit_i,
                entry_date=df.at[entry_i, "timestamp"],
                exit_date=df.at[exit_i, "timestamp"],
                entry_px=entry_px,
                exit_px=exit_px,
                ret=ret,
                reason=f"dip<={threshold:.0%}_hold{hold}",
            )
        )
        # max 1 position: skip until after exit
        i = exit_i + 1
    return trades


def backtest_pullback_15(
    df: pd.DataFrame,
    symbol: str,
    pullback: float = -0.15,
    tp: float = 0.10,
    sl: float = -0.08,
    max_hold: int = 20,
) -> list[Trade]:
    """Enter when close is <= -15% from 20d high; exit +10% / -8% / 20d; max 1 pos."""
    trades: list[Trade] = []
    i = 20
    n = len(df)
    while i < n - 1:
        h20 = df.at[i, "high_20"]
        close = df.at[i, "close"]
        if pd.isna(h20) or h20 <= 0:
            i += 1
            continue
        dd = close / h20 - 1.0
        if dd > pullback:
            i += 1
            continue
        entry_i = i + 1
        if entry_i >= n:
            break
        entry_px = float(df.at[entry_i, "open"])
        if entry_px <= 0:
            i = entry_i + 1
            continue
        exit_i = entry_i
        reason = "time"
        exit_px = float(df.at[exit_i, "close"])
        for j in range(entry_i, min(entry_i + max_hold, n)):
            hi = float(df.at[j, "high"])
            lo = float(df.at[j, "low"])
            cl = float(df.at[j, "close"])
            # intraday stop/target check (conservative: stop before target if both)
            if lo <= entry_px * (1.0 + sl):
                exit_i, exit_px, reason = j, entry_px * (1.0 + sl), "sl"
                break
            if hi >= entry_px * (1.0 + tp):
                exit_i, exit_px, reason = j, entry_px * (1.0 + tp), "tp"
                break
            exit_i, exit_px = j, cl
            reason = "time"
        ret = exit_px / entry_px - 1.0
        trades.append(
            Trade(
                symbol=symbol,
                entry_i=entry_i,
                exit_i=exit_i,
                entry_date=df.at[entry_i, "timestamp"],
                exit_date=df.at[exit_i, "timestamp"],
                entry_px=entry_px,
                exit_px=exit_px,
                ret=ret,
                reason=f"pb15_{reason}",
            )
        )
        i = exit_i + 1
    return trades


def fmt_pct(x: float) -> str:
    return f"{100.0 * x:.2f}%"


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    all_trades_rows: list[dict] = []

    specs = [
        ("dip_-5pct_hold10", lambda df, s: backtest_dip_hold(df, s, -0.05, 10)),
        ("dip_-7pct_hold10", lambda df, s: backtest_dip_hold(df, s, -0.07, 10)),
        ("dip_-10pct_hold10", lambda df, s: backtest_dip_hold(df, s, -0.10, 10)),
        ("pullback_-15_from_20d_exit_+10_-8_20d", lambda df, s: backtest_pullback_15(df, s)),
    ]

    for sym in SYMBOLS:
        df = load_symbol(sym)
        print(f"=== {sym} bars={len(df)} {df.timestamp.min().date()} → {df.timestamp.max().date()} ===")
        for label, fn in specs:
            trades = fn(df, sym)
            summary = summarize(trades, label, sym)
            results.append(summary)
            print(
                f"  {label}: n={summary['n']} win%={summary['win_pct']:.1f} "
                f"mean={fmt_pct(summary['mean_ret'])} maxDD={fmt_pct(summary['max_dd'])}"
            )
            for t in trades:
                all_trades_rows.append(
                    {
                        "strategy": label,
                        "symbol": t.symbol,
                        "entry": t.entry_date.isoformat(),
                        "exit": t.exit_date.isoformat(),
                        "entry_px": t.entry_px,
                        "exit_px": t.exit_px,
                        "ret": t.ret,
                        "reason": t.reason,
                        "notional_cap_usd": NOTIONAL,
                    }
                )

    res_df = pd.DataFrame(results)
    res_df.to_csv(REPORTS / "leaderboard.csv", index=False)
    if all_trades_rows:
        pd.DataFrame(all_trades_rows).to_csv(REPORTS / "trades.csv", index=False)

    # Rank by mean return among strategies with n>=5 (honesty: still full-sample)
    ranked = res_df[res_df["n"] >= 5].sort_values("mean_ret", ascending=False)
    lines: list[str] = []
    lines.append("# Memory Chips — leaderboard (backtest)")
    lines.append("")
    lines.append("**Upozorenje:** ovo je **full-sample** istraživanje na povijesnim dnevnim barovima. "
                 "Nije out-of-sample jamstvo. **Backtest ≠ profit.** Paper only — bez ordera.")
    lines.append("")
    lines.append("## Gate / prior art (OBAVEZNO)")
    lines.append("")
    lines.append("- Pročitaj `PRIOR_ART.md` i `reports/gate/*_VERDICT.md` — sve postojeće strategije su **FAIL**.")
    lines.append("- `reports/gate/approved_list.json` je **prazan**. Ovaj leaderboard **nije** Critic PASS.")
    lines.append("- **Nikad** ne prezentiraj FAIL strategije kao pobjednike. Follow signal samo uz Critic PASS.")
    lines.append("- Ranking ispod = research screening (OOS-ish honesty: full-sample s ogradom), ne production lista.")
    lines.append("")
    lines.append("## Univerzum i podaci")
    lines.append("")
    lines.append("- Simboli: MU, WDC, STX")
    lines.append("- Izvor: `data/ohlcv/*_1d.csv` (Alpaca IEX + reuse SIP arhive gdje postoji)")
    lines.append("- Notional cap (informativno): ≤ 500 USD, max 1 pozicija")
    lines.append("")
    lines.append("## Metrike po strategiji i simbolu")
    lines.append("")
    lines.append("| Strategija | Simbol | n | Win% | Mean ret | Median | Max DD | Avg hold |")
    lines.append("|------------|--------|--:|-----:|---------:|-------:|-------:|---------:|")
    for _, r in res_df.sort_values(["label", "symbol"]).iterrows():
        lines.append(
            f"| {r['label']} | {r['symbol']} | {int(r['n'])} | {r['win_pct']:.1f}% | "
            f"{fmt_pct(r['mean_ret'])} | {fmt_pct(r['median_ret'])} | {fmt_pct(r['max_dd'])} | "
            f"{r['avg_hold']:.1f} |"
        )
    lines.append("")
    lines.append("## Top kandidati (po mean ret, n≥5, full-sample s ogradom)")
    lines.append("")
    if ranked.empty:
        lines.append("_Nema strategija s n≥5._")
    else:
        for i, (_, r) in enumerate(ranked.head(10).iterrows(), 1):
            lines.append(
                f"{i}. **{r['symbol']} / {r['label']}** — n={int(r['n'])}, "
                f"win%={r['win_pct']:.1f}, mean={fmt_pct(r['mean_ret'])}, maxDD={fmt_pct(r['max_dd'])}"
            )
    lines.append("")
    # Frozen hypothesis highlight
    frozen = res_df[(res_df["label"] == "dip_-5pct_hold10")]
    lines.append("## Frozen hipoteza (−5% / 10d)")
    lines.append("")
    for _, r in frozen.iterrows():
        lines.append(
            f"- **{r['symbol']}**: n={int(r['n'])}, win%={r['win_pct']:.1f}, "
            f"mean={fmt_pct(r['mean_ret'])}, maxDD={fmt_pct(r['max_dd'])}"
        )
    lines.append("")
    lines.append("## Napomene")
    lines.append("")
    lines.append("- Ulaz dip strategija: signal na close dana t, ulaz na **open** dana t+1; izlaz close nakon N trgovačkih dana.")
    lines.append("- Pullback: close ≤ −15% od 20d high → ulaz next open; izlaz TP +10%, SL −8%, ili max 20d.")
    lines.append("- Max DD je na nizu trade-returna (compounded), ne na mark-to-market equity krivulji unutar tradea.")
    lines.append("- STX serija može biti kraća (IEX-only) od MU/WDC.")
    lines.append("")
    lines.append(f"_Generirano skriptom `scripts/backtest_swing.py`. Notional informativno {NOTIONAL:.0f} USD._")
    text = "\n".join(lines) + "\n"
    (REPORTS / "leaderboard.md").write_text(text, encoding="utf-8")
    print("\nWrote", REPORTS / "leaderboard.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
