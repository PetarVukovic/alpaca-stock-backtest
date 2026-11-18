"""Build the self-contained Croatian 'Karta trzista' page for the group "Metali i indeksi".

Usage:
  .venv/bin/python scripts/aichain_map_page_metals.py            # build the page
  .venv/bin/python scripts/aichain_map_page_metals.py --verify   # build, then re-check numbers against raw JSON/CSV

This group has its own script (scripts/aichain_map_page.py is the shared per-group builder; it needs a
profile.json, which the metals group does not have, and it cannot show the two close-only indices).

Inputs (read only): swing/map/{T}.json + {T}.png, swing/results/metali_referentno.json, swing/placebo.json,
swing/registration.json, swing/summary.json and data/ohlcv/{T}_1d.csv (SPX/NDX close-only facts and a last-close
cross-check). Output: swing/pages/metals_indices.html (PNG charts embedded as data URIs, Google Fonts only).
The CSS comes from scripts/top10_build_artifact.py (imported, not modified). No orders are ever sent.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import top10_build_artifact as top10

BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SWING = BASE / "swing"
OUT = SWING / "pages" / "metals_indices.html"
GROUP_KEY = "metals_indices"
RESULT_KEY = "metali_referentno"
MAPPED = ["GLD", "SLV", "GDX", "PHAU", "PHAG", "IGLN_LSE", "SMH", "SOXX"]
CLOSE_ONLY = ["SPX", "NDX"]
TESTED = ["GLD", "SLV"]
US_USD = {
    "GLD",
    "SLV",
    "GDX",
    "SMH",
    "SOXX",
}  # Alpaca US feed, USD (data/ohlcv/DATA_NOTES.txt)

NAMES = {
    "GLD": "GLD (zlato, američki fond)",
    "SLV": "SLV (srebro, američki fond)",
    "GDX": "GDX (rudnici zlata)",
    "PHAU": "PHAU (fizičko zlato)",
    "PHAG": "PHAG (fizičko srebro)",
    "IGLN_LSE": "IGLN_LSE (fizičko zlato, London)",
    "SMH": "SMH (poluvodiči, američki fond)",
    "SOXX": "SOXX (poluvodiči, američki fond)",
    "SPX": "SPX (indeks S&P 500)",
    "NDX": "NDX (indeks Nasdaq 100)",
}

MECHANISM = {
    "GLD": "Fond koji drži fizičko zlato i prati njegovu cijenu. Zlato nema zaradu ni dividendu; cijenu mu pokreću kamatne stope, jačina dolara, strah na tržištima i kupnje središnjih banaka.",
    "SLV": "Isto što i GLD, ali za srebro. Srebro je dijelom ulagački metal, a dijelom industrijska sirovina, pa se obično kreće u većim zamasima od zlata.",
    "GDX": "Nije metal nego dionice rudnika zlata. Rudnik ima prilično stalne troškove, pa kad zlato poraste za nekoliko posto, zarada rudnika poraste puno više (i obrnuto). Zato ovaj papir pojačava kretanje zlata, ali nosi i rizik poslovanja tvrtki.",
    "PHAU": "Oznaka upućuje na proizvod koji prati fizičko zlato. Izdavatelj, burza i valuta nisu potvrđeni u našim podacima.",
    "PHAG": "Oznaka upućuje na proizvod koji prati fizičko srebro. Izdavatelj, burza i valuta nisu potvrđeni u našim podacima.",
    "IGLN_LSE": "Oznaka upućuje na zlatni proizvod kotiran na londonskoj burzi (LSE). Točan izdavatelj, valuta i dostupnost za Petra nisu potvrđeni.",
    "SMH": "Fond koji drži poluvodičke tvrtke (čipove). Kreće se uglavnom s tim koliko investitori vjeruju u potražnju za AI čipovima; ovdje je referentna serija, ne nešto što je sigurno kupljivo iz EU.",
    "SOXX": "Isto kao SMH: košarica poluvodičkih tvrtki, samo drugi izdavatelj. Služi kao druga referenca za isti sektor.",
    "SPX": "Indeks 500 najvećih američkih tvrtki. Ne može se kupiti izravno; fondovi ga samo prate. Ovdje služi kao mjerilo cijelog tržišta.",
    "NDX": "Indeks 100 najvećih nefinancijskih tvrtki na burzi Nasdaq (velik udio tehnologije). Ne može se kupiti izravno; ovdje služi kao mjerilo tehnološkog tržišta.",
}

RULE_HR = {
    "B0_BUYHOLD": "Kupi prvi dan i drži do kraja. Mjerilo, ne strategija.",
    "W1_C13C_ORIG": "Petrov C13C: kupi kad je cijena iznad prosjeka zadnjih 200 dana i u 5 dana je pala 5 % ili više; stop 10 % ispod najvišeg vrha nakon kupnje.",
    "W2_MOM_BREAK_20": "Kupi kad cijena zatvori na najvišoj razini zadnjih 20 dana uz pozitivan prinos zadnjih 60 dana; izlaz ispod najniže iz zadnjih 10 dana ili nakon 15 dana; stop 8 %.",
    "W3_MOM_RANK_WEEKLY": "Svaki petak poredaj papire skupine po prinosu zadnjih 20 dana i kupi najbolju trećinu koja je iznad prosjeka 50 dana; prodaj kad ispadne iz bolje polovice.",
    "W4_SR_BOUNCE_V2": "Kupi odbijanje od potpore koja je već imala barem 2 ranija dodira; stop 1 ATR ispod potpore, cilj najbliži raniji vrh, najdulje 15 dana.",
    "W5_SR_BREAKOUT_RETEST": "Kupi kad cijena probije raniji vrh, vrati se na njega i odbije se; stop 3 % ispod razine, izlaz kad zatvori ispod prosjeka 50 dana.",
    "W6_MM_SWEEP_SHIFT": "Tjedni trend nije silazan, cijena je u jeftinijoj polovici raspona, nedavno je izbijen kratkoročni stop ispod dna (sweep) pa cijena zatvori iznad zadnjeg nižeg vrha; stop ispod dna sweepa, pola pozicije se prodaje na cilju.",
    "W7_MM_DEMAND_RETEST": "Kupi prvi povratak u svježu zonu potražnje, ali samo uz uzlaznu strukturu i cijenu u jeftinijoj polovici raspona; stop ispod zone, cilj zadnji vrh, najdulje 20 dana.",
    "W8_IBS_REVERT": "Kupi kad dan zatvori vrlo blizu svog dnevnog dna (IBS ispod 0,2) i cijena je iznad prosjeka 200 dana; izlaz kad zatvori blizu dnevnog vrha ili nakon 5 dana.",
}
CONTENDER_ORDER = [
    "B0_BUYHOLD",
    "W1_C13C_ORIG",
    "W2_MOM_BREAK_20",
    "W3_MOM_RANK_WEEKLY",
    "W4_SR_BOUNCE_V2",
    "W5_SR_BREAKOUT_RETEST",
    "W6_MM_SWEEP_SHIFT",
    "W7_MM_DEMAND_RETEST",
    "W8_IBS_REVERT",
]
SHORT = {
    "B0_BUYHOLD": "Kupi i drži",
    "W1_C13C_ORIG": "W1 C13C",
    "W2_MOM_BREAK_20": "W2 Proboj 20 dana",
    "W3_MOM_RANK_WEEKLY": "W3 Tjedni zamah",
    "W4_SR_BOUNCE_V2": "W4 Odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 Proboj i povratak",
    "W6_MM_SWEEP_SHIFT": "W6 Sweep i promjena karaktera",
    "W7_MM_DEMAND_RETEST": "W7 Povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 Zatvaranje blizu dna",
}

EXTRA_CSS = """
.tagline{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.verdict-top{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:6px;padding:18px 20px}
.verdict-top p{font-size:1.12rem;line-height:1.5;margin:0 0 8px;max-width:none}
.verdict-top p:last-child{margin-bottom:0}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.chip{font-family:var(--mono);font-size:.78rem;padding:3px 9px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted)}
.chip.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.teach{background:var(--accent-soft);border-radius:6px;padding:14px 16px;margin:0 0 14px}
.teach p{margin:0 0 8px;max-width:none}.teach p:last-child{margin:0}
.plate{overflow-x:auto}
.plate img{min-width:720px}
@media (min-width:860px){.plate img{min-width:0}}
.swipe{font-size:.82rem;color:var(--muted);margin:6px 0 0}
@media (min-width:860px){.swipe{display:none}}
td.wrap,th.wrap{white-space:normal;min-width:190px;text-align:left;vertical-align:top}
td.wrap small{display:block;color:var(--muted);font-size:.8rem;line-height:1.35}
.pos{color:var(--good)}.neg{color:var(--bad)}
.tk{font-family:var(--display);font-weight:700}
.reading{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px 16px;margin-top:10px}
.reading p{max-width:none;margin:0 0 8px}.reading p:last-child{margin:0}
.reading b.h{font-family:var(--display)}
.cmp td:first-child{font-family:var(--display);font-weight:600;white-space:normal;min-width:150px}
.sub{color:var(--muted);font-size:.85rem}
h2{margin-top:4px}
.stack{display:flex;flex-direction:column;gap:28px}
"""


# ---------------------------------------------------------------- formatting helpers


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def hr(x: float, nd: int = 0) -> str:
    """Croatian number format: decimal comma, thousands dot."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def hrs(x: float, nd: int = 0) -> str:
    """Croatian number with an explicit plus sign for positives."""
    return ("+" if x > 0 else "") + hr(x, nd)


def pct(x: float, nd: int = 1, sign: bool = False) -> str:
    return (hrs(x, nd) if sign else hr(x, nd)) + " %"


def dmy(d: Any) -> str:
    ts = pd.Timestamp(d)
    return f"{ts.day}. {ts.month}. {ts.year}."


def price(t: str, x: float) -> str:
    """Price with a currency only where the data feed makes the currency known."""
    return hr(x, 2) + (" $" if t in US_USD else "")


def eur_move(distance_pct: float) -> str:
    """Move on a 1.000 EUR position for a price distance in percent (gain positive, loss negative)."""
    return f"{hrs(1000.0 * distance_pct / 100.0, 0)} EUR"


def load(p: Path) -> Any:
    return json.loads(p.read_text())


def img_tag(path: Path, alt: str) -> str:
    return f'<img src="{top10.img(path)}" alt="{e(alt)}" loading="lazy">'


class Ctx:
    """All raw inputs, loaded once."""

    def __init__(self) -> None:
        self.maps: dict[str, dict[str, Any]] = {
            t: load(SWING / "map" / f"{t}.json") for t in MAPPED
        }
        self.res: dict[str, Any] = load(SWING / "results" / f"{RESULT_KEY}.json")
        self.placebo: dict[str, Any] = load(SWING / "placebo.json")
        self.reg: dict[str, Any] = load(SWING / "registration.json")
        self.summary: dict[str, Any] = load(SWING / "summary.json")
        self.csv: dict[str, pd.DataFrame] = {
            t: pd.read_csv(
                ROOT / "data" / "ohlcv" / f"{t}_1d.csv", parse_dates=["date"]
            )
            for t in MAPPED + CLOSE_ONLY
        }

    def bad_ohlc_rows(self, t: str) -> int:
        d = self.csv[t]
        bad = (d["high"] < d[["open", "close"]].max(axis=1) - 1e-9) | (
            d["low"] > d[["open", "close"]].min(axis=1) + 1e-9
        )
        return int(bad.sum())

    def best_ineligible(self) -> dict[str, Any]:
        return max(
            self.res["ranking"]["not_eligible"], key=lambda r: r["score_eur_per_month"]
        )


def bias_word(bias: str) -> str:
    return {"bullish": "uzlazan", "bearish": "silazan"}.get(bias, "bez jasnog smjera")


def structure_counts(c: Ctx) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"bearish": [], "bullish": [], "mixed": []}
    for t in MAPPED:
        w, d = c.maps[t]["weekly"]["bias"], c.maps[t]["daily"]["bias"]
        out[w if w == d and w in out else "mixed"].append(t)
    return out


# ---------------------------------------------------------------- sections


def sec_verdict(c: Ctx) -> str:
    sc = structure_counts(c)
    eligible = c.res["ranking"]["ranking"]
    best = c.best_ineligible()
    bh = c.res["ranking"]["buy_and_hold_reference"]
    win = c.res["window"]
    verdict_part = (
        "je pronašao barem jedno pravilo koje ispunjava"
        if eligible
        else "nije pronašao nijedno pravilo koje ispunjava"
    )
    line1 = (
        f"Od {len(MAPPED)} mapiranih papira {len(sc['bearish'])} ima silazan tjedni i dnevni trend ({', '.join(sc['bearish'])}), "
        f"{len(sc['bullish'])} ima uzlazan ({', '.join(sc['bullish'])}); swing test na GLD i SLV {verdict_part} "
        f"unaprijed zadan uvjet 'radi često', a potpore i otpori u ovoj skupini ne odbijaju cijenu češće od nasumičnih crta."
    )
    line2 = (
        f"Najbliže uvjetima bilo je pravilo {SHORT[best['contender']]} ({posla(best['trades'])} u {hr(win['months'], 0)} mjeseci, "
        f"prosječno {hrs(best['expectancy_eur'], 1)} EUR po poslu na 1.000 EUR), ali to je premalo poslova za zaključak; "
        f"kupi-i-drži bez ikakvog pravila dalo je {pct(bh['total_return'] * 100, 1, True)} u istom razdoblju."
    )
    return f"""<section id="presuda"><div class="verdict-top"><p>{e(line1)}</p><p>{e(line2)}</p>
<p class="sub">Ovo je istraživačko čitanje povijesnih cijena, nije signal za kupnju ni savjet. Razdoblje testa: {dmy(win["ai_era"][0])} do {dmy(win["ai_era"][1])} (AI era, glavno mjerilo); trošak 0,025 % po strani (2,5 baznih bodova), uz stres 2x i 3x; bez poluge, samo dugo. Nijedan nalog nije poslan; ovo nije formalni Critic PASS.</p></div></section>"""


def sec_how(c: Ctx) -> str:
    rows = []
    for t in MAPPED + CLOSE_ONLY:
        extra = ""
        if t in c.maps:
            m = c.maps[t]
            drop = (m["last_close"] / m["high_52w"]["price"] - 1) * 100
            extra = (
                f" Iz naših podataka: u zadnjih 52 tjedna kretao se između {price(t, m['low_52w']['price'])} "
                f"(od {dmy(m['low_52w']['date'])}) i {price(t, m['high_52w']['price'])} (od {dmy(m['high_52w']['date'])}); "
                f"zadnje zatvaranje je {pct(drop, 1, True)} u odnosu na taj vrh, a običan dnevni raspon (ATR14) je {pct(m['atr14_pct'], 1)} cijene."
            )
        rows.append(
            f"<div><dt>{e(NAMES[t])}</dt><dd>{e(MECHANISM[t])}{e(extra)}</dd></div>"
        )
    return f"""<section id="mehanizam"><h2>Kako ovo tržište funkcionira</h2>
<div class="teach"><p><b>Važno:</b> opisi mehanizma su <b>kontekst iz javnih izvora</b>, napisani općenito i bez brojki; nisu iz naših CSV-ova i nisu provjereni u ovom istraživanju (profil ponašanja za ovu skupinu iz prethodnog kruga ne postoji). Brojke u istom odlomku, ako ih ima, izračunate su iz naših dnevnih podataka.</p>
<p>Što je ovdje drukčije od dionica: nema jedne tvrtke čija zarada pomiče cijenu. Zlato i srebro su sirovine bez zarade, a fondovi samo prate cijenu, pa se razine i trendovi gledaju gotovo isključivo na samom grafu.</p></div>
<dl>{"".join(rows)}</dl></section>"""


def level_cell(t: str, lv: dict[str, Any], kind: str) -> str:
    rel = lv["reliability"]
    if rel["enough_touches"]:
        rtxt = f"pouzdanost: od {rel['n']} dodira odbijeno {rel['bounce']} ({pct(rel['rate'] * 100, 0)}), probijeno {rel['break']}"
    else:
        rtxt = f"pouzdanost: premalo dodira za zaključak ({rel['n']})"
    verb = (
        "ako puca ova razina" if kind == "support" else "ako cijena dođe do ove razine"
    )
    return (
        f'<td class="wrap"><b>{price(t, lv["price"])}</b> ({pct(lv["distance_pct"], 1, True)}; {eur_move(lv["distance_pct"])} na 1.000 EUR)'
        f"<small>{verb} · {lv['turning_points']} okret(a) · {e(rtxt)}</small></td>"
    )


def zone_cell(m: dict[str, Any]) -> str:
    dem = m["fresh_zones"]["demand"]
    sup = m["fresh_zones"]["supply"]
    parts: list[str] = []
    if dem:
        z = min(dem, key=lambda z: abs(z["distance_pct"]))
        parts.append(
            f"Potražnja {hr(z['low'], 2)}–{hr(z['high'], 2)} ({pct(z['distance_pct'], 1, True)})"
        )
    if sup:
        z = min(sup, key=lambda z: abs(z["distance_pct"]))
        parts.append(
            f"Ponuda {hr(z['low'], 2)}–{hr(z['high'], 2)} ({pct(z['distance_pct'], 1, True)})"
        )
    if not parts:
        parts.append("nema svježih zona")
    extra = f"svježih zona: potražnje {len(dem)}, ponude {len(sup)} · otvorenih praznina: {len(m['open_fvg']['bull'])} uzlaznih, {len(m['open_fvg']['bear'])} silaznih"
    if m["recent_sweeps"]:
        s = m["recent_sweeps"][-1]
        extra += f" · zadnji sweep {dmy(s['date'])} ({e(s['direction'])}, razina {hr(s['level'], 2)})"
    return f'<td class="wrap">{"<br>".join(parts)}<small>{extra}</small></td>'


def pos_text(m: dict[str, Any]) -> str:
    sr = m["swing_range"]
    p = sr["position_pct"]
    if sr["zone"] == "discount":
        return f"{pct(p, 0)} raspona: jeftinija polovica (diskont)"
    if sr["zone"] == "premium":
        return f"{pct(p, 0)} raspona: skuplja polovica (premium)"
    return f"{sr['zone_hr']} ({pct(p, 0)} raspona)"


def sec_now(c: Ctx) -> str:
    rows = []
    for t in MAPPED:
        m = c.maps[t]
        w, d = m["weekly"]["bias"], m["daily"]["bias"]
        sup, res = m["nearest_supports"], m["nearest_resistances"]
        s_cells = "".join(
            level_cell(t, lv, "support") for lv in sup
        ) + '<td class="wrap">nema potpore</td>' * (2 - len(sup))
        r_cells = "".join(
            level_cell(t, lv, "resistance") for lv in res
        ) + '<td class="wrap">nema otpora iznad</td>' * (2 - len(res))
        rows.append(
            f'<tr data-t="{t}"><td class="wrap"><span class="tk">{e(t)}</span><small>{dmy(m["last_date"])} · zatvaranje <b>{price(t, m["last_close"])}</b></small></td>'
            f'<td class="wrap">tjedni: {bias_word(w)}<br>dnevni: {bias_word(d)}</td>'
            f'<td class="wrap">{e(pos_text(m))}<small>raspon {hr(m["swing_range"]["low"], 2)} – {hr(m["swing_range"]["high"], 2)}</small></td>'
            f"{s_cells}{r_cells}{zone_cell(m)}</tr>"
        )
    ci = []
    for t in CLOSE_ONLY:
        d = c.csv[t].set_index("date")["close"]
        last = d.iloc[-1]
        ci.append(
            f'<tr data-t="{t}"><td class="wrap"><span class="tk">{t}</span><small>{dmy(d.index[-1])}</small></td>'
            f"<td>{hr(last, 2)}</td><td>{pct((last / d.tail(50).mean() - 1) * 100, 1, True)}</td><td>{pct((last / d.tail(200).mean() - 1) * 100, 1, True)}</td>"
            f"<td>{pct((last / d.tail(252).max() - 1) * 100, 1, True)}</td><td>{pct((last / d.tail(252).min() - 1) * 100, 1, True)}</td>"
            f'<td class="wrap">{c.bad_ohlc_rows(t)} redaka s nedosljednim dnevnim rasponom</td></tr>'
        )
    return f"""<section id="sada"><h2>Gdje je cijena sada</h2>
<div class="teach"><p><b>Kako čitati tablicu.</b> <b>Potpora</b> je cijena na kojoj se ranije zaustavio pad (kao pod ispod cijene); <b>otpor</b> je cijena na kojoj se ranije zaustavio rast (kao strop). Razina je potvrđena tek 5 svijeća nakon što je nastala, pa nikad ne gledamo u budućnost.
<b>Primjer s 1.000 EUR:</b> ako je udaljenost do potpore -2,0 %, a uložio si 1.000 EUR, pad do te razine znači oko -20 EUR. To je gola aritmetika: ne uključuje jaz preko noći (kad dan otvori ispod razine) ni trošak.</p>
<p><b>Struktura</b> je niz potvrđenih vrhova i dna: uzlazan trend = svaki vrh i dno viši od prethodnog; silazan = svaki niži. <b>Raspon</b> je prostor od zadnjeg potvrđenog dna do zadnjeg potvrđenog vrha. <b>Diskont</b> je donja polovica raspona, <b>premium</b> gornja; ako je cijena već izvan raspona, piše da je probijeno dno ili vrh. <b>Zona potražnje</b> je područje gdje je zadnja silazna svijeća prethodila snažnom skoku (zona ponude je zrcalno); <b>svježa</b> je dok se cijena nije prvi put vratila u nju.</p>
<p><b>Pouzdanost</b> razine znači: kad je cijena nakon nastanka razine došla do nje, koliko se puta odbila za barem 1,5 ATR, a koliko puta probila. Uz manje od 5 dodira ne donosimo zaključak. Svaki papir koristi svoj zadnji datum (vidi prvi stupac), a ne zajednički 5. 10. 2026. kao swing test.</p></div>
<div class="table-wrap"><table class="cmp"><thead><tr><th class="wrap">Papir</th><th class="wrap">Struktura</th><th class="wrap">Položaj u rasponu</th><th class="wrap">Potpora 1</th><th class="wrap">Potpora 2</th><th class="wrap">Otpor 1</th><th class="wrap">Otpor 2</th><th class="wrap">Aktivne zone</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="swipe">Na mobitelu povuci tablicu ulijevo i udesno.</p>
<h3 style="margin-top:20px">Indeksi bez karte: samo zatvaranje</h3>
<p>Za SPX i NDX nema karte razina: u CSV-ovima dnevni najviši i najniži iznos nisu dosljedni s otvaranjem i zatvaranjem (zadnji stupac), pa pravila podataka istraživanja dopuštaju samo zatvaranje. Ovdje je samo ono što se pouzdano računa iz zatvaranja (prosjek 50 i 200 dana, vrh i dno zadnjih 252 trgovačkih dana).</p>
<div class="table-wrap"><table><thead><tr><th class="wrap">Indeks</th><th>Zatvaranje</th><th>Prema prosjeku 50 dana</th><th>Prema prosjeku 200 dana</th><th>Prema vrhu 252 dana</th><th>Prema dnu 252 dana</th><th class="wrap">Napomena o podacima</th></tr></thead><tbody>{"".join(ci)}</tbody></table></div></section>"""


def reading_for(c: Ctx, t: str) -> str:
    m = c.maps[t]
    w, d = m["weekly"], m["daily"]
    sr = m["swing_range"]
    sup, res = m["nearest_supports"], m["nearest_resistances"]
    atr = m["atr14_pct"]
    trend = f"Tjedni trend je {bias_word(w['bias'])}, dnevni {bias_word(d['bias'])}."
    if d.get("last_bos"):
        trend += f" Zadnji dnevni proboj strukture bio je {dmy(d['last_bos']['date'])} ({d['last_bos']['direction']}, probijena razina {hr(d['last_bos']['broken_level'], 2)})"
        trend += (
            f", a zadnja promjena karaktera {dmy(d['last_shift']['date'])} ({d['last_shift']['direction']})."
            if d.get("last_shift")
            else "."
        )
    see: list[str] = [trend]
    if sr["zone"] == "outside":
        see.append(
            f"Cijena je {sr['zone_hr']}: zadnji potvrđeni raspon je {hr(sr['low'], 2)} do {hr(sr['high'], 2)}, a zatvaranje {price(t, m['last_close'])} je izvan njega."
        )
    else:
        half = (
            "jeftinija polovica (diskont)"
            if sr["zone"] == "discount"
            else "skuplja polovica (premium)"
        )
        see.append(
            f"Cijena je na {pct(sr['position_pct'], 0)} raspona od {hr(sr['low'], 2)} do {hr(sr['high'], 2)}: {half}."
        )
    bits = []
    if sup:
        bits.append(
            f"Najbliža potpora {price(t, sup[0]['price'])} je {pct(abs(sup[0]['distance_pct']), 1)} ispod ({hr(abs(sup[0]['distance_atr']), 1)} ATR)"
        )
    if res:
        bits.append(
            f"najbliži otpor {price(t, res[0]['price'])} je {pct(abs(res[0]['distance_pct']), 1)} iznad ({hr(abs(res[0]['distance_atr']), 1)} ATR)"
        )
    if bits:
        see.append("; ".join(bits) + ".")
    dem, sup_z = m["fresh_zones"]["demand"], m["fresh_zones"]["supply"]
    sweep = (
        f"nedavni sweep: {dmy(m['recent_sweeps'][-1]['date'])} ({m['recent_sweeps'][-1]['direction']})."
        if m["recent_sweeps"]
        else "nedavnih sweepova nema."
    )
    see.append(f"Svježih zona potražnje {len(dem)}, zona ponude {len(sup_z)}; {sweep}")
    todo: list[str] = []
    both_bear = w["bias"] == "bearish" and d["bias"] == "bearish"
    both_bull = w["bias"] == "bullish" and d["bias"] == "bullish"
    if both_bear:
        todo.append(
            "Dok su i tjedni i dnevni trend silazni, trader koji kupuje samo dugo uglavnom čeka: kupnja sada bila bi kupnja protiv trenda. Prvi znak okreta bio bi zatvaranje iznad najbližeg otpora"
            + (f" ({price(t, res[0]['price'])})" if res else "")
            + ", a ne samo dodir potpore."
        )
    elif both_bull:
        todo.append(
            "Trend je uzlazan pa trader traži povlačenje prema potpori umjesto potjere za vrhom. Gleda drži li se najbliža potpora i vraća li se cijena u neku svježu zonu potražnje."
        )
    else:
        todo.append(
            "Trendovi na tjednom i dnevnom grafu se razilaze, što obično znači prijelaz; trader čeka da se oba poravnaju prije odluke."
        )
    if sup:
        s1 = sup[0]
        loss = f"Ako najbliža potpora {price(t, s1['price'])} pukne, gubitak je oko {hr(abs(1000 * s1['distance_pct'] / 100), 0)} EUR na 1.000 EUR"
        if len(sup) > 1:
            loss += f"; sljedeća je {price(t, sup[1]['price'])} ({pct(sup[1]['distance_pct'], 1, True)}, {eur_move(sup[1]['distance_pct'])})"
        todo.append(loss + ".")
        if abs(s1["distance_atr"]) < 1:
            todo.append(
                f"Potpora je unutar jednog običnog dnevnog raspona (ATR14 je {pct(atr, 1)}, oko {hr(1000 * atr / 100, 0)} EUR na 1.000 EUR): običan dan bez ikakve vijesti mogao bi je dotaknuti, pa je tako tijesan stop podložan lažnim izbijanjima."
            )
    todo.append(
        "Razine su orijentir za planiranje stopa i ciljeva, ne dokaz prednosti (vidi test lažnih razina niže). Ovo nije signal."
    )
    note = ""
    if t not in US_USD:
        note = '<p class="sub">Valuta cijena za ovaj papir nije potvrđena u našim podacima; postotci i iznosi na 1.000 EUR ne ovise o valuti.</p>'
    return (
        f'<div class="reading"><p><b class="h">Što ovdje vidimo:</b> {e(" ".join(see))}</p>'
        f'<p><b class="h">Što bi swing trader gledao:</b> {e(" ".join(todo))}</p>{note}</div>'
    )


def sec_charts(c: Ctx) -> str:
    figs = []
    for t in MAPPED:
        m = c.maps[t]
        figs.append(
            f'<figure id="karta-{t}"><h3>{e(NAMES[t])}, zadnji dan {dmy(m["last_date"])}</h3>'
            f'<div class="plate">{img_tag(SWING / "map" / f"{t}.png", "Bilježnica s kartom razina za " + t)}</div>'
            f'<p class="swipe">Na mobitelu povuci graf ulijevo i udesno da vidiš sve.</p>{reading_for(c, t)}</figure>'
        )
    return f"""<section id="karte"><h2>Karta po papiru</h2>
<p>Svaka karta je kao bilježnica učitelja: svijeće su cijene, vodoravne trake su potpore (zeleno) i otpori (crveno), plava crta je prosjek zadnjih 50 dana, a isprekidana prosjek 200 dana. Brojevi u krugovima su točke objašnjene ispod grafa. Što je traka deblja, to je razina jača. Karte su izrađene iz istih CSV-ova kao i sve ostalo.</p>
<div class="stack">{"".join(figs)}</div></section>"""


def posla(n: int) -> str:
    """Croatian count of trades with the right plural form (1 posao, 2-4 posla, else poslova)."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} posao"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} posla"
    return f"{n} poslova"


REASON_HR = [
    (
        re.compile(r"only (\d+) trades? \(< 60\)"),
        lambda m: f"samo {posla(int(m.group(1)))} (treba barem 60)",
    ),
    (
        re.compile(r"expectancy <= 0 at cost 2x"),
        lambda m: "očekivanje po poslu nije iznad nule uz trošak 2x",
    ),
    (re.compile(r"profit factor < 1\.2"), lambda m: "profit factor ispod 1,2"),
]


def reason_hr(r: str) -> str:
    for rx, fn in REASON_HR:
        m = rx.fullmatch(r)
        if m:
            return fn(m)
    return r


def dash_or(x: float | None, nd: int = 1) -> str:
    return "-" if x is None else hrs(x, nd)


def pct_or_dash(x: float | None, nd: int = 0) -> str:
    return "-" if x is None else pct(x * 100, nd)


def sec_swing(c: Ctx) -> str:
    conts = c.res["contenders"]
    bh = c.res["ranking"]["buy_and_hold_reference"]
    win = c.res["window"]
    rows = []
    for cid in CONTENDER_ORDER:
        a = conts[cid]["ai_era"]
        v = conts[cid].get("verdict")
        ok = (
            "mjerilo"
            if cid == "B0_BUYHOLD"
            else (
                "da"
                if v["eligible"]
                else "ne: " + "; ".join(reason_hr(x) for x in v["reasons"])
            )
        )
        pf = "-" if a["profit_factor"] is None else hr(a["profit_factor"], 2)
        cls = "pos" if a["total_return"] > 0 else "neg"
        rows.append(
            f'<tr data-id="{cid}"><td class="wrap">{e(SHORT[cid])}<small>{e(RULE_HR[cid])}</small></td>'
            f"<td>{a['trades']}</td><td>{hr(a['trades_per_month'], 2)}</td><td>{pct_or_dash(a['hit_rate'])}</td>"
            f"<td>{dash_or(a['expectancy_eur'])}</td><td>{dash_or(a['expectancy_eur_cost_2x'])}</td><td>{pf}</td>"
            f"<td>{hr(a['median_hold_days'], 0)} / {hr(a['mean_hold_days'], 0)}</td>"
            f'<td class="{cls}">{pct(a["total_return"] * 100, 1, True)}</td><td class="wrap">{e(ok)}</td></tr>'
        )
    eligible = c.res["ranking"]["ranking"]
    best = c.best_ineligible()
    w8 = conts["W8_IBS_REVERT"]["ai_era"]
    w5 = conts["W5_SR_BREAKOUT_RETEST"]["ai_era"]
    if eligible:
        winner_txt = f"Pobjednik prema unaprijed upisanom pravilu: {e(SHORT[eligible[0]['contender']])}."
    else:
        winner_txt = (
            "<b>Nitko ne ispunjava uvjete.</b> Uvjeti su upisani prije ikakvog testa: najmanje 60 poslova u AI eri za cijelu skupinu, "
            "očekivanje po poslu veće od nule i uz dvostruki trošak, te omjer dobiti i gubitka (profit factor) najmanje 1,2. "
            "Rangiranje bi tada bilo po očekivanju po poslu puta broj poslova mjesečno. "
            f"Najbolja računica bila je za {e(SHORT[best['contender']])} ({hr(best['score_eur_per_month'], 1)} EUR mjesečno na papiru), ali sa samo {posla(best['trades'])}; "
            f"najčešće pravilo, {e(SHORT['W8_IBS_REVERT'])} ({posla(w8['trades'])}), ima profit factor {hr(w8['profit_factor'], 2)}, ispod 1,2."
        )
    ctx_rows = []
    for cid in CONTENDER_ORDER[1:]:
        cells = ""
        for blk in ("y2016_2020", "y2021_2022"):
            x = conts[cid]["contexts"][blk]
            pf = "-" if x["profit_factor"] is None else hr(x["profit_factor"], 2)
            cells += f"<td>{x['trades']}</td><td>{dash_or(x['expectancy_eur'])}</td><td>{pf}</td>"
        ctx_rows.append(f'<tr><td class="wrap">{e(SHORT[cid])}</td>{cells}</tr>')
    tk_rows = []
    for cid in CONTENDER_ORDER:
        pt = conts[cid]["ai_era"]["per_ticker"]
        cells = "".join(
            f"<td>{pt[t]['trades']}</td><td>{pct_or_dash(pt[t]['hit_rate'])}</td><td>{dash_or(pt[t]['expectancy_eur'])}</td><td>{pct(pt[t]['total_return'] * 100, 1, True)}</td>"
            for t in TESTED
        )
        tk_rows.append(f'<tr><td class="wrap">{e(SHORT[cid])}</td>{cells}</tr>')
    return f"""<section id="swing"><h2>Što je swing test pokazao za ovu skupinu</h2>
<div class="teach"><p><b>Što je testirano.</b> Osam pravila trgovanja (W1 do W8) plus kupi-i-drži kao mjerilo, na dva papira iz skupine: <b>GLD i SLV</b> (po 1.000 EUR svaki). <b>Za GDX, PHAU, PHAG, IGLN_LSE, SMH, SOXX, SPX i NDX swing test nije pokrenut</b> (registrirani test skupine metala sadrži samo GLD i SLV); za njih imamo samo kartu. Odluka se donosi na zatvaranju dana, a kupnja je na sutrašnjem otvaranju. Trošak je 0,025 % po strani; stres 2x i 3x je u datotekama rezultata.</p>
<p><b>Pojmovi.</b> <b>Očekivanje po poslu</b> je prosječna zarada jednog posla na ulogu od 1.000 EUR: +10 EUR znači da je prosječan posao donio 10 EUR prije poreza. <b>Udio dobitnih</b> je koliko je poslova završilo u plusu. <b>Profit factor</b> je ukupna dobit podijeljena s ukupnim gubitkom: 2,0 znači da su na svaki izgubljeni euro zarađena dva. <b>Dani držanja</b> su medijan / prosjek dana u poziciji. Stupac „Prinos“ je ukupni prinos na oba papira zajedno, od {dmy(win["ai_era"][0])} do {dmy(win["ai_era"][1])} ({hr(win["months"], 1)} mjeseci).</p></div>
<div class="table-wrap"><table class="cmp"><thead><tr><th class="wrap">Pravilo</th><th>Poslova</th><th>Poslova mjesečno</th><th>Udio dobitnih</th><th>Očekivanje po poslu (EUR)</th><th>Isto uz trošak 2x (EUR)</th><th>Profit factor</th><th>Dani držanja (medijan / prosjek)</th><th>Prinos</th><th class="wrap">Radi često?</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="swipe">Na mobitelu povuci tablicu ulijevo i udesno.</p>
<div class="verdict" style="margin-top:14px"><p>{winner_txt}</p>
<p>Za usporedbu, kupi-i-drži na GLD i SLV: {pct(bh["total_return"] * 100, 1, True)} ukupno, najveći pad od vrha {pct(bh["max_drawdown"] * 100, 1)}. Nijedno pravilo nije dostiglo držanje po prinosu: razdoblje je bilo snažan rast zlata i srebra, a pravila su većinu vremena bila izvan tržišta (izloženost W5: {pct(w5["exposure_pct"], 0)}). Petrov cilj je pravilo koje trguje često, pa je prinos ovdje samo kontekst.</p>
<p>Oprez pri čitanju: {e(SHORT["W5_SR_BREAKOUT_RETEST"])} ima visok profit factor ({hr(w5["profit_factor"], 2)}) na samo {w5["trades"]} poslova, a dobit dolazi od nekoliko poslova (5 najboljih čini {pct(w5["top5_profit_share"] * 100, 0)} ukupne dobiti). To je premalo za zaključak; rizik se ovdje ne ocjenjuje, ali vrijednost dokaza se ocjenjuje. Pravila W6 i W7 (mehanika s pivotima i zonama) gotovo nikad ne dobiju priliku: {conts["W6_MM_SWEEP_SHIFT"]["ai_era"]["trades"]} odnosno {conts["W7_MM_DEMAND_RETEST"]["ai_era"]["trades"]} posla u {hr(win["months"], 0)} mjeseci.</p></div>
<details><summary>Po papiru: GLD i SLV zasebno</summary><div class="table-wrap"><table class="cmp"><thead><tr><th class="wrap">Pravilo</th><th>GLD poslova</th><th>GLD udio dobitnih</th><th>GLD očekivanje (EUR)</th><th>GLD prinos</th><th>SLV poslova</th><th>SLV udio dobitnih</th><th>SLV očekivanje (EUR)</th><th>SLV prinos</th></tr></thead><tbody>{"".join(tk_rows)}</tbody></table></div></details>
<details style="margin-top:10px"><summary>Ranije godine (samo kontekst, ne mjerilo)</summary><div class="table-wrap"><table class="cmp"><thead><tr><th class="wrap">Pravilo</th><th>2016-2020 poslova</th><th>očekivanje (EUR)</th><th>profit factor</th><th>2021-2022 poslova</th><th>očekivanje (EUR)</th><th>profit factor</th></tr></thead><tbody>{"".join(ctx_rows)}</tbody></table></div><p class="sub" style="padding:8px 14px">Tržišni režim se promijenio nakon 2022., pa ovi redovi služe samo kao kontekst.</p></details>
<p class="sub" style="margin-top:12px">Pokušaja u ledgeru (K): {c.summary["ledger_k"]}. Deflated Sharpe i PSR (informativno, ne snižavaju ocjenu) nalaze se u results/{RESULT_KEY}.json. Rezultat jedne skupine od dva papira lako je slučajan; važniji je isti obrazac u više skupina.</p></section>"""


def sec_placebo(c: Ctx) -> str:
    g = c.placebo["sr"]["by_group"][GROUP_KEY]
    tot = c.placebo["sr"]["all"]
    r, rd = g["real"], g["rand"]

    def dif(k: str, which: str) -> str:
        x = g[which][k]
        return f"{hrs(x['diff'] * 100, 1)} pp [{hrs(x['ci95'][0] * 100, 1)}; {hrs(x['ci95'][1] * 100, 1)}]"

    all_cross = all(
        g["diff_vs_rand"][k]["ci95"][0] <= 0 <= g["diff_vs_rand"][k]["ci95"][1]
        for k in ("bounce_rate", "break_rate")
    )
    verdict = (
        "Ne: u ovoj skupini prave razine ne odbijaju cijenu češće od nasumičnih crta (interval razlike obuhvaća nulu)."
        if all_cross
        else "U ovoj skupini razlika postoji u barem jednoj mjeri; vidi tablicu."
    )
    events = c.placebo["mechanics_ai_era"]["events"]
    ev_rows = []
    for key, ev in events.items():
        bg = ev["by_group_h10"][GROUP_KEY]
        ev_rows.append(
            f'<tr data-ev="{key}"><td class="wrap">{e(ev["label"])}</td><td>{bg["n"]}</td><td>{hrs(bg["mean_excess"] * 100, 1)} pp</td>'
            f"<td>{eur_move(bg['mean_excess'] * 100)}</td><td>{ev['n']}</td></tr>"
        )
    ns = [ev["by_group_h10"][GROUP_KEY]["n"] for ev in events.values()]
    few = sum(1 for n in ns if n < 10)
    return f"""<section id="placebo"><h2>Test lažnih razina: pobjeđuju li crte s grafa slučajne crte?</h2>
<div class="teach"><p><b>Ideja u jednoj rečenici.</b> Kao tableta od šećera u ispitivanju lijeka: uz svaku pravu razinu stavili smo lažnu (nasumičnu cijenu u rasponu zadnjih 120 dana, istu razinu pomaknutu za ±3 %, i par crta oko prave razine), pa gledali odbija li se cijena od prave razine češće nego od lažne. Ako ne, crtanje razina ne daje prednost.</p>
<p><b>Primjer.</b> Od 100 dodira prave razine cijena se odbije u {hr(r["bounce_rate"] * 100, 0)}, a od nasumične crte u {hr(rd["bounce_rate"] * 100, 0)}. Razlika od nekoliko dodira na sto lako se dogodi slučajno, a interval pouzdanosti 95 % (raspon u kojem bi se razlika vjerojatno našla da pokus ponovimo) to potvrđuje: obuhvaća nulu.</p></div>
<p><b>{e(verdict)}</b> Uzorak: {g["n_levels"]} razina izračunatih na kraju svakog mjeseca AI ere za 8 papira ove skupine ({g["n_months"]} mjeseci); u svih 55 papira istraživanja: {tot["n_levels"]} razina i isti zaključak.</p>
<div class="table-wrap"><table><thead><tr><th class="wrap">Što se mjeri</th><th>Prave razine</th><th>Nasumična cijena</th><th>Razlika (prave minus nasumične)</th><th>Pomak ±3 %: razlika</th><th>Par oko razine: razlika</th></tr></thead><tbody>
<tr data-k="touch"><td class="wrap">Cijena dotakne razinu u 20 dana</td><td>{pct(r["touch_rate"] * 100, 1)}</td><td>{pct(rd["touch_rate"] * 100, 1)}</td><td>{dif("touch_rate", "diff_vs_rand")}</td><td>{dif("touch_rate", "diff_vs_shift")}</td><td>{dif("touch_rate", "diff_vs_match")}</td></tr>
<tr data-k="bounce"><td class="wrap">Odbijanje (barem 1,5 ATR) nakon dodira</td><td>{pct(r["bounce_rate"] * 100, 1)}</td><td>{pct(rd["bounce_rate"] * 100, 1)}</td><td>{dif("bounce_rate", "diff_vs_rand")}</td><td>{dif("bounce_rate", "diff_vs_shift")}</td><td>{dif("bounce_rate", "diff_vs_match")}</td></tr>
<tr data-k="break"><td class="wrap">Probijanje (zatvaranje 1 ATR iza razine)</td><td>{pct(r["break_rate"] * 100, 1)}</td><td>{pct(rd["break_rate"] * 100, 1)}</td><td>{dif("break_rate", "diff_vs_rand")}</td><td>{dif("break_rate", "diff_vs_shift")}</td><td>{dif("break_rate", "diff_vs_match")}</td></tr>
</tbody></table></div>
<p class="sub">pp = postotni bod (razlika između 47 % i 46 % je 1 pp). U zagradama je 95 % interval. Dodir je u nekim usporedbama statistički rjeđi ili češći za prave razine; to govori samo o tome koliko cijena razine privlači, a ne da su korisne za kupnju.</p>
<h3 style="margin-top:18px">Pravila „mehanike tržišta“ u ovoj skupini</h3>
<p>Kad se isti događaji (sweep, promjena karaktera, zona potražnje, proboj strukture) izmjere na svih 55 papira u AI eri, nijedan ne pobjeđuje slučajne dane osim jednog graničnog slučaja (povratak u svježu zonu potražnje: donja granica intervala oko nule, nestaje na 20 dana i ne vrijedi u ranijim godinama). Ovdje su brojke samo za našu skupinu: višak prinosa u 10 dana u odnosu na prosječan 10-dnevni prinos istog papira, u postotnim bodovima i na 1.000 EUR, prije troškova.</p>
<div class="table-wrap"><table class="cmp"><thead><tr><th class="wrap">Događaj</th><th>Događaja u skupini</th><th>Višak prinosa, 10 dana</th><th>Na 1.000 EUR</th><th>Događaja u svih 55 papira</th></tr></thead><tbody>{"".join(ev_rows)}</tbody></table></div>
<p class="sub">Za skupinu nemamo interval pouzdanosti: s {min(ns)} do {max(ns)} događaja (svi papiri skupine zajedno, u istom razdoblju rasta) nijedan redak nije dokaz, a redaka s manje od 10 događaja ima {few} (premalo za bilo kakvo čitanje). Razine ostaju orijentir za planiranje stopa, ne dokaz prednosti.</p></section>"""


def sec_glossary() -> str:
    imported = {k: v for k, v in top10.GLOSSARY}
    own = [
        (
            "Potpora i otpor",
            "Potpora je cijena na kojoj se ranije zaustavio pad, otpor ona na kojoj se zaustavio rast. Primjer: papir je više puta pao do 100 i odbio se; 100 je potpora. Ako sada vrijedi 105, pad do potpore je oko -4,8 %, to jest oko -48 EUR na 1.000 EUR.",
        ),
        (
            "ATR",
            "Prosječni dnevni raspon cijene (najviša minus najniža, uprosječeno 14 dana). Primjer: ATR od 2 % znači da je običan dan širok oko 20 EUR na 1.000 EUR; stop uži od toga često se izbije bez razloga.",
        ),
        (
            "Okret i razina",
            "Okret je najviša (najniža) točka s 5 nižih (viših) svijeća sa svake strane, potvrđena tek 5 svijeća poslije. Okreti blizu jedan drugome spajaju se u jednu razinu.",
        ),
        (
            "Premium i diskont",
            "Raspon je od zadnjeg potvrđenog dna do zadnjeg potvrđenog vrha. Gornja polovica je premium (skuplje), donja diskont (jeftinije). Primjer: raspon 80 do 120, diskont je ispod 100.",
        ),
        (
            "Proboj strukture (BOS) i promjena karaktera",
            "Proboj strukture je zatvaranje iza zadnjeg vrha u smjeru trenda (nastavak). Promjena karaktera je zatvaranje iza zadnjeg suprotnog okreta (npr. u padu, zatvaranje iznad zadnjeg nižeg vrha): prvi znak da bi se trend mogao okrenuti. Oboje je pravilo na zatvaranju, bez gledanja u budućnost.",
        ),
        (
            "Zona potražnje i ponude",
            "Zona potražnje je raspon zadnje silazne svijeće prije snažnog skoka (barem 2 ATR u 3 svijeće koji je probio vrh); zona ponude je zrcalno. Svježa je dok se cijena nije prvi put vratila u nju.",
        ),
        (
            "Sweep (izbijanje stopova)",
            "Svijeća prođe ispod očite najniže točke (gdje su stopovi kupaca) i zatvori se natrag iznad. Primjer: dno je 100, svijeća padne do 98, a zatvori na 101.",
        ),
        (
            "Neispunjena praznina (FVG)",
            "Tri svijeće u nizu gdje najviša cijena prve ostane ispod najniže cijene treće: cijena je 'preskočila' pojas. Otvorena je dok se cijena nije vratila u pojas.",
        ),
        (
            "Pouzdanost razine",
            "Od svih dodira razine nakon njenog nastanka, koliko se puta cijena odbila za 1,5 ATR, a koliko probila. Uz manje od 5 dodira ne donosimo zaključak.",
        ),
        (
            "Očekivanje po poslu",
            "Prosječna zarada jednog posla na 1.000 EUR. Primjer: 4 posla donesu +30, -10, +20, -20 EUR; očekivanje je +5 EUR.",
        ),
        (
            "Profit factor",
            "Ukupna dobit podijeljena s ukupnim gubitkom. 1,0 znači nula, 2,0 znači dva eura dobiti na svaki izgubljeni euro.",
        ),
        (
            "Udio dobitnih poslova",
            "Koliko je poslova završilo u plusu. Primjer: 6 od 10 je 60 %. Visok udio ne znači dobit ako su gubici veliki.",
        ),
        (
            "Kupi i drži",
            "Kupiš prvi dan i ne diraš. Primjer: 1.000 EUR u papir koji se udvostruči postaje 2.000 EUR. Sve se uspoređuje s tim.",
        ),
        (
            "Trošak (bazni bod)",
            "Bazni bod je stotinka postotka. Trošak 2,5 baznih bodova po strani je 0,025 %: na 1.000 EUR to je 0,25 EUR pri kupnji i isto pri prodaji. Stres 2x i 3x ponavlja račun s dvostrukim i trostrukim troškom.",
        ),
        (
            "Placebo",
            "Lažna razina kao kontrola. Ako prave razine nisu bolje od lažnih, crtanje razina ne daje prednost.",
        ),
        (
            "Interval pouzdanosti 95 %",
            "Raspon u kojem bi se razlika vjerojatno našla da pokus ponovimo. Ako obuhvaća nulu, razlika se ne razlikuje od slučajne.",
        ),
    ]
    items = own + [
        (k, imported[k]) for k in ("AI era", "Broj pokušaja (K) i deflated Sharpe")
    ]
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in items)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def sec_eu() -> str:
    chips = [
        f'<span class="chip warn">{t}: nepotvrđeno / referentno</span>' for t in MAPPED
    ]
    chips += [
        f'<span class="chip">{t}: indeks, ne kupuje se</span>' for t in CLOSE_ONLY
    ]
    return f"""<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>
<div class="chips">{"".join(chips)}</div>
<ul>
<li><b>GLD, SLV, GDX, SMH, SOXX</b> su američki fondovi (ETF-ovi). Za male ulagače iz EU često nisu dostupni jer nemaju KID dokument (standardizirani sažetak proizvoda za male ulagače). Ovdje su samo <b>referentne serije</b>; dostupnost je <b>nepotvrđena</b> dok se ne provjeri u samom IBKR-u.</li>
<li><b>PHAU, PHAG, IGLN_LSE</b> imaju oznake koje upućuju na proizvode kotirane izvan SAD-a (IGLN_LSE na londonskoj burzi). Burza, izdavatelj, valuta i dostupnost su <b>nepotvrđeni</b>; ako se ikad razmatra izloženost zlatu ili srebru iz EU, takve europske proizvode treba provjeriti u IBKR-u (KID, burza, valuta, naknade).</li>
<li><b>SPX i NDX</b> su indeksi i ne mogu se kupiti izravno; služe samo kao mjerilo.</li>
<li>Valuta: američki fondovi kotiraju u USD, račun je u EUR. Tečaj EUR/USD i trošak konverzije su stvarni i ovdje nisu modelirani; primjeri u eurima znače da se cijena u USD tretira kao eurski iznos.</li>
<li>Porezi i dozvole računa: <b>nepotvrđeno</b>, ne nagađam. Stvarno trgovanje je zasebna Petrova odluka; ovdje agenti ne šalju nikakve naloge.</li>
</ul></section>"""


def sec_limits(c: Ctx) -> str:
    items = [
        f"Swing test pokriva samo GLD i SLV (dva papira, {hr(c.res['window']['months'], 1)} mjeseci). Za ostalih šest papira i dva indeksa nema testa pravila, samo karte.",
        "Zlato i srebro su u razdoblju testa snažno rasli pa gotovo svako pravilo koje je većinu vremena izvan tržišta zaostaje za držanjem; to ne znači da su pravila loša, nego da je mjerilo vrlo visoko.",
        "Pivoti, razine i zone izračunati su na dnevnim svijećama jednom definicijom (5 svijeća sa svake strane). Druga definicija bila bi novi pokušaj i povećala bi K.",
        "Karte koriste zadnji datum svakog papira (od 5. 10. do 13. 10. 2026.), swing test zajednički kraj 5. 10. 2026. Brojke na karti i u testu zato nisu na isti dan.",
        "Udaljenost do razine u eurima je aritmetika na 1.000 EUR: ne uključuje jaz preko noći, proklizavanje, trošak, tečaj ni poreze.",
        "Za PHAU, PHAG i IGLN_LSE valuta i točna priroda proizvoda nisu potvrđeni; nijedna tvrdnja o njima nije provjerena u javnim izvorima u ovom radu.",
        "Opis mehanizma iz odjeljka „Kako ovo tržište funkcionira“ je opći kontekst iz javnih izvora, ne rezultat ovog istraživanja.",
        f"Pokušaja u ledgeru: K = {c.summary['ledger_k']}. Što je više pokušaja, to je lakše da najbolji izgleda dobro slučajno.",
        "Prije 2023. se ne donose zaključci; razdoblje je samo kontekst jer se tržišni režim promijenio nakon 2022.",
        "Ovo su istraživačka čitanja povijesnih cijena, nisu signal ni savjet za ulaganje. Nije formalni Critic PASS; signal ostaje PRIČEKAJ.",
    ]
    return f'<section id="granice"><h2>Granice: što ovdje nije dokazano</h2><ul>{"".join(f"<li>{e(x)}</li>" for x in items)}</ul></section>'


# ---------------------------------------------------------------- build and verify


def build() -> Path:
    c = Ctx()
    win = c.res["window"]
    body = f"""<main>
<header><span class="tagline">AICHAIN · Karta tržišta · istraživačka simulacija</span>
<h1>Karta: Metali i indeksi</h1>
<p class="lead">Gdje je cijena zlata, srebra, rudnika, poluvodičkih fondova i indeksa u odnosu na svoje ranije razine, i je li se na tome dalo zarađivati čestim swing trgovanjem u AI eri (2023.–2026.).</p></header>
{sec_verdict(c)}
{sec_how(c)}
{sec_now(c)}
{sec_charts(c)}
{sec_swing(c)}
{sec_placebo(c)}
{sec_eu()}
{sec_glossary()}
{sec_limits(c)}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima (data/ohlcv): odluka na zatvaranju, kupnja na idućem otvaranju, trošak 0,025 % po strani, bez poluge i bez kratke prodaje. Glavno razdoblje je AI era ({dmy(win["ai_era"][0])} do {dmy(win["ai_era"][1])}). Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan. Status revizije: FIXED (simulator i karte neovisno provjereni i ispravljeni 14. 10. 2026.).</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(title="Karta: Metali i indeksi", css=top10.CSS + EXTRA_CSS)
    )
    page = (
        '<!doctype html>\n<html lang="hr"><head>\n'
        + head
        + "</head><body>\n"
        + body
        + "\n</body></html>"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    return OUT


def verify() -> list[str]:
    """Re-read raw JSON/CSV and check that the key numbers appear in the built page; returns mismatches."""
    page = OUT.read_text()
    bad: list[str] = []
    rows = {
        m.group(1): m.group(2)
        for m in re.finditer(r'<tr data-t="([A-Z_]+)">(.*?)</tr>', page, re.DOTALL)
    }
    for t in MAPPED:
        m = load(SWING / "map" / f"{t}.json")
        r = rows.get(t, "")
        csv = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv", parse_dates=["date"])
        if (
            abs(float(csv["close"].iloc[-1]) - m["last_close"]) > 1e-6
            or str(csv["date"].iloc[-1].date()) != m["last_date"]
        ):
            bad.append(f"{t}: map last close/date differ from CSV")
        exp = [price(t, m["last_close"]), dmy(m["last_date"]), pos_text(m)]
        for lv in m["nearest_supports"] + m["nearest_resistances"]:
            exp += [
                price(t, lv["price"]),
                pct(lv["distance_pct"], 1, True),
                eur_move(lv["distance_pct"]),
            ]
            calc = (lv["price"] / m["last_close"] - 1) * 100
            if abs(calc - lv["distance_pct"]) > 0.01:
                bad.append(
                    f"{t}: distance_pct {lv['distance_pct']} != recomputed {calc}"
                )
        for s in exp:
            if s not in r:
                bad.append(f"{t}: expected {s}")
    for t in CLOSE_ONLY:
        d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv")["close"]
        last = float(d.iloc[-1])
        for s in (hr(last, 2), pct((last / d.tail(200).mean() - 1) * 100, 1, True)):
            if s not in rows.get(t, ""):
                bad.append(f"{t}: expected {s}")
    res = load(SWING / "results" / f"{RESULT_KEY}.json")
    crow = {
        m.group(1): m.group(2)
        for m in re.finditer(r'<tr data-id="([A-Z0-9_]+)">(.*?)</tr>', page, re.DOTALL)
    }
    for cid, v in res["contenders"].items():
        a = v["ai_era"]
        r = crow.get(cid, "")
        exp = [
            f"<td>{a['trades']}</td>",
            hr(a["trades_per_month"], 2),
            hrs(a["expectancy_eur"], 1),
            hrs(a["expectancy_eur_cost_2x"], 1),
            pct(a["total_return"] * 100, 1, True),
        ]
        if a["hit_rate"] is not None:
            exp.append(pct(a["hit_rate"] * 100, 0))
        if a["profit_factor"] is not None:
            exp.append(hr(a["profit_factor"], 2))
        for s in exp:
            if s not in r:
                bad.append(f"{cid}: expected {s}")
        if cid != "B0_BUYHOLD" and v["verdict"]["eligible"] != r.endswith(
            '<td class="wrap">da</td>'
        ):
            bad.append(f"{cid}: eligibility flag mismatch")
    pl = load(SWING / "placebo.json")["sr"]["by_group"][GROUP_KEY]
    for s in (
        str(pl["n_levels"]),
        pct(pl["real"]["bounce_rate"] * 100, 1),
        pct(pl["rand"]["bounce_rate"] * 100, 1),
    ):
        if s not in page:
            bad.append(f"placebo: expected {s}")
    evs = load(SWING / "placebo.json")["mechanics_ai_era"]["events"]
    erow = {
        m.group(1): m.group(2)
        for m in re.finditer(
            r'<tr data-ev="([A-Za-z0-9_]+)">(.*?)</tr>', page, re.DOTALL
        )
    }
    for key, ev in evs.items():
        bg = ev["by_group_h10"][GROUP_KEY]
        for s in (f"<td>{bg['n']}</td>", hrs(bg["mean_excess"] * 100, 1) + " pp"):
            if s not in erow.get(key, ""):
                bad.append(f"event {key}: expected {s}")
    if res["ranking"]["ranking"] == [] and "Nitko ne ispunjava uvjete" not in page:
        bad.append("winner statement missing")
    for u in set(re.findall(r'(?:src|href)="(https?://[^"]+)"', page)):
        if not u.startswith("https://fonts.googleapis.com/"):
            bad.append(f"external resource: {u}")
    if "<script" in page:
        bad.append("script tag present")
    return bad


def main() -> None:
    out = build()
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")
    if "--verify" in sys.argv:
        bad = verify()
        print("VERIFY:", "OK, all numbers match" if not bad else "\n".join(bad))
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
