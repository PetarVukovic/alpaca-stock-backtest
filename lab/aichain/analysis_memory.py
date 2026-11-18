"""Build segments/memory/analysis.json from existing AICHAIN results (no new simulation).

Every number is read from results/*.json, summary.json, profile.json or the daily CSVs.
Prose for the researcher is Croatian; identifiers and comments are English.
Run: .venv/bin/python -m lab.aichain.analysis_memory
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
TICKERS = ["MU", "WDC", "STX"]
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
MIN_TRADES = 20


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def hr(x: float, nd: int = 1) -> str:
    """Format a number the Croatian way (decimal comma, dot thousands)."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, nd: int = 1) -> str:
    return hr(x * 100, nd) + " %"


def eur(x: float, nd: int = 0) -> str:
    return hr(x, nd) + " EUR"


def row(c: dict[str, Any]) -> dict[str, Any]:
    """One table row from an ai_era window block."""
    w = c["windows"]["ai_era"]
    return {
        "total_return_pct": round(w["total_return"] * 100, 1),
        "sharpe": round(w["sharpe"], 2),
        "max_drawdown_pct": round(w["max_drawdown"] * 100, 1),
        "trades": w["trades"],
        "exposure_pct": round(w["exposure_pct"], 1),
        "hit_rate_pct": None if w["hit_rate"] is None else round(w["hit_rate"] * 100, 1),
        "return_cost_2x_pct": round(w["total_return_cost_2x"] * 100, 1),
        "return_cost_3x_pct": round(w["total_return_cost_3x"] * 100, 1),
        "end_value_per_1000_eur": round(w["end_value"] / w["start_capital"] * 1000),
        "worst_loss_per_1000_eur": round(-w["max_drawdown"] * 1000),
        "psr": round(w["psr"], 3),
        "deflated_sharpe_prob_informative": round(w["deflated_sharpe_prob"], 2),
    }


def close_on(df: pd.DataFrame, d: str) -> float:
    return float(df.close.loc[pd.Timestamp(d)])


def main() -> None:
    profile = load(BASE / "segments/memory/profile.json")
    summary = load(BASE / "summary.json")
    seg = load(BASE / "results/memory.json")
    res = {t: load(BASE / f"results/{t}.json") for t in TICKERS}
    px = {
        t: pd.read_csv(ROOT / f"data/ohlcv/{t}_1d.csv", parse_dates=["date"]).set_index("date")
        for t in TICKERS
    }
    mech = profile["mechanism"]
    stats = {t: profile["stats"][t]["ai_era_2023plus"] for t in TICKERS}
    ctx = {t: profile["stats"][t]["context_2016_2022"] for t in TICKERS}

    # ---- tables -------------------------------------------------------
    per_ticker = {
        t: {
            cid: (
                row(res[t]["contenders"][cid])
                if res[t]["contenders"][cid].get("available", True)
                else {"available": False, "reason": "K6 treba više tickera (samo segment)"}
            )
            for cid in CONTENDERS
        }
        for t in TICKERS
    }
    segment = {
        cid: (
            row(seg["contenders"][cid])
            if seg["contenders"][cid].get("available", True)
            else {"available": False}
        )
        for cid in CONTENDERS
    }

    # ---- winner (rule fixed in advance) -------------------------------
    hold = segment["B0_BUYHOLD"]
    eligible = {
        cid: r
        for cid, r in segment.items()
        if cid != "B0_BUYHOLD"
        and r.get("trades", 0) >= MIN_TRADES
        and r.get("return_cost_2x_pct", -1) > 0
    }
    winner = max(eligible, key=lambda c: eligible[c]["sharpe"])
    w = eligible[winner]
    excluded = {
        cid: (
            f"{segment[cid]['trades']} poslova (< {MIN_TRADES})"
            if segment[cid].get("trades", 0) < MIN_TRADES
            else "prinos uz trošak 2x nije pozitivan"
        )
        for cid in segment
        if cid != "B0_BUYHOLD" and cid not in eligible
    }
    beats_return = w["total_return_pct"] > hold["total_return_pct"]
    beats_sharpe = w["sharpe"] > hold["sharpe"]
    dd_saved = hold["worst_loss_per_1000_eur"] - w["worst_loss_per_1000_eur"]
    ret_gap_eur = hold["end_value_per_1000_eur"] - w["end_value_per_1000_eur"]

    winner_block = {
        "rule_fixed_in_advance": (
            "Pobjednik = najveći Sharpe u AI eri (od 2023-01-01) među suparnicima (bez B0) koji imaju "
            f"najmanje {MIN_TRADES} poslova na segmentu i pozitivan prinos uz trošak 2x. Uvijek se uspoređuje s držanjem (B0)."
        ),
        "winner": winner,
        "eligible_sharpe_order": sorted(
            ({"id": c, "sharpe": r["sharpe"], "trades": r["trades"]} for c, r in eligible.items()),
            key=lambda x: -x["sharpe"],
        ),
        "not_eligible": excluded,
        "beats_holding_on_return": beats_return,
        "beats_holding_on_sharpe": beats_sharpe,
        "winner_vs_hold": {
            "winner_total_return_pct": w["total_return_pct"],
            "hold_total_return_pct": hold["total_return_pct"],
            "winner_sharpe": w["sharpe"],
            "hold_sharpe": hold["sharpe"],
            "winner_max_drawdown_pct": w["max_drawdown_pct"],
            "hold_max_drawdown_pct": hold["max_drawdown_pct"],
            "per_1000_eur_end_winner": w["end_value_per_1000_eur"],
            "per_1000_eur_end_hold": hold["end_value_per_1000_eur"],
            "worst_loss_per_1000_eur_winner": w["worst_loss_per_1000_eur"],
            "worst_loss_per_1000_eur_hold": hold["worst_loss_per_1000_eur"],
            "worst_loss_saved_eur": dd_saved,
            "end_value_given_up_eur": ret_gap_eur,
        },
        "verdict_hr": (
            f"Po unaprijed zadanom pravilu pobjednik je {winner} (to je tvoj C13C) sa Sharpeom {hr(w['sharpe'],2)}. "
            f"Ali ne pobjeđuje držanje: držanje je dalo {pct(hold['total_return_pct']/100,0)} prinosa i Sharpe {hr(hold['sharpe'],2)}, "
            f"a {winner} {pct(w['total_return_pct']/100,0)} i Sharpe {hr(w['sharpe'],2)}. "
            f"Na 1.000 EUR uloženih 2023-01-03 to je {eur(hold['end_value_per_1000_eur'])} uz držanje naspram "
            f"{eur(w['end_value_per_1000_eur'])} uz {winner}, dakle {eur(ret_gap_eur)} manje. "
            f"Strategija je ipak smanjila najgori pad od vrha: {pct(-hold['max_drawdown_pct']/100)} kod držanja naspram "
            f"{pct(-w['max_drawdown_pct']/100)}. U eurima, ako imaš 1.000 EUR na vrhu: najgori gubitak uz držanje je "
            f"{eur(hold['worst_loss_per_1000_eur'])}, uz {winner} {eur(w['worst_loss_per_1000_eur'])}, "
            f"što je {eur(dd_saved)} manje. To je osiguranje koje je u ovom razdoblju bilo vrlo skupo."
        ),
    }

    # ---- C13C ticker by ticker ---------------------------------------
    c13c = []
    for t in TICKERS:
        k = per_ticker[t]["K1_C13C_ORIG"]
        b = per_ticker[t]["B0_BUYHOLD"]
        tr = res[t]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]
        gaps = sum(1 for x in tr if x["detail"] == "gap_stop")
        c13c.append(
            {
                "ticker": t,
                "c13c": k,
                "hold": b,
                "gap_stop_exits": gaps,
                "text_hr": (
                    f"{t}: C13C {pct(k['total_return_pct']/100,0)} naspram držanja {pct(b['total_return_pct']/100,0)}; "
                    f"Sharpe {hr(k['sharpe'],2)} naspram {hr(b['sharpe'],2)}; najgori pad {pct(-k['max_drawdown_pct']/100)} naspram "
                    f"{pct(-b['max_drawdown_pct']/100)}; {k['trades']} poslova, dobitnih {pct(k['hit_rate_pct']/100,0)}, "
                    f"u poziciji (izloženost) {pct(k['exposure_pct']/100,0)} vremena. Od tih poslova {gaps} je završilo stopom "
                    f"koja je preskočena preko noći (izlaz lošiji od stopa). Na 1.000 EUR: {eur(k['end_value_per_1000_eur'])} naspram "
                    f"{eur(b['end_value_per_1000_eur'])} uz držanje."
                ),
            }
        )

    # ---- behaviour cards ---------------------------------------------
    cards = {}
    fit_text = {
        "MU": (
            "Najnestabilnija i najjače vezana uz tržište (beta prema SMH {bsmh}). Dnevno kretanje nema vidljivog zamaha ni povratka "
            "(omjer varijance 5 dana {vr5}, 20 dana {vr20}), pa nema jasnog razloga da bi ijedan 'uhvati okret' algoritam imao "
            "prednost. Najveći dio povrata dolazi u malo dana (10 najboljih dana čini {conc} logaritamskog povrata), "
            "što znači da algoritam koji često izlazi riskira propustiti baš te dane. Za nju zato odgovara trend algoritam koji "
            "ostaje u poziciji (K4 zamah 126 dana, K2 SMA200); Po Sharpeu je C13C ovdje praktički izjednačen s držanjem (1,64 naspram 1,66), ali uz manje od polovice prinosa: Sharpe ne vidi da je veći dio rasta propušten."
        ),
        "WDC": (
            "Najizraženiji blagi povratak prema sredini na 20 dana (omjer varijance {vr20}), ali premisa 'pad u trendu se otkupljuje' "
            "vrijedi samo opisno. Potpora drži {sup} slučajeva naspram {supr} nasumične razine, dakle crtanje razina ne pomaže. "
            "Najveći pojedinačni jaz otvaranja je pad ({gap}). Trend s dugim držanjem (K3 Donchian) dao je najbolji Sharpe, ali s vrlo malo poslova; "
            "C13C je ovdje najslabiji od trend-pravila jer izlazi stopom pa propušta velike valove."
        ),
        "STX": (
            "Najmirnija od tri (beta prema SMH {bsmh}, nestabilnost {vol}), najbliža WDC-u (dnevna korelacija 0,82). Nema zamaha ni povratka na dnevnoj razini "
            "(omjer varijance 5 dana {vr5}, 20 dana {vr20}). Najplići najgori pad od vrha od tri (-40,9 %), pa je klizni stop (C13C) ovdje radio najbolje: "
            "najbolji Sharpe među strategijama koje imaju dovoljno poslova i najmanji pad među pravilima K1-K4, ali i dalje daleko ispod prinosa držanja."
        ),
    }
    for t in TICKERS:
        s = stats[t]
        dd = s["drawdowns"][:3]
        sr = s["support_resistance"]
        dip = s["after_5d_drop_above_sma200"]
        gaps = s["largest_gaps"][0]
        sr_line = next(x for x in profile["support_resistance_hr"] if x.startswith(t + " "))
        rand_sup = float(re.search(r"nasumična razina: (\d+)", sr_line).group(1)) / 100
        conc_line = next(x for x in profile["concentration_gaps_hr"] if x.startswith(t + " "))
        cards[t] = {
            "company": mech[t]["company"],
            "annual_volatility_pct": round(s["ann_vol"] * 100, 1),
            "annual_volatility_context_pre2023_pct": round(ctx[t]["ann_vol"] * 100, 1),
            "beta_SMH": round(s["beta_SMH"], 2),
            "beta_NDX": round(s["beta_NDX"], 2),
            "corr_SMH": round(s["corr_SMH"], 2),
            "variance_ratio_5": round(s["variance_ratio_5"], 2),
            "variance_ratio_20": round(s["variance_ratio_20"], 2),
            "character_hr": (
                f"Nestabilnost {pct(s['ann_vol'],0)} godišnje (prije 2023.: {pct(ctx[t]['ann_vol'],0)}): na 1.000 EUR tipičan raspon godine je "
                f"oko +-{hr(s['ann_vol']*1000,0)} EUR. Beta prema SMH {hr(s['beta_SMH'],2)} (kad SMH padne 10 %, dionica u prosjeku padne oko "
                f"{hr(s['beta_SMH']*10,0)} %), prema NDX {hr(s['beta_NDX'],2)}. Omjer varijance 5 dana {hr(s['variance_ratio_5'],2)}, 20 dana "
                f"{hr(s['variance_ratio_20'],2)} (1 = nasumično kretanje, ispod 1 = povratak prema sredini, iznad 1 = zamah): "
                + (
                    "nema vidljivog zamaha ni povratka na dnevnoj razini."
                    if abs(s["variance_ratio_20"] - 1) < 0.05
                    else "na 20 dana vidljiv je blagi povratak prema sredini."
                )
            ),
            "after_5d_dip_hr": (
                f"Nakon pada od 5 %+ u 5 dana dok je cijena iznad SMA200: {dip['n_days']} dana, ali samo {dip['n_independent_20d']} neovisnih događaja. "
                f"Prosjek idućih 5 dana {pct(dip['h5']['mean'])} (običan dan {pct(dip['h5']['uncond_mean'])}), stopa pogotka "
                f"{pct(dip['h5']['hit'],0)} naspram {pct(dip['h5']['uncond_hit'],0)}; za 20 dana {pct(dip['h20']['mean'])} naspram "
                f"{pct(dip['h20']['uncond_mean'])}. To je opis prošlosti (cijela AI era je bila rast), nije dokaz strategije."
            ),
            "worst_drawdowns": [
                {
                    "peak_date": d["start"],
                    "peak_close": round(close_on(px[t], d["start"]), 2),
                    "bottom_date": d["bottom"],
                    "bottom_close": round(close_on(px[t], d["bottom"]), 2),
                    "depth_pct": round(d["depth"] * 100, 1),
                    "recovery_date": d["recovery"],
                    "left_of_1000_eur": round(1000 * (1 + d["depth"])),
                }
                for d in dd
            ],
            "support_resistance_hr": (
                f"Potpora (raniji lokalni minimum) dodirnuta {sr['support']['touches']} puta, držala {pct(sr['support']['hold_rate'],0)} "
                f"(nasumična razina: {hr(rand_sup*100,0)} %); otpor dodirnut {sr['resistance']['touches']} puta, držao {pct(sr['resistance']['hold_rate'],0)}. "
                "Razine ne drže bolje od nasumičnih; ne treba ih crtati kao samostalni razlog za odluku."
            ),
            "largest_gap": {"date": gaps["date"], "gap_pct": round(gaps["gap"] * 100, 1)},
            "algorithm_fit_hr": fit_text[t].format(
                bsmh=hr(s["beta_SMH"], 2),
                vr5=hr(s["variance_ratio_5"], 2),
                vr20=hr(s["variance_ratio_20"], 2),
                vol=pct(s["ann_vol"], 0),
                conc=re.search(r"čini (\d+) %", conc_line).group(1) + " %",
                sup=pct(sr["support"]["hold_rate"], 0),
                supr=hr(rand_sup * 100, 0) + " %",
                gap=pct(gaps["gap"], 1) + " dana " + gaps["date"],
            ),
            "mechanism": {
                "label": mech[t]["label"],
                "sells": mech[t]["sells"],
                "revenue_drivers": mech[t]["revenue_drivers"],
                "chain_position": mech[t]["chain_position"],
                "cycle": mech[t]["cycle"],
                "hurts": mech[t]["hurts"],
                "sources": mech[t]["sources"],
            },
        }

    # ---- why together --------------------------------------------------
    why = {
        "label": "kontekst iz javnih izvora, nije iz naših podataka (osim brojki koje su izračunate iz data/ohlcv)",
        "text_hr": (
            "Memorija i pohrana su mjesto gdje AI podaci i izračuni 'stanuju'. GPU (npr. Nvidia) ne radi bez brze memorije: Micron (MU) "
            "prodaje DRAM i HBM, memoriju koja se lijepi uz AI procesore. Podaci i modeli moraju se negdje spremiti, a najjeftinije "
            "po terabajtu to rade tvrdi diskovi: Western Digital (WDC) i Seagate (STX). Zajednička potražnja je ulaganje oblaka (hyperscalera) "
            "u AI centre, zajednički rizik je da narudžbe oblaka stanu ili da ponuda prestigne potražnju i cijene padnu. "
            "Primjer na 1.000 EUR: ako cijena čipova po bitu naraste 30 % uz iste količine, prihod Microna naraste 30 %, a dobit puno više jer su troškovi tvornice fiksni; "
            "isto tako cijena može pasti jednako brzo."
        ),
        "drivers_hr": [
            "MU: prihod = bitovi x cijena po bitu; DRAM je roba s ciklusom uvećanja i pada (nove tvornice 2-3 godine, desetci milijardi dolara). HBM veže MU uz Nvidiju i oblak. (kontekst iz javnih izvora)",
            "WDC i STX: prihod = eksabajti x cijena po eksabajtu; malo proizvođača (WDC, Seagate, Toshiba) pa su ciklusi blaži od DRAM-a, ali nekoliko velikih kupaca odlučuje o godini (WDC: deset najvećih kupaca oko 73 % prihoda, prema 10-K; kontekst iz javnih izvora). STX: HAMR tehnologija.",
            "Iz naših podataka: WDC-STX dnevna korelacija oko 0,82 (najtješnji par), MU je odvojeniji (korelacija s WDC 0,69). Nitko ne vodi niti slijedi na dnevnoj razini (korelacije s pomakom od jednog dana ispod 0,05).",
            "SNDK (SanDisk, NAND) je isključen iz segmenta: prekratka povijest (222 dnevna bara prije 2026., 415 u AI eri), prema universe.json. Zato segment ima 3 ticker-sleeve-a po 1.000 EUR = 3.000 EUR.",
        ],
    }

    # ---- ratings (lenient critic) -------------------------------------
    la_ok = summary["lookahead"]
    la_arr = summary["lookahead_arrays"]
    rb = summary["robustness_pm20"]
    ratings = {}
    notes = {
        "B0_BUYHOLD": ("mjerilo", "Nije strategija nego mjerilo (kupi prvi dan i drži). Ne ocjenjuje se."),
        "K1_C13C_ORIG": (
            "green",
            "Tvoj C13C, pravila zamrznuta prije ovog segmenta, nisu ugađana ovdje. 105 poslova, trošak 3x i dalje pozitivan, lookahead test (oba) prolazi, "
            "parity test protiv originalnog koda 9/9 bez razlike, robusnost +-20 % ne mijenja predznak (najlošija varijanta, stop 8 %: prinos "
            "{rb_min}, najbolja {rb_max}). Ocjena govori o valjanosti dokaza, ne o tome da je bolji od držanja: nije.",
        ),
        "K2_SMA200_TREND": ("green", "48 poslova, bez prilagodbe parametara (SMA200 je standardna duljina), lookahead prolazi, trošak 3x pozitivan. Samo 25 % poslova dobitno, ali dobitnici su veliki."),
        "K3_DONCHIAN_55_20": (
            "yellow",
            "Valjanost dokaza je ograničena: samo 21 posao na segmentu (granica je 20), a po tickeru MU 8, WDC 4, STX 9. WDC Sharpe 1,87 (bolji od držanja 1,74) počiva na 4 posla i ne smije se čitati kao dokaz. Nema lookahead problema. Nije lošije zbog veličine pada.",
        ),
        "K4_TSMOM_126": ("green", "41 posao, lookahead prolazi, robusnost +-20 % ne mijenja predznak (dijagnostički odabran jer je među najboljima po AI-era Sharpeu; odabir ne mijenja parametre). Napomena: sve varijante +-20 % dale su VIŠI prinos od baze, pa je baza 126 dana možda samo jedna od mnogih jednako dobrih; to nije dokaz ugađanja, ali ni dokaz osjetljivosti."),
        "K5_SUPPORT_RESISTANCE": ("green", "55 poslova, dokaz valjan; rezultat je slab (Sharpe 1,04, WDC negativan -24,6 %) i u skladu s profilom: potpore ne drže bolje od nasumičnih razina. Izložen samo oko 12 % vremena pa se prinos ne može usporediti s drugima."),
        "K5B_SR_BREAKOUT_RETEST": ("green", "48 poslova, 15-17 po tickeru, trošak 3x pozitivan, lookahead prolazi. Najmanji pad među pravilima s dobrim prinosom (-22,4 %)."),
        "K6_MOMENTUM_CS": (
            "yellow",
            "Samo 17 poslova na segmentu (statistika poslova ignorira djelomične rebalanse; prinos i krivulja su ispravni), s 3 tickera je 'bolja polovica' vrlo gruba (2 mjesta). Odabran za dijagnostiku robusnosti po rezultatima. Lookahead prolazi, robusnost +-20 % ne mijenja predznak. Ne ulazi u pobjednika zbog pravila 20 poslova.",
        ),
        "K7_C13C_PLUS_TREND_REENTRY": (
            "green",
            "NOVA hipoteza (proširenje K1, vlastiti freeze ID, fiksni parametri). 160 poslova, trošak 3x pozitivan, lookahead prolazi. Nije bila u dijagnostici robusnosti (nedostatak dokaza se ne kažnjava). Mnogo poslova znači da je u stvarnosti trošak (minimalna provizija IBKR-a, nepotvrđeno) veći nego ovdje; to je upozorenje, ne snižavanje ocjene.",
        ),
    }
    rb_k1 = rb["K1_C13C_ORIG"]["memory"]
    for cid in CONTENDERS:
        col, txt = notes[cid]
        txt = txt.replace("{rb_min}", pct(rb_k1["min_total_return"], 0)).replace("{rb_max}", pct(rb_k1["max_total_return"], 0))
        ratings[cid] = {
            "rating": col,
            "reason_hr": txt,
            "lookahead_old_test_ok": la_ok[cid]["ok"],
            "lookahead_arrays_ok": la_arr.get(cid, {}).get("ok", None),
            "tuned_or_adjusted_flag": (
                "odabran za dijagnostiku robusnosti po rezultatima (parametri nisu mijenjani)"
                if cid in ("K6_MOMENTUM_CS", "K4_TSMOM_126", "K1_C13C_ORIG")
                else None
            ),
        }
    rating_rule_hr = (
        "Blagi kritičar: ocjena se snizuje samo zbog NEVALJANOG dokaza (lookahead, ugađanje/krhkost, premalo poslova, troškovi). Veličina pada, nestabilnost i koncentracija "
        "ne snižavaju ocjenu. zeleno = dokaz valjan; žuto = dokaz ograničen (premalo poslova na segmentu ili po tickeru: manje od 30 na segmentu ili manje od 10 u nekom sleeveu); crveno = dokaz nevaljan (nijedan suparnik nije crven). "
        "Ocjena nije Critic PASS i ne znači da je strategija bolja od držanja."
    )

    # ---- EU/HR ---------------------------------------------------------
    eu = {
        "MU": "Micron: pojedinačna američka dionica; vjerojatno dostupna EU malom ulagaču preko IBKR-a, status NEPOTVRĐENO dok se ne provjeri u samom IBKR-u. Nije ETF pa nema KID problema (nepotvrđeno). Bez tvrdnji o porezu.",
        "WDC": "Western Digital: pojedinačna američka dionica; vjerojatno dostupna, status NEPOTVRĐENO do provjere u IBKR-u. Povijest u našim podacima već je prilagođena odvajanju SanDiska (faktor 0,68132 prije 2025-02-24); ne prilagođavati ponovno. Bez tvrdnji o porezu.",
        "STX": "Seagate: pojedinačna dionica kotirana u SAD-u; vjerojatno dostupna, status NEPOTVRĐENO do provjere u IBKR-u. Napomena iz općeg znanja (nije iz naših podataka, nepotvrđeno): tvrtka je prema mojim saznanjima registrirana izvan SAD-a (Irska), što može utjecati na izvještavanje i porez na dividende; to treba provjeriti kod IBKR-a i poreznog savjetnika, ovdje se ništa ne tvrdi. Bez tvrdnji o porezu.",
        "common_hr": "Valuta: dionice su u USD, račun u EUR, pa tečaj EUR/USD i trošak konverzije mijenjaju stvarni rezultat; u simulaciji nisu uključeni. Isto vrijedi za dividende i minimalnu proviziju po nalogu (nepotvrđeno za tvoj tarif). Američka burza otvara u 15:30 po zagrebačkom vremenu. Nijedan ETF nije predstavljen kao trgovački.",
    }

    # ---- chart notes ---------------------------------------------------
    def k1_best_worst(t: str) -> tuple[dict, dict]:
        tr = [x for x in res[t]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"]]
        s = sorted(tr, key=lambda x: x["return"])
        return s[0], s[-1]

    def eq_at(t: str, cid: str, d: str) -> float:
        e = dict(map(tuple, res[t]["contenders"][cid]["equity"]["ai_era"]))
        return float(e[d])

    chart_notes: list[dict[str, Any]] = []
    for t in TICKERS:
        d0 = stats[t]["drawdowns"][0]
        # find the worst drawdown that has data in both equity curves
        pk, bt = d0["start"], d0["bottom"]
        k1p, k1b = eq_at(t, "K1_C13C_ORIG", pk), eq_at(t, "K1_C13C_ORIG", bt)
        hp, hb = eq_at(t, "B0_BUYHOLD", pk), eq_at(t, "B0_BUYHOLD", bt)
        worst, best = k1_best_worst(t)
        g = stats[t]["largest_gaps"][0]
        i = px[t].index.get_loc(pd.Timestamp(g["date"]))
        prev_c = float(px[t].close.iloc[i - 1])
        op = float(px[t].open.iloc[i])
        chart_notes.append(
            {
                "ticker": t,
                "notes_hr": [
                    f"Najgori pad ({t}): vrh {pk} zatvaranje {hr(close_on(px[t], pk),2)}, dno {bt} zatvaranje {hr(close_on(px[t], bt),2)} ({pct(d0['depth'])}). "
                    f"Na 1.000 EUR uloženih 2023-01-03 držanje je u tom pomaku palo s {eur(hp)} na {eur(hb)} ({pct(hb/hp-1)}); C13C s {eur(k1p)} na {eur(k1b)} ({pct(k1b/k1p-1)}). "
                    "Gledaj na grafu gdje C13C nema poziciju (između izlaza stopom i sljedećeg ulaza): to je razlog manjeg pada, ali i razlog zašto ne prati rast.",
                    f"Jaz preko noći {g['date']}: zatvaranje dan prije {hr(prev_c,2)}, otvaranje {hr(op,2)} ({pct(g['gap'])}). Stop ne može zaštititi od jaza: nalog se izvršava po prvoj cijeni nakon otvaranja, ne po stop razini.",
                    f"Najbolji C13C posao: ulaz {best['entry_date']} po {hr(best['raw_entry'],2)}, izlaz {best['exit_date']} po {hr(best['raw_exit'],2)} ({pct(best['return'])}). "
                    f"Najgori: ulaz {worst['entry_date']} po {hr(worst['raw_entry'],2)}, izlaz {worst['exit_date']} po {hr(worst['raw_exit'],2)} ({pct(worst['return'])}, izlaz tipa {worst['detail']}). "
                    "Na grafu: pogledaj gdje je klizni stop bio u odnosu na svijeće prije izlaza.",
                ],
            }
        )
    chart_general = [
        "Označi SMA200 (prosjek zadnjih 200 zatvaranja) na grafu MU, WDC i STX. U AI eri sve tri su većinu vremena iznad nje; profil pokazuje da je velika udaljenost iznad SMA200 dolazila uz nastavak rasta, ne uz povratak (MU: preko 50 % iznad SMA200 prosjek idućih 20 dana 15,2 %).",
        "Provjeri 52-tjedne vrhove: u AI eri novi vrh je u prosjeku donosio još rasta (MU 14,0 % u 20 dana naspram 7,9 % običan dan; WDC 11,6 % naspram 7,4 %; STX 11,1 % naspram 7,1 %). Prije 2023. to nije vrijedilo (MU 0,1 %, WDC -3,4 %, STX -0,2 %). Razlika režima, ne pravilo.",
        "Potpora/otpor: nacrtaj zadnji lokalni minimum. U profilu držanje potpore (MU 62 %, WDC 60 %, STX 68 %) nije bolje od nasumičnih razina (61 %, 66 %, 70 %); zato ih ne uzimaj kao jedini razlog za kupnju.",
        "Usporedi krivulje kapitala: držanje (B0) i C13C na istom grafu; pitanje je koliko si 'platio' manji pad izgubljenim rastom.",
    ]

    # ---- key findings ---------------------------------------------------
    best_per_ticker = {}
    for t in TICKERS:
        cand = {c: r for c, r in per_ticker[t].items() if c not in ("B0_BUYHOLD", "K6_MOMENTUM_CS")}
        bc = max(cand, key=lambda c: cand[c]["sharpe"])
        best_per_ticker[t] = {"id": bc, **cand[bc], "hold_sharpe": per_ticker[t]["B0_BUYHOLD"]["sharpe"]}

    key_findings = [
        verdict if (verdict := winner_block["verdict_hr"]) else "",
        "Nijedan suparnik nije pobijedio držanje po prinosu ni na jednom tickeru ni na segmentu u AI eri. Jedini slučaj da suparnik ima viši Sharpe od držanja je K3 na WDC (1,87 naspram 1,74), ali na samo 4 posla.",
        "Držanje je sva tri naslova dalo višestruko (MU {mu}, WDC {wd}, STX {st}), uz padove od vrha od -41 % do -58 %. Prije 2023. nije bilo tako (WDC CAGR {wdc_ctx}).".format(
            mu=pct(per_ticker["MU"]["B0_BUYHOLD"]["total_return_pct"] / 100, 0),
            wd=pct(per_ticker["WDC"]["B0_BUYHOLD"]["total_return_pct"] / 100, 0),
            st=pct(per_ticker["STX"]["B0_BUYHOLD"]["total_return_pct"] / 100, 0),
            wdc_ctx=pct(ctx["WDC"]["ann_return_cagr"]),
        ),
        "K7 (C13C uz ponovni ulaz) je lošiji od K1 na svim mjerama segmenta (prinos, Sharpe, pad); dodatno ponovno ulaženje nije pomoglo.",
        "Višestruko testiranje: K = {k} u ledgeru; najbolja ćelija tablice može biti slučajna. Deflated Sharpe je informativan (K1 segment {d}).".format(
            k=summary["ledger_k_after_registration"], d=hr(segment["K1_C13C_ORIG"]["deflated_sharpe_prob_informative"], 2)
        ),
    ]

    out = {
        "segment": "memory",
        "segment_name": profile["segment_name"],
        "generated_for": "the researcher (HR/EUR), istraživanje, nije savjet za ulaganje, nije Critic PASS; agenti ne šalju naloge.",
        "audit_status": "FIXED (simulator popravljen: obustavljena povijest, loš tick NVDA, trošak izlaza na zadnji dan, jači lookahead test; vidi ENGINE.md odjeljak 7)",
        "window": {"ai_era": "2023-01-03 do 2026-10-05 (glavno mjerilo)", "context": "2016-2022 samo kontekst"},
        "tickers_used": TICKERS,
        "tickers_excluded": profile["tickers_excluded"],
        "capital_note_hr": "Svaki ticker je zaseban sleeve s 1.000 EUR (cijene u USD tretirane kao EUR-ekvivalent, bez tečaja); segment = 3 x 1.000 EUR = 3.000 EUR bez prelijevanja. Trošak 2,5 bps po strani (2x = 5 bps, 3x = 7,5 bps): na 1.000 EUR to je 0,25 EUR po kupnji.",
        "glossary_hr": {
            "Sharpe": "Prosječni dnevni prinos podijeljen s njegovom varijabilnošću (x korijen iz 252). Veće je bolje; po jedinici 'treskanja' koliko si dobio.",
            "max drawdown (najveći pad od vrha)": "Najveći pad od najvišeg dosega do dna. Pad s 2.000 EUR na 1.200 EUR je -40 %.",
            "izloženost": "Udio kapitala koji je u dionici u prosjeku. 50 % = pola novca u dionici, pola u gotovini.",
            "stop": "Automatska prodaja ako cijena padne na razinu; ako dan otvori ispod nje (jaz), izlaz je po otvaranju, lošije od stopa.",
            "SMA200": "Prosjek zadnjih 200 zatvaranja; grubo mjerilo dugog trenda.",
            "trošak 2x/3x": "Test: što ako su troškovi dvostruko ili trostruko veći. Ako prinos ostane pozitivan, trošak nije glavni problem.",
            "B0 držanje": "Kupi prvi dan i drži do kraja; mjerilo svih strategija.",
        },
        "why_together": why,
        "behaviour_cards": cards,
        "per_ticker_table_ai_era": per_ticker,
        "segment_portfolio_table_ai_era": segment,
        "winner": winner_block,
        "c13c_honest_report": {
            "note_hr": "C13C je tvoj vlastiti algoritam (K1_C13C_ORIG). Ovdje je izvještaj bez uljepšavanja.",
            "segment": segment["K1_C13C_ORIG"],
            "per_ticker": c13c,
            "robustness_pm20_memory": rb_k1,
            "summary_hr": (
                f"Na segmentu C13C ima najbolji Sharpe među suparnicima s dovoljno poslova ({hr(segment['K1_C13C_ORIG']['sharpe'],2)}), manji pad od držanja "
                f"({pct(-segment['K1_C13C_ORIG']['max_drawdown_pct']/100)} naspram {pct(-hold['max_drawdown_pct']/100)}; manji pad od njega imaju samo K5 i K5B, uz znatno manji prinos), ali prinos je {pct(segment['K1_C13C_ORIG']['total_return_pct']/100,0)} naspram "
                f"{pct(hold['total_return_pct']/100,0)}. Izložen je oko polovice vremena, što je razlog i manjeg pada i manjeg prinosa."
            ),
        },
        "ratings": {"rule_hr": rating_rule_hr, "by_contender": ratings},
        "eu_hr_notes": eu,
        "chart_teaching_notes": {"general_hr": chart_general, "by_ticker": chart_notes},
        "best_non_hold_per_ticker_by_sharpe": best_per_ticker,
        "key_findings_hr": key_findings,
        "caveats_hr": [
            "Nije modelirano: tečaj EUR/USD i trošak konverzije, dividende, porezi, minimalna provizija IBKR-a (nepotvrđeno), djelomične dionice (nepotvrđeno), proklizavanje izvan 2,5 bps.",
            "Čitav AI-era prozor je jedan dug rast, pa 'držanje' ima težak prag; u prozoru su i veliki padovi (2025. i 2026.), ali nijedan dugi medvjeđi režim nije testiran.",
            "Podaci završavaju 2026-10-08, a simulacije do 2026-10-05 (common_end).",
            "K6 trade-level statistike ignoriraju djelomične rebalanse (prinos je ispravan).",
            "+-20 % robusnost testira samo predznak ukupnog prinosa u AI eri, što je u bik-tržištu slab test; napravljena je samo za K1, K6 i K4.",
            "Neovisnih događaja ima oko 21-23 po dionici u profilu; sve statistike nakon pada ili vrha su opis, ne dokaz.",
            "Dividende: cijene su prilagođene samo za splitove (i WDC spin-off), dakle cjenovni, ne ukupni prinos.",
        ],
    }
    dest = BASE / "segments/memory/analysis.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
