"""Six notebook-style charts per strategy: squared paper, pencil and ink, handwritten teacher notes (Croatian).

Every chart explains itself with a concrete euro example computed from the strategy's own numbers.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

INK, PENCIL, RED, GREEN, GRID, PAPER = (
    "#1d3fb8",
    "#3b3b42",
    "#c2321f",
    "#17803d",
    "#c7daee",
    "#fffef9",
)
HAND = ["Noteworthy", "Bradley Hand", "Comic Sans MS", "DejaVu Sans"]
SHADE = {"IS": "#eef0f4", "WF": "#e6f0fb", "HO": "#e8f6ea"}
LABELS = {"IS": "uzorak (IS)", "WF": "provjera (WF)", "HO": "ispit (HO)"}
plt.rcParams.update(
    {
        "font.family": HAND,
        "font.size": 11,
        "axes.edgecolor": PENCIL,
        "text.color": PENCIL,
        "axes.labelcolor": PENCIL,
        "xtick.color": PENCIL,
        "ytick.color": PENCIL,
    }
)


def eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def day(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:+.{digits}f} %".replace(".", ",")


def sketch(
    artist: Any, scale: float = 0.8, length: int = 70, randomness: int = 3
) -> Any:
    artist.set_sketch_params(scale, length, randomness)
    return artist


def paper(ax: Any, title: str) -> None:
    ax.set_facecolor(PAPER)
    ax.grid(True, color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", pad=22, color=INK)


def near(
    ax: Any, xy: tuple[Any, float], dx: float, dy: float, xmax: float = 0.56
) -> tuple[float, float]:
    """Axes-fraction position for a note placed close to a data point, kept inside the page."""
    import matplotlib.dates as mdates

    px, py = ax.transAxes.inverted().transform(
        ax.transData.transform((mdates.date2num(pd.Timestamp(xy[0])), xy[1]))
    )
    return (min(max(px + dx, 0.03), xmax), min(max(py + dy, 0.12), 0.9))


def note(
    ax: Any,
    text: str,
    xy: tuple[Any, float],
    xytext: tuple[float, float],
    color: str = PENCIL,
    rad: float = 0.25,
    size: float = 11.5,
    ha: str = "left",
) -> Any:
    """A handwritten note with a pencil arrow pointing at xy (data coordinates) from xytext (axes fraction)."""
    ann = ax.annotate(
        text,
        xy=xy,
        xycoords="data",
        xytext=xytext,
        textcoords="axes fraction",
        ha=ha,
        va="center",
        fontsize=size,
        color=color,
        arrowprops=dict(
            arrowstyle="->",
            color=color,
            lw=1.5,
            connectionstyle=f"arc3,rad={rad}",
            shrinkB=4,
        ),
    )
    if ann.arrow_patch is not None:
        sketch(ann.arrow_patch, 0.9, 60, 3)
    return ann


def times(ax: Any) -> None:
    from matplotlib.ticker import FuncFormatter, NullFormatter

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_ylabel("koliko puta veća vrijednost")


def ring(ax: Any, x: Any, y: float, color: str = RED, size: int = 900) -> None:
    ax.scatter(
        [x], [y], s=size, facecolors="none", edgecolors=color, linewidths=2.0, zorder=5
    )


def teacher(fig: Any, text: str) -> None:
    fig.text(
        0.012,
        0.012,
        "Bilješka učitelja: " + text,
        fontsize=11.5,
        color=RED,
        ha="left",
        va="bottom",
        wrap=True,
    )


def shade(ax: Any, bounds: dict[str, tuple[str, str]]) -> None:
    for name, (a, b) in bounds.items():
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=SHADE[name], alpha=0.8, lw=0)
        ax.text(
            pd.Timestamp(a),
            1.012,
            LABELS[name],
            transform=ax.get_xaxis_transform(),
            fontsize=9.5,
            color="#6b7280",
        )


def ai_era(ax: Any, ylow: float = 0.04) -> None:
    ax.axvline(pd.Timestamp("2023-01-01"), color=RED, ls="--", lw=1.3)
    ax.text(
        pd.Timestamp("2023-01-20"),
        ylow,
        "od ovdje: AI era,\nnova pravila igre",
        transform=ax.get_xaxis_transform(),
        fontsize=10,
        color=RED,
    )


def longest_zero_run(flag: pd.Series) -> tuple[int, tuple[Any, Any]]:
    best, cur, start, best_span = 0, 0, None, (None, None)
    for i, (idx, v) in enumerate(flag.items()):
        if v:
            if cur == 0:
                start = idx
            cur += 1
            if cur > best:
                best, best_span = cur, (start, idx)
        else:
            cur = 0
    return best, best_span


def save(fig: Any, out: Path, name: str) -> str:
    fig.savefig(out / name, dpi=140, facecolor=PAPER)
    plt.close(fig)
    return name


def make_charts(
    summary: dict[str, Any], bundle: dict[str, Any], outdir: str | Path
) -> dict[str, str]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    bt, pan, trades, bounds = (
        bundle["bt"],
        bundle["pan"],
        bundle["trades"],
        bundle["bounds"],
    )
    start = bounds["IS"][0]
    net, bench = bt["net"].loc[start:], bt["bench"].loc[start:]
    eq, beq = (1 + net).cumprod(), (1 + bench).cumprod()
    pos = bt["pos"].loc[start:]
    cash = pos.sum(axis=1) <= 1e-9
    files = {}

    # 1) growth of money
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    fig.subplots_adjust(bottom=0.2)
    paper(ax, "Rast tvojih novaca")
    shade(ax, bounds)
    sketch(
        ax.plot(eq.index, eq, color=INK, lw=2.0, label="strategija (nakon troškova)")[
            0
        ],
        0.6,
        60,
        4,
    )
    sketch(
        ax.plot(
            beq.index,
            beq,
            color="#6b7280",
            lw=1.4,
            label="kupi i drži (isti instrumenti)",
        )[0],
        0.6,
        60,
        4,
    )
    ax.set_yscale("log")
    ax.legend(loc="lower right", frameon=False, fontsize=10.5)
    ai_era(ax)
    n, (a, b) = longest_zero_run(cash)
    if n > 40 and a is not None:
        mid = eq.index[eq.index.get_indexer([a + (b - a) / 2], method="nearest")[0]]
        note(
            ax,
            f"ovdje {n} dana čeka\nu gotovini: ne gubi,\nali ni ne zarađuje",
            (mid, float(eq.loc[mid])),
            near(ax, (mid, float(eq.loc[mid])), -0.05, 0.3),
            rad=-0.3,
        )
    s_end, b_end = float(eq.iloc[-1]), float(beq.iloc[-1])
    ax.text(
        0.03,
        0.93,
        f"1.000 € u strategiji → {eur(1000 * s_end)}",
        transform=ax.transAxes,
        fontsize=12.5,
        color=INK,
    )
    ax.text(
        0.03,
        0.86,
        f"1.000 € kupi-i-drži → {eur(1000 * b_end)}",
        transform=ax.transAxes,
        fontsize=12.5,
        color="#4b5563",
    )
    times(ax)
    teacher(
        fig,
        "ako je plava crta iznad sive, strategija je bolja od običnog držanja. Ravni dijelovi plave = čeka u gotovini.",
    )
    files["equity"] = save(fig, out, "01_equity.png")

    # 2) worst fall
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    fig.subplots_adjust(bottom=0.24)
    paper(ax, "Najgori trenuci (pad od vrha)")
    shade(ax, bounds)
    dd, bdd = eq / eq.cummax() - 1, beq / beq.cummax() - 1
    ax.fill_between(
        bdd.index, bdd * 100, color="#9ca3af", alpha=0.35, label="kupi i drži"
    )
    ax.fill_between(dd.index, dd * 100, color=RED, alpha=0.30, label="strategija")
    ax.set_ylim(min(dd.min(), bdd.min()) * 100 * 1.35, 6)
    ai_era(ax, 0.9)
    worst = dd.idxmin()
    ring(ax, worst, dd.min() * 100, RED, 700)
    note(
        ax,
        f"najgore: {pct(dd.min())} ({day(worst)})\nod 1.000 € ostalo bi samo {eur(1000 * (1 + dd.min()))}",
        (worst, dd.min() * 100),
        near(ax, (worst, dd.min() * 100), -0.32, 0.22),
        color=RED,
        rad=0.25,
    )
    ax.legend(loc="lower right", frameon=False, fontsize=10.5)
    ax.set_ylabel("% ispod prethodnog vrha")
    teacher(
        fig,
        "pad od vrha = koliko bi vrijednost pala od najboljeg do najgoreg trenutka. Pitaj se: bih li to izdržao bez da prodam?",
    )
    files["drawdown"] = save(fig, out, "02_drawdown.png")

    # 3) year by year
    years = sorted(summary["yearly"])
    sv = np.array([summary["yearly"][y]["strategy"] for y in years]) * 100
    bv = (
        np.array([np.nan_to_num(summary["yearly"][y]["benchmark"]) for y in years])
        * 100
    )
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    fig.subplots_adjust(bottom=0.2)
    paper(ax, "Godinu po godinu")
    x = np.arange(len(years))
    ax.bar(
        x - 0.2,
        sv,
        0.4,
        color=INK,
        alpha=0.75,
        label="strategija",
        edgecolor=INK,
        hatch="///",
        lw=0.8,
    )
    ax.bar(
        x + 0.2,
        bv,
        0.4,
        color="#9ca3af",
        alpha=0.7,
        label="kupi i drži",
        edgecolor="#6b7280",
        hatch="..",
        lw=0.8,
    )
    ax.axhline(0, color=PENCIL, lw=1)
    ax.set_xticks(x, [str(y) for y in years])
    top = max(sv.max(), bv.max(), 10)
    ax.set_ylim(min(sv.min(), bv.min(), -10) * 1.3, top * 1.45)
    if 2023 in years:
        ax.axvline(years.index(2023) - 0.5, color=RED, ls="--", lw=1.3)
        ax.text(
            years.index(2023) - 0.45,
            0.03,
            "AI era →",
            transform=ax.get_xaxis_transform(),
            fontsize=10,
            color=RED,
        )
    ibest, iworst = int(np.argmax(sv)), int(np.argmin(sv))

    def fx(i):
        return float(
            ax.transAxes.inverted().transform(ax.transData.transform((i, 0)))[0]
        )

    ax.annotate(
        f"najbolja godina {years[ibest]}: {pct(sv[ibest] / 100)}\n1.000 € → {eur(1000 * (1 + sv[ibest] / 100))}",
        xy=(ibest - 0.2, sv[ibest]),
        xytext=(min(max(fx(ibest) - 0.3, 0.03), 0.6), 0.9),
        textcoords="axes fraction",
        fontsize=11,
        color=GREEN,
        arrowprops=dict(
            arrowstyle="->", color=GREEN, lw=1.5, connectionstyle="arc3,rad=0.2"
        ),
    )
    if sv[iworst] < 0:
        ax.annotate(
            f"najgora godina {years[iworst]}: {pct(sv[iworst] / 100)}\n1.000 € → {eur(1000 * (1 + sv[iworst] / 100))}",
            xy=(iworst - 0.2, sv[iworst]),
            xytext=(min(max(fx(iworst) - 0.3, 0.03), 0.6), 0.52),
            textcoords="axes fraction",
            fontsize=11,
            color=RED,
            arrowprops=dict(
                arrowstyle="->", color=RED, lw=1.5, connectionstyle="arc3,rad=-0.2"
            ),
        )
    ax.legend(loc="upper left", frameon=False, fontsize=10.5)
    ax.set_ylabel("% u godini")
    teacher(
        fig,
        "ne gledaj samo ukupno: ako jedna godina nosi sve, rezultat je krhak. Bolje je kad dobitak dolazi iz više godina.",
    )
    files["yearly"] = save(fig, out, "03_yearly.png")

    # 4) entries and exits
    tickers = list(bt["pos"].columns)
    counts = {t: sum(1 for tr in trades if tr["ticker"] == t) for t in tickers}
    primary = max(tickers, key=lambda t: counts[t])
    close = pan["close"][primary].loc[start:]
    if len(close) > 6000:
        close = close.resample("D").last().dropna()
    mine = [
        t
        for t in trades
        if t["ticker"] == primary and t["entry"] >= pd.Timestamp(start)
    ]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    fig.subplots_adjust(bottom=0.2)
    paper(ax, f"Kada ulazi i izlazi: {primary}")
    sketch(ax.plot(close.index, close, color="#6b7280", lw=1.2)[0], 0.6, 60, 3)
    ax.set_yscale("log")
    times(ax)
    if mine:
        ax.scatter(
            [t["entry"] for t in mine],
            [t["entry_px"] for t in mine],
            marker="^",
            s=34,
            color=GREEN,
            zorder=4,
            label="kupnja",
        )
        ax.scatter(
            [t["exit"] for t in mine if not t.get("open")],
            [t["exit_px"] for t in mine if not t.get("open")],
            marker="v",
            s=34,
            color=[GREEN if t["ret"] > 0 else RED for t in mine if not t.get("open")],
            zorder=4,
            label="prodaja (zelena = dobitak)",
        )
        closed = [t for t in mine if not t.get("open")] or mine
        best, worst_t = (
            max(closed, key=lambda t: t["ret"]),
            min(closed, key=lambda t: t["ret"]),
        )
        for t, col, ttl, off in (
            (best, GREEN, "najbolja", (-0.34, 0.22)),
            (worst_t, RED, "najgora", (-0.42, -0.62)),
        ):
            pos_xy = near(ax, (t["exit"], t["exit_px"]), *off)
            ring(ax, t["exit"], t["exit_px"], col, 520)
            note(
                ax,
                f"{ttl} trgovina: kupio {t['entry_px']:.0f} $ ({day(t['entry'])})\nprodao {t['exit_px']:.0f} $ → {pct(t['ret'])}\n"
                f"od 1.000 € bi bilo {eur(1000 * (1 + t['ret']))}",
                (t["exit"], t["exit_px"]),
                pos_xy,
                color=col,
                rad=0.2,
                size=10.5,
            )
    ax.legend(loc="lower right", frameon=False, fontsize=10)
    ax.yaxis.set_major_formatter(
        __import__("matplotlib.ticker", fromlist=["FuncFormatter"]).FuncFormatter(
            lambda v, _: f"{v:g} $"
        )
    )
    ax.set_ylabel("cijena (logaritamska skala)")
    teacher(
        fig,
        f"strelica gore = kupnja, dolje = prodaja. Ukupno {counts[primary]} trgovina na {primary}. Nisu sve dobre: važno je da dobitci nadmaše gubitke.",
    )
    files["trades"] = save(fig, out, "04_trades.png")

    # 5) does it survive worse conditions
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 5.0))
    fig.subplots_adjust(bottom=0.26, wspace=0.28)
    cs = summary["cost_stress"]
    vals = [(cs[k]["wf_ho_total"] or 0) * 100 for k in ("1x", "2x", "3x")]
    paper(a1, "Što ako su troškovi veći?")
    a1.bar(
        ["troškovi\nkao zadano", "dvostruki", "trostruki"],
        vals,
        color=[GREEN if v > 0 else RED for v in vals],
        alpha=0.7,
        edgecolor=PENCIL,
        hatch="//",
    )
    a1.axhline(0, color=PENCIL, lw=1)
    a1.set_ylabel("% prinosa od 2023.")
    a1.set_ylim(min(0, min(vals)) * 1.3 - 5, max(vals) * 1.35 + 5)
    a1.text(
        0.5,
        0.96,
        f"trostruki trošak: 1.000 € → {eur(1000 * (1 + vals[2] / 100))}",
        transform=a1.transAxes,
        ha="center",
        va="top",
        fontsize=10.5,
        color=GREEN if vals[2] > 0 else RED,
    )
    sens = summary["sensitivity"]
    labels = ["postavke\n−20 %", "zadane\npostavke", "postavke\n+20 %"]
    sv2 = [sens.get("minus20"), sens.get("base"), sens.get("plus20")]
    paper(a2, "Što ako malo promijenim postavke?")
    a2.bar(
        labels,
        [v if v is not None else 0 for v in sv2],
        color=[INK if (v or 0) > 0 else RED for v in sv2],
        alpha=0.7,
        edgecolor=PENCIL,
        hatch="\\\\",
    )
    a2.axhline(0, color=PENCIL, lw=1)
    a2.set_ylabel("Sharpe (kvaliteta uz rizik)")
    a2.text(
        0.5,
        0.96,
        "slični stupci = pouzdano.\nvrlo različiti = sumnjivo 'namješteno'",
        transform=a2.transAxes,
        ha="center",
        va="top",
        fontsize=10.5,
        color=PENCIL,
    )
    for a in (a1, a2):
        a.tick_params(axis="x", labelsize=9.5)
    teacher(
        fig,
        "dobra strategija ne smije puknuti čim su troškovi malo veći ili se postavka malo pomakne. To je test krhkosti.",
    )
    files["robustness"] = save(fig, out, "05_robustness.png")

    # 6) when it is invested
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    fig.subplots_adjust(bottom=0.22)
    paper(ax, "Kada je novac u igri")
    held = pos.loc[:, (pos > 0).any()]
    ax.stackplot(
        held.index,
        [held[c] * 100 for c in held.columns],
        labels=list(held.columns),
        alpha=0.75,
    )
    ax.set_ylim(0, 128)
    ax.legend(
        loc="upper left",
        ncol=min(6, max(1, len(held.columns))),
        frameon=False,
        fontsize=9.5,
    )
    inv = float((pos.sum(axis=1) > 0).mean())
    n, (a, b) = longest_zero_run(cash)
    if n > 40 and a is not None:
        mid = a + (b - a) / 2
        note(
            ax,
            f"bijelo = u gotovini\n(najduže {n} dana)",
            (mid, 5),
            near(ax, (mid, 5), 0.0, 0.4),
            rad=-0.25,
        )
    ax.text(
        0.99,
        0.93,
        f"u poziciji {inv * 100:.0f} % vremena",
        transform=ax.transAxes,
        ha="right",
        fontsize=11,
        color=INK,
    )
    ax.set_ylabel("% kapitala u dionicama")
    teacher(
        fig,
        "obojeno = novac radi, bijelo = čeka u gotovini. Manje vremena u poziciji znači manje izloženosti padovima, ali i propuštene rastove.",
    )
    files["exposure"] = save(fig, out, "06_exposure.png")
    return files
