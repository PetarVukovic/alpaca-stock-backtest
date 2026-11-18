"""Build the Croatian 'Karta trzista' artifact page for the group ai_chips_logic.

Usage:
  .venv/bin/python scripts/aichain_map_page_ai_chips_logic.py            # build the page
  .venv/bin/python scripts/aichain_map_page_ai_chips_logic.py --verify   # build, then re-check numbers vs JSON

Inputs (read only): swing/map/{T}.json + {T}.png, swing/results/{group}.json, swing/summary.json, swing/placebo.json,
swing/registration.json, swing/audit.json, segments/{group}/profile.json + analysis.json (if present), data/ohlcv/{T}_1d.csv
(only for a gap check). Output: swing/pages/{group}.html (charts embedded as data URIs, Google Fonts only).
CSS tokens and the glossary come from scripts/top10_build_artifact.py (not modified). Never places orders.
"""

from __future__ import annotations

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
EUR_UNIT = 1000.0
GROUP = "ai_chips_logic"

EXTRA_CSS = """
.tagline{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.verdict-top{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:6px;padding:18px 20px}
.verdict-top p{font-size:1.05rem;line-height:1.5;margin:0 0 8px;max-width:none}
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
@media (min-width:900px){.plate img{min-width:0}}
.swipe{font-size:.82rem;color:var(--muted);margin:6px 0 0}
@media (min-width:900px){.swipe{display:none}}
td.l,th.l{text-align:left}
td.wrap{white-space:normal;min-width:190px;vertical-align:top;font-size:.88rem;line-height:1.4}
td.wrap small,td small{display:block;color:var(--muted)}
.pos{color:var(--good)}.neg{color:var(--bad)}
main{max-width:1040px}
.tk{border-top:1px solid var(--line);padding-top:22px;margin-top:6px}
.tk h3{font-size:1.25rem}
.mech{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.mech details>div{padding:0 16px 12px;font-size:.93rem}
.mech b{color:var(--ink)}
.stickyc th:first-child,.stickyc td:first-child{position:sticky;left:0;background:var(--surface);z-index:1}
h2{margin-top:4px}
"""

CONTENDERS: dict[str, tuple[str, str]] = {
    "W1_C13C_ORIG": (
        "C13C: kupnja nakon pada",
        "Kupi dionicu koja je iznad 200-dnevnog prosjeka, a u zadnjih 5 dana je pala 5 % ili više; stop 10 % ispod vrha.",
    ),
    "W2_MOM_BREAK_20": (
        "Proboj 20-dnevnog vrha",
        "Kupi kad dionica zatvori na najvišoj cijeni zadnjih 20 dana (uz rast u 60 dana); izlaz kad padne ispod 10-dnevnog dna.",
    ),
    "W3_MOM_RANK_WEEKLY": (
        "Tjedni rang zamaha",
        "Svaki petak rangira skupinu po rastu u zadnjih 20 dana i kupi onu iz gornje trećine; izlaz kad ispadne iz gornje polovice.",
    ),
    "W4_SR_BOUNCE_V2": (
        "Odskok od potpore",
        "Kupi kad cijena dotakne potvrđenu potporu pa zatvori iznad svijeće dodira; cilj je najbliži raniji vrh.",
    ),
    "W5_SR_BREAKOUT_RETEST": (
        "Proboj vrha pa povratak",
        "Cijena probije raniji vrh, vrati se do njega i zatvori iznad; kupnja sljedeći dan, stop 3 % ispod te razine, izlaz ispod 50-dnevnog prosjeka.",
    ),
    "W6_MM_SWEEP_SHIFT": (
        "Lov na stopove + promjena karaktera",
        "Iz rječnika videa: cijena kratko probije zadnje dno i vrati se, u jeftinoj polovici raspona, pa zatvori iznad zadnjeg nižeg vrha.",
    ),
    "W7_MM_DEMAND_RETEST": (
        "Povratak u zonu potražnje",
        "Iz rječnika videa: kupnja kad se cijena prvi put vrati u svježu zonu potražnje, u uzlaznoj strukturi i u jeftinoj polovici raspona.",
    ),
    "W8_IBS_REVERT": (
        "Kupnja nakon slabog zatvaranja",
        "Kupi kad je zatvaranje pri samom dnu dnevnog raspona (iznad 200-dnevnog prosjeka); izlaz pri vrhu raspona ili nakon 5 dana.",
    ),
    "B0_BUYHOLD": (
        "Kupi i drži (mjerilo)",
        "Kupnja prvi dan i držanje do kraja; mjerilo, ne pravilo.",
    ),
}

EVENT_PLAIN = {
    "E1_sweep_shift_discount": "lov na stopove + promjena karaktera u jeftinoj polovici raspona",
    "E4_demand_zone_retest": "prvi povratak u svježu zonu potražnje",
    "E5_bos_trend": "proboj strukture u smjeru uzlaznog trenda",
}

MINUS = "−"
DASH = "–"


def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def hr(x: float, nd: int = 0) -> str:
    """Croatian number format: decimal comma, thousands dot, ASCII minus."""
    s = f"{x:,.{nd}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return MINUS + s[1:] if s.startswith("-") else s


def plural(n: int, one: str, few: str, many: str) -> str:
    """Croatian noun form after a number: 1 posao, 2 posla, 5 poslova (11 to 14 take the many form)."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def trades_hr(n: int) -> str:
    return plural(n, "posao", "posla", "poslova")


def events_hr(n: int) -> str:
    return plural(n, "događaj", "događaja", "događaja")


def structure_hr(bias: str) -> str:
    return (
        "uzlazna (viši vrhovi i viša dna)"
        if bias == "bullish"
        else "silazna (niži vrhovi i niža dna)"
    )


def direction_hr(direction: str) -> str:
    """Translate the map's shift direction word into plain words."""
    return (
        "prema gore, znak snage"
        if "bikov" in direction
        else "prema dolje, znak slabosti"
    )


def sweep_hr(direction: str, level: float) -> str:
    if "vrha" in direction:
        return f"cijena je kratko probila vrh {hr(level, 2)} $ i vratila se ispod njega (znak slabosti)"
    return f"cijena je kratko probila dno {hr(level, 2)} $ i vratila se iznad njega (znak snage)"


def repair_hr(raw: str) -> str:
    m = re.match(
        r"(\d{4})-(\d{2})-(\d{2}) (high|low|open|close) ([\d.]+) -> ([\d.]+)", raw
    )
    if not m:
        return raw
    what = {
        "high": "najviša",
        "low": "najniža",
        "open": "otvaranje",
        "close": "zatvaranje",
    }[m[4]]
    return f"{what} cijena {int(m[3])}. {int(m[2])}. {m[1]}. ispravljena s {hr(float(m[5]), 2)} na {hr(float(m[6]), 2)} $"


def sgn(x: float, nd: int = 1) -> str:
    """Signed Croatian number; the minus is the typographic one."""
    s = hr(x, nd)
    if s.startswith("-"):
        return MINUS + s[1:]
    return ("+" if x > 0 else "") + s


def usd(x: float) -> str:
    return f"{hr(x, 2)} $"


def dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)}. {int(m)}. {y}."


def load(path: Path) -> Any:
    return json.loads(path.read_text())


# ---------------------------------------------------------------- data


class Data:
    """All raw inputs of the page, loaded once; nothing here is computed beyond lookups."""

    def __init__(self, group: str) -> None:
        self.group = group
        self.res = load(SWING / "results" / f"{group}.json")
        self.summary = load(SWING / "summary.json")
        self.placebo = load(SWING / "placebo.json")
        self.reg = load(SWING / "registration.json")
        self.audit = load(SWING / "audit.json")
        self.tickers: list[str] = self.res["tickers"]
        self.maps = {t: load(SWING / "map" / f"{t}.json") for t in self.tickers}
        prof = BASE / "segments" / group / "profile.json"
        self.profile = load(prof) if prof.exists() else None
        ana = BASE / "segments" / group / "analysis.json"
        self.analysis = load(ana) if ana.exists() else None
        self.name: str = self.res["name"]
        self.k: int = self.summary["ledger_k"]
        self.era = self.res["contenders"]
        self.ranking = self.res["ranking"]
        self.end: str = self.summary["common_end"]
        self.era_start: str = self.summary["ai_era_start"]
        self.months: float = self.res["window"]["months"]

    def c(self, cid: str) -> dict[str, Any]:
        return self.era[cid]["ai_era"]

    @property
    def winner(self) -> str | None:
        r = self.ranking["ranking"]
        return r[0]["contender"] if r and r[0]["eligible"] else None


def img_tag(path: Path, alt: str) -> str:
    return f'<img src="{top10.img(path)}" alt="{e(alt)}" loading="lazy">'


def table(
    head: list[str],
    rows: list[list[str]],
    cls: str = "",
    left_cols: tuple[int, ...] = (0,),
    wrap_cols: tuple[int, ...] = (),
) -> str:
    th = "".join(
        f'<th class="{"l" if i in left_cols else ""}">{h}</th>'
        for i, h in enumerate(head)
    )
    trs = []
    for r in rows:
        tds = "".join(
            f'<td class="{("l " if i in left_cols else "") + ("wrap" if i in wrap_cols else "")}">{c}</td>'
            for i, c in enumerate(r)
        )
        trs.append(f"<tr>{tds}</tr>")
    return (
        f'<div class="table-wrap"><table class="{cls}"><thead><tr>{th}</tr></thead>'
        f"<tbody>{''.join(trs)}</tbody></table></div>"
    )


# ---------------------------------------------------------------- level helpers


def reliability_text(rel: dict[str, Any]) -> str:
    if rel["enough_touches"]:
        return f"povijesno se odbila {rel['bounce']} od {rel['n']} dodira ({hr(rel['rate'] * 100)} %), probijena {rel['break']}"
    if rel["n"] == 0:
        return "bez dodira nakon nastanka: pouzdanost se ne može procijeniti"
    return f"premalo dodira ({rel['n']}): pouzdanost se ne može procijeniti"


def level_cell(lv: dict[str, Any], last: float, kind: str) -> str:
    p = lv["price"]
    d = (p / last - 1) * 100
    eur = EUR_UNIT * (p / last - 1)
    if kind == "support":
        euro = f"ako padne do nje: gubitak oko {hr(abs(eur))} € na 1.000 €"
    else:
        euro = f"ako dosegne: dobitak oko {hr(abs(eur))} € na 1.000 €"
    return f"<b>{usd(p)}</b> ({sgn(d)} %)<small>{euro}</small><small>{reliability_text(lv['reliability'])}</small>"


def levels_cells(m: dict[str, Any], key: str, kind: str) -> str:
    lvs = m[key]
    if not lvs:
        if kind == "resistance":
            return "nema potvrđenog otpora iznad cijene (cijena je na novom vrhu)"
        return "nema potvrđene potpore ispod cijene"
    return "<br>".join(level_cell(lv, m["last_close"], kind) for lv in lvs)


def zones_cell(m: dict[str, Any]) -> str:
    parts = []
    last = m["last_close"]
    for z in m["fresh_zones"]["demand"]:
        parts.append(
            f"potražnja {hr(z['low'], 2)}{DASH}{hr(z['high'], 2)} $ ({sgn((z['high'] / last - 1) * 100)} %)"
        )
    for z in m["fresh_zones"]["supply"]:
        parts.append(
            f"ponuda {hr(z['low'], 2)}{DASH}{hr(z['high'], 2)} $ ({sgn((z['low'] / last - 1) * 100)} %)"
        )
    nb, ns = len(m["open_fvg"]["bull"]), len(m["open_fvg"]["bear"])
    txt = "<br>".join(parts) if parts else "nema svježih zona"
    return (
        f"{txt}<small>otvorenih praznina u cijeni: {nb} uzlaznih, {ns} silaznih</small>"
    )


def position_text(m: dict[str, Any]) -> str:
    r = m["swing_range"]
    return f"{r['zone_hr']}<small>{hr(r['position_pct'])} % raspona {hr(r['low'], 2)}{DASH}{hr(r['high'], 2)} $</small>"


# ---------------------------------------------------------------- sections


def verdict_sentence(d: Data) -> str:
    n = len(d.tickers)
    weekly_bull = sum(1 for m in d.maps.values() if m["weekly"]["bias"] == "bullish")
    daily_bull = sum(1 for m in d.maps.values() if m["daily"]["bias"] == "bullish")
    above = [
        t
        for t, m in d.maps.items()
        if m["swing_range"]["zone"] == "outside"
        and m["swing_range"]["position_pct"] > 100
    ]
    s1 = (
        f"Na karti od {n} dionica {weekly_bull} ih je tjedno, a {daily_bull} dnevno u uzlaznoj strukturi (viši vrhovi i viša dna); "
        f"{plural(len(above), 'dionica', 'dionice', 'dionica')} ({', '.join(above)}) {'je' if len(above) == 1 else 'su'} iznad cijelog zadnjeg raspona, pa u njima nema svježe jeftine zone za kupnju."
    )
    w = d.winner
    hold = d.ranking["buy_and_hold_reference"]["total_return"]
    if w:
        a = d.c(w)
        s2 = (
            f"Swing test: od 8 unaprijed prijavljenih pravila uvjet 'radi često' ispunjava „{CONTENDERS[w][0]}“ "
            f"({hr(a['trades_per_month'], 1)} posla mjesečno, očekivanje {hr(a['expectancy_eur'])} € po poslu na 1.000 €, uz trošak 2,5 baznih bodova po strani), "
            f"ali je od {dmy(d.era_start)} do {dmy(d.end)} zaradilo prosječno {hr(a['total_return'] * 100)} % po pretincu od 1.000 € naspram {hr(hold * 100)} % za kupi-i-drži."
        )
    else:
        s2 = "Swing test: nijedno pravilo ne ispunjava unaprijed zadane uvjete 'radi često'."
    pb = d.placebo["sr"]["by_group"][d.group]
    s3 = (
        "Potvrđene potpore i otpori u ovoj skupini ne odbijaju cijenu češće od nasumično povučenih crta "
        f"({hr(pb['real']['bounce_rate'] * 100, 1)} % naspram {hr(pb['rand']['bounce_rate'] * 100, 1)} %)."
    )
    return f"<p><b>{s1}</b></p><p>{s2}</p><p>{s3}</p>"


def sec_verdict(d: Data) -> str:
    return f"""<section id="presuda"><h2>Presuda u jednoj rečenici</h2><div class="verdict-top">
{verdict_sentence(d)}
<p class="note">Ovo je istraživačko čitanje povijesnih dnevnih cijena, ne signal i ne savjet. Nijedan nalog nije poslan; nije formalni Critic PASS.</p>
</div></section>"""


def sec_how_to_read(d: Data) -> str:
    last_dates: dict[str, list[str]] = {}
    for t, m in d.maps.items():
        last_dates.setdefault(m["last_date"], []).append(t)
    ld = "; ".join(f"{dmy(k)}: {', '.join(v)}" for k, v in sorted(last_dates.items()))
    return f"""<section id="kako-citati"><h2>Kako čitati ovu stranicu</h2>
<div class="teach">
<p><b>Swing trgovanje</b> znači držati dionicu dane do tjedne, ne minute. Zato gledamo dnevne i tjedne svijeće.</p>
<p><b>Karta</b> je pregled gdje se cijena trenutno nalazi: koje su joj najbliže <b>potpore</b> (cijene ispod, gdje se cijena ranije okrenula prema gore) i <b>otpori</b> (cijene iznad, gdje se okrenula prema dolje), u kojoj je polovici zadnjeg raspona i je li <b>struktura</b> uzlazna (svaki novi vrh i dno viši od prethodnog) ili silazna.</p>
<p>Primjer s 1.000 €: ako je dionica 100 $, a potpora 90 $, pad do potpore znači gubitak od oko 100 € na 1.000 €. Cijene su u USD i tretiraju se kao EUR-ekvivalent (tečaj nije uračunat).</p>
<p>Ovo je <b>istraživanje, ne signal</b>. Vokabular ('lov na stopove', 'promjena karaktera', 'zona potražnje') preuzet je iz diskrecijskog stila poučavanja i ovdje je preveden u stroga pravila koja ne gledaju u budućnost; testiramo ga pošteno i ne pretpostavljamo da radi.</p>
<p>Razdoblje: karta koristi zadnji datum svake dionice ({e(ld)}). Swing test koristi zajednički kraj {dmy(d.end)}. AI era ({dmy(d.era_start)} nadalje) je mjerilo, ranije godine su samo kontekst.</p>
</div></section>"""


def sec_mechanism(d: Data) -> str:
    if not d.profile:
        return ""
    cards = []
    for t in d.tickers:
        mech = d.profile["tickers"].get(t, {}).get("mehanizam_hr")
        if not mech:
            continue
        rows = [
            ("Što prodaje", mech.get("sto_prodaje")),
            ("Što vuče prihod", mech.get("sto_vodi_prihod")),
            ("Mjesto u lancu", mech.get("mjesto_u_lancu")),
            ("Tipičan ciklus", mech.get("tipican_ciklus")),
            ("Što ga boli", mech.get("sto_ga_boli")),
        ]
        body = "".join(f"<p><b>{a}:</b> {e(b)}</p>" for a, b in rows if b)
        cards.append(
            f'<details><summary>{t}</summary><div>{body}<p class="note">{e(mech.get("oznaka", ""))}.</p></div></details>'
        )
    return f"""<section id="mehanizam"><h2>Kako ovo tržište funkcionira</h2>
<p>Čipovi za umjetnu inteligenciju, logiku i analogne sklopove: cijena ovisi o tome koliko velike tehnološke tvrtke ulažu u podatkovne centre (NVDA, AMD, AVGO, MRVL, TSM), o ciklusu računala i telefona (INTC, QCOM, ARM) te o industrijskoj i automobilskoj potražnji (TXN, MCHP, ON). Ispod je kratak opis za svaku tvrtku; otvori ime tvrtke.</p>
<p class="note"><b>Kontekst iz javnih izvora</b>: poslovne činjenice nisu iz naših podataka i nisu provjerene u godišnjim izvješćima; čitati kao okvirno.</p>
<div class="mech">{"".join(cards)}</div></section>"""


def sec_table_now(d: Data) -> str:
    rows = []
    for t in d.tickers:
        m = d.maps[t]
        rep = " (loš podatak popravljen)" if m["bar_repairs"] else ""
        rows.append(
            [
                f"<b>{t}</b><small>{dmy(m['last_date'])}, {usd(m['last_close'])}{rep}</small>",
                f"tjedno: {structure_hr(m['weekly']['bias'])}<small>dnevno: {structure_hr(m['daily']['bias'])}</small>",
                position_text(m),
                levels_cells(m, "nearest_supports", "support"),
                levels_cells(m, "nearest_resistances", "resistance"),
                zones_cell(m),
            ]
        )
    head = [
        "Dionica",
        "Struktura",
        "Položaj u rasponu",
        "Dvije najbliže potpore",
        "Dva najbliža otpora",
        "Aktivne zone",
    ]
    tbl = table(
        head,
        rows,
        cls="stickyc",
        left_cols=(0, 1, 2, 3, 4, 5),
        wrap_cols=(1, 2, 3, 4, 5),
    )
    return f"""<section id="gdje-je-cijena"><h2>Gdje je cijena sada</h2>
<p>Za svaku dionicu: zadnji datum i zaključna cijena, smjer kretanja (struktura), gdje je cijena u zadnjem rasponu (<b>diskont</b> = jeftinija polovica, <b>premium</b> = skuplja polovica), dvije najbliže potpore i dva najbliža otpora s udaljenošću i eurskim primjerom na 1.000 €, te svježe zone. <b>Pouzdanost razine</b> je koliko se puta cijena od nje odbila, a koliko ju je probila (računa se samo kad ima barem 3 dodira; inače piše da je dodira premalo). Na mobitelu povuci tablicu ulijevo i udesno.</p>
{tbl}
<p class="note">Razina nije jamstvo: test lažnih razina (odjeljak 'Pobjeđuju li razine nasumične crte') pokazuje da potvrđene razine ne odbijaju cijenu bolje od nasumičnih. Služe kao orijentir za stop i cilj, ne kao prognoza.</p></section>"""


def reading(d: Data, t: str) -> str:
    m = d.maps[t]
    last = m["last_close"]
    r = m["swing_range"]
    w, dly = m["weekly"], m["daily"]
    sup = m["nearest_supports"]
    res = m["nearest_resistances"]
    out: list[str] = []
    s = f"Tjedna struktura je {structure_hr(w['bias'])}, dnevna {structure_hr(dly['bias'])}."
    if dly["last_bos"]:
        s += f" Zadnji dnevni proboj strukture: {dmy(dly['last_bos']['date'])}."
    if dly["last_shift"]:
        s += f" Zadnja promjena karaktera ({direction_hr(dly['last_shift']['direction'])}): {dmy(dly['last_shift']['date'])}."
    out.append(s)
    rng = f"{hr(r['low'], 2)}{DASH}{hr(r['high'], 2)} $"
    if r["zone"] == "outside" and r["position_pct"] > 100:
        out.append(
            f"Cijena {usd(last)} je iznad zadnjeg raspona {rng} (probijen vrh): nema jeftine polovice u kojoj bi ovaj stil tražio kupnju. "
            "Swing trader tu obično čeka povlačenje prema potpori i gleda drži li ona, umjesto da kupuje na novom vrhu."
        )
    elif r["zone"] == "outside":
        out.append(
            f"Cijena {usd(last)} je ispod zadnjeg raspona {rng} (probijeno dno): struktura je slomljena, pa ovaj stil prvo traži znak oporavka (zatvaranje iznad zadnjeg nižeg vrha)."
        )
    elif r["zone"] == "premium":
        out.append(
            f"Cijena {usd(last)} je u skupljoj polovici raspona {rng} ({hr(r['position_pct'])} %). U ovom stilu se kupnja traži u jeftinijoj polovici, pa trader čeka povlačenje ili proboj gornjeg ruba."
        )
    else:
        out.append(
            f"Cijena {usd(last)} je u jeftinijoj polovici raspona {rng} ({hr(r['position_pct'])} %), gdje ovaj stil traži kupnju, ali samo uz uzlaznu strukturu i potvrdu (zatvaranje iznad zadnjeg nižeg vrha)."
        )
    if sup:
        s0 = sup[0]
        dd = (s0["price"] / last - 1) * 100
        out.append(
            f"Najbliža potpora je {usd(s0['price'])} ({sgn(dd)} %): pad do nje bio bi oko {hr(abs(EUR_UNIT * dd / 100))} € na 1.000 €; {reliability_text(s0['reliability'])}."
        )
    if res:
        r0 = res[0]
        dd = (r0["price"] / last - 1) * 100
        out.append(
            f"Najbliži otpor je {usd(r0['price'])} ({sgn(dd)} %); {reliability_text(r0['reliability'])}."
        )
    else:
        out.append(
            "Iznad cijene nema potvrđenog otpora jer je cijena na novom vrhu; nema crte na kojoj su prije prodavali."
        )
    if m["recent_sweeps"]:
        sw = m["recent_sweeps"][-1]
        out.append(
            f"Nedavni lov na stopove ({dmy(sw['date'])}): {sweep_hr(sw['direction'], sw['level'])}."
        )
    fz = len(m["fresh_zones"]["demand"]) + len(m["fresh_zones"]["supply"])
    out.append(f"Svježih zona: {fz} (mjesta na koja se cijena još nije vratila).")
    if m["bar_repairs"]:
        out.append(
            f"Napomena o podacima: jedan loš dnevni podatak popravljen je u izračunu ({repair_hr(m['bar_repairs'][0])}); datoteka nije mijenjana."
        )
    wid = d.winner
    if wid:
        pt = d.c(wid)["per_ticker"][t]
        hold = d.c("B0_BUYHOLD")["per_ticker"][t]["total_return"]
        out.append(
            f"Swing test za ovu dionicu („{CONTENDERS[wid][0]}“, od 2023.): {trades_hr(pt['trades'])}, očekivanje {sgn(pt['expectancy_eur'], 0)} € po poslu na 1.000 €, "
            f"prinos pretinca {hr(pt['total_return'] * 100)} % naspram {hr(hold * 100)} % za kupi-i-drži."
        )
    return " ".join(out)


def sec_per_ticker(d: Data) -> str:
    blocks = []
    for t in d.tickers:
        m = d.maps[t]
        wk = "uzlazno" if m["weekly"]["bias"] == "bullish" else "silazno"
        dl = "uzlazno" if m["daily"]["bias"] == "bullish" else "silazno"
        chips = (
            f'<span class="chip">tjedno: {wk}</span><span class="chip">dnevno: {dl}</span>'
            f'<span class="chip warn">{e(m["swing_range"]["zone_hr"])}</span>'
            f'<span class="chip">ATR {hr(m["atr14_pct"], 1)} % cijene</span>'
        )
        blocks.append(
            f"""<div class="tk" id="t-{t}"><h3>{t}: {dmy(m["last_date"])}, {usd(m["last_close"])}</h3>
<div class="chips">{chips}</div>
<figure><div class="plate">{img_tag(SWING / "map" / f"{t}.png", f"Karta razina i strukture za {t}")}</div>
<p class="swipe">Na mobitelu povuci crtež ulijevo i udesno.</p>
<figcaption><b>Što ovdje vidimo i što bi swing trader gledao.</b> {reading(d, t)}</figcaption></figure></div>"""
        )
    return f"""<section id="grafovi"><h2>Karta po dionici</h2>
<p>Na svakom crtežu: svijeće (zelena = dan rasta), pokretni prosjeci (SMA50 = prosjek zadnjih 50 dana, SMA200 = 200 dana), zelene vodoravne crte i trake su potpore, crvene otpori, trake su zone dodira, uokvirene zone su potražnja (zelena) i ponuda (crvena). Brojevi u krugovima povezuju crtež s tekstom na njemu. <b>ATR</b> je prosječni dnevni raspon: ATR od 4 % znači da cijena u običnom danu pomakne oko 40 € na 1.000 €.</p>
{"".join(blocks)}</section>"""


FAIL_RE = [
    (
        re.compile(r"only (\d+) trades"),
        lambda m: f"samo {trades_hr(int(m[1]))} (traži se 60)",
    ),
    (
        re.compile(r"expectancy <= 0 at cost 2x"),
        lambda _m: "očekivanje po poslu nije pozitivno uz dvostruki trošak",
    ),
    (re.compile(r"profit factor < 1\.2"), lambda _m: "faktor dobiti ispod 1,2"),
]


def reason_hr(r: str) -> str:
    for rx, fn in FAIL_RE:
        mm = rx.search(r)
        if mm:
            return fn(mm)
    return r


def contender_rows(d: Data) -> list[list[str]]:
    rk = d.ranking
    order = [(x["contender"], x, i + 1) for i, x in enumerate(rk["ranking"])] + [
        (x["contender"], x, None) for x in rk["not_eligible"]
    ]
    rows = []
    for cid, info, rank in order:
        a = d.c(cid)
        name, desc = CONTENDERS[cid]
        if rank:
            status = (
                f'<span class="chip {"good" if rank == 1 else ""}">rang {rank}</span>'
            )
        else:
            status = (
                '<span class="chip bad">nije podobno: '
                + "; ".join(reason_hr(r) for r in info["reasons"])
                + "</span>"
            )
        pf = hr(a["profit_factor"], 2) if a["profit_factor"] is not None else DASH
        rows.append(
            [
                f"<b>{name}</b><small>{desc}</small>",
                hr(a["trades"]),
                hr(a["trades_per_month"], 1),
                hr(a["hit_rate"] * 100) + " %",
                sgn(a["expectancy_eur"], 0) + " €",
                sgn(a["expectancy_eur_cost_2x"], 0) + " €",
                pf,
                hr(a["median_hold_days"]),
                hr(a["total_return"] * 100) + " %",
                status,
            ]
        )
    b = d.c("B0_BUYHOLD")
    rows.append(
        [
            f"<b>{CONTENDERS['B0_BUYHOLD'][0]}</b><small>{CONTENDERS['B0_BUYHOLD'][1]}</small>",
            f"{b['trades']} (jedan po dionici)",
            DASH,
            DASH,
            DASH,
            DASH,
            DASH,
            hr(b["median_hold_days"]),
            hr(b["total_return"] * 100) + " %",
            '<span class="chip">mjerilo, ne rangira se</span>',
        ]
    )
    return rows


def sec_swing(d: Data) -> str:
    head = [
        "Pravilo",
        "Poslova",
        "Poslova mjesečno",
        "Stopa pogotka",
        "Očekivanje po poslu na 1.000 €",
        "Isto uz trošak 2x",
        "Faktor dobiti",
        "Medijan dana držanja",
        "Prosj. prinos pretinca",
        "Status",
    ]
    tbl = table(
        head, contender_rows(d), cls="stickyc", left_cols=(0, 9), wrap_cols=(0, 9)
    )
    w = d.winner
    if w:
        win_html = winner_block(d, w, d.c(w), d.c("B0_BUYHOLD"))
    else:
        win_html = "<p><b>Nitko ne ispunjava uvjete 'radi često'.</b> Nijedno pravilo nije imalo dovoljno poslova, pozitivno očekivanje uz trošak 2x i faktor dobiti od najmanje 1,2.</p>"
    return f"""<section id="swing-test"><h2>Što je swing test pokazao za ovu skupinu</h2>
<div class="teach">
<p>Osam pravila prijavljeno je <b>prije</b> pokretanja, bez ugađanja, i svako je testirano na istih {len(d.tickers)} dionica, svaka s vlastitih 1.000 € (<b>pretinac</b>: novac se ne prelijeva među dionicama). Razdoblje: {dmy(d.era_start)} do {dmy(d.end)} ({hr(d.months, 1)} mjeseci). Trošak: 2,5 bazna boda po strani (0,025 %: na 1.000 € to je 0,25 € pri kupnji i 0,25 € pri prodaji); stupac 'uz trošak 2x' ponavlja račun s dvostrukim troškom. Odluka na zatvaranju, kupnja na idućem otvaranju. Samo dugo, bez poluge.</p>
<p><b>Očekivanje po poslu</b> je prosječan ishod jednog posla na 1.000 €. <b>Stopa pogotka</b> je udio dobitnih poslova. <b>Faktor dobiti</b> je zbroj dobitaka podijeljen sa zbrojem gubitaka: 3 znači da na svaki izgubljeni euro dođu tri zarađena.</p>
<p>Unaprijed zadano pravilo 'radi često': najmanje 60 poslova u AI eri, očekivanje po poslu veće od nule uz trošak 2x i faktor dobiti od najmanje 1,2; među podobnima pobjeđuje onaj s najvećim umnoškom očekivanja po poslu i poslova mjesečno. Kupi-i-drži je samo mjerilo.</p>
</div>
{tbl}
<p class="note">Prinos pretinca je prosjek po dionici (svaka s 1.000 €; poslovi se ne slažu složeno). Pravila sa samo nekoliko desetaka poslova podložna su slučajnosti.</p>
{win_html}</section>"""


def winner_block(d: Data, w: str, a: dict[str, Any], hold: dict[str, Any]) -> str:
    name, desc = CONTENDERS[w]
    win_eur = a["avg_win_eur"]
    loss_eur = abs(a["avg_loss_eur"])
    n100 = 100
    wins = round(a["hit_rate"] * n100)
    rob = d.summary["robustness_top3"]["results"].get(w)
    ctx = d.era[w]["contexts"]
    rows = []
    for t in d.tickers:
        pt = a["per_ticker"][t]
        bh = hold["per_ticker"][t]["total_return"]
        cls = "pos" if pt["expectancy_eur"] > 0 else "neg"
        rows.append(
            [
                t,
                hr(pt["trades"]),
                hr(pt["hit_rate"] * 100) + " %",
                f'<span class="{cls}">{sgn(pt["expectancy_eur"], 0)} €</span>',
                hr(pt["total_return"] * 100) + " %",
                hr(bh * 100) + " %",
            ]
        )
    tbl = table(
        [
            "Dionica",
            "Poslova",
            "Stopa pogotka",
            "Očekivanje po poslu",
            "Prinos pretinca (pravilo)",
            "Prinos pretinca (kupi i drži)",
        ],
        rows,
    )
    neg = [t for t in d.tickers if a["per_ticker"][t]["expectancy_eur"] <= 0]
    robtxt = ""
    if rob:
        robtxt = (
            "Provjera osjetljivosti (svi pragovi pomaknuti za 20 %, jedan po jedan, na svim dionicama svih skupina zajedno): "
            f"{'nijedna' if not rob['fragile'] else 'neka'} varijanta nije pala ispod nule uz trošak 2x; najgora ima očekivanje {hr(rob['min_expectancy_eur_cost_2x'])} € po poslu. "
        )
    c1, c2 = ctx["y2016_2020"], ctx["y2021_2022"]
    bh_all = d.ranking["buy_and_hold_reference"]
    neg_txt = (
        f"Pravilo ne zarađuje po poslu na: {', '.join(neg)} ({len(neg)} od {len(d.tickers)} dionica). Iz profila skupine: analogni čipovi imaju slabiji AI prinos."
        if neg
        else "Pravilo ima pozitivno očekivanje na svim dionicama."
    )
    return f"""<h3>'Radi često' pobjednik: {e(name)}</h3>
<div class="verdict-top">
<p><b>Kako trguje, korak po korak.</b> {e(desc)}</p>
<p>Primjer s 1.000 €: u prosjeku dobitni posao donosi {hr(win_eur)} €, gubitni {hr(loss_eur)} € gubitka. Od 100 poslova {wins} je dobitnih i {n100 - wins} gubitnih: {wins} × {hr(win_eur)} {MINUS} {n100 - wins} × {hr(loss_eur)} = {hr(wins * win_eur - (n100 - wins) * loss_eur)} € na 100 poslova, tj. oko {hr(a["expectancy_eur"])} € po poslu. Većina poslova gubi malo, a rijetki dobitni nose rezultat. Najduži niz gubitaka zaredom bio je {a["longest_losing_streak"]}.</p>
<p>Učestalost: ukupno {trades_hr(a["trades"])} u {hr(d.months, 1)} mjeseci, {hr(a["trades_per_month"], 1)} mjesečno na cijeloj skupini (oko {hr(a["trades_per_ticker_year"], 1)} godišnje po dionici); medijan držanja {hr(a["median_hold_days"])} dana, prosjek {hr(a["mean_hold_days"], 1)} dana.</p>
<p><b>Iskreno:</b> pravilo radi često i uz trošak 2x zadržava očekivanje {sgn(a["expectancy_eur_cost_2x"], 0)} € po poslu, ali je u istom razdoblju prosječni pretinac zaradio {hr(a["total_return"] * 100)} %, a kupi-i-drži {hr(hold["total_return"] * 100)} %. Pravilo je u dionicama bilo samo {hr(a["exposure_pct"])} % vremena pa je propustilo veliki dio rasta. Najveći pad od vrha: pravilo {hr(abs(a["max_drawdown"]) * 100)} %, kupi-i-drži {hr(abs(bh_all["max_drawdown"]) * 100)} %. 'Radi često' nije isto što i 'zarađuje više od držanja'.</p>
<p>{robtxt}Prvih 5 poslova nosi {hr(a["top5_profit_share"] * 100)} % ukupne dobiti. Prije AI ere: 2016.{DASH}2020. očekivanje {sgn(c1["expectancy_eur"], 0)} € po poslu ({trades_hr(c1["trades"])}); 2021.{DASH}2022. {sgn(c2["expectancy_eur"], 0)} € ({trades_hr(c2["trades"])}, faktor dobiti {hr(c2["profit_factor"], 2)}): u padajućem tržištu pravilo je gubilo. Mjerilo je ovdje AI era.</p>
<p>Vjerojatnost da je Sharpe stvaran nakon {hr(d.k)} isprobanih pravila u laboratoriju (deflated Sharpe) je {hr(a["deflated_sharpe_prob"], 2)} za pravilo i {hr(hold["deflated_sharpe_prob"], 2)} za kupi-i-drži; blizu 1 bi značilo uvjerljiv rezultat, blizu 0 da se ne razlikuje od sreće; informativno, ne snižava ocjenu. Ocjena dokaza: pravilo je prijavljeno prije testa, bez ugađanja, prošlo je test pogleda unaprijed i ima dovoljno poslova; to <b>nije</b> formalni Critic PASS i nije signal.</p>
</div>
<h3>Pobjednik po dionicama</h3>
{tbl}
<p class="note">{neg_txt}</p>
<h3>Zašto vokabular iz videa nije pobjednik</h3>
{video_vocab(d)}"""


def video_vocab(d: Data) -> str:
    out = []
    allr = d.ranking["not_eligible"] + d.ranking["ranking"]
    for cid in ("W6_MM_SWEEP_SHIFT", "W7_MM_DEMAND_RETEST"):
        a = d.c(cid)
        info = next(x for x in allr if x["contender"] == cid)
        why = "; ".join(reason_hr(r) for r in info["reasons"]) or "podobno"
        out.append(
            f"<li><b>{CONTENDERS[cid][0]}</b>: {trades_hr(a['trades'])} ({hr(a['trades_per_month'], 1)} mjesečno), očekivanje {sgn(a['expectancy_eur'], 0)} € po poslu, faktor dobiti {hr(a['profit_factor'], 2)}. Uvjet nije ispunjen: {why}.</li>"
        )
    ev = d.placebo["mechanics_ai_era"]["events"]
    ev_rows = []
    for k, lab in EVENT_PLAIN.items():
        g = ev[k]["by_group_h10"].get(d.group)
        if g:
            ev_rows.append(
                f"<li>{lab}: {events_hr(g['n'])} u ovoj skupini, prosječni višak nad običnim danom iste dionice nakon 10 dana {sgn(g['mean_excess'] * 100, 1)} postotnih bodova "
                f"(svih 55 papira zajedno: {sgn(ev[k]['by_h']['10']['mean_excess_vs_ticker_avg'] * 100, 1)}).</li>"
            )
    return (
        f"<ul>{''.join(out)}</ul><p>Test mehanike (događaj naspram običnog dana), 10 dana nakon događaja:</p>"
        f"<ul>{''.join(ev_rows)}</ul>"
        '<p class="note">Višak je razlika prema prosječnom danu iste dionice. Za svih 55 papira zajedno interval pouzdanosti obuhvaća nulu u većini slučajeva (vidi PLACEBO.md); uzorci po skupini su mali pa ih treba čitati kao opis.</p>'
    )


def ci_phrase(diff: dict[str, Any], what: str) -> str:
    lo, hi = diff["ci95"]
    dd = diff["diff"] * 100
    lo, hi = lo * 100, hi * 100
    if lo > 0:
        verdict = "prave razine su češće"
    elif hi < 0:
        verdict = "prave razine su rjeđe"
    else:
        verdict = "nema razlike (interval obuhvaća nulu)"
    return f"{what}: razlika {sgn(dd, 1)} postotnih bodova [{sgn(lo, 1)}; {sgn(hi, 1)}]: {verdict}"


def sec_placebo(d: Data) -> str:
    pb = d.placebo["sr"]["by_group"][d.group]
    allp = d.placebo["sr"]["all"]
    real, rand = pb["real"], pb["rand"]
    names = (
        ("touch_rate", "Dodir razine"),
        ("bounce_rate", "Odbijanje nakon dodira"),
        ("break_rate", "Probijanje nakon dodira"),
    )
    items = [ci_phrase(pb["diff_vs_rand"][k], n) for k, n in names]
    items2 = [ci_phrase(pb["diff_vs_match"][k], n) for k, n in names]
    cfg = d.placebo["config"]

    def li(xs: list[str]) -> str:
        return "".join(f"<li>{e(x)}</li>" for x in xs)

    return f"""<section id="placebo"><h2>Pobjeđuju li razine nasumične crte u ovoj skupini?</h2>
<div class="teach">
<p><b>Placebo</b> je kontrola, kao tableta od šećera u ispitivanju lijeka: uz svaku pravu razinu povučemo lažne crte (nasumična cijena, pomak od 3 %, par crta oko razine). Ako lažne crte daju isti rezultat, razina nije ništa posebno. Mjerimo na zadnji dan svakog mjeseca od {dmy(d.era_start)}, samo razine poznate toga dana, sljedećih {cfg["horizon_bars"]} dana. <b>Odbijanje</b> je potez od najmanje 1,5 ATR od razine; <b>probijanje</b> je zatvaranje više od 1 ATR iza nje. <b>Interval pouzdanosti 95 %</b> je u uglatoj zagradi: ako obuhvaća nulu, razlika se ne može razlikovati od slučajne.</p>
</div>
<p>U ovoj skupini analizirano je <b>{hr(pb["n_levels"])}</b> razina u {pb["n_months"]} mjeseci. Cijena je dotaknula {hr(real["touch_rate"] * 100, 1)} % pravih razina i {hr(rand["touch_rate"] * 100, 1)} % nasumičnih. Kad je razina dotaknuta, odbila se u {hr(real["bounce_rate"] * 100, 1)} % slučajeva (nasumične: {hr(rand["bounce_rate"] * 100, 1)} %), a probijena u {hr(real["break_rate"] * 100, 1)} % (nasumične: {hr(rand["break_rate"] * 100, 1)} %). Primjer: od 100 pravih razina koje cijena dotakne, oko {hr(real["bounce_rate"] * 100)} ih odbije cijenu, a od 100 nasumičnih oko {hr(rand["bounce_rate"] * 100)}.</p>
<h3>Prave razine naspram nasumične cijene</h3><ul>{li(items)}</ul>
<h3>Prave razine naspram para lažnih crta na istoj udaljenosti</h3><ul>{li(items2)}</ul>
<p><b>Prijevod:</b> razine u ovoj skupini ne pobjeđuju slučajnost: odbijanje i probijanje su isti kao kod lažnih crta. Rjeđi dodir znači da razine cijenu ne privlače. Za svih {len(d.placebo["universe"]["used"])} papira zajedno rezultat je isti (odbijanje {hr(allp["real"]["bounce_rate"] * 100, 1)} % prema {hr(allp["rand"]["bounce_rate"] * 100, 1)} %). Razine su korisne kao orijentir gdje staviti stop i cilj, ali ne kao dokaz da će cijena tu stati.</p></section>"""


def sec_eu(d: Data) -> str:
    chips = "".join(
        f'<span class="chip warn">{t}: nepotvrđeno</span>' for t in d.tickers
    )
    notes = ""
    if d.analysis:
        eu = d.analysis["eu_hr"]["po_tickeru"]
        notes = "".join(
            f"<li><b>{t}:</b> {e(v['vrsta'])}. {e(v['napomena'].split('. ', 1)[1]) if '. ' in v['napomena'] else ''}</li>"
            for t, v in eu.items()
            if t in ("TSM", "ARM")
        )
    return f"""<section id="eu"><h2>Može li se ovo trgovati iz Hrvatske?</h2>
<div class="chips">{chips}</div>
<p>Svih {len(d.tickers)} su pojedinačne dionice kotirane u SAD-u. Takve su općenito dostupne malim ulagačima iz EU preko Interactive Brokersa, ali za svaku <b>status ostaje nepotvrđen dok se ne provjeri u samom IBKR-u</b>. Dozvole računa i porezni tretman ne nagađamo: nepotvrđeno.</p>
<ul>{notes}</ul>
<p>Američki ETF-ovi i indeksi (npr. SMH, SOXX, NDX, koji se spominju u profilu kao mjerilo kretanja sektora) često nisu dostupni malim EU ulagačima jer nemaju KID dokument: ovdje su samo <b>referentne serije, nepotvrđeno / referentno</b>, ne nešto što the researcher može kupiti.</p>
<p>Račun je u EUR, cijene u USD: tečaj EUR/USD i trošak konverzije su stvarni i nisu modelirani. Američka burza otvara u 15:30 po zagrebačkom vremenu. Samo dugo, bez poluge i bez kratke prodaje.</p></section>"""


def sec_glossary() -> str:
    g = dict(top10.GLOSSARY)
    own = [
        (
            "Struktura",
            "Smjer kretanja gledan preko vrhova i dna. Uzlazna: svaki novi vrh i dno viši od prethodnog; silazna: niži. Primjer: vrhovi 100, 110, 120 i dna 90, 95, 105 su uzlazna struktura.",
        ),
        (
            "Okret (pivot)",
            "Najviša ili najniža točka s 5 nižih (viših) svijeća sa svake strane. Potvrđuje se tek 5 svijeća nakon što nastane, da ne gledamo u budućnost.",
        ),
        (
            "Potpora i otpor",
            "Potpora je cijena ispod trenutne na kojoj se cijena ranije okrenula prema gore; otpor je cijena iznad na kojoj se okrenula prema dolje. Primjer: dionica je 3 puta pala na 90 $ i vratila se: 90 $ je potpora.",
        ),
        (
            "Proboj strukture (BOS)",
            "Zatvaranje iznad zadnjeg potvrđenog vrha u uzlaznom trendu: trend se nastavlja. Primjer: zadnji vrh 120 $, dionica zatvori na 123 $.",
        ),
        (
            "Promjena karaktera",
            "Zatvaranje iznad zadnjeg nižeg vrha u silaznom trendu: prvi znak da se trend može okrenuti.",
        ),
        (
            "Raspon, premium i diskont",
            f"Raspon ide od zadnjeg potvrđenog dna do zadnjeg potvrđenog vrha. Gornja polovica je premium (skuplja), donja diskont (jeftinija). Primjer: raspon 80{DASH}120 $, sredina 100 $; cijena 85 $ je u diskontu. Ovaj stil kupnju traži u diskontu.",
        ),
        (
            "Likvidnost i lov na stopove (sweep)",
            "Zaštitni nalozi običnih ulagača skupljaju se ispod očitih dna i iznad očitih vrhova. Lov na stopove: cijena kratko prođe kroz takvu razinu, a zatvori se natrag unutra (fitilj kroz razinu, zatvaranje natrag).",
        ),
        (
            "Zona potražnje (order block)",
            "Zadnja silazna svijeća prije snažnog rasta (barem 2 ATR u 3 svijeće) koji je probio vrh. Svježa je dok se cijena prvi put ne vrati u nju.",
        ),
        (
            "Praznina u cijeni (fair value gap)",
            f"Tri svijeće u nizu gdje najviša cijena prve ostaje ispod najniže cijene treće: cijena je 'preskočila' pojas. Primjer: prva svijeća do 100 $, treća od 103 $: praznina 100{DASH}103 $.",
        ),
        (
            "ATR",
            "Prosječni dnevni raspon cijene (najviša minus najniža, prosjek 14 dana). Primjer: ATR 4 % znači da cijena u običnom danu pomakne oko 40 € na 1.000 €.",
        ),
        (
            "Pretinac",
            "Jedna dionica s vlastitih 1.000 €. Pretinci se ne prelijevaju; 11 dionica je 11 pretinaca.",
        ),
        (
            "Očekivanje po poslu",
            "Prosječni ishod jednog posla na 1.000 €, nakon troškova. Primjer: +56 € znači da je u prosjeku posao donio 56 € (neki gube, neki dobivaju).",
        ),
        (
            "Stopa pogotka",
            "Udio dobitnih poslova. Visoka stopa nije cilj sama po sebi: 37 dobitnih od 100 može biti dobro ako su dobici veliki, a gubici mali.",
        ),
        (
            "Faktor dobiti",
            "Zbroj dobitaka podijeljen sa zbrojem gubitaka. 3 znači da na svaki izgubljeni euro dođu tri zarađena.",
        ),
        (
            "Placebo (lažna razina)",
            "Razina povučena nasumično, kao kontrola. Ako prave razine nisu bolje od lažnih, crtanje razina ne daje prednost.",
        ),
        (
            "Interval pouzdanosti 95 %",
            "Raspon u kojem bi se rezultat vjerojatno našao da ponovimo pokus. Ako obuhvaća nulu, razlika se ne razlikuje od slučajne.",
        ),
    ]
    keys = [
        "Kupi i drži",
        "AI era",
        "Prilagođeno podacima (overfitting)",
        "Gledanje u budućnost (lookahead)",
        "Broj pokušaja (K) i deflated Sharpe",
        "Troškovi i bazni bod",
    ]
    items = own + [(k, g[k]) for k in keys if k in g]
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in items)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def max_gap_days(t: str, since: str) -> int:
    import pandas as pd

    df = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv", parse_dates=["date"])
    x = df[df["date"] >= since]
    return int(x["date"].diff().dt.days.max())


def sec_limits(d: Data) -> str:
    repairs = [
        f"{t}: {repair_hr(m['bar_repairs'][0])}"
        for t, m in d.maps.items()
        if m["bar_repairs"]
    ]
    since = "2025-10-01"
    mg = max(max_gap_days(t, since) for t in d.tickers)
    code = d.audit["provenance"]["code_hashes"]["lab/aichain/swing.py"]
    code_note = (
        "Kod simulatora swing.py razlikuje se od onoga u trenutku prijave pravila (revizija je našla i ispravila greške; status: ispravljeno); brojke su iz ispravljenog izračuna."
        if not code["same"]
        else "Kod simulatora je isti kao u trenutku prijave."
    )
    items = [
        "Ovo su istraživačka čitanja povijesnih dnevnih podataka, ne signal, ne savjet i ne formalni Critic PASS. Signal ostaje PRIČEKAJ dok ne postoji odobrena strategija. Nijedan nalog (ni probni ni pravi) nije poslan.",
        f"Karta koristi zadnji datum svake dionice, swing test zajednički kraj {dmy(d.end)}; razlika među dionicama je do 8 dana.",
        f"Razdoblje swing testa: {dmy(d.era_start)} do {dmy(d.end)} ({hr(d.months, 1)} mjeseci). Ranije godine su samo kontekst; tržišni režim se promijenio nakon 2022., a AI era je razdoblje snažnog rasta čipova pa i obična kupnja većinom pobjeđuje.",
        "Trošak: 2,5 bazna boda po strani (0,025 %), uz test 2x i 3x. Minimalna provizija po nalogu kod IBKR-a, proklizavanje, djelomična ispunjenja i jaz preko noći na lošim vijestima nisu modelirani; za pravila s mnogo poslova stvarni trošak je veći.",
        "Tečaj EUR/USD, dividende i porezi nisu uključeni; cijene u USD tretiraju se kao EUR-ekvivalent. Porezni tretman i dozvole računa: nepotvrđeno.",
        f"U laboratoriju je isprobano ukupno {hr(d.k)} pravila (K): od devet pravila u ovoj skupini jedno uvijek 'pobjeđuje' i po sreći, a pobjednik gore nije formalno odobren.",
        "Pretinci: 11 × 1.000 € je puno veći ulog od jednog računa; 'poslova mjesečno' je mjera učestalosti za cijelu skupinu, ne obećanje zarade.",
        "Pouzdanost razine računa se samo kad ima barem 3 dodira; mnoge razine u ovoj skupini imaju premalo dodira pa je njihova pouzdanost nepoznata.",
        "Tekst uz svaki crtež složen je automatski iz izračunatih brojki; to je čitanje karte, ne ocjena dionice.",
        code_note,
        (
            f"Popravljeni loši podaci (CSV nije mijenjan): {'; '.join(repairs)}."
            if repairs
            else "Nije bilo popravaka podataka."
        ),
        f"Na pojedinim crtežima mjestimice nedostaju svijeće (primjerice AMD u proljeće 2026.); to je nedostatak crteža, ne podataka: najdulji razmak između dnevnih zapisa od {dmy(since)} u svih {len(d.tickers)} CSV-ova je {mg} dana.",
        "Poslovne činjenice (odjeljak o mehanizmu) su kontekst iz javnih izvora i nisu provjerene u godišnjim izvješćima. TSM je američki ADR, ne izravna tajvanska dionica.",
    ]
    ex = "".join(f"<li>{e(x)}</li>" for x in items)
    return f'<section id="granice"><h2>Granice: što nije uračunato</h2><ul>{ex}</ul></section>'


# ---------------------------------------------------------------- build


def build(group: str) -> Path:
    d = Data(group)
    body = f"""<main>
<header><span class="tagline">AICHAIN · karta tržišta · istraživačka simulacija</span>
<h1>Karta tržišta: {e(d.name)}</h1>
<p class="lead">Gdje je cijena sada, koje su joj najbliže potpore i otpori, i što je swing test pokazao od {dmy(d.era_start)} do {dmy(d.end)}. {len(d.tickers)} dionica: {", ".join(d.tickers)}.</p></header>
{sec_verdict(d)}
{sec_how_to_read(d)}
{sec_mechanism(d)}
{sec_table_now(d)}
{sec_per_ticker(d)}
{sec_swing(d)}
{sec_placebo(d)}
{sec_eu(d)}
{sec_glossary()}
{sec_limits(d)}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima (AI era od {dmy(d.era_start)} do {dmy(d.end)}): odluka na zatvaranju, kupnja na idućem otvaranju, trošak 2,5 baznih bodova po strani, bez poluge i bez kratke prodaje.
Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje, nije formalni Critic PASS i nijedan nalog (ni probni ni pravi) nije poslan.
Status revizije: ispravljeno (revizija 14. 10. 2026.); brojke su iz ispravljenih rezultata.</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(
            title="Karta: AI čipovi i logika", css=top10.CSS + EXTRA_CSS
        )
    )
    page = (
        '<!doctype html>\n<html lang="hr"><head>\n'
        + head
        + "</head><body>\n"
        + body
        + "\n</body></html>"
    )
    out = SWING / "pages" / f"{group}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page.replace("..", "."))  # ISO-date sentences end with a dot already
    return out


def verify(group: str) -> list[str]:
    """Re-check page numbers: expected strings are rebuilt from the raw JSON with separate plain formatting."""
    page = (SWING / "pages" / f"{group}.html").read_text()
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))

    def f(x: float, nd: int = 0) -> str:
        r = f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return MINUS + r[1:] if r.startswith("-") else r

    def fs(x: float, nd: int = 0) -> str:
        s = f(x, nd)
        return MINUS + s[1:] if s.startswith("-") else ("+" if x > 0 else "") + s

    bad: list[str] = []

    def need(s: str, what: str) -> None:
        if s not in text:
            bad.append(f"{what}: missing '{s}'")

    res = load(SWING / "results" / f"{group}.json")
    for t in res["tickers"]:
        m = load(SWING / "map" / f"{t}.json")
        need(f"{f(m['last_close'], 2)} $", f"{t} last close")
        need(f"{f(m['swing_range']['position_pct'])} % raspona", f"{t} range position")
        for lv in m["nearest_supports"] + m["nearest_resistances"]:
            need(f"{f(lv['price'], 2)} $", f"{t} level")
            eur = abs(1000 * (lv["price"] / m["last_close"] - 1))
            need(f"oko {f(eur)} € na 1.000 €", f"{t} euro example {lv['price']:.2f}")
    for cid, c in res["contenders"].items():
        a = c["ai_era"]
        need(f(a["trades_per_month"], 1), f"{cid} trades/month")
        need(f"{f(a['total_return'] * 100)} %", f"{cid} total return")
        if cid != "B0_BUYHOLD":
            need(f"{fs(a['expectancy_eur'])} €", f"{cid} expectancy")
            need(f"{f(a['hit_rate'] * 100)} %", f"{cid} hit rate")
    pb = load(SWING / "placebo.json")["sr"]["by_group"][group]
    for k in ("real", "rand"):
        for r in ("touch_rate", "bounce_rate", "break_rate"):
            need(f"{f(pb[k][r] * 100, 1)} %", f"placebo {k} {r}")
    need(f(pb["n_levels"]), "placebo levels n")
    w = res["ranking"]["ranking"][0]
    need(f"ukupno {f(w['trades'])} posla", "winner trades")
    for lit in ("NaN", "None", "nan"):
        if re.search(rf"\b{lit}\b", text):
            bad.append(f"literal {lit} in page text")
    if re.search(r"src=\"https?://", page):
        bad.append("external image src present")
    return bad


def main() -> None:
    out = build(GROUP)
    print(out, out.stat().st_size)
    if "--verify" in sys.argv:
        bad = verify(GROUP)
        print("VERIFY:", "OK" if not bad else "\n".join(bad))
        if bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
