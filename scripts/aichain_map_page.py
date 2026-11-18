"""Build the self-contained Croatian 'Karta trzista' artifact page for one AICHAIN group.

Usage:
  .venv/bin/python scripts/aichain_map_page.py mem_interface_storage            # build the page
  .venv/bin/python scripts/aichain_map_page.py mem_interface_storage --verify   # build, then re-check numbers

Inputs (read only): swing/map/{T}.json + {T}.png, swing/results/{group}.json, swing/summary.json, swing/placebo.json,
swing/audit.json, segments/{group}/profile.json, data/ohlcv/{T}_1d.csv (last close re-check).
Output: swing/pages/{group}.html (charts embedded as data URIs; only Google Fonts as an external resource).
The CSS tokens come from scripts/top10_build_artifact.py (imported, not modified). Never places orders.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import top10_build_artifact as top10

BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SWING = BASE / "swing"
POSITION_EUR = 1000.0

EXTRA_CSS = """
.tagline{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.verdict-top{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:6px;padding:18px 20px}
.verdict-top p{font-size:1.12rem;line-height:1.5;margin:0 0 8px;max-width:none}
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
.tcard p{font-size:.93rem;max-width:none}
.tcard ul{margin:0;padding-left:1.15em;font-size:.93rem}
.tcard li{margin-bottom:4px}
td.l,th.l{text-align:left}
td.wrap{white-space:normal;min-width:210px;text-align:left;vertical-align:top;font-size:.9rem}
td.wrap.narrow{min-width:150px}
td{vertical-align:top}
.pos{color:var(--good)}.neg{color:var(--bad)}
.mini{font-size:.82rem;color:var(--muted)}
.bars{display:grid;gap:8px}
.bar-row{display:grid;grid-template-columns:minmax(120px,200px) 1fr auto;gap:10px;align-items:center;font-size:.9rem}
.bar-track{background:var(--line);border-radius:4px;height:14px;overflow:hidden}
.bar-fill{height:100%;background:var(--accent)}
.bar-fill.bh{background:var(--warn)}
.bar-fill.neg{background:var(--bad)}
@media (max-width:520px){.bar-row{grid-template-columns:1fr auto}.bar-row .bar-track{grid-column:1 / -1}}
h2{margin-top:4px}
section>.lead2{color:var(--muted);max-width:66ch}
.src a{font-size:.8rem;word-break:break-all}
"""

GROUP_ORDER = ["RMBS", "SIMO", "MRAM", "NTAP"]

CONTENDER_NAMES = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang momentuma",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore v2",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 hvatanje likvidnosti i promjena strukture (iz videa)",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje (iz videa)",
    "W8_IBS_REVERT": "W8 IBS povratak",
    "B0_BUYHOLD": "B0 kupi i drži (mjerilo)",
}

CONTENDER_RULES = {
    "W1_C13C_ORIG": (
        "Cijena je iznad prosjeka zadnjih 200 dana, a u zadnjih 5 dana pala je 5 % ili više: kupnja idući dan na otvaranju. "
        "Izlaz kad cijena padne 10 % od najvišeg zatvaranja nakon kupnje (pomični stop)."
    ),
    "W2_MOM_BREAK_20": (
        "Cijena zatvori na najvišoj razini zadnjih 20 dana, 60-dnevni prinos je pozitivan i cijena je iznad prosjeka 50 dana: kupnja idući dan. "
        "Izlaz ispod najniže cijene zadnjih 10 dana, nakon 15 dana ili kad padne 8 % od ulaza."
    ),
    "W3_MOM_RANK_WEEKLY": (
        "Svaki petak se četiri dionice poredaju po prinosu zadnjih 20 dana. Kupuje se dionica iz gornje trećine ako je iznad prosjeka 50 dana; "
        "izlaz kad ispadne iz gornje polovice popisa."
    ),
    "W4_SR_BOUNCE_V2": (
        "Kupnja nakon odbijanja od potpore koja je već imala najmanje dva dodira; stop 1 ATR ispod zone, cilj najbliži raniji vrh, najviše 15 dana."
    ),
    "W5_SR_BREAKOUT_RETEST": (
        "Cijena probije raniji vrh, vrati se do probijene razine (u roku 1,5 %) i zatvori iznad nje: kupnja idući dan. "
        "Stop 3 % ispod razine, izlaz ispod prosjeka 50 dana."
    ),
    "W6_MM_SWEEP_SHIFT": (
        "Pravilo iz videa: tjedni trend nije medvjeđi, cijena je u jeftinoj polovici raspona, pojavi se lov na stopove ispod nedavnog dna (probijanje pa zatvaranje natrag) "
        "i cijena zatvori iznad zadnjeg nižeg vrha (promjena karaktera). Stop ispod dna lova; pola pozicije se prodaje na cilju, ostatak prati stop."
    ),
    "W7_MM_DEMAND_RETEST": (
        "Pravilo iz videa: cijena se prvi put vrati u svježu zonu potražnje dok je struktura bikovska i cijena u jeftinoj polovici raspona. "
        "Stop ispod zone, cilj zadnji vrh iznad cijene."
    ),
    "W8_IBS_REVERT": (
        "IBS pokazuje gdje je zatvaranje unutar dnevnog raspona (0 = na dnu, 1 = na vrhu). Kupnja kad je ispod 0,2 i cijena je iznad prosjeka 200 dana; "
        "izlaz kad je iznad 0,8 ili nakon 5 dana."
    ),
    "B0_BUYHOLD": "Kupnja na početku razdoblja i držanje do kraja. Mjerilo, ne pravilo.",
}

EVENT_LABELS = {
    "E1_sweep_shift_discount": "lov na stopove + promjena karaktera u jeftinoj polovici raspona",
    "E2_sweep_shift_discount_weekly": "isto, uz bikovski tjedni trend",
    "E3_sweep_shift_discount_weekly_zone": "isto, uz dodir svježe zone potražnje",
    "E4_demand_zone_retest": "prvi povratak u svježu zonu potražnje (zona je držala)",
    "E5_bos_trend": "lom strukture u smjeru bikovskog trenda",
}

GLOSSARY_EXTRA = [
    (
        "Potpora i otpor (razina)",
        (
            "Cijena na kojoj se prije dogodio okret. Potpora je ispod cijene (tu je cijena stala padati), otpor je iznad (tu je stala rasti). "
            "Primjer: dionica je tri puta stala na 100 $ i krenula gore. Ako sad košta 110 $, 100 $ je potpora, 9 % ispod; na 1.000 € to je oko 91 € razlike."
        ),
    ),
    (
        "Okret (pivot) i potvrda",
        (
            "Okret je najviša ili najniža točka u odnosu na 5 svijeća sa svake strane. Zna se tek 5 svijeća poslije, pa ga stranica koristi tek tada "
            "(inače bismo gledali u budućnost)."
        ),
    ),
    (
        "Pouzdanost razine",
        (
            "Koliko se puta cijena od te razine u prošlosti odbila (za najmanje 1,5 ATR) prije nego što ju je probila (zatvaranje 1 ATR iza nje). "
            "Primjer: 'od 7 dodira odbila se 2 puta' znači da je razina držala u 2 od 7 slučajeva. Ispod 4 dodira nema smisla zaključivati."
        ),
    ),
    (
        "ATR",
        (
            "Prosječni dnevni raspon cijene (od najniže do najviše) u zadnjih 14 dana. Primjer: ATR 5 $ na dionici od 100 $ znači da cijena u danu obično prijeđe oko 5 $, "
            "dakle oko 50 € na 1.000 €."
        ),
    ),
    (
        "Struktura, lom strukture, promjena karaktera",
        (
            "Struktura je redoslijed vrhova i dna. Bikovska: svaki vrh i svako dno viši od prethodnog. Lom strukture (BOS) je zatvaranje iza zadnjeg vrha ili dna. "
            "Promjena karaktera (market shift) je zatvaranje iznad zadnjeg nižeg vrha u padajućem nizu, prvi znak da se trend možda okreće."
        ),
    ),
    (
        "Premium i discount (skupa i jeftina polovica)",
        (
            "Raspon je od zadnjeg potvrđenog dna do zadnjeg potvrđenog vrha. Iznad polovice je 'premium', ispod 'discount'. "
            "Primjer: raspon 80 $ do 100 $, polovica je 90 $; cijena 95 $ je u premiumu. Ako je cijena iznad cijelog raspona, polovica više ne opisuje ništa."
        ),
    ),
    (
        "Zona potražnje i prazan prostor (FVG)",
        (
            "Zona potražnje je zadnja padajuća svijeća prije snažnog rasta, mjesto gdje su kupci prije 'preuzeli'. Svježa je dok joj se cijena ne vrati. "
            "Prazan prostor (FVG) je trosvijećni procjep koji cijena nije 'popunila'. To su oznake iz videa, ne dokazani zakoni."
        ),
    ),
    (
        "Lov na stopove (sweep)",
        (
            "Svijeća probije raniji vrh ili dno, a zatvori natrag unutra. Priča kaže da su tamo bili stopovi koje su veliki igrači pokupili. "
            "Ovdje je to samo pravilo koje smo testirali; test nije pokazao pouzdanu prednost."
        ),
    ),
    (
        "Očekivanje po poslu, faktor dobiti, pogodak",
        (
            "Očekivanje je prosječni ishod jednog posla na 1.000 € nakon troškova: +28 € znači da je prosječni posao donio 28 €. "
            "Faktor dobiti je zbroj dobitaka / zbroj gubitaka: 1,8 znači 1,80 € dobitka na svaki izgubljeni euro. Pogodak je udio dobitnih poslova."
        ),
    ),
    (
        "Pretinac (sleeve)",
        (
            "Svaka dionica ima svoj zamišljeni pretinac od 1.000 €; poslovi se ne zbrajaju u jednu hrpu i ne reinvestiraju. "
            "Ova skupina ima 4 pretinca, dakle 4.000 € ukupno."
        ),
    ),
    (
        "Test lažnih razina (placebo)",
        (
            "Isti test napravimo s crtama koje nisu na okretima (nasumične ili pomaknute). Ako prave razine ne odbijaju cijenu češće od lažnih, "
            "razina nije dokaz prednosti, samo orijentir."
        ),
    ),
]

GLOSSARY_TOP10_KEEP = {
    "Kupi i drži",
    "Pomični stop",
    "Pad od vrha (drawdown)",
    "Sharpe",
    "Troškovi i bazni bod",
    "Gledanje u budućnost (lookahead)",
    "Broj pokušaja (K) i deflated Sharpe",
    "AI era",
}


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def hr(x: float, nd: int = 1) -> str:
    s = f"{x:,.{nd}f}"
    return s.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def hrs(x: float, nd: int = 1) -> str:
    """Signed Croatian number (explicit plus sign, true minus)."""
    s = hr(abs(x), nd)
    if x < 0 and float(s.replace(".", "").replace(",", ".")) != 0:
        return "−" + s
    return "+" + s if x > 0 else s


def eur(x: float, nd: int = 0) -> str:
    return f"{hr(x, nd)} €"


def eurs(x: float, nd: int = 0) -> str:
    return f"{hrs(x, nd)} €"


def pct(x: float, nd: int = 1) -> str:
    """Fraction to percent text."""
    return f"{hr(x * 100, nd)} %"


def pcts(x: float, nd: int = 1) -> str:
    return f"{hrs(x * 100, nd)} %"


def pp(x: float, nd: int = 1) -> str:
    return f"{hrs(x * 100, nd)} pp"


def usd(x: float) -> str:
    return f"{hr(x, 2)} $"


def dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)}. {int(m)}. {y}."


def iso_dates(text: str) -> str:
    """Rewrite ISO dates inside profile prose as Croatian dates."""
    return re.sub(r"\d{4}-\d{2}-\d{2}", lambda m: dmy(m.group(0)), text)


def load(p: Path) -> Any:
    return json.loads(p.read_text())


class Data:
    """All inputs of one group, loaded once."""

    def __init__(self, group: str) -> None:
        self.group = group
        self.summary_all = load(SWING / "summary.json")
        self.sg = self.summary_all["groups"][group]
        self.results = load(SWING / "results" / f"{group}.json")
        self.placebo = load(SWING / "placebo.json")
        self.audit = load(SWING / "audit.json")
        prof = SWING.parent / "segments" / group / "profile.json"
        self.profile = load(prof) if prof.exists() else None
        self.tickers: list[str] = list(self.sg["tickers"])
        self.maps = {t: load(SWING / "map" / f"{t}.json") for t in self.tickers}


def short_bias(s: str) -> str:
    return s.split(" (")[0]


def level_html(lv: dict[str, Any], kind: str) -> str:
    """One support/resistance cell block: price, distance, euro on 1.000 EUR, reliability."""
    dist = lv["distance_pct"]
    eur_move = POSITION_EUR * dist / 100.0
    r = lv["reliability"]
    if kind == "support":
        line = (
            f"<b>{usd(lv['price'])}</b> ({hrs(dist)} %). Ako cijena padne do ove potpore, gubitak je oko "
            f"<span class='neg'>{eur(abs(eur_move))}</span> na 1.000 €."
        )
    else:
        line = (
            f"<b>{usd(lv['price'])}</b> ({hrs(dist)} %). Ako cijena naraste do ovog otpora, razlika je oko "
            f"<span class='pos'>{eurs(eur_move)}</span> na 1.000 €."
        )
    if r["enough_touches"] and r["n"] > 0:
        rel = (
            f"Pouzdanost: od {r['n']} dodira odbila se {r['bounce']} puta ({pct(r['rate'], 0)}), "
            f"probijena {r['break']} puta. Okreta u razini: {lv['turning_points']}."
        )
    else:
        rel = f"Pouzdanost: premalo dodira ({r['n']}) za zaključak. Okreta u razini: {lv['turning_points']}."
    return f"<p>{line}<br><span class='mini'>{rel}</span></p>"


def zones_html(m: dict[str, Any]) -> str:
    parts: list[str] = []
    fz = m["fresh_zones"]
    for z in fz["demand"]:
        parts.append(
            f"Svježa zona potražnje {usd(z['low'])} do {usd(z['high'])} ({hrs(z['distance_pct'])} % od cijene), nastala {dmy(z['base_date'])}"
        )
    for z in fz["supply"]:
        parts.append(
            f"Svježa zona ponude {usd(z['low'])} do {usd(z['high'])} ({hrs(z['distance_pct'])} %)"
        )
    for f in m["open_fvg"]["bull"][:2]:
        parts.append(
            f"Otvoren prazan prostor prema gore {usd(f['bottom'])} do {usd(f['top'])} ({dmy(f['date'])})"
        )
    for f in m["open_fvg"]["bear"][:2]:
        parts.append(
            f"Otvoren prazan prostor prema dolje {usd(f['bottom'])} do {usd(f['top'])} ({dmy(f['date'])})"
        )
    for s in m["recent_sweeps"]:
        parts.append(
            f"Lov na stopove {dmy(s['date'])}: cijena je probila vrh {usd(s['level'])} pa zatvorila ispod njega (medvjeđe upozorenje)"
        )
    if not parts:
        return (
            "<span class='mini'>Nema svježih zona ni nedavnog lova na stopove.</span>"
        )
    return "<ul>" + "".join(f"<li>{e(p)}</li>" for p in parts) + "</ul>"


def position_text(m: dict[str, Any]) -> str:
    sr = m["swing_range"]
    rng = f"raspon {usd(sr['low'])} do {usd(sr['high'])}"
    if sr["zone"] == "outside":
        return f"Iznad raspona ({rng}), {hr(sr['position_pct'], 0)} % raspona. Mjerilo skupo/jeftino ovdje ne vrijedi."
    zone = (
        "skuplja polovica (premium)"
        if sr["zone"] == "premium"
        else "jeftinija polovica (discount)"
    )
    return f"{zone}, {hr(sr['position_pct'], 0)} % raspona ({rng})."


def sec_table_now(d: Data) -> str:
    rows = []
    for t in d.tickers:
        m = d.maps[t]
        w, dd = m["weekly"], m["daily"]
        shift = dd["last_shift"]
        struct = (
            f"Tjedni: {short_bias(w['bias_hr'])}<br>Dnevni: {short_bias(dd['bias_hr'])}<br>"
            f"<span class='mini'>Zadnja promjena karaktera (dnevno): {dmy(shift['date'])}, {shift['direction']}.</span>"
        )
        sup = "".join(level_html(x, "support") for x in m["nearest_supports"])
        if len(m["nearest_supports"]) < 2:
            sup += "<p class='mini'>Potvrđena je samo jedna potpora ispod cijene.</p>"
        res = "".join(level_html(x, "resistance") for x in m["nearest_resistances"])
        if not m["nearest_resistances"]:
            h = m["high_52w"]
            res = (
                f"<p>Nema potvrđenog otpora iznad cijene (nema okreta iznad). Najviša cijena 52 tjedna je <b>{usd(h['price'])}</b> "
                f"({hrs(h['distance_pct'])} %, {dmy(h['date'])}).</p>"
            )
        elif len(m["nearest_resistances"]) < 2:
            res += "<p class='mini'>Potvrđen je samo jedan otpor iznad cijene.</p>"
        rows.append(
            f"<tr><td class='wrap narrow'><b>{t}</b><br>{dmy(m['last_date'])}<br>zatvaranje <b>{usd(m['last_close'])}</b>"
            f"<br><span class='mini'>dnevno kolebanje (ATR) {hr(m['atr14_pct'])} %</span></td>"
            f"<td class='wrap narrow'>{struct}</td><td class='wrap narrow'>{e(position_text(m))}</td>"
            f"<td class='wrap'>{sup}</td><td class='wrap'>{res}</td><td class='wrap'>{zones_html(m)}</td></tr>"
        )
    last_dates = "; ".join(f"{t} {dmy(d.maps[t]['last_date'])}" for t in d.tickers)
    return f"""<section id="sada"><h2>Gdje je cijena sada</h2>
<p class="lead2">Za svaku dionicu: gdje je cijena, u kakvom je trendu, i koje su joj dvije najbliže potpore i dva najbliža otpora. Eurski iznosi su na zamišljenih 1.000 € u dionici (isti postotak pomaka; tečaj eura i dolara nije uračunat).</p>
<div class="teach"><p><b>Primjer čitanja.</b> Ako uloženih 1.000 € pada s cijenom do potpore koja je 3,3 % ispod, gubitak je oko 33 €. To je samo udaljenost do crte, ne predviđanje da će cijena tamo stići, ni da će crta držati.</p>
<p><b>Datumi.</b> Karta za svaku dionicu koristi njezin vlastiti zadnji datum u podacima: {e(last_dates)} Test algoritama (dolje) završava svima na zajedničkom datumu {dmy(d.summary_all["common_end"])}</p></div>
<div class="table-wrap"><table class="cmp"><thead><tr><th class="l">Dionica, zadnji dan</th><th class="l">Struktura</th><th class="l">Položaj u rasponu</th><th class="l">Dvije najbliže potpore</th><th class="l">Dva najbliža otpora</th><th class="l">Zone i lov na stopove</th></tr></thead><tbody>
{"".join(rows)}</tbody></table></div>
<p class="note">Cijene su u dolarima ($). Pouzdanost razina je povijesni broj dodira; vidi dio o testu lažnih razina prije nego što joj date težinu.</p></section>"""


def watch_items(m: dict[str, Any], t: str, flags: list[str]) -> list[str]:
    items: list[str] = []
    w, dd = m["weekly"], m["daily"]
    bos, shift = dd["last_bos"], dd["last_shift"]
    items.append(
        f"Struktura: tjedni trend je {short_bias(w['bias_hr'])}, dnevni {short_bias(dd['bias_hr'])}. "
        f"Zadnji lom strukture na dnevnom grafu: {dmy(bos['date'])}, {bos['direction']} (zatvaranje preko {usd(bos['broken_level'])}); "
        f"zadnja promjena karaktera: {dmy(shift['date'])}, {shift['direction']} (zatvaranje preko {usd(shift['broken_level'])})."
    )
    sr = m["swing_range"]
    if sr["zone"] == "outside":
        items.append(
            f"Položaj: cijena {usd(m['last_close'])} je iznad zadnjeg raspona ({usd(sr['low'])} do {usd(sr['high'])}). "
            f"Swing trader tada gleda drži li se iznad starog vrha {usd(sr['high'])} ili se vraća u raspon."
        )
    elif sr["zone"] == "premium":
        items.append(
            f"Položaj: cijena je u skupljoj polovici raspona (sredina je {usd(sr['mid'])}). Onaj tko po pravilu iz videa traži kupnju samo u jeftinoj polovici, "
            f"ovdje bi čekao povratak prema sredini ili ne bi ulazio."
        )
    else:
        items.append(
            f"Položaj: cijena je u jeftinijoj polovici raspona (sredina je {usd(sr['mid'])}), što je po pravilu iz videa mjesto na kojem se traži kupnja."
        )
    s1 = m["nearest_supports"][0] if m["nearest_supports"] else None
    r1 = m["nearest_resistances"][0] if m["nearest_resistances"] else None
    if s1:
        items.append(
            f"Prva potpora {usd(s1['price'])} ({hrs(s1['distance_pct'])} %, oko {eur(abs(POSITION_EUR * s1['distance_pct'] / 100))} na 1.000 €): "
            "to je mjesto gdje bi netko razmišljao o stopu. "
            + (
                f"Povijesno je držala {s1['reliability']['bounce']} od {s1['reliability']['n']} dodira."
                if s1["reliability"]["enough_touches"]
                else "Premalo dodira da bi se išta zaključilo."
            )
        )
    if r1:
        items.append(
            f"Prvi otpor {usd(r1['price'])} ({hrs(r1['distance_pct'])} %): mjesto gdje bi se prodavači mogli pojaviti, a probijanje bi se gledalo kao potvrda snage."
        )
    else:
        items.append(
            "Iznad cijene nema potvrđenog otpora: cijena je blizu najvišeg nivoa kojeg graf poznaje, pa nema crte koja bi 'branila'."
        )
    s200 = m["sma200"]
    items.append(
        f"Prosjek 200 dana je {usd(s200['value'])}; cijena je {hr(abs(s200['distance_pct']))} % "
        f"{'iznad' if s200['distance_pct'] >= 0 else 'ispod'} njega."
    )
    if m["recent_sweeps"]:
        sw = m["recent_sweeps"][-1]
        items.append(
            f"Nedavno ({dmy(sw['date'])}) cijena je probila raniji vrh {usd(sw['level'])} i zatvorila ispod njega. "
            "U priči iz videa to je 'lov na stopove' i upozorenje; test (dolje) ne pokazuje da to pouzdano nešto znači."
        )
    for f in flags:
        items.append(f"Napomena o podacima: {f}")
    return items


def sec_mechanism(d: Data) -> str:
    if not d.profile:
        return ""
    cards = []
    for t in d.tickers:
        p = d.profile["tickers"][t]
        a = p["ai_2023plus"]
        dd = a["worst_drawdowns"][0]
        src = " ".join(
            f"<a href='{e(u)}' rel='noopener'>izvor {i + 1}</a>"
            for i, u in enumerate(p["mechanism_hr"]["izvori"])
        )
        cards.append(
            f"<div class='tcard'><h3><span>{e(p['mechanism_hr']['ime'])}</span><span class='pill'>{t}</span></h3>"
            f"<p>{e(iso_dates(p['mechanism_hr']['tekst']))}</p>"
            f"<ul><li>Od 1. 1. 2023. do {dmy(a['last'])}: ukupni prinos {hr(a['total_return'] * 100, 0)} % (1.000 € bi postalo oko {hr(1000 * (1 + a['total_return']), 0)} €).</li>"
            f"<li>Godišnje kolebanje {hr(a['ann_vol'] * 100, 0)} %; najveći pad od vrha u tom razdoblju {hr(abs(dd['size']) * 100, 0)} % "
            f"({dmy(dd['start'])} do {dmy(dd['bottom'])}).</li>"
            f"<li>Osjetljivost na poluvodiče (SMH, samo referenca): beta {hr(a['beta_SMH'], 2)}, korelacija {hr(a['corr_SMH'], 2)}.</li></ul>"
            f"<p class='src'>Kontekst iz javnih izvora: {src}</p></div>"
        )
    return f"""<section id="mehanizam"><h2>Kako ovo tržište funkcionira</h2>
<p class="lead2">Prije grafova: čime ove četiri tvrtke zarađuju i što im pomaže ili šteti. Tekstovi su <b>kontekst iz javnih izvora</b> (nisu iz naših podataka); brojke ispod tekstova izračunate su iz cjenika.</p>
<div class="teach"><p><b>Beta</b> pokazuje koliko se dionica kreće uz poluvodiče: beta 1,3 znači da se dionica u prosjeku pomaknula 1,3 % kad je SMH skočio 1 %. Na 1.000 € to je oko 13 € pomaka, i prema gore i prema dolje. <b>Korelacija</b> je od −1 do +1; što je bliže 1, to se češće kreću zajedno.</p></div>
<div class="tcards">{"".join(cards)}</div></section>"""


def sec_charts(d: Data) -> str:
    out = []
    for t in d.tickers:
        m = d.maps[t]
        flags = d.profile["tickers"][t]["data_flags"] if d.profile else []
        items = "".join(f"<li>{e(x)}</li>" for x in watch_items(m, t, flags))
        full = "".join(f"<li>{e(x)}</li>" for x in m["reading"])
        img = top10.img(SWING / "map" / f"{t}.png")
        out.append(
            f"""<figure id="graf-{t}"><h3>{t}: karta razina i strukture (zadnji dan {dmy(m["last_date"])})</h3>
<div class="plate"><img src="{img}" alt="Graf {t}: svijeće, potpore (zeleno), otpori (crveno), prosjeci 50 i 200 dana, zone i oznake strukture" loading="lazy"></div>
<p class="swipe">Na telefonu graf povucite prstom ulijevo i udesno.</p>
<figcaption><b>Kako čitati graf.</b> Svaka svijeća je jedan dan. Zelena traka ispod cijene je potpora, crvena iznad je otpor; debela crta je sama razina, a traka oko nje zona dodira. Plava linija je prosjek 50 dana, crtkana prosjek 200 dana. Brojevi 1 do 4 u grafu odgovaraju objašnjenjima ispod grafa.</figcaption>
<div class="teach"><p><b>Što ovdje vidimo i što bi swing trader gledao.</b></p><ul>{items}</ul></div>
<details><summary>Sva čitanja iz karte (točne rečenice iz izračuna)</summary><div style="padding:0 16px 12px"><ul>{full}</ul></div></details></figure>"""
        )
    return f"""<section id="grafovi"><h2>Karte po dionicama</h2>
<p class="lead2">Svaka karta prikazuje otprilike zadnjih godinu dana, s razinama i zonama izračunatim samo iz podataka koji su u tom trenutku već bili poznati (okret se potvrđuje tek 5 dana nakon nastanka). To su čitanja, ne signali.</p>
{"".join(out)}</section>"""


def reason_hr(r: str) -> str:
    r = re.sub(
        r"only (\d+) trades \(< 60\)", r"samo \1 poslova (potrebno najmanje 60)", r
    )
    r = r.replace("profit factor < 1.2", "faktor dobiti ispod 1,2")
    return r


def bar_row(label: str, val: float, vmax: float, cls: str = "") -> str:
    w = max(0.0, min(100.0, abs(val) / vmax * 100))
    neg = " neg" if val < 0 else ""
    return (
        f"<div class='bar-row'><span>{e(label)}</span><div class='bar-track'><div class='bar-fill {cls}{neg}' style='width:{w:.1f}%'></div></div>"
        f"<b>{pcts(val, 0) if val < 0 else pct(val, 0)}</b></div>"
    )


def sec_swing(d: Data) -> str:
    sg = d.sg
    pc = sg["per_contender"]
    bh = sg["buy_and_hold_reference"]
    order = [x["contender"] for x in sg["ranking"]] + [
        x["contender"]
        for x in sorted(sg["not_eligible"], key=lambda r: -r["score_eur_per_month"])
    ]
    elig = {x["contender"]: (i + 1) for i, x in enumerate(sg["ranking"])}
    inel = {x["contender"]: x["reasons"] for x in sg["not_eligible"]}
    rows = []
    for c in order:
        r = pc[c]
        status = (
            f"<span class='chip good'>podoban, rang {elig[c]}</span>"
            if c in elig
            else "<span class='chip warn'>nije podoban: "
            + e("; ".join(reason_hr(x) for x in inel[c]))
            + "</span>"
        )
        rows.append(
            f"<tr><td class='wrap'><b>{e(CONTENDER_NAMES[c])}</b></td><td>{r['trades']}</td><td>{hr(r['trades_per_month'])}</td>"
            f"<td>{pct(r['hit_rate'], 0)}</td><td>{eurs(r['expectancy_eur'], 1)}</td><td>{eurs(r['expectancy_eur_cost_2x'], 1)}</td>"
            f"<td>{hr(r['profit_factor'], 2)}</td><td>{hr(r['median_hold_days'], 0)} / {hr(r['mean_hold_days'], 1)}</td>"
            f"<td>{pcts(r['total_return'], 0)}</td><td class='wrap narrow'>{status}</td></tr>"
        )
    rows.append(
        f"<tr><td class='wrap'><b>{e(CONTENDER_NAMES['B0_BUYHOLD'])}</b></td><td>1 po dionici</td><td>–</td><td>–</td><td>–</td><td>–</td><td>–</td><td>cijelo razdoblje</td>"
        f"<td>{pcts(bh['total_return'], 0)}</td><td class='wrap narrow'><span class='chip'>mjerilo, ne rangira se</span></td></tr>"
    )
    vmax = (
        max(abs(pc[c]["total_return"]) for c in order + ["B0_BUYHOLD"] if c in pc)
        if "B0_BUYHOLD" in pc
        else bh["total_return"]
    )
    vmax = max(vmax, bh["total_return"])
    bars = "".join(
        bar_row(CONTENDER_NAMES[c].split(" (")[0], pc[c]["total_return"], vmax)
        for c in order
    )
    bars += bar_row("B0 kupi i drži", bh["total_return"], vmax, "bh")
    months = pc[order[0]]["months"]
    winner = sg["ranking"][0] if sg["ranking"] else None
    ctx = d.results["contenders"]
    if winner:
        wc = winner["contender"]
        w = pc[wc]
        rob = d.summary_all["robustness_top3"]["results"].get(wc)
        c1 = ctx[wc]["contexts"]
        rob_txt = (
            f"Provjera osjetljivosti (svaki prag pomaknut za 20 %, sve dionice iz svih skupina zajedno): najgora varijanta uz dvostruki trošak ipak ima očekivanje {eurs(rob['min_expectancy_eur_cost_2x'], 1)} po poslu, pa pravilo nije krhko na pragove."
            if rob
            else ""
        )
        win_html = f"""<div class="verdict-top"><p><b>Pobjednik po unaprijed zadanom pravilu 'radi često': {e(CONTENDER_NAMES[wc])}.</b></p>
<p>{hr(w["trades_per_month"])} poslova mjesečno ({w["trades"]} poslova u oko {hr(months, 0)} mjeseci), pogodak {pct(w["hit_rate"], 0)}, prosječni dobitak {eur(w["avg_win_eur"])}, prosječni gubitak {eur(abs(w["avg_loss_eur"]))} na 1.000 €,
očekivanje {eurs(w["expectancy_eur"], 1)} po poslu (uz trošak 2x {eurs(w["expectancy_eur_cost_2x"], 1)}), faktor dobiti {hr(w["profit_factor"], 2)}, medijan držanja {hr(w["median_hold_days"], 0)} dana.
Rang-broj: očekivanje × poslova mjesečno = {eur(winner["score_eur_per_month"], 1)} mjesečno za cijelu skupinu (4 pretinca, 4.000 € ukupno).</p>
<p><b>Što taj pobjednik ne pokazuje:</b> ukupno je donio {pcts(w["total_return"], 0)}, a kupi-i-drži {pcts(bh["total_return"], 0)} u istom razdoblju (od 1.000 € po dionici: oko {eur(1000 * (1 + w["total_return"]))} naspram oko {eur(1000 * (1 + bh["total_return"]))}); u dionicama je bio samo {hr(w["exposure_pct"], 0)} % vremena.
Pet najboljih poslova drže {pct(w["top5_profit_share"], 0)} ukupne dobiti, najdulji niz gubitaka je {w["longest_losing_streak"]} poslova zaredom. Prije AI ere isto pravilo u ovoj skupini nije radilo: 2016.–2020. očekivanje {eurs(c1["y2016_2020"]["expectancy_eur"], 1)} po poslu (poslova: {c1["y2016_2020"]["trades"]}), 2021.–2022. {eurs(c1["y2021_2022"]["expectancy_eur"], 1)} (poslova: {c1["y2021_2022"]["trades"]}); to je samo kontekst.
{e(rob_txt)}</p>
<p>Ispravljena vjerojatnost da to nije puka sreća (deflated Sharpe; laboratorij je dotad isprobao {d.summary_all["ledger_k"]} varijanti pravila) iznosi samo {pct(w["deflated_sharpe_prob"], 0)}, a bez te korekcije (PSR) {pct(w["psr"], 0)}. Ovo nije formalni Critic PASS.</p></div>"""
    else:
        win_html = "<div class=\"verdict-top\"><p><b>Nitko ne ispunjava uvjete pravila 'radi često' u ovoj skupini.</b></p></div>"
    mm = [c for c in ("W6_MM_SWEEP_SHIFT", "W7_MM_DEMAND_RETEST")]
    mm_txt = (
        f"Pravila nadahnuta videom (W6 i W7) u ovoj skupini imaju samo {pc[mm[0]]['trades']} i {pc[mm[1]]['trades']} poslova u oko {hr(months, 0)} mjeseci. "
        "To je premalo za bilo kakav zaključak o njima, a ne za zaključak da rade."
    )
    return f"""<section id="swing"><h2>Što je swing test pokazao za ovu skupinu</h2>
<p class="lead2">Osam pravila koja su zapisana prije pokretanja testa, svako na svoja 4 pretinca od 1.000 €, od 1. 1. 2023. do {dmy(d.summary_all["common_end"])} (AI era, oko {hr(months, 0)} mjeseci). Odluka na zatvaranju dana, kupnja idući dan na otvaranju, trošak 0,025 % po strani (2,5 baznih bodova), uz stres 2x i 3x. Cilj nije najveći prinos nego pravilo koje <b>stvarno radi i trguje često</b>.</p>
<div class="teach"><p><b>Pravilo 'radi često'.</b> Pravilo je podobno ako ima najmanje 60 poslova u skupini, pozitivno očekivanje po poslu i uz dvostruki trošak, te faktor dobiti od najmanje 1,2. Među podobnima rang je očekivanje po poslu × broj poslova mjesečno. Kupi-i-drži se samo prikazuje kao mjerilo.</p>
<p><b>Primjer.</b> Očekivanje +28 € znači: kad bi se isti posao ponovio mnogo puta s 1.000 €, prosjek bi bio oko 28 € po poslu nakon troškova. Pojedini posao je i dalje ili znatan dobitak ili znatan gubitak.</p></div>
{win_html}
<div class="table-wrap" style="margin-top:14px"><table class="cmp"><thead><tr><th class="l">Pravilo</th><th>Poslova</th><th>Poslova / mj.</th><th>Pogodak</th><th>Očekivanje po poslu</th><th>Uz trošak 2x</th><th>Faktor dobiti</th><th>Držanje medijan / prosjek (dana)</th><th>Ukupni prinos</th><th class="l">Status</th></tr></thead><tbody>
{"".join(rows)}</tbody></table></div>
<h3 style="margin-top:18px">Ukupni prinos uz usporedbu s kupi-i-drži</h3>
<div class="bars">{bars}</div>
<p class="note">Ukupni prinos je zbroj poslova na pretincima od 1.000 €, bez reinvestiranja. Žuta traka je kupi-i-drži. Nijedno pravilo u ovoj skupini nije pobijedilo kupi-i-drži po ukupnom prinosu; pitanje nije bilo tko je zaradio najviše nego tko trguje često i ima pozitivno očekivanje.</p>
<p>{e(mm_txt)}</p>
<details><summary>Što točno svako pravilo radi</summary><div style="padding:0 16px 12px"><dl>{"".join(f"<dt>{e(CONTENDER_NAMES[c])}</dt><dd>{e(CONTENDER_RULES[c])}</dd>" for c in order)}</dl></div></details></section>"""


def ci(x: list[float]) -> str:
    return f"[{hrs(x[0] * 100)}; {hrs(x[1] * 100)}]"


def sec_placebo(d: Data) -> str:
    g = d.placebo["sr"]["by_group"][d.group]
    real, rand, mreal, match = (
        g["real"],
        g["rand"],
        g["mreal"],
        g["match"],
    )
    dr, dm = g["diff_vs_rand"], g["diff_vs_match"]

    def row(lbl: str, a: float, b: float, diff: dict[str, Any]) -> str:
        lo, hi = diff["ci95"]
        zero = (
            "obuhvaća nulu"
            if lo <= 0 <= hi
            else ("ispod nule" if hi < 0 else "iznad nule")
        )
        return f"<tr><td class='l'>{lbl}</td><td>{pct(a)}</td><td>{pct(b)}</td><td>{pp(diff['diff'])} {ci(diff['ci95'])}</td><td>{zero}</td></tr>"

    rows_a = (
        row(
            "Dodir razine u idućih 20 dana",
            real["touch_rate"],
            rand["touch_rate"],
            dr["touch_rate"],
        )
        + row(
            "Odbijanje (kad je dodirnuta)",
            real["bounce_rate"],
            rand["bounce_rate"],
            dr["bounce_rate"],
        )
        + row(
            "Probijanje (kad je dodirnuta)",
            real["break_rate"],
            rand["break_rate"],
            dr["break_rate"],
        )
    )
    rows_c = (
        row("Dodir", mreal["touch_rate"], match["touch_rate"], dm["touch_rate"])
        + row(
            "Odbijanje", mreal["bounce_rate"], match["bounce_rate"], dm["bounce_rate"]
        )
        + row("Probijanje", mreal["break_rate"], match["break_rate"], dm["break_rate"])
    )
    _lo_b, hi_b = dr["bounce_rate"]["ci95"]
    worse = hi_b < 0
    lo_c, hi_c = dm["bounce_rate"]["ci95"]
    answer = (
        f"<b>Ne.</b> U ovoj skupini potvrđene razine ne odbijaju cijenu bolje od crta koje nitko nije povukao. Prema nasumičnim crtama su čak malo slabije (odbijanje {pct(real['bounce_rate'])} naspram {pct(rand['bounce_rate'])}, interval {ci(dr['bounce_rate']['ci95'])} ne obuhvaća nulu); "
        f"prema strožoj kontroli (par lažnih crta oko prave razine) razlika {pp(dm['bounce_rate']['diff'])} {ci(dm['bounce_rate']['ci95'])} ne razlikuje se od nule."
        if worse and lo_c <= 0 <= hi_c
        else f"Odbijanje: prave razine {pct(real['bounce_rate'])}, nasumične crte {pct(rand['bounce_rate'])}; pogledajte tablice."
    )
    pe = d.placebo["mechanics_ai_era"]["events"]
    erows = []
    for k, lab in EVENT_LABELS.items():
        ev = pe[k]
        grp = ev["by_group_h10"][d.group]
        allh = ev["by_h"]["10"]
        lo, hi = allh["excess_ci95"]
        b3 = d.audit["event_block_bootstrap"][k]["10"]["ci95_block_3"]
        if lo <= 0 <= hi:
            verdict_all = "ne razlikuje se od slučajnosti"
        elif b3[0] <= 0 <= b3[1]:
            verdict_all = (
                "granično; stroža provjera (blokovi od 3 mjeseca) obuhvaća nulu"
            )
        else:
            verdict_all = "bolje od prosjeka" if lo > 0 else "lošije od prosjeka"
        small = " (premalo događaja)" if grp["n"] < 30 else ""
        erows.append(
            f"<tr><td class='wrap'>{e(lab)}</td><td>{grp['n']}{small}</td><td>{pp(grp['mean_excess'])} ({eurs(grp['mean_excess'] * POSITION_EUR)} na 1.000 €)</td>"
            f"<td>{allh['n']}</td><td>{pp(allh['mean_excess_vs_ticker_avg'])} {ci(allh['excess_ci95'])}</td><td class='wrap narrow'>{verdict_all}</td></tr>"
        )
    e4 = d.audit["event_block_bootstrap"]["E4_demand_zone_retest"]["10"]["ci95_block_3"]
    return f"""<section id="placebo"><h2>Drže li razine bolje od nasumičnih crta?</h2>
<p class="lead2">Najvažnije pitanje o 'potporama i otporima': je li razina stvarno posebno mjesto, ili bi svaka crta na istoj udaljenosti odbila cijenu jednako često? Zato smo uz prave razine na isti način testirali lažne.</p>
<div class="verdict-top"><p>{answer}</p></div>
<div class="teach"><p><b>Kako smo mjerili.</b> Zadnji dan svakog mjeseca u AI eri uzeli smo razine koje su tada već bile poznate ({hr(g["n_levels"], 0)} razina u ovoj skupini, {g["n_months"]} mjesečnih presjeka) i gledali idućih 20 dana. 'Odbijanje' je potez od najmanje 1,5 ATR od razine, 'probijanje' zatvaranje više od 1 ATR iza nje.</p>
<p><b>Primjer.</b> Od 100 razina koje je cijena dotakla, njih oko {hr(real["bounce_rate"] * 100, 0)} se odbilo; od 100 nasumično povučenih crta koje je cijena dotakla, njih oko {hr(rand["bounce_rate"] * 100, 0)}. Da razine nešto znače, prve bi trebale biti više. Interval u zagradi je 95 % raspon u kojem bi se razlika vjerojatno našla kad bismo pokus ponovili; ako obuhvaća nulu, razlika se ne razlikuje od slučajne. pp je postotni bod.</p></div>
<h3>Kontrola (a): nasumične crte u rasponu zadnjih 120 dana</h3>
<div class="table-wrap"><table><thead><tr><th class="l">Mjera</th><th>Prave razine</th><th>Lažne crte</th><th>Razlika (pp) [95 % interval]</th><th>Interval</th></tr></thead><tbody>{rows_a}</tbody></table></div>
<h3 style="margin-top:16px">Kontrola (c): par lažnih crta oko razine (najstroža)</h3>
<div class="table-wrap"><table><thead><tr><th class="l">Mjera</th><th>Prave razine</th><th>Lažne crte</th><th>Razlika (pp) [95 % interval]</th><th>Interval</th></tr></thead><tbody>{rows_c}</tbody></table></div>
<p class="note">Pošteno upozorenje: ovo je jedna od 8 skupina i testirano je više mjera, pa se pojedini 'značajni' redak može dogoditi slučajno. Cijela slika (svih 55 papira, {hr(d.placebo["sr"]["all"]["n_levels"], 0)} razina) također ne pokazuje da razine pobjeđuju slučajnost.</p>
<h3 style="margin-top:16px">Pravila 'tržišne mehanike' iz videa, 10 dana nakon događaja (AI era)</h3>
<p>Višak je prinos nakon događaja minus prosječan prinos iste dionice u običan dan. Prvi stupac brojeva je za ovu skupinu, drugi za svih 55 papira.</p>
<div class="table-wrap"><table><thead><tr><th class="l">Događaj</th><th>Događaja u skupini</th><th>Višak u skupini</th><th>Događaja, svi papiri</th><th>Višak, svi papiri [95 % interval]</th><th class="l">Čitanje</th></tr></thead><tbody>{"".join(erows)}</tbody></table></div>
<p class="note">Jedini događaj koji u ovoj skupini izgleda dobro (povratak u svježu zonu potražnje) ima samo {pe["E4_demand_zone_retest"]["by_group_h10"][d.group]["n"]} događaja u skupini; kad se gleda cijeli uzorak, višak je granično iznad nule, a stroža provjera s blokovima od 3 mjeseca daje interval {ci(e4)} koji obuhvaća nulu. U godinama prije AI ere isti događaj nije pokazao istu prednost. Zaključak: razine i oznake iz videa korisne su kao orijentir za crtanje stopa i ciljeva, ne kao dokaz prednosti.</p></section>"""


def sec_eu(d: Data) -> str:
    return """<section id="eu"><h2>Dostupnost iz Hrvatske (EU) i valuta</h2>
<div class="teach">
<p><b>Pojedinačne dionice (RMBS, SIMO, MRAM, NTAP).</b> Američke pojedinačne dionice su općenito dostupne klijentima iz EU preko Interactive Brokersa, ali dostupnost svake pojedine dionice na Petrovu računu je <span class="chip warn">nepotvrđeno</span>: provjeriti u Interactive Brokersu prije bilo kakvog zaključka. Dozvole računa i porez nisu pretpostavljeni.</p>
<p><b>MRAM je tanka dionica</b> (malo prometa, veliki rasponi cijena): stvarni trošak ulaska i izlaska vjerojatno je veći od 0,025 % korištenih u testu. Stres 3x je bliža procjena nego osnovni trošak.</p>
<p><b>SMH (poluvodiči)</b> pojavljuje se samo kao referentna serija u mjerenju osjetljivosti (beta). Američki ETF-ovi često nisu dostupni malim ulagačima iz EU (nema KID dokumenta): <span class="chip warn">nepotvrđeno / referentno</span>, nije prijedlog za kupnju. Indeksi (NDX, SPX) ovdje služe samo kao oznake i nisu predmet testa.</p>
<p><b>Valuta.</b> Cijene su u dolarima, račun je u eurima. Eurski primjeri na ovoj stranici su postotni pomak primijenjen na 1.000 €; tečaj eura i dolara i trošak konverzije nisu uračunati i mogu pomaknuti stvarni rezultat u oba smjera.</p>
<p><b>Vrijeme.</b> Američka burza otvara u 15:30 po zagrebačkom vremenu; podaci su dnevni, pa dnevno kolebanje unutar dana nije vidljivo.</p></div></section>"""


def sec_glossary() -> str:
    base = [g for g in top10.GLOSSARY if g[0] in GLOSSARY_TOP10_KEEP]
    dl = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in GLOSSARY_EXTRA + base)
    return f'<section id="rjecnik"><h2>Rječnik, jednostavnim riječima</h2><details><summary>Otvori rječnik izraza</summary><div style="padding:0 16px 14px"><dl>{dl}</dl></div></details></section>'


def sec_limits(d: Data) -> str:
    sg = d.sg
    pc = sg["per_contender"]
    k = d.summary_all["ledger_k"]
    dates = ", ".join(f"{t} {dmy(d.maps[t]['last_date'])}" for t in d.tickers)
    pm = d.placebo
    n_months = pm["sr"]["by_group"][d.group]["n_months"]
    return f"""<section id="granice"><h2>Granice ovog istraživanja</h2><ul>
<li><b>Nije signal ni savjet.</b> Ovo su istraživačka čitanja povijesnih podataka. Ništa na stranici nije preporuka kupnje ili prodaje, nije formalni Critic PASS, i nijedan nalog (ni probni ni pravi) nije poslan.</li>
<li><b>Razdoblje i trošak.</b> Test: 1. 1. 2023. do {dmy(d.summary_all["common_end"])} (oko {hr(pc["W1_C13C_ORIG"]["months"], 0)} mjeseci), odluka na zatvaranju, kupnja idući dan na otvaranju, 0,025 % po strani (stres 2x i 3x), bez poluge, samo dugo. Karte koriste zadnji datum svake dionice ({e(dates)}).</li>
<li><b>Mala skupina.</b> Samo 4 dionice i 4 pretinca; razdoblje je razdoblje snažnog rasta čipova (AI era), što pomaže pravilima koja kupuju snagu. Rezultat u drugom razdoblju može biti drukčiji; za 2016.–2020. isto pravilo u ovoj skupini imalo je negativno očekivanje, a za 2021.–2022. blizu nule.</li>
<li><b>Koncentracija dobiti.</b> Kod pobjednika pet najboljih poslova drži {pct(pc["W1_C13C_ORIG"]["top5_profit_share"], 0)} dobiti, pa prosjek visi na malo velikih poslova. Poslovi koji gube češće su od dobitnih ({pct(1 - pc["W1_C13C_ORIG"]["hit_rate"], 0)} gubi).</li>
<li><b>Mnogo pokušaja.</b> Laboratorij je isprobao {k} varijanti pravila; što više pokušaja, to veća šansa da jedno izgleda dobro slučajno (deflated Sharpe pobjednika je samo {pct(pc["W1_C13C_ORIG"]["deflated_sharpe_prob"], 0)}). Ovdje se ne spušta ocjena zbog pada ili kolebanja, ali se strogo gleda dokaz.</li>
<li><b>Razine su orijentir.</b> Pouzdanost razina temelji se na malom broju dodira (često 2 do 8), a test lažnih razina ({n_months} mjesečnih presjeka, {hr(pm["sr"]["by_group"][d.group]["n_levels"], 0)} razina) ne pokazuje da su bolje od nasumičnih.</li>
<li><b>Podaci.</b> Samo dnevne cijene iz lokalnih datoteka. SIMO ima dva zabilježena neobična dana (skok od +45,8 % 29. 4. 2026. koji je u javnim izvorima povezan sa zaradom, i neprovjeren jaz od +80 % na otvaranju 26. 7. 2023.); MRAM ima tri skoka veća od 40 % u tankoj trgovini. PSTG je isključen iz skupine zbog zastarjelih podataka.</li>
<li><b>Revizija: ispravljeno.</b> Simulator i brojke su neovisno provjereni 14. 10. 2026. Hash datoteke s pravilima promijenjen je nakon upisa registracije (sam sadržaj zamrznutih pravila jednak je registru, a neovisni izračun se slaže), pa treba reći da točnu promjenu ne možemo dokazati.</li>
</ul></section>"""


def build(group: str) -> Path:
    d = Data(group)
    pc = d.sg["per_contender"]
    bh = d.sg["buy_and_hold_reference"]
    bulls = sum(
        1
        for t in d.tickers
        if "bikovski" in d.maps[t]["weekly"]["bias_hr"]
        and "bikovski" in d.maps[t]["daily"]["bias_hr"]
    )
    gp = d.placebo["sr"]["by_group"][group]
    bulls_txt = (
        "Sve četiri dionice su"
        if len(d.tickers) == 4
        else f"Sve {len(d.tickers)} dionice su"
        if bulls == len(d.tickers)
        else f"{bulls} od {len(d.tickers)} dionica su"
    )
    win = d.sg["ranking"][0] if d.sg["ranking"] else None
    if win:
        wc = win["contender"]
        w = pc[wc]
        win_txt = (
            f"najčešće pravilo koje ispunjava uvjete ({CONTENDER_NAMES[wc].split(' (')[0]}) trguje {hr(w['trades_per_month'])} puta mjesečno s očekivanjem {eurs(w['expectancy_eur'], 1)} po poslu na 1.000 €, "
            f"ali je od 1. 1. 2023. donijelo {pcts(w['total_return'], 0)} naspram {pcts(bh['total_return'], 0)} za kupi-i-drži"
        )
    else:
        win_txt = "nijedno pravilo ne ispunjava uvjete 'radi često'"
    verdict = (
        f"{bulls_txt} u bikovskom (uzlaznom) trendu i na tjednom i na dnevnom grafu, ali razine na kartama su orijentir, ne dokaz: "
        f"potvrđene potpore i otpori u ovoj skupini ne odbijaju cijenu bolje od nasumičnih crta (odbijanje {pct(gp['real']['bounce_rate'])} naspram {pct(gp['rand']['bounce_rate'])}), a {win_txt}."
    )
    title = "Karta: Sučelja i pohrana"
    names = ", ".join(d.tickers)
    body = f"""<main>
<header><span class="tagline">AICHAIN · karta tržišta · istraživačka simulacija</span>
<h1>{e(title)}</h1>
<p class="lead">Gdje su cijene RMBS, SIMO, MRAM i NTAP u odnosu na svoje potpore, otpore i trend, i je li swing trgovanje na tim razinama u AI eri (2023.–2026.) uopće imalo prednost pred slučajnošću.</p></header>
<div class="chips"><span class="chip">istraživanje, ne savjet</span><span class="chip">AI era od 1. 1. 2023.</span><span class="chip">trošak 0,025 % po strani</span><span class="chip">samo dugo, bez poluge</span><span class="chip good">revizija: ispravljeno</span></div>
<section id="presuda"><h2>Presuda u jednoj rečenici</h2><div class="verdict-top"><p>{e(verdict)}</p></div>
<p class="note">Dionice: {e(names)}. Sve brojke na stranici izračunate su iz dnevnih cjenika; nijedna nije izmišljena. Ovo je istraživačka simulacija na povijesnim podacima, ne obećava buduće rezultate.</p></section>
{sec_mechanism(d)}
{sec_table_now(d)}
{sec_charts(d)}
{sec_swing(d)}
{sec_placebo(d)}
{sec_eu(d)}
{sec_limits(d)}
{sec_glossary()}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima (2023.–2026., trošak 0,025 % po strani, stres 2x i 3x), bez poluge i bez kratke prodaje. Rezultati iz prošlosti ne obećavaju buduće.
Ovo nije savjet za ulaganje, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan. Status revizije: ispravljeno (neovisna provjera 14. 10. 2026.).</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(title=title, css=top10.CSS + EXTRA_CSS)
    )
    page = (
        '<!doctype html>\n<html lang="hr"><head>\n'
        + head
        + "</head><body>\n"
        + body
        + "\n</body></html>"
    )
    out_dir = SWING / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{group}.html"
    out.write_text(page)
    return out


def csv_last_close(t: str) -> tuple[str, float]:
    with (ROOT / "data" / "ohlcv" / f"{t}_1d.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    return rows[-1]["date"], float(rows[-1]["close"])


def verify(group: str) -> list[str]:
    """Re-read raw JSON/CSV independently and check that each number is in the page text. Returns mismatches."""
    page = (SWING / "pages" / f"{group}.html").read_text()
    text = html.unescape(
        re.sub(
            r"<[^>]+>", " ", re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", page)
        )
    )
    text = re.sub(r"\s+", " ", text)
    summ = load(SWING / "summary.json")["groups"][group]
    res = load(SWING / "results" / f"{group}.json")
    bad: list[str] = []

    def need(label: str, s: str) -> None:
        if s not in text:
            bad.append(f"{label}: missing '{s}'")

    for c, v in res["contenders"].items():
        if c == "B0_BUYHOLD":
            continue
        a = v["ai_era"]
        s = summ["per_contender"][c]
        for key in (
            "trades",
            "expectancy_eur",
            "profit_factor",
            "total_return",
            "hit_rate",
        ):
            if abs(a[key] - s[key]) > 1e-9:
                bad.append(f"results vs summary differ: {c}.{key}")
        need(f"{c} trades", f"{a['trades']}")
        need(f"{c} expectancy", eurs(a["expectancy_eur"], 1))
        need(f"{c} pf", hr(a["profit_factor"], 2))
        need(f"{c} total return", pcts(a["total_return"], 0))
        need(f"{c} tpm", hr(a["trades_per_month"]))
    bh = summ["buy_and_hold_reference"]
    need("B0 return", pcts(bh["total_return"], 0))
    for t in summ["tickers"]:
        m = load(SWING / "map" / f"{t}.json")
        dt, close = csv_last_close(t)
        if dt != m["last_date"] or abs(close - m["last_close"]) > 1e-9:
            bad.append(
                f"{t}: CSV last {dt} {close} differs from map {m['last_date']} {m['last_close']}"
            )
        need(f"{t} close", usd(close))
        need(f"{t} date", dmy(dt))
        for lv in m["nearest_supports"] + m["nearest_resistances"]:
            need(f"{t} level", usd(lv["price"]))
            need(f"{t} eur", eur(abs(POSITION_EUR * lv["distance_pct"] / 100)))
    p = load(SWING / "placebo.json")["sr"]["by_group"][group]
    need("placebo bounce real", pct(p["real"]["bounce_rate"]))
    need("placebo bounce rand", pct(p["rand"]["bounce_rate"]))
    need("placebo n_levels", hr(p["n_levels"], 0))
    wins = summ["ranking"][0]
    need("winner score", eur(wins["score_eur_per_month"], 1))
    return bad


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    group = args[0] if args else "mem_interface_storage"
    out = build(group)
    print(out, out.stat().st_size)
    if "--verify" in sys.argv:
        bad = verify(group)
        print("VERIFY:", "OK" if not bad else "\n".join(bad))
        if bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
