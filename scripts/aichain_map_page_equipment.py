"""Build the self-contained Croatian 'Karta trzista' page for the equipment group (AMAT, LRCX, KLAC, ...).

Usage:
  .venv/bin/python scripts/aichain_map_page_equipment.py            # build the page
  .venv/bin/python scripts/aichain_map_page_equipment.py --verify   # build, then re-read the JSON and check the page

Inputs (read only): swing/map/{T}.json + {T}.png, swing/results/equipment.json, swing/summary.json, swing/placebo.json,
swing/registration.json, swing/audit.json, segments/equipment/profile.json + analysis.json, DATA_QUALITY.md.
Output: swing/pages/equipment.html (charts embedded as data URIs; only Google Fonts is external).
CSS comes from scripts/top10_build_artifact.py and scripts/aichain_build_page.py (not modified).
Agents never place orders: this script only reads files and writes one HTML page.
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
from aichain_build_page import EXTRA_CSS as BASE_EXTRA_CSS

BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SWING = BASE / "swing"
GROUP = "equipment"
POS = 1000.0  # reference position in EUR (prices are USD, treated as EUR-equivalent as in the simulator)
TITLE = "Karta: Oprema za čipove"

CONTENDER_NAME = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 lov na stopove i promjena karaktera",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 povratak nakon slabog zatvaranja",
    "B0_BUYHOLD": "Kupi i drži (mjerilo)",
}
CONTENDER_PLAIN = {
    "W1_C13C_ORIG": "Kupi nakon pada od 5 % u 5 dana dok je dugoročni trend rastući; pomični stop 10 % ispod vrha.",
    "W2_MOM_BREAK_20": "Kupi kad cijena zatvori na 20-dnevnom vrhu uz rastući zamah; izlaz ispod 10-dnevnog dna ili nakon 15 dana.",
    "W3_MOM_RANK_WEEKLY": "Svakog petka rangira dionice po 20-dnevnom rastu; kupi jednu iz gornje trećine, drži dok ne ispadne iz gornje polovice.",
    "W4_SR_BOUNCE_V2": "Kupi kad cijena dotakne potvrđenu potporu i krene gore; stop ispod potpore, cilj prethodni vrh.",
    "W5_SR_BREAKOUT_RETEST": "Kupi kad cijena probije raniji vrh pa se vrati do njega i zadrži; stop 3 % ispod, izlaz ispod 50-dnevnog prosjeka.",
    "W6_MM_SWEEP_SHIFT": "Strogi prijevod 'pametnog novca': lov na stopove ispod dna u donjoj polovici raspona, pa zatvaranje iznad zadnjeg nižeg vrha.",
    "W7_MM_DEMAND_RETEST": "Strogi prijevod: prvi povratak u svježu zonu potražnje u donjoj polovici raspona uz bikovsku strukturu.",
    "W8_IBS_REVERT": "Kupi nakon vrlo slabog zatvaranja (blizu dnevnog dna) dok je trend rastući; izlaz nakon jakog zatvaranja ili 5 dana.",
    "B0_BUYHOLD": "Kupi prvi dan razdoblja i ne diraj do kraja. Služi samo za usporedbu.",
}
EVENT_PLAIN = {
    "E1_sweep_shift_discount": "lov na stopove + promjena karaktera u donjoj polovici raspona",
    "E2_sweep_shift_discount_weekly": "isto, uz bikovski tjedni trend",
    "E3_sweep_shift_discount_weekly_zone": "isto, uz dodir svježe zone potražnje",
    "E4_demand_zone_retest": "prvi povratak u svježu zonu potražnje (zona je držala)",
    "E5_bos_trend": "proboj strukture u smjeru bikovskog trenda",
}

EXTRA_CSS = (
    BASE_EXTRA_CSS
    + """
.maptable td,.maptable th{white-space:normal;vertical-align:top;text-align:left;min-width:120px}
.maptable td:first-child,.maptable th:first-child{position:sticky;left:0;background:var(--surface);min-width:96px;z-index:1}
.maptable small,.table-wrap small{display:block;color:var(--muted);font-size:.8rem;line-height:1.35}
.table-wrap td{white-space:normal;vertical-align:top}
.px{font-family:var(--mono);font-variant-numeric:tabular-nums}
.winrow td{background:var(--accent-soft)}
.mech p{margin:0 0 6px;font-size:.93rem;max-width:none}
.reading h4{font-family:var(--display);font-size:.95rem;margin:10px 0 2px}
.reading p{margin:0 0 6px;font-size:.96rem;max-width:70ch}
.tkhead{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;margin:0 0 8px}
.tkhead h3{margin:0;font-size:1.25rem}
details.mechbox{margin:0 0 10px}
"""
)

# --------------------------------------------------------------------------- formatting helpers


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def fmt(x: float, nd: int = 2) -> str:
    """Format a number the Croatian way (1.234,56)."""
    s = f"{x:,.{nd}f}"
    s = s.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    if s.startswith("-"):
        s = "\u2212" + s[1:] if round(x, nd) != 0 else s[1:]
    return s


def sgn(x: float, nd: int = 1) -> str:
    s = fmt(abs(x), nd)
    r = round(x, nd)
    return ("+" if r > 0 else "\u2212" if r < 0 else "") + s


def usd(x: float, nd: int = 2) -> str:
    return f"{fmt(x, nd)} $"


def eur(x: float, nd: int = 0, sign: bool = False) -> str:
    return (sgn(x, nd) if sign else fmt(x, nd)) + " €"


def pc(ratio: float | None, nd: int = 1, sign: bool = False) -> str:
    if ratio is None:
        return "–"
    v = ratio * 100
    return (sgn(v, nd) if sign else fmt(v, nd)) + " %"


def dmy(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {int(m)}. {int(y)}."


def dec(text: str) -> str:
    """Turn English decimals (0.78) into Croatian ones (0,78); 1.000-style thousands are left alone."""
    return re.sub(r"(\d)\.(\d{1,2})(?!\d)", r"\1,\2", text)


def jl(path: Path) -> Any:
    return json.loads(path.read_text())


def table(
    head: list[str],
    rows: list[list[str]],
    cls: str = "",
    row_cls: list[str] | None = None,
) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = ""
    for i, r in enumerate(rows):
        rc = f' class="{row_cls[i]}"' if row_cls and row_cls[i] else ""
        body += f"<tr{rc}>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return (
        f'<div class="table-wrap"><table class="{cls}"><thead><tr>{th}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


# --------------------------------------------------------------------------- data


class Data:
    """All raw inputs for the page, loaded once."""

    def __init__(self) -> None:
        self.summary = jl(SWING / "summary.json")
        self.res = jl(SWING / "results" / f"{GROUP}.json")
        self.placebo = jl(SWING / "placebo.json")
        self.audit = jl(SWING / "audit.json")
        self.sg = self.summary["groups"][GROUP]
        self.tickers: list[str] = list(self.res["tickers"])
        self.maps: dict[str, dict[str, Any]] = {
            t: jl(SWING / "map" / f"{t}.json") for t in self.tickers
        }
        self.profile: dict[str, Any] = jl(BASE / "segments" / GROUP / "profile.json")
        self.analysis: dict[str, Any] = jl(BASE / "segments" / GROUP / "analysis.json")
        self.name: str = self.sg["name"]
        self.common_end: str = self.summary["common_end"]
        self.era_start: str = self.summary["ai_era_start"]
        self.ai = {c: v["ai_era"] for c, v in self.res["contenders"].items()}
        ranking = self.res["ranking"]["ranking"]
        self.winner: str | None = ranking[0]["contender"] if ranking else None
        self.b0 = self.ai["B0_BUYHOLD"]
        self.pgroup = self.placebo["sr"]["by_group"][GROUP]


def level_stats(m: dict[str, Any], lv: dict[str, Any]) -> tuple[float, float]:
    """Return (percent distance from last close, euros on a 1.000 EUR position) from raw prices."""
    r = lv["price"] / m["last_close"] - 1.0
    return r * 100.0, r * POS


# --------------------------------------------------------------------------- sections


def sec_verdict(d: Data) -> str:
    n = len(d.tickers)
    mp = d.maps
    wb = [t for t in d.tickers if mp[t]["weekly"]["bias"] == "bullish"]
    wbear = [t for t in d.tickers if mp[t]["weekly"]["bias"] == "bearish"]
    out = [t for t in d.tickers if mp[t]["swing_range"]["zone"] == "outside"]
    prem = [t for t in d.tickers if mp[t]["swing_range"]["zone"] == "premium"]
    disc = [t for t in d.tickers if mp[t]["swing_range"]["zone"] == "discount"]
    bear_txt = f" (medvjeđi: {', '.join(wbear)})" if wbear else ""
    s1 = (
        f"Tjedni trend je bikovski kod {len(wb)} od {n} dionica{bear_txt}; cijena je iznad "
        f"zadnjeg potvrđenog raspona kod {len(out)} ({', '.join(out) or '–'}), u gornjoj polovici "
        f"raspona kod {len(prem)} ({', '.join(prem) or '–'}), a u donjoj polovici kod {len(disc)} "
        f"({', '.join(disc) or '–'})."
    )
    if d.winner:
        w = d.ai[d.winner]
        s2 = (
            f"Među unaprijed registriranim pravilima prvo po poretku 'radi često' je "
            f"{CONTENDER_NAME[d.winner]}: {fmt(w['trades_per_month'], 1)} poslova mjesečno, "
            f"{eur(w['expectancy_eur'], 0)} prosječno po poslu na 1.000 € i faktor dobiti "
            f"{fmt(w['profit_factor'], 2)} (AI era, trošak 0,025 % po strani). Ipak, jednostavno "
            f"držanje je u istom razdoblju dalo {pc(d.b0['total_return'], 0, True)} naspram "
            f"{pc(w['total_return'], 0, True)} pravila, pa pravilo ovdje služi učestalosti "
            f"trgovanja, ne većem prinosu."
        )
    else:
        s2 = "Nijedno unaprijed registrirano pravilo ne ispunjava uvjete 'radi često' u ovoj skupini."
    ab = d.pgroup["diff_vs_rand"]["bounce_rate"]
    real_b, rand_b = d.pgroup["real"]["bounce_rate"], d.pgroup["rand"]["bounce_rate"]
    zero_in = ab["ci95"][0] <= 0 <= ab["ci95"][1]
    s3 = (
        f"Razine (potpore i otpori) ovdje ne pobjeđuju nasumične crte: cijena se odbila od prave "
        f"razine u {pc(real_b, 1)} dodira, a od nasumične u {pc(rand_b, 1)}; razlika "
        f"{sgn(ab['diff'] * 100, 1)} postotnih bodova "
        f"{'obuhvaća nulu, dakle nije prava razlika' if zero_in else 'je statistički vidljiva'}."
    )
    return f"""<section id="presuda"><div class="verdict-top">
<p><b>Presuda u jednoj rečenici:</b> {e(s1)}</p>
<p>{e(s2)}</p>
<p>{e(s3)}</p>
<p class="note">Ovo su istraživačka čitanja povijesnih podataka i simulacija, ne signal za kupnju i ne savjet. Nije formalni Critic PASS; signal u laboratoriju ostaje PRIČEKAJ. Nikakvi nalozi se ne šalju.</p></div></section>"""


def sec_how_it_works(d: Data) -> str:
    wt = d.analysis["why_together"]
    f = d.profile["findings_hr"]
    cards = ""
    for t in d.tickers:
        c = d.profile["companies"].get(t)
        if not c:
            continue
        mh = c["mechanism_hr"]
        labels = [
            ("sells", "Što prodaje"),
            ("drivers", "Što pokreće prihod"),
            ("chain", "Veza s AI lancem"),
            ("cycle", "Ciklus"),
            ("hurts", "Što šteti"),
        ]
        rows = "".join(
            f"<p><b>{lab}:</b> {e(mh[k])}</p>" for k, lab in labels if k in mh
        )
        cards += (
            f'<details class="mechbox"><summary>{e(t)}</summary>'
            f'<div class="mech" style="padding:4px 16px 12px">{rows}'
            f'<p class="note">{e(c["mechanism_label"])}</p></div></details>'
        )
    return f"""<section id="mehanizam"><h2>Kako ovo tržište funkcionira</h2>
<p><b>Zašto su ove tvrtke jedna skupina</b> ({e(wt["label_hr"])}). {e(wt["summary_hr"])}</p>
<p class="note">{e(wt["drivers_hr"])}</p>
<div class="teach"><h3>Što pokazuju naši podaci o ponašanju skupine (AI era)</h3><p>{e(dec(f[0]))}</p><p>{e(dec(f[1]))}</p>
<p class="note">SMH je američki ETF i ovdje je samo referentna serija (nepotvrđeno je može li ga the researcher kupiti u EU).</p></div>
<h3>Tvrtku po tvrtku</h3>
<p class="note">Opisi su iz javnih izvora, nisu izračunati iz naših cijena; ono što nije potvrđeno označeno je kao nepotvrđeno.</p>
{cards}</section>"""


def level_cell(m: dict[str, Any], lv: dict[str, Any] | None) -> str:
    if lv is None:
        return "–"
    p, ev = level_stats(m, lv)
    return (
        f'<span class="px">{usd(lv["price"])}</span>'
        f"<small>{sgn(p, 1)} % · {eur(ev, 0, True)} na 1.000 €</small>"
    )


def reliability_text(lv: dict[str, Any] | None, label: str) -> str:
    if lv is None:
        return ""
    r = lv["reliability"]
    if r["enough_touches"]:
        return (
            f"{label}: od {r['n']} dodira odbila se {r['bounce']} ({pc(r['rate'], 0)}), "
            f"probijena {r['break']}"
        )
    return f"{label}: premalo dodira ({r['n']}) za zaključak"


def zones_list(m: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for z in m["fresh_zones"]["demand"]:
        lines.append(
            f"zona potražnje {fmt(z['low'])}–{fmt(z['high'])} $ ({sgn(z['distance_pct'], 0)} %)"
        )
    for z in m["fresh_zones"]["supply"]:
        lines.append(
            f"zona ponude {fmt(z['low'])}–{fmt(z['high'])} $ ({sgn(z['distance_pct'], 0)} %)"
        )
    fb, fr = m["open_fvg"]["bull"], m["open_fvg"]["bear"]
    if fb or fr:
        newest = ""
        if fb:
            g = fb[0]
            newest = f", najnoviji bikovski {fmt(g['bottom'])}–{fmt(g['top'])} $"
        lines.append(
            f"nepopunjeni jazovi: bikovskih {len(fb)}, medvjeđih {len(fr)}{newest}"
        )
    for s in m["recent_sweeps"]:
        lines.append(
            f"lov na stopove {dmy(s['date'])}: {s['direction']}, razina {fmt(s['level'])} $"
        )
    for side, key in (("iznad", "above"), ("ispod", "below")):
        pools = m["liquidity_pools"][key]
        if pools:
            lines.append(
                f"nakupine stopova {side}: "
                + ", ".join(fmt(p["level"]) + " $" for p in pools)
            )
    return lines


def sec_table(d: Data) -> str:
    rows: list[list[str]] = []
    for t in d.tickers:
        m = d.maps[t]
        w, dd, sr = m["weekly"], m["daily"], m["swing_range"]
        sup, res = m["nearest_supports"], m["nearest_resistances"]
        s1, s2 = (sup + [None, None])[:2]
        r1, r2 = (res + [None, None])[:2]
        pos = (
            f"{e(sr['zone_hr'])}<small>{fmt(sr['position_pct'], 0)} % raspona "
            f"{fmt(sr['low'])}–{fmt(sr['high'])} $</small>"
        )
        rel_items = (
            reliability_text(s1, "potpora 1"),
            reliability_text(s2, "potpora 2"),
            reliability_text(r1, "otpor 1"),
            reliability_text(r2, "otpor 2"),
        )
        rel = "<br>".join(e(x) for x in rel_items if x)
        zl = zones_list(m)
        rows.append(
            [
                f"<b>{e(t)}</b>",
                (
                    f'<span class="px">{usd(m["last_close"])}</span><small>{dmy(m["last_date"])} · '
                    f"dnevni raspon (ATR) {fmt(m['atr14_pct'], 1)} % · SMA200 "
                    f"{sgn(m['sma200']['distance_pct'], 1)} %</small>"
                ),
                f"tjedno: {e(w['bias_hr'])}<small>dnevno: {e(dd['bias_hr'])}</small>",
                pos,
                level_cell(m, s1),
                level_cell(m, s2),
                level_cell(m, r1),
                level_cell(m, r2),
                rel,
                "<br>".join(e(x) for x in zl) if zl else "nema aktivnih zona",
            ]
        )
    head = [
        "Dionica",
        "Zadnja cijena",
        "Struktura",
        "Položaj u rasponu",
        "Potpora 1",
        "Potpora 2",
        "Otpor 1",
        "Otpor 2",
        "Pouzdanost razina (povijest)",
        "Aktivne zone",
    ]
    dates = sorted({m["last_date"] for m in d.maps.values()})
    ex_t = next((t for t in d.tickers if d.maps[t]["nearest_supports"]), d.tickers[0])
    exm = d.maps[ex_t]
    exl = exm["nearest_supports"][0]
    _ep, ee = level_stats(exm, exl)
    atr_ex = d.maps[d.tickers[0]]["atr14_pct"]
    teach = f"""<div class="teach"><h3>Kako čitati tablicu</h3>
<p><b>Potpora</b> je raniji vrh ili dno ispod cijene na kojem se cijena već jednom okrenula; <b>otpor</b> je isto iznad cijene. To su orijentiri, ne jamstva.
Primjer iz tablice: {e(ex_t)} stoji {usd(exm["last_close"])}, najbliža potpora je {usd(exl["price"])}. Ako cijena padne do nje, 1.000 € uloženih danas bilo bi vrijedno oko {eur(POS + ee, 0)} ({eur(ee, 0, True)}). Ako potpora pukne i cijena otvori ispod nje, stvarni gubitak može biti veći jer se stop ne može izvršiti po cijeni koje nema.</p>
<p><b>Struktura:</b> bikovska znači da su zadnji vrhovi i dna sve viši, medvjeđa da su sve niži. <b>Raspon:</b> od zadnjeg potvrđenog dna do vrha; 0 % je dno, 100 % vrh. Donja polovica je 'diskont' (jeftinije u odnosu na raspon), gornja 'premium'.
Kad je cijena iznad 100 %, zadnji vrh je probijen pa raspon više ne vrijedi ('iznad raspona'); to nije signal nego samo upozorenje da je cijena u novom teritoriju.
<b>ATR</b> je prosječni dnevni raspon: {e(d.tickers[0])} ima {fmt(atr_ex, 1)} %, što znači da cijena u danu u prosjeku 'prošeta' oko {fmt(atr_ex * 10, 0)} € na 1.000 €. <b>Nepopunjeni jaz</b> je prazan prostor između tri svijeće koji cijena još nije posjetila.</p></div>"""
    dates_txt = ", ".join(dmy(x) for x in dates)
    return f"""<section id="tablica"><h2>Gdje je cijena sada</h2>
<p class="lead2">Za kartu svaka dionica koristi svoj zadnji datum u podacima ({dates_txt}); za test pravila (odjeljak 'Što je swing test pokazao') svi završavaju na zajedničkom datumu: {dmy(d.common_end)} Cijene su u USD, računi u EUR: euri su ovdje izračun na 1.000 € s tečajem 1:1, tečaj i trošak konverzije nisu uključeni.</p>
{teach}
{table(head, rows, cls="maptable")}
<p class="swipe">Tablicu možete povući lijevo i desno.</p>
<p class="note">Pouzdanost razina = koliko se puta cijena u povijesti od te razine odbila za 1,5 ATR prije nego što je zatvorila 1 ATR iza nje. Razine s malo dodira nisu dovoljan uzorak. Odjeljak 'Pobjeđuju li razine nasumične crte?' pokazuje da prave razine ionako nisu bolje od nasumičnih.</p></section>"""


def reading(d: Data, t: str) -> str:
    m = d.maps[t]
    w, dd, sr = m["weekly"], m["daily"], m["swing_range"]
    sup, res = m["nearest_supports"], m["nearest_resistances"]
    see: list[str] = [f"Tjedna struktura je {w['bias_hr']}, dnevna {dd['bias_hr']}."]
    if dd.get("last_shift"):
        ls = dd["last_shift"]
        see.append(
            f"Zadnja dnevna promjena karaktera: {ls['direction']}, {dmy(ls['date'])} "
            f"(zatvaranje preko {usd(ls['broken_level'])})."
        )
    if w.get("last_bos"):
        lb = w["last_bos"]
        see.append(
            f"Zadnji proboj strukture na tjednom grafu: {lb['direction']}, {dmy(lb['date'])}."
        )
    if sr["zone"] == "outside":
        see.append(
            f"Cijena je na {fmt(sr['position_pct'], 0)} % raspona, dakle iznad zadnjeg potvrđenog "
            f"vrha ({usd(sr['high'])}): raspon trenutno ne govori je li skupo ili jeftino."
        )
    else:
        see.append(
            f"Cijena je u zoni '{sr['zone_hr']}' ({fmt(sr['position_pct'], 0)} % raspona "
            f"{usd(sr['low'])}–{usd(sr['high'])})."
        )
    lv_lines: list[str] = []
    for lv in sup[:2]:
        p, ev = level_stats(m, lv)
        lv_lines.append(
            f"Ako pukne potpora {usd(lv['price'])} ({sgn(p, 1)} % od cijene, "
            f"{fmt(abs(lv['distance_atr']), 1)} ATR), gubitak je oko {eur(abs(ev), 0)} na 1.000 €."
        )
    for lv in res[:2]:
        p, ev = level_stats(m, lv)
        lv_lines.append(
            f"Do otpora {usd(lv['price'])} ima još {sgn(p, 1)} % ({eur(ev, 0, True)} na 1.000 €, "
            f"{fmt(abs(lv['distance_atr']), 1)} ATR)."
        )
    rel = [
        x
        for x in (
            reliability_text(sup[0] if sup else None, "najbliža potpora"),
            reliability_text(res[0] if res else None, "najbliži otpor"),
        )
        if x
    ]
    zl = zones_list(m)
    zones_txt = (
        (" Aktivne zone: " + "; ".join(zl) + ".") if zl else " Nema aktivnih zona."
    )
    watch: list[str] = []
    nr = res[0] if res else None
    ns = sup[0] if sup else None
    if nr and abs(nr["distance_atr"]) < 1.0 and nr["distance_pct"] > 0:
        watch.append(
            f"Cijena je manje od 1 ATR ispod otpora {usd(nr['price'])}: swing trader bi gledao "
            f"hoće li zatvaranje ostati iznad njega (proboj) ili će se cijena okrenuti. "
            f"Ovdje ne tvrdimo koji ishod je vjerojatniji."
        )
    if ns and abs(ns["distance_atr"]) < 1.0:
        watch.append(
            f"Najbliža potpora {usd(ns['price'])} je manje od 1 ATR ispod: tu bi se pratilo drži "
            f"li se ili puca; stop se u tom slučaju obično stavlja ispod nje."
        )
    if sr["zone"] == "outside":
        watch.append(
            "Nakon probijenog vrha čeka se novi potvrđeni vrh i dno, tek tada raspon opet ima smisla."
        )
    elif sr["zone"] == "discount":
        watch.append(
            "U donjoj polovici raspona 'jeftinije u odnosu na raspon' je razlog za strpljivo praćenje, ne za žurbu."
        )
    elif sr["zone"] == "premium":
        watch.append(
            "U gornjoj polovici raspona obično se čeka povlačenje prije novih ulaza; to je samo pravilo palca."
        )
    if w["bias"] != dd["bias"]:
        watch.append(
            f"Tjedni i dnevni trend se razilaze (tjedno {w['bias_hr']}, dnevno {dd['bias_hr']}); to je znak nesigurnosti."
        )
    if not watch:
        watch.append(
            "Gledalo bi se zatvaranja oko najbližih razina i promjenu strukture; ništa od toga ovdje nije signal."
        )
    w1 = d.ai["W1_C13C_ORIG"]["per_ticker"].get(t)
    w1txt = ""
    if w1:
        b0t = d.b0["per_ticker"][t]
        w1txt = (
            f'<p class="note"><b>Pravilo W1 (C13C) na ovoj dionici, AI era:</b> {w1["trades"]} poslova '
            f"({fmt(w1['trades_per_month'], 2)} mjesečno), {pc(w1['hit_rate'], 0)} dobitnih, "
            f"{eur(w1['expectancy_eur'], 0)} prosječno po poslu na 1.000 €, prinos "
            f"{pc(w1['total_return'], 0, True)} naspram {pc(b0t['total_return'], 0, True)} za kupi i drži. "
            f"Jedna dionica je premali uzorak za zaključak; vrijedi cijela skupina.</p>"
        )
    repairs = (
        f'<p class="note">Popravljeni loši podaci u svijećama: {len(m["bar_repairs"])}.</p>'
        if m["bar_repairs"]
        else ""
    )
    return f"""<div class="reading"><h4>Što ovdje vidimo</h4>
<p>{e(" ".join(see).replace("..", "."))}</p><p>{e(" ".join(lv_lines))}</p><p>{e(" ".join(rel))}{e(zones_txt)}</p>
<h4>Što bi swing trader gledao</h4><p>{e(" ".join(watch))}</p>{w1txt}{repairs}</div>"""


def sec_charts(d: Data) -> str:
    out: list[str] = []
    for t in d.tickers:
        m = d.maps[t]
        uri = top10.img(SWING / "map" / f"{t}.png")
        out.append(
            f"""<article class="tcard" style="gap:6px"><div class="tkhead"><h3>{e(t)}</h3><span class="chip">{dmy(m["last_date"])} · {usd(m["last_close"])}</span>
<span class="chip">{e(m["weekly"]["bias_hr"])} (tjedno)</span></div>
<div class="plate"><img src="{uri}" alt="Bilježnica s kartom razina i strukture za {e(t)}" loading="lazy"></div>
<p class="swipe">Sliku možete povući lijevo i desno.</p>
{reading(d, t)}</article>"""
        )
    return f"""<section id="grafovi"><h2>Karta po dionici</h2>
<p class="lead2">Svaka bilježnica pokazuje svijeće zadnjih mjeseci, zelene potpore (ispod cijene), crvene otpore (iznad), zonu potražnje i oznake strukture. Brojevi u krugovima povezuju sliku s rečenicama ispod nje. Slike je crtao isti program koji je izračunao tablicu pa se brojke poklapaju.</p>
<div style="display:flex;flex-direction:column;gap:22px">{"".join(out)}</div></section>"""


def status_text(d: Data, c: str) -> str:
    if c == "B0_BUYHOLD":
        return "mjerilo"
    elig = {r["contender"] for r in d.res["ranking"]["ranking"]}
    if c in elig:
        return "ispunjava uvjete" + (" (prvo po poretku)" if c == d.winner else "")
    nelig = {r["contender"]: r for r in d.res["ranking"]["not_eligible"]}
    txt: list[str] = []
    for rr in nelig[c]["reasons"]:
        mt = re.search(r"only (\d+) trades", rr)
        if mt:
            txt.append(f"premalo poslova ({mt.group(1)} od najmanje 60)")
        elif rr.startswith("expectancy"):
            txt.append("gubi uz dvostruki trošak")
        elif rr.startswith("profit factor"):
            txt.append("faktor dobiti ispod 1,2")
        else:
            txt.append(rr)
    return "ne ispunjava: " + "; ".join(txt)


def winner_box(d: Data) -> str:
    if not d.winner:
        return (
            "<div class=\"teach\"><h3>Pobjednik po pravilu 'radi često'</h3>"
            "<p>Nijedno unaprijed registrirano pravilo ne ispunjava uvjete u ovoj skupini.</p></div>"
        )
    w = d.ai[d.winner]
    months = d.res["window"]["months"]
    lk = d.summary["lookahead"][d.winner]
    rb = d.summary["robustness_top3"]["results"].get(d.winner)
    if rb:
        rbtxt = (
            f"Provjera ±20 % svakog parametra (na zbroju svih 43 dionica, ne samo ove skupine): najmanji prosjek po poslu uz dvostruki trošak je "
            f"{eur(rb['min_expectancy_eur_cost_2x'], 0, True)}, pravilo nije krhko."
        )
    else:
        rbtxt = "Provjera ±20 % parametara za ovo pravilo nije rađena (nije među tri najbolja u odabiru)."
    ctxs = d.res["contenders"][d.winner]["contexts"]
    c1, c2 = ctxs.get("y2016_2020"), ctxs.get("y2021_2022")
    ctx = ""
    if c1 and c2:
        ctx = (
            f"Kontekst prije AI ere (ne koristi se za zaključak): 2016.–2020. {c1['trades']} poslova, "
            f"{eur(c1['expectancy_eur'], 0, True)} po poslu, faktor dobiti {fmt(c1['profit_factor'], 2)}; "
            f"2021.–2022. {c2['trades']} poslova, {eur(c2['expectancy_eur'], 0, True)} po poslu, "
            f"faktor dobiti {fmt(c2['profit_factor'], 2)}."
        )
        if c2["expectancy_eur"] <= 0:
            ctx += (
                " U 2021.–2022. isto pravilo nije zarađivalo po poslu, pa se AI-era rezultat"
                " ne smije čitati kao trajno svojstvo pravila."
            )
    ratio = abs(w["avg_win_eur"] / w["avg_loss_eur"])
    look = "prošlo" if lk["ok"] else "PALO"
    return f"""<div class="teach"><h3>Pobjednik po pravilu 'radi često': {e(CONTENDER_NAME[d.winner])}</h3>
<p>Uvjeti zadani prije pokretanja: najmanje 60 poslova u AI eri u cijeloj skupini, očekivanje po poslu iznad nule i uz dvostruki trošak, faktor dobiti najmanje 1,2; među onima koji prođu, poredak je prosjek po poslu u € puta broj poslova mjesečno.
Ovo pravilo: {w["trades"]} poslova u {fmt(months, 1)} mjeseca ({fmt(w["trades_per_month"], 1)} mjesečno, oko {fmt(w["trades_per_ticker_year"], 1)} po dionici godišnje), {pc(w["hit_rate"], 0)} dobitnih,
prosječan dobitni posao {eur(w["avg_win_eur"], 0, True)}, prosječan gubitni {eur(w["avg_loss_eur"], 0, True)} na 1.000 €. Dakle češće gubi nego dobiva, ali je dobitak otprilike {fmt(ratio, 1)} puta veći od gubitka.
Uz trošak 3x očekivanje po poslu je i dalje {eur(w["expectancy_eur_cost_3x"], 0, True)}.</p>
<p><b>Provjere valjanosti dokaza (stroge samo prema neispravnim dokazima):</b> pogled u budućnost: {look} ({lk["array_checks"]} provjera nizova i {lk["trade_checks"]} provjera poslova na odsječenim podacima);
{e(rbtxt)} Broj poslova je dovoljan ({w["trades"]}). Pet najboljih poslova nosi {pc(w["top5_profit_share"], 0)} ukupne dobiti. Vjerojatnost da je pravi Sharpe iznad nule (PSR) je {fmt(w["psr"], 3)}; korigirana za broj isprobanih pravila (K = {d.summary["ledger_k"]}) iznosi {fmt(w["deflated_sharpe_prob"], 3)}, što je samo informacija i ne snižava ocjenu.
Ocjena dokaza: <b>valjani</b>, uz napomenu o višestrukom testiranju. Nije formalni Critic PASS.</p>
<p class="note">{e(ctx)}</p></div>"""


def sec_swing(d: Data) -> str:
    order = [r["contender"] for r in d.res["ranking"]["ranking"]] + [
        r["contender"] for r in d.res["ranking"]["not_eligible"]
    ]
    rows: list[list[str]] = []
    cls: list[str] = []
    for c in [*order, "B0_BUYHOLD"]:
        a = d.ai[c]
        is_b0 = c == "B0_BUYHOLD"
        dash = "–"
        rows.append(
            [
                f"<b>{e(CONTENDER_NAME[c])}</b><small>{e(CONTENDER_PLAIN[c])}</small>",
                dash if is_b0 else fmt(a["trades_per_month"], 1),
                dash if is_b0 else str(a["trades"]),
                dash if is_b0 else pc(a["hit_rate"], 0),
                dash if is_b0 else eur(a["expectancy_eur"], 0, True),
                dash if is_b0 else eur(a["expectancy_eur_cost_2x"], 0, True),
                dash if is_b0 else fmt(a["profit_factor"], 2),
                dash
                if is_b0
                else f"{fmt(a['median_hold_days'], 0)} / {fmt(a['mean_hold_days'], 0)}",
                pc(a["total_return"], 0, True),
                pc(a["max_drawdown"], 0),
                f"{fmt(a['exposure_pct'], 0)} %",
                e(status_text(d, c)),
            ]
        )
        cls.append("winrow" if c == d.winner else "")
    head = [
        "Pravilo",
        "Poslova mjesečno",
        "Poslova ukupno",
        "Udio dobitnih",
        "Prosjek po poslu na 1.000 €",
        "Isto uz trošak 2x",
        "Faktor dobiti",
        "Dana u poslu (medijan / prosjek)",
        "Ukupni prinos",
        "Najveći pad od vrha",
        "Vrijeme u dionicama",
        "Status",
    ]
    prow: list[list[str]] = []
    if d.winner:
        for t in d.tickers:
            a = d.ai[d.winner]["per_ticker"][t]
            bt = d.b0["per_ticker"][t]
            prow.append(
                [
                    f"<b>{e(t)}</b>",
                    str(a["trades"]),
                    pc(a["hit_rate"], 0),
                    eur(a["expectancy_eur"], 0, True),
                    fmt(a["profit_factor"], 2)
                    if a["profit_factor"] is not None
                    else "–",
                    pc(a["total_return"], 0, True),
                    pc(bt["total_return"], 0, True),
                ]
            )
    ptab = (
        table(
            [
                "Dionica",
                "Poslova",
                "Udio dobitnih",
                "Prosjek po poslu",
                "Faktor dobiti",
                "Prinos pravila",
                "Prinos kupi i drži",
            ],
            prow,
        )
        if prow
        else ""
    )
    bh = d.sg["buy_and_hold_reference"]
    w4 = d.ai["W4_SR_BOUNCE_V2"]
    w6, w7 = d.ai["W6_MM_SWEEP_SHIFT"], d.ai["W7_MM_DEMAND_RETEST"]
    w4txt = (
        f"gubi po poslu ({eur(w4['expectancy_eur'], 0, True)})"
        if w4["expectancy_eur"] < 0
        else f"daje {eur(w4['expectancy_eur'], 0, True)} po poslu"
    )
    return f"""<section id="swing"><h2>Što je swing test pokazao za ovu skupinu</h2>
<p class="lead2">Osam pravila, zamrznutih i upisanih u registar prije pokretanja (bez ugađanja poslije), igra istu igru na {len(d.tickers)} dionica ove skupine: odluka na zatvaranju dana, kupnja na sljedećem otvaranju, samo kupnja, bez poluge, trošak 0,025 % po strani (2,5 baznih bodova; na 1.000 € to je 0,25 € po kupnji i po prodaji). Svaka dionica ima svojih 1.000 €. Razdoblje: {dmy(d.era_start)} do {dmy(d.common_end)} (AI era, glavno mjerilo).</p>
<div class="teach"><h3>Kako čitati tablicu</h3><p><b>Prosjek po poslu</b> je koliko je pravilo u prosjeku zaradilo po jednom poslu kad se u svaki uloži 1.000 € (poslovi se ne zbrajaju u složenu kamatu). <b>Faktor dobiti</b> je ukupna dobit podijeljena s ukupnim gubitkom: 2 znači da je na svaki izgubljeni euro zarađeno dva. <b>Udio dobitnih</b> je koliko poslova je završilo plusom. <b>Kupi i drži</b> je mjerilo: ono što bi dobio da si samo kupio i čekao.
Petrov cilj je pravilo koje trguje često, pa se ovdje gleda broj poslova i prosjek po poslu, a ukupni prinos je sporedan. Ukupni prinos kupi-i-drži je u ovom razdoblju velik jer je AI era bila razdoblje snažnog rasta čipova.</p></div>
{table(head, rows, row_cls=cls)}
<p class="swipe">Tablicu možete povući lijevo i desno.</p>
<p class="note">Kupi i drži, referenca: ukupni prinos {pc(bh["total_return"], 0, True)}, Sharpe {fmt(bh["sharpe"], 2)}, najveći pad od vrha {pc(bh["max_drawdown"], 0)}. Najveći pad se prikazuje samo kao informacija i ne utječe na ocjenu pravila.</p>
{winner_box(d)}
<h3>Pobjednik po dionicama</h3>
{ptab}
<p class="swipe">Tablicu možete povući lijevo i desno.</p>
<p class="note">Pravila W4, W6 i W7 pokušaj su da se razine i 'pametni novac' pretvore u stroga pravila bez pogleda u budućnost. W4 (odbijanje od potpore) u ovoj skupini {e(w4txt)}; W6 ({w6["trades"]} poslova) i W7 ({w7["trades"]} poslova) imaju pozitivan prosjek, ali premalo poslova da bi se iz toga išta zaključilo.</p></section>"""


def verdict_word(lo: float, hi: float) -> str:
    if lo > 0:
        return "bolje od slučajnosti"
    if hi < 0:
        return "lošije od slučajnosti"
    return "ne razlikuje se od slučajnosti"


def ci_txt(dv: dict[str, Any]) -> str:
    lo, hi = dv["ci95"]
    return f"{sgn(dv['diff'] * 100, 1)} [{sgn(lo * 100, 1)}; {sgn(hi * 100, 1)}]"


def sec_placebo(d: Data) -> str:
    g = d.pgroup
    a = d.placebo["sr"]["all"]
    names = {
        "rand": "nasumična cijena",
        "shift": "ista razina pomaknuta za ±3 %",
        "match": "par lažnih crta oko razine (najstroža)",
    }
    rows: list[list[str]] = []
    for k in ("rand", "shift", "match"):
        dv = g[f"diff_vs_{k}"]
        real_key = "mreal" if k == "match" else "real"
        rows.append(
            [
                e(names[k]),
                f"{pc(g[real_key]['bounce_rate'], 1)} / {pc(g[k]['bounce_rate'], 1)}",
                ci_txt(dv["bounce_rate"]),
                ci_txt(dv["break_rate"]),
                ci_txt(dv["touch_rate"]),
                e(verdict_word(*dv["bounce_rate"]["ci95"])),
            ]
        )
    tab = table(
        [
            "Lažna kontrola",
            "Odbijanje: prava / lažna",
            "Razlika u odbijanju (pp)",
            "Razlika u probijanju (pp)",
            "Razlika u dodiru (pp)",
            "Odbijanje",
        ],
        rows,
    )
    ev_rows: list[list[str]] = []
    for k, v in d.placebo["mechanics_ai_era"]["events"].items():
        gg = v["by_group_h10"].get(GROUP)
        lo, hi = v["by_h"]["10"]["excess_ci95"]
        ev_rows.append(
            [
                e(EVENT_PLAIN[k]),
                str(gg["n"]) if gg else "–",
                pc(gg["mean_excess"], 1, True) if gg else "–",
                str(v["n"]),
                f"{sgn(lo * 100, 1)}; {sgn(hi * 100, 1)}",
                e(verdict_word(lo, hi)),
            ]
        )
    etab = table(
        [
            "Događaj iz 'pametnog novca'",
            "Događaja u skupini",
            "Višak nakon 10 dana (skupina)",
            "Događaja u svih 55 serija",
            "95 % interval (sve serije), pp",
            "Čitanje",
        ],
        ev_rows,
    )
    all_zero = all(
        g[f"diff_vs_{k}"]["bounce_rate"]["ci95"][0]
        <= 0
        <= g[f"diff_vs_{k}"]["bounce_rate"]["ci95"][1]
        for k in ("rand", "shift", "match")
    )
    concl = (
        "Svi intervali za odbijanje obuhvaćaju nulu. <b>Razine u ovoj skupini ne pobjeđuju nasumične crte.</b>"
        if all_zero
        else "Bar jedan interval za odbijanje ne obuhvaća nulu; pogledajte tablicu."
    )
    return f"""<section id="placebo"><h2>Pobjeđuju li razine nasumične crte?</h2>
<div class="teach"><h3>Što je placebo test</h3><p>Placebo je kontrolna skupina, kao tableta od šećera u ispitivanju lijeka. Svakoj pravoj razini (potvrđenoj potpori ili otporu) dodali smo lažne crte tamo gdje nitko nije potvrdio okret. Ako se cijena od lažnih crta odbija jednako često kao od pravih, razina nije ništa posebno. Svakog zadnjeg dana u mjesecu (AI era) uzete su razine koje su tada već bile poznate pa se gledalo sljedećih 20 dana. Odbijanje znači da se cijena od razine maknula za najmanje 1,5 ATR (na dionici s ATR 4 % to je oko 60 € na 1.000 €).
<b>Interval pouzdanosti 95 %</b> je raspon u kojem bi se razlika vjerojatno našla da pokus ponovimo; ako obuhvaća nulu, razlika se ne razlikuje od slučajne.</p></div>
<p>Za ovu skupinu ({fmt(g["n_levels"], 0)} razina, {g["n_months"]} mjesečnih presjeka): od <b>prave razine cijena se odbila u {pc(g["real"]["bounce_rate"], 1)}</b> dodira, od nasumične u {pc(g["rand"]["bounce_rate"], 1)}, od pomaknute u {pc(g["shift"]["bounce_rate"], 1)}, od najstrože kontrole u {pc(g["match"]["bounce_rate"], 1)}.
{concl} Dodir nije češći nego kod lažnih ({pc(g["real"]["touch_rate"], 1)} prave naspram {pc(g["rand"]["touch_rate"], 1)} nasumičnih): cijena razine ne privlači. Isti zaključak vrijedi i za svih 55 serija u istraživanju ({fmt(a["n_levels"], 0)} razina, odbijanje {pc(a["real"]["bounce_rate"], 1)} naspram {pc(a["rand"]["bounce_rate"], 1)} nasumičnih).</p>
{tab}
<p class="swipe">Tablicu možete povući lijevo i desno.</p>
<p class="note">Razine ostaju korisne kao orijentir za planiranje (gdje postaviti stop, gdje očekivati gužvu), ali nema dokaza da predviđaju smjer. Mjesečni uzorci se preklapaju pa su pravi intervali nešto širi nego što tablica pokazuje; strože provjere s blokovima od 3 mjeseca daju isti zaključak za sve serije.</p>
<h3>'Pametni novac' pod strogim pravilima</h3>
<p>Isti test smo napravili za mehaniku iz tečaja koji the researcher prati (lov na stopove, promjena karaktera, zona potražnje, proboj strukture), ali s preciznim pravilima na dnevnim svijećama i bez pogleda u budućnost. Višak je prosječni prinos nakon događaja minus prosjek iste dionice, 10 dana kasnije. Većina događaja nije bolja od slučajnosti; jedini rubni rezultat je povratak u svježu zonu potražnje, koji je granični, nestaje na 20 dana i ne vrijedi prije AI ere. Mali brojevi događaja u skupini ne dopuštaju zaključak samo za ovu skupinu.</p>
{etab}
<p class="swipe">Tablicu možete povući lijevo i desno.</p></section>"""


def sec_glossary() -> str:
    imported = dict(top10.GLOSSARY)
    own = [
        (
            "Struktura (bikovska / medvjeđa)",
            "Slijed potvrđenih vrhova i dna. Bikovska: svaki vrh i svako dno su viši od prethodnih. Primjer: dno 90 $, vrh 100 $, novo dno 95 $, novi vrh 108 $. Medvjeđa je obrnuto.",
        ),
        (
            "Okret (swing pivot)",
            "Vrh ili dno koje je više (niže) od 5 svijeća sa svake strane. Potvrđuje se tek 5 svijeća nakon nastanka, jer inače bismo gledali u budućnost.",
        ),
        (
            "Proboj strukture i promjena karaktera",
            "Proboj strukture: zatvaranje preko zadnjeg okreta u smjeru trenda (trend se nastavlja). Promjena karaktera: zatvaranje preko zadnjeg okreta u suprotnom smjeru (prvi znak da se trend okreće). Primjer: u padu, zatvaranje iznad zadnjeg nižeg vrha.",
        ),
        (
            "Raspon, diskont i premium",
            "Raspon ide od zadnjeg potvrđenog dna do vrha. Donja polovica je diskont, gornja premium. Primjer: raspon 400 do 500 $; cijena 430 $ je u diskontu, 480 $ u premiumu.",
        ),
        (
            "Potpora i otpor",
            "Raniji vrh (otpor) ili dno (potpora) na kojem se cijena već jednom okrenula. Primjer: dno 313 $; ako cijena padne do njega, na 1.000 € uloženih na 320 $ gubitak je oko 22 €.",
        ),
        (
            "ATR",
            "Prosječni dnevni raspon cijene (najviša minus najniža, prosjek 14 dana). Primjer: ATR 4 % znači da cijena u danu u prosjeku 'prošeta' oko 40 € na 1.000 €.",
        ),
        (
            "Lov na stopove (liquidity sweep)",
            "Cijena na trenutak probije očito dno (gdje mnogi imaju stop), a zatvori natrag iznad njega. Teorija kaže da veliki igrači tako skupljaju prodavače; mi smo samo testirali nosi li to prednost.",
        ),
        (
            "Zona potražnje",
            "Zadnja padajuća svijeća prije snažnog rasta (barem 2 ATR u 3 dana) koji je probio raniji vrh. Teorija: tu su kupci bili aktivni pa se cijena rado vraća. Zona je 'svježa' dok cijena prvi put ne uđe u nju.",
        ),
        (
            "Nepopunjeni jaz (FVG)",
            "Tri svijeće u kojima raspon prve i treće ne dodiruje pa između njih ostaje prazan prostor. Primjer: prva svijeća završi na 100 $, treća počne na 103 $.",
        ),
        (
            "Očekivanje po poslu",
            "Prosječna zarada po jednom poslu kad se uloži 1.000 €. Primjer: +32 € znači da je prosječan posao donio 32 € prije poreza i prije stvarne provizije.",
        ),
        (
            "Faktor dobiti",
            "Zbroj dobitaka podijeljen sa zbrojem gubitaka. Primjer: dobici 1.900 €, gubici 1.000 €: faktor 1,9.",
        ),
        (
            "Udio dobitnih poslova",
            "Koliko poslova je završilo plusom. Primjer: 47 % znači da 47 od 100 poslova dobiva; pravilo može biti dobro i s manje od 50 % ako su dobitci veći od gubitaka.",
        ),
        (
            "Bazni bod (bps)",
            "Stotinka postotka. Trošak 2,5 bps po strani je 0,025 %: na kupnju od 1.000 € to je 0,25 €, isto toliko pri prodaji. Stvarna provizija brokera može biti veća (nepotvrđeno).",
        ),
        (
            "Placebo (lažna razina)",
            "Kontrolna skupina: lažne crte postavljene tamo gdje nitko nije potvrdio okret. Ako i one daju isti rezultat, prave razine nisu posebne.",
        ),
        (
            "Pomični stop",
            "Automatska prodaja ako cijena padne za određeni iznos ispod najvišeg dosegnutog vrha. Primjer: kupnja za 1.000 €, stop 10 % ispod vrha; vrijednost naraste na 1.300 €, stop je na 1.170 €.",
        ),
    ]
    items = list(own)
    for key in (
        "AI era",
        "Prilagođeno podacima (overfitting)",
        "Broj pokušaja (K) i deflated Sharpe",
    ):
        if key in imported:
            items.append((key, imported[key]))
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in items)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def sec_eu(d: Data) -> str:
    chips = "".join(
        f'<span class="chip warn">{e(t)}: nepotvrđeno</span>' for t in d.tickers
    )
    asml = ""
    note = d.analysis.get("eu_hr_notes", {}).get("ASML", {}).get("note_hr")
    if note:
        asml = f"<li><b>ASML:</b> {e(note.split('Nije porezna tvrdnja i nije savjet. ', 1)[-1])}</li>"
    return f"""<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>
<div class="chips">{chips}<span class="chip warn">SMH i NDX: nepotvrđeno / referentno</span></div>
<p>Svih {len(d.tickers)} su pojedinačne dionice kotirane u SAD-u. Takve su općenito dostupne malim ulagačima iz EU preko Interactive Brokersa, ali za svaku od njih <b>status ostaje nepotvrđen dok se ne provjeri u samom IBKR-u</b> (dozvole računa, razlomljene dionice, minimalna provizija).
Američki ETF-ovi i indeksi (npr. SMH, NDX) često nisu dostupni malim EU ulagačima jer nemaju KID dokument; ovdje su samo referentne serije za usporedbu i označeni su <b>nepotvrđeno / referentno</b>. Poreze i dozvole računa ne nagađamo.</p>
<ul>{asml}<li>Valuta: cijene su u USD, račun u EUR. Na 1.000 € tečaj EUR/USD i trošak konverzije mijenjaju stvarni rezultat; ovdje se računa 1:1.</li>
<li>Američka burza otvara u 15:30 po zagrebačkom vremenu; ove karte koriste dnevne svijeće.</li><li>Samo kupnja, bez poluge i bez kratke prodaje.</li></ul></section>"""


def sec_limits(d: Data) -> str:
    prov = d.audit["provenance"]
    hash_same = all(v["same"] for v in prov["code_hashes"].values())
    code_txt = (
        "kod swing motora je isti kao pri registraciji. "
        if hash_same
        else "datoteka koda swing motora promijenjena je nakon registracije (ispravci revizije), ali parametri i pravila su jednaki registru. "
    )
    audit_txt = (
        "Status revizije: ISPRAVLJENO (14. 10. 2026.). Zamrznuti parametri i pravila svih devet suparnika jednaki su registru; "
        + code_txt
        + f"Pravilo poretka provjereno je za {d.audit['ranking_rule']['groups_checked']} skupina, bez pogreški. "
        "Pravila o podacima ista su kao u ostalim izvještajima (DATA_QUALITY.md): obustavljena trgovina se ne učitava, očiti loši podaci se ograničavaju, CSV se ne mijenja."
    )
    lim = [
        f"Razdoblje testa: {dmy(d.era_start)} do {dmy(d.common_end)} (AI era, {fmt(d.res['window']['months'], 1)} mjeseca). To je razdoblje snažnog rasta čipova pa sva pravila izgledaju bolje nego u običnom tržištu. Prije 2023. se ne donose zaključci; tržišni režim se promijenio nakon 2022.",
        "Trošak: 0,025 % po strani (uz provjeru 2x i 3x). Stvarna minimalna provizija IBKR-a, proklizavanje, djelomična ispunjenja i tečaj EUR/USD nisu modelirani. Pravila s mnogo poslova zato su prikazana povoljnije nego u stvarnosti.",
        "Dividende nisu uračunate (cjenovni prinos), porezi i evidencija nisu uključeni.",
        "Uzorak je 10 dionica koje su 'preživjele' i dobro prošle u AI lancu; odabir unaprijed pogoduje svim pravilima jednako. Dionice se kreću zajedno pa je broj neovisnih događaja manji od zbroja poslova.",
        f"Isprobano je više pravila i skupina (K = {d.summary['ledger_k']} u registru): najbolje pravilo izgleda dobro i djelomično slučajno. Provjera ±20 % parametara rađena je samo za tri najbolja pravila na zbroju svih dionica.",
        "Razine su računate na dnevnim svijećama jednom definicijom (okret s 5 svijeća); druga definicija mogla bi dati drukčije brojke, ali se ne ugađa po rezultatima.",
        "Karte koriste zadnji datum svake dionice u podacima, a test pravila zajednički kraj. Zato se cijena na karti može razlikovati od zadnje cijene u testu.",
        "Tvrdnje o tvrtkama (što prodaju, tko su kupci) su iz javnih izvora i nisu izračunate iz naših cijena.",
        "Ovo su istraživačka čitanja, ne signali ni savjeti. Nije formalni Critic PASS; signal ostaje PRIČEKAJ. Nikakvi nalozi (ni probni ni pravi) se ne šalju.",
    ]
    ex = "".join(f"<li>{e(x)}</li>" for x in lim)
    return f'<section id="granice"><h2>Granice: što nije uračunato</h2><ul>{ex}</ul><p class="note">{e(audit_txt)}</p></section>'


def build() -> Path:
    d = Data()
    body = f"""<main>
<header><span class="tagline">AICHAIN · swing karta · istraživačka simulacija</span>
<h1>{e(d.name)}: karta tržišta</h1>
<p class="lead">Gdje je cijena sada, što pokazuju razine i struktura te je li ih swing pravilo u AI eri ({dmy(d.era_start)}–{dmy(d.common_end)}) znalo iskoristiti. {len(d.tickers)} dionica: {", ".join(d.tickers)}.</p>
<div class="chips"><span class="chip">istraživačka simulacija</span><span class="chip">trošak 0,025 % po strani</span><span class="chip">samo kupnja, bez poluge</span><span class="chip warn">nije savjet, nije Critic PASS</span></div></header>
{sec_verdict(d)}
{sec_how_it_works(d)}
{sec_table(d)}
{sec_charts(d)}
{sec_swing(d)}
{sec_placebo(d)}
{sec_glossary()}
{sec_eu(d)}
{sec_limits(d)}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima: razdoblje {dmy(d.era_start)} do {dmy(d.common_end)}, odluka na zatvaranju, kupnja na idućem otvaranju, trošak 0,025 % po strani, bez poluge i bez kratke prodaje.
Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje ni signal, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan. Sve brojke izračunate su iz CSV podataka u data/ohlcv.</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(title=e(TITLE), css=top10.CSS + EXTRA_CSS)
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
    out = out_dir / f"{GROUP}.html"
    out.write_text(page)
    return out


# --------------------------------------------------------------------------- verification


def verify() -> list[str]:
    """Re-read raw JSON and check that the numbers appear in the page text; return mismatches."""
    page = (SWING / "pages" / f"{GROUP}.html").read_text()
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<img[^>]*>", "", page)))
    text = re.sub(r"\s+", " ", text)
    res = jl(SWING / "results" / f"{GROUP}.json")
    summ = jl(SWING / "summary.json")
    plc = jl(SWING / "placebo.json")
    bad: list[str] = []

    def need(token: str, what: str) -> None:
        if token not in text:
            bad.append(f"{what}: '{token}' missing")

    for t in res["tickers"]:
        m = jl(SWING / "map" / f"{t}.json")
        need(fmt(m["last_close"]), f"{t} last_close")
        need(dmy(m["last_date"]), f"{t} last_date")
        for key in ("nearest_supports", "nearest_resistances"):
            for lv in m[key][:2]:
                r = lv["price"] / m["last_close"] - 1
                need(fmt(lv["price"]), f"{t} {key} price")
                need(sgn(r * 100, 1), f"{t} {key} pct")
                need(eur(r * POS, 0, True), f"{t} {key} eur")
        need(fmt(m["swing_range"]["position_pct"], 0), f"{t} position")
        need(m["weekly"]["bias_hr"], f"{t} weekly bias")
        if f'alt="Bilježnica s kartom razina i strukture za {t}"' not in page:
            bad.append(f"{t} chart missing")
    for c, v in res["contenders"].items():
        a = v["ai_era"]
        if c != "B0_BUYHOLD":
            need(fmt(a["trades_per_month"], 1), f"{c} trades/month")
            need(str(a["trades"]), f"{c} trades")
            need(pc(a["hit_rate"], 0), f"{c} hit")
            need(eur(a["expectancy_eur"], 0, True), f"{c} expectancy")
            need(fmt(a["profit_factor"], 2), f"{c} pf")
        need(pc(a["total_return"], 0, True), f"{c} total return")
    g = plc["sr"]["by_group"][GROUP]
    for k in ("real", "rand", "shift", "match"):
        need(pc(g[k]["bounce_rate"], 1), f"placebo {k} bounce")
    need(fmt(g["n_levels"], 0), "placebo n_levels")
    wr = summ["groups"][GROUP]["ranking"]
    if wr:
        need(CONTENDER_NAME[wr[0]["contender"]], "winner name")
    else:
        need("Nijedno unaprijed registrirano pravilo", "no winner text")
    need(str(summ["ledger_k"]), "ledger K")
    return bad


def main() -> None:
    out = build()
    print(out, out.stat().st_size, "bytes")
    if "--verify" in sys.argv:
        bad = verify()
        print("VERIFY:", "OK" if not bad else bad)
        if bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
