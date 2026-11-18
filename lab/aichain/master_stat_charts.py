"""MASTER charts c10-c14, c16-c21: placebo, scoreboard, equity, contexts, maps, crypto and metals (notebook style)."""

from __future__ import annotations

from typing import Any
from unittest import mock

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image

from lab.aichain import master_data as D
from lab.aichain.master_common import (
    AI_ERA,
    CAPTIONS,
    GREEN,
    GREY,
    INK,
    LIGHT,
    LOSS,
    ORANGE,
    OUT,
    PAPER,
    PENCIL,
    RED,
    ROOT,
    SWING,
    WIN,
    bottom_note,
    canvas,
    day,
    eur,
    finish,
    hr,
    load_json,
    paper,
    pct,
    ring,
    side_notes,
    tip,
)

W = {
    "W1_C13C_ORIG": "W1 C13C",
    "W2_MOM_BREAK_20": "W2 proboj 20 dana",
    "W3_MOM_RANK_WEEKLY": "W3 rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj+test",
    "W6_MM_SWEEP_SHIFT": "W6 sweep",
    "W7_MM_DEMAND_RETEST": "W7 zona",
    "W8_IBS_REVERT": "W8 IBS",
    "B0_BUYHOLD": "kupi i drži",
}
PLACEBO = SWING / "placebo.json"


def _pb() -> dict[str, Any]:
    return load_json(PLACEBO)


# ================================================================================ c10
def c10_mm_reality() -> str:
    pb = _pb()
    ev_ai = pb["mechanics_ai_era"]["events"]
    ev_pre = pb["mechanics_pre_ai_context"]["events"]
    names = {
        "E1_sweep_shift_discount": "sweep + promjena\nsmjera u diskontu",
        "E2_sweep_shift_discount_weekly": "isto + bikovski\ntjedni trend",
        "E3_sweep_shift_discount_weekly_zone": "isto + dodir svježe\nzone potražnje",
        "E4_demand_zone_retest": "prvi povratak u\nsvježu zonu potražnje",
        "E5_bos_trend": "proboj strukture\nu bikovskom trendu",
    }
    hs = ["5", "10", "20"]
    cols = {"5": "#7aa7e6", "10": INK, "20": "#0e2569"}
    fig = canvas(
        8.8,
        "Mehanika tržišta: što je stvarno izmjereno (AI era, 55 papira)",
        "Prednost = koliko je prinos nakon događaja bio bolji od prosjeka iste dionice (postotni bodovi). Crta oko točke = 95 % interval: ako obuhvaća nulu, razlika nije dokaz.",
    )
    ax = fig.add_axes([0.065, 0.31, 0.92, 0.52])
    paper(ax)
    ax.axhline(0, color=PENCIL, lw=1.8)
    xs = np.arange(len(names))
    for hi, h in enumerate(hs):
        off = (hi - 1) * 0.25
        for xi, (k, lab) in enumerate(names.items()):
            b = ev_ai[k]["by_h"][h]
            m = b["mean_excess_vs_ticker_avg"] * 100
            lo, up = [c * 100 for c in b["excess_ci95"]]
            ax.errorbar(
                xi + off,
                m,
                yerr=[[m - lo], [up - m]],
                fmt="o",
                color=cols[h],
                ecolor=cols[h],
                elinewidth=2.4,
                capsize=5,
                ms=9,
                zorder=5,
                label=f"{h} dana poslije" if xi == 0 else None,
            )
            p = ev_pre[k]["by_h"][h]["mean_excess_vs_ticker_avg"] * 100
            ax.scatter(
                [xi + off + 0.09],
                [p],
                marker="D",
                s=46,
                facecolors="none",
                edgecolors=GREY,
                linewidths=1.5,
                zorder=4,
                label="prije 2023. (kontekst)" if (xi == 0 and hi == 0) else None,
            )
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [f"{v}\nn = {ev_ai[k]['n']}" for k, v in names.items()], fontsize=12
    )
    ax.set_ylabel("prednost nad prosjekom dionice (postotni bodovi)")
    ax.legend(loc="upper right", frameon=False, fontsize=12, ncol=2)
    ax.set_ylim(-9, 8.5)
    ax.set_xlim(-0.6, 4.6)
    e4 = ev_ai["E4_demand_zone_retest"]["by_h"]["10"]
    tip(
        ax,
        f"jedini granični slučaj: +{hr(e4['mean_excess_vs_ticker_avg'] * 100, 1)} pp na 10 dana,\ndonja granica samo +{hr(e4['excess_ci95'][0] * 100, 2)} pp; prije 2023. predznak\nje bio suprotan (sive oznake)",
        (3.05, e4["mean_excess_vs_ticker_avg"] * 100),
        (2.55, -5.6),
        rad=0.35,
        size=12,
    )
    tip(
        ax,
        "ispod nule = nakon događaja su dionice bile\nslabije nego inače, ne bolje",
        None,
        (-0.5, 7.0),
        arrow=False,
        size=12,
    )
    all5, all10, all20 = (pb["mechanics_ai_era"]["all_days"][h] for h in hs)
    fig.text(
        0.065,
        0.205,
        f"Usporedba: bilo koji dan u AI eri (svih {hr(all5['n'])} dan-papir parova): prosječan prinos {pct(all5['mean'], 1)} za 5 dana, {pct(all10['mean'], 1)} za 10, {pct(all20['mean'], 1)} za 20 dana, a {hr(100 * all20['hit_rate'])} % dana je u plusu za 20 dana. "
        "To je bik-tržište: gotovo svako pravilo 'koje kupuje' izgleda dobro, zato mjerimo samo prednost nad prosjekom iste dionice.",
        fontsize=12,
        color=INK,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "zaključak iz mjerenja: slijed 'sweep, promjena smjera, diskont' nije dao prednost (većinom ispod nule, svi intervali uz nulu ili ispod nje). Jedini granični slučaj (zona potražnje) nosi tanka donja granica i suprotan predznak prije 2023.: ne može se tvrditi da radi.",
        y=0.012,
    )
    nums = [
        "placebo.json: mechanics_ai_era.events[*].by_h[5|10|20].mean_excess_vs_ticker_avg i excess_ci95 (AI era 2023-01-01 do 2026-10-05)",
        "placebo.json: mechanics_pre_ai_context (2017 do 2022) za sive oznake",
        "n po događaju: "
        + ", ".join(f"{k.split('_')[0]} {ev_ai[k]['n']}" for k in names),
        f"E4 10 dana: {e4['mean_excess_vs_ticker_avg'] * 100:.2f} pp [{e4['excess_ci95'][0] * 100:.2f}; {e4['excess_ci95'][1] * 100:.2f}]",
        f"svi dani: 5d {all5['mean'] * 100:.2f} %, 10d {all10['mean'] * 100:.2f} %, 20d {all20['mean'] * 100:.2f} %, hit rate 20d {all20['hit_rate']:.3f}, n {all5['n']}",
    ]
    return finish(
        fig,
        "c10_mm_reality.png",
        {
            "title": "Mehanika tržišta: izmjerena prednost nad prosjekom (5, 10 i 20 dana)",
            "what_to_see": "Točke su prosječna prednost nakon događaja, crte su 95 % intervali. Plave nijanse = horizont 5, 10 i 20 dana (AI era); sivi rombovi = isti događaj prije 2023. Osim zone potražnje (E4), sve je na ili ispod nule, a intervali obuhvaćaju nulu ili leže u cijelosti ispod nje.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c11
def c11_placebo() -> str:
    pb = _pb()
    a = pb["sr"]["all"]
    fig = canvas(
        8.6,
        "Prave razine naspram nasumičnih: ista stopa dodira i odbijanja",
        f"{hr(a['n_levels'])} stvarnih razina (kraj mjeseca, 44 mjeseca, 55 papira) naspram isto toliko nasumično povučenih crta na istim grafovima.",
    )
    ax = fig.add_axes([0.06, 0.30, 0.42, 0.52])
    paper(ax)
    metrics = [
        ("touch_rate", "dodir u sljedećih\n20 dana"),
        ("bounce_rate", "odbijanje (kad je\ndodirnuta)"),
        ("break_rate", "probijanje (kad je\ndodirnuta)"),
    ]
    x = np.arange(3)
    real = [a["real"][m] * 100 for m, _ in metrics]
    rand = [a["rand"][m] * 100 for m, _ in metrics]
    ax.bar(
        x - 0.19,
        real,
        0.36,
        color=INK,
        alpha=0.85,
        edgecolor=PENCIL,
        label="prave razine (potvrđeni okreti)",
    )
    ax.bar(x + 0.19, rand, 0.36, color=LIGHT, edgecolor=PENCIL, label="nasumične crte")
    for xi, (r1, r2) in enumerate(zip(real, rand)):
        ax.text(
            xi - 0.19, r1 + 1, f"{hr(r1, 1)} %", ha="center", fontsize=12, color=INK
        )
        ax.text(
            xi + 0.19, r2 + 1, f"{hr(r2, 1)} %", ha="center", fontsize=12, color=GREY
        )
    ax.set_xticks(x)
    ax.set_xticklabels([l for _, l in metrics], fontsize=12)
    ax.set_ylabel("%")
    ax.set_ylim(0, 62)
    ax.legend(loc="upper right", frameon=False, fontsize=11.5)
    ax.set_title("Stope", loc="left", fontsize=15, color=INK)
    # differences with CI
    ax2 = fig.add_axes([0.56, 0.30, 0.42, 0.52])
    paper(ax2)
    ax2.axhline(0, color=PENCIL, lw=1.8)
    series = [
        ("diff_vs_rand", "nasumične", INK),
        ("diff_vs_shift", "pomaknute +-3 %", ORANGE),
        ("diff_vs_match", "uparene", GREEN),
    ]
    for si, (key, lab, col) in enumerate(series):
        for mi, (m, _) in enumerate(metrics):
            d = a[key][m]
            v, lo, hi = d["diff"] * 100, d["ci95"][0] * 100, d["ci95"][1] * 100
            ax2.errorbar(
                mi + (si - 1) * 0.22,
                v,
                yerr=[[v - lo], [hi - v]],
                fmt="o",
                color=col,
                ecolor=col,
                elinewidth=2.4,
                capsize=5,
                ms=9,
                label=f"naspram: {lab}" if mi == 0 else None,
            )
    ax2.set_xticks(x)
    ax2.set_xticklabels([l for _, l in metrics], fontsize=12)
    ax2.set_ylabel("razlika: prave minus lažne (postotni bodovi)")
    ax2.set_ylim(-4.2, 7.0)
    ax2.legend(loc="upper left", frameon=False, fontsize=11.5)
    ax2.set_title("Razlika i 95 % interval", loc="left", fontsize=15, color=INK)
    tip(
        ax2,
        "odbijanje i probijanje: svi intervali\nobuhvaćaju nulu, dakle nema dokazane\nrazlike prema nasumičnoj crti",
        None,
        (-0.3, -3.5),
        arrow=False,
        size=11.5,
    )
    br = a["diff_vs_rand"]["bounce_rate"]
    tr = a["diff_vs_rand"]["touch_rate"]
    fig.text(
        0.06,
        0.205,
        f"Običnim riječima: razina koju su 'potvrdili' raniji okreti nije se u ovih {hr(a['n_levels'])} slučajeva ponašala kao pod ili strop. Cijena se od nje odbila u {hr(a['real']['bounce_rate'] * 100, 1)} % slučajeva, a od nasumične crte u {hr(a['rand']['bounce_rate'] * 100, 1)} %. "
        f"Razlika {hr(br['diff'] * 100, 1)} pp (interval {hr(br['ci95'][0] * 100, 1)} do {hr(br['ci95'][1] * 100, 1)}) obuhvaća nulu. Prave razine se čak dodiruju neznatno rjeđe ({hr(tr['diff'] * 100, 1)} pp, interval {hr(tr['ci95'][0] * 100, 1)} do {hr(tr['ci95'][1] * 100, 1)}).",
        fontsize=12.5,
        color=INK,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "razine nisu 'ništa': mogu služiti kao orijentir gdje postaviti stop. Ali nemaju dokazanu moć odbijanja cijene, pa ne smiju biti jedini razlog za kupnju.",
        y=0.012,
    )
    nums = [
        f"placebo.json sr.all: n razina {a['n_levels']}, {a['n_months']} mjeseci; real touch {a['real']['touch_rate']:.4f}, bounce {a['real']['bounce_rate']:.4f}, break {a['real']['break_rate']:.4f}",
        f"nasumične: touch {a['rand']['touch_rate']:.4f}, bounce {a['rand']['bounce_rate']:.4f}, break {a['rand']['break_rate']:.4f}",
        f"razlika odbijanje vs nasumične {br['diff'] * 100:.2f} pp [{br['ci95'][0] * 100:.2f}; {br['ci95'][1] * 100:.2f}]; dodir {tr['diff'] * 100:.2f} pp [{tr['ci95'][0] * 100:.2f}; {tr['ci95'][1] * 100:.2f}]",
        "intervali: bootstrap po kalendarskim mjesecima, 2000 ponavljanja (placebo.json config)",
    ]
    return finish(
        fig,
        "c11_placebo.png",
        {
            "title": "Test lažnih razina: prave naspram nasumičnih",
            "what_to_see": "Lijevo: stope dodira, odbijanja i probijanja za prave i nasumične razine, gotovo jednake. Desno: razlike s 95 % intervalima za tri vrste lažnih razina; za odbijanje i probijanje svi intervali obuhvaćaju nulu.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c12
def c12_scoreboard() -> str:
    sm = D.summary()
    g = sm["groups"]["stocks_all"]
    per = g["per_contender"]
    bh = g["buy_and_hold_reference"]
    ids = [c for c in per if c != "B0_BUYHOLD"]
    elig = {r["contender"]: r["eligible"] for r in g["ranking"]}
    for r in g["not_eligible"]:
        elig[r["contender"]] = False
    fig = canvas(
        8.8,
        "Ploča rezultata: koliko često trguje naspram koliko zarađuje po poslu (svih 43 dionice, AI era)",
        "Svaki mjehur je jedno pravilo. Vodoravno: poslova mjesečno (logaritamska ljestvica). Okomito: očekivani dobitak po poslu na 1.000 € nakon troška. Veličina: ukupni prinos pravila.",
    )
    ax = fig.add_axes([0.065, 0.265, 0.64, 0.565])
    paper(ax)
    ax.set_xscale("log")
    xs = np.logspace(0.3, 2.1, 50)
    for sc in (500, 1000):
        ax.plot(xs, sc / xs, color=GREY, ls=":", lw=1.4)
        ax.text(
            47,
            sc / 47 * 1.06,
            f"{eur(sc)} mjesečno",
            color=GREY,
            fontsize=11,
            rotation=-9,
        )
    pos = {
        "W1_C13C_ORIG": (0, 0.0),
        "W2_MOM_BREAK_20": (6, -16),
        "W3_MOM_RANK_WEEKLY": (0, 0),
        "W4_SR_BOUNCE_V2": (0, 0),
        "W5_SR_BREAKOUT_RETEST": (0, 0),
        "W6_MM_SWEEP_SHIFT": (0, 0),
        "W7_MM_DEMAND_RETEST": (0, 0),
        "W8_IBS_REVERT": (0, 0),
    }
    for cid in ids:
        v = per[cid]
        x, y = v["trades_per_month"], v["expectancy_eur"]
        size = 400 + 2600 * max(v["total_return"], 0.01)
        ax.scatter(
            [x],
            [y],
            s=size,
            color=(INK if elig[cid] else RED),
            alpha=0.35,
            edgecolor=PENCIL,
            linewidths=1.5,
            zorder=5,
        )
        ax.text(
            x,
            y,
            W[cid].split(" ")[0],
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color=PENCIL,
            zorder=7,
        )
    ax.set_xlim(2, 130)
    ax.set_ylim(-5, 92)
    ax.set_xticks([2, 3, 5, 10, 20, 30, 50, 100])
    ax.set_xticklabels(["2", "3", "5", "10", "20", "30", "50", "100"])
    ax.set_xlabel("poslova mjesečno (svih 43 sleevea zajedno)")
    ax.set_ylabel("očekivanje po poslu (€ na 1.000 €)")
    ax.axhline(0, color=PENCIL, lw=1.4)
    w4 = per["W4_SR_BOUNCE_V2"]
    tip(
        ax,
        f"W4 je jedino neprikladno (faktor dobiti {hr(w4['profit_factor'], 2)} < 1,2):\nočekivanje oko {hr(w4['expectancy_eur'], 1)} € po poslu",
        (w4["trades_per_month"], w4["expectancy_eur"]),
        (6.5, 22),
        color=RED,
        rad=0.3,
        size=11.5,
    )
    w8 = per["W8_IBS_REVERT"]
    tip(
        ax,
        f"W8 trguje najčešće ({hr(w8['trades_per_month'])} mj.), ali\nzarađuje samo {hr(w8['expectancy_eur'], 1)} € po poslu: krhko uz provizije",
        (w8["trades_per_month"], w8["expectancy_eur"]),
        (30, 58),
        rad=-0.25,
        size=11.5,
    )
    rows = []
    for cid in ids:
        v = per[cid]
        rows.append(
            (
                W[cid],
                hr(v["trades_per_month"], 1),
                f"{'+' if v['expectancy_eur'] >= 0 else ''}{hr(v['expectancy_eur'], 0)} €",
                f"{hr(v['hit_rate'] * 100)} %",
                pct(v["total_return"], 0),
            )
        )
    fig.text(0.735, 0.83, "Pravilo", fontsize=11, color=GREY, ha="left")
    for xx, h in zip([0.838, 0.893, 0.945], ["posl./mj.", "€/posao", "pogodak"]):
        fig.text(xx, 0.83, h, fontsize=11, color=GREY, ha="left")
    for i, (n, a1, a2, a3, a4) in enumerate(rows):
        yy = 0.795 - i * 0.045
        fig.text(0.735, yy, n, fontsize=12, color=PENCIL, ha="left", va="center")
        fig.text(0.838, yy, a1, fontsize=12, color=PENCIL, ha="left", va="center")
        fig.text(0.893, yy, a2, fontsize=12, color=PENCIL, ha="left", va="center")
        fig.text(0.945, yy, a3, fontsize=12, color=PENCIL, ha="left", va="center")
    fig.text(
        0.735,
        0.795 - len(rows) * 0.045 - 0.012,
        f"Kupi i drži (mjerilo): jedna kupnja po dionici, prinos {pct(bh['total_return'], 0)} u AI eri, Sharpe {hr(bh['sharpe'], 2)}, najveći pad {pct(bh['max_drawdown'], 0)}. "
        "Nijedno pravilo ga ne dostiže po ukupnom prinosu.",
        fontsize=12,
        color=RED,
        ha="left",
        va="top",
        wrap=True,
    )
    fig.text(
        0.065,
        0.175,
        "Kako čitati: svaka točka na istoj točkastoj krivulji daje isti iznos eura mjesečno (broj poslova x dobitak po poslu). Pravila koja trguju često (W8) i ona koja trguju rjeđe, ali zarađuju više po poslu (W5, W3), mogu dati sličan mjesečni iznos. Plavi mjehuri ispunjavaju unaprijed zadano pravilo 'radi često', crveni ne.",
        fontsize=12,
        color=INK,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "ovo je AI era (bik-tržište): gotovo svako 'kupuj' pravilo izgleda dobro, a kupi-i-drži ih sve nadmašuje po ukupnom prinosu. Troškovi 2,5 bps po strani; FX, dividende, porezi i minimalna provizija nisu modelirani.",
        y=0.012,
    )
    nums = [
        "summary.json groups.stocks_all.per_contender (AI era, 43 sleevea): "
        + "; ".join(
            f"{cid.split('_')[0]} {per[cid]['trades']} poslova, {per[cid]['trades_per_month']:.1f} mj., {per[cid]['expectancy_eur']:.1f} €, ukupno {per[cid]['total_return'] * 100:.0f} %"
            for cid in ids
        ),
        f"kupi i drži (mjerilo): ukupni prinos {bh['total_return'] * 100:.0f} %, Sharpe {bh['sharpe']:.2f}, max pad {bh['max_drawdown'] * 100:.0f} %",
        "veličina mjehura = 400 + 2600 x ukupni prinos pravila (samo vizualno); točkaste krivulje = 500 i 1.000 € mjesečno (broj poslova x očekivanje)",
    ]
    return finish(
        fig,
        "c12_scoreboard.png",
        {
            "title": "Ploča rezultata W1 do W8: poslova mjesečno naspram dobitka po poslu",
            "what_to_see": "Mjehur je jedno pravilo (veličina = ukupni prinos). Što je desno, to češće trguje; što je više, to više zarađuje po poslu. Točkaste krivulje spajaju kombinacije s istim iznosom mjesečno. Tablica desno i okvir o kupi-i-drži daju brojke.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c13
def c13_equity_memory() -> str:
    mem = D.groups()["memory"]
    cids = ["B0_BUYHOLD", "W1_C13C_ORIG", "W5_SR_BREAKOUT_RETEST", "W3_MOM_RANK_WEEKLY"]
    style = {
        "B0_BUYHOLD": (GREY, "kupi i drži", 2.6, "-"),
        "W1_C13C_ORIG": (INK, "C13C (W1)", 2.6, "-"),
        "W5_SR_BREAKOUT_RETEST": (ORANGE, "W5 proboj i povratni test", 2.2, "-"),
        "W3_MOM_RANK_WEEKLY": (GREEN, "W3 tjedni rang zamaha", 2.2, "-"),
    }
    full = {c: D.group_equity(c, mem, "full") for c in cids}
    ai = {c: D.group_equity(c, mem, "ai_era") for c in cids}
    ref = D.summary()["groups"]["memory"]["per_contender"]
    for c in cids:  # the AI-era curve must equal summary.json
        assert abs(ai[c].iloc[-1] / 1000 - 1 - ref[c]["total_return"]) < 1e-9
    fig = canvas(
        12.6,
        "1.000 € po dionici u memorijskoj skupini (MU, WDC, STX): držanje naspram pravila",
        "Prosječna vrijednost jedne dionice, svaka počinje s 1.000 €. Gore: cijela povijest od 2016. (logaritamska ljestvica). Sredina i dolje: AI era od 1. 1. 2023., svaka crta kreće ponovno od 1.000 €.",
    )
    ax1 = fig.add_axes([0.065, 0.675, 0.915, 0.215])
    ax2 = fig.add_axes([0.065, 0.375, 0.915, 0.22])
    ax3 = fig.add_axes([0.065, 0.135, 0.915, 0.16])
    for ax in (ax1, ax2, ax3):
        paper(ax)
    for c in cids:
        col, lab, lw, ls = style[c]
        ax1.plot(full[c].index, full[c].values, color=col, lw=lw, label=lab)
        ax2.plot(ai[c].index, ai[c].values, color=col, lw=lw, label=lab)
        dd = ai[c] / ai[c].cummax() - 1
        ax3.plot(dd.index, dd.values * 100, color=col, lw=lw)
    ax1.set_yscale("log")
    ax2.set_yscale("log")
    ax1.set_ylabel("vrijednost (€), log")
    ax2.set_ylabel("vrijednost (€), log")
    ax3.set_ylabel("pad od vrha (%)")
    ax1.axvline(AI_ERA, color=RED, ls=":", lw=2.2)
    ax1.text(
        AI_ERA + pd.Timedelta(days=30),
        0.06,
        "početak AI ere\n(1. 1. 2023.)",
        transform=ax1.get_xaxis_transform(),
        fontsize=12,
        color=RED,
    )
    ax1.legend(loc="upper left", frameon=False, fontsize=12, ncol=2)
    from matplotlib.ticker import FuncFormatter

    fmt = FuncFormatter(lambda v, _: hr(v))
    for ax in (ax1, ax2):
        ax.yaxis.set_major_formatter(fmt)
        ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax1.set_title("Cijela povijest (od 2016.)", loc="left", fontsize=14, color=INK)
    ax2.set_title(
        "AI era (1.000 € po dionici na početku 2023.)",
        loc="left",
        fontsize=14,
        color=INK,
    )
    # end values
    yoff = {
        "B0_BUYHOLD": 1.0,
        "W1_C13C_ORIG": 1.0,
        "W5_SR_BREAKOUT_RETEST": 1.0,
        "W3_MOM_RANK_WEEKLY": 1.0,
    }
    for c in cids:
        col, lab, _, _ = style[c]
        end = float(ai[c].iloc[-1])
        ax2.text(
            ai[c].index[-1] + pd.Timedelta(days=12),
            end * yoff[c],
            eur(end),
            color=col,
            fontsize=12.5,
            va="center",
        )
    ax2.set_xlim(
        ai["B0_BUYHOLD"].index[0], ai["B0_BUYHOLD"].index[-1] + pd.Timedelta(days=150)
    )
    ax3.set_xlim(ax2.get_xlim())
    for c in cids:
        col = style[c][0]
        dd = ai[c] / ai[c].cummax() - 1
        t = dd.idxmin()
        v = float(dd.min()) * 100
        ring(ax3, t, v, col, 380)
        assert abs(dd.min() - ref[c]["max_drawdown"]) < 1e-9, (
            c,
            dd.min(),
            ref[c]["max_drawdown"],
        )
    pos = {
        "B0_BUYHOLD": (0, 14),
        "W1_C13C_ORIG": (-0.2, -8),
        "W5_SR_BREAKOUT_RETEST": (0.08, -6),
        "W3_MOM_RANK_WEEKLY": (-0.1, -1),
    }
    for c in cids:
        col, lab, _, _ = style[c]
        dd = ai[c] / ai[c].cummax() - 1
        t = dd.idxmin()
        v = float(dd.min()) * 100
        k = cids.index(c)
        ax3.text(
            0.60 + (k % 2) * 0.25,
            0.19 - (k // 2) * 0.13,
            f"{lab}: {hr(v, 0)} % ({day(t)})",
            color=col,
            fontsize=11.5,
            ha="left",
            va="center",
            transform=ax3.transAxes,
        )
    ax3.set_ylim(-62, 3)
    ax3.set_title(
        "Najgori padovi od vrha u AI eri (kružići = najgori trenutak)",
        loc="left",
        fontsize=14,
        color=INK,
    )
    end_b = float(ai["B0_BUYHOLD"].iloc[-1])
    end_1 = float(ai["W1_C13C_ORIG"].iloc[-1])
    tip(
        ax2,
        f"kupi i drži: 1.000 € -> {eur(end_b)}, ali uz pad od {hr(-ref['B0_BUYHOLD']['max_drawdown'] * 100, 0)} % (iz npr. 5.000 € na {eur(5000 * (1 + ref['B0_BUYHOLD']['max_drawdown']))}).\nPravila su prosječno uložena tek oko pola kapitala (C13C {hr(ref['W1_C13C_ORIG']['exposure_pct'], 0)} %, W5 {hr(ref['W5_SR_BREAKOUT_RETEST']['exposure_pct'], 0)} %, W3 {hr(ref['W3_MOM_RANK_WEEKLY']['exposure_pct'], 0)} %), ostatak čeka u gotovini.",
        None,
        (0.02, 0.88),
        coords="axes",
        arrow=False,
        size=12,
        box=True,
    )
    bottom_note(
        fig,
        f"držanje je u ovom uzorku pobijedilo sva pravila po ukupnom prinosu (memorijske dionice su rasle ogromno). Pravila (C13C {pct(ref['W1_C13C_ORIG']['total_return'], 0)}, W5 {pct(ref['W5_SR_BREAKOUT_RETEST']['total_return'], 0)}, W3 {pct(ref['W3_MOM_RANK_WEEKLY']['total_return'], 0)}) imaju manji pad, ali nikad nisu bolja od držanja po ukupnom prinosu. AI era je iznimno bik-tržište: ne očekuj ponavljanje.",
        y=0.012,
    )
    nums = [
        "AI era (summary.json memory): ukupni prinos "
        + "; ".join(
            f"{style[c][1]} {ref[c]['total_return'] * 100:.0f} % (max pad {ref[c]['max_drawdown'] * 100:.0f} %)"
            for c in cids
        ),
        "krivulje = zbroj tri sleevea (MU, WDC, STX) / 3; AI era re-run swing.py jednak summary.json (provjereno, razlika < 1e-9 za prinos i max pad)",
        "cijela povijest: isti motor, prozor 2016-01-01 do 2026-10-05 (summary 'full' nije u datoteci; krivulja je re-run)",
        "trošak 2,5 bps po strani; FX, dividende, porezi, provizija nisu modelirani",
    ]
    return finish(
        fig,
        "c13_equity_memory.png",
        {
            "title": "Memorijska skupina: 1.000 € po dionici, držanje naspram C13C, W5 i W3",
            "what_to_see": "Gore cijela povijest (log) s crvenom točkastom crtom na početku AI ere. Sredina: AI era od 1.000 €. Dolje: pad od vrha s označenim najgorim trenucima. Sive krivulje (držanje) su najviše, ali s najdubljim padom.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c14
def c14_c13c_vs_new() -> str:
    sm = D.summary()["groups"]
    segs = [
        "memory",
        "mem_interface_storage",
        "equipment",
        "ai_chips_logic",
        "network_servers",
        "cloud",
        "stocks_all",
    ]
    seg_names = {
        "memory": "Memorija (3)",
        "mem_interface_storage": "Sučelja memorije i pohrana (4)",
        "equipment": "Oprema za čipove (10)",
        "ai_chips_logic": "AI čipovi i logika (11)",
        "network_servers": "Mreže i serveri (8)",
        "cloud": "Oblak (7)",
        "stocks_all": "Svih 43 zajedno",
    }
    cids = [
        "W1_C13C_ORIG",
        "W5_SR_BREAKOUT_RETEST",
        "W3_MOM_RANK_WEEKLY",
        "W2_MOM_BREAK_20",
        "W8_IBS_REVERT",
        "B0_BUYHOLD",
    ]
    fig = canvas(
        9.0,
        "C13C naspram novih pravila po segmentima (AI era): prinos i Sharpe",
        "Lijeva tablica: ukupni prinos na 1.000 € po dionici. Desna: Sharpe (prinos u odnosu na kolebanje; iznad 1 je dobro, ispod 0 loše). Zelenije = bolje. Zadnji stupac je kupi i drži (mjerilo).",
    )
    cmap = LinearSegmentedColormap.from_list("rg", ["#f6c9c3", "#fff7d6", "#bfe6c9"])
    axl = fig.add_axes([0.2, 0.2, 0.37, 0.58])
    axr = fig.add_axes([0.6, 0.2, 0.37, 0.58])
    for ax, key, title, fmt in [
        (axl, "total_return", "Ukupni prinos", lambda v: pct(v, 0)),
        (axr, "sharpe", "Sharpe", lambda v: hr(v, 2)),
    ]:
        M = np.array(
            [[sm[s]["per_contender"][c][key] for c in cids] for s in segs], dtype=float
        )
        norm = np.zeros_like(M)
        for j in range(
            M.shape[1]
        ):  # colour within the column so each rule is compared across segments, B0 separately grey
            col = M[:, j]
            lo, hi = col.min(), col.max()
            norm[:, j] = (col - lo) / (hi - lo) if hi > lo else 0.5
        ax.set_facecolor(PAPER)
        ax.imshow(norm, cmap=cmap, aspect="auto", vmin=0, vmax=1)
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                ax.text(
                    j,
                    i,
                    fmt(M[i, j]),
                    ha="center",
                    va="center",
                    fontsize=12,
                    color=PENCIL,
                    fontweight="bold" if cids[j] == "W1_C13C_ORIG" else None,
                )
        ax.set_xticks(range(len(cids)))
        ax.set_xticklabels([W[c].replace(" ", "\n", 1) for c in cids], fontsize=10.5)
        ax.xaxis.tick_top()
        ax.set_yticks(range(len(segs)))
        ax.set_yticklabels(
            [seg_names[s] for s in segs] if ax is axl else [], fontsize=12
        )
        ax.set_title(title, fontsize=15, color=INK, pad=62, loc="left")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        ax.axvline(len(cids) - 1.5, color=PENCIL, lw=2)
        ax.axhline(len(segs) - 1.5, color=PENCIL, lw=1.4)
    # verification: B0 beats every rule on total return in every segment?
    beats = all(
        sm[s]["per_contender"]["B0_BUYHOLD"]["total_return"]
        > max(sm[s]["per_contender"][c]["total_return"] for c in cids[:-1])
        for s in segs
    )
    best_sh = {
        s: max(cids[:-1], key=lambda c: sm[s]["per_contender"][c]["sharpe"])
        for s in segs
    }
    wins_c13 = [s for s in segs if best_sh[s] == "W1_C13C_ORIG"]
    fig.text(
        0.04,
        0.135,
        (
            "Kupi i drži ima veći ukupni prinos od svakog pravila u svakom segmentu. "
            if beats
            else "Kupi i drži nije u svim segmentima iznad svakog pravila po prinosu (vidi tablicu). "
        )
        + f"Po Sharpeu C13C je najbolje pravilo u {len(wins_c13)} od {len(segs)} redaka ({', '.join(seg_names[s].split(' (')[0] for s in wins_c13) or 'nijednom'}); u ostalima vodi drugo pravilo. "
        "Boje se računaju unutar svakog stupca (pravilo uspoređeno kroz segmente), pa zelena ne znači 'dobro' u apsolutnom smislu nego 'bolje od ostalih segmenata za to pravilo'.",
        fontsize=12.5,
        color=RED,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "C13C je Petrov postojeći algoritam: nova pravila ga ne 'pobjeđuju' dosljedno. Svi brojevi su iz AI ere, jednog bik-tržišta, uz 2,5 bps po strani. Nijedan nije formalni Critic PASS.",
        y=0.012,
    )
    nums = [
        "summary.json groups[segment].per_contender[pravilo].total_return i .sharpe (AI era, trošak 2,5 bps po strani)",
        "redovi: memory, mem_interface_storage, equipment, ai_chips_logic, network_servers, cloud, stocks_all",
        "provjera: kupi i drži ima veći ukupni prinos od svakog pravila u svih 7 redaka: "
        + ("da" if beats else "ne"),
        "najbolji Sharpe po retku (među W1, W5, W3, W2, W8): "
        + "; ".join(f"{s} {best_sh[s].split('_')[0]}" for s in segs),
    ]
    return finish(
        fig,
        "c14_c13c_vs_new.png",
        {
            "title": "C13C naspram W5, W3, W2 i W8 po segmentima",
            "what_to_see": "Dvije toplinske tablice: ukupni prinos (lijevo) i Sharpe (desno) za pet pravila i kupi-i-drži po šest segmenata i za svih 43 dionice. Boja je relativna unutar stupca.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c16
def c16_context_2021_2022() -> str:
    r = load_json(SWING / "results" / "stocks_all.json")["contenders"]
    ids = [c for c in r if c != "B0_BUYHOLD"]
    periods = [
        ("y2016_2020", "2016. do 2020."),
        ("y2021_2022", "2021. do 2022. (pad)"),
        ("ai_era", "2023. do 2026. (AI era)"),
    ]

    def blk(c: str, p: str) -> dict[str, Any]:
        return r[c]["ai_era"] if p == "ai_era" else r[c]["contexts"][p]

    fig = canvas(
        9.0,
        "Ista pravila u tri razdoblja: zašto su rezultati specifični za AI eru",
        "Očekivana zarada po poslu na 1.000 € (nakon troška), svih 43 dionice. Pravila su ista i nepromijenjena u sva tri razdoblja.",
    )
    ax = fig.add_axes([0.06, 0.28, 0.92, 0.54])
    paper(ax)
    x = np.arange(len(ids))
    cols = [LIGHT, ORANGE, INK]
    for k, (p, lab) in enumerate(periods):
        vals = [blk(c, p)["expectancy_eur"] for c in ids]
        bars = ax.bar(
            x + (k - 1) * 0.27, vals, 0.26, color=cols[k], edgecolor=PENCIL, label=lab
        )
        for xi, v, c in zip(x + (k - 1) * 0.27, vals, ids):
            ax.text(
                xi,
                v + (1.2 if v >= 0 else -1.2),
                f"{hr(v, 0)}",
                ha="center",
                va="bottom" if v >= 0 else "top",
                fontsize=10.5,
                color=PENCIL,
            )
    ax.axhline(0, color=PENCIL, lw=1.6)
    ax.set_xticks(x)
    ax.set_xticklabels([W[c].replace(" ", "\n", 1) for c in ids], fontsize=11.5)
    ax.set_ylabel("€ po poslu (na 1.000 €)")
    ax.set_ylim(-26, 92)
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    neg = [c for c in ids if blk(c, "y2021_2022")["expectancy_eur"] <= 0]
    near0 = [c for c in ids if blk(c, "y2021_2022")["expectancy_eur"] <= 2]
    b0 = {p: blk("B0_BUYHOLD", p)["total_return"] for p, _ in periods}
    pos_ids = [c for c in ids if c not in neg]
    tip(
        ax,
        f"2021. do 2022.: očekivanje je negativno za {len(neg)} od {len(ids)} pravila,\na ostala ({', '.join(c.split('_')[0] + ' ' + ('+' if blk(c, 'y2021_2022')['expectancy_eur'] >= 0 else '') + hr(blk(c, 'y2021_2022')['expectancy_eur'], 0) + ' €' for c in pos_ids)}) su praktički nula",
        None,
        (0.02, 0.68),
        coords="axes",
        arrow=False,
        size=12.5,
    )
    fig.text(
        0.06,
        0.2,
        f"Kupi i drži na istih 43 dionice (ukupni prinos): 2016. do 2020. {pct(b0['y2016_2020'], 0)}, 2021. do 2022. {pct(b0['y2021_2022'], 0)}, AI era {pct(b0['ai_era'], 0)}. "
        f"Pravila koja najviše obećavaju u AI eri (W5, W3) u padu 2021. do 2022. gube po poslu ({hr(blk('W5_SR_BREAKOUT_RETEST', 'y2021_2022')['expectancy_eur'], 0)} € i {hr(blk('W3_MOM_RANK_WEEKLY', 'y2021_2022')['expectancy_eur'], 0)} €). "
        "Dakle: velik dio onoga što vidiš u AI eri dolazi iz tržišta koje je jako raslo, a ne iz same logike pravila.",
        fontsize=12.5,
        color=RED,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "zato je pravi test pravila kako se ponaša kad tržište ne raste. Pad 2021. do 2022. daje samo djelić te slike i jedan je događaj, ali upozorava da AI era nije normalno stanje.",
        y=0.012,
    )
    nums = [
        "results/stocks_all.json contenders[*].contexts (y2016_2020, y2021_2022) i .ai_era: expectancy_eur",
        "očekivanje 2021-2022 po pravilu: "
        + "; ".join(
            f"{c.split('_')[0]} {blk(c, 'y2021_2022')['expectancy_eur']:.1f} €"
            for c in ids
        ),
        f"kupi i drži (ukupni prinos): 2016-2020 {b0['y2016_2020'] * 100:.0f} %, 2021-2022 {b0['y2021_2022'] * 100:.0f} %, AI era {b0['ai_era'] * 100:.0f} %",
        "poslova po razdoblju: "
        + "; ".join(
            f"{c.split('_')[0]} {blk(c, 'y2016_2020')['trades']}/{blk(c, 'y2021_2022')['trades']}/{blk(c, 'ai_era')['trades']}"
            for c in ids
        ),
    ]
    return finish(
        fig,
        "c16_context_2021_2022.png",
        {
            "title": "Ista pravila u 2016. do 2020., 2021. do 2022. i u AI eri",
            "what_to_see": "Za svako pravilo tri stupca: siva = 2016. do 2020., narančasta = 2021. do 2022. (pad), plava = AI era. U padu većina pravila ima očekivanje oko nule ili ispod nje; u AI eri sva izgledaju bolje.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c17-19
def c17_19_levels() -> list[str]:
    out = []
    for n, t in [(17, "MU"), (18, "WDC"), (19, "STX")]:
        src = SWING / "map" / f"{t}.png"
        name = f"c{n}_levels_{t}.png"
        im = Image.open(src).convert("RGB")
        h = round(im.height * 1400 / im.width)
        im = im.resize((1400, h), Image.LANCZOS)
        m = load_json(SWING / "map" / f"{t}.json")
        im.quantize(
            colors=160, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
        ).save(OUT / name, optimize=True)
        lv = m["levels"]
        near_s = m["nearest_supports"][0] if m.get("nearest_supports") else None
        near_r = m["nearest_resistances"][0] if m.get("nearest_resistances") else None
        CAPTIONS[name] = {
            "title": f"{t}: karta razina i strukture (zadnji dan {m['last_date']})",
            "what_to_see": "Zelene trake = potpore ispod cijene, crvene = otpori iznad, deblja crta = razina, traka = zona dodira; krugovi 1 do 4 vezani su uz crvene bilješke ispod grafa (najbliža potpora, najbliži otpor, premium ili diskont, zadnja promjena karaktera). Graf već sadrži crvene bilješke učitelja: nije dodan novi sloj, samo je slika smanjena na 1400 px. Razine su orijentiri, ne jamstvo: placebo test (c11) pokazuje da ne odbijaju cijenu bolje od nasumičnih.",
            "numbers_used": [
                f"izvor: reports/research/AICHAIN_20261014/swing/map/{t}.png i {t}.json (zadnji datum {m['last_date']}, zadnje zatvaranje {m['last_close']:.2f}, ATR14 {m['atr14']:.2f})",
                f"broj razina u karti: {len(lv)}"
                + (
                    f"; najbliža potpora {near_s['price']:.2f}"
                    if near_s and "price" in near_s
                    else ""
                )
                + (
                    f"; najbliži otpor {near_r['price']:.2f}"
                    if near_r and "price" in near_r
                    else ""
                ),
                "napomena: karta koristi zadnji datum u CSV-u, ne zajednički kraj 2026-10-05 (vidi last_date_note u JSON-u)",
            ],
        }
        out.append(name)
    return out


# ================================================================================ c20
def _cdt_h1() -> tuple[pd.Series, pd.Series, dict[str, float]]:
    import importlib

    from lab.crypto_dt import data as cdata
    from lab.top10 import core

    module = importlib.import_module("lab.crypto_dt.strategies.cdt_h1_trend_4h")

    def loader(tickers: Any, cutoff: str = core.CUTOFF, timeframe: str = "1d") -> Any:
        return cdata.load_bars(tickers, timeframe, cutoff)

    with mock.patch.object(core, "load_frames", loader):
        frames = core.load_frames(module.UNIVERSE, timeframe=module.TIMEFRAME)
    pan = core.panel(frames)
    weights = module.weights(pan, module.PARAMS)
    bt = core.backtest(weights, pan, 1.0)
    net = bt["net"].loc["2023-01-01":]
    eq = (1 + net).cumprod()
    opens = pan["open"].loc["2023-01-01":]
    basket = (opens / opens.iloc[0]).mean(axis=1)
    m = core.metrics(net)
    return eq, basket, m


def c20_crypto_trend() -> str:
    eq, hold, m = _cdt_h1()
    res = load_json(
        ROOT
        / "reports"
        / "research"
        / "CRYPTO_DT_20261014"
        / "CDT_H1_TREND_4H"
        / "results.json"
    )
    prereg = res["prereg"]
    assert abs(float(eq.iloc[-1]) - 1 - res["eras"]["ai_era"]["total"]) < 1e-6, (
        eq.iloc[-1],
        res["eras"]["ai_era"]["total"],
    )
    assert abs(float(hold.iloc[-1]) - 1 - prereg["buy_and_hold_ai_era"]["total"]) < 1e-6
    dd_s = eq / eq.cummax() - 1
    dd_h = hold / hold.cummax() - 1
    fig = canvas(
        11.0,
        "Kripto: sporo praćenje trenda (CDT_H1, 4h) naspram kupi i drži na BTC + ETH + SOL",
        "AI era od 1. 1. 2023. do 9. 10. 2026., 1.000 € na početku, jednak iznos u tri coina. Trošak 10 bps po strani. Dostupnost kripta preko IBKR-a za HR: nepotvrđeno.",
    )
    ax1 = fig.add_axes([0.065, 0.55, 0.60, 0.30])
    ax2 = fig.add_axes([0.065, 0.31, 0.60, 0.17])
    ax3 = fig.add_axes([0.745, 0.31, 0.235, 0.54])
    for ax in (ax1, ax2, ax3):
        paper(ax)
    ax1.plot(
        eq.index,
        eq.values * 1000,
        color=INK,
        lw=2.4,
        label="CDT_H1 sporo praćenje trenda",
    )
    ax1.plot(
        hold.index,
        hold.values * 1000,
        color=GREY,
        lw=2.2,
        label="kupi i drži (BTC+ETH+SOL)",
    )
    ax1.set_yscale("log")
    from matplotlib.ticker import FuncFormatter

    ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: hr(v)))
    ax1.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax1.set_ylabel("vrijednost (€), log")
    ax1.legend(loc="upper left", frameon=False, fontsize=12)
    ax1.set_title("Rast 1.000 €", loc="left", fontsize=14, color=INK)
    e_s, e_h = float(eq.iloc[-1]) * 1000, float(hold.iloc[-1]) * 1000
    ax1.text(eq.index[-1], e_s, f" {eur(e_s)}", color=INK, fontsize=12.5, va="center")
    ax1.text(
        hold.index[-1], e_h, f" {eur(e_h)}", color=GREY, fontsize=12.5, va="center"
    )
    ax1.set_xlim(eq.index[0], eq.index[-1] + pd.Timedelta(days=170))
    ax2.fill_between(
        dd_h.index, dd_h.values * 100, color=LIGHT, alpha=0.6, label="kupi i drži"
    )
    ax2.fill_between(
        dd_s.index, dd_s.values * 100, color=INK, alpha=0.4, label="CDT_H1"
    )
    ax2.set_xlim(ax1.get_xlim())
    ax2.set_ylabel("pad od vrha (%)")
    ax2.set_ylim(min(dd_h.min(), dd_s.min()) * 100 * 1.12, 3)
    ax2.legend(loc="lower right", frameon=False, fontsize=11.5)
    th, ts = dd_h.idxmin(), dd_s.idxmin()
    ring(ax2, th, dd_h.min() * 100, RED, 420)
    ring(ax2, ts, dd_s.min() * 100, RED, 420)
    ax2.text(
        th + pd.Timedelta(days=15),
        dd_h.min() * 100 + 6,
        f"{hr(dd_h.min() * 100, 0)} %",
        color=RED,
        fontsize=12.5,
    )
    ax2.text(
        ts + pd.Timedelta(days=15),
        dd_s.min() * 100 - 7,
        f"{hr(dd_s.min() * 100, 0)} %",
        color=RED,
        fontsize=12.5,
    )
    # intraday failures
    ids = [
        "CDT_H3_UTC2123_COND",
        "CDT_H4_ID_MOM_VOL",
        "CDT_H5_BTC_LEAD_5M",
        "CDT_H1_TREND_4H",
    ]
    labs = [
        "H3\nprozor\n21-23 UTC",
        "H4\nintraday\nzamah",
        "H5\nBTC vodi\nETH/SOL",
        "H1\nsporo\n(4h trend)",
    ]
    g = []
    for i in ids:
        rr = load_json(
            ROOT / "reports" / "research" / "CRYPTO_DT_20261014" / i / "results.json"
        )
        g.append(rr["prereg"]["gross_bps_per_trade_wf_ho"])
    ax3.bar(range(4), g, color=[LOSS, LOSS, LOSS, WIN], edgecolor=PENCIL, width=0.6)
    ax3.axhline(20, color=RED, ls="--", lw=2.2)
    ax3.text(
        -0.45,
        23,
        "granica isplativosti 20 bps",
        color=RED,
        fontsize=11.5,
        ha="left",
        va="bottom",
    )
    for xi, v in enumerate(g):
        ax3.text(
            xi, v * 1.12 + 1.2, f"{hr(v, 1)}", ha="center", fontsize=12, color=PENCIL
        )
    ax3.set_yscale("symlog", linthresh=25)
    ax3.set_ylim(0, 600)
    ax3.set_yticks([0, 10, 20, 50, 100, 340])
    ax3.set_yticklabels(["0", "10", "20", "50", "100", "340"])
    ax3.set_xticks(range(4))
    ax3.set_xticklabels(labs, fontsize=10)
    ax3.set_ylabel("bruto bps po poslu (prije troška)")
    ax3.set_title("Intraday ne pokriva trošak", loc="left", fontsize=13.5, color=INK)
    h1 = res["prereg"]
    fig.text(
        0.065,
        0.215,
        f"1.000 € u CDT_H1 bi bilo oko {eur(e_s)} naspram {eur(e_h)} kod držanja (prije poreza, bez tečaja EUR/USD). Držanje je zaradilo više, ali uz pad od {hr(-dd_h.min() * 100, 0)} % (iz 5.000 € na oko {eur(5000 * (1 + dd_h.min()))}); trend pravilo je imalo najgori pad {hr(-dd_s.min() * 100, 0)} %. "
        f"Samo {hr(res['trades']['win_rate'] * 100)} % poslova je dobitnih, medijan posla je negativan ({pct(res['trades']['median'], 1)}), a dobit nose rijetki veliki trendovi. Deflated Sharpe {hr(res['deflated_sharpe_prob'], 2)} uz K = {res['k']}: statistički ne možemo tvrditi pravi edge. Formalni Critic: FAIL.",
        fontsize=12.5,
        color=RED,
        ha="left",
        va="top",
        wrap=True,
    )
    bottom_note(
        fig,
        "day trading (minute do sat) u kriptu nakon troškova nismo našli: bruto zarada po poslu (2 do 16 bps) ne pokriva 20 bps troška kruga. Preživio je samo spori trend, i to kao smanjivač rizika, ne kao dokaz prednosti.",
        y=0.012,
    )
    nums = [
        f"CDT_H1 AI era ukupno {m['total'] * 100:.1f} % (results.json eras.ai_era {res['eras']['ai_era']['total'] * 100:.1f} %), kupi i drži {prereg['buy_and_hold_ai_era']['total'] * 100:.1f} % (prereg.buy_and_hold_ai_era)",
        f"najveći pad: CDT_H1 {dd_s.min() * 100:.1f} %, kupi i drži {dd_h.min() * 100:.1f} % (izračun iz re-runa; results.json: {res['eras']['ai_era']['maxdd'] * 100:.1f} % i {prereg['buy_and_hold_ai_era']['maxdd'] * 100:.1f} %)",
        "bruto bps po poslu WF+HO: "
        + "; ".join(f"{i.split('_')[1]} {v:.1f}" for i, v in zip(ids, g))
        + "; granica isplativosti 20 bps (prereg.break_even_bps_round_trip)",
        f"poslova {res['trades']['n']}, dobitnih {res['trades']['win_rate']:.3f}, medijan {res['trades']['median']:.4f}; DSR {res['deflated_sharpe_prob']:.2f}, K {res['k']}",
        "re-run CDT_H1 samo za čitanje (bez ledger zapisa); ukupni prinos jednak results.json (provjereno)",
    ]
    return finish(
        fig,
        "c20_crypto_trend.png",
        {
            "title": "Kripto: sporo praćenje trenda (CDT_H1) naspram kupi i drži, i neuspjeli intraday",
            "what_to_see": "Gore lijevo: vrijednost 1.000 € kroz AI eru (log). Ispod: pad od vrha, s najgorim točkama. Desno: bruto zarada po poslu za tri intraday ideje (crveno) i za sporo praćenje trenda (zeleno) naspram crte od 20 bps koja pokriva trošak.",
            "numbers_used": nums,
        },
    )


# ================================================================================ c21
def c21_metals_eu() -> str:
    ig = pd.read_csv(
        ROOT / "data" / "ohlcv" / "IGLN_LSE_1d.csv", parse_dates=["date"]
    ).set_index("date")
    trades = pd.read_csv(
        ROOT
        / "reports"
        / "backtest"
        / "C36_METALS_ADV_20261013"
        / "IBKR"
        / "ROTATE_BASE_500_DIAGNOSTIC_trades.csv",
        parse_dates=["date"],
    )
    fig = canvas(
        10.4,
        "Zlato u EU: IGLN (iShares Physical Gold, ETC na londonskoj burzi, kotacija u USD)",
        "Referentni primjer: IGLN je jedan od kandidata iz provjere, ne preporuka. Razdoblje u podacima: 18. 10. 2021. do 13. 10. 2026.",
    )
    ax = fig.add_axes([0.065, 0.50, 0.60, 0.34])
    paper(ax)
    ax.plot(ig.index, ig["close"], color=ORANGE, lw=2.2, label="IGLN zatvaranje (USD)")
    ax.set_ylabel("cijena (USD)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    lo_d, hi_d = ig["close"].idxmin(), ig["close"].idxmax()
    ring(ax, lo_d, float(ig.close.min()), RED, 380)
    ring(ax, hi_d, float(ig.close.max()), RED, 380)
    ax.text(
        lo_d,
        float(ig.close.min()) - 3.2,
        f"{day(lo_d)}\n{usd(float(ig.close.min()))}",
        fontsize=11.5,
        color=RED,
        ha="center",
        va="top",
    )
    ax.text(
        hi_d,
        float(ig.close.max()) + 1.5,
        f"{day(hi_d)}\n{usd(float(ig.close.max()))}",
        fontsize=11.5,
        color=RED,
        ha="right",
        va="bottom",
    )
    ax.set_ylim(float(ig.close.min()) - 14, float(ig.close.max()) + 14)
    ax.set_title("Cijena IGLN-a", loc="left", fontsize=14, color=INK)
    steps = [
        (
            "1",
            WIN,
            "POTVRĐENO (provjera 14. 10. 2026.): IGLN je iShares fizički pokriven ETC, ISIN IE00B4ND3602, godišnja naknada 0,12 %, kotira na LSE u USD; javni KID postoji; IBKR dnevna povijest 1.258 dana, bez OHLC nesuglasnosti.",
        ),
        (
            "2",
            RED,
            "NEPOTVRĐENO: može li Petrov IBKR račun kupiti IGLN (KID/PRIIPs status kod IBKR-a, dozvole računa), tečajni trošak EUR/USD, prilagodba cijena, hrvatski porez. 'No market data permissions' za neke EUR linije opisuje podatke, ne zabranu kupnje.",
        ),
        (
            "3",
            RED,
            "NEPOTVRĐENO: ISLN (srebro) ima 53 redaka s nesuglasnim OHLC-om i nije spreman za backtest; za zlato i srebro nema deset godina provjerenih podataka.",
        ),
    ]
    side_notes(
        fig, steps, top=0.855, x=0.715, size=12, width=40, height_in=10.4, gap=0.6
    )
    # ROTATE example transactions (500 EUR account, PHAG, EUR listing); a different data set than IGLN
    ph = pd.read_csv(
        ROOT / "data" / "ohlcv" / "PHAG_1d.csv", parse_dates=["date"]
    ).set_index("date")
    ph = ph.loc[trades["date"].min() - pd.Timedelta(days=20) :]
    ax2 = fig.add_axes([0.065, 0.165, 0.915, 0.20])
    paper(ax2)
    ax2.plot(
        ph.index,
        ph["close"],
        color=GREY,
        lw=1.8,
        label="PHAG (srebro ETC, EUR) zatvaranje",
    )
    for _, r in trades.iterrows():
        buy = r["side"] == "buy"
        ax2.scatter(
            [r["date"]],
            [r["price_eur"]],
            marker="^" if buy else "v",
            s=170,
            color=WIN if buy else LOSS,
            edgecolors=PENCIL,
            zorder=8,
        )
        lab = (
            "kupnja"
            if buy
            else f"prodaja {'+' if r['net_pnl_eur'] > 0 else ''}{hr(r['net_pnl_eur'], 0)} €"
        )
        ax2.text(
            r["date"],
            r["price_eur"] + (4 if not buy else -4),
            lab,
            fontsize=10.5,
            color=WIN if buy else (LOSS if r["net_pnl_eur"] < 0 else WIN),
            ha="center",
            va="bottom" if not buy else "top",
        )
    ax2.set_ylabel("EUR")
    ax2.legend(loc="upper left", frameon=False, fontsize=11)
    ax2.set_title(
        "ROTATE (obrazovna simulacija, račun 500 €, zaseban skup PHAG/PHAU u EUR): stvarne transakcije u srebru",
        loc="left",
        fontsize=12.5,
        color=INK,
    )
    rows = trades[trades["side"] == "sell"]
    tr_sum = trades["net_pnl_eur"].dropna()
    bottom_note(
        fig,
        f"ROTATE je u istraživanju dao +11,9 % na 500 € u zadnjih ~12 mjeseci, ali na razvojnom računu bio je negativan (WF 2021. do 2023. -19,7 % na 500 €) i nije prošao unaprijed zadani odabir: obrazovni prikaz, ne najbolji algoritam. U datoteci je {len(trades)} transakcija (prodaje: {len(rows)}); zbroj neto dobiti prodaja {hr(float(tr_sum.sum()), 0)} € (prije poreza, FX, nepotvrđena provizija).",
        y=0.012,
    )
    nums = [
        f"IGLN_LSE_1d.csv: {len(ig)} redaka, {ig.index[0].date()} do {ig.index[-1].date()}; najniže zatvaranje {ig.close.min():.2f} ({lo_d.date()}), najviše {ig.close.max():.2f} ({hi_d.date()})",
        "docs/research/EU_METALS_ETC_CHECK.md: ISIN, naknada 0,12 %, LSE/USD, javni KID, 1.258 redaka, ISLN 53 nesuglasna retka, EU kupnja nepotvrđeno",
        f"ROTATE 500 € transakcije iz reports/backtest/C36_METALS_ADV_20261013/IBKR/ROTATE_BASE_500_DIAGNOSTIC_trades.csv: {len(trades)} redaka, {len(rows)} prodaja, neto zbroj prodaja {tr_sum.sum():.1f} €",
        "docs/research/GOLD_SILVER_5050_RECAP.md: ROTATE 500 € +11,88 % (1. 10. 2025. do 12. 10. 2026.), WF 2021-2023 -19,71 %",
    ]
    return finish(
        fig,
        "c21_metals_eu.png",
        {
            "title": "Zlato u EU: IGLN cijena, što je potvrđeno i nepotvrđeno, i primjer ROTATE poslova",
            "what_to_see": "Gore: cijena IGLN-a s najnižom i najvišom točkom. Desno: što je potvrđeno (identitet, naknada, podaci), a što nije (pravo kupnje, KID kod IBKR-a, tečaj, porez). Dolje: stvarne transakcije ROTATE simulacije na 500 € u srebru PHAG (zaseban podatkovni skup od IGLN-a).",
            "numbers_used": nums,
        },
    )


def usd(x: float, nd: int = 2) -> str:
    return hr(x, nd)
