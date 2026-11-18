"""Three notebook-style charts for the cross-segment overview (heatmap, 1.000 EUR, C13C vs holding).

Reuses the paper/pencil helpers of lab.top10.charts. All numbers come from overview_data (JSON files).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Patch

from lab.aichain import overview_data as D
from lab.top10.charts import GREEN, INK, PAPER, PENCIL, RED, eur, note, paper, ring, sketch, teacher

ORANGE = "#d9822b"
GREY = "#9aa0aa"


def num_hr(x: float, digits: int = 1) -> str:
    """Croatian decimal comma with a dot as thousands separator."""
    s = f"{x:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct_hr(x: float, digits: int = 0, sign: bool = False) -> str:
    s = num_hr(x * 100, digits)
    if sign and x > 0:
        s = "+" + s
    return s + " %"


def _save(fig: Any, out: Path, name: str) -> str:
    fig.savefig(out / name, dpi=140, facecolor=PAPER)
    plt.close(fig)
    return name


def chart_heatmap(out: Path) -> str:
    """Scoreboard: segment x contender, colour = end value relative to holding, text = AI-era return."""
    cols = D.CONTENDERS
    segs = D.SEGMENTS
    wins = D.winners()
    fig, ax = plt.subplots(figsize=(14.5, 8.2))
    fig.subplots_adjust(left=0.17, right=0.70, top=0.79, bottom=0.17)
    paper(ax, "Tablica rezultata: koliko je svaka strategija zaradila u AI eri u odnosu na držanje")
    ax.grid(False)
    cmap = LinearSegmentedColormap.from_list(
        "hold", ["#e07a66", "#f3c2b5", PAPER, "#bfe3c9", "#4fae78"]
    )
    norm = TwoSlopeNorm(vmin=-3.3, vcenter=0.0, vmax=1.2)
    for i, seg in enumerate(segs):
        hold = D.cell(seg, "B0_BUYHOLD")
        for j, k in enumerate(cols):
            c = D.cell(seg, k)
            if k == "B0_BUYHOLD":
                face = "#eceff3"
                txt = f"{pct_hr(c['total_return'])}\n{eur(D.per_1000(c))}"
            else:
                ratio = D.ratio_to_hold(seg, k) or 1.0
                face = cmap(norm(math.log2(max(ratio, 0.08))))
                txt = f"{pct_hr(c['total_return'])}\n{num_hr(ratio, 2)}× drž."
            ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=face, edgecolor="#b9c6d6", lw=1.0))
            if k != "B0_BUYHOLD" and not D.is_eligible(c):
                ax.add_patch(
                    plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch="///", edgecolor="#9aa0aa", lw=0)
                )
            ax.text(j, i, txt, ha="center", va="center", fontsize=10.2, color=PENCIL, linespacing=1.25)
        w = wins[seg]
        wj = cols.index(w.contender)
        ring(ax, wj, i, color=INK, size=3600)
    ax.set_xlim(-0.5, len(cols) - 0.5)
    ax.set_ylim(len(segs) - 0.5, -0.5)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([D.CONTENDER_SHORT[k].replace(" ", "\n") for k in cols], fontsize=9.5)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(segs)))
    ax.set_yticklabels([D.SEGMENT_SHORT[s] for s in segs], fontsize=12)
    ax.tick_params(length=0)
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(False)

    nw = D.winner("network_servers")
    nj = cols.index(nw.contender)
    note(
        ax,
        f"Jedini jasan pobjednik nad držanjem:\nrotacija zamaha (K6) u mrežama,\n{num_hr(nw.stats['total_return'] + 1, 1)}× ulog naspram {num_hr(nw.hold['total_return'] + 1, 1)}×.\nAli pad je veći ({pct_hr(nw.stats['max_drawdown'])} naspram {pct_hr(nw.hold['max_drawdown'])}).",
        xy=(nj + 0.5, D.SEGMENTS.index("network_servers") - 0.38),
        xytext=(1.03, 0.30),
        color=GREEN,
        rad=-0.2,
        size=10.5,
    )
    mw = D.winner("memory")
    k6m = D.cell("memory", "K6_MOMENTUM_CS")
    note(
        ax,
        f"Memorija: C13C pobjeđuje po pravilu (Sharpe {num_hr(mw.stats['sharpe'], 2)}),\nali zaradi {pct_hr(mw.stats['total_return'])} naspram {pct_hr(mw.hold['total_return'])} držanja.\nK6 ima samo {k6m['trades']} poslova (manje od 20), pa ne računa.",
        xy=(cols.index("K6_MOMENTUM_CS") + 0.5, -0.38),
        xytext=(1.03, 0.88),
        color=INK,
        rad=0.15,
        size=10.5,
    )
    cw = D.winner("cloud")
    note(
        ax,
        f"Oblak: K5B ima isti Sharpe kao držanje\n({num_hr(cw.stats['sharpe'], 2)} naspram {num_hr(cw.hold['sharpe'], 2)}), ali pad samo\n{pct_hr(cw.stats['max_drawdown'])} umjesto {pct_hr(cw.hold['max_drawdown'])}. Cijena: manji prinos.",
        xy=(cols.index("K5B_SR_BREAKOUT_RETEST") + 0.5, D.SEGMENTS.index("cloud") + 0.4),
        xytext=(1.03, 0.10),
        color=ORANGE,
        rad=-0.25,
        size=10.5,
    )
    ax.legend(
        handles=[
            Patch(facecolor="#4fae78", label="bolje od držanja"),
            Patch(facecolor="#e07a66", label="lošije od držanja"),
            Patch(facecolor="white", edgecolor="#9aa0aa", hatch="///", label="manje od 20 poslova ili gubitak uz trošak 2×"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="none", markeredgecolor=INK, markersize=16, label="pobjednik po unaprijed zadanom pravilu"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.04),
        ncol=2,
        frameon=False,
        fontsize=10.5,
    )
    teacher(
        fig,
        "Prvi broj u polju je ukupni prinos 2023.-2026. (1.000 € uloga postaje tisuću € plus prinos). "
        "Drugi je koliko puta je završna vrijednost veća ili manja od držanja.",
    )
    return _save(fig, out, "ov_01_ploca.png")


def _bars_for_segment(seg: str) -> list[tuple[str, str, float, float]]:
    """(label, colour, end value per 1.000 EUR, worst loss per 1.000 EUR) for hold, winner and C13C."""
    w = D.winner(seg)
    hold = w.hold
    items = [("drž.", GREY, D.per_1000(hold), D.worst_loss_per_1000(hold))]
    items.append((D.CONTENDER_SHORT[w.contender].split(" ")[0], INK, D.per_1000(w.stats), D.worst_loss_per_1000(w.stats)))
    if w.contender != "K1_C13C_ORIG":
        k1 = D.cell(seg, "K1_C13C_ORIG")
        items.append(("K1", ORANGE, D.per_1000(k1), D.worst_loss_per_1000(k1)))
    return items


def chart_1000(out: Path) -> str:
    """1.000 EUR per segment: end value (left) and worst loss from the peak (right), hold vs winner vs C13C."""
    segs = D.SEGMENTS
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 8.0))
    fig.subplots_adjust(left=0.06, right=0.985, top=0.83, bottom=0.2, wspace=0.14)
    paper(a1, "Kamo stigne 1.000 € (2023.-2026.)")
    paper(a2, "Koliko boli najgori pad s vrha")
    width = 0.26
    for ax, idx in ((a1, 2), (a2, 3)):
        for i, seg in enumerate(segs):
            bars = _bars_for_segment(seg)
            n = len(bars)
            for b, (lab, col, v_end, v_dd) in enumerate(bars):
                v = v_end if idx == 2 else v_dd
                x = i + (b - (n - 1) / 2) * width
                r = ax.bar(x, v, width * 0.92, color=col, alpha=0.88, zorder=3)
                sketch(r[0], 0.6, 50, 2)
                ax.text(x, v, f"{eur(v)}", ha="center", va="bottom", fontsize=8.6, rotation=90, color=PENCIL)
                ax.text(x, -0.012 * (20500 if idx == 2 else 1000), lab, ha="center", va="top", fontsize=8.6, color=col, rotation=0)
        ax.set_xticks(range(len(segs)))
        ax.set_xticklabels([D.SEGMENT_SHORT[s].replace(" ", "\n", 1) for s in segs], fontsize=10.5)
        ax.tick_params(axis="x", pad=18, length=0)
    a1.set_ylim(0, 22500)
    a2.set_ylim(0, 1000)
    a1.set_ylabel("završna vrijednost od 1.000 € uloga (€)")
    a2.set_ylabel("gubitak od vrha ako si ušao na vrhu (€)")
    mem = D.winner("memory")
    note(
        a1,
        f"Osiguranje ima cijenu:\nC13C završi s {eur(D.per_1000(mem.stats))},\ndržanje s {eur(D.per_1000(mem.hold))}.",
        xy=(0.0, D.per_1000(mem.stats) + 2400),
        xytext=(0.22, 0.58),
        color=ORANGE,
        rad=0.3,
        size=10.5,
    )
    net = D.winner("network_servers")
    note(
        a2,
        f"Mreže, K6: gubitak {eur(D.worst_loss_per_1000(net.stats))}\nnaspram {eur(D.worst_loss_per_1000(net.hold))} s držanjem.\nPobjednik je rizičniji.",
        xy=(4.0, D.worst_loss_per_1000(net.stats) + 10),
        xytext=(0.28, 0.93),
        color=RED,
        rad=-0.25,
        size=10.5,
    )
    cl = D.winner("cloud")
    note(
        a2,
        f"Oblak, K5B: samo {eur(D.worst_loss_per_1000(cl.stats))}\numjesto {eur(D.worst_loss_per_1000(cl.hold))}.",
        xy=(5.0, D.worst_loss_per_1000(cl.stats) + 20),
        xytext=(0.76, 0.50),
        color=GREEN,
        rad=0.25,
        size=10.5,
    )
    a1.legend(
        handles=[
            Patch(facecolor=GREY, label="držanje"),
            Patch(facecolor=INK, label="pobjednik po pravilu"),
            Patch(facecolor=ORANGE, label="tvoj C13C (K1), ako nije pobjednik"),
        ],
        loc="upper right",
        frameon=False,
        fontsize=10,
    )
    teacher(
        fig,
        "Memorija: pobjednik je sam C13C, pa je tamo samo jedna obojena šipka uz držanje. Iznosi su za 1.000 € po dionici, bez poreza i tečaja.",
    )
    return _save(fig, out, "ov_02_tisucu_eura.png")


def chart_c13c(out: Path) -> str:
    """C13C minus holding for each of the 43 tickers: return difference (left) and drawdown difference (right)."""
    rows = D.ticker_rows()
    ordered: list[D.TickerRow] = []
    bounds: list[tuple[str, int, int]] = []
    for seg in D.SEGMENTS:
        part = sorted([r for r in rows if r.segment == seg], key=lambda r: r.c13c_ret - r.hold_ret, reverse=True)
        bounds.append((seg, len(ordered), len(ordered) + len(part)))
        ordered.extend(part)
    n = len(ordered)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 15), sharey=True)
    fig.subplots_adjust(left=0.2, right=0.985, top=0.9, bottom=0.07, wspace=0.06)
    paper(a1, "Prinos: C13C minus držanje (postotni bodovi)")
    paper(a2, "Najgori pad: C13C minus držanje (pozitivno = manji pad)")
    palette = [INK, "#6a4fb8", "#127a78", ORANGE, "#b0338a", "#4d7c0f"]
    y = np.arange(n)
    ret_diff = np.array([(r.c13c_ret - r.hold_ret) * 100 for r in ordered])
    dd_diff = np.array([(r.c13c_dd - r.hold_dd) * 100 for r in ordered])
    colours = []
    for si, (seg, a, b) in enumerate(bounds):
        colours.extend([palette[si]] * (b - a))
    r1 = a1.barh(y, ret_diff, color=colours, alpha=0.85, zorder=3)
    r2 = a2.barh(y, dd_diff, color=colours, alpha=0.85, zorder=3)
    for r in list(r1) + list(r2):
        sketch(r, 0.5, 40, 2)
    a1.set_xscale("symlog", linthresh=100)
    a1.set_xticks([-10000, -1000, -100, 0, 100])
    a1.set_xticklabels(["-10.000", "-1.000", "-100", "0", "+100"])
    a1.axvline(0, color=PENCIL, lw=1.2, zorder=4)
    a2.axvline(0, color=PENCIL, lw=1.2, zorder=4)
    a1.set_yticks(y)
    a1.set_yticklabels([f"{r.ticker} ({r.trades})" for r in ordered], fontsize=9.5)
    a1.invert_yaxis()
    for si, (seg, a, b) in enumerate(bounds):
        for ax in (a1, a2):
            if a:
                ax.axhline(a - 0.5, color=PENCIL, lw=1.0, ls=(0, (4, 3)), zorder=2)
        a2.text(
            1.01,
            (a + b - 1) / 2,
            D.SEGMENT_SHORT[seg],
            transform=a2.get_yaxis_transform(),
            ha="left",
            va="center",
            fontsize=10,
            color=palette[si],
            rotation=270,
        )
    a1.set_xlabel("simlog skala; broj u zagradi uz oznaku je broj poslova C13C-a")
    a2.set_xlabel("postotni bodovi")
    best = max(ordered, key=lambda r: r.c13c_ret - r.hold_ret)
    worst = min(ordered, key=lambda r: r.c13c_ret - r.hold_ret)
    ib = ordered.index(best)
    iw = ordered.index(worst)
    a1.set_ylim(n + 0.5, -6.5)
    fy = lambda i: float(a1.transAxes.inverted().transform(a1.transData.transform((0, i)))[1])
    note(
        a1,
        f"{best.ticker}: jedini plus,\n+{num_hr((best.c13c_ret - best.hold_ret) * 100, 1)} postotnih bodova",
        xy=(ret_diff[ib], ib - 0.3),
        xytext=(0.40, fy(-4.2)),
        color=GREEN,
        rad=-0.2,
        size=10.5,
    )
    note(
        a1,
        f"{worst.ticker}: najveći zaostatak,\n{num_hr((worst.c13c_ret - worst.hold_ret) * 100, 0)} postotnih bodova",
        xy=(1.0, iw),
        xytext=(0.745, fy(iw - 3.5)),
        color=RED,
        rad=0.2,
        size=10.0,
    )
    smaller = int(np.sum(dd_diff > 0))
    beats = int(np.sum(ret_diff > 0))
    a2.text(
        0.03,
        0.975,
        f"Pad je manji kod {smaller} od {n} dionica,\nprinos je veći kod {beats} od {n}.\nC13C je zaštita, ne pojačivač.",
        transform=a2.transAxes,
        ha="left",
        va="top",
        fontsize=11.5,
        color=INK,
    )
    teacher(
        fig,
        "Svaka šipka je jedna dionica s 1.000 € uloga. Ulijevo na lijevoj ploči znači da je C13C zaradio manje od držanja.",
    )
    return _save(fig, out, "ov_03_c13c_sve_dionice.png")


def make_all(out: Path) -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    return {
        "heatmap": chart_heatmap(out),
        "money": chart_1000(out),
        "c13c": chart_c13c(out),
    }
