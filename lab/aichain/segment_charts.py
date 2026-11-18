"""Notebook-style PNG charts for one AI-chain segment page (graph paper, handwriting, red teacher notes).

Everything is computed from the REAL results (results/*.json), the profile statistics and the raw daily
CSVs in data/ohlcv. Reads only; never touches orders or frozen files.

Usage:
    .venv/bin/python -m lab.aichain.segment_charts mem_interface_storage
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

from lab.aichain.profile_stats import PIVOT_K, SR_BAND, SR_LOOKAHEAD, SR_MAX_AGE, drawdowns, load_close_frame, pivots
from lab.top10.charts import GREEN, GRID, INK, PAPER, PENCIL, RED, day, eur, paper, ring, sketch, teacher
from lab.top10.charts import note as _note

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
AI_START = pd.Timestamp("2023-01-01")
END = pd.Timestamp("2026-10-05")
ORANGE, GREY, GOLD = "#d9822b", "#6b7280", "#b8860b"
TICK_COLORS = {"RMBS": INK, "SIMO": GREEN, "MRAM": "#8e44ad", "NTAP": ORANGE}
NAMES = {
    "B0_BUYHOLD": "Držanje",
    "K1_C13C_ORIG": "C13C (K1)",
    "K2_SMA200_TREND": "Trend SMA200 (K2)",
    "K3_DONCHIAN_55_20": "Donchian (K3)",
    "K4_TSMOM_126": "Momentum 126 d (K4)",
    "K5_SUPPORT_RESISTANCE": "Potpora/otpor (K5)",
    "K5B_SR_BREAKOUT_RETEST": "Proboj i povratak (K5B)",
    "K6_MOMENTUM_CS": "Rotacija (K6)",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C + ponovni ulaz (K7)",
}
DPI = 110


def hr(x: float, nd: int = 1, sign: bool = False) -> str:
    x = 0.0 if round(x, nd) == 0 else x  # avoid "-0"
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s.replace(".", ",")


def pc(x: float, nd: int = 1, sign: bool = False) -> str:
    return hr(x * 100, nd, sign) + " %"


def note(ax: Any, text: str, *args: Any, **kwargs: Any) -> Any:
    """Handwritten note; dollar signs are escaped so matplotlib does not switch to math mode."""
    return _note(ax, text.replace("$", r"\$"), *args, **kwargs)


def save(fig: Any, out: Path, name: str) -> str:
    fig.savefig(out / name, dpi=DPI, facecolor=PAPER)
    plt.close(fig)
    return name


def load_inputs(segment: str) -> dict[str, Any]:
    seg_dir = BASE / "segments" / segment
    analysis = json.loads((seg_dir / "analysis.json").read_text())
    seg = json.loads((BASE / "results" / f"{segment}.json").read_text())
    tickers = analysis["analizirani_tickeri"]
    tk = {t: json.loads((BASE / "results" / f"{t}.json").read_text()) for t in tickers}
    profile = json.loads((seg_dir / "profile.json").read_text())
    stats = pd.read_csv(seg_dir / "profile_stats.csv")
    stats = stats[stats["window"] == "ai_2023plus"].set_index("ticker")
    prices = {t: load_close_frame(t).loc[:END] for t in tickers}
    return {"dir": seg_dir, "analysis": analysis, "seg": seg["contenders"], "tk": tk, "stats": stats, "profile": profile, "prices": prices, "tickers": tickers}


def equity_series(c: dict[str, Any], per: float) -> pd.Series:
    s = pd.Series({pd.Timestamp(d): v for d, v in c["equity"]["ai_era"]})
    return s / per


def stop_path(df: pd.DataFrame, entry: str, exit_: str) -> pd.Series:
    """Trailing stop of the original C13C: 90 % of the highest high known so far, never lowered.

    The new peak only moves the stop from the NEXT day (we do not know the intraday order of high and low).
    """
    seg = df.loc[pd.Timestamp(entry): pd.Timestamp(exit_)]
    peak = seg["high"].cummax().shift(1)
    peak.iloc[0] = seg["high"].iloc[0]
    return (peak * 0.9).cummax()


# --------------------------------------------------------------------------- chart 1
def chart_prices(d: dict[str, Any], out: Path, picks: list[str]) -> tuple[str, dict[str, Any]]:
    info: dict[str, Any] = {}
    fig, axes = plt.subplots(len(picks), 1, figsize=(11, 4.6 * len(picks)), sharex=False)
    fig.subplots_adjust(top=0.95, bottom=0.075, hspace=0.34, left=0.07, right=0.98)
    for ax, t in zip(axes, picks):
        df = d["prices"][t]
        sma = df["close"].rolling(200).mean()
        lo_x = pd.Timestamp("2022-07-01")
        x = df.loc[lo_x:]
        paper(ax, f"{t}: cijena, prosjek 200 dana i svaki ulaz/izlaz C13C-a")
        ax.axvspan(lo_x, AI_START, color="#eceff3", alpha=0.9, lw=0)
        ax.axvline(AI_START, color=RED, ls="--", lw=1.3)
        ax.text(AI_START + pd.Timedelta(days=15), 0.02, "AI era počinje (2023.)", transform=ax.get_xaxis_transform(), fontsize=10, color=RED)
        ax.text(lo_x + pd.Timedelta(days=8), 0.45, "prije AI ere:\nsamo kontekst", transform=ax.get_xaxis_transform(), fontsize=9, color=GREY)
        sketch(ax.plot(x.index, x["close"], color=INK, lw=1.5, label="cijena zatvaranja")[0], 0.5, 60, 3)
        ax.plot(x.index, sma.loc[lo_x:], color=ORANGE, lw=1.7, ls="--", label="prosjek 200 dana (SMA200)")
        tr = d["tk"][t]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
        ent = [(pd.Timestamp(r["entry_date"]), r["raw_entry"]) for r in tr]
        ext = [(pd.Timestamp(r["exit_date"]), r["raw_exit"], r["detail"]) for r in tr]
        ax.scatter([a for a, _ in ent], [b for _, b in ent], marker="^", s=70, color=GREEN, edgecolors="#0b4d24", zorder=6, label=f"kupnja ({len(tr)} poslova)")
        stops = [e for e in ext if e[2] != "liquidated at last close, exit cost paid"]
        ax.scatter([a for a, _, _ in stops], [b for _, b, _ in stops], marker="v", s=70, color=RED, edgecolors="#6b1409", zorder=6, label="izlaz na stopu")
        ax.legend(loc="upper left", fontsize=9, frameon=True, facecolor=PAPER, edgecolor=GRID, ncol=2)
        ax.set_ylabel("cijena u USD")
        ax.set_xlim(lo_x, END + pd.Timedelta(days=10))
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%Y"))
        info[t] = {"n_trades": len(tr)}

    # RMBS: one real dip signal; stop-line example on SIMO; gap exit example on RMBS
    ax = axes[picks.index("RMBS")]
    df = d["prices"]["RMBS"]
    tr = d["tk"]["RMBS"]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
    best = None
    for r in tr:
        ei = df.index.get_loc(pd.Timestamp(r["entry_date"]))
        sig = ei - 1
        drop = df["close"].iloc[sig] / df["close"].iloc[sig - 5] - 1
        if best is None or drop < best[0]:
            best = (drop, r, sig)
    drop, r, sig = best
    sd, s5 = df.index[sig], df.index[sig - 5]
    info["dip"] = {"ticker": "RMBS", "signal_date": str(sd.date()), "start_date": str(s5.date()), "p0": float(df["close"].iloc[sig - 5]), "p1": float(df["close"].iloc[sig]), "drop": float(drop), "entry_date": r["entry_date"], "entry_price": r["raw_entry"]}
    ax.scatter([sd], [df["close"].iloc[sig]], s=900, facecolors="none", edgecolors=RED, linewidths=2, zorder=7)
    note(ax, f"Signal {day(sd)}: u 5 dana pad {hr(abs(drop) * 100)} %\n({hr(df['close'].iloc[sig - 5], 2)} na {hr(df['close'].iloc[sig], 2)} $),\ncijena je još iznad SMA200 = signal za kupnju.\nKupnja sutradan na otvaranju: {hr(r['raw_entry'], 2)} $",
         (sd, float(df["close"].iloc[sig])), (0.46, 0.80), RED, rad=-0.15, size=10.5)
    gaps = [(pd.Timestamp(x["exit_date"]), x["raw_exit"]) for x in tr if x["detail"] == "gap_stop"]
    n_gap = len(gaps)
    if gaps:
        a_, b_ = min(gaps, key=lambda z: z[1] / float(df["close"].shift(1).loc[z[0]]))
        prev = float(df["close"].shift(1).loc[a_])
        info["gap_example"] = {"date": str(a_.date()), "open": float(b_), "prev_close": prev, "gap": float(b_ / prev - 1)}
        ring(ax, a_, float(b_), RED, 500)
        note(ax, f"{day(a_)}: dionica otvara na {hr(b_, 2)} $ (dan prije {hr(prev, 2)} $, {hr((b_ / prev - 1) * 100)} %).\nStop ne pomaže: izlaz je po otvaranju, ne po stopu.", (a_, b_), (0.08, 0.60), RED, rad=-0.15, size=10.5)
    info["gap_exits_rmbs"] = n_gap

    # SIMO: stop line on best trade
    ax = axes[picks.index("SIMO")]
    df = d["prices"]["SIMO"]
    tr = d["tk"]["SIMO"]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
    r = max(tr, key=lambda z: z["return"])
    sp = stop_path(df, r["entry_date"], r["exit_date"])
    ax.step(sp.index, sp.values, where="post", color=RED, lw=2.0, zorder=5)
    info["stop_trade"] = {"ticker": "SIMO", "entry": r["entry_date"], "exit": r["exit_date"], "entry_px": r["raw_entry"], "exit_px": r["raw_exit"], "ret": r["return"], "stop_last": float(sp.iloc[-1]), "peak": float(sp.iloc[-1] / 0.9)}
    mid = sp.index[len(sp) // 2]
    note(ax, f"Crvena stepenica = stop: uvijek 10 % ispod najvišeg\nvrha od kupnje, i nikad ne ide dolje. Kupnja {day(pd.Timestamp(r['entry_date']))}\npo {hr(r['raw_entry'], 2)} $, izlaz {day(pd.Timestamp(r['exit_date']))} po {hr(r['raw_exit'], 2)} $:\n1.000 € postaje {eur(1000 * (1 + r['return']))}.",
         (mid, float(sp.loc[mid])), (0.36, 0.50), RED, rad=0.2, size=10.5)
    # NTAP: biggest one-day jump and whether C13C was in the position that day
    ax = axes[picks.index("NTAP")]
    df = d["prices"]["NTAP"]
    tr = d["tk"]["NTAP"]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
    jump = pd.Timestamp("2026-05-29")
    prev_close = float(df["close"].shift(1).loc[jump])
    in_pos = any(pd.Timestamp(r["entry_date"]) <= jump <= pd.Timestamp(r["exit_date"]) for r in tr)
    info["ntap_jump"] = {"date": str(jump.date()), "prev_close": prev_close, "open": float(df["open"].loc[jump]), "close": float(df["close"].loc[jump]), "c13c_in_position": in_pos}
    ring(ax, jump, float(df["close"].loc[jump]), RED, 700)
    note(ax, f"{day(jump)}: skok od {hr(prev_close, 2)} na {hr(df['close'].loc[jump], 2)} $ u jednom danu\n(+{hr((df['close'].loc[jump] / prev_close - 1) * 100)} %). C13C u tom trenutku "
         + ("JE" if in_pos else "NIJE") + " bio u poziciji.\nNTAP je glatka dionica: pad od 5 % dolazi rijetko,\npa je C13C imao samo "
         + f"{len(tr)} poslova ({pc(d['analysis']['c13c_k1_iskreno']['po_tickeru']['NTAP']['K1_prinos_pct'] / 100, 1, True)}).",
         (jump, float(df["close"].loc[jump])), (0.28, 0.66), RED, rad=-0.15, size=10.5)
    teacher(fig, "Zeleni trokut = kupnja, crveni = prodaja kad cijena padne do stopa. 1.000 € u jednom poslu raste ili pada za onoliko posto koliko piše uz posao.")
    return save(fig, out, "chart_01_cijene_i_poslovi.png"), info


# --------------------------------------------------------------------------- chart 2, 3
def segment_curves(d: dict[str, Any]) -> dict[str, pd.Series]:
    return {k: equity_series(d["seg"][k], 4.0) for k in ("B0_BUYHOLD", "K1_C13C_ORIG", "K6_MOMENTUM_CS")}


def flat_stretches(d: dict[str, Any], min_days: int = 15) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Stretches where C13C held NO position in any of the four tickers (derived from its trade lists)."""
    days = pd.bdate_range("2023-01-03", END)
    inpos = pd.Series(False, index=days)
    for r in d["seg"]["K1_C13C_ORIG"]["trades"]["ai_era"]:
        inpos.loc[pd.Timestamp(r["entry_date"]): pd.Timestamp(r["exit_date"])] = True
    out: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []
    start = None
    n = 0
    for dt, v in inpos.items():
        if not v:
            start = dt if start is None else start
            n += 1
            last = dt
        elif start is not None:
            if n >= min_days:
                out.append((start, last, n))
            start, n = None, 0
    if start is not None and n >= min_days:
        out.append((start, last, n))
    return out


def k1_exposure(d: dict[str, Any]) -> pd.Series:
    """Share of the 4 sleeves C13C held on each business day (rebuilt from its trade lists)."""
    days = pd.bdate_range("2023-01-03", END)
    expo = pd.Series(0.0, index=days)
    for r in d["seg"]["K1_C13C_ORIG"]["trades"]["ai_era"]:
        expo.loc[pd.Timestamp(r["entry_date"]): pd.Timestamp(r["exit_date"])] += 1.0 / len(d["tickers"])
    return expo


def chart_equity(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    cv = segment_curves(d)
    bh, k1, k6 = cv["B0_BUYHOLD"], cv["K1_C13C_ORIG"], cv["K6_MOMENTUM_CS"]
    fig, ax = plt.subplots(figsize=(11, 6.4))
    fig.subplots_adjust(bottom=0.17, top=0.9, left=0.075, right=0.98)
    paper(ax, "Što se dogodi s 1.000 € u segmentu (4 dionice)")
    ax.axvline(AI_START, color=RED, ls="--", lw=1.3)
    ax.text(AI_START + pd.Timedelta(days=10), 0.62, "AI era počinje\novdje (2023.)", transform=ax.get_xaxis_transform(), fontsize=10, color=RED)
    for s, c, lab, lw in ((bh, GREY, "držanje", 2.0), (k1, INK, "C13C (K1)", 2.0), (k6, GREEN, "pobjednik K6 (rotacija)", 2.0)):
        sketch(ax.plot(s.index, s.values, color=c, lw=lw, label=f"{lab}: kraj {eur(s.iloc[-1])}")[0], 0.5, 60, 3)
    ax.legend(loc="upper left", fontsize=10, frameon=True, facecolor=PAPER, edgecolor=GRID)
    ax.set_ylim(0, 6700)
    ax.set_ylabel("vrijednost u € (početak 1.000 €)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    info: dict[str, Any] = {"end": {k: float(v.iloc[-1]) for k, v in cv.items()}}
    dd = bh / bh.cummax() - 1
    tro = dd.idxmin()
    pk = bh.loc[:tro].idxmax()

    def v(s: pd.Series, t: pd.Timestamp) -> float:
        return float(s.loc[:t].iloc[-1])

    info["bh_dd"] = {"peak": str(pk.date()), "trough": str(tro.date()), "bh_peak": v(bh, pk), "bh_trough": v(bh, tro), "k1_peak": v(k1, pk), "k1_trough": v(k1, tro), "k6_peak": v(k6, pk), "k6_trough": v(k6, tro)}
    ax.axvspan(pk, tro, color="#fbe3df", alpha=0.7, lw=0)
    expo = k1_exposure(d)
    e_win = float(expo.loc[pk:tro].mean())
    k1_loss = (1 - v(k1, tro) / v(k1, pk)) * 1000
    bh_loss = (1 - v(bh, tro) / v(bh, pk)) * 1000
    info["bh_dd"]["k1_exposure"] = e_win
    info["bh_dd"]["k1_loss_per_1000"] = k1_loss
    info["bh_dd"]["bh_loss_per_1000"] = bh_loss
    note(ax, f"{day(pk)} do {day(tro)}: držanje pada s {eur(v(bh, pk))} na {eur(v(bh, tro))}.\n"
         f"C13C je tad u dionicama bio prosječno samo {pc(e_win, 0)} vremena: s {eur(v(k1, pk))} na {eur(v(k1, tro))}.\n"
         f"Na 1.000 € gubitak {eur(k1_loss)} umjesto {eur(bh_loss)}: čekanje je uštedjelo oko {eur(bh_loss - k1_loss)}.",
         (tro, v(k1, tro)), (0.33, 0.66), RED, rad=-0.2, size=10.5)
    stretches = [x for x in flat_stretches(d) if x[0] > pd.Timestamp("2023-01-20")]
    chg = [(v(bh, e) / v(bh, a_) - 1, a_, e, n) for a_, e, n in stretches]
    missed = max(chg)
    info["flat_missed"] = {"start": str(missed[1].date()), "end": str(missed[2].date()), "days": missed[3], "bh_change": missed[0]}
    ax.axvspan(missed[1], missed[2], color="#e6f0fb", alpha=0.9, lw=0)
    base2 = v(bh, missed[1])
    note(ax, f"Plavo: {missed[3]} radnih dana ({day(missed[1])} do {day(missed[2])}) C13C nije držao nijednu od 4 dionica.\n"
         f"Držanje je tad raslo {pc(missed[0], 0)}: s {eur(base2)} na {eur(v(bh, missed[2]))}. Čekanje je propustilo dobit.",
         (missed[1] + (missed[2] - missed[1]) / 2, float(k1.loc[missed[1]:missed[2]].mean())), (0.30, 0.085), INK, rad=0.0, size=10.5)
    note(ax, f"K6 završava na {eur(k6.iloc[-1])}, držanje na {eur(bh.iloc[-1])}.\nK6 je jedini koji je pobijedio držanje.", (k6.index[-1], float(k6.iloc[-1])), (0.60, 0.94), GREEN, rad=-0.2, size=10.5, ha="left")
    teacher(fig, "Svaka krivulja je simulacija na pravim cijenama 2023.-2026. uz trošak 2,5 baznih bodova po strani (0,25 € na 1.000 €). Nije obećanje budućnosti.")
    return save(fig, out, "chart_02_kapital_1000_eur.png"), info


def chart_drawdown(d: dict[str, Any], out: Path, eq_info: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    cv = segment_curves(d)
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.subplots_adjust(bottom=0.17, top=0.9, left=0.075, right=0.98)
    paper(ax, "Najveći pad od vrha: koliko boli najgori dan")
    ax.axvline(AI_START, color=RED, ls="--", lw=1.3)
    ax.text(AI_START + pd.Timedelta(days=10), 0.35, "AI era počinje\n(2023.)", transform=ax.get_xaxis_transform(), fontsize=10, color=RED)
    info: dict[str, Any] = {}
    for k, c, lab in (("B0_BUYHOLD", GREY, "držanje"), ("K1_C13C_ORIG", INK, "C13C (K1)"), ("K6_MOMENTUM_CS", GREEN, "K6 (pobjednik)")):
        s = cv[k]
        dd = s / s.cummax() - 1
        sketch(ax.plot(dd.index, dd.values * 100, color=c, lw=1.8, label=f"{lab}: najgore {pc(dd.min(), 1)}")[0], 0.5, 60, 3)
        t = dd.idxmin()
        pk = s.loc[:t].idxmax()
        info[k] = {"trough": str(t.date()), "peak": str(pk.date()), "dd": float(dd.min()), "peak_val": float(s.loc[pk]), "trough_val": float(s.loc[t])}
    ax.legend(loc="lower left", fontsize=10, frameon=True, facecolor=PAPER, edgecolor=GRID)
    ax.set_ylabel("pad od dotadašnjeg vrha u %")
    ax.set_ylim(-82, 3)
    for k, c, pos in (("B0_BUYHOLD", GREY, (0.28, 0.35)), ("K6_MOMENTUM_CS", GREEN, (0.58, 0.16))):
        i = info[k]
        t = pd.Timestamp(i["trough"])
        ring(ax, t, i["dd"] * 100, RED, 500)
        loss = (i["peak_val"] - i["trough_val"]) / i["peak_val"] * 1000
        note(ax, f"{'Držanje' if k.startswith('B0') else 'K6'}, najgori dan {day(t)}:\nvrijednost s {eur(i['peak_val'])} na {eur(i['trough_val'])} (ukupni iznos).\nNa 1.000 € na vrhu to je gubitak od {eur(loss)}.",
             (t, i["dd"] * 100), pos, c if c != GREY else PENCIL, rad=0.25, size=10.5)
    k1i = info["K1_C13C_ORIG"]
    ring(ax, pd.Timestamp(k1i["trough"]), k1i["dd"] * 100, INK, 500)
    teacher(fig, "Pad od vrha: kad imaš 2.000 € i padne na 1.200 €, pad je 40 %. Lagan pad ne znači bolju strategiju: ocjenu ne snižavamo zbog veličine pada.")
    return save(fig, out, "chart_03_pad_od_vrha.png"), info


# --------------------------------------------------------------------------- chart 4
def chart_trades(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    tr = d["seg"]["K1_C13C_ORIG"]["trades"]["ai_era"]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.subplots_adjust(bottom=0.17, top=0.9, left=0.075, right=0.98)
    paper(ax, "Svih poslova C13C-a: koliko dana i koliko posto")
    ax.axhline(0, color=PENCIL, lw=1.2)
    for t, col in TICK_COLORS.items():
        for gap in (False, True):
            rows = [r for r in tr if r["ticker"] == t and (r["detail"] == "gap_stop") == gap]
            ax.scatter([r["bars_held"] for r in rows], [r["return"] * 100 for r in rows], s=48 if not gap else 60, marker="o" if not gap else "X", color=col, alpha=0.8, edgecolors="white", linewidths=0.5,
                       label=f"{t}" if not gap else None, zorder=4)
    ax.scatter([], [], marker="X", color=GREY, label="izlaz preko noći ispod stopa")
    ax.legend(loc="upper right", fontsize=10, frameon=True, facecolor=PAPER, edgecolor=GRID, ncol=2)
    ax.set_ylim(-42, 135)
    ax.set_xlabel("koliko je radnih dana posao trajao")
    ax.set_ylabel("prinos posla u %")
    best = max(tr, key=lambda r: r["return"])
    worst = min(tr, key=lambda r: r["return"])
    wins = sum(1 for r in tr if r["return"] > 0)
    info = {"n": len(tr), "wins": wins, "best": best, "worst": worst, "gap": sum(1 for r in tr if r["detail"] == "gap_stop")}
    ring(ax, best["bars_held"], best["return"] * 100, GREEN, 600)
    note(ax, f"Najbolji: {best['ticker']} {day(pd.Timestamp(best['entry_date']))} do {day(pd.Timestamp(best['exit_date']))},\n{best['bars_held']} dana, {pc(best['return'], 0, True)}. 1.000 € postaje {eur(1000 * (1 + best['return']))}.",
         (best["bars_held"], best["return"] * 100), (0.30, 0.86), GREEN, rad=0.2, size=10.5)
    ring(ax, worst["bars_held"], worst["return"] * 100, RED, 600)
    note(ax, f"Najgori: {worst['ticker']} {day(pd.Timestamp(worst['entry_date']))} do {day(pd.Timestamp(worst['exit_date']))},\n{worst['bars_held']} dana, {pc(worst['return'], 1, True)}. 1.000 € postaje {eur(1000 * (1 + worst['return']))}.",
         (worst["bars_held"], worst["return"] * 100), (0.20, 0.10), RED, rad=0.2, size=10.5)
    ax.text(0.98, 0.52, f"{wins} od {len(tr)} poslova je u plusu ({pc(wins / len(tr), 0)}).\nMnogo malih poraza, nekoliko velikih dobitaka.", transform=ax.transAxes, ha="right", fontsize=11, color=INK)
    teacher(fig, "Jedna točka = jedan posao: kupnja, pa izlaz na stopu. Većina je kratka i mala; zaradu nose rijetki dugi poslovi. Zato 'pet puta pogodio' ne znači puno.")
    return save(fig, out, "chart_04_poslovi.png"), info


# --------------------------------------------------------------------------- chart 5, 6
def contenders_table(d: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for k, v in d["seg"].items():
        w = v["windows"]["ai_era"]
        rows.append({"id": k, "name": NAMES[k], "ret": w["total_return"], "r2": w["total_return_cost_2x"], "r3": w["total_return_cost_3x"], "sharpe": w["sharpe"], "dd": w["max_drawdown"], "trades": w["trades"]})
    return pd.DataFrame(rows).set_index("id")


def chart_scoreboard(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    df = contenders_table(d).sort_values("sharpe")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 6.2), sharey=True)
    fig.subplots_adjust(bottom=0.17, top=0.88, left=0.2, right=0.98, wspace=0.08)
    win = d["analysis"]["pobjednik"]["pobjednik"]
    cols = [GOLD if i == win else (GREY if i == "B0_BUYHOLD" else INK) for i in df.index]
    bh = df.loc["B0_BUYHOLD"]
    paper(a, "Prinos 2023.-2026. (%)")
    a.barh(df["name"], df["ret"] * 100, color=cols, alpha=0.85, edgecolor=PENCIL)
    a.axvline(bh["ret"] * 100, color=RED, ls="--", lw=1.4)
    a.text(bh["ret"] * 100 + 6, 0.2, "držanje", color=RED, fontsize=10)
    for i, (k, r) in enumerate(df.iterrows()):
        a.text(max(r["ret"] * 100, 0) + 6, i, hr(r["ret"] * 100, 0) + " %", va="center", fontsize=9.5)
    a.set_xlim(-40, 470)
    paper(b, "Sharpe (veći je bolji)")
    b.barh(df["name"], df["sharpe"], color=cols, alpha=0.85, edgecolor=PENCIL)
    b.axvline(bh["sharpe"], color=RED, ls="--", lw=1.4)
    for i, (k, r) in enumerate(df.iterrows()):
        b.text(max(r["sharpe"], 0) + 0.03, i, hr(r["sharpe"], 2), va="center", fontsize=9.5)
    b.set_xlim(-0.7, 2.3)
    b.tick_params(axis="y", length=0)
    k6 = df.loc[win]
    note(a, f"Zlatna traka = pobjednik po unaprijed zadanom\npravilu (K6): 1.000 € postaje {eur(1000 * (1 + k6['ret']))}\nnaspram {eur(1000 * (1 + bh['ret']))} kod držanja.", (k6["ret"] * 100, list(df.index).index(win)), (0.50, 0.40), PENCIL, rad=0.25, size=10)
    note(b, f"Sharpe: K6 {hr(k6['sharpe'], 2)} naspram\n{hr(bh['sharpe'], 2)} držanja. Razlika je mala.", (k6["sharpe"], list(df.index).index(win)), (0.60, 0.55), RED, rad=0.2, size=10)
    teacher(fig, "Sharpe = koliko dobiti dobiješ za svaku jedinicu treskanja cijene. Crvena crta je držanje: pobjeđuje samo stupac koji prelazi crtu. Samo K6 ju je prešao i po prinosu i po Sharpeu.")
    return save(fig, out, "chart_05_ljestvica.png"), {"win": win}


def chart_costs(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    df = contenders_table(d).sort_values("ret")
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.subplots_adjust(bottom=0.21, top=0.9, left=0.22, right=0.98)
    paper(ax, "Jesu li troškovi problem? Prinos uz 1x, 2x i 3x trošak")
    y = np.arange(len(df))
    for i, (k, r) in enumerate(df.iterrows()):
        ax.plot([r["r3"] * 100, r["ret"] * 100], [i, i], color=PENCIL, lw=2.2, alpha=0.7)
    ax.scatter(df["ret"] * 100, y, s=80, color=INK, label="trošak 1x (2,5 bps po strani)", zorder=5)
    ax.scatter(df["r2"] * 100, y, s=60, color=ORANGE, label="trošak 2x", zorder=5)
    ax.scatter(df["r3"] * 100, y, s=60, color=RED, label="trošak 3x", zorder=5)
    ax.set_yticks(y, df["name"])
    ax.axvline(0, color=PENCIL, lw=1.2)
    ax.set_xlabel("prinos 2023.-2026. u %")
    ax.legend(loc="upper left", fontsize=10, frameon=True, facecolor=PAPER, edgecolor=GRID)
    k1 = df.loc["K1_C13C_ORIG"]
    k7 = df.loc["K7_C13C_PLUS_TREND_REENTRY"]
    diff1 = 1000 * (k1["ret"] - k1["r3"])
    diff7 = 1000 * (k7["ret"] - k7["r3"])
    note(ax, f"C13C (K1): 1x {hr(k1['ret'] * 100, 1)} %, 3x {hr(k1['r3'] * 100, 1)} %.\nNa 1.000 € trostruki trošak odnese tek {eur(diff1)}.", (k1["r3"] * 100, list(df.index).index("K1_C13C_ORIG")), (0.42, 0.67), RED, rad=0.0, size=10.5)
    note(ax, f"K7 trguje najčešće (199 poslova): trostruki\ntrošak odnosi {eur(diff7)} na 1.000 €. I dalje malo.", (k7["r3"] * 100, list(df.index).index("K7_C13C_PLUS_TREND_REENTRY")), (0.42, 0.36), RED, rad=0.0, size=10.5)
    ax.text(0.98, 0.05, "Mimo simulacije: minimalna provizija brokera\n(nepotvrđeno) bila bi veća za pravila s mnogo poslova.", transform=ax.transAxes, ha="right", fontsize=10, color=GREY)
    teacher(fig, "Točkice su skoro na istom mjestu: u ovom segmentu troškovi nisu razlog zašto pravila zaostaju. Mogući razlog zaostajanja (nije testirano): izlazi koji propuštaju skokove, vidi graf 7.")
    return save(fig, out, "chart_06_troskovi.png"), {"d1": diff1, "d7": diff7}


# --------------------------------------------------------------------------- chart 7 (key lesson)
def best_days(d: dict[str, Any]) -> dict[str, dict[str, float]]:
    out = {}
    for t in d["tickers"]:
        c = d["prices"][t]["close"].loc["2023-01-03":END]
        r = c.pct_change().dropna()
        tot = c.iloc[-1] / c.iloc[0] - 1
        rest = r.drop(r.nlargest(10).index)
        pj = d["profile"]["tickers"][t]["ai_2023plus"]["top10_days"]
        out[t] = {"total": float(tot), "without": float((1 + rest).prod() - 1), "top": float(r.max()), "top_date": str(r.idxmax().date()), "profile_total": float(pj["total_return"]), "profile_wo": float(pj["total_return_without_top10"]), "share": float(pj["share_of_total_log_return"])}
    return out


def chart_lesson(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    bd = best_days(d)
    ts = d["tickers"]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.subplots_adjust(bottom=0.17, top=0.9, left=0.075, right=0.98)
    paper(ax, "Ključna pouka: nekoliko dana nosi sve")
    x = np.arange(len(ts))
    w = 0.36
    a = [bd[t]["profile_total"] * 100 for t in ts]
    b = [bd[t]["profile_wo"] * 100 for t in ts]
    ax.bar(x - w / 2, a, w, color=INK, alpha=0.85, edgecolor=PENCIL, label="svih 942 dana (zbroj dnevnih prinosa)")
    ax.bar(x + w / 2, b, w, color=RED, alpha=0.8, edgecolor=PENCIL, label="bez 10 najboljih dana")
    for i in range(len(ts)):
        ax.text(x[i] - w / 2, max(a[i], 0) + 8, hr(a[i], 0) + " %", ha="center", fontsize=10)
        ax.text(x[i] + w / 2, (b[i] + 8) if b[i] >= 0 else (b[i] - 22), hr(b[i], 0) + " %", ha="center", fontsize=10)
    ax.set_xticks(x, ts, fontsize=12)
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_ylabel("prinos 2023.-2026. u %")
    ax.set_ylim(-110, 480)
    ax.legend(loc="upper left", fontsize=10, frameon=True, facecolor=PAPER, edgecolor=GRID)
    i_s = ts.index("SIMO")
    note(ax, f"SIMO: samo 10 od 942 dana (1 % dana) daju sav prinos.\nBez njih: {hr(b[i_s], 0)} %. Tko je baš tih dana bio\nvani, od 1.000 € ne bi dobio ništa.", (x[i_s] + w / 2, b[i_s]), (0.40, 0.92), RED, rad=-0.1, size=10.5)
    i_n = ts.index("NTAP")
    note(ax, f"NTAP je izuzetak: i bez njih +{hr(b[i_n], 0)} %.", (x[i_n] + w / 2, b[i_n] + 22), (0.62, 0.76), PENCIL, rad=0.0, size=10.5)
    teacher(fig, "Algoritmi koji često izlaze iz dionice (C13C) lako promaše tih 10 dana (često su baš tada u gotovini). To je mogući razlog zaostajanja za držanjem; nije posebno testirano.")
    return save(fig, out, "chart_07_najbolji_dani.png"), {"bd": bd}


# --------------------------------------------------------------------------- behaviour charts
def chart_dip(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    st = d["stats"]
    ts = d["tickers"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 6.0), sharey=False)
    fig.subplots_adjust(bottom=0.2, top=0.88, left=0.07, right=0.98, wspace=0.18)
    info: dict[str, Any] = {}
    for ax, h, title in ((a, "5", "Prosjek nakon 5 dana (%)"), (b, "20", "Prosjek nakon 20 dana (%)")):
        paper(ax, title)
        x = np.arange(len(ts))
        dip = [st.loc[t, f"drop5_fwd{h}_mean"] * 100 for t in ts]
        un = [st.loc[t, f"drop5_fwd{h}_uncond_mean"] * 100 for t in ts]
        ax.bar(x - 0.19, dip, 0.38, color=INK, alpha=0.85, edgecolor=PENCIL, label="nakon pada od 5 % u 5 dana")
        ax.bar(x + 0.19, un, 0.38, color=GREY, alpha=0.6, edgecolor=PENCIL, label="bilo koji dan")
        for i, t in enumerate(ts):
            ax.text(x[i] - 0.19, dip[i] + (0.12 if dip[i] >= 0 else -0.12), hr(dip[i], 1), ha="center", va="bottom" if dip[i] >= 0 else "top", fontsize=9)
        ax.set_xticks(x, [f"{t}\n(n={int(st.loc[t, 'drop5_n_indep'])})" for t in ts])
        ax.axhline(0, color=PENCIL, lw=1.1)
        ax.margins(y=0.2)
        info[h] = {t: (float(dip[i]), float(un[i])) for i, t in enumerate(ts)}
    b.legend(loc="upper left", fontsize=9, frameon=True, facecolor=PAPER, edgecolor=GRID)
    s = st.loc["SIMO"]
    m = st.loc["MRAM"]
    note(a, f"SIMO: 1.000 € kupljeno nakon takvog pada\nu prosjeku daje {eur(1000 * s['drop5_fwd5_mean'])} za 5 dana,\nbilo koji dan samo {eur(1000 * s['drop5_fwd5_uncond_mean'])}.", (1 - 0.19 + 0.0, s["drop5_fwd5_mean"] * 100 - 0.3), (0.42, 0.88), INK, rad=0.0, size=10)
    note(a, f"MRAM: pad se nastavlja ({hr(m['drop5_fwd5_mean'] * 100, 1)} %).\nOvdje 'kupi pad' ne radi.", (2.0, m["drop5_fwd5_mean"] * 100 / 2), (0.58, 0.30), RED, rad=0.0, size=10)
    teacher(fig, "Događaj = pad od bar 5 % u 5 dana dok je cijena iznad prosjeka 200 dana; n = broj neovisnih događaja (bar 10 dana razmaknutih). Mali n znači slab dokaz. Prosjek ne garantira da će sljedeći pad završiti isto.")
    return save(fig, out, "chart_08_nakon_pada.png"), info


def month_matrix(d: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    avg, cnt = {}, {}
    for t in d["tickers"]:
        c = d["prices"][t]["close"].loc["2022-12-01":END]
        m = c.resample("ME").last()
        r = m.pct_change().dropna().loc["2023-01-01":"2026-09-30"]  # drop the unfinished October month
        avg[t] = r.groupby(r.index.month).mean()
        cnt[t] = r.groupby(r.index.month).count()
    return pd.DataFrame(avg).T, pd.DataFrame(cnt).T


def chart_season(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    mm, cc = month_matrix(d)
    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(bottom=0.3, top=0.88, left=0.075, right=0.98)
    paper(ax, "Sezonalnost: prosječni prinos po mjesecu (2023.-2026.)")
    ax.grid(False)
    vals = mm.values * 100
    ax.imshow(vals, cmap="RdYlGn", vmin=-25, vmax=25, aspect="auto")
    mon = ["sij", "velj", "ožu", "tra", "svi", "lip", "srp", "kol", "ruj", "lis", "stu", "pro"]
    ax.set_xticks(range(12), mon)
    ax.set_yticks(range(len(mm)), list(mm.index), fontsize=12)
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            ax.text(j, i, hr(vals[i, j], 0), ha="center", va="center", fontsize=10.5, color="black")
    i, j = np.unravel_index(np.nanargmax(vals), vals.shape)
    ring(ax, j, i, RED, 1300)
    t = mm.index[i]
    note(ax, f"Najjači: {t} u mjesecu '{mon[j]}': prosjek {hr(vals[i, j], 1, True)} %,\nali samo iz {int(cc.iloc[i, j])} godina. Na 1.000 € to je {eur(10 * vals[i, j])} u prosjeku.",
         (j, i), (0.02, -0.17), RED, rad=0.2, size=10.5)
    teacher(fig, "Svaka kućica je prosjek samo 3 do 4 godine (2023., 2024., 2025., a 2026. do rujna). To je premalo za pravilo; pokazuje samo što se dogodilo, ne što će se dogoditi.")
    return save(fig, out, "chart_09_sezonalnost.png"), {"mm": mm, "cc": cc}


def chart_anatomy(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    ts = d["tickers"]
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.4))
    fig.subplots_adjust(bottom=0.1, top=0.93, left=0.075, right=0.98, hspace=0.42, wspace=0.18)
    info: dict[str, Any] = {}
    for ax, t in zip(axes.ravel(), ts):
        c = d["prices"][t]["close"].loc["2023-01-03":END]
        u = (c / c.cummax() - 1) * 100
        paper(ax, f"{t}: koliko je dionica pala od vrha")
        ax.fill_between(u.index, u.values, 0, color=INK, alpha=0.18)
        sketch(ax.plot(u.index, u.values, color=INK, lw=1.3)[0], 0.5, 60, 3)
        ep = drawdowns(c, 1)[0]
        pk, tr_, rec = pd.Timestamp(ep["start"]), pd.Timestamp(ep["bottom"]), ep.get("recovery")
        p0, p1 = float(c.loc[pk]), float(c.loc[tr_])
        info[t] = {"peak": str(pk.date()), "bottom": str(tr_.date()), "recovery": (str(pd.Timestamp(rec).date()) if rec is not None else None), "p0": p0, "p1": p1, "dd": p1 / p0 - 1}
        ring(ax, tr_, (p1 / p0 - 1) * 100, RED, 500)
        rtxt = f"oporavak {day(pd.Timestamp(rec))}" if rec is not None else "do 5. 10. 2026. nije oporavljen"
        note(ax, f"vrh {day(pk)}: {hr(p0, 2)} $\ndno {day(tr_)}: {hr(p1, 2)} $\n{pc(p1 / p0 - 1, 1)}; {rtxt}.\n1.000 € na vrhu: {eur(1000 * p1 / p0)} na dnu.",
             (tr_, (p1 / p0 - 1) * 100), (0.03, 0.15), RED, rad=0.2, size=9.5)
        ax.set_ylim(min(u.min() * 1.9, -60), 6)
        ax.set_ylabel("pad od vrha u %")
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%y"))
    teacher(fig, "Svaka krivulja ide od 0 (novi vrh) prema dolje. Što je dublja i duža, to dulje morate čekati da se 1.000 € vrati na stari iznos.")
    return save(fig, out, "chart_10_anatomija_pada.png"), info


def sr_examples(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Support events from 2025 on with the pivot, touch and outcome (same definition as profile_stats)."""
    c, lo, hi = df["close"].to_numpy(), df["low"].to_numpy(), df["high"].to_numpy()
    n = len(c)
    plows, _ = pivots(lo, hi)
    ev = []
    for p in plows:
        lvl = lo[p]
        for t in range(p + PIVOT_K + 1, min(n - SR_LOOKAHEAD - 1, p + SR_MAX_AGE)):
            if c[t] < lvl * (1 - SR_BAND):
                break
            if lo[t] <= lvl * (1 + SR_BAND) and c[t - 1] > lvl * (1 + SR_BAND):
                fut = c[t: t + SR_LOOKAHEAD + 1]
                ev.append({"p": p, "t": t, "lvl": float(lvl), "broke": bool((fut < lvl * (1 - SR_BAND)).any())})
                break
    return [e for e in ev if df.index[e["t"]] >= pd.Timestamp("2025-01-01")]


def chart_sr(d: dict[str, Any], out: Path) -> tuple[str, dict[str, Any]]:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.9))
    fig.subplots_adjust(bottom=0.2, top=0.88, left=0.07, right=0.98, wspace=0.18)
    info: dict[str, Any] = {}
    for ax, (t, want_broke) in zip(axes, (("NTAP", False), ("RMBS", True))):
        df = d["prices"][t]
        ev = [e for e in sr_examples(df) if e["broke"] == want_broke]
        e = ev[-1] if ev else None
        paper(ax, f"{t}: potpora koja {'nije izdržala' if want_broke else 'je izdržala'}")
        if e is None:
            continue
        i0, it = e["p"], e["t"]
        a, b = max(i0 - 12, 0), min(it + 14, len(df) - 1)
        x = df.iloc[a:b + 1]
        sketch(ax.plot(x.index, x["close"], color=INK, lw=1.6)[0], 0.5, 60, 3)
        ax.vlines(x.index, x["low"], x["high"], color=GREY, lw=0.8, alpha=0.6)
        lvl = e["lvl"]
        ax.hlines(lvl, df.index[i0], x.index[-1], color=GREEN if not want_broke else RED, lw=2, ls="--")
        ax.scatter([df.index[i0]], [lvl], s=60, color=PENCIL, zorder=6)
        ax.scatter([df.index[it]], [df["low"].iloc[it]], s=800, facecolors="none", edgecolors=RED, linewidths=2, zorder=7)
        end5 = df.index[min(it + SR_LOOKAHEAD, len(df) - 1)]
        c0, c5 = float(df["close"].iloc[it]), float(df["close"].iloc[min(it + SR_LOOKAHEAD, len(df) - 1)])
        cmin = float(df["close"].iloc[it: it + SR_LOOKAHEAD + 1].min())
        info[t] = {"pivot": str(df.index[i0].date()), "level": lvl, "touch": str(df.index[it].date()), "broke": want_broke, "c0": c0, "c5": c5, "cmin": cmin, "end5": str(end5.date())}
        ax.set_ylim(x["low"].min() * 0.96, x["high"].max() * 1.04)
        note(ax, f"1) dno {day(df.index[i0])}: {hr(lvl, 2)} $ = razina potpore", (df.index[i0], lvl), (0.05, 0.08), PENCIL, rad=0.2, size=9.5)
        verdict = (f"najniže zatvaranje u 5 dana {hr(cmin, 2)} $\nje više od 1,5 % ispod razine: PROBIJENA" if want_broke
                   else f"najniže zatvaranje u 5 dana {hr(cmin, 2)} $\nnije probilo razinu za 1,5 %: DRŽI")
        note(ax, f"2) dodir {day(df.index[it])} (cijena {hr(c0, 2)} $)\n3) {verdict}", (df.index[it], float(df["low"].iloc[it])), (0.30 if want_broke else 0.04, 0.86), RED, rad=0.0, size=9.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
        ax.tick_params(axis="x", labelrotation=30)
        ax.set_ylabel("cijena u USD")
    p = d["stats"]
    teacher(fig, f"Potpora = razina gdje je cijena već jednom stala padati. Kroz AI eru držala je: RMBS {pc(p.loc['RMBS', 'support_hold_share'], 0)}, SIMO {pc(p.loc['SIMO', 'support_hold_share'], 0)}, MRAM {pc(p.loc['MRAM', 'support_hold_share'], 0)}, NTAP {pc(p.loc['NTAP', 'support_hold_share'], 0)} dodira.")
    return save(fig, out, "chart_11_potpora.png"), info


def make_all(segment: str, picks: list[str]) -> dict[str, Any]:
    d = load_inputs(segment)
    out = d["dir"]
    res: dict[str, Any] = {}
    res["c1"] = chart_prices(d, out, picks)
    res["c2"] = chart_equity(d, out)
    res["c3"] = chart_drawdown(d, out, res["c2"][1])
    res["c4"] = chart_trades(d, out)
    res["c5"] = chart_scoreboard(d, out)
    res["c6"] = chart_costs(d, out)
    res["c7"] = chart_lesson(d, out)
    res["c8"] = chart_dip(d, out)
    res["c9"] = chart_season(d, out)
    res["c10"] = chart_anatomy(d, out)
    res["c11"] = chart_sr(d, out)
    info = {k: v[1] for k, v in res.items()}

    def enc(o: Any) -> Any:
        if hasattr(o, "item"):
            return o.item()
        if hasattr(o, "to_dict"):
            return o.to_dict()
        return str(o)

    (out / "chart_info.json").write_text(json.dumps(info, default=enc, ensure_ascii=False, indent=1))
    return {k: v[0] for k, v in res.items()}


if __name__ == "__main__":
    seg = sys.argv[1] if len(sys.argv) > 1 else "mem_interface_storage"
    print(make_all(seg, ["RMBS", "SIMO", "NTAP"]))
