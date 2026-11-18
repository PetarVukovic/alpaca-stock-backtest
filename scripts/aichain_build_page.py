"""Build the self-contained Croatian artifact page for one AICHAIN segment.

Usage:
  .venv/bin/python scripts/aichain_build_page.py ai_chips_logic            # build the page
  .venv/bin/python scripts/aichain_build_page.py ai_chips_logic --verify   # build, then re-read numbers vs raw results

Inputs: reports/research/AICHAIN_20261014/segments/{segment}/analysis.json, profile.json, the PNG charts made by
lab/aichain/notebook_charts.py, and results/*.json. Output: segments/{segment}/artifact.html (charts embedded as
data URIs, no external resources except Google Fonts). Reads only; never places orders.
The CSS and a few glossary entries are imported from scripts/top10_build_artifact.py (not modified).
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import top10_build_artifact as top10  # noqa: E402

from lab.aichain.notebook_charts import (  # noqa: E402
    C13,
    HOLD,
    Data,
    demo_trade,
    hr,
    iso_to_hr,
)

BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"

EXTRA_CSS = """
.tagline{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.verdict-top{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:6px;padding:18px 20px}
.verdict-top p{font-size:1.15rem;line-height:1.5;margin:0 0 8px;max-width:none}
.verdict-top p:last-child{margin-bottom:0}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.chip{font-family:var(--mono);font-size:.78rem;padding:3px 9px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted)}
.chip.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.chip.good{background:var(--good-soft);color:var(--good);border-color:transparent}
.chip.bad{background:var(--bad-soft);color:var(--bad);border-color:transparent}
.teach{background:var(--accent-soft);border-radius:6px;padding:14px 16px;margin:0 0 14px}
.teach p{margin:0 0 8px;max-width:none}.teach p:last-child{margin:0}
.plate{overflow-x:auto}
.plate img{min-width:720px}
@media (min-width:860px){.plate img{min-width:0}}
.swipe{font-size:.82rem;color:var(--muted);margin:6px 0 0}
@media (min-width:860px){.swipe{display:none}}
.tcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.tcard{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;display:flex;flex-direction:column;gap:8px;min-width:0}
.tcard h3{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:0}
.tcard ul{margin:0;padding-left:1.15em;font-size:.93rem}
.tcard li{margin-bottom:4px}
.tcard details{border:0;background:transparent}
.tcard summary{padding:4px 0;font-size:.9rem}
.tcard details p{font-size:.9rem;color:var(--muted)}
td.l,th.l{text-align:left}
td.wrap{white-space:normal;min-width:260px}
.pos{color:var(--good)}.neg{color:var(--bad)}
.ok{font-family:var(--mono);font-size:.75rem}
.cmp td:first-child{font-family:var(--display);font-weight:600}
h2{margin-top:4px}
section>.lead2{color:var(--muted);max-width:66ch}
"""

GRADE = {
    "zeleno": ("dokaz valjan", "good"),
    "žuto": ("valjan, ali ugođeno", "warn"),
    "crveno": ("dokaz nevaljan", "bad"),
    "mjerilo": ("mjerilo, ne pravilo", ""),
}

RULE_TEXT = {
    "B0_BUYHOLD": "Kupiš prvi dan i ne prodaješ ništa. Mjerilo kojem se sve ostalo mora usporediti.",
    "K1_C13C_ORIG": "Petrov C13C. Kupi kad je cijena iznad prosjeka zadnjih 200 dana (SMA200) i u 5 dana je pala 5 % ili više. "
    "Prodaje kad cijena padne 10 % ispod najvišeg vrha nakon kupnje (pomični stop).",
    "K2_SMA200_TREND": "Drži dok je cijena iznad SMA200, izađi kad se zatvori ispod njega.",
    "K3_DONCHIAN_55_20": "Kupi kad cijena prvi put nadmaši najvišu iz zadnjih 55 dana, prodaj kad padne ispod najniže iz zadnjih 20 dana.",
    "K4_TSMOM_126": "Drži dok je prinos zadnjih 126 dana (oko šest mjeseci) pozitivan.",
    "K5_SUPPORT_RESISTANCE": "Kupi kad se cijena odbije od donje razine s grafa (potpora), a iznad je još prostora do gornje razine. "
    "Stop 3 % ispod potpore, cilj je gornja razina, najdulje 30 dana.",
    "K5B_SR_BREAKOUT_RETEST": "Kupi kad cijena probije gornju razinu, vrati se na nju i odbije se. Izlaz ispod prosjeka zadnjih 50 dana ili stop 3 % ispod razine.",
    "K6_MOMENTUM_CS": "Samo za cijelu skupinu: svaki mjesec poredaj 11 dionica po prinosu zadnjih oko šest mjeseci i drži bolju polovicu; "
    "dionicu s negativnim prinosom zamijeni gotovinom.",
    "K7_C13C_PLUS_TREND_REENTRY": "Kao C13C, ali nakon izbijanja stopom ponovo kupi čim je cijena opet iznad SMA200 i iznad 20-dnevnog prosjeka. "
    "Smišljeno nakon što su rezultati C13C-a bili poznati, pa nosi rizik ugađanja.",
}

CHARACTER_PLAIN = {
    "sklonost vraćanju": "gumica: pomaci se kroz 20 dana djelomično poništavaju",
    "blizu slučajnog hoda": "bez jasnog obrasca: dan-dva unaprijed se ne može naslutiti",
    "sklonost nastavku trenda": "što raste, to sklono nastavlja",
}


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


# Lab words in the analysis texts replaced by plain Croatian (order matters: specific phrases first)
PLAIN = [
    ("INTC je jedini ticker gdje je neki suparnik (126-dnevni zamah, K4) pobijedio držanje po prinosu.",
     "INTC je jedina dionica na kojoj je neko pravilo (126-dnevni zamah, K4) pobijedilo držanje po prinosu."),
    ("Ni na jednom tickeru nije pobijedio", "Ni na jednoj dionici nije pobijedio"),
    ("ni na jednom od 11 tickera", "ni na jednoj od 11 dionica"),
    ("Ticker po ticker", "Dionicu po dionicu"),
    ("Memorijski segment je zaseban.", "Memorijske dionice obrađene su zasebno."),
    ("Segment pada kao cjelina.", "Cijela skupina pada zajedno."),
    ("Segment se kreće", "Skupina se kreće"),
    ("(gap_stop)", "(jaz preko noći)"),
    ("'gap_stop'", "'izlaz zbog jaza preko noći'"),
    ("po sleeveu", "po pretincu"),
    ("sleeve-ova", "pretinaca"),
    ("tickera", "dionica"),
    ("tickeru", "dionici"),
    ("ticker", "dionica"),
    ("na segmentu", "u skupini"),
    ("u segmentu", "u skupini"),
    ("ovom segmentu", "ovoj skupini"),
    ("segmenta", "skupine"),
    ("6 segmenata", "6 skupina"),
    ("43 dionica", "43 dionice"),
    ("AI era je bik-tržište čipova", "AI era je razdoblje snažnog rasta čipova"),
    ("u bik-tržištu", "u razdoblju općeg rasta"),
    ("suparnika", "pravila"),
    ("suparnike", "pravila"),
    ("suparnik", "pravilo"),
]


def plain(x: str) -> str:
    for a, b in PLAIN:
        x = x.replace(a, b)
    return x.replace("..", ".")


def t(x: str) -> str:
    """Escape text, rewrite ISO dates as Croatian dates and swap lab words for plain ones."""
    return e(iso_to_hr(plain(x)))


def eur(x: float) -> str:
    return f"{hr(x)} EUR"


def pct(x: float, nd: int = 1, sign: bool = False) -> str:
    s = hr(x, nd)
    if sign and x > 0:
        s = "+" + s
    return s + " %"


def dmy(d: Any) -> str:
    import pandas as pd

    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def img_tag(path: Path, alt: str) -> str:
    return f'<img src="{top10.img(path)}" alt="{e(alt)}" loading="lazy">'


def figure(d: Data, key: str, fname: str, title: str, caption_html: str) -> str:
    return (
        f'<figure id="{key}"><div class="plate">{img_tag(d.dir / fname, title)}</div>'
        f'<p class="swipe">Na mobitelu povuci graf ulijevo i udesno da vidiš sve.</p>'
        f"<figcaption><b>{e(title)}.</b> {caption_html}</figcaption></figure>"
    )


# ---------------------------------------------------------------- sections


def sec_verdict(d: Data) -> str:
    a, rows = d.a, d.a["tablica_segment_AI_era"]["suparnici"]
    pob = a["pobjednik"]
    cmp_ = pob["usporedba_s_drzanjem"]
    k1 = rows[C13]
    facts = [
        (pct(rows[HOLD]["prinos_pct"], 1, True), "držanje: prinos u AI eri", "pos"),
        (pct(rows[d.winner]["prinos_pct"], 1, True), f"{d.names[d.winner]}: prinos", "pos"),
        (pct(k1["prinos_pct"], 1, True), "C13C: prinos", "pos"),
        (f"{hr(rows[HOLD]['sharpe'], 2)} / {hr(rows[d.winner]['sharpe'], 2)}", "Sharpe: držanje / pobjednik", ""),
        (f"{pct(rows[HOLD]['max_pad_pct'], 1)} / {pct(k1['max_pad_pct'], 1)}", "najveći pad: držanje / C13C", "neg"),
        (str(k1["poslova"]), "C13C: broj poslova u 11 dionica", ""),
    ]
    tiles = "".join(f'<div class="fact"><b class="{c}">{e(v)}</b><span>{e(lbl)}</span></div>' for v, lbl, c in facts)
    return f"""
<div class="verdict-top">
<p><b>Najbolje je prošla {t(pob['pobjednik_naziv'])}, ali nitko nije pobijedio običan kupi-i-drži.</b>
Iz 1.000 EUR u svakoj dionici držanje je dalo {eur(cmp_['iz_1000_EUR_drzanje_EUR'])}, rotacija zamaha {eur(cmp_['iz_1000_EUR_pobjednik_EUR'])},
a Petrov C13C samo {eur(k1['iz_1000_EUR_po_sleeveu_EUR'])}.</p>
<p class="note">Razdoblje: 3. 1. 2023. do 5. 10. 2026. (AI era). Trošak: 0,025 % pri svakoj kupnji i prodaji (na 1.000 EUR to je 0,25 EUR).
Ovo je istraživačka simulacija na povijesnim podacima, a ne savjet ni signal za kupnju. Nijedan nalog nije poslan.</p>
</div>
<div class="facts">{tiles}</div>"""


def sec_what_is_this(d: Data) -> str:
    a = d.a
    demo = demo_trade(d, "NVDA")
    tr = demo["trade"]
    units = 1000 / tr["raw_entry"]
    return f"""
<section id="sto-je-ovo"><h2>Što je ovo, jednostavno</h2>
<p>Pitanje glasi: je li u zadnje tri i pol godine (otkad traje „AI era“, od siječnja 2023.) pametnije pravilo trgovanja
bilo bolje od onoga što radi svatko tko samo kupi i čeka? Uzeli smo {d.n} dionica čipova i svakoj dali zamišljenih
<b>1.000 EUR</b>. Taj iznos zovemo <b>pretinac</b>: jedna dionica, jedan pretinac, novac se među pretincima ne prelijeva.
Onda smo na istim podacima, uz isti trošak, pustili devet pravila i usporedili ih s držanjem.</p>
<div class="teach"><h3>Kako radi Petrov C13C, korak po korak</h3>
<ol class="steps">
<li>Večer pogledaš zatvaranje dana. Ako je cijena <b>iznad prosjeka zadnjih 200 dana</b> (SMA200, znak dugoročnog uspona) i
u zadnjih 5 dana je pala <b>5 % ili više</b>, to je signal za kupnju.</li>
<li>Sutradan po otvaranju kupiš za cijeli pretinac.</li>
<li>Odmah postaviš <b>stop</b>: automatsku prodaju 10 % ispod najvišeg vrha od kupnje. Kad cijena raste, stop ide gore, nikad dolje.</li>
<li>Kad cijena padne do stopa, prodaješ, i čekaš sljedeći signal. Dok čekaš, novac stoji u gotovini.</li></ol>
<p><b>Primjer iz stvarnih podataka (NVDA).</b> Zatvaranje {dmy(demo['signal_date'])} je {hr(demo['close_signal'], 2)} USD, a pet dana ranije
bilo je {hr(demo['close_5_before'], 2)} USD: pad od {hr(abs(demo['ret5']) * 100, 1)} %, a cijena je i dalje iznad SMA200 ({hr(demo['sma200'], 2)} USD).
To je signal. Sutradan, {dmy(tr['entry_date'])}, kupnja po {hr(tr['raw_entry'], 2)} USD: 1.000 EUR kupi oko {hr(units, 2)} dionice.
Prvi stop je oko {hr(demo['first_stop'], 2)} USD. Cijena se popela do {hr(demo['peak'], 2)} USD, a stop za njom, pa je
{dmy(tr['exit_date'])} izlaz po {hr(tr['raw_exit'], 2)} USD: dobit {pct(tr['return'] * 100, 1)}, odnosno 1.000 EUR postaje {eur(1000 * (1 + tr['return']))}.</p></div>
<p class="note">Cijene su u dolarima, a ovdje se tretiraju kao eurske (isti postotak primijenjen na 1.000 EUR). Tečaj eura i dolara, porezi i dividende
nisu uključeni. Zbog toga stvarni rezultat iz Hrvatske ne bi bio isti.</p></section>"""


def sec_story(d: Data) -> str:
    z = d.a["zasto_zajedno"]
    groups = "".join(f"<li><b>{e(k)}:</b> {e(', '.join(v))}</li>" for k, v in z["podskupine"].items())
    drivers = "".join(f"<li>{t(x)}</li>" for x in z["sto_ih_pokrece"])
    return f"""
<section id="prica"><h2>Priča ove skupine</h2>
<p>{t(z['sazetak'])}</p>
<ul>{groups}</ul>
<h3>Što ih pokreće</h3><ul>{drivers}</ul>
<p class="note"><b>Oznaka:</b> {t(z['oznaka'])}.</p>
<div class="teach"><h3>Jedna velika oklada, ne jedanaest</h3>
<p>{t(z['povezanost'])}</p><p>{t(z['najveci_zajednicki_pad'])}</p></div></section>"""


def sec_table_contenders(d: Data) -> str:
    rows = d.a["tablica_segment_AI_era"]["suparnici"]
    order = sorted(rows, key=lambda c: -rows[c]["sharpe"])
    gr = d.a["ocjene"]["ocjene"]
    tr_html = []
    for c in order:
        r = rows[c]
        g = gr[c]["ocjena"]
        lab, tone = GRADE.get(g, (g, ""))
        mark = " (pobjednik)" if c == d.winner else ""
        tr_html.append(
            f'<tr data-id="{c}"><td class="l">{e(d.names[c])}{mark}</td>'
            f"<td>{hr(r['prinos_pct'], 1)} %</td><td>{hr(r['iz_1000_EUR_po_sleeveu_EUR'])}</td><td>{hr(r['sharpe'], 2)}</td>"
            f"<td>{hr(r['max_pad_pct'], 1)} %</td><td>{r['poslova']}</td><td>{hr(r['izlozenost_pct'], 1)} %</td>"
            f"<td>{hr(r['prinos_trosak_2x_pct'], 1)} %</td><td>{hr(r['prinos_trosak_3x_pct'], 1)} %</td>"
            f'<td class="l"><span class="chip {tone}">{e(lab)}</span></td></tr>'
        )
    rule_rows = "".join(
        f"<tr><td class='l'>{e(d.names[c])}</td><td class='l wrap'>{e(RULE_TEXT[c])}</td></tr>" for c in rows
    )
    pob = d.a["pobjednik"]
    return f"""
<section id="suparnici"><h2>Tko je što napravio</h2>
<div class="table-wrap"><table class="cmp"><thead><tr><th class="l">Pravilo</th><th>Prinos</th><th>Iz 1.000 EUR</th><th>Sharpe</th>
<th>Najveći pad</th><th>Poslova</th><th>U dionicama</th><th>Prinos uz trošak 2x</th><th>Prinos uz trošak 3x</th><th class="l">Ocjena dokaza</th></tr></thead>
<tbody>{''.join(tr_html)}</tbody></table></div>
<p class="note">Zbroj za 11 pretinaca po 1.000 EUR (ukupno 11.000 EUR); „Iz 1.000 EUR“ je prosjek jednog pretinca. Poredak ide po Sharpeu.
„Ocjena dokaza“ je blaga: snižava se samo zbog nevaljanog dokaza (pogled u budućnost, ugađanje pravila, premalo poslova, trošak),
nikad zbog veličine pada ili treskanja cijene. Ocjena ne znači da je pravilo bolje od držanja i nije formalni Critic PASS laboratorija.</p>
<h3>Pobjednik i što to znači</h3>
<p>{t(pob['definicija_unaprijed'])}</p>
<p>{t(pob['iskreno'])}</p>
<h3>Što je rekao C13C</h3>
<p>{t(d.a['c13c_iskreno']['zakljucak'])}</p>
<p>{t(d.a['c13c_iskreno']['K7_napomena'])}</p>
<details><summary>Kako svako pravilo radi (jednom rečenicom)</summary>
<div class="table-wrap"><table><tbody>{rule_rows}</tbody></table></div></details></section>"""


def sec_charts_main(d: Data) -> str:
    rows = d.a["tablica_segment_AI_era"]["suparnici"]
    hold, k1, win = d.sleeve_equity(HOLD), d.sleeve_equity(C13), d.sleeve_equity(d.winner)
    import pandas as pd

    r = rows[HOLD]["najgori_pad_datumi"]
    a0, a1 = pd.Timestamp(r["vrh"]), pd.Timestamp(r["dno"])
    h_loss = hold.loc[a0] - hold.loc[a1]
    k_loss = k1.loc[a0] - k1.loc[a1]
    k7 = rows["K7_C13C_PLUS_TREND_REENTRY"]
    corr = json.loads((d.dir / "charts_meta.json").read_text())["corr_exposure_return"]
    all_trades = [x for tk in d.tickers for x in d.trades(tk)]
    n_nv = len([x for x in d.trades("NVDA") if x["entry_date"] >= "2025-07-01"])
    n_amd = len([x for x in d.trades("AMD") if x["entry_date"] >= "2025-07-01"])
    c13s = d.a["c13c_iskreno"]["segment"]["K1"]
    figs = [
        figure(
            d, "g1", "01_cijena_c13c.png", "Gdje je C13C kupovao i prodavao",
            "Plava crta je cijena, narančasta crtkana je SMA200. Zeleni trokut je kupnja, crveni izlaz stopom. Crvena stepenica na NVDA prikazuje "
            f"jedan stop kroz cijeli posao. <b>Što uočiti:</b> C13C kupuje često (od srpnja 2025. na NVDA {n_nv} puta, na AMD {n_amd} puta) i svaki put izlazi stopom, "
            "pa u dugom uzletu ne sjedi na cijelom usponu. U padu AMD-a 2024.–2025. nije imao nijednu poziciju (cijena je gotovo cijelo to vrijeme bila ispod SMA200), "
            "što je dio pada uštedjelo, ali je propustio i početak oporavka.",
        ),
        figure(
            d, "g2", "02_kapital_1000eur.png", "Što se dogodi s 1.000 EUR",
            f"Tri krivulje: držanje (plavo), pobjednik po Sharpeu (zeleno) i C13C (narančasto). Krajnje vrijednosti su prosjek jednog pretinca: "
            f"držanje {eur(hold.iloc[-1])}, {t(d.names[d.winner])} {eur(win.iloc[-1])}, C13C {eur(k1.iloc[-1])}. "
            f"<b>Što je C13C uštedio:</b> u najgorem padu držanja ({dmy(a0)} do {dmy(a1)}) držanje je izgubilo {eur(h_loss)} po pretincu, a C13C {eur(k_loss)}. "
            f"<b>Što ga je koštalo:</b> ostatak razdoblja je bio velikim dijelom u gotovini, pa je na kraju zaostao za {eur(hold.iloc[-1] - k1.iloc[-1])}.",
        ),
        figure(
            d, "g3", "03_pad_od_vrha.png", "Koliko je boljelo",
            f"Svaka crta pokazuje koliko je vrijednost tog dana bila ispod svog dotadašnjeg najvišeg vrha. Najgori dan držanja je "
            f"{dmy(a1)} s padom od {pct(abs(rows[HOLD]['max_pad_pct']), 1)}: od vrha {eur(hold.loc[a0])} ostaje {eur(hold.loc[a1])}. "
            f"C13C ima najveći pad {pct(abs(rows[C13]['max_pad_pct']), 1)}, a rotacija zamaha {pct(abs(rows[d.winner]['max_pad_pct']), 1)}, praktički kao držanje, jer ne izlazi u gotovinu nego samo mijenja dionice. "
            "Pad se ovdje samo mjeri i ne snižava ocjenu.",
        ),
        figure(
            d, "g4", "04_poslovi_c13c.png", "Svi poslovi C13C-a",
            f"Svaka točka je jedan posao u jednoj od 11 dionica ({len(all_trades)} ukupno). Većina ih je kratka i blizu nule, a nekoliko dugih daje velike dobiti. "
            f"Dobitnih je {pct(c13s['stopa_pogotka_pct'], 1)}, prosječan dobitak {pct(c13s['prosjecni_dobitak_pct'], 1)}, prosječan gubitak {pct(c13s['prosjecni_gubitak_pct'], 1)}. "
            "Crveni X označava izlaz nakon jaza preko noći: dionica je otvorila ispod stopa pa je izlaz lošiji od planiranih 10 %.",
        ),
        figure(
            d, "g5", "05_ploca_suparnika.png", "Poredak pravila",
            f"Lijevo prinos, desno Sharpe (prinos u odnosu na treskanje cijene). Držanje je prvo i po jednom i po drugom. Tri pravila na vrhu popisa "
            f"({t(d.names[d.winner])}, SMA200 trend, 126-dnevni zamah) razlikuju se tek u trećoj decimali Sharpea, pa je pobjednik pitanje sreće više nego dokaz.",
        ),
        figure(
            d, "g6", "06_otpornost_troskovi.png", "Što ako je trošak veći",
            f"Isti prinos uz običan (1x), dvostruki (2x) i trostruki (3x) trošak. Što se pravilo više kupuje i prodaje, to ga trošak jače pogađa: "
            f"C13C + ponovni ulaz ({k7['poslova']} poslova) gubi {hr(k7['prinos_pct'] - k7['prinos_trosak_3x_pct'], 1)} postotnih bodova uz 3x trošak, držanje samo "
            f"{hr(rows[HOLD]['prinos_pct'] - rows[HOLD]['prinos_trosak_3x_pct'], 1)}. Potpora/otpor (K5) pada ispod nule već uz 2x trošak, pa ne ispunjava uvjet. "
            "Minimalna provizija po nalogu kod Interactive Brokersa ovdje nije uračunata (nepotvrđeno za Petrov tarif), pa je stvarnim pravilima s mnogo poslova teže nego što prikazuje.",
        ),
        figure(
            d, "g7", "07_pouka_izlozenost.png", "Glavna pouka segmenta",
            f"Svaka točka je jedno pravilo: vodoravno koliko je vremena u prosjeku bilo u dionicama, okomito prinos. Što je pravilo duže bilo unutra, to je prošlo bolje "
            f"(povezanost {hr(corr, 2)} među samo devet točaka, pa to čitaj kao sliku, ne kao zakon). Razlog: u AI eri rast nose rijetki dani, a tko je taj dan izvan, promašuje ga. "
            "Pravila koja izlaze iz tržišta štite od pada, ali plaćaju promašenim rastom.",
        ),
    ]
    return '<section id="grafovi"><h2>Grafovi: što pokazuju i što uče</h2>' + "".join(figs) + "</section>"


def sec_per_ticker(d: Data) -> str:
    a = d.a
    rev = {v: k for k, v in d.names.items()}
    trs = []
    for tk in d.tickers:
        k = a["kartice"][tk]
        tab = a["tablica_po_tickeru_AI_era"][tk]["suparnici"]
        b0, k1 = tab[HOLD], tab[C13]
        best = k["algoritam_najbolji_po_sharpeu"]
        bid = rev[best["suparnik"]]
        bt = tab[bid]
        beat = ", ".join(best["pobjeduje_drzanje_po_prinosu"]) or "nitko"
        ch = k["karakter"]
        trs.append(
            f'<tr data-t="{tk}"><td class="l"><b>{tk}</b></td><td class="l wrap">{e(ch)}</td>'
            f"<td>{hr(b0['prinos_pct'], 1)} %</td><td>{hr(k1['prinos_pct'], 1)} %</td>"
            f'<td class="l wrap">{e(best["suparnik"])}: {hr(bt["prinos_pct"], 1)} %, Sharpe {hr(best["sharpe"], 2)} (držanje {hr(best["drzanje_sharpe"], 2)})</td>'
            f"<td>{hr(b0['max_pad_pct'], 1)} %</td><td>{hr(k1['max_pad_pct'], 1)} %</td>"
            f"<td>{hr(k['udio_dana_iznad_SMA200_pct'], 1)} %</td><td class='l wrap'>{e(beat)}</td></tr>"
        )
    cards = []
    for tk in d.tickers:
        k = a["kartice"][tk]
        dip = k["nakon_pada_5d_od_5pct_iznad_SMA200"]
        pr = k["potpora_otpor"]
        con = k["koncentracija_prinosa"]
        mech = k["mehanizam"]
        ch = k["karakter"]
        plain = next((v for kk, v in CHARACTER_PLAIN.items() if ch.startswith(kk)), "")
        extra = f"<p class='note'>{t(k['napomena'])}</p>" if k.get("napomena") else ""
        cards.append(
            f"""<div class="tcard" id="k-{tk}"><h3><span>{tk}</span><span class="chip">{e(ch.split(' (')[0])}</span></h3>
<p class="note" style="margin:0">{t(k['povijest_u_AI_eri'])}. Karakter: {e(plain)}.</p>
<ul>
<li>Prinos držanja u profilu: {pct(k['ukupni_prinos_profil_pct'], 1, True)}; treskanje cijene {hr(k['volatilnost_godisnje_pct'], 1)} % godišnje, beta prema sektoru (SMH) {hr(k['beta_smh'], 2)}.</li>
<li>Najgori pad: {t(k['najgori_pad_na_1000_eur'])}</li>
<li>Nakon pada od 5 % u 5 dana: u sljedećih 5 dana {pct(dip['5d_prosjek_pct_razrijedeno'], 1, True)} naprema {pct(dip['5d_prosjek_pct_svi_dani'], 1, True)} u svim danima (t = {hr(dip['5d_t'], 1)}); za 20 dana {pct(dip['20d_prosjek_pct_razrijedeno'], 1, True)} naprema {pct(dip['20d_prosjek_pct_svi_dani'], 1, True)} (t = {hr(dip['20d_t'], 1)}). Događaja: {dip['razrijedeni_10d']} razrijeđenih (od ukupno {dip['svi_dogadjaji']}).</li>
<li>Potpora je držala u {hr(pr['potpora_stvarna']['hold_pct'], 0)} % od {pr['potpora_stvarna']['n_touches']} dodira (lažna razina {hr(pr['potpora_placebo']['hold_pct'], 0)} %); otpor {hr(pr['otpor_stvarni']['hold_pct'], 0)} % od {pr['otpor_stvarni']['n_touches']} (lažna {hr(pr['otpor_placebo']['hold_pct'], 0)} %).</li>
<li>10 najboljih dana čini {hr(con['10_najboljih_dana_udio_pct'], 0)} % prinosa; bez njih prinos bi bio {pct(con['prinos_bez_10_najboljih_pct'], 1)}. Cijena je bila iznad SMA200 {hr(k['udio_dana_iznad_SMA200_pct'], 1)} % dana.</li>
</ul>
<p style="margin:0"><b>Što to znači za pravila:</b> {t(k['sto_to_znaci_za_algoritam'])}</p>{extra}
<details><summary>Poslovni kontekst (javni izvori, nije iz naših podataka)</summary>
<p><b>Što prodaje:</b> {t(mech['sto_prodaje'])}</p><p><b>Što vodi prihod:</b> {t(mech['sto_vodi_prihod'])}</p>
<p><b>Mjesto u lancu:</b> {t(mech['mjesto_u_lancu'])}</p><p><b>Što ga boli:</b> {t(mech['sto_ga_boli'])}</p>
<p class="note">{t(mech['oznaka'])}. Nije provjereno u godišnjim izvješćima.</p></details></div>"""
        )
    touches = [a["kartice"][tk]["potpora_otpor"][key]["n_touches"] for tk in d.tickers for key in ("potpora_stvarna", "otpor_stvarni")]
    px = d.prices("NVDA")
    bad_tick = px.loc["2024-06-10"]
    arm = next(x for x in d.trades("ARM") if x["exit_date"] == "2024-08-05")
    figs = [
        figure(
            d, "b1", "08_nakon_pada.png", "Vrijedi li kupovati nakon pada",
            f"Zeleni stupac: prosječna promjena cijene nakon što je dionica u 5 dana pala 5 % ili više (a još je iznad SMA200). Sivi: običan dan. "
            f"Skupno za 5 dana {pct(a['c13c_iskreno']['premisa_skupno_AI_era']['5d_prosjek_pct_poslije_pada'], 1)} naprema "
            f"{pct(a['c13c_iskreno']['premisa_skupno_AI_era']['5d_prosjek_pct_svi_dani'], 1)}: blago odbijanje, ali za 20 dana je običan dan bio bolji "
            f"({pct(a['c13c_iskreno']['premisa_skupno_AI_era']['20d_prosjek_pct_poslije_pada'], 1)} naprema {pct(a['c13c_iskreno']['premisa_skupno_AI_era']['20d_prosjek_pct_svi_dani'], 1)}). "
            "Kod većine dionica razlika nije veća od slučajne (t ispod 2). To je opis, ne dokaz.",
        ),
        figure(
            d, "b2", "09_anatomija_pada.png", "Anatomija najgoreg pada",
            "Svaka crta je najgori pad jedne dionice: crveno je padanje od vrha do dna, zeleno vraćanje na stari vrh. Dna se slažu oko 8. 4. 2025., "
            "pa raspodjela na jedanaest čipova nije dala zaštitu u općem padu. Neki su se oporavili tek nakon više od godine dana (npr. MRVL, ARM, INTC).",
        ),
        figure(
            d, "b3", "10_potpora_otpor.png", "Jesu li crte s grafa išta vrijedile",
            "Usporedili smo razine koje trgovci crtaju (zadnji potvrđeni vrh ili dno) s nasumično postavljenim lažnim razinama. Kad stvarne nisu jasno bolje od lažnih, "
            f"crtanje crta nije dalo prednost. Po dionici i vrsti razine je samo {min(touches)} do {max(touches)} dodira, što je premalo za čvrst zaključak. Pravilo K5 koje trguje na tim razinama završilo je na minusu.",
        ),
        figure(
            d, "b4", "11_najbolji_dani.png", "Nekoliko dana nosi sav prinos",
            f"Plavo je prinos u AI eri, crveno isti prinos kad se izbaci 10 najboljih dana (od oko 940). Ljubičasti brojevi su udio tih 10 dana u prinosu. "
            f"MCHP: {pct(a['kartice']['MCHP']['ukupni_prinos_profil_pct'], 0, True)} postaje {pct(a['kartice']['MCHP']['koncentracija_prinosa']['prinos_bez_10_najboljih_pct'], 1)}: "
            f"1.000 EUR bi bez tih deset dana postalo oko {hr(1000 * (1 + a['kartice']['MCHP']['koncentracija_prinosa']['prinos_bez_10_najboljih_pct'] / 100))} EUR umjesto oko "
            f"{hr(1000 * (1 + a['kartice']['MCHP']['ukupni_prinos_profil_pct'] / 100))} EUR. Tko je povremeno izvan tržišta, lako te dane promaši.",
        ),
        figure(
            d, "b5", "12_jazovi_i_podaci.png", "Jazovi preko noći i loš podatak",
            "Zadnji graf je lekcija o podacima: tri svijeće s tri pouke. Jaz od +26,1 % na NVDA (25. 5. 2023.): takav skok ne možeš kupiti ni zaštititi stopom. "
            f"ARM 5. 8. 2024.: stop je bio oko 10 % ispod kupnje, ali dionica je otvorila puno niže, pa je izlaz lošiji ({hr(arm['return'] * 100, 1)} %). "
            f"NVDA 10. 6. 2024.: u izvornom CSV-u najviša cijena dana je {hr(bad_tick['high'], 2)} USD uz otvaranje {hr(bad_tick['open'], 2)}, što je pogrešan unos; simulator ga je ograničio, a CSV je ostao nepromijenjen.",
        ),
    ]
    return f"""
<section id="dionice"><h2>Kako se ponaša svaka dionica</h2>
<p class="lead2">Svaka dionica se ponaša malo drukčije, a to odlučuje koje pravilo ima smisla. Ispod je tablica sa svih 11, pa kartice s detaljima.</p>
<div class="table-wrap"><table><thead><tr><th class="l">Dionica</th><th class="l">Karakter</th><th>Držanje</th><th>C13C</th><th class="l">Najbolje pravilo po Sharpeu</th>
<th>Pad držanja</th><th>Pad C13C</th><th>Dana iznad SMA200</th><th class="l">Tko je pobijedio držanje po prinosu</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div>
<p class="note">Prinosi su iz simulatora za AI eru (po pretincu od 1.000 EUR). Broj poslova ispod 20 po dionici je samo napomena; kriterij pobjednika vrijedi na razini cijele skupine. ARM je na burzi tek od 14. 9. 2023., pa mu je uzorak kraći.
Profil dionice navodi za NVDA prinos {pct(a['kartice']['NVDA']['ukupni_prinos_profil_pct'], 0)} dok simulator za držanje daje {pct(a['tablica_po_tickeru_AI_era']['NVDA']['suparnici'][HOLD]['prinos_pct'], 0)}; uzrok razlike nije istražen (nepotvrđeno).</p>
<div class="teach"><h3>Kako čitati karakter</h3>
<p><b>Sklonost vraćanju (gumica):</b> pomaci se kroz 20 dana djelomično poništavaju. <b>Blizu slučajnog hoda:</b> nema obrasca na koji bi se moglo osloniti.
<b>Sklonost nastavku trenda:</b> što raste, sklono je i dalje rasti. U ovoj skupini samo INTC ima ovo treće.</p></div>
{''.join(figs)}
<div class="tcards">{''.join(cards)}</div></section>"""


def sec_glossary(d: Data) -> str:
    imported = {k: v for k, v in top10.GLOSSARY}
    prof = json.loads((d.dir / "profile.json").read_text())["rjecnik_hr"]
    own = [
        ("Pretinac", "Jedna dionica s vlastitih 1.000 EUR. Pretinci se ne prelijevaju: ako jedna dionica miruje, njezin novac stoji kao gotovina i ne ide drugoj. Primjer: 11 dionica = 11 pretinaca = 11.000 EUR."),
        ("Držanje (kupi i drži)", "Kupiš prvi dan i ne diraš. Primjer: 1.000 EUR u dionicu koja se utrostruči postaje 3.000 EUR. Sve ostalo mjeri se prema tome."),
        ("SMA200", "Prosjek zadnjih 200 zatvaranja. Cijena iznad njega znači dugoročni uzlazni trend. Primjer: prosjek je 90 USD, cijena 100 USD: trend je uzlazni."),
        ("Stop (pomični)", "Automatska prodaja ako cijena padne za određeni iznos ispod vrha. Primjer: kupiš za 1.000 EUR, stop 10 % ispod vrha: ako dionica naraste na 1.300 EUR, stop je na 1.170 EUR."),
        ("Jaz preko noći (gap)", "Dionica sutradan otvori puno više ili niže nego što je jučer zatvorila. Stop ne pomaže: ako otvori ispod stopa, prodaješ po otvaranju. Primjer: stop na 900 EUR, otvaranje na 850 EUR, izlaz na 850 EUR."),
        ("Sharpe", "Prinos u odnosu na treskanje cijene. Veći je bolji. Primjer: dva vozača stignu u isto vrijeme, ali jedan vozi mirno: on ima veći Sharpe. Oko 1 je dobro."),
        ("Najveći pad od vrha", "Koliko je vrijednost pala od najboljeg trenutka do najgoreg. Primjer: 1.000 EUR naraste na 2.000 EUR pa padne na 1.200 EUR: pad je 40 %. To je pad na papiru dok ne prodaš."),
        ("Izloženost", "Koliki je dio novca u prosjeku bio u dionicama (ostalo je gotovina). Primjer: 50 % znači da je u prosjeku 500 od 1.000 EUR bilo uloženo."),
        ("Bazni bod (bps), trošak 2x i 3x", "Bazni bod je stotinka postotka. Trošak 2,5 baznih bodova po strani je 0,025 %: na kupnju od 1.000 EUR to je 0,25 EUR, isto toliko pri prodaji. Test 2x i 3x ponavlja račun s dvostrukim i trostrukim troškom."),
        ("Zamah (momentum)", "Dionice koje su zadnjih mjeseci najviše rasle često još neko vrijeme rastu. Primjer: kupiš dvije najbolje od četiri dionice zadnjih šest mjeseci."),
        ("Placebo (lažna razina)", "Razina s grafa postavljena nasumično, kao kontrola. Ako prave razine nisu bolje od lažnih, crtanje razina ne daje prednost."),
        ("Razrijeđeni događaji", "Isti pad od 5 % često traje nekoliko dana pa se broji više puta. Zato uz sve događaje navodimo i one barem 10 dana razmaka."),
        ("ADR", "Američki certifikat koji predstavlja dionicu strane tvrtke (TSM je ADR na tajvansku dionicu). Nosi dodatne rizike poput tečaja tajvanskog dolara i naknada ADR-a; što se točno naplaćuje je nepotvrđeno."),
        ("Test pogleda unaprijed", "Provjera da pravilo ne koristi podatak koji tog dana još nije postojao: podaci se odsijeku na slučajan dan i odluke do tog dana moraju ostati iste. Prolaz ne dokazuje da je pravilo dobro, samo da ne vara."),
    ]
    items = list(own)
    for key in ["AI era", "Prilagođeno podacima (overfitting)", "Broj pokušaja (K) i deflated Sharpe"]:
        items.append((key, imported[key]))
    for key in ["volatilnost", "beta", "korelacija", "omjer varijance (VR)", "t-vrijednost", "stopa pogotka"]:
        items.append((key[0].upper() + key[1:], prof[key]))
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{t(b)}</dd></div>" for a, b in items)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def sec_eu(d: Data) -> str:
    eu = d.a["eu_hr"]
    gen = "".join(f"<li>{t(x)}</li>" for x in eu["opce"])
    chips = "".join(
        f'<span class="chip warn">{tk}: {e(v["status"])}</span>' for tk, v in eu["po_tickeru"].items()
    )
    special = "".join(
        f"<li><b>{tk}:</b> {t(v['vrsta'])}. {t(v['napomena'].split('. ', 1)[1] if tk in ('TSM', 'ARM') else '')}</li>"
        for tk, v in eu["po_tickeru"].items()
        if tk in ("TSM", "ARM")
    )
    return f"""
<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>
<div class="chips">{chips}</div>
<p>Svih 11 su pojedinačne dionice kotirane u SAD-u. Takve su općenito dostupne malim ulagačima iz EU preko Interactive Brokersa, ali za svaku od njih
<b>status ostaje nepotvrđen dok se ne provjeri u samom IBKR-u</b>. Američki ETF-ovi (npr. SMH, indeks poluvodiča) često nisu dostupni malim EU ulagačima jer nemaju KID dokument,
pa ih ovdje ne predstavljamo kao nešto što the researcher može kupiti.</p>
<ul>{gen}</ul>
<ul>{special}</ul>
<p>Porezni tretman i evidencija: <b>nepotvrđeno</b>, bez poreznih tvrdnji. Stvarno trgovanje je zasebna Petrova odluka; ovdje agenti ne šalju nikakve naloge.</p></section>"""


def sec_limits(d: Data) -> str:
    rows = d.a["tablica_segment_AI_era"]["suparnici"]
    lim = "".join(f"<li>{t(x)}</li>" for x in d.a["ogranicenja"])
    extra = [
        "Tečaj EUR/USD: cijene su u USD i tretiraju se kao EUR. Pravi 1.000 EUR postaje USD pri kupnji i opet EUR pri prodaji; tečaj se mijenja, a konverzija ima trošak.",
        "Dividende nisu uračunate (cjenovni, ne ukupni prinos). Utjecaj nije izmjeren.",
        "Porezi i evidencija nisu uključeni.",
        "Minimalna provizija po nalogu (IBKR) nije uračunata; za male naloge i pravila s mnogo poslova (C13C, K7) stvarni trošak je veći.",
        "Stvarna izvršenja: nema proklizavanja izvan 0,025 %, nema djelomičnih ispunjenja. Razlomljene dionice kod IBKR-a su nepotvrđene. Jaz preko noći na lošim vijestima može biti gori nego u podacima.",
        "Bez poluge i bez kratke prodaje (zadano za EU malog ulagača).",
        "Provjera ±20 % parametara gleda samo mijenja li se predznak prinosa, što je u razdoblju općeg rasta slab test.",
        f"Isprobano je 9 pravila na 6 skupina i 43 dionice (K = 532): najbolji izgleda dobro i slučajno. Deflated Sharpe držanja je {hr(rows[HOLD]['deflated_sharpe_vjerojatnost'], 3)}, C13C-a {hr(rows[C13]['deflated_sharpe_vjerojatnost'], 3)}, pobjednika {hr(rows[d.winner]['deflated_sharpe_vjerojatnost'], 3)} (informativno, ne snižava ocjenu).",
        "Prije 2023. se ovdje ne donose zaključci; razdoblje je samo kontekst. Tržišni režim se promijenio nakon 2022.",
        "Ovo nije formalni Critic PASS laboratorija; signal ostaje PRIČEKAJ dok ne postoji odobrena strategija.",
    ]
    ex = "".join(f"<li>{e(x)}</li>" for x in extra)
    return f'<section id="granice"><h2>Granice: što nije uračunato</h2><ul>{ex}</ul><h3>Iz analize</h3><ul>{lim}</ul></section>'


def build(segment: str) -> Path:
    d = Data(segment)
    a = d.a
    findings = "".join(f"<li>{t(x)}</li>" for x in a["kljucni_nalazi"])
    body = f"""<main>
<header><span class="tagline">AICHAIN · {e(segment)} · istraživačka simulacija</span>
<h1>{t(a['meta']['naslov'].split(':')[0])}</h1>
<p class="lead">Je li pametno pravilo trgovanja u AI eri (2023.–2026.) bilo bolje od običnog kupi-i-drži? Jedanaest dionica, devet pravila, isti troškovi.</p></header>
{sec_verdict(d)}
{sec_what_is_this(d)}
{sec_story(d)}
<section id="nalazi"><h2>Ključni nalazi</h2><ul>{findings}</ul></section>
{sec_table_contenders(d)}
{sec_charts_main(d)}
{sec_per_ticker(d)}
{sec_glossary(d)}
{sec_eu(d)}
{sec_limits(d)}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima ({t(a['meta']['glavno_mjerilo'])}): odluka na zatvaranju, kupnja na idućem otvaranju, trošak 0,025 % po strani, bez poluge i bez kratke prodaje.
Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan.
Status revizije: simulator je neovisno provjeren 14. 10. 2026. i ispravljen (obustavljena trgovina, loš podatak NVDA, trošak zadnjeg dana); brojke su iz ispravljenih rezultata.</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(title="Analiza AI čipova", css=top10.CSS + EXTRA_CSS)
    )
    page = "<!doctype html>\n<html lang=\"hr\"><head>\n" + head + "</head><body>\n" + body + "\n</body></html>"
    out = d.dir / "artifact.html"
    out.write_text(page)
    return out


# ---------------------------------------------------------------- verification


def verify(segment: str) -> list[str]:
    """Recompute key numbers from the raw results files and check each appears in the page. Returns mismatches."""
    import numpy as np

    page = (BASE / "segments" / segment / "artifact.html").read_text()
    seg = json.loads((BASE / "results" / f"{segment}.json").read_text())
    n = len(seg["tickers"])
    bad: list[str] = []
    rows = {m.group(1): m.group(2) for m in re.finditer(r'<tr data-id="([A-Z0-9_]+)">(.*?)</tr>', page, re.S)}
    for c, v in seg["contenders"].items():
        w = v["windows"]["ai_era"]
        exp = {
            "prinos": hr(w["total_return"] * 100, 1) + " %",
            "iz 1000": hr(w["end_value"] / n),
            "sharpe": hr(w["sharpe"], 2),
            "pad": hr(w["max_drawdown"] * 100, 1) + " %",
            "poslova": f">{w['trades']}<",
            "izloženost": hr(w["exposure_pct"], 1) + " %",
            "2x": hr(w["total_return_cost_2x"] * 100, 1) + " %",
            "3x": hr(w["total_return_cost_3x"] * 100, 1) + " %",
        }
        row = rows.get(c, "")
        for k, s in exp.items():
            if s not in row:
                bad.append(f"{c} {k}: expected {s}")
    # equity curve cross-check: sum of sleeve equity ends equals end_value
    for c in ("B0_BUYHOLD", "K1_C13C_ORIG"):
        eq = seg["contenders"][c]["equity"]["ai_era"]
        last = eq[-1][1]
        if abs(last - seg["contenders"][c]["windows"]["ai_era"]["end_value"]) > 0.006:  # equity curve is stored rounded to cents
            bad.append(f"{c}: equity end != end_value")
    # per-ticker table
    trows = {m.group(1): m.group(2) for m in re.finditer(r'<tr data-t="([A-Z]+)">(.*?)</tr>', page, re.S)}
    for tk in seg["tickers"]:
        r = json.loads((BASE / "results" / f"{tk}.json").read_text())["contenders"]
        for c, col in (("B0_BUYHOLD", "hold"), ("K1_C13C_ORIG", "c13c")):
            w = r[c]["windows"]["ai_era"]
            for s in (hr(w["total_return"] * 100, 1) + " %", hr(w["max_drawdown"] * 100, 1) + " %"):
                if s not in trows.get(tk, ""):
                    bad.append(f"{tk} {col}: expected {s}")
    # analysis.json per-ticker rows (source of the page's ticker table) vs raw results
    an = json.loads((BASE / "segments" / segment / "analysis.json").read_text())
    for tk in seg["tickers"]:
        raw = json.loads((BASE / "results" / f"{tk}.json").read_text())["contenders"]
        for c, row in an["tablica_po_tickeru_AI_era"][tk]["suparnici"].items():
            if not raw[c].get("available", True) or "prinos_pct" not in row:
                continue
            w = raw[c]["windows"]["ai_era"]
            for key, val in (("prinos_pct", w["total_return"] * 100), ("max_pad_pct", w["max_drawdown"] * 100), ("sharpe", w["sharpe"])):
                if abs(row[key] - val) > (0.06 if key != "sharpe" else 0.006):
                    bad.append(f"analysis {tk} {c} {key}: {row[key]} vs raw {val:.3f}")
            if row["poslova"] != w["trades"]:
                bad.append(f"analysis {tk} {c} trades {row['poslova']} vs {w['trades']}")
    # K1 trade count
    n_tr = sum(len(json.loads((BASE / "results" / f"{tk}.json").read_text())["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]) for tk in seg["tickers"])
    tot = seg["contenders"]["K1_C13C_ORIG"]["windows"]["ai_era"]["trades"]
    if n_tr != tot:
        bad.append(f"K1 trade count: sum of tickers {n_tr} != segment {tot}")
    # headline numbers
    hold_end = seg["contenders"]["B0_BUYHOLD"]["windows"]["ai_era"]["end_value"] / n
    k6_end = seg["contenders"]["K6_MOMENTUM_CS"]["windows"]["ai_era"]["end_value"] / n
    k1_end = seg["contenders"]["K1_C13C_ORIG"]["windows"]["ai_era"]["end_value"] / n
    for s in (hr(hold_end), hr(k6_end), hr(k1_end)):
        if s + " EUR" not in page:
            bad.append(f"headline value missing: {s} EUR")
    # winner rule: highest Sharpe among >=20 trades and positive 2x
    q = []
    for c, v in seg["contenders"].items():
        if c == "B0_BUYHOLD":
            continue
        w = v["windows"]["ai_era"]
        if w["trades"] >= 20 and w["total_return_cost_2x"] > 0:
            q.append((w["sharpe"], c))
    if max(q)[1] != "K6_MOMENTUM_CS":
        bad.append(f"winner by raw results is {max(q)[1]}")
    _ = np
    return bad


if __name__ == "__main__":
    seg_name = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "ai_chips_logic"
    path = build(seg_name)
    print("built", path, f"{path.stat().st_size / 1e6:.1f} MB")
    if "--verify" in sys.argv:
        mism = verify(seg_name)
        print("MISMATCHES:" if mism else "verify OK: no mismatches", *mism, sep="\n")
