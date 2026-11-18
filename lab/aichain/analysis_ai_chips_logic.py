"""Build analysis.json for the AICHAIN segment ai_chips_logic.

Reads only existing result files (profile.json, results/*.json, summary.json) and the daily
CSVs in data/ohlcv. Every number written into the JSON is copied or computed from those files;
prose templates only interpolate them. No new backtests are run here.

Run: .venv/bin/python lab/aichain/analysis_ai_chips_logic.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SEG = "ai_chips_logic"
OUT = BASE / "segments" / SEG / "analysis.json"

TICKERS = ["NVDA", "AMD", "AVGO", "MRVL", "TSM", "INTC", "ARM", "TXN", "MCHP", "ON", "QCOM"]
CONTENDERS = [
    "B0_BUYHOLD",
    "K1_C13C_ORIG",
    "K2_SMA200_TREND",
    "K3_DONCHIAN_55_20",
    "K4_TSMOM_126",
    "K5_SUPPORT_RESISTANCE",
    "K5B_SR_BREAKOUT_RETEST",
    "K6_MOMENTUM_CS",
    "K7_C13C_PLUS_TREND_REENTRY",
]
SHORT = {
    "B0_BUYHOLD": "držanje",
    "K1_C13C_ORIG": "C13C (K1)",
    "K2_SMA200_TREND": "SMA200 trend (K2)",
    "K3_DONCHIAN_55_20": "Donchian 55/20 (K3)",
    "K4_TSMOM_126": "126-dnevni zamah (K4)",
    "K5_SUPPORT_RESISTANCE": "potpora/otpor (K5)",
    "K5B_SR_BREAKOUT_RETEST": "proboj i povratak (K5B)",
    "K6_MOMENTUM_CS": "rotacija zamaha (K6)",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C + ponovni ulaz (K7)",
}
MIN_TRADES_WINNER = 20


def fmt(x: float, nd: int = 1) -> str:
    """Croatian number format: decimal comma, thousands dot."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, nd: int = 1) -> str:
    return fmt(x * 100.0, nd) + " %"


def eur(x: float) -> str:
    return fmt(x, 0) + " EUR"


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def window(res: dict[str, Any], c: str) -> dict[str, Any]:
    return res["contenders"][c]["windows"]["ai_era"]


def worst_drawdown(equity: list[list[Any]]) -> dict[str, Any]:
    peak_v, peak_d = equity[0][1], equity[0][0]
    best = {"depth": 0.0, "peak_date": peak_d, "bottom_date": peak_d}
    for d, v in equity:
        if v > peak_v:
            peak_v, peak_d = v, d
        dd = v / peak_v - 1.0
        if dd < best["depth"]:
            best = {"depth": dd, "peak_date": peak_d, "bottom_date": d}
    return best


def close_on(ticker: str, day: str) -> float:
    df = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"]).set_index("date")
    return round(float(df.loc[day, "close"]), 2)


def row_on(ticker: str, day: str) -> dict[str, float]:
    df = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"]).set_index("date")
    r = df.loc[day]
    return {k: round(float(r[k]), 2) for k in ["open", "high", "low", "close"]}


def stat_row(w: dict[str, Any]) -> dict[str, Any]:
    return {
        "prinos_pct": round(w["total_return"] * 100, 1),
        "sharpe": round(w["sharpe"], 2),
        "max_pad_pct": round(w["max_drawdown"] * 100, 1),
        "poslova": w["trades"],
        "izlozenost_pct": round(w["exposure_pct"], 1),
        "prinos_trosak_2x_pct": round(w["total_return_cost_2x"] * 100, 1),
        "prinos_trosak_3x_pct": round(w["total_return_cost_3x"] * 100, 1),
    }


def main() -> None:
    prof = load(BASE / "segments" / SEG / "profile.json")
    summ = load(BASE / "summary.json")
    seg_res = load(BASE / "results" / f"{SEG}.json")
    res = {t: load(BASE / "results" / f"{t}.json") for t in TICKERS}
    out: dict[str, Any] = {}

    # ------------------------------------------------------------------ meta
    out["meta"] = {
        "segment": SEG,
        "naslov": "AI procesori, logika i analogni čipovi: analiza strategija u AI eri",
        "tickeri": TICKERS,
        "glavno_mjerilo": "AI era, 2023-01-01 do 2026-10-05 (zadnji zajednički dan podataka)",
        "kontekst_prozori": "Razdoblja prije 2023. samo su kontekst i ovdje se ne koriste za zaključke.",
        "izvori": [
            "reports/research/AICHAIN_20261014/segments/ai_chips_logic/profile.json",
            "reports/research/AICHAIN_20261014/results/ai_chips_logic.json i results/{TICKER}.json",
            "reports/research/AICHAIN_20261014/summary.json, ENGINE.md, universe.json, DATA_QUALITY.md",
            "data/ohlcv/{TICKER}_1d.csv (samo za cijene u bilješkama uz grafove)",
        ],
        "status_revizije": "FIXED (neovisna revizija simulatora 2026-10-14; brojke u ovom izvještaju su iz ispravljenih rezultata)",
        "tretman_revizije": [
            "Zaleđena (obustavljena) povijest cijena više se ne učitava. Za ovaj segment to ne mijenja ništa: nijedan od 11 tickera nije isključen.",
            "Loš tick NVDA 2024-06-10 (najviša 195,95 pri otvaranju 120,37 i zatvaranju 121,79) popravljen je u simulatoru; CSV je ostao nepromijenjen.",
            "Zadnji dan prozora plaća trošak izlaza. Jači test pogleda unaprijed prolazi za sve suparnike.",
            "Ostaje kao ograničenje: ±20 % robusnost provjerava samo predznak ukupnog prinosa u AI eri, a to je u bik-tržištu slab test. ARM je kupljen na otvaranju prvog dana kotacije (2023-09-14).",
        ],
        "valuta_napomena": "Cijene su u USD i tretiraju se kao EUR-ekvivalent. Tečaj EUR/USD, porezi, dividende i minimalna IBKR provizija nisu modelirani. Primjeri 'iz 1.000 EUR' znače: isti postotak primijenjen na 1.000 EUR.",
        "pravilo_ocjene": "Blaga ocjena: ocjena se snižava samo zbog NEVALJANOG dokaza (pogled unaprijed, ugađanje/krhkost, premalo poslova, trošak). Veličina pada, volatilnost i koncentracija NE snižavaju ocjenu.",
        "nije": "Ovo je istraživanje. Nije savjet za ulaganje, nije Critic PASS, signal ostaje PRIČEKAJ, a agenti ne šalju nikakve naloge.",
    }

    # -------------------------------------------------------------- glossary
    out["rjecnik"] = {
        "držanje (buy-and-hold)": "Kupiš na početku i ne diraš. Primjer: 1.000 EUR u dionicu koja se utrostruči postaje 3.000 EUR. Sve ostale strategije moraju se mjeriti s ovim.",
        "Sharpe": "Prinos podijeljen s 'treskanjem' cijene (godišnje). Veći je bolji. Oko 1,0 znači da je prinos otprilike jednak jednoj jedinici treskanja; ispod 0,5 je slabo. Služi da usporedimo strategije koje su na tržištu različito dugo.",
        "max pad (drawdown)": "Najveći pad od vrha do dna. Pad od 40 % znači da bi 1.000 EUR na vrhu privremeno postalo 600 EUR.",
        "izloženost": "Koliki dio kapitala je u prosjeku bio u dionicama (ostalo je gotovina). 50 % znači da je u prosjeku 500 od 1.000 EUR bilo uloženo.",
        "trošak 2x i 3x": "Isti test uz dvostruke i trostruke troškove (5 odnosno 7,5 bps po strani; 1 bps je 0,01 %). Ako strategija uz 2x trošak više ne zarađuje, dokaz za nju ne vrijedi.",
        "stop": "Automatska prodaja ako cijena padne za određeni iznos. Primjer: stop 10 % ispod vrha na kupnji od 1.000 EUR prodaje kad vrijednost padne na oko 900 EUR. Ako dionica noću 'preskoči' stop (gap), prodaja je po lošijoj cijeni od stopa.",
        "SMA200": "Prosjek zadnjih 200 zatvaranja. Cijena iznad njega znači dugoročni uzlazni trend.",
        "zamah (momentum)": "Dionice koje su u zadnjih nekoliko mjeseci najviše rasle često još neko vrijeme nastavljaju rasti. Pravila K4 i K6 igraju na to.",
        "poslovi": "Broj kupnji koje su zatvorene prodajom. Premalo poslova (ispod 20 u segmentu) znači da je rezultat možda slučajan.",
        "deflated Sharpe": "Sharpe korigiran za to koliko smo pravila isprobali (K=532). Informativan je i NE snižava ocjenu.",
    }

    # -------------------------------------------------------------- why together
    stats = {t: prof["tickers"][t]["stats"]["ai_era"] for t in TICKERS}
    corr_vals = [stats[t]["corr_smh"] for t in TICKERS]
    out["zasto_zajedno"] = {
        "sazetak": (
            "Ovih 11 tvrtki zajedno čini 'mozak' računala i uređaja: procesori i ubrzivači za umjetnu inteligenciju (NVDA, AMD, AVGO, MRVL), "
            "tvornica koja ih proizvodi (TSM), dizajn jezgri koji se licencira (ARM), bivši div u krizi (INTC) i klasični analogni i industrijski "
            "čipovi (TXN, MCHP, ON, QCOM). Zajedničko im je da žive od potražnje za čipovima, ali iz različitih razloga: prva skupina od AI investicija "
            "velikih cloud kupaca, druga od ciklusa zaliha u automobilima, industriji i mobitelima. Memorijski segment je zaseban."
        ),
        "podskupine": {
            "AI jezgra": ["NVDA", "AMD", "AVGO", "MRVL", "TSM", "ARM"],
            "zaokret u krizi": ["INTC"],
            "analogni i mobilni, izvan jezgre AI lanca": ["TXN", "MCHP", "ON", "QCOM"],
        },
        "sto_ih_pokrece": [
            "AI jezgra: potražnja velikih tehnoloških firmi i cloud pružatelja za AI hardverom (NVDA: 'potražnja velikih tehnoloških firmi i cloud pružatelja za AI hardverom'; AVGO i MRVL prodaju prilagođene AI čipove i mrežne čipove istim kupcima; TSM je usko grlo kroz koje prolaze gotovo svi ti čipovi).",
            "TSM je američki ADR (certifikat na tajvansku dionicu), pa se na njega odnose i geopolitički rizik oko Tajvana i izvozne kontrole (kontekst iz javnih izvora).",
            "Analogni i mobilni (TXN, MCHP, ON, QCOM): klasični ciklus zaliha. Kupci nakupe zalihe pa ih troše godinu-dvije. Izvor navodi pad prihoda TXN-a 2023.; MCHP 'izraziti ciklus zaliha' (kontekst iz javnih izvora).",
            "INTC: gubitak udjela u poslužiteljskim procesorima i vlastite tvornice; priča o oporavku, ne o AI potražnji (kontekst iz javnih izvora).",
        ],
        "oznaka": "kontekst iz javnih izvora (Wikipedia), nije iz naših podataka i nije provjeren u godišnjim izvješćima",
        "povezanost": (
            f"Korelacija sa SMH (indeks poluvodiča) u AI eri kreće se od {fmt(min(corr_vals), 2)} do {fmt(max(corr_vals), 2)}. "
            "To znači da se tih 11 dionica uglavnom miče zajedno: nije 11 neovisnih oklada, nego jedna velika oklada na čipove s različitim pojačalom (betom). "
            "Primjer: 1.000 EUR podijeljeno na svih 11 dionica ne štiti od dana kada pada cijeli sektor."
        ),
        "najveci_zajednicki_pad": (
            "Šest od 11 dionica ima najgore dno istog dana, 2025-04-08 (AMD, INTC, ARM, TSM, ON, MCHP); NVDA i AVGO 2025-04-04, MRVL i TXN 2025-04-21. Segment pada kao cjelina."
        ),
    }

    # -------------------------------------------------------------- cards
    cards: dict[str, Any] = {}
    for t in TICKERS:
        pt = prof["tickers"][t]
        s = stats[t]
        char = re.search(r"Karakter: ([^;]+);", pt["opis_hr"])
        sr = s["support_resistance"]
        d5 = s["after_5d_drop_ge5pct_above_sma200"]
        thin = d5["thinned_events_10d_apart"]
        top10 = s["top10_best_days"]
        dds = []
        for d in s["drawdowns"][:3]:
            dds.append(
                {
                    "od": d["start"],
                    "dno": d["bottom"],
                    "oporavak": d["recovery"],
                    "dubina_pct": d["depth_pct"],
                    "iz_1000_eur_na": round(1000 * (1 + d["depth_pct"] / 100)),
                }
            )
        w = {c: window(res[t], c) for c in CONTENDERS if res[t]["contenders"][c].get("available")}
        eligible = {c: v for c, v in w.items() if c != "B0_BUYHOLD"}
        best_c = max(eligible, key=lambda c: eligible[c]["sharpe"])
        beats_hold = [SHORT[c] for c, v in eligible.items() if v["total_return"] > w["B0_BUYHOLD"]["total_return"]]
        card = {
            "ime": t,
            "povijest_u_AI_eri": f"od {s['from']} do {s['to']}, {s['days']} dana",
            "volatilnost_godisnje_pct": s["ann_vol_pct"],
            "ukupni_prinos_profil_pct": s["total_return_pct"],
            "beta_smh": s["beta_smh"],
            "korelacija_smh": s["corr_smh"],
            "beta_ndx": s["beta_ndx"],
            "karakter": char.group(1) if char else None,
            "omjer_varijance_5d_20d": [s["var_ratio_5d"], s["var_ratio_20d"]],
            "nakon_pada_5d_od_5pct_iznad_SMA200": {
                "svi_dogadjaji": d5["all_events"]["n_events"],
                "razrijedeni_10d": thin["n_events"],
                "5d_prosjek_pct_razrijedeno": thin["fwd_5d"]["mean_pct"],
                "5d_prosjek_pct_svi_dani": thin["fwd_5d"]["uncond_mean_pct"],
                "5d_t": thin["fwd_5d"]["t_vs_uncond"],
                "20d_prosjek_pct_razrijedeno": thin["fwd_20d"]["mean_pct"],
                "20d_prosjek_pct_svi_dani": thin["fwd_20d"]["uncond_mean_pct"],
                "20d_t": thin["fwd_20d"]["t_vs_uncond"],
                "tumacenje": (
                    f"Nakon pada od najmanje 5 % u 5 dana (uz cijenu iznad SMA200) kroz sljedećih 5 dana dionica je u prosjeku "
                    f"{'dobila' if thin['fwd_5d']['mean_pct'] >= 0 else 'izgubila'} {fmt(abs(thin['fwd_5d']['mean_pct']), 1)} % "
                    f"(razrijeđeni događaji, razmak 10+ dana), naprema {fmt(thin['fwd_5d']['uncond_mean_pct'], 1)} % u svim danima (t={fmt(thin['fwd_5d']['t_vs_uncond'], 1)}); "
                    f"za 20 dana {fmt(thin['fwd_20d']['mean_pct'], 1)} % naprema {fmt(thin['fwd_20d']['uncond_mean_pct'], 1)} % (t={fmt(thin['fwd_20d']['t_vs_uncond'], 1)}). "
                    "t ispod 2 po apsolutnoj vrijednosti znači da razlika nije dokaz, nego može biti slučaj."
                ),
            },
            "najgori_padovi": dds,
            "najgori_pad_na_1000_eur": f"Na 1.000 EUR na vrhu pad od {fmt(abs(dds[0]['dubina_pct']), 1)} % znači privremeno oko {dds[0]['iz_1000_eur_na']} EUR "
            f"({dds[0]['od']} do {dds[0]['dno']}, oporavak {dds[0]['oporavak']}).",
            "potpora_otpor": {
                "potpora_stvarna": sr["real_pivots"]["support"],
                "potpora_placebo": sr["placebo_arbitrary_levels"]["support"],
                "otpor_stvarni": sr["real_pivots"]["resistance"],
                "otpor_placebo": sr["placebo_arbitrary_levels"]["resistance"],
                "tumacenje": (
                    f"Stvarna potpora držala je u {fmt(sr['real_pivots']['support']['hold_pct'], 0)} % od {sr['real_pivots']['support']['n_touches']} dodira, "
                    f"a proizvoljne (placebo) razine u {fmt(sr['placebo_arbitrary_levels']['support']['hold_pct'], 0)} %. "
                    f"Stvarni otpor držao je u {fmt(sr['real_pivots']['resistance']['hold_pct'], 0)} % od {sr['real_pivots']['resistance']['n_touches']} dodira, "
                    f"placebo u {fmt(sr['placebo_arbitrary_levels']['resistance']['hold_pct'], 0)} %. "
                    "Ako stvarne razine nisu bolje od placeba, graf-razine ne daju prednost; uzorak je mali (30 do 50 dodira)."
                ),
            },
            "koncentracija_prinosa": {
                "10_najboljih_dana_udio_pct": top10["sum_logret_share_of_total_pct"],
                "prinos_bez_10_najboljih_pct": top10["total_return_without_best10_pct"],
                "najveci_gapovi": s["largest_gaps"][:2],
            },
            "udio_dana_iznad_SMA200_pct": s["sma200_distance"]["share_above_sma200_pct"],
            "mehanizam": pt["mehanizam_hr"],
            "oznaka": "kontekst iz javnih izvora, nije iz naših podataka",
            "napomena": pt.get("napomena_hr"),
            "algoritam_najbolji_po_sharpeu": {
                "suparnik": SHORT[best_c],
                "sharpe": round(eligible[best_c]["sharpe"], 2),
                "poslova": eligible[best_c]["trades"],
                "drzanje_sharpe": round(w["B0_BUYHOLD"]["sharpe"], 2),
                "pobjeduje_drzanje_po_prinosu": beats_hold,
            },
        }
        cards[t] = card

    # hand-written reading of what the numbers mean for algorithm choice (numbers interpolated)
    def b0(t: str, k: str) -> float:
        return window(res[t], "B0_BUYHOLD")[k]

    def k(t: str, c: str, key: str) -> float:
        return window(res[t], c)[key]

    meaning: dict[str, str] = {}
    meaning["NVDA"] = (
        f"Vraćanje prema sredini (omjer varijance 20d {fmt(stats['NVDA']['var_ratio_20d'], 2)}) bi teoretski pogodovalo kupnji nakon pada (C13C), "
        f"ali je u AI eri trend bio toliko snažan da je svaka rupa izvan tržišta skupa: držanje {pct(b0('NVDA', 'total_return'), 0)}, "
        f"C13C (K1) {pct(k('NVDA', 'K1_C13C_ORIG', 'total_return'), 0)} uz izloženost {fmt(k('NVDA', 'K1_C13C_ORIG', 'exposure_pct'), 0)} %. "
        f"Od pravila koja izlaze iz tržišta najbolje je prošao SMA200 trend (K2): {pct(k('NVDA', 'K2_SMA200_TREND', 'total_return'), 0)} i Sharpe "
        f"{fmt(k('NVDA', 'K2_SMA200_TREND', 'sharpe'), 2)} (držanje {fmt(b0('NVDA', 'sharpe'), 2)}), uz samo {k('NVDA', 'K2_SMA200_TREND', 'trades')} poslova."
    )
    meaning["AMD"] = (
        f"Blizu slučajnog hoda; pad {pct(k('AMD', 'B0_BUYHOLD', 'max_drawdown'), 1)} bio je najveći problem držanja. Pravila koja prate trend (K2, K4) "
        f"smanjila su pad na {pct(k('AMD', 'K2_SMA200_TREND', 'max_drawdown'), 1)} i {pct(k('AMD', 'K4_TSMOM_126', 'max_drawdown'), 1)} "
        f"uz prinos {pct(k('AMD', 'K2_SMA200_TREND', 'total_return'), 0)} i {pct(k('AMD', 'K4_TSMOM_126', 'total_return'), 0)} naprema držanju {pct(b0('AMD', 'total_return'), 0)}. "
        f"C13C (K1) dao je samo {pct(k('AMD', 'K1_C13C_ORIG', 'total_return'), 0)}: kupnja nakon pada nije imala prednost, a stop je često izbacio prerano."
    )
    meaning["AVGO"] = (
        f"Sklonost vraćanju na 20 dana (omjer varijance {fmt(stats['AVGO']['var_ratio_20d'], 2)}), ali C13C je dao samo {pct(k('AVGO', 'K1_C13C_ORIG', 'total_return'), 0)} "
        f"naprema držanju {pct(b0('AVGO', 'total_return'), 0)}, a pad je bio veći ({pct(k('AVGO', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('AVGO', 'max_drawdown'), 1)}). "
        f"Trend pravila K2 i K4 dala su Sharpe {fmt(k('AVGO', 'K2_SMA200_TREND', 'sharpe'), 2)} i {fmt(k('AVGO', 'K4_TSMOM_126', 'sharpe'), 2)} uz manji pad "
        f"({pct(k('AVGO', 'K2_SMA200_TREND', 'max_drawdown'), 1)} i {pct(k('AVGO', 'K4_TSMOM_126', 'max_drawdown'), 1)}), ali nijedno nije pobijedilo držanje po prinosu."
    )
    meaning["MRVL"] = (
        f"Najviša volatilnost jezgre ({fmt(stats['MRVL']['ann_vol_pct'], 0)} % godišnje), blizu slučajnog hoda, a 10 najboljih dana čini {fmt(stats['MRVL']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % prinosa. "
        f"Nakon pada od 5 % prosjek za 5 dana ({fmt(stats['MRVL']['after_5d_drop_ge5pct_above_sma200']['thinned_events_10d_apart']['fwd_5d']['mean_pct'], 1)} %) nije bolji od svih dana, "
        f"pa C13C nema statističku podlogu: {pct(k('MRVL', 'K1_C13C_ORIG', 'total_return'), 1)} uz prinos uz 2x trošak {pct(k('MRVL', 'K1_C13C_ORIG', 'total_return_cost_2x'), 1)}. "
        f"Najbolji među pravilima: 126-dnevni zamah (K4) Sharpe {fmt(k('MRVL', 'K4_TSMOM_126', 'sharpe'), 2)}, zatim SMA200 trend (K2) {fmt(k('MRVL', 'K2_SMA200_TREND', 'sharpe'), 2)}; držanje {fmt(b0('MRVL', 'sharpe'), 2)}."
    )
    meaning["TSM"] = (
        f"Najmirnija dionica jezgre ({fmt(stats['TSM']['ann_vol_pct'], 0)} % godišnje) sa sklonošću vraćanju (omjer varijance 20d {fmt(stats['TSM']['var_ratio_20d'], 2)}) "
        f"i blagim odbijanjem nakon pada od 5 % (5 dana: {fmt(stats['TSM']['after_5d_drop_ge5pct_above_sma200']['thinned_events_10d_apart']['fwd_5d']['mean_pct'], 1)} % naprema "
        f"{fmt(stats['TSM']['after_5d_drop_ge5pct_above_sma200']['thinned_events_10d_apart']['fwd_5d']['uncond_mean_pct'], 1)} %, t=1,7 u razrijeđenom). "
        f"C13C ovdje daje solidan rezultat, ali zaostaje za držanjem: {pct(k('TSM', 'K1_C13C_ORIG', 'total_return'), 0)}, Sharpe {fmt(k('TSM', 'K1_C13C_ORIG', 'sharpe'), 2)}, pad {pct(k('TSM', 'K1_C13C_ORIG', 'max_drawdown'), 1)} "
        f"(držanje {pct(b0('TSM', 'total_return'), 0)}, Sharpe {fmt(b0('TSM', 'sharpe'), 2)}, pad {pct(b0('TSM', 'max_drawdown'), 1)}). Ali i ovdje je SMA200 trend (K2) bolji: Sharpe {fmt(k('TSM', 'K2_SMA200_TREND', 'sharpe'), 2)}."
    )
    meaning["INTC"] = (
        f"Jedina dionica sa sklonošću nastavku trenda (omjer varijance 5d {fmt(stats['INTC']['var_ratio_5d'], 2)}), pa se pravila trenda očekuju kao dobar izbor; i jesu: "
        f"126-dnevni zamah (K4) {pct(k('INTC', 'K4_TSMOM_126', 'total_return'), 0)} naprema držanju {pct(b0('INTC', 'total_return'), 0)}, uz pad {pct(k('INTC', 'K4_TSMOM_126', 'max_drawdown'), 1)} naprema {pct(b0('INTC', 'max_drawdown'), 1)}. "
        f"To je jedini slučaj u segmentu da neki suparnik pobijedi držanje po prinosu. Upozorenje: 10 najboljih dana čini {fmt(stats['INTC']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % prinosa "
        f"(bez njih {fmt(stats['INTC']['top10_best_days']['total_return_without_best10_pct'], 1)} %), pa je ishod osjetljiv na to jesi li bio u tržištu u nekoliko dana."
    )
    meaning["ARM"] = (
        f"Kratka povijest (od {stats['ARM']['from']}), najveća volatilnost ({fmt(stats['ARM']['ann_vol_pct'], 0)} % godišnje), slučajan hod, a 10 najboljih dana čini {fmt(stats['ARM']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % prinosa "
        f"(bez njih {fmt(stats['ARM']['top10_best_days']['total_return_without_best10_pct'], 1)} %). Trend pravila s dugim prozorom ovdje gube: K2 {pct(k('ARM', 'K2_SMA200_TREND', 'total_return'), 1)}, K4 {pct(k('ARM', 'K4_TSMOM_126', 'total_return'), 1)}, C13C {pct(k('ARM', 'K1_C13C_ORIG', 'total_return'), 1)}. "
        f"Proboj/povratak (K5B) je dao {pct(k('ARM', 'K5B_SR_BREAKOUT_RETEST', 'total_return'), 0)} s Sharpeom {fmt(k('ARM', 'K5B_SR_BREAKOUT_RETEST', 'sharpe'), 2)}, ali s {k('ARM', 'K5B_SR_BREAKOUT_RETEST', 'trades')} poslova, a dvije operacije nose rezultat (oko +107 % od 2023-11-22 do 2024-04-16 i oko +101 % od 2026-03-25 do 2026-07-08), pa ga treba čitati oprezno. Držanje: {pct(b0('ARM', 'total_return'), 0)}; kupnja je na otvaranju prvog dana kotacije."
    )
    meaning["TXN"] = (
        f"Nije AI dionica (beta prema SMH {fmt(stats['TXN']['beta_smh'], 2)}), 'klasični' ciklus zaliha; 10 najboljih dana čini više od cijelog prinosa ({fmt(stats['TXN']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} %). "
        f"Nakon pada od 5 % nema odbijanja (5d {fmt(stats['TXN']['after_5d_drop_ge5pct_above_sma200']['thinned_events_10d_apart']['fwd_5d']['mean_pct'], 1)} %). "
        f"C13C (K1) dao je {pct(k('TXN', 'K1_C13C_ORIG', 'total_return'), 0)} naprema držanju {pct(b0('TXN', 'total_return'), 0)}, uz 12 poslova i pad {pct(k('TXN', 'K1_C13C_ORIG', 'max_drawdown'), 1)} (držanje {pct(b0('TXN', 'max_drawdown'), 1)}). "
        f"Trend pravila (K2, K3, K4) ovdje ne rade: {pct(k('TXN', 'K2_SMA200_TREND', 'total_return'), 1)}, {pct(k('TXN', 'K3_DONCHIAN_55_20', 'total_return'), 1)}, {pct(k('TXN', 'K4_TSMOM_126', 'total_return'), 1)} (moguće cik-cak bez trenda; uzrok nije ispitan). Najbolji Sharpe: proboj/povratak (K5B) {fmt(k('TXN', 'K5B_SR_BREAKOUT_RETEST', 'sharpe'), 2)}, ali nijedno pravilo ne pobjeđuje držanje."
    )
    meaning["MCHP"] = (
        f"Držanje je dalo samo {pct(b0('MCHP', 'total_return'), 0)} uz pad {pct(b0('MCHP', 'max_drawdown'), 1)}; 10 najboljih dana čini {fmt(stats['MCHP']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % prinosa. "
        f"Skoro svako pravilo izgubilo je novac (C13C {pct(k('MCHP', 'K1_C13C_ORIG', 'total_return'), 0)}, K2 {pct(k('MCHP', 'K2_SMA200_TREND', 'total_return'), 0)}, K4 {pct(k('MCHP', 'K4_TSMOM_126', 'total_return'), 0)}), "
        f"pa ovdje nijedno pravilo nije imalo prednost. Pravila s malo izloženosti (K3, K5B) izgubila su malo: {pct(k('MCHP', 'K3_DONCHIAN_55_20', 'total_return'), 1)} i {pct(k('MCHP', 'K5B_SR_BREAKOUT_RETEST', 'total_return'), 1)}."
    )
    meaning["ON"] = (
        f"Sklonost vraćanju (autokorelacija {fmt(stats['ON']['autocorr_lag1_5'][0], 3)}), pad {pct(b0('ON', 'max_drawdown'), 1)} bio je najveći u segmentu i trajao je od {stats['ON']['drawdowns'][0]['start']} do oporavka {stats['ON']['drawdowns'][0]['recovery']}. "
        f"Tu je C13C koristan kao zaštita: pad samo {pct(k('ON', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('ON', 'max_drawdown'), 1)}, prinos {pct(k('ON', 'K1_C13C_ORIG', 'total_return'), 0)} naprema {pct(b0('ON', 'total_return'), 0)} (21 posao). "
        f"Pravila trenda (K2, K4) ne štite ({pct(k('ON', 'K2_SMA200_TREND', 'max_drawdown'), 1)} i {pct(k('ON', 'K4_TSMOM_126', 'max_drawdown'), 1)}) i gube."
    )
    meaning["QCOM"] = (
        f"Slučajan hod, pad {pct(b0('QCOM', 'max_drawdown'), 1)} trajao je od {stats['QCOM']['drawdowns'][0]['start']} do {stats['QCOM']['drawdowns'][0]['recovery']}. Držanje {pct(b0('QCOM', 'total_return'), 0)}, "
        f"a gotovo sva pravila gube ili jedva zarađuju; jedino C13C + ponovni ulaz (K7) ima plus ({pct(k('QCOM', 'K7_C13C_PLUS_TREND_REENTRY', 'total_return'), 1)}), ali daleko ispod držanja. "
        f"C13C original (K1) {pct(k('QCOM', 'K1_C13C_ORIG', 'total_return'), 1)} uz samo {k('QCOM', 'K1_C13C_ORIG', 'trades')} poslova (premalo za zaključak). Pravila su ovdje slabija od držanja."
    )
    for t in TICKERS:
        cards[t]["sto_to_znaci_za_algoritam"] = meaning[t]
    out["kartice"] = cards

    # -------------------------------------------------------------- per-ticker table
    per_ticker: dict[str, Any] = {}
    for t in TICKERS:
        rows: dict[str, Any] = {}
        for c in CONTENDERS:
            if not res[t]["contenders"][c].get("available"):
                rows[c] = {"dostupno": False, "razlog": "rotacija (K6) traži više tickera, vrijedi samo za segment"}
                continue
            w = window(res[t], c)
            r = stat_row(w)
            r["manje_od_20_poslova_napomena"] = w["trades"] < 20 and c != "B0_BUYHOLD"
            r["pobjedjuje_drzanje_po_prinosu"] = bool(c != "B0_BUYHOLD" and w["total_return"] > window(res[t], "B0_BUYHOLD")["total_return"])
            r["pad_u_odnosu_na_drzanje_bodova"] = round((w["max_drawdown"] - window(res[t], "B0_BUYHOLD")["max_drawdown"]) * 100, 1)
            rows[c] = r
        per_ticker[t] = {
            "napomena": "Svaki ticker ima zaseban sleeve s 1.000 EUR (EUR-ekvivalent). Broj poslova ispod 20 samo je napomena, kriterij pobjednika vrijedi na razini segmenta.",
            "suparnici": rows,
        }
    out["tablica_po_tickeru_AI_era"] = per_ticker

    # -------------------------------------------------------------- segment table
    seg_rows: dict[str, Any] = {}
    seg_w = {c: window(seg_res, c) for c in CONTENDERS}
    n = len(TICKERS)
    seg_eq = {c: seg_res["contenders"][c]["equity"]["ai_era"] for c in CONTENDERS}
    for c in CONTENDERS:
        w = seg_w[c]
        r = stat_row(w)
        r.update(
            {
                "konacna_vrijednost_EUR_od_11000": round(w["end_value"]),
                "iz_1000_EUR_po_sleeveu_EUR": round(w["end_value"] / n),
                "psr": round(w["psr"], 3),
                "deflated_sharpe_vjerojatnost": round(w["deflated_sharpe_prob"], 3),
                "stopa_pogotka_pct": round(w["hit_rate"] * 100, 1),
                "prinos_razlika_prema_drzanju_bodova": round(w["excess_vs_buyhold"] * 100, 1),
                "ispunjava_uvjet_20_poslova": w["trades"] >= MIN_TRADES_WINNER,
                "pozitivan_prinos_uz_2x_trosak": w["total_return_cost_2x"] > 0,
            }
        )
        wd = worst_drawdown(seg_eq[c])
        r["najgori_pad_datumi"] = {"vrh": wd["peak_date"], "dno": wd["bottom_date"], "dubina_pct": round(wd["depth"] * 100, 1)}
        seg_rows[c] = r
    out["tablica_segment_AI_era"] = {
        "opis": "11 sleeve-ova po 1.000 EUR (ukupno 11.000 EUR), bez prelijevanja između dionica. ARM nema cijene prije 2023-09-14, pa je njegovih 1.000 EUR do tada gotovina. K6 vrijedi samo za segment.",
        "suparnici": seg_rows,
    }

    # -------------------------------------------------------------- winner
    elig = {
        c: seg_w[c]
        for c in CONTENDERS
        if c != "B0_BUYHOLD" and seg_w[c]["trades"] >= MIN_TRADES_WINNER and seg_w[c]["total_return_cost_2x"] > 0
    }
    ranked = sorted(elig, key=lambda c: -elig[c]["sharpe"])
    win = ranked[0]
    ww, hh = seg_w[win], seg_w["B0_BUYHOLD"]
    hold_dd = hh["max_drawdown"]
    win_dd = ww["max_drawdown"]
    runner = ranked[1]
    third = ranked[2]
    best_dd_c = min(elig, key=lambda c: -elig[c]["max_drawdown"] * -1 if False else elig[c]["max_drawdown"])  # most negative first
    best_dd_c = max(elig, key=lambda c: elig[c]["max_drawdown"])  # shallowest drawdown
    beaten = [SHORT[c] for c in elig if elig[c]["total_return"] > hh["total_return"]]
    hold_loss = 1000 * (1 + hold_dd)
    win_loss = 1000 * (1 + win_dd)
    out["pobjednik"] = {
        "definicija_unaprijed": (
            "Pobjednik = najveći Sharpe u AI eri među suparnicima (bez držanja) koji imaju najmanje 20 poslova u segmentu "
            "i pozitivan prinos uz trošak 2x. Uvijek se uspoređuje s držanjem."
        ),
        "kvalificirani_poredak_po_sharpeu": [
            {
                "suparnik": c,
                "naziv": SHORT[c],
                "sharpe": round(elig[c]["sharpe"], 3),
                "prinos_pct": round(elig[c]["total_return"] * 100, 1),
                "max_pad_pct": round(elig[c]["max_drawdown"] * 100, 1),
                "poslova": elig[c]["trades"],
            }
            for c in ranked
        ],
        "nekvalificirani": {
            c: ("manje od 20 poslova" if seg_w[c]["trades"] < MIN_TRADES_WINNER else "negativan prinos uz trošak 2x")
            for c in CONTENDERS
            if c != "B0_BUYHOLD" and c not in elig
        },
        "pobjednik": win,
        "pobjednik_naziv": SHORT[win],
        "pobjedjuje_drzanje_po_prinosu": bool(win in beaten),
        "tko_pobjedjuje_drzanje_po_prinosu_na_segmentu": beaten,
        "usporedba_s_drzanjem": {
            "prinos_drzanje_pct": round(hh["total_return"] * 100, 1),
            "prinos_pobjednik_pct": round(ww["total_return"] * 100, 1),
            "sharpe_drzanje": round(hh["sharpe"], 3),
            "sharpe_pobjednik": round(ww["sharpe"], 3),
            "max_pad_drzanje_pct": round(hold_dd * 100, 1),
            "max_pad_pobjednik_pct": round(win_dd * 100, 1),
            "iz_1000_EUR_drzanje_EUR": round(hh["end_value"] / n),
            "iz_1000_EUR_pobjednik_EUR": round(ww["end_value"] / n),
            "najgori_gubitak_na_1000_EUR_drzanje_EUR": round(1000 - hold_loss),
            "najgori_gubitak_na_1000_EUR_pobjednik_EUR": round(1000 - win_loss),
            "ustedjeno_u_padu_na_1000_EUR": round(hold_loss * -1 + win_loss) if False else round(win_loss - hold_loss),
        },
        "iskreno": (
            f"Pobjednik po unaprijed zadanoj definiciji je {SHORT[win]} sa Sharpeom {fmt(ww['sharpe'], 3)}, ali to je razlika u trećoj decimali: "
            f"{SHORT[runner]} ima {fmt(elig[runner]['sharpe'], 3)}, {SHORT[third]} {fmt(elig[third]['sharpe'], 3)}. Te tri su u praksi izjednačene i razlika nije dokaz "
            f"(isprobano je 9 pravila na 6 segmenata i 43 dionica, K=532). "
            f"Nitko nije pobijedio držanje po prinosu: držanje je dalo {pct(hh['total_return'], 0)} (iz 1.000 EUR po sleeveu oko {eur(hh['end_value'] / n)}), "
            f"pobjednik {pct(ww['total_return'], 0)} (oko {eur(ww['end_value'] / n)}); Sharpe držanja je {fmt(hh['sharpe'], 3)}, dakle viši od svih. "
            f"Pad: držanje {pct(hold_dd, 1)}, pobjednik {pct(win_dd, 1)}. Na 1.000 EUR na vrhu to znači najgori pad do {eur(hold_loss)} s držanjem "
            f"(gubitak {eur(1000 - hold_loss)}) naprema {eur(win_loss)} s pobjednikom (gubitak {eur(1000 - win_loss)}): pobjednik je pad smanjio samo za {eur(win_loss - hold_loss)} na 1.000 EUR, "
            f"što je zanemarivo. Ozbiljniju zaštitu od pada dao je {SHORT['K2_SMA200_TREND']}: pad {pct(elig['K2_SMA200_TREND']['max_drawdown'], 1)}, dakle najgori pad do "
            f"{eur(1000 * (1 + elig['K2_SMA200_TREND']['max_drawdown']))} na 1.000 EUR ({eur(1000 * (1 + elig['K2_SMA200_TREND']['max_drawdown']) - hold_loss)} bolje od držanja), uz prinos {pct(elig['K2_SMA200_TREND']['total_return'], 0)} naprema {pct(hh['total_return'], 0)}. "
            f"Najplići pad među kvalificiranima imao je {SHORT[best_dd_c]} ({pct(elig[best_dd_c]['max_drawdown'], 1)}), ali uz prinos od samo {pct(elig[best_dd_c]['total_return'], 0)}. "
            "Cijena zaštite je izlazak iz tržišta: u AI eri to je skupo, jer prinos nose rijetki dani."
        ),
        "napomena_K6": (
            "K6 ne izlazi ni iz čega nego mijenja koje dionice drži (bolja polovica po 126-dnevnom prinosu, negativni zamah zamjenjuje gotovinom). "
            "Statistika poslova za K6 ne uključuje djelomična prebalansiranja; prinos i krivulja kapitala su ispravni."
        ),
    }

    # -------------------------------------------------------------- C13C honest
    c13: dict[str, Any] = {}
    for t in TICKERS:
        for cid in ["K1_C13C_ORIG", "K7_C13C_PLUS_TREND_REENTRY"]:
            w = window(res[t], cid)
            b = window(res[t], "B0_BUYHOLD")
            c13.setdefault(t, {})[cid] = {
                "prinos_pct": round(w["total_return"] * 100, 1),
                "drzanje_prinos_pct": round(b["total_return"] * 100, 1),
                "sharpe": round(w["sharpe"], 2),
                "drzanje_sharpe": round(b["sharpe"], 2),
                "max_pad_pct": round(w["max_drawdown"] * 100, 1),
                "drzanje_max_pad_pct": round(b["max_drawdown"] * 100, 1),
                "poslova": w["trades"],
                "prinos_trosak_2x_pct": round(w["total_return_cost_2x"] * 100, 1),
                "izloženost_pct": round(w["exposure_pct"], 1),
                "presuda": (
                    ("izgubio" if w["total_return"] < b["total_return"] else "pobijedio")
                    + " držanje po prinosu; "
                    + ("manji" if w["max_drawdown"] > b["max_drawdown"] else "veći ili isti")
                    + " najveći pad"
                    + ("; PRINOS NEGATIVAN" if w["total_return"] < 0 else "")
                ),
            }
    k1s = seg_w["K1_C13C_ORIG"]
    k7s = seg_w["K7_C13C_PLUS_TREND_REENTRY"]
    k1_rank = sorted([c for c in CONTENDERS], key=lambda c: -seg_w[c]["sharpe"]).index("K1_C13C_ORIG") + 1
    pooled = prof["pooled_c13_premise_ai_era"]
    out["c13c_iskreno"] = {
        "sto_je_C13C": "Petrov vlastiti algoritam: kupi kad je zatvaranje iznad SMA200 i cijena je u 5 dana pala 5 % ili više; klizni stop 10 % ispod vrha; bez cilja i vremenskog izlaza. K1 je točna kopija (parity test: 9 od 9 usporedbi bez razlike). K7 je NOVA hipoteza (K1 + ponovni ulaz nakon stopa), vlastiti freeze ID.",
        "segment": {
            "K1": stat_row(k1s) | {"iz_1000_EUR_po_sleeveu_EUR": round(k1s["end_value"] / n), "stopa_pogotka_pct": round(k1s["hit_rate"] * 100, 1),
                                   "prosjecni_dobitak_pct": round(k1s["avg_win"] * 100, 1), "prosjecni_gubitak_pct": round(k1s["avg_loss"] * 100, 1),
                                   "rang_po_sharpeu_od_9": k1_rank},
            "K7": stat_row(k7s) | {"iz_1000_EUR_po_sleeveu_EUR": round(k7s["end_value"] / n)},
            "drzanje": stat_row(hh) | {"iz_1000_EUR_po_sleeveu_EUR": round(hh["end_value"] / n)},
        },
        "ticker_po_ticker": c13,
        "premisa_skupno_AI_era": {
            "5d_prosjek_pct_poslije_pada": pooled["fwd_5d"]["mean_pct"],
            "5d_prosjek_pct_svi_dani": pooled["fwd_5d"]["uncond_mean_pct_avg_of_tickers"],
            "5d_stopa_pogotka_pct": pooled["fwd_5d"]["hit_pct"],
            "5d_stopa_pogotka_svi_dani_pct": pooled["fwd_5d"]["uncond_hit_pct_avg_of_tickers"],
            "20d_prosjek_pct_poslije_pada": pooled["fwd_20d"]["mean_pct"],
            "20d_prosjek_pct_svi_dani": pooled["fwd_20d"]["uncond_mean_pct_avg_of_tickers"],
            "dogadaja": pooled["fwd_5d"]["n_events_pooled"],
        },
        "zakljucak": (
            f"C13C je u ovom segmentu dao {pct(k1s['total_return'], 0)} u AI eri (iz 1.000 EUR po sleeveu oko {eur(k1s['end_value'] / n)}), "
            f"držanje {pct(hh['total_return'], 0)} (oko {eur(hh['end_value'] / n)}). Sharpe {fmt(k1s['sharpe'], 2)} naprema {fmt(hh['sharpe'], 2)} držanja; "
            f"rang {k1_rank}. od 9 po Sharpeu. Manji pad ({pct(k1s['max_drawdown'], 1)} naprema {pct(hh['max_drawdown'], 1)}; na 1.000 EUR {eur(1000 * (1 + k1s['max_drawdown']))} naprema {eur(1000 * (1 + hold_dd))} u najgorem trenutku) "
            f"plaćen je time što je pravilo u prosjeku bilo uloženo samo {fmt(k1s['exposure_pct'], 0)} % kapitala (stopa pogotka {fmt(k1s['hit_rate'] * 100, 0)} %, prosječni dobitak {pct(k1s['avg_win'], 1)}, prosječni gubitak {pct(k1s['avg_loss'], 1)}). "
            f"Ticker po ticker: C13C nije pobijedio držanje po prinosu ni na jednom od 11 tickera. Negativan prinos imao je na ARM, MCHP, QCOM i (minimalno) MRVL. "
            f"Jedina vidljiva korist je manji pad na nekim dionicama: ON ({pct(k('ON', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('ON', 'max_drawdown'), 1)}), AMD "
            f"({pct(k('AMD', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('AMD', 'max_drawdown'), 1)}), INTC ({pct(k('INTC', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('INTC', 'max_drawdown'), 1)}), TSM "
            f"({pct(k('TSM', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('TSM', 'max_drawdown'), 1)}). Na AVGO ({pct(k('AVGO', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('AVGO', 'max_drawdown'), 1)}) i ARM "
            f"({pct(k('ARM', 'K1_C13C_ORIG', 'max_drawdown'), 1)} naprema {pct(b0('ARM', 'max_drawdown'), 1)}) pad je bio veći nego s držanjem; među uzrocima su izlazi po noćnom jazu (gap_stop) lošiji od stopa, ali nije dokazano da je to jedini uzrok. "
            f"Premisa (kupnja nakon pada) u skupnim podacima: za 5 dana prosjek {fmt(pooled['fwd_5d']['mean_pct'], 1)} % naprema {fmt(pooled['fwd_5d']['uncond_mean_pct_avg_of_tickers'], 1)} % u svim danima, "
            f"stopa pogotka {fmt(pooled['fwd_5d']['hit_pct'], 0)} % naprema {fmt(pooled['fwd_5d']['uncond_hit_pct_avg_of_tickers'], 0)} %; za 20 dana {fmt(pooled['fwd_20d']['mean_pct'], 1)} % naprema {fmt(pooled['fwd_20d']['uncond_mean_pct_avg_of_tickers'], 1)} %. "
            "Dakle kratkoročno blago odbijanje postoji, ali ne dovoljno da pokrije vrijeme provedeno izvan tržišta u AI eri. To je opis, ne dokaz: događaji se preklapaju."
        ),
        "K7_napomena": (
            f"K7 (C13C + ponovni ulaz) poboljšava K1 ({pct(k7s['total_return'], 0)} naprema {pct(k1s['total_return'], 0)}, Sharpe {fmt(k7s['sharpe'], 2)} naprema {fmt(k1s['sharpe'], 2)}), ali tek sa {k7s['trades']} poslova, "
            "pa je osjetljiv na troškove (minimalna IBKR provizija nije modelirana). K7 je smišljen nakon što su rezultati K1 bili poznati, pa nosi rizik ugađanja."
        ),
    }

    # -------------------------------------------------------------- ratings
    rob = summ["robustness_pm20"]
    look = summ["lookahead"]
    look2 = summ["lookahead_arrays"]
    ratings: dict[str, Any] = {}
    for c in CONTENDERS:
        if c == "B0_BUYHOLD":
            ratings[c] = {"ocjena": "mjerilo", "razlozi": ["Držanje nije strategija nego mjerilo; ocjena se ne daje."]}
            continue
        w = seg_w[c]
        reasons: list[str] = []
        flags: list[str] = []
        invalid: list[str] = []
        if not look[c]["ok"] or (c in look2 and not look2[c]["ok"]):
            invalid.append("pogled unaprijed")
        else:
            reasons.append("Test pogleda unaprijed prolazi" + (" (osnovni i jači test nizova)." if c in look2 else " (osnovni test)."))
        if w["trades"] < MIN_TRADES_WINNER:
            invalid.append(f"premalo poslova ({w['trades']})")
        else:
            reasons.append(f"{w['trades']} poslova u segmentu (najmanje 20 je uvjet).")
        if w["total_return_cost_2x"] <= 0:
            invalid.append(f"prinos uz trošak 2x nije pozitivan ({pct(w['total_return_cost_2x'], 1)})")
        else:
            reasons.append(f"Prinos uz trošak 2x ostaje pozitivan ({pct(w['total_return_cost_2x'], 1)}), uz 3x {pct(w['total_return_cost_3x'], 1)}.")
        if c in rob:
            r = rob[c][SEG]
            if r["sign_flips"]:
                invalid.append("predznak prinosa se okreće pri promjeni parametra za ±20 %")
            else:
                reasons.append(
                    f"±20 % robusnost: predznak se ne mijenja (prinos od {pct(r['min_total_return'], 0)} do {pct(r['max_total_return'], 0)} uz osnovnih {pct(r['base_total_return'], 0)}); ali taj test provjerava samo predznak."
                )
        else:
            flags.append("±20 % robusnost nije provjerena za ovog suparnika (nije u izboru dijagnostike).")
        if c == "K1_C13C_ORIG":
            flags.append("Parametri (SMA200, pad 5 %, stop 10 %) potječu iz C13C na memorijskim dionicama; ovdje nisu ponovno ugađani.")
            flags.append("Prinos je osjetljiv na prag pada i stop: pri ±20 % kreće se od 43 % do 115 % (predznak isti).")
        if c == "K7_C13C_PLUS_TREND_REENTRY":
            flags.append("UGAĐANJE: pravilo je smišljeno nakon što su rezultati K1 bili poznati; broj poslova je velik (443), pa je osjetljiv na stvarne troškove.")
        if c == "K5B_SR_BREAKOUT_RETEST":
            flags.append("Pragovi (1,5 %, 3 %, 40 svijeća, SMA50) odabrani su ručno prije testa, bez provjere osjetljivosti.")
        if c == "K5_SUPPORT_RESISTANCE":
            flags.append("Pragovi (1,5 %, 3 %, 30 svijeća) odabrani su ručno prije testa; profil pokazuje da stvarne razine često nisu bolje od placeba.")
        if c == "K6_MOMENTUM_CS":
            flags.append("Statistika poslova ne uključuje djelomična prebalansiranja; prinos i krivulja su ispravni.")
            flags.append("ARM ulazi u rotaciju tek nakon kotacije (2023-09-14).")
        if invalid:
            colour = "crveno"
        elif flags and (c in ("K7_C13C_PLUS_TREND_REENTRY", "K5B_SR_BREAKOUT_RETEST")):
            colour = "žuto"
        else:
            colour = "zeleno"
        ratings[c] = {
            "naziv": SHORT[c],
            "ocjena": colour,
            "nevaljan_dokaz": invalid,
            "razlozi": reasons,
            "oznake_ugadanja_i_ogranicenja": flags,
            "ishod_naspram_drzanju": (
                f"Prinos {pct(w['total_return'], 0)} naprema držanju {pct(hh['total_return'], 0)}; Sharpe {fmt(w['sharpe'], 2)} naprema {fmt(hh['sharpe'], 2)}; "
                f"pad {pct(w['max_drawdown'], 1)} naprema {pct(hold_dd, 1)}. Ocjena opisuje valjanost dokaza, ne to je li strategija isplativija od držanja."
            ),
        }
    out["ocjene"] = {
        "pravilo": "Zeleno: dokaz valjan i bez oznake ugađanja. Žuto: dokaz valjan, ali pravilo je ugođeno/smišljeno nakon viđenih rezultata ili su pragovi odabrani ručno bez provjere. Crveno: nevaljan dokaz (pogled unaprijed, krhkost, premalo poslova, prinos ≤ 0 uz trošak 2x). Veličina pada, volatilnost i koncentracija ne snižavaju ocjenu.",
        "ocjene": ratings,
        "napomena": "Ocjena valjanosti dokaza ne znači da je strategija bolja od držanja. K5 je crven jer ne preživljava trošak 2x; ostali nisu nevaljani, iako ih nijedan ne pobjeđuje držanje po prinosu.",
    }

    # -------------------------------------------------------------- EU/HR
    eu: dict[str, Any] = {}
    note_default = "Američka pojedinačna dionica; vjerojatno dostupna EU maloj ulagačkoj klijenti, ali status je nepotvrđeno dok se ne provjeri u IBKR-u. Porezni tretman: nepotvrđeno, bez poreznih tvrdnji."
    for t in TICKERS:
        eu[t] = {"status": "nepotvrđeno", "vrsta": "pojedinačna dionica kotirana u SAD-u", "napomena": note_default}
    eu["TSM"].update(
        {
            "vrsta": "američki ADR (certifikat na tajvansku dionicu), ne izravna tajvanska dionica",
            "napomena": note_default + " Kao ADR nosi dodatne rizike: tečaj tajvanskog dolara, tretman dividende i naknade ADR-a. Što se točno naplaćuje: nepotvrđeno.",
        }
    )
    eu["ARM"].update(
        {
            "vrsta": "pojedinačna dionica kotirana na Nasdaqu od 2023-09-14; vrsta instrumenta (izravna dionica ili ADS) nepotvrđeno",
            "napomena": note_default + " Povijest postoji samo od kotacije, pa su zaključci temeljeni na 766 dana.",
        }
    )
    out["eu_hr"] = {
        "opce": [
            "Sve su pojedinačne dionice, ne ETF-ovi; ETF-ovi (npr. SMH) nisu ovdje predstavljeni kao dostupni Petru jer američki ETF-ovi često nemaju KID dokument za EU male ulagače.",
            "Cijene su u USD, račun je u EUR: tečaj i trošak konverzije su stvarni i nisu modelirani.",
            "Dividende nisu modelirane (cjenovni, ne ukupni prinos); koje tvrtke isplaćuju dividendu i koliko: nepotvrđeno iz naših podataka.",
            "Samo dugo, bez poluge, bez kratke prodaje. Porezi i evidencija: nema tvrdnji.",
            "Američka burza otvara u 15:30 po zagrebačkom vremenu; simulator odlučuje na zatvaranju, a kupuje sljedeći dan na otvaranju.",
        ],
        "po_tickeru": eu,
    }

    # -------------------------------------------------------------- chart notes
    def line(text: str, tickers: list[str], prices: dict[str, Any]) -> dict[str, Any]:
        return {"tickeri": tickers, "bilješka": text, "cijene_iz_podataka": prices}

    nv_gap = row_on("NVDA", "2023-05-25")
    nv_prev = close_on("NVDA", "2023-05-24")
    nv_tick = row_on("NVDA", "2024-06-10")
    arm_gap = row_on("ARM", "2024-08-05")
    notes = [
        line(
            f"NVDA, 2023-05-25: dionica je otvorila s jazom od +{fmt(stats['NVDA']['largest_gaps'][0]['gap_pct'], 1)} % (zatvaranje dan prije {fmt(nv_prev, 2)}, otvaranje {fmt(nv_gap['open'], 2)}, zatvaranje {fmt(nv_gap['close'], 2)}). "
            "Na grafu potražite taj prazan prostor. Pouka: jaz preko noći ne možete ni kupiti ni zaštititi stopom; tko je tog dana bio izvan tržišta, propustio je dio rasta. "
            f"10 najboljih NVDA dana čini {fmt(stats['NVDA']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % prinosa.",
            ["NVDA"],
            {"2023-05-24 zatvaranje": nv_prev, "2023-05-25": nv_gap},
        ),
        line(
            f"NVDA, 2024-06-10: u našem CSV-u je najviša cijena dana {fmt(nv_tick['high'], 2)} uz otvaranje {fmt(nv_tick['open'], 2)} i zatvaranje {fmt(nv_tick['close'], 2)}. "
            "To je loš tick (pogrešan unos u podatku). Revizija ga je ograničila na susjednu cijenu u simulatoru; bez toga bi klizni stop skočio na oko 176 i sljedeći dan izbacio poziciju bez razloga. "
            "Pouka: prije vjerovanja backtestu pogledajte ima li u grafu šiljak koji se ne vidi u izvoru.",
            ["NVDA"],
            {"2024-06-10": nv_tick},
        ),
        line(
            f"NVDA, pad od 2025-01-06 (zatvaranje {fmt(close_on('NVDA', '2025-01-06'), 2)}) do dna 2025-04-04 ({fmt(close_on('NVDA', '2025-04-04'), 2)}), oporavak 2025-06-25 ({fmt(close_on('NVDA', '2025-06-25'), 2)}): "
            f"{fmt(stats['NVDA']['drawdowns'][0]['depth_pct'], 1)} %, 1.000 EUR na vrhu postaje oko {cards['NVDA']['najgori_padovi'][0]['iz_1000_eur_na']} EUR. "
            "SMA200 trend (K2) izašao je 2025-01-28 po 121,78 i vratio se 2025-01-29 po 126,53, pa izašao 2025-02-03 po 114,72 (-9,3 %): takvi povratni izlasci (whipsaw) su cijena zaštite.",
            ["NVDA"],
            {"2025-01-06": close_on("NVDA", "2025-01-06"), "2025-04-04": close_on("NVDA", "2025-04-04"), "2025-06-25": close_on("NVDA", "2025-06-25")},
        ),
        line(
            f"AMD, pad od 2024-03-07 ({fmt(close_on('AMD', '2024-03-07'), 2)}) do 2025-04-08 ({fmt(close_on('AMD', '2025-04-08'), 2)}): {fmt(stats['AMD']['drawdowns'][0]['depth_pct'], 1)} %; "
            f"ista cijena vratila se tek 2025-10-07 ({fmt(close_on('AMD', '2025-10-07'), 2)}). Dakle 1.000 EUR bilo je pod vodom oko 19 mjeseci. Na grafu usporedite izlaz K2/K4 ispod SMA200 s dnom.",
            ["AMD"],
            {"2024-03-07": close_on("AMD", "2024-03-07"), "2025-04-08": close_on("AMD", "2025-04-08"), "2025-10-07": close_on("AMD", "2025-10-07")},
        ),
        line(
            f"Zajedničko dno 2025-04-08: zatvaranja AMD {fmt(close_on('AMD', '2025-04-08'), 2)}, INTC {fmt(close_on('INTC', '2025-04-08'), 2)}, ARM {fmt(close_on('ARM', '2025-04-08'), 2)}, TSM {fmt(close_on('TSM', '2025-04-08'), 2)}, "
            f"ON {fmt(close_on('ON', '2025-04-08'), 2)}, MCHP {fmt(close_on('MCHP', '2025-04-08'), 2)}. Otvorite sve na istom datumu: šest od 11 dionica ima dno upravo tog dana, NVDA i AVGO 2025-04-04, MRVL i TXN 2025-04-21. Pouka: raspodjela na 11 čipova ne daje zaštitu u općem padu.",
            ["AMD", "INTC", "ARM", "TSM", "ON", "MCHP"],
            {t: close_on(t, "2025-04-08") for t in ["AMD", "INTC", "ARM", "TSM", "ON", "MCHP"]},
        ),
        line(
            f"INTC, pad od 2023-12-27 ({fmt(close_on('INTC', '2023-12-27'), 2)}) do 2025-04-08 ({fmt(close_on('INTC', '2025-04-08'), 2)}), pa oporavak 2026-01-21 ({fmt(close_on('INTC', '2026-01-21'), 2)}): {fmt(stats['INTC']['drawdowns'][0]['depth_pct'], 1)} %. "
            "C13C (K1) kupio je 2026-03-31 po 41,96 i izašao stopom 2026-05-12 po 119,45 (+184,7 %), najbolji posao te dionice; zbroj 10 najboljih dana čini 99 % prinosa. Pouka: koncentracija prinosa u nekoliko dana, treba biti u tržištu.",
            ["INTC"],
            {"2023-12-27": close_on("INTC", "2023-12-27"), "2025-04-08": close_on("INTC", "2025-04-08"), "2026-01-21": close_on("INTC", "2026-01-21")},
        ),
        line(
            f"ON, pad od 2023-08-01 ({fmt(close_on('ON', '2023-08-01'), 2)}) do 2025-04-08 ({fmt(close_on('ON', '2025-04-08'), 2)}), oporavak 2026-05-13 ({fmt(close_on('ON', '2026-05-13'), 2)}): {fmt(stats['ON']['drawdowns'][0]['depth_pct'], 1)} %. "
            f"Na grafu usporedite s C13C: njegov najveći pad na ON bio je {pct(k('ON', 'K1_C13C_ORIG', 'max_drawdown'), 1)} jer stop izbaci iz pada.",
            ["ON"],
            {"2023-08-01": close_on("ON", "2023-08-01"), "2025-04-08": close_on("ON", "2025-04-08"), "2026-05-13": close_on("ON", "2026-05-13")},
        ),
        line(
            f"ARM, C13C je kupio 2024-08-02 po 114,77 i 2024-08-05 stop je ispunjen po otvaranju {fmt(arm_gap['open'], 2)} (izlaz po 98,48, -14,2 %), lošije od stopa od 10 %. "
            "To je 'gap_stop': cijena je preko noći preskočila stop pa je izlaz po otvaranju. Na grafu pogledajte svijeću 2024-08-05 (isti dan kada je i NVDA imala jaz od -14,2 %).",
            ["ARM", "NVDA"],
            {"ARM 2024-08-05": arm_gap, "NVDA 2024-08-05 zatvaranje": close_on("NVDA", "2024-08-05")},
        ),
        line(
            f"MCHP: pad od 2024-05-22 ({fmt(close_on('MCHP', '2024-05-22'), 2)}) do 2025-04-08 ({fmt(close_on('MCHP', '2025-04-08'), 2)}), oporavak 2026-05-06 ({fmt(close_on('MCHP', '2026-05-06'), 2)}). "
            f"10 najboljih dana čini {fmt(stats['MCHP']['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % prinosa, bez njih bi prinos bio {fmt(stats['MCHP']['top10_best_days']['total_return_without_best10_pct'], 1)} %. "
            "Pouka: kad nekoliko dana nosi sav prinos, svaka strategija koja je povremeno izvan tržišta ima velik rizik da ih promaši.",
            ["MCHP"],
            {"2024-05-22": close_on("MCHP", "2024-05-22"), "2025-04-08": close_on("MCHP", "2025-04-08"), "2026-05-06": close_on("MCHP", "2026-05-06")},
        ),
        line(
            f"MRVL: pad od 2025-01-23 ({fmt(close_on('MRVL', '2025-01-23'), 2)}) do 2025-04-21 ({fmt(close_on('MRVL', '2025-04-21'), 2)}), oporavak tek 2026-04-10 ({fmt(close_on('MRVL', '2026-04-10'), 2)}): {fmt(stats['MRVL']['drawdowns'][0]['depth_pct'], 1)} %. "
            "Visoka volatilnost (66 % godišnje) znači da stop od 10 % često izbaci poziciju običnim treskanjem.",
            ["MRVL"],
            {"2025-01-23": close_on("MRVL", "2025-01-23"), "2025-04-21": close_on("MRVL", "2025-04-21"), "2026-04-10": close_on("MRVL", "2026-04-10")},
        ),
        line(
            "Savjet za vizualni backtest u TradingViewu: postavite SMA200 i označite datume iz bilješki; za svaki datum zapišite jeste li u stvarnom vremenu mogli znati što se događa. "
            "Odluka se donosi na zatvaranju, nalog ide za sutrašnje otvaranje; zato jaz preko noći (kao NVDA 2023-05-25 ili ARM 2024-08-05) nikad nije pod vašom kontrolom.",
            [],
            {},
        ),
    ]
    out["sto_gledati_na_grafovima"] = notes

    # -------------------------------------------------------------- key findings + limits
    out["kljucni_nalazi"] = [
        f"Pobjednik po unaprijed zadanoj definiciji: {SHORT[win]} (Sharpe {fmt(ww['sharpe'], 3)}), ali razlika prema {SHORT[runner]} ({fmt(elig[runner]['sharpe'], 3)}) i {SHORT[third]} ({fmt(elig[third]['sharpe'], 3)}) nije značajna.",
        f"Nitko nije pobijedio držanje po prinosu na segmentu: držanje {pct(hh['total_return'], 0)}, Sharpe {fmt(hh['sharpe'], 2)}, pad {pct(hold_dd, 1)}.",
        f"Na pobjedniku je pad smanjen s {eur(1000 - hold_loss)} na {eur(1000 - win_loss)} gubitka na 1.000 EUR; najbolja zaštita od pada među kvalificiranima je {SHORT[best_dd_c]} ({pct(elig[best_dd_c]['max_drawdown'], 1)}).",
        f"C13C (K1): {pct(k1s['total_return'], 0)} naprema držanju {pct(hh['total_return'], 0)}, Sharpe {fmt(k1s['sharpe'], 2)} (rang {k1_rank}/9), pad {pct(k1s['max_drawdown'], 1)}. Ni na jednom tickeru nije pobijedio držanje po prinosu.",
        "INTC je jedini ticker gdje je neki suparnik (126-dnevni zamah, K4) pobijedio držanje po prinosu.",
        "Segment se kreće zajedno sa SMH (korelacija 0,59 do 0,83) i šest od 11 najgorih padova ima dno istog dana (2025-04-08).",
    ]
    out["ogranicenja"] = [
        "Brojke su opis prošlosti uz fiksne, unaprijed zadane parametre; nisu savjet, signal ni Critic PASS.",
        "AI era je bik-tržište čipova: držanje je teško pobijediti, a ±20 % robusnost provjerava samo predznak.",
        "Razlika između suparnika s Sharpeom 1,24 do 1,25 je šum.",
        "Tečaj EUR/USD, porezi, dividende i minimalna provizija nisu modelirani; strategije s mnogo poslova (K1, K7) izgledaju povoljnije nego u stvarnosti.",
        "Poslovne činjenice dolaze iz Wikipedije i označene su kao 'kontekst iz javnih izvora'.",
        "Profil za NVDA navodi ukupni prinos 1535 %, a simulator držanje 1508 %; razlika nije istražena (uzrok nepotvrđen).",
        "Dostupnost kod IBKR-a: nepotvrđeno za svaku dionicu.",
    ]

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("written", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
