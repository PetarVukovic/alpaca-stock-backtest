#!/usr/bin/env python3
"""Build the data atlas page (charts + self-contained HTML) from inventory.json. Read-only, no orders.

Input:  reports/research/DATA_ATLAS_20261014/inventory.json (scripts/data_atlas_scan.py)
Output: charts/*.png and data_atlas.html in the same folder.
Run:    .venv/bin/python scripts/data_atlas_build.py
"""

from __future__ import annotations

import html
import json
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

from lab.aichain import master_common as mc  # noqa: E402
from lab.aichain.master_common import GREY, bottom_note, canvas, finish, paper, tip  # noqa: E402
from lab.top10.charts import INK, PENCIL, RED  # noqa: E402

DIR = ROOT / "reports" / "research" / "DATA_ATLAS_20261014"
CH = DIR / "charts"
mc.OUT = CH
INV = json.loads((DIR / "inventory.json").read_text())
DF = pd.DataFrame(INV["files"])
DF["first_d"] = pd.to_datetime(DF["first"])
DF["last_d"] = pd.to_datetime(DF["last"])
DAILY = DF[DF.kind == "daily"].copy()
HOURLY = DF[DF.kind == "hourly"]
INTRA = DF[DF.kind == "intraday"]
FUT = DF[DF.kind == "futures"].copy()
FUT["root"] = FUT["ticker"].str.split("_").str[0]
PALETTE = ["#2f6fb3", "#17803d", "#d9822b", "#7a4fb3", "#c2321f", "#a0522d", "#0e8a8a", "#b5651d", "#6b7280", "#c28fb0", "#3d8a4a", "#8a6d1d", "#1f4e79", "#9c27b0", "#555555"]
CLASS_ORDER = [c for c in dict.fromkeys(DAILY.sort_values("first_d")["class"]) if c != "Terminski ugovori (IBKR)"]
CLASS_ORDER = [
    "Memorija i pohrana", "Oprema za čipove", "AI čipovi i logika", "Mreže i serveri", "Cloud", "ETF-ovi poluvodiča",
    "Zlato, srebro, rudari (SAD)", "Zlato i srebro (EU, IBKR)", "Energija i roba", "Kripto (USDT, Binance)", "Kripto (USD, Alpaca)",
    "Kripto dionice i ETF", "Široko tržište i kamate", "Indeksi (IBKR)", "Forex (IBKR)",
]
COL = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(CLASS_ORDER)}


def hr(x: float, nd: int = 0) -> str:
    return f"{x:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def dh(ts: Any) -> str:
    d = pd.Timestamp(ts)
    return f"{d.day}. {d.month}. {d.year}."


def table(head: list[str], rows: list[list[str]], sortable: bool = False) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="t"{" data-sort=\"1\"" if sortable else ""}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def figure(name: str, alt: str, cap: str) -> str:
    return f'<figure class="fig"><img data-chart="{name}" alt="{html.escape(alt)}"><figcaption>{cap}</figcaption></figure>'


def step_label(s: float | None) -> str:
    if s is None:
        return "-"
    if s >= 86400 * 0.9:
        return "1 dan"
    if s >= 3000:
        return "1 sat"
    if s >= 250:
        return "5 min"
    return "1 min"


# ------------------------------------------------------------------------------------------------ charts
def c01_matrix() -> str:
    tick = pd.concat([DAILY, HOURLY, INTRA])
    order = [(c, sorted(set(DAILY[DAILY["class"] == c]["ticker"]))) for c in CLASS_ORDER]
    have = {(r.ticker, r.timeframe) for r in tick.itertuples()}
    rows: list[tuple[str, str]] = []
    for c, ts in order:
        rows += [(c, t) for t in ts]
    half = (len(rows) + 1) // 2
    fig = canvas(15.0, "Što imamo: svaki instrument i koje učestalosti", "Kvadrat = postoji datoteka. Boja = skupina. Stupci: dnevni, satni, 5-minutni, 1-minutni.")
    for k, part in enumerate((rows[:half], rows[half:])):
        ax = fig.add_axes([0.07 + k * 0.50, 0.04, 0.40, 0.86])
        paper(ax, grid=False)
        for i, (c, t) in enumerate(part):
            for j, tf in enumerate(("1d", "1h", "5m", "1m")):
                ok = (t, tf) in have
                ax.add_patch(__import__("matplotlib").patches.Rectangle((j, -i), 0.82, 0.78, fc=COL[c] if ok else "#ece8d8", ec="none", alpha=1 if ok else 0.5))
            ax.text(-0.15, -i + 0.38, t, ha="right", va="center", fontsize=9.2, color=INK)
        ax.set_xlim(-0.1, 4)
        ax.set_ylim(-len(part) + 0.4, 1.2)
        ax.set_xticks([0.41, 1.41, 2.41, 3.41])
        ax.set_xticklabels(["dnevni", "satni", "5 min", "1 min"], fontsize=11)
        ax.xaxis.tick_top()
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
    handles = [__import__("matplotlib").patches.Patch(color=COL[c], label=c) for c in CLASS_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, -0.005))
    return finish(fig, "d01_matrix.png", {"title": "Matrica instrumenata", "what_to_see": "Koji instrument ima koje učestalosti", "numbers_used": [str(len(rows))]})


def c02_gantt() -> str:
    rows: list[tuple[str, str, pd.Timestamp, pd.Timestamp]] = []
    for c in CLASS_ORDER:
        sub = DAILY[DAILY["class"] == c].sort_values(["first_d", "ticker"])
        rows += [(c, r.ticker, r.first_d, r.last_d) for r in sub.itertuples()]
    fig = canvas(21.0, "Od kada do kada: dnevni podaci svakog instrumenta", "Svaka crta je jedna datoteka od prvog do zadnjeg dana. Crvena crta: početak AI ere (1. 1. 2023.).")
    ax = fig.add_axes([0.075, 0.035, 0.91, 0.91])
    paper(ax)
    for i, (c, t, a, b) in enumerate(rows):
        ax.plot([a, b], [-i, -i], color=COL[c], lw=5.2, solid_capstyle="butt")
        ax.text(a - pd.Timedelta(days=60), -i, t, ha="right", va="center", fontsize=8.6, color=INK)
    ax.axvline(pd.Timestamp("2023-01-01"), color=RED, ls=":", lw=2)
    ax.set_yticks([])
    ax.set_ylim(-len(rows) + 0.3, 1)
    ax.set_xlim(pd.Timestamp("2011-01-01"), pd.Timestamp("2027-02-01"))
    ax.xaxis.set_major_locator(__import__("matplotlib.dates", fromlist=["x"]).YearLocator())
    ax.xaxis.set_major_formatter(__import__("matplotlib.dates", fromlist=["x"]).DateFormatter("%Y"))
    handles = [__import__("matplotlib").patches.Patch(color=COL[c], label=c) for c in CLASS_ORDER]
    ax.legend(handles=handles, loc="upper left", fontsize=10, frameon=True, facecolor="#fffdf6")
    return finish(fig, "d02_gantt.png", {"title": "Pokrivenost dnevnih podataka", "what_to_see": "Početak i kraj svake dnevne datoteke", "numbers_used": [str(len(rows))]})


def c03_sources() -> str:
    g = DF.groupby("source").agg(files=("rows", "size"), mb=("size_mb", "sum"), rows=("rows", "sum")).sort_values("mb")
    fig = canvas(6.4, "Odakle dolaze podaci", "Broj datoteka i veličina na disku po izvoru.")
    a1 = fig.add_axes([0.28, 0.14, 0.32, 0.66])
    a2 = fig.add_axes([0.68, 0.14, 0.30, 0.66])
    for ax in (a1, a2):
        paper(ax)
    y = np.arange(len(g))
    a1.barh(y, g["files"], color="#2f6fb3", edgecolor=PENCIL)
    a2.barh(y, g["mb"], color="#d9822b", edgecolor=PENCIL)
    a1.set_yticks(y)
    a1.set_yticklabels(g.index, fontsize=11)
    a2.set_yticks([])
    a1.set_xlabel("datoteka", fontsize=12)
    a2.set_xlabel("MB na disku", fontsize=12)
    for yy, (f, m) in enumerate(zip(g["files"], g["mb"])):
        a1.text(f, yy, f" {f}", va="center", fontsize=10.5)
        a2.text(m, yy, f" {hr(m)}", va="center", fontsize=10.5)
    bottom_note(fig, "Alpaca i Binance nose gotovo sve težine; IBKR su sitni, ali jedini izvor za forex, indekse, futurese i EU metale.")
    return finish(fig, "d03_sources.png", {"title": "Izvori", "what_to_see": "Datoteke i MB po izvoru", "numbers_used": ["inventory.json"]})


def c04_timeframes() -> str:
    g = DF.assign(tf=DF["timeframe"]).groupby("tf").agg(files=("rows", "size"), rows=("rows", "sum"), mb=("size_mb", "sum")).reindex(["1d", "1h", "5m", "1m"])
    fig = canvas(6.0, "Koliko često: broj redaka po učestalosti", "Dnevni su najbrojniji po instrumentima, ali minutni i 5-minutni nose većinu redaka i megabajta.")
    a1 = fig.add_axes([0.07, 0.15, 0.40, 0.64])
    a2 = fig.add_axes([0.58, 0.15, 0.39, 0.64])
    for ax in (a1, a2):
        paper(ax)
    lab = ["dnevni (1d)", "satni (1h)", "5 min", "1 min"]
    a1.bar(lab, g["rows"], color="#17803d", edgecolor=PENCIL)
    a1.set_yscale("log")
    a1.set_title("redaka (log skala)", fontsize=13, loc="left", color=INK)
    a2.bar(lab, g["mb"], color="#d9822b", edgecolor=PENCIL)
    a2.set_title("MB na disku", fontsize=13, loc="left", color=INK)
    for ax, col in ((a1, "rows"), (a2, "mb")):
        for i, v in enumerate(g[col]):
            ax.text(i, v, hr(v), ha="center", va="bottom", fontsize=10.5)
    return finish(fig, "d04_timeframes.png", {"title": "Učestalosti", "what_to_see": "Retci i MB po učestalosti", "numbers_used": ["inventory.json"]})


# ------------------------------------------------------------------------------------------------ sections
N_TICK = DF[DF.kind.isin(["daily", "hourly", "intraday", "raw_hourly"])]["ticker"].nunique()
N_DAILY = len(DAILY)
TOTAL_ROWS = int(DF["rows"].sum())
TOTAL_MB = float(DF["size_mb"].sum()) + sum(d["size_mb"] for d in INV["derivs"])
LATEST = DAILY["last_d"].max()


def sec_summary() -> str:
    kp = [
        (hr(len(DF)), "pregledanih datoteka s cijenama (dnevne, satne, 5- i 1-minutne, futuresi)"),
        (hr(TOTAL_ROWS / 1e6, 1) + " mil.", "redaka cijena ukupno"),
        (str(DAILY["ticker"].nunique()), "instrumenata s dnevnom poviješću"),
        (f"{hr(TOTAL_MB / 1024, 1)} GB", "ukupno na disku (uključujući derivate)"),
    ]
    cards = "".join(f'<div class="kpi"><b>{v}</b><span>{t}</span></div>' for v, t in kp)
    return f"""
<section id="ukratko"><h2>Ukratko</h2>
<div class="kpis">{cards}</div>
<p class="lead">Ovo je popis svih podataka u projektu: što je u mapi <code>data/</code>, odakle je došlo, koliko često su svijeće (dan, sat, 5 minuta, minuta), koje dionice i druge instrumente pokriva te koje su poznate mane. Sve brojke dolaze iz skeniranja stvarnih datoteka (<code>scripts/data_atlas_scan.py</code>), ne iz sjećanja.</p>
<ul>
<li><b>Dnevni podaci</b> su glavni materijal: {N_DAILY} instrumenata, većina od 4. 1. 2016. do listopada 2026. (neki kraći jer su kasnije izašli na burzu ili su dohvaćeni kraće).</li>
<li><b>Satni</b> ({len(HOURLY)} datoteka) i <b>5-minutni</b> ({len(INTRA[INTRA.timeframe == '5m'])} datoteka) postoje za manji broj instrumenata; <b>1-minutni</b> samo za BTC i ETH.</li>
<li><b>Izvori:</b> Alpaca (dionice i ETF-ovi, kripto USD), Binance (kripto USDT i derivati), Interactive Brokers preko MCP-a (forex, indeksi, futuresi, EU metali), Alpaca/Benzinga vijesti i ručno provjeren kalendar događaja.</li>
<li><b>Kraj podataka nije svugdje isti</b> (od 5. do 14. 10. 2026.). Testovi u projektu koriste zajednički kraj 5. 10. 2026. gdje je to važno.</li>
<li><b>Ne postoji u data/:</b> fundamenti kompanija, opcije, dividende (cijene su samo prilagođene za splitove), kontinuirani futures nizovi i makro serije osim ECB tečajeva.</li>
</ul></section>"""


def sec_map() -> str:
    rows = []
    for c in CLASS_ORDER:
        d = DAILY[DAILY["class"] == c]
        tk = sorted(d["ticker"])
        h = len(set(HOURLY[HOURLY["class"] == c]["ticker"]))
        m5 = len(set(INTRA[(INTRA["class"] == c) & (INTRA.timeframe == "5m")]["ticker"]))
        m1 = len(set(INTRA[(INTRA["class"] == c) & (INTRA.timeframe == "1m")]["ticker"]))
        rows.append([f"<b>{c}</b>", str(len(tk)), ", ".join(tk), dh(d["first_d"].min()), dh(d["last_d"].max()), str(h), str(m5), str(m1)])
    return f"""
<section id="karta"><h2>1. Karta: što imamo</h2>
{table(["Skupina", "Dnevnih", "Instrumenti", "Najraniji dan", "Najkasniji dan", "Satnih", "5 min", "1 min"], rows)}
<p class="small">"GOLD" u skupini rudara je dionica Barrick Gold, a ne cijena zlata. Skupine su moje razvrstavanje za preglednost, ne klasifikacija iz projekta.</p>
{figure("d01_matrix.png", "Matrica instrumenata i učestalosti", "Za svaki instrument vidi se postoje li dnevni, satni, 5-minutni i 1-minutni podaci.")}
{figure("d02_gantt.png", "Pokrivenost dnevnih podataka", "Početak i kraj svake dnevne datoteke. Većina dionica kreće 2016., noviji izdanja (ARM, ALAB, CRWV, SNDK, SKHY, DRAM) kasnije; forex i indeksi idu duže unatrag.")}
</section>"""


SRC_INFO = [
    ("Alpaca SIP, split-adjusted", "Dionice i ETF-ovi (SAD): dnevni, satni, 5-minutni",
     "<code>pull_alpaca.py</code> (GET, SIP, prilagodba samo za splitove), starije kopije iz trading-laba (MU, WDC, AMAT, LRCX, KLAC, SMH). Satni: <code>adjustment=split</code> (ne <code>all</code>).",
     "Cijene nisu prilagođene za dividende. WDC prije 24. 2. 2025. množen faktorom 0,68132 zbog SanDisk spin-offa (jednom, ne ponavljati). Satni imaju stupce <code>session</code> (regular, open_mixed, extended) i <code>volume_ok</code>. Iz bilješki: STX dnevni je u početku bio Alpaca IEX kopija; koji je feed sada u datoteci nije zapisano u samoj datoteci."),
    ("Alpaca crypto (USD)", "8 kripto parova u USD, dnevni",
     "<code>pull_crypto_daily.py</code>, bez ključeva za kripto podatke.", "Počinje 2021. (Alpaca kripto povijest je kraća od Binance)."),
    ("Binance spot (data.binance.vision), USDT", "9 USDT parova: dnevni, satni, 5-minutni; 1-minutni samo BTC i ETH",
     "<code>pull_binance_klines.py</code>, javni arhiv, bez ključeva.",
     "Parovi u USDT, ne USD: ista tržišta s malom razlikom (basis), ne identično. Kripto trguje 24/7, pa nema stupaca session. Povijest od 2017. (BTC, ETH)."),
    ("Binance futures (derivati)", "Funding rate (po 8 h) i 5-minutni metrici (open interest, omjeri long/short, taker) za BTC, ETH, SOL",
     "<code>pull_binance_derivs.py</code>, mapa <code>data/derivs/</code>.", "Vidi poglavlje 5. Samo istraživanje: perpetual, ne spot; instrument za EU nepotvrđen."),
    ("IBKR MidPoint (forex)", "EURUSD, GBPUSD, AUDUSD, USDCAD, USDCHF, USDJPY: dnevni, 5-minutni",
     "<code>pull_ibkr_history.py</code> iz IBKR MCP-a (samo čitanje, bez veze s računom).", "Srednja cijena, bez volumena. Alat nema paginaciju unatrag: 5-minutni samo zadnjih nekoliko tjedana."),
    ("IBKR (indeks, Last)", "SPX, NDX, VIX: dnevni, 5-minutni", "isti alat", "Bez volumena. Imaju retke s OHLC izvan raspona (vidi poglavlje 7)."),
    ("IBKR (EU ETC / UCITS)", "PHAU, PHAG, IGLN (LSE), ISLN (LSE): dnevni", "isti alat, istraživanje EU metala", "Kratka povijest (PHAU i PHAG od listopada 2024.). ISLN ima neispravne OHLC retke: nije za backtest. Dostupnost kod IBKR-a za retail i KID nisu potvrđeni."),
    ("IBKR (terminski ugovori, Last)", "GC, MGC, SI, SIL, HG, CL: pojedinačni ugovori, dnevni, satni, 5-minutni", "isti alat, mapa <code>data/archive/ibkr_contracts/</code>",
     "Svaki ugovor je zasebna datoteka (bez kontinuiranog niza, bez roll-a i prilagodbe). Nema podataka o multiplikatoru i valuti iz alata."),
]


def sec_sources() -> str:
    g = DF.groupby("source").agg(files=("rows", "size"), rows=("rows", "sum"), mb=("size_mb", "sum"))
    rows = []
    for name, what, how, caveat in SRC_INFO:
        s = g.loc[name] if name in g.index else None
        rows.append([f"<b>{name}</b>", what, how, caveat, str(int(s.files)) if s is not None else "-", hr(float(s.rows)) if s is not None else "-", hr(float(s.mb), 1) if s is not None else "-"])
    return f"""
<section id="izvori"><h2>2. Odakle dolaze podaci</h2>
<p>Izvor nije upisan u same CSV-ove (osim kod forexa u stupcu <code>source</code>), pa je ovdje izveden iz skripti za dohvat i bilješki u <code>data/*/DATA_NOTES.txt</code> i <code>reports/data/*_manifest.json</code>. Agenti ništa ne šalju brokeru: svi dohvati su čitanje.</p>
{figure("d03_sources.png", "Izvori po datotekama i veličini", "Alpaca i Binance čine gotovo cijelu težinu na disku.")}
{table(["Izvor", "Što sadrži", "Kako je dohvaćeno", "Važno znati", "Datoteka", "Redaka", "MB"], rows)}
<p class="small">Vijesti i događaji (Alpaca/Benzinga) su opisani u poglavlju 6, ECB tečajevi su u <code>reports/data/2026-10-12_ecb.xml</code> (7,8 MB). TradingView MCP daje fundamente, vijesti i kalendare za čitanje, ali se nijedan podatak iz njega ne sprema u <code>data/</code> niti ulazi u backtest.</p>
</section>"""


def sec_freq() -> str:
    g = DF.groupby("timeframe").agg(files=("rows", "size"), tick=("ticker", "nunique"), rows=("rows", "sum"), mb=("size_mb", "sum"), first=("first_d", "min"), last=("last_d", "max")).reindex(["1d", "1h", "5m", "1m"])
    names = {"1d": "Dnevni", "1h": "Satni", "5m": "5-minutni", "1m": "1-minutni"}
    notes = {
        "1d": "Jedan redak po trgovinskom danu (kripto i svaki kalendarski dan). Stupci: date, open, high, low, close, volume, vwap, trades (dionice).",
        "1h": "Dionice: SIP, stupci ts, ts_zagreb, date_et, session, volume_ok. Za testove samo session = regular. Kripto bez session.",
        "5m": "Za day trading istraživanje. Dionice SIP, ts u UTC. Forex i indeksi samo zadnjih nekoliko tjedana (ograničenje IBKR alata).",
        "1m": "Samo BTCUSDT i ETHUSDT od 1. 1. 2023.",
    }
    rows = [[f"<b>{names[k]}</b>", str(int(r.files)), str(int(r.tick)), hr(r.rows), hr(r.mb, 1), dh(r["first"]), dh(r["last"]), notes[k]] for k, r in g.iterrows()]
    raw = DF[DF.kind == "raw_hourly"]
    return f"""
<section id="ucestalost"><h2>3. Koliko su dnevni (i koliko često su svijeće)</h2>
{figure("d04_timeframes.png", "Redci i MB po učestalosti", "Dnevni podaci su najmanji, minutni najveći.")}
{table(["Učestalost", "Datoteka", "Instrumenata", "Redaka", "MB", "Najraniji", "Najkasniji", "Napomena"], rows)}
<div class="callout warn"><b>Nisu sve datoteke jednako ažurne.</b> Dnevni podaci završavaju između {dh(DAILY['last_d'].min())} (PSTG, zastario) i {dh(DAILY['last_d'].max())}. Satni većinom 5. 10. ({int((HOURLY['last_d'].dt.date == pd.Timestamp('2026-10-05').date()).sum())} datoteka) ili 13.-14. 10. za novije dohvate. Zato projektni testovi koriste zajednički završetak 5. 10. 2026.</div>
<p class="small">Uz to je u <code>data/ohlcv/</code> pet sirovih satnih datoteka (<code>*_1h.csv</code> za MU, WDC, STX, SIMO, RMBS, ukupno {hr(raw['rows'].sum())} redaka): one se ne koriste, test koristi <code>data/hourly/*_1h_clean.csv</code>.</p>
</section>"""


def class_details() -> str:
    out = ""
    for c in CLASS_ORDER:
        sub = DAILY[DAILY["class"] == c].sort_values("ticker")
        rows = []
        for r in sub.itertuples():
            tfs = [t for t, df in (("1h", HOURLY), ("5m", INTRA[INTRA.timeframe == "5m"]), ("1m", INTRA[INTRA.timeframe == "1m"])) if (df["ticker"] == r.ticker).any()]
            exp = (r.last_d - r.first_d).days + 1
            rows.append([f"<b>{r.ticker}</b>", hr(r.rows), dh(r.first_d), dh(r.last_d), "da" if r.has_volume else "ne", str(r.max_gap_days).replace(".", ",") + " d", ", ".join(tfs) if tfs else "-", r.source])
            del exp
        out += f'<details class="code"><summary>{c} ({len(sub)})</summary>{table(["Instrument", "Dnevnih redaka", "Prvi dan", "Zadnji dan", "Volumen", "Najdulji razmak", "Još i", "Izvor"], rows)}</details>'
    return out


def sec_tickers() -> str:
    return f"""
<section id="instrumenti"><h2>4. Za koje dionice i instrumente</h2>
<p>Svaka skupina ima dolje svoju tablicu: koliko dnevnih redaka, od kada do kada, ima li volumena, koji je najdulji razmak između dva retka (za dionice 3-4 dana je vikend ili praznik, više je sumnjivo) i koje druge učestalosti postoje.</p>
<div class="callout"><b>Koji instrumenti ulaze u C13C test:</b> 43 dionice iz skupina memorija, oprema, AI čipovi, mreže i cloud (bez CRWV, SNDK, PSTG). Ostalo (ETF-ovi, metali, kripto, forex) je materijal za druga istraživanja.</div>
{class_details()}
<details class="code"><summary>Katalog svih {len(DF)} datoteka (sortabilno)</summary>{table(["Datoteka", "Vrsta", "Instrument", "Učestalost", "Redaka", "Prvi", "Zadnji", "Izvor", "MB"], [[f"<code>{r.path}</code>", r.kind, r.ticker, r.timeframe, hr(r.rows), r.first[:10], r.last[:10], r.source, hr(r.size_mb, 2)] for r in DF.itertuples()], sortable=True)}</details>
</section>"""


def sec_crypto_news() -> str:
    d = INV["derivs"]
    drows = [[f"<code>{x['path']}</code>", x["symbol"], x["what"], hr(x["rows"]), x["first"][:10], x["last"][:10], ", ".join(x["columns"]), hr(x["size_mb"], 1)] for x in d]
    nw = INV["news"]
    nrows = [[f"<code>{k}</code>", hr(v["lines"]) if v["lines"] is not None else "-", hr(v["size_mb"], 2)] for k, v in nw.items() if not k.endswith("README.md") and not k.endswith(".txt")]
    cry = DF[(DF.kind == "daily") & (DF["class"].str.startswith("Kripto ("))]
    return f"""
<section id="kripto"><h2>5. Kripto i derivati</h2>
<p>Kripto ima tri sloja: dnevni i satni Binance USDT parovi od 2017., kratki Alpaca USD dnevni parovi od 2021. i 5-/1-minutni BTC, ETH, SOL. Uz to postoje derivati iz Binance futuresa.</p>
{table(["Datoteka", "Simbol", "Što", "Redaka", "Od", "Do", "Stupci", "MB"], drows)}
<div class="callout warn"><b>Poznate mane derivata</b> (izmjereno 14. 10. 2026., iz <code>data/derivs/DATA_NOTES.txt</code>): 2022. je slabo pokrivena (top_ls_sum nedostaje u oko 87 % redaka BTC-a), retci s open interest = 0 su greške burze, ima rupa do 10 h 30 min, a taker omjer ima ekstremne vrijednosti. Perpetual nije spot, a koji je instrument dostupan za EU (IBKR, MiCA) <b>nije potvrđeno</b>. Značajke se smiju koristiti tek nakon vremena snimke.</div>
<p class="small">Kripto u USDT: {", ".join(sorted(set(cry[cry["class"].str.contains("USDT")]["ticker"])))}. Kripto u USD (Alpaca): {", ".join(sorted(set(cry[cry["class"].str.contains("Alpaca")]["ticker"])))}.</p>
</section>
<section id="vijesti"><h2>6. Vijesti, događaji, arhiva</h2>
{table(["Datoteka", "Redaka", "MB"], nrows)}
<ul>
<li><b>Vijesti (Alpaca / Benzinga):</b> oko {hr(nw['data/news/archive/news_2016-01-01_now.jsonl']['lines'])} zapisa od 2016., <b>bez punog teksta</b> (samo naslov i sažetak). Filtriraj po <code>us_reaction_date</code>: vijest nakon 22:00 po zagrebačkom vremenu računa se kao reakcija idućeg američkog dana.</li>
<li><b>Kalendar događaja:</b> <code>events_calendar.csv</code>, 58 ručno provjerenih događaja; <code>MU_earnings_dates.csv</code>, 43 Micron izvještaja (samo za MU).</li>
<li><b>Zabrana:</b> ne izmišljati sentiment s društvenih mreža; vrstu događaja odrediti prije testa.</li>
<li><b>Arhiva</b> (<code>data/archive/</code>, samo čitanje, nikad ulaz u test): {", ".join(f"{k} ({v['files']} dat., {hr(v['size_mb'], 1)} MB)" for k, v in INV['archive'].items() if k != 'README.md')}. Parquet iz trading-laba je zastario i ne koristi se.</li>
</ul></section>"""


def sec_futures() -> str:
    rows = []
    for root, g in FUT.groupby("root"):
        d1 = g[g.timeframe == "1d"]
        rows.append([f"<b>{root}</b>", str(len(d1)), hr(d1["rows"].sum()), dh(d1["first_d"].min()), dh(d1["last_d"].max()), str(len(g[g.timeframe == "1h"])), str(len(g[g.timeframe == "5m"])), hr(d1["bad_ohlc_rows"].sum())])
    return f"""
<section id="futuresi"><h2>7. Terminski ugovori (zlato, srebro, bakar, nafta)</h2>
<p>Dohvaćeni su pojedinačni ugovori preko IBKR MCP-a (GC zlato, MGC mikro zlato, SI srebro, SIL mikro srebro, HG bakar, CL nafta). Svaki ugovor je zasebna datoteka u <code>data/archive/ibkr_contracts/</code>.</p>
{table(["Korijen", "Ugovora (dnevnih)", "Dnevnih redaka", "Najraniji", "Najkasniji", "Satnih datoteka", "5-min datoteka", "Retci s neispravnim OHLC"], rows)}
<div class="callout bad"><b>Nije upotrebljivo za backtest bez dodatnog rada:</b> nema kontinuiranog niza, roll-a ni prilagodbe između ugovora, a velik broj redaka ima OHLC izvan raspona (npr. zatvaranje iznad najviše cijene, vjerojatno zbog settlement konvencije, uzrok nije potvrđen). Jedan ugovor traje samo mjesecima. Za zlato, srebro i naftu kao dugi niz nemamo čistih futures podataka.</div>
</section>"""


def sec_quality() -> str:
    bad = DF[(DF.bad_ohlc_rows > 0) & (DF.kind != "futures")]
    rows = [[f"<code>{r.path}</code>", str(r.bad_ohlc_rows), hr(r.rows)] for r in bad.itertuples()]
    stale = DAILY[DAILY["last_d"] < pd.Timestamp("2026-10-05")]
    return f"""
<section id="kvaliteta"><h2>8. Kvaliteta i poznate mane</h2>
<p>Provjera <code>scripts/validate_data.py</code> (zadnji put 14. 10. 2026. 17:08): <b>rezultat OK, 0 grešaka, 22 upozorenja</b> za jezgru memorijskih dionica (većinom velika dnevna kretanja MRAM-a koja nisu na popisu poznatih stvarnih događaja). Skripta provjerava samo dio instrumenata; ostali su provjereni skeniranjem za ovaj dokument.</p>
{table(["Mana", "Što znači", "Utjecaj"], [
    ["<b>Neispravni OHLC retci</b>", "Retci gdje zatvaranje ili otvaranje izlazi iz raspona najviše-najniže cijene.", "Indeksi SPX, NDX, VIX i EU srebro ISLN ne prolaze pravila podataka; nisu za backtest bez čišćenja."],
    ["<b>Cijene bez dividendi</b>", "Cijene su prilagođene samo za splitove (i WDC spin-off).", "Ukupni povrat podcijenjen za dionice i ETF-ove koji isplaćuju dividende."],
    ["<b>Različiti kraj podataka</b>", "Datoteke završavaju od 5. do 14. 10. 2026.", "Za usporedbu instrumenata koristiti zajednički kraj."],
    ["<b>Zamrznuta povijest</b>", "SMCI prije 14. 1. 2020. i NBIS prije 21. 10. 2024. imaju zaustavljeno trgovanje (cijena ista).", "AI-lanac testovi te periode odbacuju."],
    ["<b>Zastarjelo</b>", f"{', '.join(stale['ticker'])}: zadnji redak {dh(stale['last_d'].min()) if len(stale) else '-'}.", "Isključeno iz testova."],
    ["<b>Kratka povijest</b>", "SKHY (od 10. 7. 2026.), DRAM (od 2. 4. 2026.), SNDK (od 13. 2. 2025.), CRWV, PHAU/PHAG, ETHA, ALAB, IBIT, ARM.", "Samo praćenje; premalo za pouzdan test."],
    ["<b>Dnevna svijeća dovršena?</b>", "Zadnji redak datoteke može biti nepotpun ako je dohvaćen prije zatvaranja (16:00 New York); vrijeme spremanja nije dokaz dovršenosti.", "Validator odbija nedovršen zadnji redak; za audit se koristi <code>--through DATUM</code>."],
    ["<b>Satni: feed i volumen</b>", "SIP, split prilagodba; stariji IEX retci imaju <code>volume_ok=False</code>; polovični dani nisu označeni.", "Samo session = regular, volumen samo gdje je volume_ok."],
    ["<b>Loš tick</b>", "NVDA 10. 6. 2024.: najviša cijena izvan susjednih cijena.", "Ograničeno na susjedne cijene u simulatoru, datoteka nije mijenjana."],
])}
<h3>Datoteke s neispravnim OHLC retcima (bez futuresa)</h3>
{table(["Datoteka", "Neispravnih redaka", "Ukupno redaka"], rows)}
</section>"""


def sec_use() -> str:
    return f"""
<section id="uporaba"><h2>9. Što je za što i što nedostaje</h2>
{table(["Namjena", "Koristi", "Napomena"], [
    ["Swing strategije na dionicama (dani do tjedni)", "<code>data/ohlcv/*_1d.csv</code>", "Glavni materijal; zajednički kraj 5. 10. 2026. za usporedbe."],
    ["Kratkoročni testovi (sat)", "<code>data/hourly/*_1h_clean.csv</code>, session = regular", "Dionice i ETF-ovi od 2016.; kripto 24/7."],
    ["Day trading kripta", "<code>data/intraday/*USDT_5m_clean.csv</code>, 1-minutni BTC/ETH, derivati", "Rezultat: day trading nije prošao nakon troškova (vidi CRYPTO_DAYTRADING_RESULT)."],
    ["Zlato i srebro", "ETF-ovi GLD, SLV (SAD, nepotvrđeno za EU), PHAU, PHAG, IGLN (EU)", "Srebro EU nema čistog izvora (ISLN neispravan)."],
    ["Futuresi", "<code>data/archive/ibkr_contracts/</code>", "Samo pojedinačni ugovori, ne za backtest."],
    ["Vijesti i događaji", "<code>data/news/</code>", "Bez punog teksta; filtriraj po us_reaction_date."],
])}
<h3>Što u data/ ne postoji</h3>
<ul>
<li>Fundamenti kompanija (prihodi, marže, zalihe memorije) i procjene analitičara: dostupni su kroz TradingView MCP za čitanje, ali se ne spremaju niti koriste u testovima.</li>
<li>Dividende i korporativne akcije osim splitova (Alpaca daje <code>corporate_actions.json</code> samo kao jednokratni uzorak u arhivi).</li>
<li>Kontinuirani futures nizovi s roll-om (nafta, bakar, zlato, srebro).</li>
<li>Povijest EU ETC-ova duža od nekoliko godina i EU UCITS ETF-ovi (4GLD i Xtrackers: IBKR nije dopustio market data).</li>
<li>Opcije, knjiga naloga, makro serije (kamate, inflacija); jedino su u <code>reports/data/</code> ECB tečajevi.</li>
<li>5-minutni podaci za većinu dionica iz AI lanca (postoje samo za MU, WDC, STX, SIMO, RMBS i SMH, GLD, SLV).</li>
</ul>
<h3>Kako osvježiti podatke</h3>
{table(["Skripta", "Što radi"], [
    ["<code>scripts/pull_alpaca.py</code>", "Dionice i ETF-ovi (SIP, split), dnevni, satni, 5-minutni; ne prepisuje postojeće datoteke."],
    ["<code>scripts/pull_crypto_daily.py</code>", "Alpaca kripto USD."],
    ["<code>scripts/pull_binance_klines.py</code>", "Binance USDT dnevni do 1-minutnih."],
    ["<code>scripts/pull_binance_derivs.py</code>", "Funding i 5-minutni metrici."],
    ["<code>scripts/pull_ibkr_history.py</code>", "Izvoz IBKR MCP odgovora (samo čitanje, bez naloga)."],
    ["<code>scripts/validate_data.py</code>", "Provjera prije svakog backtesta; izlaz 1 znači: bez backtesta."],
    ["<code>scripts/data_atlas_scan.py</code>, <code>data_atlas_build.py</code>", "Skeniranje i izrada ove stranice."],
])}
</section>"""


SECTIONS = [
    ("ukratko", "Ukratko", sec_summary), ("karta", "1. Karta", sec_map), ("izvori", "2. Izvori", sec_sources),
    ("ucestalost", "3. Učestalost", sec_freq), ("instrumenti", "4. Instrumenti", sec_tickers),
    ("kripto", "5. Kripto i derivati", sec_crypto_news), ("futuresi", "7. Futuresi", sec_futures),
    ("kvaliteta", "8. Kvaliteta", sec_quality), ("uporaba", "9. Namjena i praznine", sec_use),
]

EXTRA_CSS = """
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:1em 0}
.kpi{border:2px solid var(--accent);border-radius:6px;padding:10px 14px;background:var(--example-bg);font-family:var(--ui-font);display:flex;flex-direction:column;gap:4px;min-width:0}
.kpi b{font-family:var(--hand-font);font-size:2.1rem;color:var(--hand);line-height:1}
.kpi span{font-size:.82rem;color:var(--muted);line-height:1.35}
table.t[data-sort] th{cursor:pointer;user-select:none}
table.t[data-sort] th:after{content:" \\2195";opacity:.4;font-size:.8em}
"""
SORT_JS = """
(function(){document.querySelectorAll('table[data-sort]').forEach(function(t){var ths=t.querySelectorAll('th');ths.forEach(function(th,i){th.addEventListener('click',function(){var tb=t.tBodies[0];var rows=[].slice.call(tb.rows);var dir=th.getAttribute('data-dir')==='asc'?'desc':'asc';ths.forEach(function(x){x.removeAttribute('data-dir');});th.setAttribute('data-dir',dir);function val(r){var s=r.cells[i].textContent.trim().replace(/\\./g,'').replace(',','.').replace(/[^0-9.\\-+]/g,'');var n=parseFloat(s);return isNaN(n)?r.cells[i].textContent.trim():n;}rows.sort(function(a,b){var x=val(a),y=val(b);var r=(typeof x==='number'&&typeof y==='number')?x-y:String(x).localeCompare(String(y),'hr');return dir==='asc'?r:-r;});rows.forEach(function(r){tb.appendChild(r);});});});});})();
"""
IMG_RE = re.compile(r'<img data-chart="([^"]+)" alt="([^"]*)">')


def main() -> int:
    CH.mkdir(parents=True, exist_ok=True)
    for fn in (c01_matrix, c02_gantt, c03_sources, c04_timeframes):
        fn()
    mc.write_captions()
    body = "\n".join(fn() for _, _, fn in SECTIONS)
    used: set[str] = set()

    def sub(m: re.Match[str]) -> str:
        used.add(m.group(1))
        uri, w, h, _ = encode_chart(str(CH / m.group(1)))
        return f'<img src="{uri}" alt="{m.group(2)}" loading="lazy" decoding="async" width="{w}" height="{h}">'

    body = IMG_RE.sub(sub, body)
    toc_items = [(i, t) for i, t, _ in SECTIONS]
    toc_items.insert(6, ("vijesti", "6. Vijesti i arhiva"))
    toc = "".join(f'<li><a href="#{i}">{html.escape(t)}</a></li>' for i, t in toc_items)
    doc = f"""<!DOCTYPE html>
<html lang="hr"><head><meta charset="utf-8"><title>Atlas podataka</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Inter:wght@400;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>{CSS}{EXTRA_CSS}</style></head><body><div class="wrap">
<details class="toc toc-m"><summary>Sadržaj (otvori / zatvori)</summary><nav aria-label="Sadržaj"><ul>{toc}</ul></nav></details>
<div class="layout"><aside class="toc toc-d" aria-label="Sadržaj"><div class="tp">Sadržaj</div><ul>{toc}</ul></aside><main><div class="page">
<div class="topbar"><span>Popis podataka, stanje {dh(LATEST)}. Bez naloga.</span><button type="button" class="theme" aria-label="Promijeni svijetlu i tamnu temu">Svijetlo / tamno</button></div>
<h1>Atlas podataka</h1><p class="sub">Što imamo, odakle dolazi, koliko je često i za koje instrumente. Izmjereno skeniranjem svih datoteka u data/.</p>
{body}
<footer>Skenirano skriptom scripts/data_atlas_scan.py; izvori izvedeni iz skripti za dohvat i bilješki u data/ i reports/data/. Istraživanje, nijedan nalog nije poslan.</footer>
</div></main></div></div><script>{JS}{SORT_JS}</script></body></html>"""
    check = structural_check(doc)
    missing = [n for n in used if not (CH / n).is_file()]
    (DIR / "data_atlas.html").write_bytes(doc.encode("utf-8"))
    rep = {"size_mb": round(len(doc.encode()) / 1048576, 2), "charts": len(used), "missing": missing, "structure": check}
    (DIR / "build_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 1 if check["errors"] or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
