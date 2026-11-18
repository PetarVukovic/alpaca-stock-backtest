"""Build the self-contained Croatian page for the AI-chain segment "equipment" (semiconductor equipment).

Usage:
  .venv/bin/python scripts/aichain_build_page_equipment.py            # re-renders the charts, then the page
  .venv/bin/python scripts/aichain_build_page_equipment.py --no-charts   # reuse the PNGs already on disk

Inputs (real files only): segments/equipment/{analysis,profile}.json, results/equipment.json and results/{TICKER}.json,
data/ohlcv via lab.aichain.sim.load_bars. Output: segments/equipment/artifact.html (charts embedded as data URIs).
CSS and the data-URI helper are imported from scripts/top10_build_artifact.py, which stays unchanged.
Research only: nothing here places orders.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from top10_build_artifact import CSS, HEAD, e  # noqa: E402

from lab.aichain import charts_segment as cs  # noqa: E402
from lab.aichain.sim import load_bars  # noqa: E402

SEGMENT = "equipment"
OUT_DIR = cs.RES / "segments" / SEGMENT
TITLE = "Oprema analiza"

EXTRA_CSS = """
.plate{background:#fffef9}
.sub{font-size:1.05rem;color:var(--muted);margin:0 0 10px}
.verdict-big{font-family:var(--display);font-size:clamp(1.2rem,3.6vw,1.55rem);line-height:1.35;font-weight:600;max-width:44ch;margin:0}
.euro{background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:6px;padding:12px 16px;margin:0 0 14px;max-width:70ch}
.euro p{margin:0}
.limit{background:var(--warn-soft);border-left:4px solid var(--warn);border-radius:6px;padding:12px 16px;max-width:70ch}
.limit p{margin:0 0 8px}.limit p:last-child{margin:0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.tk{background:var(--surface);border:1px solid var(--line);border-radius:6px;min-width:0}
.tk>summary{display:flex;flex-direction:column;gap:2px;padding:12px 16px;list-style:none}
.tk>summary::-webkit-details-marker{display:none}
.tk .name{font-family:var(--display);font-weight:700;font-size:1.15rem}
.tk .nums{font-family:var(--mono);font-size:.78rem;color:var(--muted)}
.tk .body{padding:0 16px 14px;border-top:1px solid var(--line)}
.tk h4{margin:14px 0 4px;font-family:var(--display);font-size:.9rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.tk p{font-size:.95rem;margin:0 0 8px}
.src{font-family:var(--mono);font-size:.74rem;color:var(--muted);word-break:break-all}
.label{display:inline-block;font-family:var(--mono);font-size:.72rem;padding:2px 8px;border-radius:4px;background:var(--warn-soft);color:var(--warn);margin-bottom:6px}
.chip{font-family:var(--mono);font-size:.78rem;padding:2px 8px;border-radius:4px;background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.chip.warn{background:var(--warn-soft);color:var(--warn)}
td.l,th.l{text-align:left;white-space:normal;min-width:180px}
.hi{font-weight:700}
.pos{color:var(--good)}.neg{color:var(--bad)}
.toc{display:flex;flex-wrap:wrap;gap:8px 14px;font-size:.92rem}
ul.plain{margin:0 0 12px;padding-left:1.3em;max-width:68ch}ul.plain li{margin-bottom:6px}
"""

NAME = cs.LABEL | {"B0_BUYHOLD": "Kupi i drži"}
RULE_TEXT = {
    "B0_BUYHOLD": "Kupi na prvom danu i ne diraj do kraja. To je mjerilo, ne strategija.",
    "K1_C13C_ORIG": "Tvoj C13C: kupi kad je cijena iznad prosjeka 200 dana i u 5 dana je pala 5 % ili više; prodaj stopom 10 % ispod najvišeg dosega. Nema cilja i nema vremenskog izlaza.",
    "K2_SMA200_TREND": "Drži dok je cijena iznad prosjeka zadnjih 200 dana; izađi kad zatvori ispod njega.",
    "K3_DONCHIAN_55_20": "Kupi kad cijena prvi put nadmaši najvišu iz zadnjih 55 dana; izađi kad padne ispod najniže iz zadnjih 20 dana.",
    "K4_TSMOM_126": "Drži dok je prinos zadnjih 126 dana (oko pola godine) pozitivan; izađi kad postane negativan.",
    "K5_SUPPORT_RESISTANCE": "Kupi kad se cijena iznad prosjeka 200 dana vrati do prijašnjeg dna (potpore); stop 3 % ispod, cilj prijašnji vrh, najdulje 30 dana.",
    "K5B_SR_BREAKOUT_RETEST": "Kupi kad cijena probije prijašnji vrh, pa se vrati do njega i ostane iznad; stop 3 % ispod razine, izlaz ispod prosjeka 50 dana.",
    "K6_MOMENTUM_CS": "Svaki mjesec poredaj dionice po prinosu zadnjih 126 dana i drži bolju polovicu; one s negativnim prinosom zamijeni gotovinom.",
    "K7_C13C_PLUS_TREND_REENTRY": "Kao C13C, ali nakon što stop izbaci poziciju, ponovno uđe čim je cijena iznad prosjeka 200 i 20 dana. Naše proširenje (novi ID).",
}
RATING_HR = {"zeleno": ("Dokazi valjani", ""), "žuto": ("Valjano, s napomenom", "warn")}


# --------------------------------------------------------------------------- formatting
def n2(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def eur(x: float) -> str:
    return f"{x:,.0f} EUR".replace(",", ".")


def pc(x: float, d: int = 0, sign: bool = False) -> str:
    s = f"{x * 100:+.{d}f}" if sign else f"{x * 100:.{d}f}"
    return s.replace(".", ",") + " %"


def day(d: Any) -> str:
    t = pd.Timestamp(d)
    return f"{t.day}. {t.month}. {t.year}."


def table(head: list[str], rows: list[list[str]], left: int = 1) -> str:
    th = "".join(
        f'<th class="{"l" if i < left else ""}">{h}</th>' for i, h in enumerate(head)
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"l" if i < left else ""}">{c}</td>' for i, c in enumerate(r)
        )
        + "</tr>"
        for r in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def img(path: Path) -> str:
    """PNG as a data URI, palette-quantized (flat notebook colours survive it) to keep the page small."""
    import base64
    import io

    from PIL import Image

    im = (
        Image.open(path)
        .convert("RGB")
        .quantize(colors=160, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    )
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def fig(fname: str, title: str, see: str, lesson: str) -> str:
    return (
        f'<figure><div class="plate"><img src="{img(OUT_DIR / fname)}" alt="{e(title)}" loading="lazy"></div>'
        f"<figcaption><b>{e(title)}.</b> {e(see)}<br><b>Pouka.</b> {e(lesson)}</figcaption></figure>"
    )


# --------------------------------------------------------------------------- build
def build(make_charts: bool = True) -> tuple[Path, list[str]]:
    info = (
        cs.make_all(SEGMENT)
        if make_charts
        else json.loads((OUT_DIR / "charts_manifest.json").read_text())
    )
    S = cs.Seg(SEGMENT)
    A, P = S.analysis, S.profile
    T = A["segment_portfolio_table_ai_era"]["contenders"]
    W = A["winner"]
    win = W["winner"]
    hold, k1, wn = T["B0_BUYHOLD"], T["K1_C13C_ORIG"], T[win]
    ev = W["euro_example_per_1000_eur"]
    tickers = S.tickers
    n_rules = len(W["eligibility"])
    ai_from, ai_to = "3. 1. 2023.", "5. 10. 2026."
    pt = A["c13c_own_algorithm"]["per_ticker"]
    log: list[str] = []

    # ---------- derived counts (checked against the JSON's own counters)
    beats_ret = [r["ticker"] for r in pt if r["beats_hold_return"]]
    beats_sh = [r["ticker"] for r in pt if r["beats_hold_sharpe"]]
    small_dd = [r["ticker"] for r in pt if r["smaller_drawdown"]]
    negative = [r["ticker"] for r in pt if r["k1_return"] < 0]
    c = A["c13c_own_algorithm"]
    assert len(beats_ret) == c["count_beats_hold_return"], "beats-return count mismatch"
    assert len(beats_sh) == c["count_beats_hold_sharpe"], "beats-sharpe count mismatch"
    assert len(small_dd) == c["count_smaller_drawdown"], "smaller-dd count mismatch"
    seg_trades = S.trades("K1_C13C_ORIG")
    tdf = pd.DataFrame(seg_trades)
    assert len(tdf) == k1["trades"], "K1 trade count mismatch"
    n_gap = int((tdf["detail"] == "gap_stop").sum())
    win_share = float((tdf["return"] > 0).mean())

    # ---------- real C13C example trades (AMAT)
    bars = load_bars("AMAT")
    close = pd.Series(bars.close, index=bars.dates)
    sma = close.rolling(200).mean()
    amat_tr = {t["entry_date"]: t for t in S.ticker_trades("AMAT", "K1_C13C_ORIG")}

    def example(entry: str) -> dict[str, Any]:
        t = amat_tr[entry]
        j = close.index.get_loc(pd.Timestamp(entry)) - 1
        return {
            "t": t,
            "sig_day": close.index[j],
            "c0": float(close.iloc[j - 5]),
            "c1": float(close.iloc[j]),
            "drop": float(close.iloc[j] / close.iloc[j - 5] - 1),
            "sma": float(sma.iloc[j]),
        }

    ex_win, ex_loss = example("2024-04-22"), example("2024-07-18")

    # ---------- header and verdict
    verdict = (
        f"Po unaprijed zadanoj mjeri najbolje je prošlo pravilo „{NAME[win]}” (Sharpe {n2(wn['sharpe'])}), ali nijedno od {n_rules} pravila, "
        f"pa ni tvoj C13C, nije prestiglo običnu kupnju i držanje: svakih uloženih 1.000 EUR (podijeljeno na {len(tickers)} dionica) do {ai_to} "
        f"vrijedi uz držanje {eur(hold['end_value_per_1000_eur'])}, uz pobjednika {eur(wn['end_value_per_1000_eur'])}, a uz C13C {eur(k1['end_value_per_1000_eur'])}."
    )
    facts = [
        (pc(hold["total_return"], 0, True), "držanje: prinos 2023.–2026.", "pos"),
        (
            pc(wn["total_return"], 0, True),
            f"pobjednik ({win.split('_')[0]}): prinos",
            "pos",
        ),
        (pc(k1["total_return"], 0, True), "C13C: prinos", "pos"),
        (
            f"{n2(hold['sharpe'])} / {n2(wn['sharpe'])} / {n2(k1['sharpe'])}",
            "Sharpe: držanje / pobjednik / C13C",
            "",
        ),
        (
            f"{pc(hold['max_drawdown'], 0)} / {pc(k1['max_drawdown'], 0)}",
            "najveći pad od vrha: držanje / C13C",
            "neg",
        ),
        (str(k1["trades"]), f"C13C trgovina na {len(tickers)} dionica", ""),
    ]
    facts_html = "".join(
        f'<div class="fact"><b class="{c_}">{v}</b><span>{e(t)}</span></div>'
        for v, t, c_ in facts
    )

    # ---------- what is this
    what = f"""
<p>Zamisli turnir. Deset tvrtki prodaje strojeve, mjerne uređaje, dijelove i materijale kojima se izrađuju računalni čipovi ({", ".join(tickers)}).
Za svaku od njih pretpostavili smo da si {ai_from} uložio 1.000 EUR (ukupno 10.000 EUR) i da od tada igra devet „pravila” koja kažu kada kupiti, a kada prodati.
Sva pravila igraju na istim cijenama do {ai_to}; svako pravilo dobije isti trošak i ne smije vidjeti budućnost.</p>
<div class="euro"><p><b>Primjer s 1.000 EUR.</b> Brojke „od 1.000 EUR” u ovoj stranici znače: uložiš 1.000 EUR podijeljeno na {len(tickers)} dionica po 100 EUR. Kupi-i-drži
ne radi ništa i na kraju vrijedi {eur(hold["end_value_per_1000_eur"])}. Tvoj C13C kupuje samo nakon pada i čuva se stopom, pa na kraju vrijedi {eur(k1["end_value_per_1000_eur"])}.
Pitanje je jesu li ta dodatna pravila zaslužila svoju složenost.</p></div>
<p>Jedno od devet pravila je <b>C13C</b>, tvoj algoritam. Jedno je <b>kupi i drži</b>, mjerilo kojem se sve ostalo mora usporediti. Ostalih sedam su poznati
klasici i jedno naše proširenje C13C-a. <b>Glavno mjerilo je AI era</b> (od 3. 1. 2023.), jer se tržište nakon 2022. promijenilo; ranije godine služe samo kao kontekst.
Ovo je <b>istraživačka simulacija na povijesnim cijenama</b>: troškovi su 2,5 baznih bodova (0,025 %) po kupnji i toliko po prodaji, bez poluge i bez kratke prodaje, i nijedan nalog nije poslan.
Rezultat u prošlosti ne obećava ništa za budućnost.</p>"""

    # ---------- segment story
    wt = A["why_together"]
    sub_rows = [[e(s["name_hr"]), ", ".join(s["tickers"])] for s in wt["subgroups"]]
    shared = "".join(f"<li>{e(x)}</li>" for x in wt["shared_behaviour_from_data_hr"])
    pn = wt["pooled_c13_premise_numbers"]
    pn_rows = [
        [
            {
                "fwd_1d": "1 dan",
                "fwd_5d": "5 dana",
                "fwd_10d": "10 dana",
                "fwd_20d": "20 dana",
            }[k],
            str(v["n_events_pooled"]),
            n2(v["mean_pct"]) + " %",
            n2(v["uncond_mean_pct_avg_of_tickers"]) + " %",
            n2(v["hit_pct"], 1) + " %",
            n2(v["uncond_hit_pct_avg_of_tickers"], 1) + " %",
        ]
        for k, v in pn.items()
    ]
    story = f"""
<p><span class="label">{e(wt["label_hr"])}</span><br>{e(wt["summary_hr"])}</p>
<p>{e(wt["drivers_hr"])}</p>
<h3>Pet skupina unutar segmenta</h3>
{table(["Skupina", "Dionice"], sub_rows, left=2)}
<h3 style="margin-top:16px">Što pokazuju naši podaci (AI era)</h3>
<ul class="plain">{shared}</ul>
<h3>Premisa C13C-a na svih deset dionica zajedno</h3>
<p>Pitanje: je li dionica nakon pada od 5 % u 5 dana (dok je iznad prosjeka 200 dana) u idućim danima rasla više nego običan dan? Događaji su prorijeđeni na najmanje 10 dana razmaka.</p>
{table(["Gledamo unaprijed", "Događaja", "Prosjek nakon pada", "Prosjek običnog dana", "Dobitnih nakon pada", "Dobitnih običnog dana"], pn_rows)}
<p class="note" style="margin-top:8px">{e(wt["pooled_c13_premise_hr"].split("UPOZORENJE:")[1].strip() if "UPOZORENJE:" in wt["pooled_c13_premise_hr"] else "")}</p>
<p class="note">{e(wt["caution_hr"])}</p>"""

    # ---------- contenders table
    rows = []
    for k_ in T:
        r = T[k_]
        rat = A["ratings"][k_]
        label, tone = RATING_HR.get(rat["rating"], ("Mjerilo", ""))
        cls = " hi" if k_ == win else ""
        rows.append(
            [
                f'<span class="{cls.strip()}">{e(NAME[k_])}</span><br><span class="note">{e(RULE_TEXT[k_])}</span>',
                pc(r["total_return"], 0, True),
                n2(r["sharpe"]),
                pc(r["max_drawdown"], 0),
                str(r["trades"]),
                n2(r["exposure_pct"], 0) + " %",
                f"{pc(r['total_return_cost_2x'], 0, True)} / {pc(r['total_return_cost_3x'], 0, True)}",
                eur(r["end_value_per_1000_eur"]),
                f'<span class="chip {tone}">{label}</span>'
                if k_ != "B0_BUYHOLD"
                else '<span class="chip">mjerilo</span>',
            ]
        )
    contenders = table(
        [
            "Pravilo",
            "Prinos",
            "Sharpe",
            "Najveći pad",
            "Trgovina",
            "U poziciji",
            "Prinos uz 2x / 3x trošak",
            "1.000 EUR postaje",
            "Dokazi",
        ],
        rows,
    )

    # ---------- per ticker table
    best = A["per_ticker_table_ai_era"]["best_by_sharpe_excluding_hold"]
    pt_rows = []
    for r in pt:
        b = best[r["ticker"]]
        pt_rows.append(
            [
                f"<b>{r['ticker']}</b>",
                pc(r["hold_return"], 0, True),
                n2(r["hold_sharpe"]),
                pc(r["hold_max_drawdown"], 0),
                pc(r["k1_return"], 0, True),
                n2(r["k1_sharpe"]),
                pc(r["k1_max_drawdown"], 0),
                str(r["k1_trades"]),
                n2(r["k1_hit_rate"] * 100, 0) + " %",
                f"{NAME[b['best_by_sharpe']].split(' ')[0]} {pc(b['return'], 0, True)} (Sharpe {n2(b['sharpe'])})",
                "da" if b["beats_hold_return"] else "ne",
            ]
        )
    pt_rows.append(
        [
            "<b>Segment</b>",
            pc(hold["total_return"], 0, True),
            n2(hold["sharpe"]),
            pc(hold["max_drawdown"], 0),
            pc(k1["total_return"], 0, True),
            n2(k1["sharpe"]),
            pc(k1["max_drawdown"], 0),
            str(k1["trades"]),
            n2(k1["hit_rate"] * 100, 0) + " %",
            f"{NAME[win].split(' ')[0]} {pc(wn['total_return'], 0, True)} (Sharpe {n2(wn['sharpe'])})",
            "ne",
        ]
    )
    per_ticker = table(
        [
            "Dionica",
            "Držanje",
            "Sharpe",
            "Pad",
            "C13C",
            "Sharpe",
            "Pad",
            "Trgovina",
            "Dobitnih",
            "Najbolje pravilo po Sharpeu (osim držanja)",
            "Prestiže držanje po prinosu?",
        ],
        pt_rows,
    )

    # ---------- C13C section
    c1w, c1l = ex_win, ex_loss
    c13c_html = f"""
<ol class="steps">
<li><b>Gleda zatvaranje dana.</b> Provjerava dvije stvari: je li cijena iznad prosjeka zadnjih 200 dana (dugoročni trend je gore) i je li pala 5 % ili više u zadnjih 5 dana.</li>
<li><b>Ako oboje vrijedi, kupuje sljedeće jutro na otvaranju.</b> Odluka se donosi navečer, a nalog je za sutra. Tako pravilo nikad ne zna budućnost.</li>
<li><b>Odmah postavlja stop 10 % ispod najvišeg dosega.</b> Stop se samo podiže, nikad spušta. Ako cijena padne do stopa, pozicija se prodaje.</li>
<li><b>Nema cilja ni roka.</b> Pozicija traje dok je stop ne izbaci (ili do kraja simulacije).</li>
</ol>
<div class="euro"><p><b>Stvaran primjer, AMAT.</b> {day(c1w["sig_day"])}: zatvaranje {n2(c1w["c1"])} USD, pet dana ranije {n2(c1w["c0"])} USD, pad {pc(c1w["drop"], 1)}; prosjek 200 dana je {n2(c1w["sma"])} USD pa je cijena iznad njega.
Signal. Sutradan, {day(c1w["t"]["entry_date"])}, kupnja po {n2(c1w["t"]["raw_entry"])} USD. Stop je kasnije slijedio cijenu prema gore i izbacio poziciju {day(c1w["t"]["exit_date"])} po {n2(c1w["t"]["raw_exit"])} USD:
{pc(c1w["t"]["return"], 1, True)} nakon troškova. Iz 1.000 EUR u ovoj dionici postalo bi {eur(1000 * (1 + c1w["t"]["return"]))} u {c1w["t"]["bars_held"]} radnih dana.</p></div>
<div class="euro"><p><b>Stvaran gubitak, isto AMAT.</b> {day(c1l["sig_day"])}: pad {pc(c1l["drop"], 1)} u 5 dana, kupnja {day(c1l["t"]["entry_date"])} po {n2(c1l["t"]["raw_entry"])} USD,
a već {day(c1l["t"]["exit_date"])} stop prodaje po {n2(c1l["t"]["raw_exit"])} USD: {pc(c1l["t"]["return"], 1, True)}. Iz 1.000 EUR ostalo bi {eur(1000 * (1 + c1l["t"]["return"]))}.
Taj se pad nastavio, pa „kupi pad” u padajućem tržištu kupuje prerano.</p></div>
<h3>Kako je C13C prošao na ovom segmentu</h3>
<ul class="plain">
<li>Prinos u AI eri {pc(k1["total_return"], 1, True)} naspram {pc(hold["total_return"], 1, True)} za držanje; Sharpe {n2(k1["sharpe"])} naspram {n2(hold["sharpe"])}.</li>
<li>Najveći pad od vrha {pc(k1["max_drawdown"], 1)} naspram {pc(hold["max_drawdown"], 1)} za držanje: na 1.000 EUR to je najgori gubitak od vrha od {eur(k1["worst_loss_per_1000_eur"])} naspram {eur(hold["worst_loss_per_1000_eur"])}.</li>
<li>{k1["trades"]} trgovina, od kojih {n2(win_share * 100, 0)} % dobitnih. Prosječni dobitak {pc(k1["avg_win"], 1, True)}, prosječni gubitak {pc(k1["avg_loss"], 1)}; u poziciji je oko {n2(k1["exposure_pct"], 0)} % vremena.</li>
<li>Po dionicama: prestigao je držanje po prinosu na {len(beats_ret)} od {len(tickers)}, po Sharpeu na {len(beats_sh)} ({", ".join(beats_sh)}), a imao je manji najveći pad na {len(small_dd)} od {len(tickers)}.
{("Negativan ukupni prinos imao je na: " + ", ".join(negative) + ".") if negative else ""}</li>
<li>{n_gap} od {len(tdf)} izlaza dogodilo se preko noći, ispod stopa (jaz): stop ne štiti od vijesti koje stignu kad je burza zatvorena.</li>
</ul>
<div class="cols">
<div><h3>Zašto bi premisa mogla vrijediti</h3><p>Nakon pada od 5 % u 5 dana dionice su u AI eri u idućih 5 dana u prosjeku rasle {n2(pn["fwd_5d"]["mean_pct"])} %, a običan dan donosi {n2(pn["fwd_5d"]["uncond_mean_pct_avg_of_tickers"])} %.
Dok je cijena iznad prosjeka 200 dana, pad je češće bio privremen. Stop reže gubitke na oko 10 %, a dobici nisu ograničeni.</p></div>
<div class="risk"><h3>Zašto ne drži</h3><p>Ulazi samo nakon pada, a stop od 10 % u dionicama koje se u godini tresu 40 do 80 % često izbaci poziciju običnim treskanjem. Zato je oko pola vremena vani, pa propusti
velik dio rasta: od 100 najboljih dana ovih dionica (10 po dionici) bio je unutra samo {info["lesson_numbers"]["k1"]}. U snažnom bik-tržištu kao što je AI era držanje je teško pobijediti.</p></div>
</div>"""

    # ---------- figures
    price_counts = {
        t: len(S.ticker_trades(t, "K1_C13C_ORIG")) for t in ["AMAT", "LRCX", "KLAC"]
    }
    chk = "; ".join(info["checks"])
    log.append("stop-line check: " + chk)
    ep = W["drawdown_episodes_from_equity_curves"]
    h_ep = ep["B0_BUYHOLD"]["window_2024_07_to_2025_04"]
    c_ep = ep["K1_C13C_ORIG"]["window_2024_07_to_2025_04"]
    lesson = info["lesson_numbers"]
    figs_main = [
        fig(
            "01_cijene_c13c.png",
            "Cijena i svaki C13C ulaz i izlaz (AMAT, LRCX, KLAC)",
            f"Plava crta je cijena zatvaranja, isprekidana je prosjek zadnjih 200 dana, zeleni trokut je kupnja, crveni obrnuti trokut izbacivanje stopom, a crvena stepenasta crta je klizni stop jedne trgovine. "
            f"Ulaza je mnogo: AMAT {price_counts['AMAT']}, LRCX {price_counts['LRCX']}, KLAC {price_counts['KLAC']} trgovina u AI eri. Cijena je na logaritamskoj skali, pa isti razmak znači isti postotak.",
            "Stop prati cijenu prema gore i štiti dobitak, ali dionica koja se u godini kreće 40 do 60 % često padne 10 % i prije nego nastavi rasti. Zato C13C stalno izlazi i ponovno ulazi.",
        ),
        fig(
            "02_rast_1000_eur.png",
            "Rast 1.000 EUR: držanje, C13C i pobjednik",
            f"Siva crta je kupi-i-drži ({eur(hold['end_value_per_1000_eur'])} na kraju), zelena pobjednik {NAME[win]} ({eur(wn['end_value_per_1000_eur'])}), plava C13C ({eur(k1['end_value_per_1000_eur'])}). "
            f"Plavo polje je razdoblje kad je C13C držao najviše 1 od 10 dionica, a ostalo je bila gotovina.",
            f"U padu od {day(h_ep['peak_date'])} do {day(h_ep['bottom_date'])} držanje je izgubilo {pc(-h_ep['depth'], 0)} vrijednosti, a C13C {pc(-c_ep['depth'], 0)}. "
            "Ta ušteda ima cijenu: kad je vani, C13C propušta i oporavak, pa mu je krivulja cijelo vrijeme ispod držanja.",
        ),
        fig(
            "03_pad_od_vrha.png",
            "Najveći pad od vrha",
            f"Svaka crta pokazuje koliko je vrijednost u svakom danu ispod svog dotadašnjeg najboljeg trenutka. Držanje je najdublje palo {pc(h_ep['depth'], 1)} ({day(h_ep['bottom_date'])}); "
            f"C13C je najdublje pao {pc(k1['max_drawdown'], 1)}.",
            f"Pad od {n2(-h_ep['depth'] * 100, 1)} % znači da 1.000 EUR u vrhu postane oko {eur(1000 * (1 + h_ep['depth']))}. Tebi pad ne snižava ocjenu (blagi kritičar), ali je dobro znati što bi podnosio: sektor je u AI eri dvaput tvrdo padao.",
        ),
        fig(
            "04_trgovine.png",
            "Svaka C13C trgovina",
            f"Svaka točka je jedna trgovina: vodoravno koliko je radnih dana trajala (logaritamska os), okomito koliko je donijela. Zeleno su dobici, crveno gubici, krugovi su izlazi preko noći ({n_gap} od {len(tdf)}).",
            f"{n2(win_share * 100, 0)} % trgovina je dobitnih; prosječni dobitak {pc(k1['avg_win'], 1, True)} veći je od prosječnog gubitka {pc(k1['avg_loss'], 1)}. Takva shema može biti isplativa i uz manje od pola dobitnika, ali traži strpljenje s mnogo malih gubitaka.",
        ),
        fig(
            "05_ljestvica.png",
            "Ljestvica pravila: prinos i Sharpe",
            f"Lijevo ukupni prinos u AI eri, desno Sharpe (prinos u odnosu na treskanje). Isprekidana crta je držanje: {pc(hold['total_return'], 0, True)} i Sharpe {n2(hold['sharpe'])}. Zeleno je pobjednik po Sharpeu, plavo C13C.",
            f"Prva četiri po Sharpeu ({', '.join(NAME[k_].split(' ')[0] + ' ' + n2(T[k_]['sharpe']) for k_ in W['ranking_by_sharpe'][:4])}) razlikuju se tek u drugoj decimali, a pokrenuto je 9 pravila: najbolje je djelomično i sreća.",
        ),
        fig(
            "06_troskovi.png",
            "Otpornost na troškove 1x, 2x i 3x",
            "Za svako pravilo tri stupca: završna vrijednost od 1.000 EUR uz osnovni trošak (2,5 baznih bodova po strani), dvostruki i trostruki. Desno: koliko EUR trostruki trošak oduzme.",
            f"Najviše plaćaju pravila s najviše trgovina (C13C {n2((k1['total_return'] - k1['total_return_cost_3x']) * 1000, 0)} EUR, K7 {n2((T['K7_C13C_PLUS_TREND_REENTRY']['total_return'] - T['K7_C13C_PLUS_TREND_REENTRY']['total_return_cost_3x']) * 1000, 0)} EUR na 1.000 EUR), ali nijedno ne mijenja predznak. "
            "Što nije u računu: minimalna provizija po nalogu, koja bi za male naloge bila veća.",
        ),
        fig(
            "07_najbolji_dani.png",
            "Ključna pouka: rast dolazi u rijetkim danima",
            "Lijevo za svaku dionicu: prinos držanja i prinos kad se izbaci samo 10 najboljih dana (brojka je udio prinosa koji ti dani nose). Desno: koliko od tih 10 dana je C13C, odnosno pobjednik, bio unutra cijeli dan.",
            f"C13C je bio unutra {lesson['k1']} od {lesson['total']} najboljih dana, pobjednik {lesson['k4']} od {lesson['total']}. Pravilo koje je često vani propušta te dane, a dani se ne daju predvidjeti. To je glavni razlog zašto držanje u ovom segmentu pobjeđuje.",
        ),
    ]

    # ---------- behaviour charts
    sr = info["sr_numbers"]
    AI = {t: P["companies"][t]["stats"]["ai_era"] for t in tickers}
    figs_behav = [
        fig(
            "08_karakter.png",
            "Treskanje i veza s poluvodičima",
            "Lijevo koliko se cijena u godini tipično „trese” (volatilnost), prije 2023. i u AI eri. Desno beta prema SMH (indeks poluvodiča), s korelacijom iznad stupca.",
            f"Sve su dionice pojačana verzija cijelog poluvodičkog tržišta (beta od {n2(min(a['beta_smh'] for a in AI.values()))} do {n2(max(a['beta_smh'] for a in AI.values()))}, korelacija od {n2(min(a['corr_smh'] for a in AI.values()))} do {n2(max(a['corr_smh'] for a in AI.values()))}): kupovina deset njih nije deset nezavisnih oklada. SMH je ovdje samo mjerilo, a ne prijedlog (američki ETF vjerojatno nije dostupan malom ulagaču iz EU, nepotvrđeno).",
        ),
        fig(
            "09_nakon_pada.png",
            "Što se događa nakon pada od 5 % u 5 dana",
            "Za svaku dionicu: prosječni prinos u idućih 5 i 20 dana nakon takvog pada (zeleno) naspram običnog dana (sivo).",
            "Pad se u prosjeku isplatio češće nego običan dan, ali je statistički uvjerljiv tek u rijetkim slučajevima; dionice padaju istih dana pa je neovisnih događaja manje nego što izgleda.",
        ),
        fig(
            "10_sezonalnost.png",
            "Sezonalnost po mjesecima",
            "Svaki kvadratić je prosječni prinos dionice u tom kalendarskom mjesecu u AI eri. Što je zelenije, to bolje.",
            "U AI eri svaki mjesec ima samo 3 do 4 opažanja po dionici, pa obrasci (npr. jak lipanj, slab srpanj) nisu dokaz. Služi samo da vidiš koliko su podaci tanki.",
        ),
        fig(
            "11_anatomija_pada.png",
            "Anatomija dva najveća pada (AMAT, ONTO, ACMR)",
            "Crveno polje je put od vrha do dna, žuto polje put oporavka do starog vrha. Zeleni kružić je vrh, crveni dno; uz svaki pad su datumi i iznosi za 1.000 EUR.",
            "Najveći pad počeo je kod 9 od 10 dionica između 3. i 16. 7. 2024., a dno je kod 8 od 10 stiglo između 4. i 8. 4. 2025.: pad je bio zajednički, pa raspršenost među ovim dionicama nije pomogla. ACMR je iznimka (pad od 1. 3. 2024.).",
        ),
        fig(
            "12_potpora_otpor_stope.png",
            "Potpora i otpor: stvarne razine naspram slučajnih",
            "Koliko često je razina (prijašnje dno ili vrh) izdržala kad se cijena vratila do nje u idućih 5 dana, uspoređeno s proizvoljnim razinama kao kontrolom.",
            "Stvarne razine nisu bile pouzdano bolje od slučajnih, pa crte na grafu nemaju posebnu snagu: u ovim podacima K5 i K5B nemaju razloga biti pobjednici, što se i vidi u ljestvici.",
        ),
        fig(
            "13_potpora_primjer.png",
            "Dva stvarna dodira potpore (AMAT, listopad 2024.)",
            f"Crvena crta: potpora s dna {day(sr['probijena']['pivot'])} ({n2(sr['probijena']['level'])} USD) dodirnuta {day(sr['probijena']['touch'])} i probijena. "
            f"Zelena crta: potpora s dna {day(sr['izdržala']['pivot'])} ({n2(sr['izdržala']['level'])} USD) dodirnuta {day(sr['izdržala']['touch'])} i izdržala.",
            "Dva primjera pokazuju što statistika broji, ali ne dokazuju ništa: jedan je izdržao, drugi nije, a oba izgledaju jednako razumno u trenutku dodira.",
        ),
    ]

    # ---------- behaviour cards
    cards = []
    ai_stats = {t: P["companies"][t]["stats"]["ai_era"] for t in tickers}
    for t in tickers:
        cc = A["company_cards"][t]
        bn = cc["behaviour_numbers"]
        m = cc["mechanism_hr"]
        gaps = ", ".join(
            f"{day(g['date'])} ({n2(g['gap_pct'], 1)} %)" for g in bn["largest_gaps"]
        )
        srcs = "<br>".join(e(s_) for s_ in cc["sources"])
        cards.append(
            f"""<details class="tk"><summary><span class="name">{t}</span>
<span class="nums">vol {n2(bn["ann_vol_pct"], 1)} % · beta {n2(bn["beta_smh"])} · iznad SMA200 {n2(bn["share_days_above_sma200_pct"], 0)} % dana · 10 najboljih dana nosi {n2(bn["top10_share_pct"], 0)} %</span></summary>
<div class="body">
<h4>Čime se bavi</h4><span class="label">{e(cc["mechanism_label"])}</span>
<p><b>Prodaje:</b> {e(m["sells"])}</p><p><b>Što pokreće prihod:</b> {e(m["drivers"])}</p><p><b>Mjesto u lancu:</b> {e(m["chain"])}</p>
<p><b>Ciklus:</b> {e(m["cycle"])}</p><p><b>Što šteti:</b> {e(m["hurts"])}</p><p class="src">Izvor: {srcs}</p>
<h4>Što pokazuju naši podaci (AI era)</h4>
<p>{e(cc["volatility_beta_hr"])}</p><p>{e(cc["after_5d_dip_hr"])}</p><p>{e(cc["worst_drawdowns_hr"])}</p>
<p>{e(cc["support_resistance_hr"])}</p><p><b>Najveći jazovi (otvaranje naspram prethodnog zatvaranja):</b> {gaps}.</p>
<p><b>Koji algoritam mu odgovara:</b> {e(cc["algorithm_fit_hr"])}</p>
</div></details>"""
        )
    # numbers in the cards are the profile's own strings; cross-check the headline ones
    for t in tickers:
        bn = A["company_cards"][t]["behaviour_numbers"]
        s_ = ai_stats[t]
        assert (
            abs(bn["ann_vol_pct"] - s_["ann_vol_pct"]) < 1e-9
            and abs(bn["beta_smh"] - s_["beta_smh"]) < 1e-9
        ), t
        assert (
            abs(
                bn["top10_share_pct"]
                - s_["top10_best_days"]["sum_logret_share_of_total_pct"]
            )
            < 1e-9
        ), t

    # ---------- EU/HR
    eu_rows = [
        [
            f"<b>{t}</b>",
            f'<span class="chip warn">{e(A["eu_hr_notes"][t]["status"])}</span>',
        ]
        for t in tickers
    ]
    eu = f"""
<p>Sve deset dionica su <b>pojedinačne američke dionice</b>, a ne ETF-ovi. EU mali ulagači općenito mogu kupovati pojedinačne američke dionice, ali <b>dostupnost i uvjeti za tvoj Interactive Brokers račun su nepotvrđeni</b>
dok ih ne provjeriš u samom IBKR-u. Ovdje ništa ne tvrdimo o porezu ni o dozvolama brokera.</p>
{table(["Dionica", "Dostupnost za tvoj račun"], eu_rows, left=1)}
<ul class="plain">
<li><b>Valuta:</b> cijene su u USD, a račun je u EUR. U simulaciji su USD tretirani kao EUR, tečaj i trošak konverzije nisu modelirani, pa je stvarni rezultat drukčiji (nepotvrđeno za koliko).</li>
<li><b>Razlomljene dionice:</b> simulacija ulaže cijeli iznos (npr. 3,33 dionice). Dopušta li IBKR to za pojedinu dionicu, nepotvrđeno je.</li>
<li><b>Minimalna provizija po nalogu:</b> nepotvrđeno za tvoj tarif; za male naloge bila bi veća od simuliranih 0,025 %.</li>
<li><b>ETF-ovi:</b> SMH i slični američki ETF-ovi koriste se samo kao mjerilo kretanja, ne kao nešto što možeš kupiti. Američki ETF-ovi često nisu dostupni malim ulagačima iz EU (nema KID dokumenta); europski ekvivalenti zahtijevaju novo testiranje.</li>
<li><b>Vrijeme:</b> američka burza otvara u 15:30 po zagrebačkom vremenu. Simulacija kupuje na otvaranju dan nakon signala.</li>
<li><b>Poluga i kratka prodaja:</b> nisu korištene.</li>
</ul>
<p class="note">{e(A["eu_hr_notes"][tickers[0]]["note_hr"])}</p>"""

    # ---------- limits
    limits = f"""
<div class="limit">
<p><b>Što ova simulacija ne modelira:</b></p>
<ul class="plain">
<li>Tečaj EUR/USD i trošak konverzije (cijene u USD tretirane kao EUR).</li>
<li>Dividende (cijene su prilagođene samo za splitove, pa je to cjenovni, a ne ukupni prinos).</li>
<li>Porezi i evidencija; ovo nije porezni savjet.</li>
<li>Minimalna provizija po nalogu kod brokera, proklizavanje veće od 2,5 baznih bodova, djelomična ispunjenja i ograničenja likvidnosti (važno za tanko trgovane dionice kao što je ACMR).</li>
<li>Posudba i kratka prodaja: nema ih.</li>
<li>Stvarne jazove na lošim vijestima: stop se ispunjava po otvaranju, ali stvarni jaz može biti gori.</li>
</ul>
<p><b>Ograničenja zaključka:</b></p>
<ul class="plain">{"".join(f"<li>{e(x)}</li>" for x in A["caveats_hr"])}</ul>
<p>{e(A["audit_status_hr"])}</p>
</div>"""

    # ---------- glossary
    gl = [
        (
            "C13C",
            "Tvoj algoritam: kupi nakon pada od 5 % u 5 dana ako je cijena iznad prosjeka 200 dana, stop 10 % ispod najvišeg dosega. Primjer: dionica od 100 EUR padne na 95 EUR, kupiš, a ako kasnije dosegne 150 EUR, stop je na 135 EUR.",
        ),
        ("Kupi i drži", A["glossary_hr"]["kupi i drži (B0)"]),
        (
            "Prosjek 200 dana (SMA200)",
            "Prosjek zadnjih 200 dnevnih zatvaranja, grubi pokazatelj dugoročnog trenda. Primjer: prosjek je 80 EUR, cijena 90 EUR: cijena je iznad prosjeka, trend je uzlazni, kao kad se penješ uzbrdo.",
        ),
        ("Stop", A["glossary_hr"]["stop"]),
        (
            "Jaz (gap)",
            A["glossary_hr"]["jaz (gap)"]
            + " Primjer: stop je na 90 EUR, dionica otvori na 85 EUR; prodaja je po 85 EUR, ne po 90 EUR.",
        ),
        ("Prinos", A["glossary_hr"]["prinos"]),
        (
            "Sharpe",
            A["glossary_hr"]["Sharpe"]
            + " Primjer: dva vozača stignu u isto vrijeme, ali jedan vozi mirno, a drugi trzajući; mirniji ima veći Sharpe.",
        ),
        (
            "Pad od vrha (drawdown)",
            A["glossary_hr"]["pad od vrha (max drawdown)"]
            + " Da bi se vratio na 1.000 EUR, ostatak mora porasti 100 %.",
        ),
        (
            "Troškovi i bazni bod (bps)",
            "Bazni bod je stoti dio postotka. Primjer: 2,5 baznih bodova je 0,025 %, pa na kupnju od 1.000 EUR platiš 0,25 EUR, a toliko i pri prodaji. Test 2x je 5 baznih bodova, 3x je 7,5.",
        ),
        ("U poziciji (izloženost)", A["glossary_hr"]["izloženost"]),
        ("Uspješnost (hit rate)", A["glossary_hr"]["uspješnost (hit rate)"]),
        ("Volatilnost", P["glossary_hr"]["volatilnost"]),
        ("Beta", P["glossary_hr"]["beta"]),
        ("Korelacija", P["glossary_hr"]["korelacija"]),
        ("Autokorelacija", P["glossary_hr"]["autokorelacija"]),
        ("Omjer varijance", P["glossary_hr"]["omjer varijance (VR)"]),
        ("Potpora i otpor", P["glossary_hr"]["potpora i otpor"]),
        (
            "Capex",
            "Kapitalni izdaci: novac koji tvornice čipova troše na strojeve i nove linije. Primjer: kad tvornica odluči potrošiti 10 milijardi EUR na opremu, to je prihod za tvrtke iz ovog segmenta; kad ulaganja stanu, prihod padne.",
        ),
        (
            "Pobjednik segmenta",
            "Unaprijed zadano: najviši Sharpe u AI eri među pravilima s barem 20 trgovina i pozitivnim prinosom uz trošak 2x. Držanje se uvijek uspoređuje zasebno.",
        ),
        (
            "AI era",
            "Razdoblje od 3. 1. 2023. do 5. 10. 2026. Glavno mjerilo, jer se tržište nakon 2022. promijenilo; stariji podaci su samo kontekst.",
        ),
        (
            "Gledanje u budućnost (lookahead)",
            "Pogreška kad test slučajno koristi podatak koji u tom trenutku nije postojao, kao da pišeš ispit s poznatim rješenjima. Zato je svako pravilo provjereno na odsječenim podacima.",
        ),
        (
            "Prilagođeno podacima (overfitting)",
            "Pravilo namješteno da savršeno pogodi prošlost, a ne zna ništa o budućnosti. Zato su parametri fiksni, bez ugađanja.",
        ),
        (
            "Broj pokušaja (K) i deflated Sharpe",
            "Što više pravila isprobaš, to je veća šansa da jedno izgleda dobro čistom srećom. Kad 500 puta baciš novčić, negdje će pasti osam glava zaredom. Deflated Sharpe zato traži veći rezultat kad je pokušaja više; ovdje je informativan.",
        ),
        (
            "PSR",
            "Vjerojatnost da je pravi Sharpe iznad nule, uzimajući u obzir iskrivljenost i debele repove. Primjer: PSR 0,98 znači da je skoro sigurno iznad nule, ali ne znači da je pravilo bolje od držanja.",
        ),
        ("Ocjena blagog kritičara", A["rating_rule_hr"]),
    ]
    gloss = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in gl)

    # ---------- assemble
    toc = (
        '<nav class="toc"><a href="#sto">Što je ovo</a><a href="#prica">Priča segmenta</a><a href="#ljestvica">Ljestvica</a><a href="#dionice">Po dionici</a>'
        '<a href="#c13c">C13C</a><a href="#grafovi">Grafovi</a><a href="#ponasanje">Kako se ponaša svaka dionica</a><a href="#eu">EU/HR</a><a href="#granice">Granice</a><a href="#rjecnik">Rječnik</a></nav>'
    )
    body = f"""<main>
<header><span class="tag">AI lanac · segment {SEGMENT} · istraživačka simulacija</span>
<h1>Oprema za proizvodnju čipova</h1>
<p class="verdict-big">{e(verdict)}</p>
<div class="badge-row"><span class="badge warn">Ne pobjeđuje držanje</span>
<span class="note">Pobjednik ima valjane dokaze (blagi kritičar: zeleno), ali manji prinos od držanja. Nije formalni Critic PASS laboratorija.</span></div>
{toc}</header>
<div class="facts">{facts_html}</div>
<p class="note">Razdoblje: AI era, {ai_from} do {ai_to}. Troškovi: 2,5 baznih bodova po strani (0,025 %), stres 2x i 3x. Istraživačka simulacija na povijesnim cijenama, bez poluge i kratke prodaje, bez ijednog naloga.</p>
<section id="sto"><h2>Što je ovo</h2>{what}</section>
<section id="prica"><h2>Priča segmenta: što ih povezuje</h2>{story}</section>
<section id="ljestvica"><h2>Ljestvica devet pravila</h2>
<p>Svih devet pravila igralo je na svih deset dionica zajedno (po 100 EUR na dionicu od svake uložene 1.000 EUR). Pobjednik je određen unaprijed: najviši Sharpe uz barem 20 trgovina i pozitivan prinos i uz trostruki trošak.</p>
{contenders}
<p class="note" style="margin-top:8px">{e(A["rating_rule_hr"])}</p>
<p class="note">{e(W["text_hr"].split("Pažnja:")[0].strip())}</p></section>
<section id="dionice"><h2>Po dionici (AI era)</h2>
<p>Isti turnir, ali gledan po jednoj dionici sa 1.000 EUR. Pravilo K6 (rotacija) ne postoji za jednu dionicu pa nije u ovoj tablici.</p>
{per_ticker}
<p class="note" style="margin-top:8px">{e(A["per_ticker_table_ai_era"]["note_hr"])} {e(best["AMAT"]["note_hr"])}</p></section>
<section id="c13c"><h2>Tvoj C13C na ovom segmentu</h2>{c13c_html}</section>
<section id="grafovi"><h2>Grafovi s bilješkama učitelja</h2>
<p>Svi grafovi su nacrtani iz stvarnih rezultata. Crveni tekst na dnu svakog grafa je „bilješka učitelja” s primjerom u eurima, a rukom pisane bilješke pokazuju točno na ono što treba gledati.</p>
{"".join(figs_main)}</section>
<section id="ponasanje"><h2>Kako se ponaša svaka dionica</h2>
<p>Prvo ponašanje svih deset dionica zajedno (opis, ne strategija), a zatim kartica za svaku dionicu: što tvrtka radi, što joj pokreće prihod i što pokazuju naši podaci. Mehanizmi poslovanja dolaze iz javnih izvora i označeni su kao takvi; brojke dolaze iz naših cijena.</p>
{"".join(figs_behav)}
<h3>Kartice po dionici</h3><div class="cards">{"".join(cards)}</div></section>
<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>{eu}</section>
<section id="granice"><h2>Granice: što nije modelirano</h2>{limits}</section>
<section id="rjecnik"><h2>Rječnik pojmova, s primjerima u eurima</h2><dl>{gloss}</dl></section>
<section class="verdict"><h3>Zaključak</h3><p>Na ovom segmentu držanje je bilo teško pobijediti. Najbolje pravilo ({NAME[win]}) dalo je {pc(wn["total_return"], 0, True)} naspram {pc(hold["total_return"], 0, True)}, a C13C {pc(k1["total_return"], 0, True)} uz najveći pad od {pc(k1["max_drawdown"], 0)} umjesto {pc(hold["max_drawdown"], 0)}.
C13C je čuvao novac u padu 2024.–2025., ali je platio propuštenim rastom. Razlike među vodećim pravilima su male, a pokrenuto je 9 pravila, pa ovo nije dokaz prednosti nijednog od njih. Signal za ulaganje ne postoji: ovo je istraživanje.</p></section>
<footer>Simulacija na povijesnim podacima (data/ohlcv, zadnji dan {ai_to}): odluka na zatvaranju, kupnja na idućem otvaranju, trošak 2,5 baznih bodova po strani, bez poluge i bez kratke prodaje, cijene u USD tretirane kao EUR.
Rezultati u prošlosti ne obećavaju budućnost. {e(A["disclaimer_hr"])} Pravila su zamrznuta (strategies/frozen/2026-10-14_AICHAIN_*.json).</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + HEAD.format(title=e(TITLE), css=CSS + EXTRA_CSS)
    )
    page = head + body
    out = OUT_DIR / "artifact.html"
    out.write_text(page)
    log.append(f"written {out} ({out.stat().st_size / 1e6:.2f} MB)")
    return out, log


if __name__ == "__main__":
    path, messages = build(make_charts="--no-charts" not in sys.argv)
    print(path)
    for m_ in messages:
        print(m_)
