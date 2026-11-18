"""Build the Croatian per-strategy artifact pages and the overview page for the TOP10 research set.

Usage:
  .venv/bin/python scripts/top10_build_artifact.py            # all strategies that have results.json + narrative.json
  .venv/bin/python scripts/top10_build_artifact.py TOP_N1_...  # one strategy
Writes reports/research/TOP10_20261014/{ID}/artifact.html and reports/research/TOP10_20261014/overview.html.
Pages are self-contained (charts embedded as data URIs). Reads only; never places orders.
"""

import base64
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/research/TOP10_20261014"
CHARTS = [
    ("equity", "01_equity.png", "Rast ulaganja"),
    ("drawdown", "02_drawdown.png", "Najveći pad od vrha"),
    ("yearly", "03_yearly.png", "Prinos po godinama"),
    ("trades", "04_trades.png", "Ulazi i izlazi"),
    ("robustness", "05_robustness.png", "Otpornost na troškove i parametre"),
    ("exposure", "06_exposure.png", "Kada je u poziciji"),
]
RATING = {
    "ZELENO": ("Obećava", "good"),
    "ŽUTO": ("Neizvjesno", "warn"),
    "CRVENO": ("Ne drži", "bad"),
}

CSS = """
:root{--bg:#f2f5f7;--surface:#ffffff;--ink:#13202b;--muted:#566877;--line:#d8e0e6;--accent:#0b6e6e;--accent-soft:#dff0ef;
--good:#1c7c46;--good-soft:#dcf1e4;--warn:#9a6208;--warn-soft:#fbefd2;--bad:#b3302a;--bad-soft:#f9dedb;--plate:#ffffff;
--display:"Archivo","Helvetica Neue",Arial,sans-serif;--body:"Source Sans 3","Helvetica Neue",Arial,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0e161d;--surface:#16212b;--ink:#e6edf2;--muted:#9aaab7;--line:#273644;
--accent:#5fc4c0;--accent-soft:#17323a;--good:#5fd38d;--good-soft:#14301f;--warn:#e8b34d;--warn-soft:#352a12;--bad:#f08178;--bad-soft:#3a1a18;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e161d;--surface:#16212b;--ink:#e6edf2;--muted:#9aaab7;--line:#273644;
--accent:#5fc4c0;--accent-soft:#17323a;--good:#5fd38d;--good-soft:#14301f;--warn:#e8b34d;--warn-soft:#352a12;--bad:#f08178;--bad-soft:#3a1a18;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:17px;line-height:1.6;margin:0;
padding-block:32px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
main{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:36px}
h1,h2,h3{font-family:var(--display);line-height:1.15;margin:0;text-wrap:balance}
h1{font-size:clamp(2rem,6vw,3rem);font-weight:700;letter-spacing:-.01em}
h2{font-size:1.5rem;font-weight:700;margin-bottom:12px}
h3{font-size:1.05rem;font-weight:700;margin-bottom:6px}
p{margin:0 0 12px;max-width:68ch}
.tag{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.lead{font-size:1.2rem;color:var(--muted);max-width:60ch}
header{display:flex;flex-direction:column;gap:12px}
.badge-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.badge{font-family:var(--display);font-weight:700;padding:6px 14px;border-radius:999px;font-size:.95rem}
.badge.good{background:var(--good-soft);color:var(--good)}.badge.warn{background:var(--warn-soft);color:var(--warn)}.badge.bad{background:var(--bad-soft);color:var(--bad)}
.note{font-size:.92rem;color:var(--muted)}
.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.fact{background:var(--surface);padding:14px 16px;min-width:0}
.fact b{display:block;font-family:var(--mono);font-size:1.4rem;font-weight:500;font-variant-numeric:tabular-nums}
.fact span{font-size:.85rem;color:var(--muted)}
.fact .pos{color:var(--good)}.fact .neg{color:var(--bad)}
@media (max-width:520px){.facts{grid-template-columns:repeat(2,1fr)}}
section{display:block}
ol.steps{padding-left:1.4em;margin:0 0 12px}ol.steps li{margin-bottom:6px;max-width:66ch}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}
.cols>div{min-width:0;border-top:3px solid var(--accent);padding-top:10px}
.cols>div.risk{border-top-color:var(--bad)}
figure{margin:0 0 28px}
.plate{background:var(--plate);border:1px solid var(--line);border-radius:6px;padding:8px}
.plate img{display:block;width:100%;height:auto}
figcaption{font-size:.95rem;color:var(--muted);margin-top:8px;max-width:68ch}
figcaption b{color:var(--ink)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.95rem;font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{font-family:var(--display);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}
.verdict{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;padding:16px 18px}
.critic{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:18px 20px}
.critic h2,.critic h3{margin-top:8px}.critic ul{padding-left:1.3em}
dl{margin:0;display:grid;gap:12px}dt{font-weight:700}dd{margin:0;color:var(--muted);max-width:66ch}
details{border:1px solid var(--line);border-radius:6px;background:var(--surface)}
summary{cursor:pointer;padding:12px 16px;font-family:var(--display);font-weight:600}
summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
pre{margin:0;padding:14px 16px;overflow-x:auto;font-family:var(--mono);font-size:.8rem;line-height:1.5;border-top:1px solid var(--line)}
footer{font-size:.88rem;color:var(--muted);border-top:1px solid var(--line);padding-top:16px}
a{color:var(--accent)}
.pill{font-family:var(--mono);font-size:.75rem;padding:2px 8px;border-radius:4px;background:var(--accent-soft);color:var(--accent)}
.grid-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-width:0;text-decoration:none;color:inherit}
.card:hover{border-color:var(--accent)}
"""

HEAD = (
    '<meta name="claude:viewport-fit-sides" content="cover">\n<title>{title}</title>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500'
    '&family=Source+Sans+3:wght@400;600&display=swap">\n<style>{css}</style>\n'
)


def e(text):
    return html.escape(str(text if text is not None else ""))


def pct(x, digits=0, sign=False):
    if x is None:
        return "–"
    s = f"{x * 100:+.{digits}f}" if sign else f"{x * 100:.{digits}f}"
    return s.replace(".", ",") + " %"


def num(x, digits=2):
    return "–" if x is None else f"{x:.{digits}f}".replace(".", ",")


EU_NOTE = {
    "GLD": "zlato (ETF)",
    "SLV": "srebro (ETF)",
    "SPY": "indeks S&P 500 (ETF)",
    "QQQ": "Nasdaq 100 (ETF)",
    "SMH": "poluvodiči (ETF)",
    "IBIT": "bitcoin (ETF)",
    "ETHA": "ethereum (ETF)",
    "UUP": "dolar (ETF)",
    "TLT": "obveznice (ETF)",
    "SOXL": "poluvodiči s polugom (ETF)",
}


def eu_block(universe):
    """Plain-language EU availability note for the instruments a strategy uses."""
    etfs = [f"{t} ({EU_NOTE[t]})" for t in universe if t in EU_NOTE]
    crypto = [t for t in universe if t.endswith(("USD", "USDT"))]
    parts = []
    if etfs:
        parts.append(
            "Američki ETF-ovi koje ovo pravilo koristi ("
            + ", ".join(etfs)
            + ") često nisu dostupni malim ulagačima iz EU, jer nemaju KID dokument. "
            "Za trgovanje iz Hrvatske traži se europski ekvivalent (UCITS ETF ili ETC na europskoj burzi) i provjerava u Interactive Brokersu. "
            "Cijene su slične, ali nisu iste, pa pravilo treba ponovno testirati na ekvivalentu."
        )
    if crypto:
        parts.append(
            "Kripto ("
            + ", ".join(crypto)
            + "): ponuda u Interactive Brokersu ovisi o državi i propisima (MiCA). "
            "Ako izravan kripto nije dostupan, postoje kripto ETP-ovi na europskim burzama. Provjeri prije nego što ovo pravilo primijeniš."
        )
    if not parts:
        parts.append(
            "Instrumenti su američke dionice, koje su dostupne klijentima iz EU preko Interactive Brokersa. Cijene su u dolarima, račun je u eurima, "
            "pa tečaj eura i trošak konverzije utječu na stvarni rezultat."
        )
    return "".join(f"<p>{e(p)}</p>" for p in parts)


GLOSSARY = [
    (
        "Kupi i drži",
        "Kupiš i ne diraš. Primjer: kupiš dionice za 1.000 € i držiš ih deset godina, bez ikakvog trgovanja. Služi kao mjerilo: strategija ima smisla samo ako je bolja od ovoga.",
    ),
    (
        "Pokretni prosjek i trend",
        "Prosjek cijene zadnjih nekoliko dana, pa se vidi smjer. Primjer: prosjek zadnjih 100 dana je 80 $, a cijena je 90 $. Cijena je iznad prosjeka, pa kažemo da je trend uzlazni, kao kad se penješ uzbrdo.",
    ),
    (
        "Proboj",
        "Cijena prvi put nadmaši najvišu cijenu iz zadnjih nekoliko tjedana. Primjer: 55 dana najviše je bilo 100 $, danas je 101 $. To je proboj, kao kad trkač prvi put prijeđe crtu cilja.",
    ),
    (
        "Pomični stop",
        "Zaštita koja ide gore s cijenom, a nikad dolje. Primjer: kupiš po 100 $ i stop držiš 10 % ispod vrha. Cijena ode na 130 $, stop je na 117 $. Ako padne na 117 $, izlaziš s dobitkom od oko 17 %.",
    ),
    (
        "Pad od vrha (drawdown)",
        "Koliko vrijednost padne od svog najboljeg trenutka do najgoreg. Primjer: imaš 1.000 €, naraste na 2.000 €, pa padne na 1.200 €. Pad od vrha je 40 %. Pitanje je jesi li to spreman izdržati bez da paničareći prodaš.",
    ),
    (
        "Sharpe",
        "Koliko dobiti dobiješ za svaku jedinicu nemira (kolebanja). Primjer: dva vozača stignu u isto vrijeme, ali jedan je vozio mirno, a drugi trzajući. Mirniji ima veći Sharpe. Oko 1 je dobro, ispod 0,5 slabo.",
    ),
    (
        "Uzorak (IS), provjera (WF), ispit (HO)",
        "Podatke dijelimo kao školu. Uzorak je gradivo iz kojeg učimo, provjera je vježbeni test, ispit je zadnji dio koji se gleda jednom. Ako strategija prođe samo gradivo, a pada na ispitu, nije naučila ništa korisno.",
    ),
    (
        "Troškovi i bazni bod",
        "Svaka kupnja i prodaja nešto košta. Bazni bod je stoti dio postotka. Primjer: 5 baznih bodova je 0,05 %, pa za 1.000 € kupnje i prodaje platiš oko 0,50 €. Kod čestog trgovanja to se skupi.",
    ),
    (
        "Gledanje u budućnost (lookahead)",
        "Pogreška kad test slučajno koristi podatak koji u tom trenutku još nije postojao. Kao da pišeš ispit s već poznatim rješenjima. Zato svako pravilo provjeravamo tako da mu skratimo podatke i vidimo mijenja li se odluka.",
    ),
    (
        "Prilagođeno podacima (overfitting)",
        "Pravilo je namješteno da savršeno pogodi prošlost, ali ne zna ništa o budućnosti. Kao učenik koji napamet nauči pitanja s prošlog roka. Zato mijenjamo postavke za 20 % i gledamo hoće li rezultat ostati sličan.",
    ),
    (
        "Broj pokušaja (K) i deflated Sharpe",
        "Što više strategija isprobaš, to je veća šansa da jedna izgleda dobro čistom srećom. Kad 500 puta baciš novčić, negdje će pasti osam glava zaredom. Deflated Sharpe zato traži veći rezultat kad je pokušaja više.",
    ),
    (
        "PBO i PSR",
        "PBO je vjerojatnost da je najbolja varijanta u uzorku zapravo srećom najbolja (niže je bolje). PSR je vjerojatnost da je pravi Sharpe iznad nule (više je bolje). Oba su provjere je li rezultat slučajnost.",
    ),
    (
        "AI era",
        "Razdoblje od 2023. nadalje, kad je AI revolucija promijenila tržište. Prije toga je bio drugačiji svijet, zato se rezultat prosuđuje po ovom razdoblju, a stariji podaci služe kao kontekst.",
    ),
    (
        "Gotovina (izloženost)",
        "Kad strategija nije u dionicama, novac stoji u gotovini. Primjer: u poziciji je 60 % vremena, 40 % čeka. Manje izloženosti znači manje padova, ali i propuštene rastove.",
    ),
]


def md_to_html(text):
    lines, out, in_list = text.splitlines(), [], False

    def inline(s):
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e(s))

    for line in lines:
        stripped = line.strip()
        item = re.match(r"^([-*]|\d+\.)\s+(.*)", stripped)
        if item:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(item.group(2))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if not stripped:
            continue
        head = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if head:
            out.append(f"<h3>{inline(head.group(2))}</h3>")
        else:
            out.append(f"<p>{inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def img(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def split_row(label, s, b):
    if not s:
        return ""
    bench = (
        f"<td>{pct(b['total'], 0, True)}</td><td>{num(b['sharpe'])}</td><td>{pct(b['maxdd'], 0)}</td>"
        if b
        else "<td>–</td><td>–</td><td>–</td>"
    )
    return f"<tr><td>{e(label)}</td><td>{pct(s['total'], 0, True)}</td><td>{num(s['sharpe'])}</td><td>{pct(s['maxdd'], 0)}</td>{bench}</tr>"


def build_strategy(folder):
    res = json.loads((folder / "results.json").read_text())
    nar = json.loads((folder / "narrative.json").read_text())
    critic_md = (
        (folder / "critic.md").read_text() if (folder / "critic.md").exists() else ""
    )
    rating = res["rating"]
    label, tone = RATING.get(rating, (rating, "warn"))
    ai, pre = res["eras"]["ai_era"], res["eras"]["pre_ai"]
    bai = res["eras"]["benchmark_ai_era"]
    kind = res["split_kind"]
    periods = {
        "equity": ("2016–2020", "2021–2023", "2024–2026"),
        "crypto": ("2021–2022", "2023–2024", "2025–2026"),
    }[kind]
    pine = ROOT / f"scripts/tradingview/{res['id']}.pine"
    figs = []
    for key, fname, title in CHARTS:
        f = folder / fname
        if f.exists():
            figs.append(
                f'<figure><div class="plate"><img src="{img(f)}" alt="{e(title)}"></div>'
                f"<figcaption><b>{e(title)}.</b> {e(nar['kako_citati_grafove'].get(key, ''))}</figcaption></figure>"
            )
    facts = [
        (
            pct(ai["total"], 0, True),
            "prinos u AI eri (2023.–2026.)",
            "pos" if ai["total"] > 0 else "neg",
        ),
        (
            pct(bai["total"], 0, True) if bai else "–",
            "kupi i drži u istom razdoblju",
            "",
        ),
        (num(ai["sharpe"]), "Sharpe u AI eri (veći je bolji)", ""),
        (pct(ai["maxdd"], 0), "najveći pad od vrha", "neg"),
        (str(res["trades"]["n"]), "trgovina ukupno", ""),
        (pct(res["exposure"], 0), "vremena u poziciji", ""),
    ]
    facts_html = "".join(
        f'<div class="fact"><b class="{c}">{v}</b><span>{e(t)}</span></div>'
        for v, t, c in facts
    )
    rows = "".join(
        [
            split_row(
                f"Uzorak (IS) {periods[0]}",
                res["splits"].get("IS"),
                res["benchmark_splits"].get("IS"),
            ),
            split_row(
                f"Walk-forward (WF) {periods[1]}",
                res["splits"].get("WF"),
                res["benchmark_splits"].get("WF"),
            ),
            split_row(
                f"Holdout (HO) {periods[2]}",
                res["splits"].get("HO"),
                res["benchmark_splits"].get("HO"),
            ),
            split_row(
                "Prije 2023. (stari režim)", pre, res["eras"].get("benchmark_pre_ai")
            ),
            split_row("AI era 2023.–2026.", ai, bai),
        ]
    )
    cs, sens = res["cost_stress"], res["sensitivity"]
    stats = [
        (
            "Uz dvostruke troškove, prinos u AI eri",
            pct(cs["2x"]["wf_ho_total"], 0, True),
        ),
        (
            "Uz trostruke troškove, prinos u AI eri",
            pct(cs["3x"]["wf_ho_total"], 0, True),
        ),
        (
            "Sharpe s parametrima −20 % / +20 %",
            f"{num(sens.get('minus20'))} / {num(sens.get('plus20'))}",
        ),
        (
            "Vjerojatnost prilagođenosti (PBO)",
            pct(res.get("pbo"), 0) if res.get("pbo") is not None else "nije izračunato",
        ),
        ("Vjerojatnost pravog Sharpea (PSR, AI era)", pct(res.get("psr_ai_era"), 0)),
        (
            "Deflated Sharpe uz K = " + str(res["k"]),
            pct(res.get("deflated_sharpe_prob"), 0),
        ),
    ]
    stats_html = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in stats)
    flags = "".join(f"<li>{e(f)}</li>" for f in res.get("flags", []))
    steps = "".join(f"<li>{e(s)}</li>" for s in nar["kako_trguje"])
    gloss = "".join(
        f"<div><dt>{e(g['pojam'])}</dt><dd>{e(g['objasnjenje'])}</dd></div>"
        for g in nar.get("pojmovnik", [])
    )
    gloss_all = "".join(
        f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in GLOSSARY
    )
    pine_html = ""
    if pine.exists():
        pine_html = (
            f"<section><h2>Pine skripta za TradingView</h2><p>Replika pravila za učenje i vizualni backtest. "
            f'Datoteka: <span class="pill">scripts/tradingview/{e(res["id"])}.pine</span></p>'
            f"<details><summary>Prikaži kod</summary><pre>{e(pine.read_text())}</pre></details></section>"
        )
    data_rng = ", ".join(
        f"{t} {a[:4]}–{b[:4]}" for t, (a, b) in res["data_range"].items()
    )
    body = f"""<main>
<header><span class="tag">{e(res["id"])} · istraživačka simulacija</span>
<h1>{e(nar["naslov"])}</h1><p class="lead">{e(nar["podnaslov"])}</p>
<div class="badge-row"><span class="badge {tone}">{e(label)}</span>
<span class="note">Ocjena blagog kritičara, temeljena na AI eri (od 2023.). Nije formalni Critic PASS laboratorija.</span></div></header>
<div class="facts">{facts_html}</div>
<section><h2>Ideja</h2><p>{e(nar["ideja"])}</p></section>
<section><h2>Kako trguje</h2><ol class="steps">{steps}</ol><h3>Primjer</h3><p>{e(nar["primjer"])}</p></section>
<section class="cols"><div><h3>Zašto bi mogla raditi</h3><p>{e(nar["zasto_bi_mogla_raditi"])}</p></div>
<div class="risk"><h3>Zašto bi mogla zakazati</h3><p>{e(nar["zasto_bi_mogla_zakazati"])}</p></div></section>
<section><h2>Grafovi</h2>{"".join(figs)}</section>
<section><h2>Brojke po razdobljima</h2><div class="table-wrap"><table><thead><tr><th>Razdoblje</th><th>Prinos</th><th>Sharpe</th><th>Najveći pad</th>
<th>Kupi i drži</th><th>Sharpe</th><th>Najveći pad</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="note">Prva tri stupca su strategija nakon troškova, zadnja tri su kupnja i držanje istih instrumenata. Podaci: {e(data_rng)}.</p></section>
<section><h2>Otpornost</h2><div class="table-wrap"><table><tbody>{stats_html}</tbody></table></div>
{('<h3 style="margin-top:14px">Upozorenja kritičara</h3><ul>' + flags + "</ul>") if flags else ""}</section>
<section class="critic"><h2>Mišljenje kritičara</h2>{md_to_html(critic_md) if critic_md else "<p>Kritika još nije napisana.</p>"}</section>
<section><h2>Pojmovnik za ovu strategiju</h2><dl>{gloss}</dl></section>
<section><h2>Rječnik trgovanja, laički, s primjerima</h2><dl>{gloss_all}</dl></section>
<section><h2>Može li se ovo trgovati iz Hrvatske?</h2>{eu_block(res["universe"])}</section>
{pine_html}
<section class="verdict"><h3>Zaključak</h3><p>{e(nar["verdikt"])}</p></section>
<footer>Simulacija na povijesnim podacima: odluka na zatvaranju, kupnja na idućem otvaranju, troškovi 5 baznih bodova za dionice i ETF-ove,
20 za kripto, bez poluge i bez kratke prodaje. Rezultati u prošlosti ne obećavaju buduće. Ovo je istraživanje, ne savjet za ulaganje,
i nijedan nalog nije poslan. Pravilo je zamrznuto u <span class="pill">{e(res["freeze_file"])}</span>.</footer>
</main>"""
    page = HEAD.format(title=e(nar["naslov"]), css=CSS) + body
    (folder / "artifact.html").write_text(page)
    return {
        "id": res["id"],
        "title": nar["naslov"],
        "subtitle": nar["podnaslov"],
        "rating": rating,
        "tone": tone,
        "label": label,
        "ai_total": ai["total"],
        "ai_sharpe": ai["sharpe"],
        "bench_total": bai["total"] if bai else None,
        "maxdd": ai["maxdd"],
        "trades": res["trades"]["n"],
        "tf": res.get("split_kind"),
    }


def build_overview(cards, urls):
    order = {"ZELENO": 0, "ŽUTO": 1, "CRVENO": 2}
    cards = sorted(
        cards, key=lambda c: (order.get(c["rating"], 3), -(c["ai_sharpe"] or 0))
    )
    items = []
    for c in cards:
        href = urls.get(c["id"])
        tag = "a" if href else "div"
        attr = f' href="{e(href)}" target="_blank" rel="noopener"' if href else ""
        items.append(
            f'<{tag} class="card"{attr}><span class="tag">{e(c["id"])}</span><h3>{e(c["title"])}</h3>'
            f'<span class="badge {c["tone"]}" style="align-self:flex-start">{e(c["label"])}</span>'
            f'<p class="note" style="margin:0">{e(c["subtitle"])}</p>'
            f'<p class="note" style="margin:0">AI era: <b>{pct(c["ai_total"], 0, True)}</b> (kupi i drži {pct(c["bench_total"], 0, True)}) · '
            f"Sharpe {num(c['ai_sharpe'])} · pad {pct(c['maxdd'], 0)} · {c['trades']} trgovina</p></{tag}>"
        )
    body = f"""<main><header><span class="tag">Memory Lab · 14. 10. 2026.</span><h1>Deset algoritamskih strategija</h1>
<p class="lead">Pet novih hipoteza i pet klasika, na istim podacima, istim troškovima i istom blagom kritičaru. Poredak ide po ocjeni, pa po Sharpeu u AI eri.</p>
<p class="note">Sve su istraživačke simulacije. Nijedna nije formalni Critic PASS i nijedan nalog nije poslan. Tržišni režim se promijenio nakon 2022., zato najviše vrijedi razdoblje od 2023.</p></header>
<section class="grid-cards">{"".join(items)}</section></main>"""
    (OUT / "overview.html").write_text(
        HEAD.format(title="Deset strategija", css=CSS) + body
    )


def main():
    wanted = sys.argv[1:]
    cards = []
    for folder in sorted(p for p in OUT.iterdir() if p.is_dir()):
        if wanted and folder.name not in wanted:
            continue
        if (folder / "results.json").exists() and (folder / "narrative.json").exists():
            cards.append(build_strategy(folder))
            print("built", folder.name)
    urls_file = OUT / "artifact_urls.json"
    urls = json.loads(urls_file.read_text()) if urls_file.exists() else {}
    if cards and not wanted:
        build_overview(cards, urls)
        print("built overview")


if __name__ == "__main__":
    main()
