"""Build reports/research/AICHAIN_20261014/segments/cloud/analysis.json for the cloud segment.

    .venv/bin/python -m lab.aichain.analysis_cloud

Read-only research. Every number is copied from results/*.json, summary.json, profile.json or the
daily CSVs under data/ohlcv. Prose is Croatian (for the researcher); identifiers and comments are English.
Agents never place orders.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "reports" / "research" / "AICHAIN_20261014"
OUT = RES / "segments" / "cloud" / "analysis.json"

TICKERS = ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "NBIS", "VRT"]
BENCH = "B0_BUYHOLD"
NAMES = {
    "B0_BUYHOLD": "B0 kupi i drži",
    "K1_C13C_ORIG": "K1 C13C (Petrov algoritam)",
    "K2_SMA200_TREND": "K2 trend SMA200",
    "K3_DONCHIAN_55_20": "K3 Donchian 55/20",
    "K4_TSMOM_126": "K4 momentum 126 dana",
    "K5_SUPPORT_RESISTANCE": "K5 potpora/otpor",
    "K5B_SR_BREAKOUT_RETEST": "K5B proboj i povratak na razinu",
    "K6_MOMENTUM_CS": "K6 rotacija po momentumu",
    "K7_C13C_PLUS_TREND_REENTRY": "K7 C13C + ponovni ulaz u trend",
}
STEP_KEYS = ("total_return", "sharpe", "max_drawdown", "trades", "exposure_pct")


# ---------------------------------------------------------------- formatting helpers


def _num(x: float, nd: int = 0) -> str:
    """Croatian number format: dot for thousands, comma for decimals."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, nd: int = 1) -> str:
    return f"{_num(x * 100, nd)} %"


def eur(x: float, nd: int = 0) -> str:
    return f"{_num(x, nd)} EUR"


def r4(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


# ---------------------------------------------------------------- data access


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def px(ticker: str, date: str, col: str) -> float:
    df = pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"]).set_index("date")
    return float(df.loc[date, col])


def ai(win: dict[str, Any]) -> dict[str, Any]:
    return win["windows"]["ai_era"]


# ---------------------------------------------------------------- sections


def build_tables(seg: dict[str, Any], per_ticker: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    ticker_rows: list[dict] = []
    for t in TICKERS:
        hold = ai(per_ticker[t]["contenders"][BENCH])
        for cid, c in per_ticker[t]["contenders"].items():
            if not c.get("available"):
                continue
            w = ai(c)
            ticker_rows.append(
                {
                    "ticker": t,
                    "suparnik": cid,
                    "naziv": NAMES[cid],
                    "pocetak_prozora": w["start"],
                    "ukupni_prinos": r4(w["total_return"]),
                    "sharpe": r4(w["sharpe"]),
                    "max_drawdown": r4(w["max_drawdown"]),
                    "poslova": w["trades"],
                    "izlozenost_pct": r4(w["exposure_pct"]),
                    "prinos_uz_trosak_2x": r4(w["total_return_cost_2x"]),
                    "razlika_prinosa_prema_drzanju_pp": None
                    if cid == BENCH
                    else r4((w["total_return"] - hold["total_return"]) * 100),
                    "drawdown_bolji_od_drzanja_pp": None
                    if cid == BENCH
                    else r4((w["max_drawdown"] - hold["max_drawdown"]) * 100),
                    "malo_poslova_oznaka": bool(w["trades"] < 10 and cid != BENCH),
                    "tekst": (
                        f"{t}, {NAMES[cid]}: prinos {pct(w['total_return'])}, Sharpe {_num(w['sharpe'], 2)}, "
                        f"najveći pad {pct(w['max_drawdown'])}, poslova {w['trades']}, izloženost {_num(w['exposure_pct'], 0)} %. "
                        f"Na 1.000 EUR: {eur(1000 * (1 + w['total_return']))} na kraju."
                    ),
                }
            )
    seg_rows: list[dict] = []
    for cid, c in seg["contenders"].items():
        w = ai(c)
        seg_rows.append(
            {
                "suparnik": cid,
                "naziv": NAMES[cid],
                "ukupni_prinos": r4(w["total_return"]),
                "prinos_uz_trosak_2x": r4(w["total_return_cost_2x"]),
                "prinos_uz_trosak_3x": r4(w["total_return_cost_3x"]),
                "sharpe": r4(w["sharpe"]),
                "max_drawdown": r4(w["max_drawdown"]),
                "poslova": w["trades"],
                "izlozenost_pct": r4(w["exposure_pct"]),
                "krajnja_vrijednost_eur_na_7000": r4(w["end_value"]),
                "krajnja_vrijednost_eur_na_1000": r4(w["end_value"] / 7.0),
                "razlika_prinosa_prema_drzanju_pp": None
                if cid == BENCH
                else r4((w["total_return"] - ai(seg["contenders"][BENCH])["total_return"]) * 100),
                "psr": r4(w["psr"]),
                "deflated_sharpe_prob": r4(w["deflated_sharpe_prob"]),
            }
        )
    return ticker_rows, seg_rows


def worst_drawdown(seg: dict[str, Any], cid: str) -> dict[str, Any]:
    eq = pd.DataFrame(seg["contenders"][cid]["equity"]["ai_era"], columns=["d", "v"]).set_index("d").v
    dd = eq / eq.cummax() - 1
    trough = dd.idxmin()
    peak = eq[:trough].idxmax()
    return {
        "vrh": peak,
        "vrijednost_na_vrhu_eur": r4(eq[peak]),
        "dno": trough,
        "vrijednost_na_dnu_eur": r4(eq[trough]),
        "pad": r4(dd.min()),
        "gubitak_na_papiru_eur_segment": r4(eq[peak] - eq[trough]),
        "gubitak_na_papiru_eur_po_1000_na_vrhu": r4(-dd.min() * 1000),
    }


def pick_winner(seg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Winner = highest AI-era Sharpe among contenders (not B0) with >= 20 trades and positive return at cost 2x."""
    cands = []
    for cid, c in seg["contenders"].items():
        if cid == BENCH:
            continue
        w = ai(c)
        ok_trades = w["trades"] >= 20
        ok_cost = w["total_return_cost_2x"] > 0
        cands.append(
            {
                "suparnik": cid,
                "sharpe": r4(w["sharpe"]),
                "poslova": w["trades"],
                "prinos_uz_trosak_2x": r4(w["total_return_cost_2x"]),
                "ispunjava_20_poslova": ok_trades,
                "pozitivan_prinos_uz_2x": ok_cost,
                "kvalificiran": ok_trades and ok_cost,
            }
        )
    qual = sorted((c for c in cands if c["kvalificiran"]), key=lambda c: -c["sharpe"])
    return qual[0], sorted(cands, key=lambda c: -c["sharpe"])


# ---------------------------------------------------------------- ratings


def rate(cid: str, seg: dict[str, Any], summ: dict[str, Any]) -> dict[str, Any]:
    """Lenient critic: only INVALID evidence lowers the rating. Size of drawdown, volatility, concentration never do."""
    w = ai(seg["contenders"][cid])
    la1 = summ["lookahead"][cid]["ok"]
    la2 = summ["lookahead_arrays"].get(cid, {}).get("ok")
    red: list[str] = []
    yellow: list[str] = []
    notes: list[str] = []
    if not la1 or la2 is False:
        red.append("test pogleda u budućnost pao")
    if w["trades"] < 20:
        red.append(f"manje od 20 poslova na segmentu ({w['trades']})")
    if w["total_return_cost_2x"] <= 0:
        red.append("prinos uz dvostruki trošak nije pozitivan")
    if cid == "K6_MOMENTUM_CS":
        notes.append("jači test signalnih nizova ne postoji za rotaciju (K6); prošao je prvi test pogleda u budućnost na 48 provjera")
    if w["psr"] < 0.95:
        yellow.append(
            f"statistička pouzdanost slaba: PSR {_num(w['psr'], 2)} (vjerojatnost da je pravi Sharpe iznad nule; ispod 0,95 nije dovoljno čvrsto)"
        )
    rob = summ["robustness_pm20"].get(cid, {}).get("cloud")
    tuned: list[str] = []
    if rob is None:
        yellow.append("robusnost +-20 % parametara nije izmjerena za ovaj segment (nema dokaza ni za ni protiv)")
    else:
        worst = rob["min_total_return"] / rob["base_total_return"]
        if worst < 0.5:
            yellow.append(
                f"krhko na parametrima: pomak jednog parametra za 20 % spušta prinos s {pct(rob['base_total_return'], 0)} na {pct(rob['min_total_return'], 0)}"
            )
        else:
            notes.append(
                f"robusnost +-20 % prolazi: prinos ostaje između {pct(rob['min_total_return'], 0)} i {pct(rob['max_total_return'], 0)} (osnova {pct(rob['base_total_return'], 0)})"
            )
    if cid == "K7_C13C_PLUS_TREND_REENTRY":
        tuned.append("proširenje K1 napravljeno nakon što je ponašanje K1 bilo poznato (nova hipoteza, vlastiti freeze ID); izgleda kao ugađanje na isti podatak")
    if cid in ("K6_MOMENTUM_CS", "K4_TSMOM_126"):
        tuned.append("odabran za dijagnostiku robusnosti po rezultatima (srednji AI-era Sharpe po segmentima); parametri nisu mijenjani")
    if cid in ("K5_SUPPORT_RESISTANCE", "K5B_SR_BREAKOUT_RETEST"):
        tuned.append("dopune specifikacije (npr. 40 svijeća istek, 1,5 % tolerancija) odabrane unaprijed, bez gledanja rezultata; nema oznake ugađanja, ali ni mjerene robusnosti")
    colour = "crveno" if red else ("žuto" if yellow else "zeleno")
    return {
        "suparnik": cid,
        "naziv": NAMES[cid],
        "ocjena": colour,
        "crveni_razlozi": red,
        "zuti_razlozi": yellow,
        "napomene": notes,
        "oznake_ugadanja": tuned,
        "poslova_na_segmentu": w["trades"],
        "psr": r4(w["psr"]),
        "lookahead_prvi_test": la1,
        "lookahead_jaki_test": la2,
    }


# ---------------------------------------------------------------- cards


def card(t: str, prof: dict[str, Any], pt: dict[str, Any]) -> dict[str, Any]:
    p = prof["tickers"][t]
    a = p["windows"]["ai"]
    tt = p["tumacenje_hr"]
    cs = pt["contenders"]
    hold = ai(cs[BENCH])
    strat = {cid: ai(c) for cid, c in cs.items() if cid != BENCH and c.get("available")}
    best_id = max(strat, key=lambda k: strat[k]["sharpe"])
    best = strat[best_id]
    k1 = strat["K1_C13C_ORIG"]
    dd_list = [
        {
            "pocetak": d["start"],
            "dno": d["bottom"],
            "oporavak": d["recovery"] or "još nije oporavljen",
            "pad": r4(d["depth"]),
            "gubitak_na_1000_eur": round(-d["depth"] * 1000),
        }
        for d in a["drawdowns"][:3]
    ]
    drop = a["after_drop5_above_sma200"]
    return {
        "ticker": t,
        "tvrtka": p["mehanizam_hr"]["ime"],
        "podaci": {"prvi_datum": p["first_date"], "zadnji_datum": p["last_date"], "barova_ai_era": a["bars"]},
        "kontekst_iz_javnih_izvora": {
            "oznaka": p["oznaka_mehanizma"],
            "sto_prodaje": p["mehanizam_hr"]["sto_prodaje"],
            "sto_vozi_prihod": p["mehanizam_hr"]["sto_vozi_prihod"],
            "mjesto_u_lancu": p["mehanizam_hr"]["mjesto_u_lancu"],
            "ciklus": p["mehanizam_hr"]["ciklus"],
            "sto_steti": p["mehanizam_hr"]["sto_steti"],
        },
        "iz_nasih_podataka": {
            "volatilnost_god": r4(a["ann_vol"]),
            "beta_prema_SMH": r4(a["market"]["SMH"]["beta"]),
            "beta_prema_NDX": r4(a["market"]["NDX"]["beta"]),
            "korelacija_SMH": r4(a["market"]["SMH"]["corr"]),
            "autokorelacija_lag1": r4(a["character"]["autocorr"]["1"]),
            "omjer_varijance_20d": r4(a["character"]["vr20"]["vr"]),
            "omjer_varijance_20d_z": r4(a["character"]["vr20"]["z"]),
            "ukupni_prinos_ai_era": r4(a["total_return"]),
            "najgori_padovi": dd_list,
            "rizik_i_veza": tt["rizik_i_veza"],
            "karakter": tt["karakter"],
            "nakon_pada_5_dana_iznad_SMA200": {
                "dana": drop["n_events"],
                "epizoda": drop["n_episodes"],
                "mali_uzorak": drop["small_sample"],
                "prosjek_nakon_5d": r4(drop["f5"]["mean"]),
                "uobicajeno_5d": r4(drop["f5"]["base_mean"]),
                "prosjek_nakon_20d": r4(drop["f20"]["mean"]),
                "uobicajeno_20d": r4(drop["f20"]["base_mean"]),
                "ocjena_premise": tt["premisa_C13C_verdict"],
                "tekst": tt["premisa_C13C"],
            },
            "najgori_pad_tekst": tt["najgori_pad"],
            "skokovi_i_koncentracija": tt["skokovi_i_koncentracija"],
            "sma200": tt["sma200"],
            "podrska_otpor": tt["podrska_otpor"],
        },
        "najbolji_suparnik_po_sharpeu_na_tickeru": {
            "suparnik": best_id,
            "sharpe": r4(best["sharpe"]),
            "prinos": r4(best["total_return"]),
            "sharpe_drzanja": r4(hold["sharpe"]),
            "prinos_drzanja": r4(hold["total_return"]),
            "napomena": f"Poslova: {best['trades']}. Jedan ticker je mali uzorak; ovo ne bira pobjednika segmenta.",
        },
        "c13c_na_tickeru": {
            "prinos": r4(k1["total_return"]),
            "prinos_drzanja": r4(hold["total_return"]),
            "sharpe": r4(k1["sharpe"]),
            "sharpe_drzanja": r4(hold["sharpe"]),
            "max_drawdown": r4(k1["max_drawdown"]),
            "max_drawdown_drzanja": r4(hold["max_drawdown"]),
            "poslova": k1["trades"],
        },
    }


ALGO_TEXT: dict[str, str] = {}


def algo_texts(per_ticker: dict[str, Any]) -> dict[str, str]:
    """What the behaviour means for algorithm choice, with numbers copied from the AI-era results."""

    def g(t: str, cid: str) -> dict[str, Any]:
        return ai(per_ticker[t]["contenders"][cid])

    out: dict[str, str] = {}
    h = g("MSFT", BENCH)
    out["MSFT"] = (
        f"MSFT je najmirnija u segmentu i nema statistički vidljiv sklon ni trendu ni vraćanju (omjer varijance 0,99). "
        f"Takvoj dionici pristaje jednostavan filtar trenda koji uglavnom samo skraćuje pad. Mjereno: držanje {pct(h['total_return'])} uz najveći pad {pct(h['max_drawdown'])}; "
        f"K1 (C13C) {pct(g('MSFT','K1_C13C_ORIG')['total_return'])} uz pad {pct(g('MSFT','K1_C13C_ORIG')['max_drawdown'])} i samo {g('MSFT','K1_C13C_ORIG')['trades']} posla, "
        f"K7 {pct(g('MSFT','K7_C13C_PLUS_TREND_REENTRY')['total_return'])}. Nitko ne pobjeđuje držanje u prinosu; "
        f"Sharpe K1 ({_num(g('MSFT','K1_C13C_ORIG')['sharpe'],2)}) je iznad držanja ({_num(h['sharpe'],2)}), ali sa 4 posla to je tanak dokaz."
    )
    h = g("AMZN", BENCH)
    out["AMZN"] = (
        f"AMZN pokazuje blagi nagib prema vraćanju (omjer varijance 0,76, z = -1,5, granično), a pad od 5 dana nije značajno bolji od uobičajenog (premisa C13C se ne potvrđuje). "
        f"To ne pogoduje ni čistom praćenju trenda (K2 {pct(g('AMZN','K2_SMA200_TREND')['total_return'])}) ni C13C-u (K1 {pct(g('AMZN','K1_C13C_ORIG')['total_return'])}). "
        f"Najbolji Sharpe ima K5B (proboj i povratak na razinu) s {_num(g('AMZN','K5B_SR_BREAKOUT_RETEST')['sharpe'],2)} i prinosom {pct(g('AMZN','K5B_SR_BREAKOUT_RETEST')['total_return'])}, "
        f"ali držanje je {pct(h['total_return'])} uz Sharpe {_num(h['sharpe'],2)}. Za AMZN je držanje daleko bolje."
    )
    h = g("GOOGL", BENCH)
    out["GOOGL"] = (
        f"GOOGL je u gotovo čistom usponu (85 % dana iznad SMA200), pa su pravila koja ostaju u trendu bolja od onih koja čekaju pad. "
        f"K2 (SMA200) {pct(g('GOOGL','K2_SMA200_TREND')['total_return'])} i K5B {pct(g('GOOGL','K5B_SR_BREAKOUT_RETEST')['total_return'])} uz Sharpe {_num(g('GOOGL','K5B_SR_BREAKOUT_RETEST')['sharpe'],2)} (isto kao držanje, {_num(h['sharpe'],2)}) "
        f"i pad {pct(g('GOOGL','K5B_SR_BREAKOUT_RETEST')['max_drawdown'])} naspram {pct(h['max_drawdown'])} kod držanja. "
        f"C13C je ovdje izgubio ({pct(g('GOOGL','K1_C13C_ORIG')['total_return'])}): u 5 od 15 izlaza stop je ispunjen na jazu (cijena otvorila ispod stopa)."
    )
    h = g("META", BENCH)
    out["META"] = (
        f"META ima najveće jazove na izvješćima u segmentu (+19,8 % dana 2023-02-02, -14,6 % dana 2024-04-25), pa uski stop često ne štiti: K1 je u 6 od 14 izlaza izašao po otvaranju ispod stopa. "
        f"Najbolje se držao K4 (momentum) s {pct(g('META','K4_TSMOM_126')['total_return'])} i Sharpeom {_num(g('META','K4_TSMOM_126')['sharpe'],2)}, "
        f"ali držanje je {pct(h['total_return'])} i Sharpe {_num(h['sharpe'],2)}. Dobit ovisi o malo dana (10 najboljih dana čini 66 % ukupnog logaritamskog prinosa), "
        f"pa pravila koja su puno izvan tržišta propuste baš te dane."
    )
    h = g("ORCL", BENCH)
    out["ORCL"] = (
        f"ORCL je najvolatilniji među velikim oblacima (47 %) i jedini gdje pravila nisu jasno iza držanja: držanje {pct(h['total_return'])} uz Sharpe {_num(h['sharpe'],2)} i pad {pct(h['max_drawdown'])}; "
        f"K5 (potpora/otpor) {pct(g('ORCL','K5_SUPPORT_RESISTANCE')['total_return'])} uz Sharpe {_num(g('ORCL','K5_SUPPORT_RESISTANCE')['sharpe'],2)} i pad {pct(g('ORCL','K5_SUPPORT_RESISTANCE')['max_drawdown'])}; "
        f"K7 {pct(g('ORCL','K7_C13C_PLUS_TREND_REENTRY')['total_return'])}; K1 {pct(g('ORCL','K1_C13C_ORIG')['total_return'])} uz pad {pct(g('ORCL','K1_C13C_ORIG')['max_drawdown'])}. "
        f"Nakon pada od 5 dana prosjek nakon 20 dana je -2,65 % (uobičajeno +1,55 %): kupnja pada ovdje nije pomogla, što objašnjava zašto pravilo koje drži malo i izlazi brzo prolazi bolje."
    )
    h = g("NBIS", BENCH)
    out["NBIS"] = (
        f"NBIS ima samo oko 490 stvarnih dana (od 2024-10-21), volatilnost 113 % i beta prema NDX 2,52. Nakon pada od 5 dana cijena je u prosjeku rasla (+16,5 % nakon 20 dana; mali uzorak), ali "
        f"K1 koji tu ideju koristi dobio je samo {pct(g('NBIS','K1_C13C_ORIG')['total_return'])} u {g('NBIS','K1_C13C_ORIG')['trades']} poslova jer ga stop (10 % ispod vrha) stalno izbacuje u titranju. "
        f"Dugo držanje bi je prošlo daleko bolje: K4 {pct(g('NBIS','K4_TSMOM_126')['total_return'])} u samo 2 posla, držanje {pct(h['total_return'])}. "
        f"Takvoj dionici pristaju široki stopovi ili praćenje trenda, ne uski stopovi."
    )
    h = g("VRT", BENCH)
    out["VRT"] = (
        f"VRT je vrlo volatilan (62 %), s betom 1,17 prema SMH, i jedina dionica u segmentu gdje je C13C stvarno dobro prošao: K1 {pct(g('VRT','K1_C13C_ORIG')['total_return'])} uz Sharpe {_num(g('VRT','K1_C13C_ORIG')['sharpe'],2)} i pad {pct(g('VRT','K1_C13C_ORIG')['max_drawdown'])} "
        f"(držanje {pct(h['total_return'])}, Sharpe {_num(h['sharpe'],2)}, pad {pct(h['max_drawdown'])}). Uzorak događaja je dovoljno velik (40 odvojenih epizoda pada od 5 dana), "
        f"ali nakon pada prosjek nakon 20 dana (6,74 %) nije bolji od uobičajenog (7,14 %); K1 ovdje ne zarađuje od prosječnog odbijanja nakon pada, nego od toga što klizni stop dopušta da dobitni poslovi traju (najbolji posao +157 %). "
        f"K5B ima Sharpe {_num(g('VRT','K5B_SR_BREAKOUT_RETEST')['sharpe'],2)} (iznad držanja) s padom {pct(g('VRT','K5B_SR_BREAKOUT_RETEST')['max_drawdown'])}."
    )
    return out


def c13c_report(per_ticker: dict[str, Any], seg: dict[str, Any], summ: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for t in TICKERS:
        k = ai(per_ticker[t]["contenders"]["K1_C13C_ORIG"])
        h = ai(per_ticker[t]["contenders"][BENCH])
        tr = per_ticker[t]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
        gaps = sum(1 for x in tr if x["detail"] == "gap_stop")
        wins = sum(1 for x in tr if x["return"] > 0)
        beats_ret = k["total_return"] > h["total_return"]
        beats_sharpe = k["sharpe"] > h["sharpe"]
        beats_dd = k["max_drawdown"] > h["max_drawdown"]
        rows.append(
            {
                "ticker": t,
                "prinos_c13c": r4(k["total_return"]),
                "prinos_drzanja": r4(h["total_return"]),
                "sharpe_c13c": r4(k["sharpe"]),
                "sharpe_drzanja": r4(h["sharpe"]),
                "max_drawdown_c13c": r4(k["max_drawdown"]),
                "max_drawdown_drzanja": r4(h["max_drawdown"]),
                "poslova": k["trades"],
                "dobitnih_poslova": wins,
                "izlaza_na_jazu_ispod_stopa": gaps,
                "bolji_prinos_od_drzanja": beats_ret,
                "bolji_sharpe_od_drzanja": beats_sharpe,
                "manji_pad_od_drzanja": beats_dd,
                "tekst": (
                    f"{t}: C13C {pct(k['total_return'])} naspram držanja {pct(h['total_return'])}; na 1.000 EUR to je {eur(1000*(1+k['total_return']))} naspram {eur(1000*(1+h['total_return']))}. "
                    f"Najveći pad {pct(k['max_drawdown'])} naspram {pct(h['max_drawdown'])}; poslova {k['trades']} (dobitnih {wins}), izlaza po jazu ispod stopa {gaps}."
                ),
            }
        )
    sk = ai(seg["contenders"]["K1_C13C_ORIG"])
    sh = ai(seg["contenders"][BENCH])
    rob = summ["robustness_pm20"]["K1_C13C_ORIG"]["cloud"]
    return {
        "napomena": "K1 je Petrov vlastiti algoritam C13C u simulatoru koji je parity testom (9 od 9) identičan originalu. Rezultati su prikazani bez uljepšavanja.",
        "po_tickeru": rows,
        "segment": {
            "prinos": r4(sk["total_return"]),
            "prinos_drzanja": r4(sh["total_return"]),
            "sharpe": r4(sk["sharpe"]),
            "sharpe_drzanja": r4(sh["sharpe"]),
            "max_drawdown": r4(sk["max_drawdown"]),
            "max_drawdown_drzanja": r4(sh["max_drawdown"]),
            "poslova": sk["trades"],
            "prinos_uz_trosak_2x": r4(sk["total_return_cost_2x"]),
            "prinos_uz_trosak_3x": r4(sk["total_return_cost_3x"]),
        },
        "zakljucak_hr": (
            f"C13C ne pobjeđuje držanje ni na jednom od 7 tickera u prinosu. Na segmentu: {pct(sk['total_return'],0)} naspram {pct(sh['total_return'],0)} (na 7.000 EUR: {eur(sk['end_value'])} naspram {eur(sh['end_value'])}). "
            f"Najveći pad je manji na MSFT, ORCL i VRT (na NBIS-u praktički isti), a veći na AMZN, GOOGL i META: stop stalno izbacuje iz dionice, a ponovnog ulaza nema dok se ne ponovi pad od 5 %. "
            f"Sharpe je bolji od držanja samo na MSFT-u. Najviši prinos ima na VRT-u, najlošiji je na GOOGL-u i AMZN-u (negativan ili oko nule). Premisa C13C (kupnja nakon pada od 5 % iznad SMA200) u AI eri se u ovom segmentu ne potvrđuje na AMZN, GOOGL, META, ORCL i VRT; "
            f"samo MSFT i NBIS idu u prilog, ali s malim uzorkom."
        ),
        "robusnost_pm20": {
            "osnova_prinos": r4(rob["base_total_return"]),
            "najgori_prinos": r4(rob["min_total_return"]),
            "najbolji_prinos": r4(rob["max_total_return"]),
            "predznak_se_mijenja": rob["sign_flips"],
            "tekst": (
                f"Pomak jednog parametra za 20 % mijenja prinos K1 s {pct(rob['base_total_return'],0)} na raspon od {pct(rob['min_total_return'],0)} do {pct(rob['max_total_return'],0)} "
                f"(SMA 160 ili pad 6 % spuštaju na {pct(rob['min_total_return'],0)}). Predznak ostaje pozitivan, ali veličina jako ovisi o parametrima: to je znak krhkosti."
            ),
        },
    }


def chart_notes() -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    def add(ticker: str, naslov: str, tekst: str, datumi: list[str]) -> None:
        notes.append({"ticker": ticker, "naslov": naslov, "tekst": tekst, "datumi": datumi})

    c0, o1, c1 = px("ORCL", "2025-09-09", "close"), px("ORCL", "2025-09-10", "open"), px("ORCL", "2025-09-10", "close")
    low = px("ORCL", "2026-07-24", "close")
    add(
        "ORCL",
        "Jaz od 32 % pa pad od 65 %",
        f"Na grafu ORCL pogledaj 2025-09-10: dan prije zatvaranje je {_num(c0,2)} USD, a dionica otvara na {_num(o1,2)} USD. Taj prazan prostor među svijećama zove se jaz (gap): "
        f"nitko nije mogao kupiti ili prodati po cijenama između. Na 1.000 EUR to je skok na 1.320 EUR preko noći. Zatvaranje tog dana je {_num(c1,2)} USD, a dno je 2026-07-24 na {_num(low,2)} USD, "
        f"što je pad od 65 %: 1.000 EUR vrijednih na vrhu postaje oko 350 EUR. Pravilo K5 je kupilo 2025-08-21 po 233,05 USD i cilj je ispunjen po otvaranju jaza ({_num(319.19,2)}), +36,9 %; "
        f"obrnuta strana jaza je kod stopova (vidi VRT).",
        ["2025-09-09", "2025-09-10", "2026-07-24"],
    )
    vo, vc = px("VRT", "2025-01-27", "open"), px("VRT", "2025-01-24", "close")
    add(
        "VRT",
        "Stop nije osiguranje protiv jaza",
        f"VRT: 2025-01-24 zatvara na {_num(vc,2)} USD, a 2025-01-27 otvara na {_num(vo,2)} USD (-20 %). K5B je ušao 2025-01-22 po {_num(150.08,2)} sa stopom 3 % ispod razine, "
        f"ali stop je ispunjen tek po otvaranju {_num(vo,2)}, gubitak 22 % umjesto 3 %. Na 1.000 EUR to je 220 EUR, ne 30 EUR. Dno tog pada: 2025-04-04 na {_num(px('VRT','2025-04-04','close'),2)} USD (zatvaranje), "
        f"pad od vrha 2025-01-23 ({_num(px('VRT','2025-01-23','close'),2)} USD) od 61 %.",
        ["2025-01-22", "2025-01-27", "2025-04-04"],
    )
    add(
        "META",
        "Dobit s trailing stopom i jaz na izvješću",
        f"META: 2023-02-01 zatvara na {_num(px('META','2023-02-01','close'),2)} USD, a 2023-02-02 otvara na {_num(px('META','2023-02-02','open'),2)} USD (+19,8 %). "
        f"K1 je ušao 2023-02-10 po {_num(176.35,2)} i izašao 2023-08-17 po {_num(293.05,2)} (stop se podizao uz vrh; zatvaranje dan prije {_num(px('META','2023-08-16','close'),2)}): +66 %, "
        f"na 1.000 EUR dobit od oko 660 EUR u 130 dana. Pogledaj kako se klizni stop (10 % ispod najvišeg vrha) drži ispod cijene dok traje uspon.",
        ["2023-02-02", "2023-02-10", "2023-08-17"],
    )
    add(
        "AMZN",
        "Gubitak koji nadmašuje stop",
        f"AMZN: K1 je kupio 2024-07-18 po {_num(189.59,2)}. Zatvaranje 2024-08-01 je {_num(px('AMZN','2024-08-01','close'),2)}, a 2024-08-02 dionica otvara na {_num(px('AMZN','2024-08-02','open'),2)} (-9,4 %). "
        f"Stop je bio iznad te cijene, pa je ispunjenje po otvaranju: gubitak 12,1 %, na 1.000 EUR 121 EUR. Takvih izlaza na jazu ima 2 od 12 poslova na AMZN-u.",
        ["2024-07-18", "2024-08-01", "2024-08-02"],
    )
    add(
        "NBIS",
        "Dvije faze: pad od 58 % i skok od 52 %",
        f"NBIS: zatvaranje 2025-02-18 je {_num(px('NBIS','2025-02-18','close'),2)} USD, dno 2025-04-08 je {_num(px('NBIS','2025-04-08','close'),2)} USD (pad 58 %, 1.000 EUR postaje oko 417 EUR). "
        f"Pa 2025-09-08 zatvara {_num(px('NBIS','2025-09-08','close'),2)}, a 2025-09-09 otvara na {_num(px('NBIS','2025-09-09','open'),2)} (+51,7 %, najveći jaz u segmentu). "
        f"K4 (momentum) je ušao 2025-04-25 po {_num(24.57,2)} i izašao 2026-03-27 po {_num(105.83,2)}: +330 % u jednom poslu, što pokazuje koliko ukupni rezultat ovisi o jednoj odluci. "
        f"Podaci počinju tek 2024-10-21; prije toga je trgovanje bilo zaustavljeno pa je ta povijest izbačena.",
        ["2025-02-18", "2025-04-08", "2025-09-09", "2025-04-25", "2026-03-27"],
    )
    add(
        "MSFT",
        "Spori pad bez jaza",
        f"MSFT: vrh zatvaranja 2025-10-28 na {_num(px('MSFT','2025-10-28','close'),2)} USD, dno 2026-06-25 na {_num(px('MSFT','2026-06-25','close'),2)} USD (pad 35 %, na 1.000 EUR 349 EUR na papiru, 164 trgovačka dana). "
        f"K1 je ušao 2025-11-05 po {_num(513.3,2)} i stop ga je izbacio 2026-01-14 po {_num(463.35,2)} (-9,8 %), pa je izbjegnut daljnji pad do dna. Ukupno samo 4 posla u 3,75 godine; pogledaj koliko dugo K1 stoji u gotovini.",
        ["2025-10-28", "2025-11-05", "2026-01-14", "2026-06-25"],
    )
    add(
        "GOOGL",
        "Najbolji pojedinačni posao K5B",
        f"GOOGL: K5B je ušao 2025-05-20 po {_num(166.43,2)} (povratak na probijenu razinu) i držao do 2026-02-11 po {_num(318.97,2)}, +91,6 % (na 1.000 EUR dobit 916 EUR) jer je izlaz tek kad zatvaranje padne ispod SMA50. "
        f"Usporedi s K1 koji u istom razdoblju čeka pad od 5 % i često izlazi na jazu. Pogledaj razinu probijanja na grafu: nakon proboja cijena se vrati do razine, a onda raste.",
        ["2025-05-20", "2026-02-11"],
    )
    return notes


def eu_notes() -> dict[str, Any]:
    base = (
        "Pojedinačna američka dionica; općenito dostupna EU malim ulagačima (za razliku od američkih ETF-ova bez KID dokumenta), "
        "ali dostupnost kod IBKR-a za točan simbol i razlomljene dionice je nepotvrđeno do provjere u IBKR-u. Porez i tečaj EUR/USD nisu modelirani; porezne tvrdnje nema."
    )
    return {
        "opce": base,
        "po_tickeru": {
            "MSFT": {"status": "nepotvrđeno", "napomena": "Američka dionica, USD. Dividende postoje u stvarnosti, a cijene u podacima su bez dividendi (porez na dividendu nije procijenjen)."},
            "AMZN": {"status": "nepotvrđeno", "napomena": "Američka dionica, USD. Podjela 20:1 iz 2022. već je u podacima ujednačena."},
            "GOOGL": {"status": "nepotvrđeno", "napomena": "Klasa A (GOOGL, s pravom glasa). Podjela 20:1 iz 2022. već je ujednačena; postoji i klasa C (GOOG), koja se ovdje ne analizira."},
            "META": {"status": "nepotvrđeno", "napomena": "Američka dionica, USD."},
            "ORCL": {"status": "nepotvrđeno", "napomena": "Američka dionica, USD."},
            "NBIS": {"status": "nepotvrđeno", "napomena": "Nebius Group je strana (nizozemska) holding tvrtka čijim se dionicama trguje u SAD-u; pojedinosti oko ADR-a/statusa kod IBKR-a su nepotvrđeno. Povijest prije 2024-10-21 je zaustavljena trgovina (stara tvrtka) i ne koristi se."},
            "VRT": {"status": "nepotvrđeno", "napomena": "Američka dionica, USD. Prije 2020-02 cijena je SPAC (GSAH) oko 10 USD, pa je kontekstni prozor od 2018 nepouzdan; AI era nije pogođena."},
        },
        "iskljuceno": "CRWV (CoreWeave) nije analiziran: povijest je prekratka (388 dana u AI eri, 192 prije 2026). Nije tvrdnja o dostupnosti ili vrijednosti.",
    }


def main() -> None:
    seg = load(RES / "results" / "cloud.json")
    per_ticker = {t: load(RES / "results" / f"{t}.json") for t in TICKERS}
    summ = load(RES / "summary.json")
    prof = load(RES / "segments" / "cloud" / "profile.json")

    ticker_rows, seg_rows = build_tables(seg, per_ticker)
    winner, cands = pick_winner(seg)
    wid = winner["suparnik"]
    wseg = ai(seg["contenders"][wid])
    hseg = ai(seg["contenders"][BENCH])
    dd_hold = worst_drawdown(seg, BENCH)
    dd_win = worst_drawdown(seg, wid)
    beats_hold = {cid: ai(c)["total_return"] > hseg["total_return"] for cid, c in seg["contenders"].items() if cid != BENCH}
    runner = next(c for c in cands if c["kvalificiran"] and c["suparnik"] != wid)
    k6 = ai(seg["contenders"]["K6_MOMENTUM_CS"])

    # per-ticker contribution of the winner (concentration is reported, never penalised)
    contrib = {}
    for t in TICKERS:
        w = ai(per_ticker[t]["contenders"][wid])
        contrib[t] = r4(1000 * w["total_return"])
    vrt_share = contrib["VRT"] / sum(contrib.values())

    algo = algo_texts(per_ticker)
    cards = []
    for t in TICKERS:
        c = card(t, prof, per_ticker[t])
        c["sto_to_znaci_za_algoritam"] = algo[t]
        cards.append(c)

    ratings = [rate(cid, seg, summ) for cid in seg["contenders"] if cid != BENCH]
    ratings.insert(0, {"suparnik": BENCH, "naziv": NAMES[BENCH], "ocjena": "mjerilo", "napomene": ["Nije strategija, nego mjerilo (kupi i drži); ne ocjenjuje se."]})
    rating_of = {r["suparnik"]: r["ocjena"] for r in ratings}

    analysis: dict[str, Any] = {
        "segment": "cloud",
        "naziv": prof["naziv"],
        "izvor": "Brojke su kopirane iz results/*.json, summary.json, segments/cloud/profile.json i data/ohlcv/*_1d.csv; ništa nije izmišljeno. Istraživanje, nije savjet za ulaganje, nije Critic PASS; agenti ne šalju naloge.",
        "prozor": {"ai_era_od": "2023-01-01", "do": seg["contenders"][BENCH]["windows"]["ai_era"]["end"], "napomena": "NBIS počinje tek 2024-10-21 (prije toga zaustavljena trgovina); do tada njegov novac u simulatoru miruje kao gotovina."},
        "audit_status": "FIXED (zamrznuta/obustavljena povijest izbačena, loš tick NVDA, trošak izlaza na kraju, jači test pogleda unaprijed); poznata ograničenja: robusnost +-20 % gleda samo predznak, B0 kupuje na otvaranju prvog dana kotacije, CAGR je jedan dan kraći.",
        "zasto_zajedno": {
            "tekst": (
                "Ovih sedam tvrtki spaja jedna stvar: ulaganja u podatkovne centre za umjetnu inteligenciju (capex = novac potrošen na zgrade, struju, hlađenje i čipove). "
                "Microsoft, Amazon, Google i Meta kupuju GPU-ove i memoriju (HBM), pa su kupci lanca iznad sebe (NVDA, MU). "
                "Oracle i Nebius iznajmljuju računalnu snagu drugima, uglavnom uz zaduživanje. Vertiv prodaje napajanje i hlađenje podatkovnim centrima i zarađuje od ukupnog capexa, ne od toga koji oblak pobijedi. "
                "Primjer: kad oblaci povećaju ulaganja za 1.000 EUR, dio toga ode Vertivu i čipovima, a oblaci sami moraju dokazati da prihod opravdava trošak. [kontekst iz javnih izvora, nije iz naših podataka]"
            ),
            "pokretaci": [
                "Capex ciklus: dizanje ulaganja prvo hrani dobavljače (VRT, čipovi), a ulagači kod samih oblaka sumnjaju u povrat (META, ORCL, MSFT).",
                "Zaduženost i ugovori: ORCL i NBIS grade unaprijed na dug uz ugovore s velikim kupcima; ako kupac odgodi, financiranje postaje problem.",
                "Oglašavanje i softver kao drugi pokretač kod META-e, GOOGL-a i MSFT-a (dionica nije samo AI).",
            ],
            "oznaka": "kontekst iz javnih izvora, nije iz naših podataka",
            "iz_nasih_podataka": (
                "Iz naših podataka (AI era): volatilnost raste kako se ide od velikih oblaka (MSFT 26 %, GOOGL 31 %, AMZN 33 %, META 39 %) prema ORCL (47 %), VRT (62 %) i NBIS (113 %). "
                "Primjer: 1.000 EUR u MSFT-u tipično njiše oko 263 EUR godišnje, a u NBIS-u oko 1.133 EUR."
            ),
            "mehanizmi_po_tickeru": {c["ticker"]: c["kontekst_iz_javnih_izvora"] for c in cards},
        },
        "kartice": cards,
        "tablica_po_tickeru": ticker_rows,
        "tablica_segment": seg_rows,
        "segment_postavke": "Jednak kapital po tickeru (7 x 1.000 EUR = 7.000 EUR), bez prelijevanja među tickerima; cijene u USD tretirane kao EUR-ekvivalent (tečaj nije modeliran). Trošak 2,5 bps po strani, stres 2x i 3x.",
        "pobjednik": {
            "definicija_unaprijed": "Pobjednik = najviši Sharpe u AI eri među suparnicima (bez B0 mjerila) s najmanje 20 poslova na segmentu i pozitivnim prinosom uz trošak 2x.",
            "kandidati": cands,
            "pobjednik": wid,
            "naziv": NAMES[wid],
            "ocjena_pobjednika": rating_of[wid],
            "brojke": {
                "sharpe": r4(wseg["sharpe"]),
                "prinos": r4(wseg["total_return"]),
                "prinos_uz_trosak_2x": r4(wseg["total_return_cost_2x"]),
                "prinos_uz_trosak_3x": r4(wseg["total_return_cost_3x"]),
                "poslova": wseg["trades"],
                "max_drawdown": r4(wseg["max_drawdown"]),
            },
            "drzanje": {
                "sharpe": r4(hseg["sharpe"]),
                "prinos": r4(hseg["total_return"]),
                "max_drawdown": r4(hseg["max_drawdown"]),
            },
            "pobjeduje_drzanje_u_prinosu": beats_hold[wid],
            "ijedan_suparnik_pobjeduje_drzanje_u_prinosu": any(beats_hold.values()),
            "najblizi_drzanju": {
                "suparnik": "K6_MOMENTUM_CS",
                "prinos": r4(k6["total_return"]),
                "prinos_drzanja": r4(hseg["total_return"]),
                "max_drawdown": r4(k6["max_drawdown"]),
                "sharpe": r4(k6["sharpe"]),
            },
            "drugi_po_sharpeu": runner,
            "najgori_pad_drzanje": dd_hold,
            "najgori_pad_pobjednik": dd_win,
            "smanjenje_najgoreg_pada_po_1000_eur": r4(dd_hold["gubitak_na_papiru_eur_po_1000_na_vrhu"] - dd_win["gubitak_na_papiru_eur_po_1000_na_vrhu"]),
            "doprinos_po_tickeru_eur_na_1000": contrib,
            "udio_VRT_u_dobiti_pobjednika": r4(vrt_share),
            "tekst": (
                f"Prema unaprijed zadanoj definiciji pobjednik je {NAMES[wid]} (Sharpe {_num(wseg['sharpe'],2)}, {wseg['trades']} poslova, prinos uz trošak 2x {pct(wseg['total_return_cost_2x'])}). "
                f"Nitko ne pobjeđuje držanje u prinosu: držanje je {pct(hseg['total_return'],0)} (Sharpe {_num(hseg['sharpe'],2)}), pobjednik {pct(wseg['total_return'],0)}. "
                f"Na 1.000 EUR u svakom od 7 tickera to je na kraju {eur(hseg['end_value']/7)} kod držanja naspram {eur(wseg['end_value']/7)} kod pobjednika. "
                f"Pobjednik je ipak skratio najgori pad: držanje je od vrha {dd_hold['vrh']} do dna {dd_hold['dno']} palo {pct(-dd_hold['pad'])}, pobjednik od {dd_win['vrh']} do {dd_win['dno']} {pct(-dd_win['pad'])} (to su različita razdoblja; svaki je mjeren na svojoj krivulji). "
                f"Na 1.000 EUR na vrhu to je najgori gubitak od {eur(dd_hold['gubitak_na_papiru_eur_po_1000_na_vrhu'])} kod držanja naspram {eur(dd_win['gubitak_na_papiru_eur_po_1000_na_vrhu'])} kod strategije, dakle {eur(dd_hold['gubitak_na_papiru_eur_po_1000_na_vrhu']-dd_win['gubitak_na_papiru_eur_po_1000_na_vrhu'])} manje (na cijelom segmentu od 7.000 EUR: {eur(dd_hold['gubitak_na_papiru_eur_segment'])} naspram {eur(dd_win['gubitak_na_papiru_eur_segment'])}). "
                f"Cijena za to je {eur((hseg['end_value']-wseg['end_value'])/7)} manje završne vrijednosti po 1.000 EUR. "
                f"K6 rotacija je najbliža držanju ({pct(k6['total_return'],0)} i Sharpe {_num(k6['sharpe'],2)}, pad {pct(-k6['max_drawdown'])}), a razlika Sharpea između K5B i K6 ({_num(wseg['sharpe']-k6['sharpe'],3)}) je premala da bi bila dokaz. "
                f"Oko {_num(vrt_share*100,0)} % zbroja dobiti po tickerima pobjednika dolazi iz VRT-a (koncentracija se samo bilježi, ne snižava ocjenu)."
            ),
            "upozorenja_hr": [
                "Odabir 7 tvrtki je napravljen znajući da su u AI eri porasle (pristranost unatrag); držanje je zato u ovom uzorku neobično visoko.",
                "K = 533 pokušaja u ledgeru: deflated Sharpe vjerojatnost pobjednika je " + _num(wseg["deflated_sharpe_prob"], 2) + " (informativno, ne snižava ocjenu).",
                "Pobjednik ima žutu ocjenu jer robusnost +-20 % nije mjerena za K5B u ovom segmentu.",
            ],
        },
        "c13c": c13c_report(per_ticker, seg, summ),
        "ocjene": ratings,
        "pravilo_ocjene": "Blaga ocjena rizika: ocjena se snižava samo zbog NEVALJANOG dokaza (pogled u budućnost, ugađanje ili krhkost parametara, premalo poslova, trošak), nikad zbog veličine pada, volatilnosti ili koncentracije. Crveno = nevaljan dokaz; žuto = valjan dokaz s rupom (nema mjerene robusnosti, PSR ispod 0,95, krhkost ili oznaka ugađanja); zeleno = nema rupa.",
        "eu_hr": eu_notes(),
        "biljeske_za_grafove": chart_notes(),
        "ogranicenja": [
            "Tečaj EUR/USD, dividende, porezi i minimalna IBKR provizija nisu modelirani (nepotvrđeno za Petrov tarif).",
            "Razlomljene dionice kod IBKR-a su nepotvrđene; simulator ih pretpostavlja.",
            "NBIS ima samo oko 490 dana podataka; svi zaključci o njemu su slabi.",
            "Jedan segment s 7 tickera je mali uzorak; važniji je obrazac koji se ponavlja kroz više segmenata.",
        ],
    }
    OUT.write_text(json.dumps(analysis, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", OUT, "winner", wid, rating_of)


if __name__ == "__main__":
    main()
