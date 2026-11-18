#!/usr/bin/env python3
"""Build the W5 vs C13C beginner page with a real-data quiz (self-contained HTML). Research only, no orders.

Every chart is drawn from ``data/ohlcv`` through the same simulator and rules as the lab; every number in the
questions is computed here. Output: reports/research/W5_QUIZ_20261014/w5_quiz.html (+ charts, cases.json).
Run: .venv/bin/python scripts/w5_quiz_build.py
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from master_assemble import CSS, JS, encode_chart  # noqa: E402

from lab.aichain import master_common as mc  # noqa: E402
from lab.aichain import w5_quiz_data as Q  # noqa: E402
from lab.aichain.master_common import canvas, finish, hr, paper, tip  # noqa: E402
from lab.aichain.swing_run import peer_groups  # noqa: E402
from lab.top10.charts import GREEN, INK, PENCIL, RED  # noqa: E402

OUT = ROOT / "reports" / "research" / "W5_QUIZ_20261014"
CH = OUT / "charts"
mc.OUT = CH
SUMM = json.loads((ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing" / "summary.json").read_text())
W5N, C13N = "W5_SR_BREAKOUT_RETEST", "W1_C13C_ORIG"
BLUE, ORANGE, WIN, LOSS = "#2f6fb3", "#d9822b", "#17803d", "#c2321f"
ERA = pd.Timestamp("2023-01-01")
STOCKS = [t for k in ("memory", "mem_interface_storage", "equipment", "ai_chips_logic", "network_servers", "cloud") for t in peer_groups()[k]]
BARS = {t: Q.load_bars(t) for t in STOCKS}


def pcts(x: float, nd: int = 1) -> str:
    return f"{'+' if x >= 0 else '-'}{hr(abs(x) * 100, nd)} %"


def dh(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


# ----------------------------------------------------------------------------------------------- data
EVENTS: dict[str, list[Q.Event]] = {}
W5T: dict[str, list[dict[str, Any]]] = {}
C13T: dict[str, list[dict[str, Any]]] = {}
for _t in STOCKS:
    EVENTS[_t], _ = Q.w5_events(BARS[_t])
    W5T[_t] = Q.sleeve_trades(BARS[_t], W5N)
    C13T[_t] = Q.sleeve_trades(BARS[_t], C13N)


def date_of(t: str, i: int) -> pd.Timestamp:
    return BARS[t].dates[i]


def idx_of(t: str, d: Any) -> int:
    return int(np.searchsorted(BARS[t].dates.values, np.datetime64(pd.Timestamp(d))))


def w5_trade_for_signal(t: str, sig_i: int) -> dict[str, Any] | None:
    if sig_i + 1 >= len(BARS[t]):
        return None
    fill = BARS[t].dates[sig_i + 1]
    return next((x for x in W5T[t] if pd.Timestamp(x["entry_date"]) == fill), None)


def pooled_stats() -> dict[str, Any]:
    ev = [(t, e) for t in STOCKS for e in EVENTS[t] if date_of(t, e.i) >= ERA]
    kinds = pd.Series([e.kind for _, e in ev]).value_counts().to_dict()
    tr = [x for t in STOCKS for x in W5T[t]]
    df = pd.DataFrame(tr)
    df["why"] = np.where(df["detail"] == "gap_stop", "gap", df["reason"])
    by = df.groupby("why")["return"].agg(["count", "mean"]).to_dict("index")
    pnl = df["return"] * 1000
    top10 = float(pnl.nlargest(10).sum() / pnl.sum())
    pos = float(pnl.nlargest(10).sum() / pnl[pnl > 0].sum())
    c = pd.DataFrame([x for t in STOCKS for x in C13T[t]])
    return {"kinds": kinds, "by": by, "top10_net": top10, "top10_gross": pos, "n_w5": len(df), "hit_w5": float((df["return"] > 0).mean()),
            "med_w5": float(df["return"].median()), "n_c": len(c), "hit_c": float((c["return"] > 0).mean()), "med_c": float(c["return"].median())}


ST = pooled_stats()
SW5, SC = SUMM["groups"]["stocks_all"]["per_contender"][W5N], SUMM["groups"]["stocks_all"]["per_contender"][C13N]
MW5, MC = SUMM["groups"]["memory"]["per_contender"][W5N], SUMM["groups"]["memory"]["per_contender"][C13N]


# ----------------------------------------------------------------------------------------------- case selection
def pick_cases() -> dict[str, Any]:
    cases: dict[str, Any] = {}
    # W5 big winner after a retest (memory first)
    ent = []
    for t in STOCKS:
        for e in EVENTS[t]:
            if e.kind == "entry" and date_of(t, e.i) >= ERA:
                tr = w5_trade_for_signal(t, e.i)
                ent.append((t, e, tr))
    win = max((x for x in ent if x[2] and x[0] in ("MU", "WDC", "STX")), key=lambda x: x[2]["return"])
    cases["w5_buy"] = win
    stop_loss = [x for x in ent if x[2] and x[0] == "MU" and x[2]["reason"] == "stop" and x[2]["detail"] == "stop"]
    cases["w5_stop"] = max(stop_loss, key=lambda x: x[1].i)
    sma_exit = [x for x in ent if x[2] and x[0] == "MU" and x[2]["reason"] == "signal" and 0.2 < x[2]["return"] < 0.6]
    cases["w5_sma"] = sma_exit[0]
    # armed-day case: the arm that led to a big winner on MU
    mu_big = max((x for x in ent if x[2] and x[0] == "MU"), key=lambda x: x[2]["return"])
    arm_i = mu_big[1].armed_i
    cases["w5_arm"] = ("MU", mu_big[1], mu_big[2], arm_i)
    # cancel: memory-chain name, cancelled within 10 days of arm, level well above close at cancel
    cancels = [(t, e) for t in ("MU", "WDC", "STX", "AMAT", "LRCX", "TER", "AMD", "NVDA") for e in EVENTS[t] if e.kind == "cancel" and date_of(t, e.i) >= pd.Timestamp("2024-01-01") and 2 <= e.i - e.armed_i <= 12]
    cases["w5_cancel"] = cancels[len(cancels) // 3]
    expires = [(t, e) for t in STOCKS for e in EVENTS[t] if e.kind == "expire" and date_of(t, e.i) >= ERA and t in ("MU", "WDC", "STX", "AMAT", "LRCX", "NVDA", "AMD", "TSM")]
    cases["w5_expire"] = expires[0]
    # signal ignored because a position is already open
    ign = []
    for t in ("MU", "WDC", "STX"):
        for e in EVENTS[t]:
            if e.kind == "entry" and date_of(t, e.i) >= ERA and w5_trade_for_signal(t, e.i) is None:
                ign.append((t, e))
    cases["w5_ignored"] = ign[3] if len(ign) > 3 else ign[0]
    # C13C
    sig = []
    for t in ("MU", "WDC", "STX"):
        for x in C13T[t]:
            sig.append((t, x))
    cases["c_win"] = max(sig, key=lambda x: x[1]["return"])
    cases["c_loss"] = min(((t, x) for t, x in sig if x["reason"] == "stop"), key=lambda x: x[1]["return"])
    # C13C near-miss: above SMA200 but drop between -4.5 and -3.5 percent; and below SMA200 with a deep drop
    d = Q.c13c_signal_days(BARS["MU"])
    d = d[d.index >= pd.Timestamp("2024-01-01")]
    near = d[(d.close > d.sma200) & (d.chg5 <= -0.035) & (d.chg5 > -0.048)]
    cases["c_near"] = ("MU", near.index[len(near) // 2])
    below = d[(d.close < d.sma200) & (d.chg5 <= -0.08)]
    cases["c_below"] = ("MU", below.index[0])
    return cases


CASES = pick_cases()


# ----------------------------------------------------------------------------------------------- charts
def draw_window(ax: Any, t: str, lo: int, hi: int, sma: int, level: float | None = None, now_i: int | None = None) -> pd.Series:
    b = BARS[t]
    df = pd.DataFrame({"open": b.open, "high": b.high, "low": b.low, "close": b.close}, index=b.dates)
    ma = df["close"].rolling(sma).mean()
    lo = max(lo, 0)
    hi = min(hi, len(df) - 1)
    sub = df.iloc[lo : hi + 1]
    xs = mc.candles(ax, sub)
    ax.plot(xs, ma.iloc[lo : hi + 1].to_numpy(), color=BLUE, lw=2, ls="--", label=f"prosjek {sma} dana")
    paper(ax)
    pos = np.linspace(0, len(sub) - 1, 7).round().astype(int)
    ax.set_xticks(pos)
    ax.set_xticklabels([f"{sub.index[p].day}.{sub.index[p].month}.{str(sub.index[p].year)[2:]}" for p in pos], fontsize=10.5)
    if level is not None:
        ax.axhline(level, color=ORANGE, lw=2.4)
        ax.text(0.005, level, " otpor (razina)", transform=ax.get_yaxis_transform(), va="bottom", fontsize=12, color=ORANGE)
    ax.set_xlim(-1, len(sub) + 2)
    lo_p, hi_p = float(sub["low"].min()), float(sub["high"].max())
    if sma == 200:  # the 200-day average must stay visible, the question quotes its value
        lo_p = min(lo_p, float(ma.iloc[lo : hi + 1].min()))
    pad = (hi_p - lo_p) * 0.08
    ax.set_ylim(lo_p - pad, hi_p + pad)
    ax.legend(loc="upper left", fontsize=10.5, frameon=False)
    ax.set_title(f"{t}, dnevne svijeće", loc="left", fontsize=13, color=INK)
    ax._sub_index = sub.index  # type: ignore[attr-defined]
    return sub["close"]


def x_of(ax: Any, d: Any) -> int:
    return int(ax._sub_index.get_indexer([pd.Timestamp(d)], method="nearest")[0])  # type: ignore[attr-defined]


def chart_before(name: str, t: str, now_i: int, sma: int, level: float | None, note: str, n_back: int = 70) -> str:
    fig = canvas(5.6, f"{t}: danas je {dh(date_of(t, now_i))}", note)
    ax = fig.add_axes([0.05, 0.1, 0.92, 0.7])
    draw_window(ax, t, now_i - n_back, now_i, sma, level)  # nothing after "today" is drawn: no future leak
    xs = ax._sub_index  # type: ignore[attr-defined]
    k = x_of(ax, date_of(t, now_i))
    ax.set_xlim(-1, len(xs) + 16)
    ax.axvline(k + 0.5, color=RED, lw=2, ls=":")
    ax.axvspan(k + 0.5, len(xs) + 16, color="#e8e4d4", alpha=1.0, zorder=0)
    ax.text(k + 0.9, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.5, "budućnost:\nne znaš\nšto slijedi", fontsize=14, color=RED, zorder=7)
    return finish(fig, name, {"title": name, "what_to_see": note, "numbers_used": [t, str(now_i)]})


def chart_after_w5(name: str, t: str, sig_i: int, trade: dict[str, Any] | None, level: float, sma: int, note: str, end_pad: int = 12, n_back: int = 55) -> str:
    b = BARS[t]
    exit_i = idx_of(t, trade["exit_date"]) if trade else sig_i + 10
    fig = canvas(5.8, f"{t}: što se stvarno dogodilo", note)
    ax = fig.add_axes([0.05, 0.1, 0.92, 0.7])
    draw_window(ax, t, sig_i - n_back, exit_i + end_pad, sma, level)
    if trade:
        k_in, k_out = x_of(ax, trade["entry_date"]), x_of(ax, trade["exit_date"])
        ax.scatter([k_in], [trade["raw_entry"]], marker="^", s=190, color=WIN, zorder=8)
        ax.scatter([k_out], [trade["raw_exit"]], marker="v", s=190, color=LOSS if trade["return"] < 0 else ORANGE, zorder=8)
        ax.hlines(level * 0.97, k_in, k_out, color=RED, lw=2, ls="-", zorder=5)
        ax.text(k_in, level * 0.97, " stop 3 % ispod razine", color=RED, va="top", fontsize=11.5)
        ax.axvspan(k_in, k_out, color="#bfe6c9", alpha=0.35, zorder=0)
        tip(ax, f"kupnja {dh(trade['entry_date'])}\n{hr(trade['raw_entry'], 2)} $", (k_in, trade["raw_entry"]), (k_in - 6, trade["raw_entry"] * 0.9), color=WIN, size=11.5, ha="right")
        tip(ax, f"izlaz {dh(trade['exit_date'])}\n{hr(trade['raw_exit'], 2)} $ ({pcts(trade['return'])})", (k_out, trade["raw_exit"]), (max(k_out - 18, 2), trade["raw_exit"] * 1.12), color=RED, size=11.5)
    return finish(fig, name, {"title": name, "what_to_see": note, "numbers_used": [t, str(sig_i)]})


def chart_after_c13c(name: str, t: str, trade: dict[str, Any], note: str, n_back: int = 45) -> str:
    b = BARS[t]
    sig_i = idx_of(t, trade["entry_date"]) - 1
    exit_i = idx_of(t, trade["exit_date"])
    fig = canvas(5.8, f"{t}: što se stvarno dogodilo", note)
    ax = fig.add_axes([0.05, 0.1, 0.92, 0.7])
    draw_window(ax, t, sig_i - n_back, exit_i + 14, 200, None)
    k_in, k_out = x_of(ax, trade["entry_date"]), x_of(ax, trade["exit_date"])
    ax.scatter([k_in], [trade["raw_entry"]], marker="^", s=190, color=WIN, zorder=8)
    ax.scatter([k_out], [trade["raw_exit"]], marker="v", s=190, color=LOSS if trade["return"] < 0 else ORANGE, zorder=8)
    m = (b.dates >= pd.Timestamp(trade["entry_date"])) & (b.dates <= pd.Timestamp(trade["exit_date"]))
    ids = np.nonzero(m)[0]
    peak = np.maximum.accumulate(np.maximum(b.high[ids], trade["raw_entry"]))
    stop = np.maximum.accumulate(peak * 0.9)
    ax.step(np.arange(k_in, k_in + len(ids)), stop, where="post", color=RED, lw=2.2)
    ax.axvspan(k_in, k_out, color="#bfe6c9", alpha=0.35, zorder=0)
    tip(ax, f"kupnja {dh(trade['entry_date'])}\n{hr(trade['raw_entry'], 2)} $", (k_in, trade["raw_entry"]), (k_in - 8, trade["raw_entry"] * 0.88), color=WIN, size=11.5, ha="right")
    tip(ax, f"izlaz {dh(trade['exit_date'])}\n{hr(trade['raw_exit'], 2)} $ ({pcts(trade['return'])})", (k_out, trade["raw_exit"]), (max(k_out - 14, 2), trade["raw_exit"] * 1.12), color=RED, size=11.5)
    return finish(fig, name, {"title": name, "what_to_see": note, "numbers_used": [t, str(sig_i)]})


def chart_c13c_before(name: str, t: str, now_i: int, note: str) -> str:
    fig = canvas(5.6, f"{t}: danas je {dh(date_of(t, now_i))}", note)
    ax = fig.add_axes([0.05, 0.1, 0.92, 0.7])
    draw_window(ax, t, now_i - 45, now_i, 200, None)
    xs = ax._sub_index  # type: ignore[attr-defined]
    k = x_of(ax, date_of(t, now_i))
    ax.set_xlim(-1, len(xs) + 14)
    b = BARS[t]
    ax.axvspan(k - 5, k, color="#ffe9a8", alpha=0.7, zorder=1)
    ax.text(k - 5, ax.get_ylim()[1], " zadnjih 5 dana", fontsize=11.5, color=ORANGE, va="top")
    ax.axvline(k + 0.5, color=RED, lw=2, ls=":")
    ax.axvspan(k + 0.5, len(xs) + 14, color="#e8e4d4", alpha=1.0, zorder=0)
    ax.text(k + 0.9, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.5, "budućnost:\nne znaš", fontsize=14, color=RED, zorder=7)
    return finish(fig, name, {"title": name, "what_to_see": note, "numbers_used": [t, str(now_i)]})


def chart_compare(name: str, t: str, lo: int, hi: int) -> tuple[str, dict[str, Any]]:
    d0, d1 = date_of(t, lo), date_of(t, hi)
    w5 = [x for x in W5T[t] if d0 <= pd.Timestamp(x["entry_date"]) and pd.Timestamp(x["exit_date"]) <= d1]
    c = [x for x in C13T[t] if d0 <= pd.Timestamp(x["entry_date"]) and pd.Timestamp(x["exit_date"]) <= d1]
    fig = canvas(7.2, f"{t}: obje strategije na istom grafu", f"{dh(d0)} do {dh(d1)}. Zeleno: W5 trgovine. Narančasto: C13C trgovine.")
    ax = fig.add_axes([0.05, 0.1, 0.92, 0.72])
    draw_window(ax, t, lo, hi, 50, None)
    for x, col, yoff in [(x, WIN, 0.0) for x in w5] + [(x, ORANGE, -0.0) for x in c]:
        k_in, k_out = x_of(ax, x["entry_date"]), x_of(ax, x["exit_date"])
        top = ax.get_ylim()[1] if col == WIN else ax.get_ylim()[0]
        yy = top * (0.985 if col == WIN else 1.015)
        ax.hlines(yy, k_in, k_out, color=col, lw=6)
        ax.plot([k_in, k_out], [yy, yy], ls='none', marker='|', ms=16, mew=2.5, color='#fffdf6')
    return finish(fig, name, {"title": name, "what_to_see": "obje strategije", "numbers_used": [t]}), {"w5": w5, "c": c, "d0": dh(d0), "d1": dh(d1), "t": t}


# ----------------------------------------------------------------------------------------------- questions
def money(frac: float) -> str:
    return f"{hr(1000 * (1 + frac), 0)} €"


def build_questions() -> list[dict[str, Any]]:
    qs: list[dict[str, Any]] = []
    k = ST["kinds"]
    by = ST["by"]
    qs += [
        {
            "part": "1. Osnove (pojmovi)", "q": "Što je za W5 <b>otpor</b>?",
            "opts": ["Bilo koja crta koju nacrtam na grafu", "Zadnji potvrđeni vrh: dan čija je najviša cijena veća od 5 dana prije i 5 dana poslije (potvrda stiže tek 5 dana kasnije)", "Prosjek zadnjih 50 dana", "Najviša cijena ikad"],
            "ok": 1, "why": "Otpor je \"strop\" do kojeg je cijena već dolazila pa se vratila. W5 ga računa strogo po pravilu (swing vrh s 5 dana na svakoj strani), a vrh se smije koristiti tek kad je potvrđen, da pravilo ne vidi budućnost.",
        },
        {
            "part": "1. Osnove (pojmovi)", "q": "Cijena je prvi put zatvorila iznad otpora. Što radi W5?",
            "opts": ["Kupuje sutra po otvaranju", "Ništa ne kupuje, samo \"naoruža\" razinu i čeka povratak", "Prodaje", "Kupuje dvostruko više"],
            "ok": 1,
            "why": f"Proboj sam nije signal. Od {hr(k.get('arm', 0))} probojeva u AI eri (43 dionice) samo {hr(k.get('entry', 0))} je dobilo retest signal, {hr(k.get('cancel', 0))} se vratilo ispod razine (poništeno), a {hr(k.get('expire', 0))} je isteklo bez povratka u 40 dana. Čekanje filtrira lažne probojeve.",
        },
        {
            "part": "1. Osnove (pojmovi)", "q": "Što je <b>retest</b> koji W5 traži?",
            "opts": ["Cijena padne duboko ispod razine", "Najniža cijena dana spusti se na razinu ili najviše 1,5 % iznad nje, a dan se zatvori IZNAD razine", "Cijena zatvori na novom vrhu", "Cijena se ne pomakne 40 dana"],
            "ok": 1, "why": "Retest je provjera: bivši strop mora postati pod. Dodir razine bez probijanja (zatvaranje iznad nje) znači da su kupci tu preuzeli kontrolu.",
        },
        {
            "part": "1. Osnove (pojmovi)", "q": "Gdje W5 stavlja zaštitni stop?",
            "opts": ["10 % ispod vrha cijene (kao C13C)", "3 % ispod RAZINE (probijenog otpora), fiksno od kupnje", "3 % ispod ulazne cijene", "Nema stopa"],
            "ok": 1,
            "why": f"Stop je vezan uz razinu, ne uz ulaz, i ne pomiče se. Kad cijena u stopu padne, prosječan stvarni gubitak je {pcts(by['stop']['mean'])} (po otvaranju s prazninom, gap, {pcts(by['gap']['mean'])}), jer se kupuje malo iznad razine.",
        },
        {
            "part": "1. Osnove (pojmovi)", "q": "Što je glavni način na koji W5 <b>zarađuje</b> (izlaz s dobiti)?",
            "opts": ["Fiksna meta od +10 %", "Izlaz kad cijena zatvori ispod prosjeka 50 dana (SMA50)", "Izlaz nakon točno 5 dana", "Izlaz kad se cijena vrati na razinu"],
            "ok": 1,
            "why": f"U AI eri su izlazi na SMA50 ({by['signal']['count']} trgovina) imali prosječno {pcts(by['signal']['mean'])}, a izlazi na stopu ({by['stop']['count']} trgovina) {pcts(by['stop']['mean'])}. Dobit nosi trend koji dopustiš da traje, gubitke reže stop.",
        },
        {
            "part": "1. Osnove (pojmovi)", "q": "W5 ima signal za kupnju, a već držiš otvorenu W5 poziciju u istoj dionici. Što radi pravilo?",
            "opts": ["Kupuje još jednu", "Preskače signal: jedna pozicija po dionici", "Prodaje staru i kupuje novu", "Povećava stop"],
            "ok": 1, "why": f"Pravilo drži najviše jednu poziciju po dionici. Zato je od {hr(k.get('entry', 0))} signala u AI eri odigrano {ST['n_w5']} trgovina (ostali signali su pali dok je pozicija bila otvorena).",
        },
    ]
    return qs


def build_chart_questions() -> list[dict[str, Any]]:
    qs: list[dict[str, Any]] = []
    # 1 armed day
    t, e, tr, arm_i = CASES["w5_arm"]
    lvl = e.level
    b = chart_before("q_arm_before.png", t, arm_i, 50, lvl, "Žuta/narančasta crta je otpor. Danas je cijena zatvorila iznad nje prvi put.")
    a = chart_after_w5("q_arm_after.png", t, e.i, tr, lvl, 50, f"W5 je kupila tek nakon povratka na razinu ({dh(date_of(t, e.i))}).")
    qs.append({"part": "2. W5 na stvarnim grafovima", "img": b, "after": a, "q": f"{t}, {dh(date_of(t, arm_i))}. Cijena je prvi put zatvorila iznad otpora ({hr(lvl, 2)} $). Što radi W5 sutra?",
               "opts": ["Kupuje po otvaranju", "Čeka (razina je naoružana), ne kupuje", "Prodaje"], "ok": 1,
               "why": f"Ovo je tek proboj. W5 je pričekala {(date_of(t, e.i) - date_of(t, arm_i)).days} dana na retest ({dh(date_of(t, e.i))}), kupila idući dan po otvaranju i izašla na SMA50 s {pcts(tr['return'])} u {tr['bars_held']} trgovinskih dana (1.000 € postaje {money(tr['return'])})."})
    # 2 retest buy
    t, e, tr = CASES["w5_buy"]
    lvl = e.level
    b = chart_before("q_buy_before.png", t, e.i, 50, lvl, "Narančasta crta je otpor iz proboja. Danas je cijena dotaknula razinu i zatvorila iznad nje.")
    a = chart_after_w5("q_buy_after.png", t, e.i, tr, lvl, 50, "Zelena strelica je kupnja idući dan, crvena crta stop.", end_pad=15)
    qs.append({"part": "2. W5 na stvarnim grafovima", "img": b, "after": a, "q": f"{t}, {dh(date_of(t, e.i))}. Najniža cijena dana dotakla je razinu {hr(lvl, 2)} $, a dan je zatvoren iznad nje. Što radi W5 sutra?",
               "opts": ["Ne radi ništa", "Kupuje po otvaranju", "Čeka još tjedan"], "ok": 1,
               "why": f"To je točno retest signal. Kupnja {dh(tr['entry_date'])} po {hr(tr['raw_entry'], 2)} $, izlaz {dh(tr['exit_date'])} po {hr(tr['raw_exit'], 2)} $ ({pcts(tr['return'])}, {tr['bars_held']} dana). 1.000 € postaje {money(tr['return'])}. Ovo je najbolja memorijska trgovina W5 u AI eri, rijetka: tipična trgovina je mnogo manja."})
    # 3 stop loss
    t, e, tr = CASES["w5_stop"]
    lvl = e.level
    b = chart_before("q_stop_before.png", t, e.i, 50, lvl, "Retest signal: dodir razine, zatvaranje iznad.")
    a = chart_after_w5("q_stop_after.png", t, e.i, tr, lvl, 50, "Cijena je pala ispod stopa, izlaz s gubitkom.", end_pad=8)
    stop_px = lvl * 0.97
    qs.append({"part": "2. W5 na stvarnim grafovima", "img": b, "after": a, "q": f"{t}, {dh(date_of(t, e.i))}. Retest signal: razina {hr(lvl, 2)} $. Ako W5 kupi sutra, na kojoj će cijeni biti zaštitni stop?",
               "opts": [f"{hr(lvl * 0.97, 2)} $ (3 % ispod razine)", f"{hr(tr['raw_entry'] * 0.90, 2)} $ (10 % ispod ulaza)", f"{hr(lvl * 0.90, 2)} $ (10 % ispod razine)"], "ok": 0,
               "why": f"Stop je 3 % ispod razine, {hr(stop_px, 2)} $. Kupilo se po {hr(tr['raw_entry'], 2)} $, a izlaz je bio po {hr(tr['raw_exit'], 2)} $ ({pcts(tr['return'])}). Na 1.000 € to je oko {hr(abs(tr['return']) * 1000, 0)} € gubitka. Većina gubitaka W5 je mala; zaradu čine velike pobjede."})
    # 4 cancel
    t, e = CASES["w5_cancel"]
    lvl = e.level
    b = chart_before("q_cancel_before.png", t, e.i, 50, lvl, "Razina je bila probijena prije nekoliko dana. Danas je cijena zatvorila ISPOD razine.", n_back=60)
    b2 = b
    qs.append({"part": "2. W5 na stvarnim grafovima", "img": b, "after": None, "q": f"{t}, {dh(date_of(t, e.i))}. Prije {e.i - e.armed_i} dana W5 je naoružala razinu {hr(lvl, 2)} $ (proboj). Danas je cijena zatvorila ispod nje ({hr(BARS[t].close[e.i], 2)} $). Što je s tim probojem?",
               "opts": ["Još vrijedi, W5 čeka retest", "Poništen je: lažni proboj, nema trgovine", "W5 kupuje jer je jeftinije"], "ok": 1,
               "why": f"Zatvaranje ispod razine poništava proboj. Od svih probojeva u AI eri ({hr(ST['kinds'].get('arm', 0))}) takvih je bilo {hr(ST['kinds'].get('cancel', 0))}. To je upravo zaštita od lažnih probojeva: nema ulaza, nema gubitka."})
    # 5 expired
    t, e = CASES["w5_expire"]
    lvl = e.level
    b = chart_before("q_expire_before.png", t, e.i, 50, lvl, "Razina iz proboja prije 40+ dana. Cijena je cijelo vrijeme ostala iznad nje, ali nije se vratila.", n_back=70)
    qs.append({"part": "2. W5 na stvarnim grafovima", "img": b, "after": None, "q": f"{t}, {dh(date_of(t, e.i))}. Proboj razine {hr(lvl, 2)} $ bio je prije {e.i - e.armed_i} trgovinskih dana. Cijena se nije vratila na razinu. Što je s tim probojem?",
               "opts": ["Nastavlja se čekati neograničeno", "Istekao je nakon 40 dana, više nema signala", "W5 kupuje po tržišnoj cijeni"], "ok": 1,
               "why": f"Retest mora doći u 40 trgovinskih dana. Ovdje je prošlo {e.i - e.armed_i}, pa je razina istekla. Takvih je u AI eri bilo {hr(ST['kinds'].get('expire', 0))}. Dionica koja ode bez povratka ostaje neiskorištena: to je cijena filtra."})
    # 6 ignored signal
    t, e = CASES["w5_ignored"]
    lvl = e.level
    held = next(x for x in W5T[t] if pd.Timestamp(x["entry_date"]) <= date_of(t, e.i) <= pd.Timestamp(x["exit_date"]))
    b = chart_before("q_ign_before.png", t, e.i, 50, lvl, "Retest signal na današnji dan, ali W5 već drži poziciju u ovoj dionici.", n_back=70)
    qs.append({"part": "2. W5 na stvarnim grafovima", "img": b, "after": None, "q": f"{t}, {dh(date_of(t, e.i))}. Retest signal je ispunjen, ali W5 već drži poziciju otvorenu {dh(held['entry_date'])} (izlaz kasnije {dh(held['exit_date'])}). Što radi?",
               "opts": ["Kupuje još jednu poziciju", "Preskače signal: jedna pozicija po dionici", "Zatvara staru"], "ok": 1,
               "why": f"Preskače. Stara pozicija je završila {dh(held['exit_date'])} s {pcts(held['return'])} u {held['bars_held']} dana."})
    # C13C questions
    t, x = CASES["c_win"]
    sig_i = idx_of(t, x["entry_date"]) - 1
    d = Q.c13c_signal_days(BARS[t])
    row = d.iloc[sig_i]
    b = chart_c13c_before("qc_win_before.png", t, sig_i, "Isprekidana linija je prosjek 200 dana. Žuto su zadnjih 5 dana.")
    a = chart_after_c13c("qc_win_after.png", t, x, "Crvena stepenasta crta je stop (90 % vrha), samo se diže.")
    qs.append({"part": "3. C13C na stvarnim grafovima", "img": b, "after": a, "q": f"{t}, {dh(date_of(t, sig_i))}. Zatvaranje {hr(row.close, 2)} $, prosjek 200 dana {hr(row.sma200, 2)} $, promjena u 5 dana {pcts(row.chg5)}. Što radi C13C sutra?",
               "opts": ["Kupuje po otvaranju", "Ne radi ništa", "Prodaje"], "ok": 0,
               "why": f"Oba uvjeta su ispunjena: iznad prosjeka 200 dana i pad veći od 5 % u 5 dana. Kupnja {dh(x['entry_date'])} po {hr(x['raw_entry'], 2)} $, stop 10 % ispod vrha, izlaz {dh(x['exit_date'])} po {hr(x['raw_exit'], 2)} $ ({pcts(x['return'])}, {x['bars_held']} dana). 1.000 € postaje {money(x['return'])}."})
    t, x = CASES["c_loss"]
    sig_i = idx_of(t, x["entry_date"]) - 1
    row = Q.c13c_signal_days(BARS[t]).iloc[sig_i]
    b = chart_c13c_before("qc_loss_before.png", t, sig_i, "Ista situacija: iznad prosjeka 200 dana i pad u zadnjih 5 dana.")
    a = chart_after_c13c("qc_loss_after.png", t, x, "Pad se nastavio, stop je izbacio poziciju s gubitkom.")
    qs.append({"part": "3. C13C na stvarnim grafovima", "img": b, "after": a, "q": f"{t}, {dh(date_of(t, sig_i))}. Pad u 5 dana {pcts(row.chg5)}, zatvaranje {hr(row.close, 2)} $ iznad prosjeka 200 dana ({hr(row.sma200, 2)} $). Hoće li ova trgovina sigurno zaraditi?",
               "opts": ["Da, uvijek se vrati", "Ne, može se nastaviti pad i stop izbaci s gubitkom", "Da, jer je iznad prosjeka 200 dana"], "ok": 1,
               "why": f"C13C kupuje korekciju, ali ona može postati veći pad. Ova trgovina je završila {pcts(x['return'])} ({hr(abs(x['return']) * 1000, 0)} € na 1.000 €) za {x['bars_held']} dana. C13C je uspješan u {pcts(ST['hit_c'], 0).replace('+', '')} trgovina (W5 {pcts(ST['hit_w5'], 0).replace('+', '')})."})
    t, dd = CASES["c_near"]
    i = idx_of(t, dd)
    row = Q.c13c_signal_days(BARS[t]).iloc[i]
    b = chart_c13c_before("qc_near_before.png", t, i, "Iznad prosjeka 200 dana, ali pad u zadnjih 5 dana nije dovoljno velik.")
    qs.append({"part": "3. C13C na stvarnim grafovima", "img": b, "after": None, "q": f"{t}, {dh(dd)}. Zatvaranje {hr(row.close, 2)} $, iznad prosjeka 200 dana ({hr(row.sma200, 2)} $), pad u 5 dana {pcts(row.chg5)}. Što radi C13C?",
               "opts": ["Kupuje sutra", "Ne kupuje: pad nije dosegao -5 %"], "ok": 1,
               "why": f"Trend je u redu, ali okidač traži pad od najmanje 5 % u 5 dana, a ovdje je {pcts(row.chg5)}. Pravilo je strogo: bez izuzetaka."})
    t, dd = CASES["c_below"]
    i = idx_of(t, dd)
    row = Q.c13c_signal_days(BARS[t]).iloc[i]
    b = chart_c13c_before("qc_below_before.png", t, i, "Dubok pad, ali cijena je ispod prosjeka 200 dana.")
    qs.append({"part": "3. C13C na stvarnim grafovima", "img": b, "after": None, "q": f"{t}, {dh(dd)}. Pad u 5 dana {pcts(row.chg5)} (velik), ali zatvaranje {hr(row.close, 2)} $ je ISPOD prosjeka 200 dana ({hr(row.sma200, 2)} $). Što radi C13C?",
               "opts": ["Kupuje: veći pad je bolja prilika", "Ne kupuje: nema dugoročnog uzlaznog trenda"], "ok": 1,
               "why": "Trend filter je prvi uvjet. Ispod prosjeka 200 dana C13C ne kupuje ni na dubokom padu; to ga u medvjeđim fazama drži izvan tržišta (u 2021.-2022. je bio oko nule dok je držanje gubilo)."})
    return qs


def compare_questions() -> list[dict[str, Any]]:
    f = lambda x, n=0: hr(x, n)  # noqa: E731
    qs = [
        {"part": "4. W5 naspram C13C", "q": "Koja strategija trguje <b>češće</b> (43 dionice, AI era)?",
         "opts": [f"W5: {f(SW5['trades_per_month'])} trgovina mjesečno", f"C13C: {f(SC['trades_per_month'])} trgovina mjesečno"], "ok": 1,
         "why": f"C13C ({f(SC['trades_per_month'])}/mj.) je više nego dvostruko češći od W5 ({f(SW5['trades_per_month'])}/mj.), jer se korekcije događaju češće od probojeva s povratkom."},
        {"part": "4. W5 naspram C13C", "q": "Koja ima veći <b>udio dobitnih</b> trgovina?",
         "opts": [f"W5: {pcts(SW5['hit_rate'], 0).replace('+', '')}", f"C13C: {pcts(SC['hit_rate'], 0).replace('+', '')}"], "ok": 1,
         "why": f"C13C {pcts(SC['hit_rate'], 0).replace('+', '')}, W5 {pcts(SW5['hit_rate'], 0).replace('+', '')}. W5 gubi češće, ali malo (stop blizu), a dobitnike drži dugo."},
        {"part": "4. W5 naspram C13C", "q": "Koja nosi veći <b>očekivani iznos po trgovini</b> (€ na 1.000 €)?",
         "opts": [f"W5: {f(SW5['expectancy_eur'])} €", f"C13C: {f(SC['expectancy_eur'])} €"], "ok": 0,
         "why": f"W5 {f(SW5['expectancy_eur'])} € naspram C13C {f(SC['expectancy_eur'])} €, profit factor {hr(SW5['profit_factor'], 2)} naspram {hr(SC['profit_factor'], 2)}. Ali W5 trguje rjeđe, pa C13C ipak ima veći ukupni prinos ({pcts(SC['total_return'], 0)} naspram {pcts(SW5['total_return'], 0)})."},
        {"part": "4. W5 naspram C13C", "q": "Koja je imala <b>manji najveći pad</b> (43 dionice, AI era)?",
         "opts": [f"W5: {pcts(SW5['max_drawdown'], 0).replace('+', '')}", f"C13C: {pcts(SC['max_drawdown'], 0).replace('+', '')}"], "ok": 0,
         "why": f"W5 {pcts(SW5['max_drawdown'], 0)} naspram C13C {pcts(SC['max_drawdown'], 0)}. Stop blizu razine reže gubitke brzo."},
        {"part": "4. W5 naspram C13C", "q": f"Koliko dobiti W5 nosi <b>10 najboljih trgovina</b>?",
         "opts": ["Oko 10 %", f"Oko {hr(ST['top10_gross'] * 100, 0)} % ukupnih dobitaka", "Nijedna posebno", "100 %"], "ok": 1,
         "why": f"Od {ST['n_w5']} W5 trgovina, 10 najboljih daje oko {hr(ST['top10_gross'] * 100, 0)} % zbroja svih dobitaka (neto dobit: {hr(ST['top10_net'] * 100, 0)} %). Zato je W5 osjetljiv: bez nekoliko velikih pobjeda rezultat bi bio osrednji."},
        {"part": "4. W5 naspram C13C", "q": f"U memorijskoj trojci (MU, WDC, STX) W5 zarađuje po trgovini <b>više ili manje</b> nego C13C?",
         "opts": [f"Više: {f(MW5['expectancy_eur'])} € naspram {f(MC['expectancy_eur'])} €", f"Manje: {f(MW5['expectancy_eur'])} € naspram {f(MC['expectancy_eur'])} €"], "ok": 0,
         "why": f"W5 {f(MW5['expectancy_eur'])} € (profit factor {hr(MW5['profit_factor'], 2)}) naspram {f(MC['expectancy_eur'])} € ({hr(MC['profit_factor'], 2)}). Ali W5 ima oko {hr(MW5['trades_per_month'], 1)} trgovinu mjesečno na svih troje, a {hr(MW5['top5_profit_share'] * 100, 0)} % dobiti nose 5 najboljih trgovina."},
        {"part": "4. W5 naspram C13C", "q": "Placebo test: kako se ponašaju <b>prave razine</b> prema lažnim (nasumično postavljenim)?",
         "opts": ["Prave razine drže puno bolje", "Prave razine nisu bolje od lažnih (dodir 28,1 % naspram 29,2 %)", "Lažne razine nikad ne drže"], "ok": 1,
         "why": "Na 24.510 pravih razina, 55 papira i 44 mjeseca nije pronađena razlika. To znači da W5 vjerojatno ne zarađuje zato što razine \"magično\" drže, nego zato što kupuje jake dionice nakon proboja i drži ih dok traje uzlazni trend. Dobra strategija, ali ne ono što priča o razinama obećava."},
    ]
    return qs


# ----------------------------------------------------------------------------------------------- page
def compare_chart_question() -> dict[str, Any]:
    t = "MU"
    mu_big = max((x for x in W5T[t]), key=lambda x: x["return"])
    s = idx_of(t, mu_big["entry_date"])
    lo, hi = s - 25, idx_of(t, mu_big["exit_date"]) + 10
    img, data = chart_compare("q_cmp.png", t, lo, hi)
    w5r = [x["return"] for x in data["w5"]]
    cr = [x["return"] for x in data["c"]]
    w5_tot = float(np.prod([1 + r for r in w5r]) - 1) if w5r else 0.0
    c_tot = float(np.prod([1 + r for r in cr]) - 1) if cr else 0.0
    return {"part": "4. W5 naspram C13C", "img": img, "after": None,
            "q": f"{t}, {data['d0']} do {data['d1']}. Zelene crte su W5 trgovine ({len(w5r)}), narančaste C13C trgovine ({len(cr)}). Ako si u svakoj trgovini ulagao svih 1.000 € i sve ih redom nizao (složeno), koja je ispala bolje?",
            "opts": [f"W5: 1.000 € postaje {money(w5_tot)}", f"C13C: 1.000 € postaje {money(c_tot)}"], "ok": 0 if w5_tot > c_tot else 1,
            "why": f"W5: {len(w5r)} trgovina, 1.000 € postaje {money(w5_tot)}. C13C: {len(cr)} trgovina, 1.000 € postaje {money(c_tot)}. To je samo jedno razdoblje jedne dionice; ne zaključuj iz njega ništa općenito."}


def main() -> int:
    CH.mkdir(parents=True, exist_ok=True)
    all_q = build_questions() + build_chart_questions() + compare_questions()
    all_q.insert(len(all_q) - 7, compare_chart_question())
    import random

    for i, q in enumerate(all_q):
        q["id"] = i
        for key in ("q", "why"):
            q[key] = q[key].replace("..", ".")
        q["opts"] = [o.replace("..", ".") for o in q["opts"]]
        order = list(range(len(q["opts"])))
        random.Random(20261014 + i).shuffle(order)  # fixed seed: the correct answer is not always option 2
        q["opts"] = [q["opts"][j] for j in order]
        q["ok"] = order.index(q["ok"])
    parts: dict[str, list[dict[str, Any]]] = {}
    for q in all_q:
        parts.setdefault(q["part"], []).append(q)
    mc.write_captions()
    # embed images
    for q in all_q:
        for key in ("img", "after"):
            if q.get(key):
                uri, w, h, _ = encode_chart(str(CH / q[key]))
                q[key] = uri
    (OUT / "cases.json").write_text(json.dumps([{k: v for k, v in q.items() if k not in ("img", "after")} for q in all_q], ensure_ascii=False, indent=1))
    from w5_quiz_page import render  # noqa: E402

    page = render(all_q, ST, SW5, SC, MW5, MC, CSS, JS)
    (OUT / "w5_quiz.html").write_bytes(page.encode("utf-8"))
    print(len(all_q), "pitanja,", round(len(page.encode()) / 1048576, 2), "MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
