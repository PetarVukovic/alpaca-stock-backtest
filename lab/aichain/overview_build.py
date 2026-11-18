"""Build reports/research/AICHAIN_20261014/overview.html (self-contained, Croatian notebook page).

Usage: .venv/bin/python -m lab.aichain.overview_build
Charts are embedded as data URIs; every number comes from overview_data (the JSON result files).
Segment page URLs are NOT known yet: the coordinator replaces the marked placeholder list later.
"""

from __future__ import annotations

import base64
import html
import importlib.util
import json
from pathlib import Path

from lab.aichain import overview_data as D
from lab.aichain import overview_text as T
from lab.aichain.overview_charts import make_all, num_hr, pct_hr

ROOT = D.ROOT
OUT = D.RES
CHART_DIR = OUT / "overview_charts"


def _legacy():
    """Reuse CSS/HEAD of the TOP10 page builder (same notebook look)."""
    spec = importlib.util.spec_from_file_location("top10_art", ROOT / "scripts/top10_build_artifact.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


EXTRA_CSS = """
.sc td.l,.sc th.l{text-align:left;white-space:normal;min-width:11rem}
.sc td{vertical-align:top}
.badge.mute{background:var(--accent-soft);color:var(--accent)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.ph{border:2px dashed var(--warn);background:var(--warn-soft);border-radius:6px;padding:14px 18px}
.ph li{margin-bottom:6px}.ph code{font-family:var(--mono);font-size:.85rem}
.hand{font-family:"Noteworthy","Bradley Hand",cursive;color:var(--bad)}
"""


def img(name: str) -> str:
    data = base64.b64encode((CHART_DIR / name).read_bytes()).decode()
    return f"data:image/png;base64,{data}"


def e(x: object) -> str:
    return html.escape(str(x))


TONE = {"zeleno": ("zeleno", "good"), "žuto": ("žuto", "warn"), "crveno": ("crveno", "bad"), "mjerilo": ("mjerilo", "mute")}


def badge(r: str) -> str:
    label, tone = TONE.get(r, (r, "mute"))
    return f'<span class="badge {tone}" style="font-size:.8rem;padding:2px 10px">{e(label)}</span>'


def scoreboard() -> str:
    rows = []
    for seg in D.SEGMENTS:
        w = D.winner(seg)
        c, h = w.stats, w.hold
        k1 = D.cell(seg, "K1_C13C_ORIG")
        rate = D.ratings(seg).get(w.contender, "nepoznato")
        yes = lambda b: '<b style="color:var(--good)">da</b>' if b else '<b style="color:var(--bad)">ne</b>'
        rows.append(
            f"<tr><td class='l'><b>{e(D.SEGMENT_SHORT[seg])}</b><br><span class='note'>{len(D.segment_tickers(seg))} dionica</span></td>"
            f"<td class='l'>{e(D.CONTENDER_SHORT[w.contender])}<br>{badge(rate)}</td>"
            f"<td>{num_hr(D.per_1000(c), 0)} / {num_hr(D.per_1000(h), 0)} / {num_hr(D.per_1000(k1), 0)}</td>"
            f"<td>{num_hr(c['sharpe'], 2)} / {num_hr(h['sharpe'], 2)}</td>"
            f"<td>{pct_hr(c['max_drawdown'])} / {pct_hr(h['max_drawdown'])}</td>"
            f"<td>{c['trades']}</td><td>{yes(w.beats_hold_return)}</td><td>{yes(w.smaller_drawdown)}</td></tr>"
        )
    return (
        '<div class="table-wrap"><table class="sc"><thead><tr><th class="l">Segment</th><th class="l">Pobjednik (pravilo)</th>'
        "<th>1.000 EUR postane: pobjednik / držanje / C13C</th><th>Sharpe: pobjednik / držanje</th>"
        "<th>Najgori pad: pobjednik / držanje</th><th>Poslova</th><th>Prinos veći od držanja?</th><th>Pad manji?</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def contender_table() -> str:
    rows = []
    for r in D.overall_table():
        k = r["id"]
        rows.append(
            f"<tr><td class='l'><b>{e(D.CONTENDER_SHORT[k])}</b></td><td>{r['wins']}</td><td>{num_hr(r['mean_sharpe'], 2)}</td>"
            f"<td>{r['beats_hold_return']} / 6</td><td>{r['beats_hold_sharpe']} / 6</td><td>{r['smaller_dd']} / 6</td>"
            f"<td>{pct_hr(r['mean_dd'])}</td><td>{r['min_trades']}</td></tr>"
        )
    return (
        '<div class="table-wrap"><table class="sc"><thead><tr><th class="l">Pravilo</th><th>Pobjeda u segmentima</th>'
        "<th>Prosječni Sharpe</th><th>Prinos &gt; držanje</th><th>Sharpe &gt; držanje</th><th>Manji pad od držanja</th>"
        "<th>Prosječni najgori pad</th><th>Najmanje poslova u segmentu</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def build() -> Path:
    make_all(CHART_DIR)
    leg = _legacy()
    wins = D.winners()
    oc = T.overall_counts()
    tc = T.c13c_ticker_counts()
    ot = {r["id"]: r for r in D.overall_table()}
    mem = D.winner("memory")
    net = D.winner("network_servers")
    cl = D.winner("cloud")
    k6 = ot["K6_MOMENTUM_CS"]
    hold_ms = ot["B0_BUYHOLD"]["mean_sharpe"]
    ineligible_k6 = D.cell("memory", "K6_MOMENTUM_CS")["trades"]
    max_dsr = max(w.stats["deflated_sharpe_prob"] for w in wins.values())
    k = D.summary()["ledger_k_after_registration"]

    facts = f"""<div class="facts">
<div class="fact"><b>6</b><span>segmenata AI lanca</span></div>
<div class="fact"><b>{tc['n']}</b><span>dionica u analizi</span></div>
<div class="fact"><b>9</b><span>pravila (uz držanje)</span></div>
<div class="fact"><b class="pos">{oc['beats_ret']} / 6</b><span>pobjednika koji su pobijedili držanje po prinosu</span></div>
<div class="fact"><b class="pos">{oc['smaller_dd']} / 6</b><span>pobjednika s manjim najgorim padom</span></div>
<div class="fact"><b class="neg">{tc['beats_ret']} / {tc['n']}</b><span>dionica na kojima C13C zaradi više od držanja</span></div>
</div>"""

    seg_list = "".join(
        f'<li data-segment="{s}"><b>{e(D.SEGMENT_TITLE[s])}</b> <code>[URL: TBD_{s}]</code></li>' for s in D.SEGMENTS
    )

    body = f"""<main>
<header><span class="tag">Memory Lab · AI lanac · 14. 10. 2026.</span>
<h1>AI lanac: pregled svih šest segmenata</h1>
<p class="lead">Šest skupina dionica, devet pravila, isti simulator, isti troškovi. Glavno mjerilo je AI era (od 2023.). Ovo je istraživanje, ne savjet za ulaganje: nijedan nalog nije poslan i nijedno pravilo nije dobilo Critic PASS.</p>
{facts}
</header>

<section class="verdict"><h2>Kratki odgovor</h2>
<p><b>Držanje je u AI eri teško pobijediti.</b> Pravilo s najvišim Sharpeom u segmentu (uz najmanje {D.MIN_TRADES} poslova i plus uz trošak 2×) pobijedilo je držanje po prinosu u {oc['beats_ret']} od 6 segmenata, a po Sharpeu u {oc['beats_sharpe']} od 6. Manji najgori pad imalo je u {oc['smaller_dd']} od 6.</p>
<p>Primjer s 1.000 EUR: u mrežama i serverima držanje završi s {T.eur(D.per_1000(net.hold))}, a K6 (rotacija zamaha) s {T.eur(D.per_1000(net.stats))}. Ali ako si ušao na vrhu, najgori pad K6 je {T.eur(D.worst_loss_per_1000(net.stats))} umjesto {T.eur(D.worst_loss_per_1000(net.hold))}: pobjednik je i rizičniji.</p>
<p><b>Tvoj C13C:</b> pobjeđuje po pravilu u memoriji (Sharpe {num_hr(mem.stats['sharpe'], 2)}), ali ni tamo ne stiže držanje ({T.eur(D.per_1000(mem.stats))} naspram {T.eur(D.per_1000(mem.hold))} na 1.000 EUR). Na {tc['n']} dionica zaradi više od držanja na {tc['beats_ret']}, ali ima manji najgori pad na {tc['smaller_dd']}. Ponaša se kao osiguranje: smanji pad, ali plati prinosom.</p>
<p class="note">Rejting dokaza (zeleno, žuto, crveno) ne znači da je pravilo bolje od držanja, nego samo da dokaz nije nevaljan (pogled u budućnost, ugađanje, premalo poslova, trošak). Veličina pada ne snižava ocjenu.</p>
</section>

<section><h2>Kako čitati brojke</h2>
<dl>
<dt>Držanje (kupi i drži)</dt><dd>Kupiš na početku i ne diraš. Primjer: 1.000 EUR u dionicu koja se utrostruči postane 3.000 EUR. Svako pravilo mora biti bolje od ovoga da bi imalo smisla.</dd>
<dt>Sharpe</dt><dd>Koliko si dobio za svaku jedinicu treskanja cijene. Primjer: dva vozača stignu u isto vrijeme, ali jedan vozi mirno, a drugi trzajući; mirniji ima veći Sharpe. Oko 1 je dobro.</dd>
<dt>Najgori pad od vrha (drawdown)</dt><dd>Najveći pad od najboljeg trenutka do najgoreg. Primjer: 2.000 EUR padne na 1.200 EUR, to je -40 %, odnosno 400 EUR gubitka na svakih 1.000 EUR s vrha.</dd>
<dt>Deflated Sharpe</dt><dd>Sharpe korigiran za to da smo isprobali puno kombinacija (K = {k}). Kad izabereš najbolju od puno loto kombinacija, ona izgleda dobro i slučajno. Najviši iznos među pobjednicima je {num_hr(max_dsr, 2)}, a za čvrst dokaz traži se iznad 0,95.</dd>
</dl></section>

<section><h2>1. Tablica rezultata: segment × pravilo</h2>
<figure><div class="plate"><img src="{img('ov_01_ploca.png')}" alt="Toplinska karta: prinos svakog pravila u AI eri u odnosu na držanje, po segmentima"></div>
<figcaption><b>Kako čitati:</b> zelena polja pobjeđuju držanje, crvena zaostaju. U polju je ukupni prinos 2023.-2026. i koliko puta je završna vrijednost veća ili manja od držanja. Krugom je označen pobjednik po unaprijed zadanom pravilu. Šrafirano znači manje od {D.MIN_TRADES} poslova ili gubitak uz trošak 2×. U cijeloj tablici samo su dva polja zelena: K6 u sučeljima i pohrani te K6 u mrežama i serverima. Rotacija u memoriji ima samo {ineligible_k6} poslova pa ne računa.</figcaption></figure>
{scoreboard()}
<p class="note">Poslova i Sharpe su na razini segmenta. 1.000 EUR je po dionici (jednaka težina, bez prelijevanja novca među dionicama). Tečaj EUR/USD, dividende i porezi nisu modelirani.</p></section>

<section><h2>2. Što se dogodi s 1.000 EUR</h2>
<figure><div class="plate"><img src="{img('ov_02_tisucu_eura.png')}" alt="Završna vrijednost 1.000 EUR i najgori pad: držanje, pobjednik i C13C po segmentima"></div>
<figcaption><b>Lijevo:</b> gdje završi 1.000 EUR uloženih na početku 2023. <b>Desno:</b> koliko bi iz 1.000 EUR kupljenih na samom vrhu nestalo u najgorem padu. U oblaku K5B skrati pad s {T.eur(D.worst_loss_per_1000(cl.hold))} na {T.eur(D.worst_loss_per_1000(cl.stats))}, ali završi s {T.eur(D.per_1000(cl.stats))} umjesto {T.eur(D.per_1000(cl.hold))}. To je cijena osiguranja.</figcaption></figure></section>

<section><h2>3. Kako je prošao tvoj C13C na svim dionicama</h2>
<figure><div class="plate"><img src="{img('ov_03_c13c_sve_dionice.png')}" alt="C13C minus držanje po svim dionicama: prinos i najgori pad"></div>
<figcaption><b>Lijevo:</b> razlika prinosa C13C-a i držanja u postotnim bodovima (simlog skala jer su razlike ogromne). <b>Desno:</b> razlika najgoreg pada; pozitivno znači da je C13C imao manji pad. C13C je imao manji pad na {tc['smaller_dd']} od {tc['n']} dionica, a veći prinos od držanja samo na {tc['beats_ret']} (SIMO). Veći Sharpe od držanja ima na {tc['beats_sharpe']} dionica.</figcaption></figure></section>

<section><h2>Pravila redom: tko je odradio posao</h2>
{contender_table()}
<p>K6 ima najviše pobjeda ({k6['wins']} od 6) i prosječni Sharpe {num_hr(k6['mean_sharpe'], 2)}, što je blizu držanja ({num_hr(hold_ms, 2)}) ali ne iznad. Među pravilima koja su u svih 6 segmenata zadovoljila oba uvjeta (najmanje {D.MIN_TRADES} poslova i plus uz trošak 2×) K4 ima najviši prosječni Sharpe ({num_hr(ot['K4_TSMOM_126']['mean_sharpe'], 2)}). Razlike među prva četiri pravila su male, a K je {k}, pa to nije dokaz prednosti.</p></section>

<section><h2>Što ne smiješ zaključiti</h2>
<ul>
<li>AI era je bik-tržište čipova: držanje je sjajno prošlo, pa je svako pravilo koje povremeno izlazi zaostalo.</li>
<li>Najbolja ćelija velike tablice dobra je djelomično slučajno; nijedan deflated Sharpe pobjednika nije iznad 0,95.</li>
<li>Američke pojedinačne dionice su općenito dostupne EU malim ulagačima, ali status za svaki simbol u Interactive Brokersu je <b>nepotvrđeno</b> dok ga ne provjeriš. Američki ETF-ovi (npr. SMH) često nisu dostupni (nema KID dokumenta) i ovdje se ne predstavljaju kao trgovački.</li>
<li>Nije modelirano: tečaj EUR/USD, dividende, porezi, minimalna provizija IBKR-a, razlomljene dionice (nepotvrđeno) i proklizavanje. Nema savjeta o porezu ni obećanja zarade.</li>
</ul></section>

<section><h2>Stranice po segmentima</h2>
<p class="note">Poveznice će dodati koordinator. Zamijeni svaki <code>[URL: TBD_...]</code> stvarnom adresom stranice.</p>
<!-- SEGMENT_URLS_PLACEHOLDER_START -->
<ul class="ph" id="segment-urls">{seg_list}</ul>
<!-- SEGMENT_URLS_PLACEHOLDER_END -->
</section>

<footer>Svi brojevi dolaze iz <code>summary.json</code>, <code>universe.json</code>, <code>results/*.json</code> i <code>segments/*/analysis.json</code> u mapi AICHAIN_20261014. Istraživanje, ne savjet za ulaganje; agenti ne šalju nikakve naloge. Cjelovito izvješće: <code>docs/research/AICHAIN_RESULT.md</code>.</footer>
</main>"""
    page = leg.HEAD.format(title="AI lanac: pregled", css=leg.CSS + EXTRA_CSS) + body
    path = OUT / "overview.html"
    path.write_text(page, encoding="utf-8")
    facts_json = {
        "winners": {
            s: {"id": w.contender, "sharpe": w.stats["sharpe"], "beats_hold_return": w.beats_hold_return}
            for s, w in wins.items()
        },
        "c13c_tickers": tc,
        "overall": oc,
    }
    (OUT / "overview_facts.json").write_text(json.dumps(facts_json, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(build())
