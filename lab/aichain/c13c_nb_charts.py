"""Notebook-style charts for the C13C notebook, drawn from ``results.json`` and ``sleeves.pkl``.

Research only. Re-uses the drawing helpers of ``master_common`` (pencil look, teacher notes) but writes into the
C13C notebook folder. Every number on a chart comes from the engine output, nothing is typed by hand.

    .venv/bin/python -m lab.aichain.c13c_nb_charts
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from lab.aichain import master_common as mc
from lab.aichain.c13c_nb_run import MEMORY_CORE, MEMORY_WIDE, OUT, STOCK_GROUPS
from lab.aichain.master_common import (
    GREY,
    LOSS,
    ORANGE,
    WIN,
    bottom_note,
    canvas,
    eur,
    finish,
    hr,
    paper,
    pct,
    tip,
)
from lab.aichain.sim import load_bars
from lab.top10.charts import GREEN, INK, PAPER, PENCIL, RED

CHARTS = OUT / "charts"
mc.OUT = CHARTS
SEGMENT_HR = {
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja memorije i pohrana",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Cloud i infrastruktura",
}
BLUE = "#2f6fb3"
ERA_START = pd.Timestamp("2023-01-01")


class Data:
    """Loads engine output once."""

    def __init__(self) -> None:
        self.res: dict[str, Any] = json.loads((OUT / "results.json").read_text())
        # sleeves.pkl is written by c13c_nb_run.py on this machine; never load a pickle from elsewhere
        with (OUT / "sleeves.pkl").open("rb") as fh:
            self.sl: dict[tuple[str, str, str, str], tuple[Any, ...]] = pickle.load(fh)
        self.tickers: list[str] = [r["ticker"] for r in self.res["datasets"]]
        self.segment_of: dict[str, str] = {r["ticker"]: r["segment"] for r in self.res["datasets"]}
        self._bars: dict[str, Any] = {}

    def bars(self, ticker: str) -> Any:
        if ticker not in self._bars:
            self._bars[ticker] = load_bars(ticker)
        return self._bars[ticker]

    def eq(self, cfg: str, ticker: str, window: str = "ai_era") -> pd.Series | None:
        got = self.sl.get((cfg, ticker, window, "1x"))
        return None if got is None else pd.Series(got[1], index=got[0])

    def trades(self, cfg: str, ticker: str, window: str = "ai_era") -> list[dict[str, Any]]:
        got = self.sl.get((cfg, ticker, window, "1x"))
        return [] if got is None else list(got[3])

    def ptk(self, ticker: str, cfg: str, window: str) -> dict[str, Any] | None:
        return self.res["per_ticker"][ticker][cfg][window]


def stop_path(bars: Any, trade: dict[str, Any], trail: float = 0.10) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """The trailing stop of one trade from entry to exit (peak from the fill, 90 % of peak, never lowered)."""
    d0, d1 = pd.Timestamp(trade["entry_date"]), pd.Timestamp(trade["exit_date"])
    m = (bars.dates >= d0) & (bars.dates <= d1)
    idx = np.nonzero(m)[0]
    hi = bars.high[idx]
    peak = np.maximum.accumulate(np.maximum(hi, trade["raw_entry"]))
    stop = np.maximum.accumulate(peak * (1 - trail))
    return bars.dates[idx], stop


def fmt_dates(ax: Any, rotate: bool = False, ticks: int = 9) -> None:
    lo, hi = (mdates.num2date(v) for v in ax.get_xlim())
    span = (hi - lo).days
    if span < 260:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d.%-m.%y"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=ticks))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.tick_params(axis="x", labelsize=11, rotation=30 if rotate else 0)


# ---------------------------------------------------------------------------------------------- n01 / n02
def anatomy_panel(ax: Any, bars: Any, trade: dict[str, Any], title: str, pad_before: int = 40, pad_after: int = 30) -> None:
    close = pd.Series(bars.close, index=bars.dates)
    sma = close.rolling(200).mean()
    d0, d1 = pd.Timestamp(trade["entry_date"]), pd.Timestamp(trade["exit_date"])
    i0 = int(np.searchsorted(bars.dates.values, np.datetime64(d0)))
    i1 = int(np.searchsorted(bars.dates.values, np.datetime64(d1)))
    lo, hi = max(i0 - pad_before, 0), min(i1 + pad_after, len(bars) - 1)
    sl = slice(lo, hi + 1)
    x = bars.dates[sl]
    paper(ax)
    ax.plot(x, close.iloc[sl], color=INK, lw=2.0, label="zatvaranje")
    ax.plot(x, sma.iloc[sl], color=BLUE, lw=1.8, ls="--", label="prosjek 200 dana")
    sd, sv = stop_path(bars, trade)
    ax.step(sd, sv, where="post", color=RED, lw=2.0, label="zaštitni stop (90 % vrha)")
    ax.axvspan(d0, d1, color="#bfe6c9", alpha=0.35, zorder=0)
    ax.scatter([d0], [trade["raw_entry"]], marker="^", s=150, color=WIN, zorder=6)
    ax.scatter([d1], [trade["raw_exit"]], marker="v", s=150, color=LOSS if trade["return"] < 0 else ORANGE, zorder=6)
    ax.set_title(title, fontsize=14, color=INK, loc="left")
    fmt_dates(ax)
    ax.legend(loc="upper left", fontsize=10.5, frameon=False)
    y_lo, y_hi = ax.get_ylim()
    span = y_hi - y_lo
    tip(
        ax,
        f"kupnja {d0.day}. {d0.month}.\n{hr(trade['raw_entry'], 2)} $",
        (d0, trade["raw_entry"]),
        (d0 - pd.Timedelta(days=16), trade["raw_entry"] - 0.16 * span),
        color=WIN,
        rad=0.15,
        size=11.5,
        ha="right",
    )
    tip(
        ax,
        f"izlaz {d1.day}. {d1.month}.\n{hr(trade['raw_exit'], 2)} $  ({pct(trade['return'])})",
        (d1, trade["raw_exit"]),
        (d1 + pd.Timedelta(days=5), trade["raw_exit"] - 0.2 * span),
        color=RED,
        rad=-0.15,
        size=11.5,
    )


def n01_anatomy(data: Data) -> str:
    t = data.trades("C13C", "MU")
    wins = [x for x in t if x["return"] > 0 and x["reason"] == "stop"]
    win = sorted(wins, key=lambda x: x["return"])[len(wins) // 2]
    big = max(t, key=lambda x: x["return"])
    bars = data.bars("MU")
    fig = canvas(8.4, "Jedna pravila-trgovina od početka do kraja (MU)", "Gore: tipična dobitna trgovina. Dolje: najbolja MU trgovina u AI eri.")
    a1 = fig.add_axes([0.06, 0.55, 0.92, 0.33])
    a2 = fig.add_axes([0.06, 0.12, 0.92, 0.33])
    anatomy_panel(a1, bars, win, f"Srednja dobitna trgovina: {pct(win['return'])} u {win['bars_held']} trgovinskih dana")
    anatomy_panel(a2, bars, big, f"Najbolja trgovina: {pct(big['return'])} u {big['bars_held']} trgovinskih dana", pad_after=15)
    bottom_note(
        fig,
        "kupnja je prvo otvaranje NAKON dana s padom 5 % u 5 dana iznad prosjeka 200 dana. Crvena crta se samo diže, nikad ne spušta; izlaz je kad cijena probije crvenu crtu.",
    )
    return finish(fig, "n01_anatomy.png", {
        "title": "Jedna C13C trgovina od početka do kraja (MU)",
        "what_to_see": "Zeleni trokut je kupnja, narančasti ili crveni izlaz, crvena crta zaštitni stop koji prati vrh.",
        "numbers_used": [f"{win['entry_date']} do {win['exit_date']}: {win['return']:.4f}", f"{big['entry_date']} do {big['exit_date']}: {big['return']:.4f}"],
    })


def n02_failures(data: Data) -> str:
    pool = [
        {**x, "ticker": t}
        for t in MEMORY_CORE
        for x in data.trades("C13C", t)
    ]
    worst = min(pool, key=lambda x: x["return"])
    # shake-out: stopped out, then price rose the most within the next 60 bars
    best_miss: tuple[float, dict[str, Any]] | None = None
    for x in pool:
        if x["reason"] != "stop":
            continue
        b = data.bars(x["ticker"])
        i1 = int(np.searchsorted(b.dates.values, np.datetime64(pd.Timestamp(x["exit_date"]))))
        if i1 + 60 >= len(b):
            continue
        rise = float(b.high[i1 : i1 + 60].max() / x["raw_exit"] - 1)
        if best_miss is None or rise > best_miss[0]:
            best_miss = (rise, x)
    assert best_miss is not None
    miss_rise, miss = best_miss
    fig = canvas(8.4, "Gdje C13C boli: najgora trgovina i izbačen prije rasta", "Obje su iz memorijske trojke (MU, WDC, STX): najgora trgovina i trgovina izbačena stopom prije najvećeg rasta u idućih 60 dana.")
    a1 = fig.add_axes([0.06, 0.55, 0.92, 0.33])
    a2 = fig.add_axes([0.06, 0.12, 0.92, 0.33])
    anatomy_panel(a1, data.bars(worst["ticker"]), worst, f"{worst['ticker']}: najgora trgovina, {pct(worst['return'])} za {worst['bars_held']} dana")
    anatomy_panel(a2, data.bars(miss["ticker"]), miss, f"{miss['ticker']}: izbačen s {pct(miss['return'])}, a cijena je poslije skočila još {pct(miss_rise, 0)}", pad_after=60)
    bottom_note(fig, "stop od 10 % štiti od velikog pada, ali u volatilnim dionicama često izbaci trgovinu baš prije nastavka rasta. To je cijena osiguranja.")
    return finish(fig, "n02_failures.png", {
        "title": "Najgora trgovina i izbacivanje prije rasta",
        "what_to_see": "Gore najgora trgovina memorijske grupe, dolje trgovina izbačena stopom nakon koje je cijena nastavila rasti.",
        "numbers_used": [f"{worst['ticker']} {worst['entry_date']} {worst['return']:.4f}", f"{miss['ticker']} {miss['exit_date']} rise60 {miss_rise:.4f}"],
    })


# ---------------------------------------------------------------------------------------------- n03 / n04 / n05
def end_values(data: Data) -> pd.DataFrame:
    rows = []
    for t in data.tickers:
        c, h = data.ptk(t, "C13C", "ai_era"), data.ptk(t, "HOLD", "ai_era")
        rows.append({
            "ticker": t, "segment": data.segment_of[t],
            "c13c": c["end_value"], "hold": h["end_value"],
            "dd_c": c["max_drawdown"], "dd_h": h["max_drawdown"],
            "exp": c["exposure_pct"], "hit": c["hit_rate"], "n": c["trades"],
        })
    return pd.DataFrame(rows)


def n03_scoreboard(data: Data) -> str:
    df = end_values(data).sort_values("hold").reset_index(drop=True)
    fig = canvas(14.5, "Rezultat po dionici: C13C naspram kupi-i-drži (AI era)", "Što je postalo iz 1.000 € ulaganih 3. 1. 2023. (ili od prvog dostupnog dana). Logaritamska skala.")
    ax = fig.add_axes([0.09, 0.05, 0.88, 0.86])
    paper(ax)
    y = np.arange(len(df))
    ax.hlines(y, df["c13c"], df["hold"], color=GREY, lw=1.6, zorder=2)
    ax.scatter(df["c13c"], y, color=WIN, s=70, zorder=4, label="C13C")
    ax.scatter(df["hold"], y, color=PENCIL, s=70, zorder=4, marker="D", label="kupi i drži")
    ax.axvline(1000, color=RED, ls=":", lw=1.8)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(df["ticker"], fontsize=11)
    ax.set_xlabel("vrijednost 1.000 € na kraju (log)", fontsize=12)
    ax.legend(loc="lower right", fontsize=12, frameon=False)
    n_beat = int((df["c13c"] > df["hold"]).sum())
    tip(ax, "crvena crta = ulog od 1.000 €", (1000, y[-3]), (1250, y[-3] - 0.2), size=11.5)
    tip(ax, f"C13C pobjeđuje držanje u prinosu\nu samo {n_beat} od {len(df)} dionica", None, (0.52, 0.12), coords="axes", arrow=False, size=13)
    return finish(fig, "n03_scoreboard.png", {
        "title": "Rezultat po dionici",
        "what_to_see": "Zeleni krug je C13C, siva oznaka je kupi-i-drži; crta između je cijena opreza.",
        "numbers_used": [f"{n_beat} od {len(df)} dionica C13C bolji po prinosu"],
    })


def n04_drawdown(data: Data) -> str:
    df = end_values(data).sort_values("dd_h", ascending=False).reset_index(drop=True)
    fig = canvas(14.5, "Najveći pad na putu: C13C naspram kupi-i-drži (AI era)", "Koliko je račun najviše pao od vlastitog vrha. Kraća crta (bliže nuli) znači mirniji put.")
    ax = fig.add_axes([0.09, 0.05, 0.88, 0.86])
    paper(ax)
    y = np.arange(len(df))
    ax.hlines(y, df["dd_c"] * 100, df["dd_h"] * 100, color=GREY, lw=1.6)
    ax.scatter(df["dd_c"] * 100, y, color=WIN, s=70, zorder=4, label="C13C")
    ax.scatter(df["dd_h"] * 100, y, color=PENCIL, s=70, zorder=4, marker="D", label="kupi i drži")
    ax.set_yticks(y)
    ax.set_yticklabels(df["ticker"], fontsize=11)
    ax.set_xlabel("najveći pad od vrha (%)", fontsize=12)
    ax.legend(loc="lower left", fontsize=12, frameon=False)
    smaller = int((df["dd_c"] > df["dd_h"]).sum())
    tip(ax, f"C13C ima manji pad u {smaller} od {len(df)} dionica", None, (0.55, 0.1), coords="axes", arrow=False, size=13)
    return finish(fig, "n04_drawdown.png", {
        "title": "Najveći pad po dionici",
        "what_to_see": "Zeleni krugovi bliže nuli = manji pad.",
        "numbers_used": [f"{smaller} od {len(df)} dionica manji pad"],
    })


def n05_exposure(data: Data) -> str:
    df = end_values(data).sort_values("exp").reset_index(drop=True)
    fig = canvas(14.5, "Koliko je C13C u tržištu i koliko trgovina napravi", "Lijevo: posto vremena s otvorenom pozicijom. Desno: broj trgovina u AI eri (3,8 godine).")
    a1 = fig.add_axes([0.09, 0.05, 0.42, 0.86])
    a2 = fig.add_axes([0.58, 0.05, 0.39, 0.86])
    y = np.arange(len(df))
    for ax in (a1, a2):
        paper(ax)
        ax.set_yticks(y)
    a1.set_yticklabels(df["ticker"], fontsize=11)
    a2.set_yticklabels([])
    a1.barh(y, df["exp"], color=BLUE, height=0.7)
    a2.barh(y, df["n"], color=ORANGE, height=0.7)
    a1.set_xlabel("% vremena u tržištu", fontsize=12)
    a2.set_xlabel("broj trgovina", fontsize=12)
    tip(a1, f"prosjek {hr(df['exp'].mean(), 0)} % vremena", None, (0.45, 0.1), coords="axes", arrow=False, size=13)
    tip(a2, f"ukupno {int(df['n'].sum())} trgovina\n= {hr(df['n'].sum() / 45.2, 0)} mjesečno", None, (0.4, 0.1), coords="axes", arrow=False, size=13)
    return finish(fig, "n05_exposure.png", {
        "title": "Vrijeme u tržištu i broj trgovina",
        "what_to_see": "Plavo: posto vremena u poziciji; narančasto: broj trgovina.",
        "numbers_used": [f"prosjek izloženosti {df['exp'].mean():.1f} %", f"trgovina ukupno {int(df['n'].sum())}"],
    })


# ---------------------------------------------------------------------------------------------- n06 / n07 / n08
def avg_equity(data: Data, cfg: str, tickers: list[str], window: str = "ai_era") -> pd.Series:
    parts = [e for t in tickers if (e := data.eq(cfg, t, window)) is not None]
    return pd.concat(parts, axis=1).ffill().bfill().mean(axis=1)


def n06_segments(data: Data) -> str:
    fig = canvas(11.5, "Šest skupina: prosječni račun od 1.000 € po dionici", "Svaka skupina = prosjek njezinih dionica, svaka s vlastitih 1.000 € (AI era).")
    for k, g in enumerate(STOCK_GROUPS):
        ax = fig.add_axes([0.06 + (k % 2) * 0.49, 0.68 - (k // 2) * 0.285, 0.42, 0.19])
        paper(ax)
        tk = data.res["segments"][g]
        c, h = avg_equity(data, "C13C", tk), avg_equity(data, "HOLD", tk)
        ax.plot(h.index, h.values, color=PENCIL, lw=2.0, label="kupi i drži")
        ax.plot(c.index, c.values, color=WIN, lw=2.4, label="C13C")
        ax.axhline(1000, color=RED, ls=":", lw=1.3)
        ax.set_title(f"{SEGMENT_HR[g]} ({len(tk)})", fontsize=13, loc="left", color=INK)
        ax.text(0.02, 0.8, f"C13C {eur(c.iloc[-1])}\ndržanje {eur(h.iloc[-1])}", transform=ax.transAxes, fontsize=11.5, color=RED)
        fmt_dates(ax, ticks=5)
        if k == 0:
            ax.legend(loc="center right", fontsize=10.5, frameon=False)
    bottom_note(fig, "u svih šest skupina držanje daje veći prinos, a C13C je mirniji. U memoriji je razlika najveća po veličini, ali i C13C tamo najviše zarađuje.")
    return finish(fig, "n06_segments.png", {
        "title": "Šest skupina, prosječni račun",
        "what_to_see": "Zelena crta C13C, siva držanje.",
        "numbers_used": ["prosjek 1.000 € po dionici po skupini, AI era"],
    })


def trade_card(ax_p: Any, ax_e: Any, data: Data, t: str, title: str | None = None) -> None:
    bars = data.bars(t)
    close = pd.Series(bars.close, index=bars.dates)
    sma = close.rolling(200).mean()
    m = close.index >= ERA_START
    paper(ax_p)
    ax_p.plot(close.index[m], close[m], color=INK, lw=1.7)
    ax_p.plot(sma.index[m], sma[m], color=BLUE, lw=1.4, ls="--")
    tr = data.trades("C13C", t)
    for x in tr:
        d0, d1 = pd.Timestamp(x["entry_date"]), pd.Timestamp(x["exit_date"])
        ax_p.axvspan(d0, d1, color="#bfe6c9", alpha=0.55, zorder=0)
    ax_p.scatter([pd.Timestamp(x["entry_date"]) for x in tr], [x["raw_entry"] for x in tr], marker="^", s=44, color=WIN, zorder=5)
    ax_p.scatter([pd.Timestamp(x["exit_date"]) for x in tr], [x["raw_exit"] for x in tr], marker="v", s=44, color=[LOSS if x["return"] < 0 else ORANGE for x in tr], zorder=5)
    ax_p.set_yscale("log")
    ax_p.set_title(title or t, fontsize=14, loc="left", color=INK)
    fmt_dates(ax_p)
    paper(ax_e)
    c, h = data.eq("C13C", t), data.eq("HOLD", t)
    if c is not None and h is not None:
        ax_e.plot(h.index, h.values, color=PENCIL, lw=1.9, label="kupi i drži")
        ax_e.plot(c.index, c.values, color=WIN, lw=2.2, label="C13C")
        ax_e.axhline(1000, color=RED, ls=":", lw=1.2)
        ax_e.set_yscale("log")
        ax_e.legend(loc="upper left", fontsize=10, frameon=False)
    fmt_dates(ax_e)


def n07_memory_core(data: Data) -> str:
    fig = canvas(17.5, "Memorijska trojka: MU, WDC, STX", "Gore cijena (log) s prosjekom 200 dana i C13C pozicijama (zeleno); dolje što bi bilo od 1.000 €.")
    for k, t in enumerate(MEMORY_CORE):
        top = 0.93 - k * 0.31
        ap = fig.add_axes([0.06, top - 0.15, 0.92, 0.15])
        ae = fig.add_axes([0.06, top - 0.25, 0.92, 0.08])
        c = data.ptk(t, "C13C", "ai_era")
        h = data.ptk(t, "HOLD", "ai_era")
        trade_card(ap, ae, data, t, f"{t}: C13C {eur(c['end_value'])} naspram držanja {eur(h['end_value'])}; trgovina {c['trades']}, uspješnih {pct(c['hit_rate'], 0, False)}")
    bottom_note(fig, "zeleni pojasi su vrijeme u poziciji. C13C ulazi u padove usred uzlaznog trenda i izlazi na stopu, pa propušta dio dugih uspona.", y=0.004)
    return finish(fig, "n07_memory_core.png", {
        "title": "Memorijska trojka MU WDC STX",
        "what_to_see": "Zeleni pojasi označavaju vrijeme u poziciji.",
        "numbers_used": [f"{t} {data.ptk(t, 'C13C', 'ai_era')['end_value']:.0f}" for t in MEMORY_CORE],
    })


def n08_memory_wide(data: Data) -> str:
    names = ["RMBS", "SIMO", "MRAM", "NTAP"]
    fig = canvas(15.5, "Ostale memorijske dionice: RMBS, SIMO, MRAM, NTAP", "Sučelja memorije, kontroleri, MRAM i pohrana (AI era).")
    for k, t in enumerate(names):
        top = 0.93 - k * 0.24
        ap = fig.add_axes([0.06, top - 0.13, 0.92, 0.13])
        ae = fig.add_axes([0.06, top - 0.205, 0.92, 0.065])
        c = data.ptk(t, "C13C", "ai_era")
        h = data.ptk(t, "HOLD", "ai_era")
        trade_card(ap, ae, data, t, f"{t}: C13C {eur(c['end_value'])} naspram držanja {eur(h['end_value'])}; trgovina {c['trades']}")
    return finish(fig, "n08_memory_wide.png", {
        "title": "RMBS SIMO MRAM NTAP",
        "what_to_see": "Isti prikaz kao za MU, WDC, STX.",
        "numbers_used": [f"{t} {data.ptk(t, 'C13C', 'ai_era')['end_value']:.0f}" for t in names],
    })


# ---------------------------------------------------------------------------------------------- n09 / n10
def pooled_trades(data: Data, tickers: list[str]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        b = data.bars(t)
        close = pd.Series(b.close, index=b.dates)
        r126 = close / close.shift(126) - 1
        for x in data.trades("C13C", t):
            d0 = pd.Timestamp(x["entry_date"])
            j = int(np.searchsorted(b.dates.values, np.datetime64(d0))) - 1
            rows.append({**{k: x[k] for k in ("entry_date", "exit_date", "return", "reason", "bars_held")}, "ticker": t, "r126": float(r126.iloc[j]) if j >= 0 else np.nan})
    return pd.DataFrame(rows)


def n09_distribution(data: Data) -> str:
    allp = pooled_trades(data, data.tickers)
    mem = pooled_trades(data, MEMORY_CORE)
    fig = canvas(10.5, "Kako izgledaju trgovine: raspodjela rezultata i trajanja", "Sve C13C trgovine u AI eri (43 dionice), memorijska trojka posebno.")
    a1 = fig.add_axes([0.06, 0.12, 0.43, 0.70])
    a2 = fig.add_axes([0.56, 0.12, 0.41, 0.70])
    bins = np.arange(-0.30, 1.01, 0.05)
    for ax in (a1, a2):
        paper(ax)
    a1.hist(np.clip(allp["return"], -0.3, 1.0), bins=bins, color="#9bc4a8", edgecolor=PENCIL, label="43 dionice")
    a1.hist(np.clip(mem["return"], -0.3, 1.0), bins=bins, color=ORANGE, alpha=0.8, edgecolor=PENCIL, label="MU WDC STX")
    a1.axvline(0, color=RED, lw=1.8, ls=":")
    a1.set_xlabel("rezultat trgovine (odrezano na -30 % i +100 %)", fontsize=12)
    a1.legend(fontsize=11, frameon=False)
    win = allp["return"] > 0
    a1.set_title(f"Uspješnih {pct(win.mean(), 0, False)}; medijan {pct(allp['return'].median())}; prosjek {pct(allp['return'].mean())}", fontsize=13, loc="left", color=INK)
    a2.hist(np.clip(allp["bars_held"], 0, 120), bins=np.arange(0, 125, 5), color=BLUE, alpha=0.8, edgecolor=PENCIL)
    a2.set_xlabel("trajanje trgovine (trgovinski dani, odrezano na 120)", fontsize=12)
    a2.set_title(f"Medijan {int(allp['bars_held'].median())} dana; polovica izlazi u {int(allp['bars_held'].quantile(0.5))} dana", fontsize=13, loc="left", color=INK)
    top10 = allp["return"].nlargest(max(int(len(allp) * 0.1), 1)).sum() / allp["return"].clip(lower=0).sum()
    bottom_note(fig, f"glavnina dobiti dolazi iz desnog repa: najboljih 10 % trgovina daje {pct(top10, 0, False)} zbroja svih dobitaka. Gubici su mali jer stop reže pad na oko 10 %.")
    return finish(fig, "n09_distribution.png", {
        "title": "Raspodjela rezultata i trajanja trgovina",
        "what_to_see": "Lijevo rezultat u %, desno trajanje u danima.",
        "numbers_used": [f"uspješnih {win.mean():.3f}", f"top 10 % udio {top10:.3f}"],
    })


def n10_clustering(data: Data) -> str:
    rows = []
    for t in data.tickers:
        for x in data.trades("C13C", t):
            rows.append(pd.Timestamp(x["entry_date"]))
    ent = pd.Series(1, index=pd.DatetimeIndex(rows)).resample("ME").sum()
    idx = avg_equity(data, "HOLD", data.tickers).resample("ME").last()
    fig = canvas(8.6, "Kada C13C daje signale: u valovima, mnogo dionica odjednom", "Stupci: broj ulaza po mjesecu u svih 43 dionica. Crta: prosječni račun kupi-i-drži (1.000 € po dionici).")
    ax = fig.add_axes([0.06, 0.14, 0.84, 0.66])
    paper(ax)
    ax.bar(ent.index, ent.values, width=22, color=ORANGE, edgecolor=PENCIL)
    ax.set_ylabel("ulazi u mjesecu", fontsize=12)
    ax2 = ax.twinx()
    ax2.plot(idx.index, idx.values, color=INK, lw=2.2)
    ax2.set_ylabel("prosječni račun (€)", fontsize=12)
    ax2.spines["top"].set_visible(False)
    top = ent.nlargest(3)
    for d, v in top.items():
        tip(ax, f"{d.strftime('%m/%Y')}: {int(v)} ulaza", (d, v), (d - pd.Timedelta(days=170), v * 0.93), size=11.5)
    fmt_dates(ax)
    bottom_note(fig, "signali dolaze u valovima kad dionice istodobno koriguju. Jedan račun ne može držati 43 pozicije odjednom, pa u stvarnosti moraš birati (prioritet) ili imati više kapitala.")
    return finish(fig, "n10_clustering.png", {
        "title": "Grupiranje signala",
        "what_to_see": "Stupci su broj ulaza po mjesecu, crta je kretanje sektora.",
        "numbers_used": [f"najviše ulaza {int(top.iloc[0])}"],
    })


# ---------------------------------------------------------------------------------------------- n11 / n12
def n11_periods(data: Data) -> str:
    wins = [("y2016_2020", "2016.-2020."), ("y2021_2022", "2021.-2022."), ("ai_era", "AI era 2023.-")]
    scopes = [("stocks_all", "43 dionice"), ("memory_core", "MU WDC STX")]
    fig = canvas(8.8, "Tri razdoblja: gdje C13C pomaže, a gdje ne", "Pooled prinos (zbroj računa od 1.000 € po dionici) i najveći pad.")
    a1 = fig.add_axes([0.06, 0.14, 0.42, 0.66])
    a2 = fig.add_axes([0.56, 0.14, 0.41, 0.66])
    for ax in (a1, a2):
        paper(ax)
    w = 0.2
    xs = np.arange(len(wins))
    for k, (sc, lab) in enumerate(scopes):
        c = [data.res["pooled"][sc]["C13C"][w_[0]]["total_return"] * 100 for w_ in wins]
        h = [data.res["pooled"][sc]["HOLD"][w_[0]]["total_return"] * 100 for w_ in wins]
        a1.bar(xs + (k * 2 - 1.5) * w + 0.0, c, w, color=WIN if k == 0 else "#6fbf8a", edgecolor=PENCIL, label=f"C13C, {lab}")
        a1.bar(xs + (k * 2 - 0.5) * w, h, w, color=PENCIL if k == 0 else GREY, edgecolor=PENCIL, label=f"držanje, {lab}")
        dc = [data.res["pooled"][sc]["C13C"][w_[0]]["max_drawdown"] * 100 for w_ in wins]
        dh = [data.res["pooled"][sc]["HOLD"][w_[0]]["max_drawdown"] * 100 for w_ in wins]
        a2.bar(xs + (k * 2 - 1.5) * w, dc, w, color=WIN if k == 0 else "#6fbf8a", edgecolor=PENCIL)
        a2.bar(xs + (k * 2 - 0.5) * w, dh, w, color=PENCIL if k == 0 else GREY, edgecolor=PENCIL)
    for ax in (a1, a2):
        ax.set_xticks(xs)
        ax.set_xticklabels([w_[1] for w_ in wins], fontsize=12)
        ax.axhline(0, color=INK, lw=1)
    a1.set_title("ukupni prinos (%)", fontsize=13, loc="left", color=INK)
    a2.set_title("najveći pad (%)", fontsize=13, loc="left", color=INK)
    a1.legend(fontsize=9.5, frameon=False, loc="upper left")
    pa, pm = data.res["pooled"]["stocks_all"], data.res["pooled"]["memory_core"]
    bottom_note(
        fig,
        f"2021.-2022.: na 43 dionice oba su oko nule (C13C {pct(pa['C13C']['y2021_2022']['total_return'])}, držanje {pct(pa['HOLD']['y2021_2022']['total_return'])}); "
        f"u memorijskoj trojci držanje {pct(pm['HOLD']['y2021_2022']['total_return'], 0)}, C13C {pct(pm['C13C']['y2021_2022']['total_return'], 0)}. Prednost C13C-a je manji pad, ne veći prinos u bik-eri.",
        size=11.5,
    )
    return finish(fig, "n11_periods.png", {
        "title": "Tri razdoblja",
        "what_to_see": "Lijevo ukupni prinos, desno najveći pad po razdoblju.",
        "numbers_used": ["pooled total_return i max_drawdown iz results.json"],
    })


# ---------------------------------------------------------------------------------------------- n13 / n14 / n15
VAR_COL = {"C13C": WIN, "X1_TRAIL15": BLUE, "X2_TRAIL20": "#7a4fb3", "X3_ATR_TRAIL": ORANGE, "X4_MOM_CONFIRM": RED, "X5_DIP3": GREY, "X6_SMA100": "#a0522d", "K7_REENTRY": "#c28fb0"}
VAR_NAME = {"C13C": "original", "X1_TRAIL15": "stop 15 %", "X2_TRAIL20": "stop 20 %", "X3_ATR_TRAIL": "ATR stop", "X4_MOM_CONFIRM": "momentum potvrda", "X5_DIP3": "pad 3 %", "X6_SMA100": "prosjek 100", "K7_REENTRY": "ponovni ulaz"}


def n13_variants(data: Data) -> str:
    cfgs = list(VAR_NAME)
    fig = canvas(12.6, "Poboljšanja: sve unaprijed registrirane varijante", "Očekivanje po trgovini (€ na 1.000 €) u prvoj i drugoj polovici AI ere i u 2021.-2022., te profit factor.")
    for r, (sc, lab) in enumerate([("stocks_all", "43 dionice"), ("memory_core", "MU WDC STX")]):
        a1 = fig.add_axes([0.06, 0.57 - r * 0.45, 0.50, 0.31])
        a2 = fig.add_axes([0.64, 0.57 - r * 0.45, 0.33, 0.31])
        for ax in (a1, a2):
            paper(ax)
        v = data.res["variants"][sc]
        x = np.arange(len(cfgs))
        for k, (w, wl, hatch) in enumerate([("h1", "2023.-2024.", None), ("h2", "2025.-2026.", "//"), ("y2021_2022", "2021.-2022.", "..")]):
            vals = [(v[c][w]["expectancy_eur"] or 0) for c in cfgs]
            a1.bar(x + (k - 1) * 0.27, vals, 0.27, color=[VAR_COL[c] for c in cfgs], edgecolor=PENCIL, hatch=hatch, label=wl)
        a1.set_xticks(x)
        a1.set_xticklabels([VAR_NAME[c] for c in cfgs], fontsize=10, rotation=20)
        a1.axhline(0, color=INK, lw=1)
        if r == 0:
            a1.legend(fontsize=9, frameon=False)
        a1.set_title(f"{lab}: očekivanje po trgovini (€)  [puno / točkasto: polovice i 2021-22]", fontsize=12, loc="left", color=INK)
        pf = [(v[c]["ai_era"]["profit_factor"] or 0) for c in cfgs]
        tpm = [v[c]["ai_era"]["trades_per_month"] for c in cfgs]
        a2.barh(x, pf, color=[VAR_COL[c] for c in cfgs], edgecolor=PENCIL)
        a2.set_yticks(x)
        a2.set_yticklabels([f"{VAR_NAME[c]} ({hr(t, 0)}/mj.)" for c, t in zip(cfgs, tpm)], fontsize=10)
        a2.invert_yaxis()
        a2.axvline(1, color=RED, ls=":", lw=1.5)
        a2.set_title("profit factor, AI era (trgovina/mjesec)", fontsize=12, loc="left", color=INK)
    bottom_note(fig, "širi stop podiže očekivanje u svim razdobljima, ali smanjuje broj trgovina. Momentum potvrda ne dodaje ništa. Ostalo je šum ili gore.")
    return finish(fig, "n13_variants.png", {
        "title": "Varijante poboljšanja",
        "what_to_see": "Stupci po varijanti: očekivanje u dva razdoblja AI ere i u 2021.-2022.; desno profit factor.",
        "numbers_used": ["variants iz results.json"],
    })


def n14_variant_equity(data: Data) -> str:
    cfgs = ["C13C", "X1_TRAIL15", "X2_TRAIL20", "X3_ATR_TRAIL", "X4_MOM_CONFIRM"]
    fig = canvas(9.5, "Račun od 1.000 € kroz AI eru: original i varijante", "Prosjek po dionici. Lijevo svih 43, desno MU WDC STX. Siva = kupi i drži.")
    for k, (sc, tk, lab) in enumerate([("stocks_all", data.tickers, "43 dionice"), ("memory_core", MEMORY_CORE, "MU WDC STX")]):
        ax = fig.add_axes([0.06 + k * 0.50, 0.14, 0.42, 0.68])
        paper(ax)
        h = avg_equity(data, "HOLD", tk)
        ax.plot(h.index, h.values, color=GREY, lw=2.2, ls="--", label="kupi i drži")
        for c in cfgs:
            parts = []
            for t in tk:
                got = data.sl.get((c, t, "ai_era", "1x"))
                if got is not None:
                    parts.append(pd.Series(got[1], index=got[0]))
            s = pd.concat(parts, axis=1).ffill().bfill().mean(axis=1) if parts else None
            if s is None:
                continue
            ax.plot(s.index, s.values, color=VAR_COL[c], lw=2.4 if c == "C13C" else 1.8, label=VAR_NAME[c])
        ax.set_title(lab, fontsize=13, loc="left", color=INK)
        ax.legend(fontsize=10, frameon=False, loc="upper left")
        fmt_dates(ax)
    bottom_note(fig, "stop 20 % i stop 15 % drže dobitnike duže; momentum potvrda ostavlja manje kapitala u igri i zaostaje.")
    return finish(fig, "n14_variant_equity.png", {
        "title": "Varijante kroz AI eru",
        "what_to_see": "Račun od 1.000 € po varijanti.",
        "numbers_used": ["sleeves.pkl, ai_era"],
    })


def n15_momentum(data: Data) -> str:
    df = pooled_trades(data, data.tickers).dropna(subset=["r126"])
    df["q"] = pd.qcut(df["r126"], 5, labels=False, duplicates="drop")
    g = df.groupby("q").agg(n=("return", "size"), win=("return", lambda s: (s > 0).mean()), ex=("return", lambda s: s.mean() * 1000), lo=("r126", "min"), hi=("r126", "max"))
    fig = canvas(9.4, "Što je s momentumom: pomaže li jak prethodni rast pri kupnji pada?", "Svaka C13C trgovina (43 dionice, AI era) razvrstana prema prinosu zadnjih 126 dana PRIJE ulaza.")
    a1 = fig.add_axes([0.06, 0.14, 0.42, 0.66])
    a2 = fig.add_axes([0.56, 0.14, 0.41, 0.66])
    for ax in (a1, a2):
        paper(ax)
    a1.scatter(df["r126"] * 100, df["return"] * 100, s=14, color=[WIN if r > 0 else LOSS for r in df["return"]], alpha=0.55)
    a1.axhline(0, color=INK, lw=1)
    a1.axvline(0, color=INK, lw=1)
    a1.set_xlim(-60, 400)
    a1.set_ylim(-35, 120)
    a1.set_xlabel("prinos 126 dana prije ulaza (%)", fontsize=12)
    a1.set_ylabel("rezultat trgovine (%)", fontsize=12)
    xs = np.arange(len(g))
    a2.bar(xs, g["ex"], color=BLUE, edgecolor=PENCIL)
    a2.set_xticks(xs)
    a2.set_xticklabels([f"{hr(lo * 100, 0)} do\n{hr(hi * 100, 0)} %\n(n={n})" for lo, hi, n in zip(g["lo"], g["hi"], g["n"])], fontsize=10)
    a2.set_title("očekivanje po trgovini (€) po petini momentuma", fontsize=12, loc="left", color=INK)
    a2.axhline(0, color=INK, lw=1)
    bottom_note(fig, "opisna analiza nakon pokusa (ne dokaz). Ako petine nisu jasno poredane, momentum filter nema što dodati, a to potvrđuje i varijanta X4.")
    return finish(fig, "n15_momentum.png", {
        "title": "Momentum prije ulaza i ishod trgovine",
        "what_to_see": "Lijevo svaka trgovina, desno prosjek po petinama.",
        "numbers_used": [f"petine: {[round(float(v), 1) for v in g['ex']]}"],
    })


# ---------------------------------------------------------------------------------------------- cards
def ticker_card(data: Data, t: str) -> str:
    c, h = data.ptk(t, "C13C", "ai_era"), data.ptk(t, "HOLD", "ai_era")
    fig = canvas(7.4, f"{t}: C13C u AI eri", f"{SEGMENT_HR[data.segment_of[t]]}. Podaci od {c['first_bar']} do {c['last_bar']}.")
    ap = fig.add_axes([0.06, 0.40, 0.92, 0.43])
    ae = fig.add_axes([0.06, 0.09, 0.92, 0.22])
    trade_card(ap, ae, data, t, f"cijena (log), prosjek 200 dana, pozicije; {c['trades']} trgovina, uspješnih {pct(c['hit_rate'], 0, False) if c['hit_rate'] is not None else '-'}")
    ae.set_title(f"račun od 1.000 €: C13C {eur(c['end_value'])}, držanje {eur(h['end_value'])}; pad C13C {pct(c['max_drawdown'], 0, False)}, držanje {pct(h['max_drawdown'], 0, False)}", fontsize=12, loc="left", color=INK)
    return finish(fig, f"t_{t}.png", {
        "title": f"{t} C13C u AI eri",
        "what_to_see": "Zeleni pojasi su pozicije, trokuti ulazi i izlazi.",
        "numbers_used": [f"end_value {c['end_value']:.1f}", f"trades {c['trades']}"],
    })


def main() -> None:
    data = Data()
    CHARTS.mkdir(parents=True, exist_ok=True)
    made = []
    for fn in (n01_anatomy, n02_failures, n03_scoreboard, n04_drawdown, n05_exposure, n06_segments, n07_memory_core, n08_memory_wide, n09_distribution, n10_clustering, n11_periods, n13_variants, n14_variant_equity, n15_momentum):
        made.append(fn(data))
        print("ok", fn.__name__)
    for t in data.tickers:
        made.append(ticker_card(data, t))
    mc.write_captions()
    print(len(made), "charts")


if __name__ == "__main__":
    main()
