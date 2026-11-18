"""Notebook-style charts for the teaching page, drawn from real bars and the saved swing/placebo results.

Research only: nothing here places orders. The examples come from ``learn_examples`` (a disclosed pick rule);
the evidence charts only read ``swing/summary.json``, ``swing/placebo.json`` and ``swing/results/*.json``.
Style helpers are imported from ``lab.top10.charts`` and ``lab.aichain.notebook_charts`` (not modified).
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
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

from lab.aichain import learn_examples as le
from lab.aichain import mechanics as mx
from lab.aichain.levels_charts import _candles
from lab.aichain.notebook_charts import dmy, free_note, hr, save, say, sheet
from lab.top10 import charts as nb

OUT = le.SWING / "learn"
ORANGE = "#d9822b"
PURPLE = "#7b4fa3"
GREY = "#8b8f99"
FIG = (11.0, 6.0)


# ----------------------------------------------------------------------------- shared drawing helpers


def X(c: le.Ctx, i: int) -> float:
    """Matplotlib date number of bar ``i``."""
    return float(mdates.date2num(c.P.bars.dates[i].to_pydatetime()))


def pct(x: float, nd: int = 1, sign: bool = True) -> str:
    s = f"{x * 100:+.{nd}f}" if sign else f"{x * 100:.{nd}f}"
    return s.replace(".", ",") + " %"


def usd(x: float) -> str:
    return hr(x, 2) + " USD"


def frame(
    c: le.Ctx, s: int, e: int, title: str, size: tuple[float, float] = FIG
) -> tuple[Any, Any]:
    """Figure with graph-paper axes and real candles for bars ``s..e-1``."""
    fig, ax = plt.subplots(figsize=size)
    sheet(ax, title)
    _candles(ax, c.P, s, e)
    b = c.P.bars
    lo, hi = float(b.low[s:e].min()), float(b.high[s:e].max())
    pad = (hi - lo) * 0.12
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(X(c, s) - 1.5, X(c, e - 1) + 3.5)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=7))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: dmy(mdates.num2date(v))))
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: hr(v, 0 if v >= 100 else 1))
    )
    ax.set_ylabel("cijena dionice (USD)")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.92, bottom=0.13)
    ax._placer = Placer(ax, c, s, e)
    return fig, ax


def hline(
    ax: Any,
    c: le.Ctx,
    i0: int,
    i1: int,
    y: float,
    color: str,
    ls: str = "-",
    lw: float = 1.8,
) -> None:
    ax.plot([X(c, i0), X(c, i1)], [y, y], color=color, ls=ls, lw=lw, zorder=5)
    if hasattr(ax, "_placer"):
        ax._placer.block(X(c, i0), X(c, i1), y, y)


def dot(
    ax: Any,
    c: le.Ctx,
    i: int,
    y: float,
    color: str,
    marker: str = "o",
    size: float = 70,
) -> None:
    ax.scatter(
        [X(c, i)],
        [y],
        s=size,
        color=color,
        marker=marker,
        zorder=8,
        edgecolor=nb.PAPER,
        lw=0.8,
    )
    if hasattr(ax, "_placer"):
        lo, hi = ax.get_ylim()
        ax._placer.block(
            X(c, i) - 1.5, X(c, i) + 1.5, y, y, pad=0.02 * (hi - lo) / (hi - lo)
        )


class Placer:
    """Greedy placement of handwritten notes: close to their point, clear of candles and of earlier notes."""

    def __init__(self, ax: Any, c: le.Ctx, s: int, e: int) -> None:
        self.ax = ax
        self.rects: list[tuple[float, float, float, float]] = []
        b = c.P.bars
        fig = ax.figure
        fig.canvas.draw()
        inv = ax.transAxes.inverted()
        xs = np.array([X(c, i) for i in range(s, e)])
        lo = inv.transform(ax.transData.transform(np.c_[xs, b.low[s:e]]))
        hi = inv.transform(ax.transData.transform(np.c_[xs, b.high[s:e]]))
        half = 0.004
        for k in range(len(xs)):
            self.rects.append(
                (lo[k, 0] - half, lo[k, 1] - 0.012, hi[k, 0] + half, hi[k, 1] + 0.012)
            )

    def block(
        self, x0: float, x1: float, y0: float, y1: float, pad: float = 0.012
    ) -> None:
        """Keep notes off a drawn line or box (data coordinates)."""
        inv = self.ax.transAxes.inverted()
        (a0, b0), (a1, b1) = inv.transform(
            self.ax.transData.transform([(x0, y0), (x1, y1)])
        )
        self.rects.append(
            (
                min(a0, a1) - 0.004,
                min(b0, b1) - pad,
                max(a0, a1) + 0.004,
                max(b0, b1) + pad,
            )
        )

    def free(self, r: tuple[float, float, float, float]) -> bool:
        x0, y0, x1, y1 = r
        if x0 < 0.01 or x1 > 0.99 or y0 < 0.02 or y1 > 0.97:
            return False
        return not any(
            x0 < q[2] and x1 > q[0] and y0 < q[3] and y1 > q[1] for q in self.rects
        )

    def place(
        self,
        point: tuple[float, float],
        w: float,
        h: float,
        hint: tuple[float, float] | None,
    ) -> tuple[float, float]:
        best, best_cost = None, 1e9
        for xl in np.arange(0.015, 0.99 - w, 0.02):
            for yc in np.arange(0.06, 0.95, 0.02):
                r = (xl, yc - h / 2, xl + w, yc + h / 2)
                if not self.free(r):
                    continue
                cx, cy = xl + w / 2, yc
                cost = np.hypot(cx - point[0], (cy - point[1]) * 1.6)
                if hint is not None:
                    cost += 0.25 * np.hypot(xl - hint[0], yc - hint[1])
                if cost < best_cost:
                    best, best_cost = (xl, yc), cost
        if best is None:
            best = hint or (0.05, 0.5)
        self.rects.append((best[0], best[1] - h / 2, best[0] + w, best[1] + h / 2))
        return best


def note(
    ax: Any,
    c: le.Ctx,
    i: int,
    y: float,
    text: str,
    at: tuple[float, float] | None = None,
    color: str = nb.RED,
    width: int = 30,
    rad: float = 0.2,
    size: float = 10.5,
) -> None:
    """Handwritten note pointing at bar ``i`` / price ``y``; ``at`` is only a soft hint for the position."""
    pl: Placer = ax._placer  # set by frame()
    inv = ax.transAxes.inverted()
    px, py = inv.transform(ax.transData.transform((X(c, i), y)))
    lines = sum(len(textwrap.wrap(p, width)) or 1 for p in text.split("\n"))
    w = min(0.62, width * 0.0092 + 0.02)
    h = lines * 0.036 + 0.03
    pos = pl.place((px, py), w, h, at)
    say(ax, text, (X(c, i), y), pos, color=color, rad=rad, size=size, width=width)


def legend(fig: Any, text: str) -> None:
    """One-line explanation of colours and lines, written under the chart (outside the plot)."""
    fig.text(0.075, 0.012, text, fontsize=10, color=nb.RED, ha="left", va="bottom")


def vband(
    ax: Any, c: le.Ctx, i0: int, i1: int, color: str, alpha: float = 0.12
) -> None:
    ax.axvspan(X(c, i0) - 0.5, X(c, i1) + 0.5, color=color, alpha=alpha, zorder=1, lw=0)


def zone_box(
    ax: Any,
    c: le.Ctx,
    i0: int,
    i1: int,
    lo: float,
    hi: float,
    color: str,
    alpha: float = 0.22,
) -> None:
    if hasattr(ax, "_placer"):
        ax._placer.block(X(c, i0), X(c, i1), lo, hi, 0.0)
    ax.add_patch(
        Rectangle(
            (X(c, i0) - 0.5, lo),
            X(c, i1) - X(c, i0) + 1,
            hi - lo,
            facecolor=color,
            alpha=alpha,
            edgecolor=color,
            lw=1.2,
            zorder=2,
        )
    )


def outcome_marks(ax: Any, c: le.Ctx, t: int) -> tuple[float, float]:
    """Entry (open of t+1) and 10-day mark (close of t+10); returns (entry, exit) prices."""
    b = c.P.bars
    entry, ex = float(b.open[t + 1]), float(b.close[t + le.H])
    dot(ax, c, t + 1, entry, nb.GREEN, "o", 90)
    dot(ax, c, t + le.H, ex, nb.INK if ex >= entry else nb.RED, "s", 80)
    ax.axvline(X(c, t), color=nb.RED, ls="--", lw=1.1, zorder=2)
    ax.axvline(X(c, t + le.H), color=GREY, ls=":", lw=1.1, zorder=2)
    return entry, ex


def result_text(c: le.Ctx, t: int) -> str:
    r = le.euro_result(c, t)
    word = "dobio bi" if r["pnl"] >= 0 else "izgubio bi"
    return (
        f"Nakon 10 dana: {usd(r['exit'])} naspram {usd(r['entry'])} kod kupnje. "
        f"Od 1.000 € {word} oko {hr(abs(r['pnl']), 0)} € (uz troškove)."
    )


def kind_word(kind: str) -> str:
    return "dobar primjer" if kind == "clean" else "neuspjeli primjer"


# ----------------------------------------------------------------------------- momentum


def chart_momentum(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    s, e = t - 45, t + 32
    tr = ex.extra["trade"]
    fig, ax = frame(
        c, s, e, f"Zamah: proboj 20-dnevnog vrha, {ex.ticker}, {kind_word(ex.kind)}"
    )
    hh = pd.Series(b.close).rolling(20).max().to_numpy()
    xs = [X(c, i) for i in range(s, t + 1)]
    ax.step(xs, hh[s : t + 1], where="post", color=nb.INK, lw=1.8, zorder=5)
    for k in range(s, t + 1):
        ax._placer.block(X(c, k), X(c, k) + 1, float(hh[k]), float(hh[k]))
    entry, _ = outcome_marks(ax, c, t)
    ex_i = int(
        np.searchsorted(b.dates.values, np.datetime64(pd.Timestamp(tr["exit_date"])))
    )
    stop = float(tr["raw_entry"]) * 0.92
    hline(ax, c, t + 1, min(ex_i, e - 1), stop, nb.RED, "--", 1.4)
    if ex_i < e:
        dot(ax, c, ex_i, float(tr["raw_exit"]), ORANGE, "X", 110)
    top = b.high[s:e].max()
    note(
        ax,
        c,
        t,
        float(b.close[t]),
        f"Signal: zatvaranje {dmy(b.dates[t])} ({usd(b.close[t])}) je najviše u zadnjih 20 dana.",
        (0.03, 0.88),
        width=34,
    )
    note(
        ax,
        c,
        t + 1,
        entry,
        f"Kupnja sutradan na otvaranju: {usd(entry)}.",
        (0.40, 0.14),
        color=nb.GREEN,
        width=26,
        rad=-0.2,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.50, 0.90 if ex.r10 < 0 else 0.20),
        color=nb.INK,
        width=36,
    )
    legend(
        fig,
        "plava crta: najviše zatvaranje zadnjih 20 dana  |  crvena isprekidana: stop 8 % ispod kupnje  |  crvena okomita: dan odluke",
    )
    if ex_i < e:
        note(
            ax,
            c,
            ex_i,
            float(tr["raw_exit"]),
            f"Pravilo je izašlo {dmy(tr['exit_date'])}: {pct(tr['return'])} ({'stop' if tr['reason'] == 'stop' else 'signal izlaza'}).",
            (0.62, 0.50),
            color=ORANGE,
            width=30,
            rad=0.25,
        )
    del top
    return save(fig, out, f"momentum_{ex.kind}.png")


# ----------------------------------------------------------------------------- support / resistance


def chart_sr(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    lvl = float(ex.extra["level"])
    brk = int(ex.extra["break_i"])
    tr = ex.extra["trade"]
    s, e = max(0, brk - 55), t + 30
    fig, ax = frame(
        c,
        s,
        e,
        f"Potpora i otpor: proboj pa povratni test, {ex.ticker}, {kind_word(ex.kind)}",
    )
    zone_box(ax, c, s, e - 1, lvl * 0.985, lvl * 1.015, nb.INK, 0.14)
    hline(ax, c, s, e - 1, lvl, nb.INK, "-", 2.0)
    for p in ex.extra["members"]:
        if p.idx >= s:
            dot(ax, c, p.idx, p.price, ORANGE, "v", 110)
    hline(ax, c, t + 1, min(t + 30, e - 1), lvl * 0.97, nb.RED, "--", 1.4)
    outcome_marks(ax, c, t)
    dot(ax, c, brk, float(b.close[brk]), nb.GREEN, "^", 110)
    nm = len([p for p in ex.extra["members"] if p.idx >= s])
    note(
        ax,
        c,
        brk,
        float(b.close[brk]),
        f"{dmy(b.dates[brk])}: prvo zatvaranje iznad razine {usd(lvl)} (proboj). Do tada je to bio OTPOR.",
        (0.03, 0.88),
        width=34,
    )
    if nm:
        p0 = next(p for p in ex.extra["members"] if p.idx >= s)
        note(
            ax,
            c,
            p0.idx,
            p0.price,
            f"Narančasti trokuti: okreti (vrhovi) koji čine razinu. Dodira: {len(ex.extra['members'])}.",
            (0.03, 0.62),
            color=ORANGE,
            width=30,
            rad=-0.25,
        )
    note(
        ax,
        c,
        t,
        float(b.close[t]),
        f"{dmy(b.dates[t])}: povratak do zone (±1,5 %) i zatvaranje iznad nje = signal. Sada je razina POTPORA.",
        (0.42, 0.14),
        width=34,
        rad=-0.15,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.50, 0.90),
        color=nb.INK,
        width=36,
    )
    legend(
        fig,
        "plava traka: zona, ne crta (razina ±1,5 %)  |  crvena isprekidana: stop 3 % ispod razine  |  narančasti trokuti: okreti",
    )
    note(
        ax,
        c,
        min(
            int(
                np.searchsorted(
                    b.dates.values, np.datetime64(pd.Timestamp(tr["exit_date"]))
                )
            ),
            e - 1,
        ),
        float(tr["raw_exit"]),
        f"Pravilo je izašlo {dmy(tr['exit_date'])}: {pct(tr['return'])}.",
        (0.70, 0.32),
        color=ORANGE,
        width=26,
    )
    return save(fig, out, f"sr_{ex.kind}.png")


# ----------------------------------------------------------------------------- market structure


def _labelled_pivots(c: le.Ctx, s: int, e: int) -> list[tuple[mx.Pivot, str]]:
    """Pivots whose confirmation falls in the window, labelled HH/LH/HL/LL against the previous same-kind pivot."""
    out: list[tuple[mx.Pivot, str]] = []
    last: dict[str, mx.Pivot | None] = {"H": None, "L": None}
    for p in sorted(c.P.pivots, key=lambda q: q.idx):
        prev = last[p.kind]
        if prev is not None and p.idx >= s and p.idx < e:
            if p.kind == "H":
                out.append((p, "HH" if p.price > prev.price else "LH"))
            else:
                out.append((p, "HL" if p.price > prev.price else "LL"))
        last[p.kind] = p
    return out


def chart_structure_anatomy(out: Path) -> tuple[str, dict[str, Any]]:
    w = le.structure_window("MU")
    c = le.ctx(w["ticker"])
    b = c.P.bars
    s, e = w["s"], w["e"]
    fig, ax = frame(
        c,
        s,
        e,
        f"Struktura tržišta: vrhovi, dna, proboj i promjena ({w['ticker']}, stvarni podaci)",
        (11.5, 6.6),
    )
    lab = _labelled_pivots(c, s, e)
    for p, name in lab:
        up = p.kind == "H"
        col = nb.GREEN if name in ("HH", "HL") else nb.RED
        dot(ax, c, p.idx, p.price, col, "v" if up else "^", 60)
        ax.annotate(
            name,
            (X(c, p.idx), p.price),
            xytext=(0, 9 if up else -15),
            textcoords="offset points",
            ha="center",
            fontsize=9.5,
            color=col,
            zorder=9,
        )
    evs = [ev for ev in c.P.struct.events if s <= ev["idx"] < e]
    for ev in evs:
        li, ei = ev["level_idx"], ev["idx"]
        col = ORANGE if ev["kind"] == "shift" else nb.INK
        ax.plot(
            [X(c, max(li, s)), X(c, ei)],
            [ev["level"]] * 2,
            color=col,
            ls="--",
            lw=1.4,
            zorder=6,
        )
        label = ("BOS" if ev["kind"] == "bos" else "PROMJENA") + (
            " gore" if ev["dir"] == 1 else " dolje"
        )
        ax.annotate(
            label,
            (X(c, ei), ev["level"]),
            xytext=(2, 6 if ev["dir"] == 1 else -13),
            textcoords="offset points",
            fontsize=8.5,
            color=col,
            zorder=9,
        )
    # one pivot demonstrates the 5-bar delay
    demo = next((p for p, _ in lab if p.kind == "H" and p.idx > s + 40), None)
    facts: dict[str, Any] = {
        "window": [str(b.dates[s].date()), str(b.dates[e - 1].date())],
        "events": [],
    }
    if demo is not None:
        ax.axvspan(
            X(c, demo.idx), X(c, demo.confirm), color=nb.RED, alpha=0.18, lw=0, zorder=1
        )
        note(
            ax,
            c,
            demo.idx,
            demo.price,
            f"Vrh od {dmy(b.dates[demo.idx])} ({usd(demo.price)}) postaje poznat tek 5 dana kasnije ({dmy(b.dates[demo.confirm])}): crveno polje.",
            (0.03, 0.12),
            width=38,
            rad=-0.2,
        )
        facts["demo_pivot"] = {
            "date": str(b.dates[demo.idx].date()),
            "price": demo.price,
            "known": str(b.dates[demo.confirm].date()),
        }
    for ev in evs:
        facts["events"].append(
            {
                "kind": ev["kind"],
                "dir": ev["dir"],
                "date": str(b.dates[ev["idx"]].date()),
                "level": ev["level"],
            }
        )
    legend(
        fig,
        "zeleno: viši vrhovi (HH) i viša dna (HL)  |  crveno: niži vrhovi (LH) ili niža dna (LL)  |  plavo isprekidano: BOS  |  narančasto: PROMJENA smjera",
    )
    return save(fig, out, "struktura_anatomija.png"), facts


def chart_bos(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    ev = ex.extra["event"]
    s, e = t - 55, t + 32
    fig, ax = frame(
        c,
        s,
        e,
        f"Proboj strukture (BOS) u uzlaznom trendu, {ex.ticker}, {kind_word(ex.kind)}",
    )
    lvl = float(ev["level"])
    ax.plot(
        [X(c, max(ev["level_idx"], s)), X(c, t)],
        [lvl, lvl],
        color=nb.INK,
        ls="--",
        lw=1.8,
        zorder=6,
    )
    dot(ax, c, ev["level_idx"], lvl, nb.GREEN, "v", 90)
    outcome_marks(ax, c, t)
    note(
        ax,
        c,
        ev["level_idx"],
        lvl,
        f"Zadnji potvrđeni vrh: {usd(lvl)} ({dmy(b.dates[ev['level_idx']])}).",
        (0.03, 0.86),
        width=30,
        color=nb.GREEN,
        rad=-0.2,
    )
    note(
        ax,
        c,
        t,
        float(b.close[t]),
        f"{dmy(b.dates[t])}: zatvaranje {usd(b.close[t])} iznad tog vrha = BOS (struktura se nastavlja).",
        (0.30, 0.14),
        width=34,
        rad=-0.15,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.52, 0.90 if ex.r10 < 0 else 0.22),
        color=nb.INK,
        width=36,
    )
    return save(fig, out, f"bos_{ex.kind}.png")


# ----------------------------------------------------------------------------- liquidity sweep


def chart_sweep(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    sw, sh = ex.extra["sweep"], ex.extra["shift"]
    s, e = min(sw["pivot_idx"], sw["idx"]) - 25, t + 32
    s = max(s, 0)
    fig, ax = frame(
        c,
        s,
        e,
        f"Lov na stopove (sweep) + promjena smjera, {ex.ticker}, {kind_word(ex.kind)}",
    )
    hline(ax, c, max(sw["pivot_idx"], s), sw["idx"], sw["level"], nb.INK, "-", 1.8)
    dot(ax, c, sw["pivot_idx"], sw["level"], nb.GREEN, "^", 90)
    dot(ax, c, sw["idx"], float(b.low[sw["idx"]]), ORANGE, "v", 110)
    hline(ax, c, max(sh["level_idx"], s), t, sh["level"], ORANGE, "--", 1.6)
    outcome_marks(ax, c, t)
    mid = 0.5 * (ex.extra["range_lo"] + ex.extra["range_hi"])
    ax.axhline(mid, color=GREY, ls=":", lw=1.2, zorder=2)
    note(
        ax,
        c,
        sw["pivot_idx"],
        sw["level"],
        f"Dno {usd(sw['level'])} ({dmy(b.dates[sw['pivot_idx']])}): svi ga vide, ispod su tuđi stop-nalozi.",
        (0.02, 0.18),
        width=30,
        color=nb.GREEN,
        rad=-0.2,
    )
    note(
        ax,
        c,
        sw["idx"],
        float(b.low[sw["idx"]]),
        f"{dmy(b.dates[sw['idx']])}: fitilj {usd(b.low[sw['idx']])} ispod dna, ali zatvaranje {usd(b.close[sw['idx']])} natrag iznad = SWEEP.",
        (0.26, 0.05),
        width=32,
        color=ORANGE,
        rad=0.2,
    )
    note(
        ax,
        c,
        t,
        float(b.close[t]),
        f"{dmy(b.dates[t])}: zatvaranje iznad zadnjeg nižeg vrha {usd(sh['level'])} = PROMJENA smjera, signal.",
        (0.30, 0.88),
        width=34,
        rad=-0.15,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.58, 0.60 if ex.r10 < 0 else 0.30),
        color=nb.INK,
        width=34,
    )
    legend(
        fig,
        "siva točkasta: sredina raspona (ispod = diskont)  |  narančasta isprekidana: zadnji niži vrh  |  crvena okomita: dan odluke",
    )
    return save(fig, out, f"sweep_{ex.kind}.png")


def chart_equal_lows(info: dict[str, Any], out: Path) -> str:
    c = le.ctx(info["ticker"])
    b = c.P.bars
    mem = info["members"]
    s = max(0, min(p.idx for p in mem) - 25)
    j = info["sweep_i"]
    e = min(c.n, j + 25)
    fig, ax = frame(
        c,
        s,
        e,
        f"Jednaka dna (isti stopovi na istom mjestu), {info['ticker']}, stvarni podaci",
    )
    lvl = info["level"]
    hline(ax, c, s, e - 1, lvl, nb.INK, "-", 1.6)
    ax.axhspan(
        lvl * (1 - mx.EQUAL_TOL),
        lvl * (1 + mx.EQUAL_TOL),
        color=nb.INK,
        alpha=0.12,
        zorder=1,
    )
    for p in mem:
        dot(ax, c, p.idx, p.price, nb.GREEN, "^", 100)
    dot(ax, c, j, float(b.low[j]), ORANGE, "v", 110)
    srt = sorted(mem, key=lambda p: p.idx)
    note(
        ax,
        c,
        srt[0].idx,
        srt[0].price,
        f"Dva dna unutar 0,3 %: {usd(srt[0].price)} i {usd(srt[-1].price)}. Ispod njih ima mnogo stop-naloga.",
        (0.03, 0.80),
        width=34,
        color=nb.GREEN,
        rad=-0.2,
    )
    note(
        ax,
        c,
        j,
        float(b.low[j]),
        f"{dmy(b.dates[j])}: cijena probije razinu ({usd(b.low[j])}), ali zatvara natrag iznad ({usd(b.close[j])}).",
        (0.45, 0.14),
        width=34,
        color=ORANGE,
        rad=0.2,
    )
    return save(fig, out, "jednaka_dna.png")


# ----------------------------------------------------------------------------- demand zone / order block


def chart_zone(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    z = ex.extra["zone"]
    s, e = max(0, z["base"] - 12), t + 32
    fig, ax = frame(
        c, s, e, f"Zona potražnje (order block), {ex.ticker}, {kind_word(ex.kind)}"
    )
    zone_box(ax, c, z["base"], e - 1, z["lo"], z["hi"], nb.GREEN, 0.20)
    dot(ax, c, z["base"], float(b.low[z["base"]]), nb.GREEN, "^", 100)
    dot(ax, c, z["known"], float(b.close[z["known"]]), nb.INK, "^", 90)
    outcome_marks(ax, c, t)
    note(
        ax,
        c,
        z["base"],
        float(b.high[z["base"]]),
        f"{dmy(b.dates[z['base']])}: zadnja silazna svijeća prije jakog rasta. Njezin raspon {usd(z['lo'])} do {usd(z['hi'])} je zona.",
        (0.03, 0.12),
        width=34,
        color=nb.GREEN,
        rad=-0.2,
    )
    note(
        ax,
        c,
        z["known"],
        float(b.close[z["known"]]),
        f"{dmy(b.dates[z['known']])}: rast od barem 2 prosječna dnevna raspona preko zadnjeg vrha. Tek tada zona postoji.",
        (0.03, 0.80),
        width=34,
        color=nb.INK,
        rad=-0.2,
    )
    note(
        ax,
        c,
        t,
        float(b.close[t]),
        f"{dmy(b.dates[t])}: cijena se prvi put vratila u zonu i zatvorila iznad njezina dna = signal.",
        (0.38, 0.12),
        width=32,
        rad=-0.15,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.55, 0.90 if ex.r10 < 0 else 0.34),
        color=nb.INK,
        width=36,
    )
    return save(fig, out, f"zona_{ex.kind}.png")


# ----------------------------------------------------------------------------- premium / discount


def chart_discount(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    x = ex.extra
    lo, hi = x["range_lo"], x["range_hi"]
    s, e = max(0, min(x["range_lo_i"], x["range_hi_i"], x["sweep"]["idx"]) - 25), t + 30
    fig, ax = frame(c, s, e, f"Premium i diskont, {ex.ticker}, {kind_word(ex.kind)}")
    mid = 0.5 * (lo + hi)
    ax.axhspan(lo, mid, color=nb.GREEN, alpha=0.13, zorder=1, lw=0)
    ax.axhspan(mid, hi, color=nb.RED, alpha=0.10, zorder=1, lw=0)
    ax.axhline(mid, color=GREY, ls=":", lw=1.4, zorder=2)
    dot(ax, c, x["range_lo_i"], lo, nb.GREEN, "^", 100)
    dot(ax, c, x["range_hi_i"], hi, nb.RED, "v", 100)
    sidx = x["sweep"]["idx"]
    dot(ax, c, sidx, float(b.close[sidx]), ORANGE, "o", 90)
    outcome_marks(ax, c, t)
    posn = (float(b.close[sidx]) - lo) / (hi - lo) * 100
    note(
        ax,
        c,
        x["range_lo_i"],
        lo,
        f"Zadnje potvrđeno dno {usd(lo)}.",
        (0.03, 0.08),
        width=24,
        color=nb.GREEN,
        rad=-0.2,
    )
    note(
        ax,
        c,
        x["range_hi_i"],
        hi,
        f"Zadnji potvrđeni vrh {usd(hi)}.",
        (0.03, 0.88),
        width=24,
        color=nb.RED,
        rad=-0.2,
    )
    where = (
        f"je na {hr(posn, 0)} % raspona"
        if posn >= 0
        else "je čak ispod zadnjeg potvrđenog dna"
    )
    note(
        ax,
        c,
        sidx,
        float(b.close[sidx]),
        f"{dmy(b.dates[sidx])}: zatvaranje {usd(b.close[sidx])} {where}, dakle u DISKONTU (ispod sredine {usd(mid)}).",
        (0.30, 0.56),
        width=34,
        color=ORANGE,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.58, 0.90 if ex.r10 < 0 else 0.22),
        color=nb.INK,
        width=36,
    )
    legend(
        fig,
        "zeleno polje: diskont (donja polovica raspona)  |  crveno polje: premium (gornja polovica)  |  crvena okomita: dan odluke",
    )
    return save(fig, out, f"diskont_{ex.kind}.png")


# ----------------------------------------------------------------------------- top-down (weekly + daily)


def _weekly_candles(ax: Any, w: mx.Weekly, i0: int, i1: int) -> None:
    x = mdates.date2num(w.end[i0:i1].to_pydatetime())
    o, h, lo, cl = w.open[i0:i1], w.high[i0:i1], w.low[i0:i1], w.close[i0:i1]
    up = cl >= o
    ax.vlines(x, lo, h, color=nb.PENCIL, lw=0.9, zorder=3)
    body = np.maximum(np.abs(cl - o), (h - lo) * 0.02)
    ax.bar(
        x[up],
        body[up],
        bottom=np.minimum(o, cl)[up],
        width=3.6,
        color=nb.PAPER,
        edgecolor=nb.GREEN,
        lw=1.0,
        zorder=4,
    )
    ax.bar(
        x[~up],
        body[~up],
        bottom=np.minimum(o, cl)[~up],
        width=3.6,
        color=nb.PENCIL,
        edgecolor=nb.PENCIL,
        lw=0.6,
        zorder=4,
    )


def chart_topdown(ex: le.Example, out: Path) -> str:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    t = ex.t
    w = c.P.weekly
    known = w.known_at <= t
    wi = (
        int(np.flatnonzero(known & w.complete)[-1]) if (known & w.complete).any() else 0
    )
    i0 = max(0, wi - 60)
    fig, (axw, ax) = plt.subplots(
        2, 1, figsize=(11, 8.4), gridspec_kw={"height_ratios": [1, 1.25]}
    )
    sheet(
        axw,
        f"Odozgo prema dolje: tjedni smjer, dnevni okidač, {ex.ticker}, {kind_word(ex.kind)}",
    )
    _weekly_candles(axw, w, i0, wi + 1)
    wp = [
        p
        for p in mx.find_pivots(w.high[: wi + 1], w.low[: wi + 1])
        if p.idx >= i0 and p.confirm <= wi
    ]
    for p in wp:
        up = p.kind == "H"
        axw.scatter(
            [mdates.date2num(w.end[p.idx].to_pydatetime())],
            [p.price],
            marker="v" if up else "^",
            color=nb.GREEN if not up else nb.RED,
            s=55,
            zorder=8,
        )
    axw.set_xlim(
        mdates.date2num(w.end[i0].to_pydatetime()) - 8,
        mdates.date2num(w.end[wi].to_pydatetime()) + 12,
    )
    axw.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=7))
    axw.xaxis.set_major_formatter(FuncFormatter(lambda v, _: dmy(mdates.num2date(v))))
    axw.set_ylabel("tjedna svijeća (USD)")
    bias = int(c.P.wbias[t])
    word = {
        1: "BIKOVSKI (viši vrhovi i viša dna)",
        -1: "MEDVJEĐI",
        0: "bez jasnog smjera",
    }[bias]
    free_note(
        axw,
        f"Tjedni trend na dan {dmy(b.dates[t])}: {word}.\nSamo završeni tjedni; trokuti su potvrđeni vrhovi (crveno) i dna (zeleno).",
        (0.03, 0.86),
        width=64,
        size=10,
    )
    s, e = max(0, t - 70), t + 32
    sheet(ax, "Dnevni graf istog razdoblja: okidač")
    _candles(ax, c.P, s, e)
    lo, hi = float(b.low[s:e].min()), float(b.high[s:e].max())
    ax.set_ylim(lo - (hi - lo) * 0.12, hi + (hi - lo) * 0.12)
    ax.set_xlim(X(c, s) - 1.5, X(c, e - 1) + 3.5)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=7))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: dmy(mdates.num2date(v))))
    ax.set_ylabel("cijena dionice (USD)")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.95, bottom=0.07, hspace=0.28)
    ax._placer = Placer(ax, c, s, e)
    sw, sh = ex.extra["sweep"], ex.extra["shift"]
    hline(ax, c, max(sw["pivot_idx"], s), sw["idx"], sw["level"], nb.INK, "-", 1.6)
    dot(ax, c, sw["idx"], float(b.low[sw["idx"]]), ORANGE, "v", 100)
    hline(ax, c, max(sh["level_idx"], s), t, sh["level"], ORANGE, "--", 1.5)
    outcome_marks(ax, c, t)
    note(
        ax,
        c,
        sw["idx"],
        float(b.low[sw["idx"]]),
        f"{dmy(b.dates[sw['idx']])}: sweep dna u diskontu.",
        (0.03, 0.14),
        width=26,
        color=ORANGE,
        rad=-0.2,
    )
    note(
        ax,
        c,
        t,
        float(b.close[t]),
        f"{dmy(b.dates[t])}: promjena smjera uz bikovski tjedni trend = signal.",
        (0.30, 0.86),
        width=32,
        rad=-0.15,
    )
    note(
        ax,
        c,
        t + le.H,
        float(b.close[t + le.H]),
        result_text(c, t),
        (0.56, 0.62 if ex.r10 < 0 else 0.22),
        color=nb.INK,
        width=36,
    )
    return save(fig, out, f"topdown_{ex.kind}.png")


# ----------------------------------------------------------------------------- evidence charts (saved JSON only)

RULE_NAMES = {
    "W1_C13C_ORIG": "W1 C13C",
    "W2_MOM_BREAK_20": "W2 proboj 20 dana",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang",
    "W4_SR_BOUNCE_V2": "W4 odbijanje potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj + povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 sweep + promjena",
    "W7_MM_DEMAND_RETEST": "W7 zona potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
}


def load_swing() -> dict[str, Any]:
    return json.loads((le.SWING / "summary.json").read_text())


def load_placebo() -> dict[str, Any]:
    return json.loads((le.SWING / "placebo.json").read_text())


def chart_ev_rules(out: Path) -> str:
    s = load_swing()
    g = s["groups"]["stocks_all"]
    pc = g["per_contender"]
    rows = [(k, pc[k]) for k in RULE_NAMES]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    sheet(ax, "Što pravila zarađuju po poslu (sve dionice, AI era)")
    names = [RULE_NAMES[k] for k, _ in rows][::-1]
    vals = [r["expectancy_eur"] for _, r in rows][::-1]
    elig = {x["contender"]: x["eligible"] for x in g["ranking"] + g["not_eligible"]}
    cols = [nb.GREEN if elig[k] else nb.RED for k, _ in rows][::-1]
    ax.barh(names, vals, color=cols, alpha=0.75, zorder=3)
    for i, (k, r) in enumerate(rows[::-1]):
        ax.text(
            r["expectancy_eur"] + 1.5,
            i,
            f"{hr(r['expectancy_eur'], 0)} € po poslu | {hr(r['trades_per_month'], 1)} poslova mj. | {hr(r['hit_rate'] * 100, 0)} % dobitnih",
            va="center",
            fontsize=9.5,
            color=nb.PENCIL,
        )
    ax.set_xlim(0, max(vals) * 1.85)
    ax.set_xlabel("prosječna zarada po poslu na 1.000 € (prije poreza)")
    bh = g["buy_and_hold_reference"]["total_return"]
    free_note(
        ax,
        f"Zeleno: zadovoljava pravilo 'radi često'. Crveno: ne.\nKupi-i-drži na istim dionicama: {hr(bh * 100, 0)} % u istom razdoblju;\nnijedno pravilo ga ne dostiže, jer su većinom u gotovini.",
        (0.46, 0.10),
        width=60,
        size=10,
    )
    fig.subplots_adjust(left=0.2, right=0.985, top=0.92, bottom=0.1)
    return save(fig, out, "dokaz_pravila.png")


def chart_ev_eras(out: Path) -> str:
    g = json.loads((le.SWING / "results" / "stocks_all.json").read_text())["contenders"]
    eras = [
        ("y2016_2020", "2016 do 2020"),
        ("y2021_2022", "2021 do 2022 (pad)"),
        ("ai_era", "AI era (2023+)"),
    ]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    sheet(ax, "Isto pravilo, tri razdoblja: zarada po poslu")
    keys = list(RULE_NAMES)
    w = 0.26
    cols = [GREY, nb.RED, nb.GREEN]
    for j, (ek, el) in enumerate(eras):
        vals = []
        for k in keys:
            blk = g[k]["ai_era"] if ek == "ai_era" else g[k]["contexts"][ek]
            vals.append(blk["expectancy_eur"])
        ax.bar(
            np.arange(len(keys)) + (j - 1) * w,
            vals,
            w,
            label=el,
            color=cols[j],
            alpha=0.8,
            zorder=3,
        )
    ax.axhline(0, color=nb.PENCIL, lw=1.2)
    ax.set_xticks(np.arange(len(keys)))
    ax.set_xticklabels(
        [RULE_NAMES[k].replace(" ", "\n", 1) for k in keys], fontsize=8.8
    )
    ax.set_ylabel("zarada po poslu na 1.000 € (EUR)")
    ax.legend(loc="upper right", frameon=False)
    free_note(
        ax,
        "U padu 2021 do 2022 većina pravila nema prednost ili gubi.\nTo je razlog zašto 'radi' vrijedi samo za AI eru.",
        (0.03, 0.88),
        width=56,
        size=10,
    )
    fig.subplots_adjust(left=0.08, right=0.985, top=0.92, bottom=0.14)
    return save(fig, out, "dokaz_razdoblja.png")


def chart_ev_levels(out: Path) -> str:
    sr = load_placebo()["sr"]["all"]
    series = [
        ("real", "prave razine", nb.GREEN),
        ("rand", "nasumične crte", GREY),
        ("shift", "pomak ±3 %", ORANGE),
        ("mreal", "prave razine (samo podskup za par)", "#5aa37a"),
        ("match", "par oko razine", PURPLE),
    ]
    metrics = [
        ("touch_rate", "dodir u idućih 20 dana"),
        ("bounce_rate", "odbijanje (nakon dodira)"),
        ("break_rate", "probijanje (nakon dodira)"),
    ]
    fig, ax = plt.subplots(figsize=(11, 6.0))
    sheet(ax, "Razine nasuprot lažnim crtama (55 papira, AI era)")
    w = 0.16
    for j, (k, lab, col) in enumerate(series):
        vals = [sr[k][m] * 100 for m, _ in metrics]
        bars = ax.bar(
            np.arange(3) + (j - 2) * w,
            vals,
            w,
            label=lab,
            color=col,
            alpha=0.8,
            zorder=3,
        )
        for r, v in zip(bars, vals):
            ax.text(
                r.get_x() + r.get_width() / 2,
                v + 0.6,
                hr(v, 1),
                ha="center",
                fontsize=8.2,
            )
    ax.set_xticks(range(3))
    ax.set_xticklabels([m[1] for m in metrics])
    ax.set_ylabel("postotak slučajeva")
    ax.set_ylim(0, 66)
    ax.legend(loc="upper left", ncol=3, frameon=False, fontsize=9)
    d = sr["diff_vs_rand"]["bounce_rate"]
    legend(
        fig,
        f"Odbijanje: prave {hr(sr['real']['bounce_rate'] * 100, 1)} %, nasumične {hr(sr['rand']['bounce_rate'] * 100, 1)} %. Razlika {hr(d['diff'] * 100, 1)} pp, interval [{hr(d['ci95'][0] * 100, 1)}; {hr(d['ci95'][1] * 100, 1)}] obuhvaća nulu: razina ne odbija cijenu češće od lažne crte.",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.92, bottom=0.14)
    return save(fig, out, "dokaz_razine.png")


def chart_ev_mech(out: Path) -> str:
    p = load_placebo()
    ai = p["mechanics_ai_era"]["events"]
    pre = p["mechanics_pre_ai_context"]["events"]
    keys = list(ai)
    short = {
        "E1_sweep_shift_discount": "E1 sweep + promjena\nu diskontu",
        "E2_sweep_shift_discount_weekly": "E2 isto + bikovski\ntjedni trend",
        "E3_sweep_shift_discount_weekly_zone": "E3 isto + dodir\nsvježe zone",
        "E4_demand_zone_retest": "E4 prvi povratak\nu zonu potražnje",
        "E5_bos_trend": "E5 BOS u bikovskom\ntrendu",
    }
    fig, ax = plt.subplots(figsize=(11, 6.2))
    sheet(ax, "Mehanika tržišta: višak prinosa nad prosjekom papira, 10 dana")
    for j, (src, lab, col) in enumerate(
        [(ai, "AI era (2023+)", nb.GREEN), (pre, "2017 do 2022", GREY)]
    ):
        for i, k in enumerate(keys):
            st = src[k]["by_h"]["10"]
            y = i + (0.16 if j == 0 else -0.16)
            m, lo, hi = (
                st["mean_excess_vs_ticker_avg"] * 100,
                st["excess_ci95"][0] * 100,
                st["excess_ci95"][1] * 100,
            )
            ax.plot([lo, hi], [y, y], color=col, lw=3, alpha=0.8, zorder=3)
            ax.scatter(
                [m], [y], color=col, s=60, zorder=5, label=lab if i == 0 else None
            )
            ax.text(
                hi + 0.4, y, f"n={src[k]['n']}", va="center", fontsize=8.5, color=col
            )
    ax.axvline(0, color=nb.RED, lw=1.5)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([short[k] for k in keys], fontsize=9.3)
    ax.set_xlabel("višak prinosa u postotnim bodovima (pp); crta = 95 % interval")
    ax.legend(loc="lower left", frameon=False)
    legend(
        fig,
        "Interval koji obuhvaća nulu (crvena crta) = nema dokaza prednosti. E4 u AI eri jedva dodiruje nulu odozdo, a prije AI ere ima suprotan predznak.",
    )
    ax.set_xlim(-8, 5.4)
    ax.invert_yaxis()
    fig.subplots_adjust(left=0.19, right=0.985, top=0.92, bottom=0.14)
    return save(fig, out, "dokaz_mehanika.png")
