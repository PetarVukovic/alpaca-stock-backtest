"""Build the self-contained Croatian "Karta trzista" page for the AICHAIN swing group "cloud".

Usage:
  .venv/bin/python scripts/aichain_map_page_cloud.py cloud            # build the page
  .venv/bin/python scripts/aichain_map_page_cloud.py cloud --verify   # build, then re-check numbers vs raw JSON and CSV

Inputs (read only): swing/map/{T}.json + {T}.png, swing/results/{group}.json, swing/summary.json, swing/placebo.json,
swing/audit.json, segments/{group}/profile.json + analysis.json, data/ohlcv/{T}_1d.csv (verification only).
Output: swing/pages/{group}.html (charts embedded as data URIs; only Google Fonts as external resource).
The CSS tokens and a few glossary entries are imported from scripts/top10_build_artifact.py (not modified).
Never places orders. Research reading, not a signal and not a Critic PASS.
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
MINUS = "−"

GROUP_TITLE = {"cloud": "Karta: Cloud"}

EXTRA_CSS = """
.tagline{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.verdict-top{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:6px;padding:18px 20px}
.verdict-top p{font-size:1.12rem;line-height:1.5;margin:0 0 8px;max-width:none}
.verdict-top p:last-child{margin-bottom:0}
.verdict-top p.note{font-size:.92rem}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.chip{font-family:var(--mono);font-size:.78rem;padding:3px 9px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted)}
.chip.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.chip.good{background:var(--good-soft);color:var(--good);border-color:transparent}
.chip.bad{background:var(--bad-soft);color:var(--bad);border-color:transparent}
.teach{background:var(--accent-soft);border-radius:6px;padding:14px 16px;margin:0 0 14px}
.teach p{margin:0 0 8px;max-width:none}.teach p:last-child{margin:0}
.teach ul{margin:0 0 8px;padding-left:1.2em}
.teach li{margin-bottom:5px}
.plate{overflow-x:auto}
.plate img{min-width:720px}
@media (min-width:860px){.plate img{min-width:0}}
.swipe{font-size:.82rem;color:var(--muted);margin:6px 0 0}
@media (min-width:860px){.swipe{display:none}}
.tcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.tcard{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;display:flex;flex-direction:column;gap:8px;min-width:0}
.tcard h3{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:0}
.tcard p{font-size:.93rem;margin:0}
.tcard details{border:0;background:transparent}
.tcard summary{padding:4px 0;font-size:.9rem}
.tcard details li{font-size:.8rem;overflow-wrap:anywhere}
td.l,th.l{text-align:left}
td.wrap,th.wrap{white-space:normal;min-width:220px;text-align:left}
.pos{color:var(--good)}.neg{color:var(--bad)}
.read{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;margin-top:8px}
.read p{font-size:.97rem;max-width:none}
.read p:last-child{margin-bottom:0}
.read .lbl{font-family:var(--mono);font-size:.74rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);display:block;margin-bottom:2px}
.cmp tr.win td{background:var(--accent-soft)}
.cmp td:first-child{font-family:var(--display);font-weight:600}
.cmp td.small{font-size:.82rem;color:var(--muted)}
h2{margin-top:4px}
section>.lead2{color:var(--muted);max-width:66ch}
"""

# ---------------------------------------------------------------- formatting helpers


def hr(x: float, nd: int = 0) -> str:
    """Format a number the Croatian way: decimal comma, thousands dot."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def sgn(x: float, nd: int = 0) -> str:
    """Format a signed number with a real minus sign; zero after rounding gets no sign."""
    s = hr(abs(x), nd)
    if round(x, nd) == 0:
        return s
    return (MINUS if x < 0 else "+") + s


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def usd(x: float) -> str:
    return f"{hr(x, 2)} $"


def eur(x: float, nd: int = 0) -> str:
    return f"{hr(x, nd)} EUR"


def pct(x: float, nd: int = 1, sign: bool = False) -> str:
    return (sgn(x, nd) if sign else hr(x, nd)) + " %"


def dmy(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {int(m)}. {y}."


def poslova(n: int) -> str:
    """Croatian plural of 'posao' with the number: 1 posao, 2-4 posla, 5+ poslova (11-14 poslova)."""
    last, last2 = n % 10, n % 100
    word = (
        "posao"
        if last == 1 and last2 != 11
        else "posla"
        if 2 <= last <= 4 and not 12 <= last2 <= 14
        else "poslova"
    )
    return f"{hr(n)} {word}"


def euro_move(price: float, close: float) -> float:
    """Euro result on a 1.000 EUR position if the stock moves from close to price (dollar prices read as percent moves)."""
    return 1000.0 * (price / close - 1.0)


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def img_tag(path: Path, alt: str) -> str:
    return f'<img src="{top10.img(path)}" alt="{e(alt)}" loading="lazy">'


# ---------------------------------------------------------------- data


class Data:
    """All inputs of one group page, read once."""

    def __init__(self, group: str) -> None:
        self.group = group
        self.summary = load(SWING / "summary.json")
        self.g = self.summary["groups"][group]
        self.results = load(SWING / "results" / f"{group}.json")
        self.placebo = load(SWING / "placebo.json")
        self.tickers: list[str] = self.g["tickers"]
        self.maps = {t: load(SWING / "map" / f"{t}.json") for t in self.tickers}
        prof_path = BASE / "segments" / group / "profile.json"
        self.profile = load(prof_path)["tickers"] if prof_path.exists() else {}
        ana_path = BASE / "segments" / group / "analysis.json"
        self.analysis = load(ana_path) if ana_path.exists() else {}
        self.c = self.results["contenders"]
        self.ranking = self.g["ranking"]
        self.not_eligible = self.g["not_eligible"]
        self.winner: str | None = self.ranking[0]["contender"] if self.ranking else None


CONTENDER_NAME = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 sweep i promjena karaktera (iz videa)",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje (iz videa)",
    "W8_IBS_REVERT": "W8 povratak nakon slabog zatvaranja",
    "B0_BUYHOLD": "Kupi i drži (mjerilo)",
}

CONTENDER_RULE = {
    "W1_C13C_ORIG": "Kupi kad je cijena iznad prosjeka zadnjih 200 dana i u 5 dana je pala 5 % ili više. Izlaz: pomični stop 10 % ispod najvišeg vrha nakon kupnje.",
    "W2_MOM_BREAK_20": "Kupi kad je zatvaranje najviše u 20 dana (uz rast u zadnjih 60 dana i cijenu iznad 50-dnevnog prosjeka). Izlaz: zatvaranje ispod najniže iz zadnjih 10 dana, ili nakon 15 dana, ili stop 8 %.",
    "W3_MOM_RANK_WEEKLY": "Svakog petka poredaj dionice skupine po rastu u zadnjih 20 dana i drži jednu iz gornje trećine ako je iznad 50-dnevnog prosjeka. Izlaz: dionica ispadne iz gornje polovice.",
    "W4_SR_BOUNCE_V2": "Kupi kad se cijena odbije od potpore koja je već imala barem 2 dodira. Izlaz: stop ispod potpore, cilj prvi raniji vrh, najdulje 15 dana.",
    "W5_SR_BREAKOUT_RETEST": "Kupi kad cijena probije raniji vrh, vrati se na njega i odbije se. Izlaz: stop 3 % ispod probijene razine ili zatvaranje ispod 50-dnevnog prosjeka.",
    "W6_MM_SWEEP_SHIFT": "Model iz videa: tjedni trend nije medvjeđi, cijena u jeftinijoj polovici raspona, sweep (probijanje nižeg dna pa povratak), pa zatvaranje iznad zadnjeg nižeg vrha. Stop ispod sweepa, cilj raniji vrh, pola prodaje na cilju.",
    "W7_MM_DEMAND_RETEST": "Model iz videa: prvi povratak u svježu zonu potražnje uz bikovsku strukturu i cijenu u jeftinijoj polovici raspona. Stop ispod zone, cilj raniji vrh, najdulje 20 dana.",
    "W8_IBS_REVERT": "Kupi kad je dan zatvoren pri samom dnu dnevnog raspona (iznad 200-dnevnog prosjeka). Izlaz kad zatvaranje bude pri vrhu raspona ili nakon 5 dana.",
    "B0_BUYHOLD": "Kupiš prvi dan i ne prodaješ ništa.",
}

ORDER = [
    "W5_SR_BREAKOUT_RETEST",
    "W3_MOM_RANK_WEEKLY",
    "W1_C13C_ORIG",
    "W8_IBS_REVERT",
    "W2_MOM_BREAK_20",
    "W4_SR_BOUNCE_V2",
    "W6_MM_SWEEP_SHIFT",
    "W7_MM_DEMAND_RETEST",
]

EVENT_PLAIN = {
    "E1_sweep_shift_discount": "sweep + promjena karaktera u jeftinijoj polovici",
    "E2_sweep_shift_discount_weekly": "isto, uz bikovski tjedni trend",
    "E3_sweep_shift_discount_weekly_zone": "isto, uz dodir svježe zone potražnje",
    "E4_demand_zone_retest": "prvi povratak u svježu zonu potražnje",
    "E5_bos_trend": "proboj strukture u smjeru bikovskog trenda",
}

# ---------------------------------------------------------------- per-ticker text


def bias_word(b: str) -> str:
    return {"bullish": "bikovski", "bearish": "medvjeđi"}.get(b, b)


def level_reliability(lv: dict[str, Any]) -> str:
    r = lv["reliability"]
    if r["n"] == 0:
        return "još bez dodira nakon nastanka"
    if r["enough_touches"]:
        return f"odbila je {r['bounce']} od {r['n']} dodira ({pct(r['rate'] * 100, 0)})"
    return f"premalo dodira za zaključak ({r['n']})"


def nearest_fvg(m: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    close = m["last_close"]
    cands = [("bikovska", g) for g in m["open_fvg"]["bull"]] + [
        ("medvjeđa", g) for g in m["open_fvg"]["bear"]
    ]
    if not cands:
        return None
    return min(cands, key=lambda kg: abs((kg[1]["bottom"] + kg[1]["top"]) / 2 - close))


def zones_cell(m: dict[str, Any]) -> str:
    parts: list[str] = []
    for z in m["fresh_zones"]["demand"][:1]:
        parts.append(
            f"potražnja {hr(z['low'], 2)}–{hr(z['high'], 2)} $ ({pct(z['distance_pct'], 1, True)})"
        )
    for z in m["fresh_zones"]["supply"][:1]:
        parts.append(
            f"ponuda {hr(z['low'], 2)}–{hr(z['high'], 2)} $ ({pct(z['distance_pct'], 1, True)})"
        )
    nf = nearest_fvg(m)
    if nf:
        kind, g = nf
        parts.append(f"{kind} praznina {hr(g['bottom'], 2)}–{hr(g['top'], 2)} $")
    for s in m["recent_sweeps"][-1:]:
        parts.append(f"{s['direction']} {dmy(s['date'])}")
    return "; ".join(parts) if parts else "nema"


def range_text(m: dict[str, Any]) -> str:
    sr = m["swing_range"]
    z = sr["zone"]
    if z == "premium":
        return f"premium ({hr(sr['position_pct'], 0)} % raspona)"
    if z == "discount":
        return f"diskont ({hr(sr['position_pct'], 0)} % raspona)"
    if sr["position_pct"] > 100:
        return f"iznad raspona ({hr(sr['position_pct'], 0)} %)"
    return f"ispod raspona ({sgn(sr['position_pct'], 0)} %)"


def reading(m: dict[str, Any]) -> tuple[str, str]:
    """Return (what we see, what a swing trader would watch) as plain Croatian text, all numbers from the map JSON."""
    close = m["last_close"]
    w, d = m["weekly"], m["daily"]
    sr = m["swing_range"]
    sup, res = m["nearest_supports"], m["nearest_resistances"]

    if w["bias"] == d["bias"]:
        s1 = (
            f"Tjedni i dnevni trend se slažu: oba su {bias_word(w['bias'])} "
            f"({'viši vrhovi i više dno' if w['bias'] == 'bullish' else 'niži vrhovi i niže dno'} na oba vremenska okvira)."
        )
    else:
        s1 = (
            f"Tjedni i dnevni trend se ne slažu: tjedni je {bias_word(w['bias'])}, a dnevni {bias_word(d['bias'])}. "
            "Kratkoročno se cijena kreće drukčije od većeg trenda, što je često mjesto prijelaza."
        )
    ds = d.get("last_shift")
    if ds:
        s1 += (
            f" Zadnja dnevna promjena karaktera (zatvaranje iza zadnjeg suprotnog vrha ili dna) bila je {dmy(ds['date'])}, "
            f"{bias_word(ds['direction'])}, preko razine {usd(ds['broken_level'])}."
        )
    if sr["zone"] == "outside":
        above = sr["position_pct"] > 100
        s1 += (
            f" Cijena {usd(close)} je {'iznad' if above else 'ispod'} zadnjeg potvrđenog raspona {usd(sr['low'])} do {usd(sr['high'])} "
            f"({sgn(sr['position_pct'], 0)} % raspona): {'probijen je vrh' if above else 'probijeno je dno'}."
        )
    else:
        zone_word = (
            "u skupljoj polovici raspona (premium)"
            if sr["zone"] == "premium"
            else "u jeftinijoj polovici raspona (diskont)"
        )
        s1 += (
            f" Cijena {usd(close)} je {zone_word} {usd(sr['low'])} do {usd(sr['high'])}, na {hr(sr['position_pct'], 0)} % raspona "
            f"(sredina je {usd(sr['mid'])})."
        )
    if sup:
        s1 += (
            f" Najbliža potpora je {usd(sup[0]['price'])} ({pct(sup[0]['distance_pct'], 1, True)}, "
            f"{sgn(euro_move(sup[0]['price'], close))} EUR na 1.000 EUR; {level_reliability(sup[0])})."
        )
    if res:
        s1 += (
            f" Najbliži otpor je {usd(res[0]['price'])} ({pct(res[0]['distance_pct'], 1, True)}, "
            f"{sgn(euro_move(res[0]['price'], close))} EUR na 1.000 EUR; {level_reliability(res[0])})."
        )
    extra: list[str] = []
    if m["fresh_zones"]["demand"]:
        z = m["fresh_zones"]["demand"][0]
        extra.append(
            f"najbliža svježa zona potražnje je {usd(z['low'])} do {usd(z['high'])} ({pct(z['distance_pct'], 1, True)})"
        )
    if m["fresh_zones"]["supply"]:
        z = m["fresh_zones"]["supply"][0]
        extra.append(
            f"najbliža svježa zona ponude je {usd(z['low'])} do {usd(z['high'])} ({pct(z['distance_pct'], 1, True)})"
        )
    for s in m["recent_sweeps"][-2:]:
        extra.append(f"{s['direction']} na razini {usd(s['level'])} ({dmy(s['date'])})")
    if extra:
        s1 += " Još: " + "; ".join(extra) + "."

    if w["bias"] == "bullish" and d["bias"] == "bullish":
        if sr["zone"] == "discount":
            s2 = (
                "Ovo je mjesto koje model iz videa traži: trend gore na oba okvira i cijena u jeftinijoj polovici raspona. "
                f"Swing trader bi gledao hoće li se cijena održati iznad najbliže potpore ({usd(sup[0]['price'])}) i hoće li doći do prvog otpora "
                f"({usd(res[0]['price'])}). Ako potpora pukne, struktura gubi smisao."
            )
        else:
            target = sr["mid"] if sr["zone"] == "premium" else sup[0]["price"]
            s2 = (
                "Trend je gore, ali cijena je u skupljem dijelu, a model iz videa kupuje u jeftinijoj polovici raspona. "
                f"Strpljiv swing trader ne juri cijenu nego čeka povlačenje prema {usd(target)} "
                f"({pct((target / close - 1) * 100, 1, True)}), gdje bi gledao reakciju na potpori."
            )
    elif w["bias"] == "bearish" and d["bias"] == "bearish":
        s2 = (
            "Dok su oba okvira medvjeđa, dugi posao nije u skladu sa strukturom. Swing trader bi čekao da cijena zatvori iznad "
            f"{'prvog otpora ' + usd(res[0]['price']) if res else 'zadnjeg nižeg vrha'} i da se pojavi bikovska promjena karaktera, "
            "a do tada bi samo promatrao."
        )
    else:
        s2 = (
            "Okviri se razilaze, pa model iz videa ne daje čist odgovor. Swing trader bi čekao da dnevni trend opet pristane uz tjedni: "
            f"ovdje to znači povratak iznad zadnjeg raspona ({usd(sr['high'])}) ili, ako se pad nastavi, pad ispod najbliže potpore "
            f"({usd(sup[0]['price'])})."
        )
    s2 += " Ovo je čitanje grafa, ne signal; test lažnih razina (odjeljak 'Pobjeđuju li razine nasumične crte') pokazuje da razine same po sebi ne daju prednost nad slučajnošću."
    return s1, s2


# ---------------------------------------------------------------- sections


def sec_verdict(d: Data) -> str:
    w = d.c[d.winner]["ai_era"] if d.winner else None
    b0 = d.c["B0_BUYHOLD"]["ai_era"]
    n = len(d.tickers)
    wk_bull = sum(1 for m in d.maps.values() if m["weekly"]["bias"] == "bullish")
    dl_bull = sum(1 for m in d.maps.values() if m["daily"]["bias"] == "bullish")
    upper = sum(1 for m in d.maps.values() if m["swing_range"]["position_pct"] > 50)
    pb = d.placebo["sr"]["by_group"][d.group]
    if d.winner and w:
        verdict = (
            f"Skupina Cloud je strukturno uglavnom bikovska ({wk_bull} od {n} dionica tjedno, {dl_bull} od {n} dnevno), a razine s grafa se u ovim podacima "
            f"ne ponašaju bolje od nasumičnih crta; od devet testiranih algoritama najčešće trguje i uz to radi {CONTENDER_NAME[d.winner]}, "
            "ali kupi-i-drži je u istom razdoblju dao puno više."
        )
    else:
        verdict = "Nijedan algoritam u ovoj skupini ne ispunjava uvjete 'radi često'."
    tiles: list[tuple[str, str, str]] = []
    if w:
        tiles = [
            (
                hr(w["trades"]),
                f"poslova u {hr(w['months'], 0)} mjeseci (pobjednik)",
                "",
            ),
            (
                hr(w["trades_per_month"], 1),
                "poslova mjesečno, svih 7 dionica zajedno",
                "",
            ),
            (eur(w["expectancy_eur"]), "očekivanje po poslu na 1.000 EUR", "pos"),
            (pct(w["hit_rate"] * 100, 0), "poslova je dobitnih", "neg"),
            (
                eur(1000 * (1 + w["total_return"])),
                "iz 1.000 EUR po dionici: pobjednik",
                "",
            ),
            (
                eur(1000 * (1 + b0["total_return"])),
                "iz 1.000 EUR po dionici: kupi i drži",
                "pos",
            ),
        ]
    tl = "".join(
        f'<div class="fact"><b class="{c}">{e(v)}</b><span>{e(lbl)}</span></div>'
        for v, lbl, c in tiles
    )
    return f"""
<div class="verdict-top">
<p><b>{e(verdict)}</b></p>
<p class="note">Razdoblje simulacije: 3. 1. 2023. do 5. 10. 2026. (AI era). Karta razina i struktura koristi zadnji dan svakog papira (13. 10. 2026.). Trošak: 0,025 % pri svakoj kupnji i prodaji
(na 1.000 EUR to je 0,25 EUR); testirano i uz dvostruki i trostruki trošak. Ovo je istraživačka simulacija na povijesnim podacima, ne savjet, ne signal za kupnju i ne Critic PASS.
Nijedan nalog nije poslan.</p>
<p class="note">Struktura: {upper} od {n} dionica je u skupljoj polovici raspona ili iznad njega. Test lažnih razina za ovu skupinu: potvrđene razine odbijaju cijenu u {pct(pb["real"]["bounce_rate"] * 100, 1)} slučajeva, nasumične crte u {pct(pb["rand"]["bounce_rate"] * 100, 1)}.</p>
</div>
<div class="facts">{tl}</div>"""


def sec_how_to_read() -> str:
    return """
<section id="kako-citati"><h2>Kako čitati ovu kartu (rječnik s primjerima)</h2>
<div class="teach">
<p>Sve se svodi na dva pitanja: gdje je cijena u odnosu na mjesta na kojima se prije događao okret, i ide li trend gore ili dolje. Svaki pojam objašnjavam običnim riječima, a primjeri su na ulogu od <b>1.000 EUR</b>.</p>
<ul>
<li><b>Vrh i dno (okret):</b> točka koja je viša (niža) od 5 svijeća s obje strane. Potvrđuje se tek 5 svijeća kasnije, pa se nikad ne gleda u budućnost.</li>
<li><b>Struktura:</b> niz potvrđenih vrhova i dna. Viši vrhovi i viša dna = bikovski trend; niži vrhovi i niža dna = medvjeđi. Tjedna struktura daje smjer, dnevna detalje.</li>
<li><b>Proboj strukture (BOS) i promjena karaktera:</b> BOS je zatvaranje preko zadnjeg vrha u smjeru trenda (trend se nastavlja). Promjena karaktera je zatvaranje preko zadnjeg suprotnog vrha ili dna (prvi znak da se trend okreće).</li>
<li><b>Raspon, premium i diskont:</b> raspon ide od zadnjeg potvrđenog dna do vrha. Gornja polovica je premium (skuplje), donja diskont (jeftinije). Primjer: raspon 100 do 120 USD, cijena 115 USD je premium; kupnja u diskontu znači bliže 100 nego 120.</li>
<li><b>Potpora i otpor:</b> cijena na kojoj je pad (potpora) ili rast (otpor) prije stao. Pouzdanost = koliko se puta cijena od razine odbila za 1,5 ATR prije nego što ju je zatvaranjem probila za 1 ATR. Ako je dodira premalo, pouzdanost se ne računa.</li>
<li><b>ATR:</b> prosječni dnevni raspon cijene u zadnjih 14 dana. Primjer: ATR 2 % znači da je tipičan dan 20 EUR na 1.000 EUR.</li>
<li><b>Sweep (hvatanje likvidnosti):</b> cijena na trenutak probije ispod očitog dna (gdje stoje tuđi stop nalozi) pa se zatvori natrag iznad. Kod dna je to bikovski znak, kod vrha medvjeđi.</li>
<li><b>Zona potražnje (order block) i zona ponude:</b> zadnja silazna (uzlazna) svijeća prije snažnog pomaka. Svježa je dok se cijena prvi put ne vrati u nju.</li>
<li><b>Praznina (fair value gap):</b> tri svijeće u nizu u kojima se prva i treća ne dodiruju; cijena se često vrati i popuni taj razmak. Otvorena = još nije popunjena.</li>
<li><b>Euro primjer:</b> cijene su u dolarima, ali pomak u postocima primjenjujem na 1.000 EUR. Ako potpora pukne 5 %, gubitak je oko 50 EUR na 1.000 EUR. Tečaj eura i dolara nije uračunat.</li>
</ul>
<p class="note">Ove pojmove the researcher je vidio u predavanju o 'pametnom novcu'. Ovdje su pretvoreni u stroga pravila bez gledanja u budućnost i testirani pošteno; ne pretpostavljamo da rade.</p>
</div></section>"""


def sec_mechanism(d: Data) -> str:
    z = d.analysis.get("zasto_zajedno", {})
    cards = []
    for t in d.tickers:
        p = d.profile.get(t)
        if not p:
            continue
        mech = p["mehanizam_hr"]
        ai = p["windows"]["ai"]
        dd = min(x["depth"] for x in ai["drawdowns"])
        src = "".join(
            f'<li><a href="{e(u)}" rel="noopener">{e(u)}</a></li>'
            for u in mech.get("izvori", [])
        )
        cards.append(
            f"""<div class="tcard"><h3><span>{e(t)} · {e(mech["ime"])}</span></h3>
<p><b>Što prodaje:</b> {e(mech["sto_prodaje"])}</p>
<p><b>Što vozi prihod:</b> {e(mech["sto_vozi_prihod"])}</p>
<p><b>Mjesto u lancu:</b> {e(mech["mjesto_u_lancu"])}</p>
<p><b>Ciklus:</b> {e(mech["ciklus"])}</p>
<p><b>Što može naštetiti:</b> {e(mech["sto_steti"])}</p>
<div class="chips"><span class="chip">njihanje u godini {pct(ai["ann_vol"] * 100, 0)}</span><span class="chip">najgori pad u AI eri {pct(dd * 100, 0)}</span><span class="chip warn">kontekst iz javnih izvora</span></div>
<details><summary>Izvori</summary><ul>{src}</ul></details></div>"""
        )
    return f"""
<section id="mehanizam"><h2>Kako ovo tržište funkcionira</h2>
<div class="teach"><p>{e(z.get("tekst", ""))}</p><p>{e(z.get("iz_nasih_podataka", ""))}</p></div>
<p class="note">Opisi poslovanja su <b>kontekst iz javnih izvora</b> (sekundarni izvori, brojke se u izvorima razlikuju, nepotvrđeno). Njihanje i pad izračunati su iz naših dnevnih podataka (AI era od 3. 1. 2023.; NBIS od 21. 10. 2024.). Primjer: njihanje od 26 % znači da 1.000 EUR tipično pleše oko 260 EUR gore ili dolje tijekom godine.</p>
<div class="tcards">{"".join(cards)}</div></section>"""


def sec_now(d: Data) -> str:
    rows = []
    for t in d.tickers:
        m = d.maps[t]
        w, dl = m["weekly"], m["daily"]
        tone_w = "pos" if w["bias"] == "bullish" else "neg"
        tone_d = "pos" if dl["bias"] == "bullish" else "neg"
        rows.append(
            f'<tr data-t="{t}"><td class="l"><b>{t}</b></td><td>{dmy(m["last_date"])}</td><td>{hr(m["last_close"], 2)} $</td>'
            f'<td class="{tone_w}">{bias_word(w["bias"])}</td><td class="{tone_d}">{bias_word(dl["bias"])}</td>'
            f'<td class="wrap">{e(range_text(m))}</td><td class="wrap">{e(zones_cell(m))}</td></tr>'
        )
    lrows = []
    for t in d.tickers:
        m = d.maps[t]
        close = m["last_close"]
        for kind, lst in (
            ("potpora", m["nearest_supports"]),
            ("otpor", m["nearest_resistances"]),
        ):
            for lv in lst:
                mv = euro_move(lv["price"], close)
                if kind == "potpora":
                    eff = f"ako pukne: {sgn(mv)} EUR na 1.000 EUR"
                else:
                    eff = f"ako cijena stigne do otpora: {sgn(mv)} EUR na 1.000 EUR"
                tone = "neg" if kind == "potpora" else "pos"
                lrows.append(
                    f'<tr data-lv="{t}-{kind}-{round(lv["price"], 2)}"><td class="l">{t}</td><td class="l">{kind}</td><td>{hr(lv["price"], 2)} $</td>'
                    f'<td>{pct(lv["distance_pct"], 1, True)}</td><td class="wrap {tone}">{e(eff)}</td>'
                    f'<td class="wrap">{e(level_reliability(lv))}</td></tr>'
                )
    return f"""
<section id="sada"><h2>Gdje je cijena sada</h2>
<p class="lead2">Zadnji dostupni dan svake dionice je 13. 10. 2026. (zajednički kraj simulacije 5. 10. 2026. ovdje nije primijenjen jer karta opisuje trenutno stanje). Cijene su u dolarima.</p>
<div class="table-wrap"><table class="now"><thead><tr><th class="l">Dionica</th><th>Zadnji dan</th><th>Zatvaranje</th><th>Tjedna struktura</th><th>Dnevna struktura</th><th class="wrap">Položaj u rasponu</th><th class="wrap">Aktivne zone (zone, praznine, sweep)</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<h3 style="margin-top:22px">Dvije najbliže potpore i dva najbliža otpora</h3>
<p class="note">Udaljenost je u odnosu na zadnje zatvaranje. Euro primjer: pomak u postocima primijenjen na 1.000 EUR (potpora 5 % ispod = oko 50 EUR gubitka na papiru). Neke dionice imaju samo jedan otpor ili razinu koja je ujedno zadnji vrh, pa nemaju dva reda.</p>
<div class="table-wrap"><table class="lv"><thead><tr><th class="l">Dionica</th><th class="l">Vrsta</th><th>Razina</th><th>Udaljenost</th><th class="wrap">Na 1.000 EUR</th><th class="wrap">Pouzdanost razine</th></tr></thead>
<tbody>{"".join(lrows)}</tbody></table></div>
<p class="note">Pouzdanost je izmjerena izvan uzorka: razina se računa samo iz podataka koji su u tom trenutku već postojali. Razine s manje od 6 dodira ne računaju se kao pouzdane. Ni one s najviše dodira ne pobjeđuju nasumične crte (vidi odjeljak o lažnim razinama).</p>
</section>"""


def sec_charts(d: Data) -> str:
    out = []
    for t in d.tickers:
        m = d.maps[t]
        s1, s2 = reading(m)
        alt = f"{t}: karta razina i strukture, zadnji dan {dmy(m['last_date'])}"
        out.append(
            f"""<figure id="graf-{t}"><h3>{t}: karta razina i strukture</h3>
<div class="plate">{img_tag(SWING / "map" / f"{t}.png", alt)}</div>
<p class="swipe">Na mobitelu povuci graf ulijevo i udesno da vidiš sve.</p>
<div class="read"><span class="lbl">Što ovdje vidimo</span><p>{e(s1)}</p><span class="lbl">Što bi swing trader gledao</span><p>{e(s2)}</p></div></figure>"""
        )
    return f"""
<section id="grafovi"><h2>Karta po dionici</h2>
<p class="lead2">Na svakom grafu: svijeće, prosjeci 50 i 200 dana, razine (zelene su potpore ispod cijene, crvene otpori iznad), zone, praznine, oznake strukture i brojevi 1 do 4 koji odgovaraju bilješkama ispod slike.
Traka oko razine je zona dodira, a uz razinu piše koliko se puta cijena odbila.</p>
{"".join(out)}</section>"""


def contender_row(
    name: str, w: dict[str, Any], status: str, win: bool, ref: bool = False
) -> str:
    pf = w.get("profit_factor")
    cells = [
        f'<td class="l">{e(CONTENDER_NAME[name])}{" (pobjednik)" if win else ""}</td>',
        f"<td>{hr(w['trades'])}</td>",
        f"<td>{hr(w['trades_per_month'], 1)}</td>",
        "<td>–</td>" if ref else f"<td>{pct(w['hit_rate'] * 100, 0)}</td>",
        "<td>–</td>" if ref else f"<td>{sgn(w['expectancy_eur'])} EUR</td>",
        "<td>–</td>" if ref else f"<td>{sgn(w['expectancy_eur_cost_2x'])} EUR</td>",
        "<td>–</td>" if pf is None else f"<td>{hr(pf, 2)}</td>",
        "<td>–</td>"
        if ref
        else f"<td>{hr(w['median_hold_days'], 0)} / {hr(w['mean_hold_days'], 0)}</td>",
        f"<td>{sgn(w['total_return'] * 100, 0)} %</td>",
        f'<td class="wrap small">{e(status)}</td>',
    ]
    cls = ' class="win"' if win else ""
    return f'<tr data-id="{name}"{cls}>' + "".join(cells) + "</tr>"


def reason_hr(reasons: list[str]) -> str:
    out = []
    for r in reasons:
        r = r.replace("only", "samo").replace("trades (< 60)", "poslova (treba 60)")
        r = r.replace("profit factor", "faktor dobiti")
        out.append(r)
    return "nije podoban: " + "; ".join(out)


def sec_swing(d: Data) -> str:
    rest = {r["contender"]: r for r in d.not_eligible}
    ranked = [r["contender"] for r in d.ranking]
    rows = []
    for name in ORDER:
        w = d.c[name]["ai_era"]
        status = (
            f"podoban, mjesto {ranked.index(name) + 1} od {len(ranked)}"
            if name in ranked
            else reason_hr(rest[name]["reasons"])
        )
        rows.append(contender_row(name, w, status, name == d.winner))
    rows.append(
        contender_row(
            "B0_BUYHOLD",
            d.c["B0_BUYHOLD"]["ai_era"],
            "mjerilo, ne pravilo",
            False,
            ref=True,
        )
    )

    b0 = d.c["B0_BUYHOLD"]["ai_era"]
    n = len(d.tickers)
    if d.winner:
        wn = d.c[d.winner]["ai_era"]
        c2122 = d.c[d.winner]["contexts"].get("y2021_2022", {})
        pt = wn["per_ticker"]
        pt_b = b0["per_ticker"]
        prow = "".join(
            f'<tr data-pt="{t}"><td class="l">{t}</td><td>{hr(pt[t]["trades"])}</td><td>{pct(pt[t]["hit_rate"] * 100, 0)}</td>'
            f"<td>{sgn(pt[t]['expectancy_eur'])} EUR</td><td>{sgn(pt[t]['total_return'] * 100, 0)} %</td><td>{sgn(pt_b[t]['total_return'] * 100, 0)} %</td></tr>"
            for t in d.tickers
        )
        win_box = f"""
<div class="verdict-top" style="margin-top:18px">
<p><b>Pobjednik pravila 'radi često': {e(CONTENDER_NAME[d.winner])}.</b> Pravilo je upisano prije testa: podoban je algoritam s barem 60 poslova u AI eri, pozitivnim očekivanjem uz dvostruki trošak
i faktorom dobiti od barem 1,2; među podobnima pobjeđuje onaj s najvećim umnoškom očekivanja po poslu i broja poslova mjesečno.
Ovdje: {hr(wn["trades"])} poslova u {hr(wn["months"], 0)} mjeseci ({hr(wn["trades_per_month"], 1)} mjesečno za svih {n} dionica zajedno, odnosno oko {hr(wn["trades_per_ticker_year"], 1)} po dionici godišnje), očekivanje {eur(wn["expectancy_eur"])} po poslu na 1.000 EUR
(uz trošak 2x: {eur(wn["expectancy_eur_cost_2x"])}, uz 3x: {eur(wn["expectancy_eur_cost_3x"])}), faktor dobiti {hr(wn["profit_factor"], 2)}.</p>
</div>
<div class="teach"><h3>Što to znači, bez uljepšavanja</h3>
<ul>
<li><b>Većina poslova gubi.</b> Samo {pct(wn["hit_rate"] * 100, 0)} poslova je dobitno. Prosječan dobitak je {eur(wn["avg_win_eur"])}, a prosječan gubitak {eur(abs(wn["avg_loss_eur"]))} na 1.000 EUR. Pravilo zarađuje jer rijetki veliki dobici nadmašuju česte male gubitke.</li>
<li><b>Prosjek drže rijetki veliki poslovi.</b> Pet najboljih poslova nosi {pct(wn["top5_profit_share"] * 100, 0)} ukupne dobiti. Bez njih bi rezultat bio puno slabiji.</li>
<li><b>Nije uvijek 'dani do tjedana'.</b> Tipičan posao traje {hr(wn["median_hold_days"], 0)} dana, ali prosjek je {hr(wn["mean_hold_days"], 0)} dana jer pobjednički poslovi traju mjesecima. Najdulji niz uzastopnih gubitaka je {hr(wn["longest_losing_streak"])}.</li>
<li><b>Kupi i drži je jači.</b> Iz 1.000 EUR u svakoj dionici držanje daje {eur(1000 * (1 + b0["total_return"]))}, a pobjednik {eur(1000 * (1 + wn["total_return"]))} (u gotovini je {pct(100 - wn["exposure_pct"], 0)} vremena). AI era je razdoblje snažnog rasta ovih dionica, pa je držanje teško pobijediti. Ova tablica je zato o učestalosti i pouzdanosti poslova, ne o tome što je isplativije od držanja.</li>
<li><b>Raniji kontekst:</b> 2021. do 2022. (pad tržišta) isto pravilo u ovoj skupini ima {poslova(c2122.get("trades", 0))}, očekivanje {sgn(c2122.get("expectancy_eur", 0))} EUR i faktor dobiti {hr(c2122.get("profit_factor") or 0, 2)} (mali uzorak). Mjerilo ostaje AI era.</li>
<li><b>Višestruko testiranje:</b> u ledger je upisano {d.summary["ledger_k"]} pokušaja (K). Najbolji redak tablice često je dijelom sreća. Deflated Sharpe (vjerojatnost da je rezultat više od sreće; informativno) za pobjednika je {hr(wn["deflated_sharpe_prob"], 2)}, a za kupi-i-drži {hr(b0["deflated_sharpe_prob"], 2)}.</li>
</ul></div>
<h3>Isto pravilo po dionici (AI era)</h3>
<div class="table-wrap"><table><thead><tr><th class="l">Dionica</th><th>Poslova</th><th>Dobitnih</th><th>Očekivanje po poslu</th><th>Prinos pravila</th><th>Prinos držanja</th></tr></thead><tbody>{prow}</tbody></table></div>
<p class="note">Sa samo 4 do 19 poslova po dionici ovi brojevi su slabi; NBIS ima oko 490 dana podataka.</p>"""
    else:
        win_box = '<div class="verdict-top"><p><b>Nitko ne ispunjava uvjete pravila "radi često".</b></p></div>'

    rules = "".join(
        f"<li><b>{e(CONTENDER_NAME[k])}:</b> {e(CONTENDER_RULE[k])}</li>"
        for k in [*ORDER, "B0_BUYHOLD"]
    )
    w6, w7 = d.c["W6_MM_SWEEP_SHIFT"]["ai_era"], d.c["W7_MM_DEMAND_RETEST"]["ai_era"]
    return f"""
<section id="swing-test"><h2>Što je swing test pokazao za ovu skupinu</h2>
<p class="lead2">Devet pravila, svako zamrznuto i upisano u ledger prije pokretanja. Svaka dionica ima svoj 'pretinac' od 1.000 EUR, novac se među pretincima ne prelijeva. Odluka pada na zatvaranju dana, kupnja je na idućem otvaranju, samo dugo, bez poluge.
Razdoblje: 3. 1. 2023. do 5. 10. 2026. Trošak 0,025 % po strani.</p>
<div class="table-wrap"><table class="cmp"><thead><tr><th class="l">Algoritam</th><th>Poslova</th><th>Mjesečno</th><th>Dobitnih</th><th>Očekivanje po poslu</th><th>Uz trošak 2x</th><th>Faktor dobiti</th><th>Dana držanja (medijan / prosjek)</th><th>Prinos u AI eri</th><th class="wrap">Status</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="note"><b>Očekivanje po poslu</b> = prosječan prinos jednog posla primijenjen na 1.000 EUR (prosjek +2 % znači +20 EUR po poslu). <b>Faktor dobiti</b> = zbroj dobitaka podijeljen sa zbrojem gubitaka (iznad 1 zarađuje; 4 znači 4 EUR dobiti na svaki izgubljeni euro). Kupi-i-drži ima 7 'poslova' (jedna kupnja po dionici). Sve brojke su iz simulatora, bez poreza i bez tečaja.</p>
{win_box}
<div class="teach" style="margin-top:14px"><h3>Modeli iz videa (W6 i W7)</h3>
<p>Strogo pretvoreni u pravila, u ovoj skupini rade premalo: {poslova(w6["trades"])} za W6 (očekivanje {sgn(w6["expectancy_eur"])} EUR) i {poslova(w7["trades"])} za W7 (očekivanje {sgn(w7["expectancy_eur"])} EUR) u {hr(w6["months"], 0)} mjeseci. Ne dosežu minimum od 60 poslova, pa se ne ocjenjuju kao pobjednici; s tako malo poslova brojke ne dokazuju ništa.</p></div>
<details><summary>Kako točno radi svaki algoritam</summary><ul style="padding:6px 16px 14px 32px">{rules}</ul></details>
</section>"""


def sec_placebo(d: Data) -> str:
    pb = d.placebo["sr"]["by_group"][d.group]
    allp = d.placebo["sr"]["all"]
    dr = pb["diff_vs_rand"]
    lo_b, hi_b = dr["bounce_rate"]["ci95"]
    lo_k, _hi_k = dr["break_rate"]["ci95"]

    def ci(c: list[float]) -> str:
        return f"[{sgn(c[0] * 100, 1)}; {sgn(c[1] * 100, 1)}]"

    def mrow(key: str, label: str) -> str:
        r = dr[f"{key}_rate"]
        return (
            f'<tr data-m="{key}"><td class="l">{label}</td><td>{pct(pb["real"][f"{key}_rate"] * 100, 1)}</td>'
            f"<td>{pct(pb['rand'][f'{key}_rate'] * 100, 1)}</td><td>{sgn(r['diff'] * 100, 1)} pp {ci(r['ci95'])}</td></tr>"
        )

    mech_rows = []
    for key, label in EVENT_PLAIN.items():
        ev = d.placebo["mechanics_ai_era"]["events"][key]
        g = ev["by_group_h10"].get(d.group)
        if not g:
            continue
        a = ev["by_h"]["10"]
        mech_rows.append(
            f'<tr data-ev="{key}"><td class="l">{e(label)}</td><td>{hr(g["n"])}</td><td>{sgn(g["mean_excess"] * 100, 1)} pp</td>'
            f"<td>{hr(a['n'])}</td><td>{sgn(a['mean_excess_vs_ticker_avg'] * 100, 1)} pp {ci(a['excess_ci95'])}</td></tr>"
        )
    if lo_k > 0:
        break_note = "Probijanje: prave razine su u ovoj skupini probijene češće nego nasumične crte i interval ne obuhvaća nulu, pa su ovdje razine, ako išta, malo manje pouzdane od nasumičnih."
    else:
        break_note = "Probijanje se ne razlikuje značajno od nasumičnih crta."
    n_papers = len(d.placebo["universe"]["used"])
    return f"""
<section id="placebo"><h2>Pobjeđuju li razine nasumične crte u ovoj skupini?</h2>
<div class="teach"><p><b>Odgovor: ne.</b> Placebo je kontrolna skupina, kao tableta od šećera u ispitivanju lijeka. Svakoj pravoj razini (potvrđenoj okretima) dodali smo lažnu: nasumičnu cijenu u rasponu zadnjih 120 dana. Ako lažne crte daju isti rezultat, razina nije ništa posebno.
Na kraju svakog mjeseca u AI eri uzeli smo razine koje su tada već bile poznate i gledali sljedećih 20 dana.</p></div>
<div class="table-wrap"><table class="plc"><thead><tr><th class="l">Mjera</th><th>Prave razine</th><th>Nasumične crte</th><th>Razlika (95 % interval)</th></tr></thead><tbody>
{mrow("touch", "Cijena je dotaknula razinu u 20 dana")}
{mrow("bounce", "Nakon dodira odbila se za 1,5 ATR")}
{mrow("break", "Nakon dodira probila se za 1 ATR")}
</tbody></table></div>
<p class="note">{hr(pb["n_levels"])} razina u {pb["n_months"]} mjeseci. pp = postotni bod (razlika između 47 % i 46 % je 1 pp; od 100 dodira, 1 pp je jedan dodir više). Interval od 95 %: ako obuhvaća nulu, razlika se ne razlikuje od slučajne. Računat je po kalendarskim mjesecima jer se dionice istog mjeseca kreću zajedno.</p>
<p><b>Običnim riječima:</b> {e(break_note)} Odbijanje: razlika {sgn(dr["bounce_rate"]["diff"] * 100, 1)} pp s intervalom {ci([lo_b, hi_b])} obuhvaća nulu, dakle nema dokaza da prave razine odbijaju cijenu češće. Dodir: prave razine su dodirnute rjeđe nego nasumične ({sgn(dr["touch_rate"]["diff"] * 100, 1)} pp), dakle cijenu ne privlače.
Za svih {n_papers} papira zajedno rezultat je isti (odbijanje {pct(allp["real"]["bounce_rate"] * 100, 1)} prave naspram {pct(allp["rand"]["bounce_rate"] * 100, 1)} nasumične).
Razine su zato orijentir za postavljanje stopa i ciljeva, a ne dokaz prednosti. Primjer: stop 3 % ispod razine ograničava gubitak na oko 30 EUR na 1.000 EUR, ali razina sama ne jamči da će cijena tamo stati.</p>
<h3>Isto za mehaniku iz videa (višak povrata 10 dana nakon događaja)</h3>
<div class="table-wrap"><table><thead><tr><th class="l">Događaj</th><th>Cloud: broj</th><th>Cloud: višak</th><th>Svih {n_papers} papira: broj</th><th>Svih {n_papers} papira: višak i 95 % interval</th></tr></thead><tbody>{"".join(mech_rows)}</tbody></table></div>
<p class="note">Višak = povrat nakon događaja minus prosječan povrat istog papira u istom razdoblju (da rast tržišta ne laska pravilu). Primjer: ako papir u prosjeku raste 2 % u 10 dana, a nakon događaja 3 %, višak je +1 pp, odnosno 10 EUR na 1.000 EUR prije troškova. Za skupinu Cloud nema intervala (premalo događaja), pa su brojke samo orijentacijske; interval vrijedi za sve papire zajedno. U AI eri samo se 'prvi povratak u zonu potražnje' približava korisnosti, i to granično; u skupini Cloud je višak ondje praktički nula.</p>
</section>"""


def sec_eu(d: Data) -> str:
    eu = d.analysis.get("eu_hr", {})
    per = eu.get("po_tickeru", {})
    chips = "".join(
        f'<span class="chip warn">{t}: nepotvrđeno</span>' for t in d.tickers
    )
    notes = "".join(
        f"<li><b>{t}:</b> {e(per[t]['napomena'])}</li>" for t in d.tickers if t in per
    )
    return f"""
<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>
<div class="chips">{chips}</div>
<p>Svih sedam su pojedinačne dionice kotirane u SAD-u. Takve su općenito dostupne malim ulagačima iz EU preko Interactive Brokersa, ali <b>status ostaje nepotvrđen dok se ne provjeri u samom IBKR-u</b>
(točan simbol, razlomljene dionice, dozvole računa). Ništa od toga ovdje ne nagađam.</p>
<ul>{notes}</ul>
<p><b>Referentne serije (nepotvrđeno / referentno):</b> SMH (indeks čipova) i NDX (Nasdaq 100) pojavljuju se samo u profilu kao mjerilo za korelaciju i betu. To su američki ETF-ovi i indeksi koji često nisu dostupni malim EU ulagačima jer nemaju KID dokument,
pa ih ne predstavljamo kao nešto što the researcher može kupiti; umjesto njih postoje UCITS ETF-ovi na europskim burzama čiju dostupnost treba provjeriti.</p>
<p>Valuta: cijene su u USD, račun je u EUR. Pretvorba i njezin trošak su stvarni, ovdje nisu uračunati. Porezni tretman i evidencija: <b>nepotvrđeno</b>, bez poreznih tvrdnji. Zadano: bez poluge i bez kratke prodaje.
{e(eu.get("iskljuceno", ""))}</p></section>"""


def sec_limits(d: Data) -> str:
    items = [
        "Ovo su istraživačka čitanja i simulacija na povijesnim podacima, ne signal, ne savjet i ne formalni Critic PASS. Signal ostaje PRIČEKAJ; nijedan nalog (ni probni ni pravi) nije poslan.",
        "Razdoblje: simulacija 3. 1. 2023. do 5. 10. 2026. (AI era je mjerilo; ranije godine su samo kontekst, a tržišni režim se promijenio nakon 2022.). Karta razina koristi zadnji dan svakog papira, 13. 10. 2026.",
        "Sedam dionica je mali uzorak, a NBIS ima samo oko 490 dana podataka (od 21. 10. 2024.); zaključci o njemu su slabi. CRWV je izostavljen zbog prekratke povijesti.",
        "Razine, zone i strukture su pravila na dnevnim svijećama; drugi trgovac bi ih nacrtao drukčije. Ne tvrdimo da su 'prave', samo opisujemo što pravila daju i kako su se ponašala.",
        "Trošak je 0,025 % po strani (testirano i 2x i 3x). Minimalna IBKR provizija po nalogu, proklizavanje, tečaj EUR/USD, dividende i porezi nisu uračunati. Razlomljene dionice su nepotvrđene. Jaz preko noći na lošim vijestima može biti gori nego u podacima.",
        "Skupina nije portfelj: sedam pretinaca od po 1.000 EUR je ulog od 7.000 EUR, mnogo veći nego što ga ima jedan mali račun. 'Poslova mjesečno' mjeri učestalost, ne obećava zaradu.",
        "Prosjek pobjednika drže rijetki veliki poslovi (pet najboljih nosi više od dvije trećine dobiti), a većina poslova gubi.",
        f"Isprobano je više pravila na više skupina (ledger K = {d.summary['ledger_k']}); najbolji redak tablice dijelom je i sreća. Parametri nisu ugađani na ovoj skupini.",
        "Revizija: neovisni program je ponovno izračunao broj poslova, očekivanje i faktor dobiti za 13 kombinacija i sve se slaže, a test pogleda u budućnost prolazi za svih devet pravila. Status revizije: ispravljeno. Napomena: kontrolni zbroj datoteke simulatora zapisan pri registraciji nije jednak onome u trenutku pokretanja; zamrznuti parametri i tekst pravila su isti i nema dokaza da se pravilo promijenilo, ali što je točno promijenjeno ne mogu dokazati.",
        "Pojmovi iz videa (BOS, promjena karaktera, sweep, zone) ovdje su strogo, bez gledanja u budućnost, pretvoreni u pravila; diskrecijsko čitanje grafa uživo moglo bi dati drukčije zaključke.",
    ]
    return f'<section id="granice"><h2>Granice: što nije uračunato</h2><ul>{"".join(f"<li>{e(x)}</li>" for x in items)}</ul></section>'


def sec_glossary() -> str:
    g = dict(top10.GLOSSARY)
    items = [
        (
            "Pretinac",
            "Jedna dionica s vlastitih 1.000 EUR. Pretinci se ne prelijevaju. Primjer: 7 dionica = 7 pretinaca = 7.000 EUR.",
        ),
        (
            "Očekivanje po poslu",
            "Prosječan prinos jednog posla primijenjen na 1.000 EUR. Primjer: prosjek +8 % po poslu = +80 EUR po poslu, prije poreza i tečaja.",
        ),
        (
            "Faktor dobiti",
            "Zbroj dobitaka podijeljen sa zbrojem gubitaka. Primjer: 4 znači 4 EUR zarade na svaki izgubljeni euro; ispod 1 znači gubitak.",
        ),
        (
            "Kupi i drži",
            "Kupiš prvi dan i ne prodaješ. Primjer: 1.000 EUR u dionicu koja se utrostruči postaje 3.000 EUR. Sve ostalo mjeri se prema tome.",
        ),
        (
            "Stop",
            "Automatska prodaja ako cijena padne na određenu razinu. Primjer: kupnja za 1.000 EUR, stop 3 % ispod: izlaz oko 970 EUR.",
        ),
        (
            "Placebo (lažna razina)",
            "Razina nacrtana nasumično, kao kontrola. Ako prave razine nisu bolje od lažnih, crtanje razina ne daje prednost.",
        ),
    ]
    for k in (
        "AI era",
        "Prilagođeno podacima (overfitting)",
        "Broj pokušaja (K) i deflated Sharpe",
    ):
        if k in g:
            items.append((k, g[k]))
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in items)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def build(group: str) -> Path:
    d = Data(group)
    naslov = GROUP_TITLE.get(group, f"Karta: {group}")
    body = f"""<main>
<header><span class="tagline">AICHAIN · karta tržišta · {e(group)} · istraživačka simulacija</span>
<h1>Karta tržišta: {e(d.g["name"])}</h1>
<p class="lead">Gdje je cijena sada u odnosu na razine i strukturu, kako ova skupina živi i što je swing test pokazao. {e(", ".join(d.tickers))}.</p></header>
{sec_verdict(d)}
{sec_how_to_read()}
{sec_mechanism(d)}
{sec_now(d)}
{sec_charts(d)}
{sec_swing(d)}
{sec_placebo(d)}
{sec_eu(d)}
{sec_limits(d)}
{sec_glossary()}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima: odluka na zatvaranju, kupnja na idućem otvaranju, trošak 0,025 % po strani, bez poluge i bez kratke prodaje; razdoblje 3. 1. 2023. do 5. 10. 2026., karta do 13. 10. 2026.
Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje, nije signal, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan.</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(title=naslov, css=top10.CSS + EXTRA_CSS)
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


# ---------------------------------------------------------------- verification


def verify(group: str) -> list[str]:
    """Recompute page numbers from raw CSVs and JSON files and check each appears in the built page."""
    page = (SWING / "pages" / f"{group}.html").read_text()
    d = Data(group)
    bad: list[str] = []

    def need(s: str, ctx: str, scope: str = page) -> None:
        if s not in scope:
            bad.append(f"{ctx}: expected '{s}'")

    trows = {
        m.group(1): m.group(2)
        for m in re.finditer(r'<tr data-t="([A-Z]+)">(.*?)</tr>', page, re.DOTALL)
    }
    lrows = {
        x.group(1): x.group(2)
        for x in re.finditer(r'<tr data-lv="([^"]+)">(.*?)</tr>', page, re.DOTALL)
    }
    for t in d.tickers:
        with (ROOT / "data" / "ohlcv" / f"{t}_1d.csv").open() as f:
            last = list(csv.DictReader(f))[-1]
        close = float(last["close"])
        m = d.maps[t]
        if abs(close - m["last_close"]) > 1e-9 or last["date"][:10] != m["last_date"]:
            bad.append(
                f"{t}: map last bar {m['last_date']} {m['last_close']} != CSV {last['date']} {last['close']}"
            )
        need(hr(close, 2) + " $", f"{t} close", trows.get(t, ""))
        need(dmy(last["date"]), f"{t} last date", trows.get(t, ""))
        for kind, lst in (
            ("potpora", m["nearest_supports"]),
            ("otpor", m["nearest_resistances"]),
        ):
            for lv in lst:
                row = lrows.get(f"{t}-{kind}-{round(lv['price'], 2)}", "")
                if not row:
                    bad.append(f"{t} {kind} {lv['price']}: row missing")
                    continue
                dist = (lv["price"] / close - 1) * 100
                if abs(dist - lv["distance_pct"]) > 0.01:
                    bad.append(
                        f"{t} {kind}: distance_pct {lv['distance_pct']} vs recomputed {dist:.3f}"
                    )
                need(sgn(1000 * (lv["price"] / close - 1)), f"{t} {kind} euro", row)
                need(pct(lv["distance_pct"], 1, True), f"{t} {kind} dist", row)
        if f'id="graf-{t}"' not in page:
            bad.append(f"{t}: chart missing")

    crows = {
        m.group(1): m.group(2)
        for m in re.finditer(
            r'<tr data-id="([A-Z0-9_]+)"[^>]*>(.*?)</tr>', page, re.DOTALL
        )
    }
    for name, v in d.c.items():
        w = v["ai_era"]
        row = crows.get(name, "")
        need(f">{hr(w['trades'])}<", f"{name} trades", row)
        need(f">{hr(w['trades_per_month'], 1)}<", f"{name} per month", row)
        need(f">{sgn(w['total_return'] * 100, 0)} %<", f"{name} total return", row)
        if name != "B0_BUYHOLD":
            need(f">{pct(w['hit_rate'] * 100, 0)}<", f"{name} hit", row)
            need(f">{sgn(w['expectancy_eur'])} EUR<", f"{name} expectancy", row)
            need(
                f">{sgn(w['expectancy_eur_cost_2x'])} EUR<",
                f"{name} expectancy 2x",
                row,
            )
    sm = d.g["per_contender"]
    for name in ORDER:
        a, b = sm[name], d.c[name]["ai_era"]
        for k in ("trades", "expectancy_eur", "hit_rate", "profit_factor"):
            if a[k] is not None and abs(a[k] - b[k]) > 1e-9:
                bad.append(f"summary vs results {name} {k}: {a[k]} vs {b[k]}")
    # 'works often' rule recomputed from the raw numbers
    elig = [
        (w["expectancy_eur"] * w["trades_per_month"], n)
        for n in ORDER
        for w in [d.c[n]["ai_era"]]
        if w["trades"] >= 60
        and w["expectancy_eur_cost_2x"] > 0
        and w["profit_factor"] >= 1.2
    ]
    best = max(elig)[1] if elig else None
    if best != d.winner:
        bad.append(f"winner recomputed {best} vs stored {d.winner}")
    if d.winner:
        w = d.c[d.winner]["ai_era"]
        need(
            f"Pobjednik pravila 'radi često': {CONTENDER_NAME[d.winner]}", "winner box"
        )
        tot = sum(x["trades"] for x in w["per_ticker"].values())
        if tot != w["trades"]:
            bad.append(f"winner trades {w['trades']} != per-ticker sum {tot}")
        need(eur(1000 * (1 + w["total_return"])), "winner end value")
        need(
            eur(1000 * (1 + d.c["B0_BUYHOLD"]["ai_era"]["total_return"])),
            "hold end value",
        )
        for t, x in w["per_ticker"].items():
            need(
                f">{sgn(x['expectancy_eur'])} EUR<",
                f"{t} per-ticker expectancy",
                re.search(rf'<tr data-pt="{t}">(.*?)</tr>', page, re.DOTALL).group(1),
            )

    pb = d.placebo["sr"]["by_group"][group]
    prow = {
        m.group(1): m.group(2)
        for m in re.finditer(r'<tr data-m="([a-z]+)">(.*?)</tr>', page, re.DOTALL)
    }
    for key in ("touch", "bounce", "break"):
        need(
            pct(pb["real"][f"{key}_rate"] * 100, 1),
            f"placebo real {key}",
            prow.get(key, ""),
        )
        need(
            pct(pb["rand"][f"{key}_rate"] * 100, 1),
            f"placebo rand {key}",
            prow.get(key, ""),
        )
        need(
            sgn(pb["diff_vs_rand"][f"{key}_rate"]["diff"] * 100, 1) + " pp",
            f"placebo diff {key}",
            prow.get(key, ""),
        )

    ext = [
        u
        for u in re.findall(
            r'<(?:link|script|img)[^>]+(?:src|href)="(https?://[^"]+)"', page
        )
        if "fonts.googleapis.com" not in u
    ]
    if ext:
        bad.append(f"external resources other than Google Fonts: {ext}")
    if not re.search(r"<title>Karta: [^<]+</title>", page):
        bad.append("title format")
    return bad


if __name__ == "__main__":
    grp = (
        sys.argv[1]
        if len(sys.argv) > 1 and not sys.argv[1].startswith("--")
        else "cloud"
    )
    path = build(grp)
    print("built", path, f"{path.stat().st_size / 1e6:.1f} MB")
    if "--verify" in sys.argv:
        mism = verify(grp)
        print("MISMATCHES:" if mism else "verify OK: no mismatches", *mism, sep="\n")
