"""Build the self-contained Croatian 'Karta trzista' artifact page for the crypto swing group.

Usage:
  .venv/bin/python scripts/aichain_map_page_crypto.py            # build the page
  .venv/bin/python scripts/aichain_map_page_crypto.py --verify   # build, then re-read numbers vs the JSON files

Inputs (read only): reports/research/AICHAIN_20261014/swing/{map/*.json, map/*.png, results/crypto.json,
summary.json, placebo.json, audit.json}. Output: swing/pages/crypto.html with the charts embedded as data URIs;
the only external resource is Google Fonts. Never places orders.
CSS and glossary entries are imported from scripts/top10_build_artifact.py (not modified). This is a separate file
from scripts/aichain_map_page.py (owned by another group's run) so the two never overwrite each other.
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

import top10_build_artifact as top10

from lab.aichain.notebook_charts import hr

SWING = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing"
GROUP = "crypto"

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
.tcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.tcard{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;display:flex;flex-direction:column;gap:8px;min-width:0}
.tcard h3{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:0}
.tcard p{font-size:.95rem;margin:0}
td.l,th.l{text-align:left}
td.wrap{white-space:normal;min-width:200px;vertical-align:top;font-size:.9rem;line-height:1.45}
td.wrap small{color:var(--muted);display:block}
.pos{color:var(--good)}.neg{color:var(--bad)}
.map-table{min-width:980px}
.contenders{min-width:900px}
.rowwin td{background:var(--good-soft)}
.read{border-top:1px solid var(--line);padding-top:10px}
.read h4{font-family:var(--display);font-size:.95rem;margin:12px 0 4px}
.read ul{margin:0 0 8px;padding-left:1.2em}
.read li{margin-bottom:4px;max-width:70ch}
.tick-h{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;margin-bottom:6px}
section>.lead2{color:var(--muted);max-width:66ch}
.small{font-size:.88rem;color:var(--muted)}
"""

NAMES = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 hvatanje likvidnosti i promjena strukture",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
    "B0_BUYHOLD": "Kupi i drži (mjerilo)",
}

RULES = {
    "W1_C13C_ORIG": "Kupi kad je cijena iznad prosjeka zadnjih 200 dana i u 5 dana je pala 5 % ili više. Prodaj kad cijena padne 10 % ispod najvišeg vrha nakon kupnje.",
    "W2_MOM_BREAK_20": "Kupi sutradan na otvaranju kad je današnje zatvaranje najviše u zadnjih 20 dana, prinos zadnjih 60 dana je pozitivan i cijena je iznad prosjeka zadnjih 50 dana. "
    "Izlaz: zatvaranje ispod najniže cijene prethodnih 10 dana, ili nakon 15 dana, ili stop 8 % ispod ulaza.",
    "W3_MOM_RANK_WEEKLY": "Svake nedjelje poredaj kovanice po prinosu zadnjih 20 dana; kupi onu iz gornje trećine ako je iznad prosjeka 50 dana; prodaj kad ispadne iz gornje polovice.",
    "W4_SR_BOUNCE_V2": "Kupi odbijanje od potpore koju je cijena već dodirnula barem dva puta; stop 1 ATR ispod zone, cilj je najbliži raniji vrh iznad, najdulje 15 dana.",
    "W5_SR_BREAKOUT_RETEST": "Kupi kad cijena probije raniji vrh, vrati se na probijenu razinu i odbije se; izlaz ispod prosjeka 50 dana ili stop 3 % ispod razine.",
    "W6_MM_SWEEP_SHIFT": "Tjedni trend nije medvjeđi, cijena je u jeftinijoj polovici raspona, nedavno je probijeno i vraćeno donje dno (lov na stopove), a zatvaranje iznad zadnjeg nižeg vrha je okidač. Stop ispod dna probijanja, pola se prodaje na cilju.",
    "W7_MM_DEMAND_RETEST": "Kupi prvi povratak cijene u svježu zonu potražnje, ako je struktura bikovska i cijena u jeftinijoj polovici raspona. Stop ispod zone, cilj zadnji vrh, najdulje 20 dana.",
    "W8_IBS_REVERT": "Kupi kad dnevno zatvaranje završi u donjih 20 % dnevnog raspona i cijena je iznad prosjeka 200 dana; prodaj kad završi u gornjih 20 % ili nakon 5 dana.",
    "B0_BUYHOLD": "Kupi prvi dan razdoblja i ne prodaješ ništa.",
}

REASONS = {
    "profit factor < 1.2": "faktor dobiti ispod 1,2",
    "expectancy <= 0 at cost 2x": "očekivanje uz dvostruki trošak nije pozitivno",
}

# Mechanism context from public general knowledge (NOT computed from the CSVs); kept qualitative on purpose.
MECHANISM = {
    "BTCUSDT": (
        "Bitcoin",
        "Najstarija i najveća kriptovaluta. Nema tvrtku iza sebe ni zarade: cijenu određuju ponuda i potražnja, priča o 'digitalnom zlatu' i priljev novca velikih ulagača. "
        "Količina je unaprijed ograničena, a otprilike svake četiri godine proizvodnja novih novčića se prepolovi.",
    ),
    "ETHUSDT": (
        "Ethereum",
        "Mreža na kojoj rade aplikacije i ugovori. Ether se plaća kao naknada za korištenje mreže, pa potražnja dijelom ovisi o tome koliko se mreža koristi. "
        "Obično se kreće u smjeru bitcoina, ali s većim zamasima.",
    ),
    "SOLUSDT": (
        "Solana",
        "Mlađa, brža mreža za aplikacije. Manja je i spekulativnija od prve dvije, pa su pomaci veći u oba smjera; cijena jako ovisi o raspoloženju prema novijim projektima.",
    ),
    "BNBUSDT": (
        "BNB",
        "Token povezan s jednom od najvećih burzi kriptovaluta. Dio potražnje dolazi od popusta i usluga na toj burzi, pa na cijenu utječu i poslovanje i regulacija same burze. "
        "Na ovoj stranici BNB je samo na karti, ne i u testu algoritama.",
    ),
}


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def pctf(x: float, nd: int = 1, sign: bool = False) -> str:
    """Fraction (0.44) -> '44,0 %'."""
    s = hr(x * 100, nd)
    return ("+" + s if sign and x > 0 else s) + " %"


def pctp(x: float, nd: int = 1, sign: bool = False) -> str:
    """Value already in percent (1.09) -> '1,1 %'."""
    s = hr(x, nd)
    return ("+" + s if sign and x > 0 else s) + " %"


def eur(x: float, nd: int = 0, sign: bool = False) -> str:
    s = hr(x, nd)
    return ("+" + s if sign and x > 0 else s) + " EUR"


def dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)}. {int(m)}. {y}."


def trades_word(n: int) -> str:
    """Croatian plural of 'posao' for a count: 1 posao, 2-4 posla, otherwise poslova."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} posao"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} posla"
    return f"{n} poslova"


def price(x: float) -> str:
    return hr(x, 2)


def load(rel: str) -> Any:
    return json.loads((SWING / rel).read_text())


class Data:
    """All inputs of the crypto page, read once."""

    def __init__(self) -> None:
        self.res = load(f"results/{GROUP}.json")
        self.summary = load("summary.json")
        self.placebo = load("placebo.json")
        self.audit = load("audit.json")
        self.tickers_test: list[str] = self.res["tickers"]
        used = self.placebo["universe"]["used"]
        self.tickers_map: list[str] = [k for k, v in used.items() if v == GROUP]
        self.maps = {tk: load(f"map/{tk}.json") for tk in self.tickers_map}
        self.name: str = self.res["name"].split(" (")[0]
        self.cost_bps: float = self.res["cost_bps_per_side"]
        self.months: float = self.res["window"]["months"]
        self.win = self.res["window"]["ai_era"]
        self.winners = self.res["ranking"]["ranking"]

    def ai(self, cid: str) -> dict[str, Any]:
        return self.res["contenders"][cid]["ai_era"]


# ---------------------------------------------------------------- level text helpers


def reliability_text(r: dict[str, Any]) -> str:
    n = r["n"]
    if n == 0:
        return "bez ijednog dodira"
    if not r["enough_touches"]:
        return f"premalo dodira za zaključak ({n}; odbila se {r['bounce']}, probijena {r['break']})"
    return f"od {n} dodira odbila se {r['bounce']} puta ({pctf(r['rate'], 0)}), probijena {r['break']}"


def level_cell(lv: dict[str, Any], support: bool) -> str:
    dist = abs(lv["distance_pct"])
    eur_move = 1000 * dist / 100
    if support:
        eff = f"ako cijena padne do nje (pad {pctp(dist)}), 1.000 EUR postaje oko {hr(1000 - eur_move)} EUR ({eur(-eur_move)})"
    else:
        eff = f"ako cijena naraste do nje (rast {pctp(dist)}), 1.000 EUR postaje oko {hr(1000 + eur_move)} EUR ({eur(eur_move, 0, True)})"
    return (
        f"<b>{price(lv['price'])}</b> ({pctp(lv['distance_pct'], 1, True)})"
        f"<small>{e(eff)}</small>"
        f"<small>Pouzdanost: {e(reliability_text(lv['reliability']))}</small>"
    )


def zones_cell(m: dict[str, Any]) -> str:
    parts: list[str] = []
    for z in m["fresh_zones"]["demand"]:
        parts.append(
            f"zona potražnje {price(z['low'])} do {price(z['high'])} ({pctp(z['distance_pct'], 1, True)})"
        )
    for z in m["fresh_zones"]["supply"]:
        parts.append(
            f"zona ponude {price(z['low'])} do {price(z['high'])} ({pctp(z['distance_pct'], 1, True)})"
        )
    bull, bear = len(m["open_fvg"]["bull"]), len(m["open_fvg"]["bear"])
    parts.append(f"otvorene praznine u cijeni: {bull} bikovske, {bear} medvjeđih")
    if m["recent_sweeps"]:
        for s in m["recent_sweeps"]:
            parts.append(
                f"nedavno: {s['direction']} na {price(s['level'])} ({dmy(s['date'])})"
            )
    else:
        parts.append("nedavnih lovova na stopove nema")
    return "<br>".join(e(p) for p in parts)


def structure_cell(m: dict[str, Any]) -> str:
    w, d = m["weekly"], m["daily"]
    ws, ds = w["last_shift"], d["last_shift"]
    return (
        f"<b>Tjedni:</b> {e(w['bias_hr'])}<small>zadnja promjena karaktera: {e(ws['direction'])}, {dmy(ws['date'])}</small>"
        f"<b>Dnevni:</b> {e(d['bias_hr'])}<small>zadnja promjena karaktera: {e(ds['direction'])}, {dmy(ds['date'])}</small>"
    )


def range_cell(m: dict[str, Any]) -> str:
    r = m["swing_range"]
    return (
        f"<b>{pctp(r['position_pct'], 0)}</b> raspona, {e(r['zone_hr'])}"
        f"<small>raspon {price(r['low'])} ({dmy(r['low_date'])}) do {price(r['high'])} ({dmy(r['high_date'])})</small>"
    )


# ---------------------------------------------------------------- sections


def sec_verdict(d: Data) -> str:
    test = ", ".join(d.tickers_test)
    only_map = [tk for tk in d.tickers_map if tk not in d.tickers_test]
    b0 = d.ai("B0_BUYHOLD")
    if d.winners:
        cid = d.winners[0]["contender"]
        a = d.ai(cid)
        first = (
            f"Od {dmy(d.win[0])} do {dmy(d.win[1])} ({hr(d.months, 1)} mjeseci) jedino pravilo koje zadovoljava unaprijed zadani uvjet 'radi često' je "
            f"<b>{e(NAMES[cid])}</b>: {trades_word(a['trades'])} ({hr(a['trades_per_month'], 1)} mjesečno), "
            f"pogodak {pctf(a['hit_rate'], 0)}, očekivanje {eur(a['expectancy_eur'])} po poslu na 1.000 EUR "
            f"({eur(a['expectancy_eur_cost_2x'])} uz dvostruki trošak), faktor dobiti {hr(a['profit_factor'], 2)}."
        )
        second = (
            f"Ali obično držanje bilo je po ukupnom prinosu daleko bolje ({pctf(b0['total_return'], 0)} naspram {pctf(a['total_return'], 0)}), "
            "a razine potpore i otpora s karte ne pobjeđuju nasumično nacrtane crte (vidi odjeljak 'Pobjeđuju li razine nasumične crte?')."
        )
    else:
        first = "Nijedno pravilo ne zadovoljava unaprijed zadani uvjet 'radi često' (najmanje 60 poslova, pozitivno očekivanje uz dvostruki trošak i faktor dobiti od najmanje 1,2)."
        second = "Razine potpore i otpora s karte ne pobjeđuju nasumično nacrtane crte."
    scope = (
        f"Test obuhvaća {len(d.tickers_test)} kovanice ({e(test)}); {e(', '.join(only_map))} je samo na karti jer nije bio u testu."
        if only_map
        else ""
    )
    return f"""
<section id="presuda"><h2>Presuda u jednoj rečenici</h2>
<div class="verdict-top"><p>{first}</p><p>{second}</p><p class="small">{scope} Ovo je istraživačka simulacija na povijesnim podacima, ne savjet za ulaganje i ne signal za kupnju.</p></div></section>"""


def sec_mechanism(d: Data) -> str:
    cards = []
    for tk in d.tickers_map:
        m = d.maps[tk]
        name, text = MECHANISM[tk]
        atr = f"Iz podataka: tipičan dnevni raspon (ATR14) je {pctp(m['atr14_pct'])} cijene, pa je to oko {hr(10 * m['atr14_pct'])} EUR dnevno na 1.000 EUR. "
        if tk in d.tickers_test:
            bh = d.res["contenders"]["B0_BUYHOLD"]["ai_era"]["per_ticker"][tk]
            extra = (
                f'<p class="small">{atr}'
                f"Obično držanje od {dmy(d.win[0])}: 1.000 EUR je u najgorem trenutku palo na oko {hr(1000 * (1 + bh['max_drawdown']))} EUR (pad {pctf(-bh['max_drawdown'], 0)}), "
                f"a do kraja testa bilo je oko {hr(1000 * (1 + bh['total_return']))} EUR (prošlost ne obećava budućnost).</p>"
            )
        else:
            extra = f'<p class="small">{atr}Nije u testu algoritama, pa nema rezultata držanja ni pravila.</p>'
        cards.append(
            f'<div class="tcard"><h3>{e(name)} <span class="pill">{e(tk)}</span></h3><p>{e(text)}</p>{extra}</div>'
        )
    return f"""
<section id="mehanizam"><h2>Kako ovo tržište funkcionira</h2>
<div class="teach"><p><b>Kratko:</b> kripto trguje 24 sata dnevno, 7 dana u tjednu, bez zatvaranja burze, pa jedna dnevna svijeća ovdje znači jedan puni kalendarski dan, a vikendi se računaju kao i ostali dani.
Cijene se izražavaju u USDT (digitalni novčić vezan uz dolar), a primjeri u eurima samo primjenjuju isti postotak na 1.000 EUR; tečaj eura se ne uračunava.</p>
<p>Ispod je opis svake kovanice. <b>Opisi su kontekst iz javnih izvora, ne izračun iz naših podataka</b>, i nisu provjereni novim izvorom; brojke u sivim redcima su izračunate iz CSV-ova.</p></div>
<div class="tcards">{"".join(cards)}</div></section>"""


def sec_now(d: Data) -> str:
    rows = []
    for tk in d.tickers_map:
        m = d.maps[tk]
        sup = "<br>".join(level_cell(x, True) for x in m["nearest_supports"])
        res = "<br>".join(level_cell(x, False) for x in m["nearest_resistances"])
        tag = (
            "" if tk in d.tickers_test else ' <span class="chip warn">samo karta</span>'
        )
        rows.append(
            f'<tr data-t="{e(tk)}"><td class="l wrap"><b>{e(tk)}</b>{tag}</td>'
            f'<td class="wrap"><b>{dmy(m["last_date"])}</b><small>zatvaranje {price(m["last_close"])} USDT</small><small>dnevni raspon (ATR14) {pctp(m["atr14_pct"])}</small></td>'
            f'<td class="wrap">{structure_cell(m)}</td><td class="wrap">{range_cell(m)}</td>'
            f'<td class="wrap">{sup}</td><td class="wrap">{res}</td><td class="wrap">{zones_cell(m)}</td></tr>'
        )
    ld = ", ".join(dmy(x) for x in sorted({m["last_date"] for m in d.maps.values()}))
    return f"""
<section id="sada"><h2>Gdje je cijena sada</h2>
<p class="lead2">Karta koristi zadnji datum svakog papira ({e(ld)}); test algoritama završava {dmy(d.win[1])} (zajednički kraj podataka za sve grupe).</p>
<div class="teach"><p><b>Kako čitati tablicu.</b> <b>Potpora</b> je cijena ispod trenutne na kojoj se pad ranije zaustavljao; <b>otpor</b> je cijena iznad na kojoj se rast zaustavljao.
Udaljenost je u postocima, a euri pokazuju što taj pomak znači na ulogu od 1.000 EUR (pomak od 2 % je 20 EUR). Ako potpora pukne, gubitak je veći od prikazanog.</p>
<p><b>Struktura</b> je niz zadnjih potvrđenih vrhova i dna: viši vrhovi i viša dna su bikovska (uzlazna), niži vrhovi i niža dna medvjeđa (silazna) slika. Tjedna daje veću sliku, dnevna kraću.
<b>Raspon</b> ide od zadnjeg potvrđenog dna do zadnjeg potvrđenog vrha; donja polovica je 'diskont' (jeftinije), gornja 'premium' (skuplje). <b>Pouzdanost</b> je koliko se puta cijena izvan uzorka odbila od razine; uz malo dodira to nije zaključak.</p></div>
<div class="table-wrap"><table class="map-table"><thead><tr><th class="l">Papir</th><th class="l">Zadnji dan</th><th class="l">Struktura</th><th class="l">Položaj u rasponu</th><th class="l">Dvije najbliže potpore</th><th class="l">Dva najbliža otpora</th><th class="l">Aktivne zone</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="small">Zona potražnje ili ponude je 'svježa' dok joj se cijena prvi put ne vrati. Praznina u cijeni je brz pomak koji je ostavio neprekrivenu rupu između svijeća. Sve razine i zone su smjernice za postavljanje stopa i ciljeva, ne zajamčena odbijanja.</p></section>"""


def ticker_reading(m: dict[str, Any]) -> str:
    w, dd, r = m["weekly"], m["daily"], m["swing_range"]
    items: list[str] = []
    if w["bias"] == dd["bias"]:
        items.append(f"Tjedna i dnevna slika slažu se: obje su {e(w['bias_hr'])}.")
    else:
        items.append(
            f"Tjedna slika je {e(w['bias_hr'])}, a dnevna {e(dd['bias_hr'])}. Kad se dva vremenska okvira ne slažu, swing trader obično kraći okvir čita kao korekciju ili prvi znak okreta većeg trenda; "
            "taj obrazac nije dokazan ovim testom (W6 koristi tjedni filter i ima premalo poslova)."
        )
    width = (r["high"] / r["low"] - 1) * 100
    items.append(
        f"Cijena je na {pctp(r['position_pct'], 0)} zadnjeg raspona ({e(r['zone_hr'])}). Raspon je širok {pctp(width, 1)}, pa bi 1.000 EUR kupljenih na dnu raspona na vrhu bilo oko {hr(1000 * (1 + width / 100))} EUR."
    )
    sup, res = m["nearest_supports"][0], m["nearest_resistances"][0]
    items.append(
        f"Najbliža potpora je {price(sup['price'])} ({pctp(abs(sup['distance_pct']))} ispod; {e(reliability_text(sup['reliability']))}); "
        f"najbliži otpor je {price(res['price'])} ({pctp(abs(res['distance_pct']))} iznad; {e(reliability_text(res['reliability']))})."
    )
    items.append(
        f"Prosjek zadnjih 50 dana ({price(m['sma50']['value'])}) je {pctp(abs(m['sma50']['distance_pct']))} {'ispod' if m['sma50']['distance_pct'] > 0 else 'iznad'} cijene, "
        f"prosjek zadnjih 200 dana ({price(m['sma200']['value'])}) {pctp(abs(m['sma200']['distance_pct']))} {'ispod' if m['sma200']['distance_pct'] > 0 else 'iznad'} cijene. "
        f"52-tjedni vrh je {price(m['high_52w']['price'])} ({pctp(m['high_52w']['distance_pct'], 1, True)}), dno {price(m['low_52w']['price'])} ({pctp(m['low_52w']['distance_pct'], 1, True)})."
    )
    pool_txt = []
    for side, lab, what in (("above", "iznad", "vrha"), ("below", "ispod", "dna")):
        for p in m["liquidity_pools"][side]:
            pool_txt.append(
                f"{lab} cijene na {price(p['level'])} ({pctp(p['distance_pct'], 1, True)}, {p['members']} istaknuta {what})"
            )
    items.append(
        "Skupine stopova (mjesta gdje se skupljaju zaštitne naredbe): "
        + ("; ".join(pool_txt) if pool_txt else "nema istaknutih")
        + "."
    )
    repairs = m["bar_repairs"]
    if repairs:
        last_rep = max(x.split(" ")[0] for x in repairs)
        rep_txt = f"U podacima je ispravljeno {len(repairs)} očito loših cijena (zadnja {dmy(last_rep)}); to može pomaknuti stare okrete, a koliko, nije izmjereno."
    else:
        rep_txt = "U podacima nije bilo ispravaka loših cijena."
    watch = [
        f"drži li cijena potporu {price(sup['price'])} ili je zatvaranje dana probije prema dolje (slika se tada mijenja, a gubitak do sljedeće razine raste);",
        f"zatvara li dan iznad otpora {price(res['price'])} (prvi uvjet za nastavak rasta);",
    ]
    if w["bias"] != dd["bias"]:
        watch.append(
            "hoće li se dnevna slika uskladiti s tjednom (nova promjena karaktera) ili će tjedna popustiti."
        )
    else:
        watch.append(
            "ostaju li vrhovi i dna u istom smjeru ili dođe do promjene karaktera."
        )
    return (
        '<div class="read"><h4>Što ovdje vidimo</h4><ul>'
        + "".join(f"<li>{x}</li>" for x in items)
        + f'</ul><p class="small">{e(rep_txt)}</p>'
        "<h4>Što bi swing trader gledao</h4><ul>"
        + "".join(f"<li>{e(x)}</li>" for x in watch)
        + "</ul>"
        '<p class="small">Ovo je čitanje karte, ne preporuka. Test lažnih razina (sljedeći odjeljci) pokazuje da razine same po sebi ne daju prednost.</p></div>'
    )


def sec_charts(d: Data) -> str:
    out = []
    for tk in d.tickers_map:
        m = d.maps[tk]
        name = MECHANISM[tk][0]
        tag = (
            "" if tk in d.tickers_test else '<span class="chip warn">samo karta</span>'
        )
        fig = (
            f'<figure><div class="plate"><img src="{top10.img(SWING / "map" / f"{tk}.png")}" alt="{e(tk)}: karta razina i strukture" loading="lazy"></div>'
            '<p class="swipe">Na mobitelu povuci graf ulijevo i udesno da vidiš sve.</p></figure>'
        )
        out.append(
            f'<div id="karta-{e(tk)}"><div class="tick-h"><h3>{e(name)} ({e(tk)}), zadnji dan {dmy(m["last_date"])}</h3>{tag}</div>{fig}{ticker_reading(m)}</div>'
        )
    sep = '<hr style="border:0;border-top:1px solid var(--line);margin:24px 0">'
    return (
        '<section id="grafovi"><h2>Bilježnica po kovanici</h2>'
        '<p class="lead2">Na grafu: zelene trake su potpore ispod cijene, crvene otpori iznad, debljina i oznaka pokazuju koliko je puta razina držala. '
        "Isprekidane linije su prosjeci zadnjih 50 i 200 dana.</p>"
        + sep.join(out)
        + "</section>"
    )


def contender_rows(d: Data) -> str:
    order = [w["contender"] for w in d.winners] + [
        r["contender"] for r in d.res["ranking"]["not_eligible"]
    ]
    winners = {w["contender"] for w in d.winners}
    reasons = {r["contender"]: r["reasons"] for r in d.res["ranking"]["not_eligible"]}
    b0 = d.ai("B0_BUYHOLD")
    rows = []
    for cid in [*order, "B0_BUYHOLD"]:
        a = d.ai(cid)
        if cid == "B0_BUYHOLD":
            verdict = "mjerilo, ne rangira se"
            cls = ""
            hit = pf = exp = exp2 = "–"
            hold = f"{hr(a['median_hold_days'], 0)} / {hr(a['mean_hold_days'], 0)}"
        else:
            if cid in winners:
                verdict = '<span class="chip good">DA, radi često</span>'
                cls = ' class="rowwin"'
            else:
                txt = "; ".join(
                    REASONS.get(
                        x,
                        re.sub(
                            r"only (\d+) trades \(< 60\)",
                            lambda mm: (
                                f"samo {trades_word(int(mm.group(1)))} (manje od 60)"
                            ),
                            x,
                        ),
                    )
                    for x in reasons[cid]
                )
                verdict = f'<span class="chip bad">ne</span><br><small>{e(txt)}</small>'
                cls = ""
            hit = pctf(a["hit_rate"], 0)
            pf = hr(a["profit_factor"], 2) if a["profit_factor"] is not None else "–"
            hold = f"{hr(a['median_hold_days'], 0)} / {hr(a['mean_hold_days'], 1)}"
            exp = eur(a["expectancy_eur"], 1)
            exp2 = eur(a["expectancy_eur_cost_2x"], 1)
        diff = a["total_return"] - b0["total_return"]
        rows.append(
            f'<tr data-id="{cid}"{cls}><td class="l wrap"><b>{e(NAMES[cid])}</b><small>{e(RULES[cid])}</small></td>'
            f"<td>{a['trades']}</td><td>{hr(a['trades_per_month'], 1)}</td><td>{hit}</td><td>{exp}</td><td>{exp2}</td><td>{pf}</td><td>{hold}</td>"
            f'<td>{pctf(a["total_return"], 0)}</td><td>{"–" if cid == "B0_BUYHOLD" else hr(diff * 100, 0) + " pp"}</td><td class="l wrap">{verdict}</td></tr>'
        )
    return "".join(rows)


def sec_swing(d: Data) -> str:
    ctx_rows = ""
    if d.winners:
        cid = d.winners[0]["contender"]
        a = d.ai(cid)
        b0 = d.ai("B0_BUYHOLD")
        pt = []
        for tk, v in a["per_ticker"].items():
            bh = b0["per_ticker"][tk]
            pt.append(
                f'<tr data-p="{e(tk)}"><td class="l">{e(tk)}</td><td>{v["trades"]}</td><td>{pctf(v["hit_rate"], 0)}</td><td>{eur(v["expectancy_eur"], 1)}</td>'
                f"<td>{hr(v['profit_factor'], 2)}</td><td>{hr(v['median_hold_days'], 0)}</td><td>{pctf(v['total_return'], 0)}</td><td>{pctf(bh['total_return'], 0)}</td><td>{pctf(bh['max_drawdown'], 0)}</td></tr>"
            )
        cx = d.res["contenders"][cid]["contexts"]
        cr = "".join(
            f'<tr data-c="{k}"><td class="l">{lab}</td><td>{cx[k]["trades"]}</td><td>{eur(cx[k]["expectancy_eur"], 1)}</td><td>{hr(cx[k]["profit_factor"], 2)}</td><td>{pctf(cx[k]["total_return"], 0)}</td></tr>'
            for k, lab in (
                ("y2016_2020", "2016.–2020. (samo kontekst)"),
                ("y2021_2022", "2021.–2022. (samo kontekst)"),
            )
        )
        ctx_rows = f"""
<h3>Pobjednik po kovanici</h3>
<div class="table-wrap"><table><thead><tr><th class="l">Kovanica</th><th>Poslova</th><th>Pogodak</th><th>Očekivanje / posao</th><th>Faktor dobiti</th><th>Medijan držanja (dana)</th><th>Prinos pravila</th><th>Prinos držanja</th><th>Najveći pad držanja</th></tr></thead><tbody>{"".join(pt)}</tbody></table></div>
<p class="small">Pogodak je udio dobitnih poslova. Najveći pad je najgori trenutak od vrha: pad od 50 % znači da je 1.000 EUR palo na 500 EUR (na papiru, dok ne prodaš). Rizik se ovdje prikazuje da ga vidiš, ne snižava ocjenu.</p>
<h3>Isto pravilo u ranijim razdobljima</h3>
<div class="table-wrap"><table><thead><tr><th class="l">Razdoblje</th><th>Poslova</th><th>Očekivanje / posao</th><th>Faktor dobiti</th><th>Prinos</th></tr></thead><tbody>{cr}</tbody></table></div>
<p class="small">Isti fiksni parametri, bez novog ugađanja. U kriptu je predznak očekivanja isti u sva tri razdoblja, što upućuje na stabilnost, ali ranije godine su drugačije tržište, pa su samo kontekst.</p>"""
        win_block = f"""
<div class="verdict"><h3>Pobjednik pravila 'radi često': {e(NAMES[cid])}</h3>
<p>Pravilo je zadano unaprijed: najmanje 60 poslova u AI eri, pozitivno očekivanje po poslu uz dvostruki trošak i faktor dobiti od najmanje 1,2; među podobnima rang je očekivanje po poslu pomnoženo brojem poslova mjesečno.
Ovdje: {trades_word(a["trades"])} ({hr(a["trades_per_month"], 1)} mjesečno, oko {hr(a["trades_per_ticker_year"], 1)} po kovanici godišnje), prosječan dobitni posao {eur(a["avg_win_eur"])}, prosječan gubitni {eur(a["avg_loss_eur"])} na 1.000 EUR,
dobitnih je {pctf(a["hit_rate"], 0)}; rang-broj iznosi oko {eur(d.winners[0]["score_eur_per_month"])} mjesečno preko tri pretinca od 1.000 EUR (to je mjerilo za poredak, ne obećanje).</p>
<p><b>Zašto bi moglo vrijediti:</b> kripto ima dugotrajne trendove, a pravilo kupuje tek kad cijena već probija vrh i izlazi brzo kad trend oslabi; očekivanje je pozitivno na sve tri kovanice uz osnovni trošak, a na cijeloj skupini i uz dvostruki i trostruki trošak ({eur(a["expectancy_eur_cost_3x"], 1)} po poslu uz trostruki).</p>
<p><b>Zašto bi moglo ne vrijediti:</b> pet najboljih poslova čini {pctf(a["top5_profit_share"], 0)} ukupne dobiti, dakle rezultat visi na nekoliko velikih poteza; razdoblje 2023.–2026. uključuje snažan rast kriptovaluta; provjera ±20 % parametara nije rađena za ovo pravilo na kriptu (nepotvrđeno, pa ugađanje nije isključeno);
informativni 'deflated Sharpe' je {hr(a["deflated_sharpe_prob"], 2)} (niska vrijednost znači da se uz mnogo isprobanih pravila ne može isključiti sreća); isprobano je 9 pravila (ledger K = {d.summary["ledger_k"]}). Obično držanje je dalo {pctf(b0["total_return"], 0)} prema {pctf(a["total_return"], 0)}, uz najveći pad {pctf(-b0["max_drawdown"], 0)} naspram {pctf(-a["max_drawdown"], 0)}; pravilo je bilo uloženo u {pctf(a["exposure_pct"] / 100, 0)} vremena.</p></div>"""
    else:
        win_block = '<div class="verdict"><h3>Nitko ne ispunjava uvjete</h3></div>'
    return f"""
<section id="swing"><h2>Što je swing test pokazao za ovu skupinu</h2>
<p class="lead2">Osam pravila i kupi-i-drži, na kovanicama {e(", ".join(d.tickers_test))}, od {dmy(d.win[0])} do {dmy(d.win[1])} ({hr(d.months, 1)} mjeseci), trošak {hr(d.cost_bps, 0)} baznih bodova (0,10 %) po strani, svaki posao na 1.000 EUR, bez poluge i bez kratke prodaje.
Odluka pada na zatvaranju dana, kupnja na sljedećem otvaranju. Svaka kovanica ima vlastiti pretinac od 1.000 EUR.</p>
<div class="teach"><p><b>Očekivanje po poslu</b> je prosječna zarada jednog posla na 1.000 EUR: +40 EUR znači da je prosječan posao donio 40 EUR, iako se pojedini poslovi jako razlikuju. <b>Faktor dobiti</b> je zbroj dobitaka podijeljen sa zbrojem gubitaka: 2 znači 2 EUR dobiti za svaki izgubljeni euro.
<b>Radi često</b> traži najmanje 60 poslova, pozitivno očekivanje uz dvostruki trošak i faktor dobiti 1,2 ili više. Držanje (medijan / prosjek) je u danima.</p></div>
<div class="table-wrap"><table class="contenders"><thead><tr><th class="l">Algoritam i pravilo</th><th>Poslova</th><th>Poslova / mj.</th><th>Pogodak</th><th>Očekivanje / posao</th><th>Uz trošak 2x</th><th>Faktor dobiti</th><th>Držanje (dana)</th><th>Ukupni prinos</th><th>Prema držanju</th><th class="l">Radi često?</th></tr></thead>
<tbody>{contender_rows(d)}</tbody></table></div>
<p class="small">'Prema držanju' je razlika ukupnog prinosa pravila i kupi-i-drži u postotnim bodovima. Ukupni prinos je za Petrov cilj sekundaran; pitanje je što trguje često i radi. Kupi-i-drži ima 3 posla jer se kupuje jednom po kovanici.</p>
{win_block}
{ctx_rows}
</section>"""


def sec_placebo(d: Data) -> str:
    g = d.placebo["sr"]["by_group"][GROUP]
    cfg = d.placebo["config"]
    ctrls = (
        ("rand", "diff_vs_rand", "nasumična cijena u zadnjih 120 dana"),
        ("shift", "diff_vs_shift", "ista razina pomaknuta za 3 % gore i dolje"),
        (
            "match",
            "diff_vs_match",
            "par lažnih crta oko prave razine (najstroža kontrola)",
        ),
    )

    def cell(x: dict[str, Any]) -> str:
        lo, hi = x["ci95"]
        return f"{hr(x['diff'] * 100, 1)} pp [{hr(lo * 100, 1)}; {hr(hi * 100, 1)}]"

    rows = []
    for key, dk, lab in ctrls:
        real = g["real"] if key != "match" else g["mreal"]
        fake = g[key]
        rows.append(
            f'<tr data-k="{key}"><td class="l wrap">{e(lab)}</td><td>{pctf(real["bounce_rate"], 1)} / {pctf(fake["bounce_rate"], 1)}</td><td>{cell(g[dk]["bounce_rate"])}</td>'
            f"<td>{pctf(real['break_rate'], 1)} / {pctf(fake['break_rate'], 1)}</td><td>{cell(g[dk]['break_rate'])}</td></tr>"
        )
    all_zero = all(
        g[dk][mt]["ci95"][0] <= 0 <= g[dk][mt]["ci95"][1]
        for _, dk, _ in ctrls
        for mt in ("bounce_rate", "break_rate")
    )
    ex = g["diff_vs_match"]["touch_rate"]
    al = d.placebo["sr"]["all"]
    w4 = d.ai("W4_SR_BOUNCE_V2")
    answer = (
        "Ne. Razine s karte nisu ni odbijale ni držale bolje od nasumično nacrtanih crta: svi intervali pouzdanosti za odbijanje i probijanje obuhvaćaju nulu."
        if all_zero
        else "Barem jedna usporedba pokazuje razliku; pogledaj intervale u tablici."
    )
    return f"""
<section id="placebo"><h2>Pobjeđuju li razine nasumične crte?</h2>
<div class="teach"><p><b>Placebo je kontrolna skupina</b>, kao tableta od šećera u ispitivanju lijeka. Ako i lažne crte, nacrtane tamo gdje nitko nije potvrdio okret, daju isti rezultat, prava razina nije ništa posebno.
Na zadnji dan svakog mjeseca od 2023. uzeli smo razine koje su tada već bile poznate i gledali sljedećih 20 dana. <b>Odbijanje</b> je potez od barem {hr(cfg["bounce_atr"], 1)} ATR od razine (ATR je prosječni dnevni raspon: uz ATR od 4 % to je oko 40 EUR dnevno na 1.000 EUR) prije nego što cijena zatvori {hr(cfg["break_atr"], 1)} ATR iza razine (<b>probijanje</b>).
<b>pp</b> je postotni bod (razlika između 49 % i 48 % je 1 pp); u uglatoj zagradi je 95 % interval: ako obuhvaća nulu, razlika se ne razlikuje od slučajne.</p></div>
<p><b>Odgovor za kripto: {e(answer)}</b> Uzorak je {g["n_levels"]} razina na {g["n_months"]} mjeseci i {len(d.tickers_map)} kovanice ({e(", ".join(d.tickers_map))}), pa su intervali široki.</p>
<div class="table-wrap"><table><thead><tr><th class="l">Usporedba s</th><th>Odbijanje: prava / lažna</th><th>Razlika u odbijanju</th><th>Probijanje: prava / lažna</th><th>Razlika u probijanju</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p>Dodir: u usporedbi s parom lažnih crta prave razine kripta dodiruju se {hr(abs(ex["diff"]) * 100, 1)} pp {"rjeđe" if ex["diff"] < 0 else "češće"} (interval {hr(ex["ci95"][0] * 100, 1)} do {hr(ex["ci95"][1] * 100, 1)} pp): cijena razine ne privlači.
Isti zaključak vrijedi na svih {al["n_levels"]} razina svih grupa zajedno. To se slaže i s rezultatom algoritma W4 (odbijanje od potpore): u kriptu je imao očekivanje {eur(w4["expectancy_eur"], 1)} po poslu i faktor dobiti {hr(w4["profit_factor"], 2)}.</p>
<p class="small">Razine na karti zato služe kao smjernice za postavljanje stopa i za procjenu koliko bi pad stajao (vidi euro-primjere), a ne kao dokaz da će se cijena odbiti.</p></section>"""


def sec_glossary() -> str:
    imported = dict(top10.GLOSSARY)
    own = [
        (
            "Swing trgovanje",
            "Držanje položaja dane do tjedne, ne sekunde ni godine. Primjer: kupiš za 1.000 EUR, držiš dva tjedna, prodaš.",
        ),
        (
            "Potpora i otpor",
            "Potpora je razina ispod cijene na kojoj se pad ranije zaustavljao; otpor je razina iznad na kojoj se rast zaustavljao. Primjer: cijena je 100, potpora 95: pad do nje je 5 %, tj. 50 EUR na 1.000 EUR.",
        ),
        (
            "Okret (swing pivot)",
            "Najviša (najniža) točka koja je viša (niža) od 5 svijeća sa svake strane. Potvrđuje se tek 5 dana kasnije, jer prije toga ne znamo je li vrh pravi.",
        ),
        (
            "Struktura: bikovska i medvjeđa",
            "Bikovska: viši vrhovi i viša dna (uzlazno stubište). Medvjeđa: niži vrhovi i niža dna (silazno).",
        ),
        (
            "Proboj strukture i promjena karaktera",
            "Proboj strukture je zatvaranje iznad zadnjeg vrha u smjeru trenda (nastavak). Promjena karaktera je zatvaranje preko zadnjeg suprotnog okreta, npr. iznad zadnjeg nižeg vrha u padu: prvi znak da se trend možda okreće.",
        ),
        (
            "Raspon, diskont i premium",
            "Raspon ide od zadnjeg potvrđenog dna do vrha. Donja polovica je 'diskont', gornja 'premium'. Primjer: raspon 80 do 120, cijena 90 je u diskontu.",
        ),
        (
            "Likvidnost i lov na stopove",
            "Zaštitne naredbe se skupljaju ispod očitih dna. Lov na stopove: svijeća probije takvo dno, ali zatvori natrag iznad. Primjer: dno 90, svijeća dođe na 88 i zatvori na 91.",
        ),
        (
            "Zona potražnje i zona ponude",
            "Zona potražnje je zadnja padajuća svijeća prije snažnog rasta; ponude zadnja rastuća prije snažnog pada. Svježa je dok joj se cijena prvi put ne vrati.",
        ),
        (
            "Praznina u cijeni (fair value gap)",
            "Tri svijeće kod kojih najviša cijena prve ostaje ispod najniže treće: pomak je bio tako brz da je ostala neprekrivena rupa.",
        ),
        (
            "ATR",
            "Prosječni dnevni raspon (najviša minus najniža) zadnjih 14 dana. Primjer: ATR 3 % znači da se cijena u prosjeku pomakne oko 30 EUR dnevno na 1.000 EUR.",
        ),
        (
            "Prosjek 50 i 200 dana (SMA)",
            "Prosjek zadnjih 50 odnosno 200 zatvaranja. Cijena iznad prosjeka znači uzlazni trend tog razdoblja.",
        ),
        (
            "Očekivanje po poslu i faktor dobiti",
            "Očekivanje je prosječna zarada jednog posla (na 1.000 EUR). Faktor dobiti je zbroj dobitaka / zbroj gubitaka; 1,5 znači 1,50 EUR dobiti za svaki izgubljeni euro.",
        ),
        (
            "Bazni bod (bps) i stres troška 2x i 3x",
            "Bazni bod je stotinka postotka. Kripto ovdje ima 10 baznih bodova po strani = 0,10 %: 1 EUR pri kupnji i 1 EUR pri prodaji na 1.000 EUR. Stres 2x i 3x ponavlja račun s dvostrukim i trostrukim troškom.",
        ),
        (
            "Najveći pad od vrha",
            "Pad od najboljeg do najgoreg trenutka: 1.000 EUR naraste na 2.000 EUR pa padne na 1.200 EUR = pad 40 % (na papiru dok ne prodaš).",
        ),
        (
            "Placebo i interval pouzdanosti",
            "Placebo je lažna kontrola; ako ona daje isti rezultat, stvarna razina nije posebna. Interval od 95 % je raspon u kojem bi se razlika vjerojatno našla pri ponavljanju; ako obuhvaća nulu, razlika se ne razlikuje od slučajne.",
        ),
        (
            "Pretinac",
            "Jedna kovanica s vlastitih 1.000 EUR; pretinci se ne prelijevaju.",
        ),
        (
            "USDT",
            "Digitalni novčić koji bi trebao vrijediti oko jedan američki dolar. Cijene su u USDT, a primjeri u eurima samo preslikavaju postotke; tečaj nije uračunat.",
        ),
    ]
    for key in (
        "AI era",
        "Prilagođeno podacima (overfitting)",
        "Broj pokušaja (K) i deflated Sharpe",
    ):
        if key in imported:
            own.append((key, imported[key]))
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in own)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def sec_eu(d: Data) -> str:
    chips = "".join(
        f'<span class="chip warn">{e(tk)}: nepotvrđeno</span>' for tk in d.tickers_map
    )
    return f"""
<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>
<div class="chips">{chips}<span class="chip warn">kripto ETF-ovi (npr. IBIT, ETHA): referentno</span></div>
<p>Za sve četiri kovanice <b>dostupnost na Interactive Brokersu ostaje nepotvrđena</b>: ponuda kripta ovisi o državi i propisima (u EU okvir MiCA), a to treba provjeriti u samom IBKR-u za Petrov račun.
Ako izravna kripto trgovina nije dostupna, alternativa su kripto ETP-ovi na europskim burzama; to su drugi instrumenti s drugim troškovima i drugim radnim vremenom, pa pravilo treba ponovno testirati na njima.</p>
<p>Američki kripto ETF-ovi (npr. IBIT, ETHA) često nisu dostupni malim ulagačima iz EU jer nemaju KID dokument; ovdje ih ne predstavljamo kao nešto što the researcher može kupiti. Postoji li za BNB ikakav europski proizvod: <b>nepotvrđeno</b>.</p>
<p>Cijene su u USDT, račun je u eurima: tečaj eura i trošak konverzije su stvarni, a ovdje nisu uračunati. Kripto trguje 24/7, a broker i burza mogu imati druga radna vremena. Porezni tretman i evidencija: <b>nepotvrđeno</b>, bez poreznih tvrdnji.
Stvarno trgovanje je zasebna Petrova odluka; agenti ne šalju nikakve naloge (ni probne ni prave).</p></section>"""


def sec_limits(d: Data) -> str:
    rep = d.audit["crypto_repair"]["repairs_per_crypto_ticker"]
    rep_txt = ", ".join(f"{k.replace('USDT', '')} {v}" for k, v in rep.items())
    bnb = len(d.maps["BNBUSDT"]["bar_repairs"]) if "BNBUSDT" in d.maps else 0
    last_dates = ", ".join(sorted({dmy(m["last_date"]) for m in d.maps.values()}))
    items = [
        f"Razdoblje testa: {dmy(d.win[0])} do {dmy(d.win[1])} ({hr(d.months, 1)} mjeseci). AI era je mjerilo, ranije godine su samo kontekst. Karta koristi zadnji datum svakog papira ({last_dates}).",
        f"Trošak: {hr(d.cost_bps, 0)} baznih bodova (0,10 %) po strani uz stres 2x i 3x; stvarni trošak kod brokera, provizije po nalogu i proklizavanje nisu poznati (nepotvrđeno).",
        "Test obuhvaća samo BTC, ETH i SOL (3 pretinca). BNB je samo na karti i u testu lažnih razina; algoritmi na njemu nisu pokrenuti.",
        "Kripto ima malo neovisnih kovanica: BTC, ETH i SOL se kreću zajedno, pa 104 posla nisu 104 neovisna dokaza.",
        "Razdoblje 2023.–2026. uključuje snažan rast kripta; pravila koja prate trend u tome imaju laku podlogu. Zaključci prije 2023. se ne donose.",
        "Provjera ±20 % parametara nije rađena za pobjednika na kriptu (rađena je samo za tri najbolja pravila na dionicama). Nepotvrđeno je koliko je rezultat osjetljiv na parametre.",
        f"Popravak podataka: pravilo za loše cijene ograničilo je {sum(rep.values())} niskih cijena u kriptu ({rep_txt}), od kojih su mnoge vjerojatno stvarni brzi padovi; "
        f"u reviziji je provjereno da to mijenja samo W8 (ne i pobjednika), ali može pomaknuti stare razine na karti. Na karti BNB ima {bnb} takvih popravaka.",
        "Revizija (14. 10. 2026.): 20 neovisnih izračuna podudara se sa spremljenima; test pogleda unaprijed bez grešaka (576 provjera nizova i 48 provjera poslova po pravilu). "
        "Zamrznuti parametri i pravila jednaki su registriranima; datoteka simulatora ima drugačiji otisak nego pri registraciji, što je u skladu sa statusom revizije 'ispravljeno'.",
        "Kripto nema dividende; tečaj EUR/USD i porezi nisu uračunati.",
        "Bez poluge i bez kratke prodaje (zadano za EU malog ulagača).",
        "Ovo nije formalni Critic PASS laboratorija; signal ostaje PRIČEKAJ dok ne postoji odobrena strategija.",
    ]
    if not d.winners:
        items.insert(0, "Nijedno pravilo nije zadovoljilo uvjet 'radi često'.")
    ex = "".join(f"<li>{e(x)}</li>" for x in items)
    return f'<section id="granice"><h2>Granice: što nije uračunato</h2><ul>{ex}</ul></section>'


def build() -> Path:
    d = Data()
    names = ", ".join(MECHANISM[tk][0] for tk in d.tickers_map)
    body = f"""<main>
<header><span class="tagline">AICHAIN · karta tržišta · {e(d.name)} · istraživačka simulacija</span>
<h1>Karta tržišta: {e(d.name)}</h1>
<p class="lead">Gdje je cijena sada, što je swing test pokazao i pomažu li crtane razine. Kovanice: {e(names)}.</p>
<div class="chips"><span class="chip">razdoblje testa {dmy(d.win[0])} do {dmy(d.win[1])}</span><span class="chip">trošak {hr(d.cost_bps, 0)} bps po strani</span><span class="chip warn">istraživačka simulacija</span><span class="chip warn">nije signal ni savjet</span></div></header>
{sec_verdict(d)}
{sec_mechanism(d)}
{sec_now(d)}
{sec_charts(d)}
{sec_swing(d)}
{sec_placebo(d)}
{sec_eu(d)}
{sec_limits(d)}
{sec_glossary()}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima ({dmy(d.win[0])} do {dmy(d.win[1])}): odluka na zatvaranju dana, kupnja na sljedećem otvaranju, trošak {hr(d.cost_bps, 0)} baznih bodova po strani, bez poluge i bez kratke prodaje.
Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje, nije formalni Critic PASS, a nijedan nalog (ni probni ni pravi) nije poslan. Status revizije: ispravljeno (14. 10. 2026.).</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(title=f"Karta: {d.name}", css=top10.CSS + EXTRA_CSS)
    )
    page = (
        '<!doctype html>\n<html lang="hr"><head>\n'
        + head
        + "</head><body>\n"
        + body
        + "\n</body></html>"
    )
    out = SWING / "pages" / f"{GROUP}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


# ---------------------------------------------------------------- verification


def verify() -> list[str]:
    """Re-read the JSON files and check that each key number appears in the built page. Returns mismatches."""
    page = (SWING / "pages" / f"{GROUP}.html").read_text()
    res = load(f"results/{GROUP}.json")
    plc = load("placebo.json")
    bad: list[str] = []
    rows = {
        m.group(1): m.group(2)
        for m in re.finditer(
            r'<tr data-id="([A-Z0-9_]+)"[^>]*>(.*?)</tr>', page, re.DOTALL
        )
    }
    for cid, v in res["contenders"].items():
        a = v["ai_era"]
        row = rows.get(cid, "")
        exp = [
            f">{a['trades']}<",
            hr(a["trades_per_month"], 1),
            pctf(a["total_return"], 0),
        ]
        if cid != "B0_BUYHOLD":
            exp += [
                pctf(a["hit_rate"], 0),
                eur(a["expectancy_eur"], 1),
                eur(a["expectancy_eur_cost_2x"], 1),
            ]
            if a["profit_factor"] is not None:
                exp.append(hr(a["profit_factor"], 2))
        bad += [f"{cid}: expected {s!r} in row" for s in exp if s not in row]
    for tk in res["tickers"]:
        w2 = res["contenders"]["W2_MOM_BREAK_20"]["ai_era"]["per_ticker"][tk]
        m = re.search(rf'<tr data-p="{tk}">(.*?)</tr>', page, re.DOTALL)
        r = m.group(1) if m else ""
        exp = (
            f">{w2['trades']}<",
            eur(w2["expectancy_eur"], 1),
            hr(w2["profit_factor"], 2),
        )
        bad += [f"{tk} W2 per ticker: expected {s!r}" for s in exp if s not in r]
    for tk in [k for k, v in plc["universe"]["used"].items() if v == GROUP]:
        mp = load(f"map/{tk}.json")
        m = re.search(rf'<tr data-t="{tk}">(.*?)</tr>', page, re.DOTALL)
        r = m.group(1) if m else ""
        exp = [
            price(mp["last_close"]),
            dmy(mp["last_date"]),
            mp["weekly"]["bias_hr"],
            mp["daily"]["bias_hr"],
        ]
        for lv in mp["nearest_supports"] + mp["nearest_resistances"]:
            move = 1000 * abs(lv["distance_pct"]) / 100
            exp += [price(lv["price"]), pctp(lv["distance_pct"], 1, True)]
            exp.append(eur(-move) if lv["type"] == "support" else eur(move, 0, True))
        bad += [f"{tk} map row: expected {s!r}" for s in exp if html.escape(s) not in r]
    g = plc["sr"]["by_group"][GROUP]
    for key, dk in (
        ("rand", "diff_vs_rand"),
        ("shift", "diff_vs_shift"),
        ("match", "diff_vs_match"),
    ):
        m = re.search(rf'<tr data-k="{key}">(.*?)</tr>', page, re.DOTALL)
        r = m.group(1) if m else ""
        for mt in ("bounce_rate", "break_rate"):
            x = g[dk][mt]
            exp = (
                hr(x["diff"] * 100, 1),
                hr(x["ci95"][0] * 100, 1),
                hr(x["ci95"][1] * 100, 1),
            )
            bad += [f"placebo {key} {mt}: expected {s!r}" for s in exp if s not in r]
    return bad


def main() -> None:
    out = build()
    print(out, out.stat().st_size, "bytes")
    if "--verify" in sys.argv:
        bad = verify()
        print("verify:", "OK" if not bad else f"{len(bad)} mismatches")
        for b in bad:
            print("  ", b)
        if bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
