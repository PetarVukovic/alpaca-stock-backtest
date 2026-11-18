"""Build the self-contained Croatian artifact page for the AI-chain segment network_servers (research only, no orders).

Usage:
  .venv/bin/python scripts/aichain_page_netsrv.py [--no-charts] [--verify-only]

Reads segments/network_servers/analysis.json, profile.json, results/network_servers.json and results/{TICKER}.json,
draws the notebook charts through lab.aichain.page_charts and writes segments/network_servers/artifact.html with every
PNG embedded as a data URI. CSS, glossary and EU block are imported from scripts/top10_build_artifact.py (never edited).
This file has its own name because scripts/aichain_build_page.py is written by another worker.
"""

from __future__ import annotations

import base64
import html
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab.aichain.page_charts import Data, main as draw_charts  # noqa: E402
from lab.aichain.sim import load_bars  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "top10_build_artifact", ROOT / "scripts" / "top10_build_artifact.py"
)
assert _spec is not None and _spec.loader is not None
T10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T10)

SEGMENT = "network_servers"
NAMES = {
    "B0_BUYHOLD": "Kupi i drži (mjerilo)",
    "K1_C13C_ORIG": "C13C original (tvoj algoritam)",
    "K2_SMA200_TREND": "Trend: iznad SMA200",
    "K3_DONCHIAN_55_20": "Proboj 55/20 (Donchian)",
    "K4_TSMOM_126": "Vremenski momentum 126 dana",
    "K5_SUPPORT_RESISTANCE": "Potpora/otpor (odskok)",
    "K5B_SR_BREAKOUT_RETEST": "Proboj otpora i povratni test",
    "K6_MOMENTUM_CS": "Rotacija momentuma (samo segment)",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C plus ponovni ulaz (nova hipoteza)",
}
RULES_PLAIN = {
    "B0_BUYHOLD": "Kupiš na prvi dan i ne diraš ništa do kraja. Ovo je mjerilo: svako pravilo mora biti bolje od ovoga da bi imalo smisla.",
    "K1_C13C_ORIG": "Tvoj algoritam. Kupi nakon pada od 5 % ili više u 5 dana, ali samo dok je cijena iznad dugoročnog prosjeka (SMA200). Zaštita je stop 10 % ispod najvišeg vrha, koji se samo diže.",
    "K2_SMA200_TREND": "Drži dok je cijena iznad SMA200, izađi kad padne ispod.",
    "K3_DONCHIAN_55_20": "Kupi kad cijena prvi put nadmaši najviše iz zadnjih 55 dana, izađi kad padne ispod najnižeg iz zadnjih 20 dana.",
    "K4_TSMOM_126": "Drži dok je prinos zadnjih 126 dana (otprilike šest mjeseci) pozitivan.",
    "K5_SUPPORT_RESISTANCE": "Kupi kad cijena dotakne zadnje dno (potporu) i odskoči; stop 3 % ispod dna, cilj je zadnji vrh.",
    "K5B_SR_BREAKOUT_RETEST": "Kupi kad cijena probije stari vrh, pa se vrati do njega i drži; stop 3 % ispod razine.",
    "K6_MOMENTUM_CS": "Radi samo na cijeloj skupini: svakog prvog u mjesecu poredaš osam dionica po prinosu zadnjih šest mjeseci i držiš bolju polovicu; dionice s negativnim prinosom zamijeniš gotovinom.",
    "K7_C13C_PLUS_TREND_REENTRY": "Nova hipoteza: kao C13C, ali kad stop izbije, ponovno uđe čim je cijena iznad SMA200 i iznad prosjeka zadnjih 20 dana.",
}
RATING = {
    "zeleno": ("dokaz valjan", "good"),
    "žuto": ("dokaz nepotpun", "warn"),
    "crveno": ("dokaz nevaljan", "bad"),
}
CHAR_FIX = {"vracanju": "vraćanju", "slucajnog": "slučajnog"}

EXTRA_CSS = """
.teacher{background:var(--surface);border:1px dashed var(--bad);border-radius:6px;padding:12px 16px;color:var(--ink)}
.teacher b{color:var(--bad)}
.lead-verdict{font-family:var(--display);font-size:clamp(1.15rem,3.4vw,1.5rem);line-height:1.4;font-weight:600;max-width:62ch;margin:0}
.facts.six{grid-template-columns:repeat(3,1fr)}
@media (max-width:520px){.facts.six{grid-template-columns:repeat(2,1fr)}}
.tcard{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px 18px;display:flex;flex-direction:column;gap:8px;min-width:0}
.tcard h3{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.tcard p{margin:0;max-width:none}
.tcard .src{font-size:.88rem;color:var(--muted)}
.tcard ul{margin:0;padding-left:1.2em}.tcard li{margin-bottom:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}
.tag-warn{font-size:.88rem;color:var(--warn);background:var(--warn-soft);border-radius:4px;padding:4px 8px}
.unconf{font-family:var(--mono);font-size:.78rem;background:var(--warn-soft);color:var(--warn);padding:1px 6px;border-radius:4px;white-space:nowrap}
.plate{background:#fffef9}
details.rule{margin-bottom:8px}
td.l,th.l{text-align:left}
table.wrap td{white-space:normal;text-align:left}
nav.toc{display:flex;flex-wrap:wrap;gap:8px 14px;font-size:.92rem}
"""


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def n(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def eur(x: float) -> str:
    return f"{x:,.0f} EUR".replace(",", ".")


def pc(x: float, nd: int = 1, sign: bool = False) -> str:
    return (n(x, nd) if not sign else (("+" if x >= 0 else "") + n(x, nd))) + " %"


def dh(iso: str) -> str:
    y, m, d = str(iso)[:10].split("-")
    return f"{int(d)}. {int(m)}. {y}."


def img_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def fig(out: Path, fname: str, alt: str, caption: str) -> str:
    return (
        f'<figure><div class="plate"><img src="{img_uri(out / fname)}" alt="{e(alt)}" loading="lazy"></div>'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def demo_trade(d: Data) -> dict[str, Any]:
    """Real LITE trade used as the step-by-step C13C example (numbers computed from prices and the trade list)."""
    t = "LITE"
    tr = next(x for x in d.tk_trades(t) if x["entry_date"] == "2024-10-22")
    bars = load_bars(t)
    close = pd.Series(bars.close, index=bars.dates)
    high = pd.Series(bars.high, index=bars.dates)
    sma = close.rolling(200).mean()
    ei = close.index.get_loc(pd.Timestamp(tr["entry_date"]))
    sig = ei - 1
    peak = max(tr["raw_entry"], float(high.iloc[ei]))
    return {
        "ticker": t,
        "signal_date": str(close.index[sig].date()),
        "signal_close": float(close.iloc[sig]),
        "close_5_before": float(close.iloc[sig - 5]),
        "dip": float(close.iloc[sig] / close.iloc[sig - 5] - 1),
        "sma200": float(sma.iloc[sig]),
        "entry_date": tr["entry_date"],
        "entry": tr["raw_entry"],
        "stop0": round(peak * 0.9, 2),
        "exit_date": tr["exit_date"],
        "exit": tr["raw_exit"],
        "ret": tr["return"],
        "bars": tr["bars_held"],
    }


def build(redraw: bool = True) -> Path:
    import json

    d = Data(SEGMENT)
    out = d.out
    if redraw:
        draw_charts(SEGMENT)
    A = d.analysis
    prof = json.loads((out / "profile.json").read_text())
    seg_tbl = A["tablica_segmenta_jednak_kapital_AI_era"]["suparnici"]
    tk_tbl = A["tablica_po_dionici_AI_era"]
    win = A["tko_je_najbolje_odradio_posao"]
    win_id = win["pobjednik"]
    hold, k1, k6 = seg_tbl["B0_BUYHOLD"], seg_tbl["K1_C13C_ORIG"], seg_tbl[win_id]
    n_t = len(d.tickers)
    ex = demo_trade(d)
    k1w = d.win("K1_C13C_ORIG")
    start_iso, end_iso = d.win("B0_BUYHOLD")["start"], d.win("B0_BUYHOLD")["end"]
    period = f"{dh(start_iso)} do {dh(end_iso)}"
    ledger_k = A["ocjene"]["napomena_nije_critic"].split("K=")[-1].split(".")[0].strip()

    verdict = (
        f"Najbolje je posao odradila rotacija momentuma (pravilo K6) i pobijedila običnu kupnju i držanje: "
        f"1.000 EUR podijeljenih na osam dionica postalo je {eur(k6['za_1000_EUR_na_kraju'])} naspram "
        f"{eur(hold['za_1000_EUR_na_kraju'])}, ali uz dublji najgori gubitak ({eur(k6['za_1000_EUR_najgori_pad_EUR'])} naspram "
        f"{eur(hold['za_1000_EUR_najgori_pad_EUR'])}). Tvoj C13C završio je na {eur(k1['za_1000_EUR_na_kraju'])}, nije pobijedio držanje "
        f"ni na jednoj od {n_t} dionica, ali je najgori gubitak skratio na {eur(k1['za_1000_EUR_najgori_pad_EUR'])}."
    )
    facts = [
        (eur(hold["za_1000_EUR_na_kraju"]), "kupi i drži: što je ostalo od 1.000 EUR", ""),
        (eur(k1["za_1000_EUR_na_kraju"]), "C13C: što je ostalo od 1.000 EUR", ""),
        (eur(k6["za_1000_EUR_na_kraju"]), "rotacija momentuma: od 1.000 EUR", "pos"),
        (eur(hold["za_1000_EUR_najgori_pad_EUR"]), "najgori gubitak držanja", "neg"),
        (eur(k1["za_1000_EUR_najgori_pad_EUR"]), "najgori gubitak C13C-a", "neg"),
        (eur(k6["za_1000_EUR_najgori_pad_EUR"]), "najgori gubitak pobjednika", "neg"),
    ]
    facts_html = "".join(
        f'<div class="fact"><b class="{c}">{e(v)}</b><span>{e(t)}</span></div>' for v, t, c in facts
    )

    ocj = A["ocjene"]["po_suparniku"]
    rows = []
    for k, v in seg_tbl.items():
        rt = ocj.get(k)
        badge = (
            f'<span class="badge {RATING[rt["ocjena"]][1]}" style="font-size:.78rem;padding:2px 10px">{RATING[rt["ocjena"]][0]}</span>'
            if rt
            else '<span class="pill">mjerilo</span>'
        )
        cls = ' style="font-weight:700"' if k == win_id else ""
        rows.append(
            f"<tr{cls}><td class='l'>{e(NAMES[k])}</td><td>{eur(v['za_1000_EUR_na_kraju'])}</td><td>{pc(v['povrat_ukupno_pct'], 0, True)}</td>"
            f"<td>{n(v['sharpe'], 2)}</td><td>{pc(v['max_pad_pct'], 1)}</td><td>{eur(v['za_1000_EUR_najgori_pad_EUR'])}</td>"
            f"<td>{v['broj_poslova']}</td><td>{pc(v['povrat_trosak_2x_pct'], 0, True)}</td><td>{pc(v['povrat_trosak_3x_pct'], 0, True)}</td>"
            f"<td>{n(v['deflated_sharpe_vjerojatnost'], 2)}</td><td>{badge}</td></tr>"
        )
    contenders_table = (
        '<div class="table-wrap"><table><thead><tr><th class="l">Pravilo</th><th>1.000 EUR na kraju</th><th>Povrat</th><th>Sharpe</th>'
        "<th>Najveći pad</th><th>Najgori gubitak na 1.000 EUR</th><th>Poslova</th><th>Povrat uz trošak 2x</th><th>Povrat uz trošak 3x</th>"
        f'<th>Deflated Sharpe vjerojatnost</th><th>Ocjena dokaza</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )
    rules_html = "".join(
        f"<details class='rule'><summary>{e(NAMES[k])}</summary><p style='padding:0 16px 12px'>{e(RULES_PLAIN[k])}</p></details>"
        for k in seg_tbl
    )

    trows = []
    for t in d.tickers:
        s = tk_tbl[t]["suparnici"]
        cands = {k: v for k, v in s.items() if k != "B0_BUYHOLD"}
        best = max(cands, key=lambda k: cands[k]["sharpe"])
        b, h, c = cands[best], s["B0_BUYHOLD"], s["K1_C13C_ORIG"]
        beat = [NAMES[k].split(" (")[0] for k, v in cands.items() if v["bolji_povrat_od_drzanja"]]
        trows.append(
            f"<tr><td class='l'><b>{t}</b><br><span class='note'>od {dh(tk_tbl[t]['od'])}</span></td>"
            f"<td>{eur(h['za_1000_EUR_na_kraju'])}<br><span class='note'>Sharpe {n(h['sharpe'], 2)}, pad {pc(h['max_pad_pct'], 0)}</span></td>"
            f"<td>{eur(c['za_1000_EUR_na_kraju'])}<br><span class='note'>Sharpe {n(c['sharpe'], 2)}, pad {pc(c['max_pad_pct'], 0)}</span></td>"
            f"<td>{c['broj_poslova']}</td><td>{pc(c['izlozenost_pct'], 0)}</td>"
            f"<td class='l'>{e(NAMES[best].split(' (')[0])}<br><span class='note'>Sharpe {n(b['sharpe'], 2)}, {eur(b['za_1000_EUR_na_kraju'])}</span></td>"
            f"<td class='l'>{('da: ' + e(', '.join(beat))) if beat else 'nijedno pravilo'}</td></tr>"
        )
    ticker_table = (
        '<div class="table-wrap"><table><thead><tr><th class="l">Dionica</th><th>Držanje (od 1.000 EUR)</th><th>C13C (od 1.000 EUR)</th>'
        '<th>Poslova C13C</th><th>C13C u poziciji</th><th class="l">Najviši Sharpe među pravilima</th><th class="l">Pravila s većim povratom od držanja</th></tr></thead>'
        f'<tbody>{"".join(trows)}</tbody></table></div>'
    )

    cards = []
    for t in d.tickers:
        c = A["kartice_dionica"][t]
        p, dip, w, sr, m = (
            c["ponasanje_AI_era"],
            c["nakon_pada_5d_iznad_SMA200"],
            c["najgori_padovi"][0],
            c["potpora_otpor"],
            c["mehanizam"],
        )
        ch = p["karakter"]
        for a, b in CHAR_FIX.items():
            ch = ch.replace(a, b)
        warn = f'<p class="tag-warn">{e(c["upozorenje"])}</p>' if c.get("upozorenje") else ""
        rec = dh(w["oporavak"]) if re.match(r"\d{4}-", w["oporavak"]) else w["oporavak"]
        vol = p["volatilnost_godisnja_pct"]
        gap = p["najveci_jaz"]
        cards.append(
            f"""<article class="tcard"><h3>{t} <span class="pill">{e(ch)}</span></h3>
<p class="src"><b>Što je to:</b> {e(m['sells'])} <b>Mjesto u lancu:</b> {e(m['chain_position'])} <i>({e(m['label'])})</i></p>
<ul>
<li><b>Njihanje:</b> {pc(vol, 0)} godišnje. U običnoj godini 1.000 EUR se kreće otprilike između {eur(1000 - 10 * vol)} i {eur(1000 + 10 * vol)}. Beta prema SMH {n(p['beta_SMH'], 2)} (korelacija {n(p['korelacija_SMH'], 2)}).</li>
<li><b>Dugoročni smjer:</b> zatvaranje je iznad SMA200 u {pc(p['udio_dana_iznad_SMA200_pct'], 0)} dana. Ukupni povrat u AI eri {pc(p['ukupni_povrat_pct'], 0, True)}; bez 10 najboljih dana samo {pc(p['povrat_bez_10_najboljih_dana_pct'], 0, True)}.</li>
<li><b>Nakon pada od 5 % u 5 dana:</b> {e(dip['tumacenje'])}</li>
<li><b>Najgori pad:</b> vrh {dh(w['vrh'])}, dno {dh(w['dno'])}, oporavak {e(rec)}: {pc(w['dubina_pct'], 1)}. {e(w['primjer_1000_EUR'])}.</li>
<li><b>Najveći jaz preko noći:</b> {pc(gap['gap_pct'], 1, True)} dana {dh(gap['date'])}.</li>
<li><b>Potpora i otpor:</b> {e(sr['tumacenje'])}</li>
<li><b>Koji algoritam pristaje:</b> {e(c['koji_algoritam_pristaje'])}</li>
</ul>{warn}</article>"""
        )
    cards_html = f'<div class="cards">{"".join(cards)}</div>'

    rrows = "".join(
        f"<tr><td class='l'>{e(NAMES[k])}</td><td><span class='badge {RATING[v['ocjena']][1]}' style='font-size:.78rem;padding:2px 10px'>{RATING[v['ocjena']][0]}</span></td>"
        f"<td class='l'>{e(' '.join(v['nedostaci_dokaza']) or v['obrazlozenje'])}</td></tr>"
        for k, v in ocj.items()
    )
    rating_table = f'<div class="table-wrap"><table class="wrap"><thead><tr><th class="l">Pravilo</th><th>Ocjena dokaza</th><th class="l">Što nedostaje ili je slabo</th></tr></thead><tbody>{rrows}</tbody></table></div>'

    g10 = dict(T10.GLOSSARY)
    pg = prof["glossary_hr"]
    gl = [
        ("Istraživačka simulacija", "Računalna igra na stvarnim povijesnim cijenama: pravilo 'kupuje' i 'prodaje' kao da je bilo tada. Primjer: 1.000 EUR i pravilo 'kupi nakon pada'; simulacija zbroji što bi ostalo. Nijedan nalog se ne šalje, a prošlost ne obećava budućnost."),
        ("Kupi i drži", g10["Kupi i drži"]),
        ("SMA200", pg["SMA200"] + " Primjer: prosjek zadnjih 200 zatvaranja je 50 USD, a dionica je na 60 USD: 20 % iznad prosjeka, dugoročni uzlazni smjer."),
        ("Pad od 5 % u 5 dana (signal C13C-a)", "Zatvaranje je barem 5 % niže nego prije 5 trgovačkih dana. Primjer: prije 5 dana 100 USD, danas 94 USD: pad 6 %. C13C to čita kao priliku za kupnju, ali samo ako je cijena i dalje iznad SMA200."),
        ("Stop (pomični)", g10["Pomični stop"] + " U C13C-u je stop 10 % ispod najvišeg poznatog vrha i nikad se ne spušta."),
        ("Jaz preko noći (gap)", pg["jaz (gap)"] + " Primjer: dionica zatvori na 100 USD, sutra otvori na 80 USD: -20 %. Stop na 90 USD tada ne može izaći po 90, nego po 80, pa 1.000 EUR postane 800 EUR umjesto 900 EUR."),
        ("Pad od vrha (drawdown)", g10["Pad od vrha (drawdown)"]),
        ("Najgori gubitak na 1.000 EUR", "Najveći pad iskazan u eurima. Primjer: pad od 46,4 % znači da 1.000 EUR na vrhu postane 536 EUR na dnu, dakle gubitak od 464 EUR."),
        ("Sharpe", g10["Sharpe"]),
        ("Izloženost i gotovina", g10["Gotovina (izloženost)"]),
        ("Trošak i bazni bod", "Svaka kupnja i prodaja nešto košta. Ovdje 2,5 baznih bodova po strani: bazni bod je stoti dio postotka, pa je 2,5 baznih bodova 0,025 %. Na 1.000 EUR to je 0,25 EUR pri kupnji i isto pri prodaji. Provjeravamo i dvostruki (5) i trostruki (7,5) trošak."),
        ("Rotacija momentuma", "Svaki mjesec poredaš dionice po prinosu zadnjih šest mjeseci i držiš bolju polovicu. Primjer: od osam dionica držiš četiri najbolje, svaku sa 250 EUR od 1.000 EUR, a sve s negativnim prinosom zamijeniš gotovinom."),
        ("Donchian proboj", g10["Proboj"]),
        ("Potpora i otpor", pg["potpora/otpor"] + " Primjer: dionica je dvaput odskočila s 16 USD; 16 USD je potpora. Ako je treći put probije, potpora nije izdržala."),
        ("Njihanje (volatilnost)", pg["volatilnost"]),
        ("Beta i korelacija", pg["beta"] + " " + pg["korelacija"]),
        ("SMH", "Fond (ETF) koji prati poluvodiče. Ovdje služi samo kao mjerilo za betu i korelaciju. To je američki ETF i za tebe iz EU vjerojatno nije dostupan (nema KID dokumenta): nepotvrđeno, ne predlaže se kao ulaganje."),
        ("Reverzija i trend", pg["omjer varijance (VR)"]),
        ("Neovisni događaji", pg["nezavisni događaji"]),
        ("AI era", g10["AI era"]),
        ("Broj pokušaja (K) i deflated Sharpe", g10["Broj pokušaja (K) i deflated Sharpe"] + f" Ovdje je K = {ledger_k} pokušaja; nijedan deflated Sharpe nije iznad 0,95, pa je to samo informacija."),
        ("Gledanje u budućnost (lookahead)", g10["Gledanje u budućnost (lookahead)"]),
        ("Prilagođeno podacima (overfitting)", g10["Prilagođeno podacima (overfitting)"]),
        ("Critic PASS", "Formalna provjera laboratorija koju strategija mora proći prije bilo kakvog trgovanja. Ovdje je ocjena samo blaga istraživačka i NIJE Critic PASS: lista odobrenih strategija ostaje prazna."),
    ]
    gl_html = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in gl)

    eu = A["EU_HR"]
    eu_rows = "".join(
        f"<tr><td class='l'><b>{t}</b></td><td class='l'>{e(v['vrsta'])}</td><td><span class='unconf'>nepotvrđeno</span></td><td class='l'>{e(v['napomena'])}</td></tr>"
        for t, v in eu["po_dionici"].items()
    )
    eu_html = (
        T10.eu_block(d.tickers)
        + f"<p>{e(eu['pravilo'])}</p><p>{e(eu['valuta'])}</p><p>{e(eu['porezi'])}</p>"
        '<div class="table-wrap"><table class="wrap"><thead><tr><th class="l">Dionica</th><th class="l">Vrsta</th><th>Dostupnost u IBKR-u</th><th class="l">Napomena</th></tr></thead>'
        f"<tbody>{eu_rows}</tbody></table></div>"
        "<p class='note'>Također nepotvrđeno za tvoj račun: kupnja djelomičnih dionica, minimalna provizija po nalogu (za mali nalog stvarni trošak bio bi veći od 2,5 baznih bodova) i trošak pretvorbe eura u dolare. "
        "SMH i ostali američki ETF-ovi ovdje služe samo kao mjerilo; nijedan se ne predstavlja kao dostupan.</p>"
    )

    limits = list(A["ogranicenja"]) + [
        "Tečaj eura i dolara, dividende, porezi, minimalna provizija i stvarno proklizavanje cijene nisu modelirani; za pravila s mnogo poslova (C13C, C13C plus ponovni ulaz) stvarna provizija bila bi veća od one u simulaciji.",
        "Svih osam dionica su današnji pobjednici AI vala, izabrani unatrag; to je optimističan uzorak jednako za svako pravilo i za držanje.",
        "Jedno razdoblje od oko tri i pol godine, uglavnom uzlazno tržište; test promjene postavki za 20 % gleda samo mijenja li se predznak ukupnog povrata, što je u takvom tržištu slab test.",
    ]
    limits_html = "<ul>" + "".join(f"<li>{e(x)}</li>" for x in limits) + "</ul>"

    zz = A["zasto_zajedno"]
    story_html = (
        f"<p>{e(zz['tekst'])}</p><p><b>Primjer u eurima:</b> {e(zz['primjer_1000_EUR'])}</p><ul>"
        + "".join(f"<li>{e(x)}</li>" for x in zz["razlike_unutar_grupe"])
        + f"</ul><p class='note'>{e(zz['oznaka'])}</p>"
    )
    read_win = "".join(f"<li>{e(x)}</li>" for x in win["kako_citati_pobjedu"])
    c13 = A["C13C_iskreno"]
    prem = c13["premisa_C13C_iz_profila"]
    f5, f20 = prem["brojke"]["fwd5"], prem["brojke"]["fwd20"]

    example_html = f"""<ol class="steps">
<li><b>Gledamo večernje zatvaranje.</b> {dh(ex['signal_date'])}: {ex['ticker']} je zatvorio na {n(ex['signal_close'], 2)} USD, a pet trgovačkih dana ranije na {n(ex['close_5_before'], 2)} USD. To je pad od {pc(abs(ex['dip']) * 100, 1)}, dakle barem 5 %.</li>
<li><b>Provjera dugoročnog smjera.</b> Prosjek zadnjih 200 dana (SMA200) je {n(ex['sma200'], 2)} USD, a zatvaranje je {n(ex['signal_close'], 2)} USD, dakle iznad njega. Pad u usponu: signal vrijedi.</li>
<li><b>Kupnja sutradan na otvaranju.</b> {dh(ex['entry_date'])} po {n(ex['entry'], 2)} USD (plus trošak 0,025 %). Za 1.000 EUR to je oko {n(1000 / ex['entry'], 1)} dionica (u simulaciji su dopuštene i djelomične, što je za tvoj račun nepotvrđeno).</li>
<li><b>Odmah se postavlja stop.</b> 10 % ispod najvišeg poznatog vrha: početno oko {n(ex['stop0'], 2)} USD. Kad cijena napravi novi vrh, stop se digne, nikad ne spusti.</li>
<li><b>Izlaz.</b> {dh(ex['exit_date'])} cijena je pala do stopa i prodaja je izvršena po {n(ex['exit'], 2)} USD, nakon {ex['bars']} trgovačkih dana: {pc(ex['ret'] * 100, 1, True)}. 1.000 EUR je postalo {eur(1000 * (1 + ex['ret']))}.</li>
</ol>
<p class="note">Ovo je jedan stvarni posao iz simulacije, odabran zato što dobro pokazuje korake; većina poslova nije ovako dobra (dobitnih je {n(k1w['hit_rate'] * 100, 0)} %).</p>"""

    why_html = f"""<section class="cols"><div><h3>Zašto bi ovo moglo imati smisla</h3>
<p>Pad usred uzlaznog trenda često se brzo vrati: u AI eri, kroz svih osam dionica ({f5['events']} neovisnih događaja), prosjek 20 dana nakon takvog pada je {pc(f20['mean_pct'], 1, True)} naspram {pc(f20['uncond_mean_pct'], 1, True)} za bilo koji drugi dan. Na 1.000 EUR to je razlika od oko {eur(10 * (f20['mean_pct'] - f20['uncond_mean_pct']))}. Stop je zaštita: gubitak je u pravilu ograničen na oko 10 %.</p></div>
<div class="risk"><h3>Zašto bi moglo zakazati</h3>
<p>Razlika je mala u odnosu na njihanje, a kod ANET, CRDO i HPE nakon pada je prosjek čak lošiji od običnog dana (5 dana: {pc(f5['mean_pct'], 1, True)} naspram {pc(f5['uncond_mean_pct'], 1, True)}, svih osam zajedno). Stop izbacuje iz dionice usred velikog trenda (LITE), a jaz preko noći probija stop pa gubitak bude veći od 10 %. Osim toga, C13C je u poziciji samo {n(k1w['exposure_pct'], 0)} % kapitala, pa propušta veliki dio rasta.</p></div></section>"""

    f = lambda fn, alt, cap: fig(out, fn, alt, cap)  # noqa: E731
    f_price = f("01_cijena_c13c.png", "Cijena LITE, SMCI i ANET s ulazima i izlazima C13C-a",
        "<b>Čitaj ovako.</b> Plava crta je cijena, isprekidana siva je SMA200. Zeleni trokut je kupnja, crveni je izlaz na stopu (prazan trokut: stop je bio iznad ulaza pa je posao ipak završio dobitkom). Narančasta crta je stop jednog posla: diže se za vrhom i nikad ne pada. Kod LITE vidi koliko je puta C13C izašao dok je cijena nastavljala rasti. Kod SMCI vidi pad od 84,8 % kojem je C13C izmaknuo. Kod ANET vidi da je izašao prije dna iz travnja 2025. i vratio se tek kasnije.")
    f_eq = f("02_kapital.png", "Rast 1.000 EUR: držanje, C13C i pobjednik",
        "<b>Rast novca.</b> Sve tri crte kreću od 1.000 EUR. Pobjednik je najviše, ali i najjače pada u veljači i ožujku 2025. C13C raste sporo jer je većinu vremena dijelom u gotovini, a tijekom zajedničkog pada gubi mnogo manje.")
    f_dd = f("03_pad.png", "Pad od vrha: držanje, C13C i pobjednik",
        "<b>Koliko je boljelo.</b> Što je crta niže, to je dublji pad od najboljeg trenutka. Pobjednik ide dublje od držanja (cijena koncentracije na bolju polovicu), a C13C ostaje plitak. Narančasta točka je najgori pojedinačni dan držanja.")
    f_tr = f("04_poslovi.png", "Svi poslovi C13C-a: trajanje i povrat",
        "<b>Svaki posao je jedna točka.</b> Većina poslova traje nekoliko dana i završava malim plusom ili malim minusom. Nekoliko dugih poslova nosi velik dio dobiti. Najgori posao nije bio spor pad nego jaz preko noći.")
    f_sc = f("05_ljestvica.png", "Ljestvica suparnika: EUR na kraju i Sharpe",
        "<b>Tko je ispred, a tko iza držanja.</b> Lijevo je što je ostalo od 1.000 EUR, desno Sharpe. Samo rotacija momentuma je desno od iscrtkane crte na oba grafa. C13C ima Sharpe blizu držanja, ali bitno manje eura.")
    f_co = f("06_troskovi.png", "Povrat uz trošak 1x, 2x i 3x",
        "<b>Provjera troškova.</b> Za većinu pravila stupci se jedva razlikuju, jer rijetko trguju. Najviše se smanjuje C13C plus ponovni ulaz sa 525 poslova. Troškovi ovdje ne mijenjaju poredak, ali stvarna provizija za malu narudžbu mogla bi biti veća (nepotvrđeno).")
    f_ls = f("07_pouka_osiguranje.png", "Pouka: C13C kao osiguranje",
        "<b>Ključna pouka ovog segmenta.</b> Desno: C13C je na svih osam dionica smanjio najgori gubitak. Lijevo: ni na jednoj nije zaradio više od držanja. Kod LITE je razlika golema jer je bio samo četvrtinu vremena u poziciji, a kod SMCI je osiguranje gotovo besplatno.")
    f_dip = f("08_pad_pa_povrat.png", "Prosječni povrat nakon pada u odnosu na običan dan",
        "<b>Je li pad dobra prilika?</b> Plavi stupac je prosjek nakon pada od 5 % u 5 dana (uz cijenu iznad SMA200), sivi je običan dan. Plavi iznad sivog podupire logiku C13C-a; kod ANET, CRDO i HPE (5 dana) nije tako. Blijedi stupci imaju manje od 15 događaja.")
    f_se = f("09_sezonalnost.png", "Prosječni povrat po kalendarskim mjesecima",
        "<b>Sezonski obrazac, s oprezom.</b> Svaka kućica je prosjek od samo dva do četiri mjeseca. Neke izgledaju zadivljujuće (LITE u kolovozu), ali s tako malo promatranja to može biti slučajnost. Ne koristi to kao pravilo.")
    f_an = f("10_anatomija_pada.png", "Anatomija najgoreg pada svake dionice",
        "<b>Pad ima dva dijela.</b> Crveno je padanje do dna, zeleno je čekanje da se vrati stari vrh. SMCI se do kraja podataka nije oporavio. Gledaj duljinu zelenih traka: pad se ne plaća samo dubinom, nego i čekanjem.")
    f_to = f("11_zajednicki_pad.png", "Svih osam dionica zajedno u padu 2025.",
        "<b>Jedna velika oklada, ne osam.</b> Sedam od osam dionica dotaknulo je dno u istom tjednu početkom travnja 2025. Raznolikost unutar skupine ne štiti od zajedničkog šoka. Izuzetak je SMCI, koji je imao vlastitu priču.")
    f_sr = f("12_potpora_otpor_udio.png", "Udio dodira na kojima su potpora i otpor održali",
        "<b>Drže li razine?</b> Zeleni stupac je potpora (dno), crveni otpor (vrh). Crta na 50 % je bacanje novčića. Većina stupaca je ispod crte, pa razine češće popuste nego izdrže; HPE i DELL su iznimke za potporu.")
    f_se2 = f("13_potpora_primjeri.png", "Primjeri reakcije na potporu kod HPE",
        "<b>Pogledaj stvarne dodire.</b> Točkaste crte su razine potpore. Zeleni krug: razina je izdržala. Prazni crveni krug s križićem: razina je probijena. Prikazan je izrez od 9 mjeseci s najviše dodira.")

    toc = (
        '<nav class="toc"><a href="#sto">Što je ovo</a><a href="#prica">Priča segmenta</a><a href="#pobjednik">Tko je pobijedio</a>'
        '<a href="#c13c">Tvoj C13C</a><a href="#dionice">Svaka dionica</a><a href="#ocjene">Ocjene dokaza</a><a href="#pojmovi">Pojmovnik</a>'
        '<a href="#eu">EU/HR</a><a href="#granice">Granice</a></nav>'
    )
    body = f"""<main>
<header><span class="tag">AI lanac · {e(A['naziv'])} · istraživačka simulacija</span>
<h1>{e(A['naziv'])}</h1>
<p class="lead-verdict">{verdict}</p>
<div class="badge-row"><span class="badge warn">Pobjednik: dokaz nepotpun</span><span class="badge good">C13C: dokaz valjan</span>
<span class="note">Razdoblje: {period} (AI era). Troškovi: 2,5 baznih bodova po strani. Ocjena blagog kritičara; nije formalni Critic PASS.</span></div>
{toc}</header>
<div class="facts six">{facts_html}</div>
<p class="note" style="margin-top:-18px">Svaki iznos je što bi ostalo od 1.000 EUR podijeljenih na osam dionica (po 125 EUR), simulacija na povijesnim podacima. Najgori gubitak je najveći pad od vrha, u eurima. Ovo nije savjet za ulaganje i ne obećava dobit.</p>

<section id="sto"><h2>Što je ovo</h2>
<p>Zamisli da je 3. 1. 2023. netko dao 1.000 EUR i rekao: podijeli na ovih osam dionica pa ih vodi po jednom jasnom pravilu. Mi smo to računalno odigrali na stvarnim cijenama do {dh(end_iso)}, za devet pravila odjednom, uz iste troškove, i usporedili s najjednostavnijim što postoji: kupiš i ne diraš ništa.</p>
<p>Osam dionica su američke tvrtke koje grade žice, svjetlo i kućišta oko AI čipova: preklopnici (ANET), čipovi za veze (CRDO, ALAB), optika i laseri (COHR, LITE) i gotovi serveri (SMCI, DELL, HPE). Glavno mjerilo je AI era, od 1. 1. 2023., jer se tržište nakon 2022. promijenilo; ranije godine služe samo kao kontekst.</p>
<div class="teacher"><b>Šest riječi prije nego počneš.</b>
<ul><li><b>Držanje:</b> kupiš i ne diraš. 1.000 EUR ostaje uloženo do kraja.</li>
<li><b>SMA200:</b> prosjek cijene zadnjih 200 dana; iznad njega je dionica u dugoročnom usponu.</li>
<li><b>Stop:</b> automatska prodaja ako cijena padne za dogovoreni postotak (ovdje 10 % ispod vrha).</li>
<li><b>Jaz preko noći:</b> sutrašnje otvaranje je puno niže od jučerašnjeg zatvaranja; stop tada ne može izaći po svojoj cijeni.</li>
<li><b>Sharpe:</b> koliko zarade po jedinici nemira; veći je bolji, oko 1 je dobro.</li>
<li><b>Najgori gubitak:</b> koliko bi od 1.000 EUR nestalo između najboljeg i najgoreg trenutka.</li></ul></div>
<h3 style="margin-top:20px">Kako C13C radi, korak po korak, na stvarnom poslu</h3>{example_html}
<h3>Devet pravila koja se natječu</h3>{rules_html}
<p class="note">Pobjednik je izabran po pravilu zadanom unaprijed: najviši Sharpe uz najmanje 20 poslova i pozitivan povrat uz dvostruki trošak. Odluka se donosi na zatvaranju, a kupnja se izvršava na sljedećem otvaranju (pravilo ne vidi budućnost).</p></section>

<section id="prica"><h2>Priča segmenta</h2>{story_html}{f_to}</section>

<section id="pobjednik"><h2>Tko je odradio posao najbolje</h2>
<p>{e(win['tekst'])}</p>
<div class="teacher"><b>Kako čitati pobjedu:</b><ul>{read_win}</ul></div>
<h3 style="margin-top:20px">Ljestvica svih devet pravila (cijeli segment, 1.000 EUR podijeljeno na osam dionica)</h3>{contenders_table}
<p class="note">Sve brojke su iz AI ere {period}, nakon troškova 2,5 baznih bodova po strani; stupci s 2x i 3x pokazuju stres troškova. Broj poslova rotacije ne broji djelomična rebalansiranja.</p>
{f_sc}{f_eq}{f_dd}{f_co}</section>

<section id="c13c"><h2>Tvoj C13C, iskreno</h2>
<p>{e(c13['sazetak'])}</p>
<div class="verdict"><h3>Jedna rečenica</h3><p>C13C je ovdje bio osiguranje od padova, a ne stroj za zaradu: najgori gubitak je prepolovljen ({eur(k1['za_1000_EUR_najgori_pad_EUR'])} naspram {eur(hold['za_1000_EUR_najgori_pad_EUR'])}), ali zarada je otprilike tri puta manja ({eur(k1['za_1000_EUR_na_kraju'])} naspram {eur(hold['za_1000_EUR_na_kraju'])}).</p></div>
{why_html}
{f_price}{f_tr}{f_ls}
<p class="note">{e(c13['vazno'])} {e(prem['napomena'])}</p></section>

<section id="dionice"><h2>Kako se ponaša svaka dionica</h2>
<p>Prvo pregled po dionici (AI era), pa kartice s ponašanjem. Opisi tvrtki su kontekst iz javnih izvora i nisu iz naših podataka; sve brojke ponašanja su izračunate iz dnevnih cijena.</p>
{ticker_table}
<p class="note">'Najviši Sharpe među pravilima' ne uključuje držanje ni rotaciju (ona radi samo na cijelom segmentu). Zadnji stupac pokazuje koja pravila su na toj dionici zaradila više od držanja; ALAB je uvršten tek 20. 3. 2024., pa je njegovo držanje optimistično.</p>
{cards_html}
{f_dip}{f_se}{f_an}{f_sr}{f_se2}</section>

<section id="ocjene"><h2>Ocjene dokaza (blagi kritičar)</h2>
<p>{e(A['ocjene']['pravilo'])} {e(A['ocjene']['napomena_nije_critic'])}</p>{rating_table}
<p class="note">Zeleno = dokaz valjan, žuto = dokaz nije oboren ali nedostaje ili je slabija jedna provjera, crveno = dokaz nevaljan. Nema crvenih. Ovo je istraživačka ocjena, ne Critic PASS i ne ulazi u listu odobrenih strategija.</p></section>

<section id="pojmovi"><h2>Pojmovnik, s primjerima u eurima</h2><dl>{gl_html}</dl></section>

<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>{eu_html}</section>

<section id="granice"><h2>Granice: što nije modelirano</h2>{limits_html}</section>

<footer>Istraživačka simulacija na povijesnim dnevnim cijenama ({period}); odluka na zatvaranju, kupnja na sljedećem otvaranju, trošak 2,5 baznih bodova po strani (provjereno i na 2x i 3x),
bez poluge i bez kratke prodaje, zasebna svota od 1.000 EUR po dionici, tečaj eura i dolara nije modeliran. Rezultati iz prošlosti ne obećavaju budućnost. Ovo nije savjet za ulaganje,
nijedan nalog nije poslan, a nijedno pravilo nije dobilo formalni Critic PASS. Status revizije podataka: {e(A['status_revizije'].split(' (')[0])}.</footer>
</main>"""
    head = T10.HEAD.format(title="Mreže, analiza", css=T10.CSS + EXTRA_CSS)
    page = '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n' + head + body
    path = out / "artifact.html"
    path.write_text(page)
    return path


def verify() -> list[str]:
    """Re-read the numbers shown on the page against results/*.json and report mismatches."""
    d = Data(SEGMENT)
    text = re.sub(
        r"data:image/png;base64,[A-Za-z0-9+/=]+", "IMG", (d.out / "artifact.html").read_text()
    )
    issues: list[str] = []

    def has(s: str, label: str) -> None:
        if s not in text:
            issues.append(f"missing {label}: {s!r}")

    for cid in ("B0_BUYHOLD", "K1_C13C_ORIG", "K6_MOMENTUM_CS"):
        has(eur(d.win(cid)["end_value"] / d.n), f"{cid} end EUR")
    for t in d.tickers:
        for cid in ("B0_BUYHOLD", "K1_C13C_ORIG"):
            w = d.tk[t]["contenders"][cid]["windows"]["ai_era"]
            has(eur(w["end_value"]), f"{t} {cid} end EUR")
            has(f"Sharpe {n(w['sharpe'], 2)}, pad {pc(w['max_drawdown'] * 100, 0)}", f"{t} {cid} sharpe/pad")
        w1 = d.tk[t]["contenders"]["K1_C13C_ORIG"]["windows"]["ai_era"]
        has(f"<td>{w1['trades']}</td>", f"{t} trades")
        has(pc(round(w1["exposure_pct"]), 0), f"{t} exposure")
    for cid, v in d.analysis["tablica_segmenta_jednak_kapital_AI_era"]["suparnici"].items():
        w = d.win(cid)
        if round(w["sharpe"], 2) != round(v["sharpe"], 2):
            issues.append(f"{cid} sharpe analysis {v['sharpe']} vs results {w['sharpe']}")
        if round(w["total_return"] * 100, 1) != round(v["povrat_ukupno_pct"], 1):
            issues.append(f"{cid} return analysis {v['povrat_ukupno_pct']} vs results {w['total_return'] * 100:.1f}")
        if round(w["max_drawdown"] * 100, 1) != round(v["max_pad_pct"], 1):
            issues.append(f"{cid} max dd analysis {v['max_pad_pct']} vs results {w['max_drawdown'] * 100:.1f}")
        has(pc(w["total_return_cost_3x"] * 100, 0, True), f"{cid} 3x")
    return issues


def main() -> None:
    flags = sys.argv[1:]
    if "--verify-only" not in flags:
        p = build(redraw="--no-charts" not in flags)
        print("wrote", p, f"{p.stat().st_size / 1e6:.2f} MB")
    problems = verify()
    print("verify:", "OK" if not problems else "\n".join(problems))


if __name__ == "__main__":
    main()
