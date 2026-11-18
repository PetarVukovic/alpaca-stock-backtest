"""MASTER charts c01-c09, c15, c22: real candles and real trades from the engine re-runs (notebook style)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from lab.aichain import master_data as D
from lab.aichain.master_common import (
    GREEN,
    GREY,
    INK,
    LIGHT,
    LOSS,
    ORANGE,
    PAPER,
    PENCIL,
    RED,
    WIN,
    badge,
    bottom_note,
    candles,
    canvas,
    date_ticks,
    day,
    eur,
    finish,
    hr,
    nearest_to,
    paper,
    pct,
    read_daily,
    ring,
    side_notes,
    tip,
    usd,
)

C13 = "W1_C13C_ORIG"
W5 = "W5_SR_BREAKOUT_RETEST"


def _bars(ticker: str) -> Any:
    return D.runner().bars[ticker]


def _frame(ticker: str) -> pd.DataFrame:
    b = _bars(ticker)
    return pd.DataFrame(
        {"open": b.open, "high": b.high, "low": b.low, "close": b.close}, index=b.dates
    )


def _pos(frame: pd.DataFrame, date: str) -> int:
    return int(frame.index.get_loc(pd.Timestamp(date)))


# ================================================================================ c01
def c01_price_anatomy() -> str:
    raw = read_daily("MU")
    sma200 = raw["close"].rolling(200).mean()
    wk = raw.loc["2023-08-14":"2023-08-18", ["open", "high", "low", "close"]]
    assert len(wk) == 5
    fig = canvas(
        9.2,
        "Svijeća: jedan dan na jednoj slici (stvarni MU, tjedan 14. 8. - 18. 8. 2023.)",
        "Svaka svijeća sažima cijeli dan trgovanja u četiri broja: otvaranje, najviše, najniže i zatvaranje.",
    )
    a1 = fig.add_axes([0.055, 0.50, 0.60, 0.385])
    paper(a1)
    xs = candles(a1, wk, width=0.5)
    a1.set_xticks(xs)
    a1.set_xticklabels([f"{d.day}. {d.month}." for d in wk.index], fontsize=12)
    a1.set_ylabel("cijena (USD)")
    a1.set_xlim(-2.9, 4.7)
    a1.set_ylim(57.5, 74.5)
    mon, tue, fri = wk.iloc[0], wk.iloc[1], wk.iloc[4]
    for lab, val, ypos, xt in [
        (f"najviše {usd(mon.high)}", mon.high, 71.8, 0.0),
        (f"zatvaranje {usd(mon.close)}\n(zadnja cijena dana)", mon.close, 68.6, 0.25),
        (f"otvaranje {usd(mon.open)}\n(prva cijena dana)", mon.open, 63.6, -0.25),
        (f"najniže {usd(mon.low)}", mon.low, 60.2, 0.0),
    ]:
        tip(
            a1,
            lab,
            (xt, val),
            (-0.5, ypos),
            rad=0.0 if xt == 0 else 0.15,
            size=11.5,
            ha="right",
        )
    tip(
        a1,
        f"tamna svijeća: dan u minusu\n(zatvaranje {usd(tue.close)} ispod\notvaranja {usd(tue.open)})",
        (1, (tue.open + tue.close) / 2),
        (1.1, 72.0),
        rad=0.25,
        size=11.5,
    )
    tip(
        a1,
        "fitilj: koliko se cijena privremeno\npopela ili spustila, pa se vratila",
        (4, fri.high),
        (1.55, 60.0),
        rad=-0.3,
        size=11.5,
        box=False,
    )
    tip(
        a1,
        "tijelo = od otvaranja\ndo zatvaranja",
        (-0.25, (mon.open + mon.close) / 2),
        (-0.5, 66.2),
        color=INK,
        rad=0.0,
        size=11.5,
        ha="right",
    )
    mon_r = mon.close / mon.open - 1
    tue_r = tue.close / tue.open - 1
    wk_r = fri.close / mon.open - 1
    steps = [
        (
            "1",
            GREEN,
            f"Zelena/svijetla svijeća: zatvaranje iznad otvaranja. Ponedjeljak: 1.000 € uloženo na otvaranju ({usd(mon.open)}) vrijedi na zatvaranju ({usd(mon.close)}) {pct(mon_r)} = {eur(1000 * mon_r)}.",
        ),
        (
            "2",
            PENCIL,
            f"Tamna svijeća: zatvaranje ispod otvaranja. Utorak: otvaranje {usd(tue.open)}, zatvaranje {usd(tue.close)} = {pct(tue_r)}, na 1.000 € to je {eur(1000 * tue_r)}.",
        ),
        (
            "3",
            INK,
            f"Cijeli tjedan: otvaranje ponedjeljka {usd(mon.open)}, zatvaranje petka {usd(fri.close)} = {pct(wk_r)} = {eur(1000 * wk_r)} (bez troškova; USD se ovdje tretira kao EUR).",
        ),
    ]
    side_notes(fig, steps, top=0.865, x=0.715, size=12.5, width=40, height_in=9.2)
    # context panel: 90 trading days with SMA200
    end = raw.index.get_loc(wk.index[-1]) + 1
    seg = raw.iloc[end - 90 : end]
    a2 = fig.add_axes([0.055, 0.125, 0.93, 0.255])
    paper(a2)
    cx = candles(a2, seg[["open", "high", "low", "close"]], width=0.6)
    a2.plot(
        cx,
        sma200.iloc[end - 90 : end].to_numpy(),
        color=INK,
        lw=2.4,
        label="SMA200: prosjek zatvaranja zadnjih 200 dana",
    )
    a2.axvspan(len(seg) - 5.5, len(seg) - 0.5, color="#ffe9a8", alpha=0.8, zorder=1)
    date_ticks(a2, seg.index, 9, "{d}. {m}.")
    a2.set_ylabel("cijena (USD)")
    a2.legend(loc="upper left", frameon=False, fontsize=12)
    s_last = float(sma200.iloc[end - 1])
    a2.set_ylim(float(seg.low.min()) * 0.93, float(seg.high.max()) * 1.1)
    tip(
        a2,
        "žuto = tjedan s gornje slike",
        (len(seg) - 3, float(seg.high.iloc[-3])),
        (len(seg) - 30, float(seg.high.max()) * 1.05),
        rad=-0.2,
        size=12,
    )
    rel = "iznad" if seg.close.iloc[-1] > s_last else "ispod"
    tip(
        a2,
        f"na dan {day(seg.index[-1])}: SMA200 = {usd(s_last)}, cijena {usd(seg.close.iloc[-1])} je {rel} njega",
        None,
        (len(seg) * 0.30, float(seg.low.min()) * 0.93 + 0.9),
        color=INK,
        arrow=False,
        size=12,
        box=False,
    )
    bottom_note(
        fig,
        "svijeća je samo sažetak dana. Ne kaže što će cijena napraviti sutra, ali pokazuje koliko je dan bio nemiran (dugi fitilji) i tko je 'pobijedio' (boja tijela). Ovaj tjedan je završio u minusu: nije svaki tjedan prikazan na uspješan način.",
        y=0.012,
    )
    nums = [
        f"MU dnevni CSV (data/ohlcv/MU_1d.csv), 14. 8. 2023.: otvaranje {mon.open}, najviše {mon.high}, najniže {mon.low}, zatvaranje {mon.close}",
        f"15. 8. 2023.: otvaranje {tue.open}, zatvaranje {tue.close}; 18. 8. 2023. zatvaranje {fri.close}",
        f"izračun: ponedjeljak {pct(mon_r)}, utorak {pct(tue_r)}, tjedan {pct(wk_r)} (iz CSV-a, bez troškova)",
        f"SMA200 na 18. 8. 2023. = {s_last:.2f} (izračun iz CSV-a, 200 zatvaranja)",
    ]
    return finish(
        fig,
        "c01_price_anatomy.png",
        {
            "title": "Anatomija svijeće na stvarnom MU tjednu",
            "what_to_see": "Gore: pet dnevnih svijeća, ponedjeljak označen otvaranjem, zatvaranjem, najvišim i najnižim, uz tijelo i fitilj. Desno: što isti dan znači u eurima. Dolje: isti tjedan (žuto) u kontekstu zadnjih 90 dana s prosjekom 200 dana.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c02 / c03
def _c13_pick() -> tuple[dict[str, Any], float, list[dict[str, Any]]]:
    tr = D.sleeve("MU", C13).trades
    wins = [t for t in tr if t["return"] > 0]
    med = float(np.median([t["return"] for t in wins]))
    ok = []
    for i, t in enumerate(tr):
        gap = (
            99
            if i == 0
            else (
                pd.Timestamp(t["entry_date"]) - pd.Timestamp(tr[i - 1]["exit_date"])
            ).days
        )
        if t["return"] > 0 and gap >= 3 and t["bars_held"] >= 10:
            ok.append(t)
    return nearest_to(ok, lambda x: x["return"], med), med, tr


def c02_c13c_walkthrough() -> str:
    t, med, tr = _c13_pick()
    wins = [x for x in tr if x["return"] > 0]
    f = _frame("MU")
    ei, xi = _pos(f, t["entry_date"]), _pos(f, t["exit_date"])
    a, b = max(0, ei - 70), min(len(f), xi + 14)
    seg = f.iloc[a:b]
    sma200 = f["close"].rolling(200).mean()
    fig = canvas(
        9.2,
        "C13C korak po korak: jedan stvarni MU posao (od signala do izlaza)",
        f"Posao: kupnja {day(t['entry_date'])}, izlaz {day(t['exit_date'])}. Odabir po pravilu: dobitni posao najbliži medijanu dobitnih MU poslova u AI eri ({pct(med)}).",
    )
    ax = fig.add_axes([0.06, 0.13, 0.635, 0.735])
    paper(ax)
    xs = candles(ax, seg, width=0.6)
    ax.plot(
        xs,
        sma200.iloc[a:b].to_numpy(),
        color=INK,
        lw=2.4,
        label="SMA200 (prosjek 200 dana)",
    )
    si = ei - 1
    five_back = si - 5
    c_now, c_5 = float(f.close.iloc[si]), float(f.close.iloc[five_back])
    drop = c_now / c_5 - 1
    sma_s = float(sma200.iloc[si])
    ax.axvspan(five_back - a, si - a + 0.4, color="#ffe9a8", alpha=0.8, zorder=1)
    stop = D.trail_stop_series(f.high.to_numpy(), ei, xi, t["entry_price"], 0.10)
    ax.step(
        np.arange(ei, xi + 1) - a,
        stop,
        where="post",
        color=RED,
        lw=2.4,
        label="klizni stop (10 % ispod najvišeg)",
        zorder=6,
    )
    ax.scatter(
        [ei - a],
        [t["raw_entry"]],
        marker="^",
        s=240,
        color=WIN,
        zorder=10,
        edgecolors=PENCIL,
        linewidths=1.3,
    )
    ax.scatter(
        [xi - a],
        [t["raw_exit"]],
        marker="v",
        s=240,
        color=LOSS,
        zorder=10,
        edgecolors=PENCIL,
        linewidths=1.3,
    )
    assert abs(min(f.open.iloc[xi], stop[-1]) - t["raw_exit"]) < 0.02, (
        t["raw_exit"],
        stop[-1],
    )
    date_ticks(ax, seg.index, 9, "{d}. {m}.")
    ax.set_ylabel("cijena (USD)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    ymax, ymin = float(seg.high.max()), float(seg.low.min())
    ax.set_ylim(ymin * 0.95, ymax * 1.05)
    badge(ax, si - a, c_now + (ymax - ymin) * 0.06, 1)
    badge(ax, ei - a, t["raw_entry"] - (ymax - ymin) * 0.07, 2, WIN)
    pk = ei + int(np.argmax(f.high.to_numpy()[ei : xi + 1]))
    badge(ax, pk - a, float(f.high.iloc[pk]) + (ymax - ymin) * 0.06, 3)
    badge(ax, xi - a, t["raw_exit"] - (ymax - ymin) * 0.07, 4, LOSS)
    peak = float(f.high.iloc[ei : xi + 1].max())
    ret = t["return"]
    steps = [
        (
            "1",
            RED,
            f"SIGNAL (zatvaranje {day(f.index[si])}): cijena {usd(c_now)} je iznad SMA200 ({usd(sma_s)}) I pala je {pct(drop, 1, False)} u 5 dana ({usd(c_5)} -> {usd(c_now)}, žuti pojas). Oba uvjeta odjednom = signal.",
        ),
        (
            "2",
            WIN,
            f"KUPNJA sljedeći dan na otvaranju: {usd(t['raw_entry'])}. Početni stop {usd(stop[0])} (10 % ispod). Najgori slučaj: oko {eur(100)} od 1.000 €.",
        ),
        (
            "3",
            RED,
            f"Stop SAMO raste. Najviši doseg {usd(peak)} povukao ga je na {usd(float(stop.max()))}; nikad se ne spušta.",
        ),
        (
            "4",
            LOSS,
            f"IZLAZ {day(t['exit_date'])} po {usd(t['raw_exit'])}: cijena je dotaknula stop. Rezultat s 1.000 €: {pct(ret)} = {eur(1000 * ret)} (nakon troška 0,025 % po strani).",
        ),
    ]
    side_notes(fig, steps, top=0.855, x=0.725, size=12.5, width=38, height_in=9.2)
    best = max(x["return"] for x in tr)
    bottom_note(
        fig,
        f"medijan svih {len(wins)} dobitnih MU poslova u AI eri je {pct(med)}, a najbolji {pct(best)}. Većina poslova je dakle manja od ovog, a svaki gubitak ograničen stopom na oko -10 %.",
        y=0.012,
    )
    nums = [
        f"MU C13C trade (re-run swing.py, jednak summary.json): ulaz {t['entry_date']} po {t['raw_entry']:.2f}, izlaz {t['exit_date']} po {t['raw_exit']:.2f}, povrat nakon troška {pct(t['return'])}",
        f"signal {day(f.index[si])}: zatvaranje {c_now:.2f}, 5 dana ranije {c_5:.2f} = {pct(drop)}, SMA200 {sma_s:.2f}",
        f"medijan dobitnih MU poslova AI ere {pct(med)} ({len(wins)} dobitnih od {len(tr)}), najbolji {pct(best)}",
        "trošak 2,5 bps po strani (summary.json cost_note); klizni stop 10 % ispod najvišeg (lab/aichain/contenders.py)",
    ]
    return finish(
        fig,
        "c02_c13c_walkthrough.png",
        {
            "title": "C13C na jednom stvarnom MU poslu",
            "what_to_see": "Žuti pojas = pet dana pada prije signala. Zeleni trokut = kupnja na sljedećem otvaranju. Crvena stepenica = klizni stop koji samo raste. Crveni trokut = izlaz kad cijena dotakne stop. Brojevi u krugovima povezuju točke na grafu s objašnjenjem desno.",
            "numbers_used": nums,
        },
    )


def c03_c13c_failure() -> str:
    tr = D.sleeve("MU", C13).trades
    seq = [t for t in tr if "2024-06-27" <= t["entry_date"] <= "2024-08-02"]
    assert len(seq) == 4 and all(t["return"] < 0 for t in seq)
    f = _frame("MU")
    sma200 = f["close"].rolling(200).mean()
    a, b = _pos(f, "2024-05-24"), _pos(f, "2024-08-30") + 1
    seg = f.iloc[a:b]
    fig = canvas(
        9.6,
        "C13C kad ne uspije: stvarni MU niz od četiri gubitka zaredom (srpanj - kolovoz 2024.)",
        "Stop radi svoj posao (gubitak je ograničen na oko -10 %), ali se tržište vraćalo naprijed-natrag pa je stop četiri puta zaredom izbacio.",
    )
    ax = fig.add_axes([0.06, 0.35, 0.635, 0.51])
    paper(ax)
    xs = candles(ax, seg, width=0.6)
    ax.plot(xs, sma200.iloc[a:b].to_numpy(), color=INK, lw=2.2, label="SMA200")
    value = 1000.0
    steps = []
    ymax, ymin = float(seg.high.max()), float(seg.low.min())
    ax.set_ylim(ymin * 0.9, ymax * 1.1)
    for k, t in enumerate(seq, 1):
        ei, xi = _pos(f, t["entry_date"]) - a, _pos(f, t["exit_date"]) - a
        ax.axvspan(
            ei - 0.5,
            xi + 0.5,
            color="#fde2de" if k % 2 else "#fbd0ca",
            alpha=0.8,
            zorder=1,
        )
        ax.scatter(
            [ei],
            [t["raw_entry"]],
            marker="^",
            s=170,
            color=WIN,
            edgecolors=PENCIL,
            zorder=10,
        )
        ax.scatter(
            [xi],
            [t["raw_exit"]],
            marker="v",
            s=170,
            color=LOSS,
            edgecolors=PENCIL,
            zorder=10,
        )
        badge(ax, (ei + xi) / 2, ymax * 1.06, k, LOSS)
        value *= 1 + t["return"]
        steps.append(
            (
                str(k),
                LOSS,
                f"{day(t['entry_date'])} do {day(t['exit_date'])}: kupnja {usd(t['raw_entry'])}, stop-izlaz {usd(t['raw_exit'])} = {pct(t['return'])}. Ostane {eur(value)}.",
            )
        )
    date_ticks(ax, seg.index, 9, "{d}. {m}.")
    ax.set_ylabel("cijena (USD)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    low_end = side_notes(
        fig, steps, top=0.855, x=0.725, size=12.5, width=38, height_in=9.6
    )
    fig.text(
        0.725,
        low_end - 0.005,
        f"Zbroj: 1.000 € -> {eur(value)} ({pct(value / 1000 - 1)}).",
        fontsize=13.5,
        color=RED,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax2 = fig.add_axes([0.06, 0.135, 0.635, 0.13])
    paper(ax2)
    rets = [t["return"] * 100 for t in seq]
    ax2.bar(
        range(1, 5),
        rets,
        color=LOSS,
        alpha=0.8,
        width=0.5,
        edgecolor=PENCIL,
        hatch="//",
    )
    for k, r in enumerate(rets, 1):
        ax2.text(
            k,
            r - 0.8,
            f"{hr(r, 1)} %",
            ha="center",
            va="top",
            fontsize=12.5,
            color=PENCIL,
        )
    ax2.set_ylim(-17, 2)
    ax2.axhline(0, color=PENCIL, lw=1)
    ax2.set_xticks(range(1, 5))
    ax2.set_xticklabels([f"posao {k}" for k in range(1, 5)], fontsize=12)
    ax2.set_ylabel("povrat (%)")
    mem = D.summary()["groups"]["memory"]["per_contender"][C13]
    losers = [t for t in tr if t["return"] <= 0]
    fig.text(
        0.725,
        0.245,
        f"Cijeli MU zapis C13C u AI eri: {len(tr)} poslova, {len(losers)} gubitnih ({hr(100 * len(losers) / len(tr))} %). U cijeloj memorijskoj skupini (MU, WDC, STX) najdulji niz gubitaka je {mem['longest_losing_streak']} poslova zaredom.",
        fontsize=12,
        color=INK,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "ovo je cijena ovog pravila: kad tržište 'pili' gore-dolje, stop izbaci iz posla, a pravilo odmah kupi opet. Nijedan od četiri posla nije 'greška' pravila, to su uobičajeni gubici koje veliki dobici moraju pokriti.",
        y=0.012,
    )
    nums = [
        "MU C13C poslovi: "
        + "; ".join(
            f"{t['entry_date']}->{t['exit_date']} {pct(t['return'])}" for t in seq
        ),
        f"slaganje: 1.000 € x produkt (1 + povrat) = {value:.0f} €",
        f"MU C13C AI era: {len(tr)} poslova, {len(losers)} gubitnih; memorijska skupina najdulji niz gubitaka {mem['longest_losing_streak']} (summary.json)",
    ]
    return finish(
        fig,
        "c03_c13c_failure.png",
        {
            "title": "C13C: stvarni niz od četiri stop-a zaredom na MU (srpanj - kolovoz 2024.)",
            "what_to_see": "Crvene trake su četiri uzastopna posla koja su završila stopom. Zeleni trokut = ulaz, crveni = izlaz. Donji stupci pokazuju svaki gubitak, a desni stupac računa što bi ostalo od 1.000 €.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c04 / c05  (W5)
def _w5_details(ticker: str, t: dict[str, Any]) -> dict[str, Any]:
    f = _frame(ticker)
    rule = D.rule_for(ticker, W5)
    ei = _pos(f, t["entry_date"])
    level = float(rule.level[ei - 1])
    close = f.close.to_numpy()
    bi = None
    for j in range(ei - 1, max(ei - 60, 1), -1):
        if close[j] > level and close[j - 1] <= level:
            bi = j
            break
    return {"f": f, "ei": ei, "level": level, "bi": bi, "ri": ei - 1}


def _w5_pool() -> list[tuple[str, dict[str, Any]]]:
    return [(tk, t) for tk in ["MU", "WDC", "STX"] for t in D.sleeve(tk, W5).trades]


def _draw_w5(
    ticker: str, t: dict[str, Any], success: bool
) -> tuple[Any, dict[str, Any]]:
    d = _w5_details(ticker, t)
    f, ei, level, bi, ri = d["f"], d["ei"], d["level"], d["bi"], d["ri"]
    xi = _pos(f, t["exit_date"])
    a = max(0, (bi if bi is not None else ei - 8) - 14)
    b = min(len(f), xi + 12)
    seg = f.iloc[a:b]
    sma50 = f.close.rolling(50).mean()
    fig = canvas(
        9.0,
        f"W5 proboj i povratni test: stvarni {'dobitni' if success else 'gubitni'} posao ({ticker})",
        f"{ticker}, kupnja {day(t['entry_date'])}, izlaz {day(t['exit_date'])}. Odabir po pravilu: "
        + (
            "dobitni posao najbliži medijanu dobitnih W5 poslova u memorijskoj skupini (MU, WDC, STX), AI era."
            if success
            else "posao zaustavljen stopom (trajao najmanje 3 dana), najbliži medijanu gubitaka od stopa u memorijskoj skupini, AI era."
        ),
    )
    ax = fig.add_axes([0.06, 0.13, 0.635, 0.735])
    paper(ax)
    xs = candles(ax, seg, width=0.6)
    ax.plot(
        xs,
        sma50.iloc[a:b].to_numpy(),
        color=INK,
        lw=1.8,
        ls="--",
        label="SMA50 (izlazni prosjek)",
    )
    ax.axhline(level, color=ORANGE, lw=2.6, zorder=2)
    ax.axhspan(level, level * 1.015, color=ORANGE, alpha=0.2, zorder=1)
    stop = level * 0.97
    ax.hlines(
        stop,
        ei - a - 0.3,
        xi - a + 0.3,
        color=RED,
        lw=2.6,
        zorder=6,
        label="stop: 3 % ispod razine",
    )
    ymin, ymax = float(seg.low.min()), float(seg.high.max())
    lo, hi = min(ymin, stop) * 0.96, ymax * 1.06
    ax.set_ylim(lo, hi)
    hi_a, lo_a = seg.high.to_numpy(), seg.low.to_numpy()
    near = lambda r: int(((lo_a[r] <= level * 1.05) & (hi_a[r] >= level * 0.99)).sum())
    left = near(slice(0, 9)) <= near(slice(len(seg) - 9, len(seg)))
    ax.text(
        0.4 if left else len(seg) - 0.6,
        level * 1.02,
        f"razina (zadnji potvrđeni vrh) {usd(level)}",
        color=ORANGE,
        fontsize=12.5,
        va="bottom",
        ha="left" if left else "right",
    )
    off = (hi - lo) * 0.065
    if bi is not None:
        badge(ax, bi - a, float(f.close.iloc[bi]) + off, 1, INK)
    badge(ax, ri - a, float(f.close.iloc[ri]) + off, 2, ORANGE)
    badge(ax, ei - a, t["raw_entry"] - off, 3, WIN)
    badge(ax, xi - a, t["raw_exit"] - off, 4, LOSS if t["return"] < 0 else WIN)
    ax.scatter(
        [ei - a],
        [t["raw_entry"]],
        marker="^",
        s=250,
        color=WIN,
        edgecolors=PENCIL,
        zorder=10,
    )
    ax.scatter(
        [xi - a],
        [t["raw_exit"]],
        marker="v",
        s=250,
        color=LOSS,
        edgecolors=PENCIL,
        zorder=10,
    )
    date_ticks(ax, seg.index, 9, "{d}. {m}.")
    ax.set_ylabel("cijena (USD)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    why = (
        "zatvaranje ispod SMA50"
        if t["reason"] == "signal"
        else (
            "stop (razina - 3 %), uz jaz prema dolje"
            if t["detail"] == "gap_stop"
            else "cijena je dotaknula stop (razina - 3 %)"
        )
    )
    risk = 1 - stop / t["raw_entry"]
    steps = [
        (
            "1",
            INK,
            (
                f"PROBOJ: zatvaranje {usd(float(f.close.iloc[bi]))} iznad razine ({day(f.index[bi])}). "
                if bi is not None
                else ""
            )
            + "Razina je zadnji potvrđeni vrh, mjesto gdje su prodavači ranije zaustavili cijenu.",
        ),
        (
            "2",
            ORANGE,
            f"POVRATNI TEST ({day(f.index[ri])}): cijena se vratila do razine (unutar 1,5 % iznad) i zatvorila iznad nje: razina izgleda kao novi pod.",
        ),
        (
            "3",
            WIN,
            f"KUPNJA sljedeće jutro po {usd(t['raw_entry'])}. Stop {usd(stop)} je {pct(-risk, 1, False)} ispod ulaza: najgori slučaj oko {eur(1000 * risk)} na 1.000 €.",
        ),
        (
            "4",
            LOSS if t["return"] < 0 else WIN,
            f"IZLAZ {day(t['exit_date'])} po {usd(t['raw_exit'])} ({why}). Rezultat s 1.000 €: {pct(t['return'])} = {eur(1000 * t['return'])}.",
        ),
    ]
    side_notes(fig, steps, top=0.855, x=0.725, size=12.5, width=38, height_in=9.0)
    return fig, {"level": level, "stop": stop, "bi": bi, "f": f}


def c04_breakout_retest() -> str:
    allw = _w5_pool()
    pool = [(tk, t) for tk, t in allw if t["return"] > 0 and t["bars_held"] >= 5]
    med = float(np.median([t["return"] for _, t in allw if t["return"] > 0]))
    tk, t = nearest_to(pool, lambda x: x[1]["return"], med)
    fig, info = _draw_w5(tk, t, True)
    summ = D.summary()["groups"]["memory"]["per_contender"][W5]
    bottom_note(
        fig,
        f"u memorijskoj skupini W5 dobije samo {hr(100 * summ['hit_rate'])} % poslova, ali je prosječan dobitak {pct(summ['avg_win_pct'], 0)}, a prosječan gubitak {pct(summ['avg_loss_pct'], 1)}. Zato uz samo {summ['trades']} poslova dobit nose rijetki veliki dobici.",
        y=0.012,
    )
    nums = [
        f"{tk} W5 posao: ulaz {t['entry_date']} {t['raw_entry']:.2f}, izlaz {t['exit_date']} {t['raw_exit']:.2f}, povrat nakon troška {pct(t['return'])}",
        f"razina (zadnji potvrđeni vrh) {info['level']:.2f}, stop = razina x 0,97 = {info['stop']:.2f}",
        f"medijan dobitnih W5 poslova (MU, WDC, STX, AI era) {pct(med)}",
        f"memorijska skupina W5: {summ['trades']} poslova, hit rate {summ['hit_rate']:.3f}, prosječni dobitak {summ['avg_win_pct']:.3f}, prosječni gubitak {summ['avg_loss_pct']:.3f} (summary.json)",
    ]
    return finish(
        fig,
        "c04_breakout_retest.png",
        {
            "title": f"W5 proboj i povratni test: stvarni dobitni posao ({tk})",
            "what_to_see": "Narančasta crta = razina (zadnji potvrđeni vrh), narančasti pojas = zona 1,5 % iznad nje. Brojevi 1 do 4 prate slijed: proboj, povratni test, kupnja sa stopom 3 % ispod razine, izlaz.",
            "numbers_used": nums,
        },
    )


def c05_breakout_failure() -> str:
    allw = _w5_pool()
    pool = [(tk, t) for tk, t in allw if t["return"] <= 0 and t["reason"] == "stop"]
    med = float(np.median([t["return"] for _, t in pool]))
    allstops = len(pool)
    pool = [(tk, t) for tk, t in pool if t["bars_held"] >= 3]
    tk, t = nearest_to(pool, lambda x: x[1]["return"], med)
    fig, info = _draw_w5(tk, t, False)
    summ = D.summary()["groups"]["memory"]["per_contender"][W5]
    bottom_note(
        fig,
        f"od {len(allw)} W5 poslova na MU, WDC i STX u AI eri njih {allstops} završi gubitkom na stopu. Gubitak je mali, ali razina koja je izgledala kao novi pod nije držala. Prosječan gubitak skupine je {pct(summ['avg_loss_pct'], 1)}.",
        y=0.012,
    )
    nums = [
        f"{tk} W5 posao: ulaz {t['entry_date']} {t['raw_entry']:.2f}, izlaz {t['exit_date']} {t['raw_exit']:.2f}, povrat nakon troška {pct(t['return'])}",
        f"razina {info['level']:.2f}, stop {info['stop']:.2f}",
        f"MU+WDC+STX W5 poslovi AI ere: {len(allw)}; gubitni stopom: {allstops}; medijan tih gubitaka {pct(med)}",
        f"memorijska skupina W5 prosječni gubitak {summ['avg_loss_pct']:.3f} (summary.json)",
    ]
    return finish(
        fig,
        "c05_breakout_failure.png",
        {
            "title": f"W5 kad ne uspije: stvarni gubitak ({tk})",
            "what_to_see": "Isti crtež kao c04, ali nakon povratnog testa cijena nije ostala iznad razine nego je dotaknula stop 3 % ispod nje.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c06  (W3 ranking)
W3 = "W3_MOM_RANK_WEEKLY"


def _w3_fridays(group: str) -> list[dict[str, Any]]:
    """Every AI-era Friday decision of W3 in ``group``: 20-day return per name, held-set and the real next 4 weeks."""
    names = D.groups()[group]
    bars = {t: _bars(t) for t in names}
    ser = {t: pd.Series(b.close, index=b.dates) for t, b in bars.items()}
    opn = {t: pd.Series(b.open, index=b.dates) for t, b in bars.items()}
    ret20 = {t: s / s.shift(20) - 1 for t, s in ser.items()}
    sma50 = {t: s.rolling(50).mean() for t, s in ser.items()}
    ref = ser[names[0]]
    for t in names:
        if len(ser[t]) > len(ref):
            ref = ser[t]
    last = ref.index[-1]
    out = []
    for d in ref.index:
        if d < AI_START or d.weekday() != 4:
            continue
        row = {}
        for t in names:
            if d not in ser[t].index:
                continue
            j = ser[t].index.get_loc(d)
            r = ret20[t].iloc[j]
            if np.isnan(r) or j + 20 >= len(ser[t]):
                continue
            fwd = ser[t].iloc[j + 20] / opn[t].iloc[j + 1] - 1
            row[t] = {
                "r20": float(r),
                "above50": bool(ser[t].iloc[j] > sma50[t].iloc[j]),
                "fwd": float(fwd),
                "fill": opn[t].index[j + 1],
            }
        m = len(row)
        if m < 5:
            continue
        k = max(1, math.ceil(m / 3 - 1e-9))
        order = sorted(row, key=lambda t: -row[t]["r20"])
        top = order[:k]
        held = [t for t in top if row[t]["above50"]]
        out.append(
            {"date": d, "row": row, "order": order, "top": top, "held": held, "m": m}
        )
    del last
    return out


AI_START = pd.Timestamp("2023-01-01")


def c06_momentum_rank() -> str:
    group = "ai_chips_logic"
    fr = [x for x in _w3_fridays(group) if x["held"]]
    for x in fr:
        x["excess"] = float(
            np.mean([x["row"][t]["fwd"] for t in x["held"]])
            - np.mean([v["fwd"] for v in x["row"].values()])
        )
    med = float(np.median([x["excess"] for x in fr]))
    pick = nearest_to(fr, lambda x: x["excess"], med)
    share_pos = float(np.mean([x["excess"] > 0 for x in fr]))
    mean_ex = float(np.mean([x["excess"] for x in fr]))
    row, order, top, held = pick["row"], pick["order"], pick["top"], pick["held"]
    d = pick["date"]
    fig = canvas(
        9.4,
        f"W3 tjedni rang zamaha: stvarni petak {day(d)} (skupina: AI čipovi i logika)",
        "Svakog petka poredamo dionice skupine po prinosu zadnjih 20 dana; kupujemo vodeću trećinu (ako je iznad SMA50) i zadržavamo dok ne ispadne iz gornje polovice.",
    )
    ax1 = fig.add_axes([0.075, 0.2, 0.30, 0.63])
    ax2 = fig.add_axes([0.435, 0.2, 0.30, 0.63])
    for ax in (ax1, ax2):
        paper(ax)
    ys = np.arange(len(order))[::-1]
    r20 = [row[t]["r20"] * 100 for t in order]
    cols = [WIN if t in held else (ORANGE if t in top else LIGHT) for t in order]
    ax1.barh(ys, r20, color=cols, edgecolor=PENCIL, height=0.62)
    ax1.set_yticks(ys)
    ax1.set_yticklabels(order, fontsize=12.5)
    ax1.set_xlabel("prinos zadnjih 20 dana (%) do petka", fontsize=12)
    ax1.set_title("1. Rang u petak (zatvaranje)", loc="left", fontsize=14, color=INK)
    for y, v in zip(ys, r20):
        ax1.text(
            v + (1 if v >= 0 else -1),
            y,
            f"{hr(v, 1)} %",
            va="center",
            ha="left" if v >= 0 else "right",
            fontsize=11,
        )
    ax1.set_xlim(min(r20) - 12, max(r20) + 22)
    k = len(top)
    ax1.axhline(ys[k - 1] - 0.5, color=RED, ls="--", lw=1.6)
    ax1.text(
        max(r20) + 21,
        ys[k - 1] + 0.45,
        f"vodeća trećina\n= {k} od {len(order)}",
        color=RED,
        fontsize=11.5,
        ha="right",
        va="bottom",
    )
    f2 = [row[t]["fwd"] * 100 for t in order]
    ax2.barh(ys, f2, color=cols, edgecolor=PENCIL, height=0.62)
    ax2.set_yticks(ys)
    ax2.set_yticklabels([])
    ax2.set_xlabel("što se dogodilo sljedeća 4 tjedna (%)", fontsize=12)
    ax2.set_title(
        "2. Stvarnost: ponedjeljak -> 20. dan poslije",
        loc="left",
        fontsize=14,
        color=INK,
    )
    for y, v in zip(ys, f2):
        ax2.text(
            v + (1 if v >= 0 else -1),
            y,
            f"{hr(v, 1)} %",
            va="center",
            ha="left" if v >= 0 else "right",
            fontsize=11,
        )
    allm = float(np.mean(f2))
    hm = float(np.mean([row[t]["fwd"] * 100 for t in held]))
    ax2.axvline(allm, color=PENCIL, ls=":", lw=2)
    ax2.axvline(hm, color=WIN, ls="--", lw=2)
    ax2.set_xlim(min(f2) - 14, max(f2) + 26)
    ax2.axhline(ys[k - 1] - 0.5, color=RED, ls="--", lw=1.6)
    steps = [
        (
            "1",
            WIN,
            f"Zeleno = vodeća trećina I iznad SMA50: W3 tih {len(held)} kupuje ({', '.join(held)}), svaka s vlastitih 1.000 €. Narančasto (ako ga ima) = u trećini, ali ispod SMA50: ne kupuje se.",
        ),
        (
            "2",
            WIN,
            f"Zelena crtkana crta: prosjek kupljenih = {pct(hm / 100)}; točkasta: prosjek svih {len(order)} dionica = {pct(allm / 100)}. Na 1.000 € po kupljenoj dionici to je {eur(10 * hm)} u 4 tjedna.",
        ),
        (
            "3",
            RED,
            f"Ovaj petak je odabran po pravilu: izlazi najbliži medijanu (prednost vodećih nad prosjekom skupine {pct(med, 1)} u 4 tjedna). Preko svih {len(fr)} petaka AI ere: prosječna prednost {pct(mean_ex, 1)}, a vodeći su bili bolji od skupine u {hr(100 * share_pos)} % petaka.",
        ),
    ]
    side_notes(fig, steps, top=0.83, x=0.785, size=12, width=33, height_in=9.4)
    bottom_note(
        fig,
        "rang zamaha je tanak signal: u većini petaka prednost vodećih je mala, a ponekad negativna. To je opis, ne novi test: pravi rezultat pravila W3 (42 posla u memoriji, očekivanje +113 € po poslu) je u c12 i c14.",
        y=0.012,
    )
    nums = [
        f"skupina ai_chips_logic ({', '.join(D.groups()[group])}); petak {d.date()}; 20-dnevni prinosi iz CSV-a (zatvaranje)",
        "stvarnost = zatvaranje 20. trgovačkog dana nakon petka / otvaranje sljedećeg ponedjeljka - 1 (izračun iz CSV-a, bez troškova)",
        f"petaka AI ere s kupljenim imenom: {len(fr)}; prosječna prednost {mean_ex * 100:.2f} pp; udio petaka s prednošću > 0: {share_pos:.3f}; odabrani petak nosi prednost {pick['excess'] * 100:.2f} pp (medijan {med * 100:.2f} pp)",
        "W3 pravilo: top trećina (zaokruženo gore), zatvaranje iznad SMA50, izlaz kad ispadne iz gornje polovice (swing.py)",
    ]
    return finish(
        fig,
        "c06_momentum_rank.png",
        {
            "title": "Tjedni rang zamaha na stvarnom petku (AI čipovi i logika)",
            "what_to_see": "Lijevo: poredak 11 dionica po prinosu zadnjih 20 dana s označenom vodećom trećinom. Desno: što su iste dionice stvarno napravile u sljedeća 4 tjedna. Crtkane crte pokazuju prosjek kupljenih naspram prosjeka cijele skupine.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c07  (W8 IBS)
W8 = "W8_IBS_REVERT"


def c07_ibs() -> str:
    ticker = "MU"
    f = _frame(ticker)
    tr = D.sleeve(ticker, W8).trades
    wins = [t for t in tr if t["return"] > 0 and 3 <= t["bars_held"] <= 5]
    med = float(np.median([t["return"] for t in tr if t["return"] > 0]))
    t = nearest_to(wins, lambda x: x["return"], med)
    ei, xi = _pos(f, t["entry_date"]), _pos(f, t["exit_date"])
    rng = (f.high - f.low).replace(0, np.nan)
    ibs = (f.close - f.low) / rng
    sma200 = f.close.rolling(200).mean()
    a, b = ei - 22, min(len(f), xi + 8)
    seg = f.iloc[a:b]
    si = ei - 1
    fig = canvas(
        9.4,
        "W8 IBS povratak: stvarni MU posao, kratko držanje (dani)",
        f"MU, kupnja {day(t['entry_date'])}, izlaz {day(t['exit_date'])} ({t['bars_held']} dana). Odabir po pravilu: dobitni posao s 3 do 5 dana držanja najbliži medijanu dobitnih MU poslova ({pct(med)}).",
    )
    ax = fig.add_axes([0.06, 0.40, 0.635, 0.45])
    paper(ax)
    xs = candles(ax, seg, width=0.6)
    ax.plot(xs, sma200.iloc[a:b].to_numpy(), color=INK, lw=2.0, label="SMA200")
    ax.scatter(
        [ei - a],
        [t["raw_entry"]],
        marker="^",
        s=240,
        color=WIN,
        edgecolors=PENCIL,
        zorder=10,
    )
    ax.scatter(
        [xi - a],
        [t["raw_exit"]],
        marker="v",
        s=240,
        color=LOSS,
        edgecolors=PENCIL,
        zorder=10,
    )
    ymin, ymax = float(seg.low.min()), float(seg.high.max())
    ax.set_ylim(ymin * 0.96, ymax * 1.07)
    off = (ymax - ymin) * 0.08
    badge(ax, si - a, float(f.high.iloc[si]) + off, 1)
    badge(ax, ei - a, t["raw_entry"] - off, 2, WIN)
    xi_sig = xi - 1
    badge(ax, xi - a, t["raw_exit"] + off, 3, LOSS if t["return"] < 0 else WIN)
    date_ticks(ax, seg.index, 9, "{d}. {m}.")
    ax.set_ylabel("cijena (USD)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    # IBS strip
    ax2 = fig.add_axes([0.06, 0.20, 0.635, 0.14])
    paper(ax2)
    iv = ibs.iloc[a:b].to_numpy()
    ax2.bar(
        xs,
        iv,
        color=[WIN if v > 0.8 else (RED if v < 0.2 else LIGHT) for v in iv],
        width=0.6,
        edgecolor=PENCIL,
        lw=0.6,
    )
    ax2.axhline(0.2, color=RED, ls="--", lw=1.4)
    ax2.axhline(0.8, color=WIN, ls="--", lw=1.4)
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("IBS")
    date_ticks(ax2, seg.index, 9, "{d}. {m}.")
    ax2.set_xlim(ax.get_xlim())
    ibs_sig, ibs_exit = float(ibs.iloc[si]), float(ibs.iloc[xi - 1])
    sig_bar = f.iloc[si]
    ret = t["return"]
    steps = [
        (
            "1",
            RED,
            f"IBS = (zatvaranje - najniže) / (najviše - najniže). Dana {day(f.index[si])}: ({usd(sig_bar.close)} - {usd(sig_bar.low)}) / ({usd(sig_bar.high)} - {usd(sig_bar.low)}) = {hr(ibs_sig, 2)}. Ispod 0,2 znači da je dan zatvoren pri samom dnu raspona, a cijena je iznad SMA200 ({usd(float(sma200.iloc[si]))}).",
        ),
        (
            "2",
            WIN,
            f"KUPNJA sljedeći dan na otvaranju: {usd(t['raw_entry'])}. Ideja: nagli dnevni pad se često malo ispravi.",
        ),
        (
            "3",
            LOSS if ret < 0 else WIN,
            f"IZLAZ {day(t['exit_date'])} po {usd(t['raw_exit'])} (otvaranje dana nakon što je IBS prešao 0,8, najkasnije nakon 5 dana). S 1.000 €: {pct(ret)} = {eur(1000 * ret)}.",
        ),
    ]
    side_notes(fig, steps, top=0.855, x=0.725, size=12, width=38, height_in=9.4)
    # commission teaching box
    sm = D.summary()["groups"]["stocks_all"]["per_contender"][W8]
    exp, tpm = sm["expectancy_eur"], sm["trades_per_month"]
    ax3 = fig.add_axes([0.745, 0.115, 0.235, 0.255])
    paper(ax3, grid=False)
    vals = [exp, 6.0, exp - 6.0]
    ax3.bar([0, 1, 2], vals, color=[WIN, LOSS, ORANGE], edgecolor=PENCIL, width=0.6)
    ax3.axhline(0, color=PENCIL, lw=1)
    for xk, v in zip([0, 1, 2], vals):
        ax3.text(
            xk,
            v + (0.3 if v >= 0 else -0.3),
            eur(v, 1),
            ha="center",
            va="bottom" if v >= 0 else "top",
            fontsize=11.5,
        )
    ax3.set_xticks([0, 1, 2])
    ax3.set_xticklabels(
        ["očekivanje\npo poslu", "2 naloga\npo 3 €", "ostane"], fontsize=10.5
    )
    ax3.set_yticks([])
    ax3.set_ylim(-1.5, exp + 3)
    ax3.set_title("Provizija pojede zaradu", fontsize=12.5, color=RED, loc="left")
    bottom_note(
        fig,
        f"W8 je u prosjeku +{hr(exp, 1)} € po poslu na 1.000 € (trošak 0,025 % po strani već uračunat), ali ima {hr(tpm, 0)} poslova mjesečno. Pretpostavka iz C36 modela: minimalna provizija 3 € po nalogu, nepotvrđeno za Petrov IBKR tarif, nije u glavnom modelu. Kupnja + prodaja = 6 €, što je veći dio od tih {hr(exp, 1)} €: zato je ovo pravilo krhko.",
        y=0.012,
    )
    nums = [
        f"MU W8 posao: ulaz {t['entry_date']} {t['raw_entry']:.2f}, izlaz {t['exit_date']} {t['raw_exit']:.2f}, povrat nakon troška {pct(ret)}; držanje {t['bars_held']} dana",
        f"IBS signalnog dana: {ibs_sig:.3f}; dnevni OHLC iz CSV-a",
        f"W8 na svih 43 dionice (summary.json): {sm['trades']} poslova, {tpm:.2f} mjesečno, očekivanje {exp:.2f} € po poslu, uz trošak 2x {sm['expectancy_eur_cost_2x']:.2f} €, faktor dobiti {sm['profit_factor']:.2f}",
        "provizija 3 € po nalogu: pretpostavka C36 modela (docs/research/GOLD_SILVER_5050_RECAP.md: max(3 EUR, 0,0005 x nominal)), nepotvrđena za Petrov IBKR račun",
    ]
    return finish(
        fig,
        "c07_ibs.png",
        {
            "title": "IBS povratak (W8) na stvarnom MU poslu i zašto je 7 € po poslu krhko",
            "what_to_see": "Gore: svijeće sa signalnim danom (zatvoren pri dnu raspona), kupnjom i izlazom. Sredina: IBS po danima s granicama 0,2 i 0,8. Desno dolje: očekivanje po poslu naspram dva naloga s pretpostavljenom minimalnom provizijom.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c08  (W4 bounce failures)
W4 = "W4_SR_BOUNCE_V2"


def _w4_detail(ticker: str, t: dict[str, Any]) -> dict[str, Any]:
    f = _frame(ticker)
    bars = _bars(ticker)
    rule = D.rule_for(ticker, W4)
    ei = _pos(f, t["entry_date"])
    sg = ei - 1
    a = D.S.atr(bars, 14)
    stop, target = float(rule.stop_arr[sg]), float(rule.target_arr[sg])
    level = (stop + 1.0 * float(a[sg])) / 0.99
    return {"f": f, "ei": ei, "stop": stop, "target": target, "level": level}


def c08_bounce_fail() -> str:
    pool = []
    for tk in ["MU", "WDC", "STX", "RMBS", "SIMO", "NTAP"]:
        for t in D.sleeve(tk, W4).trades:
            pool.append((tk, t))

    def clean_window(tk: str, t: dict[str, Any]) -> bool:
        """Skip examples whose chart window holds a candle spanning more than 35 percent of the price (data-quality doubt)."""
        f = _frame(tk)
        a0, b0 = max(0, _pos(f, t["entry_date"]) - 16), _pos(f, t["exit_date"]) + 6
        seg = f.iloc[a0:b0]
        return bool(((seg.high / seg.low - 1) < 0.35).all())

    losses = [
        (tk, t)
        for tk, t in pool
        if t["return"] <= -0.03 and t["bars_held"] >= 3 and clean_window(tk, t)
    ]
    med = float(np.median([t["return"] for _, t in losses]))
    chosen: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for tk, t in sorted(losses, key=lambda x: abs(x[1]["return"] - med)):
        if tk not in seen:
            chosen.append((tk, t))
            seen.add(tk)
        if len(chosen) == 3:
            break
    sm_mem = D.summary()["groups"]["memory"]["per_contender"][W4]
    sm_all = D.summary()["groups"]["stocks_all"]["per_contender"][W4]
    fig = canvas(
        9.2,
        "Odbijanje od potpore (W4): zašto gubi (tri stvarna gubitna posla)",
        "Cijena dotakne potvrđenu potporu, zatvori iznad visokog dana dodira, kupnja sa stopom ispod zone, cilj je zadnji vrh. Tri gubitka su odabrana po pravilu (vidi napomenu dolje).",
    )
    axes = [fig.add_axes([0.04 + i * 0.318, 0.40, 0.29, 0.43]) for i in range(3)]
    notes: list[str] = []
    for ax, (tk, t) in zip(axes, chosen):
        d = _w4_detail(tk, t)
        f, ei = d["f"], d["ei"]
        xi = _pos(f, t["exit_date"])
        a0, b0 = max(0, ei - 16), min(len(f), xi + 6)
        seg = f.iloc[a0:b0]
        paper(ax)
        xs = candles(ax, seg, width=0.62)
        ax.axhspan(
            d["level"] * 0.99, d["level"] * 1.01, color=GREEN, alpha=0.22, zorder=1
        )
        ax.axhline(d["level"], color=GREEN, lw=2.0)
        ax.hlines(d["stop"], ei - a0 - 0.3, xi - a0 + 0.3, color=RED, lw=2.4, zorder=6)
        ax.hlines(
            d["target"],
            ei - a0 - 0.3,
            xi - a0 + 0.3,
            color=INK,
            lw=2.0,
            ls="--",
            zorder=6,
        )
        ax.scatter(
            [ei - a0],
            [t["raw_entry"]],
            marker="^",
            s=170,
            color=WIN,
            edgecolors=PENCIL,
            zorder=10,
        )
        ax.scatter(
            [xi - a0],
            [t["raw_exit"]],
            marker="v",
            s=170,
            color=LOSS,
            edgecolors=PENCIL,
            zorder=10,
        )
        lo = min(float(seg.low.min()), d["stop"]) * 0.985
        hi = max(float(seg.high.max()), d["target"]) * 1.015
        ax.set_ylim(lo, hi)
        date_ticks(ax, seg.index, 4, "{d}. {m}.")
        ax.tick_params(labelsize=10.5)
        ax.set_title(
            f"{tk}: {pct(t['return'])} ({day(t['entry_date'])})",
            loc="left",
            fontsize=13,
            color=LOSS,
        )
        up = d["target"] / t["raw_entry"] - 1
        dn = 1 - d["stop"] / t["raw_entry"]
        notes.append(
            f"{tk}: cilj {pct(up, 1)} gore, stop {pct(-dn, 1, False)} dolje; ishod {pct(t['return'])}."
        )
    ax0 = axes[0]
    ax0.text(
        0.02,
        0.04,
        "zelena traka = potpora\ncrvena = stop\ncrtkana = cilj",
        transform=ax0.transAxes,
        fontsize=10.5,
        color=PENCIL,
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.25", fc=PAPER, ec="none", alpha=0.9),
    )
    # why-it-loses strip
    ax_b = fig.add_axes([0.06, 0.16, 0.30, 0.15])
    paper(ax_b, grid=False)
    vals = [sm_all["avg_win_eur"], sm_all["avg_loss_eur"]]
    ax_b.bar([0, 1], vals, color=[WIN, LOSS], edgecolor=PENCIL, width=0.55)
    for xk, v in zip([0, 1], vals):
        ax_b.text(
            xk,
            v + (2 if v > 0 else -2),
            f"{'+' if v > 0 else '-'}{hr(abs(v))} €",
            ha="center",
            va="bottom" if v > 0 else "top",
            fontsize=12,
        )
    ax_b.axhline(0, color=PENCIL, lw=1)
    ax_b.set_xticks([0, 1])
    ax_b.set_xticklabels(
        [
            f"prosječan dobitni\nposao ({hr(100 * sm_all['hit_rate'])} % poslova)",
            f"prosječan gubitni\nposao ({hr(100 * (1 - sm_all['hit_rate']))} % poslova)",
        ],
        fontsize=10.5,
    )
    ax_b.set_yticks([])
    ax_b.set_ylim(min(vals) * 1.55, max(vals) * 1.9)
    ax_b.set_title(
        "Svih 43 dionice, AI era (na 1.000 €)", fontsize=12.5, color=INK, loc="left"
    )
    fig.text(
        0.40,
        0.315,
        f"Zašto gubi: cilj (zadnji vrh) ograničava dobitak na mali iznos, a stop mora biti ispod zone s dodatnim 1 ATR prostora, pa je gubitak veći od dobitka. "
        f"Pobjeđuje u {hr(100 * sm_all['hit_rate'])} % poslova, ali očekivanje je tek {hr(sm_all['expectancy_eur'], 1)} € po poslu (faktor dobiti {hr(sm_all['profit_factor'], 2)}), uz trošak 2x {hr(sm_all['expectancy_eur_cost_2x'], 1)} €. "
        f"U memorijskoj skupini je negativno: {hr(sm_mem['expectancy_eur'], 1)} € po poslu ({sm_mem['trades']} poslova). Test lažnih razina potvrđuje isto: prave razine ne odbijaju cijenu ništa češće od nasumičnih (c11).",
        fontsize=12.5,
        color=RED,
        va="top",
        ha="left",
        wrap=True,
    )
    fig.text(
        0.40,
        0.175,
        "  ".join(notes),
        fontsize=11,
        color=PENCIL,
        va="top",
        ha="left",
        wrap=True,
    )
    bottom_note(
        fig,
        "'potpora drži' zvuči logično jer pamtimo slučajeve u kojima je držala. Odabir primjera: gubici od najmanje 3 % koji su trajali najmanje 3 dana, najbliži medijanu, svaki na drugoj dionici (MU, WDC, STX, RMBS, SIMO, NTAP), bez prozora sa sumnjivom svijećom. Brojke pokazuju da potvrđena razina nije bolja od nasumične crte.",
        y=0.012,
    )
    nums = [
        "tri W4 posla: "
        + "; ".join(
            f"{tk} {t['entry_date']}->{t['exit_date']} {pct(t['return'])}"
            for tk, t in chosen
        ),
        f"W4 svih 43 dionice (summary.json): {sm_all['trades']} poslova, hit rate {sm_all['hit_rate']:.3f}, prosječni dobitak {sm_all['avg_win_eur']:.1f} €, prosječni gubitak {sm_all['avg_loss_eur']:.1f} €, očekivanje {sm_all['expectancy_eur']:.2f} € (2x trošak {sm_all['expectancy_eur_cost_2x']:.2f} €), faktor dobiti {sm_all['profit_factor']:.2f}",
        f"W4 memorijska skupina: {sm_mem['trades']} poslova, očekivanje {sm_mem['expectancy_eur']:.1f} €, faktor dobiti {sm_mem['profit_factor']:.2f}",
        f"medijan gubitaka >= 3 % (>= 3 dana) u uzorku: {pct(med)}",
    ]
    return finish(
        fig,
        "c08_bounce_fail.png",
        {
            "title": "Odbijanje od potpore: tri stvarna gubitka i zašto pravilo gubi",
            "what_to_see": "Gore: tri stvarna W4 posla sa zonom potpore (zeleno), stopom (crveno) i ciljem (crtkano). Dolje lijevo: prosječan dobitak i gubitak na svih 43 dionice. Dolje desno: objašnjenje i brojke.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c09  (market mechanics on a real chart)
W6 = "W6_MM_SWEEP_SHIFT"
CHIP_GROUPS = ["memory", "mem_interface_storage", "equipment", "ai_chips_logic"]


def _w6_details(ticker: str, t: dict[str, Any]) -> dict[str, Any]:
    bars = _bars(ticker)
    f = _frame(ticker)
    rule = D.rule_for(ticker, W6)
    p = rule.params
    sig = _pos(f, t["entry_date"]) - 1
    highs, lows = D.S.pivot_lists(bars.high, bars.low, int(p["pivot"]))
    atr = D.S.atr(bars, int(p["atr_n"]))
    stop, target = float(rule.stop_arr[sig]), float(rule.target_arr[sig])
    sweep_low = stop + p["atr_mult"] * float(atr[sig])
    cand = [
        j
        for j in range(sig - int(p["sweep_window"]) + 1, sig + 1)
        if abs(bars.low[j] - sweep_low) < 1e-6
    ]
    assert cand, "sweep bar not found"
    sw = cand[-1]
    hp = sum(1 for h in highs if h[0] <= sw - 1)
    lp = sum(1 for lo in lows if lo[0] <= sw - 1)
    sh_c, sh_p, sh = highs[hp - 1]
    sl_c, sl_p, sl = lows[lp - 1]
    swept = None
    for _, pb, v in lows[max(0, lp - int(p["sweep_levels"])) : lp]:
        if bars.low[sw] < v and bars.close[sw] > v:
            swept = (pb, v)
    assert swept is not None
    hp2 = sum(1 for h in highs if h[0] <= sig)
    lower_high = None
    for j in range(hp2 - 1, 0, -1):
        if highs[j][2] < highs[j - 1][2]:
            lower_high = (highs[j][1], highs[j][2])
            break
    assert lower_high is not None
    # demand zone (W7 definition, drawn for teaching): last bearish candle at or before the sweep bar
    m = sw
    while m > 0 and not (bars.close[m] < bars.open[m]):
        m -= 1
    return {
        "f": f,
        "sig": sig,
        "sw": sw,
        "sh": (sh_p, sh),
        "sl": (sl_p, sl),
        "swept": swept,
        "lower_high": lower_high,
        "stop": stop,
        "target": target,
        "zone": (m, float(bars.low[m]), float(bars.high[m])),
        "wsma": rule.wsma_arr,
    }


def c09_mm_example() -> str:
    chip = [t for g in CHIP_GROUPS for t in D.groups()[g]]
    pool = []
    for tk in chip:
        for t in D.sleeve(tk, W6).trades:
            pool.append((tk, t))
    winners = [
        (tk, t)
        for tk, t in pool
        if t["return"] > 0
        and t["partial"]
        and t["bars_held"] >= 8
        and t["reason"] != "end"
    ]
    med = float(np.median([t["return"] for _, t in pool if t["return"] > 0]))

    def ok(tk: str, t: dict[str, Any]) -> bool:
        try:
            _w6_details(tk, t)
        except AssertionError:
            return False
        f = _frame(tk)
        a0, b0 = max(0, _pos(f, t["entry_date"]) - 60), _pos(f, t["exit_date"]) + 4
        seg = f.iloc[a0:b0]
        return bool(((seg.high / seg.low - 1) < 0.35).all())

    winners = [x for x in winners if ok(*x)]
    tk, t = nearest_to(winners, lambda x: x[1]["return"], med)
    d = _w6_details(tk, t)
    f, sig, sw = d["f"], d["sig"], d["sw"]
    xi = _pos(f, t["exit_date"])
    ei = sig + 1
    first = min(d["sh"][0], d["sl"][0], sw) - 8
    a0, b0 = max(0, first), min(len(f), xi + 6)
    seg = f.iloc[a0:b0]
    fig = canvas(
        9.8,
        f"Mehanika tržišta na stvarnom grafu: slijed pravila W6 ({tk})",
        f"{tk}, signal {day(f.index[sig])}, kupnja {day(t['entry_date'])}, izlaz {day(t['exit_date'])}. Odabir po pravilu: dobitni W6 posao s polovičnim izlazom, najbliži medijanu dobitnih W6 poslova na čip dionicama ({pct(med)}).",
    )
    ax = fig.add_axes([0.06, 0.12, 0.635, 0.73])
    paper(ax)
    xs = candles(ax, seg, width=0.6)
    sh_x, sh_y = max(d["sh"][0] - a0, 0), d["sh"][1]
    sl_x, sl_y = max(d["sl"][0] - a0, 0), d["sl"][1]
    mid = sl_y + 0.5 * (sh_y - sl_y)
    left = min(sh_x, sl_x)
    ax.add_patch(
        Rectangle(
            (left, mid),
            sig - a0 - left + 0.4,
            sh_y - mid,
            fc="#fde2de",
            ec="none",
            alpha=0.55,
            zorder=0,
        )
    )
    ax.add_patch(
        Rectangle(
            (left, sl_y),
            sig - a0 - left + 0.4,
            mid - sl_y,
            fc="#dcefe0",
            ec="none",
            alpha=0.75,
            zorder=0,
        )
    )
    ax.hlines([sh_y, sl_y], left, sig - a0 + 0.4, color=GREY, lw=1.3)
    ax.hlines(mid, left, sig - a0 + 0.4, color=GREY, lw=1.3, ls=":")
    ax.plot(
        xs,
        d["wsma"][a0:b0],
        color=INK,
        lw=1.6,
        ls="--",
        label="tjedni prosjek 10 tjedana",
    )
    # swept low
    sp_x, sp_y = max(d["swept"][0] - a0, 0), d["swept"][1]
    ax.hlines(sp_y, sp_x, sw - a0 + 1.5, color=ORANGE, lw=2.2)
    ring(ax, sw - a0, float(f.low.iloc[sw]), ORANGE, 520)
    # lower high
    lh_x, lh_y = max(d["lower_high"][0] - a0, 0), d["lower_high"][1]
    ax.hlines(lh_y, lh_x, sig - a0 + 1.2, color=INK, lw=2.2)
    # demand zone
    zm, zl, zh = d["zone"]
    ax.add_patch(
        Rectangle(
            (zm - a0 - 0.4, zl),
            sig - a0 - (zm - a0) + 1.2,
            zh - zl,
            fc="#cfe3ff",
            ec=INK,
            lw=1.2,
            alpha=0.65,
            zorder=1,
        )
    )
    ax.hlines(d["stop"], ei - a0 - 0.3, xi - a0 + 0.3, color=RED, lw=2.4, zorder=6)
    ax.hlines(
        d["target"], ei - a0 - 0.3, xi - a0 + 0.3, color=WIN, lw=2.2, ls="--", zorder=6
    )
    ax.scatter(
        [ei - a0],
        [t["raw_entry"]],
        marker="^",
        s=240,
        color=WIN,
        edgecolors=PENCIL,
        zorder=10,
    )
    ax.scatter(
        [xi - a0],
        [t["raw_exit"]],
        marker="v",
        s=240,
        color=LOSS,
        edgecolors=PENCIL,
        zorder=10,
    )
    ymin, ymax = (
        min(float(seg.low.min()), d["stop"]),
        max(float(seg.high.max()), d["target"]),
    )
    ax.set_ylim(ymin * 0.97, ymax * 1.07)
    ax.set_xlim(-1, len(seg) + 0.5)
    span = ymax * 1.07 - ymin * 0.97
    date_ticks(ax, seg.index, 9, "{d}. {m}.")
    ax.set_ylabel("cijena (USD)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    badge(ax, left + 0.2, sh_y + span * 0.04, 1, GREY)
    badge(ax, left + 0.2, mid + span * 0.0, 2, GREY)
    badge(ax, sw - a0, float(f.low.iloc[sw]) - span * 0.055, 3, ORANGE)
    badge(ax, sig - a0, lh_y + span * 0.05, 4, INK)
    badge(ax, zm - a0 - 1.0, zh + span * 0.07, 5, INK)
    badge(ax, ei - a0, t["raw_entry"] - span * 0.06, 6, WIN)
    badge(ax, xi - a0, t["raw_exit"] + span * 0.06, 7, LOSS if t["return"] < 0 else WIN)
    ret = t["return"]
    steps = [
        (
            "1",
            GREY,
            f"RASPON: zadnji potvrđeni vrh ({usd(sh_y)}) i dno ({usd(sl_y)}) (pivot = 5 svijeća sa svake strane, poznat tek 5 dana kasnije).",
        ),
        (
            "2",
            GREY,
            f"SREDINA raspona {usd(mid)}: iznad = 'skupo' (premium, crveno), ispod = 'jeftino' (diskont, zeleno). Pravilo traži cijenu u diskontu.",
        ),
        (
            "3",
            ORANGE,
            f"SWEEP: svijeća ({day(f.index[sw])}) je probila raniji pivot-dno {usd(sp_y)} (najniže {usd(float(f.low.iloc[sw]))}), ali je zatvorila iznad njega.",
        ),
        (
            "4",
            INK,
            f"PROMJENA SMJERA: zatvaranje {usd(float(f.close.iloc[sig]))} iznad zadnjeg nižeg vrha {usd(lh_y)} ({day(f.index[sig])}). Tjedni prosjek 10 tjedana mora biti ispod cijene.",
        ),
        (
            "5",
            INK,
            "ZONA POTRAŽNJE (nacrtano po definiciji W7): raspon zadnje silazne svijeće prije rasta; ne koristi se za ulaz u W6.",
        ),
        (
            "6",
            WIN,
            f"KUPNJA po {usd(t['raw_entry'])}; stop {usd(d['stop'])} (ispod dna sweepa - 0,5 ATR), cilj {usd(d['target'])} (crtkano).",
        ),
        (
            "7",
            LOSS if ret < 0 else WIN,
            f"Pola se proda na cilju, ostatak prati. Zbroj posla s 1.000 €: {pct(ret)} = {eur(1000 * ret)}; izlaz {day(t['exit_date'])}.",
        ),
    ]
    side_notes(
        fig, steps, top=0.855, x=0.725, size=11.5, width=41, height_in=9.8, gap=0.55
    )
    bottom_note(
        fig,
        "ovo je primjer za učenje slijeda, a c10 pokazuje što je slijed stvarno donio: na svih 55 papira u AI eri nije se pokazala pouzdana prednost. U memorijskoj skupini je W6 imao 11 poslova i prosjek -40 € po poslu.",
        y=0.012,
    )
    mem6 = D.summary()["groups"]["memory"]["per_contender"][W6]
    nums = [
        f"{tk} W6 posao: ulaz {t['entry_date']} {t['raw_entry']:.2f}, izlaz {t['exit_date']} {t['raw_exit']:.2f}, povrat {pct(ret)}, polovični izlaz na cilju: {t['partial']}",
        f"raspon: vrh {sh_y:.2f}, dno {sl_y:.2f}, sredina {mid:.2f}; sweep dna {sp_y:.2f}; niži vrh {lh_y:.2f}; stop {d['stop']:.2f}; cilj {d['target']:.2f}",
        f"medijan dobitnih W6 poslova na čip dionicama (memorija, sučelja i pohrana, oprema, AI čipovi) {pct(med)}",
        f"W6 memorijska skupina (summary.json): {mem6['trades']} poslova, očekivanje {mem6['expectancy_eur']:.1f} € po poslu",
    ]
    return finish(
        fig,
        "c09_mm_example.png",
        {
            "title": "Mehanika tržišta (sweep, promjena smjera, diskont, zona) na stvarnom grafu",
            "what_to_see": "Siva kutija = zadnji raspon vrh-dno; crvenkasto gornja polovica ('skupo'), zeleno donja ('jeftino'). Narančasti krug = sweep dna. Plava crta = niži vrh koji zatvaranje probija (promjena smjera). Plavi pravokutnik = zona potražnje. Zeleni trokut = kupnja, crvena crta = stop, zelena crtkana = cilj.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c15  (trade return distribution)
def c15_trade_distribution() -> str:
    sm = D.summary()["groups"]["stocks_all"]["per_contender"]
    fig = canvas(
        7.8,
        "Raspodjela poslova: mnogo malih gubitaka, nekoliko velikih dobitaka (svih 43 dionice, AI era)",
        "Svaki stupac je broj poslova s tim povratom nakon troška. Isti stvarni poslovi koji čine rezultate pravila C13C i W5.",
    )
    axes = [fig.add_axes([0.055 + i * 0.49, 0.34, 0.44, 0.47]) for i in range(2)]
    info: dict[str, Any] = {}
    for ax, cid, name, col in zip(
        axes, [C13, W5], ["C13C (W1)", "W5 proboj i povratni test"], [INK, ORANGE]
    ):
        tr = D.pooled_trades(cid)
        ref = sm[cid]
        assert len(tr) == ref["trades"], (len(tr), ref["trades"])
        r = np.array([t["return"] for t in tr]) * 100
        pnl = r * 10  # EUR on 1.000 EUR per trade
        order = np.sort(pnl)[::-1]
        top10 = float(order[:10].sum() / pnl.sum())
        top5 = float(order[:5].sum() / pnl.sum())
        assert abs(top5 - ref["top5_profit_share"]) < 1e-9, (
            top5,
            ref["top5_profit_share"],
        )
        med = float(np.median(r))
        lose = float((r <= 0).mean())
        paper(ax)
        lo, hi, step = -30, 60, 3
        bins = np.arange(lo, hi + step, step)
        clipped = np.clip(r, lo + 0.01, hi - 0.01)
        n, _, patches = ax.hist(clipped, bins=bins, edgecolor=PENCIL, lw=0.8)
        for pch, left in zip(patches, bins[:-1]):
            pch.set_facecolor(LOSS if left < 0 else WIN)
            pch.set_alpha(0.75)
        ax.axvline(0, color=PENCIL, lw=1.4)
        ax.axvline(med, color=INK, lw=2.4, ls="--")
        ax.set_xlabel(
            "povrat posla (%)  (krajnji stupci skupljaju sve izvan raspona)",
            fontsize=11,
        )
        ax.set_ylabel("broj poslova")
        ax.set_title(f"{name}: {len(r)} poslova", loc="left", fontsize=15, color=col)
        ymax = float(n.max())
        ax.set_ylim(0, ymax * 1.32)
        tip(
            ax,
            f"medijan posla: {pct(med / 100)}",
            (med, ymax * 0.55),
            (med + 8, ymax * 0.66),
            color=INK,
            rad=-0.2,
            size=12.5,
        )
        big = int((r > hi).sum())
        info[cid] = dict(
            n=len(r),
            med=med,
            lose=lose,
            top10=top10,
            top5=top5,
            mean=float(r.mean()),
            best=float(r.max()),
            worst=float(r.min()),
            big=big,
            total=float(pnl.sum()),
        )
        ax.text(
            0.98,
            0.95,
            f"gubitnih: {hr(100 * lose)} %\nprosjek: {pct(float(r.mean()) / 100, 1)} = {eur(float(r.mean()) * 10, 1)} po poslu\nnajbolji posao: {pct(float(r.max()) / 100, 0)}\nnajgori: {pct(float(r.min()) / 100, 0)}\n10 najboljih poslova = {hr(100 * top10)} % cijele dobiti",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=11.5,
            color=PENCIL,
            bbox=dict(boxstyle="round,pad=0.3", fc="#fff7d6", ec=GREY, lw=0.8),
        )
    a, b = info[C13], info[W5]
    fig.text(
        0.055,
        0.24,
        f"Što to znači za tebe: C13C ima {a['n']} poslova, {hr(100 * a['lose'])} % ih je gubitnih, a 10 najboljih nosi {hr(100 * a['top10'])} % ukupne dobiti. "
        f"W5 ima {b['n']} poslova, {hr(100 * b['lose'])} % gubitnih, a 10 najboljih nosi {hr(100 * b['top10'])} %. Ako propustiš nekoliko najboljih poslova, rezultat se jako promijeni, a ne znaš unaprijed koji će to biti.",
        fontsize=12.5,
        color=RED,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "'dobit' je ovdje zbroj povrata poslova pomnožen s 1.000 € po poslu (poslovi se ne slažu kamatom na kamatu). Ovo je isti način računanja kao u summary.json (top5 udio provjeren: jednak).",
        y=0.012,
    )
    nums = [
        f"C13C svih 43 dionice AI era: {a['n']} poslova (summary.json: {sm[C13]['trades']}), medijan {a['med']:.2f} %, gubitnih {a['lose']:.3f}, top 5 udio {a['top5']:.3f} (summary: {sm[C13]['top5_profit_share']:.3f}), top 10 udio {a['top10']:.3f}",
        f"W5 svih 43 dionice AI era: {b['n']} poslova (summary.json: {sm[W5]['trades']}), medijan {b['med']:.2f} %, gubitnih {b['lose']:.3f}, top 5 udio {b['top5']:.3f} (summary: {sm[W5]['top5_profit_share']:.3f}), top 10 udio {b['top10']:.3f}",
        f"najbolji/najgori posao: C13C {a['best']:.1f} % / {a['worst']:.1f} %; W5 {b['best']:.1f} % / {b['worst']:.1f} %",
    ]
    return finish(
        fig,
        "c15_trade_distribution.png",
        {
            "title": "Raspodjela povrata poslova za C13C i W5",
            "what_to_see": "Crveni stupci su gubitni poslovi, zeleni dobitni; crtkana crta je medijan. Žuta kutija: udio gubitnih, prosjek, najbolji i najgori posao te koliki dio cijele dobiti nose 10 najboljih poslova.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c22  (position size)
def c22_position_size() -> str:
    t, med, tr = _c13_pick()
    f = _frame("MU")
    ei = _pos(f, t["entry_date"])
    entry = float(t["raw_entry"])
    stop = float(
        D.trail_stop_series(f.high.to_numpy(), ei, ei + 1, t["entry_price"], 0.10)[0]
    )
    dist = entry - stop
    dpct = dist / entry
    # W5 example for a tighter stop (MU, same pick rule as c05)
    allw = _w5_pool()
    pool = [(tk, x) for tk, x in allw if x["return"] <= 0 and x["reason"] == "stop"]
    medl = float(np.median([x["return"] for _, x in pool]))
    pool = [(tk, x) for tk, x in pool if x["bars_held"] >= 3]
    tk5, t5 = nearest_to(pool, lambda x: x[1]["return"], medl)
    d5 = _w5_details(tk5, t5)
    stop5 = d5["level"] * 0.97
    dist5 = t5["raw_entry"] - stop5
    dpct5 = dist5 / t5["raw_entry"]
    account = 5000.0
    fig = canvas(
        9.4,
        "Veličina pozicije: razmak do stopa određuje koliko dionica smiješ kupiti",
        f"Račun {eur(account)}. Pravilo: unaprijed odlučiš koliki gubitak ({pct(0.01, 0, False)}, {pct(0.02, 0, False)} ili {pct(0.03, 0, False)} računa) smiješ izgubiti ako stop pukne, pa iz toga izračunaš veličinu pozicije.",
    )
    ax = fig.add_axes([0.07, 0.40, 0.50, 0.44])
    paper(ax, grid=False)
    risks = [0.01, 0.02, 0.03]
    pos_eur = [account * r / dpct for r in risks]
    risk_eur = [account * r for r in risks]
    xs = np.arange(3)
    ax.bar(xs, [account] * 3, color="#eef0f4", edgecolor=PENCIL, width=0.62)
    ax.bar(xs, pos_eur, color=INK, alpha=0.75, edgecolor=PENCIL, width=0.62)
    ax.text(
        -0.4,
        6350,
        f"siva = cijeli račun {eur(account)}\nplava = iznos kupnje (pozicija)",
        fontsize=11.5,
        color=GREY,
        ha="left",
        va="center",
    )
    for xk, pe, re_ in zip(xs, pos_eur, risk_eur):
        ax.text(
            xk,
            pe + 120,
            f"pozicija {eur(pe)} ({hr(100 * pe / account)} % računa)",
            ha="center",
            va="bottom",
            fontsize=11.5,
            color=INK,
        )
        ax.text(
            xk,
            account + 120,
            f"gubitak ako stop\npukne: {eur(re_)}",
            ha="center",
            va="bottom",
            fontsize=12,
            color=RED,
        )
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [f"rizik {pct(r, 0, False)} računa" for r in risks], fontsize=12.5
    )
    ax.set_ylim(0, account * 1.33)
    ax.set_ylabel("EUR")
    ax.set_title(
        "Stvarni MU primjer (C13C): stop 10 % ispod ulaza",
        loc="left",
        fontsize=14,
        color=INK,
    )
    # price sketch
    ax2 = fig.add_axes([0.63, 0.40, 0.35, 0.44])
    paper(ax2, grid=False)
    ax2.set_xlim(0, 10)
    ax2.set_ylim(stop * 0.93, entry * 1.06)
    ax2.hlines(entry, 1, 9, color=WIN, lw=3)
    ax2.hlines(stop, 1, 9, color=RED, lw=3)
    ax2.annotate(
        "",
        xy=(5, stop),
        xytext=(5, entry),
        arrowprops=dict(arrowstyle="<->", color=PENCIL, lw=2),
    )
    ax2.text(
        5.25,
        (entry + stop) / 2,
        f"razmak {usd(dist)}\n= {pct(dpct, 1, False)}\ncijene ulaza",
        fontsize=12.5,
        color=PENCIL,
        va="center",
    )
    ax2.text(
        1,
        entry + dist * 0.18,
        f"kupnja {usd(entry)}  ({day(t['entry_date'])})",
        fontsize=12,
        color=WIN,
    )
    ax2.text(1, stop - dist * 0.55, f"stop {usd(stop)}", fontsize=12, color=RED)
    ax2.set_xticks([])
    ax2.set_ylabel("cijena MU (USD)")
    ax2.set_title("Odakle razmak", loc="left", fontsize=14, color=INK)
    # table of shares
    rows = []
    for r in risks:
        re_ = account * r
        sh = re_ / dist
        rows.append(
            (
                pct(r, 0, False),
                eur(re_),
                f"{hr(sh, 1)} dionica",
                eur(sh * entry),
                f"{hr(math.floor(sh), 0)} dionica = {eur(math.floor(sh) * entry)}",
            )
        )
    tx = 0.07
    fig.text(
        tx,
        0.325,
        "Račun: gubitak / razmak = broj dionica",
        fontsize=14,
        color=INK,
        fontweight="bold",
        ha="left",
    )
    hdr = [
        "rizik",
        "gubitak ako stop pukne",
        "dionica (razlomljeno)",
        "iznos kupnje",
        "samo cijele dionice",
    ]
    cols_x = [0.07, 0.15, 0.33, 0.50, 0.66]
    for xx, h in zip(cols_x, hdr):
        fig.text(xx, 0.29, h, fontsize=12, color=GREY, ha="left")
    for i, row in enumerate(rows):
        for xx, v in zip(cols_x, row):
            fig.text(xx, 0.255 - i * 0.034, v, fontsize=13, color=PENCIL, ha="left")
    # W5 tighter-stop line
    pe5 = account * 0.01 / dpct5
    fig.text(
        0.07,
        0.125,
        f"Uži stop, veća pozicija za isti rizik: W5 primjer ({tk5}, {day(t5['entry_date'])}): ulaz {usd(t5['raw_entry'])}, stop {usd(stop5)} = samo {pct(dpct5, 1, False)} ispod. Uz rizik 1 % računa ({eur(account * 0.01)}) pozicija bi bila {eur(pe5)} ({hr(100 * pe5 / account)} % računa), dok C13C-ov stop 10 % ispod daje {eur(pos_eur[0])}. Tijesan stop = veća pozicija, ali ga i češće 'okine' običan dnevni šum.",
        fontsize=12.5,
        color=RED,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "primjer s tečajem USD = EUR (kao u projektu); stvarni tečaj, provizije i mogu li se kupiti razlomljene dionice kod IBKR-a su nepotvrđeni. Ovo je matematika veličine pozicije, ne preporuka koliko riskirati. Gubitak veći od stopa moguće je kad cijena preskoči stop (jaz).",
        y=0.012,
    )
    nums = [
        f"MU C13C primjer {t['entry_date']}: ulaz {entry:.2f}, početni stop {stop:.2f} (10 % ispod), razmak {dist:.2f} USD = {dpct * 100:.1f} %",
        "pozicija = račun x rizik / postotak razmaka: "
        + "; ".join(
            f"{pct(r, 0, False)} -> {pe:.0f} €" for r, pe in zip(risks, pos_eur)
        ),
        f"W5 primjer {tk5} {t5['entry_date']}: ulaz {t5['raw_entry']:.2f}, stop {stop5:.2f}, razmak {dpct5 * 100:.1f} %; 1 % rizika -> {pe5:.0f} €",
        "račun 5.000 € i rizik 1, 2, 3 % su ilustrativne vrijednosti za nastavu (zadane u zadatku), ne preporuka",
    ]
    return finish(
        fig,
        "c22_position_size.png",
        {
            "title": "Koliko dionica kupiti: razmak do stopa određuje veličinu pozicije",
            "what_to_see": "Lijevo: račun od 5.000 € i koliki dio ide u poziciju kad riskiraš 1, 2 ili 3 % računa uz stvarni MU razmak do stopa od 10 %. Desno: odakle taj razmak. Dolje: tablica broja dionica i usporedba s tjesnijim W5 stopom.",
            "numbers_used": nums,
        },
    )
