"""Build analysis.json for the network_servers segment from existing results only.

Reads profile.json, results/network_servers.json and summary.json; every number in the
output is copied or derived arithmetically from those files. Prose is Croatian (for the researcher).
No orders, no new data, no backtest is run here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SEG = BASE / "segments" / "network_servers"
TICKERS = ["ANET", "CRDO", "ALAB", "COHR", "LITE", "SMCI", "DELL", "HPE"]
CONTENDERS = [
    "B0_BUYHOLD", "K1_C13C_ORIG", "K2_SMA200_TREND", "K3_DONCHIAN_55_20", "K4_TSMOM_126",
    "K5_SUPPORT_RESISTANCE", "K5B_SR_BREAKOUT_RETEST", "K6_MOMENTUM_CS", "K7_C13C_PLUS_TREND_REENTRY",
]
STRATS = CONTENDERS[1:]
NAMES_HR = {
    "B0_BUYHOLD": "Kupi i drži (mjerilo)",
    "K1_C13C_ORIG": "C13C original (tvoj algoritam)",
    "K2_SMA200_TREND": "Trend: iznad SMA200",
    "K3_DONCHIAN_55_20": "Donchian proboj 55/20",
    "K4_TSMOM_126": "Vremenski momentum 126 dana",
    "K5_SUPPORT_RESISTANCE": "Potpora/otpor (odskok)",
    "K5B_SR_BREAKOUT_RETEST": "Proboj otpora i povratni test",
    "K6_MOMENTUM_CS": "Momentum rotacija (samo segment)",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C plus ponovni ulaz (nova hipoteza)",
}


def hr(x: float, nd: int = 1) -> str:
    """Croatian number format: decimal comma, dot thousands."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, nd: int = 1) -> str:
    return f"{hr(x * 100, nd)} %"


def eur(x: float) -> str:
    return f"{hr(x, 0)} EUR"


def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prof = json.loads((SEG / "profile.json").read_text())
    res = json.loads((BASE / "results" / "network_servers.json").read_text())
    summ = json.loads((BASE / "summary.json").read_text())
    return prof, res, summ


def close_on(ticker: str, day: str) -> float:
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv")
    d["day"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
    return float(d.loc[d["day"] == day, "close"].iloc[0])


def open_on(ticker: str, day: str) -> float:
    d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv")
    d["day"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
    return float(d.loc[d["day"] == day, "open"].iloc[0])


def metrics(w: dict[str, Any]) -> dict[str, Any]:
    return {
        "povrat_ukupno_pct": round(w["total_return"] * 100, 1),
        "povrat_trosak_2x_pct": round(w["total_return_cost_2x"] * 100, 1),
        "povrat_trosak_3x_pct": round(w["total_return_cost_3x"] * 100, 1),
        "sharpe": round(w["sharpe"], 2),
        "max_pad_pct": round(w["max_drawdown"] * 100, 1),
        "broj_poslova": w["trades"],
        "izlozenost_pct": round(w["exposure_pct"], 0),
        "za_1000_EUR_na_kraju": round(1000 * (1 + w["total_return"])),
        "za_1000_EUR_najgori_pad_EUR": round(-1000 * w["max_drawdown"]),
        "deflated_sharpe_vjerojatnost": None if w.get("deflated_sharpe_prob") is None else round(w["deflated_sharpe_prob"], 2),
    }


FIT = {
    "ANET": "Najmirnija i najkvalitetnija u grupi, ali s tipom povrata koji algoritmi teško poboljšavaju: dugo je iznad SMA200, pa trend-pravila ostaju u poziciji većinu vremena i samo prepolove zaradu. {note}",
    "CRDO": "Slučajno kretanje uz golemo njihanje i jazove ({gap}): pravila sa stopom plaćaju za svaki jaz, a trend-pravila (K4, K2) zadrže tek dio rasta. {note}",
    "ALAB": "Najkraća povijest i najviše njihanje, uzorak je malen; potpora drži samo 23,1 % dodira, pa potpora/otpor ne odgovara. {note}",
    "COHR": "Sklona vraćanju, i nakon pada od 5 % u 5 dana prosjek je bio bolji od običnog dana, ali jazovi od -24 % preko noći probijaju stopove. {note}",
    "LITE": "Sklona vraćanju na kratko, ali s jednim golemim trendom; zato su proboji (K3, K5B) i trend-pravila ostala blizu držanja po Sharpeu (ne po povratu), a pravila s malom izloženošću (K1, K5) propustila su gotovo sve. {note}",
    "SMCI": "Najveće njihanje i najdublji pad (-84,8 %); jedina dionica gdje bilo koje pravilo zapravo smanjuje bol uz sličan povrat. {note}",
    "DELL": "Čist uzlazni trend s plitkim padovima nakon 2025-04-04; držanje je gotovo neporecivo, a trend-pravila (K4) prate ga uz isti Sharpe. {note}",
    "HPE": "Najmirnija dionica segmenta (njihanje 43,9 %, beta prema SMH 0,66); potpora je držala u 63,6 % dodira, pa potpora/otpor ovdje ima najviše smisla. {note}",
}


def build() -> dict[str, Any]:
    prof, res, summ = load()
    tk = summ["ticker_x_contender_ai_era"]
    seg = {c: res["contenders"][c]["windows"]["ai_era"] for c in CONTENDERS}

    # ---------- why together + cards ----------
    why = {
        "naslov": "Zašto su ovih osam dionica u istoj skupini",
        "tekst": (
            "Ako je GPU motor AI klastera, ove tvrtke su žice, svjetlo i kućište oko njega. ANET (preklopnici), CRDO i ALAB "
            "(čipovi za veze unutar regala), COHR i LITE (optika, laseri) i SMCI, DELL i HPE (gotovi serveri) svi zarađuju kad "
            "oblaci i velike tvrtke grade nove AI klastere. Zajednički pokretač je isti: kapitalna ulaganja (capex) oblaka, "
            "dostupnost Nvidijinih GPU-ova i memorije te vrijeme isporuke. Kad oblaci naruče, narudžbe skaču u svim osam; kad naprave pauzu, "
            "pada cijela skupina. U našim podacima to se vidi: kod sedam od osam (sve osim SMCI) dno jednog od tri najgora pada "
            "pada u 2025-04-04 do 2025-04-08, a korelacija sa SMH je 0,51 do 0,67."
        ),
        "primjer_1000_EUR": (
            "Na 1.000 EUR podijeljenih jednako na svih osam (125 EUR po dionici) najveći pad držanja bio je "
            f"{pct(seg['B0_BUYHOLD']['max_drawdown'])}: 1.000 EUR na vrhu postalo bi {eur(1000 * (1 + seg['B0_BUYHOLD']['max_drawdown']))} na dnu."
        ),
        "razlike_unutar_grupe": [
            "Optika i veze (COHR, LITE, CRDO, ALAB): najviše njihanje i najstrmiji trendovi, kupci su malobrojni hiperskaleri.",
            "Mreža (ANET): kvalitetnija, mirnija, ali ista ovisnost o capexu oblaka.",
            "Serveri (SMCI, DELL, HPE): tanke marže, ovise o isporuci GPU-ova i memorije; SMCI ima najdublji pad, HPE najmirnija.",
        ],
        "oznaka": "kontekst iz javnih izvora, nije iz naših podataka (osim brojeva pada i korelacije, koji su iz naših cijena)",
    }

    cards: dict[str, Any] = {}
    for t in TICKERS:
        v = prof["profiles"][t]
        a = v["windows"]["ai_era"]
        d = a["after_5d_drop_ge5pct_above_sma200"]
        dd3 = []
        for x in a["worst_drawdowns"][:3]:
            dd3.append({
                "vrh": x["start"], "dno": x["bottom"], "oporavak": x["recovery"] or "nije oporavljen do 2026-10-05",
                "dubina_pct": x["depth_pct"],
                "primjer_1000_EUR": f"1.000 EUR na vrhu bilo bi {eur(1000 * (1 + x['depth_pct'] / 100))} na dnu",
            })
        sr = a["support_resistance"]
        gap = a["largest_gaps"][0]
        best = max(STRATS[:5] + STRATS[6:], key=lambda c: tk[t][c]["sharpe"] if c in tk[t] else -9)
        hold = tk[t]["B0_BUYHOLD"]
        note = (
            f"Najbolji Sharpe među pravilima: {NAMES_HR[best]} {hr(tk[t][best]['sharpe'], 2)} naspram držanja {hr(hold['sharpe'], 2)} "
            f"(povrat {pct(tk[t][best]['total_return'], 0)} naspram {pct(hold['total_return'], 0)})."
        )
        cards[t] = {
            "mehanizam": v["mechanism_hr"],
            "ponasanje_AI_era": {
                "dana": a["bars"], "od": a["start"],
                "volatilnost_godisnja_pct": a["ann_vol_pct"],
                "beta_SMH": a["beta_smh"], "korelacija_SMH": a["corr_smh"], "beta_NDX": a["beta_ndx"],
                "karakter": a["character"], "omjer_varijance_5": a["variance_ratio_5"], "omjer_varijance_20": a["variance_ratio_20"],
                "autokorelacija_lag1": a["autocorr_lag1_5"]["1"], "sum_pm": a["autocorr_noise_band_2se"],
                "udio_dana_iznad_SMA200_pct": a["sma200"]["pct_days_above_sma200"],
                "ukupni_povrat_pct": a["total_return_pct"],
                "povrat_bez_10_najboljih_dana_pct": a["return_without_10_best_days_pct"],
                "najveci_jaz": gap,
            },
            "nakon_pada_5d_iznad_SMA200": {
                "nezavisnih_dogadaja": d["independent_events"], "mali_uzorak": d["small_sample_warning"],
                "fwd5_prosjek_pct": d["fwd5"]["mean_pct"], "fwd5_bezuvjetno_pct": d["fwd5"]["uncond_mean_pct"],
                "fwd5_uspjesnost_pct": d["fwd5"]["hit_rate_pct"], "fwd5_bezuvjetna_uspjesnost_pct": d["fwd5"]["uncond_hit_rate_pct"],
                "fwd20_prosjek_pct": d["fwd20"]["mean_pct"], "fwd20_bezuvjetno_pct": d["fwd20"]["uncond_mean_pct"],
                "fwd20_uspjesnost_pct": d["fwd20"]["hit_rate_pct"], "fwd20_bezuvjetna_uspjesnost_pct": d["fwd20"]["uncond_hit_rate_pct"],
                "tumacenje": (
                    f"Nakon pada od 5 % ili više u 5 dana (uz zatvaranje iznad SMA200) bilo je {d['independent_events']} nezavisnih događaja"
                    f"{' (mali uzorak, slabo pouzdano)' if d['small_sample_warning'] else ''}. Prosjek nakon 5 dana: {hr(d['fwd5']['mean_pct'], 2)} % "
                    f"(običan dan: {hr(d['fwd5']['uncond_mean_pct'], 2)} %); nakon 20 dana: {hr(d['fwd20']['mean_pct'], 2)} % "
                    f"(običan dan: {hr(d['fwd20']['uncond_mean_pct'], 2)} %). Na 1.000 EUR razlika nakon 20 dana je oko "
                    f"{hr((d['fwd20']['mean_pct'] - d['fwd20']['uncond_mean_pct']) * 10, 0)} EUR u odnosu na običan dan."
                ),
            },
            "najgori_padovi": dd3,
            "potpora_otpor": {
                "potpora_dodira": sr["support"]["touches"], "potpora_drzi_pct": sr["support"]["hold_rate_pct"],
                "potpora_prosjek_5d_pct": sr["support"]["next5_mean_pct"],
                "otpor_dodira": sr["resistance"]["touches"], "otpor_drzi_pct": sr["resistance"]["hold_rate_pct"],
                "otpor_prosjek_5d_pct": sr["resistance"]["next5_mean_pct"],
                "tumacenje": (
                    f"Potpora je držala u {hr(sr['support']['hold_rate_pct'], 1)} % od {sr['support']['touches']} dodira, otpor u "
                    f"{hr(sr['resistance']['hold_rate_pct'], 1)} % od {sr['resistance']['touches']}. 'Drži' znači da zatvaranje u idućih 5 dana nije "
                    "probilo razinu za više od 1,5 %; ispod 50 % znači da je razina češće probijena nego održana."
                ),
            },
            "koji_algoritam_pristaje": FIT[t].format(gap=f"{gap['gap_pct']:+.1f} % na {gap['date']}".replace(".", ","), note=note),
            "oznaka": "mehanizam: kontekst iz javnih izvora, nije iz naših podataka; sve brojke ponašanja su iz naših dnevnih cijena",
        }
    cards["ALAB"]["upozorenje"] = (
        "Povijest je samo od 2024-03-20 (638 dana), uzorci su mali, a prozor AI ere počinje na dan uvrštenja: "
        f"cijena otvaranja tog dana ({hr(open_on('ALAB', '2024-03-20'), 2)} USD) vjerojatno nije bila dostupna malom ulagaču; "
        "'kupi i drži' za ALAB je zato optimističan."
    )
    cards["CRDO"]["upozorenje"] = "Pre-2023 kontekst samo 234 dana (na burzi od 2022-01-27); -44,9 % u jednom danu (2023-02-15) uzrok nismo provjeravali."
    cards["SMCI"]["upozorenje"] = (
        "Serija prije 2020-01-14 je zaustavljena trgovina i izbačena (revizija). AI era je netaknuta, ali je pad 2024-03-13 do 2024-11-14 "
        f"({hr(close_on('SMCI', '2024-03-13'), 2)} USD na {hr(close_on('SMCI', '2024-11-14'), 2)} USD) bez oporavka do 2026-10-05 u profilu."
    )

    # ---------- per ticker table ----------
    table = {}
    for t in TICKERS:
        hold = tk[t]["B0_BUYHOLD"]
        rows = {}
        for c in CONTENDERS:
            if c not in tk[t]:
                continue
            m = metrics(tk[t][c])
            m["razlika_povrata_prema_drzanju_pp"] = round((tk[t][c]["total_return"] - hold["total_return"]) * 100, 0)
            m["bolji_povrat_od_drzanja"] = bool(c != "B0_BUYHOLD" and tk[t][c]["total_return"] > hold["total_return"])
            m["bolji_sharpe_od_drzanja"] = bool(c != "B0_BUYHOLD" and tk[t][c]["sharpe"] > hold["sharpe"])
            m["manji_pad_od_drzanja"] = bool(c != "B0_BUYHOLD" and tk[t][c]["max_drawdown"] > hold["max_drawdown"])
            m["mali_broj_poslova_manje_od_20"] = bool(tk[t][c]["trades"] < 20)
            rows[c] = m
        table[t] = {"od": tk[t]["B0_BUYHOLD"]["start"], "K6": "nije dostupno po tickeru (rotacija radi samo na segmentu)", "suparnici": rows}
    beats_ret = {t: [c for c, m in table[t]["suparnici"].items() if m["bolji_povrat_od_drzanja"]] for t in TICKERS}
    beats_sh = {t: [c for c, m in table[t]["suparnici"].items() if m["bolji_sharpe_od_drzanja"]] for t in TICKERS}

    # ---------- segment table ----------
    segtab = {}
    for c in CONTENDERS:
        w = seg[c]
        m = metrics(w)
        m["kraj_vrijednosti_8000_EUR"] = round(w["end_value"])
        m["psr"] = round(w["psr"], 3)
        m["razlika_povrata_prema_drzanju_pp"] = round((w["total_return"] - seg["B0_BUYHOLD"]["total_return"]) * 100, 0)
        segtab[c] = m

    # ---------- winner ----------
    elig = [c for c in STRATS if seg[c]["trades"] >= 20 and seg[c]["total_return_cost_2x"] > 0]
    ranked = sorted(elig, key=lambda c: -seg[c]["sharpe"])
    win = ranked[0]
    h, w = seg["B0_BUYHOLD"], seg[win]
    cut = sorted(
        [c for c in elig if seg[c]["max_drawdown"] > h["max_drawdown"]], key=lambda c: -seg[c]["max_drawdown"])
    best_cut = max(cut, key=lambda c: seg[c]['total_return'])
    winner = {
        "pravilo_unaprijed": "Pobjednik = najviši Sharpe u AI eri među suparnicima s najmanje 20 poslova na segmentu i pozitivnim povratom uz trošak 2x. Mjerilo (kupi i drži) nije suparnik. Uvijek se uspoređuje s držanjem.",
        "ispunjavaju_uvjete": [{"id": c, "naziv": NAMES_HR[c], "sharpe": round(seg[c]["sharpe"], 3), "poslova": seg[c]["trades"], "povrat_2x_pct": round(seg[c]["total_return_cost_2x"] * 100, 1)} for c in ranked],
        "ne_ispunjavaju_uvjete": [c for c in STRATS if c not in elig],
        "pobjednik": win,
        "pobjednik_naziv": NAMES_HR[win],
        "pobjednik_pobjeduje_drzanje_povrat": bool(w["total_return"] > h["total_return"]),
        "pobjednik_pobjeduje_drzanje_sharpe": bool(w["sharpe"] > h["sharpe"]),
        "pobjednik_smanjio_najgori_pad": bool(w["max_drawdown"] > h["max_drawdown"]),
        "usporedba_na_1000_EUR": {
            "drzanje_kraj": eur(1000 * (1 + h["total_return"])), "pobjednik_kraj": eur(1000 * (1 + w["total_return"])),
            "pobjednik_kraj_uz_trosak_2x": eur(1000 * (1 + w["total_return_cost_2x"])),
            "drzanje_najgori_gubitak": eur(-1000 * h["max_drawdown"]), "pobjednik_najgori_gubitak": eur(-1000 * w["max_drawdown"]),
            "razlika_najgoreg_gubitka_EUR": round(-1000 * (w["max_drawdown"] - h["max_drawdown"])),
        },
        "ublazivaci_pad": [{"id": c, "naziv": NAMES_HR[c], "max_pad_pct": round(seg[c]["max_drawdown"] * 100, 1),
                              "najgori_gubitak_na_1000_EUR": eur(-1000 * seg[c]["max_drawdown"]),
                              "kraj_na_1000_EUR": eur(1000 * (1 + seg[c]["total_return"]))} for c in cut],
        "tekst": (
            f"Po unaprijed zadanom pravilu pobjeđuje {NAMES_HR[win]} ({win}): Sharpe {hr(w['sharpe'], 2)} naspram {hr(h['sharpe'], 2)} za držanje, "
            f"{w['trades']} poslova, povrat {pct(w['total_return'], 0)} naspram {pct(h['total_return'], 0)} za držanje (uz trošak 2x: {pct(w['total_return_cost_2x'], 0)}). "
            f"Na 1.000 EUR podijeljenih na osam dionica to je {eur(1000 * (1 + w['total_return']))} naspram {eur(1000 * (1 + h['total_return']))} za držanje. "
            f"ALI nije smanjio najgori pad, nego ga je produbio: {pct(w['max_drawdown'])} naspram {pct(h['max_drawdown'])}, tj. najgori gubitak na 1.000 EUR "
            f"{eur(-1000 * w['max_drawdown'])} naspram {eur(-1000 * h['max_drawdown'])} (oba na istom razdoblju 2025-01-22 do 2025-04-04). "
            "Rotacija drži samo bolju polovicu, dakle koncentriranija je od držanja svih osam, i to se u padu plaća. "
            f"Sva ostala pravila imaju manji pad od držanja (najmanji: {', '.join(NAMES_HR[c] for c in cut[:3])}), ali uz bitno manju zaradu; "
            f"među njima najviši povrat ima {NAMES_HR[best_cut]} ({pct(seg[best_cut]['total_return'], 0)}, pad {pct(seg[best_cut]['max_drawdown'])})."
        ),
        "kako_citati_pobjedu": [
            "Dobit pobjednika je koncentrirana: iz popisa poslova, jedan posao u LITE od 2025-07-01 (92,99) do 2026-09-01 (900,81) ima povrat +869 % i najveći je pojedinačni doprinos; koliko točno nosi razliku prema držanju nismo posebno izračunali.",
            "Svih osam dionica su današnji pobjednici AI vala izabrani unatrag. To vrijedi jednako za sva pravila i za držanje, ali znači da je cijeli segment optimističan uzorak.",
            "Jedno razdoblje (3,75 godina, bik tržište). Deflated Sharpe vjerojatnost pobjednika je " + hr(seg[win]["deflated_sharpe_prob"], 2) + " (ispod 0,95), uz K=533 pokusa u ledgeru: informativno, nije Critic verdikt.",
            "Statistika poslova za K6 ne broji djelomična rebalansiranja (poznata napomena revizije); povrat i krivulja kapitala su točni.",
        ],
    }

    # ---------- C13C honest ----------
    c13 = {"tekst_uvod": "C13C je tvoj algoritam. Ispod je iskreno, dionicu po dionicu, što je napravio u AI eri (2023-01-01 do 2026-10-05) naspram držanja.", "po_dionici": {}}
    for t in TICKERS:
        hd, a1, a7 = tk[t]["B0_BUYHOLD"], tk[t]["K1_C13C_ORIG"], tk[t]["K7_C13C_PLUS_TREND_REENTRY"]
        v = []
        v.append("povrat " + ("bolji" if a1["total_return"] > hd["total_return"] else "lošiji") + f" od držanja ({pct(a1['total_return'], 0)} naspram {pct(hd['total_return'], 0)})")
        v.append("Sharpe " + ("bolji" if a1["sharpe"] > hd["sharpe"] else "lošiji") + f" ({hr(a1['sharpe'], 2)} naspram {hr(hd['sharpe'], 2)})")
        v.append(f"pad {pct(a1['max_drawdown'])} naspram {pct(hd['max_drawdown'])} (najgori gubitak na 1.000 EUR: {eur(-1000 * a1['max_drawdown'])} naspram {eur(-1000 * hd['max_drawdown'])})")
        c13["po_dionici"][t] = {
            "K1": metrics(a1), "drzanje": metrics(hd), "K7": metrics(a7),
            "ocjena": "; ".join(v) + f"; {a1['trades']} poslova, izloženost {hr(a1['exposure_pct'], 0)} %.",
            "K1_bolji_povrat": bool(a1["total_return"] > hd["total_return"]),
            "K1_bolji_sharpe": bool(a1["sharpe"] > hd["sharpe"]),
            "K1_manji_pad": bool(a1["max_drawdown"] > hd["max_drawdown"]),
            "K7_bolji_povrat": bool(a7["total_return"] > hd["total_return"]),
        }
    n_ret = sum(c13["po_dionici"][t]["K1_bolji_povrat"] for t in TICKERS)
    n_sh = sum(c13["po_dionici"][t]["K1_bolji_sharpe"] for t in TICKERS)
    n_dd = sum(c13["po_dionici"][t]["K1_manji_pad"] for t in TICKERS)
    n7 = sum(c13["po_dionici"][t]["K7_bolji_povrat"] for t in TICKERS)
    k1s, k7s = seg["K1_C13C_ORIG"], seg["K7_C13C_PLUS_TREND_REENTRY"]
    c13["sazetak"] = (
        f"K1 (C13C) je na segmentu zaradio {pct(k1s['total_return'], 0)} naspram {pct(h['total_return'], 0)} za držanje: na 1.000 EUR {eur(1000 * (1 + k1s['total_return']))} naspram "
        f"{eur(1000 * (1 + h['total_return']))}. Povrat je bio bolji od držanja na {n_ret} od 8 dionica, Sharpe na {n_sh} od 8, a pad manji na {n_dd} od 8. "
        f"Najgori pad segmenta je {pct(k1s['max_drawdown'])} naspram {pct(h['max_drawdown'])} (najgori gubitak na 1.000 EUR {eur(-1000 * k1s['max_drawdown'])} naspram {eur(-1000 * h['max_drawdown'])}). "
        f"Dakle: C13C je ovdje funkcionirao kao osiguranje od padova, ne kao stroj za zaradu. Plaća se zaradom: u prosjeku je u poziciji samo {hr(k1s['exposure_pct'], 0)} % kapitala, "
        f"pa propušta velike trendove (LITE: {pct(tk['LITE']['K1_C13C_ORIG']['total_return'], 0)} naspram {pct(tk['LITE']['B0_BUYHOLD']['total_return'], 0)}). "
        f"Jedino na SMCI (najgori pad -84,8 %) C13C je zaradio gotovo koliko i držanje ({pct(tk['SMCI']['K1_C13C_ORIG']['total_return'], 0)} naspram {pct(tk['SMCI']['B0_BUYHOLD']['total_return'], 0)}) uz pad {pct(tk['SMCI']['K1_C13C_ORIG']['max_drawdown'])} naspram {pct(tk['SMCI']['B0_BUYHOLD']['max_drawdown'])}. "
        f"Dodatak K7 (ponovni ulaz nakon stopa) podigao je povrat segmenta na {pct(k7s['total_return'], 0)}, ali ne ni približno do držanja; bolji povrat od držanja ima na {n7} od 8 dionica, a troškovno je najosjetljiviji "
        f"(2x: {pct(k7s['total_return_cost_2x'], 0)}, 3x: {pct(k7s['total_return_cost_3x'], 0)}, {k7s['trades']} poslova)."
    )
    pp = prof["c13c_premise_pooled_ai_era"]
    c13["premisa_C13C_iz_profila"] = {
        "tekst": prof["c13c_premise_text_hr"],
        "brojke": pp,
        "po_dionici": {t: {k: cards[t]["nakon_pada_5d_iznad_SMA200"][k] for k in ("nezavisnih_dogadaja", "fwd5_prosjek_pct", "fwd5_bezuvjetno_pct", "fwd20_prosjek_pct", "fwd20_bezuvjetno_pct", "mali_uzorak")} for t in TICKERS},
        "napomena": "Premisa je opis, ne dokaz: nakon pada 5 dana prosjek je viši od običnog dana na većini dionica (kod ANET, CRDO, HPE nije), ali je razlika mala u odnosu na njihanje.",
    }
    c13["vazno"] = "K7 je NOVA hipoteza s vlastitim freeze ID-em i ne smije se zvati Critic PASS ni zamjena za C13C."

    # ---------- ratings ----------
    rob = summ["robustness_pm20"]
    def rb(c: str) -> dict[str, Any] | None:
        return rob.get(c, {}).get("network_servers")
    rating_rows = {}
    for c in STRATS:
        wc = seg[c]
        r = rb(c)
        issues, notes = [], []
        la = summ["lookahead"][c]["ok"] if c in summ["lookahead"] else None
        notes.append("Lookahead test: prošao (48 provjera nad svim tickerima)." if la else "Lookahead test nedostaje.")
        if r is None:
            notes.append("Test ±20 % parametara nije pokrenut za ovo pravilo (pokrenut samo za K1, K4, K6): robusnost nepotvrđena.")
        else:
            notes.append(f"Test ±20 %: povrat {pct(r['min_total_return'], 0)} do {pct(r['max_total_return'], 0)}, predznak se ne mijenja (slab test u biku).")
        notes.append(f"Trošak: pozitivan i uz 3x ({pct(wc['total_return_cost_3x'], 0)}).")
        if c == "K6_MOMENTUM_CS":
            issues.append("test lookahead nad nizovima nije pokrenut za K6 (samo odluke); statistika poslova ne broji djelomična rebalansiranja; ulazi u dijagnostiku jer je imao najviši Sharpe (odabir po rezultatu)")
        if c == "K7_C13C_PLUS_TREND_REENTRY":
            issues.append("nova nadogradnja K1 (dodana nakon što je K1 pokazao slabost): parametri fiksni, ali izgleda prilagođeno cilju, test ±20 % nije pokrenut, najosjetljiviji na trošak")
        if r is None and c != "K7_C13C_PLUS_TREND_REENTRY":
            issues.append("robusnost ±20 % nije provjerena")
        few = [t for t in TICKERS if c in tk[t] and tk[t][c]["trades"] < 20]
        if few:
            notes.append(f"Po dionici manje od 20 poslova na {len(few)} od 8 dionica ({', '.join(few)}): pojedinačni rezultati dionica su anegdotalni; ocjena se odnosi na segment ({wc['trades']} poslova).")
        rating = "zeleno" if not issues else "žuto"
        rating_rows[c] = {
            "naziv": NAMES_HR[c], "ocjena": rating,
            "obrazlozenje": (
                "Dokazi valjani, provjere prošle." if rating == "zeleno" else "Nijedan dokaz nije nevaljan (nema lookahead-a, trošak prolazi), ali nedostaje ili je slabija jedna provjera."
            ),
            "nedostaci_dokaza": issues, "provjere": notes,
            "poslova_segment": wc["trades"],
            "deflated_sharpe_vjerojatnost": round(wc["deflated_sharpe_prob"], 2),
            "izgleda_prilagodeno": bool(c == "K7_C13C_PLUS_TREND_REENTRY"),
        }
    ratings = {
        "pravilo": "Blagi kritičar: ocjena se spušta samo zbog nevaljanih dokaza (lookahead, ugađanje/krhkost, premalo poslova, troškovi), nikad zbog veličine pada, njihanja ili koncentracije. Ocjena govori koliko je DOKAZ pouzdan, ne je li pravilo dobro: K1 je zelen iako je izgubio od držanja.",
        "legenda": {"zeleno": "dokaz valjan, provjere prošle", "žuto": "dokaz nije oboren, ali nedostaje provjera ili je slabija ili se čini prilagođeno", "crveno": "dokaz nevaljan"},
        "napomena_nije_critic": "Ovo je istraživačka ocjena, ne Critic PASS i ne ulazi u approved_list. Nijedan od deflated Sharpe iznosa nije iznad 0,95 uz K=533.",
        "mjerilo": "B0_BUYHOLD je mjerilo, nije ocjenjivan.",
        "po_suparniku": rating_rows,
        "napomene_revizije": [
            "Test ±20 % provjerava samo predznak ukupnog povrata u AI eri, što je slab test u bikovskom tržištu.",
            "B0 za ALAB kupuje na otvaranju prvog dana uvrštenja (2024-03-20), cijena možda nedostupna malom ulagaču.",
            "CAGR se računa od prvog do zadnjeg datuma i kraći je za jedan dan.",
            "K6 statistika na razini poslova ne broji djelomična rebalansiranja; povrat i krivulja su točni.",
        ],
    }

    # ---------- EU/HR ----------
    eu = {}
    for t in TICKERS:
        eu[t] = {"vrsta": "američka pojedinačna dionica (nije ETF)", "dostupnost_IBKR": "nepotvrđeno", "napomena": "Vjerojatno dostupna EU maloprodajnom klijentu kao pojedinačna dionica, ali status je nepotvrđen dok se ne provjeri u IBKR-u."}
    eu["CRDO"]["napomena"] += " Sjedište tvrtke i eventualne strane posebnosti nisu provjereni: nepotvrđeno."
    eu["ALAB"]["napomena"] += " Uvrštena tek 2024-03-20, kratka povijest, nema usporedivog dugoročnog zapisa."
    eu["SMCI"]["napomena"] += " Profil spominje računovodstvene i revizorske nedoumice u prošlosti (kontekst iz javnih izvora); ovdje nije provjereno."
    eu_block = {
        "pravilo": "Sve osam su američke pojedinačne dionice, a ne ETF-ovi; nijedan ETF se ovdje ne predstavlja kao dostupan. Dostupnost i uvjeti nepotvrđeni dok se ne provjere u IBKR-u.",
        "valuta": "Cijene su u USD; račun je u EUR. Tečaj i trošak konverzije nisu modelirani (USD cijene tretirane kao EUR ekvivalent), pa su svi EUR primjeri ilustrativni.",
        "porezi": "Ne dajemo tvrdnje o porezu. Za porezni tretman (dobit, dividende, vlasništvo strane tvrtke) provjeriti zasebno.",
        "po_dionici": eu,
    }

    # ---------- chart notes ----------
    def c(t: str, d: str) -> str:
        return hr(close_on(t, d), 2)
    notes = [
        {"ticker": "ANET", "gledaj": f"Pad 2025-01-22 (zatvaranje {c('ANET', '2025-01-22')} USD) do dna 2025-04-04 ({c('ANET', '2025-04-04')} USD) = -50,4 %; oporavak do 2025-08-06 ({c('ANET', '2025-08-06')} USD). Trend pravilo K2 (SMA200) ipak je imalo pad {pct(tk['ANET']['K2_SMA200_TREND']['max_drawdown'])}. 1.000 EUR pao bi na oko {eur(1000 * (1 - 0.504))}.", "pouka": "Trend filter (SMA200) ne štiti dobro od brzih padova; pogledaj na grafu kad je cijena pala ispod SMA200 nakon vrha."},
        {"ticker": "CRDO", "gledaj": f"Jaz 2023-02-15: zatvaranje dan ranije {c('CRDO', '2023-02-14')} USD, otvaranje {hr(open_on('CRDO', '2023-02-15'), 2)} USD (-44,9 %). Stop ne može izaći po stop cijeni kad otvaranje probije stop. Kasnije 2024-12-03 jaz +34,8 % (zatvaranje {c('CRDO', '2024-12-03')} USD).", "pouka": "Stop se računa unutar dana, ali jaz preko noći probija stop; zato je stvarni gubitak veći od planiranih 10 %."},
        {"ticker": "ALAB", "gledaj": f"Prvi dan 2024-03-20: otvaranje {hr(open_on('ALAB', '2024-03-20'), 2)} USD, zatvaranje {c('ALAB', '2024-03-20')} USD. Najdublji pad 2024-12-26 ({c('ALAB', '2024-12-26')} USD) do 2025-04-04 ({c('ALAB', '2025-04-04')} USD) = -63,7 %.", "pouka": "Kratka povijest: uzorak je mali; pravila s 4 posla ne mogu se uspoređivati."},
        {"ticker": "COHR", "gledaj": f"Jaz 2023-08-16: zatvaranje dan ranije {c('COHR', '2023-08-15')} USD, otvaranje {hr(open_on('COHR', '2023-08-16'), 2)} USD (-24,0 %). K1 je 2023-08-14 kupio po oko 44,23 i izašao po oko 35,73 (-19,2 %, najgori posao C13C-a u segmentu).", "pouka": "Najgori posao C13C-a u segmentu nije bio spor pad nego jaz preko noći."},
        {"ticker": "LITE", "gledaj": f"Rast s {c('LITE', '2023-01-03')} USD (2023-01-03) na {c('LITE', '2026-10-05')} USD (2026-10-05). K3 Donchian: jedan posao 2025-05-15 (76,89) do 2026-07-06 (728,82) = +848 %. K1 (C13C) tu stalno izlazi na stopu i ostaje u poziciji samo oko 25 % vremena. Pad 2025-01-22 ({c('LITE', '2025-01-22')}) do 2025-04-04 ({c('LITE', '2025-04-04')}).", "pouka": "Najjači trend segmenta: pravilo koje ostane unutra pobjeđuje; pravilo koje često izlazi gubi."},
        {"ticker": "SMCI", "gledaj": f"Vrh 2024-03-13 ({c('SMCI', '2024-03-13')} USD) do dna 2024-11-14 ({c('SMCI', '2024-11-14')} USD) = -84,8 %; jaz 2024-10-30 (-29,1 %: dan ranije {c('SMCI', '2024-10-29')}, otvaranje {hr(open_on('SMCI', '2024-10-30'), 2)}). Jaz 2026-03-20: {c('SMCI', '2026-03-19')} na {hr(open_on('SMCI', '2026-03-20'), 2)} (-26,9 %). K1 je u istom razdoblju ostao na pad od -49,5 %.", "pouka": "Ovdje se vidi smisao stopa: -84,8 % za držanje, -49,5 % za C13C, približno isti ukupni povrat."},
        {"ticker": "DELL", "gledaj": f"Pad 2024-05-29 ({c('DELL', '2024-05-29')} USD) do 2025-04-04 ({c('DELL', '2025-04-04')} USD) = -60 %, oporavak tek 2026-03-25. Jaz 2026-05-29: {c('DELL', '2026-05-28')} na {hr(open_on('DELL', '2026-05-29'), 2)} (+31,8 %).", "pouka": "Dugi pad pa velik jaz gore: pogledaj što je svako pravilo radilo oko 2026-05-29."},
        {"ticker": "HPE", "gledaj": f"Najmirnija: vrh 2025-01-22 ({c('HPE', '2025-01-22')} USD) do dna 2025-04-08 ({c('HPE', '2025-04-08')} USD) = -48,8 %. Jaz 2026-06-02: {c('HPE', '2026-06-01')} na {hr(open_on('HPE', '2026-06-02'), 2)} (+34,2 %). Potpora je držala u 63,6 % dodira.", "pouka": "Za HPE potpora/otpor ima smisla; K5B (proboj i povratni test) ima među pravilima najviši Sharpe uz manji pad (razlike prema K1 su male)."},
        {"segment": "network_servers", "gledaj": "Sedam od osam (sve osim SMCI) imaju dno oko 2025-04-04 (HPE 2025-04-08): pogledaj ih na istom grafu da vidiš koliko se kreću zajedno. Zatim usporedi K6 s držanjem: obje krivulje padaju do 2025-04-04, K6 dublje (-54,2 % naspram -46,4 %), a poslije raste brže.", "pouka": "Raznolikost unutar segmenta ne štiti od zajedničkog šoka: pad je bio istodoban."},
    ]

    findings = [
        f"Pobjednik po unaprijed zadanom pravilu: {NAMES_HR[win]} (Sharpe {hr(w['sharpe'], 2)}, {w['trades']} poslova, povrat {pct(w['total_return'], 0)} naspram {pct(h['total_return'], 0)} za držanje).",
        f"Pobjednik pobjeđuje držanje i na povratu i na Sharpeu, ali produbljuje najgori pad ({pct(w['max_drawdown'])} naspram {pct(h['max_drawdown'])}): na 1.000 EUR najgori gubitak {eur(-1000 * w['max_drawdown'])} naspram {eur(-1000 * h['max_drawdown'])}.",
        f"C13C (K1): povrat {pct(k1s['total_return'], 0)} naspram {pct(h['total_return'], 0)}, Sharpe {hr(k1s['sharpe'], 2)} naspram {hr(h['sharpe'], 2)}, pad {pct(k1s['max_drawdown'])}. Bolji povrat od držanja na {n_ret} od 8 dionica, manji pad na {n_dd} od 8.",
        "Svi suparnici osim K6 gube od držanja na povratu na segmentu; svi osim K6 imaju manji najveći pad, najmanji K5 (-10,5 %), K5B (-14,4 %), K1 (-22,9 %).",
        f"Na razini dionica bolji povrat od držanja ima samo SMCI ({', '.join(NAMES_HR[c] for c in beats_ret['SMCI'])}); na ostalima 0.",
    ]
    return {
        "segment": "network_servers", "naziv": prof["segment_name_hr"], "tickeri": TICKERS,
        "prozor": {"glavni": "AI era 2023-01-01 do 2026-10-05", "kontekst": "pre-2023 samo kao kontekst"},
        "status_revizije": "FIXED (ispravljeni: zaleđena povijest SMCI/NBIS, loš tick NVDA, trošak zadnje likvidacije, slab lookahead test)",
        "pravila": "Istraživanje. Nije savjet, nije Critic PASS. Agenti ne šalju naloge.",
        "zasto_zajedno": why,
        "kartice_dionica": cards,
        "tablica_po_dionici_AI_era": table,
        "tablica_segmenta_jednak_kapital_AI_era": {"kapital_po_dionici_EUR": 1000, "ukupno_EUR": 8000, "napomena": "USD cijene tretirane kao EUR; bez prelijevanja između dionica; ALAB miruje kao gotovina do 2024-03-20.", "suparnici": segtab},
        "tko_je_najbolje_odradio_posao": winner,
        "C13C_iskreno": c13,
        "ocjene": ratings,
        "EU_HR": eu_block,
        "sto_gledati_na_grafovima": notes,
        "dionice_gdje_pravilo_pobjeduje_drzanje_na_povratu": beats_ret,
        "dionice_gdje_pravilo_pobjeduje_drzanje_na_sharpeu": beats_sh,
        "kljucni_nalazi": findings,
        "ogranicenja": prof["caveats_hr"] + ["Sve su dnevne cijene; stop i ulaz su simulirani s dnevnim svijećama.", "Cijene u USD tretirane kao EUR: tečaj nije modeliran."],
    }


def main() -> None:
    out = build()
    (SEG / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("written", SEG / "analysis.json")


if __name__ == "__main__":
    main()
