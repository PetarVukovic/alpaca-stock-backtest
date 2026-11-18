"""Build and verify the MASTER_20261014 teaching charts (read-only research; no orders, no ledger writes).

    .venv/bin/python -m lab.aichain.master_run            # build all 22 charts + captions + verification.json
    .venv/bin/python -m lab.aichain.master_run --verify   # verification only

Outputs: reports/research/MASTER_20261014/charts/ (c01..c22 PNG, captions.json, verification.json).
Every number drawn is read from the project files or recomputed from the daily CSVs; ``verify`` re-checks the
trade-level facts straight against ``data/ohlcv`` and the group facts against ``swing/summary.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import master_data as D
from lab.aichain import master_stat_charts as ST
from lab.aichain import master_trade_charts as TR
from lab.aichain.master_common import OUT, ROOT, load_json, read_daily, write_captions


def build_all() -> list[str]:
    files = [
        TR.c01_price_anatomy(),
        TR.c02_c13c_walkthrough(),
        TR.c03_c13c_failure(),
        TR.c04_breakout_retest(),
        TR.c05_breakout_failure(),
        TR.c06_momentum_rank(),
        TR.c07_ibs(),
        TR.c08_bounce_fail(),
        TR.c09_mm_example(),
        ST.c10_mm_reality(),
        ST.c11_placebo(),
        ST.c12_scoreboard(),
        ST.c13_equity_memory(),
        ST.c14_c13c_vs_new(),
        TR.c15_trade_distribution(),
        ST.c16_context_2021_2022(),
        *ST.c17_19_levels(),
        ST.c20_crypto_trend(),
        ST.c21_metals_eu(),
        TR.c22_position_size(),
    ]
    write_captions()
    return files


# ------------------------------------------------------------------------------------------ verification
def _row(check: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": check, "ok": bool(ok), "detail": detail}


def _trade_vs_csv(ticker: str, t: dict[str, Any]) -> tuple[bool, str]:
    raw = read_daily(ticker)
    e, x = raw.loc[pd.Timestamp(t["entry_date"])], raw.loc[pd.Timestamp(t["exit_date"])]
    entry_ok = abs(float(e["open"]) - t["raw_entry"]) < 1e-9
    xo = abs(float(x["open"]) - t["raw_exit"]) < 1e-9
    inside = float(x["low"]) - 1e-9 <= t["raw_exit"] <= float(x["high"]) + 1e-9
    close_exit = (
        abs(float(x["close"]) - t["raw_exit"]) < 1e-9
    )  # forced end-of-window exit
    ok = entry_ok and (xo or inside or close_exit)
    return (
        ok,
        f"{ticker} {t['entry_date']}: CSV open {float(e['open']):.2f} vs {t['raw_entry']:.2f}; exit {t['raw_exit']:.2f} (CSV O/L/H/C {float(x['open']):.2f}/{float(x['low']):.2f}/{float(x['high']):.2f}/{float(x['close']):.2f})",
    )


def verify() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rep = D.verify_against_summary()
    out.append(
        _row(
            "engine re-run equals summary.json (7 group/rule pairs: trades and total return)",
            all(v["ok"] for v in rep.values()),
            json.dumps({k: v["trades"] for k, v in rep.items()}),
        )
    )
    sm = D.summary()
    # c01 raw candle numbers
    mu = read_daily("MU")
    wk = mu.loc["2023-08-14":"2023-08-18"]
    out.append(
        _row(
            "c01 MU 14.8.2023. OHLC 64.37/68.48/64.20/68.28",
            [round(v, 2) for v in wk.iloc[0][["open", "high", "low", "close"]]]
            == [64.37, 68.48, 64.2, 68.28],
            str(wk.iloc[0][["open", "high", "low", "close"]].to_dict()),
        )
    )
    out.append(
        _row(
            "c01 week return = close Fri / open Mon - 1 = -1.2 %",
            abs((wk.close.iloc[-1] / wk.open.iloc[0] - 1) * 100 + 1.2) < 0.06,
            f"{(wk.close.iloc[-1] / wk.open.iloc[0] - 1) * 100:.3f} %",
        )
    )
    # c02 / c03 C13C trades against raw CSV
    t2, med, tr = TR._c13_pick()
    ok, d = _trade_vs_csv("MU", t2)
    out.append(_row("c02 C13C trade entry/exit prices exist in MU CSV", ok, d))
    close = mu["close"]
    sma = close.rolling(200).mean()
    sig = pd.Timestamp(t2["entry_date"])
    sig_i = mu.index.get_loc(sig) - 1
    drop = close.iloc[sig_i] / close.iloc[sig_i - 5] - 1
    out.append(
        _row(
            "c02 signal day: close > SMA200 and 5-day return <= -5 % (raw CSV)",
            bool(close.iloc[sig_i] > sma.iloc[sig_i] and drop <= -0.05),
            f"close {close.iloc[sig_i]:.2f}, SMA200 {sma.iloc[sig_i]:.2f}, 5d {drop * 100:.2f} %",
        )
    )
    seq = [t for t in tr if "2024-06-27" <= t["entry_date"] <= "2024-08-02"]
    oks = [_trade_vs_csv("MU", t) for t in seq]
    out.append(
        _row(
            "c03 four stop-outs: entry/exit prices exist in MU CSV",
            all(o for o, _ in oks),
            " | ".join(d for _, d in oks),
        )
    )
    val = 1000 * np.prod([1 + t["return"] for t in seq])
    out.append(
        _row(
            "c03 compounding 1.000 EUR through four trades",
            abs(val - 656) < 1,
            f"{val:.1f} EUR",
        )
    )
    # c04 / c05 W5 trades
    allw = TR._w5_pool()
    med_w = float(np.median([t["return"] for _, t in allw if t["return"] > 0]))
    pool = [(tk, t) for tk, t in allw if t["return"] > 0 and t["bars_held"] >= 5]
    tk, t4 = TR.nearest_to(pool, lambda x: x[1]["return"], med_w)
    ok, d = _trade_vs_csv(tk, t4)
    out.append(_row("c04 W5 trade prices exist in CSV", ok, d))
    loss = [(a, t) for a, t in allw if t["return"] <= 0 and t["reason"] == "stop"]
    medl = float(np.median([t["return"] for _, t in loss]))
    loss = [(a, t) for a, t in loss if t["bars_held"] >= 3]
    tk5, t5 = TR.nearest_to(loss, lambda x: x[1]["return"], medl)
    ok, d = _trade_vs_csv(tk5, t5)
    out.append(_row("c05 W5 trade prices exist in CSV", ok, d))
    # c06 rank vs rule arrays
    fr = [x for x in TR._w3_fridays("ai_chips_logic") if x["held"]]
    for x in fr:
        x["excess"] = float(
            np.mean([x["row"][t]["fwd"] for t in x["held"]])
            - np.mean([v["fwd"] for v in x["row"].values()])
        )
    pick = TR.nearest_to(
        fr, lambda x: x["excess"], float(np.median([x["excess"] for x in fr]))
    )
    name = pick["order"][0]
    rule = D.rule_for(name, "W3_MOM_RANK_WEEKLY")
    i = _idx(name, pick["date"])
    out.append(
        _row(
            "c06 rank of the top name on the picked Friday equals the engine rank (W3 rule arrays)",
            rule.rank_arr[i] == 1.0 and int(rule.count_arr[i]) == pick["m"],
            f"{name} {pick['date'].date()} rank {rule.rank_arr[i]}, count {rule.count_arr[i]} vs {pick['m']}",
        )
    )
    # c07 IBS
    t7 = TR.nearest_to(
        [
            t
            for t in D.sleeve("MU", "W8_IBS_REVERT").trades
            if t["return"] > 0 and 3 <= t["bars_held"] <= 5
        ],
        lambda x: x["return"],
        float(
            np.median(
                [
                    t["return"]
                    for t in D.sleeve("MU", "W8_IBS_REVERT").trades
                    if t["return"] > 0
                ]
            )
        ),
    )
    ok, d = _trade_vs_csv("MU", t7)
    si = mu.index.get_loc(pd.Timestamp(t7["entry_date"])) - 1
    r = mu.iloc[si]
    ibs = (r.close - r.low) / (r.high - r.low)
    out.append(
        _row(
            "c07 W8 trade exists in CSV and the signal day IBS < 0.2 and close > SMA200",
            ok and ibs < 0.2 and r.close > sma.iloc[si],
            f"{d}; IBS {ibs:.3f}",
        )
    )
    # summary-derived charts
    g = sm["groups"]["stocks_all"]["per_contender"]
    bh = sm["groups"]["stocks_all"]["buy_and_hold_reference"]["total_return"]
    out.append(
        _row(
            "c12 no rule reaches buy-and-hold total return (stocks_all)",
            all(g[c]["total_return"] < bh for c in g if c != "B0_BUYHOLD"),
            f"best rule {max(g[c]['total_return'] for c in g if c != 'B0_BUYHOLD'):.3f} vs B0 {bh:.3f}",
        )
    )
    c16 = load_json(
        ROOT / "reports/research/AICHAIN_20261014/swing/results/stocks_all.json"
    )["contenders"]
    neg = [
        c
        for c in c16
        if c != "B0_BUYHOLD" and c16[c]["contexts"]["y2021_2022"]["expectancy_eur"] <= 0
    ]
    out.append(
        _row(
            "c16 2021-2022 expectancy <= 0 for 6 of 8 rules (as in docs/research/AICHAIN_SWING_RESULT.md)",
            len(neg) == 6,
            ", ".join(c.split("_")[0] for c in neg),
        )
    )
    ref = sm["groups"]["memory"]["per_contender"]
    out.append(
        _row(
            "c13 memory AI-era drawdowns vs summary.json (B0 -47.7, W1 -34, W5 -22, W3 -28 %)",
            all(
                abs(ref[c]["max_drawdown"] - v) < 0.006
                for c, v in [
                    ("B0_BUYHOLD", -0.4775),
                    ("W1_C13C_ORIG", -0.34),
                    ("W5_SR_BREAKOUT_RETEST", -0.2235),
                    ("W3_MOM_RANK_WEEKLY", -0.28),
                ]
            ),
            str(
                {
                    c: round(ref[c]["max_drawdown"], 4)
                    for c in (
                        "B0_BUYHOLD",
                        "W1_C13C_ORIG",
                        "W5_SR_BREAKOUT_RETEST",
                        "W3_MOM_RANK_WEEKLY",
                    )
                }
            ),
        )
    )
    rot = pd.read_csv(
        ROOT
        / "reports/backtest/C36_METALS_ADV_20261013/IBKR/ROTATE_BASE_500_DIAGNOSTIC_trades.csv"
    )
    out.append(
        _row(
            "c21 ROTATE 500 EUR: final cash 559.42 (docs) = 500 + sum of net sells",
            abs(500 + rot["net_pnl_eur"].dropna().sum() - 559.42) < 0.1,
            f"{500 + rot['net_pnl_eur'].dropna().sum():.2f}",
        )
    )
    pb = load_json(ROOT / "reports/research/AICHAIN_20261014/swing/placebo.json")
    e4 = pb["mechanics_ai_era"]["events"]["E4_demand_zone_retest"]["by_h"]["10"]
    out.append(
        _row(
            "c10 E4 10-day excess +1.79 pp, CI lower 0.06 pp (placebo.json)",
            abs(e4["mean_excess_vs_ticker_avg"] * 100 - 1.79) < 0.01
            and abs(e4["excess_ci95"][0] * 100 - 0.06) < 0.01,
            f"{e4['mean_excess_vs_ticker_avg'] * 100:.3f} [{e4['excess_ci95'][0] * 100:.3f}]",
        )
    )
    return out


def _idx(ticker: str, date: pd.Timestamp) -> int:
    return int(D.runner().bars[ticker].dates.get_loc(date))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)
    if not args.verify:
        files = build_all()
        print(f"built {len(files)} charts into {OUT}")
    report = verify()
    (OUT / "verification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    bad = [r for r in report if not r["ok"]]
    for r in report:
        print(("OK   " if r["ok"] else "FAIL ") + r["check"])
    print(f"{len(report) - len(bad)}/{len(report)} checks ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
