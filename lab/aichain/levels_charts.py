"""Notebook-style map chart per ticker (graph paper, pencil, red teacher notes in Croatian).

Reuses the style helpers of ``lab.top10.charts`` (imported, not edited). Research only.
"""

from __future__ import annotations

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

from lab.aichain import levels as lv
from lab.aichain.levels_map import hr_date, hr_num, hr_pct
from lab.top10 import charts as nb

BARS_SHOWN = 250


def _candles(ax: Any, P: lv.Prepared, s: int, e: int) -> None:
    b = P.bars
    x = mdates.date2num(b.dates[s:e].to_pydatetime())
    o, h, lo, c = b.open[s:e], b.high[s:e], b.low[s:e], b.close[s:e]
    up = c >= o
    ax.vlines(x, lo, h, color=nb.PENCIL, lw=0.8, zorder=3)
    body_h = np.maximum(np.abs(c - o), (h - lo) * 0.02)
    ax.bar(
        x[up],
        body_h[up],
        bottom=np.minimum(o, c)[up],
        width=0.65,
        color=nb.PAPER,
        edgecolor=nb.GREEN,
        lw=0.9,
        zorder=4,
    )
    ax.bar(
        x[~up],
        body_h[~up],
        bottom=np.minimum(o, c)[~up],
        width=0.65,
        color=nb.PENCIL,
        edgecolor=nb.PENCIL,
        lw=0.6,
        zorder=4,
    )


def _sma(close: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(close).rolling(n).mean().to_numpy()


def _spread_labels(ys: list[float], lo: float, hi: float, gap: float) -> list[float]:
    """Nudge label heights apart (data units) so right-hand labels do not overlap."""
    order = np.argsort(ys)
    out = np.array(ys, float)
    prev = -np.inf
    for i in order:
        out[i] = max(out[i], prev + gap)
        prev = out[i]
    over = out.max() - hi
    if over > 0:
        out -= over
    return list(np.clip(out, lo, hi))


def _wrap(text: str, width: int = 40) -> str:
    return "\n".join(textwrap.wrap(text, width))


def draw(P: lv.Prepared, m: dict[str, Any], out_path: Path, placebo_line: str) -> None:
    """Render one ticker's notebook page to ``out_path`` (PNG)."""
    b = P.bars
    n = len(b)
    s = max(0, n - BARS_SHOWN)
    t = n - 1
    close = float(b.close[t])
    dates = b.dates
    fig, ax = plt.subplots(figsize=(14.5, 9.8))
    fig.subplots_adjust(left=0.065, right=0.86, top=0.915, bottom=0.30)
    ref = " [referentno, nepotvrđeno za EU]" if m["group"] == "metals_indices" else ""
    nb.paper(
        ax,
        f"{P.ticker}{ref}: karta razina i strukture (zadnji dan {hr_date(m['last_date'])})",
    )
    _candles(ax, P, s, n)
    xs = mdates.date2num(dates[s:n].to_pydatetime())
    for k, (nn, col, ls) in enumerate(((50, nb.INK, "-"), (200, nb.PENCIL, "--"))):
        ax.plot(
            xs,
            _sma(b.close, nn)[s:n],
            color=col,
            lw=1.6,
            ls=ls,
            label=f"prosjek {nn} dana (SMA{nn})",
            zorder=5,
        )
    ylo = float(b.low[s:n].min())
    yhi = float(b.high[s:n].max())
    pad = (yhi - ylo) * 0.06
    ylo -= pad
    yhi += pad
    x_left, x_right = xs[0], xs[-1]
    x_ext = x_right + (x_right - x_left) * 0.16
    a = float(P.atr[t])

    # swing range with 50 percent line and premium / discount shading
    sr = m["swing_range"]
    if sr:
        x0 = max(
            mdates.date2num(pd.Timestamp(min(sr["low_date"], sr["high_date"]))), x_left
        )
        lo_r, hi_r, mid = sr["low"], sr["high"], sr["mid"]
        ax.fill_between([x0, x_right], mid, hi_r, color=nb.RED, alpha=0.07, zorder=1)
        ax.fill_between([x0, x_right], lo_r, mid, color=nb.GREEN, alpha=0.08, zorder=1)
        for yv, ls, lab in (
            (hi_r, "--", "vrh raspona"),
            (lo_r, "--", "dno raspona"),
            (mid, ":", "50 % raspona"),
        ):
            ax.hlines(yv, x0, x_right, color=nb.INK, lw=1.2, ls=ls, zorder=2)
        ax.text(
            x0 + 2, hi_r, "premium (skupo)", color=nb.RED, fontsize=9.5, va="bottom"
        )
        ax.text(
            x0 + 2, lo_r, "diskont (jeftino)", color=nb.GREEN, fontsize=9.5, va="top"
        )

    # S/R bands: keep the strongest visible plus the nearest two of each side
    vis = [L for L in m["levels"] if ylo <= L["price"] <= yhi]
    keep = sorted(vis, key=lambda L: -L["strength"])[:7]
    for L in m["nearest_supports"] + m["nearest_resistances"]:
        if L not in keep and ylo <= L["price"] <= yhi:
            keep.append(L)
    ys, labs, cols = [], [], []
    for L in keep:
        col = nb.GREEN if L["type"] == "support" else nb.RED
        half = max(0.25 * a, 0.002 * L["price"])
        ax.fill_between(
            [x_left, x_right],
            L["price"] - half,
            L["price"] + half,
            color=col,
            alpha=0.2,
            lw=0,
            zorder=1,
        )
        ax.hlines(L["price"], x_left, x_right, color=col, lw=1.1, alpha=0.9, zorder=2)
        rel = L["reliability"]
        r_txt = (
            f"{rel['rate'] * 100:.0f} % od {rel['n']}"
            if rel["enough_touches"]
            else (f"{rel['n']} dodira (malo)" if rel["n"] else "bez dodira")
        )
        ys.append(L["price"])
        labs.append(f"{hr_num(L['price'])}  odbijanje: {r_txt}")
        cols.append(col)
    fixed = _spread_labels(ys, ylo, yhi, (yhi - ylo) * 0.034)
    for y0, y1, lab, col in zip(ys, fixed, labs, cols):
        ax.text(
            x_right + (x_ext - x_right) * 0.04,
            y1,
            lab,
            color=col,
            fontsize=9.3,
            va="center",
            ha="left",
            clip_on=False,
        )

    # equal highs / lows (liquidity)
    for key, txt in (
        ("above", "jednaki vrhovi: stopovi iznad"),
        ("below", "jednaki dnevi: stopovi ispod"),
    ):
        for p in m["liquidity_pools"][key]:
            if not ylo <= p["level"] <= yhi:
                continue
            x0 = max(mdates.date2num(pd.Timestamp(p["first_date"])), x_left)
            ax.hlines(
                p["level"],
                x0,
                x_right,
                color=nb.PENCIL,
                lw=1.4,
                ls=(0, (1, 2)),
                zorder=3,
            )
            ax.text(
                x_left + 3, p["level"], txt, color=nb.PENCIL, fontsize=8.5, va="bottom"
            )
            break

    # fresh demand / supply zones
    for kind, col, name in (
        ("demand", nb.GREEN, "zona potražnje"),
        ("supply", nb.RED, "zona ponude"),
    ):
        for z in m["fresh_zones"][kind][:2]:
            if z["high"] - z["low"] > 0.2 * (yhi - ylo):
                continue
            if not (
                ylo + 0.03 * (yhi - ylo) <= z["high"]
                and z["low"] <= yhi - 0.03 * (yhi - ylo)
            ):
                continue
            x0 = max(mdates.date2num(pd.Timestamp(z["known_date"])), x_left)
            ax.add_patch(
                Rectangle(
                    (x0, z["low"]),
                    x_right - x0,
                    z["high"] - z["low"],
                    facecolor="none",
                    edgecolor=col,
                    lw=1.4,
                    hatch="///",
                    alpha=0.7,
                    zorder=2,
                )
            )
            ax.text(x0, z["high"], name, color=col, fontsize=8.5, va="bottom")

    # last BOS / market shift
    for key, txt in (("last_bos", "BOS"), ("last_shift", "promjena karaktera")):
        e = m["daily"][key]
        if not e:
            continue
        ed, ld = pd.Timestamp(e["date"]), pd.Timestamp(e["broken_level_date"])
        if ed < dates[s]:
            continue
        x0 = max(mdates.date2num(ld), x_left)
        ax.hlines(
            e["broken_level"], x0, mdates.date2num(ed), color=nb.INK, lw=1.8, zorder=6
        )
        ax.scatter(
            [mdates.date2num(ed)],
            [e["broken_level"]],
            marker="^" if e["direction"] == "bikovski" else "v",
            s=90,
            color=nb.INK,
            zorder=7,
        )
        ax.text(
            mdates.date2num(ed),
            e["broken_level"],
            " " + txt,
            color=nb.INK,
            fontsize=9.5,
            va="bottom" if e["direction"] == "bikovski" else "top",
            zorder=7,
        )

    ax.set_xlim(x_left, x_ext)
    ax.set_ylim(ylo, yhi)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.legend(loc="upper left", fontsize=9, frameon=True, facecolor=nb.PAPER)
    ax.set_ylabel("cijena")

    # teacher notes pointing at the most important things
    notes: list[tuple[str, tuple[float, float], str]] = []
    sup, res = m["nearest_supports"], m["nearest_resistances"]
    if sup:
        r = sup[0]
        notes.append(
            (
                f"Najbliža potpora {hr_num(r['price'])}: {hr_pct(abs(r['distance_pct']))} ispod. Pad do nje je oko {hr_num(abs(1000 * (r['price'] / close - 1)), 0)} EUR na svakih 1.000 EUR.",
                (mdates.date2num(dates[t]), r["price"]),
                nb.GREEN,
            )
        )
    if not res:
        notes.insert(
            1,
            (
                "Iznad cijene nema potvrđenog otpora: cijena je na novom vrhu, nema crte na kojoj su prije prodavali, ali ni oslonca.",
                (mdates.date2num(dates[t]), close),
                nb.RED,
            ),
        )
    if not sup:
        notes.insert(
            0,
            (
                "Ispod cijene nema potvrđene potpore u zadnjim godinama: nema poznatog oslonca u blizini.",
                (mdates.date2num(dates[t]), close),
                nb.GREEN,
            ),
        )
    if res:
        r = res[0]
        notes.append(
            (
                f"Najbliži otpor {hr_num(r['price'])}: {hr_pct(abs(r['distance_pct']))} iznad. Tu su prije prodavali.",
                (mdates.date2num(dates[t]), r["price"]),
                nb.RED,
            )
        )
    if sr:
        if sr["zone"] == "discount":
            msg = f"Cijena je u diskontu: jeftinijoj polovici zadnjeg raspona ({hr_num(sr['position_pct'], 0)} %)."
        elif sr["zone"] == "premium":
            msg = f"Cijena je u premiumu: skupljoj polovici zadnjeg raspona ({hr_num(sr['position_pct'], 0)} %)."
        elif sr["position_pct"] > 100:
            msg = f"Cijena je iznad zadnjeg raspona ({hr_num(sr['position_pct'], 0)} %): probijen je vrh raspona."
        else:
            msg = f"Cijena je ispod zadnjeg raspona ({hr_num(sr['position_pct'], 0)} %): probijeno je dno raspona."
        notes.append((msg, (mdates.date2num(dates[t]), sr["mid"]), nb.PENCIL))
    ev = m["daily"]["last_shift"] or m["daily"]["last_bos"]
    if ev and pd.Timestamp(ev["date"]) >= dates[s]:
        is_shift = ev is m["daily"]["last_shift"]
        kind = "promjena karaktera" if is_shift else "proboj strukture (BOS)"
        dirw = (
            ("bikovska" if ev["direction"] == "bikovski" else "medvjeđa")
            if is_shift
            else ev["direction"]
        )
        notes.append(
            (
                f"Zadnje: {kind}, {dirw}, {hr_date(ev['date'])} Trend se gleda preko vrhova i dna.",
                (mdates.date2num(pd.Timestamp(ev["date"])), ev["broken_level"]),
                nb.INK,
            )
        )
    span = x_right - x_left
    slots = [(0.012, 0.235), (0.50, 0.235), (0.012, 0.175), (0.50, 0.175)]
    for k, ((txt, xy, col), (fx, fy)) in enumerate(zip(notes[:4], slots), start=1):
        fig.text(
            fx,
            fy,
            f"{k}) " + _wrap(txt, 84),
            fontsize=10.8,
            color=nb.RED,
            va="top",
            ha="left",
        )
        ax.text(
            xy[0] - 0.02 * span * k,
            xy[1],
            str(k),
            color=nb.RED,
            fontsize=11,
            ha="center",
            va="center",
            bbox={
                "boxstyle": "circle,pad=0.2",
                "fc": nb.PAPER,
                "ec": nb.RED,
                "lw": 1.4,
            },
            zorder=10,
        )
    fig.text(
        0.012,
        0.012,
        "Bilješka učitelja: " + _wrap(placebo_line, 150),
        fontsize=11,
        color=nb.RED,
        ha="left",
        va="bottom",
    )
    fig.text(
        0.012,
        0.105,
        "Zeleno = potpora (pod cijenom), crveno = otpor (iznad cijene), debela crta = razina, traka = zona dodira; "
        "pouzdanost = koliko se puta cijena od razine odbila za 1,5 ATR prije nego je zatvorila 1 ATR iza nje.",
        fontsize=9.3,
        color=nb.PENCIL,
        ha="left",
        va="bottom",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, facecolor=nb.PAPER)
    plt.close(fig)
