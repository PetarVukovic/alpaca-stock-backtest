"""Notebook-style PNG charts for the AI-chain segment "cloud" (Croatian labels, real results only).

Reads reports/research/AICHAIN_20261014/{results/*.json, segments/cloud/*.json} and data/ohlcv/*_1d.csv.
Writes 11 PNGs next to analysis.json. Read-only on data; never places orders.

Usage:
    .venv/bin/python -m lab.aichain.cloud_charts
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lab.aichain.profile_stats import SR_BAND, SR_MAX_AGE, pivots
from lab.top10.charts import (
    GREEN,
    GRID,
    INK,
    PAPER,
    PENCIL,
    RED,
    paper,
    ring,
    sketch,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SEG = BASE / "segments" / "cloud"
AI_START = pd.Timestamp("2023-01-01")
TICKERS = ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "NBIS", "VRT"]
COLORS = {
    "MSFT": "#1d3fb8",
    "AMZN": "#d98a00",
    "GOOGL": "#17803d",
    "META": "#7a3fb0",
    "ORCL": "#c2321f",
    "NBIS": "#0f8a8a",
    "VRT": "#3b3b42",
}
HOLD, K1, K5B = "B0_BUYHOLD", "K1_C13C_ORIG", "K5B_SR_BREAKOUT_RETEST"
NAMES = {
    "B0_BUYHOLD": "kupi i drži",
    "K1_C13C_ORIG": "K1 C13C (Petrov)",
    "K2_SMA200_TREND": "K2 trend SMA200",
    "K3_DONCHIAN_55_20": "K3 proboj 55/20",
    "K4_TSMOM_126": "K4 zamah 126 dana",
    "K5_SUPPORT_RESISTANCE": "K5 potpora/otpor",
    "K5B_SR_BREAKOUT_RETEST": "K5B proboj i povratak",
    "K6_MOMENTUM_CS": "K6 rotacija",
    "K7_C13C_PLUS_TREND_REENTRY": "K7 C13C + ponovni ulaz",
}
HAND = ["Noteworthy", "Bradley Hand", "Comic Sans MS", "DejaVu Sans"]
plt.rcParams.update({"font.family": HAND, "font.size": 11})


def eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def hr_pct(x: float, digits: int = 0, sign: bool = False) -> str:
    s = f"{x * 100:+.{digits}f}" if sign else f"{x * 100:.{digits}f}"
    return s.replace(".", ",") + " %"


def usd(x: float) -> str:
    # "USD" instead of a dollar sign: matplotlib treats paired dollar signs as math text
    return f"{x:,.2f} USD".replace(",", "X").replace(".", ",").replace("X", ".")


def dmy(d: Any) -> str:
    t = pd.Timestamp(d)
    return f"{t.day}. {t.month}. {t.year}."


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_px(ticker: str) -> pd.DataFrame:
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv")
    d["date"] = pd.to_datetime(d["date"].astype(str).str[:10])
    d = d.drop_duplicates("date").sort_values("date").set_index("date")
    return d[["open", "high", "low", "close"]].astype(float)


def series(pairs: list[list[Any]]) -> pd.Series:
    return pd.Series(
        [p[1] for p in pairs], index=pd.to_datetime([p[0] for p in pairs]), dtype=float
    )


def drawdown(eq: pd.Series) -> pd.Series:
    return eq / eq.cummax() - 1


def anno(
    ax: Any,
    text: str,
    xy: tuple[Any, float],
    off: tuple[float, float],
    color: str = PENCIL,
    rad: float = 0.25,
    size: float = 11,
    ha: str = "left",
    frac: bool = False,
) -> None:
    """Handwritten note with a pencil arrow; `off` is points from the data point, or axes fraction if frac."""
    is_date = isinstance(xy[0], (str, pd.Timestamp, np.datetime64))
    xy_num = (pd.Timestamp(xy[0]) if is_date else xy[0], xy[1])
    ann = ax.annotate(
        text,
        xy=xy_num,
        xycoords="data",
        xytext=off,
        textcoords="axes fraction" if frac else "offset points",
        ha=ha,
        va="center",
        fontsize=size,
        color=color,
        arrowprops=dict(arrowstyle="->", color=color, lw=1.5, connectionstyle=f"arc3,rad={rad}", shrinkB=4),
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.85),
        zorder=8,
    )
    if ann.arrow_patch is not None:
        sketch(ann.arrow_patch, 0.9, 60, 3)


def teach(fig: Any, text: str, y: float = 0.012) -> None:
    fig.text(0.012, y, "Bilješka učitelja: " + text, fontsize=11.5, color=RED, ha="left", va="bottom", wrap=True)


def era_line(ax: Any, x: str = "2023-01-01", label: bool = True, ypos: float = 0.04) -> None:
    ax.axvline(pd.Timestamp(x), color=RED, ls="--", lw=1.3)
    if label:
        ax.text(
            pd.Timestamp(x) + pd.Timedelta(days=12),
            ypos,
            "od ovdje: AI era",
            transform=ax.get_xaxis_transform(),
            fontsize=10,
            color=RED,
        )


def save(fig: Any, name: str) -> str:
    SEG.mkdir(parents=True, exist_ok=True)
    fig.savefig(SEG / name, dpi=105, facecolor=PAPER)
    plt.close(fig)
    return name


class Data:
    """All real inputs of the cloud segment, loaded once."""

    def __init__(self) -> None:
        self.analysis = load_json(SEG / "analysis.json")
        self.profile = load_json(SEG / "profile.json")
        self.seg = load_json(BASE / "results" / "cloud.json")
        self.res = {t: load_json(BASE / "results" / f"{t}.json") for t in TICKERS}
        self.px = {t: load_px(t) for t in TICKERS}
        self.n = len(TICKERS)
        self.table = {r["suparnik"]: r for r in self.analysis["tablica_segment"]}

    def seg_eq(self, cid: str) -> pd.Series:
        """Segment equity of the AI era, rescaled to 1.000 EUR per ticker (segment value / 7)."""
        return series(self.seg["contenders"][cid]["equity"]["ai_era"]) / self.n

    def trades(self, ticker: str, cid: str) -> list[dict[str, Any]]:
        return self.res[ticker]["contenders"][cid]["trades"]["ai_era"]

    def seg_trades(self, cid: str) -> list[dict[str, Any]]:
        return self.seg["contenders"][cid]["trades"]["ai_era"]

    def ai(self, ticker: str) -> dict[str, Any]:
        return self.profile["tickers"][ticker]["windows"]["ai"]


# --------------------------------------------------------------------------------------------
# 1) price + SMA200 + C13C entries/exits, with one stop line and one dip example
# --------------------------------------------------------------------------------------------
def chart_prices(d: Data) -> str:
    picks = ["VRT", "ORCL", "MSFT"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 14.2))
    fig.subplots_adjust(top=0.96, bottom=0.12, hspace=0.42, left=0.08, right=0.97)
    start = pd.Timestamp("2022-07-01")
    facts: dict[str, Any] = {}
    for ax, tk in zip(axes, picks):
        px = d.px[tk]
        sma = px["close"].rolling(200).mean()
        cl = px["close"].loc[start:]
        paper(ax, f"{tk}: cijena, prosjek 200 dana i svaka kupnja i prodaja pravila C13C")
        ax.title.set_fontsize(13)
        ax.plot(cl.index, cl, color=INK, lw=1.4, label="cijena zatvaranja")
        ax.plot(sma.loc[start:].index, sma.loc[start:], color="#8a8f99", lw=1.5, ls="--", label="prosjek 200 dana (SMA200)")
        era_line(ax)
        tr = d.trades(tk, K1)
        for t in tr:
            ed, xd = pd.Timestamp(t["entry_date"]), pd.Timestamp(t["exit_date"])
            ax.scatter([ed], [t["raw_entry"]], marker="^", s=70, color=GREEN, zorder=6, edgecolors="white", linewidths=0.6)
            col = RED if t["reason"] == "stop" else "#8a8f99"
            ax.scatter([xd], [t["raw_exit"]], marker="v", s=70, color=col, zorder=6, edgecolors="white", linewidths=0.6)
        ax.scatter([], [], marker="^", color=GREEN, label=f"kupnja ({len(tr)} poslova)")
        ax.scatter([], [], marker="v", color=RED, label="izlaz po stopu")
        ax.legend(loc="upper left", frameon=False, fontsize=9.5, ncol=2)
        ax.set_ylabel("cijena u dolarima")
        facts[tk] = len(tr)

    # MSFT: dip example + trailing stop line for the trade 2025-11-05 .. 2026-01-14
    ax = axes[2]
    px = d.px["MSFT"]
    tr = [t for t in d.trades("MSFT", K1) if t["entry_date"] == "2025-11-05"][0]
    ed, xd = pd.Timestamp(tr["entry_date"]), pd.Timestamp(tr["exit_date"])
    i_entry = px.index.get_loc(ed)
    sig = px.index[i_entry - 1]
    chg = px["close"].iloc[i_entry - 1] / px["close"].iloc[i_entry - 6] - 1
    sma_sig = px["close"].rolling(200).mean().iloc[i_entry - 1]
    assert chg <= -0.05 and px["close"].iloc[i_entry - 1] > sma_sig, "dip signal check failed"
    seg = px.loc[ed:xd]
    peak = seg["high"].shift(1).cummax().fillna(seg["high"].iloc[0])
    stop = (peak * 0.9).round(2)
    stop.iloc[0] = np.nan
    ax.plot(stop.index, stop, color=RED, lw=2.0, drawstyle="steps-post", label="stop (10 % ispod vrha)")
    ax.legend(loc="upper left", frameon=False, fontsize=9.5, ncol=2)
    anno(
        ax,
        f"{dmy(sig)}: pad {hr_pct(chg)} u 5 dana, a cijena je\nsvejedno iznad prosjeka 200 dana = signal.\nKupnja idući dan po {usd(tr['raw_entry'])}",
        (ed, tr["raw_entry"]),
        (-250, -110),
        color=GREEN,
        rad=0.3,
        size=10.5,
    )
    anno(
        ax,
        f"{dmy(xd)}: cijena je pala na stop\n{usd(tr['raw_exit'])}, gubitak {hr_pct(tr['return'], 1)}\n(na 1.000 € to je {eur(abs(tr['return']) * 1000)}). Prodano.",
        (xd, tr["raw_exit"]),
        (-60, -105),
        color=RED,
        rad=-0.3,
        size=10.5,
    )

    # VRT: one stop example vs the gap
    ax = axes[0]
    vtr = d.trades("VRT", K1)
    big = max(vtr, key=lambda t: t["return"])
    anno(
        ax,
        f"najbolji posao: kupnja {dmy(big['entry_date'])} po {usd(big['raw_entry'])},\nizlaz {dmy(big['exit_date'])} po {usd(big['raw_exit'])}:\n{hr_pct(big['return'], 0, True)}, na 1.000 € to je {eur(1000 * big['return'])} dobiti",
        (pd.Timestamp(big["exit_date"]), big["raw_exit"]),
        (0.12, 0.62),
        color=GREEN,
        rad=0.2,
        frac=True,
        size=10.5,
    )
    # ORCL: peak and fall
    ax = axes[1]
    o = d.px["ORCL"]["close"]
    pk = o.loc["2025-09-01":"2025-09-30"].idxmax()
    lo = o.loc[pk:].idxmin()
    anno(
        ax,
        f"vrh {dmy(pk)} {usd(o[pk])}, dno {dmy(lo)} {usd(o[lo])}:\npad {hr_pct(o[lo] / o[pk] - 1)}. Od 1.000 € ostane {eur(1000 * o[lo] / o[pk])}",
        (lo, o[lo]),
        (-380, -30),
        color=RED,
        rad=-0.2,
        size=10.5,
    )
    for ax in axes:
        ax.set_xlim(start, pd.Timestamp("2026-10-20"))
    teach(
        fig,
        "zeleni trokut gore = kupnja (pravilo kupuje kad cijena padne 5 % u 5 dana, a ipak je iznad dugog prosjeka). "
        "Crveni trokut dolje = prodaja jer je cijena pala 10 % od najvišeg vrha. Sivi isprekidani pravac je prosjek "
        "zadnjih 200 dana: ispod njega pravilo ne kupuje. Primjer: kupiš za 1.000 €, a stop te izbaci 10 % ispod vrha, "
        "pa izgubiš oko 100 € umjesto da gledaš dalje pad.",
        y=0.008,
    )
    return save(fig, "01_cijene.png")


# --------------------------------------------------------------------------------------------
# 2) equity of 1.000 EUR
# --------------------------------------------------------------------------------------------
def chart_equity(d: Data) -> str:
    hold, k1, k5b = d.seg_eq(HOLD), d.seg_eq(K1), d.seg_eq(K5B)
    fig, ax = plt.subplots(figsize=(11, 6.6))
    fig.subplots_adjust(bottom=0.2, left=0.09, right=0.97, top=0.9)
    paper(ax, "Što se dogodi s 1.000 € po tvrtki (prosjek sedam)")
    for s, c, lab, lw in (
        (hold, "#6b7280", "kupi i drži", 2.0),
        (k1, INK, "K1 C13C (Petrov algoritam)", 1.8),
        (k5b, GREEN, "K5B proboj i povratak (pobjednik)", 2.0),
    ):
        sketch(ax.plot(s.index, s, color=c, lw=lw, label=lab)[0], 0.6, 60, 4)
    ax.legend(loc="upper left", frameon=False, fontsize=10.5)
    ax.set_ylabel("vrijednost u eurima")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    era_line(ax, "2023-01-03", ypos=0.3)
    ax.set_xlim(pd.Timestamp("2022-12-01"), pd.Timestamp("2026-12-15"))

    w = d.analysis["pobjednik"]["najgori_pad_drzanje"]
    a, b = pd.Timestamp(w["vrh"]), pd.Timestamp(w["dno"])
    ax.axvspan(a, b, color="#fbe1dc", alpha=0.7, lw=0)
    hv0, hv1, kv0, kv1 = hold[a], hold[b], k5b[a], k5b[b]
    anno(
        ax,
        f"Najgori pad držanja ({dmy(a)} do {dmy(b)}):\nkupi-i-drži {eur(hv0)} → {eur(hv1)} ({hr_pct(hv1 / hv0 - 1)}),\nK5B za isto vrijeme {eur(kv0)} → {eur(kv1)} ({hr_pct(kv1 / kv0 - 1)}).\nOd početnih 1.000 € pravilo je tu uštedjelo {eur(kv1 - kv0 - (hv1 - hv0))}.",
        (b, hv1),
        (0.10, 0.62),
        color=RED,
        rad=0.3,
        size=10,
        frac=True,
    )
    anno(ax, f"kupi i drži: {eur(hold.iloc[-1])}", (hold.index[-1], hold.iloc[-1]), (-185, -22), color="#6b7280", size=11, rad=0.2)
    anno(ax, f"K5B: {eur(k5b.iloc[-1])}", (k5b.index[-1], k5b.iloc[-1]), (-100, 60), color=GREEN, size=11, rad=-0.2)
    anno(ax, f"K1: {eur(k1.iloc[-1])}", (k1.index[-1], k1.iloc[-1]), (-95, -75), color=INK, size=11, rad=0.2)
    teach(
        fig,
        f"Sve linije kreću od 1.000 € dana 3. 1. 2023. Pravila su ponekad u gotovini (ne drže dionicu), pa gube manje u padu, "
        f"ali i propuste dio rasta. Ovdje nitko nije dostigao držanje: {eur(hold.iloc[-1])} naspram {eur(k5b.iloc[-1])}. "
        "Troškovi trgovanja su uračunati.",
    )
    return save(fig, "02_ulaganje.png")


# --------------------------------------------------------------------------------------------
# 3) drawdown comparison
# --------------------------------------------------------------------------------------------
def chart_drawdown(d: Data) -> str:
    fig, ax = plt.subplots(figsize=(11, 6.4))
    fig.subplots_adjust(bottom=0.2, left=0.09, right=0.97, top=0.9)
    paper(ax, "Najveći pad od vrha, usporedba")
    eqs = {HOLD: d.seg_eq(HOLD), K1: d.seg_eq(K1), K5B: d.seg_eq(K5B)}
    dd = {k: drawdown(v) * 100 for k, v in eqs.items()}
    for k, c, lab in ((HOLD, "#6b7280", "kupi i drži"), (K1, INK, "K1 C13C"), (K5B, GREEN, "K5B (pobjednik)")):
        ax.fill_between(dd[k].index, dd[k], 0, color=c, alpha=0.12, lw=0)
        sketch(ax.plot(dd[k].index, dd[k], color=c, lw=1.8, label=lab)[0], 0.6, 60, 4)
    ax.legend(loc="lower left", frameon=False, fontsize=10.5, bbox_to_anchor=(0.0, 0.0))
    ax.set_ylabel("pad od dotadašnjeg vrha (%)")
    era_line(ax, "2023-01-03", ypos=0.55)
    ax.set_xlim(pd.Timestamp("2022-12-01"), pd.Timestamp("2026-12-15"))
    w = d.analysis["pobjednik"]["najgori_pad_drzanje"]
    bot = pd.Timestamp(w["dno"])
    peak_val = eqs[HOLD].loc[pd.Timestamp(w["vrh"])]
    bot_val = eqs[HOLD].loc[bot]
    assert abs((bot_val / peak_val - 1) - w["pad"]) < 0.01
    ring(ax, bot, dd[HOLD][bot], color=RED, size=700)
    anno(
        ax,
        f"Najgori dan držanja: {dmy(bot)}, pad {hr_pct(w['pad'], 1)}.\nOd {eur(peak_val)} (vrh {dmy(w['vrh'])}) ostane {eur(bot_val)}.\nNa svakih 1.000 € koje si imao na vrhu\nto je {eur(w['gubitak_na_papiru_eur_po_1000_na_vrhu'])} manje na papiru.",
        (bot, dd[HOLD][bot]),
        (0.10, 0.30),
        color=RED,
        rad=0.2,
        size=10.5,
        frac=True,
    )
    pw = d.analysis["pobjednik"]["najgori_pad_pobjednik"]
    pb = pd.Timestamp(pw["dno"])
    anno(
        ax,
        f"K5B u svom najgorem: {dmy(pb)}, {hr_pct(pw['pad'], 1)}\n(oko {eur(pw['gubitak_na_papiru_eur_po_1000_na_vrhu'])} na 1.000 €)",
        (pb, dd[K5B][pb]),
        (50, 70),
        color=GREEN,
        rad=0.3,
        size=10.5,
    )
    teach(
        fig,
        "pad od vrha pita: koliko bi mi manje vrijedilo u najgorem trenutku nego u najboljem prije toga? "
        "Primjer: imaš 1.000 €, naraste na 1.200 €, pa padne na 900 €. Pad je 25 % (300 € od 1.200 €), "
        "iako si i dalje malo ispod ulaganja. Brojke su iz simulacije, a ne obećanje.",
    )
    return save(fig, "03_pad.png")


# --------------------------------------------------------------------------------------------
# 4) trade scatter K1
# --------------------------------------------------------------------------------------------
def chart_trades(d: Data) -> str:
    tr = d.seg_trades(K1)
    df = pd.DataFrame(tr)
    fig, ax = plt.subplots(figsize=(11, 6.8))
    fig.subplots_adjust(bottom=0.22, left=0.09, right=0.97, top=0.9)
    paper(ax, f"Svih {len(df)} poslova pravila C13C: koliko dana i s kojim ishodom")
    for tk in TICKERS:
        s = df[df["ticker"] == tk]
        ax.scatter(s["bars_held"], s["return"] * 100, s=46, color=COLORS[tk], alpha=0.8, label=f"{tk} ({len(s)})", edgecolors="white", linewidths=0.5)
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_xlabel("koliko trgovačkih dana je pozicija bila otvorena")
    ax.set_ylabel("ishod posla (%)")
    ax.legend(loc="upper right", frameon=False, fontsize=9.5, ncol=2)
    best = df.loc[df["return"].idxmax()]
    worst = df.loc[df["return"].idxmin()]
    win = (df["return"] > 0).mean()
    anno(
        ax,
        f"najbolji: {best['ticker']}, {dmy(best['entry_date'])} do {dmy(best['exit_date'])},\n{hr_pct(best['return'], 0, True)} u {int(best['bars_held'])} dana\n(1.000 € → {eur(1000 * (1 + best['return']))})",
        (best["bars_held"], best["return"] * 100),
        (-260, -45),
        color=GREEN,
        rad=0.3,
        size=10.5,
    )
    anno(
        ax,
        f"najgori: {worst['ticker']}, {dmy(worst['entry_date'])} do {dmy(worst['exit_date'])},\n{hr_pct(worst['return'], 0, True)} u {int(worst['bars_held'])} dana\n(1.000 € → {eur(1000 * (1 + worst['return']))})" + ("; stop je preskočen jazom" if worst["detail"] == "gap_stop" else ""),
        (worst["bars_held"], worst["return"] * 100),
        (60, 70),
        color=RED,
        rad=-0.3,
        size=10.5,
    )
    ax.text(0.45, 0.9, f"dobitnih poslova: {win * 100:.0f} % od {len(df)}".replace(".", ","), transform=ax.transAxes, fontsize=11, color=INK)
    teach(
        fig,
        "svaka točka je jedan posao. Desno su dugi poslovi, gore dobici. Većina točaka je blizu nule ili malo ispod, "
        "a nekoliko ih je daleko gore: rezultat drže rijetki veliki dobici. Gubitak veći od 10 % znači da je dionica "
        "preko noći 'preskočila' stop (jaz): stop je zamišljen na 10 % ispod vrha, ali prodaja ide po prvoj cijeni koja se pojavi.",
    )
    return save(fig, "04_poslovi.png")


# --------------------------------------------------------------------------------------------
# 5) contender scoreboard
# --------------------------------------------------------------------------------------------
def chart_scoreboard(d: Data) -> str:
    order = [c for c in NAMES if c in d.table]
    rows = sorted(order, key=lambda c: d.table[c]["ukupni_prinos"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.6), sharey=True)
    fig.subplots_adjust(bottom=0.2, left=0.2, right=0.97, top=0.88, wspace=0.08)
    for ax, key, title, fmt in (
        (a1, "ukupni_prinos", "Prinos u AI eri (2023.–2026.)", lambda v: f"{v * 100:.0f} %"),
        (a2, "sharpe", "Sharpe (veći je bolji)", lambda v: f"{v:.2f}".replace(".", ",")),
    ):
        paper(ax, title)
        ax.title.set_fontsize(13)
        vals = [d.table[c][key] for c in rows]
        cols = ["#6b7280" if c == HOLD else (GREEN if c == K5B else INK) for c in rows]
        ax.barh([NAMES[c] for c in rows], vals, color=cols, alpha=0.85, height=0.62)
        for i, v in enumerate(vals):
            ax.text(v + max(vals) * 0.01, i, fmt(v), va="center", fontsize=10)
        ax.axvline(d.table[HOLD][key], color=RED, ls="--", lw=1.5)
        ax.set_xlim(0, max(vals) * 1.2)
        ax.grid(True, axis="y", alpha=0)
    h = d.table[HOLD]
    anno(
        a1,
        f"crtica = kupi i drži:\n{h['ukupni_prinos'] * 100:.0f} % (1.000 € → {eur(h['krajnja_vrijednost_eur_na_1000'])})",
        (h["ukupni_prinos"], rows.index(HOLD)),
        (0.42, 0.22),
        color=RED,
        rad=0.2,
        size=10.5,
        frac=True,
    )
    anno(
        a2,
        "Sharpe skoro isti kao kod držanja:\nrazlika u drugoj decimali nije dokaz",
        (d.table[K5B]["sharpe"], rows.index(K5B)),
        (0.30, 0.07),
        color=GREEN,
        rad=0.3,
        size=10.5,
        frac=True,
    )
    teach(
        fig,
        "svaki red je jedna 'ideja za trgovanje'. Crvena crta je držanje bez trgovanja. Nijedna ideja ne preskače crtu u prinosu. "
        "Sharpe govori koliko dobiti dobiješ po jedinici nemira: veći je bolji, a oko 1 je solidno. "
        "Pobjednika smo odredili unaprijed: najviši Sharpe uz bar 20 poslova.",
    )
    return save(fig, "05_ljestvica.png")


# --------------------------------------------------------------------------------------------
# 6) cost robustness
# --------------------------------------------------------------------------------------------
def chart_costs(d: Data) -> str:
    order = [c for c in NAMES if c in d.table]
    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    fig.subplots_adjust(bottom=0.27, left=0.09, right=0.97, top=0.9)
    paper(ax, "Što ako je trgovanje skuplje? Troškovi 1×, 2× i 3×")
    x = np.arange(len(order))
    w = 0.26
    for j, (key, lab, col) in enumerate(
        (("ukupni_prinos", "osnovni trošak (1×)", "#9db4d8"), ("prinos_uz_trosak_2x", "dvostruki (2×)", INK), ("prinos_uz_trosak_3x", "trostruki (3×)", RED))
    ):
        ax.bar(x + (j - 1) * w, [d.table[c][key] * 100 for c in order], w, color=col, alpha=0.85, label=lab)
    ax.set_xticks(x)
    ax.set_xticklabels([NAMES[c].replace(" ", "\n", 1) for c in order], fontsize=8.5)
    ax.set_ylabel("prinos u AI eri (%)")
    ax.legend(loc="upper right", frameon=False, fontsize=10)
    k1 = d.table[K1]
    i = order.index(K1)
    anno(
        ax,
        f"C13C ima {k1['poslova']} poslova: s 3× troškom\nspusti se sa {k1['ukupni_prinos'] * 100:.0f} % na {k1['prinos_uz_trosak_3x'] * 100:.0f} %".replace(".", ","),
        (i + w, k1["prinos_uz_trosak_3x"] * 100),
        (-30, 130),
        color=INK,
        rad=-0.3,
        size=10.5,
    )
    teach(
        fig,
        "svako trgovanje ima trošak (razlika kupovne i prodajne cijene, provizija). Osnovno je 2,5 bps po strani (bps = stoti dio postotka), "
        "pa 5 bps ukupno znači oko 0,50 € na 1.000 €. Stres-test množi trošak s 2 i 3. Rezultati ostaju gotovo isti jer ovdje "
        "nema tisuća poslova, a dionice su likvidne. To ne uključuje porez, tečaj eura ni IBKR minimalnu proviziju.",
    )
    return save(fig, "06_troskovi.png")


# --------------------------------------------------------------------------------------------
# 7) key lesson
# --------------------------------------------------------------------------------------------
def chart_lesson(d: Data) -> str:
    pw = d.analysis["pobjednik"]
    contrib = pw["doprinos_po_tickeru_eur_na_1000"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.6), gridspec_kw={"width_ratios": [1.5, 1]})
    fig.subplots_adjust(bottom=0.25, left=0.09, right=0.97, top=0.88, wspace=0.28)
    paper(a1, "Odakle dolazi dobit pobjednika (K5B)")
    a1.title.set_fontsize(12.5)
    tks = sorted(contrib, key=lambda t: contrib[t])
    a1.barh(tks, [contrib[t] for t in tks], color=[GREEN if contrib[t] > 0 else RED for t in tks], alpha=0.85, height=0.62)
    for i, t in enumerate(tks):
        v = contrib[t]
        a1.text(v + (150 if v >= 0 else -150), i, eur(v), va="center", ha="left" if v >= 0 else "right", fontsize=10)
    a1.set_xlabel("dobit ili gubitak u eurima (na 1.000 € po tvrtki)")
    a1.set_xlim(min(contrib.values()) - 1500, max(contrib.values()) * 1.2)
    a1.grid(True, axis="y", alpha=0)
    share = pw["udio_VRT_u_dobiti_pobjednika"]
    a1.annotate(
        f"{share * 100:.0f} % cijele dobiti\nje samo jedna tvrtka (VRT)",
        xy=(contrib["VRT"] * 0.85, 6),
        xytext=(3600, 3.3),
        fontsize=10.5,
        color=RED,
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.5, connectionstyle="arc3,rad=-0.3"),
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.85),
    )
    paper(a2, "Najgori pad, na 1.000 € na vrhu")
    a2.title.set_fontsize(12.5)
    hv, kv = pw["najgori_pad_drzanje"]["gubitak_na_papiru_eur_po_1000_na_vrhu"], pw["najgori_pad_pobjednik"]["gubitak_na_papiru_eur_po_1000_na_vrhu"]
    a2.bar(["kupi i drži", "K5B"], [hv, kv], color=["#6b7280", GREEN], alpha=0.85, width=0.55)
    a2.text(0, hv + 8, eur(hv), ha="center", fontsize=11)
    a2.text(1, kv + 8, eur(kv), ha="center", fontsize=11)
    a2.set_ylim(0, hv * 1.25)
    a2.set_ylabel("gubitak na papiru (€)")
    a2.grid(True, axis="x", alpha=0)
    teach(
        fig,
        f"lekcija segmenta: držanje je zaradilo više ({eur(d.table[HOLD]['krajnja_vrijednost_eur_na_1000'])} naspram {eur(d.table[K5B]['krajnja_vrijednost_eur_na_1000'])} po 1.000 €), "
        f"a pobjednik je u najgorem padu izgubio {eur(hv - kv)} manje po 1.000 €. Cijena te sigurnosti je {eur(d.table[HOLD]['krajnja_vrijednost_eur_na_1000'] - d.table[K5B]['krajnja_vrijednost_eur_na_1000'])} manje na kraju. "
        "Pazi: tih sedam tvrtki smo izabrali znajući da su u AI eri porasle, pa je držanje ovdje neobično dobro (pristranost unatrag).",
    )
    return save(fig, "07_lekcija.png")


# --------------------------------------------------------------------------------------------
# 8) behaviour: forward return after a 5-day dip vs normal
# --------------------------------------------------------------------------------------------
def chart_dip(d: Data) -> str:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.6), sharey=False)
    fig.subplots_adjust(bottom=0.27, left=0.07, right=0.98, top=0.88, wspace=0.18)
    x = np.arange(len(TICKERS))
    notes: dict[str, str] = {}
    for ax, h, title in ((a1, "f5", "5 dana nakon pada"), (a2, "f20", "20 dana nakon pada")):
        paper(ax, title)
        ax.title.set_fontsize(13)
        aft = [d.ai(t)["after_drop5_above_sma200"] for t in TICKERS]
        after = [a[h]["mean"] * 100 for a in aft]
        base = [a[h]["base_mean"] * 100 for a in aft]
        ax.bar(x - 0.19, after, 0.38, color=INK, alpha=0.85, label="nakon pada od 5 %")
        ax.bar(x + 0.19, base, 0.38, color="#b9c0cc", label="uobičajeni dan")
        ax.axhline(0, color=PENCIL, lw=1)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{t}\n({a['n_episodes']} ep.)" for t, a in zip(TICKERS, aft)], fontsize=9)
        ax.set_ylabel("prosječni prinos poslije (%)")
        ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    o = d.ai("ORCL")["after_drop5_above_sma200"]["f20"]
    anno(
        a2,
        f"ORCL: nakon pada prosječno {hr_pct(o['mean'], 1, True)},\nobično {hr_pct(o['base_mean'], 1, True)}.\nKupnja pada ovdje nije pomogla.",
        (4 + 0.19 - 0.38, o["mean"] * 100),
        (-330, 190),
        color=RED,
        rad=-0.2,
        size=10.5,
    )
    mfull = [t for t in TICKERS if d.ai(t)["after_drop5_above_sma200"]["small_sample"]]
    teach(
        fig,
        "C13C kupuje kad dionica padne bar 5 % u 5 dana, a stoji iznad prosjeka 200 dana. Pitanje je 'poslije takvog pada ide li gore više nego inače?'. "
        "Plavi stupac je prosjek nakon takvih padova, sivi prosjek svih dana. Ako je plavi viši, premisa se potvrđuje. U ovom segmentu to se "
        f"ne vidi jasno (ep. = broj odvojenih pada); za {', '.join(mfull) if mfull else 'nijednu'} je uzorak mali. Primjer: +2 % na 1.000 € je 20 €.",
    )
    return save(fig, "08_nakon_pada.png")


# --------------------------------------------------------------------------------------------
# 9) seasonality heatmap
# --------------------------------------------------------------------------------------------
def chart_season(d: Data) -> str:
    months = ["sij", "velj", "ožu", "tra", "svi", "lip", "srp", "kol", "ruj", "lis", "stu", "pro"]
    m = np.full((len(TICKERS), 12), np.nan)
    n = np.zeros((len(TICKERS), 12), dtype=int)
    for i, t in enumerate(TICKERS):
        s = d.ai(t)["seasonality"]
        for k in range(12):
            r = s.get(str(k + 1))
            if r:
                m[i, k] = r["mean"] * 100
                n[i, k] = r["n"]
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    fig.subplots_adjust(bottom=0.27, left=0.08, right=0.98, top=0.88)
    paper(ax, "Prosječni prinos po kalendarskom mjesecu u AI eri")
    ax.grid(False)
    ax.imshow(np.clip(m, -20, 20), cmap="RdYlGn", vmin=-20, vmax=20, aspect="auto")
    ax.set_xticks(range(12))
    ax.set_xticklabels(months)
    ax.set_yticks(range(len(TICKERS)))
    ax.set_yticklabels(TICKERS)
    for i in range(len(TICKERS)):
        for k in range(12):
            if not np.isnan(m[i, k]):
                ax.text(k, i, f"{round(m[i, k]):d}", ha="center", va="center", fontsize=9.5, color="#111")
    imax = np.unravel_index(np.nanargmax(np.where(np.arange(len(TICKERS))[:, None] == 5, -999, m)), m.shape)
    ring(ax, imax[1], imax[0], color=RED, size=900)
    ax.annotate(
        f"{TICKERS[imax[0]]}, {months[imax[1]]}: {round(m[imax]):d} % u prosjeku, ali\nsamo {n[imax]} godine mjerenja (NBIS izuzet: ima ~2 godine)",
        xy=(imax[1], imax[0]),
        xycoords="data",
        textcoords="axes fraction",
        xytext=(0.52, 1.03),
        va="bottom",
        fontsize=10.5,
        color=RED,
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.5, connectionstyle="arc3,rad=0.3"),
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.9),
    )
    teach(
        fig,
        "svaki kvadratić je prosječni prinos tog mjeseca u AI eri (zeleno = rast, crveno = pad; boja je ograničena na ±20 %). Za svaki mjesec imamo "
        "samo nekoliko opažanja (najviše 4 godine), što je premalo: to je šum, a ne zakon. 'Svibanj je dobar' na 1.000 € znači "
        "da bi se u 4 godine svibnja prosjek jednom mogao dogoditi i slučajno. NBIS je u tablici, ali ima oko dvije godine podataka.",
    )
    return save(fig, "09_sezonalnost.png")


# --------------------------------------------------------------------------------------------
# 10) drawdown anatomy small multiples
# --------------------------------------------------------------------------------------------
def chart_anatomy(d: Data) -> str:
    fig, axes = plt.subplots(4, 2, figsize=(11.5, 15))
    fig.subplots_adjust(top=0.965, bottom=0.09, hspace=0.55, wspace=0.22, left=0.08, right=0.97)
    flat = axes.ravel()
    for ax, tk in zip(flat, TICKERS):
        first = pd.Timestamp(d.profile["tickers"][tk]["first_date"])
        px = d.px[tk]["close"].loc[max(AI_START, first) :]  # NBIS: halted-trading flat prices excluded
        dd = d.ai(tk)["drawdowns"][0]
        a, b = pd.Timestamp(dd["start"]), pd.Timestamp(dd["bottom"])
        rec = pd.Timestamp(dd["recovery"]) if dd["recovery"] else None
        norm = px / px.iloc[0] * 1000
        paper(ax, f"{tk}")
        ax.title.set_fontsize(13)
        ax.plot(norm.index, norm, color=INK, lw=1.2)
        ax.axvspan(a, b, color="#fbe1dc", alpha=0.8, lw=0)
        ring(ax, a, norm.loc[a], color=GREEN, size=250)
        ring(ax, b, norm.loc[b], color=RED, size=250)
        if rec is not None:
            ring(ax, rec, norm.loc[rec], color=INK, size=250)
        ax.set_yscale("log")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_ylabel("1.000 € na početku", fontsize=8.5)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
        ax.yaxis.set_minor_formatter(plt.NullFormatter())
        lost = norm.loc[a] - norm.loc[b]
        txt = f"vrh {dmy(a)} → dno {dmy(b)}\n{hr_pct(dd['depth'])}: -{eur(1000 * (1 - norm.loc[b] / norm.loc[a]))} na 1.000 € s vrha\n" + (f"oporavak {dmy(rec)}" if rec is not None else "još nije oporavljen")
        ax.text(0.02, 0.97, txt, transform=ax.transAxes, fontsize=8.8, color=RED, va="top", bbox=dict(boxstyle="round,pad=0.2", fc=PAPER, ec="none", alpha=0.85))
    ax = flat[7]
    ax.axis("off")
    ax.text(
        0.0,
        0.95,
        "Kako čitati:\n\nzeleni krug = vrh prije pada\ncrveni krug = dno\nplavi krug = dan kad je cijena\nopet na starom vrhu\n\nCrvena podloga je trajanje pada.\nOs je logaritamska: jednaki\nrazmaci znače jednake postotke.",
        transform=ax.transAxes,
        fontsize=11.5,
        va="top",
        color=PENCIL,
    )
    teach(
        fig,
        "svaka dionica ima barem jedan pad od vrha do dna. Tvrtke koje rastu na tuđim ulaganjima ili se zadužuju (VRT, ORCL, NBIS) padaju dublje. "
        "Zato 1.000 € s vrha postane i 350 € na papiru (ORCL). Pad nije gubitak dok ne prodaš, ali pitaj sebe možeš li gledati takav pad.",
    )
    return save(fig, "10_anatomija_pada.png")


# --------------------------------------------------------------------------------------------
# 11) support / resistance reaction examples (same pivot rule as profile_stats)
# --------------------------------------------------------------------------------------------
def sr_examples(df: pd.DataFrame) -> list[dict[str, Any]]:
    """First touch of each confirmed swing level; returns level, pivot bar, touch bar and outcome."""
    c, lo, hi = df["close"].to_numpy(), df["low"].to_numpy(), df["high"].to_numpy()
    n = len(c)
    k = 5
    plows, phighs = pivots(lo, hi, k)
    out: list[dict[str, Any]] = []
    for kind, plist in (("support", plows), ("resistance", phighs)):
        for p in plist:
            lvl = lo[p] if kind == "support" else hi[p]
            for t in range(p + k + 1, min(n - 6, p + SR_MAX_AGE)):
                if kind == "support":
                    if c[t] < lvl * (1 - SR_BAND):
                        break
                    if lo[t] <= lvl * (1 + SR_BAND) and c[t - 1] > lvl * (1 + SR_BAND):
                        broke = bool((c[t : t + 6] < lvl * (1 - SR_BAND)).any())
                        out.append({"kind": kind, "level": lvl, "p": p, "t": t, "broke": broke})
                        break
                else:
                    if c[t] > lvl * (1 + SR_BAND):
                        break
                    if hi[t] >= lvl * (1 - SR_BAND) and c[t - 1] < lvl * (1 - SR_BAND):
                        broke = bool((c[t : t + 6] > lvl * (1 + SR_BAND)).any())
                        out.append({"kind": kind, "level": lvl, "p": p, "t": t, "broke": broke})
                        break
    return out


def chart_sr(d: Data) -> str:
    tk = "GOOGL"
    px = d.px[tk]
    win = px.loc["2025-05-01":"2026-01-31"]
    ev = [e for e in sr_examples(px) if win.index[0] <= px.index[e["t"]] <= win.index[-1] and px.index[e["p"]] >= win.index[0] - pd.Timedelta(days=60)]
    fig, ax = plt.subplots(figsize=(11.5, 7))
    fig.subplots_adjust(bottom=0.24, left=0.08, right=0.97, top=0.9)
    paper(ax, f"{tk}: što se dogodilo kad je cijena prvi put dotaknula staru razinu")
    ax.plot(win.index, win["close"], color=INK, lw=1.4)
    held_ex = broke_ex = None
    for e in ev:
        t0, t1 = px.index[e["p"] + 5], px.index[e["t"]]
        col = RED if e["broke"] else GREEN
        ax.hlines(e["level"], t0, min(t1 + pd.Timedelta(days=12), win.index[-1]), colors=col, lw=1.6, linestyles="-" if not e["broke"] else ":")
        ax.scatter([t1], [e["level"]], s=95, facecolors="none", edgecolors=col, linewidths=2.0, zorder=6)
        late = t1 >= pd.Timestamp("2025-06-15")
        if e["broke"] and broke_ex is None and late:
            broke_ex = e
        if not e["broke"] and held_ex is None and late and e["kind"] == "support":
            held_ex = e
    ax.set_ylabel("cijena u dolarima")
    ax.plot([], [], color=GREEN, label="razina je izdržala")
    ax.plot([], [], color=RED, ls=":", label="razina je probijena")
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    prof = d.profile["tickers"][tk]["tumacenje_hr"]["podrska_otpor"].split(" Zadržavanje")[0]

    def fraction_note(e: dict[str, Any], text: str, at: tuple[float, float], color: str) -> None:
        t1 = px.index[e["t"]]
        ann = ax.annotate(
            text,
            xy=(t1, e["level"]),
            xycoords="data",
            xytext=at,
            textcoords="axes fraction",
            fontsize=10.5,
            color=color,
            va="center",
            arrowprops=dict(arrowstyle="->", color=color, lw=1.5, connectionstyle="arc3,rad=0.25", shrinkB=5),
            bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.9),
        )
        sketch(ann.arrow_patch, 0.9, 60, 3)

    def after5(e: dict[str, Any]) -> str:
        t = e["t"]
        c0, c5 = px["close"].iloc[t], px["close"].iloc[t + 5]
        return f"5 dana poslije: {usd(c5)} ({hr_pct(c5 / c0 - 1, 1, True)}), na 1.000 € to je {eur(1000 * c5 / c0)}"

    if held_ex is not None:
        t1 = px.index[held_ex["t"]]
        fraction_note(
            held_ex,
            f"{dmy(t1)}: cijena pada do stare podrške\n{usd(held_ex['level'])} i izdrži (nema probijanja).\n{after5(held_ex)}",
            (0.10, 0.58),
            GREEN,
        )
    if broke_ex is not None:
        t1 = px.index[broke_ex["t"]]
        what = (
            "podrška nije izdržala, cijena je zatvorila ispod nje"
            if broke_ex["kind"] == "support"
            else "otpor je probijen, cijena je zatvorila iznad njega"
        )
        fraction_note(
            broke_ex,
            f"{dmy(t1)}: razina {usd(broke_ex['level'])}:\n{what}.\n{after5(broke_ex)}",
            (0.50, 0.22),
            RED,
        )
    teach(
        fig,
        "podrška je cijena na kojoj je pad prije stao, otpor je cijena na kojoj je rast prije stao. Crtice su te razine, krug je prvi dodir. "
        f"Za {tk} u AI eri: {prof} 'Zadržala' znači da cijena u idućih nekoliko dana nije zatvorila više od 1,5 % preko razine. "
        "Nema usporedbe sa slučajnim razinama, pa to nije dokaz da razine 'rade'.",
    )
    return save(fig, "11_podrska_otpor.png")


def main() -> None:
    d = Data()
    done = [
        chart_prices(d),
        chart_equity(d),
        chart_drawdown(d),
        chart_trades(d),
        chart_scoreboard(d),
        chart_costs(d),
        chart_lesson(d),
        chart_dip(d),
        chart_season(d),
        chart_anatomy(d),
        chart_sr(d),
    ]
    print("\n".join(str(SEG / f) for f in done))


if __name__ == "__main__":
    main()
