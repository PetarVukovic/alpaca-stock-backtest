"""Notebook-style charts for one AICHAIN segment (squared paper, pencil, red teacher notes in Croatian).

Reads only existing result files (analysis.json, results/*.json) and the daily CSVs in data/ohlcv.
No new backtests are run here: every number drawn is copied or recomputed from those files.
The look reuses the helpers of ``lab.top10.charts`` (imported, not modified).

Run: .venv/bin/python lab/aichain/notebook_charts.py ai_chips_logic
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lab.top10.charts import (  # noqa: E402
    GREEN,
    GRID,
    INK,
    PAPER,
    PENCIL,
    RED,
    ring,
    sketch,
)

BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
ORANGE = "#d9822b"
PURPLE = "#7b4fa3"
ERA = pd.Timestamp("2023-01-01")
HOLD, C13, K7C = "B0_BUYHOLD", "K1_C13C_ORIG", "K7_C13C_PLUS_TREND_REENTRY"


# ---------------------------------------------------------------- formatting helpers


def hr(x: float, nd: int = 0) -> str:
    """Croatian number format: decimal comma, thousands dot."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def eur(x: float) -> str:
    return f"{hr(x)} EUR"


def dmy(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def iso_to_hr(text: str) -> str:
    """Rewrite every ISO date (2025-04-08) in a text as a Croatian date (8. 4. 2025.)."""
    return re.sub(r"(\d{4})-(\d{2})-(\d{2})", lambda m: f"{int(m[3])}. {int(m[2])}. {m[1]}.", text)


def wrap(text: str, width: int = 34) -> str:
    return "\n".join(textwrap.fill(p, width) for p in text.split("\n"))


# ---------------------------------------------------------------- drawing helpers


def sheet(ax: Any, title: str) -> None:
    ax.set_facecolor(PAPER)
    ax.grid(True, color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", pad=10, color=INK)


def say(
    ax: Any,
    text: str,
    xy: tuple[Any, float],
    at: tuple[float, float],
    color: str = RED,
    rad: float = 0.2,
    size: float = 10.5,
    width: int = 34,
    ha: str = "left",
) -> None:
    """Handwritten note at ``at`` (axes fraction) with a pencil arrow to ``xy`` (data coordinates)."""
    ann = ax.annotate(
        wrap(text, width),
        xy=xy,
        xycoords="data",
        xytext=at,
        textcoords="axes fraction",
        ha=ha,
        va="center",
        fontsize=size,
        color=color,
        bbox=dict(boxstyle="round,pad=0.3", fc=PAPER, ec="none", alpha=0.85),
        arrowprops=dict(
            arrowstyle="->",
            color=color,
            lw=1.4,
            connectionstyle=f"arc3,rad={rad}",
            shrinkB=3,
        ),
        zorder=9,
    )
    if ann.arrow_patch is not None:
        sketch(ann.arrow_patch, 0.9, 60, 3)


def free_note(
    ax: Any,
    text: str,
    at: tuple[float, float],
    color: str = RED,
    size: float = 10.5,
    width: int = 40,
) -> None:
    ax.text(
        at[0],
        at[1],
        wrap(text, width),
        transform=ax.transAxes,
        fontsize=size,
        color=color,
        va="center",
        bbox=dict(boxstyle="round,pad=0.3", fc=PAPER, ec="none", alpha=0.85),
        zorder=9,
    )


def teacher(fig: Any, text: str, width: int = 150) -> None:
    fig.text(
        0.012,
        0.008,
        wrap("Bilješka učitelja: " + text, width),
        fontsize=11,
        color=RED,
        ha="left",
        va="bottom",
    )


def era_line(ax: Any, y: float = 0.03) -> None:
    ax.axvline(ERA, color=RED, ls="--", lw=1.2)
    ax.text(
        ERA + pd.Timedelta(days=12),
        y,
        "od ovdje: AI era",
        transform=ax.get_xaxis_transform(),
        fontsize=9.5,
        color=RED,
    )


def date_axis(ax: Any) -> None:
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))


def eur_axis(ax: Any, axis: str = "y") -> None:
    fmt = FuncFormatter(lambda v, _: hr(v))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def save(fig: Any, out: Path, name: str) -> str:
    fig.savefig(out / name, dpi=125, facecolor=PAPER)
    plt.close(fig)
    return name


# ---------------------------------------------------------------- data access


class Data:
    """Everything the charts need, loaded once."""

    def __init__(self, segment: str) -> None:
        self.segment = segment
        self.dir = BASE / "segments" / segment
        self.a: dict[str, Any] = json.loads((self.dir / "analysis.json").read_text())
        self.tickers: list[str] = self.a["meta"]["tickeri"]
        self.seg: dict[str, Any] = json.loads(
            (BASE / "results" / f"{segment}.json").read_text()
        )
        self.res: dict[str, dict[str, Any]] = {
            t: json.loads((BASE / "results" / f"{t}.json").read_text())
            for t in self.tickers
        }
        self.n = len(self.tickers)
        self.names: dict[str, str] = {
            "B0_BUYHOLD": "držanje",
            "K1_C13C_ORIG": "C13C (K1)",
            "K2_SMA200_TREND": "SMA200 trend (K2)",
            "K3_DONCHIAN_55_20": "Donchian 55/20 (K3)",
            "K4_TSMOM_126": "126-dnevni zamah (K4)",
            "K5_SUPPORT_RESISTANCE": "potpora/otpor (K5)",
            "K5B_SR_BREAKOUT_RETEST": "proboj i povratak (K5B)",
            "K6_MOMENTUM_CS": "rotacija zamaha (K6)",
            "K7_C13C_PLUS_TREND_REENTRY": "C13C + ponovni ulaz (K7)",
        }
        self.winner: str = self.a["pobjednik"]["pobjednik"]
        self._px: dict[str, pd.DataFrame] = {}

    def prices(self, t: str) -> pd.DataFrame:
        if t not in self._px:
            df = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv", parse_dates=["date"])
            self._px[t] = df.set_index("date").sort_index()
        return self._px[t]

    def sleeve_equity(self, c: str) -> pd.Series:
        """Average pocket of 1.000 EUR: segment equity divided by the number of pockets."""
        eq = self.seg["contenders"][c]["equity"]["ai_era"]
        s = pd.Series({pd.Timestamp(d): v for d, v in eq}) / self.n
        return s

    def trades(self, t: str, c: str = C13) -> list[dict[str, Any]]:
        return self.res[t]["contenders"][c]["trades"]["ai_era"]

    def row(self, c: str) -> dict[str, Any]:
        return self.a["tablica_segment_AI_era"]["suparnici"][c]

    def invested_fraction(self) -> pd.Series:
        idx = pd.bdate_range("2023-01-03", "2026-10-05")
        inpos = pd.DataFrame(0, index=idx, columns=self.tickers)
        for t in self.tickers:
            for x in self.trades(t):
                inpos.loc[pd.Timestamp(x["entry_date"]) : pd.Timestamp(x["exit_date"]), t] = 1
        return inpos.sum(axis=1) / self.n


def c13c_stop_path(df: pd.DataFrame, tr: dict[str, Any]) -> pd.Series:
    """Replicate the trailing stop of K1 (10 % below the known peak, cents, never lowered) for one trade."""
    ent, ex = pd.Timestamp(tr["entry_date"]), pd.Timestamp(tr["exit_date"])
    win = df.loc[ent:ex]
    peak = float(tr["entry_price"])
    stop = round(peak * 0.9, 2)
    out = {}
    for d, row in win.iterrows():
        out[d] = stop
        peak = max(peak, float(row["high"]))
        stop = max(stop, round(peak * 0.9, 2))
    return pd.Series(out)


def demo_trade(d: Data, t: str = "NVDA") -> dict[str, Any]:
    """Pick the long, profitable C13C trade used as the worked example and recompute its signal day.

    Shared by the NVDA panel of chart 1 and the page text, so both quote the same numbers.
    """
    df = d.prices(t)
    c = df["close"]
    sma = c.rolling(200).mean()
    trs = d.trades(t)
    ymax = float(c.loc[ERA:].max())
    cand = [x for x in trs if x["return"] > 0 and x["bars_held"] >= 40 and x["raw_entry"] >= 0.35 * ymax]
    tr = max(cand, key=lambda x: x["bars_held"])
    sig = df.index[df.index.get_loc(pd.Timestamp(tr["entry_date"])) - 1]
    r5 = float(c.loc[sig] / c.shift(5).loc[sig] - 1)
    assert r5 <= -0.05 and c.loc[sig] > sma.loc[sig], (sig, r5)
    peak = float(df.loc[pd.Timestamp(tr["entry_date"]) : pd.Timestamp(tr["exit_date"]), "high"].max())
    return {
        "trade": tr,
        "signal_date": sig,
        "ret5": r5,
        "close_signal": float(c.loc[sig]),
        "close_5_before": float(c.shift(5).loc[sig]),
        "sma200": float(sma.loc[sig]),
        "peak": peak,
        "first_stop": float(c13c_stop_path(df, tr).iloc[0]),
    }


# ---------------------------------------------------------------- chart 1: price + trades


def chart_price(d: Data, out: Path) -> str:
    picks = ["NVDA", "AMD", "INTC"]
    fig, axes = plt.subplots(3, 1, figsize=(12.5, 14.2), sharex=False)
    fig.subplots_adjust(top=0.96, bottom=0.095, left=0.07, right=0.985, hspace=0.3)
    tl = {t: d.a["kartice"][t] for t in picks}
    for ax, t in zip(axes, picks):
        df = d.prices(t)
        c = df["close"]
        sma = c.rolling(200).mean()
        win = c.loc[ERA:]
        sheet(ax, f"{t}: cijena, prosjek SMA200 i svi ulazi/izlazi C13C")
        sketch(ax.plot(win.index, win.values, color=INK, lw=1.5, label="cijena (zatvaranje)")[0], 0.7, 70, 2)
        ax.plot(sma.loc[ERA:].index, sma.loc[ERA:].values, color=ORANGE, lw=1.4, ls="--", label="SMA200")
        trs = d.trades(t)
        ax.scatter([pd.Timestamp(x["entry_date"]) for x in trs], [x["raw_entry"] for x in trs],
                   marker="^", s=58, color=GREEN, zorder=6, label=f"kupnja ({len(trs)})")
        stops = [x for x in trs if x["reason"] == "stop"]
        ax.scatter([pd.Timestamp(x["exit_date"]) for x in stops], [x["raw_exit"] for x in stops],
                   marker="v", s=58, color=RED, zorder=6, label="izlaz stopom")
        ends = [x for x in trs if x["reason"] != "stop"]
        if ends:
            ax.scatter([pd.Timestamp(x["exit_date"]) for x in ends], [x["raw_exit"] for x in ends],
                       marker="s", s=40, color=PURPLE, zorder=6, label="kraj razdoblja")
        era_line(ax)
        date_axis(ax)
        ax.set_ylabel("cijena u USD")
        if t == "INTC":
            ax.legend(loc="upper left", bbox_to_anchor=(0.36, 1.0), fontsize=9, frameon=True, facecolor=PAPER, edgecolor="none", ncol=4)
        else:
            ax.legend(loc="lower right", fontsize=9, frameon=True, facecolor=PAPER, edgecolor="none", ncol=2)
        ymax = float(win.max())
        ax.set_ylim(float(win.min()) * 0.8, ymax * 1.08)
        if t == "NVDA":
            demo = demo_trade(d, t)
            tr, sig, r5 = demo["trade"], demo["signal_date"], demo["ret5"]
            sp = c13c_stop_path(df, tr)
            ax.plot(sp.index, sp.values, color=RED, lw=2.2, drawstyle="steps-post", zorder=7)
            say(ax, f"SIGNAL za kupnju, {dmy(sig)}: cijena je za 5 dana pala {hr(abs(r5) * 100, 1)} %, "
                    f"a još je iznad SMA200. Sutradan kupujem po {hr(tr['raw_entry'], 2)} USD "
                    f"(100 EUR bi kupilo oko {hr(100 / tr['raw_entry'], 2)} dionice).",
                xy=(pd.Timestamp(tr["entry_date"]), tr["raw_entry"]), at=(0.30, 0.72), width=46, rad=0.15)
            mid = sp.index[int(len(sp) * 0.75)]
            say(ax, f"Crvena stepenica je STOP: uvijek 10 % ispod najvišeg vrha, raste s cijenom, nikad ne pada. "
                    f"Izlaz {dmy(tr['exit_date'])} po {hr(tr['raw_exit'], 2)} USD: {hr(tr['return'] * 100, 1)} % dobiti "
                    f"(1.000 EUR postaje {eur(1000 * (1 + tr['return']))}).",
                xy=(mid, float(sp.loc[mid])), at=(0.60, 0.38), width=46, rad=-0.15)
            gap = pd.Timestamp("2023-05-25")
            say(ax, f"Jaz preko noći +26,1 %: zatvaranje {hr(c.loc['2023-05-24'], 2)}, sljedeće jutro "
                    f"otvaranje {hr(df.loc[gap, 'open'], 2)} USD. Takav skok ne možeš ni kupiti ni zaštititi.",
                xy=(gap, float(df.loc[gap, "open"])), at=(0.02, 0.55), width=32, rad=0.1)
            bad = [x for x in trs if x["detail"] == "gap_stop"]
            if bad:
                w = min(bad, key=lambda x: x["return"])
                say(ax, f"Najgori izlaz ({dmy(w['exit_date'])}): {hr(w['return'] * 100, 1)} %. "
                        "Dionica je otvorila ispod stopa, pa se izlazi po lošijoj cijeni.",
                    xy=(pd.Timestamp(w["exit_date"]), w["raw_exit"]), at=(0.07, 0.86), width=40, rad=0.1)
        elif t == "AMD":
            peak_d, bot_d = pd.Timestamp("2024-03-07"), pd.Timestamp("2025-04-08")
            dd0 = tl["AMD"]["najgori_padovi"][0]
            say(ax, f"Držanje: od {dmy(peak_d)} ({hr(c.loc[peak_d], 2)} USD) do {dmy(bot_d)} "
                    f"({hr(c.loc[bot_d], 2)} USD) pad {hr(dd0['dubina_pct'], 1)} %: "
                    f"1.000 EUR bi pao na oko {hr(dd0['iz_1000_eur_na'])} EUR.",
                xy=(bot_d, float(c.loc[bot_d])), at=(0.26, 0.60), width=44, rad=0.1)
            flat_from = max((pd.Timestamp(x["exit_date"]) for x in trs if pd.Timestamp(x["exit_date"]) <= pd.Timestamp("2025-02-01")), default=None)
            nxt = min((pd.Timestamp(x["entry_date"]) for x in trs if pd.Timestamp(x["entry_date"]) > pd.Timestamp("2025-02-01")), default=None)
            if flat_from is not None and nxt is not None:
                mid = flat_from + (nxt - flat_from) / 2
                ax.axvspan(flat_from, nxt, color="#fde8e4", alpha=0.7, lw=0, zorder=0)
                say(ax, f"Ružičasto, od {dmy(flat_from)} do {dmy(nxt)}: C13C nema nijednu poziciju (cijena je {hr(100 * float((c.loc[flat_from:nxt] <= sma.loc[flat_from:nxt]).mean()))} % tih dana ispod SMA200). "
                        "Izbjegao je dio pada (štedi), ali ne sudjeluje ni u oporavku.",
                    xy=(mid, float(c.asof(mid))), at=(0.12, 0.84), width=50, rad=-0.1)
        else:
            best = max(trs, key=lambda x: x["return"])
            ex = pd.Timestamp(best["exit_date"])
            say(ax, f"Najbolji posao cijelog segmenta: kupnja {dmy(best['entry_date'])} po "
                    f"{hr(best['raw_entry'], 2)} USD, izlaz {dmy(best['exit_date'])} po "
                    f"{hr(best['raw_exit'], 2)} USD = {hr(best['return'] * 100, 1)} %. "
                    f"Iz 1.000 EUR to je {eur(1000 * (1 + best['return']))}.",
                xy=(ex, best["raw_exit"]), at=(0.10, 0.82), width=46, rad=-0.1)
            low = pd.Timestamp("2025-04-08")
            say(ax, f"Ista dionica na dnu {dmy(low)}: {hr(c.loc[low], 2)} USD. Držanje je prošlo pad "
                    f"od {hr(abs(tl['INTC']['najgori_padovi'][0]['dubina_pct']), 1)} %.",
                xy=(low, float(c.loc[low])), at=(0.22, 0.52), width=40, rad=0.1)
    teacher(fig, "zeleni trokut gore = kupnja, crveni trokut dolje = izlaz stopom (stop je automatska prodaja ako cijena "
                 "padne 10 % ispod vrha). Narančasta crtkana crta je SMA200 (prosjek zadnjih 200 zatvaranja): "
                 "C13C kupuje samo kad je cijena IZNAD nje. Trošak je 0,025 % po strani (na 1.000 EUR to je 0,25 EUR).", width=135)
    return save(fig, out, "01_cijena_c13c.png")


# ---------------------------------------------------------------- chart 2: equity


def chart_equity(d: Data, out: Path) -> str:
    hold, k1, win = d.sleeve_equity(HOLD), d.sleeve_equity(C13), d.sleeve_equity(d.winner)
    fig, ax = plt.subplots(figsize=(12.5, 7.6))
    fig.subplots_adjust(top=0.93, bottom=0.17, left=0.08, right=0.985)
    sheet(ax, "1.000 EUR u svakoj od 11 dionica: koliko je ostalo na kraju")
    frac = d.invested_fraction()
    # longest stretch in which C13C held (almost) nothing
    low = (frac <= 0.1).astype(int)
    best_n, best_span, cur, st = 0, (None, None), 0, None
    for dt, v in low.items():
        if v:
            if cur == 0:
                st = dt
            cur += 1
            if cur > best_n:
                best_n, best_span = cur, (st, dt)
        else:
            cur = 0
    if best_span[0] is not None:
        ax.axvspan(best_span[0], best_span[1], color="#fde8e4", alpha=0.8, lw=0, zorder=0)
    ax.plot(hold.index, hold.values, color=INK, lw=2.2, label=f"držanje: {eur(hold.iloc[-1])}")
    ax.plot(win.index, win.values, color=GREEN, lw=2.0, label=f"{d.names[d.winner]}: {eur(win.iloc[-1])}")
    ax.plot(k1.index, k1.values, color=ORANGE, lw=2.0, label=f"C13C (K1): {eur(k1.iloc[-1])}")
    ax.axhline(1000, color=PENCIL, lw=1, ls=":")
    ax.text(hold.index[3], 1000 * 1.05, "uloženo: 1.000 EUR", fontsize=9.5, color=PENCIL)
    era_line(ax, 0.55)
    date_axis(ax)
    eur_axis(ax)
    ax.set_ylabel("vrijednost jednog pretinca od 1.000 EUR")
    ax.legend(loc="upper left", fontsize=11, frameon=True, facecolor=PAPER, edgecolor="none")
    a0, a1 = pd.Timestamp(d.row(HOLD)["najgori_pad_datumi"]["vrh"]), pd.Timestamp(d.row(HOLD)["najgori_pad_datumi"]["dno"])
    h0, h1 = hold.loc[a0], hold.loc[a1]
    k0, k1v = k1.loc[a0], k1.loc[a1]
    say(ax, f"Pad držanja {dmy(a0)} do {dmy(a1)}: s {eur(h0)} na {eur(h1)}, gubitak {eur(h0 - h1)}. "
            f"U istom razdoblju C13C: s {eur(k0)} na {eur(k1v)}, gubitak {eur(k0 - k1v)}, dakle "
            f"{eur((h0 - h1) - (k0 - k1v))} manje. Ali kasnije ne sudjeluje u oporavku.",
        xy=(a1, float(h1)), at=(0.40, 0.55), width=44, rad=0.25)
    if best_span[0] is not None:
        n_days = best_n
        mid = best_span[0] + (best_span[1] - best_span[0]) / 2
        say(ax, f"Ružičasto: oko {n_days} radnih dana (od {dmy(best_span[0])} do {dmy(best_span[1])}) C13C gotovo "
                "nigdje nije bio u dionicama. To je cijena zaštite: novac čeka u gotovini.",
            xy=(mid, float(k1.asof(mid))), at=(0.52, 0.23), width=42, rad=-0.25)
    end = hold.index[-1]
    say(ax, f"Kraj: držanje {eur(hold.iloc[-1])}, pobjednik po Sharpeu {eur(win.iloc[-1])}, C13C {eur(k1.iloc[-1])}. "
            "Nitko nije pobijedio držanje po prinosu.",
        xy=(end, float(hold.iloc[-1])), at=(0.60, 0.88), width=42, rad=-0.2, color=RED, ha="left")
    teacher(fig, f"ovo je prosjek jednog pretinca: 11 pretinaca po 1.000 EUR, zbroj podijeljen s 11 (npr. držanje "
                 f"{eur(d.row(HOLD)['konacna_vrijednost_EUR_od_11000'])} / 11 = {eur(hold.iloc[-1])}). "
                 "Bez poreza, tečaja EUR/USD i dividendi; cijene u USD tretirane kao EUR.")
    return save(fig, out, "02_kapital_1000eur.png")


# ---------------------------------------------------------------- chart 3: drawdown


def drawdown(eq: pd.Series) -> pd.Series:
    return eq / eq.cummax() - 1.0


def chart_drawdown(d: Data, out: Path) -> str:
    cs = [(HOLD, INK), (d.winner, GREEN), (C13, ORANGE)]
    fig, ax = plt.subplots(figsize=(12.5, 7.4))
    fig.subplots_adjust(top=0.93, bottom=0.16, left=0.08, right=0.985)
    sheet(ax, "Koliko je boljelo: pad od najboljeg trenutka")
    series = {}
    for c, col in cs:
        dd = drawdown(d.sleeve_equity(c)) * 100
        series[c] = dd
        ax.plot(dd.index, dd.values, color=col, lw=1.9, label=d.names[c])
        ax.fill_between(dd.index, dd.values, 0, color=col, alpha=0.07)
    ax.set_ylabel("pad od vrha u %")
    ax.set_ylim(min(s.min() for s in series.values()) * 1.18, 3)
    era_line(ax, 0.03)
    date_axis(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0.07, 0.0), fontsize=11, frameon=True, facecolor=PAPER, edgecolor="none")
    hd = series[HOLD]
    wd = hd.idxmin()
    r = d.row(HOLD)["najgori_pad_datumi"]
    peak_v = d.sleeve_equity(HOLD).loc[pd.Timestamp(r["vrh"])]
    say(ax, f"Najgori dan držanja: {dmy(wd)}, pad {hr(hd.min(), 1)} %. Od vrha {eur(peak_v)} ostaje "
            f"{eur(peak_v * (1 + hd.min() / 100))}: gubitak {eur(peak_v * -hd.min() / 100)} na papiru.",
        xy=(wd, float(hd.min())), at=(0.40, 0.22), width=44, rad=0.2)
    kd = series[C13]
    kk = kd.idxmin()
    kpeak = d.sleeve_equity(C13).cummax().loc[kk]
    say(ax, f"C13C: najgori dan {dmy(kk)}, {hr(kd.min(), 1)} %. Od vrha {eur(kpeak)} do "
            f"{eur(kpeak * (1 + kd.min() / 100))}.",
        xy=(kk, float(kd.min())), at=(0.05, 0.50), width=34, rad=-0.25)
    wd2 = series[d.winner]
    ww = wd2.idxmin()
    say(ax, f"{d.names[d.winner]}: {hr(wd2.min(), 1)} %, praktički isto kao držanje. "
            "Ta rotacija ne izlazi u gotovinu, samo zamjenjuje dionice.",
        xy=(ww, float(wd2.min())), at=(0.62, 0.42), width=36, rad=0.25)
    teacher(fig, "pad od 38,8 % na 1.000 EUR znači da u najgorem trenutku vrijedi oko 612 EUR. Pad je vidljiv samo "
                 "na papiru dok ne prodaš; pitanje je izdržiš li ga. Ovdje se pad ne ocjenjuje, samo se mjeri.")
    return save(fig, out, "03_pad_od_vrha.png")


# ---------------------------------------------------------------- chart 4: trades


def chart_trades(d: Data, out: Path) -> str:
    rows = []
    for t in d.tickers:
        for x in d.trades(t):
            rows.append({**x, "t": t})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(12.5, 7.6))
    fig.subplots_adjust(top=0.93, bottom=0.18, left=0.08, right=0.985)
    sheet(ax, f"Svih {len(df)} poslova C13C: koliko su trajali i koliko su donijeli")
    ok = df[df["detail"] == "stop"]
    gp = df[df["detail"] == "gap_stop"]
    en = df[df["reason"] == "end"]
    ax.scatter(ok["bars_held"], ok["return"] * 100, s=26, color=INK, alpha=0.55, label=f"izlaz stopom ({len(ok)})")
    ax.scatter(gp["bars_held"], gp["return"] * 100, s=34, color=RED, alpha=0.8, marker="X", label=f"izlaz s jazom preko noći ({len(gp)})")
    ax.scatter(en["bars_held"], en["return"] * 100, s=40, color=PURPLE, marker="s", label=f"kraj razdoblja ({len(en)})")
    ax.axhline(0, color=PENCIL, lw=1.3)
    ax.set_xlabel("koliko je radnih dana pozicija trajala")
    ax.set_ylabel("rezultat posla u %")
    ax.legend(loc="upper right", fontsize=10.5, frameon=True, facecolor=PAPER, edgecolor="none")
    best = df.loc[df["return"].idxmax()]
    worst = df.loc[df["return"].idxmin()]
    say(ax, f"Najbolji: {best['t']}, {dmy(best['entry_date'])} do {dmy(best['exit_date'])}, "
            f"{hr(best['return'] * 100, 1)} % u {int(best['bars_held'])} dana. 1.000 EUR postaje {eur(1000 * (1 + best['return']))}.",
        xy=(best["bars_held"], best["return"] * 100), at=(0.36, 0.86), width=42, rad=0.2)
    say(ax, f"Najgori: {worst['t']}, {dmy(worst['entry_date'])} do {dmy(worst['exit_date'])}, "
            f"{hr(worst['return'] * 100, 1)} % za samo {int(worst['bars_held'])} dana (jaz preko noći). 1.000 EUR postaje {eur(1000 * (1 + worst['return']))}.",
        xy=(worst["bars_held"], worst["return"] * 100), at=(0.10, 0.33), width=40, rad=0.15)
    wins = df[df["return"] > 0]
    loss = df[df["return"] <= 0]
    c = d.a["c13c_iskreno"]["segment"]["K1"]
    free_note(ax, f"Pogodak {hr(c['stopa_pogotka_pct'], 1)} %: dobitnih poslova {len(wins)} od {len(df)}. "
                  f"Prosječan dobitak {hr(c['prosjecni_dobitak_pct'], 1)} %, prosječan gubitak {hr(c['prosjecni_gubitak_pct'], 1)} %. "
                  "Dakle: češće se gubi, ali dobici su veći od gubitaka.",
              at=(0.50, 0.55), width=46)
    teacher(fig, "svaka točka je jedan posao, bilo koja od 11 dionica. Vodoravno: koliko dana si bio u poziciji; "
                 "okomito: koliko si zaradio ili izgubio. Crveni X su izlazi kad je dionica preko noći otvorila ispod stopa, "
                 "pa izlaz nije po 10 % nego lošije.")
    return save(fig, out, "04_poslovi_c13c.png")


# ---------------------------------------------------------------- chart 5: scoreboard


def chart_scoreboard(d: Data, out: Path) -> str:
    rows = d.a["tablica_segment_AI_era"]["suparnici"]
    cs = list(rows.keys())
    # three-decimal Sharpe from the winner ranking separates the near-tie K6/K2/K4
    sharpe = {c: float(rows[c]["sharpe"]) for c in cs}
    for q in d.a["pobjednik"]["kvalificirani_poredak_po_sharpeu"]:
        sharpe[q["suparnik"]] = float(q["sharpe"])
    order = sorted(cs, key=lambda c: -sharpe[c])
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 7.4), sharey=True)
    fig.subplots_adjust(top=0.86, bottom=0.2, left=0.2, right=0.985, wspace=0.08)
    labels = [d.names[c] for c in order]
    y = np.arange(len(order))[::-1]

    def colour(c: str) -> str:
        if c == HOLD:
            return INK
        if c == d.winner:
            return GREEN
        if c == C13:
            return ORANGE
        return "#9aa5b1" if rows[c]["prinos_trosak_2x_pct"] > 0 else RED

    panels = [
        (axes[0], [rows[c]["prinos_pct"] for c in order], "Prinos u AI eri (%)", " %", 1),
        (axes[1], [sharpe[c] for c in order], "Sharpe (veći je bolji)", "", 3),
    ]
    for ax, vals, title, sfx, nd in panels:
        sheet(ax, title)
        ax.barh(y, vals, color=[colour(c) for c in order], height=0.62, alpha=0.9)
        top = max(vals)
        for yy, v in zip(y, vals):
            if v >= 0:
                ax.text(v + top * 0.015, yy, hr(v, nd) + sfx, va="center", ha="left", fontsize=10.5)
            else:
                ax.text(top * 0.015, yy, hr(v, nd) + sfx, va="center", ha="left", fontsize=10.5, color=RED)
        ax.axvline(0, color=PENCIL, lw=1.2)
        ax.set_xlim(min(0, min(vals)) - top * 0.04, top * 1.25)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=11)
    sh = sharpe[HOLD]
    axes[1].axvline(sh, color=INK, ls=":", lw=1.4)
    say(axes[1], f"Isprekidana crta: Sharpe držanja ({hr(sh, 2)}). Nijedno pravilo je ne dostiže.",
        xy=(sh, y[4]), at=(0.60, 0.16), width=22, rad=0.2, size=10)
    wn = d.a["pobjednik"]
    say(axes[0], f"Zeleno: pobjednik po unaprijed zadanom pravilu, {wn['pobjednik_naziv']}, Sharpe {hr(sharpe[d.winner], 3)}. "
                 f"K2 ({hr(sharpe['K2_SMA200_TREND'], 3)}) i K4 ({hr(sharpe['K4_TSMOM_126'], 3)}) su praktički jednaki: razlika je šum.",
        xy=(rows[d.winner]["prinos_pct"], y[order.index(d.winner)]), at=(0.52, 0.38), width=34, rad=0.15, size=10)
    say(axes[0], "Narančasto: C13C. Prinos " + hr(rows[C13]["prinos_pct"], 1) + " % naprema držanju " + hr(rows[HOLD]["prinos_pct"], 1) + " %.",
        xy=(rows[C13]["prinos_pct"], y[order.index(C13)]), at=(0.42, 0.16), width=30, rad=0.2, size=10)
    teacher(fig, "poredak ide po Sharpeu (prinos u odnosu na treskanje cijene). Crveni stupac (potpora/otpor) ima negativan prinos "
                 "već uz dvostruki trošak, pa ne kvalificira. Plavo = držanje, kupiš i ne diraš: to je mjerilo, ne pravilo. "
                 "Probano je 9 pravila na 6 segmenata i 43 dionice (K=532): najbolji može izgledati dobro i slučajno.", width=140)
    fig.suptitle("Tko je radio najbolje u AI eri (2023. do 2026.)", x=0.02, y=0.985, ha="left", fontsize=15, fontweight="bold", color=INK)
    return save(fig, out, "05_ploca_suparnika.png")


# ---------------------------------------------------------------- chart 6: costs


def chart_costs(d: Data, out: Path) -> str:
    rows = d.a["tablica_segment_AI_era"]["suparnici"]
    order = [HOLD, "K2_SMA200_TREND", "K4_TSMOM_126", d.winner, C13, K7C, "K3_DONCHIAN_55_20", "K5B_SR_BREAKOUT_RETEST", "K5_SUPPORT_RESISTANCE"]
    order = list(dict.fromkeys(order))
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 7.0), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.subplots_adjust(top=0.92, bottom=0.27, left=0.07, right=0.985, wspace=0.12)
    ax, bx = axes
    sheet(ax, "Prinos uz običan, dvostruki i trostruki trošak (%)")
    x = np.arange(len(order))
    w = 0.27
    for i, (key, lab, col) in enumerate([("prinos_pct", "trošak 1x", INK), ("prinos_trosak_2x_pct", "trošak 2x", ORANGE), ("prinos_trosak_3x_pct", "trošak 3x", RED)]):
        ax.bar(x + (i - 1) * w, [rows[c][key] for c in order], w, color=col, alpha=0.85, label=lab)
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels([d.names[c].replace(" (", "\n(") for c in order], rotation=40, ha="right", fontsize=9.5)
    ax.legend(fontsize=10, frameon=True, facecolor=PAPER, edgecolor="none")
    sheet(bx, "Koliko postotnih bodova prinosa pojede trošak 3x")
    lost = [rows[c]["prinos_pct"] - rows[c]["prinos_trosak_3x_pct"] for c in order]
    bx.barh(np.arange(len(order))[::-1], lost, color=[RED if c in (C13, K7C) else "#9aa5b1" for c in order], height=0.6)
    for yy, v, c in zip(np.arange(len(order))[::-1], lost, order):
        bx.text(v + 0.15, yy, f"{hr(v, 1)} b.  ({rows[c]['poslova']} poslova)", va="center", fontsize=10)
    bx.set_yticks([])
    bx.set_xlim(0, max(lost) * 1.8)
    bx.grid(axis="y", visible=False)
    k7 = rows[K7C]
    free_note(bx, f"C13C+ (K7) trguje {k7['poslova']} puta pa gubi najviše: "
                  f"{hr(k7['prinos_pct'] - k7['prinos_trosak_3x_pct'], 1)} bodova. "
                  "Pravi minimum provizije kod IBKR-a (nepotvrđeno) ovdje nije uračunat, pa je stvarno gore.",
              at=(0.50, 0.84), width=28, size=10)
    teacher(fig, "osnovni trošak je 2,5 baznih bodova po strani (0,025 %: na kupnju od 1.000 EUR to je 0,25 EUR). "
                 "2x je 0,05 %, 3x je 0,075 %. Što se češće trguje, to se trošak više zbroji: držanje trguje 11 puta "
                 "(po jednom po dionici), K7 njih 443.")
    return save(fig, out, "06_otpornost_troskovi.png")


# ---------------------------------------------------------------- chart 7: lesson (exposure vs return)


def chart_lesson(d: Data, out: Path) -> tuple[str, float]:
    rows = d.a["tablica_segment_AI_era"]["suparnici"]
    cs = list(rows.keys())
    ex = np.array([rows[c]["izlozenost_pct"] for c in cs])
    rt = np.array([rows[c]["prinos_pct"] for c in cs])
    corr = float(np.corrcoef(ex, rt)[0, 1])
    fig, ax = plt.subplots(figsize=(12.5, 7.4))
    fig.subplots_adjust(top=0.93, bottom=0.17, left=0.08, right=0.985)
    sheet(ax, "Glavna pouka: u AI eri je prinos išao uz vrijeme u dionicama")
    for c, xx, yy in zip(cs, ex, rt):
        col = INK if c == HOLD else GREEN if c == d.winner else ORANGE if c == C13 else RED if c == "K5_SUPPORT_RESISTANCE" else "#6b7683"
        ax.scatter([xx], [yy], s=170, color=col, zorder=5, edgecolors="white")
    offs = {HOLD: (-22, 22), d.winner: (-34, -30), "K2_SMA200_TREND": (-6, 38), "K4_TSMOM_126": (2, -38),
            K7C: (6, 30), C13: (8, -34), "K3_DONCHIAN_55_20": (0, 34), "K5B_SR_BREAKOUT_RETEST": (-12, 40), "K5_SUPPORT_RESISTANCE": (8, 30)}
    for c, xx, yy in zip(cs, ex, rt):
        dx, dy = offs.get(c, (6, 6))
        ax.annotate(d.names[c], (xx, yy), xytext=(xx + dx, yy + dy), fontsize=10.5, color=PENCIL,
                    arrowprops=dict(arrowstyle="-", color=PENCIL, lw=0.8))
    ax.axhline(0, color=PENCIL, lw=1.1)
    ax.set_xlabel("u prosjeku koliki dio novca je bio u dionicama (%)")
    ax.set_ylabel("prinos u AI eri (%)")
    ax.set_xlim(0, 112)
    free_note(ax, f"Što je pravilo duže u dionicama, to je u ovom razdoblju prošlo bolje (povezanost {hr(corr, 2)}). "
                  "To nije zakon prirode, nego opis bik-tržišta čipova: rast nose rijetki dani, a tko je tada izvan, promašuje.",
              at=(0.05, 0.80), width=48)
    rh = rows[HOLD]
    say(ax, f"Držanje je 98,7 % vremena unutra i dalo je {hr(rh['prinos_pct'], 0)} %: 1.000 EUR postaje {eur(rh['iz_1000_EUR_po_sleeveu_EUR'])}.",
        xy=(rh["izlozenost_pct"], rh["prinos_pct"]), at=(0.30, 0.66), width=36, rad=-0.15)
    rk = rows[C13]
    say(ax, f"C13C je bio unutra otprilike pola vremena ({hr(rk['izlozenost_pct'], 0)} %) i dao {hr(rk['prinos_pct'], 0)} %: "
            f"1.000 EUR postaje {eur(rk['iz_1000_EUR_po_sleeveu_EUR'])}.",
        xy=(rk["izlozenost_pct"], rk["prinos_pct"]), at=(0.58, 0.20), width=34, rad=0.2)
    teacher(fig, "izloženost 50 % znači da je u prosjeku pola novca bilo u dionicama, a pola u gotovini. Gotovina ne nosi ni "
                 "rizik ni prinos (kamata na gotovinu ovdje nije uračunata). Devet točaka je premalo za pravi statistički dokaz: čitaj ovo kao sliku, ne kao zakon.")
    save(fig, out, "07_pouka_izlozenost.png")
    return "07_pouka_izlozenost.png", corr


# ---------------------------------------------------------------- behaviour charts


def chart_after_dip(d: Data, out: Path) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 7.2), sharey=False)
    fig.subplots_adjust(top=0.84, bottom=0.25, left=0.07, right=0.985, wspace=0.14)
    ts = d.tickers
    x = np.arange(len(ts))
    for ax, h, ttl in [(axes[0], "5d", "Što se dogodi u sljedećih 5 dana"), (axes[1], "20d", "Što se dogodi u sljedećih 20 dana")]:
        sheet(ax, ttl)
        a = [d.a["kartice"][t]["nakon_pada_5d_od_5pct_iznad_SMA200"][f"{h}_prosjek_pct_razrijedeno"] for t in ts]
        b = [d.a["kartice"][t]["nakon_pada_5d_od_5pct_iznad_SMA200"][f"{h}_prosjek_pct_svi_dani"] for t in ts]
        ax.bar(x - 0.2, a, 0.4, color=GREEN, alpha=0.85, label="nakon pada od 5 % u 5 dana")
        ax.bar(x + 0.2, b, 0.4, color="#9aa5b1", alpha=0.9, label="svi dani (običan prosjek)")
        ax.axhline(0, color=PENCIL, lw=1)
        ax.set_xticks(x)
        ax.set_xticklabels(ts, rotation=45, fontsize=10)
        ax.set_ylabel("prosječna promjena cijene (%)")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", bbox_to_anchor=(0.5, 0.12), ncol=2, fontsize=10, frameon=False)
    pooled = d.a["c13c_iskreno"]["premisa_skupno_AI_era"]
    free_note(axes[0], f"Skupno: nakon pada prosjek {hr(pooled['5d_prosjek_pct_poslije_pada'], 1)} % naprema "
                       f"{hr(pooled['5d_prosjek_pct_svi_dani'], 1)} % u svim danima: blago odbijanje.",
              at=(0.55, 0.80), width=26, size=10)
    free_note(axes[1], f"Za 20 dana obrnuto: {hr(pooled['20d_prosjek_pct_poslije_pada'], 1)} % nakon pada naprema "
                       f"{hr(pooled['20d_prosjek_pct_svi_dani'], 1)} % u svim danima. Dionice su inače rasle toliko da je običan dan bio bolji.",
              at=(0.66, 0.74), width=26, size=10)
    n = [d.a["kartice"][t]["nakon_pada_5d_od_5pct_iznad_SMA200"]["razrijedeni_10d"] for t in ts]
    teacher(fig, f"zeleni stupac: kupio si nakon što je cijena za 5 dana pala 5 % ili više (a još je iznad SMA200). "
                 f"Siv: kupio si bilo koji dan. Broj razrijeđenih događaja po dionici je {min(n)} do {max(n)}; "
                 "razlika uglavnom nije veća od slučajne (t ispod 2). Na 1.000 EUR: 1,7 % je 17 EUR u 5 dana.")
    fig.suptitle("Je li 'kupi nakon pada' ovdje imalo smisla?", x=0.02, y=0.985, ha="left", fontsize=15, fontweight="bold", color=INK)
    return save(fig, out, "08_nakon_pada.png")


def chart_dd_anatomy(d: Data, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(12.5, 7.8))
    fig.subplots_adjust(top=0.92, bottom=0.2, left=0.08, right=0.985)
    sheet(ax, "Anatomija najgoreg pada svake dionice: od vrha, preko dna, do oporavka")
    end = pd.Timestamp("2026-10-05")
    ts = sorted(d.tickers, key=lambda t: d.a["kartice"][t]["najgori_padovi"][0]["dubina_pct"])
    for i, t in enumerate(ts):
        p = d.a["kartice"][t]["najgori_padovi"][0]
        a0, bot = pd.Timestamp(p["od"]), pd.Timestamp(p["dno"])
        rec = pd.Timestamp(p["oporavak"]) if p["oporavak"] else None
        y = len(ts) - 1 - i
        ax.plot([a0, bot], [y, y], color=RED, lw=5, solid_capstyle="round", alpha=0.85)
        ax.plot([bot, rec or end], [y, y], color=GREEN, lw=5, solid_capstyle="round", alpha=0.8)
        ax.scatter([bot], [y], s=70, color=INK, zorder=5)
        txt = f"{hr(p['dubina_pct'], 1)} %  (1.000 EUR -> {hr(p['iz_1000_eur_na'])} EUR)"
        ax.text(a0 - pd.Timedelta(days=15), y, t, ha="right", va="center", fontsize=11, fontweight="bold")
        ax.text((rec or end) + pd.Timedelta(days=12), y, txt + ("" if rec else "  oporavak nije dovršen"), va="center", fontsize=9.5)
    ax.axvline(pd.Timestamp("2025-04-08"), color=PURPLE, ls="--", lw=1.4)
    ax.text(pd.Timestamp("2025-04-08"), -0.95, "8. 4. 2025.", color=PURPLE, fontsize=10, ha="center")
    ax.set_ylim(-1.2, len(ts) - 0.4)
    ax.set_yticks([])
    ax.set_xlim(pd.Timestamp("2023-03-01"), pd.Timestamp("2027-09-01"))
    date_axis(ax)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("crveno = padanje od vrha do dna,  zeleno = vraćanje na stari vrh,  točka = dno")
    free_note(ax, iso_to_hr(d.a["zasto_zajedno"]["najveci_zajednicki_pad"]).replace("..", ".").replace("Segment pada kao cjelina", "Cijela skupina pada zajedno"), at=(0.70, 0.20), width=30, size=10)
    teacher(fig, "svaka crta je jedan pad. Gledaj koliko su dna poredana jedno ispod drugog: skoro svi su pali istovremeno, "
                 "pa 11 dionica nisu 11 neovisnih oklada. Primjer: 1.000 EUR, pad od 60 % znači 400 EUR, a da se vrati na 1.000 EUR "
                 "treba rast od 150 %, ne 60 %.")
    return save(fig, out, "09_anatomija_pada.png")


def chart_sr(d: Data, out: Path) -> str:
    ts = d.tickers
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 7.0), sharey=True)
    fig.subplots_adjust(top=0.84, bottom=0.26, left=0.07, right=0.985, wspace=0.08)
    x = np.arange(len(ts))
    for ax, key, ttl in [(axes[0], "potpora", "Potpora (donja razina): koliko često je držala"), (axes[1], "otpor", "Otpor (gornja razina): koliko često je držao")]:
        sheet(ax, ttl)
        real = [d.a["kartice"][t]["potpora_otpor"][f"{key}_{'stvarna' if key == 'potpora' else 'stvarni'}"]["hold_pct"] for t in ts]
        plc = [d.a["kartice"][t]["potpora_otpor"][f"{key}_placebo"]["hold_pct"] for t in ts]
        ax.bar(x - 0.2, real, 0.4, color=INK, alpha=0.85, label="stvarna razina s grafa")
        ax.bar(x + 0.2, plc, 0.4, color="#c2c7cf", label="proizvoljna (lažna) razina")
        ax.axhline(50, color=PENCIL, ls=":", lw=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels(ts, rotation=45, fontsize=10)
        ax.set_ylim(0, 105)
    axes[0].set_ylabel("držalo u % dodira")
    axes[0].legend(fontsize=9.5, loc="lower left", frameon=True, facecolor=PAPER, edgecolor="none")
    nt = [d.a["kartice"][t]["potpora_otpor"][k]["n_touches"] for t in ts for k in ("potpora_stvarna", "otpor_stvarni")]
    free_note(axes[0], f"Crtkana crta je 50 %: bacanje novčića. Po dionici i vrsti razine je samo {min(nt)} do {max(nt)} dodira, premalo da bi razlika od lažnih razina bila dokaz.",
              at=(0.12, 0.92), width=38, size=10)
    teacher(fig, "'držati' znači da se cijena nakon dodira razine odbila natrag. Usporedili smo prave razine (zadnji potvrđeni vrh ili dno) "
                 "s nasumično postavljenim lažnim razinama. Ako stvarne nisu jasno bolje od lažnih, crtanje crta nije dalo prednost. "
                 "Pravilo K5 (potpora/otpor) u ovom je segmentu završilo na minusu.")
    fig.suptitle("Jesu li crte potpore i otpora išta vrijedile?", x=0.02, y=0.985, ha="left", fontsize=15, fontweight="bold", color=INK)
    return save(fig, out, "10_potpora_otpor.png")


def chart_best_days(d: Data, out: Path) -> str:
    ts = sorted(d.tickers, key=lambda t: -d.a["kartice"][t]["koncentracija_prinosa"]["10_najboljih_dana_udio_pct"])
    fig, ax = plt.subplots(figsize=(12.5, 7.2))
    fig.subplots_adjust(top=0.92, bottom=0.2, left=0.1, right=0.985)
    sheet(ax, "Prinos s cijelom godinom naprema prinosu bez 10 najboljih dana")
    x = np.arange(len(ts))
    full = [d.a["kartice"][t]["ukupni_prinos_profil_pct"] for t in ts]
    wo = [d.a["kartice"][t]["koncentracija_prinosa"]["prinos_bez_10_najboljih_pct"] for t in ts]
    ax.bar(x - 0.2, full, 0.4, color=INK, alpha=0.85, label="svi dani")
    ax.bar(x + 0.2, wo, 0.4, color=RED, alpha=0.8, label="bez 10 najboljih dana")
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(ts, fontsize=11)
    ax.set_ylabel("prinos u AI eri (%)")
    ax.legend(fontsize=10.5, loc="upper left", frameon=True, facecolor=PAPER, edgecolor="none")
    for xi, t in zip(x, ts):
        v = d.a["kartice"][t]["koncentracija_prinosa"]["10_najboljih_dana_udio_pct"]
        ax.text(xi, max(full) * -0.07, f"{hr(v, 0)} %", ha="center", fontsize=9.5, color=PURPLE)
    ax.text(-0.75, max(full) * -0.07, "udio\n10 dana", fontsize=9, color=PURPLE, ha="center")
    ax.set_ylim(max(full) * -0.13, max(full) * 1.08)
    ax.set_xlim(-1.15, len(ts) - 0.4)
    m = d.a["kartice"]["MCHP"]
    say(ax, f"MCHP: s cijelom godinom {hr(m['ukupni_prinos_profil_pct'], 0)} %, bez 10 najboljih dana "
            f"{hr(m['koncentracija_prinosa']['prinos_bez_10_najboljih_pct'], 1)} %. Iz 1.000 EUR: "
            f"{eur(1000 * (1 + m['ukupni_prinos_profil_pct'] / 100))} naprema {eur(1000 * (1 + m['koncentracija_prinosa']['prinos_bez_10_najboljih_pct'] / 100))}.",
        xy=(ts.index("MCHP") + 0.2, m["koncentracija_prinosa"]["prinos_bez_10_najboljih_pct"]), at=(0.10, 0.42), width=36, rad=0.2)
    teacher(fig, "u oko 940 radnih dana, 10 najboljih (ispod 1,1 % svih dana) nosi velik dio cijelog prinosa. "
                 "Zato je teško uspjeti pravilom koje je povremeno izvan tržišta: ti dani se ne najavljuju.")
    return save(fig, out, "11_najbolji_dani.png")


def chart_gaps(d: Data, out: Path) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 6.2))
    fig.subplots_adjust(top=0.8, bottom=0.25, left=0.05, right=0.99, wspace=0.28)
    specs = [
        ("NVDA", "2023-05-25", 8, 8, "Jaz preko noći: +26,1 %"),
        ("ARM", "2024-08-05", 8, 6, "Stop probijen preko noći (ARM)"),
        ("NVDA", "2024-06-10", 8, 8, "Loš podatak (NVDA)"),
    ]
    for ax, (t, dt, pre, post, ttl) in zip(axes, specs):
        df = d.prices(t)
        i = df.index.get_loc(pd.Timestamp(dt))
        w = df.iloc[i - pre : i + post + 1]
        sheet(ax, ttl)
        ax.title.set_fontsize(12)
        for k, (dd, r) in enumerate(w.iterrows()):
            col = GREEN if r["close"] >= r["open"] else RED
            hi = r["high"]
            if t == "NVDA" and dt == "2024-06-10" and dd == pd.Timestamp(dt):
                hi = r["high"]
            ax.plot([k, k], [r["low"], hi], color=PENCIL, lw=1)
            ax.add_patch(plt.Rectangle((k - 0.3, min(r["open"], r["close"])), 0.6, max(abs(r["close"] - r["open"]), 0.01), color=col, alpha=0.85))
        ax.set_xticks(range(0, len(w), 4))
        ax.set_xticklabels([f"{x.day}.{x.month}." for x in w.index[::4]], fontsize=9)
        k0 = pre
        r0 = df.loc[pd.Timestamp(dt)]
        prev = df["close"].iloc[i - 1]
        if dt == "2023-05-25":
            ax.annotate(wrap(f"Jučer zatvaranje {hr(prev, 2)}, danas otvaranje {hr(r0['open'], 2)} USD. Praznina se ne može kupiti.", 26),
                        xy=(k0, r0["open"]), xytext=(0.02, 0.78), textcoords="axes fraction", fontsize=9.5, color=RED,
                        arrowprops=dict(arrowstyle="->", color=RED, connectionstyle="arc3,rad=-0.2"), bbox=dict(boxstyle="round", fc=PAPER, ec="none"))
        elif t == "ARM":
            tr = [x for x in d.trades("ARM") if x["exit_date"] == dt][0]
            ax.axhline(tr["raw_entry"] * 0.9, color=RED, ls="--", lw=1.2)
            ax.annotate(wrap(f"Kupnja {dmy(tr['entry_date'])} po {hr(tr['raw_entry'], 2)}. Stop oko {hr(tr['raw_entry'] * 0.9, 2)}; otvaranje {hr(r0['open'], 2)}: izlaz {hr(tr['raw_exit'], 2)} ({hr(tr['return'] * 100, 1)} %).", 28),
                        xy=(k0, r0["open"]), xytext=(0.02, 0.22), textcoords="axes fraction", fontsize=9.5, color=RED,
                        arrowprops=dict(arrowstyle="->", color=RED, connectionstyle="arc3,rad=0.2"), bbox=dict(boxstyle="round", fc=PAPER, ec="none"))
        else:
            ax.annotate(wrap(f"Najviša cijena u CSV-u {hr(r0['high'], 2)}, otvaranje {hr(r0['open'], 2)}, zatvaranje {hr(r0['close'], 2)}. Šiljak je pogrešan unos; simulator ga je ograničio.", 28),
                        xy=(k0, r0["high"]), xytext=(0.02, 0.35), textcoords="axes fraction", fontsize=9.5, color=RED,
                        arrowprops=dict(arrowstyle="->", color=RED, connectionstyle="arc3,rad=0.2"), bbox=dict(boxstyle="round", fc=PAPER, ec="none"))
        ax.set_ylabel("cijena u USD")
    teacher(fig, "svijeća pokazuje jedan dan: tijelo od otvaranja do zatvaranja, tanka crta najvišu i najnižu cijenu. Zelena = dan završio više nego što je počeo. "
                 "Stop ne štiti od jaza: ako dionica otvori ispod stopa, izlaz je po otvaranju. Prije vjerovanja backtestu pogledaj ima li u podacima šiljak.", width=170)
    fig.suptitle("Što graf ne pokazuje na prvi pogled: jazovi i loši podaci", x=0.02, y=0.97, ha="left", fontsize=15, fontweight="bold", color=INK)
    return save(fig, out, "12_jazovi_i_podaci.png")


def make_all(segment: str) -> dict[str, str]:
    d = Data(segment)
    out = d.dir
    files = {
        "cijena": chart_price(d, out),
        "kapital": chart_equity(d, out),
        "pad": chart_drawdown(d, out),
        "poslovi": chart_trades(d, out),
        "ploca": chart_scoreboard(d, out),
        "troskovi": chart_costs(d, out),
    }
    f7, corr = chart_lesson(d, out)
    files["pouka"] = f7
    files["nakon_pada"] = chart_after_dip(d, out)
    files["anatomija"] = chart_dd_anatomy(d, out)
    files["potpora"] = chart_sr(d, out)
    files["dani"] = chart_best_days(d, out)
    files["jazovi"] = chart_gaps(d, out)
    (out / "charts_meta.json").write_text(json.dumps({"files": files, "corr_exposure_return": corr}, indent=1))
    return files


if __name__ == "__main__":
    print(make_all(sys.argv[1] if len(sys.argv) > 1 else "ai_chips_logic"))
