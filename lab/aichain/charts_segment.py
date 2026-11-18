"""Notebook-style charts for one AI-chain segment page (graph paper, handwriting, pencil arrows, red teacher notes).

Everything is drawn from REAL files only: ``segments/{segment}/analysis.json`` and ``profile.json``,
``results/{segment}.json`` and ``results/{TICKER}.json``, and the daily bars in ``data/ohlcv``.
Nothing is invented; every number in a note is computed here from those files. Research only, no orders.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lab.aichain.contenders import trail_stop
from lab.aichain.profile_stats import (
    PIVOT_K,
    SR_BAND,
    SR_LOOKAHEAD,
    SR_MAX_AGE,
    load_close_frame,
    pivots,
)
from lab.aichain.sim import load_bars
from lab.top10.charts import GREEN, GRID, INK, PAPER, PENCIL, RED, sketch

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "reports/research/AICHAIN_20261014"
AI_START = pd.Timestamp("2023-01-01")
HOLD_C, C13C_C, WIN_C, OTHER_C = "#6b7280", INK, GREEN, "#b08a2e"
FONT = 11.5


# --------------------------------------------------------------------------- formatting
def eur(x: float) -> str:
    return f"{x:,.0f} EUR".replace(",", ".")


def day(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def pc(x: float, digits: int = 0, sign: bool = True) -> str:
    s = f"{x * 100:+.{digits}f}" if sign else f"{x * 100:.{digits}f}"
    return s.replace(".", ",") + " %"


def usd(x: float) -> str:
    return f"{x:,.2f} USD".replace(",", "X").replace(".", ",").replace("X", ".")


def hr(text: str) -> str:
    """Croatian decimal comma for 1-2 digit decimals; 3-digit groups stay thousands dots (1.000)."""
    return re.sub(r"(?<=\d)\.(?=\d{1,2}(?!\d))", ",", text)


def wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(hr(text), width=width))


# --------------------------------------------------------------------------- data access
def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


class Seg:
    """Lazy access to all real inputs of one segment."""

    def __init__(self, segment: str) -> None:
        self.segment = segment
        self.dir = RES / "segments" / segment
        self.analysis: dict[str, Any] = load_json(self.dir / "analysis.json")
        self.profile: dict[str, Any] = load_json(self.dir / "profile.json")
        self.seg: dict[str, Any] = load_json(RES / "results" / f"{segment}.json")
        self.tickers: list[str] = list(self.seg["tickers"])
        self._tk: dict[str, dict[str, Any]] = {}

    def tk(self, ticker: str) -> dict[str, Any]:
        if ticker not in self._tk:
            self._tk[ticker] = load_json(RES / "results" / f"{ticker}.json")
        return self._tk[ticker]

    def curve(self, contender: str, per: float = 10.0) -> pd.Series:
        """Segment equity of one contender per 1.000 EUR invested (10 sleeves of 1.000 EUR divided by ``per``)."""
        rows = self.seg["contenders"][contender]["equity"]["ai_era"]
        return pd.Series(
            [v / per for _, v in rows], index=pd.DatetimeIndex([d for d, _ in rows])
        )

    def trades(self, contender: str) -> list[dict[str, Any]]:
        return list(self.seg["contenders"][contender]["trades"]["ai_era"])

    def ticker_trades(self, ticker: str, contender: str) -> list[dict[str, Any]]:
        return list(self.tk(ticker)["contenders"][contender]["trades"]["ai_era"])

    def table(self, contender: str) -> dict[str, Any]:
        return self.analysis["segment_portfolio_table_ai_era"]["contenders"][contender]


# --------------------------------------------------------------------------- notebook primitives
def paper(ax: Any, title: str) -> None:
    ax.set_facecolor(PAPER)
    ax.grid(True, color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", pad=24, color=INK)


def legend_top(ax: Any, **kw: Any) -> None:
    ax.legend(
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=kw.pop("ncol", 4),
        frameon=False,
        fontsize=10.5,
        **kw,
    )


def frac(ax: Any, xs: Any, ys: Any) -> np.ndarray:
    """Data points to axes-fraction coordinates (needs final limits)."""
    seq = list(xs)
    if isinstance(seq[0], (pd.Timestamp, np.datetime64)):
        xn = mdates.date2num(pd.DatetimeIndex(seq))
    else:
        xn = np.asarray(seq, float)
    pts = ax.transData.transform(np.column_stack([xn, np.asarray(ys, float)]))
    return ax.transAxes.inverted().transform(pts)


class Notes:
    """Places handwritten notes on free paper, away from the plotted lines and from each other."""

    def __init__(self, ax: Any, xs: Any, ys_list: list[Any]) -> None:
        self.ax = ax
        ax.figure.canvas.draw()
        self.pts = np.vstack([frac(ax, xs, y) for y in ys_list])
        self.taken: list[tuple[float, float, float, float]] = [
            (0.0, 0.93, 1.0, 0.07),
        ]

    def _size(self, text: str, size: float) -> tuple[float, float]:
        bb = self.ax.get_window_extent()
        dpi = self.ax.figure.dpi
        lines = text.split("\n")
        w = max(len(s) for s in lines) * 0.60 * size * dpi / 72 / bb.width
        h = len(lines) * 1.6 * size * dpi / 72 / bb.height
        return w, h

    def _score(self, x0: float, y0: float, w: float, h: float) -> float:
        p = self.pts
        inside = (
            (p[:, 0] > x0 - 0.01)
            & (p[:, 0] < x0 + w + 0.01)
            & (p[:, 1] > y0 - 0.02)
            & (p[:, 1] < y0 + h + 0.02)
        )
        s = float(inside.sum())
        for tx, ty, tw, th in self.taken:
            if x0 < tx + tw and tx < x0 + w and y0 < ty + th and ty < y0 + h:
                s += 5000.0
        return s

    def put(
        self,
        text: str,
        xy: tuple[Any, float],
        width: int = 34,
        color: str = PENCIL,
        size: float = FONT,
        near: tuple[float, float] | None = None,
        rad: float = 0.25,
        arrow: bool = True,
        at: tuple[float, float] | None = None,
    ) -> None:
        """Write ``text`` (wrapped) in the freest spot and point a pencil arrow at ``xy`` (data coordinates)."""
        text = wrap(text, width)
        w, h = self._size(text, size)
        target = near
        if target is None:
            target = tuple(frac(self.ax, [xy[0]], [xy[1]])[0])
        best: tuple[float, float, float] | None = None
        if at is not None:
            best = (0.0, at[0], at[1])
        xs0 = [] if at is not None else np.linspace(0.02, max(0.03, 0.98 - w), 14)
        for x0 in xs0:
            for y0 in np.linspace(0.03, max(0.04, 0.92 - h), 14):
                sc = self._score(x0, y0, w, h)
                cx, cy = x0 + w / 2, y0 + h / 2
                sc += 2.0 * np.hypot(cx - target[0], cy - target[1])
                if best is None or sc < best[0]:
                    best = (sc, x0, y0)
        assert best is not None
        _, x0, y0 = best
        self.taken.append((x0, y0, w, h))
        kw: dict[str, Any] = {}
        if arrow:
            kw["arrowprops"] = dict(
                arrowstyle="->",
                color=color,
                lw=1.4,
                connectionstyle=f"arc3,rad={rad}",
                shrinkB=3,
            )
        a = self.ax.annotate(
            text,
            xy=xy,
            xycoords="data",
            xytext=(x0, y0),
            textcoords="axes fraction",
            ha="left",
            va="bottom",
            fontsize=size,
            color=color,
            **kw,
        )
        if a.arrow_patch is not None:
            sketch(a.arrow_patch, 0.9, 60, 3)


def circle(ax: Any, x: Any, y: float, color: str = RED, size: int = 700) -> None:
    ax.scatter(
        [x], [y], s=size, facecolors="none", edgecolors=color, linewidths=2.0, zorder=6
    )


def teacher(fig: Any, text: str, width: int = 118) -> float:
    """Write the red teacher note under the plots; returns the bottom margin (figure fraction) it needs."""
    body = wrap("Bilješka učitelja: " + text, width)
    n = body.count("\n") + 1
    h = fig.get_size_inches()[1]
    margin = (n * 0.23 + 0.2) / h
    fig.text(0.012, 0.008, body, fontsize=11.5, color=RED, ha="left", va="bottom")
    return margin


def ai_line(ax: Any, x: Any = None, label: bool = True) -> None:
    x = pd.Timestamp("2023-01-01") if x is None else pd.Timestamp(x)
    ax.axvline(x, color=RED, ls="--", lw=1.3)
    if label:
        ax.text(
            x + pd.Timedelta(days=14),
            0.84,
            "od ovdje: AI era\n(glavno mjerilo)",
            transform=ax.get_xaxis_transform(),
            fontsize=10,
            color=RED,
        )


def save(fig: Any, path: Path) -> str:
    fig.savefig(path, dpi=118, facecolor=PAPER)
    plt.close(fig)
    return path.name


def money_axis(ax: Any) -> None:
    from matplotlib.ticker import FuncFormatter

    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", "."))
    )
    ax.set_ylabel("vrijednost u EUR (od 1.000 EUR)")


def date_axis(ax: Any) -> None:
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%Y."))


# --------------------------------------------------------------------------- 1 price with entries/exits/stop
def stop_path(bars: Any, trade: dict[str, Any], trail: float = 0.10) -> pd.Series:
    """Re-derive the sliding stop of one K1 trade exactly like ``sim.run_sleeve`` (a raise acts from the next bar)."""
    i = int(bars.dates.get_loc(pd.Timestamp(trade["entry_date"])))
    j = int(bars.dates.get_loc(pd.Timestamp(trade["exit_date"])))
    peak = float(trade["entry_price"])
    stop = trail_stop(peak, trail)
    out: dict[pd.Timestamp, float] = {}
    for k in range(i, j + 1):
        out[bars.dates[k]] = stop
        if k < j:
            peak = max(peak, float(bars.high[k]))
            stop = max(stop, trail_stop(peak, trail))
    return pd.Series(out)


def chart_price(S: Seg, outdir: Path, tickers: list[str]) -> str:
    fig, axes = plt.subplots(len(tickers), 1, figsize=(11.5, 4.3 * len(tickers)))
    checks: list[str] = []
    used_signal_dates: list[pd.Timestamp] = []
    for ax, tk in zip(np.atleast_1d(axes), tickers):
        bars = load_bars(tk)
        close = pd.Series(bars.close, index=bars.dates)
        sma = close.rolling(200).mean()
        view = close[close.index >= "2022-01-03"]
        trades = S.ticker_trades(tk, "K1_C13C_ORIG")
        paper(ax, f"{tk}: cijena, prosjek 200 dana i svaki C13C ulaz/izlaz")
        ax.plot(view.index, view.values, color=INK, lw=1.5, label="cijena zatvaranja")
        ax.plot(
            sma[view.index].index,
            sma[view.index].values,
            color=PENCIL,
            lw=1.3,
            ls="--",
            label="prosjek 200 dana (SMA200)",
        )
        ax.scatter(
            [pd.Timestamp(t["entry_date"]) for t in trades],
            [t["raw_entry"] for t in trades],
            marker="^",
            s=70,
            color=GREEN,
            zorder=5,
            label="kupnja (C13C)",
        )
        stops = [t for t in trades if t["reason"] in ("stop",)]
        ax.scatter(
            [pd.Timestamp(t["exit_date"]) for t in stops],
            [t["raw_exit"] for t in stops],
            marker="v",
            s=70,
            color=RED,
            zorder=5,
            label="izbacivanje stopom",
        )
        end = [t for t in trades if t["reason"] == "end"]
        if end:
            ax.scatter(
                [pd.Timestamp(t["exit_date"]) for t in end],
                [t["raw_exit"] for t in end],
                marker="s",
                s=45,
                color=PENCIL,
                zorder=5,
                label="kraj simulacije",
            )
        # stop line for the longest winning stop trade not longer than ~4 months
        cand = [
            t
            for t in trades
            if t["detail"] == "stop"
            and t["return"] > 0.05
            and 15 <= t["bars_held"] <= 85
        ]
        st = max(cand, key=lambda t: t["return"]) if cand else None
        if st is not None:
            sp = stop_path(bars, st)
            ax.step(
                sp.index,
                sp.values,
                where="post",
                color=RED,
                lw=2.0,
                zorder=4,
                label="stop (klizni)",
            )
            last_stop = float(sp.iloc[-1])
            checks.append(
                f"{tk}: zadnji stop {last_stop:.2f} vs izlaz {st['raw_exit']:.2f} ({st['detail']})"
            )
            assert (
                abs(last_stop - st["raw_exit"]) < 0.02 or st["detail"] == "gap_stop"
            ), (tk, last_stop, st)
        # the deepest dip signal that was not already used on a previous panel (a different episode each time)
        cands = []
        for t in trades:
            ei = int(bars.dates.get_loc(pd.Timestamp(t["entry_date"])))
            sj = ei - 1
            drop = close.iloc[sj] / close.iloc[sj - 5] - 1
            above = close.iloc[sj] > sma.iloc[sj]
            assert drop <= -0.05 and above, (tk, t["entry_date"], drop)
            cands.append((drop, t, sj))
        cands.sort(key=lambda c: c[0])
        best = None
        for c in cands:
            ed = pd.Timestamp(c[1]["entry_date"])
            if all(abs((ed - u).days) > 60 for u in used_signal_dates):
                best = c
                break
        if best is not None:
            used_signal_dates.append(pd.Timestamp(best[1]["entry_date"]))
        ax.set_yscale("log")
        ax.set_ylim(view.min() * 0.85, view.max() * 1.25)
        ticks = [
            v
            for v in (25, 50, 100, 200, 400, 800)
            if view.min() * 0.85 < v < view.max() * 1.25
        ]
        ax.set_yticks(ticks)
        ax.set_yticks([], minor=True)
        ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.set_xlim(pd.Timestamp("2022-01-03"), pd.Timestamp("2026-11-10"))
        ai_line(ax)
        date_axis(ax)
        ax.set_ylabel("cijena u USD (logaritamska skala)")
        legend_top(ax, ncol=3)
        notes = Notes(ax, view.index, [view.values, sma[view.index].values])
        notes.taken.append((0.2, 0.8, 0.2, 0.14))
        if best is not None:
            drop, t, sj = best
            d0, d1 = close.index[sj - 5], close.index[sj]
            units = 1000 / t["raw_entry"]
            notes.put(
                f"{day(d1)}: u 5 dana pad {pc(drop, 1)} ({close.iloc[sj - 5]:.2f} → {close.iloc[sj]:.2f} USD), "
                f"a cijena je iznad SMA200: signal za kupnju. Sutradan na otvaranju {t['raw_entry']:.2f} USD; "
                f"1.000 EUR = {units:.2f} dionica.",
                (pd.Timestamp(t["entry_date"]), t["raw_entry"]),
                width=40,
                color=GREEN,
            )
        if st is not None:
            peak_end = float(
                bars.high[bars.dates.get_loc(pd.Timestamp(st["exit_date"]))]
            )
            notes.put(
                f"Crvena crta je stop: uvijek 10 % ispod najvišeg dosega i nikad ne pada. "
                f"Ovdje je pratila cijenu od {st['entry_price']:.2f} do izlaza {st['raw_exit']:.2f} USD "
                f"({pc(st['return'], 1)}, {day(st['exit_date'])}).",
                (pd.Timestamp(st["exit_date"]), st["raw_exit"]),
                width=40,
                color=RED,
            )
        gaps = [t for t in trades if t["detail"] == "gap_stop"]
        if gaps and tk == tickers[-1]:
            g = min(gaps, key=lambda t: t["return"])
            notes.put(
                f"Izlaz preko noći ({day(g['exit_date'])}): dan je otvoren ispod stopa pa je izlaz po {g['raw_exit']:.2f} USD "
                f"({pc(g['return'], 1)}) a ne po stopu. Stop ne štiti od jaza.",
                (pd.Timestamp(g["exit_date"]), g["raw_exit"]),
                width=40,
            )
    m = teacher(
        fig,
        "Zelen trokut je kupnja, crven obrnuti trokut je izbacivanje stopom. Pravilo C13C kupuje samo kad cijena padne 5 % u 5 dana, "
        "a još je iznad dugoročnog prosjeka (SMA200). Primjer: 1.000 EUR kupi na ulazu dionice, a ako cijena padne 10 % od vrha, "
        "stop prodaje i ostaje otprilike 900 EUR (ili više, ako je vrh bio visoko iznad ulaza). "
        "Prije crvene crte (2023.) simulacija ne trguje, to je samo kontekst.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    S._checks = getattr(S, "_checks", []) + checks  # type: ignore[attr-defined]
    return save(fig, outdir / "01_cijene_c13c.png")


# --------------------------------------------------------------------------- 2 equity
def invested_count(S: Seg, contender: str, cal: pd.DatetimeIndex) -> pd.Series:
    cnt = pd.Series(0, index=cal)
    for t in S.trades(contender):
        m = (cal >= pd.Timestamp(t["entry_date"])) & (
            cal < pd.Timestamp(t["exit_date"])
        )
        cnt[m] += 1
    return cnt


def longest_run(flag: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    best, cur, st = (None, None), 0, None
    bl = 0
    for d, v in flag.items():
        if v:
            if cur == 0:
                st = d
            cur += 1
            if cur > bl:
                bl, best = cur, (st, d)
        else:
            cur = 0
    assert best[0] is not None
    return best  # type: ignore[return-value]


def chart_equity(S: Seg, outdir: Path) -> str:
    win = S.analysis["winner"]["winner"]
    hold, c13, wn = S.curve("B0_BUYHOLD"), S.curve("K1_C13C_ORIG"), S.curve(win)
    cnt = invested_count(S, "K1_C13C_ORIG", c13.index)
    r0, r1 = longest_run(cnt <= 1)
    fig, ax = plt.subplots(figsize=(11.5, 6.6))
    paper(ax, f"Rast 1.000 EUR u cijelom segmentu ({len(S.tickers)} dionica)")
    ax.axvspan(r0, r1, color="#e8f0ff", alpha=0.9, lw=0)
    ax.plot(hold.index, hold.values, color=HOLD_C, lw=2.0, label="kupi i drži")
    ax.plot(c13.index, c13.values, color=C13C_C, lw=2.0, label="C13C (tvoj algoritam)")
    ax.plot(
        wn.index,
        wn.values,
        color=WIN_C,
        lw=2.0,
        label=f"pobjednik segmenta ({win.split('_', 1)[0]} {win.split('_', 1)[1].replace('_', ' ').title()})",
    )
    ax.set_xlim(
        hold.index[0] - pd.Timedelta(days=20), hold.index[-1] + pd.Timedelta(days=40)
    )
    ax.axvline(hold.index[0], color=RED, ls="--", lw=1.3)
    ax.text(
        hold.index[0] + pd.Timedelta(days=10),
        0.025,
        "AI era počinje:\n3. 1. 2023.",
        transform=ax.get_xaxis_transform(),
        color=RED,
        fontsize=10,
    )
    date_axis(ax)
    money_axis(ax)
    legend_top(ax, ncol=3)
    ax.set_ylim(0, max(hold.max(), wn.max()) * 1.1)
    ep = S.analysis["winner"]["drawdown_episodes_from_equity_curves"]["B0_BUYHOLD"][
        "window_2024_07_to_2025_04"
    ]
    pk, bt = pd.Timestamp(ep["peak_date"]), pd.Timestamp(ep["bottom_date"])
    h_pk, h_bt, c_pk, c_bt = hold[pk], hold[bt], c13[pk], c13[bt]
    ax.scatter(
        [hold.index[-1]] * 3,
        [hold.iloc[-1], wn.iloc[-1], c13.iloc[-1]],
        color=[HOLD_C, WIN_C, C13C_C],
        s=40,
        zorder=5,
    )
    ax.scatter([pk, bt], [h_pk, h_bt], color=HOLD_C, s=45, zorder=5)
    ax.scatter([pk, bt], [c_pk, c_bt], color=C13C_C, s=45, zorder=5)
    mid = c13.index[
        int(np.searchsorted(c13.index.values, (r0 + (r1 - r0) / 2).to_datetime64()))
    ]
    n = Notes(ax, hold.index, [hold.values, c13.values, wn.values])
    n.put(
        f"Plavo polje ({day(r0)} do {day(r1)}): C13C drži najviše 1 od 10 dionica, ostalo je gotovina. Crta mu je gotovo ravna jer novac samo stoji.",
        (mid, float(c13[mid])),
        width=42,
        color=C13C_C,
        at=(0.50, 0.60),
    )
    n.put(
        f"Veliki pad ({day(pk)} → {day(bt)}): držanje {eur(h_pk)} → {eur(h_bt)}, gubitak {eur(h_pk - h_bt)}. "
        f"C13C {eur(c_pk)} → {eur(c_bt)}, gubitak {eur(c_pk - c_bt)}. C13C je tu sačuvao {eur((h_pk - h_bt) - (c_pk - c_bt))} od svake 1.000 EUR.",
        (bt, float(h_bt)),
        width=40,
        color=HOLD_C,
        at=(0.10, 0.66),
    )
    for series, col, lab in (
        (hold, HOLD_C, "kupi i drži"),
        (wn, WIN_C, "pobjednik"),
        (c13, C13C_C, "C13C"),
    ):
        ax.text(
            series.index[-1] + pd.Timedelta(days=6),
            float(series.iloc[-1]),
            f"{eur(series.iloc[-1])}",
            color=col,
            fontsize=10.5,
            va="center",
        )
    ax.set_xlim(
        hold.index[0] - pd.Timedelta(days=20), hold.index[-1] + pd.Timedelta(days=150)
    )
    n.put(
        "Cijena sigurnosti: dok je C13C vani, propušta i uspon, pa mu je crta cijelo vrijeme ispod crte držanja.",
        (pd.Timestamp("2024-06-03"), float(c13["2024-06-03":].iloc[0])),
        width=30,
        color=RED,
        at=(0.03, 0.36),
    )
    m = teacher(
        fig,
        f"Svi počinju s 1.000 EUR (podijeljeno ravnomjerno na {len(S.tickers)} dionica, 100 EUR po dionici). Crta držanja je mjerilo: "
        f"strategija ima smisla samo ako ga prestigne ili bar bitno smanji muku. Ovdje nitko od {len(S.analysis['winner']['eligibility'])} pravila nije prestigao držanje po prinosu. "
        "Cijene su u USD, tretirane kao EUR; tečaj, porezi i dividende nisu uključeni.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "02_rast_1000_eur.png")


# --------------------------------------------------------------------------- 3 drawdown
def chart_drawdown(S: Seg, outdir: Path) -> str:
    win = S.analysis["winner"]["winner"]
    curves = {
        "kupi i drži": (S.curve("B0_BUYHOLD"), HOLD_C),
        "C13C": (S.curve("K1_C13C_ORIG"), C13C_C),
        "pobjednik": (S.curve(win), WIN_C),
    }
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    paper(ax, "Najveći pad od vrha (drawdown): koliko boli put do dna")
    dds: dict[str, pd.Series] = {}
    for name, (c, col) in curves.items():
        dd = c / c.cummax() - 1
        dds[name] = dd
        ax.fill_between(dd.index, dd.values * 100, 0, color=col, alpha=0.12)
        ax.plot(
            dd.index,
            dd.values * 100,
            color=col,
            lw=1.8,
            label=name if name != "pobjednik" else f"pobjednik ({win.split('_')[0]})",
        )
    ax.set_ylabel("pad od dotadašnjeg vrha u %")
    ax.set_ylim(-60, 4)
    ax.axvline(S.curve("B0_BUYHOLD").index[0], color=RED, ls="--", lw=1.3)
    date_axis(ax)
    legend_top(ax, ncol=3)
    hold, c13 = curves["kupi i drži"][0], curves["C13C"][0]
    dd_h, dd_c = dds["kupi i drži"], dds["C13C"]
    d_h = dd_h.idxmin()
    d_c = dd_c.idxmin()
    peak_h = hold[:d_h].idxmax()
    peak_c = c13[:d_c].idxmax()
    ret_h = hold.pct_change().dropna()
    wd = ret_h.idxmin()
    n = Notes(
        ax,
        hold.index,
        [dd_h.values * 100, dd_c.values * 100, dds["pobjednik"].values * 100],
    )
    n.put(
        f"Držanje, najgore dno {day(d_h)}: {pc(dd_h.min(), 1)}. Na 1.000 EUR: vrh {eur(hold[peak_h])} ({day(peak_h)}) → dno {eur(hold[d_h])}, "
        f"dakle {eur(hold[peak_h] - hold[d_h])} manje.",
        (d_h, dd_h.min() * 100),
        width=40,
        color=HOLD_C,
        at=(0.03, 0.03),
    )
    n.put(
        f"C13C, najgore dno {day(d_c)}: {pc(dd_c.min(), 1)}. Na 1.000 EUR: vrh {eur(c13[peak_c])} → dno {eur(c13[d_c])}, pad {eur(c13[peak_c] - c13[d_c])}.",
        (d_c, dd_c.min() * 100),
        width=40,
        color=C13C_C,
        at=(0.66, 0.03),
    )
    n.put(
        f"Najgori pojedini dan za držanje: {day(wd)}, {pc(ret_h.min(), 1)}. Da je tog jutra bilo {eur(hold[:wd].iloc[-2])} u segmentu, do večeri je ostalo {eur(hold[wd])} "
        f"(gubitak {eur(hold[:wd].iloc[-2] - hold[wd])} u jednom danu).",
        (wd, float(dd_h[wd] * 100)),
        width=40,
        color=RED,
        at=(0.03, 0.33),
    )
    m = teacher(
        fig,
        "Pad od vrha je vrijednost u odnosu na najbolji dosadašnji trenutak: 2.000 EUR koji padne na 1.200 EUR je pad od 40 %. "
        "Za tebe pad nije razlog za nižu ocjenu (blagi kritičar), ali treba znati što podnosiš: sektor je u AI eri padao tvrdo i dvaput. "
        "C13C pada manje jer je većinu vremena u gotovini, a platio je to manjim rastom.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "03_pad_od_vrha.png")


# --------------------------------------------------------------------------- 4 trades
def chart_trades(S: Seg, outdir: Path) -> str:
    tr = S.trades("K1_C13C_ORIG")
    df = pd.DataFrame(tr)
    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(11.5, 6.6), gridspec_kw={"width_ratios": [3.2, 1]}, sharey=True
    )
    paper(
        ax, f"Svaka od {len(df)} C13C trgovina: koliko je trajala i koliko je donijela"
    )
    cols = {"stop": GREEN, "gap_stop": RED}
    kind = df["detail"].where(df["reason"] != "end", "end")
    win = df["return"] > 0
    ax.scatter(
        df.loc[win, "bars_held"],
        df.loc[win, "return"] * 100,
        s=26,
        color=GREEN,
        alpha=0.7,
        label="dobitak",
    )
    ax.scatter(
        df.loc[~win, "bars_held"],
        df.loc[~win, "return"] * 100,
        s=26,
        color=RED,
        alpha=0.7,
        label="gubitak",
    )
    gp = df[kind == "gap_stop"]
    ax.scatter(
        gp["bars_held"],
        gp["return"] * 100,
        s=80,
        facecolors="none",
        edgecolors=PENCIL,
        linewidths=1.2,
        label="izlaz preko noći (jaz)",
    )
    ax.axhline(0, color=PENCIL, lw=1.2)
    ax.set_xlabel("dana u poziciji (radni dani, os nije linearna)")
    ax.set_xscale("log")
    ax.set_ylabel("povrat trgovine u %")
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    legend_top(ax, ncol=3)
    best = df.loc[df["return"].idxmax()]
    worst = df.loc[df["return"].idxmin()]
    ax2.hist(
        df["return"] * 100,
        bins=24,
        orientation="horizontal",
        color=INK,
        alpha=0.55,
        edgecolor=PAPER,
    )
    ax2.axhline(0, color=PENCIL, lw=1.2)
    ax2.set_facecolor(PAPER)
    ax2.grid(True, color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    ax2.set_title("koliko ih je gdje", loc="left", fontsize=11, color=INK)
    n_win = int(win.sum())
    avg_w, avg_l = df.loc[win, "return"].mean(), df.loc[~win, "return"].mean()
    ax.set_xlim(0.8, 260)
    ax.set_ylim(df["return"].min() * 100 - 8, df["return"].max() * 100 * 1.12)
    n = Notes(ax, df["bars_held"], [df["return"] * 100])
    n.put(
        f"Najbolja: {best['ticker']}, {day(best['entry_date'])} → {day(best['exit_date'])}, {pc(best['return'], 0)} u {int(best['bars_held'])} radnih dana. "
        f"Iz 1.000 EUR bi postalo {eur(1000 * (1 + best['return']))}.",
        (best["bars_held"], best["return"] * 100),
        width=36,
        color=GREEN,
        at=(0.04, 0.78),
    )
    n.put(
        f"Najgora: {worst['ticker']}, {day(worst['entry_date'])} → {day(worst['exit_date'])}, {pc(worst['return'], 0)} u {int(worst['bars_held'])} radnih dana. "
        f"Iz 1.000 EUR ostalo bi {eur(1000 * (1 + worst['return']))}.",
        (worst["bars_held"], worst["return"] * 100),
        width=36,
        color=RED,
        at=(0.04, 0.52),
    )
    n.put(
        f"{n_win} od {len(df)} trgovina ({n_win / len(df) * 100:.0f} %) donosi dobitak; prosječni dobitak {pc(avg_w, 1)}, prosječni gubitak {pc(avg_l, 1)}. "
        f"Gubitnika je više, ali su manji.",
        (3, float(avg_l * 100)),
        width=58,
        color=PENCIL,
        arrow=False,
        at=(0.50, 0.02),
    )
    m = teacher(
        fig,
        f"Svaka točka je jedna kupnja do prodaje. Stop od 10 % reže gubitke na oko -10 % (krugovi su dani kad je dionica otvorila ispod stopa pa je gubitak veći: {len(gp)} takvih od {len(df)}), "
        "a dobici se ne režu pa mogu narasti. Primjer: 100 EUR u svakoj od deset dionica, jedna dobra trgovina od +60 % nadoknadi nekoliko stopa od -10 %. "
        "Trgovine različitih dionica često se preklapaju jer sektor pada i raste skupa.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "04_trgovine.png")


# --------------------------------------------------------------------------- 5 scoreboard
LABEL = {
    "B0_BUYHOLD": "kupi i drži",
    "K1_C13C_ORIG": "K1 C13C",
    "K2_SMA200_TREND": "K2 iznad SMA200",
    "K3_DONCHIAN_55_20": "K3 proboj 55/20",
    "K4_TSMOM_126": "K4 trend 126 dana",
    "K5_SUPPORT_RESISTANCE": "K5 potpora/otpor",
    "K5B_SR_BREAKOUT_RETEST": "K5B proboj + povrat",
    "K6_MOMENTUM_CS": "K6 rotacija najjačih",
    "K7_C13C_PLUS_TREND_REENTRY": "K7 C13C + ponovni ulaz",
}


def chart_scoreboard(S: Seg, outdir: Path) -> str:
    tb = S.analysis["segment_portfolio_table_ai_era"]["contenders"]
    win = S.analysis["winner"]["winner"]
    ids = sorted(tb, key=lambda k: tb[k]["total_return"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.4), sharey=True)

    def col(k: str) -> str:
        return (
            HOLD_C
            if k == "B0_BUYHOLD"
            else WIN_C
            if k == win
            else C13C_C
            if k == "K1_C13C_ORIG"
            else OTHER_C
        )

    ylab = [LABEL[k] for k in ids]
    paper(a1, "Prinos u AI eri")
    a1.barh(
        ylab,
        [tb[k]["total_return"] * 100 for k in ids],
        color=[col(k) for k in ids],
        alpha=0.8,
    )
    for y, k in enumerate(ids):
        a1.text(
            tb[k]["total_return"] * 100 + 6,
            y,
            f"{tb[k]['total_return'] * 100:.0f} %".replace(".", ","),
            va="center",
            fontsize=10.5,
        )
    a1.axvline(tb["B0_BUYHOLD"]["total_return"] * 100, color=HOLD_C, ls="--", lw=1.5)
    a1.set_xlabel("ukupni prinos 2023.–2026. u %")
    a1.set_xlim(0, tb["B0_BUYHOLD"]["total_return"] * 100 * 1.22)
    paper(a2, "Sharpe u AI eri")
    a2.barh(
        ylab, [tb[k]["sharpe"] for k in ids], color=[col(k) for k in ids], alpha=0.8
    )
    for y, k in enumerate(ids):
        a2.text(
            tb[k]["sharpe"] + 0.02,
            y,
            f"{tb[k]['sharpe']:.2f}".replace(".", ","),
            va="center",
            fontsize=10.5,
        )
    a2.axvline(tb["B0_BUYHOLD"]["sharpe"], color=HOLD_C, ls="--", lw=1.5)
    a2.set_xlabel("Sharpe (veći je bolji)")
    a2.set_xlim(0, max(tb[k]["sharpe"] for k in ids) * 1.22)
    a2.xaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.1f}".replace(".", ","))
    )
    hold_r, hold_s = tb["B0_BUYHOLD"]["total_return"], tb["B0_BUYHOLD"]["sharpe"]
    a1.annotate(
        wrap(
            f"Isprekidana crta = držanje {hold_r * 100:.0f} %. Nijedno pravilo ne dolazi do nje.".replace(
                ".", ","
            ),
            28,
        ),
        xy=(hold_r * 100, 7.2),
        xytext=(0.36, 0.05),
        textcoords="axes fraction",
        fontsize=FONT,
        color=HOLD_C,
        ha="left",
        arrowprops=dict(
            arrowstyle="->", color=HOLD_C, lw=1.4, connectionstyle="arc3,rad=0.25"
        ),
    )
    a2.annotate(
        wrap(
            f"Pobjednik po Sharpeu: {LABEL[win]} ({tb[win]['sharpe']:.2f}) uz držanje {hold_s:.2f}. Razlike među prva četiri su male.".replace(
                ".", ","
            ),
            30,
        ),
        xy=(tb[win]["sharpe"], ids.index(win)),
        xytext=(0.60, 0.04),
        textcoords="axes fraction",
        fontsize=FONT,
        color=WIN_C,
        ha="left",
        arrowprops=dict(
            arrowstyle="->", color=WIN_C, lw=1.4, connectionstyle="arc3,rad=-0.25"
        ),
    )
    m = teacher(
        fig,
        f"Sharpe je prinos u odnosu na treskanje: veći je bolji, a oko 1 je dobro. Sive: držanje, zelena: pobjednik po Sharpeu, plava: C13C, žute: ostala pravila. "
        f"Primjer: držanjem je 1.000 EUR postalo {eur(tb['B0_BUYHOLD']['end_value_per_1000_eur'])}, pobjednikom {eur(tb[win]['end_value_per_1000_eur'])}, C13C-om {eur(tb['K1_C13C_ORIG']['end_value_per_1000_eur'])}. "
        "Pokrenuto je 9 pravila, pa je najbolje djelomično i sreća; razlika među vodećima nije dokaz.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "05_ljestvica.png")


# --------------------------------------------------------------------------- 6 cost robustness
def chart_costs(S: Seg, outdir: Path) -> str:
    tb = S.analysis["segment_portfolio_table_ai_era"]["contenders"]
    ids = [k for k in tb if k != "B0_BUYHOLD"]
    ids = sorted(ids, key=lambda k: -tb[k]["trades"])
    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(11.5, 6.3), gridspec_kw={"width_ratios": [2.1, 1.3]}
    )
    paper(a1, "Završna vrijednost od 1.000 EUR uz 1x, 2x i 3x troškove")
    x = np.arange(len(ids))
    w = 0.27
    for j, (key, lab, c) in enumerate(
        [
            ("total_return", "1x (2,5 bps po strani)", "#4f6fd8"),
            ("total_return_cost_2x", "2x (5 bps)", "#2a47a0"),
            ("total_return_cost_3x", "3x (7,5 bps)", "#162a66"),
        ]
    ):
        a1.bar(
            x + (j - 1) * w,
            [(1 + tb[k][key]) * 1000 for k in ids],
            w,
            color=c,
            label=lab,
        )
    a1.set_xticks(x)
    a1.set_xticklabels([wrap(LABEL[k], 11) for k in ids], fontsize=9, rotation=0)
    a1.set_ylabel("EUR od 1.000 EUR")
    a1.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", "."))
    )
    hold_end = (1 + S.table("B0_BUYHOLD")["total_return"]) * 1000
    a1.axhline(hold_end, color=HOLD_C, ls="--", lw=1.4)
    a1.text(
        len(ids) - 0.5,
        hold_end * 1.01,
        "kupi i drži",
        color=HOLD_C,
        fontsize=10,
        ha="right",
    )
    legend_top(a1, ncol=3)
    paper(a2, "Što 3x trošak oduzme (broj trgovina)")
    loss = [
        ((1 + tb[k]["total_return"]) - (1 + tb[k]["total_return_cost_3x"])) * 1000
        for k in ids
    ]
    a2.barh(
        [f"{LABEL[k]} ({tb[k]['trades']})" for k in ids],
        loss,
        color=[C13C_C if "C13C" in k else OTHER_C for k in ids],
        alpha=0.85,
    )
    for y, (k, l) in enumerate(zip(ids, loss)):
        a2.text(
            l + max(loss) * 0.02,
            y,
            eur(l),
            va="center",
            fontsize=10,
        )
    a2.set_xlim(0, max(loss) * 1.35)
    a2.set_xlabel("EUR manje, 1x → 3x")
    k1 = "K1_C13C_ORIG"
    a1.annotate(
        wrap(
            f"C13C: 1x {eur((1 + tb[k1]['total_return']) * 1000)}, 3x {eur((1 + tb[k1]['total_return_cost_3x']) * 1000)}. Pravilo ostaje pozitivno i uz trostruke troškove.",
            34,
        ),
        xy=(ids.index(k1), (1 + tb[k1]["total_return"]) * 1000),
        xytext=(0.02, 0.60),
        textcoords="axes fraction",
        fontsize=FONT,
        color=INK,
        ha="left",
        arrowprops=dict(
            arrowstyle="->", color=INK, lw=1.4, connectionstyle="arc3,rad=0.25"
        ),
    )
    a2.annotate(
        wrap(
            "Više trgovina znači veći račun za trošak. Zato C13C i K7 plaćaju najviše.",
            26,
        ),
        xy=(loss[0], 0),
        xytext=(0.50, 0.62),
        textcoords="axes fraction",
        fontsize=FONT,
        color=RED,
        ha="left",
        arrowprops=dict(
            arrowstyle="->", color=RED, lw=1.4, connectionstyle="arc3,rad=-0.25"
        ),
    )
    m = teacher(
        fig,
        "Trošak je u simulaciji 2,5 bps po strani (1 bps = 0,01 %): na kupnju od 1.000 EUR to je 0,25 EUR, i toliko pri prodaji. Test 2x i 3x pita preživi li pravilo lošije izvršenje. "
        "Što nije u računu: minimalna provizija po nalogu kod brokera (nepotvrđeno za Petrov tarif), tečaj EUR/USD i porez. Pravila s mnogo malih trgovina zato su ovdje prikazana povoljnije nego u stvarnosti.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "06_troskovi.png")


# --------------------------------------------------------------------------- 7 key lesson: the best days
def held_whole_day(trades: list[dict[str, Any]], d: pd.Timestamp) -> bool:
    return any(
        pd.Timestamp(t["entry_date"]) < d < pd.Timestamp(t["exit_date"]) for t in trades
    )


def chart_lesson(S: Seg, outdir: Path) -> tuple[str, dict[str, Any]]:
    win = S.analysis["winner"]["winner"]
    rows = []
    for tk in S.tickers:
        ai = S.profile["companies"][tk]["stats"]["ai_era"]
        days = [pd.Timestamp(d) for d in ai["top10_best_days"]["dates"]]
        k1 = S.ticker_trades(tk, "K1_C13C_ORIG")
        k4 = S.ticker_trades(tk, win)
        rows.append(
            dict(
                tk=tk,
                total=ai["total_return_pct"],
                wo=ai["top10_best_days"]["total_return_without_best10_pct"],
                share=ai["top10_best_days"]["sum_logret_share_of_total_pct"],
                k1=sum(held_whole_day(k1, d) for d in days),
                k4=sum(held_whole_day(k4, d) for d in days),
                n=len(days),
            )
        )
    df = pd.DataFrame(rows)
    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(11.5, 6.4), gridspec_kw={"width_ratios": [1.5, 1]}
    )
    paper(a1, "Prinos s 10 najboljih dana i bez njih")
    y = np.arange(len(df))
    a1.barh(y - 0.2, df["total"], 0.38, color=HOLD_C, label="držanje, svih dana")
    a1.barh(
        y + 0.2,
        df["wo"],
        0.38,
        color=RED,
        alpha=0.75,
        label="držanje bez 10 najboljih dana",
    )
    a1.set_yticks(y)
    a1.set_yticklabels(df["tk"])
    a1.invert_yaxis()
    a1.axvline(0, color=PENCIL, lw=1.2)
    a1.set_xlabel("prinos 2023.–2026. u % (zatvaranje do zatvaranja)")
    legend_top(a1, ncol=2)
    for yy, r in df.iterrows():
        a1.text(
            max(r["total"], r["wo"], 0) + 12,
            yy,
            f"{r['share']:.0f} %".replace(".", ","),
            va="center",
            fontsize=9.5,
            color=INK,
        )
    a1.set_xlim(min(df["wo"].min() * 1.3, -30), df["total"].max() * 1.7)
    paper(a2, "Koliko od tih 10 dana je pravilo bilo unutra")
    a2.barh(y - 0.2, df["k1"], 0.38, color=C13C_C, label="C13C")
    a2.barh(
        y + 0.2, df["k4"], 0.38, color=WIN_C, label=f"pobjednik ({win.split('_')[0]})"
    )
    a2.set_yticks(y)
    a2.set_yticklabels(df["tk"])
    a2.invert_yaxis()
    a2.set_xlim(0, 15)
    a2.set_xlabel("od 10 najboljih dana, cijeli dan u poziciji")
    legend_top(a2, ncol=2)
    k1_all, k4_all = int(df["k1"].sum()), int(df["k4"].sum())
    tot = int(df["n"].sum())
    ent = df.loc[df["tk"] == "ENTG"].iloc[0]
    amat = df.iloc[0]
    a1.text(
        0.60,
        0.52,
        wrap(
            f"Brojka desno od stupca je udio prinosa koji nose 10 najboljih dana. ENTG: {ent['share']:.0f} %, pa bez tih dana ostaje {ent['wo']:.0f} % umjesto {ent['total']:.0f} %.",
            26,
        ),
        transform=a1.transAxes,
        fontsize=FONT,
        color=RED,
        va="bottom",
    )
    a2.text(
        0.62,
        0.30,
        wrap(
            f"Ukupno C13C: {k1_all} od {tot} najboljih dana, {LABEL[win]}: {k4_all} od {tot}. Tko je vani, ne dobije te dane.",
            22,
        ),
        transform=a2.transAxes,
        fontsize=FONT,
        color=PENCIL,
        va="bottom",
    )
    m = teacher(
        fig,
        f"Pouka segmenta: rast ovih dionica dolazi u rijetkim, snažnim danima. Primjer: 1.000 EUR u {amat['tk']} od 3. 1. 2023. do 5. 10. 2026. (zatvaranje do zatvaranja) postaje "
        f"{eur(1000 * (1 + amat['total'] / 100))}, a bez samo 10 najboljih dana ({amat['share']:.0f} % cijelog prinosa) samo {eur(1000 * (1 + amat['wo'] / 100))}. "
        "Pravilo koje je oko pola vremena vani te dane često propusti. "
        "Dan se računa kao 'unutra' samo ako je pozicija držana cijeli dan (ulaz prije njega, izlaz poslije njega).",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "07_najbolji_dani.png"), dict(
        k1=k1_all, k4=k4_all, total=tot, rows=rows
    )


# --------------------------------------------------------------------------- behaviour charts
def chart_character(S: Seg, outdir: Path) -> str:
    tk = S.tickers
    ai = [S.profile["companies"][t]["stats"]["ai_era"] for t in tk]
    pre = [S.profile["companies"][t]["stats"]["pre_2023"] for t in tk]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 5.6))
    paper(a1, "Treskanje: godišnja volatilnost")
    x = np.arange(len(tk))
    a1.bar(
        x - 0.2,
        [p["ann_vol_pct"] for p in pre],
        0.38,
        color="#9aa3b5",
        label="prije 2023.",
    )
    a1.bar(x + 0.2, [a["ann_vol_pct"] for a in ai], 0.38, color=INK, label="AI era")
    a1.set_xticks(x)
    a1.set_xticklabels(tk, rotation=45)
    a1.set_ylabel("% godišnje")
    a1.set_ylim(0, 125)
    legend_top(a1, ncol=2)
    vols = [a["ann_vol_pct"] for a in ai]
    hi = int(np.argmax(vols))
    a1.annotate(
        wrap(
            f"{tk[hi]} najviše divlja: {vols[hi]:.0f} % godišnje. Na 1.000 EUR to je tipičan raspon od oko {vols[hi] * 10:.0f} EUR gore ili dolje u godini.".replace(
                ".", ","
            ),
            30,
        ),
        xy=(hi + 0.2, vols[hi]),
        xytext=(0.03, 0.70),
        textcoords="axes fraction",
        fontsize=FONT,
        color=RED,
        arrowprops=dict(
            arrowstyle="->", color=RED, lw=1.4, connectionstyle="arc3,rad=-0.25"
        ),
    )
    paper(a2, "Koliko slijede poluvodiče (SMH)")
    a2.bar(x, [a["beta_smh"] for a in ai], 0.55, color=GREEN, alpha=0.75)
    for xi, a in zip(x, ai):
        a2.text(
            xi,
            a["beta_smh"] + 0.02,
            f"{a['corr_smh']:.2f}".replace(".", ","),
            ha="center",
            fontsize=9.5,
        )
    a2.axhline(1, color=PENCIL, ls="--", lw=1.3)
    a2.set_xticks(x)
    a2.set_xticklabels(tk, rotation=45)
    a2.set_ylabel("beta prema SMH")
    a2.set_ylim(0, max(a["beta_smh"] for a in ai) * 1.9)
    bmax = int(np.argmax([a["beta_smh"] for a in ai]))
    a2.annotate(
        wrap(
            f"Beta 1 = pomiče se jednako kao SMH. {tk[bmax]} ima {ai[bmax]['beta_smh']:.2f}: kad SMH padne 10 %, ona u prosjeku padne oko {ai[bmax]['beta_smh'] * 10:.1f} %. Broj iznad stupca je korelacija.".replace(
                ".", ","
            ),
            34,
        ),
        xy=(bmax, ai[bmax]["beta_smh"]),
        xytext=(0.03, 0.66),
        textcoords="axes fraction",
        fontsize=FONT,
        color=PENCIL,
        arrowprops=dict(
            arrowstyle="->", color=PENCIL, lw=1.4, connectionstyle="arc3,rad=0.25"
        ),
    )
    m = teacher(
        fig,
        "Sve su to pojačana verzija cijelog poluvodičkog tržišta, a ne zasebne oklade. Primjer: beta 1,2 znači da u danu kad indeks padne 10 %, dionica u prosjeku padne 12 %, "
        "to jest 1.000 EUR postaje 880 EUR. SMH ovdje služi samo kao mjerilo kretanja (američki ETF koji ti vjerojatno nije dostupan, nepotvrđeno), ne kao prijedlog za kupnju.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "08_karakter.png")


def chart_dip_forward(S: Seg, outdir: Path) -> str:
    tk = S.tickers
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.0), sharey=False)
    stats = {
        t: S.profile["companies"][t]["stats"]["ai_era"][
            "after_5d_drop_ge5pct_above_sma200"
        ]["thinned_events_10d_apart"]
        for t in tk
    }
    for ax, h, lab in ((a1, "fwd_5d", "5 dana"), (a2, "fwd_20d", "20 dana")):
        paper(ax, f"Prinos {lab} nakon pada, naspram običnog dana")
        x = np.arange(len(tk))
        ax.bar(
            x - 0.2,
            [stats[t][h]["uncond_mean_pct"] for t in tk],
            0.38,
            color="#9aa3b5",
            label="običan dan",
        )
        ax.bar(
            x + 0.2,
            [stats[t][h]["mean_pct"] for t in tk],
            0.38,
            color=GREEN,
            alpha=0.8,
            label="nakon pada 5 %+",
        )
        ax.axhline(0, color=PENCIL, lw=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels(tk, rotation=45)
        ax.set_ylabel(f"prosječni prinos nakon {lab} u %")
        ax.set_ylim(
            0,
            max(
                max(stats[t][h]["mean_pct"], stats[t][h]["uncond_mean_pct"]) for t in tk
            )
            * 1.75,
        )
        legend_top(ax, ncol=2)
    ev = [stats[t]["n_events"] for t in tk]
    more5 = sum(
        stats[t]["fwd_5d"]["mean_pct"] > stats[t]["fwd_5d"]["uncond_mean_pct"]
        for t in tk
    )
    more20 = sum(
        stats[t]["fwd_20d"]["mean_pct"] > stats[t]["fwd_20d"]["uncond_mean_pct"]
        for t in tk
    )
    t0 = tk[0]
    a1.annotate(
        wrap(
            f"Primjer {t0}: nakon pada od 5 % u 5 dana (iznad SMA200) {stats[t0]['n_events']} događaja, u idućih 5 dana prosječno {stats[t0]['fwd_5d']['mean_pct']:.2f} % naspram {stats[t0]['fwd_5d']['uncond_mean_pct']:.2f} % običnog dana. Na 1.000 EUR: {1000 * stats[t0]['fwd_5d']['mean_pct'] / 100:.0f} EUR naspram {1000 * stats[t0]['fwd_5d']['uncond_mean_pct'] / 100:.0f} EUR.".replace(
                ".", ","
            ),
            34,
        ),
        xy=(0.2, stats[t0]["fwd_5d"]["mean_pct"]),
        xytext=(0.30, 0.70),
        textcoords="axes fraction",
        fontsize=FONT,
        color=GREEN,
        arrowprops=dict(
            arrowstyle="->", color=GREEN, lw=1.4, connectionstyle="arc3,rad=0.25"
        ),
    )
    diff5 = np.mean(
        [
            stats[t]["fwd_5d"]["mean_pct"] - stats[t]["fwd_5d"]["uncond_mean_pct"]
            for t in tk
        ]
    )
    diff20 = np.mean(
        [
            stats[t]["fwd_20d"]["mean_pct"] - stats[t]["fwd_20d"]["uncond_mean_pct"]
            for t in tk
        ]
    )
    sig5 = sum(stats[t]["fwd_5d"].get("t_vs_uncond", 0) >= 2 for t in tk)
    sig20 = sum(stats[t]["fwd_20d"].get("t_vs_uncond", 0) >= 2 for t in tk)
    a2.text(
        0.03,
        0.97,
        wrap(
            f"Nakon pada je prinos bio veći od običnog dana kod {more5} od {len(tk)} dionica za 5 dana (u prosjeku {diff5:+.1f} postotnih bodova) i kod {more20} od {len(tk)} za 20 dana ({diff20:+.1f} boda). "
            f"Statistički uvjerljivo (t od 2 naviše) samo kod {sig5} dionica za 5 dana i {sig20} za 20 dana: slab dokaz.",
            38,
        ),
        transform=a2.transAxes,
        fontsize=FONT,
        color=RED,
        va="top",
    )
    m = teacher(
        fig,
        f"Pitanje: je li pad od 5 % u 5 dana (dok je cijena iznad dugoročnog prosjeka) dobra prilika za kupnju? Događaji su prorijeđeni na barem 10 dana razmaka (broj po dionici: {min(ev)} do {max(ev)}). "
        "Dionice padaju istih dana, pa je neovisnih događaja manje nego što izgleda, a AI era je snažan rast. Ovo je opis ponašanja, ne obećanje.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "09_nakon_pada.png")


def chart_seasonality(S: Seg, outdir: Path) -> str:
    tk = S.tickers
    mat = np.array(
        [
            [
                S.profile["companies"][t]["stats"]["ai_era"]["seasonality"][str(m)][
                    "mean_pct"
                ]
                for m in range(1, 13)
            ]
            for t in tk
        ]
    )
    fig, ax = plt.subplots(figsize=(11.5, 6.0))
    paper(ax, "Sezonalnost: prosječni mjesečni prinos u AI eri (u %)")
    lim = np.abs(mat).max()
    im = ax.imshow(mat, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.grid(False)
    ax.set_xticks(range(12))
    ax.set_xticklabels(
        [
            "sij",
            "velj",
            "ožu",
            "tra",
            "svi",
            "lip",
            "srp",
            "kol",
            "ruj",
            "lis",
            "stu",
            "pro",
        ]
    )
    ax.set_yticks(range(len(tk)))
    ax.set_yticklabels(tk)
    for i in range(len(tk)):
        for j in range(12):
            ax.text(
                j,
                i,
                f"{int(round(mat[i, j]))}",
                ha="center",
                va="center",
                fontsize=9.5,
                color="white" if abs(mat[i, j]) > lim * 0.7 else PENCIL,
            )
    cm = mat.mean(axis=0)
    best, worst = int(np.argmax(cm)), int(np.argmin(cm))
    names = [
        "siječanj",
        "veljača",
        "ožujak",
        "travanj",
        "svibanj",
        "lipanj",
        "srpanj",
        "kolovoz",
        "rujan",
        "listopad",
        "studeni",
        "prosinac",
    ]
    ax.annotate(
        wrap(
            f"Prosjek svih 10 dionica: najbolji mjesec {names[best]} ({cm[best]:.1f} %), najlošiji {names[worst]} ({cm[worst]:.1f} %). Ali svaka ćelija je samo 3 do 4 godine!".replace(
                ".", ","
            ),
            34,
        ),
        xy=(worst, len(tk) - 0.5),
        xytext=(0.02, -0.14),
        textcoords="axes fraction",
        va="top",
        fontsize=FONT,
        color=RED,
        annotation_clip=False,
        arrowprops=dict(
            arrowstyle="->", color=RED, lw=1.4, connectionstyle="arc3,rad=0.25"
        ),
    )
    ax.set_ylim(len(tk) - 0.5, -0.5)
    m = teacher(
        fig,
        "Svaki kvadratić je prosječni prinos te dionice u tom kalendarskom mjesecu, zelenije je bolje. Primjer: 1.000 EUR u mjesecu s prosjekom +10 % postaje 1.100 EUR. "
        "Ali u AI eri svaki mjesec ima samo 3 do 4 opažanja po dionici (4 godine), pa jedna godina mijenja sve. Ne koristi ovo za odluke; služi samo da vidiš da obrasci nisu stabilni.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "10_sezonalnost.png")


def chart_drawdown_anatomy(S: Seg, outdir: Path, tickers: list[str]) -> str:
    fig, axes = plt.subplots(len(tickers), 1, figsize=(11.5, 3.9 * len(tickers)))
    for ax, tk in zip(np.atleast_1d(axes), tickers):
        df = load_close_frame(tk)
        px = df["close"][(df.index >= "2023-01-03") & (df.index <= "2026-10-05")]
        v = px / px.iloc[0] * 1000
        dds = S.profile["companies"][tk]["stats"]["ai_era"]["drawdowns"][:2]
        paper(ax, f"{tk}: anatomija dva najveća pada (1.000 EUR kupljeno 3. 1. 2023.)")
        ax.plot(v.index, v.values, color=INK, lw=1.5)
        ax.set_ylabel("EUR")
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", "."))
        )
        date_axis(ax)
        ax.set_ylim(0, v.max() * 1.18)
        notes = Notes(ax, v.index, [v.values])
        for k, d in enumerate(dds):
            s, b = pd.Timestamp(d["start"]), pd.Timestamp(d["bottom"])
            r = pd.Timestamp(d["recovery"]) if d["recovery"] else v.index[-1]
            ax.axvspan(s, b, color="#ffe3de", alpha=0.7, lw=0)
            if d["recovery"]:
                ax.axvspan(b, r, color="#fff4d6", alpha=0.7, lw=0)
            ax.scatter([s, b], [v[s], v[b]], color=[GREEN, RED], zorder=5, s=50)
            depth = v[b] / v[s] - 1
            assert abs(depth * 100 - d["depth_pct"]) < 0.15, (tk, depth, d)
            txt = (
                f"Pad {k + 1}: vrh {day(s)} ({eur(v[s])}) → dno {day(b)} ({eur(v[b])}), {pc(depth, 1)}. "
                + (
                    f"Oporavak do starog vrha: {day(r)} ({(r - b).days} dana od dna)."
                    if d["recovery"]
                    else "Još nije oporavljeno do 5. 10. 2026."
                )
            )
            notes.put(
                txt,
                (b, float(v[b])),
                width=40,
                color=RED if k == 0 else PENCIL,
                at=(0.04, 0.58) if k == 0 else (0.44, 0.60),
            )
        ax.set_xlim(v.index[0], v.index[-1] + pd.Timedelta(days=30))
    m = teacher(
        fig,
        "Crveno polje je put od vrha do dna, žuto polje put oporavka do starog vrha. Primjer: 1.000 EUR u vrhu pada za polovicu na 500 EUR, a da bi se vratio na 1.000 EUR mora porasti 100 %, ne 50 %. "
        "Zato su dugi padovi opasniji nego što se čini. U ovom segmentu je većina dionica imala najveći pad u gotovo istom razdoblju (srpanj 2024. do travanj 2025.), pa raspršenost među njima nije pomogla.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "11_anatomija_pada.png")


def sr_events_full(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Same first-touch logic as ``profile_stats.sr_events`` (real pivots only) but keeps the level and the pivot."""
    c, lo, hi = df["close"].to_numpy(), df["low"].to_numpy(), df["high"].to_numpy()
    n = len(c)
    plows, phighs = pivots(lo, hi)
    ev: list[dict[str, Any]] = []
    for kind, plist in (("support", plows), ("resistance", phighs)):
        for p in plist:
            lvl = lo[p] if kind == "support" else hi[p]
            for t in range(p + PIVOT_K + 1, min(n - SR_LOOKAHEAD - 1, p + SR_MAX_AGE)):
                if kind == "support":
                    if c[t] < lvl * (1 - SR_BAND):
                        break
                    if lo[t] <= lvl * (1 + SR_BAND) and c[t - 1] > lvl * (1 + SR_BAND):
                        fut = c[t : t + SR_LOOKAHEAD + 1]
                        ev.append(
                            dict(
                                kind=kind,
                                p=p,
                                t=t,
                                lvl=float(lvl),
                                broke=bool((fut < lvl * (1 - SR_BAND)).any()),
                            )
                        )
                        break
                else:
                    if c[t] > lvl * (1 + SR_BAND):
                        break
                    if hi[t] >= lvl * (1 - SR_BAND) and c[t - 1] < lvl * (1 - SR_BAND):
                        fut = c[t : t + SR_LOOKAHEAD + 1]
                        ev.append(
                            dict(
                                kind=kind,
                                p=p,
                                t=t,
                                lvl=float(lvl),
                                broke=bool((fut > lvl * (1 + SR_BAND)).any()),
                            )
                        )
                        break
    return ev


def chart_sr_rates(S: Seg, outdir: Path) -> str:
    tk = S.tickers
    sr = {
        t: S.profile["companies"][t]["stats"]["ai_era"]["support_resistance"]
        for t in tk
    }
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 5.8))
    for ax, kind, lab in (
        (a1, "support", "potpora (prijašnje dno)"),
        (a2, "resistance", "otpor (prijašnji vrh)"),
    ):
        paper(ax, f"Koliko često je {lab} izdržala")
        x = np.arange(len(tk))
        real = [sr[t]["real_pivots"][kind]["hold_pct"] for t in tk]
        fake = [sr[t]["placebo_arbitrary_levels"][kind]["hold_pct"] for t in tk]
        ax.bar(x - 0.2, fake, 0.38, color="#9aa3b5", label="slučajne razine")
        ax.bar(x + 0.2, real, 0.38, color=INK, label="stvarna dna/vrhovi")
        ax.axhline(50, color=PENCIL, ls="--", lw=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels(tk, rotation=45)
        ax.set_ylim(0, 135)
        ax.set_yticks([0, 20, 40, 60, 80, 100])
        ax.set_ylabel("% dodira u kojima je razina izdržala")
        legend_top(ax, ncol=2)
    better_s = sum(
        sr[t]["real_pivots"]["support"]["hold_pct"]
        > sr[t]["placebo_arbitrary_levels"]["support"]["hold_pct"]
        for t in tk
    )
    better_r = sum(
        sr[t]["real_pivots"]["resistance"]["hold_pct"]
        > sr[t]["placebo_arbitrary_levels"]["resistance"]["hold_pct"]
        for t in tk
    )
    a1.text(
        0.03,
        0.76,
        wrap(
            f"Stvarna dna su izdržala bolje od slučajnih razina samo kod {better_s} od {len(tk)} dionica.",
            34,
        ),
        transform=a1.transAxes,
        fontsize=FONT,
        color=RED,
        va="bottom",
    )
    a2.text(
        0.03,
        0.76,
        wrap(
            f"Stvarni vrhovi: bolje od slučajnih kod {better_r} od {len(tk)}. Dakle nema jasne magije u 'crtama' na grafu.",
            34,
        ),
        transform=a2.transAxes,
        fontsize=FONT,
        color=RED,
        va="bottom",
    )
    m = teacher(
        fig,
        "Potpora je razina na kojoj se cijena prošli put okrenula prema gore, otpor je ona na kojoj se okrenula prema dolje. 'Izdržala' znači da u idućih 5 dana zatvaranje nije probilo razinu za više od 1,5 %. "
        "Kontrola su proizvoljne razine pomaknute za 7 dana: ako stvarne crte nisu bolje od njih, nisu ništa posebno. Primjer: 'izdržala 60 %' znači da od 10 dodira 6 puta cijena nije propala.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "12_potpora_otpor_stope.png")


def chart_sr_example(
    S: Seg, outdir: Path, tk: str = "AMAT"
) -> tuple[str, dict[str, Any]]:
    df = load_close_frame(tk)
    df = df[df.index <= "2026-10-05"]
    ev = [e for e in sr_events_full(df) if df.index[e["t"]] >= AI_START]
    # consistency with the profile (same events, same counts)
    prof = S.profile["companies"][tk]["stats"]["ai_era"]["support_resistance"][
        "real_pivots"
    ]
    ns = sum(e["kind"] == "support" for e in ev)
    nr = sum(e["kind"] == "resistance" for e in ev)
    assert (
        ns == prof["support"]["n_touches"] and nr == prof["resistance"]["n_touches"]
    ), (ns, nr, prof)
    c_all = df["close"].to_numpy()

    def fwd5(e: dict[str, Any]) -> float:
        return float(c_all[e["t"] + SR_LOOKAHEAD] / c_all[e["t"]] - 1)

    # clear-cut examples: a support that held and then rose 5 %+, and one that broke and fell 4 %+
    held = [
        e for e in ev if e["kind"] == "support" and not e["broke"] and fwd5(e) >= 0.05
    ]
    broke = [
        e for e in ev if e["kind"] == "support" and e["broke"] and fwd5(e) <= -0.04
    ]
    best: tuple[int, dict[str, Any], dict[str, Any]] | None = None
    for a in held:
        for b in broke:
            gap = abs(a["t"] - b["t"])
            if gap <= 110 and (best is None or gap < best[0]):
                best = (gap, a, b)
    assert best is not None
    _, a, b = best
    lo_i = max(0, min(a["p"], b["p"]) - 8)
    hi_i = min(len(df) - 1, max(a["t"], b["t"]) + 28)
    w = df.iloc[lo_i : hi_i + 1]
    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    paper(ax, f"{tk}: primjeri dodira potpore (jedan je izdržao, jedan nije)")
    ax.plot(w.index, w["close"], color=INK, lw=1.6, label="cijena zatvaranja")
    ax.plot(w.index, w["low"], color="#9aa3b5", lw=0.8, label="najniža cijena dana")
    out: dict[str, Any] = {}
    for e, col, tag in ((a, GREEN, "izdržala"), (b, RED, "probijena")):
        p, t = e["p"], e["t"]
        ax.hlines(
            e["lvl"],
            df.index[p],
            df.index[min(t + SR_LOOKAHEAD, len(df) - 1)],
            color=col,
            lw=2.0,
            ls="-",
        )
        ax.hlines(
            [e["lvl"] * (1 - SR_BAND), e["lvl"] * (1 + SR_BAND)],
            df.index[t],
            df.index[min(t + SR_LOOKAHEAD, len(df) - 1)],
            color=col,
            lw=0.8,
            ls=":",
        )
        ax.scatter(
            [df.index[p]], [df["low"].iloc[p]], marker="o", s=60, color=col, zorder=5
        )
        circle(ax, df.index[t], float(df["low"].iloc[t]), color=col, size=600)
        out[tag] = dict(
            pivot=str(df.index[p].date()),
            touch=str(df.index[t].date()),
            level=e["lvl"],
            close5=float(df["close"].iloc[t + SR_LOOKAHEAD]),
            touch_close=float(df["close"].iloc[t]),
        )
    ax.set_ylim(w["low"].min() * 0.74, w["close"].max() * 1.22)
    ax.set_xlim(w.index[0], w.index[-1] + pd.Timedelta(days=4))
    ax.set_ylabel("cijena u USD")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y."))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
    legend_top(ax, ncol=2)
    n = Notes(ax, w.index, [w["close"].values, w["low"].values])
    for e, col, tag in ((a, GREEN, "izdržala"), (b, RED, "probijena")):
        p, t = e["p"], e["t"]
        lvl = e["lvl"]
        c5 = float(df["close"].iloc[t + SR_LOOKAHEAD])
        if tag == "izdržala":
            msg = (
                f"Potpora izdržala: dno od {day(df.index[p])} na {lvl:.2f} USD. Dodir {day(df.index[t])}: nijedno zatvaranje u idućih 5 dana nije palo ispod {lvl * (1 - SR_BAND):.2f}. "
                f"1.000 EUR kupljeno na zatvaranju dodira vrijedi nakon 5 dana {1000 * c5 / float(df['close'].iloc[t]):.0f} EUR."
            )
        else:
            msg = (
                f"Potpora probijena: dno od {day(df.index[p])} na {lvl:.2f} USD. Dodir {day(df.index[t])}: zatvaranje je palo ispod {lvl * (1 - SR_BAND):.2f}. "
                f"1.000 EUR kupljeno na zatvaranju dodira vrijedi nakon 5 dana {1000 * c5 / float(df['close'].iloc[t]):.0f} EUR."
            )
        n.put(
            msg,
            (df.index[t], float(df["low"].iloc[t])),
            width=40,
            color=col,
            at=(0.03, 0.70) if tag == "probijena" else (0.46, 0.03),
        )
    m = teacher(
        fig,
        "Puni kružić je dno koje postaje potpora, vodoravna crta je ta razina, a veliki prsten je dan kad se cijena prvi put vratila do nje. Točkaste crte su pojas od 1,5 %. "
        "Razina se smije koristiti tek 5 dana nakon dna jer se tek tada zna da je dno bilo dno (bez gledanja u budućnost). Dva primjera nisu dokaz: pogledaj prethodni graf za statistiku.",
    )
    fig.tight_layout(rect=(0, m, 1, 1))
    return save(fig, outdir / "13_potpora_primjer.png"), out


# --------------------------------------------------------------------------- driver
def make_all(segment: str = "equipment") -> dict[str, Any]:
    S = Seg(segment)
    out = S.dir
    info: dict[str, Any] = {}
    info["price"] = chart_price(S, out, ["AMAT", "LRCX", "KLAC"])
    info["equity"] = chart_equity(S, out)
    info["drawdown"] = chart_drawdown(S, out)
    info["trades"] = chart_trades(S, out)
    info["scoreboard"] = chart_scoreboard(S, out)
    info["costs"] = chart_costs(S, out)
    info["lesson"], info["lesson_numbers"] = chart_lesson(S, out)
    info["character"] = chart_character(S, out)
    info["dip"] = chart_dip_forward(S, out)
    info["season"] = chart_seasonality(S, out)
    info["anatomy"] = chart_drawdown_anatomy(S, out, ["AMAT", "ONTO", "ACMR"])
    info["sr_rates"] = chart_sr_rates(S, out)
    info["sr_example"], info["sr_numbers"] = chart_sr_example(S, out)
    info["checks"] = getattr(S, "_checks", [])
    (out / "charts_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=1, default=str)
    )
    return info


if __name__ == "__main__":
    import sys

    print(
        json.dumps(
            make_all(sys.argv[1] if len(sys.argv) > 1 else "equipment"),
            ensure_ascii=False,
            indent=1,
            default=str,
        )
    )
