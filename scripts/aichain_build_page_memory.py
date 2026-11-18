"""Build the self-contained Croatian page for the AI-chain segment "memory".

Usage:
  .venv/bin/python -m lab.aichain.memory_page_charts          # PNG charts (once, or after data changes)
  .venv/bin/python scripts/aichain_build_page_memory.py       # artifact.html + number cross-check

Reads only REAL outputs: results/*.json, segments/memory/{analysis,profile,chart_info}.json.
Reuses the CSS, head and EU block of scripts/top10_build_artifact.py (imported, not edited).
Research only; nothing here sends an order.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from top10_build_artifact import CSS, HEAD, e, eu_block  # noqa: E402

BASE = ROOT / "reports/research/AICHAIN_20261014"
SEG = BASE / "segments/memory"
TITLE = "Memorija analiza"

EXTRA_CSS = """
.badge-row .note{flex:1 1 260px}
.fact b{font-size:1.1rem!important;overflow-wrap:anywhere}
.pill.warn{background:var(--warn-soft);color:var(--warn)}
.pill.good{background:var(--good-soft);color:var(--good)}
.pill.bad{background:var(--bad-soft);color:var(--bad)}
h3.sub{margin:18px 0 6px}
ul{padding-left:1.3em;margin:0 0 12px}ul li{margin-bottom:6px;max-width:68ch}
.callout{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:6px;padding:14px 18px}
.callout.neutral{border-left-color:var(--accent)}
.tcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.tcard{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px 18px;min-width:0}
.tcard h3{font-size:1.25rem;margin-bottom:2px}
.tcard dl{gap:8px}.tcard dt{font-size:.82rem;font-family:var(--mono);text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:500}
.tcard dd{color:var(--ink);font-size:.95rem}
.ctx{font-size:.85rem;color:var(--muted);border-top:1px dashed var(--line);margin-top:10px;padding-top:8px}
.tag-ctx{display:inline-block;font-family:var(--mono);font-size:.72rem;background:var(--accent-soft);color:var(--accent);border-radius:4px;padding:1px 6px;margin-bottom:4px}
td.l,th.l{text-align:left}
td.wrap{white-space:normal;min-width:220px;text-align:left}
tr.me td{background:var(--accent-soft);font-weight:600}
tr.bench td{color:var(--muted)}
.fig-title{font-family:var(--display);font-weight:700;margin:0 0 6px}
.cols3{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
"""


# ---------------------------------------------------------------- number formatting (Croatian)
def hr(x: float, digits: int = 0) -> str:
    s = f"{x:,.{digits}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pc(x: float, digits: int = 0, sign: bool = False) -> str:
    """x already in percent."""
    body = f"{x:+,.{digits}f}" if sign else f"{x:,.{digits}f}"
    return body.replace(",", "§").replace(".", ",").replace("§", ".") + " %"


def eur(x: float) -> str:
    return f"{hr(x)} €"


def dd(iso: str | None) -> str:
    if not iso:
        return "-"
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {int(m)}. {y}."


def img(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((SEG / name).read_bytes()).decode()


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


NAMES = {
    "B0_BUYHOLD": "Kupi i drži",
    "K1_C13C_ORIG": "C13C (tvoje pravilo)",
    "K2_SMA200_TREND": "Drži iznad SMA200 (K2)",
    "K3_DONCHIAN_55_20": "Proboj 55/20 (K3)",
    "K4_TSMOM_126": "Zamah 126 dana (K4)",
    "K5_SUPPORT_RESISTANCE": "Potpora (K5)",
    "K5B_SR_BREAKOUT_RETEST": "Proboj i povratak (K5B)",
    "K6_MOMENTUM_CS": "Rotacija po zamahu (K6)",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C + ponovni ulaz (K7)",
}
PLAIN = {
    "B0_BUYHOLD": "Kupiš prvi dan i ništa ne diraš do kraja. To je mjerilo, ne strategija.",
    "K1_C13C_ORIG": "Kupuješ nakon pada od 5 % u 5 dana, ali samo ako je dionica u dugom uzletu (iznad SMA200). Prodaješ kad cijena padne 10 % ispod najvišeg dosega (pomični stop).",
    "K2_SMA200_TREND": "Držiš dok je cijena iznad SMA200, izlaziš kad padne ispod nje.",
    "K3_DONCHIAN_55_20": "Kupuješ kad cijena probije najviši vrh zadnjih 55 dana, prodaješ kad padne ispod najnižeg dna zadnjih 20 dana.",
    "K4_TSMOM_126": "Držiš dok je prinos zadnjih 126 dana (oko šest mjeseci) pozitivan.",
    "K5_SUPPORT_RESISTANCE": "Kupuješ kad cijena u uzletu padne do ranijeg lokalnog dna (potpore) i obrani ga.",
    "K5B_SR_BREAKOUT_RETEST": "Kupuješ kad cijena probije raniji lokalni vrh i vrati se do te razine, a odbije se.",
    "K6_MOMENTUM_CS": "Svaki mjesec držiš bolju polovicu dionica po zamahu (rotacija). Ima premalo poslova za proglašenje pobjednika.",
    "K7_C13C_PLUS_TREND_REENTRY": "Kao C13C, ali se nakon izbijanja stopom vraćaš čim se trend potvrdi. Nova hipoteza, vlastiti freeze ID.",
}
RATING = {
    "green": ("dokaz valjan", "good"),
    "yellow": ("dokaz ograničen", "warn"),
    "red": ("dokaz nevaljan", "bad"),
    "mjerilo": ("mjerilo", ""),
}


def para(text: str) -> str:
    return f"<p>{e(text)}</p>"


def fig(name: str, title: str, caption_html: str) -> str:
    return (
        f'<figure><p class="fig-title">{e(title)}</p><div class="plate"><img src="{img(name)}" alt="{e(title)}" loading="lazy"></div>'
        f"<figcaption>{caption_html}</figcaption></figure>"
    )


# ---------------------------------------------------------------- page
def build() -> tuple[str, dict[str, str]]:
    A = load(SEG / "analysis.json")
    P = load(SEG / "profile.json")
    CI = load(SEG / "chart_info.json")
    tab = A["segment_portfolio_table_ai_era"]
    per = A["per_ticker_table_ai_era"]
    win = A["winner"]
    wv = win["winner_vs_hold"]
    hold, c13 = tab["B0_BUYHOLD"], tab["K1_C13C_ORIG"]
    rat = A["ratings"]["by_contender"]
    tickers: list[str] = A["tickers_used"]
    honest = A["c13c_honest_report"]
    checks: dict[str, str] = {}

    def chk(label: str, text: str) -> str:
        checks[label] = text
        return text

    # ---- header
    verdict_line = (
        f"Najbolje je posao odradio C13C (Sharpe {hr(c13['sharpe'], 2)}), ali držanje je ipak pobijedilo: "
        f"od 1.000 € uloženih 3. 1. 2023. držanje bi do 5. 10. 2026. dalo {eur(hold['end_value_per_1000_eur'])}, a C13C {eur(c13['end_value_per_1000_eur'])}."
    )
    for label, val in (
        ("hold_end", eur(hold["end_value_per_1000_eur"])),
        ("c13_end", eur(c13["end_value_per_1000_eur"])),
        ("c13_sharpe", hr(c13["sharpe"], 2)),
    ):
        checks[label] = val
    facts = [
        (pc(c13["total_return_pct"], 0, True), "C13C, prinos u AI eri", "pos"),
        (pc(hold["total_return_pct"], 0, True), "kupi i drži, isto razdoblje", ""),
        (f"{hr(c13['sharpe'], 2)} / {hr(hold['sharpe'], 2)}", "Sharpe: C13C / držanje", ""),
        (f"{pc(c13['max_drawdown_pct'], 1)} / {pc(hold['max_drawdown_pct'], 1)}", "najveći pad: C13C / držanje", "neg"),
        (f"{eur(c13['end_value_per_1000_eur'])} / {eur(hold['end_value_per_1000_eur'])}", "1.000 € postane: C13C / držanje", ""),
        (str(c13["trades"]), "C13C poslova na tri dionice", ""),
    ]
    facts_html = "".join(f'<div class="fact"><b class="{c}">{e(v)}</b><span>{e(t)}</span></div>' for v, t, c in facts)

    header = f"""<header><span class="tag">Memorija (DRAM, NAND, diskovi) · istraživačka simulacija · 3. 1. 2023. do 5. 10. 2026.</span>
<h1>Memorija: Micron, Western Digital i Seagate</h1>
<p class="lead">{e(verdict_line)}</p>
<div class="badge-row"><span class="badge good">Ocjena dokaza za C13C: zeleno</span><span class="badge warn">Držanje je bolje po prinosu</span>
<span class="note">Ocjena blagog kritičara govori je li dokaz valjan, ne je li strategija bolja od držanja. Nije formalni Critic PASS laboratorija.
Ovo je istraživačka simulacija na povijesnim podacima, nije savjet za ulaganje i nijedan nalog nije poslan.</span></div></header>
<div class="facts">{facts_html}</div>"""

    # ---- what is this
    ex = CI["price"]["MU"]["first"]
    what = f"""<section><h2>Što je ovo, običnim riječima</h2>
<p>Pitanje je jednostavno: <b>je li se u tri dionice koje čine memoriju i pohranu za AI isplatilo trgovati po pravilu C13C, ili je bilo bolje samo kupiti i čekati?</b>
Gledamo Micron (MU), Western Digital (WDC) i Seagate (STX). Sve je izračunato na stvarnim dnevnim cijenama, kao igra na papiru: nikakav novac nije stvarno uložen.</p>
<p><b>Primjer s 1.000 €.</b> Zamisli da si 3. 1. 2023. u svaku od tri dionice stavio po 1.000 € (ukupno 3.000 €, a sve brojke niže prikazujemo po 1.000 €).
<b>Držanje</b> znači da kupiš prvi dan i ne diraš ništa: 1.000 € je do 5. 10. 2026. narastao na {e(eur(hold['end_value_per_1000_eur']))}.
<b>C13C</b> je tvoje pravilo koje ne drži stalno, nego čeka priliku:</p>
<ol class="steps">
<li>Na kraju dana pogleda je li dionica u dugom uzletu: zatvaranje je iznad SMA200 (prosjeka zadnjih 200 zatvaranja).</li>
<li>Pogleda je li u zadnjih 5 dana pala 5 % ili više. To je mali, privremeni pad usred uzleta, kao zastoj na uzbrdici.</li>
<li>Ako su oba uvjeta ispunjena, sutradan na otvaranju kupi.</li>
<li>Odmah postavi stop (automatsku prodaju) 10 % ispod najvišeg dosega od kupnje. Stop ide samo gore, nikad dolje.</li>
<li>Kad cijena padne na stop, proda. Nema cilja dobiti: pušta dobitke da rastu.</li>
</ol>
<p><b>Stvaran primjer iz podataka:</b> MU je {e(dd(CI['price']['MU']['sig_day']))} pao {e(pc(abs(CI['price']['MU']['sig_drop']), 1))} u 5 dana, a ostao iznad SMA200. Sutradan je kupnja po {e(hr(ex['raw_entry'], 2))} $.
Posao je zatvoren {e(dd(ex['exit_date']))} po {e(hr(ex['raw_exit'], 2))} $, što je nakon troškova {e(pc(ex['return'] * 100, 1, True))}: od 1.000 € to je {e(eur(1000 * (1 + ex['return'])))}.</p>
<p><b>Troškovi.</b> U simulaciji svaka kupnja i svaka prodaja plaćaju 2,5 baznih bodova (0,025 %): na 1.000 € to je 0,25 € po strani. Testiramo i dvostruke i trostruke troškove. Tečaj eura prema dolaru, porezi i minimalna provizija brokera nisu uključeni (vidi dio o ograničenjima).</p>
<p class="note">Razdoblje: glavno mjerilo je AI era, od 3. 1. 2023. do 5. 10. 2026. (nakon 2022. tržište se promijenilo, pa to razdoblje najviše vrijedi). 2016. do 2022. služi samo kao kontekst. Rezultati iz prošlosti ne obećavaju ništa za budućnost.</p></section>"""

    # ---- segment story
    why = A["why_together"]
    story = f"""<section><h2>Priča segmenta: zašto su ove tri dionice zajedno</h2>
<span class="tag-ctx">{e(why['label'])}</span>
<p>{e(why['text_hr'])}</p>
<ul>{''.join(f'<li>{e(d)}</li>' for d in why['drivers_hr'])}</ul>
<p class="note">Isključeno: {e(A['tickers_excluded'][0]['ticker'])}, razlog: {e(A['tickers_excluded'][0]['reason'])}.
Svaki ticker je zaseban račun s 1.000 €, bez prelijevanja novca među njima. {e(A['capital_note_hr'])}</p></section>"""

    # ---- verdict + scoreboard table
    order = [k for k in NAMES if k in tab and "total_return_pct" in tab[k]]
    rows = []
    for k in order:
        t = tab[k]
        lab, tone = RATING.get(rat[k]["rating"], (rat[k]["rating"], "warn"))
        cls = "me" if k == "K1_C13C_ORIG" else ("bench" if k == "B0_BUYHOLD" else "")
        pill = f'<span class="pill {tone}">{e(lab)}</span>'
        rows.append(
            f'<tr class="{cls}"><td class="l">{e(NAMES[k])}</td><td>{pc(t["total_return_pct"], 0, True)}</td><td>{hr(t["sharpe"], 2)}</td>'
            f'<td>{pc(t["max_drawdown_pct"], 1)}</td><td>{t["trades"]}</td><td>{pc(t["exposure_pct"], 0)}</td>'
            f'<td>{eur(t["end_value_per_1000_eur"])}</td><td>{pill}</td><td class="wrap">{e(PLAIN[k])}</td></tr>'
        )
    verdict = f"""<section><h2>Tko je odradio posao</h2>
<div class="verdict"><p><b>{e(win['verdict_hr'])}</b></p></div>
<p style="margin-top:14px">Pobjednik se bira po pravilu zadanom unaprijed: {e(win['rule_fixed_in_advance'])} Zato K6 ({e(win['not_eligible']['K6_MOMENTUM_CS'])}) ne može pobijediti, ma kako izgledao.</p>
<div class="table-wrap"><table><thead><tr><th class="l">Pravilo</th><th>Prinos</th><th>Sharpe</th><th>Najveći pad</th><th>Poslova</th><th>U poziciji</th><th>1.000 € postane</th><th>Ocjena dokaza</th><th class="l">Što radi</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">Segment = tri dionice zajedno (3 x 1.000 €), AI era 3. 1. 2023. do 5. 10. 2026., trošak 2,5 bps po strani. Ocjena: <b>zeleno</b> = dokaz valjan, <b>žuto</b> = dokaz ograničen (premalo poslova), <b>crveno</b> = nevaljan (nijedan). Pad, nestabilnost i koncentracija ocjenu ne snižavaju. Ocjena nije Critic PASS i ne znači da je pravilo bolje od držanja.
Višestruko testiranje: u dnevniku pokušaja je K = 533, pa i najbolja ćelija tablice može biti djelomično sreća (deflated Sharpe za C13C na segmentu: {hr(c13['deflated_sharpe_prob_informative'], 2)}, informativno).</p></section>"""
    checks["winner"] = win["winner"]

    # ---- per ticker table
    prow = []
    for t in tickers:
        h, c = per[t]["B0_BUYHOLD"], per[t]["K1_C13C_ORIG"]
        best = A["best_non_hold_per_ticker_by_sharpe"][t]
        gap = next(x for x in honest["per_ticker"] if x["ticker"] == t)["gap_stop_exits"]
        prow.append(
            f'<tr><td class="l"><b>{t}</b></td><td>{pc(h["total_return_pct"], 0, True)}</td><td>{pc(c["total_return_pct"], 0, True)}</td>'
            f'<td>{hr(h["sharpe"], 2)}</td><td>{hr(c["sharpe"], 2)}</td><td>{pc(h["max_drawdown_pct"], 1)}</td><td>{pc(c["max_drawdown_pct"], 1)}</td>'
            f'<td>{c["trades"]}</td><td>{pc(c["exposure_pct"], 0)}</td><td>{gap}</td>'
            f'<td>{eur(h["end_value_per_1000_eur"])} / {eur(c["end_value_per_1000_eur"])}</td>'
            f'<td class="l">{e(NAMES[best["id"]])}: Sharpe {hr(best["sharpe"], 2)}, {best["trades"]} poslova</td></tr>'
        )
    tick = f"""<section><h2>Po dionici (AI era)</h2>
<div class="table-wrap"><table><thead><tr><th class="l">Dionica</th><th>Prinos: držanje</th><th>Prinos: C13C</th><th>Sharpe: držanje</th><th>Sharpe: C13C</th>
<th>Pad: držanje</th><th>Pad: C13C</th><th>C13C poslova</th><th>C13C u poziciji</th><th>Izlazi preko noći ispod stopa</th><th>1.000 € postane (držanje / C13C)</th><th class="l">Najbolje pravilo po Sharpeu (bez držanja)</th></tr></thead>
<tbody>{''.join(prow)}</tbody></table></div>
<p class="note">Na WDC je najbolji Sharpe pravila K3 (1,87 naspram držanja 1,74), ali to počiva na samo 4 posla i ne smije se čitati kao dokaz. Nijedno pravilo nije pobijedilo držanje po prinosu ni na jednoj dionici.
"Izlaz preko noći ispod stopa" znači da je dionica sljedeće jutro otvorila ispod stopa, pa je prodaja bila po lošijoj cijeni od stopa.</p></section>"""

    # ---- charts block
    pr = CI["price"]
    eq, dr, tr = CI["equity"], CI["drawdown"], CI["trades"]
    cost_rows = CI["costs"]["rows"]
    figs = []
    for t in tickers:
        info = pr[t]
        b, w = info["best"], info["worst"]
        figs.append(
            fig(
                info["file"],
                f"{t}: cijena, SMA200 i svaki ulaz i izlaz C13C",
                f"<b>Što gledaš:</b> plava crta je cijena, siva crtkana je SMA200. Zeleni trokut gore je kupnja, crveni trokut dolje je izlaz stopom, a C13C je na {t} imao {info['n_trades']} poslova. "
                f"Crvena točkasta crta je <b>stop jednog posla</b> (najboljeg): počinje 10 % ispod cijene kupnje i putuje gore za svakim novim vrhom, ali nikad dolje. Crta je rekonstrukcija po pravilu, a završava na {hr(info['stop_final'], 2)} $, a stvarni izlaz je bio po {hr(b['raw_exit'], 2)} $. "
                f"<b>Što nauči:</b> signal ({dd(info['sig_day'])}) je bio pad od {pc(abs(info['sig_drop']), 1)} u 5 dana uz cijenu iznad SMA200, a ne bilo kakav pad. Najbolji posao je donio {pc(b['return'] * 100, 1, True)} "
                f"(1.000 € postane {eur(1000 * (1 + b['return']))}), najgori {pc(w['return'] * 100, 1, True)} (1.000 € postane {eur(1000 * (1 + w['return']))}). "
                f"Vidi se i da C13C često izlazi i ulazi kroz uzlet: zato nema svaki rast.",
            )
        )
    figs.append(
        fig(
            eq["file"],
            "Rast 1.000 €: držanje, C13C i najjači po prinosu",
            f"<b>Što gledaš:</b> kamo je išao 1.000 € u tri varijante. Sivo je držanje ({eur(eq['hold_end'])} na kraju), plavo C13C ({eur(eq['c13_end'])}), zeleno pravilo K4 koje je dalo najviši prinos među pravilima ({eur(eq['k4_end'])}). Skala je logaritamska: jednak razmak znači isti postotak rasta. "
            f"<b>Što nauči:</b> od {dd(eq['fall_peak'])} do {dd(eq['fall_bottom'])} držanje je palo s {eur(eq['hold_peak_val'])} na {eur(eq['hold_bottom_val'])}, a C13C s {eur(eq['c13_peak_val'])} na {eur(eq['c13_bottom_val'])}. "
            f"Ravni dio plave crte ({eq['flat_days']} dana) je razdoblje kad su sve tri dionice bile u gotovini: tada ni ne gubiš ni ne zarađuješ. To je i zasluga i cijena C13C-a: zaštitio je od dijela pada, ali nije pratio rast.",
        )
    )
    figs.append(
        fig(
            dr["file"],
            "Najgori trenuci: pad od vrha",
            f"<b>Što gledaš:</b> na svaki dan, koliko je vrijednost ispod svog dotadašnjeg najvišeg dosega. Sivo je držanje, crveno C13C. "
            f"<b>Što nauči:</b> najgori trenutak držanja bio je {dd(dr['hold_bottom'])}: {pc(dr['hold_dd'], 1)}, a ako si imao 1.000 € na vrhu, ostalo bi {eur(1000 * (1 + dr['hold_dd'] / 100))} (gubitak {eur(-10 * dr['hold_dd'])}). "
            f"C13C je imao dno {dd(dr['c13_bottom'])} na {pc(dr['c13_dd'], 1)}, gubitak {eur(-10 * dr['c13_dd'])}, dakle {eur(10 * (dr['c13_dd'] - dr['hold_dd']))} manje. "
            f"Najgori pojedinačni dan držanja bio je {dd(dr['worst_day_date'])} ({pc(dr['worst_day'], 1)}); stop ne štiti od takvih dana jer dionica otvori ispod stopa.",
        )
    )
    figs.append(
        fig(
            tr["file"],
            "Svaki C13C posao: trajanje i prinos",
            f"<b>Što gledaš:</b> svaka točka je jedan posao na MU, WDC ili STX. Vodoravno je koliko je dana trajao, okomito koliko je donio (nakon troškova). "
            f"<b>Što nauči:</b> {tr['wins']} od {tr['n']} poslova bilo je dobitno, prosječni dobitak {pc(tr['avg_win'], 1, True)}, prosječni gubitak {pc(tr['avg_loss'], 1, True)}. "
            f"Najbolji je {tr['best']['ticker']} {pc(tr['best']['ret'], 1, True)} ({dd(tr['best']['entry_date'])} do {dd(tr['best']['exit_date'])}), najgori {tr['worst']['ticker']} {pc(tr['worst']['ret'], 1, True)}. "
            f"{tr['gap_exits']} poslova završilo je izlazom preko noći ispod stopa. Kratki poslovi su većinom mali gubici, dugi su veliki dobici.",
        )
    )
    figs.append(
        fig(
            CI["scoreboard"]["file"],
            "Ljestvica suparnika: prinos i Sharpe naspram držanja",
            f"<b>Što gledaš:</b> lijevo ukupni prinos u AI eri, desno Sharpe (dobit po jedinici nemira: veći je bolji). Crvena crtica je držanje. "
            f"<b>Što nauči:</b> nijedno pravilo ne prelazi crvenu crtu po prinosu ({pc(hold['total_return_pct'], 0)} držanje, C13C {pc(c13['total_return_pct'], 0)}). "
            f"Po Sharpeu je C13C ({hr(c13['sharpe'], 2)}) skoro izjednačen s držanjem ({hr(hold['sharpe'], 2)}), ali Sharpe ne vidi da je veći dio rasta propušten.",
        )
    )
    k1c, k7c = cost_rows["K1_C13C_ORIG"], cost_rows["K7_C13C_PLUS_TREND_REENTRY"]
    figs.append(
        fig(
            CI["costs"]["file"],
            "Otpornost na troškove: 1x, 2x, 3x",
            f"<b>Što gledaš:</b> za svako pravilo tri šipke: koliko posto zarade ostane uz osnovne troškove (100 %), dvostruke i trostruke. "
            f"<b>Što nauči:</b> troškovi nisu glavni problem. Kod C13C-a od 1.000 € ostane {eur(k1c['end3'])} umjesto {eur(k1c['end1'])} (zadržano {pc(k1c['kept'], 0)} zarade). "
            f"Najviše gubi K7 koji najviše trguje: {eur(k7c['end3'])} umjesto {eur(k7c['end1'])}. Što se češće trguje, to troškovi više grizu. "
            f"Stvarna minimalna provizija brokera nije modelirana (nepotvrđeno za tvoj tarif).",
        )
    )
    figs.append(
        fig(
            CI["lesson"]["file"],
            "Pouka segmenta: manji pad je skup",
            f"<b>Što gledaš:</b> svaka točka je jedno pravilo. Vodoravno najveći pad od vrha (lijevo = mirnije), okomito koliko je od 1.000 € postalo na kraju. "
            f"<b>Što nauči:</b> C13C je smanjio najgori gubitak sa {eur(wv['worst_loss_per_1000_eur_hold'])} na {eur(wv['worst_loss_per_1000_eur_winner'])} na 1.000 € (ušteda {eur(wv['worst_loss_saved_eur'])}), "
            f"ali je za to \"platio\" {eur(wv['end_value_given_up_eur'])} manje na kraju. To je osiguranje koje je u ovom razdoblju bilo vrlo skupo. "
            f"Ovo vrijedi za AI eru, dugu uzlaznu fazu; u dugom padajućem tržištu račun bi mogao izgledati drukčije (taj režim nije testiran).",
        )
    )
    charts = f'<section><h2>Grafovi koji objašnjavaju rezultat</h2>{"".join(figs)}</section>'

    # ---- behaviour section
    cards = A["behaviour_cards"]
    ccards = []
    for t in tickers:
        c = cards[t]
        m = c["mechanism"]
        dds = c["worst_drawdowns"][0]
        ccards.append(
            f"""<div class="tcard"><h3>{t} · {e(c['company'])}</h3>
<span class="tag-ctx">iz naših podataka (AI era)</span>
<dl><div><dt>Karakter</dt><dd>{e(c['character_hr'])}</dd></div>
<div><dt>Nakon pada od 5 %</dt><dd>{e(c['after_5d_dip_hr'])}</dd></div>
<div><dt>Najveći pad</dt><dd>Vrh {e(dd(dds['peak_date']))} ({e(hr(dds['peak_close'], 2))} $), dno {e(dd(dds['bottom_date']))} ({e(hr(dds['bottom_close'], 2))} $), {e(pc(dds['depth_pct'], 1))}. Od 1.000 € ostane {e(eur(dds['left_of_1000_eur']))}; {'oporavak do starog vrha ' + e(dd(dds['recovery_date'])) if dds.get('recovery_date') else 'do kraja podataka stari vrh nije dosegnut'}.</dd></div>
<div><dt>Potpora i otpor</dt><dd>{e(c['support_resistance_hr'])}</dd></div>
<div><dt>Najveći jaz otvaranja</dt><dd>{e(dd(c['largest_gap']['date']))}: {e(pc(c['largest_gap']['gap_pct'], 1, True))}. Stop ne štiti od jaza.</dd></div>
<div><dt>Koji algoritam odgovara</dt><dd>{e(c['algorithm_fit_hr'])}</dd></div></dl>
<div class="ctx"><span class="tag-ctx">{e(m['label'])}</span><dl>
<div><dt>Što prodaje</dt><dd>{e(m['sells'])}</dd></div><div><dt>Što pokreće prihod</dt><dd>{e(m['revenue_drivers'])}</dd></div>
<div><dt>Mjesto u AI lancu</dt><dd>{e(m['chain_position'])}</dd></div><div><dt>Ciklus</dt><dd>{e(m['cycle'])}</dd></div>
<div><dt>Što može povrijediti</dt><dd>{e(m['hurts'])}</dd></div></dl></div></div>"""
        )
    dp, sn = CI["dip"]["vals"], CI["season"]["info"]
    pre = P["premise_c13c_hr"]
    beh_figs = [
        fig(
            CI["dip"]["file"],
            "Što se dogodilo nakon pada od 5 % u 5 dana (dok je cijena iznad SMA200)",
            f"<b>Što gledaš:</b> za svaku dionicu četiri stupca: prosječan prinos idućih 5 dana u običan dan i nakon takvog pada, prije 2023. i u AI eri. "
            f"<b>Što nauči:</b> na MU je nakon takvog pada u AI eri idućih 5 dana u prosjeku bilo {pc(dp['MU']['ai_dip'], 1, True)} naspram {pc(dp['MU']['ai_normal'], 1, True)} u običan tjedan (na 1.000 € to je oko {eur(10 * dp['MU']['ai_dip'])} naspram {eur(10 * dp['MU']['ai_normal'])}). "
            f"Prije 2023. razlika je bila mnogo manja ({pc(dp['MU']['pre_dip'], 1, True)} naspram {pc(dp['MU']['pre_normal'], 1, True)}). Pažnja: neovisnih događaja je samo oko 21 do 23 po dionici, a cijela AI era je bila rast. To je opis prošlosti, ne dokaz strategije.",
        ),
        fig(
            CI["season"]["file"],
            "Sezonalnost: prosječan prinos po mjesecu u AI eri",
            f"<b>Što gledaš:</b> za svaki mjesec prosjek svih godina AI ere. "
            f"<b>Što nauči:</b> MU je u svibnju u prosjeku imao {pc(sn['MU']['best'], 0, True)}, a u srpnju {pc(sn['MU']['worst'], 0, True)}. {e(P['seasonality_warning_hr'])}",
        ),
        fig(
            CI["drawdowns"]["file"],
            "Anatomija najvećeg pada svake dionice",
            "<b>Što gledaš:</b> crveno je put od vrha do dna, zeleno put natrag do starog vrha. Točke su označene s datumom i cijenom zatvaranja. "
            f"<b>Što nauči:</b> MU je trebao {CI['drawdowns']['info']['MU']['days_down']} dana od vrha do dna i još {(date.fromisoformat(CI['drawdowns']['info']['MU']['recovery']) - date.fromisoformat(CI['drawdowns']['info']['MU']['bottom'])).days} dana da se vrati. "
            "WDC je u svom najvećem padu još uvijek ispod starog vrha. Ovo su pad od vrha i oporavak izračunati na zatvaranjima. Tako izgledaju 40 do 58 % pada iz uzleta: nisu iznimka u ovom segmentu, nego dio njegove naravi.",
        ),
        fig(
            CI["support"]["file"],
            "MU: potpore i što se dogodilo pri dodiru",
            f"<b>Što gledaš:</b> isprekidane linije su raniji lokalni minimumi (potpore). Krug = potpora je u idućih 5 dana držala, križić = probijena. "
            f"<b>Što nauči:</b> {e(P['support_resistance_hr'][0])} {e(P['support_resistance_reading_hr'])} "
            f"Oznake na grafu su ilustracija po istoj definiciji za razdoblje 2025. do 2026.; službene brojke su iz profila, a one na grafu mogu se malo razlikovati u broju dodira.",
        ),
    ]
    prof_notes = f"""<div class="callout neutral"><h3>Što još kaže profil (AI era)</h3><ul>
<li>{e(pre['reading'])}</li>
<li>{e(P['after_52w_high_reading_hr'])}</li>
<li>{e(P['sma200_reading_hr'])}</li>
<li>{e(P['lead_lag_reading_hr'])}</li>
<li>Koncentracija: {e(P['concentration_gaps_hr'][0])} {e(P['concentration_gaps_hr'][1])} {e(P['concentration_gaps_hr'][2])}</li>
<li>{e(P['context_before_after_2023_hr'])}</li></ul></div>"""
    behav = f"""<section><h2>Kako se ponaša svaka dionica</h2>
<p>Ovo je opis ponašanja u prošlosti, nije savjet i nije strategija. Dio o poslovanju dolazi iz javnih izvora i izričito je označen; brojke o kretanju cijena izračunate su iz naših dnevnih podataka.</p>
<div class="tcards">{''.join(ccards)}</div>
<h3 class="sub">Grafovi ponašanja</h3>{''.join(beh_figs)}{prof_notes}</section>"""

    # ---- honest C13C report
    rb = honest["robustness_pm20_memory"]
    vrows = []
    pname = {"sma": "SMA duljina", "dip": "veličina pada", "trail": "pomični stop"}
    for v in rb["variants"]:
        val = v["value"]
        shown = f"{int(round(val))} dana" if v["param"] == "sma" else pc(val * 100, 0)
        vrows.append(
            f'<tr><td class="l">{e(pname[v["param"]])} {"-20 %" if v["factor"] < 1 else "+20 %"}</td><td>{e(shown)}</td><td>{pc(v["total_return"] * 100, 0, True)}</td><td>{hr(v["sharpe"], 2)}</td></tr>'
        )
    honest_html = f"""<section><h2>Tvoj C13C bez uljepšavanja</h2>
<p>{e(honest['summary_hr'])}</p>
<ul>{''.join(f'<li>{e(x["text_hr"])}</li>' for x in honest['per_ticker'])}</ul>
<h3 class="sub">Što ako se postavke pomaknu za 20 %?</h3>
<p>Ako pravilo radi samo uz savršeno odabrane brojke, to je znak da je pogođeno za prošlost. Zato svaku postavku pomaknemo za 20 % gore i dolje i gledamo mijenja li se ishod. Osnovni prinos je {pc(rb['base_total_return'] * 100, 0, True)} (Sharpe {hr(rb['base_sharpe'], 2)}).</p>
<div class="table-wrap"><table><thead><tr><th class="l">Postavka</th><th>Vrijednost</th><th>Prinos u AI eri</th><th>Sharpe</th></tr></thead><tbody>{''.join(vrows)}</tbody></table></div>
<p class="note">Najlošija varijanta ({pc(rb['min_total_return'] * 100, 0, True)}) i najbolja ({pc(rb['max_total_return'] * 100, 0, True)}) ostaju pozitivne{', predznak se nigdje ne okreće' if not rb['sign_flips'] else ''}. U bik-tržištu je to slab test (gotovo sve je pozitivno), pa ovo samo isključuje očitu krhkost; ne dokazuje da pravilo vrijedi ubuduće. Ocjena C13C-a: {e(rat['K1_C13C_ORIG']['reason_hr'])}</p>
<h3 class="sub">Ključni zaključci</h3><ul>{''.join(f'<li>{e(x)}</li>' for x in A['key_findings_hr'][1:])}</ul></section>"""

    # ---- glossary
    gl = [
        ("Kupi i drži", "Kupiš i ne diraš. 1.000 € uložen 3. 1. 2023. u ovaj segment bio bi 5. 10. 2026. vrijedan " + eur(hold["end_value_per_1000_eur"]) + ". Služi kao mjerilo svih pravila."),
        ("SMA200", "Prosjek zadnjih 200 zatvaranja, grubo mjerilo dugog trenda. Ako je prosjek 100 €, a cijena 120 €, cijena je iznad njega: dionica je u dugom uzletu, kao da se penješ uzbrdo."),
        ("Pomični stop", "Automatska prodaja koja ide gore s cijenom, a nikad dolje. Kupiš po 100 €, stop je na 90 €. Cijena ode na 130 €, stop je na 117 €. Ako padne na 117 €, izlaziš s oko +17 %."),
        ("Jaz preko noći (gap)", "Dionica sljedeće jutro otvori puno niže nego što je prethodni dan zatvorila. Stop od 90 € ne pomaže ako dionica otvori na 80 €: prodaja je po 80 €. U ovom segmentu je to bilo " + str(CI["trades"]["gap_exits"]) + " od " + str(CI["trades"]["n"]) + " C13C poslova."),
        ("Pad od vrha (drawdown)", "Koliko vrijednost padne od svog najboljeg trenutka do dna. 1.000 € naraste na 2.000 €, pa padne na 1.200 €: pad od vrha je 40 %."),
        ("Sharpe", "Koliko dobiti dobiješ po jedinici nemira (kolebanja). Dva vozača stignu u isto vrijeme, ali jedan je vozio mirno, a drugi trzajući: mirniji ima veći Sharpe. Oko 1 je dobro, preko 1,5 vrlo dobro, ispod 0,5 slabo."),
        ("Izloženost", "Udio vremena kad je novac u dionici. 50 % znači da je pola vremena u dionici, pola u gotovini. Manja izloženost znači manje padova, ali i propuštene rastove."),
        ("Trošak, bazni bod (bps)", "Bazni bod je stoti dio postotka. 2,5 bps = 0,025 %, pa na kupnju od 1.000 € platiš 0,25 €, i toliko pri prodaji. Test 2x i 3x pita: što ako je trošak dvostruko ili trostruko veći."),
        ("AI era", "Razdoblje od 2023. nadalje, kad je AI promijenio tržište. Glavno mjerilo; 2016. do 2022. samo je kontekst."),
        ("Sleeve (zaseban račun)", "Svaka dionica ima svojih 1.000 €, bez prelijevanja. Ako jedna miruje u gotovini, ta 1.000 € ne pomaže drugoj dionici."),
        ("Volatilnost (nestabilnost)", "Koliko cijena tipično skače gore-dolje u godini. 50 % znači tipičan raspon godine oko +-500 € na 1.000 €."),
        ("Beta i korelacija", "Beta 1,3 prema SMH: kad SMH padne 10 %, dionica u prosjeku padne oko 13 %. Korelacija 0,76 znači da većinu dana idu istim smjerom. SMH i NDX ovdje su samo mjerila, ne prijedlog za trgovanje."),
        ("Omjer varijance", "Raste li nestabilnost brže (iznad 1, zamah) ili sporije (ispod 1, povratak prema sredini) kad gledaš dulje razdoblje. Blizu 1 = kretanje je gotovo nasumično."),
        ("Neovisni događaj", "Događaj odvojen od prethodnog najmanje 20 dana. Ako je dionica pala 5 dana zaredom, to je jedan događaj, ne pet: pravi uzorak je taj manji broj."),
        ("Potpora i otpor", "Potpora je raniji lokalni minimum za koji se vjeruje da će cijenu 'zadržati'. Provjerili smo: drži otprilike jednako često kao nasumična razina, pa sama crta nije razlog za kupnju."),
        ("Broj pokušaja (K) i deflated Sharpe", "Što više pravila isprobaš, veća je šansa da jedno izgleda dobro čistom srećom: 500 puta baci novčić i negdje će pasti osam glava zaredom. Ovdje je K = 533. Deflated Sharpe zato traži veći rezultat; ovdje je samo informativan."),
        ("PSR", "Vjerojatnost da je pravi Sharpe iznad nule. Za C13C na segmentu " + hr(c13["psr"], 2) + " (1 = gotovo sigurno), ali to ne znači da je bolji od držanja."),
        ("Gledanje u budućnost (lookahead)", "Pogreška kad test slučajno koristi podatak koji u tom trenutku još nije postojao, kao ispit s već poznatim rješenjima. Ovdje je pravilo vidjelo samo podatke do zatvaranja, a kupnja ide sutra na otvaranju; oba testa prolaze."),
        ("Logaritamska skala", "Na grafu jednak razmak znači isti postotak, ne isti iznos. Zato se i rast od 50 $ na 100 $ vidi jednako velik kao od 500 $ na 1.000 $."),
    ]
    gloss = f"""<section><h2>Rječnik pojmova s primjerima</h2><dl>{''.join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in gl)}</dl></section>"""

    # ---- EU/HR block
    eun = A["eu_hr_notes"]
    eu_items = "".join(
        f'<li><b>{t}</b> <span class="pill warn">nepotvrđeno</span> {e(eun[t])}</li>' for t in tickers
    )
    eu = f"""<section><h2>Može li se ovo trgovati iz Hrvatske?</h2>
{eu_block(tickers)}
<ul>{eu_items}</ul>
<p>{e(eun['common_hr'])} <span class="pill warn">nepotvrđeno</span></p>
<p class="note">Sve što piše o dostupnosti kod Interactive Brokersa, o proviziji, razlomljenim dionicama i o porezima je <b>nepotvrđeno</b> dok se ne provjeri u samom brokeru, a o porezu se ovdje ništa ne tvrdi. SMH i NDX u analizi su samo mjerila; ne predlažemo ih kao proizvod jer američki ETF-ovi često nisu dostupni malim ulagačima iz EU (nema KID dokumenta).
Pretpostavka je dugo bez poluge i bez kratke prodaje.</p></section>"""

    # ---- limits
    caveats = A["caveats_hr"]
    limits = f"""<section><h2>Ograničenja: što nije modelirano</h2>
<ul>{''.join(f'<li>{e(x)}</li>' for x in caveats)}
<li>Ovo je istraživačka simulacija: ocjene blagog kritičara nisu formalni Critic PASS, a u laboratoriju je popis odobrenih strategija i dalje prazan.</li>
<li>Stop je u simulaciji ispunjen po cijeni stopa ili po otvaranju ako je dan otvorio ispod njega. U stvarnosti je moguće i lošije proklizavanje, pogotovo kod ovako nestabilnih dionica.</li>
<li>Kupnja je na sljedećem otvaranju, a cijena otvaranja nije garantirana. Razlomljene dionice su pretpostavka (nepotvrđeno).</li>
<li>Profil: {e(' '.join(P['limits_hr']))}</li>
<li>Status provjere simulatora: {e(A['audit_status'])}</li></ul></section>"""

    # ---- final plain verdict
    final = f"""<section class="verdict"><h3>Zaključak običnim riječima</h3>
<p>U razdoblju od 3. 1. 2023. do 5. 10. 2026. sve tri dionice su bile u dugom, snažnom uzletu (uz padove od 41 do 58 %), pa je najbolje rezultate dalo ono najjednostavnije: kupiti i držati. C13C je među pravilima imao najbolji Sharpe ({hr(c13['sharpe'], 2)}) i manji najveći pad ({pc(c13['max_drawdown_pct'], 1)} naspram {pc(hold['max_drawdown_pct'], 1)}), ali je u prosjeku bio izložen samo oko {hr(c13['exposure_pct'], 0)} % vremena pa je propustio velik dio rasta:
na 1.000 € {eur(c13['end_value_per_1000_eur'])} naspram {eur(hold['end_value_per_1000_eur'])}. Rezultat vrijedi za ovo razdoblje i ove troškove; ne znači da će tako biti ubuduće, a ni da bi držanje u lošijem razdoblju prošlo dobro. Ovo nije savjet za ulaganje, nije Critic PASS i ne obećava zaradu.</p></section>"""

    footer = f"""<footer>Istraživačka simulacija na povijesnim dnevnim podacima (data/ohlcv), razdoblje 3. 1. 2023. do 5. 10. 2026. (AI era), kontekst 2016. do 2022. Odluka na zatvaranju, kupnja na idućem otvaranju, trošak 2,5 bps po strani (testirano i 5 i 7,5 bps), bez poluge i bez kratke prodaje, tri dionice po 1.000 €.
Rezultati iz prošlosti ne obećavaju buduće. Ovo je istraživanje, ne savjet za ulaganje, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan.
Izvori: <span class="pill">results/*.json</span> <span class="pill">segments/memory/analysis.json</span> <span class="pill">segments/memory/profile.json</span>.</footer>"""

    body = f"<main>{header}{what}{story}{verdict}{tick}{charts}{behav}{honest_html}{gloss}{eu}{limits}{final}{footer}</main>"
    css = CSS + EXTRA_CSS
    page = (
        '<!doctype html>\n<html lang="hr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        + HEAD.format(title=e(TITLE), css=css)
        + "</head><body>"
        + body
        + "</body></html>"
    )
    return page, checks


# ---------------------------------------------------------------- cross-check against JSON
def verify(page: str) -> list[str]:
    """Recompute headline numbers from the raw results and compare with the page and analysis."""
    A = load(SEG / "analysis.json")
    seg = load(BASE / "results/memory.json")
    text = re.sub(r"<[^>]+>", " ", page)
    text = text.replace("&amp;", "&")
    problems: list[str] = []

    def has(s: str, why: str) -> None:
        if s not in text:
            problems.append(f"missing on page: {s!r} ({why})")

    tab = A["segment_portfolio_table_ai_era"]
    for cid, row in tab.items():
        if "total_return_pct" not in row:
            continue
        eq = seg["contenders"][cid]["equity"]["ai_era"]
        base = 3000.0  # segment = 3 sleeves x 1000 EUR; the first curve point is already after day one
        raw_ret = (eq[-1][1] / base - 1) * 100
        if abs(raw_ret - row["total_return_pct"]) > 0.15:
            problems.append(f"{cid}: equity-derived return {raw_ret:.1f} vs analysis {row['total_return_pct']}")
        end1000 = 1000 * eq[-1][1] / base
        if abs(end1000 - row["end_value_per_1000_eur"]) > 1.0:
            problems.append(f"{cid}: end value per 1000 {end1000:.0f} vs analysis {row['end_value_per_1000_eur']}")
        trades = seg["contenders"][cid]["trades"]["ai_era"]
        if cid != "K6_MOMENTUM_CS" and len(trades) != row["trades"] and cid != "B0_BUYHOLD":
            problems.append(f"{cid}: trades json {len(trades)} vs analysis {row['trades']}")
    # per-ticker equity vs table
    for t, rows in A["per_ticker_table_ai_era"].items():
        res = load(BASE / f"results/{t}.json")
        for cid in ("B0_BUYHOLD", "K1_C13C_ORIG"):
            eq = res["contenders"][cid]["equity"]["ai_era"]
            r = (eq[-1][1] / 1000.0 - 1) * 100
            if abs(r - rows[cid]["total_return_pct"]) > 0.15:
                problems.append(f"{t} {cid}: equity return {r:.1f} vs table {rows[cid]['total_return_pct']}")
    # drawdown from equity
    for cid, key in (("B0_BUYHOLD", "max_drawdown_pct"), ("K1_C13C_ORIG", "max_drawdown_pct")):
        vals = [v for _, v in seg["contenders"][cid]["equity"]["ai_era"]]
        peak, worst = 3000.0, 0.0
        for v in vals:
            peak = max(peak, v)
            worst = min(worst, v / peak - 1)
        if abs(worst * 100 - tab[cid][key]) > 0.15:
            problems.append(f"{cid}: drawdown from equity {worst * 100:.1f} vs {tab[cid][key]}")
    # numbers that must be visible in the Croatian text
    w = A["winner"]["winner_vs_hold"]
    for s, why in (
        (f"{w['per_1000_eur_end_hold']:,}".replace(",", "."), "hold end"),
        (f"{w['per_1000_eur_end_winner']:,}".replace(",", "."), "winner end"),
        (f"{w['worst_loss_saved_eur']}", "saved"),
        (f"{w['end_value_given_up_eur']:,}".replace(",", "."), "given up"),
        (pc(w["winner_max_drawdown_pct"], 1), "winner dd"),
        (pc(w["hold_max_drawdown_pct"], 1), "hold dd"),
        (hr(w["winner_sharpe"], 2), "winner sharpe"),
        (hr(w["hold_sharpe"], 2), "hold sharpe"),
    ):
        has(s, why)
    return problems


def main() -> None:
    page, _ = build()
    out = SEG / "artifact.html"
    out.write_text(page, encoding="utf-8")
    print("wrote", out, f"{len(page) / 1e6:.2f} MB")
    problems = verify(page)
    print("cross-check problems:", problems if problems else "none")


if __name__ == "__main__":
    main()
