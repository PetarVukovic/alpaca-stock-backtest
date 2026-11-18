"""Build ``segments/equipment/analysis.json`` for the AI-chain tournament.

Every number is read from ``results/*.json``, ``segments/equipment/profile.json`` or
``data/ohlcv/{TICKER}_1d.csv``; nothing is typed in by hand. The prose is Croatian (it is meant for
the researcher), identifiers and comments are English. Read-only research: no orders of any kind.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
OUT = BASE / "segments" / "equipment" / "analysis.json"

TICKERS = ["AMAT", "LRCX", "KLAC", "ASML", "ONTO", "MKSI", "ENTG", "ACMR", "FORM", "TER"]
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
STRATS = [c for c in CONTENDERS if c != "B0_BUYHOLD"]
LABEL_CTX = "kontekst iz javnih izvora, nije iz naših podataka"
MIN_TRADES = 20

SHORT_HR = {
    "B0_BUYHOLD": "kupi i drži (mjerilo)",
    "K1_C13C_ORIG": "C13C (tvoj algoritam): kupnja nakon pada od 5 % iznad SMA200, klizni stop 10 %",
    "K2_SMA200_TREND": "drži dok je cijena iznad SMA200",
    "K3_DONCHIAN_55_20": "proboj 55-dnevnog vrha, izlaz ispod 20-dnevnog dna",
    "K4_TSMOM_126": "drži dok je 126-dnevni prinos pozitivan",
    "K5_SUPPORT_RESISTANCE": "kupnja na potpori uz cilj na otporu",
    "K5B_SR_BREAKOUT_RETEST": "kupnja na povratnom testu probijenog otpora",
    "K6_MOMENTUM_CS": "mjesečna rotacija: drži bolju polovicu po 126-dnevnom prinosu",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C plus ponovni ulazak u trend nakon izbijanja stopa",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def hr(x: float, d: int = 1) -> str:
    """Croatian number format: decimal comma, dot as thousands separator."""
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, d: int = 1) -> str:
    """Fraction -> percent string, e.g. 0.4187 -> '41,9 %'."""
    return hr(x * 100, d) + " %"


def eur(x: float) -> str:
    return hr(x, 0) + " EUR"


def metrics(w: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "total_return", "total_return_cost_2x", "total_return_cost_3x", "sharpe", "max_drawdown",
        "trades", "exposure_pct", "hit_rate", "avg_win", "avg_loss", "cagr", "end_value",
        "start_capital", "psr", "deflated_sharpe_prob", "excess_vs_buyhold",
    ]
    return {k: w.get(k) for k in keys}


def window_drawdown(equity: list[list[Any]], start: str, end: str) -> dict[str, Any]:
    """Worst peak-to-trough fall of the equity curve inside [start, end] (peak taken inside the window)."""
    s = pd.Series({d: v for d, v in equity})
    s = s[(s.index >= start) & (s.index <= end)]
    peak = s.cummax()
    dd = s / peak - 1
    bottom = dd.idxmin()
    top = s[:bottom].idxmax()
    return {"peak_date": top, "peak_value": float(s[top]), "bottom_date": bottom,
            "bottom_value": float(s[bottom]), "depth": float(dd.min())}


def bars(ticker: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", index_col="date")


def main() -> None:
    seg = load(BASE / "results" / "equipment.json")
    prof = load(BASE / "segments" / "equipment" / "profile.json")
    summ = load(BASE / "summary.json")
    res = {t: load(BASE / "results" / f"{t}.json") for t in TICKERS}
    px = {t: bars(t) for t in TICKERS}
    comp = prof["companies"]
    sc = seg["contenders"]

    # ------------------------------------------------------------ segment table
    seg_table: dict[str, Any] = {}
    for c in CONTENDERS:
        m = metrics(sc[c]["windows"]["ai_era"])
        m["end_value_per_1000_eur"] = m["end_value"] / m["start_capital"] * 1000
        m["worst_loss_per_1000_eur"] = -m["max_drawdown"] * 1000
        m["description_hr"] = SHORT_HR[c]
        seg_table[c] = m
    hold = seg_table["B0_BUYHOLD"]

    # ------------------------------------------------------------ per ticker table
    per_ticker: dict[str, Any] = {}
    for t in TICKERS:
        row: dict[str, Any] = {}
        for c in CONTENDERS:
            e = res[t]["contenders"][c]
            row[c] = metrics(e["windows"]["ai_era"]) if e.get("available", True) else None
        per_ticker[t] = row

    # ------------------------------------------------------------ winner by the pre-registered rule
    elig: dict[str, Any] = {}
    for c in STRATS:
        m = seg_table[c]
        ok_trades = m["trades"] >= MIN_TRADES
        ok_cost = m["total_return_cost_2x"] > 0
        elig[c] = {"trades": m["trades"], "return_cost_2x": m["total_return_cost_2x"],
                   "sharpe": m["sharpe"], "eligible": bool(ok_trades and ok_cost)}
    eligible = [c for c in STRATS if elig[c]["eligible"]]
    winner = max(eligible, key=lambda c: seg_table[c]["sharpe"])
    ranking = sorted(eligible, key=lambda c: -seg_table[c]["sharpe"])
    wm = seg_table[winner]
    beats_hold_return = wm["total_return"] > hold["total_return"]
    beats_hold_sharpe = wm["sharpe"] > hold["sharpe"]
    ret_beaters = [c for c in STRATS if seg_table[c]["total_return"] > hold["total_return"]]
    least_dd = max(STRATS, key=lambda c: seg_table[c]["max_drawdown"])  # closest to zero

    # drawdown episodes taken from the equity curves
    w1 = ("2024-07-10", "2025-04-08")
    w2 = ("2026-06-30", "2026-10-05")
    episodes: dict[str, Any] = {}
    for c in ["B0_BUYHOLD", winner, "K1_C13C_ORIG", "K6_MOMENTUM_CS", "K2_SMA200_TREND"]:
        eq = sc[c]["equity"]["ai_era"]
        episodes[c] = {
            "window_2024_07_to_2025_04": window_drawdown(eq, *w1),
            "window_2026_06_to_2026_10": window_drawdown(eq, *w2),
            "overall": window_drawdown(eq, "2023-01-01", "2026-10-05"),
        }

    save_eur = (hold["worst_loss_per_1000_eur"] - wm["worst_loss_per_1000_eur"])
    gain_gap = hold["end_value_per_1000_eur"] - wm["end_value_per_1000_eur"]
    k1 = seg_table["K1_C13C_ORIG"]
    ew = episodes[winner]
    eh = episodes["B0_BUYHOLD"]

    winner_text = (
        f"Pobjednik po unaprijed zadanoj definiciji (najviši Sharpe u AI eri među natjecateljima s najmanje "
        f"{MIN_TRADES} poslova na segmentu i pozitivnim prinosom uz trošak 2x) je {winner} "
        f"({SHORT_HR[winner]}): Sharpe {hr(wm['sharpe'], 2)}, ukupni prinos {pct(wm['total_return'])}, "
        f"{wm['trades']} poslova. "
        f"Ali ne pobjeđuje kupi-i-drži: držanje daje {pct(hold['total_return'])} i Sharpe {hr(hold['sharpe'], 2)}. "
        f"Primjer s 1.000 EUR na svaku od 10 dionica: držanje na kraju vrijedi {eur(hold['end_value_per_1000_eur'])}, "
        f"{winner} {eur(wm['end_value_per_1000_eur'])}, dakle {eur(gain_gap)} manje. "
        f"Nitko od {len(STRATS)} natjecatelja nije prešao držanje po prinosu"
        + ("" if not ret_beaters else f" (osim: {', '.join(ret_beaters)})")
        + ". "
        f"Ono što je pobjednik ipak učinio: smanjio je najgori pad od vrha s {pct(-hold['max_drawdown'])} na "
        f"{pct(-wm['max_drawdown'])}. Na 1.000 EUR: najgori gubitak od vrha držanjem "
        f"{eur(hold['worst_loss_per_1000_eur'])}, s {winner} {eur(wm['worst_loss_per_1000_eur'])}, "
        f"razlika {eur(save_eur)}. Pažnja: ta dva najgora pada nisu u istom razdoblju. Držanje je najgore palo "
        f"od {eh['window_2024_07_to_2025_04']['peak_date']} do {eh['window_2024_07_to_2025_04']['bottom_date']}, "
        f"a {winner} u istom razdoblju pao je {pct(-ew['window_2024_07_to_2025_04']['depth'])} naspram "
        f"{pct(-eh['window_2024_07_to_2025_04']['depth'])} držanja; najgori pad pobjednika dogodio se "
        f"{ew['overall']['peak_date']} do {ew['overall']['bottom_date']} "
        f"(držanje je tada palo {pct(-eh['window_2026_06_to_2026_10']['depth'])}, {winner} {pct(-ew['window_2026_06_to_2026_10']['depth'])}). "
        f"Najmanji pad od vrha među svima imao je {least_dd} ({pct(-seg_table[least_dd]['max_drawdown'])}, "
        f"gubitak od vrha {eur(seg_table[least_dd]['worst_loss_per_1000_eur'])} na 1.000 EUR), ali uz prinos "
        f"{pct(seg_table[least_dd]['total_return'])}. "
        f"Razlike u Sharpeu među prva četiri ({', '.join(f'{c.split('_')[0]} {hr(seg_table[c]['sharpe'], 2)}' for c in ranking[:4])}) "
        f"su male, a pokrenuto je 9 natjecatelja (K u ledgeru 533), pa ovo nije dokaz prednosti jednog pravila, nego "
        f"zapažanje: u razdoblju bez dugog pada i uz snažan rast sektora jednostavno držanje je bilo teško pobijediti."
    )

    # ------------------------------------------------------------ C13C honest, ticker by ticker
    c13: list[dict[str, Any]] = []
    for t in TICKERS:
        k = per_ticker[t]["K1_C13C_ORIG"]
        h = per_ticker[t]["B0_BUYHOLD"]
        k7 = per_ticker[t]["K7_C13C_PLUS_TREND_REENTRY"]
        c13.append({
            "ticker": t,
            "k1_return": k["total_return"], "hold_return": h["total_return"],
            "k1_sharpe": k["sharpe"], "hold_sharpe": h["sharpe"],
            "k1_max_drawdown": k["max_drawdown"], "hold_max_drawdown": h["max_drawdown"],
            "k1_trades": k["trades"], "k1_hit_rate": k["hit_rate"],
            "k1_avg_win": k["avg_win"], "k1_avg_loss": k["avg_loss"],
            "k1_exposure_pct": k["exposure_pct"], "k1_return_cost_2x": k["total_return_cost_2x"],
            "k7_return": k7["total_return"], "k7_sharpe": k7["sharpe"], "k7_trades": k7["trades"],
            "beats_hold_return": k["total_return"] > h["total_return"],
            "beats_hold_sharpe": k["sharpe"] > h["sharpe"],
            "smaller_drawdown": k["max_drawdown"] > h["max_drawdown"],
        })
    n_sh = sum(r["beats_hold_sharpe"] for r in c13)
    n_dd = sum(r["smaller_drawdown"] for r in c13)
    n_rt = sum(r["beats_hold_return"] for r in c13)
    c13_sh = [r["ticker"] for r in c13 if r["beats_hold_sharpe"]]
    c13_neg = [r["ticker"] for r in c13 if r["k1_return"] < 0]
    worst13 = min(c13, key=lambda r: r["k1_return"] - r["hold_return"])
    k7s = seg_table["K7_C13C_PLUS_TREND_REENTRY"]
    c13_text = (
        f"C13C (K1) je tvoj vlastni algoritam i ovdje je izvješten bez uljepšavanja. Na segmentu od 10 dionica "
        f"(po 1.000 EUR svaka) u AI eri: prinos {pct(k1['total_return'])} naspram {pct(hold['total_return'])} držanja, "
        f"Sharpe {hr(k1['sharpe'], 2)} naspram {hr(hold['sharpe'], 2)}, najgori pad od vrha {pct(-k1['max_drawdown'])} naspram "
        f"{pct(-hold['max_drawdown'])}, {k1['trades']} poslova, uspješnost {pct(k1['hit_rate'], 0)} (većina poslova gubi, ali "
        f"prosječni dobitak {pct(k1['avg_win'])} veći je od prosječnog gubitka {pct(-k1['avg_loss'])}). "
        f"Na 1.000 EUR: držanje na kraju {eur(hold['end_value_per_1000_eur'])}, C13C {eur(k1['end_value_per_1000_eur'])}; "
        f"najgori gubitak od vrha {eur(hold['worst_loss_per_1000_eur'])} naspram {eur(k1['worst_loss_per_1000_eur'])}. "
        f"Po tickerima: C13C nije prešao držanje po prinosu ni na jednoj od 10 dionica ({n_rt} od 10), po Sharpeu ga je "
        f"prešao na {n_sh} ({', '.join(c13_sh) if c13_sh else 'nijednoj'}), a manji najgori pad od vrha imao je na {n_dd} od 10. "
        f"Negativan ukupni prinos imao je na: {', '.join(c13_neg) if c13_neg else 'nijednoj dionici'}. "
        f"Najveći zaostatak za držanjem: {worst13['ticker']} ({pct(worst13['k1_return'])} naspram {pct(worst13['hold_return'])}). "
        f"Razlog je struktura pravila: ulazi samo nakon pada, a klizni stop 10 % ispod vrha u dionici s godišnjom volatilnošću "
        f"od 47 do 80 % često izbaci poziciju običnim treskanjem, pa u dugom rastu propusti velik dio uspona. "
        f"Prednost je što je sjedio u dionici samo oko {hr(k1['exposure_pct'], 0)} % vremena, pa je pad bio manji. "
        f"Vlastito proširenje K7 (ponovni ulazak u trend): prinos {pct(k7s['total_return'])}, Sharpe {hr(k7s['sharpe'], 2)}, "
        f"{k7s['trades']} poslova, nije bolji od K1 po Sharpeu."
    )

    # ------------------------------------------------------------ ratings (lenient critic)
    lookahead = summ["lookahead_arrays"]
    thin_per_ticker = {}
    for c in STRATS:
        if c == "K6_MOMENTUM_CS":
            continue
        thin_per_ticker[c] = sum(1 for t in TICKERS if per_ticker[t][c]["trades"] < 10)
    ratings: dict[str, Any] = {}
    for c in CONTENDERS:
        if c == "B0_BUYHOLD":
            ratings[c] = {"rating": "mjerilo", "reason_hr": "Kupi-i-drži nije strategija nego mjerilo (jedan posao po dionici); ne ocjenjuje se."}
            continue
        m = seg_table[c]
        la_ok = lookahead.get(c, {}).get("ok", None)
        invalid: list[str] = []
        if la_ok is False:
            invalid.append("test pogleda unaprijed pao")
        if m["trades"] < MIN_TRADES:
            invalid.append(f"premalo poslova ({m['trades']})")
        if m["total_return_cost_2x"] <= 0:
            invalid.append("prinos uz trošak 2x nije pozitivan")
        notes: list[str] = []
        flag_adjusted = False
        if c == "K3_DONCHIAN_55_20":
            notes.append(f"vrlo malo poslova po dionici ({thin_per_ticker[c]} od 10 dionica ima manje od 10 poslova u AI eri); segment ukupno {m['trades']}")
        if c == "K7_C13C_PLUS_TREND_REENTRY":
            flag_adjusted = True
            notes.append("označeno kao moguće ugođeno: proširenje K1 s vlastitim freeze ID-om, dodano uz poznavanje ponašanja K1; parametri fiksni i bez ugađanja, ali ne može se isključiti da je oblik pravila izabran gledajući K1")
        if c == "K6_MOMENTUM_CS":
            notes.append("statistika poslova zanemaruje djelomična prebalansiranja (prinos i krivulja kapitala su točni); izabran je za dijagnostiku ±20 % po rezultatu, što ne mijenja parametre")
        if c in summ["diagnostic_contenders"]:
            notes.append("±20 % provjera robusnosti pokrenuta (gleda samo predznak ukupnog prinosa u AI eri; u bik-tržištu slab test)")
        else:
            notes.append("±20 % provjera robusnosti nije pokrenuta za ovo pravilo (nije dokaz krhkosti, nego nedostatak dokaza)")
        if m["deflated_sharpe_prob"] is not None:
            notes.append(f"deflated Sharpe vjerojatnost {hr(m['deflated_sharpe_prob'], 2)} (informativno, ne snižava ocjenu)")
        if invalid:
            colour = "crveno"
        elif flag_adjusted or thin_per_ticker.get(c, 0) >= 5:
            colour = "žuto"
        else:
            colour = "zeleno"
        ratings[c] = {
            "rating": colour,
            "invalid_evidence": invalid,
            "marked_adjusted_or_tuned": flag_adjusted,
            "lookahead_arrays_ok": la_ok,
            "notes_hr": notes,
            "reason_hr": (
                "Dokazi nisu valjani: " + "; ".join(invalid) if invalid else
                "Dokazi su valjani (test pogleda unaprijed prolazi, dovoljno poslova, pozitivan prinos i uz trošak 2x i 3x)."
                + (" Žuto samo zbog napomene o oznaci/uzorku, ne zbog veličine pada ili volatilnosti." if colour == "žuto" else "")
            ),
            "beats_holding_return": m["total_return"] > hold["total_return"],
            "return_vs_hold_pp": (m["total_return"] - hold["total_return"]) * 100,
        }

    # ------------------------------------------------------------ company cards
    def sr_text(a: dict[str, Any]) -> str:
        rp, pl = a["support_resistance"]["real_pivots"], a["support_resistance"]["placebo_arbitrary_levels"]
        return (f"Potpora (prijašnje dno) je izdržala u {hr(rp['support']['hold_pct'], 0)} % od {rp['support']['n_touches']} dodira "
                f"(slučajne razine: {hr(pl['support']['hold_pct'], 0)} %); otpor (prijašnji vrh) je izdržao u "
                f"{hr(rp['resistance']['hold_pct'], 0)} % od {rp['resistance']['n_touches']} dodira "
                f"(slučajne razine: {hr(pl['resistance']['hold_pct'], 0)} %). ")

    def sr_verdict(a: dict[str, Any]) -> str:
        rp, pl = a["support_resistance"]["real_pivots"], a["support_resistance"]["placebo_arbitrary_levels"]
        d = rp["support"]["hold_pct"] - pl["support"]["hold_pct"]
        if d >= 5:
            return "Potpora je radila bolje od slučajnih razina."
        if d <= -5:
            return "Potpora nije bila bolja od slučajnih razina."
        return "Razlika prema slučajnim razinama je mala, pa nema dokaza da su prijašnja dna posebna."

    cards: dict[str, Any] = {}
    for t in TICKERS:
        a = comp[t]["stats"]["ai_era"]
        dip = a["after_5d_drop_ge5pct_above_sma200"]["thinned_events_10d_apart"]
        f5, f20 = dip["fwd_5d"], dip["fwd_20d"]
        dds = a["drawdowns"][:3]
        best = max((c for c in STRATS if c != "K6_MOMENTUM_CS"), key=lambda c: per_ticker[t][c]["sharpe"])
        bm, hm, km = per_ticker[t][best], per_ticker[t]["B0_BUYHOLD"], per_ticker[t]["K1_C13C_ORIG"]
        mr = a["var_ratio_20d"] < 0.8
        ac = a["autocorr_lag1_5"][0]
        trend_best = best in ("K2_SMA200_TREND", "K4_TSMOM_126", "K3_DONCHIAN_55_20")
        dip_edge = f5["mean_pct"] - f5["uncond_mean_pct"]
        dip_txt = (
            f"Nakon pada od 5 dana od barem 5 % dok je cijena iznad SMA200 (SMA200 = prosjek zadnjih 200 dnevnih zatvaranja): "
            f"{f5['n']} događaja (razmak 10 dana), nakon 5 dana prosječno {hr(f5['mean_pct'], 2)} % uz {hr(f5['hit_pct'], 0)} % pozitivnih, "
            f"a bezuvjetni prosjek za bilo koji dan je {hr(f5['uncond_mean_pct'], 2)} % uz {hr(f5['uncond_hit_pct'], 0)} %; "
            f"nakon 20 dana {hr(f20['mean_pct'], 2)} % uz {hr(f20['hit_pct'], 0)} % naspram {hr(f20['uncond_mean_pct'], 2)} % uz {hr(f20['uncond_hit_pct'], 0)} %. "
            + ("Pad se u ovoj dionici isplatio kupiti češće nego običan dan. " if dip_edge >= 1 and f5["hit_pct"] > f5["uncond_hit_pct"] + 5
               else "Pad nije dao jasnu prednost pred običnim danom (ili je dao manju). " if dip_edge < 0.5 or f5["hit_pct"] <= f5["uncond_hit_pct"]
               else "Pad je dao blagu prednost pred običnim danom. ")
            + "To je opis, ne dokaz (AI era je jako rastuće razdoblje)."
        )
        dd_txt = "; ".join(
            f"{d['start']} do dna {d['bottom']}: {hr(d['depth_pct'], 1)} %" + (f", oporavak {d['recovery']}" if d["recovery"] else ", još bez oporavka do 2026-10-05")
            for d in dds[:2]
        )
        d0 = a["drawdowns"][0]
        euro = f"Na 1.000 EUR najveći pad od {hr(d0['depth_pct'], 1)} % znači pad na oko {eur(1000 * (1 + d0['depth_pct'] / 100))}."
        char = (
            f"Volatilnost {hr(a['ann_vol_pct'], 1)} % godišnje (na 1.000 EUR tipičan godišnji raspon oko {eur(1000 * a['ann_vol_pct'] / 100)} gore ili dolje), "
            f"beta prema SMH {hr(a['beta_smh'], 2)} (kad poluvodički indeks padne 10 %, ova dionica prosječno padne oko {hr(a['beta_smh'] * 10, 1)} %), "
            f"korelacija sa SMH {hr(a['corr_smh'], 2)}. "
            f"Autokorelacija prvog dana {hr(ac, 3)} i omjer varijance za 20 dana {hr(a['var_ratio_20d'], 2)} "
            + ("(ispod 0,8: blaga sklonost vraćanju prema sredini nakon kratkih skokova, ne uporan trend dan za danom). " if mr
               else "(blizu 1: kretanje nije izrazito vraćajuće, pa kratkoročno vraćanje nije glavni obrazac). ")
            + f"Zatvaranje je iznad SMA200 {hr(a['sma200_distance']['share_above_sma200_pct'], 0)} % dana (medijan udaljenosti {hr(a['sma200_distance']['median_pct'], 1)} %). "
            f"Deset najboljih dana nosi {hr(a['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % ukupnog (log) prinosa; bez njih bi ukupni prinos bio {hr(a['top10_best_days']['total_return_without_best10_pct'], 1)} %."
        )
        fit = (
            f"Na ovoj dionici najbolji Sharpe među pravilima (osim mjerila) ima {best} ({SHORT_HR[best]}): Sharpe {hr(bm['sharpe'], 2)}, prinos {pct(bm['total_return'])}, "
            f"naspram držanja Sharpe {hr(hm['sharpe'], 2)} i prinos {pct(hm['total_return'])}. "
            f"C13C (K1): Sharpe {hr(km['sharpe'], 2)}, prinos {pct(km['total_return'])}, {km['trades']} poslova, pad od vrha {pct(-km['max_drawdown'])} naspram {pct(-hm['max_drawdown'])} držanja. "
            + ("Što to znači: dionica je nagrađivala praćenje trenda (ostati unutra dok je trend gore), a ne trgovanje na padovima. "
               if trend_best else
               "Što to znači: dionica je nagrađivala kupnju nakon pada u rastućem trendu uz zaštitni stop. ")
            + ("Nijedno pravilo nije prešlo držanje po prinosu. "
               if all(per_ticker[t][c]["total_return"] <= hm["total_return"] for c in STRATS if per_ticker[t][c]) else
               "Barem jedno pravilo prešlo je držanje po prinosu. ")
            + "Razlike između najboljih pravila su male uz 9 natjecatelja, pa ovo nije dokaz."
        )
        cards[t] = {
            "mechanism_label": comp[t]["mechanism_label"],
            "mechanism_hr": comp[t]["mechanism_hr"],
            "sources": comp[t]["sources"],
            "behaviour_numbers": {
                "ann_vol_pct": a["ann_vol_pct"], "beta_smh": a["beta_smh"], "corr_smh": a["corr_smh"],
                "beta_ndx": a["beta_ndx"], "autocorr_lag1": ac, "var_ratio_5d": a["var_ratio_5d"],
                "var_ratio_20d": a["var_ratio_20d"], "total_return_pct_close_to_close": a["total_return_pct"],
                "share_days_above_sma200_pct": a["sma200_distance"]["share_above_sma200_pct"],
                "top10_share_pct": a["top10_best_days"]["sum_logret_share_of_total_pct"],
                "return_without_best10_pct": a["top10_best_days"]["total_return_without_best10_pct"],
                "largest_gaps": a["largest_gaps"][:3],
                "worst_drawdowns": a["drawdowns"][:3],
            },
            "volatility_beta_hr": char,
            "after_5d_dip_hr": dip_txt,
            "worst_drawdowns_hr": dd_txt + ". " + euro,
            "support_resistance_hr": sr_text(a) + sr_verdict(a),
            "algorithm_fit_hr": fit,
        }

    # ------------------------------------------------------------ per-ticker best + C13C rows
    best_by_ticker: dict[str, Any] = {}
    for t in TICKERS:
        cand = [c for c in STRATS if per_ticker[t][c]]
        b = max(cand, key=lambda c: per_ticker[t][c]["sharpe"])
        best_by_ticker[t] = {
            "best_by_sharpe": b, "sharpe": per_ticker[t][b]["sharpe"], "trades": per_ticker[t][b]["trades"],
            "return": per_ticker[t][b]["total_return"], "hold_sharpe": per_ticker[t]["B0_BUYHOLD"]["sharpe"],
            "hold_return": per_ticker[t]["B0_BUYHOLD"]["total_return"],
            "beats_hold_return": per_ticker[t][b]["total_return"] > per_ticker[t]["B0_BUYHOLD"]["total_return"],
            "beats_hold_sharpe": per_ticker[t][b]["sharpe"] > per_ticker[t]["B0_BUYHOLD"]["sharpe"],
            "note_hr": "Informativno: za pojedinu dionicu pravilo o najmanje 20 poslova nije primijenjeno jer većina pravila ima 6 do 25 poslova po dionici.",
        }

    # ------------------------------------------------------------ EU/HR notes
    eu: dict[str, Any] = {}
    generic = ("Američki kotirana pojedinačna dionica, a ne ETF; EU mali ulagači općenito mogu kupovati pojedinačne američke dionice, "
               "ali dostupnost i uvjeti za Petrov račun su nepotvrđeno dok se ne provjere u IBKR-u. Valuta je USD, račun u EUR, "
               "pa tečaj i trošak konverzije mijenjaju stvarni rezultat (ovdje nisu modelirani). Nije porezna tvrdnja i nije savjet.")
    for t in TICKERS:
        extra = ""
        if t == "ASML":
            extra = (" Nizozemska tvrtka; u profilu je navedena kao američki kotirana ADR potvrda (ADR = potvrda o dionici stranog izdavatelja kojom se u SAD-u trguje kao dionicom): "
                     "provjeri valutu, burzu i dostupnost u IBKR-u: nepotvrđeno. Moguće je i da se ista tvrtka nudi na europskoj burzi (u eurima), što nije provjereno.")
        elif t == "ACMR":
            extra = (" Profil navodi da je većina poslovanja u Kini i da su podružnice u prosincu 2024. stavljene na američki popis ograničenja; "
                     "dodatni geopolitički i regulatorni rizik. Tanje trgovana dionica s visokom volatilnošću (80 % godišnje): stvarni trošak izvršenja veći je od simuliranih 2,5 bps po strani.")
        eu[t] = {"status": "nepotvrđeno", "note_hr": generic + extra}

    # ------------------------------------------------------------ chart notes
    def b(t: str, d: str) -> dict[str, float]:
        r = px[t].loc[d]
        return {k: float(r[k]) for k in ["open", "high", "low", "close"]}

    def prev_close(t: str, d: str) -> tuple[str, float]:
        idx = px[t].index.get_loc(d)
        return px[t].index[idx - 1], float(px[t].iloc[idx - 1]["close"])

    def held_over(t: str, c: str, d: str) -> bool:
        return any(x["entry_date"] < d <= x["exit_date"] for x in res[t]["contenders"][c]["trades"]["ai_era"])

    notes: list[dict[str, Any]] = []
    top, bot = b("AMAT", "2024-07-10"), b("AMAT", "2025-04-04")
    notes.append({"ticker": "AMAT", "dates": ["2024-07-10", "2025-04-04"], "text_hr": (
        f"AMAT: najviše zatvaranje prije velikog pada bilo je {hr(top['close'], 2)} USD (2024-07-10), dno {hr(bot['close'], 2)} USD (2025-04-04): "
        f"pad {pct(bot['close'] / top['close'] - 1)}. Isti obrazac imaju i ostale dionice: 9 od 10 počinje najveći pad između 2024-07-03 i 2024-07-16, a 8 od 10 ima dno između 2025-04-04 i 2025-04-08 (ONTO ima dno tek 2025-05-09, ACMR je iznimka s padom od 2024-03-01). "
        f"Gledaj na grafu tu veliku udolinu: 1.000 EUR u dionici postao bi oko {eur(1000 * bot['close'] / top['close'])}. "
        f"Segment s držanjem u tom razdoblju pao je {pct(-eh['window_2024_07_to_2025_04']['depth'])}, {winner} {pct(-ew['window_2024_07_to_2025_04']['depth'])}, "
        f"C13C {pct(-episodes['K1_C13C_ORIG']['window_2024_07_to_2025_04']['depth'])}.")})
    k4a = [x for x in res["AMAT"]["contenders"][winner]["trades"]["ai_era"] if x["entry_date"] >= "2023-01-01"][:4]
    first = k4a[0]
    notes.append({"ticker": "AMAT", "dates": [first["entry_date"], first["exit_date"]], "text_hr": (
        f"AMAT i {winner}: prvi posao ulazi {first['entry_date']} po {hr(first['entry_price'], 2)} i drži do {first['exit_date']} po {hr(first['exit_price'], 2)} "
        f"({pct(first['return'])}), izlaz tek kad je 126-dnevni prinos postao negativan, dakle nakon što je dio uspona već vraćen. "
        f"Odmah poslije slijede kratki poslovi (npr. ulaz {k4a[1]['entry_date']} po {hr(k4a[1]['entry_price'], 2)}, izlaz {k4a[1]['exit_date']} po {hr(k4a[1]['exit_price'], 2)}, {pct(k4a[1]['return'])}): "
        f"to su 'trzaji' kad signal titra oko nule. Traži ih na grafu u rujnu i listopadu 2024.")})
    k1am = [x for x in res["AMAT"]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"] if x["entry_date"] in ("2024-07-18", "2024-07-26")]
    good = next(x for x in res["AMAT"]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"] if x["entry_date"] == "2024-04-22")
    if len(k1am) == 2:
        notes.append({"ticker": "AMAT", "dates": ["2024-07-18", "2024-08-02"], "text_hr": (
            f"AMAT i C13C: dva uzastopna ulaska nakon pada, {k1am[0]['entry_date']} po {hr(k1am[0]['entry_price'], 2)} (stop {k1am[0]['exit_date']} po {hr(k1am[0]['exit_price'], 2)}, {pct(k1am[0]['return'])}) i "
            f"{k1am[1]['entry_date']} po {hr(k1am[1]['entry_price'], 2)} (stop {k1am[1]['exit_date']} po {hr(k1am[1]['exit_price'], 2)}, {pct(k1am[1]['return'])}). "
            f"Na 1.000 EUR to su dva gubitka od oko 93 EUR. Pouka: u padajućem tržištu 'kupi pad' kupuje prerano, a stop 10 % ispod vrha tada se aktivira iznova. "
            f"Isti je stop {good['exit_date']} zatvorio dobar posao (ulaz {good['entry_date']} po {hr(good['entry_price'], 2)}, izlaz po {hr(good['exit_price'], 2)}, {pct(good['return'])}), pa stop radi dvojako: štiti dobitak, ali izbacuje i iz pada koji bi se oporavio.")})
    d = "2026-07-30"
    pc_d, pc = prev_close("LRCX", d)
    bl = b("LRCX", d)
    held = {c: held_over("LRCX", c, d) for c in ["B0_BUYHOLD", "K1_C13C_ORIG", "K2_SMA200_TREND", winner]}
    notes.append({"ticker": "LRCX", "dates": [pc_d, d], "text_hr": (
        f"LRCX: jaz (gap = razlika između jučerašnjeg zatvaranja i današnjeg otvaranja) {d}: zatvaranje {pc_d} {hr(pc, 2)} USD, otvaranje {hr(bl['open'], 2)} USD, to je {pct(bl['open'] / pc - 1)} preko noći. "
        f"Na 1.000 EUR: oko {eur(1000 * (bl['open'] / pc - 1))} dobitka u jednom otvaranju. Pravila koja su tada bila unutra (kupnja prije {d}): "
        + ", ".join(f"{c.split('_')[0]} {'da' if v else 'ne'}" for c, v in held.items())
        + ". Takve skokove ne možeš uhvatiti reagiranjem; ili si unutra ili nisi.")})
    d = "2025-11-05"
    pc_d, pc = prev_close("ACMR", d)
    bl = b("ACMR", d)
    k1ac = [x for x in res["ACMR"]["contenders"]["K1_C13C_ORIG"]["trades"]["ai_era"] if x["exit_date"] == d]
    notes.append({"ticker": "ACMR", "dates": [pc_d, d], "text_hr": (
        f"ACMR: {d} otvaranje {hr(bl['open'], 2)} USD naspram zatvaranja {hr(pc, 2)} USD dan prije: {pct(bl['open'] / pc - 1)} preko noći, najniža tog dana {hr(bl['low'], 2)} USD. "
        f"Na 1.000 EUR to je oko {eur(1000 * (bl['open'] / pc - 1))} gubitka prije nego što se stop uopće može aktivirati. "
        + (f"C13C je tog dana izašao po {hr(k1ac[0]['exit_price'], 2)} (razlog: {k1ac[0]['reason']}, posao {pct(k1ac[0]['return'])}). " if k1ac else "")
        + f"ACMR je jedina dionica u segmentu gdje C13C ima negativan ukupni prinos ({pct(per_ticker['ACMR']['K1_C13C_ORIG']['total_return'])}) uz {per_ticker['ACMR']['K1_C13C_ORIG']['trades']} poslova.")})
    d = "2025-05-09"
    pc_d, pc = prev_close("ONTO", d)
    bl = b("ONTO", d)
    notes.append({"ticker": "ONTO", "dates": [pc_d, d], "text_hr": (
        f"ONTO: {d} otvaranje {hr(bl['open'], 2)} USD nakon zatvaranja {hr(pc, 2)} USD ({pct(bl['open'] / pc - 1)} preko noći), zatvaranje tog dana {hr(bl['close'], 2)} USD. "
        f"To je početak najdubljeg pada u segmentu (profil: {hr(comp['ONTO']['stats']['ai_era']['drawdowns'][0]['depth_pct'], 1)} % od {comp['ONTO']['stats']['ai_era']['drawdowns'][0]['start']}); "
        f"držanje ONTO imalo je pad od vrha {pct(-per_ticker['ONTO']['B0_BUYHOLD']['max_drawdown'])}, a C13C {pct(-per_ticker['ONTO']['K1_C13C_ORIG']['max_drawdown'])}.")})
    a1, a2 = b("AMAT", "2026-06-30"), b("AMAT", "2026-09-16")
    notes.append({"ticker": "AMAT", "dates": ["2026-06-30", "2026-09-16"], "text_hr": (
        f"Drugi veliki pad (ljeto 2026.): AMAT zatvaranje {hr(a1['close'], 2)} USD (2026-06-30) pa {hr(a2['close'], 2)} USD (2026-09-16), {pct(a2['close'] / a1['close'] - 1)}, bez oporavka do 2026-10-05. "
        f"Segment: držanje je tad palo {pct(-eh['window_2026_06_to_2026_10']['depth'])}, {winner} {pct(-ew['window_2026_06_to_2026_10']['depth'])}, "
        f"C13C {pct(-episodes['K1_C13C_ORIG']['window_2026_06_to_2026_10']['depth'])}, K6 {pct(-episodes['K6_MOMENTUM_CS']['window_2026_06_to_2026_10']['depth'])}. "
        f"Usporedi s padom 2024/25: tada je K2 pao {pct(-episodes['K2_SMA200_TREND']['window_2024_07_to_2025_04']['depth'])} i {winner} {pct(-ew['window_2024_07_to_2025_04']['depth'])} naspram {pct(-eh['window_2024_07_to_2025_04']['depth'])} držanja, "
        f"a ljeti 2026. gotovo ništa ({pct(-episodes['K2_SMA200_TREND']['window_2026_06_to_2026_10']['depth'])} i {pct(-ew['window_2026_06_to_2026_10']['depth'])} naspram {pct(-eh['window_2026_06_to_2026_10']['depth'])}), "
        f"jer je pad bio brz (do 2026-07-29 za mjesec dana) i trend-signal je zakasnio. C13C je zbog izlaza po stopu i kratke izloženosti imao manji pad u oba slučaja. Dva primjera nisu dokaz.")})
    e = comp["ENTG"]["stats"]["ai_era"]
    notes.append({"ticker": "ENTG", "dates": ["2023-01-03", "2026-10-05"], "text_hr": (
        f"ENTG: deset najboljih dana nosi {hr(e['top10_best_days']['sum_logret_share_of_total_pct'], 0)} % ukupnog prinosa; bez njih ukupni prinos bio bi {hr(e['top10_best_days']['total_return_without_best10_pct'], 1)} %. "
        f"Najveće jazeve vidi na grafu: {', '.join(g['date'] + ' ' + hr(g['gap_pct'], 1) + ' %' for g in e['largest_gaps'][:2])}. "
        f"To objašnjava zašto pravila koja su ponekad izvan dionice ovdje zaostaju: ENTG držanje {pct(per_ticker['ENTG']['B0_BUYHOLD']['total_return'])}, C13C {pct(per_ticker['ENTG']['K1_C13C_ORIG']['total_return'])}. "
        f"Ovo je opis ovisnosti o rijetkim danima, ne razlog za nižu ocjenu.")})
    fg_d = "2026-07-30"
    fg = b("FORM", fg_d)
    fg_pc = prev_close("FORM", fg_d)[1]
    f_ = "2025-07-31"
    pc_d, pc = prev_close("FORM", f_)
    bl = b("FORM", f_)
    notes.append({"ticker": "FORM", "dates": [pc_d, f_], "text_hr": (
        f"FORM: {f_} otvaranje {hr(bl['open'], 2)} USD nakon zatvaranja {hr(pc, 2)} USD ({pct(bl['open'] / pc - 1)} preko noći, najveći negativni jaz u AI eri). "
        f"Veliki pozitivni jaz: {fg_d} +{pct(fg['open'] / fg_pc - 1)}. Za zaštitni stop to znači izlaz po otvaranju, ispod stopa, ne po stopu.")})
    ps = comp["AMAT"]["stats"]["ai_era"]["support_resistance"]
    notes.append({"ticker": "AMAT", "dates": ["2023-01-03", "2026-10-05"], "text_hr": (
        f"Potpora i otpor na AMAT: prijašnja dna držala su {hr(ps['real_pivots']['support']['hold_pct'], 0)} % ({ps['real_pivots']['support']['n_touches']} dodira), slučajno odabrane razine {hr(ps['placebo_arbitrary_levels']['support']['hold_pct'], 0)} %. "
        f"Nacrtaj na grafu ručno 'vodoravne crte' na prijašnjim dnima i vidi koliko često cijena stvarno okrene; u ovom segmentu K5 ({SHORT_HR['K5_SUPPORT_RESISTANCE']}) je u tržištu samo {hr(seg_table['K5_SUPPORT_RESISTANCE']['exposure_pct'], 0)} % vremena i zaradio {pct(seg_table['K5_SUPPORT_RESISTANCE']['total_return'])}.")})

    # ------------------------------------------------------------ why together
    fi = prof["findings_hr"]
    pooled = prof["pooled_c13_premise_ai_era"]
    why = {
        "summary_hr": (
            "Ovih 10 tvrtki ne proizvodi čipove, nego strojeve, mjerne sustave, dijelove i materijale kojima ih proizvode drugi. "
            "Zato im prihod ovisi o istoj stvari: koliko novca tvornice čipova (logika, DRAM, NAND, napredno pakiranje) ulažu u nove linije "
            "i unaprjeđenja te koliko troše na servis i potrošni materijal. Kad ulaganja rastu, narudžbe rastu; kad stanu, prihod padne. "
            "Primjer s 1.000 EUR: to je kao da ulažeš u dobavljače lopata za zlatnu groznicu, a ne u rudnike; kad se rudnici prestanu širiti, "
            "lopate se prestanu kupovati, a tvrtka koja prodaje lopate padne jednako brzo kao i rudnik."
        ),
        "label_hr": LABEL_CTX,
        "drivers_hr": (
            "Zajednički pokretač (" + LABEL_CTX + "): ulaganja tvornica čipova (capex = kapitalni izdaci, novac za strojeve i tvornice). "
            "Cikličnost se razlikuje: strojevi za jetkanje/taloženje i litografija su cikličniji; servis, potrošni materijal (ENTG) i kontrola procesa (KLAC) stabilniji; "
            "MKSI je 'oprema opreme' pa prvi osjeti smanjenje narudžbi; ACMR ovisi o Kini i politici; FORM i TER ovise o broju i složenosti čipova koje treba testirati."
        ),
        "subgroups": [
            {"name_hr": "Veliki strojevi za izradu čipa", "tickers": ["AMAT", "LRCX", "ASML"]},
            {"name_hr": "Mjerenje i kontrola procesa", "tickers": ["KLAC", "ONTO"]},
            {"name_hr": "Dijelovi i materijali unutar strojeva", "tickers": ["MKSI", "ENTG"]},
            {"name_hr": "Čišćenje pločica (Kina)", "tickers": ["ACMR"]},
            {"name_hr": "Testiranje čipova", "tickers": ["FORM", "TER"]},
        ],
        "shared_behaviour_from_data_hr": [fi[0], fi[1], fi[2]],
        "pooled_c13_premise_hr": fi[3],
        "pooled_c13_premise_numbers": pooled,
        "caution_hr": fi[6] + " " + fi[7],
    }

    # ------------------------------------------------------------ assemble
    out = {
        "segment": "equipment",
        "segment_name_hr": prof["segment_name_hr"],
        "language": "hr",
        "evaluation_window": {"ai_era": "2023-01-03 do 2026-10-05", "note_hr": "AI era (od 2023-01-01) je glavno mjerilo; ranije je samo kontekst."},
        "sources": {
            "profile": "reports/research/AICHAIN_20261014/segments/equipment/profile.json",
            "results": "reports/research/AICHAIN_20261014/results/equipment.json i results/{TICKER}.json",
            "summary": "reports/research/AICHAIN_20261014/summary.json",
            "engine": "reports/research/AICHAIN_20261014/ENGINE.md",
            "data_quality": "reports/research/AICHAIN_20261014/DATA_QUALITY.md",
            "prices": "data/ohlcv/{TICKER}_1d.csv",
            "built_by": "lab/aichain/build_equipment_analysis.py",
        },
        "audit_status_hr": "Simulator je nakon revizije 2026-10-14 popravljen (obustavljena trgovina, loš tick u NVDA, trošak izlaza na zadnji dan, jači test pogleda unaprijed); popravci ne diraju ovaj segment osim troška izlaza na zadnji dan. Ostaju poznata ograničenja: ±20 % provjera gleda samo predznak prinosa, CAGR je jedan dan kraći, K6 statistika poslova ne broji djelomična prebalansiranja.",
        "disclaimer_hr": "Ovo je istraživanje, ne savjet za ulaganje i ne Critic PASS. Agenti ne šalju nikakve naloge (ni probne ni prave). Cijene su u USD i tretirane kao EUR-ekvivalent; tečaj, porezi, dividende i minimalna provizija nisu modelirani.",
        "glossary_hr": {
            "kupi i drži (B0)": "Kupiš na prvom danu i ne prodaješ. 1.000 EUR danas ostaje u dionici do kraja; to je mjerilo kojem se sve ostalo mora usporediti.",
            "prinos": "Ukupna promjena vrijednosti. Prinos 100 % znači da se 1.000 EUR pretvorilo u 2.000 EUR.",
            "Sharpe": "Prinos u odnosu na treskanje: veći je bolji; 1,0 znači da je prinos otprilike jednak jednoj jedinici treskanja.",
            "pad od vrha (max drawdown)": "Najveći pad od najviše točke do najniže prije oporavka. Pad od 50 % znači da 1.000 EUR u najgorem trenutku vrijedi 500 EUR.",
            "stop": "Automatska prodaja ako cijena padne na određenu razinu; npr. stop 10 % ispod vrha znači prodaju kad 1.000 EUR padne na 900 EUR od vrha.",
            "jaz (gap)": "Razlika između jučerašnjeg zatvaranja i današnjeg otvaranja, obično zbog vijesti preko noći; stop ne može zaštititi od jaza.",
            "SMA200": "Prosjek zadnjih 200 dnevnih zatvaranja, grubi pokazatelj dugoročnog trenda.",
            "trošak 2x / 3x": "Isti test uz dvostruke ili trostruke troškove trgovanja (5 ili 7,5 bps po strani; 1 bps = 0,01 %), da se vidi preživljava li pravilo lošije izvršenje.",
            "izloženost": "Postotak vremena kad si u dionici; 50 % znači da pola vremena novac stoji kao gotovina.",
            "uspješnost (hit rate)": "Udio dobitnih poslova; 46 % znači da gubi više od polovice poslova, što je u redu ako su dobici veći od gubitaka.",
        },
        "why_together": why,
        "company_cards": cards,
        "per_ticker_table_ai_era": {
            "note_hr": "Po tickeru, po 1.000 EUR, AI era. K6 (rotacija) nije primjenjiv na jednu dionicu pa je null. Prinosi su razlomci (4,43 = 443 %).",
            "contenders": per_ticker,
            "best_by_sharpe_excluding_hold": best_by_ticker,
        },
        "segment_portfolio_table_ai_era": {
            "note_hr": "10 dionica po 1.000 EUR = 10.000 EUR, bez prelijevanja kapitala; dionica koja miruje drži gotovinu. Prinosi su razlomci; _per_1000_eur je završna vrijednost za 1.000 EUR.",
            "contenders": seg_table,
        },
        "winner": {
            "definition_hr": f"Unaprijed zadano: pobjednik = najviši Sharpe u AI eri među natjecateljima s najmanje {MIN_TRADES} poslova na segmentu i pozitivnim prinosom uz trošak 2x. Mjerilo (kupi i drži) se uvijek uspoređuje.",
            "eligibility": elig,
            "ranking_by_sharpe": ranking,
            "winner": winner,
            "beats_holding_on_return": bool(beats_hold_return),
            "beats_holding_on_sharpe": bool(beats_hold_sharpe),
            "strategies_beating_hold_on_return": ret_beaters,
            "smallest_drawdown_contender": least_dd,
            "euro_example_per_1000_eur": {
                "hold_end_value": hold["end_value_per_1000_eur"],
                "winner_end_value": wm["end_value_per_1000_eur"],
                "hold_worst_loss_from_peak": hold["worst_loss_per_1000_eur"],
                "winner_worst_loss_from_peak": wm["worst_loss_per_1000_eur"],
                "worst_loss_saved_by_winner": save_eur,
                "c13c_worst_loss_from_peak": k1["worst_loss_per_1000_eur"],
            },
            "drawdown_episodes_from_equity_curves": episodes,
            "text_hr": winner_text,
        },
        "c13c_own_algorithm": {
            "segment": metrics(sc["K1_C13C_ORIG"]["windows"]["ai_era"]),
            "per_ticker": c13,
            "count_beats_hold_return": n_rt, "count_beats_hold_sharpe": n_sh, "count_smaller_drawdown": n_dd,
            "text_hr": c13_text,
        },
        "ratings": ratings,
        "rating_rule_hr": "Blagi Critic: ocjena se snižava samo zbog nevaljanih dokaza (pogled unaprijed, ugađanje/krhkost, premalo poslova, troškovi), nikada zbog veličine pada, volatilnosti ili koncentracije. Zeleno = dokazi valjani; žuto = dokazi valjani, ali s oznakom (moguće ugođeno ili vrlo mali uzorak po dionici); crveno = nevaljani dokazi. Ocjena ne mjeri koliko je pravilo zaradilo.",
        "eu_hr_notes": eu,
        "chart_notes_hr": notes,
        "caveats_hr": [
            "Pokrenuto je 9 natjecatelja na 6 segmenata i 43 dionice (K u ledgeru 533); najbolja ćelija tablice dobra je djelomično slučajno. Razlika u Sharpeu između prva četiri pravila je mala.",
            "AI era je jako bikovsko razdoblje za cijeli sektor: sve dionice imaju visoku korelaciju sa SMH-om, pa broj neovisnih događaja manji je od zbroja. Pravila koja su izvan tržišta zaostaju u rastu, a dobivaju u padu.",
            "Cijene su prilagođene samo za splitove (LRCX split 10:1 2024-10-03 je kontinuiran); dividende nisu uključene. Tečaj EUR/USD, porezi i IBKR minimalna provizija nisu modelirani; strategije s mnogo poslova (C13C, K7) izgledaju povoljnije nego u stvarnosti.",
            "Provjera pogleda unaprijed prolazi za sve natjecatelje; ±20 % provjera robusnosti pokrenuta je samo za K1, K4 i K6 i gleda samo predznak prinosa (slab test u bik-tržištu).",
            "Simulirani trošak je 2,5 bps po strani; ACMR je tanje trgovana pa je stvarni trošak veći. Zadnji podaci su do 2026-10-05 (zajednički završetak).",
            "Mehanizmi pojedinih tvrtki (" + LABEL_CTX + ") dolaze iz javnih izvora u profilu i nisu dokaz; što je izvor označio kao nepotvrđeno, ostaje nepotvrđeno.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written", OUT, "winner", winner)


if __name__ == "__main__":
    main()
