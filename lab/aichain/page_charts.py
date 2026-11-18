"""Notebook-style PNG charts for one AI-chain segment page (research only, no orders).

Everything is drawn from the REAL simulation output in ``reports/research/AICHAIN_20261014``:
``results/{segment}.json`` (segment equity and trades), ``results/{TICKER}.json`` (per ticker trades),
``segments/{segment}/analysis.json`` and ``profile_numbers.json``. Prices come from ``data/ohlcv`` through
``lab.aichain.sim.load_bars``. Nothing is invented: every number written into a note is computed here.

The style (graph paper, handwriting font, pencil arrows, red teacher notes) reuses the helpers of
``lab/top10/charts.py`` without modifying that module.

Usage:
  .venv/bin/python -m lab.aichain.page_charts network_servers
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from lab.aichain.sim import AI_ERA_START, load_bars
from lab.top10.charts import (
    GREEN,
    GRID,
    INK,
    PAPER,
    PENCIL,
    RED,
    day,
    eur,
    paper,
    ring,
    save,
    sketch,
    teacher as _teacher_unused,
)

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
GREY = "#6b7280"
ORANGE = "#d9770a"
PALETTE = [
    "#1d3fb8",
    "#c2321f",
    "#17803d",
    "#d9770a",
    "#7b3fa0",
    "#0e7490",
    "#9a6208",
    "#be185d",
]
NAMES = {
    "B0_BUYHOLD": "kupi i drži",
    "K1_C13C_ORIG": "C13C (tvoj)",
    "K2_SMA200_TREND": "trend SMA200",
    "K3_DONCHIAN_55_20": "proboj 55/20",
    "K4_TSMOM_126": "momentum 126 d.",
    "K5_SUPPORT_RESISTANCE": "potpora/otpor",
    "K5B_SR_BREAKOUT_RETEST": "proboj + povratni test",
    "K6_MOMENTUM_CS": "rotacija momentuma",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C + ponovni ulaz",
}
# Which tickers the price chart shows and which single trade gets the stop-line demonstration.
PRICE_PICKS: dict[str, list[dict[str, str]]] = {
    "network_servers": [
        {"ticker": "LITE", "demo": "2024-10-22", "story": "trend"},
        {"ticker": "SMCI", "demo": "2025-09-03", "story": "crash"},
        {"ticker": "ANET", "demo": "2023-10-27", "story": "gap"},
    ]
}
SR_PICK = {"network_servers": "HPE"}


def teacher(fig: Any, text: str, width: int = 150) -> None:
    """Red 'Bilješka učitelja' line at the bottom of the figure, wrapped so it never leaves the page."""
    import textwrap

    fig.text(
        0.012,
        0.012,
        textwrap.fill("Bilješka učitelja: " + text, width=width),
        fontsize=11.5,
        color=RED,
        ha="left",
        va="bottom",
    )


def num(x: float, nd: int = 1) -> str:
    """Croatian decimal comma."""
    return f"{x:.{nd}f}".replace(".", ",")


def pc(x: float, nd: int = 1, sign: bool = False) -> str:
    return (f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}").replace(".", ",") + " %"


def usd(x: float) -> str:
    return f"{x:,.2f} USD".replace(",", "X").replace(".", ",").replace("X", ".")


def short_day(d: Any) -> str:
    t = pd.Timestamp(d)
    return f"{t.day}. {t.month}. {t.year}."


def hand(
    ax: Any,
    text: str,
    xy: tuple[Any, float],
    xytext: tuple[Any, float],
    color: str = PENCIL,
    rad: float = 0.2,
    size: float = 10.5,
    ha: str = "left",
    arrow: bool = True,
    frac: bool = False,
) -> Any:
    """Handwritten note; xy is in DATA coordinates (dates allowed), xytext in data or axes fraction."""

    def conv(p: tuple[Any, float]) -> tuple[float, float]:
        x = p[0]
        if isinstance(x, (pd.Timestamp, np.datetime64, str)):
            x = mdates.date2num(pd.Timestamp(x))
        return (x, p[1])

    kw: dict[str, Any] = dict(
        xy=conv(xy),
        xycoords="data",
        xytext=xytext if frac else conv(xytext),
        textcoords="axes fraction" if frac else "data",
        ha=ha,
        va="center",
        fontsize=size,
        color=color,
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.85),
        zorder=8,
    )
    if arrow:
        kw["arrowprops"] = dict(
            arrowstyle="->",
            color=color,
            lw=1.4,
            connectionstyle=f"arc3,rad={rad}",
            shrinkB=3,
        )
    ann = ax.annotate(text, **kw)
    if arrow and ann.arrow_patch is not None:
        sketch(ann.arrow_patch, 0.9, 60, 3)
    return ann


def date_axis(ax: Any) -> None:
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%Y."))


def ai_line(ax: Any, label_y: float = 0.03) -> None:
    ax.axvline(pd.Timestamp(AI_ERA_START), color=RED, ls="--", lw=1.2)
    ax.text(
        pd.Timestamp(AI_ERA_START) + pd.Timedelta(days=14),
        label_y,
        "1. 1. 2023.: početak AI ere\n(sve lijevo je samo kontekst)",
        transform=ax.get_xaxis_transform(),
        fontsize=8.5,
        color=RED,
    )


class Data:
    """All real inputs for one segment, loaded once."""

    def __init__(self, segment: str) -> None:
        self.segment = segment
        self.out = BASE / "segments" / segment
        self.analysis = json.loads((self.out / "analysis.json").read_text())
        self.seg = json.loads((BASE / "results" / f"{segment}.json").read_text())
        self.tickers: list[str] = self.seg["tickers"]
        self.tk = {
            t: json.loads((BASE / "results" / f"{t}.json").read_text())
            for t in self.tickers
        }
        self.prof = {
            (p["ticker"], p["window"]): p
            for p in json.loads((self.out / "profile_numbers.json").read_text())[
                "profiles"
            ]
        }
        self.n = len(self.tickers)
        self.cap = float(self.seg["start_capital_per_sleeve"])

    def seg_equity(self, cid: str) -> pd.Series:
        """Segment equity per 1.000 EUR invested (sum of sleeves divided by the number of sleeves)."""
        rows = self.seg["contenders"][cid]["equity"]["ai_era"]
        s = pd.Series(
            [r[1] for r in rows], index=pd.to_datetime([r[0] for r in rows])
        )
        return s / self.n

    def win(self, cid: str) -> dict[str, Any]:
        return self.seg["contenders"][cid]["windows"]["ai_era"]

    def trades(self, cid: str) -> list[dict[str, Any]]:
        return self.seg["contenders"][cid]["trades"]["ai_era"]

    def tk_trades(self, t: str, cid: str = "K1_C13C_ORIG") -> list[dict[str, Any]]:
        return self.tk[t]["contenders"][cid]["trades"]["ai_era"]


def drawdown(eq: pd.Series) -> pd.Series:
    return eq / eq.cummax() - 1


# ---------------------------------------------------------------- 1 price + C13C
def chart_price(d: Data) -> str:
    picks = PRICE_PICKS[d.segment]
    fig, axes = plt.subplots(len(picks), 1, figsize=(11.5, 5.0 * len(picks) + 0.8))
    fig.subplots_adjust(bottom=0.085, hspace=0.3, top=0.965, left=0.075, right=0.985)
    for ax, pk in zip(np.atleast_1d(axes), picks):
        t = pk["ticker"]
        bars = load_bars(t)
        close = pd.Series(bars.close, index=bars.dates)
        high = pd.Series(bars.high, index=bars.dates)
        sma = close.rolling(200).mean()
        win = close.index >= pd.Timestamp(AI_ERA_START)
        c, s = close[win], sma[win]
        paper(ax, f"{t}: cijena, SMA200 i svaki ulaz/izlaz C13C-a")
        ax.plot(c.index, c, color=INK, lw=1.4, label="zatvaranje (USD)")
        ax.plot(s.index, s, color=GREY, lw=1.3, ls="--", label="SMA200 (prosjek 200 dana)")
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(plt.NullFormatter())
        ax.set_ylabel("USD (logaritamska ljestvica)")
        date_axis(ax)
        tr = d.tk_trades(t)
        ex = [x for x in tr if x["reason"] == "stop"]
        ax.scatter(
            [pd.Timestamp(x["entry_date"]) for x in tr],
            [x["raw_entry"] for x in tr],
            marker="^",
            s=46,
            color=GREEN,
            edgecolor="white",
            lw=0.5,
            zorder=6,
        )
        loss = [x for x in ex if x["return"] < 0]
        win_s = [x for x in ex if x["return"] >= 0]
        ax.scatter(
            [pd.Timestamp(x["exit_date"]) for x in loss],
            [x["raw_exit"] for x in loss],
            marker="v",
            s=46,
            color=RED,
            edgecolor="white",
            lw=0.5,
            zorder=6,
        )
        ax.scatter(
            [pd.Timestamp(x["exit_date"]) for x in win_s],
            [x["raw_exit"] for x in win_s],
            marker="v",
            s=46,
            facecolor=PAPER,
            edgecolor=RED,
            lw=1.3,
            zorder=6,
        )
        # demo trade: stop line = 90 % of the highest high known before each bar, never lowered
        demo = next(x for x in tr if x["entry_date"] == pk["demo"])
        ei = close.index.get_loc(pd.Timestamp(demo["entry_date"]))
        xi = close.index.get_loc(pd.Timestamp(demo["exit_date"]))
        sig = ei - 1
        dip = close.iloc[sig] / close.iloc[sig - 5] - 1
        peak = max(demo["raw_entry"], float(high.iloc[ei]))
        stops_x, stops_y = [], []
        cur = round(peak * 0.9, 2)
        for j in range(ei, xi + 1):
            stops_x.append(close.index[j])
            stops_y.append(cur)
            peak = max(peak, float(high.iloc[j]))
            cur = max(cur, round(peak * 0.9, 2))
        ax.plot(stops_x, stops_y, color=ORANGE, lw=2.2, zorder=5, label="stop (10 % ispod vrha) za jedan posao")
        pad = pd.Timedelta(days=25)
        tdates = [pd.Timestamp(demo["entry_date"]), pd.Timestamp(demo["exit_date"])]
        lo = float(min(c.min(), 1e9))
        hi = float(c.max())
        yr = hi / lo
        # --- notes
        sigd, ed = close.index[sig], close.index[ei]
        y_sig = float(close.iloc[sig])
        ax.scatter([sigd], [y_sig], s=420, facecolors="none", edgecolors=RED, lw=2, zorder=7)
        sig_txt = (
            f"signal {short_day(sigd)}:\nzatvaranje {usd(y_sig)} je {pc(abs(dip) * 100)} ispod\n"
            f"cijene 5 dana prije, a ipak iznad SMA200\n"
            f"-> sutradan kupnja po {usd(demo['raw_entry'])}"
        )
        ex_txt = (
            f"stop se diže s vrhom i izbija {short_day(demo['exit_date'])}\n"
            f"po {usd(demo['raw_exit'])}: {pc(demo['return'] * 100, 1, True)}, "
            f"{demo['bars_held']} dana. 1.000 EUR -> {eur(1000 * (1 + demo['return']))}"
        )
        if pk["story"] == "trend":
            hand(ax, sig_txt, (sigd, y_sig), (0.17, 0.64), color=RED, rad=-0.25, size=9.4, frac=True)
            hand(ax, ex_txt, (tdates[1], demo["raw_exit"]), (0.38, 0.05), color=ORANGE, rad=0.3, size=9.4, frac=True)
            hand(
                ax,
                f"{t} ide s {usd(float(c.iloc[0]))} na {usd(float(c.iloc[-1]))}, a C13C je\n"
                f"u poziciji samo {num(d.tk[t]['contenders']['K1_C13C_ORIG']['windows']['ai_era']['exposure_pct'], 0)} % vremena:\n"
                f"stalno izlazi na stopu, propušta trend",
                (pd.Timestamp("2026-01-12"), float(c["2026-01-12":].iloc[0])),
                (0.64, 0.23),
                color=PENCIL,
                rad=-0.3,
                size=9.4,
                frac=True,
            )
        elif pk["story"] == "crash":
            sm = d.analysis["kartice_dionica"][t]["najgori_padovi"][0]
            top, bot = pd.Timestamp(sm["vrh"]), pd.Timestamp(sm["dno"])
            ring(ax, top, float(close.loc[top]), RED, 600)
            ring(ax, bot, float(close.loc[bot]), RED, 600)
            lastx = [x for x in tr if pd.Timestamp(x["exit_date"]) <= bot][-1]
            hand(
                ax,
                f"vrh {short_day(top)}: {usd(float(close.loc[top]))}\ndno {short_day(bot)}: {usd(float(close.loc[bot]))}\n"
                f"držanje: {pc(sm['dubina_pct'], 1)}, pa od 1.000 EUR\nostane {eur(1000 * (1 + sm['dubina_pct'] / 100))}",
                (bot, float(close.loc[bot])),
                (0.40, 0.12),
                color=RED,
                rad=0.3,
                size=9.4,
                frac=True,
            )
            hand(
                ax,
                f"C13C je {short_day(lastx['exit_date'])} izašao po {usd(lastx['raw_exit'])}\n"
                f"i ostao u gotovini do dna: stop je\nspasio većinu novca",
                (pd.Timestamp(lastx["exit_date"]), lastx["raw_exit"]),
                (0.45, 0.88),
                color=PENCIL,
                rad=-0.25,
                size=9.4,
                frac=True,
            )
            hand(ax, sig_txt, (sigd, y_sig), (0.62, 0.16), color=ORANGE, rad=0.2, size=9.0, frac=True)
        else:
            sm = d.analysis["kartice_dionica"][t]["najgori_padovi"][0]
            bot = pd.Timestamp(sm["dno"])
            before = [x for x in tr if pd.Timestamp(x["exit_date"]) <= bot][-1]
            after = [x for x in tr if pd.Timestamp(x["entry_date"]) > bot][0]
            ring(ax, bot, float(close.loc[bot]), RED, 600)
            hand(
                ax,
                f"dno {short_day(bot)}: {usd(float(close.loc[bot]))}.\nC13C je izašao već {short_day(before['exit_date'])} po {usd(before['raw_exit'])},\n"
                f"ali se vratio tek {short_day(after['entry_date'])} po {usd(after['raw_entry'])}:\nušteda u padu, ali propušten dio oporavka",
                (bot, float(close.loc[bot])),
                (0.42, 0.07),
                color=RED,
                rad=0.25,
                size=9.4,
                frac=True,
            )
            hand(ax, sig_txt, (sigd, y_sig), (0.03, 0.66), color=ORANGE, rad=0.25, size=9.0, frac=True)
            hand(ax, ex_txt, (tdates[1], demo["raw_exit"]), (0.03, 0.86), color=ORANGE, rad=-0.3, size=9.0, frac=True)
        if pk["story"] == "crash":
            ax.set_ylim(float(c.min()) * 0.6, float(close.max()) * 1.35)
        ai_line(ax, 0.01)
    h = [
        Line2D([], [], color=INK, lw=1.4),
        Line2D([], [], color=GREY, lw=1.3, ls="--"),
        Line2D([], [], marker="^", color=GREEN, lw=0, ms=8),
        Line2D([], [], marker="v", color=RED, lw=0, ms=8),
        Line2D([], [], marker="v", markerfacecolor=PAPER, markeredgecolor=RED, lw=0, ms=8),
        Line2D([], [], color=ORANGE, lw=2.2),
    ]
    fig.legend(
        h,
        ["zatvaranje", "SMA200", "kupnja", "izlaz na stopu s gubitkom", "izlaz na stopu s dobitkom", "stop jednog posla"],
        loc="lower center",
        bbox_to_anchor=(0.5, 0.025),
        ncol=6,
        fontsize=9,
        frameon=False,
    )
    teacher(
        fig,
        "zeleni trokut = kupnja nakon pada od 5 % u 5 dana (uz cijenu iznad SMA200). Crveni = stop je izbio (puni: gubitak, prazni: stop je bio iznad ulaza pa je ipak dobitak).",
    )
    fig.savefig(d.out / "01_cijena_c13c.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "01_cijena_c13c.png"


# ---------------------------------------------------------------- 2 equity
def chart_equity(d: Data) -> str:
    win_id = d.analysis["tko_je_najbolje_odradio_posao"]["pobjednik"]
    hold, k1, k6 = (d.seg_equity(x) for x in ("B0_BUYHOLD", "K1_C13C_ORIG", win_id))
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    fig.subplots_adjust(bottom=0.17, left=0.08, right=0.985, top=0.9)
    paper(ax, "Što bi postalo od 1.000 EUR (podijeljeno na 8 dionica)")
    for s, col, lw, lab in (
        (hold, GREY, 1.8, "kupi i drži"),
        (k1, INK, 2.0, "C13C (tvoj algoritam)"),
        (k6, GREEN, 2.0, NAMES[win_id] + " (pobjednik)"),
    ):
        ax.plot(s.index, s, color=col, lw=lw, label=lab)
    ax.set_ylabel("EUR (od početnih 1.000 EUR)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    date_axis(ax)
    ax.legend(loc="upper left", frameon=True, facecolor=PAPER, edgecolor=GRID, fontsize=10)
    dd = d.analysis["kartice_dionica"]["ANET"]["najgori_padovi"][0]
    pk_d, bt_d = pd.Timestamp(dd["vrh"]), pd.Timestamp(dd["dno"])
    h_pk, h_bt = float(hold.loc[pk_d]), float(hold.loc[bt_d])
    c_pk, c_bt = float(k1.loc[pk_d]), float(k1.loc[bt_d])
    ax.axvspan(pk_d, bt_d, color="#f6d9d4", alpha=0.6, lw=0)
    hand(
        ax,
        f"zajednički pad {short_day(pk_d)} -> {short_day(bt_d)}:\n"
        f"držanje {eur(h_pk)} -> {eur(h_bt)} (gubi {eur(h_pk - h_bt)})\n"
        f"C13C {eur(c_pk)} -> {eur(c_bt)} (gubi {eur(c_pk - c_bt)})",
        (bt_d, h_bt),
        (0.33, 0.50),
        color=RED,
        rad=0.25,
        size=10,
        frac=True,
    )
    expo = d.win("K1_C13C_ORIG")["exposure_pct"]
    hand(
        ax,
        f"C13C je u prosjeku u dionicama samo {num(expo, 0)} % novca,\nostalo čeka u gotovini. Ravni dio plave crte\n(travanj 2025. do kraja te godine) = čeka",
        (pd.Timestamp("2025-08-01"), float(k1.loc["2025-08-01"])),
        (0.30, 0.27),
        color=PENCIL,
        rad=0.2,
        size=10,
        frac=True,
    )
    for s, col, dy in ((hold, GREY, 0), (k1, INK, 0), (k6, GREEN, 0)):
        ax.annotate(
            eur(float(s.iloc[-1])),
            (s.index[-1], float(s.iloc[-1])),
            xytext=(6, dy),
            textcoords="offset points",
            fontsize=10.5,
            color=col,
            va="center",
        )
    ax.set_xlim(hold.index[0], hold.index[-1] + pd.Timedelta(days=120))
    teacher(
        fig,
        f"na početku je 1.000 EUR. Što je crta viša na kraju, to je više novca ostalo. Ravni dijelovi plave crte = C13C čeka u gotovini. Na kraju: držanje {eur(float(hold.iloc[-1]))}, C13C {eur(float(k1.iloc[-1]))}, pobjednik {eur(float(k6.iloc[-1]))}.",
    )
    fig.savefig(d.out / "02_kapital.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "02_kapital.png"


# ---------------------------------------------------------------- 3 drawdown
def chart_drawdown(d: Data) -> str:
    win_id = d.analysis["tko_je_najbolje_odradio_posao"]["pobjednik"]
    series = {
        "kupi i drži": (d.seg_equity("B0_BUYHOLD"), GREY),
        "C13C (tvoj)": (d.seg_equity("K1_C13C_ORIG"), INK),
        NAMES[win_id] + " (pobjednik)": (d.seg_equity(win_id), GREEN),
    }
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    fig.subplots_adjust(bottom=0.2, left=0.08, right=0.985, top=0.9)
    paper(ax, "Koliko je boljelo: pad od najboljeg trenutka")
    for lab, (s, col) in series.items():
        dd = drawdown(s) * 100
        ax.fill_between(dd.index, dd, 0, color=col, alpha=0.08, lw=0)
        ax.plot(dd.index, dd, color=col, lw=1.6, label=lab)
    hold = series["kupi i drži"][0]
    dh = drawdown(hold) * 100
    tb = dh.idxmin()
    ring(ax, tb, float(dh.min()), RED, 700)
    pk = hold.loc[:tb].idxmax()
    hand(
        ax,
        f"najgore za držanje: {short_day(tb)}, {pc(float(dh.min()))}\n"
        f"od 1.000 EUR na vrhu ({short_day(pk)}) ostane\n{eur(1000 * (1 + dh.min() / 100))}: to je {eur(1000 * -dh.min() / 100)} manje",
        (tb, float(dh.min())),
        (0.07, 0.15),
        color=RED,
        rad=0.2,
        size=10,
        frac=True,
    )
    ret = hold.pct_change().dropna()
    wd = ret.idxmin()
    prev = float(hold.shift(1).loc[wd])
    cur = float(hold.loc[wd])
    ax.scatter([wd], [float(dh.loc[wd])], s=60, color=ORANGE, zorder=7)
    hand(
        ax,
        f"najgori jedan dan: {short_day(wd)}, {pc(float(ret.min()) * 100)}\n"
        f"(vrijednost {eur(prev)} -> {eur(cur)}: u jednom\ndanu nestane {eur(prev - cur)})",
        (wd, float(dh.loc[wd])),
        (0.56, 0.90),
        color=ORANGE,
        rad=0.25,
        size=10,
        frac=True,
    )
    k1 = series["C13C (tvoj)"][0]
    k1dd = drawdown(k1) * 100
    hand(
        ax,
        f"C13C: najgori pad samo {pc(float(k1dd.min()))}\n(najgori gubitak {eur(1000 * -k1dd.min() / 100)} umjesto {eur(1000 * -dh.min() / 100)})",
        (k1dd.idxmin(), float(k1dd.min())),
        (0.04, 0.46),
        color=INK,
        rad=0.25,
        size=10,
        frac=True,
    )
    ax.set_ylabel("% ispod prethodnog vrha")
    ax.legend(loc="lower left", frameon=True, facecolor=PAPER, edgecolor=GRID, fontsize=10)
    ax.set_ylim(float(dh.min()) * 1.18, 4)
    date_axis(ax)
    teacher(
        fig,
        "svaka crta pokazuje koliko je vrijednost bila ispod svog najvišeg trenutka. -46 % znači: 1.000 EUR na vrhu je na dnu samo 536 EUR. Pitanje nije samo koliko možeš zaraditi nego i koliko pada možeš izdržati bez panične prodaje.",
    )
    fig.savefig(d.out / "03_pad.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "03_pad.png"


# ---------------------------------------------------------------- 4 trades
def chart_trades(d: Data) -> str:
    tr = d.trades("K1_C13C_ORIG")
    df = pd.DataFrame(tr)
    df["ret"] = df["return"] * 100
    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(11.5, 6.0), gridspec_kw={"width_ratios": [3.3, 1]}
    )
    fig.subplots_adjust(bottom=0.2, left=0.075, right=0.985, top=0.9, wspace=0.05)
    paper(ax, f"Svih {len(df)} poslova C13C-a: koliko je trajao i koliko je donio")
    col = {t: PALETTE[i % 8] for i, t in enumerate(d.tickers)}
    for t in d.tickers:
        s = df[df["ticker"] == t]
        ax.scatter(s["bars_held"], s["ret"], s=22, color=col[t], alpha=0.75, label=t, edgecolor="white", lw=0.3)
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_xlabel("koliko trgovačkih dana je pozicija trajala")
    ax.set_ylabel("povrat posla (%)")
    ax.legend(ncol=4, fontsize=8.5, frameon=True, facecolor=PAPER, edgecolor=GRID, loc="upper right")
    best = df.loc[df["ret"].idxmax()]
    worst = df.loc[df["ret"].idxmin()]
    for r, colr, nm in ((best, GREEN, "najbolji"), (worst, RED, "najgori")):
        ring(ax, r["bars_held"], float(r["ret"]), colr, 600)
    xmax = float(df["bars_held"].max())
    hand(
        ax,
        f"najbolji: {best['ticker']}, {short_day(best['entry_date'])} -> {short_day(best['exit_date'])}\n"
        f"{pc(float(best['ret']), 0, True)}: 1.000 EUR -> {eur(1000 * (1 + best['return']))}",
        (best["bars_held"], float(best["ret"])),
        (best["bars_held"] + xmax * 0.12, float(best["ret"]) * 0.8),
        color=GREEN,
        rad=0.2,
        size=10,
    )
    hand(
        ax,
        f"najgori: {worst['ticker']}, {short_day(worst['entry_date'])} -> {short_day(worst['exit_date'])}\n"
        f"{pc(float(worst['ret']), 1)}: 1.000 EUR -> {eur(1000 * (1 + worst['return']))}\n(jaz preko noći probio je stop)"
        if worst["detail"] == "gap_stop"
        else f"najgori: {worst['ticker']}, {short_day(worst['entry_date'])}\n{pc(float(worst['ret']), 1)}: 1.000 EUR -> {eur(1000 * (1 + worst['return']))}",
        (worst["bars_held"], float(worst["ret"])),
        (worst["bars_held"] + xmax * 0.2, float(worst["ret"]) * 0.6),
        color=RED,
        rad=-0.2,
        size=10,
    )
    w = d.win("K1_C13C_ORIG")
    ax2.set_facecolor(PAPER)
    ax2.axis("off")
    ax2.text(
        0.0,
        0.97,
        "Čitaj ovako:\n\n"
        f"dobitni poslovi: {num(w['hit_rate'] * 100, 0)} %\n"
        f"prosječna dobit: {pc(w['avg_win'] * 100, 1, True)}\n"
        f"  = {eur(1000 * w['avg_win'])} na 1.000 EUR\n\n"
        f"prosječni gubitak: {pc(w['avg_loss'] * 100, 1)}\n"
        f"  = {eur(-1000 * w['avg_loss'])} na 1.000 EUR\n\n"
        "Stop reže gubitke\npri oko -10 %, a dobitke\nostavlja da rastu: zato\nje prosječna dobit veća\nod prosječnog gubitka.",
        transform=ax2.transAxes,
        fontsize=10.5,
        va="top",
        color=PENCIL,
        linespacing=1.35,
    )
    teacher(
        fig,
        f"svaka točka je jedan posao. Desno = dulje u poziciji, gore = veći dobitak. Većina poslova traje manje od tjedan-dva, a nekoliko velikih nosi rezultat. Ovdje je {len(df)} poslova na osam dionica.",
    )
    fig.savefig(d.out / "04_poslovi.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "04_poslovi.png"


# ---------------------------------------------------------------- 5 scoreboard
def chart_scoreboard(d: Data) -> str:
    t = d.analysis["tablica_segmenta_jednak_kapital_AI_era"]["suparnici"]
    ids = list(t)
    order = sorted(ids, key=lambda k: t[k]["za_1000_EUR_na_kraju"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.0), sharey=True)
    fig.subplots_adjust(bottom=0.2, left=0.2, right=0.985, top=0.9, wspace=0.08)
    paper(a1, "Koliko je ostalo od 1.000 EUR")
    paper(a2, "Sharpe (nagrada za nemir)")
    win = d.analysis["tko_je_najbolje_odradio_posao"]["pobjednik"]
    cols = []
    for k in order:
        cols.append(GREY if k == "B0_BUYHOLD" else (GREEN if k == win else (INK if k == "K1_C13C_ORIG" else "#9fb3d9")))
    y = np.arange(len(order))
    vals = [t[k]["za_1000_EUR_na_kraju"] for k in order]
    a1.barh(y, vals, color=cols, edgecolor=PENCIL, lw=0.8, hatch="//", alpha=0.85)
    for yi, v in zip(y, vals):
        a1.text(v + 150, yi, eur(v), va="center", fontsize=9.5, color=PENCIL)
    a1.axvline(t["B0_BUYHOLD"]["za_1000_EUR_na_kraju"], color=GREY, ls="--", lw=1.4)
    a1.set_yticks(y)
    a1.set_yticklabels([NAMES[k] for k in order], fontsize=10.5)
    a1.set_xlim(0, max(vals) * 1.25)
    a1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    a1.set_xlabel("EUR na kraju")
    sh = [t[k]["sharpe"] for k in order]
    a2.barh(y, sh, color=cols, edgecolor=PENCIL, lw=0.8, hatch="//", alpha=0.85)
    for yi, v in zip(y, sh):
        a2.text(v + 0.03, yi, num(v, 2), va="center", fontsize=9.5, color=PENCIL)
    a2.axvline(t["B0_BUYHOLD"]["sharpe"], color=GREY, ls="--", lw=1.4)
    a2.set_xlim(0, max(sh) * 1.2)
    a2.set_xlabel("Sharpe (veći je bolji)")
    wi = order.index(win)
    hand(
        a1,
        f"pobjednik po pravilu unaprijed:\n{NAMES[win]}, {eur(t[win]['za_1000_EUR_na_kraju'])}",
        (t[win]["za_1000_EUR_na_kraju"] * 0.9, wi + 0.3),
        (0.42, 0.62),
        color=GREEN,
        rad=0.25,
        size=10,
        frac=True,
    )
    ki = order.index("K1_C13C_ORIG")
    hand(
        a1,
        f"tvoj C13C: {eur(t['K1_C13C_ORIG']['za_1000_EUR_na_kraju'])},\nispod držanja ({eur(t['B0_BUYHOLD']['za_1000_EUR_na_kraju'])})",
        (t["K1_C13C_ORIG"]["za_1000_EUR_na_kraju"] * 1.28, ki + 0.1),
        (0.42, 0.30),
        color=INK,
        rad=-0.25,
        size=10,
        frac=True,
    )
    a1.legend(
        [Line2D([], [], color=GREY, ls="--", lw=1.4)],
        ["držanje (mjerilo)"],
        loc="lower right",
        frameon=True,
        facecolor=PAPER,
        edgecolor=GRID,
        fontsize=9.5,
    )
    a2.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: num(v, 2)))
    teacher(
        fig,
        "sve što je desno od iscrtkane crte pobijedilo je običnu kupnju i držanje. Pobjednik je izabran po pravilu zadanom unaprijed (najviši Sharpe uz bar 20 poslova), a ne po tome tko izgleda najbolje.",
    )
    fig.savefig(d.out / "05_ljestvica.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "05_ljestvica.png"


# ---------------------------------------------------------------- 6 costs
def chart_costs(d: Data) -> str:
    t = d.analysis["tablica_segmenta_jednak_kapital_AI_era"]["suparnici"]
    ids = list(t)
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    fig.subplots_adjust(bottom=0.27, left=0.08, right=0.985, top=0.9)
    paper(ax, "Što ako je trgovanje skuplje: trošak 1x, 2x i 3x")
    x = np.arange(len(ids))
    w = 0.27
    for i, (key, lab, col) in enumerate(
        (
            ("povrat_ukupno_pct", "1x (2,5 baznih bodova po strani)", "#9fb3d9"),
            ("povrat_trosak_2x_pct", "2x (5)", INK),
            ("povrat_trosak_3x_pct", "3x (7,5)", "#0b1f6b"),
        )
    ):
        ax.bar(
            x + (i - 1) * w,
            [t[k][key] for k in ids],
            w,
            color=col,
            edgecolor=PENCIL,
            lw=0.7,
            hatch=["//", "..", "xx"][i],
            alpha=0.85,
            label=lab,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([NAMES[k].replace(" ", "\n", 1) for k in ids], fontsize=9)
    ax.set_ylabel("ukupni povrat u AI eri (%)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    ax.legend(frameon=True, facecolor=PAPER, edgecolor=GRID, fontsize=9.5, loc="upper center", bbox_to_anchor=(0.5, 1.0))
    k7 = t["K7_C13C_PLUS_TREND_REENTRY"]
    i7 = ids.index("K7_C13C_PLUS_TREND_REENTRY")
    loss7 = k7["povrat_ukupno_pct"] - k7["povrat_trosak_3x_pct"]
    k1 = t["K1_C13C_ORIG"]
    i1 = ids.index("K1_C13C_ORIG")
    hand(
        ax,
        f"najviše osjetljiv: {NAMES['K7_C13C_PLUS_TREND_REENTRY']}\n({k7['broj_poslova']} poslova): trošak 3x uzme\n{num(loss7, 0)} postotnih bodova = {eur(10 * loss7)} na 1.000 EUR",
        (i7 + w, k7["povrat_trosak_3x_pct"] + 15),
        (0.40, 0.42),
        color=RED,
        rad=-0.2,
        size=10,
        frac=True,
    )
    hand(
        ax,
        f"držanje: skoro bez razlike\n({num(t['B0_BUYHOLD']['povrat_ukupno_pct'], 0)} % -> {num(t['B0_BUYHOLD']['povrat_trosak_3x_pct'], 0)} %)\njer ima samo 8 kupnji",
        (0 + w, t["B0_BUYHOLD"]["povrat_trosak_3x_pct"] + 15),
        (0.13, 0.66),
        color=PENCIL,
        rad=0.2,
        size=10,
        frac=True,
    )
    ax.set_ylim(0, max(t[k]["povrat_ukupno_pct"] for k in ids) * 1.12)
    teacher(
        fig,
        "svaka kupnja i prodaja nešto košta. Baza je 2,5 baznih bodova po strani (0,025 %: na 1.000 EUR to je 0,25 EUR). Provjeravamo ostaje li pravilo dobro kad je trošak dvostruko i trostruko veći. Stupci koji se jedva mijenjaju rijetko trguju; oni koji se smanje trguju često.",
    )
    fig.savefig(d.out / "06_troskovi.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "06_troskovi.png"


# ---------------------------------------------------------------- 7 lesson
def chart_lesson(d: Data) -> str:
    rows = d.analysis["C13C_iskreno"]["po_dionici"]
    ts = d.tickers
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.0), sharey=True)
    fig.subplots_adjust(bottom=0.22, left=0.075, right=0.985, top=0.9, wspace=0.07)
    paper(a1, "Završno stanje od 1.000 EUR")
    paper(a2, "Najgori gubitak na 1.000 EUR")
    y = np.arange(len(ts))
    h = 0.38
    hv = [rows[t]["drzanje"]["za_1000_EUR_na_kraju"] for t in ts]
    kv = [rows[t]["K1"]["za_1000_EUR_na_kraju"] for t in ts]
    a1.barh(y - h / 2, hv, h, color=GREY, edgecolor=PENCIL, hatch="..", alpha=0.8, label="kupi i drži")
    a1.barh(y + h / 2, kv, h, color=INK, edgecolor=PENCIL, hatch="//", alpha=0.85, label="C13C")
    a1.set_yticks(y)
    a1.set_yticklabels(ts, fontsize=11)
    a1.invert_yaxis()
    for yi, v1, v2 in zip(y, hv, kv):
        a1.text(v1 + 250, yi - h / 2, eur(v1), va="center", fontsize=8.8, color=GREY)
        a1.text(v2 + 250, yi + h / 2, eur(v2), va="center", fontsize=8.8, color=INK)
    a1.set_xlim(0, max(hv) * 1.28)
    a1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    a1.legend(loc="upper right", frameon=True, facecolor=PAPER, edgecolor=GRID, fontsize=9.5)
    hl = [rows[t]["drzanje"]["za_1000_EUR_najgori_pad_EUR"] for t in ts]
    kl = [rows[t]["K1"]["za_1000_EUR_najgori_pad_EUR"] for t in ts]
    a2.barh(y - h / 2, hl, h, color=GREY, edgecolor=PENCIL, hatch="..", alpha=0.8)
    a2.barh(y + h / 2, kl, h, color=INK, edgecolor=PENCIL, hatch="//", alpha=0.85)
    for yi, v1, v2 in zip(y, hl, kl):
        a2.text(v1 + 8, yi - h / 2, eur(v1), va="center", fontsize=8.8, color=GREY)
        a2.text(v2 + 8, yi + h / 2, eur(v2), va="center", fontsize=8.8, color=INK)
    a2.set_xlim(0, max(hl) * 1.3)
    li = ts.index("LITE")
    sm = ts.index("SMCI")
    ex = rows["LITE"]["K1"]["izlozenost_pct"]
    hand(
        a1,
        f"LITE: držanje {eur(hv[li])}, C13C samo {eur(kv[li])}.\nC13C je bio u poziciji {num(ex, 0)} % vremena,\npropustio je veliki trend",
        (kv[li] + 2300, li + h / 2),
        (0.42, 0.655),
        color=RED,
        rad=0.3,
        size=9.6,
        frac=True,
    )
    hand(
        a1,
        f"SMCI: gotovo isto\n({eur(hv[sm])} naspram {eur(kv[sm])})\na najgori gubitak upola manji",
        (kv[sm] + 2400, sm + h / 2),
        (0.60, 0.32),
        color=GREEN,
        rad=-0.25,
        size=9.6,
        frac=True,
    )
    teacher(
        fig,
        "C13C je na svih osam dionica smanjio najgori gubitak (desno), ali ni na jednoj nije zaradio više od držanja (lijevo). To je osiguranje: plaćaš ga propuštenom zaradom. Gdje dionica ima veliku zaradu i dubok pad (SMCI), osiguranje je gotovo besplatno.",
    )
    fig.savefig(d.out / "07_pouka_osiguranje.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "07_pouka_osiguranje.png"


# ---------------------------------------------------------------- B1 dip forward
def chart_dip(d: Data) -> str:
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 5.6))
    fig.subplots_adjust(bottom=0.3, left=0.07, right=0.985, top=0.88, wspace=0.18)
    ts = d.tickers
    x = np.arange(len(ts))
    for ax, h, ttl in ((axs[0], "fwd5", "5 dana nakon pada"), (axs[1], "fwd20", "20 dana nakon pada")):
        paper(ax, f"Prosječni povrat {ttl}")
        ev, base, small = [], [], []
        for t in ts:
            p = d.prof[(t, "ai_era")]["after_5d_drop_ge5pct_above_sma200"]
            ev.append(p[h]["mean_pct"])
            base.append(p[h]["uncond_mean_pct"])
            small.append(p["independent_events"] < 15 or p["small_sample_warning"])
        for i in range(len(ts)):
            ax.bar(x[i] - 0.2, ev[i], 0.38, color=INK, alpha=0.5 if small[i] else 0.85, edgecolor=PENCIL, hatch="//", lw=0.8)
            ax.bar(x[i] + 0.2, base[i], 0.38, color=GREY, alpha=0.7, edgecolor=PENCIL, hatch="..", lw=0.8)
            ax.text(x[i] - 0.2, ev[i] + 0.2, num(ev[i], 1), ha="center", fontsize=8, color=INK)
            ax.text(x[i] + 0.2, base[i] + 0.2, num(base[i], 1), ha="center", fontsize=8, color=GREY)
        ax.set_xticks(x)
        ax.set_xticklabels(ts, fontsize=10)
        ax.set_ylabel("prosječni povrat (%)")
        ax.axhline(0, color=PENCIL, lw=1)
    fig.legend(
        handles=[
            plt.Rectangle((0, 0), 1, 1, fc=INK, ec=PENCIL, hatch="//", alpha=0.85),
            plt.Rectangle((0, 0), 1, 1, fc=GREY, ec=PENCIL, hatch="..", alpha=0.7),
        ],
        labels=["nakon pada od 5 % u 5 dana (uz cijenu iznad SMA200)", "bilo koji običan dan"],
        fontsize=10,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.085),
        ncol=2,
    )
    li = ts.index("LITE")
    pl = d.prof[("LITE", "ai_era")]["after_5d_drop_ge5pct_above_sma200"]
    hand(
        axs[1],
        f"LITE: {pc(pl['fwd20']['mean_pct'])} nakon pada\nnaspram {pc(pl['fwd20']['uncond_mean_pct'])} običnog dana.\nNa 1.000 EUR: {eur(10 * pl['fwd20']['mean_pct'])} naspram\n{eur(10 * pl['fwd20']['uncond_mean_pct'])} u 20 dana",
        (li - 0.2, pl["fwd20"]["mean_pct"]),
        (0.03, 0.80),
        color=RED,
        rad=0.2,
        size=9.6,
        frac=True,
    )
    worse = [
        t
        for t in ts
        if d.prof[(t, "ai_era")]["after_5d_drop_ge5pct_above_sma200"]["fwd5"]["mean_pct"]
        < d.prof[(t, "ai_era")]["after_5d_drop_ge5pct_above_sma200"]["fwd5"]["uncond_mean_pct"]
    ]
    pw = d.prof[(worse[0], "ai_era")]["after_5d_drop_ge5pct_above_sma200"]
    hand(
        axs[0],
        f"{', '.join(worse)}: nakon pada\nčak slabije od običnog dana",
        (ts.index(worse[0]) - 0.2, pw["fwd5"]["mean_pct"] + 0.5),
        (0.03, 0.80),
        color=PENCIL,
        rad=0.3,
        size=9.6,
        frac=True,
    )
    teacher(
        fig,
        "provjeravamo temelj C13C-a: je li kupnja nakon naglog pada bolja od običnog dana? Plavi stupac iznad sivog = da. Blijedi plavi stupci imaju malo događaja (manje od 15) pa im ne vjeruj previše.",
    )
    fig.savefig(d.out / "08_pad_pa_povrat.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "08_pad_pa_povrat.png"


# ---------------------------------------------------------------- B2 seasonality
def chart_season(d: Data) -> str:
    ts = d.tickers
    mons = ["sij", "velj", "ožu", "tra", "svi", "lip", "srp", "kol", "ruj", "lis", "stu", "pro"]
    mat = np.full((len(ts), 12), np.nan)
    cnt = np.zeros((len(ts), 12), dtype=int)
    for i, t in enumerate(ts):
        s = d.prof[(t, "ai_era")]["seasonality_month"]
        for m in range(12):
            v = s.get(str(m + 1))
            if v:
                mat[i, m] = v["mean_pct"]
                cnt[i, m] = v["n_months"]
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    fig.subplots_adjust(bottom=0.25, left=0.07, right=0.80, top=0.9)
    paper(ax, "Mjeseci: prosječni povrat u tom kalendarskom mjesecu (AI era)")
    ax.grid(False)
    vmax = np.nanmax(np.abs(mat))
    ax.imshow(mat, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto", alpha=0.75)
    for i in range(len(ts)):
        for m in range(12):
            if not np.isnan(mat[i, m]):
                ax.text(m, i, num(mat[i, m], 0), ha="center", va="center", fontsize=9.5, color=PENCIL)
    ax.set_xticks(range(12))
    ax.set_xticklabels(mons)
    ax.set_yticks(range(len(ts)))
    ax.set_yticklabels(ts, fontsize=11)
    ax.tick_params(length=0)
    li, aug = ts.index("LITE"), 7
    ring(ax, aug, li, RED, 1500)
    ax.annotate(
        f"LITE u kolovozu: {pc(mat[li, aug], 1, True)}\nu svih {cnt[li, aug]} promatranih\nkolovoza = {eur(10 * mat[li, aug])}\nna 1.000 EUR.\nAli to je samo {cnt[li, aug]} mjeseca!",
        xy=(aug + 0.4, li),
        xytext=(1.03, 0.55),
        textcoords="axes fraction",
        fontsize=10,
        color=RED,
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.4, connectionstyle="arc3,rad=0.25"),
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.9),
    )
    ax.set_ylim(len(ts) - 0.4, -0.5)
    nmin, nmax = int(cnt[cnt > 0].min()), int(cnt.max())
    teacher(
        fig,
        f"broj u kućici = prosječni povrat tog mjeseca u %. Zeleno raste, crveno pada. Svaka kućica je prosjek od samo {nmin} do {nmax} mjeseci (tri i pol godine podataka), što je premalo da bi se na to oslonio. Sezonski obrazac je ovdje zanimljivost, ne pravilo.",
    )
    fig.savefig(d.out / "09_sezonalnost.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "09_sezonalnost.png"


# ---------------------------------------------------------------- B3 drawdown anatomy
def chart_anatomy(d: Data) -> str:
    ts = d.tickers
    fig, axs = plt.subplots(4, 2, figsize=(11.5, 15.0))
    fig.subplots_adjust(bottom=0.085, left=0.07, right=0.985, top=0.965, hspace=0.62, wspace=0.18)
    for ax, t in zip(axs.flat, ts):
        bars = load_bars(t)
        s = pd.Series(bars.close, index=bars.dates)
        s = s[s.index >= pd.Timestamp(AI_ERA_START)]
        idx = s / float(s.iloc[0]) * 1000
        wd = d.prof[(t, "ai_era")]["worst_drawdowns"][0]
        top, bot = pd.Timestamp(wd["start"]), pd.Timestamp(wd["bottom"])
        rec = pd.Timestamp(wd["recovery"]) if wd.get("recovery") else None
        paper(ax, f"{t}: najgori pad {pc(wd['depth_pct'], 1)}")
        ax.title.set_fontsize(11.5)
        ax.plot(idx.index, idx, color=INK, lw=1.2)
        ax.set_yscale("log")
        ticks = [v for v in (300, 500, 1000, 2000, 5000, 10000, 20000) if idx.min() * 0.8 <= v <= idx.max() * 1.2]
        ax.set_yticks(ticks)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
        ax.yaxis.set_minor_formatter(plt.NullFormatter())
        ax.axvspan(top, bot, color="#f6d9d4", alpha=0.8, lw=0)
        if rec is not None:
            ax.axvspan(bot, rec, color="#dcf1e4", alpha=0.8, lw=0)
        yt, yb = float(idx.loc[top]), float(idx.loc[bot])
        ring(ax, bot, yb, RED, 300)
        rec_txt = f"oporavak {short_day(rec)}" if rec is not None else "do 5. 10. 2026. nije oporavljen"
        ax.text(
            0.02,
            0.97,
            f"vrh {short_day(top)} -> dno {short_day(bot)}\n"
            f"1.000 EUR na vrhu -> {eur(1000 * (1 + wd['depth_pct'] / 100))} na dnu\n{rec_txt}"
            + (f" ({wd['days_to_recover']} dana)" if rec is not None else ""),
            transform=ax.transAxes,
            fontsize=8.6,
            color=RED,
            va="top",
            bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.85),
        )
        date_axis(ax)
        ax.tick_params(labelsize=8)
    teacher(
        fig,
        "crvena traka = padanje od vrha do dna, zelena = vrijeme do povratka na stari vrh. Os pokazuje što bi postalo od 1.000 EUR uloženih na početku AI ere (ili na dan uvrštenja). Gledaj koliko traju zelene trake: pad se ne boli samo dubinom nego i čekanjem.",
    )
    fig.savefig(d.out / "10_anatomija_pada.png", dpi=115, facecolor=PAPER)
    plt.close(fig)
    return "10_anatomija_pada.png"


# ---------------------------------------------------------------- B4 together
def chart_together(d: Data) -> str:
    ts = d.tickers
    a, b = pd.Timestamp("2024-12-02"), pd.Timestamp("2025-09-30")
    fig, ax = plt.subplots(figsize=(11.5, 6.0))
    fig.subplots_adjust(bottom=0.19, left=0.075, right=0.985, top=0.9)
    paper(ax, "Svih osam zajedno: veljača do travnja 2025.")
    bottoms: dict[str, pd.Timestamp] = {}
    norm: dict[str, pd.Series] = {}
    ref_day = pd.Timestamp("2025-01-22")
    for i, t in enumerate(ts):
        bars = load_bars(t)
        s_ = pd.Series(bars.close, index=bars.dates)
        w_ = s_[(s_.index >= a) & (s_.index <= b)]
        base_s = float(s_.loc[ref_day]) if ref_day in s_.index else float(w_.iloc[0])
        norm[t] = w_ / base_s * 100
        ax.plot(norm[t].index, norm[t], color=PALETTE[i], lw=1.5, label=t)
        sub = w_[(w_.index >= ref_day) & (w_.index <= pd.Timestamp("2025-06-30"))]
        bottoms[t] = sub.idxmin()
    ax.axvline(pd.Timestamp("2025-04-04"), color=RED, ls="--", lw=1.3)
    ax.axhline(100, color=PENCIL, lw=1)
    same = [t for t in ts if abs((bottoms[t] - pd.Timestamp("2025-04-04")).days) <= 4]
    ax.legend(ncol=4, fontsize=9, frameon=True, facecolor=PAPER, edgecolor=GRID, loc="upper right")
    ax.set_ylim(-35, 215)
    hand(
        ax,
        f"{len(same)} od {len(ts)} dionica ima dno u istom tjednu\n(4. do 8. 4. 2025.): {', '.join(same)}.\nRaznolikost unutar skupine ne štiti\nkad dođe zajednički šok.",
        (pd.Timestamp("2025-04-04"), float(norm[same[0]].loc[bottoms[same[0]]]) - 3),
        (0.50, 0.10),
        color=RED,
        rad=-0.15,
        size=10,
        frac=True,
    )
    others = [t for t in ts if t not in same]
    for o in others:
        hand(
            ax,
            f"{o}: dno {short_day(bottoms[o])},\nu drugo vrijeme",
            (bottoms[o], float(norm[o].loc[bottoms[o]])),
            (0.08, 0.10),
            color=PENCIL,
            rad=0.2,
            size=9.5,
            frac=True,
        )
    ax.set_ylabel("cijena, 22. 1. 2025. = 100")
    date_axis(ax)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%Y."))
    teacher(
        fig,
        "svaka crta je jedna dionica, sve počinju na 100 dana 22. 1. 2025. Padne li 100 na 50, 1.000 EUR u toj dionici postane 500 EUR. Ako sve crte padaju u isto vrijeme, držanje osam dionica nije osam odvojenih oklada nego jedna velika oklada na istu stvar.",
    )
    fig.savefig(d.out / "11_zajednicki_pad.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "11_zajednicki_pad.png"


# ---------------------------------------------------------------- B5/B6 support resistance
def sr_events_with_levels(df: pd.DataFrame, kind: str) -> list[dict[str, Any]]:
    """Same first-touch logic as ``profile_stats.sr_events`` but keeps the level and its pivot bar."""
    from lab.aichain.profile_stats import (
        PIVOT_K,
        SR_BAND,
        SR_LOOKAHEAD,
        SR_MAX_AGE,
        pivots,
    )

    c, lo, hi = df["close"].to_numpy(), df["low"].to_numpy(), df["high"].to_numpy()
    n = len(c)
    plows, phighs = pivots(lo, hi)
    out: list[dict[str, Any]] = []
    for p in plows if kind == "support" else phighs:
        lvl = lo[p] if kind == "support" else hi[p]
        for t in range(p + PIVOT_K + 1, min(n - SR_LOOKAHEAD - 1, p + SR_MAX_AGE)):
            if kind == "support":
                if c[t] < lvl * (1 - SR_BAND):
                    break
                if lo[t] <= lvl * (1 + SR_BAND) and c[t - 1] > lvl * (1 + SR_BAND):
                    broke = bool((c[t : t + SR_LOOKAHEAD + 1] < lvl * (1 - SR_BAND)).any())
                    out.append({"t": t, "p": p, "lvl": float(lvl), "broke": broke, "fwd5": c[t + SR_LOOKAHEAD] / c[t] - 1})
                    break
            else:
                if c[t] > lvl * (1 + SR_BAND):
                    break
                if hi[t] >= lvl * (1 - SR_BAND) and c[t - 1] < lvl * (1 - SR_BAND):
                    broke = bool((c[t : t + SR_LOOKAHEAD + 1] > lvl * (1 + SR_BAND)).any())
                    out.append({"t": t, "p": p, "lvl": float(lvl), "broke": broke, "fwd5": c[t + SR_LOOKAHEAD] / c[t] - 1})
                    break
    return out


def chart_sr_rates(d: Data) -> str:
    ts = d.tickers
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    fig.subplots_adjust(bottom=0.25, left=0.07, right=0.985, top=0.9)
    paper(ax, "Drže li potpora i otpor? Udio dodira koji su održali razinu")
    x = np.arange(len(ts))
    sup, res, ns, nr = [], [], [], []
    for t in ts:
        sr = d.prof[(t, "ai_era")]["support_resistance"]
        sup.append(sr["support"]["hold_rate_pct"])
        res.append(sr["resistance"]["hold_rate_pct"])
        ns.append(sr["support"]["touches"])
        nr.append(sr["resistance"]["touches"])
    ax.bar(x - 0.2, sup, 0.38, color=GREEN, alpha=0.75, edgecolor=PENCIL, hatch="//", label="potpora (dno na koje cijena naiđe)")
    ax.bar(x + 0.2, res, 0.38, color=RED, alpha=0.65, edgecolor=PENCIL, hatch="..", label="otpor (vrh na koji cijena naiđe)")
    for i in range(len(ts)):
        ax.text(x[i] - 0.2, sup[i] + 1, f"{num(sup[i], 0)} %\n({ns[i]})", ha="center", fontsize=8, color=GREEN)
        ax.text(x[i] + 0.2, res[i] + 1, f"{num(res[i], 0)} %\n({nr[i]})", ha="center", fontsize=8, color=RED)
    ax.axhline(50, color=PENCIL, ls="--", lw=1.3)
    ax.text(-0.45, 51.5, "50 %: bacanje novčića", fontsize=9, color=PENCIL, ha="left")
    ax.set_xticks(x)
    ax.set_xticklabels(ts, fontsize=10.5)
    ax.set_ylim(0, 85)
    ax.set_ylabel("razina održana (%)")
    ax.legend(fontsize=9, frameon=True, facecolor=PAPER, edgecolor=GRID, loc="upper left")
    hi_i = int(np.argmax(sup))
    hand(
        ax,
        f"{ts[hi_i]}: potpora održala u {num(sup[hi_i], 0)} % dodira",
        (x[hi_i] - 0.2, sup[hi_i] + 8),
        (x[hi_i] - 3.4, 77),
        color=GREEN,
        rad=-0.2,
        size=9.6,
    )
    teacher(
        fig,
        "'održala' znači: u idućih 5 dana zatvaranje nije probilo razinu za više od 1,5 %. U zagradi je broj dodira. Ispod 50 % je razina češće probijena nego održana. Ovo je opis, ne dokaz da se na tome može zaraditi.",
    )
    fig.savefig(d.out / "12_potpora_otpor_udio.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "12_potpora_otpor_udio.png"


def chart_sr_examples(d: Data) -> str:
    t = SR_PICK[d.segment]
    raw = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv")
    raw["date"] = pd.to_datetime(raw["date"].astype(str).str[:10])
    df = raw.drop_duplicates("date").sort_values("date").set_index("date")[["open", "high", "low", "close"]].astype(float)
    df = df[df.index <= pd.Timestamp("2026-10-05")]
    ev = sr_events_with_levels(df, "support")
    ev = [e for e in ev if df.index[e["t"]] >= pd.Timestamp(AI_ERA_START)]
    # window of ~9 months with the most touches
    best, best_n = None, -1
    for start in pd.date_range("2023-02-01", "2026-01-01", freq="MS"):
        end = start + pd.DateOffset(months=9)
        n = sum(1 for e in ev if start <= df.index[e["t"]] <= end)
        if n > best_n:
            best, best_n = (start, end), n
    start, end = best
    w = df[(df.index >= start - pd.Timedelta(days=60)) & (df.index <= end + pd.Timedelta(days=15))]
    sel = [e for e in ev if start <= df.index[e["t"]] <= end]
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    fig.subplots_adjust(bottom=0.2, left=0.07, right=0.985, top=0.9)
    paper(ax, f"{t}: kako je cijena reagirala kad je dotaknula potporu")
    ax.plot(w.index, w["close"], color=INK, lw=1.4)
    date_axis(ax)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    held = [e for e in sel if not e["broke"]]
    broke = [e for e in sel if e["broke"]]
    for e in sel:
        td = df.index[e["t"]]
        pd_ = df.index[e["p"]]
        ax.hlines(e["lvl"], pd_, min(td + pd.Timedelta(days=12), w.index[-1]), color=GREEN if not e["broke"] else RED, lw=1.2, ls=":")
        ax.scatter([td], [e["lvl"]], s=70, marker="o", facecolors="none" if e["broke"] else GREEN, edgecolors=RED if e["broke"] else GREEN, lw=1.8, zorder=6)
        if e["broke"]:
            ax.scatter([td], [e["lvl"]], s=60, marker="x", color=RED, zorder=7)
    ymin, ymax = float(w["close"].min()), float(w["close"].max())
    ax.set_ylim(ymin * 0.88, ymax * 1.08)
    hx = held[0] if held else None
    bx = broke[0] if broke else None
    if hx:
        td = df.index[hx["t"]]
        c5 = float(df["close"].iloc[hx["t"] + 5])
        hand(
            ax,
            f"potpora držala ({short_day(td)}):\nrazina {usd(hx['lvl'])}, 5 dana poslije\nzatvaranje {usd(c5)}: {pc(hx['fwd5'] * 100, 1, True)}\n(na 1.000 EUR: {eur(1000 * hx['fwd5'])})",
            (td, hx["lvl"]),
            (0.30, 0.07),
            color=GREEN,
            rad=0.2,
            size=9.4,
            frac=True,
        )
    if bx:
        td = df.index[bx["t"]]
        c5 = float(df["close"].iloc[bx["t"] + 5])
        hand(
            ax,
            f"potpora probijena ({short_day(td)}):\nrazina {usd(bx['lvl'])}, 5 dana poslije\nzatvaranje {usd(c5)}: {pc(bx['fwd5'] * 100, 1, True)}\n(na 1.000 EUR: {eur(1000 * bx['fwd5'])})",
            (td, bx["lvl"]),
            (0.22, 0.80),
            color=RED,
            rad=-0.2,
            size=9.4,
            frac=True,
        )
    ax.set_ylabel("USD")
    ax.set_xlim(w.index[0], w.index[-1] + pd.Timedelta(days=20))
    ax.legend(
        [
            Line2D([], [], marker="o", color=GREEN, lw=0, ms=8),
            Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor=RED, lw=0, ms=8),
        ],
        [f"potpora održala ({len(held)} u ovom prozoru)", f"potpora probijena ({len(broke)})"],
        loc="upper right",
        fontsize=9,
        frameon=True,
        facecolor=PAPER,
        edgecolor=GRID,
    )
    sr = d.prof[(t, "ai_era")]["support_resistance"]["support"]
    teacher(
        fig,
        f"točkasta crta je razina potpore (zadnje potvrđeno dno), krug je dan kad je cijena prvi put dotaknula razinu. Na cijelom AI razdoblju potpora je kod {t} održala u {num(sr['hold_rate_pct'], 0)} % od {sr['touches']} dodira. Ovdje je izrez od 9 mjeseci s najviše dodira.",
    )
    fig.savefig(d.out / "13_potpora_primjeri.png", dpi=125, facecolor=PAPER)
    plt.close(fig)
    return "13_potpora_primjeri.png"


ALL = [
    chart_price,
    chart_equity,
    chart_drawdown,
    chart_trades,
    chart_scoreboard,
    chart_costs,
    chart_lesson,
    chart_dip,
    chart_season,
    chart_anatomy,
    chart_together,
    chart_sr_rates,
    chart_sr_examples,
]


def main(segment: str) -> list[str]:
    d = Data(segment)
    names = []
    for fn in ALL:
        names.append(fn(d))
        print("chart", names[-1])
    return names


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "network_servers")
