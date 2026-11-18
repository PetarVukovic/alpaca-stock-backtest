"""Render facts.json into the readable Croatian FACTS.md used by the master-document writers."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

GROUP_NAMES = {
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja memorije i pohrana",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Oblak i podatkovni centri",
    "crypto": "Kripto (zasebna grupa)",
    "metali_referentno": "Metali (nepotvrđeno / referentno)",
    "stocks_all": "Sve dionice (zbroj 43 sleevea)",
}
SEGMENTS = ["memory", "mem_interface_storage", "equipment", "ai_chips_logic", "network_servers", "cloud"]
W_ORDER = ["W1_C13C_ORIG", "W2_MOM_BREAK_20", "W3_MOM_RANK_WEEKLY", "W4_SR_BOUNCE_V2", "W5_SR_BREAKOUT_RETEST",
           "W6_MM_SWEEP_SHIFT", "W7_MM_DEMAND_RETEST", "W8_IBS_REVERT", "B0_BUYHOLD"]
W_SHORT = {"W1_C13C_ORIG": "W1", "W2_MOM_BREAK_20": "W2", "W3_MOM_RANK_WEEKLY": "W3", "W4_SR_BOUNCE_V2": "W4",
           "W5_SR_BREAKOUT_RETEST": "W5", "W6_MM_SWEEP_SHIFT": "W6", "W7_MM_DEMAND_RETEST": "W7",
           "W8_IBS_REVERT": "W8", "B0_BUYHOLD": "B0"}


def f(x, nd: int = 1, suffix: str = "") -> str:
    """Format a number the Croatian way (comma decimals, dot thousands); '-' for None."""
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "da" if x else "ne"
    if isinstance(x, str):
        return x
    q = Decimal(1).scaleb(-nd)
    v = Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP)
    if v == 0:
        v = abs(v)
    s = f"{v:,.{nd}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + suffix


def kv(d: dict, nd: int = 1, suffix: str = "") -> str:
    """Render a small dict as 'key: value; key: value' with Croatian number formatting."""
    return "; ".join(f"{k}: {f(v, nd, suffix) if isinstance(v, (int, float)) and not isinstance(v, bool) else v}" for k, v in d.items())


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in row) + " |")
    return "\n".join(out) + "\n"


def render(F: dict) -> str:  # noqa: C901 - one long document builder, kept linear on purpose
    L: list[str] = []
    A = L.append
    H = F["meta"]
    sw, tour, top, cdt, st, c13 = F["swing"], F["tournament"], F["top10"], F["crypto_day_trading"], F["state_now"], F["c13c"]

    A("# FACTS: sve brojke za glavni dokument (2026-10-14)\n")
    A(f"*{H['status_hr']}*\n")
    A("Ovaj dokument generira `scripts/master_facts_20261014.py` iz projektnih datoteka; strojno čitljiva inačica je `facts.json` (iste brojke). "
      "Brojke iz JSON-ova su preuzete programski; brojke iz Markdown izvještaja prepisane su ručno uz oznaku izvora. "
      "Ništa nije izmišljeno. Sve što je 'nepotvrđeno' tako je i označeno.\n")
    A("## 0. Kako čitati i koja brojka pobjeđuje\n")
    for x in H["source_precedence_hr"]:
        A(f"- {x}")
    A("\n**Troškovi po testu:**\n")
    for k, v in H["costs_by_test_hr"].items():
        A(f"- {k}: {v}")
    A("\n**Što NIJE modelirano (vrijedi za sve osim ako piše drukčije):**\n")
    for x in H["not_modelled_hr"]:
        A(f"- {x}")
    A(f"\n**Ledger K:** {H['ledger_k_final']} (zadnja vrijednost). Povijest: {H['ledger_k_history']}. {H['ledger_note']}\n")

    # ------------------------------------------------------------------ 1 timeline
    A("## 1. Što smo napravili: vremenska crta\n")
    for t in F["timeline"]:
        A(f"### {t['date']}: {t['title_hr']}\n")
        A(f"{t['what_hr']}\n")
        A(f"*Izvor: {t['source']}*\n")

    # data
    D = F["data"]
    A("## 1b. Podaci\n")
    A(f"- Katalog: {D['catalog_headline']['rows']}, {D['catalog_headline']['files']}. {D['catalog_headline']['note_hr']} (izvor: {D['catalog_headline']['source']})")
    A("\nPo klasi imovine (broj instrumenata s tom razinom podataka):\n")
    A(table(["Klasa", "Instrumenata", "Dnevno", "Satno", "5 min", "1 min"],
            [[c["class"], c["instruments"], c["daily"], c["hourly"], c["min5"], c["min1"]] for c in D["catalog_by_class"]]))
    A("**Pravila podataka:**\n")
    for x in D["rules_hr"]:
        A(f"- {x}")
    u = D["tournament_and_swing_universe"]
    A(f"\n**Univerzum turnira i swing testa:** {u['stocks_total']} dionica u 6 segmenata (memorija 3, sučelja i pohrana 4, oprema 10, AI čipovi 11, mreže i serveri 8, oblak 7), "
      f"zajednički kraj {u['common_end']}, AI era {u['ai_era_start']}. Kripto u swingu: {', '.join(u['crypto_swing_group'])}; metali (referentno, nepotvrđeno): {', '.join(u['metals_swing_group_reference'])}.\n")
    A("**Isključeno:**\n")
    for e in u["excluded"]:
        A(f"- {e['ticker']}: {e['reason_hr']}")
    A(f"\n{u['threshold_hr']}\n")
    A("**Čišćenje i poznata ograničenja:**\n")
    for x in D["cleaning_hr"]:
        A(f"- {x}")
    A(f"\n{D['placebo_universe_vs_swing_universe_hr']}\n")
    A("Papiri s kasnijim prvim korištenim datumom: " + ", ".join(f"{k} {v}" for k, v in D["first_bar_exceptions_swing"].items()) + ".\n")

    # ------------------------------------------------------------------ TOP10
    A("## 1c. TOP10 strategija (N1-N5, C1-C5), stroj lab/top10/, AI era\n")
    m = top["meta"]
    A(f"Troškovi {m['costs_bps_per_side']['stocks_etf']} bps po strani (dionice i ETF), {m['costs_bps_per_side']['crypto']} (kripto), {m['costs_bps_per_side']['forex']} (forex). {m['splits']}. K {m['ledger_k_range']}. {m['ai_era_end_note']}. {m['rating_note_hr']} {m['benchmark_note_hr']}\n")
    rows = []
    for sid, s in top["strategies"].items():
        ai, bm = s["ai_era"], s["ai_era_benchmark"]
        rows.append([s["short_id"], s["title_hr"], s["rating"], f(ai["total_return_pct"], 0, " %"), f(ai["end_value_per_1000_eur"], 0, " €"),
                     f(bm["total_return_pct"], 0, " %"), f(ai["sharpe"], 2), f(ai["max_drawdown_pct"], 0, " %"), f(bm["max_drawdown_pct"], 0, " %"),
                     s["trades"], "DA" if s["beats_hold_on_return_ai_era"] else "ne"])
    A(table(["ID", "Naslov", "Ocjena", "Prinos AI era", "1.000 € postane", "Kupi i drži (njihova košara)", "Sharpe", "Pad", "Pad držanja", "Trgovina", "Bolja od držanja?"], rows))
    A("\nDetalji po strategiji (pravila, robusnost, godišnje):\n")
    for sid, s in top["strategies"].items():
        A(f"### {s['short_id']}: {s['title_hr']} ({s['rating']}), K={s['k']}\n")
        A(f"- Univerzum: {', '.join(s['universe'])}. Pine: `{s['pine_file']}`; zamrznuto: `{s['freeze_file']}`.")
        A(f"- Hipoteza: {s['hypothesis']}")
        A("- Pravila: " + " | ".join(s["rules"] or []))
        A(f"- Parametri: {s['params']}")
        A(f"- AI era: {f(s['ai_era']['total_return_pct'],0,' %')} (CAGR {f(s['ai_era']['cagr_pct'],0,' %')}), Sharpe {f(s['ai_era']['sharpe'],2)}, pad {f(s['ai_era']['max_drawdown_pct'],0,' %')}; "
          f"držanje {f(s['ai_era_benchmark']['total_return_pct'],0,' %')}, Sharpe {f(s['ai_era_benchmark']['sharpe'],2)}. Prije AI ere: strategija {f(s['pre_ai']['total_return_pct'],0,' %')}, držanje {f(s['pre_ai_benchmark']['total_return_pct'],0,' %')}.")
        A(f"- Razdoblja strategija IS/WF/HO: {kv(s['splits_total_return_pct'],0,' %')}; držanje: {kv(s['benchmark_splits_total_return_pct'],0,' %')}.")
        A(f"- Trgovina {s['trades']}, dobitnih {f(s['win_rate_pct'],0,' %')}, medijan trgovine {f(s['median_trade_pct'],1,' %')}, najbolja {f(s['best_trade_pct'],0,' %')}, izloženost {f(s['exposure_pct'],0,' %')}.")
        A(f"- Trošak 1x/2x/3x (WF+HO ukupno): {kv(s['cost_stress_wf_ho_total_pct'],0,' %')}; ±20 % Sharpe: {kv(s['sensitivity_pm20_wf_ho_sharpe'],2)}; PBO {f(s['pbo_pct'],0,' %')}; deflated Sharpe {f(s['deflated_sharpe_prob_pct'],0,' %')}; PSR {f(s['psr_ai_era'],3)}.")
        A(f"- Zastavice: {s['flags'] if s['flags'] else 'nema'}")
        A(f"- Presuda (narativ): {s['verdict_hr']}")
        A(f"- Godišnje (strategija / košara): " + "; ".join(f"{y}: {f(v['strategy'],0,' %')} / {f(v['benchmark'],0,' %')}" for y, v in s["yearly_pct"].items()))
        A(f"- Stranica: {s['artifact_url']}\n")

    # ------------------------------------------------------------------ EU metals
    E = F["eu_metals"]
    A("## 1d. Provjera EU zamjena za GLD/SLV (potvrđeno naspram nepotvrđeno)\n")
    A(f"*Izvor: {E['source']}*\n")
    A(f"{E['headline_hr']}\n")
    A("**Potvrđeno:**\n")
    for x in E["confirmed_hr"]:
        A(f"- {x}")
    A("\n**NEPOTVRĐENO:**\n")
    for x in E["unconfirmed_hr"]:
        A(f"- {x}")
    A("\n" + table(["Linija", "ISIN", "Burza", "Valuta", "Naknada (TER)", "Javni KID", "Kupnja za HR retail"],
                   [[x["line"], x["isin"], x["venue"], x["ccy"], f(x["fee_pct"], 2, " %") if x["fee_pct"] is not None else "-", x["kid_public"], x["retail_buy"]] for x in E["table_hr"]]))

    R = F["rotate_c36_recap"]
    A("## 1e. ROTATE / C36 (zlato i srebro), sažetak i Critic FAIL\n")
    A(f"*Izvor: {R['source']}*\n")
    A(R["answer_5050_hr"] + "\n")
    A("**ROTATE pravila:**\n")
    for x in R["rotate_rules_hr"]:
        A(f"- {x}")
    A(f"\n**EU instrumenti (PHAU/PHAG, EUR), {R['ibkr_period']}:**\n")
    A(table(["Kapital €", "Model", "Završno €", "Neto prinos", "Sharpe", "Najveći pad", "Transakcija", "Troškovi €"],
            [[x["capital"], x["model"], f(x["end_eur"], 2), f(x["net_return_pct"], 2, " %"), f(x["sharpe"], 3), f(x["max_dd_pct"], 2, " %"), x["transactions"], f(x["costs_eur"], 2)] for x in R["ibkr_results"]]))
    A("\n" + R["buyhold_500_trap_hr"] + "\n")
    A(R["rotate_500_trades_hr"] + "\n")
    A("**Desetogodišnji GLD/SLV proxy (NIJE EU ETC rezultat):**\n")
    A(table(["Kapital €", "Model", "Završno €", "Ukupni prinos", "CAGR", "Sharpe", "Najveći pad", "Transakcija"],
            [[x["capital"], x["model"], f(x["end_eur"], 2), f(x["total_return_pct"], 2, " %"), f(x["cagr_pct"], 2, " %"), f(x["sharpe"], 3), f(x["max_dd_pct"], 2, " %"), x["transactions"]] for x in R["proxy_gld_slv_10y"]]))
    A("\n" + R["wf_2021_2023_proxy_hr"] + "\n")
    A(R["tv_vs_python_hr"] + "\n")
    A(f"**Critic C35:** {R['critic']['c35']}\n")
    A(f"**Critic C36:** {R['critic']['c36']} Ostale obitelji na 500 EUR: {R['critic']['other_families_500eur']}.\n")
    A(R["n3_c4_context_hr"] + " " + R["swing_metals_result_hr"] + "\n")

    # ------------------------------------------------------------------ crypto DT
    A("## 1f. Kripto day trading (sedam CDT ID-eva), iskren rezultat\n")
    A(f"*Izvor: {cdt['meta']['source_doc']}; troškovi {cdt['meta']['costs_bps_per_side']} bps po strani; {cdt['meta']['splits']}; {cdt['meta']['data']}.*\n")
    A(table(["ID", "Ideja", "WF", "HO", "Poslova IS/WF/HO", "Bruto bps po poslu", "Ishod"],
            [[x["id"], x["idea"], f(x["WF_pct"], 1, " %"), f(x["HO_pct"], 1, " %"), x["trades_is_wf_ho"], f(x["gross_bps_per_trade"], 1), x["outcome"]] for x in cdt["doc_table"]]))
    A("\nBrojke iz results.json (provjera tablice iznad):\n")
    A(table(["ID", "K", "Strojna ocjena", "IS", "WF", "HO", "AI era", "Sharpe AI era", "Pad AI era", "Trošak x2 (WF+HO)", "Zastavice"],
            [[i, v["k"], v["machine_rating"], f(v["is_total_pct"], 1, " %"), f(v["wf_total_pct"], 1, " %"), f(v["ho_total_pct"], 1, " %"), f(v["ai_era_total_pct"], 1, " %"),
              f(v["ai_era_sharpe"], 2), f(v["ai_era_max_dd_pct"], 1, " %"), f(v["cost_stress_wf_ho_total_pct"].get("2x"), 1, " %"), "; ".join(v["flags"])] for i, v in cdt["ids"].items()]))
    h = cdt["h1_ai_era_vs_buy_hold"]
    A(f"\n**H1 u AI eri naspram pravog kupi-i-drži (BTC+ETH+SOL):** H1 +{f(h['h1']['total_pct'],1)} %, CAGR {f(h['h1']['cagr_pct'],1)} %, najveći pad {f(h['h1']['max_drawdown_pct'],1)} %, Calmar {f(h['h1']['calmar'],2)}; "
      f"kupi-i-drži +{f(h['buy_hold_btc_eth_sol']['total_pct'],1)} %, CAGR {f(h['buy_hold_btc_eth_sol']['cagr_pct'],1)} %, pad {f(h['buy_hold_btc_eth_sol']['max_drawdown_pct'],1)} %, Calmar {f(h['buy_hold_btc_eth_sol']['calmar'],2)}. {h['euro_example']}. "
      f"Holdout 2025+: H1 +{f(h['holdout_2025_plus']['h1_pct'],1)} %, kupi-i-drži {f(h['holdout_2025_plus']['buy_hold_pct'],1)} %. Stres troška (WF+HO ukupno): {kv(h['cost_stress_wf_ho_total_pct'],1,' %')}. ±20 %: {h['pm20_neighbours_positive']} susjeda pozitivno. "
      f"Uloženo ~{h['invested_share_wf_ho_pct']} % kapitala; dobitnih {h['trades_win_rate_pct']} %; medijan držanja {h['median_hold_days']} dana. PSR {h['psr_ai_era']}, Deflated Sharpe {h['deflated_sharpe']} uz K={h['k_at_run']}, PBO {h['pbo']}.\n")
    A(f"**Critic H1:** {cdt['critic_h1']['verdict']}. Pale provjere {cdt['critic_h1']['failed_checks']}; prolaze {cdt['critic_h1']['passed']}. ({cdt['critic_h1']['source']})\n")
    A("**Iskrena presuda:**\n")
    for x in cdt["honest_verdict_hr"]:
        A(f"- {x}")
    A("\n**Što je neovisni pregled srušio:**\n")
    for x in cdt["review_findings_hr"]:
        A(f"- {x}")
    A(f"\n**Što je preživjelo:** {cdt['what_survived_hr']} **Neriješeno:** {cdt['unresolved_hr']}\n")

    # ------------------------------------------------------------------ tournament
    A("## 1g. Turnir AI lanca: 9 suparnika, 6 segmenata (K=533, raniji test)\n")
    A(f"*{tour['meta']['note_hr']} Razdoblje {tour['meta']['window_ai_era'][0]} do {tour['meta']['window_ai_era'][1]}, trošak {tour['meta']['cost_bps_per_side']} bps po strani.*\n")
    A("Suparnici: " + "; ".join(f"{k.split('_')[0]} = {v}" for k, v in tour["meta"]["contenders"].items()) + ".\n")
    A("**Pobjednik po segmentu** (najviši Sharpe među pravilima s najmanje 20 poslova i pozitivnim prinosom uz trošak 2x; držanje se ne računa):\n")
    rows = []
    for seg in SEGMENTS:
        s = tour["segments"][seg]
        wv = s["winner_vs_hold"]
        rows.append([s["name"], len(s["tickers_used"]), s["winner_name"], f(wv["winner_sharpe"], 2), f(wv["hold_sharpe"], 2), f(wv["winner_total_return_pct"], 0, " %"), f(wv["hold_total_return_pct"], 0, " %"),
                     f(wv["winner_max_drawdown_pct"], 0, " %"), f(wv["hold_max_drawdown_pct"], 0, " %"), f(wv["per_1000_eur_end_winner"], 0, " €"), f(wv["per_1000_eur_end_hold"], 0, " €"),
                     "DA" if s["beats_hold_on_return"] else "ne", s["ratings_by_contender"]["winner"]])
    A(table(["Segment", "Dionica", "Pobjednik", "Sharpe pobj.", "Sharpe držanje", "Prinos pobj.", "Prinos držanje", "Pad pobj.", "Pad držanje", "1.000 € pobj.", "1.000 € držanje", "Pobjeđuje držanje po prinosu?", "Ocjena"], rows))
    A("\n**Svi suparnici po segmentu (prinos / Sharpe / pad / poslova):**\n")
    ks = list(tour["meta"]["contenders"].keys())
    rows = []
    for seg in SEGMENTS:
        s = tour["segments"][seg]
        row = [s["name"]]
        for k in ks:
            c = s["contenders"].get(k)
            row.append(f"{f(c['total_return_pct'],0,' %')} / {f(c['sharpe'],2)} / {f(c['max_drawdown_pct'],0,' %')} / {c['trades']}" if c else "-")
        rows.append(row)
    A(table(["Segment"] + [tour["meta"]["contenders"][k] for k in ks], rows))
    A("\n**Koliko puta je suparnik bolji od držanja (po segmentima):**\n")
    A(table(["Suparnik", "Segmenata", "Prinos iznad držanja", "Sharpe iznad držanja", "Manji pad"],
            [[v["name"], v["segments"], v["return_above_hold"], v["sharpe_above_hold"], v["smaller_drawdown"]] for v in tour["contender_beats_hold_counts_by_segment"].values()]))
    A("\n**Deflated Sharpe pobjednika (K=533):** " + "; ".join(f"{tour['segments'][s]['name']} {f(tour['segments'][s]['contenders'][tour['segments'][s]['winner']]['deflated_sharpe_prob'],2)}" for s in SEGMENTS) + ". Čvrst dokaz traži iznad 0,95.\n")

    # ------------------------------------------------------------------ swing
    A("## 1h. Swing test W1 do W8 (autoritativni, revidirani)\n")
    mt = sw["meta"]
    A(f"Razdoblje AI era {mt['window_ai_era'][0]} do {mt['window_ai_era'][1]} (45,1 mjeseci); trošak {mt['costs_bps_per_side']['stocks_and_metals']} bps po strani za dionice i metale, {mt['costs_bps_per_side']['crypto']} bps za kripto, stres 2x i 3x; sleeve {mt['sleeve_capital_eur']} € po papiru; K={mt['ledger_k']}; sha256 registracije {mt['registration_sha256'][:16]}...; K po suparniku: {kv(mt['k_by_contender'],0)}.\n")
    A(f"**Unaprijed upisano pravilo 'radi često':** {mt['rule_works_often']}\n")
    SR = F["swing_rules_hr"]
    A("### Pravila W1 do W8 (običnim riječima, parametri fiksni)\n")
    A(f"*{SR['source']}*\n")
    A(SR["vocabulary_hr"] + "\n")
    A(table(["Pravilo", "Pojam", "Ulaz", "Izlaz", "Parametri"],
            [[x["id"], x["concept"], x["rule_hr"], x["exit_hr"], kv(sw["rules"][[k for k in sw["rules"] if k.startswith(x["id"] + "_")][0]]["params"], 3)] for x in SR["rules"]]))
    A("\nTočan engleski tekst pravila iz registra: facts.json pod swing.rules[*].rules_en; interpretacije: swing.rule_interpretations_en. " + SR["w5_equals_k5b_hr"] + " " + SR["registered_before_first_run_hr"] + " **" + SR["not_run_hr"] + "**\n")
    A("### Sve dionice (zbroj 43 sleevea), AI era\n")
    rows = []
    for cid in W_ORDER:
        b = sw["groups"]["stocks_all"]["contenders"][cid]
        if cid == "B0_BUYHOLD":
            rows.append([sw["pooled_rule_stats"][cid]["name"], "-", "-", "-", "-", "-", "-", "-", "-", f(b.get("total_return_pct"), 0, " %"), f(b.get("end_value_per_1000_eur"), 0, " €"),
                         f(b.get("sharpe"), 2), f(b.get("max_drawdown_pct"), 0, " %"), f(b.get("deflated_sharpe_prob"), 2), "mjerilo"])
            continue
        rows.append([sw["pooled_rule_stats"][cid]["name"], b.get("trades"), f(b.get("trades_per_month"), 1), f(b.get("hit_rate_pct"), 0, " %"), f(b.get("expectancy_eur"), 1, " €"),
                     f(b.get("expectancy_eur_cost_2x"), 1, " €"), f(b.get("profit_factor"), 2), f(b.get("median_hold_days"), 1), f(b.get("mean_hold_days"), 1),
                     f(b.get("total_return_pct"), 0, " %"), f(b.get("end_value_per_1000_eur"), 0, " €"), f(b.get("sharpe"), 2), f(b.get("max_drawdown_pct"), 0, " %"),
                     f(b.get("deflated_sharpe_prob"), 2), "DA" if b.get("eligible") else ("mjerilo" if cid == "B0_BUYHOLD" else "ne")])
    A(table(["Pravilo", "Poslova", "Poslova mj.", "Pogodak", "Zarada po poslu (1.000 €)", "Uz trošak 2x", "Faktor dobiti", "Medijan držanja (dana)", "Prosjek držanja", "Ukupni prinos", "1.000 € postane", "Sharpe", "Max pad", "Deflated Sharpe", "Podobno"], rows))
    A("\nRang među podobnima (eura mjesečno na 43 sleevea; NIJE zarada jednog računa):\n")
    A(table(["#", "Pravilo", "Poslova mj.", "Po poslu", "Faktor dobiti", "EUR/mj."],
            [[i + 1, x["name"], f(x["trades_per_month"], 1), f(x["expectancy_eur"], 0, " €"), f(x["profit_factor"], 2), f(x["score_eur_per_month"], 0)] for i, x in enumerate(sw["groups"]["stocks_all"]["ranking"])]))
    A(f"\nNije podobno (sve dionice): {'; '.join(k + ' (' + ', '.join(v) + ')' for k, v in sw['groups']['stocks_all']['not_eligible'].items())}\n")
    A(f"Kupi i drži (sve dionice): {f(sw['groups']['stocks_all']['buy_and_hold']['total_return_pct'],0,' %')}, Sharpe {f(sw['groups']['stocks_all']['buy_and_hold']['sharpe'],2)}, pad {f(sw['groups']['stocks_all']['buy_and_hold']['max_drawdown_pct'],0,' %')}.\n")

    A("### Rezultati po skupini (najbolje podobno pravilo i usporedba s držanjem)\n")
    rows = []
    for g in GROUP_NAMES:
        G = sw["groups"][g]
        bh = G["buy_and_hold"]
        if G["ranking"]:
            t0 = G["ranking"][0]
            b = G["contenders"][t0["contender"]]
            rows.append([GROUP_NAMES[g], G["n_tickers"], t0["name"], f(t0["trades_per_month"], 1), f(t0["expectancy_eur"], 0, " €"), f(t0["profit_factor"], 2), f(b.get("total_return_pct"), 0, " %"), f(bh["total_return_pct"], 0, " %"), f(bh["end_value_per_1000_eur"], 0, " €"), f(b.get("end_value_per_1000_eur"), 0, " €")])
        else:
            rows.append([GROUP_NAMES[g], G["n_tickers"], "nitko nije podoban", "-", "-", "-", "-", f(bh["total_return_pct"], 0, " %"), f(bh["end_value_per_1000_eur"], 0, " €"), "-"])
    A(table(["Skupina", "Papira", "Najbolje pravilo", "Poslova mj.", "Po poslu", "Faktor dobiti", "Prinos pravila", "Prinos držanja", "1.000 € držanje", "1.000 € pravilo"], rows))

    A("\n### Puni popis: svako pravilo u svakoj skupini (poslova / po poslu € / faktor dobiti / prinos / Sharpe / pad / podobno)\n")
    rows = []
    for g in GROUP_NAMES:
        row = [GROUP_NAMES[g]]
        for cid in W_ORDER:
            b = sw["groups"][g]["contenders"][cid]
            row.append(f"{b.get('trades')} / {f(b.get('expectancy_eur'),0)} / {f(b.get('profit_factor'),2)} / {f(b.get('total_return_pct'),0,' %')} / {f(b.get('sharpe'),2)} / {f(b.get('max_drawdown_pct'),0,' %')} / {'DA' if b.get('eligible') else 'ne'}")
        rows.append(row)
    A(table(["Skupina"] + [W_SHORT[c] for c in W_ORDER], rows))
    A("\nPoslova mjesečno po skupini i pravilu:\n")
    rows = [[GROUP_NAMES[g]] + [f(sw["groups"][g]["contenders"][c].get("trades_per_month"), 1) for c in W_ORDER[:-1]] for g in GROUP_NAMES]
    A(table(["Skupina"] + [W_SHORT[c] for c in W_ORDER[:-1]], rows))
    A("\nPogodak (%), medijan držanja (dana), trošak 2x očekivanje (€), 3x faktor dobiti, prinos uz trošak 2x po skupini (sve dionice i segmenti):\n")
    rows = []
    for g in SEGMENTS + ["stocks_all"]:
        for cid in W_ORDER[:-1]:
            b = sw["groups"][g]["contenders"][cid]
            rows.append([GROUP_NAMES[g], W_SHORT[cid], f(b.get("hit_rate_pct"), 0), f(b.get("median_hold_days"), 1), f(b.get("expectancy_eur_cost_2x"), 1), f(b.get("profit_factor_cost_3x"), 2), f(b.get("total_return_cost_2x_pct"), 0, " %"), f(b.get("longest_losing_streak")), f(b.get("top5_profit_share_pct"), 0, " %")])
    A(table(["Skupina", "Pravilo", "Pogodak %", "Medijan držanja", "Očekivanje 2x €", "Faktor dobiti 3x", "Prinos uz 2x", "Najduži niz gubitaka", "Udio 5 najboljih u dobiti"], rows))

    A("\n### Dosljednost kroz 8 skupina (podobno u koliko; pozitivno očekivanje u koliko)\n")
    A(table(["Pravilo", "Podobno u", "Pozitivno očekivanje u", "Podobne skupine"],
            [[v["name"], f"{v['eligible_in']} / {v['of']}", f"{v['positive_expectancy_in']} / {v['of']}", ", ".join(GROUP_NAMES[g] for g in v["eligible_groups"])] for v in sw["consistency_across_groups"].values()]))

    A("\n### Razdoblja (sve dionice): 2016-2020, 2021-2022 (pad tržišta) i AI era; poslova / zarada po poslu / faktor dobiti / prinos\n")
    rows = []
    for cid, v in sw["contexts_pooled"].items():
        if cid == "B0_BUYHOLD":
            continue
        a, b, c = v["y2016_2020"], v["y2021_2022"], v["ai_era"]
        rows.append([v["name"], f"{a['trades']} / {f(a['expectancy_eur'],0,' €')} / {f(a['profit_factor'],2)} / {f(a['total_return_pct'],0,' %')}", f"{b['trades']} / {f(b['expectancy_eur'],0,' €')} / {f(b['profit_factor'],2)} / {f(b['total_return_pct'],0,' %')}", f"{c['trades']} / {f(c['expectancy_eur'],0,' €')} / {f(c['profit_factor'],2)} / {f(c['total_return_pct'],0,' %')}"])
    bh = sw["contexts_pooled"]["B0_BUYHOLD"]
    rows.append(["B0 kupi i drži", f(bh["y2016_2020_total_return_pct"], 0, " %"), f(bh["y2021_2022_total_return_pct"], 0, " %"), f(bh["ai_era_total_return_pct"], 0, " %")])
    A(table(["Pravilo", "2016-2020", "2021-2022 (pad)", "AI era"], rows))
    nonpos = [v["name"] for k, v in sw["contexts_pooled"].items() if k != "B0_BUYHOLD" and v["context_2021_2022_expectancy_nonpositive"]]
    A(f"\nU 2021-2022 očekivanje po poslu je nula ili negativno za {len(nonpos)} od 8 pravila ({', '.join(n.split(' ')[0] for n in nonpos)}); W1 (+1 €, faktor dobiti 1,04) i W8 (+2 €, faktor dobiti 1,14) su pozitivni, ali blizu nule. Zato 'radi' vrijedi samo za AI eru dok se ne pokaže suprotno u drugom režimu.\n")

    A("### Koncentracija na rijetke velike poslove (revizija, sve dionice)\n")
    A(table(["Pravilo", "Poslova", "Medijan posla", "Prosjek posla", "Prosjek bez 10 najboljih", "Udio 10 najboljih u dobiti", "Najveći posao"],
            [[v["name"], v["trades"], f(v["median_trade_return_pct"], 1, " %"), f(v["mean_trade_return_pct"], 1, " %"), f(v["mean_without_best10_pct"], 1, " %"), f(v["best10_share_of_profit_pct"], 0, " %"), f(v["largest_trade_return_pct"], 0, " %")] for v in sw["concentration_pooled"].values()]))
    A("\nUdio 5 najboljih poslova u dobiti po skupini:\n")
    rows = [[W_SHORT[c]] + [f(sw["concentration_by_group_top5_share_pct"][c][g], 0, " %") for g in GROUP_NAMES] for c in sw["concentration_by_group_top5_share_pct"]]
    A(table(["Pravilo"] + [GROUP_NAMES[g] for g in GROUP_NAMES], rows))
    A("\nNajveći pojedinačni posao W5 (+640 %) provjeren sam prema data/ohlcv/LITE_1d.csv: " + F["checked_by_me"][0] + "\n")

    A("### Robusnost ±20 % (tri najbolja po očekivanju, jedan prag po jedan)\n")
    A(f"*{sw['robustness_pm20_note']}.*\n")
    for cid, v in sw["robustness_pm20"].items():
        A(f"**{v['name']}**: osnova {f(v['base_expectancy_eur'],1)} € po poslu ({v['base_trades']} poslova); fragilno: {f(v['fragile'])}; najlošije očekivanje uz trošak 2x: {f(v['worst_expectancy_cost_2x_eur'],1)} €.\n")
        A(table(["Prag", "Faktor", "Vrijednost", "Poslova", "Očekivanje €", "Uz 2x €", "Faktor dobiti"], [[x["param"], x["factor"], x["value"], x["trades"], f(x["expectancy_eur"], 1), f(x["expectancy_eur_cost_2x"], 1), f(x["profit_factor"], 2)] for x in v["variants"]]))
    A("Napomena: slab test u bik-tržištu (ne gleda drugi režim).\n")

    mx = sw["deflated_sharpe_max_rule"]
    A(f"### Deflated Sharpe (K=542)\n\nNajviši među pravilima: {mx[0]} = {f(mx[1],2)}. Po pravilu (sve dionice): " + "; ".join(f"{W_SHORT[c]} {f(v,2)}" for c, v in sw["deflated_sharpe_pooled"].items()) + ". Čvrst dokaz traži iznad 0,95; ovdje su vrijednosti niske (oko 0,3 do 0,4 za najbolja pravila), pa je ovo uputa gdje dalje istraživati, ne dokaz.\n")
    A("### Test pogleda u budućnost (lookahead)\n")
    A(table(["Pravilo", "Prolazi", "Provjera nizova", "Provjera poslova", "Greške"], [[W_SHORT[c] + " " + c.split('_', 1)[1], f(v["ok"]), v["array_checks"], v["trade_checks"], v["failures"]] for c, v in sw["lookahead"].items()]))

    # placebo
    P = sw["placebo"]["levels"]
    A("\n### Placebo: pobjeđuju li razine slučajnost?\n")
    skipped = "; ".join(f"{k} ({v})" for k, v in P["skipped"].items())
    A(f"{f(P['n_levels'], 0)} razina (zadnji trgovački dan svakog od {P['n_months']} mjeseci AI ere, {P['n_papers']} papira). Preskočeno prema pravilima podataka: {skipped}. "
      "Dodir = raspon svijeće unutar 0,25 ATR od crte; odbijanje = potez od 1,5 ATR natrag unutar 10 svijeća nakon prvog dodira; probijanje = zatvaranje više od 1 ATR iza razine "
      "(ako se u istoj svijeći dogode oba, računa se probijanje); razine bliže od 0,5 ATR izbačene; ishod se gleda 20 dana unaprijed; samo razine koje su tada već bile poznate (okret potvrđen 5 svijeća poslije). "
      "Interval = bootstrap po kalendarskim mjesecima (2000 ponavljanja, sjeme 20261014).\n")
    r0 = P["real_pct"]
    A(table(["Kontrola", "Broj", "Dodir %", "Odbijanje %", "Probijanje %", "Razlika odbijanja (pp) [95 %]", "Razlika probijanja (pp) [95 %]", "Razlika dodira (pp) [95 %]"],
            [["PRAVE razine", P["n_levels"], f(r0["touch_rate"]), f(r0["bounce_rate"]), f(r0["break_rate"]), "-", "-", "-"]] +
            [[nm, P["n_controls"][key], f(P["controls_pct"][key]["touch_rate"]), f(P["controls_pct"][key]["bounce_rate"]), f(P["controls_pct"][key]["break_rate"]),
              f"{f(P['diff_pp_with_ci95'][key]['bounce_rate']['diff_pp'])} [{f(P['diff_pp_with_ci95'][key]['bounce_rate']['ci95_pp'][0])}; {f(P['diff_pp_with_ci95'][key]['bounce_rate']['ci95_pp'][1])}]",
              f"{f(P['diff_pp_with_ci95'][key]['break_rate']['diff_pp'])} [{f(P['diff_pp_with_ci95'][key]['break_rate']['ci95_pp'][0])}; {f(P['diff_pp_with_ci95'][key]['break_rate']['ci95_pp'][1])}]",
              f"{f(P['diff_pp_with_ci95'][key]['touch_rate']['diff_pp'])} [{f(P['diff_pp_with_ci95'][key]['touch_rate']['ci95_pp'][0])}; {f(P['diff_pp_with_ci95'][key]['touch_rate']['ci95_pp'][1])}]"]
             for nm, key in (("Nasumična cijena", "random_price"), ("Pomak ±3 %", "shift_pm3pct"), ("Par oko razine", "pair_around"))]))
    A(f"\nStroži intervali s blokovima od 3 mjeseca (usporedba s nasumičnom cijenom, pp): dodir {P['block3_ci95_pp_vs_random']['touch_rate']}, odbijanje {P['block3_ci95_pp_vs_random']['bounce_rate']}, probijanje {P['block3_ci95_pp_vs_random']['break_rate']}.\n")
    A("Odbijanje po skupini (prave / nasumične, %): " + "; ".join(f"{GROUP_NAMES.get(g, "Metali, indeksi i ETF-ovi (referentno)" if g == "metals_indices" else g)} {f(v['real'])} / {f(v['random'])} (n={v['n_levels']})" for g, v in P["by_group_bounce_real_vs_random_pct"].items()) + ".\n")
    A("Odbijanje po broju okreta (prave / nasumične, %): " + "; ".join(f"{k}: {f(v['real'])} / {f(v['random'])} (n={v['n']})" for k, v in P["by_touches_bounce_real_vs_random_pct"].items()) + ". Po jačini (prave, %): " + "; ".join(f"{k} {f(v)}" for k, v in P["by_strength_bounce_real_pct"].items()) + ".\n")
    A(f"**Presuda:** {P['verdict_hr']}\n")
    A("**Mehanika tržišta (višak prinosa nad prosjekom istog papira, postotni bodovi, 95 % interval):**\n")
    ev = sw["placebo"]["mechanics"]
    rows = []
    for eid, e in ev["ai_era"]["events"].items():
        pre = ev["pre_ai_2017_2022"]["events"][eid]
        bh = e["by_horizon"]
        rows.append([eid.split("_")[0], e["label"], e["n"],
                     "; ".join(f"{h}d {f(bh[h]['excess_vs_ticker_avg_pp'])} [{f(bh[h]['excess_ci95_pp'][0])}; {f(bh[h]['excess_ci95_pp'][1])}]" for h in ("5", "10", "20")),
                     f"[{f(e['block3_ci95_excess_pp']['10'][0])}; {f(e['block3_ci95_excess_pp']['10'][1])}]",
                     f"{pre['n']}: 10d {f(pre['by_horizon']['10']['excess_vs_ticker_avg_pp'])} [{f(pre['by_horizon']['10']['excess_ci95_pp'][0])}; {f(pre['by_horizon']['10']['excess_ci95_pp'][1])}]"])
    A(table(["Događaj", "Opis", "Broj (AI era)", "Višak 5/10/20 dana", "Blokovi 3 mj. (10 d)", "2017-2022: broj i 10 d"], rows))
    A("\nProsjek svih dana (AI era): " + ", ".join(f"{h} dana {f(v)} %" for h, v in ev["ai_era"]["all_days_mean_pct"].items()) + ".\n")
    A(sw["placebo"]["mechanics_verdict_hr"] + "\n")

    # audit
    Au = sw["audit"]
    A("### Revizija swing testa i što je nađeno\n")
    A(f"- Neovisni program bez uvoza motora: {Au['independent_program_checks']} provjera (swing {Au['independent_checks_by_kind']['swing']}, karte {Au['independent_checks_by_kind']['map']}, placebo {Au['independent_checks_by_kind']['placebo']}), sve se slažu: {f(Au['independent_program_all_match'])}.")
    A(f"- Pravilo ranga ponovno izračunato iz spremljenih brojeva: {Au['ranking_rule_groups_checked']} skupina, razlika u {Au['ranking_rule_groups_wrong']}. Zamrznute datoteke jednake registru: {f(Au['frozen_equal_registry_all'])}.")
    A(f"- Hash swing.py: registriran {Au['swing_py_hash_registered']}, trenutni {Au['swing_py_hash_now']} (isti: {f(Au['swing_py_hash_same'])}); swing_run.py isti: {f(Au['swing_run_py_hash_same'])}.")
    w8a, w8b = Au["crypto_W8_with_repair"], Au["crypto_W8_without_repair"]
    A(f"- Kripto popravci loših tickova: {kv(Au['crypto_bad_tick_repairs'],0)}; mijenja samo {', '.join(Au['crypto_repair_changes_contenders'])}: s popravkom {w8a['trades']} poslova, očekivanje {f(w8a['expectancy_eur'],2)} €, faktor dobiti {f(w8a['profit_factor'],2)}; bez popravka {f(w8b['expectancy_eur'],2)} €, faktor dobiti {f(w8b['profit_factor'],2)}.")
    for x in Au["findings_hr"]:
        A(f"- {x}")

    PN = F["pine_status"]
    A("\n### Pine skripte za master dokument (stanje prevođenja i usklađenosti)\n")
    A(f"*Izvor: {PN['source']}*\n")
    A(table(["Datoteka", "Vrsta", "Prevođenje na poslužitelju", "Prevođenje u Desktopu"], [[x["file"], x["kind"], x["server_compile"], x["desktop_compile"]] for x in PN["files"]]))
    w = PN["w1_mu_tradingview_vs_python"]
    A(f"\nW1 na MU: TradingView {w['tv_trades']} trgovina, pogodak {f(w['tv_hit_pct'])} %, prinos {f(w['tv_return_pct'])} %, faktor dobiti {f(w['tv_profit_factor'],3)}, pad {f(w['tv_max_dd_pct'])} %; "
      f"Python {w['py_trades']} trgovina, pogodak {f(w['py_hit_pct'])} %, prinos {f(w['py_return_pct'])} %, faktor dobiti {f(w['py_profit_factor'],2)}, pad {f(w['py_max_dd_pct'])} %. {w['note_hr']} {PN['not_measured_hr']}\n")
    A(PN["incident_hr"] + " " + PN["alert_note_hr"] + "\n")

    # ------------------------------------------------------------------ 2 C13C
    A("\n## 2. Gdje stoji C13C (Petrov algoritam)\n")
    A(c13["what_it_is_hr"] + "\n")
    A("### 2a. Turnir (K1) po segmentu, AI era 2023-01-03 do 2026-10-05, sleeve 1.000 € po papiru\n")
    rows = []
    for seg in SEGMENTS:
        t = c13["in_today_tests"]["tournament_K1_per_segment"][seg]
        c, h2 = t["c13c"], t["hold"]
        rows.append([GROUP_NAMES[seg], f(c["total_return_pct"], 0, " %"), f(c["end_value_per_1000_eur"], 0, " €"), f(c["sharpe"], 2), f(c["max_drawdown_pct"], 0, " %"), c["trades"], f(h2["total_return_pct"], 0, " %"), f(h2["end_value_per_1000_eur"], 0, " €"), f(h2["sharpe"], 2), f(h2["max_drawdown_pct"], 0, " %"), t["winner"], t["c13c_rating"]])
    A(table(["Segment", "C13C prinos", "1.000 € postane", "Sharpe", "Max pad", "Poslova", "Držanje prinos", "1.000 € držanje", "Sharpe držanja", "Pad držanja", "Pobjednik segmenta", "Ocjena C13C"], rows))
    cc = tour["c13c_ticker_counts"]
    A(f"\nPo dionici (43): C13C veći prinos od držanja na {cc['beats_hold_on_return']}, veći Sharpe na {cc['beats_hold_on_sharpe']}, manji najgori pad na {cc['smaller_drawdown_than_hold']} (objavljeno u overview_facts.json: {cc['published_in_overview_facts']['beats_ret']} / {cc['published_in_overview_facts']['beats_sharpe']} / {cc['published_in_overview_facts']['smaller_dd']}, slaže se).\n")
    A("**Ocjena C13C po segmentima i čitanje:** C13C je pobjednik samo u memoriji (Sharpe 1,78 naspram 1,85 za držanje), ali ni tamo ne pobjeđuje držanje po prinosu (7.677 € naspram 19.368 € iz 1.000 €); pad je manji (-34 % naspram -48 %, tj. 337 € naspram 477 € na 1.000 € s vrha), a 'osiguranje' je koštalo oko 11.691 € završne vrijednosti. Zaključak turnira: alat za smanjenje pada, ne pojačivač prinosa. K7 (ponovni ulaz) ne popravlja (prosječni Sharpe 1,05 naspram 1,16 za K1).\n")
    A("### 2b. Swing W1 (isti C13C) po skupini, AI era\n")
    rows = []
    for g in GROUP_NAMES:
        b = c13["in_today_tests"]["swing_W1_per_group"][g]
        rows.append([GROUP_NAMES[g], b.get("trades"), f(b.get("trades_per_month"), 1), f(b.get("hit_rate_pct"), 0, " %"), f(b.get("expectancy_eur"), 0, " €"), f(b.get("profit_factor"), 2), f(b.get("median_hold_days"), 1), f(b.get("total_return_pct"), 0, " %"), f(b.get("end_value_per_1000_eur"), 0, " €"), f(b.get("sharpe"), 2), f(b.get("max_drawdown_pct"), 0, " %"), "DA" if b.get("eligible") else "ne"])
    A(table(["Skupina", "Poslova", "Poslova mj.", "Pogodak", "Po poslu", "Faktor dobiti", "Medijan držanja", "Prinos", "1.000 € postane", "Sharpe", "Pad", "Podobno"], rows))
    ctxw = c13["in_today_tests"]["swing_W1_contexts_pooled"]
    def _ctx(d):
        return f"{d['trades']} poslova, {f(d['expectancy_eur'],0)} € po poslu, faktor dobiti {f(d['profit_factor'],2)}, prinos {f(d['total_return_pct'],0,' %')}, pogodak {f(d['hit_rate_pct'],0,' %')}"
    A(f"\nW1 sve dionice kroz razdoblja: 2016-2020: {_ctx(ctxw['y2016_2020'])}; 2021-2022: {_ctx(ctxw['y2021_2022'])}; AI era: {_ctx(ctxw['ai_era'])}.\n")
    A("Napomena: turnir K1 i swing W1 su ISTO pravilo (parity test 9 od 9) i daju iste segmentne brojke (npr. memorija 668 %, Sharpe 1,78; mreže i serveri 224 %, Sharpe 1,28); swing dodaje statistiku po poslu (pogodak, zarada po poslu, faktor dobiti, trajanje).\n")
    A("### 2c. Po dionici MU, WDC, STX, RMBS, SIMO: C13C naspram držanja i W5, W3, W2, W8\n")
    for t in ("MU", "WDC", "STX", "RMBS", "SIMO"):
        d = c13["per_ticker_memory5"][t]
        A(f"**{t}** (segment {GROUP_NAMES[d['segment']]})\n")
        rows = []
        for cid, v in d["tournament"].items():
            rows.append([tour["meta"]["contenders"][cid], f(v["total_return_pct"], 0, " %"), f(v["end_value_per_1000_eur"], 0, " €"), f(v["sharpe"], 2), f(v["max_drawdown_pct"], 0, " %"), v["trades"]])
        A(table(["Turnir pravilo", "Prinos", "1.000 € postane", "Sharpe", "Max pad", "Poslova"], rows))
        rows = []
        for cid, v in d["swing"].items():
            if v:
                rows.append([W_SHORT[cid], v["trades"], f(v["trades_per_month"], 2), f(v["hit_rate_pct"], 0, " %"), f(v["expectancy_eur"], 0, " €"), f(v["profit_factor"], 2), f(v["median_hold_days"], 1), f(v["top5_profit_share_pct"], 0, " %"), f(v["total_return_pct"], 0, " %"), f(v["sharpe"], 2), f(v["max_drawdown_pct"], 0, " %")])
        A(table(["Swing pravilo", "Poslova", "Poslova mj.", "Pogodak", "Po poslu", "Faktor dobiti", "Medijan držanja", "Udio 5 najboljih u dobiti", "Prinos", "Sharpe", "Pad"], rows))
    A("### 2d. Segmenti memorija i sučelja: C13C naspram ostalih swing pravila i držanja\n")
    for g in ("memory", "mem_interface_storage", "stocks_all"):
        A(f"**{GROUP_NAMES[g]}**\n")
        rows = [[W_SHORT[cid], v["trades"], f(v["trades_per_month"], 1), f(v["hit_rate_pct"], 0, " %"), f(v["expectancy_eur"], 0, " €"), f(v["profit_factor"], 2), f(v["total_return_pct"], 0, " %"), f(v["end_value_per_1000_eur"], 0, " €"), f(v["sharpe"], 2), f(v["max_drawdown_pct"], 0, " %")] for cid, v in c13["vs_other_rules_per_group"][g].items()]
        A(table(["Pravilo", "Poslova", "Poslova mj.", "Pogodak", "Po poslu", "Faktor dobiti", "Prinos", "1.000 € postane", "Sharpe", "Pad"], rows))
    A("### 2e. Povijest C13C: Critic i računi od 600 EUR\n")
    CH = F["c13c_history"]
    for g in CH["gate_verdicts"]:
        A(f"- **{g['id']}** ({g['date']}): {g['verdict']}. {g['detail']} *({g['source']})*")
    A("\n" + CH["c13c_family_note_hr"] + "\n")
    A(CH["windows_note_hr"] + "\n")
    c34 = CH["c34_600eur_2024_10_11_to_2026_10_08"]
    A(f"**C34 račun od 600 EUR, 11.10.2024.-8.10.2026.** ({c34['profile_hr']}) *{c34['source']}*\n")
    A(table(["Dionica", "Cijele: završno €", "Frakcije: završno €", "Prinos frakcija", "Max pad računa", "Zatvorenih", "Kupi-i-drži (frakcije) €", "Trošak x2 €", "Stop 1 % lošiji €"],
            [[x["ticker"], f(x["whole_end_eur"], 2), f(x["fractional_end_eur"], 2), f(x["fractional_return_pct"], 2, " %"), f(x["max_dd_account_pct"], 2, " %"), x["closed_trades"], f(x["buy_hold_fractional_eur"], 2), f(x["cost2x_eur"], 2), f(x["stop_1pct_worse_eur"], 2)] for x in c34["per_ticker"]]))
    ca = c34["combined_account"]
    A(f"\nZajednički račun (jedna pozicija, prioritet MU, WDC, STX, SIMO, RMBS, MRAM, SNDK): cijele {f(ca['whole_end_eur'],2)} € ({f(ca['whole_return_pct'],2)} %, pad {f(ca['whole_max_dd_pct'],2)} %), frakcije {f(ca['fractional_end_eur'],2)} € ({f(ca['fractional_return_pct'],2)} %, pad {f(ca['fractional_max_dd_pct'],2)} %), {ca['closed_trades']} zatvorenih.\n")
    A("IS 2016-2020 / WF 2021-2023 (resetirano na 600 €, frakcije): " + "; ".join(f"{k}: IS {f(v['IS_2016_2020_pct'],2)} % ({v['IS_trades']}), WF {f(v['WF_2021_2023_pct'],2)} % ({v['WF_trades']})" for k, v in c34["is_wf_fractional_reset_600"].items()) + ".\n")
    A("Po godinama (frakcije): " + "; ".join(f"{k}: " + ", ".join(f"{kk} {f(vv,2)} %" for kk, vv in v.items()) for k, v in c34["yearly_fractional_pct"].items()) + ".\n")
    A(c34["takeaway_hr"] + "\n")
    c2 = CH["c34_rmbs_simo_2024_01_02_to_2026_10_09"]
    A("**RMBS i SIMO od 2.1.2024. do 9.10.2026.** *" + c2["source"] + "*\n")
    A(table(["Dionica", "Profil", "Završno €", "Prinos", "CAGR", "Max pad", "Zatvorenih"], [[x["ticker"], x["profile"], f(x["end_eur"], 2), f(x["return_pct"], 2, " %"), f(x["cagr_pct"], 2, " %"), f(x["max_dd_pct"], 2, " %"), x["trades"]] for x in c2["rows"]]))
    A(f"\nKupi-i-drži: {kv(c2['buy_hold_eur'],2,' €')}. {c2['caveats_hr']}\n")
    c3 = CH["c13c_2022_to_2026_10_08_600eur_three_stocks"]
    A(f"**C13C 2022.-2026. (MU/WDC/STX, jedna pozicija)** *{c3['source']}*: 500 € postane {f(c3['c13c_end_eur']['500'],2)} €, 600 € postane {f(c3['c13c_end_eur']['600'],2)} € (CAGR {kv(c3['cagr_pct'],2,' %')}; najveći pad {kv(c3['max_dd_pct'],2,' %')}). C29 {f(c3['c29_end_eur_600'],2)} €, C30 {f(c3['c30_end_eur_600'],2)} €. "
      f"Jednako podijeljeno kupi-i-drži MU/WDC/STX: {f(c3['buy_hold_equal_mu_wdc_stx_600_eur'],2)} € (pad {c3['buy_hold_max_dd_pct']} %); SMA200 držanje {f(c3['sma200_hold_600_eur'],2)} € (pad {c3['sma200_hold_max_dd_pct']} %). Godišnje 600 € C13C: {kv(c3['yearly_600_c13c_pct'],2,' %')}. {c3['smh_regime_hr']}\n")
    c4 = CH["c21_c22_600eur_windows"]
    A(f"**C21/C22 računi 600 EUR (MU/WDC/STX)** *{c4['source']}*\n")
    A(table(["Prozor", "Završni račun €", "Prinos", "Max pad"], [[x["window"], f(x["end_eur"], 2), f(x["return_pct"], 2, " %"), f(x["max_dd_pct"], 2, " %")] for x in c4["rows"]]))
    A(f"\nNakon ChatGPT-a (1.12.2022.) svaka dionica zasebno s 600 €: {kv(c4['post_chatgpt_per_stock_600_end_eur'],2,' €')}; pasivna košarica MU/WDC/STX {f(c4['post_chatgpt_buy_hold_3stocks_end_eur'],2)} €. {c4['post_chatgpt_closed_trades']}.\n")
    cr = CH["correlation_2024_01_02_to_2026_10_09"]
    A(f"**Korelacije dnevnih prinosa pet kandidata** *{cr['source']}*: {kv(cr['pairs'],3)}. Memorijski papiri nisu diversifikacija jedan drugome.\n")

    # ------------------------------------------------------------------ 3 state now
    A("## 3. Stanje sada po papiru (karte, swing/map)\n")
    A(f"{st['meta']['note_hr']}\n")
    glabel = dict(GROUP_NAMES, crypto="Kripto (BTC, ETH, SOL, BNB; kripto na IBKR-u za HR: nepotvrđeno)", metals_indices="Metali, rudari, indeksi i ETF-ovi (referentno; američki ETF-ovi i EU dostupnost nepotvrđeni)")
    order = ["memory", "mem_interface_storage", "equipment", "ai_chips_logic", "network_servers", "cloud", "crypto", "metals_indices"]
    for g in order:
        ts = [t for t, v in st["tickers"].items() if v["group"] == g]
        if not ts:
            continue
        A(f"### {glabel.get(g, g)}\n")
        rows = []
        for t in ts:
            v = st["tickers"][t]
            sr_ = v["swing_range"]

            def lv(x):
                rate = f"{x['bounced']}/{x['touches_after_formation']}" if x["touches_after_formation"] else "0"
                tag = "" if x["enough_touches"] else "*"
                return f"{f(x['price'],2)} ({f(x['distance_pct'],1,' %')}; {f(x['distance_atr'],1)} ATR; okreta {x['turning_points']}; odbila {rate}{tag})"

            bias = {"bullish": "bikovski", "bearish": "medvjeđi", "range": "bočni"}
            pos = sr_["position_pct"]
            if sr_["zone"] == "outside":
                zone = f"izvan raspona, {'iznad vrha' if pos > 100 else 'ispod dna'} ({f(pos,0,' %')})"
            else:
                zone = f"{'premium (skuplja polovica)' if sr_['zone'] == 'premium' else 'discount (jeftinija polovica)'} ({f(pos,0,' %')})"
            rows.append([t, v["last_date"], f(v["last_close"], 2), bias.get(v["weekly_bias"], v["weekly_bias"]), bias.get(v["daily_bias"], v["daily_bias"]), zone,
                         f(v["sma200_distance_pct"], 0, " %"), f(v["high_52w"]["distance_pct"], 0, " %"),
                         " ; ".join(lv(x) for x in v["nearest_supports"]) or "nema potvrđene potpore ispod", " ; ".join(lv(x) for x in v["nearest_resistances"]) or "nema potvrđenog otpora iznad (cijena blizu ili iznad starih vrhova)"])
        A(table(["Papir", "Zadnji datum", "Zadnje zatvaranje", "Tjedni trend", "Dnevni trend", "Položaj u zadnjem rasponu (postotak raspona)", "Cijena iznad SMA200 za", "52-tjedni vrh je iznad cijene za", "Dvije najbliže potpore (udalj.; ATR; okreta; odbila od dodira)", "Dva najbliža otpora"], rows))
        A("\n*'*' uz razinu = premalo dodira za zaključak o pouzdanosti. Odbijanje pokazuje povijest te razine izvan uzorka; placebo test kaže da potvrđene razine ne odbijaju češće od nasumičnih crta.*\n")
    A("Rječnik za tablicu: bikovski = viši vrhovi i više dna; premium/discount = gornja/donja polovica zadnjeg potvrđenog raspona (premium = skuplje); ATR = prosječni dnevni raspon (14 dana).\n")

    # ------------------------------------------------------------------ 4 artifacts
    A("## 4. Svi prije objavljeni artefakti (glavni dokument ih zamjenjuje)\n")
    A(F["artifacts_note_hr"] + "\n")
    A(table(["Naslov", "URL", "Što je sadržavao", "Izvor"], [[x["title"], x["url"] or "URL nije pronađen u datotekama", x["contains_hr"], x["source"]] for x in F["artifacts_previous"]]))

    # ------------------------------------------------------------------ 5 reconciliation
    A("\n## 5. Usklađivanje proturječnih brojki (koja izvor pobjeđuje)\n")
    for x in F["reconciliation"]:
        A(f"- **{x['topic']}**: {x['conflict']} *Pobjeđuje:* {x['wins']} *Što napisati:* {x['action_hr']}")
    A("\n## 6. Neprovjerive ili nepotvrđene tvrdnje (ne tvrditi u dokumentu)\n")
    for x in F["unverifiable_claims"]:
        A(f"- {x}")
    A("\n## 7. Što sam sam provjerio\n")
    for x in F["checked_by_me"]:
        A(f"- {x}")
    A("")
    return "\n".join(L)
