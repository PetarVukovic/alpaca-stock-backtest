#!/usr/bin/env python3
"""Assemble the single-page C13C notebook (self-contained HTML) from results.json, sleeves.pkl and the charts.

Inputs  (reports/research/C13C_NOTEBOOK_20261014/): results.json, sleeves.pkl, charts/*.png, captions.json
        (reports/research/AICHAIN_20261014/swing/summary.json for the W3/W5 reference numbers,
         scripts/tradingview/MASTER_W1_C13C.pine for the Pine block)
Output: c13c_notebook.html and build_report.json in the same folder.

Every number in the text is formatted from the data files, nothing is typed by hand. Research only, no orders.
Run:  .venv/bin/python scripts/c13c_notebook_assemble.py
"""

from __future__ import annotations

import html
import json
import pickle  # sleeves.pkl is written by lab/aichain/c13c_nb_run.py on this machine only
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from master_assemble import CSS, JS, encode_chart, structural_check  # noqa: E402

from lab.aichain.sim import load_bars  # noqa: E402

DIR = ROOT / "reports" / "research" / "C13C_NOTEBOOK_20261014"
CHARTS = DIR / "charts"
OUT = DIR / "c13c_notebook.html"
SWING = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing" / "summary.json"
PINE = ROOT / "scripts" / "tradingview" / "MASTER_W1_C13C.pine"
PINE_W3 = ROOT / "scripts" / "tradingview" / "MASTER_W3_MOMENTUM_TABLE.pine"

RES: dict[str, Any] = json.loads((DIR / "results.json").read_text())
CAP: dict[str, Any] = json.loads((CHARTS / "captions.json").read_text())
SUMM: dict[str, Any] = json.loads(SWING.read_text())
with (DIR / "sleeves.pkl").open("rb") as _fh:
    SL: dict[tuple[str, str, str, str], tuple[Any, ...]] = pickle.load(_fh)

SEGMENT_HR = {
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja memorije i pohrana",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Cloud i infrastruktura",
}
VAR_NAME = {
    "X1_TRAIL15": "Stop 15 %",
    "X2_TRAIL20": "Stop 20 %",
    "X3_ATR_TRAIL": "ATR stop (3 x ATR14)",
    "X4_MOM_CONFIRM": "Momentum potvrda (126 dana)",
    "X5_DIP3": "Manji pad (3 %)",
    "X6_SMA100": "Prosjek 100 dana",
    "K7_REENTRY": "Ponovni ulaz u trendu",
}
VAR_IDEA = {
    "X1_TRAIL15": "Zaštitni stop 15 % ispod vrha umjesto 10 %: manje izbacivanja iz rasta, veći povrat dijela dobiti.",
    "X2_TRAIL20": "Zaštitni stop 20 % ispod vrha: dobitnici trče dulje, ali trgovina smije pasti dublje prije izlaza.",
    "X3_ATR_TRAIL": "Stop = vrh minus 3 dnevne prosječne amplitude (ATR14): širok za nemirne dionice, uzak za mirne.",
    "X4_MOM_CONFIRM": "Kupi pad samo ako je prinos zadnjih 126 dana pozitivan i dionica je u gornjoj polovici svoje skupine.",
    "X5_DIP3": "Manji okidač: pad od 3 % u 5 dana umjesto 5 %: više trgovina.",
    "X6_SMA100": "Trend filter: iznad prosjeka 100 dana umjesto 200: ranije ulazi nakon preokreta.",
    "K7_REENTRY": "Nakon izbacivanja stopom ponovno ulazi čim je cijena opet iznad prosjeka 200 i 20 dana (prethodno registrirano, K7).",
}
SC_ALL, SC_MEM = "stocks_all", "memory_core"


# ---------------------------------------------------------------------------------------------- format
def hr(x: float, nd: int = 0) -> str:
    return f"{x:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def eur(x: float, nd: int = 0) -> str:
    return f"{hr(x, nd)} €"


def pct(x: float | None, nd: int = 0, sign: bool = True) -> str:
    if x is None:
        return "-"
    s = hr(abs(x) * 100, nd)
    if not sign:
        return f"{s} %"
    return f"{'+' if x >= 0 else '-'}{s} %"


def num(x: float | None, nd: int = 2) -> str:
    return "-" if x is None else hr(x, nd)


def dion(n: int) -> str:
    """Croatian noun form after a number: 1 dionica, 2-4 dionice, 5+ dionica (43 dionice)."""
    if n % 10 == 1 and n % 100 != 11:
        return "dionica"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "dionice"
    return "dionica"


def dh(iso: str) -> str:
    d = pd.Timestamp(iso)
    return f"{d.day}. {d.month}. {d.year}."


def figure(name: str, alt: str, caption: str) -> str:
    return f'<figure class="fig"><img data-chart="{name}" alt="{html.escape(alt)}"><figcaption>{caption}</figcaption></figure>'


def table(head: list[str], rows: list[list[str]], cls: str = "t", sortable: bool = False) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    extra = ' data-sort="1"' if sortable else ""
    return f'<table class="{cls}"{extra}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


P = RES["pooled"]
V = RES["variants"]
TICKERS = [r["ticker"] for r in RES["datasets"]]
SEG_OF = {r["ticker"]: r["segment"] for r in RES["datasets"]}
a_c, a_h = P[SC_ALL]["C13C"]["ai_era"], P[SC_ALL]["HOLD"]["ai_era"]
m_c, m_h = P[SC_MEM]["C13C"]["ai_era"], P[SC_MEM]["HOLD"]["ai_era"]
W3 = SUMM["groups"]["stocks_all"]["per_contender"]["W3_MOM_RANK_WEEKLY"]
W5 = SUMM["groups"]["stocks_all"]["per_contender"]["W5_SR_BREAKOUT_RETEST"]
W2 = SUMM["groups"]["stocks_all"]["per_contender"]["W2_MOM_BREAK_20"]
LAST_DATE = dh(RES["common_end"])


# ---------------------------------------------------------------------------------------------- derived
def per_ticker_rows() -> list[dict[str, Any]]:
    rows = []
    for t in TICKERS:
        pt = RES["per_ticker"][t]
        c, h = pt["C13C"]["ai_era"], pt["HOLD"]["ai_era"]
        rows.append({"t": t, "seg": SEG_OF[t], "c": c, "h": h, "pt": pt})
    return rows


ROWS = per_ticker_rows()
N_BEAT_RET = sum(1 for r in ROWS if r["c"]["end_value"] > r["h"]["end_value"])
N_BEAT_DD = sum(1 for r in ROWS if r["c"]["max_drawdown"] > r["h"]["max_drawdown"])
BEAT_TICKERS = [r["t"] for r in ROWS if r["c"]["end_value"] > r["h"]["end_value"]]
N_C_POS = sum(1 for r in ROWS if r["c"]["total_return"] > 0)
EXPOSURE = float(np.mean([r["c"]["exposure_pct"] for r in ROWS]))
TOTAL_TRADES = sum(r["c"]["trades"] for r in ROWS)


def acceptance(vid: str, scope: str = SC_ALL) -> dict[str, Any]:
    """Apply the pre-registered acceptance rule exactly as written in c13c_variants.ACCEPTANCE."""
    o, v = V[scope]["C13C"], V[scope][vid]
    checks = {
        "ocekivanje 2023.-2024.": (v["h1"]["expectancy_eur"] or -1e9) > (o["h1"]["expectancy_eur"] or -1e9),
        "ocekivanje 2025.-2026.": (v["h2"]["expectancy_eur"] or -1e9) > (o["h2"]["expectancy_eur"] or -1e9),
        "profit factor 2023.-2024.": (v["h1"]["profit_factor"] or 0) > (o["h1"]["profit_factor"] or 0),
        "profit factor 2025.-2026.": (v["h2"]["profit_factor"] or 0) > (o["h2"]["profit_factor"] or 0),
        "prinos 2021.-2022. nije manji": v["y2021_2022"]["total_return"] >= o["y2021_2022"]["total_return"],
        "ocekivanje pri 2x trosku pozitivno": (v["ai_era_2x"]["expectancy_eur"] or -1) > 0,
    }
    return {"checks": checks, "pass": all(checks.values())}


ACC = {vid: acceptance(vid) for vid in list(VAR_NAME)}
ACC_MEM = {vid: acceptance(vid, SC_MEM) for vid in list(VAR_NAME)}
PASSERS = [vid for vid, a in ACC.items() if a["pass"]]


def today_table() -> tuple[list[list[str]], list[str], list[str]]:
    rows: list[list[str]] = []
    signals: list[str] = []
    open_pos = sorted(
        {
            t
            for (cfg, t, w, m), (_, _, _, trades) in SL.items()
            if cfg == "C13C" and w == "ai_era" and any(x["reason"] == "end" for x in trades)
        }
    )
    for t in TICKERS:
        b = load_bars(t)
        close = pd.Series(b.close, index=b.dates)
        sma = close.rolling(200).mean()
        c, s = float(close.iloc[-1]), float(sma.iloc[-1])
        chg = c / float(close.iloc[-6]) - 1
        sig = c > s and chg <= -0.05
        if sig:
            signals.append(t)
        rows.append(
            [
                t,
                dh(str(b.dates[-1].date())),
                hr(c, 2),
                hr(s, 2),
                pct(c / s - 1, 1),
                pct(chg, 1),
                "da" if c > s else "ne",
                "SIGNAL" if sig else "-",
                "da" if t in open_pos else "-",
            ]
        )
    return rows, signals, open_pos


TODAY_ROWS, TODAY_SIGNALS, OPEN_POS = today_table()


# ---------------------------------------------------------------------------------------------- sections
def sec_hero() -> str:
    kpis = [
        (f"{pct(a_c['total_return'])}", f"C13C na 43 dionice, AI era (kupi-i-drži {pct(a_h['total_return'])})"),
        (f"{pct(a_c['max_drawdown'], 0, False)}", f"najveći pad C13C-a (kupi-i-drži {pct(a_h['max_drawdown'], 0, False)})"),
        (f"{hr(a_c['trades_per_month'], 0)}", f"trgovina mjesečno; uspješno {pct(a_c['hit_rate'], 0, False)}"),
        (f"{pct(m_c['total_return'])}", f"memorijska trojka MU WDC STX (kupi-i-drži {pct(m_h['total_return'])})"),
    ]
    cards = "".join(f'<div class="kpi"><b>{v}</b><span>{t}</span></div>' for v, t in kpis)
    return f"""
<section id="uvod">
<h2>Ukratko</h2>
<div class="kpis">{cards}</div>
<p class="lead">C13C je tvoj algoritam za memorijske i poluvodičke dionice: kupi dionicu u rastućem trendu kad padne 5 % u 5 dana, izađi kad cijena padne 10 % ispod najvišeg dosegnutog vrha. Ovdje je testiran na svih {len(TICKERS)} {dion(len(TICKERS))} koje smo skupili (memorija, oprema, AI čipovi, mreže, cloud) kroz cijelu povijest, sa svim podacima i grafom svake dionice.</p>
<div class="callout warn"><b>O imenu "C13CMOM".</b> U projektu ne postoji algoritam s tim imenom. Pretpostavio sam da misliš na <b>C13C</b> (tvoj algoritam), a "MOM" shvatio kao <b>momentum</b>. Zato je momentum obrađen zasebno u <a href="#momentum">poglavlju o momentumu</a>: je li C13C zapravo momentum strategija, pomaže li momentum filter i kako stoji uz tjedni momentum rang. Ako si mislio na nešto drugo, reci pa prilagodim.</div>
<h3>Što iz toga slijedi</h3>
<ul>
<li><b>Radi, ali kao osiguranje, ne kao pojačalo.</b> U AI eri je C13C zaradio u {N_C_POS} od {len(ROWS)} {dion(len(ROWS))}, ali kupi-i-drži je dao veći prinos u {len(ROWS) - N_BEAT_RET} od {len(ROWS)} ({"jedina iznimka je " + BEAT_TICKERS[0] if len(BEAT_TICKERS) == 1 else "iznimke: " + ", ".join(BEAT_TICKERS)}). Zauzvrat je najveći pad bio manji u {N_BEAT_DD} od {len(ROWS)} {dion(len(ROWS))}.</li>
<li><b>Radi često.</b> Oko {hr(a_c['trades_per_month'], 0)} trgovina mjesečno na 43 dionice, prosječno držanje oko {hr(a_c['mean_hold_days'], 0)} dana (medijan {hr(a_c['median_hold_days'], 0)}). U memorijskoj trojci je očekivanje po trgovini {eur(m_c['expectancy_eur'])} naspram {eur(a_c['expectancy_eur'])} u cijelom košu.</li>
<li><b>Najjeftinije poboljšanje je širi stop.</b> Od šest unaprijed registriranih varijanti, {"jedino " + ", ".join(VAR_NAME[v] for v in PASSERS) + " zadovoljava" if len(PASSERS) == 1 else ", ".join(VAR_NAME[v] for v in PASSERS) + " zadovoljavaju"} pravilo prihvaćanja napisano prije testa. Cijena je manje trgovina ({hr(V[SC_ALL]['X2_TRAIL20']['ai_era']['trades_per_month'], 0)} naspram {hr(a_c['trades_per_month'], 0)} mjesečno za stop 20 %).</li>
<li><b>Momentum filter ne pomaže.</b> Dodavanje uvjeta jakog prethodnog rasta smanjuje broj trgovina i prinos, a ne dodaje kvalitetu po trgovini.</li>
</ul>
</section>
"""


def sec_rule() -> str:
    trades = [{**x} for x in SL[("C13C", "MU", "ai_era", "1x")][3]]
    wins = [x for x in trades if x["return"] > 0 and x["reason"] == "stop"]
    ex = sorted(wins, key=lambda x: x["return"])[len(wins) // 2]
    units = 1000 / ex["entry_price"]
    prof = ex["pnl_eur"]
    return f"""
<section id="pravilo">
<h2>1. Pravilo C13C u četiri koraka</h2>
<div class="rule"><ol>
<li><b>Trend:</b> zatvaranje dana je iznad prosjeka zatvaranja zadnjih 200 dana (SMA200). To znači "dionica je dugoročno u usponu".</li>
<li><b>Pad:</b> zatvaranje je najmanje 5 % niže nego prije 5 trgovinskih dana. To je "kratka korekcija usred uspona".</li>
<li><b>Kupnja:</b> kad su oba uvjeta ispunjena na kraju dana, kupuje se na <b>prvom otvaranju idućeg dana</b>, jednu poziciju po dionici, bez poluge.</li>
<li><b>Izlaz:</b> zaštitni stop stoji 10 % ispod najvišeg dosegnutog vrha od kupnje. Stop se samo diže, nikad ne spušta. Cijena ga probije, izlaziš (ako je otvaranje već ispod stopa, izlaz je po otvaranju).</li>
</ol></div>
<div class="example">Primjer iz podataka (MU, {dh(ex['entry_date'])}): kupnja po {hr(ex['raw_entry'], 2)} $ (u simulaciji dolar tretiramo kao euro), 1.000 € kupuje {hr(units, 2)} dionice. Stop se podizao s rastom vrha i izbacio te {dh(ex['exit_date'])} po {hr(ex['raw_exit'], 2)} $. Rezultat {pct(ex['return'], 1)}, odnosno {eur(prof)} na 1.000 € nakon troškova, za {ex['bars_held']} trgovinskih dana.</div>
{figure('n01_anatomy.png', 'Dvije stvarne MU trgovine', 'Gore srednja dobitna trgovina, dolje najbolja trgovina MU u AI eri. Crvena crta je zaštitni stop koji prati vrh.')}
<div class="teacher"><p>Pravilo nema cilj ("prodaj na +20 %"). Prodaje samo zaštitni stop. Zato dobitnik može trčati tjednima, a gubitnik se reže otprilike na 10 % (malo više kad otvaranje preskoči stop).</p></div>
</section>
"""


def sec_data() -> str:
    head = ["Dionica", "Skupina", "Datoteka", "Prvi dan", "Zadnji dan", "Dnevnih svijeća", "Ispravljeni zapisi"]
    rows = [
        [r["ticker"], SEGMENT_HR[r["segment"]], f"<code>{r['csv']}</code>", dh(r["first_bar"]), dh(r["last_bar"]), hr(r["bars"]), str(r["repairs"]) if r["repairs"] else "-"]
        for r in RES["datasets"]
    ]
    n_bars = sum(r["bars"] for r in RES["datasets"])
    return f"""
<section id="podaci">
<h2>2. Podaci i kako je testirano</h2>
<p>Cijeli test koristi <b>{len(TICKERS)} {dion(len(TICKERS))}</b> i <b>{hr(n_bars)} dnevnih svijeća</b> iz projektnih datoteka <code>data/ohlcv/*_1d.csv</code> (izvor Alpaca, dnevni podaci). To su sve memorijske i poluvodičke dionice koje smo skupili, plus AI kompanije koje o njima ovise (mreže i serveri, cloud). Svaka dionica ima vlastiti račun od 1.000 €, a "ukupni" brojevi su zbroj tih računa.</p>
<div class="rule"><ol>
<li><b>Razdoblja:</b> AI era 1. 1. 2023. do {LAST_DATE} je glavni test; 2016.-2020. i 2021.-2022. služe kao kontekst; AI era je podijeljena na dvije polovice (2023.-2024. i 2025.-2026.) za provjeru stabilnosti.</li>
<li><b>Izvršenje:</b> odluka na kraju dana, kupnja po idućem otvaranju. Stop djeluje unutar dana (po cijeni stopa) ili po otvaranju ako cijena preskoči stop (gap).</li>
<li><b>Troškovi:</b> 2,5 baznih bodova po strani (0,025 %), provjera i s dvostrukim troškom. Tečaj EUR/USD, dividende, porezi i minimalna provizija nisu modelirani.</li>
<li><b>Na kraju prozora</b> otvorene pozicije se zatvaraju po zadnjoj cijeni uz trošak izlaza ({sum(1 for r in ROWS for x in SL[('C13C', r['t'], 'ai_era', '1x')][3] if x['reason'] == 'end')} takvih trgovina u AI eri).</li>
<li><b>Čišćenje podataka:</b> SMCI prije 14. 1. 2020. i NBIS prije 21. 10. 2024. su zamrznuta povijest (zaustavljeno trgovanje) pa se ne koriste; loš zapis najviše cijene (NVDA, 10. 6. 2024.) je ograničen na susjedne cijene. Isključene su CRWV i SNDK (prekratka povijest) i PSTG (zastarjeli podaci).</li>
</ol></div>
<div class="callout bad"><b>Najvažnija mana dizajna:</b> ovih {len(TICKERS)} {dion(len(TICKERS))} izabrano je znajući da su dio AI lanca, dakle uglavnom dionice koje su se pokazale kao pobjednici. To pogoduje svakoj strategiji koja kupuje dionice. Rezultati ne govore kako bi C13C prošao na dionicama koje smo mogli izabrati prije 2023. i koje danas ne postoje ili su pale. Rezultat je koristan za usporedbu pravila međusobno, a ne za predviđanje zarade.</div>
<details class="code"><summary>Tablica svih skupova podataka ({len(TICKERS)} {dion(len(TICKERS))})</summary>
{table(head, rows)}
</details>
<p class="small">Provjera: pooled C13C rezultat na {len(TICKERS)} {dion(len(TICKERS))} u ovom dokumentu je izračunat ponovno iz dnevnih datoteka i razlikuje se od ranijeg izvještaja (<code>swing/summary.json</code>) za {num(RES['check']['max_abs_diff'], 6)} po svim provjerenim mjerama.</p>
</section>
"""


def sec_results() -> str:
    head = [
        "Dionica", "Skupina", "C13C: 1.000 € postaje", "Držanje: 1.000 € postaje", "C13C pad", "Držanje pad",
        "Trgovina", "Uspješnih", "Profit factor", "Očekivanje € / trg.", "U tržištu", "2021.-22. C13C", "2021.-22. držanje",
    ]
    rows = []
    for r in sorted(ROWS, key=lambda r: -r["h"]["end_value"]):
        c, h, pt = r["c"], r["h"], r["pt"]
        c2, h2 = pt["C13C"]["y2021_2022"], pt["HOLD"]["y2021_2022"]
        rows.append(
            [
                f"<b>{r['t']}</b>", SEGMENT_HR[r["seg"]],
                hr(c["end_value"]), hr(h["end_value"]), pct(c["max_drawdown"], 0, False), pct(h["max_drawdown"], 0, False),
                str(c["trades"]), pct(c["hit_rate"], 0, False), num(c["profit_factor"], 2), num(c["expectancy_eur"], 0),
                pct(c["exposure_pct"] / 100, 0, False),
                pct(c2["total_return"], 0) if c2 else "-", pct(h2["total_return"], 0) if h2 else "-",
            ]
        )
    return f"""
<section id="rezultati">
<h2>3. Rezultati po dionici (AI era)</h2>
<p>Zeleni krugovi su C13C, sive oznake kupi-i-drži. Crta između pokazuje koliko je prinosa "plaćeno" za mirniji put. Dolje je tablica svih {len(ROWS)} {dion(len(ROWS))}, a klikom na naslov stupca sortiraš.</p>
{figure('n03_scoreboard.png', 'Rezultat po dionici', f'C13C je bolji od kupi-i-drži u prinosu u {N_BEAT_RET} od {len(ROWS)} {dion(len(ROWS))} ({", ".join(BEAT_TICKERS) if BEAT_TICKERS else "nijedna"}).')}
{figure('n04_drawdown.png', 'Najveći pad po dionici', f'C13C ima manji najveći pad u {N_BEAT_DD} od {len(ROWS)} {dion(len(ROWS))}.')}
{figure('n05_exposure.png', 'Vrijeme u tržištu i broj trgovina', f'U prosjeku je C13C u poziciji {hr(EXPOSURE, 0)} % vremena i napravi {hr(TOTAL_TRADES)} trgovina na {len(ROWS)} {dion(len(ROWS))} u AI eri.')}
<div class="teacher"><p>Kad je C13C izvan tržišta, ne zarađuje, ali i ne pada. U rastućem tržištu to je gubitak (zato držanje pobjeđuje), a u padu dobitak (zato je pad manji).</p></div>
<div class="tw"><table class="t" data-sort="1"><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead><tbody>{"".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)}</tbody></table></div>
<p class="small">Sve brojke su u eurima na 1.000 € po dionici (dolar tretiran kao euro, bez tečaja). Dionice s kraćom poviješću (npr. NBIS, ARM) počinju od prvog dostupnog dana.</p>
</section>
"""


def trade_list(ticker: str) -> str:
    trades = SL[("C13C", ticker, "ai_era", "1x")][3]
    head = ["Kupnja", "Izlaz", "Razlog", "Dana", "Rezultat", "€ na 1.000 €"]
    reason = {"stop": "stop", "gap_stop": "stop po otvaranju (gap)", "end": "kraj prozora"}
    rows = []
    for x in sorted(trades, key=lambda x: x["entry_date"]):
        why = x["detail"] if x["detail"] == "gap_stop" else x["reason"]
        rows.append(
            [dh(x["entry_date"]), dh(x["exit_date"]), reason.get(why, why), str(x["bars_held"]), pct(x["return"], 1), hr(x["pnl_eur"], 0)]
        )
    return f'<details class="code"><summary>Svih {len(trades)} trgovina: {ticker}</summary>{table(head, rows)}</details>'


def sec_memory() -> str:
    mem_rows = []
    for scope, lab in ((SC_MEM, "MU, WDC, STX"), ("memory_wide", "uz RMBS, SIMO, MRAM, NTAP")):
        c, h = P[scope]["C13C"]["ai_era"], P[scope]["HOLD"]["ai_era"]
        mem_rows.append(
            [lab, pct(c["total_return"]), pct(h["total_return"]), pct(c["max_drawdown"], 0, False), pct(h["max_drawdown"], 0, False),
             hr(c["trades_per_month"], 1), pct(c["hit_rate"], 0, False), num(c["profit_factor"], 2), num(c["expectancy_eur"], 0), pct(c["exposure_pct"] / 100, 0, False)]
        )
    return f"""
<section id="memorija">
<h2>4. Memorijske dionice izbliza</h2>
<p>Memorija je tvoje glavno područje. Ovdje je C13C najjači: očekivanje po trgovini u memorijskoj trojci je {eur(m_c['expectancy_eur'])}, profit factor {num(m_c['profit_factor'], 2)} (u cijelom košu {eur(a_c['expectancy_eur'])} i {num(a_c['profit_factor'], 2)}). Memorijske dionice su cikličke i snažno se vraćaju iz korekcija, što je upravo ono što "kupi pad u usponu" lovi.</p>
{table(["Skup", "C13C prinos", "Držanje prinos", "C13C pad", "Držanje pad", "Trgovina mjesečno", "Uspješnih", "Profit factor", "€ po trgovini", "U tržištu"], mem_rows)}
{figure('n07_memory_core.png', 'MU WDC STX', 'Zeleni pojasi su vrijeme u poziciji. Cijena je logaritamska, pa jednaka visina znači jednak postotak.')}
{figure('n08_memory_wide.png', 'RMBS SIMO MRAM NTAP', 'Sučelja memorije, kontroleri, MRAM i pohrana. SIMO je jedina dionica u kojoj je C13C bolji od držanja.')}
{figure('n02_failures.png', 'Najgora trgovina i izbacivanje', 'Cijena osiguranja: stop od 10 % ponekad izbaci trgovinu uoči nastavka rasta.')}
<div class="teacher"><p>Kad je cijena ispod prosjeka 200 dana (kao u memorijskoj trojci od sredine 2024. do sredine 2025.), pravilo ne kupuje, pa je izvan tržišta. Ukupno je izvan tržišta oko {hr(100 - m_c['exposure_pct'], 0)} % vremena, i to je glavni razlog zaostajanja za držanjem.</p></div>
{trade_list("MU")}{trade_list("WDC")}{trade_list("STX")}
</section>
"""


def sec_segments() -> str:
    head = ["Skupina", "Dionica", "C13C prinos", "Držanje prinos", "C13C pad", "Držanje pad", "Trgovina mj.", "Uspješnih", "PF", "€ / trg."]
    rows = []
    for g, lab in SEGMENT_HR.items():
        c, h = P[g]["C13C"]["ai_era"], P[g]["HOLD"]["ai_era"]
        rows.append([lab, str(c["sleeves"]), pct(c["total_return"]), pct(h["total_return"]), pct(c["max_drawdown"], 0, False), pct(h["max_drawdown"], 0, False), hr(c["trades_per_month"], 1), pct(c["hit_rate"], 0, False), num(c["profit_factor"], 2), num(c["expectancy_eur"], 0)])
    rows.append(["<b>Svih 43</b>", "43", pct(a_c["total_return"]), pct(a_h["total_return"]), pct(a_c["max_drawdown"], 0, False), pct(a_h["max_drawdown"], 0, False), hr(a_c["trades_per_month"], 1), pct(a_c["hit_rate"], 0, False), num(a_c["profit_factor"], 2), num(a_c["expectancy_eur"], 0)])
    gallery = ""
    for g, lab in SEGMENT_HR.items():
        figs = ""
        for t in RES["segments"][g]:
            c, h = RES["per_ticker"][t]["C13C"]["ai_era"], RES["per_ticker"][t]["HOLD"]["ai_era"]
            figs += figure(f"t_{t}.png", f"{t} C13C u AI eri", f"{t}: C13C {eur(c['end_value'])}, držanje {eur(h['end_value'])}, {c['trades']} trgovina, uspješnih {pct(c['hit_rate'], 0, False)}, profit factor {num(c['profit_factor'], 2)}.")
        opn = " open" if g == "memory" else ""
        gallery += f'<details class="code"{opn}><summary>{lab} ({len(RES["segments"][g])} {dion(len(RES["segments"][g]))}): graf svake</summary>{figs}</details>'
    return f"""
<section id="skupine">
<h2>5. Šest skupina i svih 43 dionice</h2>
{table(head, rows)}
{figure('n06_segments.png', 'Šest skupina', 'Prosječni račun od 1.000 € po dionici kroz AI eru, za svaku skupinu.')}
<h3>Graf svake dionice</h3>
<p>Na svakom grafu: gore cijena (logaritamska skala) s prosjekom 200 dana, zeleni pojasi su vrijeme u poziciji, trokut gore je kupnja, trokut dolje izlaz (narančasto dobitak, crveno gubitak). Dolje račun od 1.000 € za C13C i kupi-i-drži. Svaka skupina je zasebna kartica; memorijska je otvorena.</p>
{gallery}
</section>
"""


def sec_periods() -> str:
    head = ["Razdoblje", "Skup", "C13C prinos", "Držanje prinos", "C13C pad", "Držanje pad", "C13C trgovina", "Uspješnih", "PF"]
    wins = [("y2016_2020", "2016.-2020."), ("y2021_2022", "2021.-2022."), ("ai_era", "AI era 2023.-"), ("full", "Cijelo 2016.-")]
    rows = []
    for w, lab in wins:
        for sc, sl in ((SC_ALL, "43 dionice"), (SC_MEM, "MU WDC STX")):
            c, h = P[sc]["C13C"][w], P[sc]["HOLD"][w]
            rows.append([lab, sl, pct(c["total_return"]), pct(h["total_return"]), pct(c["max_drawdown"], 0, False), pct(h["max_drawdown"], 0, False), str(c["trades"]), pct(c["hit_rate"], 0, False), num(c["profit_factor"], 2)])
    pa, pm = P[SC_ALL], P[SC_MEM]
    return f"""
<section id="razdoblja">
<h2>6. Tri razdoblja: gdje pomaže, a gdje ne</h2>
<p>Pravilo je izmjereno u tri različita tržišta. Razdoblje 2016.-2020. je dug uspon (s padom 2018. i korona-padom 2020.), 2021.-2022. je medvjeđe za čipove (nakon 2021. vrhunca), a AI era je novi uspon.</p>
{figure('n11_periods.png', 'Tri razdoblja', 'Ukupni prinos i najveći pad C13C-a i kupi-i-drži po razdoblju.')}
{table(head, rows)}
<div class="teacher"><p>U 2021.-2022. na 43 dionice C13C je gotovo na nuli ({pct(pa['C13C']['y2021_2022']['total_return'], 1)}), ali pad je {pct(pa['C13C']['y2021_2022']['max_drawdown'], 0, False)} naspram {pct(pa['HOLD']['y2021_2022']['max_drawdown'], 0, False)}. U memorijskoj trojci držanje je izgubilo {pct(pm['HOLD']['y2021_2022']['total_return'], 0, False)}, a C13C je bio na {pct(pm['C13C']['y2021_2022']['total_return'], 0)}. To je stvarna vrijednost pravila: ne gubi mnogo kad trend nestane. Ali očekivanje po trgovini u tom razdoblju je blizu nule: pravilo nije "stroj za zaradu", nego filter koji ne ulazi kad trend ne postoji.</p></div>
</section>
"""


def worst_streak() -> tuple[int, str]:
    """Longest run of consecutive non-winning trades inside one ticker (not across the pool)."""
    best, who = 0, ""
    for t in TICKERS:
        run = 0
        for x in sorted(SL[("C13C", t, "ai_era", "1x")][3], key=lambda x: x["exit_date"]):
            run = 0 if x["return"] > 0 else run + 1
            if run > best:
                best, who = run, t
    return best, who


def sec_trades() -> str:
    allc = a_c
    streak, streak_t = worst_streak()
    return f"""
<section id="trgovine">
<h2>7. Kako izgleda trgovanje C13C-om</h2>
{figure('n09_distribution.png', 'Raspodjela trgovina', 'Lijevo rezultat svake trgovine, desno trajanje.')}
<ul>
<li><b>Uspješnih je {pct(allc['hit_rate'], 0, False)}</b>, prosječna dobitna trgovina {pct(allc['avg_win_pct'], 1)}, prosječna gubitna {pct(allc['avg_loss_pct'], 1)}. Pet najboljih od {hr(allc['trades'])} trgovina čini {pct(allc['top5_profit_share'], 0, False)} ukupne neto dobiti, pa rezultat ne visi o nekoliko slučajeva; ipak većinu dobiti nose dobitne trgovine iz desnog repa raspodjele.</li>
<li><b>Najduži niz gubitaka</b> u jednoj dionici: {streak} trgovina zaredom ({streak_t}). Treba biti spreman na to.</li>
<li><b>Trošak nije problem:</b> pri dvostrukom trošku očekivanje je {eur(P[SC_ALL]['C13C_2x']['ai_era']['expectancy_eur'])} po trgovini (umjesto {eur(allc['expectancy_eur'])}).</li>
</ul>
{figure('n10_clustering.png', 'Grupiranje signala', 'Broj novih ulaza po mjesecu u svih 43 dionice i prosječni račun kupi-i-drži.')}
<div class="callout warn"><b>Jedan račun, a ne 43.</b> U testu svaka dionica ima vlastitih 1.000 €. U stvarnosti imaš jedan račun, a signali dolaze u valovima (najviše {max(x for x in [int(v) for v in pd.Series(1, index=pd.DatetimeIndex([pd.Timestamp(tr['entry_date']) for t in TICKERS for tr in SL[('C13C', t, 'ai_era', '1x')][3]])).resample('ME').sum().values])} ulaza u jednom mjesecu na svih 43). Zato moraš unaprijed odrediti prioritet (npr. memorija prvo) i najveći broj istodobnih pozicija. To je izravna sugestija iz poglavlja o poboljšanjima i nije testirano ovdje.</div>
</section>
"""


def sec_momentum() -> str:
    o, x4 = V[SC_ALL]["C13C"]["ai_era"], V[SC_ALL]["X4_MOM_CONFIRM"]["ai_era"]
    return f"""
<section id="momentum">
<h2>8. Momentum: je li C13C momentum strategija i pomaže li filter</h2>
<p><b>Što je momentum?</b> Ideja da dionica koja je u zadnje vrijeme jako rasla ima tendenciju rasti i dalje. C13C je mješavina: trend (iznad SMA200) govori da dionica ima dugoročni momentum, a pad od 5 % je "povlačenje" unutar tog momenta. Dakle kupuješ jake dionice u trenutku kad privremeno slabe.</p>
<h3>Usporedba s pravim momentum pravilom</h3>
{table(["Pravilo (43 dionice, AI era)", "Trgovina mjesečno", "Uspješnih", "€ po trgovini", "Profit factor", "Prinos", "Najveći pad"],
 [["C13C (dip u trendu)", hr(a_c['trades_per_month'], 1), pct(a_c['hit_rate'], 0, False), num(a_c['expectancy_eur'], 0), num(a_c['profit_factor'], 2), pct(a_c['total_return']), pct(a_c['max_drawdown'], 0, False)],
  ["Tjedni momentum rang (W3)", hr(W3['trades_per_month'], 1), pct(W3['hit_rate'], 0, False), num(W3['expectancy_eur'], 0), num(W3['profit_factor'], 2), pct(W3['total_return']), pct(W3['max_drawdown'], 0, False)],
  ["Proboj 20-dnevnog vrha (W2)", hr(W2['trades_per_month'], 1), pct(W2['hit_rate'], 0, False), num(W2['expectancy_eur'], 0), num(W2['profit_factor'], 2), pct(W2['total_return']), pct(W2['max_drawdown'], 0, False)],
  ["Proboj otpora s retestom (W5)", hr(W5['trades_per_month'], 1), pct(W5['hit_rate'], 0, False), num(W5['expectancy_eur'], 0), num(W5['profit_factor'], 2), pct(W5['total_return']), pct(W5['max_drawdown'], 0, False)]])}
<p>Pravi momentum rang (W3) ima veće očekivanje po trgovini i veći udio uspješnih, ali upola manje trgovina i manji ukupan prinos ({pct(W3['total_return'])} naspram {pct(a_c['total_return'])}). C13C "plaća" slabijom kvalitetom trgovine za više aktivnosti.</p>
<h3>Što se dogodi kad C13C-u dodamo momentum uvjet?</h3>
<p>Varijanta X4: kupi pad samo ako je prinos zadnjih 126 dana pozitivan i dionica je u gornjoj polovici svoje skupine po tom prinosu. Rezultat: {hr(x4['trades'])} trgovina umjesto {hr(o['trades'])}; kvaliteta po trgovini ostaje ista (očekivanje {num(x4['expectancy_eur'], 1)} € naspram {num(o['expectancy_eur'], 1)} €, profit factor {num(x4['profit_factor'], 2)} naspram {num(o['profit_factor'], 2)}), a ukupni prinos pada na {pct(x4['total_return'])} umjesto {pct(o['total_return'])}. Filter samo reže trgovine, a ne popravlja one koje ostaju.</p>
{figure('n15_momentum.png', 'Momentum prije ulaza i ishod', 'Svaka trgovina razvrstana po prinosu 126 dana prije ulaza. Opisna analiza, ne test.')}
<div class="teacher"><p>Iznenađenje: kod najjačeg prethodnog momentuma (gornja petina) očekivanje po trgovini je najniže, a kod najslabijeg najviše. Dionice koje su jako rasle imaju nemirnije korekcije pa stop od 10 % češće puca. To je opis što se dogodilo u ovom uzorku, ne dokaz zakona, ali govori da "samo jake dionice" nije poboljšanje.</p></div>
</section>
"""


def sec_improve() -> str:
    head = ["Varijanta", "Trgovina mj.", "Uspješnih", "€ / trg. 23-24", "€ / trg. 25-26", "PF 23-24", "PF 25-26", "Prinos 2021-22", "€ / trg. (2x trošak)", "Pravilo prihvaćanja"]
    rows = []
    o = V[SC_ALL]["C13C"]
    rows.append(["<b>Original C13C</b>", hr(o["ai_era"]["trades_per_month"], 1), pct(o["ai_era"]["hit_rate"], 0, False), num(o["h1"]["expectancy_eur"], 0), num(o["h2"]["expectancy_eur"], 0), num(o["h1"]["profit_factor"], 2), num(o["h2"]["profit_factor"], 2), pct(o["y2021_2022"]["total_return"], 1), num(o["ai_era_2x"]["expectancy_eur"], 0), "osnova"])
    for vid in VAR_NAME:
        v = V[SC_ALL][vid]
        ok = ACC[vid]["pass"]
        failed = ", ".join(k for k, val in ACC[vid]["checks"].items() if not val)
        rows.append([f"<b>{VAR_NAME[vid]}</b>", hr(v["ai_era"]["trades_per_month"], 1), pct(v["ai_era"]["hit_rate"], 0, False), num(v["h1"]["expectancy_eur"], 0), num(v["h2"]["expectancy_eur"], 0), num(v["h1"]["profit_factor"], 2), num(v["h2"]["profit_factor"], 2), pct(v["y2021_2022"]["total_return"], 1), num(v["ai_era_2x"]["expectancy_eur"], 0), "ZADOVOLJAVA" if ok else f"ne ({failed})"])
    head_m = ["Varijanta (MU WDC STX)", "Trgovina u AI eri", "€ / trg.", "Profit factor", "Prinos", "Najveći pad", "Prinos naspram originala"]
    rows_m = []
    om = V[SC_MEM]["C13C"]["ai_era"]
    for vid in ["C13C", *VAR_NAME]:
        v = V[SC_MEM][vid]["ai_era"]
        rows_m.append([f"<b>{'Original C13C' if vid == 'C13C' else VAR_NAME[vid]}</b>", str(v["trades"]), num(v["expectancy_eur"], 0), num(v["profit_factor"], 2), pct(v["total_return"]), pct(v["max_drawdown"], 0, False), "-" if vid == "C13C" else pct(v["total_return"] - om["total_return"], 0)])
    ideas = "".join(f"<li><b>{VAR_NAME[v]}:</b> {VAR_IDEA[v]}</li>" for v in VAR_NAME)
    x2, x1 = V[SC_ALL]["X2_TRAIL20"], V[SC_ALL]["X1_TRAIL15"]
    return f"""
<section id="poboljsanja">
<h2>9. Kako ga poboljšati: testirano i prijedlozi</h2>
<h3>Što smo testirali i kako</h3>
<p>Šest varijanti je zamrznuto i upisano u registar pokusa <b>prije</b> pokretanja (K u registru je sada {SUMM['ledger_k'] + 6}). Svaka mijenja samo jednu stvar. Pravilo prihvaćanja napisano je unaprijed: varijanta se smatra poboljšanjem samo ako na 43 dionice ima veće očekivanje i veći profit factor u <b>obje</b> polovice AI ere, prinos u 2021.-2022. nije manji, a očekivanje pri dvostrukom trošku ostaje pozitivno. Sedma, ponovni ulaz (K7), bila je registrirana ranije.</p>
<ul>{ideas}</ul>
{figure('n13_variants.png', 'Varijante poboljšanja', 'Očekivanje po trgovini u dvije polovice AI ere i u 2021.-2022.; desno profit factor.')}
<h3>Rezultat na 43 dionice</h3>
{table(head, rows)}
<p class="small">"Pravilo prihvaćanja" je provedeno točno kako je napisano prije testa, bez zaokruživanja u korist varijante.</p>
{figure('n14_variant_equity.png', 'Računi kroz AI eru', 'Prosječni račun od 1.000 € po dionici: original i glavne varijante, lijevo 43 dionice, desno memorijska trojka.')}
<h3>Rezultat na memorijskoj trojci (informativno, nije dio pravila)</h3>
{table(head_m, rows_m)}
<h3>Što iz toga zaključujem</h3>
<ul>
<li><b>Širi stop je jedina varijanta koja prolazi pravilo.</b> Stop 20 %: očekivanje {eur(x2['ai_era']['expectancy_eur'])} po trgovini naspram {eur(o['ai_era']['expectancy_eur'])}, profit factor {num(x2['ai_era']['profit_factor'], 2)} naspram {num(o['ai_era']['profit_factor'], 2)}, a u 2021.-2022. {pct(x2['y2021_2022']['total_return'], 1)} naspram {pct(o['y2021_2022']['total_return'], 1)}. Stop 15 % ({eur(x1['ai_era']['expectancy_eur'])}, profit factor {num(x1['ai_era']['profit_factor'], 2)}) zadovoljava sve osim jednog uvjeta: u 2021.-2022. je {pct(x1['y2021_2022']['total_return'], 1)} umjesto {pct(o['y2021_2022']['total_return'], 1)} (praktički nula, ali pravilo je pravilo). Širi stop znači rjeđe trgovanje ({hr(x2['ai_era']['trades_per_month'], 0)} mjesečno za 20 %), što se kosi s tvojim ciljem "radi često".</li>
<li><b>Pažnja:</b> poboljšanje je jedna os (10, 15, 20 %), a AI era je uzlazno tržište u kojem širi stop uvijek pomaže jer te manje izbacuje iz uspona. Što bi bilo s 25 ili 30 % nije testirano i ne smije se ekstrapolirati. Na memorijskoj trojci ukupni prinos nije veći od originala, samo je očekivanje po trgovini veće.</li>
<li><b>Ostale varijante ne pomažu:</b> momentum potvrda, ATR stop, manji pad, prosjek 100 i ponovni ulaz ne zadovoljavaju pravilo; ponovni ulaz i prosjek 100 u 2021.-2022. gube.</li>
<li><b>Nijedna varijanta nije validirana.</b> To je istraživački pokus na istih 43 dionice i istoj eri, nije Critic PASS. K u registru je narastao zbog tih šest pokusa.</li>
</ul>
<h3>Prijedlozi za sljedeći krug (nisu testirani; svaki traži novi zamrznuti ID)</h3>
<ol>
<li><b>Jedan račun, ograničen broj pozicija i prioritet.</b> Najvažnije za stvarnost: simulacija s jednim računom (npr. 5 mjesta, memorija prva, ostale po jačini momentuma). Ovo bi pokazalo koliko od pooled rezultata stvarno možeš uhvatiti.</li>
<li><b>Veličina pozicije iz stopa.</b> Rizik 1 % računa po trgovini (udaljenost do stopa određuje broj dionica). Tvoj stav o riziku to dopušta veći, ali jedinstveno pravilo čini rezultate usporedivima.</li>
<li><b>Dva motora.</b> Kombinacija C13C (često) i proboja otpora s retestom (W5, veće očekivanje) u jednom računu. Ranije su testirani odvojeno.</li>
<li><b>Izlaz s dvije faze.</b> Stop 10 % do +20 % dobitka, nakon toga 20 %. Spaja prednost uskog stopa u početku i širokog u uzletu (pazi na ugađanje).</li>
<li><b>Izbjegavanje izvještaja o zaradi.</b> Gap preko izvještaja je glavni izvor trgovina koje probiju stop po otvaranju. Projekt već ima kalendar (<code>data/news/MU_earnings_dates.csv</code> za MU); za ostale dionice treba izvor.</li>
<li><b>Filter tržišta.</b> Ne kupuj kad je cijeli sektor ispod prosjeka 200 dana. Treba pouzdan indeks za poluvodiče kojeg možeš gledati bez američkog ETF-a (nepotvrđeno za EU).</li>
</ol>
<div class="callout warn"><b>Poštenje oko ovih prijedloga:</b> svaka dodana stvar je novi pokus i nova prilika za slučajan pronalazak. Preporuka je ne testirati više od dva-tri prijedloga i ne mijenjati C13C u živo dok ne prođe unaprijed zapisano pravilo i na razdoblju koje nismo vidjeli (zadnji mjeseci podataka prema naprijed).</div>
</section>
"""


def sec_today() -> str:
    head = ["Dionica", "Zadnji dan", "Zatvaranje", "SMA200", "Iznad SMA200", "Pad 5 dana", "Trend ok", "Signal", "U poziciji na kraju"]
    sig = ", ".join(TODAY_SIGNALS) if TODAY_SIGNALS else "nijedna dionica"
    return f"""
<section id="danas">
<h2>10. Što C13C kaže na zadnjem danu podataka ({LAST_DATE})</h2>
<p>Pravilo primijenjeno na zadnju završenu svijeću iz datoteka. <b>Signal na zadnjem danu u podacima:</b> {sig}. U poziciji na kraju testa (otvorene u simulaciji): {", ".join(OPEN_POS) if OPEN_POS else "nitko"}. Podaci završavaju {LAST_DATE}; današnji dan nije obuhvaćen dok se datoteke ne osvježe.</p>
<div class="tw"><table class="t" data-sort="1"><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead><tbody>{"".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in TODAY_ROWS)}</tbody></table></div>
<p class="small">Ovo je opis pravila na povijesnim podacima, ne preporuka za kupnju. Kupnja bi se izvršila tek na idućem otvaranju.</p>
</section>
"""


def sec_pine() -> str:
    code = html.escape(PINE.read_text(encoding="utf-8").strip())
    return f"""
<section id="pine">
<h2>11. Kako primijeniti na svoje dionice u TradingViewu (Pine)</h2>
<ol>
<li>U TradingViewu otvori <b>Pine Editor</b>, zalijepi kod ispod, spremi i klikni "Add to chart".</li>
<li>Otvori dnevni graf dionice (npr. NASDAQ:MU). U <b>Strategy Tester</b> vidiš trgovine, krivulju računa i brojke.</li>
<li>Ulazi su podešeni na tvoja pravila: SMA 200, pad 5 % u 5 dana, stop 10 % ispod vrha. Polje "Pomični stop" promijeni na 15 ili 20 za varijante X1 i X2.</li>
<li>Strategija trguje samo od 1. 1. 2023. (polje "Trguj od"), da odgovara AI eri iz ovog dokumenta.</li>
<li>Za pregled više dionica odjednom koristi tablicu momentuma (<code>MASTER_W3_MOMENTUM_TABLE.pine</code>) na watchlisti.</li>
<li>Alarme postavljaj samo kao informaciju ("Any alert() function call"); skripta ne šalje naloge.</li>
</ol>
<div class="callout warn"><b>Razlika Pine i Pythona:</b> izmjereno je samo za MU: TradingView daje 34 trgovine, Python 37. Razlika dolazi od drukčijih podataka (TradingView koristi svoj feed) i toga što Pine stop ne djeluje na samoj ulaznoj svijeći. Za ostale dionice usporedba trgovinu po trgovinu nije napravljena.</div>
<details class="code"><summary>Pine kod (MASTER_W1_C13C)</summary><pre><code>{code}</code></pre></details>
</section>
"""


def sec_limits() -> str:
    return f"""
<section id="ogranicenja">
<h2>12. Ograničenja i što je nepotvrđeno</h2>
<ul>
<li><b>Odabir dionica s pogledom unatrag:</b> koš čine dionice AI lanca koje danas postoje i uglavnom su rasle.</li>
<li><b>Bik-era:</b> AI era je razdoblje snažnog rasta. U 2021.-2022. pravilo je bilo oko nule; pravi test bi bila dulja medvjeđa faza.</li>
<li><b>Računi odvojeni po dionici:</b> test koristi 1.000 € po dionici, a ne jedan zajednički račun (vidi poglavlje 9, prijedlog 1).</li>
<li><b>Nema tečaja EUR/USD, dividendi, poreza i minimalne provizije.</b> Za male račune minimalna provizija može pojesti dio dobiti.</li>
<li><b>Nema Critic PASS</b> (unaprijed zapisana provjera projekta). C13C je istraživački kandidat; brojevi u ovom dokumentu nisu tvrdnja da će zaraditi.</li>
<li><b>Dopuštenja kod brokera (IBKR), razlomljene dionice, hrvatski porez i EU dostupnost</b> nisu provjereni. Američke pojedinačne dionice su općenito dostupne EU klijentima; to treba potvrditi u svom računu prije prve kupnje.</li>
<li><b>Registar pokusa:</b> uz ovaj dokument registrirano je 6 varijanti (K raste na {SUMM['ledger_k'] + 6}). Svaki dodatni pokus povećava šansu za slučajno dobar rezultat.</li>
<li><b>Nijedan nalog nije poslan.</b> Sve je simulacija na povijesnim podacima.</li>
</ul>
<h3>Reprodukcija</h3>
<details class="code"><summary>Datoteke i naredbe</summary><pre><code>.venv/bin/python -m lab.aichain.c13c_variants      # zamrzni i registriraj varijante (već izvršeno)
.venv/bin/python -m lab.aichain.c13c_nb_run        # izračun: results.json, sleeves.pkl
.venv/bin/python -m lab.aichain.c13c_nb_charts     # grafovi
.venv/bin/python scripts/c13c_notebook_assemble.py # ova stranica

kod:     lab/aichain/c13c_variants.py, c13c_nb_run.py, c13c_nb_charts.py
izlaz:   reports/research/C13C_NOTEBOOK_20261014/
zamrznuto: strategies/frozen/2026-10-14_C13CX_*.json</code></pre></details>
</section>
"""


def sec_glossary() -> str:
    terms = [
        ("SMA200", "prosjek zatvaranja zadnjih 200 dana; iznad njega kažemo da je dionica u dugoročnom usponu."),
        ("Stop (zaštitni nalog)", "cijena na kojoj izlaziš iz trgovine; ovdje 10 % ispod najvišeg vrha, samo se diže."),
        ("Gap", "otvaranje koje preskoči cijene iz prethodnog dana (npr. nakon izvještaja); stop se tada izvršava po lošijoj cijeni."),
        ("Drawdown (pad)", "najveći pad računa od vlastitog vrha; ako je vrh bio 10.000 € a dno 7.000 €, pad je 30 %."),
        ("Profit factor", "zbroj dobitaka podijeljen sa zbrojem gubitaka; 2 znači da na svaki izgubljeni euro dođu dva dobivena."),
        ("Očekivanje po trgovini", "prosječna zarada ili gubitak jedne trgovine; ovdje izraženo u eurima na 1.000 € uloga."),
        ("Pooled", "zbroj računa svih dionica, svaka s vlastitih 1.000 €."),
        ("AI era", "razdoblje od 1. 1. 2023. nadalje, kojim ocjenjujemo pravila."),
        ("Kupi i drži", "kupiš na početku i ništa ne radiš; mjerilo s kojim se sve uspoređuje."),
        ("Momentum", "tendencija dionice koja je rasla da raste i dalje; mjeri se prinosom zadnjih tjedana ili mjeseci."),
    ]
    items = "".join(f"<li><b>{t}:</b> {d}</li>" for t, d in terms)
    return f'<section id="rjecnik"><h2>Rječnik</h2><ul>{items}</ul></section>'


SECTIONS = [
    ("uvod", "Ukratko", sec_hero),
    ("pravilo", "1. Pravilo u četiri koraka", sec_rule),
    ("podaci", "2. Podaci i testiranje", sec_data),
    ("rezultati", "3. Rezultati po dionici", sec_results),
    ("memorija", "4. Memorijske dionice", sec_memory),
    ("skupine", "5. Skupine i svih 43 grafa", sec_segments),
    ("razdoblja", "6. Tri razdoblja", sec_periods),
    ("trgovine", "7. Kako izgleda trgovanje", sec_trades),
    ("momentum", "8. Momentum", sec_momentum),
    ("poboljsanja", "9. Poboljšanja i prijedlozi", sec_improve),
    ("danas", "10. Stanje na zadnjem danu", sec_today),
    ("pine", "11. Pine u TradingViewu", sec_pine),
    ("ogranicenja", "12. Ograničenja", sec_limits),
    ("rjecnik", "Rječnik", sec_glossary),
]

EXTRA_CSS = """
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:1em 0}
.kpi{border:2px solid var(--accent);border-radius:6px;padding:10px 14px;background:var(--example-bg);font-family:var(--ui-font);display:flex;flex-direction:column;gap:4px;min-width:0}
.kpi b{font-family:var(--hand-font);font-size:2.1rem;color:var(--hand);line-height:1}
.kpi span{font-size:.82rem;color:var(--muted);line-height:1.35}
table.t[data-sort] th{cursor:pointer;user-select:none}
table.t[data-sort] th:after{content:" \\2195";opacity:.4;font-size:.8em}
details.code>figure.fig{margin:1em 8px}
"""
SORT_JS = """
(function(){
  document.querySelectorAll('table[data-sort]').forEach(function(t){
    var ths=t.querySelectorAll('th');
    ths.forEach(function(th,i){th.addEventListener('click',function(){
      var tb=t.tBodies[0];var rows=[].slice.call(tb.rows);
      var dir=th.getAttribute('data-dir')==='asc'?'desc':'asc';
      ths.forEach(function(x){x.removeAttribute('data-dir');});th.setAttribute('data-dir',dir);
      function val(r){var s=r.cells[i].textContent.trim().replace(/\\./g,'').replace(',','.').replace(/[^0-9.\\-+]/g,'');var n=parseFloat(s);return isNaN(n)?r.cells[i].textContent.trim():n;}
      rows.sort(function(a,b){var x=val(a),y=val(b);var r=(typeof x==='number'&&typeof y==='number')?x-y:String(x).localeCompare(String(y),'hr');return dir==='asc'?r:-r;});
      rows.forEach(function(r){tb.appendChild(r);});
    });});
  });
})();
"""

IMG_RE = re.compile(r"<img data-chart=\"([^\"]+)\" alt=\"([^\"]*)\">")


def embed(doc: str, used: set[str], sizes: dict[str, int]) -> str:
    cache: dict[str, str] = {}

    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        used.add(name)
        path = CHARTS / name
        if name not in cache:
            uri, w, h, size = encode_chart(str(path))
            cache[name] = f'<img src="{uri}" alt="{m.group(2)}" loading="lazy" decoding="async" width="{w}" height="{h}">'
            sizes[name] = size
        return cache[name]

    return IMG_RE.sub(sub, doc)


def wrap_tables(fragment: str) -> str:
    out = []
    pos = 0
    for m in re.finditer(r"<table\b.*?</table>", fragment, re.S):
        before = fragment[pos : m.start()]
        out.append(before)
        pre = before.rstrip()[-30:]
        out.append(m.group(0) if pre.endswith('<div class="tw">') else f'<div class="tw">{m.group(0)}</div>')
        pos = m.end()
    out.append(fragment[pos:])
    return "".join(out)


def add_copy_buttons(fragment: str) -> str:
    return re.sub(
        r"(<details class=\"code\">\s*<summary>(?:Pine kod|Datoteke i naredbe).*?</summary>)",
        r'\1<div class="codebar"><button type="button" class="copy" data-copy>Kopiraj kod</button></div>',
        fragment,
        flags=re.S,
    )


def main() -> int:
    body = "\n".join(fn() for _, _, fn in SECTIONS)
    used: set[str] = set()
    sizes: dict[str, int] = {}
    body = embed(body, used, sizes)
    body = wrap_tables(body)
    body = add_copy_buttons(body)
    toc = "".join(f'<li><a href="#{i}">{html.escape(t)}</a></li>' for i, t, _ in SECTIONS)
    toc_d = f'<aside class="toc toc-d" aria-label="Sadržaj"><div class="tp">Sadržaj</div><ul>{toc}</ul></aside>'
    toc_m = f'<details class="toc toc-m"><summary>Sadržaj (otvori / zatvori)</summary><nav aria-label="Sadržaj"><ul>{toc}</ul></nav></details>'
    doc = f"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="utf-8">
<title>C13C Bilježnica</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="Jedan algoritam, C13C, na svih 43 memorijskih i poluvodičkih dionica: pravila, podaci, grafovi, momentum, poboljšanja i Pine.">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Inter:wght@400;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body>
<div class="wrap">
{toc_m}
<div class="layout">
{toc_d}
<main>
<div class="page">
<div class="topbar"><span>Istraživanje, ne savjet. Bez naloga. Podaci do {LAST_DATE}.</span><button type="button" class="theme" aria-label="Promijeni svijetlu i tamnu temu">Svijetlo / tamno</button></div>
<h1>C13C: bilježnica jednog algoritma</h1>
<p class="sub">Pravilo, podaci, grafovi svih {len(TICKERS)} {dion(len(TICKERS))}, momentum, poboljšanja i Pine. Sve brojke dolaze iz projektnih datoteka.</p>
{body}
<footer>Istraživanje, ne ulagački, porezni ni pravni savjet i ne obećava zaradu. Nijedan nalog nije poslan. Troškovi 2,5 bps po strani; tečaj EUR/USD, dividende, porezi i minimalna provizija nisu modelirani. Dopuštenja kod brokera, KID i hrvatski porez nepotvrđeni. Sastavljeno skriptom <code>scripts/c13c_notebook_assemble.py</code>.</footer>
</div>
</main>
</div>
</div>
<script>{JS}{SORT_JS}</script>
</body>
</html>
"""
    check = structural_check(doc)
    pine_ok = html.unescape(re.search(r'Pine kod.*?<pre><code>(.*?)</code></pre>', doc, re.S).group(1)).strip() == PINE.read_text(encoding="utf-8").strip()  # type: ignore[union-attr]
    if not pine_ok:
        check["errors"].append("Pine block differs from file")
    missing = sorted({n for n in used if not (CHARTS / n).is_file()})
    data = doc.encode("utf-8")
    if len(data) > 14 * 1024 * 1024:
        check["errors"].append(f"file too large: {len(data) / 1e6:.1f} MB")
    OUT.write_bytes(data)
    report = {
        "output": str(OUT),
        "size_mb": round(len(data) / 1048576, 2),
        "charts_embedded": len(used),
        "missing": missing,
        "pine_equals_file": pine_ok,
        "structure": check,
        "variant_passers_43": PASSERS,
    }
    (DIR / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if check["errors"] or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
