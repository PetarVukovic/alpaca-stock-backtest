"""Notebook-style PNG charts for the "memory" segment page (squared paper, pencil, red teacher notes).

Reads only the REAL outputs of the simulator (results/*.json, segments/memory/analysis.json and
profile.json) and the daily CSVs in data/ohlcv. Writes PNGs next to the segment analysis.
Research only: nothing here touches a broker. Unique module name on purpose: other segment
builders live next to it in lab/aichain/.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from lab.aichain.profile_stats import pivots
from lab.top10.charts import GREEN, GRID, INK, PAPER, PENCIL, RED, sketch

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports/research/AICHAIN_20261014"
COMMON_END = pd.Timestamp("2026-10-05")
AI_START = pd.Timestamp("2023-01-03")
GREY = "#6b7280"
HAND = ["Noteworthy", "Bradley Hand", "Comic Sans MS", "DejaVu Sans"]
plt.rcParams.update(
    {
        "text.parse_math": False,
        "font.family": HAND,
        "font.size": 12.5,
        "axes.edgecolor": PENCIL,
        "text.color": PENCIL,
        "axes.labelcolor": PENCIL,
        "xtick.color": PENCIL,
        "ytick.color": PENCIL,
    }
)

NAMES = {
    "B0_BUYHOLD": "Kupi i drži",
    "K1_C13C_ORIG": "C13C (tvoje pravilo)",
    "K2_SMA200_TREND": "Drži iznad SMA200 (K2)",
    "K3_DONCHIAN_55_20": "Proboj 55/20 (K3)",
    "K4_TSMOM_126": "Zamah 126 dana (K4)",
    "K5_SUPPORT_RESISTANCE": "Potpora (K5)",
    "K5B_SR_BREAKOUT_RETEST": "Proboj i povratak (K5B)",
    "K6_MOMENTUM_CS": "Rotacija po zamahu (K6)",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C + ponovni ulaz (K7)",
}
MONTHS = ["sij", "velj", "ožu", "tra", "svi", "lip", "srp", "kol", "ruj", "lis", "stu", "pro"]


# ---------------------------------------------------------------- formatting
def hr(x: float, digits: int = 0) -> str:
    """Croatian number: dot for thousands, comma for decimals."""
    s = f"{x:,.{digits}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def eur(x: float) -> str:
    return f"{hr(x)} €"


def pc(x: float, digits: int = 1, sign: bool = False) -> str:
    """Percent text; x is already in percent."""
    body = f"{x:+,.{digits}f}" if sign else f"{x:,.{digits}f}"
    return body.replace(",", "§").replace(".", ",").replace("§", ".") + " %"


def day(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


# ---------------------------------------------------------------- drawing helpers
def paper(ax: Any, title: str) -> None:
    ax.set_facecolor(PAPER)
    ax.grid(True, color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", pad=14, color=INK)


def logfmt(ax: Any) -> None:
    """Plain number ticks on a log y axis (mathtext is disabled for the whole module)."""
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: hr(v)))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())


def place(ax: Any, x: Any, y: float, dx: float, dy: float) -> tuple[float, float]:
    """Axes-fraction spot near data point (x, y), shifted by (dx, dy) and kept inside the page."""
    px, py = ax.transAxes.inverted().transform(
        ax.transData.transform((mdates.date2num(pd.Timestamp(x)), y))
    )
    return (min(max(px + dx, 0.12), 0.95), min(max(py + dy, 0.08), 0.86))


def note(
    ax: Any,
    text: str,
    xy: tuple[Any, float],
    at: tuple[float, float],
    color: str = PENCIL,
    rad: float = 0.25,
    size: float = 11.5,
    ha: str = "left",
) -> None:
    """Handwritten note at axes-fraction `at`, pencil arrow to data point `xy`."""
    ann = ax.annotate(
        text,
        xy=xy,
        xycoords="data",
        xytext=at,
        textcoords="axes fraction",
        ha=ha,
        va="center",
        fontsize=size,
        color=color,
        zorder=8,
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.85),
        arrowprops=dict(
            arrowstyle="->", color=color, lw=1.5, connectionstyle=f"arc3,rad={rad}", shrinkB=5
        ),
    )
    if ann.arrow_patch is not None:
        sketch(ann.arrow_patch, 0.9, 60, 3)


def ring(ax: Any, x: Any, y: float, color: str = RED, size: int = 700) -> None:
    ax.scatter([x], [y], s=size, facecolors="none", edgecolors=color, linewidths=2.0, zorder=7)


def ai_line(ax: Any, ylow: float = 0.03) -> None:
    ax.axvline(AI_START, color=RED, ls="--", lw=1.3)
    ax.text(
        AI_START - pd.Timedelta(days=10),
        ylow,
        "AI era počinje (2023.), glavno mjerilo",
        transform=ax.get_xaxis_transform(),
        fontsize=10.5,
        color=RED,
        rotation=90,
        ha="right",
        va="bottom",
    )


def teacher(fig: Any, text: str, width: int = 105) -> None:
    fig.text(
        0.015,
        0.012,
        textwrap.fill("Bilješka učitelja: " + text, width),
        fontsize=11.5,
        color=RED,
        ha="left",
        va="bottom",
    )


def save(fig: Any, out: Path, name: str) -> str:
    fig.savefig(out / name, dpi=130, facecolor=PAPER)
    plt.close(fig)
    return name


# ---------------------------------------------------------------- data
def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def prices(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data/ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"])
    df = df.drop_duplicates("date").sort_values("date").set_index("date")
    df = df[df.index <= COMMON_END][["open", "high", "low", "close"]]
    df["sma200"] = df["close"].rolling(200).mean()
    return df


def equity_series(res: dict[str, Any], cid: str, per: float = 3.0) -> pd.Series:
    rows = res["contenders"][cid]["equity"]["ai_era"]
    return pd.Series({pd.Timestamp(d): v / per for d, v in rows})


def stop_path(px: pd.DataFrame, trade: dict[str, Any]) -> pd.Series:
    """Approximate K1 trailing stop of one trade: 90 % of the highest high so far, acts next session."""
    seg = px.loc[trade["entry_date"] : trade["exit_date"]]
    peak = trade["entry_price"]
    vals: dict[pd.Timestamp, float] = {}
    prev_stop = round(peak * 0.9, 2)
    for d, row in seg.iterrows():
        vals[d] = prev_stop  # the stop in force during this session
        peak = max(peak, row["high"])
        prev_stop = max(prev_stop, round(peak * 0.9, 2))
    return pd.Series(vals)


# ---------------------------------------------------------------- chart 1: price + trades
def chart_price(ticker: str, out: Path) -> dict[str, Any]:
    res = load_json(BASE / "results" / f"{ticker}.json")
    trades = res["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
    px = prices(ticker)
    view = px.loc["2022-01-03":]
    fig, ax = plt.subplots(figsize=(10, 7.4))
    fig.subplots_adjust(bottom=0.30, left=0.09, right=0.98, top=0.9)
    paper(ax, f"{ticker}: cijena, SMA200 i svaki ulaz/izlaz C13C")
    sketch(ax.plot(view.index, view["close"], color=INK, lw=1.6, label="zatvaranje")[0], 0.5, 60, 3)
    ax.plot(view.index, view["sma200"], color=GREY, lw=1.4, ls="--", label="SMA200 (prosjek 200 dana)")
    ax.set_yscale("log")
    logfmt(ax)
    ai_line(ax, 0.26)
    entries = [(pd.Timestamp(t["entry_date"]), t["raw_entry"]) for t in trades]
    stops = [(pd.Timestamp(t["exit_date"]), t["raw_exit"]) for t in trades if t["reason"] == "stop"]
    ends = [(pd.Timestamp(t["exit_date"]), t["raw_exit"]) for t in trades if t["reason"] != "stop"]
    ax.scatter(*zip(*entries), marker="^", s=70, color=GREEN, zorder=6, label="kupnja (C13C ulaz)")
    ax.scatter(*zip(*stops), marker="v", s=70, color=RED, zorder=6, label="izlaz stopom (automatska prodaja)")
    if ends:
        ax.scatter(*zip(*ends), marker="s", s=60, color=GREY, zorder=6, label="otvoreno, računato po zadnjoj cijeni")
    best = max(trades, key=lambda t: t["return"])
    worst = min(trades, key=lambda t: t["return"])
    sp = stop_path(px, best)
    ax.plot(sp.index, sp.values, color=RED, lw=1.8, ls=":", drawstyle="steps-post", zorder=5, label="klizni stop (primjer jednog posla)")
    first = trades[0]
    f_entry = pd.Timestamp(first["entry_date"])
    pos = px.index.get_loc(f_entry)
    sig_day = px.index[pos - 1]
    sig_close = px["close"].iloc[pos - 1]
    sig_prev = px["close"].iloc[pos - 1 - 5]
    drop = (sig_close / sig_prev - 1) * 100
    sma_v = px["sma200"].iloc[pos - 1]
    ax.set_xlim(pd.Timestamp("2021-11-15"), COMMON_END + pd.Timedelta(days=40))
    ax.set_ylim(float(view["close"].min()) * 0.8, float(view["close"].max()) * 1.9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    b_exit = pd.Timestamp(best["exit_date"])
    w_exit = pd.Timestamp(worst["exit_date"])
    note(ax, f"signal za kupnju: pad {pc(abs(drop), 1)} u 5 dana", (f_entry, first["raw_entry"]),
         place(ax, f_entry, first["raw_entry"], -0.02, 0.30), color=GREEN, rad=0.2, size=11)
    note(ax, f"najbolji posao {pc(best['return'] * 100, 1, True)}", (b_exit, best["raw_exit"]),
         place(ax, b_exit, best["raw_exit"], -0.06, 0.08), color=INK, rad=-0.2, size=11, ha="right")
    note(ax, f"najgori posao {pc(worst['return'] * 100, 1, True)}", (w_exit, worst["raw_exit"]),
         place(ax, w_exit, worst["raw_exit"], 0.0, -0.40), color=RED, rad=0.2, size=11, ha="center")
    gap_txt = "izlaz po otvaranju ispod stopa (jaz preko noći)" if worst["detail"] == "gap_stop" else "izlaz stopom"
    details = (
        f"signal {day(sig_day)}: pad {pc(abs(drop), 1)} u 5 dana ({hr(sig_prev, 2)} $ -> {hr(sig_close, 2)} $) uz cijenu iznad SMA200 ({hr(sma_v, 2)} $); "
        f"sutradan kupnja po {hr(first['raw_entry'], 2)} $. "
        f"Najbolji posao: {day(best['entry_date'])} po {hr(best['raw_entry'], 2)} $ -> {day(best['exit_date'])} po {hr(best['raw_exit'], 2)} $; "
        f"iz 1.000 € to je {eur(1000 * (1 + best['return']))}; crvena točkasta crta je njegov stop koji putuje gore s cijenom. "
        f"Najgori: {day(worst['entry_date'])} -> {day(worst['exit_date'])}, {gap_txt}, na 1.000 € to je {eur(1000 * worst['return'])}."
    )
    ax.legend(loc="upper left", frameon=False, fontsize=9.2, ncol=3, columnspacing=1.0, handletextpad=0.4)
    ax.set_ylabel("cijena u $ (logaritamska skala)")
    teacher(
        fig,
        details + " Logaritamska skala: jednaka udaljenost na grafu znači isti postotak (100 -> 200 $ je isto što i 500 -> 1.000 $).",
        width=118,
    )
    name = save(fig, out, f"01_price_{ticker}.png")
    return {
        "file": name,
        "n_trades": len(trades),
        "n_stop": len(stops),
        "best": best,
        "worst": worst,
        "first": first,
        "sig_drop": float(drop),
        "sig_day": str(sig_day.date()),
        "stop_final": float(sp.iloc[-1]),
    }


# ---------------------------------------------------------------- chart 2: equity
def chart_equity(seg: dict[str, Any], out: Path) -> dict[str, Any]:
    hold = equity_series(seg, "B0_BUYHOLD")
    c13 = equity_series(seg, "K1_C13C_ORIG")
    k4 = equity_series(seg, "K4_TSMOM_126")
    fig, ax = plt.subplots(figsize=(10, 6.4))
    fig.subplots_adjust(bottom=0.22, left=0.12, right=0.98, top=0.9)
    paper(ax, "Rast 1.000 €: držanje, C13C (pobjednik po Sharpeu) i najjači po prinosu")
    sketch(ax.plot(hold.index, hold, color=GREY, lw=1.8, label="kupi i drži")[0], 0.5, 60, 3)
    sketch(ax.plot(c13.index, c13, color=INK, lw=2.0, label="C13C (pobjednik po pravilu)")[0], 0.5, 60, 3)
    sketch(ax.plot(k4.index, k4, color=GREEN, lw=1.5, label="zamah 126 dana (K4, najviši prinos među pravilima)")[0], 0.5, 60, 3)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: eur(v)))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="upper left", frameon=False, fontsize=10.5)
    ax.set_ylabel("vrijednost 1.000 € od 3. 1. 2023.")
    dd_h = hold / hold.cummax() - 1
    t_h = dd_h.idxmin()
    p_h = hold.loc[:t_h].idxmax()
    flat = c13.diff().abs() < 1e-9
    best_n, cur, start, span = 0, 0, None, (None, None)
    for d, v in flat.items():
        if v:
            if cur == 0:
                start = d
            cur += 1
            if cur > best_n:
                best_n, span = cur, (start, d)
        else:
            cur = 0
    ret_h = hold.loc[t_h] / hold.loc[p_h] - 1
    ret_c = c13.loc[t_h] / c13.loc[p_h] - 1
    note(
        ax,
        f"od {day(p_h)} do {day(t_h)}:\ndržanje {eur(hold.loc[p_h])} -> {eur(hold.loc[t_h])} ({pc(ret_h * 100, 0, True)}),\n"
        f"C13C {eur(c13.loc[p_h])} -> {eur(c13.loc[t_h])} ({pc(ret_c * 100, 0, True)}).\n"
        f"Izlaskom iz dionica C13C je tu štetu smanjio.",
        (t_h, hold.loc[t_h]),
        (0.04, 0.47),
        color=RED,
        rad=-0.2,
        size=10.5,
    )
    ring(ax, t_h, hold.loc[t_h], RED, 600)
    if best_n >= 15:
        mid = span[0] + (span[1] - span[0]) / 2
        mid = c13.index[c13.index.get_indexer([mid], method="nearest")[0]]
        note(
            ax,
            f"ovdje {best_n} dana sve tri\nglave čekaju u gotovini:\nne gubi, ali ni ne zarađuje",
            (mid, c13.loc[mid]),
            (0.30, 0.66),
            color=INK,
            rad=0.25,
            size=10.5,
        )
    ax.text(0.97, 0.12, f"na kraju (5. 10. 2026.):\n  držanje {eur(hold.iloc[-1])}\n  C13C {eur(c13.iloc[-1])}\n  K4 {eur(k4.iloc[-1])}",
            transform=ax.transAxes, fontsize=11.5, color=PENCIL, va="center", ha="right")
    teacher(
        fig,
        "ako je plava crta ispod sive, strategija je zaradila manje od držanja. Ravni dijelovi plave crte znače da novac "
        "stoji u gotovini: štiti od pada, ali ne prati rast. Isti račun: 3 dionice po 1.000 €, prikaz po 1.000 €.",
    )
    name = save(fig, out, "02_equity.png")
    return {
        "file": name,
        "hold_end": float(hold.iloc[-1]),
        "c13_end": float(c13.iloc[-1]),
        "k4_end": float(k4.iloc[-1]),
        "fall_peak": str(p_h.date()),
        "fall_bottom": str(t_h.date()),
        "hold_peak_val": float(hold.loc[p_h]),
        "hold_bottom_val": float(hold.loc[t_h]),
        "c13_peak_val": float(c13.loc[p_h]),
        "c13_bottom_val": float(c13.loc[t_h]),
        "flat_days": int(best_n),
    }


# ---------------------------------------------------------------- chart 3: drawdown
def chart_drawdown(seg: dict[str, Any], out: Path) -> dict[str, Any]:
    hold = equity_series(seg, "B0_BUYHOLD")
    c13 = equity_series(seg, "K1_C13C_ORIG")
    dd_h = hold / np.maximum.accumulate(hold.to_numpy()) - 1
    dd_c = c13 / np.maximum.accumulate(c13.to_numpy()) - 1
    fig, ax = plt.subplots(figsize=(10, 5.8))
    fig.subplots_adjust(bottom=0.24, left=0.09, right=0.98, top=0.9)
    paper(ax, "Najgori trenuci: koliko vrijednost padne od vrha")
    ax.fill_between(dd_h.index, dd_h * 100, color="#9ca3af", alpha=0.45, label="kupi i drži")
    ax.fill_between(dd_c.index, dd_c * 100, color=RED, alpha=0.30, label="C13C")
    ax.set_ylim(dd_h.min() * 100 * 1.4, 24)
    ax.set_yticks([t for t in range(-60, 1, 10)])
    ax.set_ylabel("% ispod prethodnog vrha")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="lower right", frameon=False, fontsize=11)
    th, tc = dd_h.idxmin(), dd_c.idxmin()
    ring(ax, th, dd_h.min() * 100, GREY, 650)
    ring(ax, tc, dd_c.min() * 100, RED, 650)
    note(
        ax,
        f"držanje, dno {day(th)}: {pc(dd_h.min() * 100, 1)}\nako imaš 1.000 € na vrhu, ostane\n{eur(1000 * (1 + dd_h.min()))}, gubitak {eur(-1000 * dd_h.min())}",
        (th, dd_h.min() * 100),
        (0.14, 0.17),
        color=PENCIL,
        rad=0.25,
        size=10.5,
    )
    note(
        ax,
        f"C13C, dno {day(tc)}: {pc(dd_c.min() * 100, 1)}\nna 1.000 € gubitak {eur(-1000 * dd_c.min())},\ndakle {eur(1000 * (dd_c.min() - dd_h.min()))} manje",
        (tc, dd_c.min() * 100),
        (0.66, 0.20),
        color=RED,
        rad=0.3,
        size=10.5,
    )
    r_h = hold.pct_change().dropna()
    wd = r_h.idxmin()
    ax.annotate(
        f"najgori jedan dan (držanje): {pc(r_h.min() * 100, 1)}\n{day(wd)}, to je {eur(-1000 * r_h.min())} na 1.000 €",
        xy=(wd, dd_h.loc[wd] * 100),
        xytext=(0.20, 0.93),
        textcoords="axes fraction",
        fontsize=10.5,
        color=PENCIL,
        va="center",
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.85),
        arrowprops=dict(arrowstyle="->", color=PENCIL, lw=1.3, connectionstyle="arc3,rad=-0.2"),
    )
    ai_line(ax, 0.03)
    teacher(
        fig,
        "pad od vrha = koliko bi vrijednost pala od najboljeg do najgoreg trenutka. Pitaj se: bih li to izdržao bez da prodam? "
        "Manji pad nije besplatan, vidi sljedeći grafikon o cijeni te zaštite.",
    )
    name = save(fig, out, "03_drawdown.png")
    return {
        "file": name,
        "hold_dd": float(dd_h.min() * 100),
        "c13_dd": float(dd_c.min() * 100),
        "hold_bottom": str(th.date()),
        "c13_bottom": str(tc.date()),
        "worst_day": float(r_h.min() * 100),
        "worst_day_date": str(wd.date()),
    }


# ---------------------------------------------------------------- chart 4: trades
def chart_trades(seg: dict[str, Any], out: Path) -> dict[str, Any]:
    trades = seg["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
    df = pd.DataFrame(trades)
    df["ret"] = df["return"] * 100
    colors = {"MU": INK, "WDC": "#b8860b", "STX": "#8a2be2"}
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(bottom=0.22, left=0.09, right=0.98, top=0.9)
    paper(ax, "Svaki C13C posao: koliko dana je trajao i koliko je donio")
    for t, g in df.groupby("ticker"):
        ax.scatter(g["bars_held"], g["ret"], s=46, color=colors.get(t, GREY), alpha=0.85, label=t, edgecolors=PAPER, linewidths=0.6)
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_xlabel("dana u poziciji (trgovinskih dana)")
    ax.set_ylabel("prinos posla u %")
    ax.legend(loc="upper left", frameon=False, fontsize=11)
    b = df.loc[df["ret"].idxmax()]
    w = df.loc[df["ret"].idxmin()]
    wins, loss = df[df["ret"] > 0], df[df["ret"] <= 0]
    note(
        ax,
        f"najbolji: {b['ticker']} {pc(b['ret'], 1, True)}\n{day(b['entry_date'])} -> {day(b['exit_date'])}, {int(b['bars_held'])} dana\nna 1.000 € = {eur(1000 * b['ret'] / 100)} dobitka",
        (b["bars_held"], b["ret"]),
        (0.40, 0.84),
        color=GREEN,
        rad=-0.2,
    )
    note(
        ax,
        f"najgori: {w['ticker']} {pc(w['ret'], 1, True)}\n{day(w['entry_date'])} -> {day(w['exit_date'])}\nna 1.000 € = {eur(1000 * w['ret'] / 100)}",
        (w["bars_held"], w["ret"]),
        (0.45, 0.32),
        color=RED,
        rad=0.25,
    )
    ax.text(
        0.97,
        0.52,
        f"{len(wins)} dobitnih, {len(loss)} gubitnih od {len(df)}\nprosječni dobitak {pc(wins['ret'].mean(), 1, True)}\nprosječni gubitak {pc(loss['ret'].mean(), 1, True)}",
        transform=ax.transAxes,
        ha="right",
        fontsize=11.5,
        color=PENCIL,
        bbox=dict(boxstyle="round,pad=0.3", fc=PAPER, ec=GRID),
    )
    teacher(
        fig,
        "gubici su ograničeni stopom na oko 10 %, a dobici nisu ograničeni: nekoliko velikih poslova nosi većinu zarade. "
        f"Zato je dovoljno da dobitnih bude otprilike pola ({len(wins)} od {len(df)}), a dobitak je u prosjeku oko tri puta veći od gubitka.",
    )
    name = save(fig, out, "04_trades.png")
    return {
        "file": name,
        "n": int(len(df)),
        "wins": int(len(wins)),
        "avg_win": float(wins["ret"].mean()),
        "avg_loss": float(loss["ret"].mean()),
        "best": {k: (v if isinstance(v, str) else float(v)) for k, v in b.to_dict().items()},
        "worst": {k: (v if isinstance(v, str) else float(v)) for k, v in w.to_dict().items()},
        "gap_exits": int((df["detail"] == "gap_stop").sum()),
    }


# ---------------------------------------------------------------- chart 5: scoreboard
def chart_scoreboard(analysis: dict[str, Any], out: Path) -> dict[str, Any]:
    tab = analysis["segment_portfolio_table_ai_era"]
    order = [k for k in NAMES if k in tab and "total_return_pct" in tab[k]]
    ret = [tab[k]["total_return_pct"] for k in order]
    sh = [tab[k]["sharpe"] for k in order]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 6.2), sharey=True)
    fig.subplots_adjust(bottom=0.24, left=0.27, right=0.98, top=0.88, wspace=0.08)
    y = np.arange(len(order))[::-1]
    col = [GREY if k == "B0_BUYHOLD" else (INK if k == "K1_C13C_ORIG" else "#7aa7d6") for k in order]
    for ax, vals, title, unit in ((a1, ret, "Prinos u AI eri (%)", "%"), (a2, sh, "Sharpe u AI eri", "")):
        paper(ax, title)
        ax.title.set_fontsize(13.5)
        bars = ax.barh(y, vals, color=col, edgecolor=PENCIL, lw=0.8, hatch="//", alpha=0.85)
        for bar in bars:
            sketch(bar, 0.6, 50, 2)
        for yy, v in zip(y, vals):
            ax.text(v + (max(vals) * 0.015), yy, hr(v, 0 if unit else 2) + (" %" if unit else ""), va="center", fontsize=10.5)
        ax.axvline(vals[0], color=RED, ls="--", lw=1.4)
        ax.set_xlim(0, max(vals) * 1.25)
    a1.set_yticks(y, [NAMES[k] for k in order])
    a1.text(ret[0], y[0] + 0.62, "držanje", color=RED, fontsize=10.5, ha="right")
    a2.text(sh[0], y[0] + 0.62, "držanje", color=RED, fontsize=10.5, ha="right")
    k1 = order.index("K1_C13C_ORIG")
    a2.set_xlim(0, max(sh) * 1.55)
    a2.text(sh[0] + 0.12, y[k1], "<- gotovo isto kao\n    držanje (1,78 : 1,85)", fontsize=10.5, color=INK, va="center")
    teacher(
        fig,
        "crvena crtica je držanje. Nijedno pravilo ne preskače crvenu crtu po prinosu; po Sharpeu je najbliže C13C. "
        "Sharpe = dobit po jedinici nemira: veći je bolji, ali ne vidi propušteni rast.",
    )
    name = save(fig, out, "05_scoreboard.png")
    return {"file": name, "order": order}


# ---------------------------------------------------------------- chart 6: cost robustness
def chart_costs(analysis: dict[str, Any], out: Path) -> dict[str, Any]:
    tab = analysis["segment_portfolio_table_ai_era"]
    order = [k for k in NAMES if k in tab and "total_return_pct" in tab[k]]
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(bottom=0.34, left=0.28, right=0.97, top=0.9)
    paper(ax, "Ostaje li zarada ako su troškovi 2x i 3x veći?")
    y = np.arange(len(order))[::-1]
    w = 0.26
    rows: dict[str, dict[str, float]] = {}
    for off, key, lab, c in (
        (w, "total_return_pct", "troškovi 1x (2,5 bps po strani)", INK),
        (0, "return_cost_2x_pct", "2x (5 bps)", "#7aa7d6"),
        (-w, "return_cost_3x_pct", "3x (7,5 bps)", RED),
    ):
        vals = [tab[k][key] / tab[k]["total_return_pct"] * 100 for k in order]
        ax.barh(y + off, vals, height=w * 0.86, color=c, alpha=0.85, edgecolor=PENCIL, lw=0.6, label=lab)
    for k in order:
        rows[k] = {
            "end1": 1000 * (1 + tab[k]["total_return_pct"] / 100),
            "end3": 1000 * (1 + tab[k]["return_cost_3x_pct"] / 100),
            "kept": tab[k]["return_cost_3x_pct"] / tab[k]["total_return_pct"] * 100,
        }
    for yy, k in zip(y, order):
        ax.text(100.8, yy, f"{eur(rows[k]['end1'])} -> {eur(rows[k]['end3'])}", va="center", fontsize=10.2, color=PENCIL)
    ax.set_yticks(y, [NAMES[k] for k in order])
    ax.set_xlim(78, 120)
    ax.axvline(100, color=PENCIL, lw=1.2)
    ax.set_xlabel("koliko % zarade ostane (100 % = zarada uz osnovne troškove)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, frameon=False, fontsize=10.5)
    k1, k7 = rows["K1_C13C_ORIG"], rows["K7_C13C_PLUS_TREND_REENTRY"]
    note(
        ax,
        f"C13C: od 1.000 € ostane\n{eur(k1['end3'])} umjesto\n{eur(k1['end1'])} ({pc(k1['kept'], 0)} zarade)",
        (k1["kept"], y[order.index("K1_C13C_ORIG")] - w),
        (0.03, 0.58),
        color=INK,
        rad=-0.2,
        size=10.5,
    )
    note(
        ax,
        f"K7 trguje najčešće\n(160 poslova), pa gubi\nnajviše: {pc(k7['kept'], 0)} zadržano",
        (k7["kept"], y[order.index("K7_C13C_PLUS_TREND_REENTRY")] - w),
        (0.03, 0.25),
        color=RED,
        rad=0.25,
        size=10.5,
    )
    teacher(
        fig,
        "svaka kupnja i prodaja nešto košta (kod nas 0,25 € na 1.000 €). Što pravilo češće trguje, to ga skuplje koštaju 2x i 3x veći troškovi. "
        "Vodoravno vidiš postotak zarade koji preživi. Napomena: stvarna minimalna provizija IBKR-a nije modelirana (nepotvrđeno).",
    )
    name = save(fig, out, "06_costs.png")
    return {"file": name, "rows": rows}


# ---------------------------------------------------------------- chart 7: lesson
def chart_lesson(analysis: dict[str, Any], out: Path) -> dict[str, Any]:
    tab = analysis["segment_portfolio_table_ai_era"]
    order = [k for k in NAMES if k in tab and "total_return_pct" in tab[k]]
    fig, ax = plt.subplots(figsize=(10, 6.4))
    fig.subplots_adjust(bottom=0.22, left=0.13, right=0.98, top=0.9)
    paper(ax, "Pouka segmenta: manji pad je skup")
    offs = {  # label offset (dx in pad points, y multiplier, horizontal alignment)
        "B0_BUYHOLD": (-0.5, 1.13, "center"),
        "K4_TSMOM_126": (0.8, 1.02, "left"),
        "K2_SMA200_TREND": (-0.8, 1.0, "right"),
        "K6_MOMENTUM_CS": (0.0, 0.84, "center"),
        "K3_DONCHIAN_55_20": (0.8, 0.98, "left"),
        "K1_C13C_ORIG": (0.8, 0.9, "left"),
        "K7_C13C_PLUS_TREND_REENTRY": (0.8, 0.94, "left"),
        "K5B_SR_BREAKOUT_RETEST": (0.8, 0.95, "left"),
        "K5_SUPPORT_RESISTANCE": (0.8, 1.0, "left"),
    }
    for k in order:
        x = -tab[k]["max_drawdown_pct"]
        yv = tab[k]["end_value_per_1000_eur"]
        c = GREY if k == "B0_BUYHOLD" else (INK if k == "K1_C13C_ORIG" else "#7aa7d6")
        ax.scatter([x], [yv], s=130, color=c, edgecolors=PENCIL, zorder=5)
        dx, mult, ha = offs[k]
        ax.text(x + dx, yv * mult, NAMES[k], fontsize=10.2, color=PENCIL, ha=ha, va="center")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: eur(v)))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_xlabel("najveći pad od vrha u % (lijevo = mirnije)")
    ax.set_ylabel("od 1.000 € na kraju (log. skala)")
    w = analysis["winner"]["winner_vs_hold"]
    h, c13 = tab["B0_BUYHOLD"], tab["K1_C13C_ORIG"]
    note(
        ax,
        f"C13C: pad {pc(-c13['max_drawdown_pct'], 1)} umjesto {pc(-h['max_drawdown_pct'], 1)}.\nNajgori gubitak na 1.000 € je {eur(w['worst_loss_per_1000_eur_winner'])}\numjesto {eur(w['worst_loss_per_1000_eur_hold'])}: ušteda {eur(w['worst_loss_saved_eur'])}.",
        (-c13["max_drawdown_pct"], c13["end_value_per_1000_eur"]),
        (0.04, 0.68),
        color=INK,
        rad=-0.2,
    )
    note(
        ax,
        f"cijena te zaštite: završna vrijednost\n{eur(c13['end_value_per_1000_eur'])} umjesto {eur(h['end_value_per_1000_eur'])},\ndakle {eur(w['end_value_given_up_eur'])} manje",
        (-h["max_drawdown_pct"], h["end_value_per_1000_eur"]),
        (0.50, 0.24),
        color=RED,
        rad=-0.25,
    )
    ax.set_xlim(15, 56)
    ax.set_ylim(1200, 32000)
    teacher(
        fig,
        "svaka točka je jedno pravilo. Gore desno = najviše novca ali i najveći pad; dolje lijevo = mirnije ali puno manje novca. "
        "U ovom razdoblju (duga AI-era uzlazna faza) osiguranje je bilo vrlo skupo. To ne znači da će tako biti i ubuduće.",
    )
    name = save(fig, out, "07_lesson.png")
    return {"file": name}


# ---------------------------------------------------------------- behaviour charts
def chart_dip(profile: dict[str, Any], tickers: list[str], out: Path) -> dict[str, Any]:
    fig, axes = plt.subplots(1, len(tickers), figsize=(10.4, 5.4), sharey=True)
    fig.subplots_adjust(bottom=0.26, left=0.08, right=0.99, top=0.84, wspace=0.08)
    vals: dict[str, dict[str, float]] = {}
    for ax, t in zip(axes, tickers):
        s = profile["stats"][t]
        a, c = s["ai_era_2023plus"], s["context_2016_2022"]
        v = [
            c["after_5d_drop_above_sma200"]["h5"]["uncond_mean"] * 100,
            c["after_5d_drop_above_sma200"]["h5"]["mean"] * 100,
            a["after_5d_drop_above_sma200"]["h5"]["uncond_mean"] * 100,
            a["after_5d_drop_above_sma200"]["h5"]["mean"] * 100,
        ]
        vals[t] = {
            "pre_normal": v[0],
            "pre_dip": v[1],
            "ai_normal": v[2],
            "ai_dip": v[3],
            "n_ind": a["after_5d_drop_above_sma200"]["n_independent_20d"],
        }
        paper(ax, t)
        ax.title.set_fontsize(14)
        cols = ["#c9ced6", "#9db4d4", "#b9bec7", INK]
        bars = ax.bar(range(4), v, color=cols, edgecolor=PENCIL, hatch="//", lw=0.8)
        for bar in bars:
            sketch(bar, 0.6, 50, 2)
        for i, x in enumerate(v):
            ax.text(i, x + 0.12, pc(x, 1), ha="center", fontsize=10.2)
        ax.set_xticks(range(4), ["običan\ndan\nprije", "nakon\npada\nprije", "običan\ndan\nAI era", "nakon\npada\nAI era"], fontsize=9)
        ax.set_ylim(0, 7.0)
    axes[0].set_ylabel("prosječan prinos idućih 5 dana (%)")
    t0 = tickers[0]
    note(
        axes[0],
        f"AI era: nakon pada od 5 % u 5 dana\n(a iznad SMA200) idućih 5 dana\nu prosjeku {pc(vals[t0]['ai_dip'], 1)} naspram {pc(vals[t0]['ai_normal'], 1)}",
        (3, vals[t0]["ai_dip"]),
        (0.05, 0.93),
        color=INK,
        rad=-0.2,
        size=10,
    )
    teacher(
        fig,
        f"na 1.000 € ({t0}) to bi bilo oko {eur(10 * vals[t0]['ai_dip'])} u 5 dana nakon takvog pada, naspram {eur(10 * vals[t0]['ai_normal'])} običnog tjedna. "
        f"Pažnja: samo oko {vals[t0]['n_ind']} neovisnih događaja po dionici, a prije 2023. razlika je bila mnogo manja. Opis prošlosti, ne dokaz.",
    )
    name = save(fig, out, "08_dip.png")
    return {"file": name, "vals": vals}


def chart_season(profile: dict[str, Any], tickers: list[str], out: Path) -> dict[str, Any]:
    fig, axes = plt.subplots(len(tickers), 1, figsize=(10, 8.6), sharex=True)
    fig.subplots_adjust(bottom=0.2, left=0.09, right=0.98, top=0.92, hspace=0.35)
    info: dict[str, Any] = {}
    for ax, t in zip(axes, tickers):
        sm = profile["stats"][t]["ai_era_2023plus"]["seasonality_month"]
        v = [sm[str(m)]["mean"] * 100 for m in range(1, 13)]
        n = [sm[str(m)]["n_years"] for m in range(1, 13)]
        paper(ax, f"{t}: prosječan prinos po mjesecu, AI era")
        ax.title.set_fontsize(13)
        bars = ax.bar(range(12), v, color=[GREEN if x >= 0 else RED for x in v], alpha=0.75, edgecolor=PENCIL, hatch="//", lw=0.7)
        for bar in bars:
            sketch(bar, 0.6, 50, 2)
        ax.axhline(0, color=PENCIL, lw=1)
        ax.set_xticks(range(12), [f"{MONTHS[i]}\n({n[i]} god.)" for i in range(12)], fontsize=9.2)
        ax.set_ylabel("%")
        ib, iw = int(np.argmax(v)), int(np.argmin(v))
        info[t] = {"best_m": ib + 1, "best": v[ib], "worst_m": iw + 1, "worst": v[iw]}
        ax.annotate(f"najbolji: {MONTHS[ib]} {pc(v[ib], 0, True)}", xy=(ib, v[ib]), xytext=(ib + 0.8, v[ib] * 0.9), fontsize=10.5, color=GREEN)
        ax.annotate(f"najlošiji: {MONTHS[iw]} {pc(v[iw], 0, True)}", xy=(iw, v[iw]), xytext=(iw + 0.8, v[iw]), fontsize=10.5, color=RED)
        ax.set_ylim(min(v) * 1.6 - 2, max(v) * 1.35 + 2)
    teacher(
        fig,
        "UPOZORENJE: svaki mjesec ima samo 3 do 4 opservacije (po jedna godišnje), pa je ovo gotovo sigurno slučajnost. "
        "Primjer: 'svibanj +32 %' na 1.000 € zvuči sjajno, ali je to četiri svibnja u jednom rastućem razdoblju. Nemoj trgovati po kalendaru.",
    )
    name = save(fig, out, "09_season.png")
    return {"file": name, "info": info}


def chart_drawdowns(cards: dict[str, Any], tickers: list[str], out: Path) -> dict[str, Any]:
    fig, axes = plt.subplots(len(tickers), 1, figsize=(10, 12.4))
    fig.subplots_adjust(bottom=0.1, left=0.09, right=0.98, top=0.95, hspace=0.42)
    info: dict[str, Any] = {}
    for ax, t in zip(axes, tickers):
        px = prices(t).loc["2023-01-03":]
        d = cards[t]["worst_drawdowns"][0]
        pk, bt = pd.Timestamp(d["peak_date"]), pd.Timestamp(d["bottom_date"])
        rc = pd.Timestamp(d["recovery_date"]) if d.get("recovery_date") else None
        paper(ax, f"{t}: anatomija najvećeg pada ({pc(d['depth_pct'], 1)})")
        ax.title.set_fontsize(13.5)
        sketch(ax.plot(px.index, px["close"], color=INK, lw=1.4)[0], 0.5, 60, 3)
        ax.axvspan(pk, bt, color=RED, alpha=0.13, lw=0)
        if rc is not None:
            ax.axvspan(bt, rc, color=GREEN, alpha=0.10, lw=0)
        ax.set_yscale("log")
        logfmt(ax)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.scatter([pk], [d["peak_close"]], s=70, color=GREEN, zorder=6)
        ax.scatter([bt], [d["bottom_close"]], s=70, color=RED, zorder=6)
        ax.set_ylim(float(px["close"].min()) * 0.4, float(px["close"].max()) * 1.6)
        ax.set_xlim(px.index[0] - pd.Timedelta(days=20), px.index[-1] + pd.Timedelta(days=25))
        note(ax, f"vrh {day(pk)}\nzatvaranje {hr(d['peak_close'], 2)} $", (pk, d["peak_close"]),
             place(ax, pk, d["peak_close"], -0.06, 0.22), color=GREEN, rad=0.15, size=10.5, ha="right")
        txt = f"dno {day(bt)}, {hr(d['bottom_close'], 2)} $\n{pc(d['depth_pct'], 1)}: od 1.000 € ostane {eur(d['left_of_1000_eur'])}"
        bx, _ = place(ax, bt, d["bottom_close"], -0.03, 0.0)
        note(ax, txt, (bt, d["bottom_close"]), (bx, 0.09), color=RED, rad=0.2, size=10.5, ha="right")
        if rc is not None:
            ax.text(0.62, 0.62, f"oporavak do starog vrha\n{day(rc)}\n({(rc - bt).days} dana nakon dna)", transform=ax.transAxes, fontsize=10.5, color=GREEN)
        else:
            ax.text(0.62, 0.62, "do kraja podataka\nnije dosegao stari vrh", transform=ax.transAxes, fontsize=10.5, color=RED)
        info[t] = {"peak": d["peak_date"], "bottom": d["bottom_date"], "recovery": d.get("recovery_date"), "days_down": (bt - pk).days}
        ax.set_ylabel("cijena u $ (log.)")
    teacher(
        fig,
        "crveno = put od vrha do dna, zeleno = put natrag do starog vrha. Pad od 58 % traži rast od 137 % samo da se vratiš na staro: "
        "zato 1.000 € koji padne na 422 € mora više nego udvostručiti da bi opet bio 1.000 €.",
    )
    name = save(fig, out, "10_drawdowns.png")
    return {"file": name, "info": info}


def chart_support(ticker: str, out: Path, profile: dict[str, Any]) -> dict[str, Any]:
    """Mark confirmed swing lows and their first touch (held / broke) on the price chart."""
    px = prices(ticker)
    lo, hi, c = px["low"].to_numpy(), px["high"].to_numpy(), px["close"].to_numpy()
    plows, _ = pivots(lo, hi)
    band, look, k = 0.015, 5, 5
    events = []
    for p in plows:
        lvl = lo[p]
        for t in range(p + k + 1, min(len(c) - look - 1, p + 250)):
            if c[t] < lvl * (1 - band):
                break
            if lo[t] <= lvl * (1 + band) and c[t - 1] > lvl * (1 + band):
                broke = bool((c[t : t + look + 1] < lvl * (1 - band)).any())
                events.append((px.index[p], px.index[t], lvl, broke))
                break
    ai = [e for e in events if e[1] >= AI_START]
    view_from = pd.Timestamp("2025-01-02")
    show = [e for e in ai if e[1] >= view_from]
    held = sum(1 for e in ai if not e[3])
    fig, ax = plt.subplots(figsize=(10, 6.4))
    fig.subplots_adjust(bottom=0.24, left=0.09, right=0.98, top=0.9)
    paper(ax, f"{ticker}: potpore (raniji lokalni minimumi) i što se dogodilo pri dodiru")
    v = px.loc[view_from:]
    sketch(ax.plot(v.index, v["close"], color=INK, lw=1.4)[0], 0.5, 60, 3)
    ax.set_yscale("log")
    logfmt(ax)
    for pdt, tdt, lvl, broke in show:
        col = RED if broke else GREEN
        ax.hlines(lvl, max(pdt, view_from), tdt, color=col, lw=1.4, ls="--")
        ax.scatter([tdt], [lvl], s=60, color=col, zorder=6, marker="x" if broke else "o")
    ax.scatter([], [], color=GREEN, marker="o", label="potpora je držala (5 dana nakon dodira)")
    ax.scatter([], [], color=RED, marker="x", label="potpora je probijena")
    ax.legend(loc="upper left", frameon=False, fontsize=10.5)
    ax.set_ylabel("cijena u $ (log.)")
    sr = profile["stats"][ticker]["ai_era_2023plus"]
    sup, ctl = sr["support_resistance"]["support"], sr["support_resistance_control_any_bar"]["support"]
    ex_held = next((e for e in show if not e[3]), None)
    ex_broke = next((e for e in show if e[3]), None)
    if ex_held:
        note(ax, f"primjer: razina {hr(ex_held[2], 2)} $ iz {day(ex_held[0])}\ndodirnuta {day(ex_held[1])}, držala", (ex_held[1], ex_held[2]), (0.30, 0.30), color=GREEN, rad=0.2, size=10.5)
    if ex_broke:
        note(ax, f"primjer: razina {hr(ex_broke[2], 2)} $ iz {day(ex_broke[0])}\ndodirnuta {day(ex_broke[1])}, probijena", (ex_broke[1], ex_broke[2]), (0.28, 0.12), color=RED, rad=-0.2, size=10.5)
    ax.text(
        0.97, 0.52,
        f"cijela AI era, {ticker}: {sup['touches']} dodira,\nrazina držala {pc(sup['hold_rate'] * 100, 0)};\nnasumična razina: {pc(ctl['hold_rate'] * 100, 0)}",
        transform=ax.transAxes, ha="right", fontsize=11.5, color=PENCIL,
        bbox=dict(boxstyle="round,pad=0.3", fc=PAPER, ec=GRID),
    )
    teacher(
        fig,
        "'držala' znači da u idućih 5 dana nema zatvaranja više od 1,5 % ispod razine. Brojke u kutiji vrijede za cijelu AI eru; na grafu je radi preglednosti samo 2025.-2026. "
        "Ključno: nasumično odabrana razina drži gotovo jednako često, pa crta potpore sama nije razlog za kupnju.",
    )
    name = save(fig, out, f"11_support_{ticker}.png")
    return {
        "file": name,
        "my_touches_ai": len(ai),
        "my_held_ai": held,
        "profile_touches": sup["touches"],
        "profile_hold": sup["hold_rate"],
    }


# ---------------------------------------------------------------- driver
def make_all(segment: str = "memory") -> dict[str, Any]:
    seg_dir = BASE / "segments" / segment
    analysis = load_json(seg_dir / "analysis.json")
    profile = load_json(seg_dir / "profile.json")
    seg = load_json(BASE / "results" / f"{segment}.json")
    tickers: list[str] = analysis["tickers_used"]
    cards = analysis["behaviour_cards"]
    info: dict[str, Any] = {"price": {}}
    for t in tickers:
        info["price"][t] = chart_price(t, seg_dir)
    info["equity"] = chart_equity(seg, seg_dir)
    info["drawdown"] = chart_drawdown(seg, seg_dir)
    info["trades"] = chart_trades(seg, seg_dir)
    info["scoreboard"] = chart_scoreboard(analysis, seg_dir)
    info["costs"] = chart_costs(analysis, seg_dir)
    info["lesson"] = chart_lesson(analysis, seg_dir)
    info["dip"] = chart_dip(profile, tickers, seg_dir)
    info["season"] = chart_season(profile, tickers, seg_dir)
    info["drawdowns"] = chart_drawdowns(cards, tickers, seg_dir)
    info["support"] = chart_support(tickers[0], seg_dir, profile)
    return info


if __name__ == "__main__":
    result = make_all()
    target = BASE / "segments/memory/chart_info.json"
    with target.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1, default=str)
    print("memory charts done")
