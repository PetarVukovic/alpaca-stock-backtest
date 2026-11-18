"""Build the self-contained Croatian teaching page "Momentum, potpora i otpor, mehanika trzista".

Usage:
  .venv/bin/python scripts/aichain_learn_page.py            # draw charts, build page and facts.json
  .venv/bin/python scripts/aichain_learn_page.py --verify   # build, then re-check every number against the raw files

Inputs (read only): swing/summary.json, swing/placebo.json, swing/audit.json, swing/results/*.json,
AICHAIN summary.json, data/ohlcv/{T}_1d.csv (examples and verification only).
Outputs: swing/pages/uciti.html (charts embedded as data URIs), swing/learn/*.png, swing/learn/facts.json.
Never places orders. Research reading: not a signal, not advice, not a formal Critic PASS.
"""

from __future__ import annotations

import base64
import csv
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

from lab.aichain import learn_charts as lc
from lab.aichain import learn_examples as le

BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SWING = BASE / "swing"
LEARN = SWING / "learn"
PAGE = SWING / "pages" / "uciti.html"
FACTS = LEARN / "facts.json"
MINUS = "−"
RULES = [
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
    "W1_C13C_ORIG": "W1 C13C",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 sweep i promjena smjera",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
}

# ---------------------------------------------------------------- formatting


def e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def hr(x: float, nd: int = 0) -> str:
    """Croatian number format: decimal comma, thousands dot, true minus sign."""
    s = f"{abs(x):,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (
        (MINUS + s) if x < 0 and float(s.replace(".", "").replace(",", ".")) != 0 else s
    )


def sg(x: float, nd: int = 1) -> str:
    """Signed number with + or true minus."""
    s = hr(abs(x), nd)
    if round(abs(x), nd) == 0:
        return s
    return ("+" if x > 0 else MINUS) + s


def pc(x: float, nd: int = 1) -> str:
    return hr(x * 100, nd) + " %"


def spc(x: float, nd: int = 1) -> str:
    return sg(x * 100, nd) + " %"


def eur(x: float, nd: int = 0) -> str:
    return hr(x, nd) + " €"


def seur(x: float, nd: int = 0) -> str:
    return sg(x, nd) + " €"


def usd(x: float, nd: int = 2) -> str:
    return hr(x, nd) + " USD"


def dmy(d: Any) -> str:
    import pandas as pd

    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def img(name: str) -> str:
    return (
        "data:image/png;base64,"
        + base64.b64encode((LEARN / name).read_bytes()).decode()
    )


def jl(path: Path) -> Any:
    return json.loads(path.read_text())


# ---------------------------------------------------------------- data


class Data:
    """Every number on the page is read from these saved files (or from the daily CSVs for the examples)."""

    def __init__(self) -> None:
        self.S = jl(SWING / "summary.json")
        self.PL = jl(SWING / "placebo.json")
        self.AU = jl(SWING / "audit.json")
        self.RS = jl(SWING / "results" / "stocks_all.json")
        self.RM = jl(SWING / "results" / "memory.json")
        self.ROOT = jl(BASE / "summary.json")
        self.g = self.S["groups"]["stocks_all"]
        self.pc = self.g["per_contender"]
        self.k = self.S["ledger_k"]

    def rule(self, k: str) -> dict[str, Any]:
        return self.pc[k]

    def eligible(self, k: str) -> bool:
        return any(x["contender"] == k for x in self.g["ranking"])

    def rank_pos(self, k: str) -> int | None:
        for i, x in enumerate(self.g["ranking"], 1):
            if x["contender"] == k:
                return i
        return None

    def era(self, k: str, era: str) -> dict[str, Any]:
        return self.RS["contenders"][k]["contexts"][era]

    def bh(self) -> dict[str, Any]:
        return self.g["buy_and_hold_reference"]

    def count_beat_hold(self, key: str) -> tuple[int, int]:
        seg = self.ROOT["segment_x_contender_ai_era"]
        win = sum(
            1
            for s in seg.values()
            if s[key]["total_return"] > s["B0_BUYHOLD"]["total_return"]
        )
        return win, len(seg)

    def ev(
        self, name: str, h: str = "10", era: str = "mechanics_ai_era"
    ) -> dict[str, Any]:
        return self.PL[era]["events"][name]["by_h"][h]


def ex_facts(ex: le.Example) -> dict[str, Any]:
    c = le.ctx(ex.ticker)
    b = c.P.bars
    r = le.euro_result(c, ex.t)
    out: dict[str, Any] = {
        "ticker": ex.ticker,
        "kind": ex.kind,
        "signal_date": str(b.dates[ex.t].date()),
        "signal_close": float(b.close[ex.t]),
        "entry_date": str(b.dates[ex.t + 1].date()),
        "entry_open": r["entry"],
        "exit_date": str(b.dates[ex.t + le.H].date()),
        "exit_close": r["exit"],
        "r10": ex.r10,
        "pnl_eur": r["pnl"],
    }
    x = ex.extra
    if "trade" in x:
        tr = x["trade"]
        out["trade"] = {
            "exit_date": tr["exit_date"],
            "raw_exit": float(tr["raw_exit"]),
            "raw_entry": float(tr["raw_entry"]),
            "reason": tr["reason"],
            "detail": tr["detail"],
            "return": float(tr["return"]),
            "bars_held": int(tr["bars_held"]),
        }
    if "level" in x:
        out["level"] = float(x["level"])
        out["break_date"] = str(b.dates[x["break_i"]].date())
        out["break_close"] = float(b.close[x["break_i"]])
        out["touches"] = len(x["members"])
    if "event" in x:
        out["bos_level"] = float(x["event"]["level"])
        out["bos_level_date"] = str(b.dates[x["event"]["level_idx"]].date())
    if "sweep" in x:
        sw, sh = x["sweep"], x["shift"]
        out["sweep_date"] = str(b.dates[sw["idx"]].date())
        out["sweep_level"] = float(sw["level"])
        out["sweep_level_date"] = str(b.dates[sw["pivot_idx"]].date())
        out["sweep_low"] = float(b.low[sw["idx"]])
        out["sweep_close"] = float(b.close[sw["idx"]])
        out["shift_level"] = float(sh["level"])
        out["range_lo"] = x["range_lo"]
        out["range_hi"] = x["range_hi"]
        out["atr_at_sweep"] = float(c.P.atr[sw["idx"]])
        out["min_low_after_sweep"] = float(b.low[sw["idx"] + 1 : ex.t + 1].min())
    if "zone" in x:
        z = x["zone"]
        out["zone_lo"] = z["lo"]
        out["zone_hi"] = z["hi"]
        out["zone_base_date"] = str(b.dates[z["base"]].date())
        out["zone_known_date"] = str(b.dates[z["known"]].date())
    return out


# ---------------------------------------------------------------- html pieces

EXTRA_CSS = """
.tagline{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.verdict-top{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:6px;padding:18px 20px}
.verdict-top p{font-size:1.05rem;line-height:1.5;margin:0 0 8px;max-width:none}
.verdict-top p:last-child{margin-bottom:0}
.verdict-top ul{margin:0 0 8px;padding-left:1.2em}.verdict-top li{margin-bottom:6px;max-width:none}
.warnbox{background:var(--warn-soft);color:var(--ink);border-radius:6px;padding:14px 16px}
.warnbox p{margin:0 0 8px;max-width:none}.warnbox p:last-child{margin:0}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.chip{font-family:var(--mono);font-size:.78rem;padding:3px 9px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted)}
.chip.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.chip.good{background:var(--good-soft);color:var(--good);border-color:transparent}
.chip.bad{background:var(--bad-soft);color:var(--bad);border-color:transparent}
.teach{background:var(--accent-soft);border-radius:6px;padding:14px 16px;margin:0 0 14px}
.teach p{margin:0 0 8px;max-width:none}.teach p:last-child{margin:0}
.teach ul{margin:0 0 8px;padding-left:1.2em}.teach li{margin-bottom:5px}
.evid{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:6px;padding:14px 16px;margin:0 0 14px}
.evid p{max-width:none}.evid p:last-child{margin-bottom:0}
.plate{overflow-x:auto}
.plate img{min-width:700px}
@media (min-width:860px){.plate img{min-width:0}}
.swipe{font-size:.82rem;color:var(--muted);margin:6px 0 0}
@media (min-width:860px){.swipe{display:none}}
nav.toc{display:flex;flex-wrap:wrap;gap:8px}
nav.toc a{font-size:.88rem;text-decoration:none;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink)}
nav.toc a:hover{border-color:var(--accent)}
td.l,th.l{text-align:left;white-space:normal}
.small td,.small th{font-size:.86rem;padding:7px 9px}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:0 0 14px}
.kv div{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.kv b{display:block;font-family:var(--mono);font-size:1.15rem;font-weight:500}
.kv span{font-size:.84rem;color:var(--muted)}
h2 span.n{color:var(--accent);margin-right:6px}
"""


def fig(name: str, alt: str, caption: str) -> str:
    return (
        f'<figure><div class="plate"><img src="{img(name)}" alt="{e(alt)}" loading="lazy"></div>'
        f'<p class="swipe">Na telefonu: grafikon se može povući ulijevo i udesno.</p>'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def chip(text: str, kind: str = "warn") -> str:
    return f'<span class="chip {kind}">{e(text)}</span>'


def table(
    head: list[str], rows: list[list[str]], small: bool = True, left: int = 1
) -> str:
    th = "".join(
        f'<th class="{"l" if i < left else ""}">{h}</th>' for i, h in enumerate(head)
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"l" if i < left else ""}">{c}</td>' for i, c in enumerate(r)
        )
        + "</tr>"
        for r in rows
    )
    return f'<div class="table-wrap"><table class="{"small" if small else ""}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def kv(items: list[tuple[str, str]]) -> str:
    return (
        '<div class="kv">'
        + "".join(f"<div><b>{b}</b><span>{s}</span></div>" for b, s in items)
        + "</div>"
    )


# ---------------------------------------------------------------- the page


def build_facts(d: Data) -> dict[str, Any]:
    """Draw every chart and collect the facts of the picked examples."""
    LEARN.mkdir(parents=True, exist_ok=True)
    picks = {cn: le.pick(cn) for cn in le.CONCEPT_FIRST}
    F: dict[str, Any] = {
        "examples": {},
        "rule": "clean: first event with r10 >= +5 %, failed: first with r10 <= -5 %",
    }
    for cn, pair in picks.items():
        for kind, ex in pair.items():
            if ex is None:
                raise RuntimeError(f"no {kind} example found for {cn}")
            F["examples"][f"{cn}_{kind}"] = ex_facts(ex)
    lc.chart_momentum(picks["momentum"]["clean"], LEARN)
    lc.chart_momentum(picks["momentum"]["failed"], LEARN)
    lc.chart_sr(picks["sr_flip"]["clean"], LEARN)
    lc.chart_sr(picks["sr_flip"]["failed"], LEARN)
    _, anat = lc.chart_structure_anatomy(LEARN)
    F["anatomy"] = anat
    lc.chart_bos(picks["bos"]["clean"], LEARN)
    lc.chart_bos(picks["bos"]["failed"], LEARN)
    lc.chart_sweep(picks["sweep"]["clean"], LEARN)
    lc.chart_sweep(picks["sweep"]["failed"], LEARN)
    eq = le.equal_lows_example()
    if eq is None:
        raise RuntimeError("no equal-lows example found")
    lc.chart_equal_lows(eq, LEARN)
    c = le.ctx(eq["ticker"])
    b = c.P.bars
    srt = sorted(eq["members"], key=lambda p: p.idx)
    F["equal_lows"] = {
        "ticker": eq["ticker"],
        "level": eq["level"],
        "p1_date": str(b.dates[srt[0].idx].date()),
        "p1_price": srt[0].price,
        "p2_date": str(b.dates[srt[-1].idx].date()),
        "p2_price": srt[-1].price,
        "sweep_date": str(b.dates[eq["sweep_i"]].date()),
        "sweep_low": float(b.low[eq["sweep_i"]]),
        "sweep_close": float(b.close[eq["sweep_i"]]),
    }
    lc.chart_zone(picks["zone"]["clean"], LEARN)
    lc.chart_zone(picks["zone"]["failed"], LEARN)
    lc.chart_discount(picks["discount"]["clean"], LEARN)
    lc.chart_discount(picks["discount"]["failed"], LEARN)
    lc.chart_topdown(picks["topdown"]["clean"], LEARN)
    lc.chart_topdown(picks["topdown"]["failed"], LEARN)
    for fn in (
        lc.chart_ev_rules,
        lc.chart_ev_eras,
        lc.chart_ev_levels,
        lc.chart_ev_mech,
    ):
        fn(LEARN)
    return F


def cap_example(f: dict[str, Any], what: str) -> str:
    """Caption sentence shared by every example: real dates, prices and the fixed 10-day outcome.

    The 10-day hold is the same measure the event study uses and the rule the example is picked by;
    a rule trade (momentum, support/resistance) has its own exit, which the caller appends.
    """
    word = "dobio bi" if f["pnl_eur"] >= 0 else "izgubio bi"
    return (
        f"<b>{e(f['ticker'])}, odluka {dmy(f['signal_date'])}</b> ({e(what)}). Kupnja idućeg dana na otvaranju po "
        f"{usd(f['entry_open'])}. Mjera za usporedbu je držanje točno 10 dana: zatvaranje {usd(f['exit_close'])} ({spc(f['r10'])}), "
        f"što bi od 1.000 € dalo da ste {word} oko {eur(abs(f['pnl_eur']))} (uz trošak 0,025 % po strani)."
    )


def cap_trade(tr: dict[str, Any]) -> str:
    """Rule-trade outcome sentence (the rule's own exit, which differs from the 10-day hold)."""
    return (
        f" <b>Samo pravilo</b> je izašlo {dmy(tr['exit_date'])} uz {spc(tr['return'])} po poslu "
        f"({seur(tr['return'] * 1000)} na 1.000 €)."
    )


def sec_header(d: Data) -> str:
    return f"""<header><span class="tagline">AICHAIN · učenje · istraživačka simulacija</span>
<h1>Momentum, potpora i otpor, mehanika tržišta</h1>
<p class="lead">Učimo od nule, na stvarnim cijenama i stvarnim datumima, i mjerimo ono što je najvažnije: pobjeđuje li išta od ovoga običnu slučajnost.</p>
<div class="chips">{chip("istraživačka simulacija", "warn")}{chip("nije savjet", "warn")}{chip("nije Critic PASS", "warn")}{chip("nijedan nalog nije poslan", "good")}</div>
<nav class="toc"><a href="#iskreno">Iskreno unaprijed</a><a href="#sazetak">Sažetak</a><a href="#momentum">Momentum</a><a href="#razine">Potpora i otpor</a><a href="#struktura">Struktura</a><a href="#likvidnost">Likvidnost</a><a href="#zone">Zone</a><a href="#diskont">Premium i diskont</a><a href="#topdown">Odozgo prema dolje</a><a href="#pravila">Pravila W1 do W8</a><a href="#mjerenja">Mjerenja</a><a href="#praksa">U praksi</a><a href="#pojmovnik">Pojmovnik</a></nav></header>"""


def sec_honest(d: Data) -> str:
    return f"""<section id="iskreno"><h2>Iskreno unaprijed</h2>
<div class="warnbox">
<p><b>Odakle dolazi rječnik.</b> Pojmovi na ovoj stranici (sweep, order block, premium i diskont, promjena smjera i slični) dolaze iz diskrecijske nastave "pametnog novca" koju the researcher prati. To je stil u kojem trgovac gleda graf i odlučuje od oka. Njegove tvrdnje <b>nisu dokazane</b>. Naš je posao drugačiji: svaki pojam pretvaramo u strogo pravilo koje se može izračunati, bez gledanja u budućnost, i pošteno ga testiramo, ne pretpostavljajući da radi.</p>
<p><b>Što je izmjereno.</b> Razdoblje: <b>3. 1. 2023. do 5. 10. 2026.</b> (AI era je glavno mjerilo; godine 2016. do 2022. služe samo kao kontekst). Podaci: dnevne svijeće {len(d.g["tickers"])} dionica (te kripto i dva metala odvojeno), samo dugo, bez posuđenog novca. Trošak: <b>0,025 % po strani</b> za dionice (na 1.000 € to je 0,25 € pri kupnji i 0,25 € pri prodaji), kripto 0,10 %. Ništa od toga ne uključuje tečaj eura i dolara, provizije IBKR-a, dividende ni poreze.</p>
<p><b>Što ovo nije.</b> To je <b>istraživačka simulacija</b> na povijesnim cijenama. Nije savjet za ulaganje, nije signal za kupnju, nije formalni Critic PASS, a nijedan nalog (ni probni ni pravi) nije poslan. Rezultati iz prošlosti ne obećavaju ništa o budućnosti. Američki ETF-ovi (GLD, SLV, SMH, SOXX) često nisu dostupni malim ulagačima iz EU, pa su ovdje samo referentne serije, označene <b>nepotvrđeno / referentno</b>.</p>
</div></section>"""


def sec_summary(d: Data) -> str:
    sr = d.PL["sr"]["all"]
    e4 = d.ev("E4_demand_zone_retest")
    bh = d.bh()
    c = sr["diff_vs_rand"]["bounce_rate"]["ci95"]
    assert c[0] <= 0 <= c[1]
    n_bad = sum(1 for k in RULES if d.era(k, "y2021_2022")["expectancy_eur"] <= 0)
    return f"""<section id="sazetak"><h2>Sažetak u šest točaka</h2>
<div class="verdict-top"><ul>
<li><b>Potpora i otpor.</b> Razina koju su potvrdila dva okreta cijene ne odbija cijenu češće od crte koju smo povukli nasumično: odbijanje {pc(sr["real"]["bounce_rate"])} naspram {pc(sr["rand"]["bounce_rate"])} (24.510 razina, 55 papira, AI era). Razlika je unutar slučajnosti.</li>
<li><b>Mehanika tržišta</b> (lov na stopove, promjena smjera, proboj strukture, zone) kao <b>strogo pravilo</b> na dnevnim svijećama ne pokazuje pouzdanu prednost nad prosjekom. Jedini granični rezultat je prvi povratak u svježu zonu potražnje ({sg(e4["mean_excess_vs_ticker_avg"] * 100)} postotnih bodova na 10 dana, donja granica intervala jedva iznad nule), a prije 2023. nema isti predznak.</li>
<li><b>Što ipak "radi često".</b> Po unaprijed upisanom pravilu ({hr(d.g["ranking"][0]["trades_per_month"], 1)} poslova mjesečno u zbroju svih dionica) prvi je {e(SHORT[d.g["ranking"][0]["contender"]])}, zatim {e(SHORT[d.g["ranking"][1]["contender"]])} i {e(SHORT[d.g["ranking"][2]["contender"]])}. To su pravila praćenja trenda i zamaha, ne "pametan novac".</li>
<li><b>Ali samo u AI eri.</b> U padu 2021. i 2022. očekivanje po poslu je nula ili negativno za {n_bad} od 8 pravila.</li>
<li><b>Držanje je jače.</b> Kupi-i-drži je na istim dionicama dao {pc(bh["total_return"], 0)} u AI eri; najbolje pravilo po ukupnom prinosu {pc(max(d.rule(k)["total_return"] for k in RULES), 0)}. Pravila su većinom u gotovini, pa je to i očekivano.</li>
<li><b>Za što su razine ipak korisne.</b> Kao orijentir za stop i veličinu pozicije (vidi odjeljak "Kako bi swing trader ovo koristio u praksi"), ne kao proročanstvo. Sve je u skladu s činjenicom da je ledger pokušaja K = {d.k}, pa najbolja ćelija tablice često izgleda dobro i slučajno.</li>
</ul></div></section>"""


def sec_how(d: Data) -> str:
    return """<section id="kako"><h2>Kako mjerimo (tri pitanja)</h2>
<div class="teach">
<p><b>1. Pobjeđuje li slučajnost?</b> Svakoj pravoj razini dodamo "lažne" (nasumična cijena, ista razina pomaknuta za 3 %, par crta oko razine). To je <b>placebo</b>, kao tableta od šećera u ispitivanju lijeka: ako i lažne crte daju isti rezultat, prava razina nije ništa posebna. Isto za događaje (npr. lov na stopove): uspoređujemo prinos nakon događaja s prosjekom istog papira u istom razdoblju. Taj se razlika zove <b>višak</b>.</p>
<p><b>2. Radi li kao pravilo i trguje li često?</b> Svaki pojam smo pretvorili u pravilo W1 do W8 s fiksnim brojevima (bez ugađanja) i pustili ga na 43 dionice. Pravilo je "podobno" samo ako ima barem 60 poslova u AI eri, pozitivnu zaradu po poslu i uz dvostruki trošak te <b>faktor dobiti</b> barem 1,2 (faktor dobiti 1,5 znači: na svaki izgubljeni euro dobijete 1,50 €).</p>
<p><b>3. Je li bolje od kupi-i-drži?</b> Kupi-i-drži znači kupiti na početku i ne dirati. Primjer: 1.000 € uloženo i držano. To je poštena mjera, jer pravilo koje ne pobjeđuje držanje nema što tražiti osim ako nudi nešto drugo (manje vremena u dionicama, češće male poslove).</p>
<p><b>Interval pouzdanosti 95 %</b> je raspon u kojem bi se razlika vjerojatno našla kad bismo pokus ponovili. Ako obuhvaća nulu (npr. od −2,9 do +0,0), razlika se ne razlikuje od slučajne. <b>pp</b> je postotni bod: razlika između 47 % i 46 % je 1 pp.</p>
</div></section>"""


# ---- concept sections


def sec_momentum(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["momentum_clean"], F["examples"]["momentum_failed"]
    w2, w3 = d.rule("W2_MOM_BREAK_20"), d.rule("W3_MOM_RANK_WEEKLY")
    a2, a3 = (
        d.era("W2_MOM_BREAK_20", "y2021_2022"),
        d.era("W3_MOM_RANK_WEEKLY", "y2021_2022"),
    )
    bh = d.bh()
    k4w, k4n = d.count_beat_hold("K4_TSMOM_126")
    k6w, k6n = d.count_beat_hold("K6_MOMENTUM_CS")
    au2, au3 = (
        d.AU["trade_concentration"]["W2_MOM_BREAK_20"],
        d.AU["trade_concentration"]["W3_MOM_RANK_WEEKLY"],
    )
    trc, trf = c["trade"], f["trade"]
    assert a2["expectancy_eur"] < 0 and a3["expectancy_eur"] < 0
    return f"""<section id="momentum"><h2><span class="n">1.</span>Momentum (zamah)</h2>
<div class="teach">
<p><b>Jednostavno.</b> Momentum je navika cijene da nastavi onamo kamo je već krenula: ono što je zadnjih tjedana raslo sklono je još neko vrijeme rasti, kao kotrljajuća kugla na nizbrdici. Trgovac koji prati zamah ne pita "je li jeftino", nego "ide li gore".</p>
<p><b>Primjer u eurima.</b> Dionica je u zadnjih 20 dana svaki dan bila niža od današnjeg zatvaranja. To je "20-dnevni vrh". Danas je prvi put iznad svega. Ako uložite 1.000 € u {
        usd(c["entry_open"])
    } po dionici, dobivate oko {
        hr(1000 / c["entry_open"], 2)
    } dionice; ako cijena 10 dana poslije bude {
        usd(c["exit_close"])
    }, vaših 1.000 € vrijedi oko {
        eur(1000 + c["pnl_eur"])
    }. Cijene su u dolarima, a simulator radi jednostavnosti računa 1 USD kao 1 €; stvarni tečaj to mijenja.</p>
</div>
<h3>Naše četiri varijante (fiksni brojevi, bez ugađanja)</h3>
{
        table(
            ["Pravilo", "Što radi, običnim riječima"],
            [
                [
                    "K4 zamah 126",
                    "Drži dionicu dok je njezin prinos u zadnjih 126 dana (oko pola godine) pozitivan.",
                ],
                [
                    "K6 rotacija",
                    "Prvog dana u mjesecu poredaj dionice skupine po prinosu zadnjih 126 dana i drži bolju polovicu; dionice s negativnim prinosom zamijeni gotovinom.",
                ],
                [
                    "W2 proboj 20-dnevnog vrha",
                    "Kupi sutra na otvaranju kad je zatvaranje najviše u zadnjih 20 dana, 60-dnevni prinos je pozitivan i cijena je iznad prosjeka 50 dana. Izlaz: zatvaranje ispod najnižeg od zadnjih 10 dana, ili nakon 15 dana, ili stop 8 % ispod kupnje.",
                ],
                [
                    "W3 tjedni rang",
                    "Svakog petka poredaj dionice skupine po prinosu zadnjih 20 dana; drži dionicu iz vodeće trećine koja je iznad prosjeka 50 dana; izađi kad ispadne iz gornje polovice.",
                ],
            ],
            left=2,
        )
    }
{
        fig(
            "momentum_clean.png",
            "Zamah, dobar primjer",
            cap_example(c, "pravilo W2")
            + f" Pravilo je izašlo {dmy(trc['exit_date'])} uz {spc(trc['return'])} po poslu.",
        )
    }
{
        fig(
            "momentum_failed.png",
            "Zamah, neuspjeli primjer",
            cap_example(f, "pravilo W2")
            + f" Pravilo je izašlo {dmy(trf['exit_date'])} uz {spc(trf['return'])} po poslu: zamah se ugasio, a stop je ostao ispod.",
        )
    }
<p class="note">Odabir primjera je pravilo, ne ljepota: prvi događaj u AI eri na MU (zatim NVDA, AMD) čiji je prinos nakon 10 dana barem +5 % (dobar) ili najviše −5 % (neuspjeli).</p>
<div class="evid"><h3>Što su mjerenja pokazala</h3>
<p><b>Trguje često i u AI eri zarađuje po poslu.</b> W2: {hr(w2["trades"])} poslova ({
        hr(w2["trades_per_month"], 1)
    } mjesečno u zbroju 43 dionica), prosječno {
        seur(w2["expectancy_eur"])
    } po poslu na 1.000 €, faktor dobiti {hr(w2["profit_factor"], 2)}, pogodak {
        pc(w2["hit_rate"], 0)
    }. W3: {hr(w3["trades"])} poslova ({hr(w3["trades_per_month"], 1)} mjesečno), {
        seur(w3["expectancy_eur"])
    } po poslu, faktor dobiti {
        hr(w3["profit_factor"], 2)
    }. Oba su "podobna" po unaprijed zadanom pravilu.</p>
<p><b>Ali tipičan posao gubi.</b> Medijan posla W2 je {
        spc(au2["median_return"])
    } (pola poslova je lošije od toga), a prosjek vuku rijetki veliki dobitnici: 10 najboljih poslova drži {
        pc(au2["best10_share_of_profit"], 0)
    } dobiti W2 i {
        pc(au3["best10_share_of_profit"], 0)
    } dobiti W3. Zamah je dakle "trend koji drži pobjednike", ne "većina poslova pobjeđuje".</p>
<p><b>U padu ne radi.</b> U razdoblju 2021. do 2022. očekivanje po poslu je {
        seur(a2["expectancy_eur"])
    } za W2 i {
        seur(a3["expectancy_eur"])
    } za W3. Zato "radi" vrijedi samo za AI eru dok se ne pokaže suprotno.</p>
<p><b>Držanje je ipak bolje.</b> Kupi-i-drži: {pc(bh["total_return"], 0)} u AI eri; W2 {
        pc(w2["total_return"], 0)
    }, W3 {pc(w3["total_return"], 0)}. Rotacija K6 je pobijedila držanje u {k6w} od {
        k6n
    } skupina, a K4 u {k4w} od {
        k4n
    }. Za zamah <b>nema zasebnog placebo testa</b> (usporedba je s držanjem i s drugim razdobljima).</p>
<p>{chip("radi često u AI eri", "good")} {chip("ne pobjeđuje držanje", "warn")} {
        chip("u padu 2021 do 2022 gubi", "bad")
    }</p></div></section>"""


def sec_levels(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["sr_flip_clean"], F["examples"]["sr_flip_failed"]
    sr = d.PL["sr"]["all"]
    dr, ds, dm = sr["diff_vs_rand"], sr["diff_vs_shift"], sr["diff_vs_match"]
    for dd in (dr, ds, dm):
        for m in ("bounce_rate", "break_rate"):
            assert dd[m]["ci95"][0] <= 0 <= dd[m]["ci95"][1]
    w4, w5 = d.rule("W4_SR_BOUNCE_V2"), d.rule("W5_SR_BREAKOUT_RETEST")
    au5 = d.AU["trade_concentration"]["W5_SR_BREAKOUT_RETEST"]
    strg = d.PL["sr"]["by_strength"]
    tch = d.PL["sr"]["by_touches"]
    blk = d.AU["placebo_block_bootstrap"]["diffs"]["rand"]["bounce_rate"]["block_3"]
    trc, trf = c["trade"], f["trade"]
    atr_pct = d.PL["context"]["median_atr14_pct"]
    rows = []
    for lab, k in (
        ("nasumična cijena", "rand"),
        ("pomak ±3 %", "shift"),
        ("par oko razine", "match"),
    ):
        dd = sr[f"diff_vs_{k}"]
        real = sr["mreal"] if k == "match" else sr["real"]
        rows.append(
            [
                lab,
                f"{pc(real['touch_rate'])} / {pc(sr[k]['touch_rate'])}",
                f"{pc(real['bounce_rate'])} / {pc(sr[k]['bounce_rate'])}",
                f"{sg(dd['bounce_rate']['diff'] * 100)} [{sg(dd['bounce_rate']['ci95'][0] * 100)}; {sg(dd['bounce_rate']['ci95'][1] * 100)}]",
                f"{pc(real['break_rate'])} / {pc(sr[k]['break_rate'])}",
                f"{sg(dd['break_rate']['diff'] * 100)} [{sg(dd['break_rate']['ci95'][0] * 100)}; {sg(dd['break_rate']['ci95'][1] * 100)}]",
            ]
        )
    return f"""<section id="razine"><h2><span class="n">2.</span>Potpora i otpor</h2>
<div class="teach">
<p><b>Jednostavno.</b> <b>Potpora</b> je razina ispod cijene na kojoj se cijena ranije okrenula prema gore ("tu su kupci stali"). <b>Otpor</b> je razina iznad cijene na kojoj se okrenula prema dolje. Ideja je da cijena "pamti" mjesta, jer su ondje ljudi kupovali ili prodavali i opet će reagirati. Što je više <b>dodira</b> (okreta na istom mjestu), to bi razina trebala biti jača.</p>
<p><b>Zona, ne crta.</b> Cijena rijetko okrene točno na istoj brojci, pa razinu zamišljamo kao traku. U našem pravilu okreti unutar 1 % cijene (ili pola prosječnog dnevnog raspona) spajaju se u jednu razinu.</p>
<p><b>Obrnuta uloga ("flip").</b> Kad cijena zatvori iznad otpora, taj bi se otpor mogao pretvoriti u potporu: cijena se vrati do njega, "testira" ga odozgo i odbije. To je naše pravilo W5.</p>
<p><b>Primjer u eurima.</b> {e(c["ticker"])} je {dmy(c["break_date"])} prvi put zatvorio iznad {usd(c["level"])}, razine koju su prije činila {c["touches"]} okreta. Kad se {dmy(c["signal_date"])} vratio do zone i zatvorio iznad nje, pravilo bi sutradan kupilo po {usd(c["entry_open"])}, sa stopom 3 % ispod razine ({usd(c["level"] * 0.97)}). 1.000 € kupilo bi oko {hr(1000 / c["entry_open"], 2)} dionice. Prosječni dnevni raspon ove vrste dionica (<b>ATR</b>, prosjek razlike najviše i najniže cijene dana tijekom 14 dana) je u medijanu oko {hr(atr_pct, 1)} % cijene, dakle stop od 3 % je manji od jednog uobičajenog dana.</p>
</div>
<h3>Kako je razina napravljena (strogo)</h3>
<p><b>Okret (pivot)</b> je najviša (najniža) točka koja je viša (niža) od 5 svijeća sa svake strane. Zato je poznat tek 5 svijeća nakon nastanka: dno od 90 € s 5 viših svijeća na obje strane saznajemo tek 5 dana kasnije. Okreti blizu jedan drugome spajaju se u razinu, noviji okret vrijedi više (poluvrijeme 250 svijeća). Odluka je uvijek na zatvaranju dana, a kupnja na idućem otvaranju.</p>
{fig("sr_clean.png", "Potpora i otpor, dobar primjer", cap_example(c, "pravilo W5") + f" Razina {usd(c['level'])}, prvo zatvaranje iznad nje {dmy(c['break_date'])}." + cap_trade(trc))}
{fig("sr_failed.png", "Potpora i otpor, neuspjeli primjer", cap_example(f, "pravilo W5") + f" Razina {usd(f['level'])}." + cap_trade(trf) + f" Stop je bio 3 % ispod razine ({usd(f['level'] * 0.97)}), ali kupnja je bila na {usd(f['entry_open'])}, pa je gubitak {spc(trf['return'])} na ulog, a ne 3 %.")}
<div class="evid"><h3>Što su mjerenja pokazala: test lažnih razina</h3>
<p>U AI eri uzeli smo zadnji trgovački dan svakog mjeseca (44 mjeseca, 55 papira), sve razine koje su tada <b>već bile poznate</b> ({hr(sr["n_levels"])} razina), i gledali sljedećih 20 dana. <b>Dodir</b> je svijeća koja dođe unutar 0,25 ATR od crte. <b>Odbijanje</b> je potez od najmanje 1,5 ATR natrag s razine u idućih 10 svijeća, a <b>probijanje</b> zatvaranje više od 1 ATR iza razine. Primjer: dionica od 100 € s ATR-om 4 € znači odbijanje od 6 € (na 1.000 € to je 60 €).</p>
{table(["Kontrola", "Dodir: prava / lažna", "Odbijanje: prava / lažna", "Razlika u odbijanju (pp) i interval", "Probijanje: prava / lažna", "Razlika u probijanju (pp) i interval"], rows, left=1)}
<p>Svi intervali za odbijanje i probijanje obuhvaćaju nulu, i uz strožu provjeru s blokovima od 3 mjeseca (odbijanje protiv nasumičnih crta: od {sg(blk[0] * 100)} do {sg(blk[1] * 100)} pp). Razina potvrđena okretima <b>ne odbija cijenu ništa češće</b> od mjesta na kojem nitko nije povukao crtu. Dodiri su čak malo rjeđi nego kod nasumičnih crta ({sg(dr["touch_rate"]["diff"] * 100)} pp). Jače razine ne pomažu: najjača trećina daje razliku u odbijanju {sg(strg["jako (gornja trećina)"]["diff_vs_match"]["bounce_rate"]["diff"] * 100)} pp, a razine s 4 i više okreta {sg(tch["4+ okreta"]["diff_vs_match"]["bounce_rate"]["diff"] * 100)} pp (obje uz interval koji obuhvaća nulu).</p>
<p><b>Pravila.</b> W4 (kupi odbijanje od potpore uz dvije potvrde): {hr(w4["trades"])} poslova, ali samo {seur(w4["expectancy_eur"])} po poslu i faktor dobiti {hr(w4["profit_factor"], 2)}; <b>nije podobno</b>. W5 (proboj pa povratni test): {hr(w5["trades"])} poslova, {seur(w5["expectancy_eur"])} po poslu, faktor dobiti {hr(w5["profit_factor"], 2)}, ali pogodak je samo {pc(w5["hit_rate"], 0)}, medijan posla je {spc(au5["median_return"])}, a 10 najboljih poslova drži {pc(au5["best10_share_of_profit"], 0)} dobiti (najbolji je donio {pc(au5["largest_return"], 0)} na ulog). Rezultat W5 treba čitati kao "povremeni veliki trend", ne kao "razine drže".</p>
<p>{chip("ne pobjeđuje slučajnost", "bad")} {chip("koristi se za stop i planiranje, ne kao predviđanje", "warn")}</p></div></section>"""


def sec_structure(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["bos_clean"], F["examples"]["bos_failed"]
    an = F["anatomy"]
    e5 = {h: d.ev("E5_bos_trend", h) for h in ("5", "10", "20")}
    for st in e5.values():
        assert st["excess_ci95"][0] <= 0 <= st["excess_ci95"][1]
    ev_txt = ", ".join(
        f"{dmy(x['date'])} ({'BOS gore' if x['kind'] == 'bos' and x['dir'] == 1 else 'BOS dolje' if x['kind'] == 'bos' else 'promjena gore' if x['dir'] == 1 else 'promjena dolje'})"
        for x in an["events"][:6]
    )
    dp = an["demo_pivot"]
    return f"""<section id="struktura"><h2><span class="n">3.</span>Struktura tržišta: vrhovi, dna, proboj i promjena smjera</h2>
<div class="teach">
<p><b>Jednostavno.</b> Zamislite stepenice. Ako je svaki novi vrh viši od prethodnog (<b>HH</b>, viši vrh) i svako novo dno više od prethodnog (<b>HL</b>, više dno), stepenice vode gore: <b>bikovska struktura</b>. Ako su vrhovi sve niži (<b>LH</b>) i dna sve niža (<b>LL</b>), vode dolje: <b>medvjeđa struktura</b>.</p>
<p><b>Proboj strukture (BOS, break of structure).</b> Zatvaranje iznad zadnjeg vrha u bikovskom trendu: stepenice se nastavljaju. <b>Promjena smjera (market shift, change of character).</b> U silaznom trendu zatvaranje iznad zadnjeg <i>nižeg vrha</i>: prvi znak da se trend možda okreće.</p>
<p><b>Primjer u eurima.</b> Zadnji potvrđeni vrh je {usd(c["bos_level"])}. Cijena zatvori na {usd(c["signal_close"])}: BOS. Pravilo "kupi sutra" na {usd(c["entry_open"])} s 1.000 € daje oko {hr(1000 / c["entry_open"], 2)} dionice.</p>
</div>
{fig("struktura_anatomija.png", "Anatomija strukture na MU", f"<b>Anatomija na stvarnim podacima (MU, {dmy(an['window'][0])} do {dmy(an['window'][1])}).</b> Trokuti su potvrđeni okreti, označeni HH, HL, LH ili LL u odnosu na prethodni okret iste vrste. Isprekidane crte su probijene razine, redom prvih šest događaja u prozoru: {e(ev_txt)}. Crveno polje: vrh od {dmy(dp['date'])} ({usd(dp['price'])}) postao je poznat tek {dmy(dp['known'])}, 5 trgovačkih dana kasnije. Prije toga ga pravilo ne smije koristiti.")}
{fig("bos_clean.png", "BOS, dobar primjer", cap_example(c, "BOS u bikovskom trendu") + f" Probijeni vrh: {usd(c['bos_level'])} ({dmy(c['bos_level_date'])}).")}
{fig("bos_failed.png", "BOS, neuspjeli primjer", cap_example(f, "BOS u bikovskom trendu") + f" Probijeni vrh: {usd(f['bos_level'])} ({dmy(f['bos_level_date'])}); proboj nije potrajao.")}
<div class="evid"><h3>Što su mjerenja pokazala</h3>
<p>BOS u smjeru bikovskog trenda (događaj E5): {hr(d.PL["mechanics_ai_era"]["events"]["E5_bos_trend"]["n"])} događaja u AI eri. Prinos nakon 5, 10 i 20 dana je u prosjeku {pc(e5["5"]["mean"])}, {pc(e5["10"]["mean"])} i {pc(e5["20"]["mean"])}, ali to je uglavnom bik-tržište: <b>višak</b> nad prosjekom istog papira je {sg(e5["5"]["mean_excess_vs_ticker_avg"] * 100)}, {sg(e5["10"]["mean_excess_vs_ticker_avg"] * 100)} i {sg(e5["20"]["mean_excess_vs_ticker_avg"] * 100)} pp, a sva tri intervala obuhvaćaju nulu (npr. 10 dana: od {sg(e5["10"]["excess_ci95"][0] * 100)} do {sg(e5["10"]["excess_ci95"][1] * 100)} pp). Primjer: ako je papir u prosjeku {pc(d.PL["mechanics_ai_era"]["all_days"]["10"]["mean"])} u 10 dana, nakon BOS-a nije bio ništa bolji.</p>
<p>Promjena smjera ne postoji kao samostalan test; ulazi u okidač W6 (vidi odjeljak o likvidnosti). Neovisni test pogleda u budućnost: pivoti, struktura i okidači računati na skraćenim podacima (64 nasumična reza) uvijek se poklapaju s punim izračunom.</p>
<p>{chip("ne pobjeđuje slučajnost", "bad")}</p></div></section>"""


def sec_liquidity(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["sweep_clean"], F["examples"]["sweep_failed"]
    eq = F["equal_lows"]
    e1 = {h: d.ev("E1_sweep_shift_discount", h) for h in ("5", "10", "20")}
    for h in ("10", "20"):
        assert e1[h]["excess_ci95"][0] <= 0 <= e1[h]["excess_ci95"][1]
    e1b = d.AU["event_block_bootstrap"]["E1_sweep_shift_discount"]["5"]
    w6 = d.rule("W6_MM_SWEEP_SHIFT")
    au6 = d.AU["trade_concentration"]["W6_MM_SWEEP_SHIFT"]
    a6 = d.era("W6_MM_SWEEP_SHIFT", "y2021_2022")
    after_low = c["min_low_after_sweep"]
    sweep_after = (
        f"cijena je do dana odluke ({dmy(c['signal_date'])}) još pala do {usd(after_low)}, dakle sweep nije bio dno"
        if after_low < c["sweep_low"]
        else f"cijena do dana odluke ({dmy(c['signal_date'])}) nije pala ispod {usd(c['sweep_low'])}"
    )
    return f"""<section id="likvidnost"><h2><span class="n">4.</span>Likvidnost, lov na stopove (sweep) i jednaka dna</h2>
<div class="teach">
<p><b>Jednostavno.</b> Mnogi trgovci stavljaju stop (automatsku prodaju) tik ispod očitog dna. Tamo se skupi mnogo naloga, tzv. <b>likvidnost</b>. Teorija kaže: veliki igrači ponekad cijenu na kratko "probiju" ispod dna da pokupe te naloge, pa se cijena vrati. Takav potez (fitilj ispod dna, a zatvaranje opet iznad) zove se <b>sweep</b> ili "lov na stopove".</p>
<p><b>Jednaka dna i vrhovi.</b> Dva dna na gotovo istoj cijeni (u našem pravilu unutar 0,3 %) smatraju se posebno "očitima": ispod njih ima najviše stopova.</p>
<p><b>Primjer u eurima.</b> Dno je {usd(c["sweep_level"])}, a cijena jedan dan probije na {usd(c["sweep_low"])} i zatvori na {usd(c["sweep_close"])}. Ako ste imali stop na {usd(c["sweep_level"] * 0.995)}, izbačeni ste. Teorija kaže da cijena nakon toga ide gore. U ovom stvarnom primjeru {sweep_after}. Na 1.000 € to je razlika između "izlaz na dnu" i "ostao u poziciji".</p>
</div>
<h3>Okidač koji smo testirali (strogo)</h3>
<p>Tjedni trend nije medvjeđi; cijena je u diskontu (donja polovica raspona, vidi odjeljak 6); u zadnjih 5 svijeća fitilj ispod jednog od zadnja tri potvrđena dna uz zatvaranje iznad njega; zatim zatvaranje iznad zadnjeg nižeg vrha je okidač. Kupnja idućeg dana na otvaranju, stop ispod dna sweepa umanjen za pola ATR-a.</p>
{fig("jednaka_dna.png", "Jednaka dna na NVDA", f"<b>Jednaka dna (ilustracija vokabulara, nije zasebno testirano).</b> {e(eq['ticker'])}: dna od {dmy(eq['p1_date'])} ({usd(eq['p1_price'])}) i {dmy(eq['p2_date'])} ({usd(eq['p2_price'])}) razlikuju se manje od 0,3 %. Dana {dmy(eq['sweep_date'])} cijena je pala na {usd(eq['sweep_low'])}, ali zatvorila na {usd(eq['sweep_close'])}, dakle iznad razine.")}
{fig("sweep_clean.png", "Sweep, dobar primjer", cap_example(c, "sweep, pa promjena smjera") + f" Dno {usd(c['sweep_level'])} ({dmy(c['sweep_level_date'])}), sweep {dmy(c['sweep_date'])}, promjena smjera iznad {usd(c['shift_level'])}.")}
{fig("sweep_failed.png", "Sweep, neuspjeli primjer", cap_example(f, "sweep, pa promjena smjera") + f" Dno {usd(f['sweep_level'])} ({dmy(f['sweep_level_date'])}), sweep {dmy(f['sweep_date'])}, promjena smjera iznad {usd(f['shift_level'])}.")}
<div class="evid"><h3>Što su mjerenja pokazala</h3>
<p><b>Događaj E1</b> (sweep, pa promjena smjera u diskontu): {e1["5"]["n"]} događaja u AI eri. Višak nad prosjekom papira: {sg(e1["5"]["mean_excess_vs_ticker_avg"] * 100)} pp na 5 dana (interval od {sg(e1["5"]["excess_ci95"][0] * 100)} do {sg(e1["5"]["excess_ci95"][1] * 100)}; uz blokove od 3 mjeseca od {sg(e1b["ci95_block_3"][0] * 100)} do {sg(e1b["ci95_block_3"][1] * 100)}, dakle statistički lošije od prosjeka), {sg(e1["10"]["mean_excess_vs_ticker_avg"] * 100)} pp na 10 dana i {sg(e1["20"]["mean_excess_vs_ticker_avg"] * 100)} pp na 20 dana (oba intervala obuhvaćaju nulu). Pogodak na 5 dana je {pc(e1["5"]["hit_rate"], 0)}, ispod polovice.</p>
<p><b>Pravilo W6</b> je formalno podobno ({hr(w6["trades"])} poslova, {seur(w6["expectancy_eur"])} po poslu, faktor dobiti {hr(w6["profit_factor"], 2)}), ali to je oko jedan posao po dionici godišnje, pa "trguje često" ne stoji. Bez 10 najboljih poslova prosječni prinos pada na {spc(au6["mean_without_best10"], 2)} po poslu ({pc(au6["best10_share_of_profit"], 0)} dobiti drži samo 10 poslova), a u razdoblju 2021. do 2022. očekivanje je {seur(a6["expectancy_eur"])}. Pozitivan prosjek ne treba čitati kao dokaz da je lov na stopove stvaran; vjerojatniji izvori su izlaz uz praćenje i bik-tržište (to nije posebno izmjereno).</p>
<p><b>Jednaka dna i vrhovi nisu zasebno testirani.</b> Naš sweep koristi potvrđena dna općenito, ne samo jednaka.</p>
<p>{chip("ne pobjeđuje slučajnost", "bad")} {chip("jednaka dna: nije testirano zasebno", "warn")}</p></div></section>"""


def sec_zones(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["zone_clean"], F["examples"]["zone_failed"]
    e3 = {h: d.ev("E3_sweep_shift_discount_weekly_zone", h) for h in ("5", "10")}
    e4 = {h: d.ev("E4_demand_zone_retest", h) for h in ("5", "10", "20")}
    e4p = d.PL["mechanics_pre_ai_context"]["events"]["E4_demand_zone_retest"]["by_h"][
        "10"
    ]
    blk = d.AU["event_block_bootstrap"]["E4_demand_zone_retest"]["10"]
    w7 = d.rule("W7_MM_DEMAND_RETEST")
    au7 = d.AU["trade_concentration"]["W7_MM_DEMAND_RETEST"]
    a7 = d.era("W7_MM_DEMAND_RETEST", "y2021_2022")
    assert (
        e4["10"]["excess_ci95"][0] > 0
        and blk["ci95_block_3"][0] < 0
        and e4["20"]["excess_ci95"][0] < 0
    )
    return f"""<section id="zone"><h2><span class="n">5.</span>Zone potražnje i ponude, order block i procjep</h2>
<div class="teach">
<p><b>Jednostavno.</b> <b>Zona potražnje</b> (u žargonu <b>order block</b>) je mjesto s kojeg je krenuo snažan rast: zadnja silazna (crna) svijeća prije poteza. Teorija: ondje su kupci nagomilali velike naloge, pa će ih cijena kad se vrati "braniti". <b>Zona ponude</b> je zrcalna slika za pad. Zona je <b>svježa</b> dok joj se cijena prvi put ne vrati.</p>
<p><b>Procjep (fair value gap, FVG)</b> je praznina između tri svijeće: najviša cijena prve je niža od najniže cijene treće. Opisan je u nastavi, ali ga <b>nijedno naše pravilo ne koristi i nije testiran</b>.</p>
<p><b>Primjer u eurima.</b> {e(c["ticker"])}, zona od {usd(c["zone_lo"])} do {usd(c["zone_hi"])}. Cijena se prvi put vratila {dmy(c["signal_date"])}; kupnja idućeg dana na {usd(c["entry_open"])} s 1.000 € je oko {hr(1000 / c["entry_open"], 2)} dionice. Stop ispod dna zone ({usd(c["zone_lo"])}) znači najveći planirani gubitak od oko {eur(1000 * (c["entry_open"] - c["zone_lo"]) / c["entry_open"])} na 1.000 €.</p>
</div>
<p><b>Strogo pravilo.</b> Zona je raspon (najviša do najniža) zadnje silazne svijeće prije rasta od barem 2 ATR-a unutar 3 svijeće koji je probio zadnji potvrđeni vrh. Zona postoji tek kad rast završi (to je dan "poznata od"). Svježa je do prvog povratka.</p>
{fig("zona_clean.png", "Zona potražnje, dobar primjer", cap_example(c, "prvi povratak u zonu") + f" Zona nastala {dmy(c['zone_base_date'])}, poznata od {dmy(c['zone_known_date'])}.")}
{fig("zona_failed.png", "Zona potražnje, neuspjeli primjer", cap_example(f, "prvi povratak u zonu") + f" Zona nastala {dmy(f['zone_base_date'])}, poznata od {dmy(f['zone_known_date'])}; zona nije zadržala cijenu.")}
<div class="evid"><h3>Što su mjerenja pokazala</h3>
<p><b>Događaj E4</b> (prvi povratak u svježu zonu koja je držala): {e4["10"]["n"]} događaja u AI eri. Višak nad prosjekom papira: {sg(e4["5"]["mean_excess_vs_ticker_avg"] * 100)} pp na 5 dana, <b>{sg(e4["10"]["mean_excess_vs_ticker_avg"] * 100)} pp na 10 dana</b> (interval od {sg(e4["10"]["excess_ci95"][0] * 100, 2)} do {sg(e4["10"]["excess_ci95"][1] * 100)}) i {sg(e4["20"]["mean_excess_vs_ticker_avg"] * 100)} pp na 20 dana (interval obuhvaća nulu). To je oko {eur(e4["10"]["mean_excess_vs_ticker_avg"] * 1000)} na 1.000 € prije troškova, uz donju granicu jedva iznad nule. Uz blokove od 3 mjeseca donja granica pada na {sg(blk["ci95_block_3"][0] * 100)} pp, dakle ispod nule. U godinama 2017. do 2022. višak je {sg(e4p["mean_excess_vs_ticker_avg"] * 100)} pp (interval od {sg(e4p["excess_ci95"][0] * 100)} do {sg(e4p["excess_ci95"][1] * 100)}). To je tipičan obrazac za slučajnost ili za učinak jednog tržišnog režima, uz 15 kombinacija po razdoblju (jedan slučajni "pogodak" je očekivan).</p>
<p><b>Događaj E3</b> (sweep i promjena smjera, uz bikovski tjedni trend i dodir svježe zone): samo {e3["5"]["n"]} događaja, višak {sg(e3["10"]["mean_excess_vs_ticker_avg"] * 100)} pp na 10 dana (interval od {sg(e3["10"]["excess_ci95"][0] * 100)} do {sg(e3["10"]["excess_ci95"][1] * 100)}): statistički <b>lošije</b> od prosjeka. Više "slaganja" uvjeta nije dalo više, nego manje.</p>
<p><b>Pravilo W7</b>: {hr(w7["trades"])} poslova ({hr(w7["trades_per_ticker_year"], 1)} po dionici godišnje), {seur(w7["expectancy_eur"])} po poslu, faktor dobiti {hr(w7["profit_factor"], 2)}, pogodak {pc(w7["hit_rate"], 0)}. Formalno podobno, ali 10 najboljih poslova drži {pc(au7["best10_share_of_profit"], 0)} dobiti (ostali zajedno gube), a u 2021. do 2022. očekivanje je {seur(a7["expectancy_eur"])}. To nije "trguje često".</p>
<p>{chip("granično, samo AI era", "warn")} {chip("procjep (FVG): nije testiran", "warn")}</p></div></section>"""


def sec_discount(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["discount_clean"], F["examples"]["discount_failed"]
    return f"""<section id="diskont"><h2><span class="n">6.</span>Premium i diskont</h2>
<div class="teach">
<p><b>Jednostavno.</b> Uzmite zadnje potvrđeno dno i zadnji potvrđeni vrh: to je <b>raspon</b>. Gornja polovica je <b>premium</b> (skupo), donja je <b>diskont</b> (jeftino). Pravilo kaže: dugo se traži samo u diskontu, kao kad kupujete na sniženju, a ne na vrhuncu.</p>
<p><b>Primjer u eurima.</b> Raspon od 80 € do 120 €: sredina je 100 €. Cijena od 90 € je u diskontu (na 25 % raspona), cijena od 110 € u premiumu. Pravi primjer: {e(c["ticker"])} je imao raspon od {usd(c["range_lo"])} do {usd(c["range_hi"])}, sredina {usd((c["range_lo"] + c["range_hi"]) / 2)}.</p>
</div>
{fig("diskont_clean.png", "Premium i diskont, dobar primjer", cap_example(c, "sweep i promjena smjera u diskontu") + f" Raspon {usd(c['range_lo'])} do {usd(c['range_hi'])}.")}
{fig("diskont_failed.png", "Premium i diskont, neuspjeli primjer", cap_example(f, "sweep i promjena smjera u diskontu") + f" Raspon {usd(f['range_lo'])} do {usd(f['range_hi'])}.")}
<p class="note">Za ovaj odjeljak preskaču se MU, WDC i STX (već se pojavljuju u drugim odjeljcima), pa su uzeti prvi događaji na {e(c["ticker"])} koji zadovoljavaju isto pravilo +5 % / −5 %, uz uvjet da je raspon barem 10 % cijene (da se slika može čitati). Uvjet ne ovisi o ishodu.</p>
<div class="evid"><h3>Što su mjerenja pokazala</h3>
<p><b>Premium i diskont nisu testirani zasebno.</b> Diskont je jedan od uvjeta u događaju E1 i u pravilima W6 i W7; rezultati tih testova (odjeljci 4 i 5) ne daju prednost, ali se ne može reći koliko je tome pridonio baš uvjet diskonta. Svaki zaseban test bio bi novi pokušaj (povećava K u ledgeru) i predlažemo ga kao novu hipotezu s novim ID-em (vidi izvještaj).</p>
<p>{chip("nije testirano zasebno", "warn")}</p></div></section>"""


def sec_topdown(d: Data, F: dict[str, Any]) -> str:
    c, f = F["examples"]["topdown_clean"], F["examples"]["topdown_failed"]
    e2 = {h: d.ev("E2_sweep_shift_discount_weekly", h) for h in ("5", "10", "20")}
    e2b = d.AU["event_block_bootstrap"]["E2_sweep_shift_discount_weekly"]["5"]
    e1 = d.ev("E1_sweep_shift_discount", "5")
    e2p = d.ev("E2_sweep_shift_discount_weekly", "5", "mechanics_pre_ai_context")
    assert e2["5"]["excess_ci95"][1] < 0 and e2b["ci95_block_3"][1] < 0
    return f"""<section id="topdown"><h2><span class="n">7.</span>Odozgo prema dolje: tjedni smjer, dnevni okidač</h2>
<div class="teach">
<p><b>Jednostavno.</b> Prvo pogledate veliku sliku (<b>tjedne</b> svijeće): ide li trend gore? Ako ne ide, dnevne signale za kupnju preskačete. Tek onda na <b>dnevnom</b> grafu tražite zone i točan okidač. To je kao da prvo pogledate vremensku prognozu za tjedan, pa tek onda odlučite hoćete li poći na izlet.</p>
<p><b>Strogo.</b> Tjedne svijeće gradimo iz dnevnih, a tjedan se koristi tek kad je završen. Tjedna struktura se računa istim pravilom okreta kao i dnevna. U W6 tjedni trend ne smije biti medvjeđi (tjedno zatvaranje iznad prosjeka zadnjih 10 tjedana).</p>
<p><b>Primjer u eurima.</b> {e(c["ticker"])} je {dmy(c["signal_date"])} imao bikovski tjedni trend, a dnevno je zatvorio iznad zadnjeg nižeg vrha ({usd(c["shift_level"])}). Kupnja idućeg dana na {usd(c["entry_open"])}: 1.000 € je oko {hr(1000 / c["entry_open"], 2)} dionice.</p>
</div>
{fig("topdown_clean.png", "Odozgo prema dolje, dobar primjer", cap_example(c, "tjedni bikovski trend + dnevni okidač"))}
{fig("topdown_failed.png", "Odozgo prema dolje, neuspjeli primjer", cap_example(f, "tjedni bikovski trend + dnevni okidač") + " Tjedni trend je bio bikovski, a ipak je dnevni signal propao: filter smanjuje buku, ne daje jamstvo.")}
<div class="evid"><h3>Što su mjerenja pokazala</h3>
<p>Događaj E2 je E1 uz uvjet bikovskog tjednog trenda. Ako je top-down filter koristan, višak bi trebao porasti. Nije: E1 na 5 dana {sg(e1["mean_excess_vs_ticker_avg"] * 100)} pp, a E2 (n={e2["5"]["n"]}) <b>{sg(e2["5"]["mean_excess_vs_ticker_avg"] * 100)} pp</b>, interval od {sg(e2["5"]["excess_ci95"][0] * 100)} do {sg(e2["5"]["excess_ci95"][1] * 100)} (uz blokove od 3 mjeseca do {sg(e2b["ci95_block_3"][1] * 100)}): statistički lošije od prosjeka. Na 10 dana {sg(e2["10"]["mean_excess_vs_ticker_avg"] * 100)} pp i na 20 dana {sg(e2["20"]["mean_excess_vs_ticker_avg"] * 100)} pp (oba intervala obuhvaćaju nulu). U godinama 2017. do 2022. višak je {sg(e2p["mean_excess_vs_ticker_avg"] * 100)} pp (interval od {sg(e2p["excess_ci95"][0] * 100)} do {sg(e2p["excess_ci95"][1] * 100)}), dakle blizu nule. Tjedni filter je lijep za razumijevanje, ali u našim podacima ga ne možemo opravdati kao prednost.</p>
<p>{chip("ne pobjeđuje slučajnost", "bad")}</p></div></section>"""


def sec_rules(d: Data) -> str:
    rows = []
    mapping = {
        "W1_C13C_ORIG": "Nije iz videa. Petrov algoritam: pad od 5 % unutar uzlaznog trenda (iznad prosjeka 200 dana), stop 10 % ispod vrha. Mjerilo.",
        "W2_MOM_BREAK_20": "Momentum: proboj 20-dnevnog vrha.",
        "W3_MOM_RANK_WEEKLY": "Momentum: tjedni rang unutar skupine.",
        "W4_SR_BOUNCE_V2": "Potpora: odbijanje od razine s dvije potvrde.",
        "W5_SR_BREAKOUT_RETEST": "Potpora i otpor: proboj pa povratni test (obrnuta uloga).",
        "W6_MM_SWEEP_SHIFT": "Likvidnost, promjena smjera, diskont, tjedni smjer (odozgo prema dolje).",
        "W7_MM_DEMAND_RETEST": "Zona potražnje, struktura, diskont.",
        "W8_IBS_REVERT": "Nije iz videa: kupi snažan jednodnevni pad unutar uzlaznog trenda (kontrola).",
    }
    for k in RULES:
        r = d.rule(k)
        a = d.era(k, "y2021_2022")
        ok = d.eligible(k)
        rows.append(
            [
                e(SHORT[k]),
                e(mapping[k]),
                hr(r["trades"]),
                hr(r["trades_per_month"], 1),
                seur(r["expectancy_eur"]),
                hr(r["profit_factor"], 2),
                seur(a["expectancy_eur"]),
                chip("podobno", "good") if ok else chip("nije podobno", "bad"),
            ]
        )
    la = {x["array_checks"] for x in d.S["lookahead"].values()}
    lt = {x["trade_checks"] for x in d.S["lookahead"].values()}
    assert (
        len(la) == 1
        and len(lt) == 1
        and all(x["ok"] for x in d.S["lookahead"].values())
    )
    LA, LT = la.pop(), lt.pop()
    return f"""<section id="pravila"><h2>Kako je svaki pojam postao strogo pravilo (W1 do W8)</h2>
<p>Svih osam pravila registrirano je <b>prije prvog pokretanja</b> (ledger K od 534 do 542: osam pravila i mjerilo), s fiksnim brojevima i bez ugađanja. Svako pravilo odlučuje na zatvaranju dana, kupuje na idućem otvaranju, samo dugo, a svaka je odluka provjerena testom pogleda u budućnost ({LA} provjera nizova i {LT} provjera poslova po pravilu, bez ijedne greške). Tablica je za zbroj 43 dionica u AI eri; zadnji stupac je isti test u padu 2021. do 2022.</p>
{table(["Pravilo", "Koji pojam", "Poslova", "Poslova mj.", "Zarada po poslu", "Faktor dobiti", "2021 do 2022", "Pravilo 'radi često'"], rows, left=2)}
<p class="note">Ovdje 'poslova mj.' znači poslova mjesečno za cijelu skupinu od 43 dionice (svaka dionica ima svojih 1.000 €). Za jednu dionicu to je oko {hr(d.rule("W2_MOM_BREAK_20")["trades_per_ticker_year"], 1)} poslova godišnje za W2, a samo {hr(d.rule("W6_MM_SWEEP_SHIFT")["trades_per_ticker_year"], 1)} za W6. Primjer: pratite li samo MU, WDC i STX, pravilo W1 daje oko {hr(d.RM["contenders"]["W1_C13C_ORIG"]["ai_era"]["trades_per_month"], 1)} poslova mjesečno.</p></section>"""


def sec_evidence(d: Data) -> str:
    sr = d.PL["sr"]["all"]
    bh = d.bh()
    return f"""<section id="mjerenja"><h2>Sva mjerenja na jednom mjestu</h2>
<h3>1. Što pravila zarađuju po poslu</h3>
{fig("dokaz_pravila.png", "Zarada po poslu za pravila W1 do W8", f"<b>Kako čitati.</b> Svaka vodoravna traka je jedno pravilo; dužina je prosječna zarada po poslu na uloženih 1.000 € (prije poreza). Zelena traka: ispunjava pravilo 'radi često'; crvena: ne. Uz traku piše koliko poslova mjesečno pravilo napravi na 43 dionice i koliki je udio dobitnih. Zaključak: najbolje pravilo po poslu (W5) ima pogodak od samo {pc(d.rule('W5_SR_BREAKOUT_RETEST')['hit_rate'], 0)}, a kupi-i-drži je u istom razdoblju dao {pc(bh['total_return'], 0)}.")}
<h3>2. Isto pravilo, tri razdoblja</h3>
{fig("dokaz_razdoblja.png", "Zarada po poslu po razdobljima", "<b>Kako čitati.</b> Za svako pravilo tri stupca: 2016. do 2020. (sivo), pad 2021. do 2022. (crveno) i AI era (zeleno). Stupac ispod nule znači da je pravilo prosječno gubilo po poslu. Zato je AI era jedino mjerilo na kojem 'radi' vrijedi, a nijedno pravilo nije dokazano u drugom režimu.")}
<h3>3. Razine nasuprot lažnim crtama</h3>
{fig("dokaz_razine.png", "Razine i lažne crte", f"<b>Kako čitati.</b> Tri skupine stupaca: koliko često se crta dodirne, koliko često se cijena nakon dodira odbije, koliko često je probije. Zeleno su prave razine, ostale boje lažne crte. Ako su stupci istih visina, razina nema posebnu moć. Ovdje su: odbijanje {pc(sr['real']['bounce_rate'])} (prave) naspram {pc(sr['rand']['bounce_rate'])}, {pc(sr['shift']['bounce_rate'])} i {pc(sr['match']['bounce_rate'])} (lažne). Svijetlozeleni stupac je ista usporedba samo na podskupu razina koji ima par.")}
<h3>4. Mehanika tržišta: višak prinosa</h3>
{fig("dokaz_mehanika.png", "Višak prinosa za događaje E1 do E5", "<b>Kako čitati.</b> Svaki redak je jedan događaj. Točka je prosječni višak prinosa nad prosjekom istog papira (na 10 dana, u postotnim bodovima), a crta je 95 % interval pouzdanosti. Crvena okomita crta je nula. Ako crta preklapa nulu, nema dokaza prednosti. Zeleno je AI era, sivo 2017. do 2022. Samo E4 u AI eri jedva stoji desno od nule, a u ranijim godinama ima suprotan predznak.")}
</section>"""


def sec_practice(d: Data, F: dict[str, Any]) -> str:
    ex = F["examples"]
    mom = ex["momentum_clean"]
    sr = ex["sr_flip_clean"]
    sw = ex["sweep_clean"]
    dist_mom = 0.08
    dist_sr = (sr["entry_open"] - sr["level"] * 0.97) / sr["entry_open"]
    stop_sw = sw["sweep_low"] - 0.5 * sw["atr_at_sweep"]
    dist_sw = (sw["entry_open"] - stop_sw) / sw["entry_open"]
    rows = []
    for lab, dist in (
        (f"W2: stop 8 % ispod kupnje ({e(mom['ticker'])}, primjer)", dist_mom),
        (
            f"W5: stop 3 % ispod razine ({e(sr['ticker'])}, primjer; od ulaza {pc(dist_sr)})",
            dist_sr,
        ),
        (
            f"W6: ispod dna sweepa umanjeno za pola ATR-a ({e(sw['ticker'])}, primjer; od ulaza {pc(dist_sw)})",
            dist_sw,
        ),
    ):
        cells = [lab, pc(dist)]
        for acct in (1000, 5000):
            risk = acct * 0.01
            pos = min(risk / dist, acct * 0.25)
            cells.append(f"{eur(pos)} ({pc(pos / acct, 0)} računa)")
        rows.append(cells)
    comm_rows = []
    for order in (125, 250, 625, 1250):
        comm_rows.append(
            [
                eur(order),
                eur(order * 0.00025 * 2, 2),
                eur(1.0 * 2, 2),
                pc(2.0 / order, 2),
            ]
        )
    memo = d.RM["contenders"]
    mw = memo["W1_C13C_ORIG"]["ai_era"]["trades_per_month"]
    sw_trade = F["examples"]["sr_flip_failed"]["trade"]
    sw_trade_t = F["examples"]["sr_flip_failed"]["ticker"]
    expo = [
        d.rule(k)["exposure_pct"]
        for k in ("W1_C13C_ORIG", "W2_MOM_BREAK_20", "W8_IBS_REVERT")
    ]
    EXP_LO, EXP_HI = hr(min(expo), 0), hr(max(expo), 0)
    return f"""<section id="praksa"><h2>Kako bi swing trader ovo koristio u praksi</h2>
<div class="warnbox"><p>Ovo je <b>obrazovni primjer računa</b>, ne preporuka ni savjet. Brojevi 1 % rizika i 25 % ograničenja su ilustracija; svatko ih bira sam.</p></div>
<h3>Kontrolni popis prije svake kupnje (ono što iz mjerenja ima smisla)</h3>
<div class="teach"><ul>
<li><b>Struktura i tjedni smjer.</b> Je li dionica iznad dugoročnog prosjeka i je li tjedni trend uzlazan? To ne daje prednost nad slučajnošću, ali izbjegava kupnju u očitom padu (u padu 2021. do 2022. većina pravila nije radila).</li>
<li><b>Gdje je najbliža razina ispod cijene?</b> Koristi se za stop, ne kao jamstvo odbijanja (placebo test).</li>
<li><b>Je li cijena u zoni ili usred ničega?</b> Što je zona bliže stopu, to je gubitak ako pogriješite manji.</li>
<li><b>Što je okidač?</b> Zatvaranje iznad vrha, povratak u zonu ili promjena smjera: odluka na zatvaranju, nalog za idući dan.</li>
<li><b>Gdje je stop?</b> Odredite ga prije kupnje, ne nakon.</li>
<li><b>Koliko novca?</b> Iznos određuje udaljenost stopa i rizik u eurima, ne osjećaj.</li>
<li><b>Kalendar.</b> Je li izvještaj o dobiti u idućih nekoliko dana? Stop ne štiti od jaza preko noći (vidi niže).</li>
<li><b>Udaljenost stopa od ulaza, ne od razine.</b> Stop W5 je 3 % ispod <i>razine</i>, ali kupnja je često iznad razine. Primjer iz stvarnih podataka: {e(sw_trade_t)} {dmy(F["examples"]["sr_flip_failed"]["signal_date"])}, razina {usd(F["examples"]["sr_flip_failed"]["level"])}, kupnja po {usd(F["examples"]["sr_flip_failed"]["trade"]["raw_entry"])}, stop {usd(F["examples"]["sr_flip_failed"]["level"] * 0.97)}; izlaz po {usd(sw_trade["raw_exit"])} donio je {spc(sw_trade["return"])} na ulog, ne 3 %.</li>
<li><b>Gotovina je pozicija.</b> Pravila ovdje većinom nisu u dionicama (prosječna izloženost za W1, W2 i W8 je od {EXP_LO} % do {EXP_HI} %); čekanje bez signala nije propuštena prilika, nego dio pravila.</li>
</ul></div>
<h3>Gdje staviti stop</h3>
<p><b>Stop</b> je naredba za automatsku prodaju ako cijena padne na određenu razinu. U ovim pravilima stop dolazi iz strukture: 8 % ispod kupnje (W2), 3 % ispod probijene razine (W5), ispod dna sweepa umanjeno za pola prosječnog dnevnog raspona (W6), ispod dna zone (W7). <b>Pažnja:</b> ako dionica otvori ispod stopa (jaz preko noći, npr. nakon loših vijesti), izlazi se po otvaranju, dakle lošije od stopa; simulator to računa, a stvarni jaz može biti još gori.</p>
<h3>Koliko kupiti (primjer na računima od 1.000 € i 5.000 €)</h3>
<p>Pravilo je: iznos pozicije = rizik u eurima podijeljen s udaljenošću stopa. Ako riskirate 1 % računa i stop je 8 % od kupnje: račun od 1.000 € riskira 10 €, pozicija je 10 € / 0,08 = 125 €. Ako cijena padne do stopa, gubite oko 10 €, ne 125 €. Primjer ograničenja: nikad više od 25 % računa u jednoj dionici.</p>
{table(["Stop (primjer iz stvarnih podataka)", "Udaljenost stopa", "Pozicija, račun 1.000 €", "Pozicija, račun 5.000 €"], rows, left=1)}
<h3>Upozorenje o minimalnoj proviziji</h3>
<p>Simulator naplaćuje samo 0,025 % po strani (za 125 € to je 0,03 € po strani). <b>Stvarna provizija IBKR-a</b> ima po nalogu često minimum, a <b>je li i koliko je to za Petrov tarif nije potvrđeno</b>. Ako je minimum, na primjer, 1 € po nalogu (samo primjer), mala pozicija znatno je skuplja:</p>
{table(["Iznos naloga", "Simulirani trošak (kupnja + prodaja)", "Primjer: minimum 1 € po nalogu, kupnja + prodaja", "Taj minimum kao dio pozicije"], comm_rows, left=1)}
<p>Što više malih poslova (W2, W8 i druga pravila s mnogo poslova), to se ovaj učinak više nakuplja, pa su ta pravila u simulaciji <b>povoljnije prikazana nego u stvarnosti</b>. Na računu od 1.000 € s pozicijama od 125 € do 250 € trošak ne bi smio biti zanemaren: prije nego što pravilo izgleda "dobro", provjerite stvarnu provizijsku tablicu i radite li s razlomljenim dionicama (to je za Petrov račun također nepotvrđeno).</p>
<h3>Koliko je realno trgovati često</h3>
<p>Kad bi the researcher pratio samo tri dionice memorije (MU, WDC, STX), pravilo W1 daje oko {hr(mw, 1)} poslova mjesečno, pravilo W2 oko {hr(memo["W2_MOM_BREAK_20"]["ai_era"]["trades_per_month"], 1)}. "30 poslova mjesečno" iz tablice vrijedi za 43 dionice odjednom, a to nije jedan mali račun.</p>
<h3>Dostupnost instrumenata (EU/HR)</h3>
<p>Američke pojedinačne dionice (MU, NVDA, AMAT i druge) općenito su dostupne klijentima iz EU preko Interactive Brokersa. Američki ETF-ovi (GLD, SLV, SMH, SOXX) često nisu (nema KID dokumenta), pa su u ovim testovima samo <b>nepotvrđeni / referentni</b>. Kripto ovisi o državi i propisima (MiCA): nepotvrđeno. Prije bilo kakve primjene provjerite dostupnost u IBKR-u. Računi su u eurima, instrumenti u dolarima: tečaj EUR/USD i trošak konverzije stvarni su, a ovdje su pojednostavljeni. Porezi nisu dio ove analize i ne dajemo savjet o porezu.</p>
</section>"""


def sec_limits(d: Data) -> str:
    return f"""<section id="ogranicenja"><h2>Poštena ograničenja</h2>
<ul>
<li><b>Bik-tržište.</b> AI era je jak uzlazni period, a odabrane dionice su "preživjeli" lanca. To pogoduje svim pravilima jednako (zato su kontrole isti papir i isto razdoblje), ali ne znamo kako bi rezultati izgledali u pravom padu.</li>
<li><b>Višestruko testiranje.</b> U ledgeru je K = {d.k} pokušaja. Najbolja ćelija tablice često je dobra zbog sreće; važniji je obrazac koji drže mnoge skupine. <b>Deflated Sharpe</b> (omjer prinosa i kolebanja uz korekciju za broj pokušaja) najvišeg pravila je {hr(max(d.rule(k)["deflated_sharpe_prob"] for k in RULES), 2)}, daleko ispod 0,95.</li>
<li><b>Jedna definicija pojma.</b> Svaki pojam testiran je u jednoj strogoj verziji na dnevnim svijećama (5 svijeća za okret, 2 ATR za impuls, 0,3 % za jednako dno). Druga definicija može dati drukčiji rezultat, ali bi bila novi pokušaj i povećala bi K.</li>
<li><b>Nije testirano zasebno:</b> jednaka dna i vrhovi, procjep (FVG), premium i diskont, satne svijeće, zone ponude (kratka prodaja je isključena).</li>
<li><b>Nije modelirano:</b> tečaj EUR/USD, minimalna provizija, dividende, porezi, razlomljene dionice na Petrovu računu, proklizavanje i likvidnost tankih papira, loše vijesti preko noći.</li>
<li><b>Critic PASS ne postoji.</b> Ništa na ovoj stranici nije formalni Critic PASS; lista odobrenih ostaje prazna, signal je PRIČEKAJ.</li>
</ul></section>"""


GLOSS = [
    (
        "Swing trgovanje",
        "Držanje pozicije dane do tjedne, ne minute. Primjer: kupite u ponedjeljak, prodate za dva tjedna.",
    ),
    (
        "Svijeća",
        "Jedan dan na grafu: cijena otvaranja, najviša, najniža i zatvaranja. Primjer: otvori 100 €, najviša 104 €, najniža 98 €, zatvori 102 €.",
    ),
    (
        "ATR (prosječni dnevni raspon)",
        "Koliko cijena u prosjeku pređe u jednom danu (najviša minus najniža, prosjek 14 dana). Primjer: ATR 4 € na dionici od 100 € znači da je dnevno kretanje oko 4 %.",
    ),
    (
        "Okret (pivot)",
        "Najviša (najniža) točka viša (niža) od 5 svijeća s obje strane. Poznata tek 5 dana kasnije.",
    ),
    (
        "Momentum (zamah)",
        "Tendencija da ono što raste nastavi rasti neko vrijeme. Primjer: dionica koja je u 20 dana napravila novi vrh.",
    ),
    (
        "Potpora i otpor",
        "Razine na kojima se cijena prije okrenula, gore (otpor) ili dolje (potpora). U našem testu ne odbijaju cijenu češće od lažnih crta.",
    ),
    (
        "Obrnuta uloga (flip)",
        "Probijeni otpor postaje potpora. Primjer: cijena zatvori iznad 70 €, vrati se na 70 € i odbije se gore.",
    ),
    (
        "HH, HL, LH, LL",
        "Viši vrh, više dno, niži vrh, niže dno. Dva uzastopna HH i HL su uzlazna struktura.",
    ),
    (
        "BOS i promjena smjera",
        "BOS: zatvaranje iznad zadnjeg vrha u uzlaznom trendu (nastavak). Promjena smjera: u silaznom trendu zatvaranje iznad zadnjeg nižeg vrha (mogući preokret).",
    ),
    (
        "Likvidnost i sweep",
        "Mjesto s mnogo stop-naloga (ispod očitih dna). Sweep je fitilj ispod dna uz zatvaranje natrag iznad.",
    ),
    (
        "Zona potražnje (order block)",
        "Zadnja silazna svijeća prije snažnog rasta; raspon te svijeće je zona. Svježa je do prvog povratka cijene.",
    ),
    (
        "Procjep (fair value gap)",
        "Praznina između tri svijeće. Opisan u nastavi, ovdje nije testiran.",
    ),
    (
        "Premium i diskont",
        "Gornja i donja polovica zadnjeg raspona od dna do vrha. Dugo se traži samo u diskontu.",
    ),
    ("Odozgo prema dolje", "Prvo tjedni smjer, pa dnevni okidač."),
    (
        "Stop",
        "Automatska prodaja kad cijena padne na određenu razinu. Ako dan otvori ispod stopa, izlaz je po otvaranju.",
    ),
    (
        "Placebo",
        "Kontrolna skupina (lažne crte). Ako daju isti rezultat kao prave, prava stvar nije ništa posebna.",
    ),
    (
        "Interval pouzdanosti i pp",
        "Raspon u kojem bi se razlika vjerojatno našla pri ponavljanju pokusa. pp je postotni bod. Ako interval obuhvaća nulu, nema dokaza razlike.",
    ),
    (
        "Višak (excess)",
        "Prinos nakon događaja minus prosječni prinos istog papira u istom razdoblju. Primjer: papir +2 %, nakon signala +3 %, višak +1 pp, to je 10 € na 1.000 € prije troškova.",
    ),
    (
        "Očekivanje po poslu, faktor dobiti, pogodak",
        "Prosječna zarada po poslu na 1.000 €; zbroj dobitaka podijeljen sa zbrojem gubitaka; udio dobitnih poslova.",
    ),
    (
        "Sleeve",
        "Jedna dionica s vlastitih 1.000 €. Grupa je zbroj takvih računa bez prelijevanja.",
    ),
    (
        "Bazni bod (bps)",
        "Stotinka postotka. 2,5 bps = 0,025 %; na 1.000 € to je 0,25 €.",
    ),
    ("Kupi-i-drži", "Kupiš na početku i držiš. Mjerilo, ne strategija."),
    (
        "Deflated Sharpe i K",
        "Sharpe je omjer prinosa i kolebanja. K je broj isprobanih pravila; što ih je više, veća je šansa da jedno izgleda dobro slučajno, pa se traži veći rezultat.",
    ),
    (
        "Pogled u budućnost (lookahead)",
        "Pogreška kad test koristi podatak koji u tom trenutku nije postojao. Svako pravilo provjereno je na skraćenim podacima.",
    ),
]


def sec_gloss() -> str:
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in GLOSS)
    return f'<section id="pojmovnik"><h2>Pojmovnik s primjerima</h2><dl>{dl}</dl></section>'


def build(F: dict[str, Any], d: Data) -> str:
    body = f"""<main>
{sec_header(d)}
{sec_honest(d)}
{sec_summary(d)}
{sec_how(d)}
{sec_momentum(d, F)}
{sec_levels(d, F)}
{sec_structure(d, F)}
{sec_liquidity(d, F)}
{sec_zones(d, F)}
{sec_discount(d, F)}
{sec_topdown(d, F)}
{sec_rules(d)}
{sec_evidence(d)}
{sec_practice(d, F)}
{sec_limits(d)}
{sec_gloss()}
<footer>Istraživačka simulacija na povijesnim dnevnim podacima (dionice do 5. 10. 2026., AI era od 3. 1. 2023.): odluka na zatvaranju, kupnja na idućem otvaranju, trošak 0,025 % po strani, bez poluge i bez kratke prodaje. Rezultati iz prošlosti ne obećavaju buduće. Ovo nije savjet za ulaganje, nije signal, nije formalni Critic PASS, nema savjeta o porezu i nijedan nalog (ni probni ni pravi) nije poslan.</footer>
</main>"""
    head = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + top10.HEAD.format(
            title="Momentum, potpora i otpor, mehanika tržišta",
            css=top10.CSS + EXTRA_CSS,
        )
    )
    return (
        '<!doctype html>\n<html lang="hr"><head>\n'
        + head
        + "</head><body>\n"
        + body
        + "\n</body></html>"
    )


# ---------------------------------------------------------------- verification


def raw_bar(t: str, day: str) -> dict[str, float]:
    with (ROOT / "data" / "ohlcv" / f"{t}_1d.csv").open() as f:
        for row in csv.DictReader(f):
            if row["date"][:10] == day:
                return {k: float(row[k]) for k in ("open", "high", "low", "close")}
    raise KeyError(f"{t} {day}")


def verify(F: dict[str, Any], d: Data) -> list[str]:
    """Check examples against raw CSV rows and key page numbers against the raw JSON files."""
    page = PAGE.read_text()
    bad: list[str] = []

    def need(s: str, ctx: str) -> None:
        if s not in page:
            bad.append(f"{ctx}: expected '{s}'")

    for key, f in F["examples"].items():
        tk = f["ticker"]
        if tk in ("NVDA",) or tk in d.S["data_handling"]["bad_tick_repairs"]:
            pass
        o = raw_bar(tk, f["entry_date"])["open"]
        c10 = raw_bar(tk, f["exit_date"])["close"]
        c0 = raw_bar(tk, f["signal_date"])["close"]
        if (
            abs(o - f["entry_open"]) > 1e-6
            or abs(c10 - f["exit_close"]) > 1e-6
            or abs(c0 - f["signal_close"]) > 1e-6
        ):
            bad.append(
                f"{key}: CSV mismatch open {o} vs {f['entry_open']}, close10 {c10} vs {f['exit_close']}"
            )
        r10 = c10 / o - 1
        if abs(r10 - f["r10"]) > 1e-9:
            bad.append(f"{key}: r10 {r10} vs {f['r10']}")
        if not (r10 >= 0.05 or r10 <= -0.05):
            bad.append(f"{key}: outcome inside the +-5 % band")
        need(usd(f["entry_open"]), f"{key} entry")
        need(usd(f["exit_close"]), f"{key} exit")
        need(dmy(f["signal_date"]), f"{key} date")
    # rule table from the group result file (an independent copy of summary.json numbers)
    for k in RULES:
        a = d.RS["contenders"][k]["ai_era"]
        s = d.rule(k)
        for field in ("trades", "expectancy_eur", "profit_factor", "trades_per_month"):
            if abs(a[field] - s[field]) > 1e-9:
                bad.append(f"{k}.{field}: results {a[field]} vs summary {s[field]}")
        need(hr(a["trades"]), f"{k} trades")
        need(seur(a["expectancy_eur"]), f"{k} expectancy")
    # placebo numbers
    sr = d.PL["sr"]["all"]
    need(pc(sr["real"]["bounce_rate"]), "placebo real bounce")
    need(pc(sr["rand"]["bounce_rate"]), "placebo rand bounce")
    need(hr(sr["n_levels"]), "placebo n levels")
    for name in ("E1_sweep_shift_discount", "E4_demand_zone_retest", "E5_bos_trend"):
        n = d.PL["mechanics_ai_era"]["events"][name]["n"]
        need(hr(n), f"{name} n")
    # buy and hold
    need(pc(d.bh()["total_return"], 0), "buy and hold")
    if "$" in re.sub(r"data:image[^\"]+", "", page):
        bad.append("literal dollar sign in page text (use USD)")
    # headline cross-check against the page headlines listed in the task: all group winners
    for gk, g in d.S["groups"].items():
        if g["ranking"]:
            top = g["ranking"][0]
            ref = d.RM if gk == "memory" else jl(SWING / "results" / f"{gk}.json")
            r = ref["contenders"][top["contender"]]["ai_era"]
            if abs(r["trades"] - top["trades"]) > 0:
                bad.append(
                    f"group {gk}: ranking trades {top['trades']} vs results {r['trades']}"
                )
    return bad


def main() -> None:
    d = Data()
    F = build_facts(d)
    FACTS.write_text(json.dumps(F, ensure_ascii=False, indent=2, default=str))
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(build(F, d))
    print(f"page {PAGE} ({PAGE.stat().st_size / 1e6:.1f} MB)")
    if "--verify" in sys.argv:
        bad = verify(F, d)
        if bad:
            print("VERIFY FAILED")
            for b in bad:
                print(" -", b)
            raise SystemExit(1)
        print("VERIFY OK")


if __name__ == "__main__":
    main()
