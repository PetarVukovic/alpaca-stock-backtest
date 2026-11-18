"""Shared helpers for the MASTER_20261014 teaching charts (notebook style, Croatian notes).

Research only: nothing here places orders or writes to the ledger. Charts are drawn from the real CSVs in
``data/ohlcv`` and from engine runs of ``lab.aichain.swing`` (read-only re-runs, verified equal to ``summary.json``).
The look reuses the colour constants and sketch helper of ``lab.top10.charts`` (imported, not modified).
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from PIL import Image

from lab.top10.charts import GREEN, GRID, INK, PAPER, PENCIL, RED, sketch

ROOT = Path(__file__).resolve().parents[2]
AICHAIN = ROOT / "reports" / "research" / "AICHAIN_20261014"
SWING = AICHAIN / "swing"
OUT = ROOT / "reports" / "research" / "MASTER_20261014" / "charts"
AI_ERA = pd.Timestamp("2023-01-01")
WIDTH_IN = 14.0  # 14 in x 100 dpi = 1400 px
DPI = 100
ORANGE = "#d9822b"
GREY = "#6b7280"
LIGHT = "#9ca3af"
WIN = "#17803d"
LOSS = "#c2321f"

plt.rcParams.update(
    {
        "font.family": ["Noteworthy", "Bradley Hand", "Comic Sans MS", "DejaVu Sans"],
        "font.size": 13,
        "axes.edgecolor": PENCIL,
        "text.color": PENCIL,
        "axes.labelcolor": PENCIL,
        "xtick.color": PENCIL,
        "ytick.color": PENCIL,
        "axes.unicode_minus": False,
    }
)

CAPTIONS: dict[str, dict[str, Any]] = {}


# ------------------------------------------------------------------------------------------ formatting
def hr(x: float, nd: int = 0) -> str:
    """Croatian number format: thousands dot, decimal comma."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def eur(x: float, nd: int = 0) -> str:
    return f"{hr(x, nd)} €"


def pct(x: float, nd: int = 1, sign: bool = True) -> str:
    """``x`` is a fraction (0.155 -> +15,5 %)."""
    s = hr(abs(x) * 100, nd)
    if not sign:
        return f"{s} %"
    return f"{'+' if x >= 0 else '-'}{s} %"


def day(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def usd(x: float, nd: int = 2) -> str:
    return f"{hr(x, nd)}"


# ------------------------------------------------------------------------------------------ data
def read_daily(ticker: str) -> pd.DataFrame:
    """Raw daily CSV (as on disk) indexed by date."""
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"])
    d = d.drop_duplicates("date").sort_values("date").set_index("date")
    return d


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text())


# ------------------------------------------------------------------------------------------ drawing
def new_fig(
    height: float, title: str, subtitle: str | None = None, rows: int = 1, **kw: Any
):
    fig, axes = plt.subplots(rows, 1, figsize=(WIDTH_IN, height), **kw)
    fig.patch.set_facecolor(PAPER)
    fig.text(
        0.012,
        0.985,
        title,
        fontsize=21,
        fontweight="bold",
        color=INK,
        ha="left",
        va="top",
    )
    if subtitle:
        fig.text(
            0.012,
            0.985 - 0.045 * (7.0 / height),
            subtitle,
            fontsize=13,
            color=GREY,
            ha="left",
            va="top",
        )
    return fig, axes


def canvas(height: float, title: str, subtitle: str | None = None) -> Any:
    """Empty 1400 px wide notebook page with a title; axes are added by the caller with ``fig.add_axes``."""
    fig = plt.figure(figsize=(WIDTH_IN, height))
    fig.patch.set_facecolor(PAPER)
    fig.text(
        0.012,
        0.99,
        title,
        fontsize=21,
        fontweight="bold",
        color=INK,
        ha="left",
        va="top",
    )
    if subtitle:
        fig.text(
            0.012,
            0.99 - 0.052 * (7.0 / height),
            subtitle,
            fontsize=12.5,
            color=GREY,
            ha="left",
            va="top",
        )
    return fig


def paper(ax: Any, grid: bool = True) -> None:
    ax.set_facecolor(PAPER)
    if grid:
        ax.grid(True, color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def tip(
    ax: Any,
    text: str,
    xy: tuple[float, float] | None,
    xytext: tuple[float, float],
    color: str = RED,
    rad: float = 0.25,
    size: float = 12.5,
    ha: str = "left",
    coords: str = "data",
    arrow: bool = True,
    box: bool = True,
    lw: float = 1.6,
) -> Any:
    """Red handwritten teacher note; ``xytext`` in data (default) or axes-fraction coordinates; pencil arrow to ``xy``."""
    kw: dict[str, Any] = {}
    if arrow and xy is not None:
        kw["arrowprops"] = dict(
            arrowstyle="->",
            color=color,
            lw=lw,
            connectionstyle=f"arc3,rad={rad}",
            shrinkB=5,
        )
    tcoords = "data" if coords == "data" else "axes fraction"
    ann = ax.annotate(
        text,
        xy=xy if xy is not None else xytext,
        xycoords="data" if xy is not None else tcoords,
        xytext=xytext,
        textcoords=tcoords,
        ha=ha,
        va="center",
        fontsize=size,
        color=color,
        bbox=dict(boxstyle="round,pad=0.3", fc=PAPER, ec="none", alpha=0.85)
        if box
        else None,
        zorder=9,
        annotation_clip=False,
        **kw,
    )
    if arrow and xy is not None and ann.arrow_patch is not None:
        sketch(ann.arrow_patch, 0.9, 60, 3)
    return ann


def ring(ax: Any, x: float, y: float, color: str = RED, size: float = 650) -> None:
    ax.scatter(
        [x], [y], s=size, facecolors="none", edgecolors=color, linewidths=2.2, zorder=8
    )


def candles(
    ax: Any, df: pd.DataFrame, x: np.ndarray | None = None, width: float = 0.62
) -> np.ndarray:
    """Draw OHLC candles at integer positions (trading days, no weekend gaps). Returns the x positions."""
    xs = np.arange(len(df)) if x is None else x
    for xi, (o, h, lo, c) in zip(xs, df[["open", "high", "low", "close"]].to_numpy()):
        up = c >= o
        col = GREEN if up else PENCIL
        ax.vlines(xi, lo, h, color=col, lw=1.3, zorder=3)
        body_lo, body_hi = min(o, c), max(o, c)
        ax.add_patch(
            Rectangle(
                (xi - width / 2, body_lo),
                width,
                max(body_hi - body_lo, 1e-9),
                fc=col if not up else "#bfe6c9",
                ec=col,
                lw=1.3,
                zorder=4,
            )
        )
    return xs


def date_ticks(
    ax: Any, dates: pd.DatetimeIndex, n: int = 8, fmt: str = "{d}. {m}."
) -> None:
    pos = np.linspace(0, len(dates) - 1, n).round().astype(int)
    ax.set_xticks(pos)
    ax.set_xticklabels(
        [fmt.format(d=dates[p].day, m=dates[p].month, y=dates[p].year) for p in pos],
        fontsize=11,
    )


def era_line(ax: Any, ylow: float = 0.03, label: bool = True) -> None:
    ax.axvline(AI_ERA, color=RED, ls=":", lw=2.0, zorder=2)
    if label:
        ax.text(
            AI_ERA + pd.Timedelta(days=25),
            ylow,
            "početak AI ere\n(1. 1. 2023.)",
            transform=ax.get_xaxis_transform(),
            fontsize=12,
            color=RED,
        )


def bottom_note(fig: Any, text: str, y: float = 0.012, size: float = 12.5) -> None:
    fig.text(
        0.012,
        y,
        "Bilješka učitelja: " + text,
        fontsize=size,
        color=RED,
        ha="left",
        va="bottom",
        wrap=True,
    )


def finish(fig: Any, name: str, caption: dict[str, Any]) -> str:
    """Save as an optimised PNG exactly 1400 px wide and register the Croatian caption."""
    OUT.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor=PAPER)
    plt.close(fig)
    buf.seek(0)
    im = Image.open(buf).convert("RGB")
    if im.width != 1400:
        im = im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS)
    im.quantize(
        colors=160, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    ).save(OUT / name, optimize=True)
    CAPTIONS[name] = caption
    return name


def write_captions() -> None:
    p = OUT / "captions.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(CAPTIONS)
    p.write_text(json.dumps(dict(sorted(old.items())), indent=2, ensure_ascii=False))


def smart_ylim(ax: Any, lo: float, hi: float, pad: float = 0.08) -> None:
    span = hi - lo
    ax.set_ylim(lo - span * pad, hi + span * pad)


def nearest_to_median(items: list[Any], key: Any) -> Any:
    """The item whose key is closest to the median key (a transparent, non-cherry-picked choice)."""
    vals = np.array([key(i) for i in items], dtype=float)
    med = float(np.median(vals))
    return items[int(np.argmin(np.abs(vals - med)))]


def nearest_to(items: list[Any], key: Any, target: float) -> Any:
    """The item whose key is closest to ``target`` (used with a stated, non-cherry-picked target such as a median)."""
    return min(items, key=lambda i: abs(float(key(i)) - target))


def badge(
    ax: Any, x: float, y: float, n: int | str, color: str = RED, size: float = 13
) -> None:
    """Numbered red circle placed on a data point (data coordinates); the text for it lives in ``side_notes``."""
    ax.annotate(
        str(n),
        xy=(x, y),
        xytext=(0, 0),
        textcoords="offset points",
        ha="center",
        va="center",
        fontsize=size,
        fontweight="bold",
        color="white",
        bbox=dict(boxstyle="circle,pad=0.22", fc=color, ec=PENCIL, lw=1.0),
        zorder=12,
    )


def side_notes(
    fig: Any,
    steps: list[tuple[str, str, str]],
    top: float = 0.85,
    x: float = 0.715,
    size: float = 12.5,
    width: int = 38,
    height_in: float = 9.0,
    gap: float = 0.9,
) -> float:
    """Right-hand column of numbered teacher notes ``(number, colour, text)``; returns the lowest y used."""
    import textwrap

    line_h = size * 1.42 / 72.0 / height_in
    y = top
    for num, color, text in steps:
        lines = textwrap.wrap(text, width=width, break_long_words=False) or [""]
        fig.text(
            x - 0.028,
            y,
            num,
            fontsize=size + 1.5,
            fontweight="bold",
            color="white",
            ha="center",
            va="top",
            bbox=dict(boxstyle="circle,pad=0.22", fc=color, ec=PENCIL, lw=1.0),
        )
        for li, line in enumerate(lines):
            fig.text(
                x,
                y - li * line_h,
                line,
                fontsize=size,
                color=color,
                ha="left",
                va="top",
            )
        y -= (len(lines) + gap) * line_h
    return y


def nz(x: float | None, default: float = float("nan")) -> float:
    return (
        default if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
    )
