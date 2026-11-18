#!/usr/bin/env python3
"""Collect every number the master document needs into one facts.json + FACTS.md.

Read-only on all project files. Writes only:
  reports/research/MASTER_20261014/facts.json
  reports/research/MASTER_20261014/FACTS.md

Numbers come from the project JSON files whenever a JSON exists. Numbers that exist only in
Markdown reports are copied by hand into the HAND_* structures below, each with a `source`
field, so every value can be traced. Nothing here sends orders or touches broker APIs.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "reports" / "research"
AIC = RES / "AICHAIN_20261014"
SW = AIC / "swing"
TOP = RES / "TOP10_20261014"
CDT = RES / "CRYPTO_DT_20261014"
OUT = RES / "MASTER_20261014"

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
W_NAMES = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 sweep i promjena smjera",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
    "B0_BUYHOLD": "B0 kupi i drži (mjerilo)",
}
K_NAMES = {
    "B0_BUYHOLD": "Držanje (mjerilo)",
    "K1_C13C_ORIG": "K1 C13C",
    "K2_SMA200_TREND": "K2 SMA200",
    "K3_DONCHIAN_55_20": "K3 proboj 55/20",
    "K4_TSMOM_126": "K4 zamah 126",
    "K5_SUPPORT_RESISTANCE": "K5 potpora",
    "K5B_SR_BREAKOUT_RETEST": "K5B proboj + povratak",
    "K6_MOMENTUM_CS": "K6 rotacija zamaha",
    "K7_C13C_PLUS_TREND_REENTRY": "K7 C13C + ponovni ulaz",
}
MEM5 = ["MU", "WDC", "STX", "RMBS", "SIMO"]


def jl(p: Path):
    return json.loads(p.read_text())


def r(x, n=2):
    if x is None:
        return None
    return round(float(x), n)


def pct(x, n=1):
    return None if x is None else round(float(x) * 100, n)


def eur_end(total_return, start=1000.0):
    return None if total_return is None else round(start * (1 + float(total_return)), 0)


# --------------------------------------------------------------------------------------
# SWING (audited, authoritative)
# --------------------------------------------------------------------------------------
def stat_block(s: dict) -> dict:
    """Normalise one stats dict from swing results (AI era or a context window)."""
    keep = {
        "trades": s.get("trades"),
        "trades_per_month": r(s.get("trades_per_month"), 2),
        "hit_rate_pct": pct(s.get("hit_rate")),
        "avg_win_eur": r(s.get("avg_win_eur"), 0),
        "avg_loss_eur": r(s.get("avg_loss_eur"), 0),
        "expectancy_eur": r(s.get("expectancy_eur"), 2),
        "expectancy_eur_cost_2x": r(s.get("expectancy_eur_cost_2x"), 2),
        "expectancy_eur_cost_3x": r(s.get("expectancy_eur_cost_3x"), 2),
        "profit_factor": r(s.get("profit_factor"), 2),
        "profit_factor_cost_2x": r(s.get("profit_factor_cost_2x"), 2),
        "profit_factor_cost_3x": r(s.get("profit_factor_cost_3x"), 2),
        "median_hold_days": r(s.get("median_hold_days"), 1),
        "mean_hold_days": r(s.get("mean_hold_days"), 1),
        "longest_losing_streak": s.get("longest_losing_streak"),
        "top5_profit_share_pct": pct(s.get("top5_profit_share")),
        "sleeves": s.get("sleeves"),
        "total_return_pct": pct(s.get("total_return"), 0),
        "total_return_cost_2x_pct": pct(s.get("total_return_cost_2x"), 0),
        "total_return_cost_3x_pct": pct(s.get("total_return_cost_3x"), 0),
        "sharpe": r(s.get("sharpe"), 2),
        "max_drawdown_pct": pct(s.get("max_drawdown"), 0),
        "exposure_pct": r(s.get("exposure_pct"), 0),
        "psr": r(s.get("psr"), 3),
        "deflated_sharpe_prob": r(s.get("deflated_sharpe_prob"), 3),
    }
    return {k: v for k, v in keep.items() if v is not None}


def build_swing() -> dict:
    summ = jl(SW / "summary.json")
    reg = jl(SW / "registration.json")
    audit = jl(SW / "audit.json")
    aind = jl(SW / "audit_independent.json")
    out: dict = {
        "meta": {
            "window_ai_era": [summ["ai_era_start"], summ["common_end"]],
            "ledger_k": summ["ledger_k"],
            "registration_sha256": summ["registration_sha256"],
            "costs_bps_per_side": {"stocks_and_metals": 2.5, "crypto": 10.0, "stress": ["2x", "3x"]},
            "sleeve_capital_eur": 1000,
            "k_by_contender": summ["registered"],
            "rule_works_often": (
                "Eligible = at least 60 trades in AI era over the group, positive expectancy per trade at "
                "cost 2x and profit factor >= 1.2. Among eligible: rank = expectancy per trade x trades "
                "per month. Buy-and-hold is a benchmark, never ranked."
            ),
        },
        "groups": {},
        "pooled_rule_stats": {},
        "consistency_across_groups": {},
        "contexts_pooled": {},
        "concentration_pooled": {},
        "concentration_by_group_top5_share_pct": {},
        "robustness_pm20": {},
        "lookahead": {},
        "audit": {},
        "placebo": {},
    }

    months = None
    for gid, g in summ["groups"].items():
        res = jl(SW / "results" / f"{gid}.json")
        months = res["window"]["months"]
        entry = {
            "name": g["name"],
            "n_tickers": len(g["tickers"]),
            "tickers": g["tickers"],
            "months_ai_era": r(res["window"]["months"], 1),
            "ranking": [
                {
                    "contender": x["contender"],
                    "name": W_NAMES[x["contender"]],
                    "trades": x["trades"],
                    "trades_per_month": r(x["trades_per_month"], 2),
                    "expectancy_eur": r(x["expectancy_eur"], 2),
                    "expectancy_eur_cost_2x": r(x["expectancy_eur_cost_2x"], 2),
                    "profit_factor": r(x["profit_factor"], 2),
                    "score_eur_per_month": r(x["score_eur_per_month"], 0),
                }
                for x in g["ranking"]
            ],
            "not_eligible": {x["contender"]: x["reasons"] for x in g["not_eligible"]},
            "buy_and_hold": {
                "total_return_pct": pct(g["buy_and_hold_reference"]["total_return"], 0),
                "sharpe": r(g["buy_and_hold_reference"]["sharpe"], 2),
                "max_drawdown_pct": pct(g["buy_and_hold_reference"]["max_drawdown"], 0),
                "end_value_per_1000_eur": eur_end(g["buy_and_hold_reference"]["total_return"]),
            },
            "contenders": {},
        }
        for cid, c in res["contenders"].items():
            ai = c["ai_era"]
            blk = stat_block(ai)
            blk["end_value_per_1000_eur"] = eur_end(ai.get("total_return"))
            vd = c.get("verdict") or {}
            blk["eligible"] = vd.get("eligible", False)
            blk["not_eligible_reasons"] = vd.get("reasons", [])
            blk["score_eur_per_month"] = r(vd.get("score_eur_per_month"), 0)
            ctx = {}
            for cname, cs in c.get("contexts", {}).items():
                ctx[cname] = stat_block(cs)
            blk["contexts"] = ctx
            pt = ai.get("per_ticker")
            if pt:
                blk["per_ticker"] = {
                    t: {
                        "trades": v["trades"],
                        "trades_per_month": r(v["trades_per_month"], 2),
                        "hit_rate_pct": pct(v["hit_rate"]),
                        "expectancy_eur": r(v["expectancy_eur"], 2),
                        "profit_factor": r(v["profit_factor"], 2),
                        "median_hold_days": r(v.get("median_hold_days"), 1),
                        "top5_profit_share_pct": pct(v.get("top5_profit_share")),
                        "total_return_pct": pct(v["total_return"], 0),
                        "end_value_per_1000_eur": eur_end(v["total_return"]),
                        "sharpe": r(v["sharpe"], 2),
                        "max_drawdown_pct": pct(v["max_drawdown"], 0),
                        "total_return_cost_2x_pct": pct(v.get("total_return_cost_2x"), 0),
                        "first_bar": v.get("first_bar"),
                    }
                    for t, v in pt.items()
                }
            entry["contenders"][cid] = blk
        out["groups"][gid] = entry

    out["rules"] = {
        cid: {"name": W_NAMES[cid], "k": c["k"], "freeze_file": c["freeze_file"], "freeze_sha256": c["freeze_sha256"],
              "params": c["params"], "rules_en": c["rules"], "perturbed_thresholds_pm20": c["perturbed_thresholds"]}
        for cid, c in reg["contenders"].items()
    }
    out["rule_interpretations_en"] = reg["interpretations"]
    out["eligibility_registered"] = reg["works_often_rule"]
    out["windows"] = reg["windows"]

    # pooled stats shortcut
    pooled = out["groups"]["stocks_all"]
    out["pooled_rule_stats"] = {
        cid: {"name": W_NAMES[cid], **{k: v for k, v in b.items() if k not in ("per_ticker",)}}
        for cid, b in pooled["contenders"].items()
    }

    # consistency: eligible in how many of 8 groups (all except stocks_all)
    eight = [g for g in GROUP_NAMES if g != "stocks_all"]
    for cid in W_NAMES:
        if cid == "B0_BUYHOLD":
            continue
        elig = [g for g in eight if out["groups"][g]["contenders"][cid]["eligible"]]
        pos = [g for g in eight if (out["groups"][g]["contenders"][cid].get("expectancy_eur") or 0) > 0]
        out["consistency_across_groups"][cid] = {
            "name": W_NAMES[cid],
            "eligible_in": len(elig),
            "of": len(eight),
            "eligible_groups": elig,
            "positive_expectancy_in": len(pos),
            "positive_expectancy_groups": pos,
        }

    # pooled contexts (2016-2020, 2021-2022) next to AI era
    for cid in W_NAMES:
        if cid == "B0_BUYHOLD":
            continue
        b = pooled["contenders"][cid]
        c = b.get("contexts", {})
        out["contexts_pooled"][cid] = {
            "name": W_NAMES[cid],
            "y2016_2020": {k: c.get("y2016_2020", {}).get(k) for k in
                           ("trades", "expectancy_eur", "profit_factor", "total_return_pct", "hit_rate_pct")},
            "y2021_2022": {k: c.get("y2021_2022", {}).get(k) for k in
                           ("trades", "expectancy_eur", "profit_factor", "total_return_pct", "hit_rate_pct")},
            "ai_era": {k: b.get(k) for k in
                       ("trades", "expectancy_eur", "profit_factor", "total_return_pct", "hit_rate_pct")},
            "context_2021_2022_expectancy_nonpositive": (c.get("y2021_2022", {}).get("expectancy_eur") or 0) <= 0.5,
        }
    # 2021-2022 buy&hold pooled context
    out["contexts_pooled"]["B0_BUYHOLD"] = {
        "name": W_NAMES["B0_BUYHOLD"],
        "y2016_2020_total_return_pct": pooled["contenders"]["B0_BUYHOLD"]["contexts"].get("y2016_2020", {}).get("total_return_pct"),
        "y2021_2022_total_return_pct": pooled["contenders"]["B0_BUYHOLD"]["contexts"].get("y2021_2022", {}).get("total_return_pct"),
        "ai_era_total_return_pct": pooled["contenders"]["B0_BUYHOLD"].get("total_return_pct"),
    }

    # concentration (audit) and by-group top5 share
    for cid, c in audit["trade_concentration"].items():
        out["concentration_pooled"][cid] = {
            "name": W_NAMES[cid],
            "trades": c["trades"],
            "median_trade_return_pct": pct(c["median_return"]),
            "mean_trade_return_pct": pct(c["mean_return"]),
            "best10_share_of_profit_pct": pct(c["best10_share_of_profit"], 0),
            "mean_without_best10_pct": pct(c["mean_without_best10"]),
            "largest_trade_return_pct": pct(c["largest_return"], 0),
        }
    for cid in ("W5_SR_BREAKOUT_RETEST", "W6_MM_SWEEP_SHIFT", "W7_MM_DEMAND_RETEST", "W1_C13C_ORIG", "W3_MOM_RANK_WEEKLY"):
        out["concentration_by_group_top5_share_pct"][cid] = {
            g: out["groups"][g]["contenders"][cid].get("top5_profit_share_pct") for g in GROUP_NAMES
        }

    # robustness +-20% (top 3)
    for cid, rb in summ["robustness_top3"]["results"].items():
        out["robustness_pm20"][cid] = {
            "name": W_NAMES[cid],
            "base_expectancy_eur": r(rb["base_expectancy_eur"], 1),
            "base_trades": rb["base_trades"],
            "fragile": rb["fragile"],
            "worst_expectancy_cost_2x_eur": r(rb["min_expectancy_eur_cost_2x"], 1),
            "variants": [
                {"param": v["param"], "factor": v["factor"], "value": v["value"], "trades": v["trades"],
                 "expectancy_eur": r(v["expectancy_eur"], 1), "expectancy_eur_cost_2x": r(v["expectancy_eur_cost_2x"], 1),
                 "profit_factor": r(v["profit_factor"], 2)}
                for v in rb["variants"]
            ],
        }
    out["robustness_pm20_note"] = summ["robustness_top3"]["selection_rule"]

    out["lookahead"] = {
        cid: {"ok": v["ok"], "array_checks": v["array_checks"], "trade_checks": v["trade_checks"], "failures": len(v["failures"])}
        for cid, v in summ["lookahead"].items()
    }

    # deflated Sharpe: pooled per contender and best
    out["deflated_sharpe_pooled"] = {cid: b.get("deflated_sharpe_prob") for cid, b in pooled["contenders"].items()}
    out["deflated_sharpe_max_rule"] = max(
        ((cid, v) for cid, v in out["deflated_sharpe_pooled"].items() if v is not None and cid != "B0_BUYHOLD"),
        key=lambda t: t[1],
    )

    # audit
    ch = audit["provenance"]["code_hashes"]
    out["audit"] = {
        "date": audit["date"],
        "independent_program_checks": aind["checks"],
        "independent_program_all_match": aind["all_match"],
        "independent_checks_by_kind": {k: sum(1 for x in aind["rows"] if x["kind"] == k) for k in {x["kind"] for x in aind["rows"]}},
        "ranking_rule_groups_checked": audit["ranking_rule"]["groups_checked"],
        "ranking_rule_groups_wrong": len(audit["ranking_rule"]["groups_wrong"]),
        "frozen_equal_registry_all": audit["provenance"]["all_frozen_equal"],
        "swing_py_hash_registered": ch["lab/aichain/swing.py"]["registered"][:10],
        "swing_py_hash_now": ch["lab/aichain/swing.py"]["now"][:10],
        "swing_py_hash_same": ch["lab/aichain/swing.py"]["same"],
        "swing_run_py_hash_same": ch["lab/aichain/swing_run.py"]["same"],
        "crypto_bad_tick_repairs": audit["crypto_repair"]["repairs_per_crypto_ticker"],
        "crypto_repair_changes_contenders": audit["crypto_repair"]["contenders_changed"],
        "crypto_W8_with_repair": audit["crypto_repair"]["repaired"]["W8_IBS_REVERT"],
        "crypto_W8_without_repair": audit["crypto_repair"]["raw"]["W8_IBS_REVERT"],
        "bad_tick_repairs_all": summ["data_handling"]["bad_tick_repairs"],
        "findings_hr": [
            "Prosjek nose rijetki veliki poslovi: medijan W5 posla je −2,5 %, 10 najboljih poslova drži 50 % dobiti.",
            "W6 i W7 su podobni samo formalno: bez 10 najboljih poslova W6 ima +0,18 % po poslu, W7 −0,41 %.",
            "Hash koda swing.py zapisan pri registraciji (5d43a06ba8) nije jednak hashu koda koji je pokrenuo rezultate (ddef6f8a46); parametri i tekst pravila jednaki su registru, neovisni program daje iste brojeve, ali što je točno promijenjeno ne može se dokazati (nema git povijesti).",
            "Pravilo za loše tickove je pisano za dionice; u kriptu je ograničilo 13 niskih cijena koje su vjerojatno stvarni fitilji (BTC 1, ETH 7, SOL 5). Mijenja se samo W8 u kriptu (očekivanje 1,53 € s popravkom, 1,82 € bez), podobnost se ne mijenja.",
            "Nije nađeno: pogled u budućnost, krivi redoslijed stopa i cilja, nenaplaćen trošak, razlika u formulama, rezultati koji se ne slažu sa sirovim cijenama.",
        ],
    }

    # placebo
    plc = jl(SW / "placebo.json")
    sr = plc["sr"]["all"]
    pb = audit["placebo_block_bootstrap"]["diffs"]

    def rate(x):
        return {k: pct(x[k]) for k in ("touch_rate", "bounce_rate", "break_rate")}

    out["placebo"]["levels"] = {
        "n_levels": sr["n_levels"],
        "n_months": sr["n_months"],
        "n_papers": len(plc["universe"]["used"]),
        "skipped": plc["universe"]["skipped"],
        "real_pct": rate(sr["real"]),
        "controls_pct": {"random_price": rate(sr["rand"]), "shift_pm3pct": rate(sr["shift"]), "pair_around": rate(sr["match"])},
        "n_controls": {"random_price": sr["rand"]["n"], "shift_pm3pct": sr["shift"]["n"], "pair_around": sr["match"]["n"]},
        "diff_pp_with_ci95": {
            ctl: {m: {"diff_pp": pct(sr[key][m]["diff"]), "ci95_pp": [pct(sr[key][m]["ci95"][0]), pct(sr[key][m]["ci95"][1])]}
                  for m in ("touch_rate", "bounce_rate", "break_rate")}
            for ctl, key in (("random_price", "diff_vs_rand"), ("shift_pm3pct", "diff_vs_shift"), ("pair_around", "diff_vs_match"))
        },
        "block3_ci95_pp_vs_random": {m: [pct(pb["rand"][m]["block_3"][0]), pct(pb["rand"][m]["block_3"][1])]
                                     for m in ("touch_rate", "bounce_rate", "break_rate")},
        "config": plc["config"],
        "by_group_bounce_real_vs_random_pct": {
            g: {"n_levels": v["n_levels"], "real": pct(v["real"]["bounce_rate"]), "random": pct(v["rand"]["bounce_rate"])}
            for g, v in plc["sr"]["by_group"].items()
        },
        "by_strength_bounce_real_pct": {k: pct(v["real"]["bounce_rate"]) for k, v in plc["sr"]["by_strength"].items()},
        "by_touches_bounce_real_vs_random_pct": {k: {"real": pct(v["real"]["bounce_rate"]), "random": pct(v["rand"]["bounce_rate"]), "n": v["n_levels"]}
                                                 for k, v in plc["sr"]["by_touches"].items()},
        "verdict_hr": "Potvrđena razina odbija cijenu ništa češće od lažne crte; svi intervali obuhvaćaju nulu. Dodir je čak malo rjeđi nego kod nasumičnih crta.",
    }
    ev_out = {}
    for blockname, key in (("ai_era", "mechanics_ai_era"), ("pre_ai_2017_2022", "mechanics_pre_ai_context")):
        ev_out[blockname] = {"period": plc[key]["period"], "all_days_mean_pct": {h: pct(v["mean"]) for h, v in plc[key]["all_days"].items()}, "events": {}}
        for eid, e in plc[key]["events"].items():
            row = {"label": e["label"], "n": e["n"], "by_horizon": {}}
            for h, v in e["by_h"].items():
                row["by_horizon"][h] = {
                    "mean_pct": pct(v["mean"]),
                    "excess_vs_ticker_avg_pp": pct(v["mean_excess_vs_ticker_avg"]),
                    "excess_ci95_pp": [pct(v["excess_ci95"][0]), pct(v["excess_ci95"][1])],
                    "hit_rate_pct": pct(v["hit_rate"]),
                }
            if blockname == "ai_era":
                ab = audit["event_block_bootstrap"].get(eid)
                if ab:
                    row["block3_ci95_excess_pp"] = {h: [pct(ab[h]["ci95_block_3"][0]), pct(ab[h]["ci95_block_3"][1])] for h in ab}
            ev_out[blockname]["events"][eid] = row
    out["placebo"]["mechanics"] = ev_out
    out["placebo"]["mechanics_verdict_hr"] = (
        "E1, E2, E3 i E5 ne pokazuju prednost (E2 i E3 su statistički lošiji od prosjeka). E4 (prvi povratak u svježu zonu potražnje) je jedini "
        "granični slučaj: +1,8 pp na 10 dana (interval od +0,1 do +3,5 pp), uz blokove od 3 mjeseca interval obuhvaća nulu (−0,1 do +4,0), "
        "nestaje na 20 dana, a 2017.–2022. ima suprotan predznak. Testirano je 15 kombinacija po razdoblju za događaje i 9 za razine."
    )
    return out


# --------------------------------------------------------------------------------------
# AI-chain tournament (earlier, K=533)
# --------------------------------------------------------------------------------------
# Evidence ratings of the segment winner and of C13C, copied from docs/research/AICHAIN_RESULT.md
# (section 6 table and section 7 table); they are Markdown-only values.
TOURNAMENT_RATING_WINNER = {"memory": "zeleno", "mem_interface_storage": "žuto", "equipment": "zeleno",
                            "ai_chips_logic": "zeleno", "network_servers": "žuto", "cloud": "žuto"}
TOURNAMENT_RATING_C13C = {"memory": "zeleno", "mem_interface_storage": "zeleno", "equipment": "zeleno",
                          "ai_chips_logic": "zeleno", "network_servers": "zeleno", "cloud": "žuto"}


def build_tournament() -> dict:
    s = jl(AIC / "summary.json")
    s_tickers = {g: jl(SW / "summary.json")["groups"][g]["tickers"] for g in SEGMENTS}
    ov = jl(AIC / "overview_facts.json")
    out = {
        "meta": {
            "window_ai_era": [s["ai_era_start"], s["common_end"]],
            "cost_bps_per_side": s["cost_bps_per_side"],
            "ledger_k_after_registration": s["ledger_k_after_registration"],
            "note_hr": "Raniji turnir (9 suparnika, K=533). Revidirani simulator nakon neovisne revizije. Mjerilo i troškovi isti kao u swing testu, ali K je 533, ne 542, pa se deflated Sharpe vrijednosti ne smiju miješati.",
            "contenders": K_NAMES,
        },
        "segments": {},
        "per_ticker": {},
        "c13c_ticker_counts": {},
        "contender_beats_hold_counts_by_segment": {},
    }
    for seg in SEGMENTS:
        sg = s["segment_x_contender_ai_era"][seg]
        hold = sg["B0_BUYHOLD"]
        # fixed rule from the tournament: best Sharpe among rules (no hold) with >= 20 trades and
        # positive return at cost 2x; K6 in memory has 17 trades and is excluded.
        elig = {c: v for c, v in sg.items() if c != "B0_BUYHOLD" and v["trades"] >= 20 and v["total_return_cost_2x"] > 0}
        win = max(elig, key=lambda c: elig[c]["sharpe"])
        w = sg[win]
        k1 = sg["K1_C13C_ORIG"]
        entry = {
            "name": GROUP_NAMES[seg],
            "tickers_used": s_tickers[seg],
            "winner": win,
            "winner_name": K_NAMES[win],
            "winner_rule": "highest AI-era Sharpe among rules (hold excluded) with >= 20 trades and positive return at cost 2x",
            "beats_hold_on_return": w["total_return"] > hold["total_return"],
            "beats_hold_on_sharpe": w["sharpe"] > hold["sharpe"],
            "smaller_drawdown_than_hold": abs(w["max_drawdown"]) < abs(hold["max_drawdown"]),
            "winner_vs_hold": {
                "winner_total_return_pct": pct(w["total_return"], 0), "hold_total_return_pct": pct(hold["total_return"], 0),
                "winner_sharpe": r(w["sharpe"], 2), "hold_sharpe": r(hold["sharpe"], 2),
                "winner_max_drawdown_pct": pct(w["max_drawdown"], 0), "hold_max_drawdown_pct": pct(hold["max_drawdown"], 0),
                "per_1000_eur_end_winner": eur_end(w["total_return"]), "per_1000_eur_end_hold": eur_end(hold["total_return"]),
                "per_1000_eur_end_c13c": eur_end(k1["total_return"]),
                "worst_loss_per_1000_eur_winner": round(1000 * abs(w["max_drawdown"])),
                "worst_loss_per_1000_eur_hold": round(1000 * abs(hold["max_drawdown"])),
            },
            "not_eligible": {c: f"{v['trades']} trades (<20)" if v["trades"] < 20 else "return at cost 2x not positive"
                             for c, v in sg.items() if c != "B0_BUYHOLD" and c not in elig},
            "published_winner_matches": ov["winners"][seg]["id"] == win,
            "ratings_by_contender": {"winner": TOURNAMENT_RATING_WINNER[seg], "K1_C13C_ORIG": TOURNAMENT_RATING_C13C[seg]},
            "contenders": {},
        }
        for cid, v in sg.items():
            entry["contenders"][cid] = {
                "name": K_NAMES[cid],
                "total_return_pct": pct(v["total_return"], 0),
                "sharpe": r(v["sharpe"], 2),
                "max_drawdown_pct": pct(v["max_drawdown"], 0),
                "trades": v["trades"],
                "hit_rate_pct": pct(v["hit_rate"]),
                "exposure_pct": r(v["exposure_pct"], 0),
                "end_value_per_1000_eur": eur_end(v["total_return"]),
                "total_return_cost_2x_pct": pct(v["total_return_cost_2x"], 0),
                "excess_vs_hold_pp": pct(v.get("excess_vs_buyhold"), 0),
                "deflated_sharpe_prob": r(v["deflated_sharpe_prob"], 2),
                "psr": r(v["psr"], 3),
            }
        out["segments"][seg] = entry

    # per-ticker K1 vs hold vs the others
    beats_ret = beats_sh = smaller_dd = n = 0
    for t, row in s["ticker_x_contender_ai_era"].items():
        b0, k1 = row["B0_BUYHOLD"], row["K1_C13C_ORIG"]
        n += 1
        beats_ret += k1["total_return"] > b0["total_return"]
        beats_sh += k1["sharpe"] > b0["sharpe"]
        smaller_dd += abs(k1["max_drawdown"]) < abs(b0["max_drawdown"])
        out["per_ticker"][t] = {
            cid: {
                "total_return_pct": pct(v["total_return"], 0),
                "sharpe": r(v["sharpe"], 2),
                "max_drawdown_pct": pct(v["max_drawdown"], 0),
                "trades": v["trades"],
                "end_value_per_1000_eur": eur_end(v["total_return"]),
            }
            for cid, v in row.items()
        }
    out["c13c_ticker_counts"] = {
        "n_tickers": n, "beats_hold_on_return": int(beats_ret), "beats_hold_on_sharpe": int(beats_sh),
        "smaller_drawdown_than_hold": int(smaller_dd),
        "published_in_overview_facts": ov["c13c_tickers"],
    }
    # beats-hold counts per contender (segment level)
    for cid in K_NAMES:
        if cid == "B0_BUYHOLD":
            continue
        br = bs = sd = 0
        valid = 0
        for seg in SEGMENTS:
            c = s["segment_x_contender_ai_era"][seg].get(cid)
            b = s["segment_x_contender_ai_era"][seg]["B0_BUYHOLD"]
            if c is None:
                continue
            valid += 1
            br += c["total_return"] > b["total_return"]
            bs += c["sharpe"] > b["sharpe"]
            sd += abs(c["max_drawdown"]) < abs(b["max_drawdown"])
        out["contender_beats_hold_counts_by_segment"][cid] = {
            "name": K_NAMES[cid], "segments": valid, "return_above_hold": int(br), "sharpe_above_hold": int(bs), "smaller_drawdown": int(sd)}
    out["winners_published"] = ov["winners"]
    out["overall_published"] = ov["overall"]
    out["robustness_pm20"] = {
        cid: {k: (r(v, 3) if isinstance(v, float) else v) for k, v in rb.items() if k != "variants"}
        for cid, rb in s["robustness_pm20"].items()
    }
    return out


# --------------------------------------------------------------------------------------
# TOP10
# --------------------------------------------------------------------------------------
def build_top10() -> dict:
    out = {
        "meta": {
            "date": "2026-10-14",
            "engine": "lab/top10/",
            "costs_bps_per_side": {"stocks_etf": 5, "crypto": 20, "forex": 2},
            "splits": "equity: IS 2016-2020 / WF 2021-2023 / HO 2024+; AI era (from 2023-01) carries the rating",
            "ai_era_end_note": "data ends 2026-10-08 (TOP10) - not the same end date as tournament/swing (2026-10-05)",
            "rating_note_hr": "Blaga ocjena (ZELENO/ŽUTO/CRVENO): pad i koncentracija ne spuštaju ocjenu. Nije Critic PASS.",
            "benchmark_note_hr": "'Kupi i drži' u TOP10 je jednako podijeljeni ulog u SVE simbole strategije, ne nužno isti skup koji strategija trguje (kritičar to navodi kod N1).",
            "ledger_k_range": "508-517",
        },
        "strategies": {},
    }
    order = ["TOP_N1_SEMI_LEADLAG", "TOP_N2_AI_CAPEX_BREADTH", "TOP_N3_GOLD_USD_REGIME", "TOP_N4_BTC_VOL_COMPRESSION",
             "TOP_N5_CRYPTO_HOURLY_TREND", "TOP_C1_TSMOM_MULTI", "TOP_C2_DONCHIAN_TURTLE", "TOP_C3_IBS_REVERT",
             "TOP_C4_GOLD_SILVER_RATIO", "TOP_C5_ORB_5M"]
    urls = jl(TOP / "artifact_urls.json")
    for sid in order:
        d = jl(TOP / sid / "results.json")
        n = jl(TOP / sid / "narrative.json")
        e = d["eras"]
        ai, bai, pre, bpre = e["ai_era"], e["benchmark_ai_era"], e["pre_ai"], e["benchmark_pre_ai"]
        out["strategies"][sid] = {
            "short_id": sid.replace("TOP_", ""),
            "title_hr": n.get("naslov"),
            "subtitle_hr": n.get("podnaslov"),
            "universe": d["universe"],
            "k": d["k"],
            "rating": d["rating"],
            "flags": d["flags"],
            "hypothesis": d.get("hypothesis"),
            "rules": d.get("rules"),
            "params": d.get("params"),
            "ai_era": {"total_return_pct": pct(ai["total"], 0), "end_value_per_1000_eur": eur_end(ai["total"]),
                       "sharpe": r(ai["sharpe"], 2), "max_drawdown_pct": pct(ai["maxdd"], 0), "cagr_pct": pct(ai["cagr"], 0), "days": ai["days"]},
            "ai_era_benchmark": {"total_return_pct": pct(bai["total"], 0), "end_value_per_1000_eur": eur_end(bai["total"]),
                                 "sharpe": r(bai["sharpe"], 2), "max_drawdown_pct": pct(bai["maxdd"], 0)},
            "pre_ai": {"total_return_pct": pct(pre["total"], 0), "sharpe": r(pre["sharpe"], 2)},
            "pre_ai_benchmark": {"total_return_pct": pct(bpre["total"], 0), "sharpe": r(bpre["sharpe"], 2)},
            "splits_total_return_pct": {k: pct(v["total"], 0) for k, v in d["splits"].items()},
            "benchmark_splits_total_return_pct": {k: pct(v["total"], 0) for k, v in d["benchmark_splits"].items()},
            "trades": d["trades"]["n"],
            "win_rate_pct": pct(d["trades"]["win_rate"], 0),
            "median_trade_pct": pct(d["trades"]["median"]),
            "best_trade_pct": pct(d["trades"]["best"], 0),
            "exposure_pct": pct(d["exposure"], 0),
            "cost_stress_wf_ho_total_pct": {k: pct(v["wf_ho_total"], 0) for k, v in d["cost_stress"].items()},
            "sensitivity_pm20_wf_ho_sharpe": {k: r(v, 2) for k, v in d["sensitivity"].items()},
            "pbo_pct": pct(d["pbo"], 0),
            "deflated_sharpe_prob_pct": pct(d["deflated_sharpe_prob"], 0),
            "psr_ai_era": r(d["psr_ai_era"], 3),
            "beats_hold_on_return_ai_era": ai["total"] > bai["total"],
            "yearly_pct": {y: {"strategy": pct(v["strategy"], 0), "benchmark": pct(v["benchmark"], 0)} for y, v in d["yearly"].items()},
            "verdict_hr": n.get("verdikt"),
            "artifact_url": urls.get(sid),
            "freeze_file": d.get("freeze_file"),
            "pine_file": f"scripts/tradingview/{sid}.pine",
        }
    return out


# --------------------------------------------------------------------------------------
# Crypto day trading (JSON numbers + hand honest verdict)
# --------------------------------------------------------------------------------------
def build_cdt() -> dict:
    ids = ["CDT_H1_TREND_4H", "CDT_H1B_TREND_4H_NOVOL", "CDT_H2_TREND_4H_CROWD", "CDT_H2Q_TREND_4H_CROWD_QTL",
           "CDT_H3_UTC2123_COND", "CDT_H4_ID_MOM_VOL", "CDT_H5_BTC_LEAD_5M"]
    out = {
        "meta": {
            "source_doc": "docs/research/CRYPTO_DAYTRADING_RESULT.md",
            "costs_bps_per_side": 10,
            "splits": "crypto IS 2021-22 / WF 2023-24 / HO 2025+",
            "data": "Binance USDT spot bars (IBKR availability for the researcher, HR/MiCA: nepotvrđeno)",
            "ai_era_window": "2023-01-01 to 2026-10-09",
        },
        "ids": {},
        "doc_table": [
            {"id": "CDT_H1_TREND_4H", "idea": "4h Donchian 20/40/80, vol-skaliran", "WF_pct": 149.3, "HO_pct": 12.6, "trades_is_wf_ho": "125 / 108 / 114", "gross_bps_per_trade": 340, "outcome": "zadovoljava kriterije; formalni Critic FAIL"},
            {"id": "CDT_H1B_TREND_4H_NOVOL", "idea": "isto bez vol skaliranja", "WF_pct": 232.7, "HO_pct": 0.7, "trades_is_wf_ho": "125 / 108 / 114", "gross_bps_per_trade": 340, "outcome": "HO tanak, pri 2x trošku HO −6,3 %"},
            {"id": "CDT_H2_TREND_4H_CROWD", "idea": "H1 + funding/OI filter", "WF_pct": 161.1, "HO_pct": 14.8, "trades_is_wf_ho": "126 / 127 / 137", "gross_bps_per_trade": 304, "outcome": "nevaljan kao replikacija (pogrešno implementiran percentil), zamijenjen s H2Q"},
            {"id": "CDT_H2Q_TREND_4H_CROWD_QTL", "idea": "isto, pravilo doslovno kao registrirano", "WF_pct": 153.2, "HO_pct": 14.7, "trades_is_wf_ho": "136 / 179 / 166", "gross_bps_per_trade": 228, "outcome": "zadovoljava kriterije; filter djeluje na 1-2 % barova"},
            {"id": "CDT_H3_UTC2123_COND", "idea": "uvjetni prozor 21-23 UTC", "WF_pct": -0.8, "HO_pct": -1.1, "trades_is_wf_ho": "129 / 105 / 15", "gross_bps_per_trade": 15.6, "outcome": "pada"},
            {"id": "CDT_H4_ID_MOM_VOL", "idea": "intraday momentum + volumen", "WF_pct": -4.4, "HO_pct": -11.9, "trades_is_wf_ho": "144 / 283 / 186", "gross_bps_per_trade": 9.4, "outcome": "pada"},
            {"id": "CDT_H5_BTC_LEAD_5M", "idea": "lead-lag BTC → ETH/SOL na 5m", "WF_pct": -44.7, "HO_pct": -33.1, "trades_is_wf_ho": "772 / 638 / 478", "gross_bps_per_trade": 2.3, "outcome": "pada, 2x trošak −88 %"},
        ],
        "h1_ai_era_vs_buy_hold": {
            "source": "docs/research/CRYPTO_DAYTRADING_RESULT.md (adversarial review corrected buy-and-hold)",
            "h1": {"total_pct": 180.7, "cagr_pct": 31.5, "max_drawdown_pct": -21.9, "calmar": 1.44},
            "buy_hold_btc_eth_sol": {"total_pct": 497.6, "cagr_pct": 60.7, "max_drawdown_pct": -70.4, "calmar": 0.86},
            "euro_example": "1.000 € od 2023-01-01: H1 oko 2.807 €, kupi-i-drži oko 5.976 € (uz pad od 70 %)",
            "holdout_2025_plus": {"h1_pct": 12.6, "buy_hold_pct": -26.8},
            "cost_stress_wf_ho_total_pct": {"1x": 180.7, "1.5x": 162.4, "2x": 145.3, "3x": 114.4},
            "pm20_neighbours_positive": "12 od 12",
            "invested_share_wf_ho_pct": 35,
            "trades_win_rate_pct": 31,
            "median_hold_days": 5,
            "psr_ai_era": 0.99, "deflated_sharpe": 0.33, "k_at_run": 518, "pbo": 0.27,
        },
        "critic_h1": {
            "source": "reports/gate/2026-10-14_CDT_H1_TREND_4H_VERDICT.md (as quoted in CRYPTO_DAYTRADING_RESULT.md)",
            "verdict": "FAIL",
            "failed_checks": "10 (Deflated Sharpe p = 0,9975, PBO 0,70), 11 (Monte Carlo pad), 13 (holdout: 0,04 % po trgovini, bez 3 najbolje −0,96 %), 14",
            "passed": "0-9 i 12",
        },
        "honest_verdict_hr": [
            "Intraday day trading (1 min do 1 h), long-only, koji zarađuje nakon troškova u AI eri: NIJE pronađen. Sve tri intraday hipoteze (H3, H4, H5) padaju; bruto zarada po poslu (15,6 / 9,4 / 2,3 bps) je ispod praga isplativosti od 20 bps.",
            "Preživio je spori trend (4h Donchian, držanje danima, medijan 5 dana), ne day trading. U AI eri zarađuje manje od kupi-i-drži (+181 % naspram +498 %), ali uz oko trećinu pada (−22 % naspram −70 %).",
            "Formalni lab Critic za H1 je FAIL. Time je spori trend opis rizika u uzorku, ne dokazan edge. Deflated Sharpe 0,33 do 0,40.",
        ],
        "review_findings_hr": [
            "H2 nije provodio registrirano pravilo (rang umjesto percentila vrijednosti); popravljeno novim ID-om H2Q.",
            "Referenca 'kupi i drži' iz core.py nije bila kupi-i-drži nego koš rebalansiran na svakom baru bez troška; zamijenjena pravom usporedbom.",
            "'Ex-top3' na neponderiranim tradeovima ne prati uloženi kapital; dodan kriterij na doprinosu portfelju.",
            "Bruto bps otvorenih tradeova bio je precijenjen za 10 bps; ispravljeno.",
            "Tolerancija starosti OI snimke dopuštala 20 min umjesto 15 (jedna pojava u 2021.); ispravljeno u H2Q.",
        ],
        "what_survived_hr": "Samo spori trend kao smanjivač vremena u tržištu (H1, H1B, H2Q). Ništa nije dokazan edge.",
        "unresolved_hr": "Jedan bar kašnjenja izvršenja daje H1 WF +133,0 % / HO +8,9 % i H1B HO −3,5 %. Univerzum BTC/ETH/SOL je preživjeli. PBO i DSR ne uzimaju u obzir serijsku ovisnost.",
    }
    for i in ids:
        d = jl(CDT / i / "results.json")
        e = d["eras"]
        out["ids"][i] = {
            "k": d["k"],
            "machine_rating": d["rating"],
            "wf_total_pct": pct(d["splits"]["WF"]["total"]),
            "ho_total_pct": pct(d["splits"]["HO"]["total"]),
            "is_total_pct": pct(d["splits"]["IS"]["total"]),
            "ai_era_total_pct": pct(e["ai_era"]["total"], 1),
            "ai_era_sharpe": r(e["ai_era"]["sharpe"], 2),
            "ai_era_max_dd_pct": pct(e["ai_era"]["maxdd"], 1),
            "benchmark_in_results_json_ai_era_total_pct": pct(e["benchmark_ai_era"]["total"], 1),
            "benchmark_note": "results.json benchmark = per-bar rebalanced basket (known flaw); the doc's corrected buy-and-hold is +497.6 %",
            "cost_stress_wf_ho_total_pct": {k: pct(v["wf_ho_total"], 1) for k, v in d["cost_stress"].items()},
            "trades_n": d["trades"]["n"],
            "exposure_time_pct": pct(d["exposure"], 0),
            "deflated_sharpe_prob_pct": pct(d["deflated_sharpe_prob"], 0),
            "flags": d["flags"],
        }
    return out


# --------------------------------------------------------------------------------------
# State now (map)
# --------------------------------------------------------------------------------------
def build_state_now() -> dict:
    out = {
        "meta": {
            "note_hr": "Stanje je na zadnji datum SVAKOG papira (2026-10-05 do 2026-10-13), ne na današnji dan 2026-10-14. Razine su orijentir za stop i veličinu pozicije, ne signal: placebo test je pokazao da potvrđene razine ne odbijaju cijenu češće od nasumičnih crta. Dostupnost za EU malog ulagača: nepotvrđeno.",
            "groups": {},
        },
        "tickers": {},
    }
    reg = jl(SW / "registration.json")["groups"]
    t2g = {t: g for g, ts in reg.items() for t in ts}
    for f in sorted((SW / "map").glob("*.json")):
        m = jl(f)
        t = m["ticker"]

        def lv(x):
            rel = x["reliability"]
            return {
                "price": r(x["price"], 2),
                "distance_pct": r(x["distance_pct"], 1),
                "distance_atr": r(x["distance_atr"], 1),
                "turning_points": x["turning_points"],
                "last_touch_date": x["last_touch_date"],
                "touches_after_formation": rel["n"],
                "bounced": rel["bounce"],
                "broken": rel["break"],
                "bounce_rate_pct": pct(rel["rate"], 0) if rel.get("rate") is not None else None,
                "enough_touches": rel["enough_touches"],
            }

        sr = m["swing_range"]
        out["tickers"][t] = {
            "group": m.get("group") or t2g.get(t),
            "last_date": m["last_date"],
            "last_close": r(m["last_close"], 2),
            "atr14_pct": r(m["atr14_pct"], 1),
            "weekly_bias": m["weekly"]["bias"],
            "daily_bias": m["daily"]["bias"],
            "weekly_last_bos": m["weekly"]["last_bos"],
            "daily_last_bos": m["daily"]["last_bos"],
            "daily_last_shift": m["daily"]["last_shift"],
            "swing_range": {"low": r(sr["low"], 2), "low_date": sr["low_date"], "high": r(sr["high"], 2), "high_date": sr["high_date"],
                            "mid": r(sr["mid"], 2), "position_pct": r(sr["position_pct"], 0), "zone": sr["zone"]},
            "sma50_distance_pct": r(m["sma50"]["distance_pct"], 1),
            "sma200_distance_pct": r(m["sma200"]["distance_pct"], 1),
            "high_52w": {"price": r(m["high_52w"]["price"], 2), "date": m["high_52w"]["date"], "distance_pct": r(m["high_52w"]["distance_pct"], 1)},
            "low_52w": {"price": r(m["low_52w"]["price"], 2), "date": m["low_52w"]["date"], "distance_pct": r(m["low_52w"]["distance_pct"], 1)},
            "nearest_supports": [lv(x) for x in m["nearest_supports"]],
            "nearest_resistances": [lv(x) for x in m["nearest_resistances"]],
            "fresh_demand_zones": m["fresh_zones"]["demand"],
            "fresh_supply_zones": m["fresh_zones"]["supply"],
            "bar_repairs": m["bar_repairs"],
            "chart_png": f"reports/research/AICHAIN_20261014/swing/map/{t}.png",
        }
    return out


# --------------------------------------------------------------------------------------
# C13C standing (programmatic parts)
# --------------------------------------------------------------------------------------
def build_c13c(swing: dict, tour: dict) -> dict:
    out = {
        "what_it_is_hr": "C13C: kupi kad je zatvaranje iznad prosjeka zadnjih 200 dana i cijena je pala 5 % ili više u 5 dana (kupnja na sljedećem otvaranju); klizni stop 10 % ispod poznatog vrha, nikad se ne spušta. Nema cilja ni vremenskog izlaza.",
        "in_today_tests": {},
        "per_ticker_memory5": {},
        "vs_other_rules_per_group": {},
    }
    # tournament K1 per segment (all six)
    out["in_today_tests"]["tournament_K1_per_segment"] = {
        seg: {
            "c13c": tour["segments"][seg]["contenders"]["K1_C13C_ORIG"],
            "hold": tour["segments"][seg]["contenders"]["B0_BUYHOLD"],
            "winner": tour["segments"][seg]["winner_name"],
            "c13c_rating": tour["segments"][seg]["ratings_by_contender"].get("K1_C13C_ORIG"),
        }
        for seg in SEGMENTS
    }
    # swing W1 per group (AI era)
    out["in_today_tests"]["swing_W1_per_group"] = {
        g: {k: v for k, v in swing["groups"][g]["contenders"]["W1_C13C_ORIG"].items() if k not in ("per_ticker", "contexts")}
        for g in GROUP_NAMES
    }
    out["in_today_tests"]["swing_W1_contexts_pooled"] = swing["contexts_pooled"]["W1_C13C_ORIG"]
    for t in MEM5:
        grp = "memory" if t in ("MU", "WDC", "STX") else "mem_interface_storage"
        w = {}
        for cid in ("W1_C13C_ORIG", "W2_MOM_BREAK_20", "W3_MOM_RANK_WEEKLY", "W5_SR_BREAKOUT_RETEST", "W8_IBS_REVERT"):
            pt = swing["groups"][grp]["contenders"][cid].get("per_ticker", {})
            w[cid] = pt.get(t)
        out["per_ticker_memory5"][t] = {
            "segment": grp,
            "tournament": {cid: tour["per_ticker"][t][cid] for cid in ("B0_BUYHOLD", "K1_C13C_ORIG", "K2_SMA200_TREND", "K4_TSMOM_126", "K5B_SR_BREAKOUT_RETEST", "K7_C13C_PLUS_TREND_REENTRY")},
            "swing": w,
        }
    for g in ("memory", "mem_interface_storage", "stocks_all"):
        out["vs_other_rules_per_group"][g] = {
            cid: {k: swing["groups"][g]["contenders"][cid].get(k) for k in
                  ("trades", "trades_per_month", "hit_rate_pct", "expectancy_eur", "profit_factor", "total_return_pct", "end_value_per_1000_eur", "sharpe", "max_drawdown_pct")}
            for cid in swing["groups"][g]["contenders"]
        }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    swing = build_swing()
    tour = build_tournament()
    top10 = build_top10()
    cdt = build_cdt()
    state = build_state_now()
    c13c = build_c13c(swing, tour)
    facts = {
        "generated_for": "master document 2026-10-14 (the researcher, HR/EUR). Research only; no orders; not advice; approved_list is empty, signal PRIČEKAJ.",
        "swing": swing,
        "tournament": tour,
        "top10": top10,
        "crypto_day_trading": cdt,
        "state_now": state,
        "c13c": c13c,
    }
    # hand-curated sections live in a sibling module to keep this file readable
    from importlib import util
    hp = Path(__file__).with_name("master_facts_hand_20261014.py")
    spec = util.spec_from_file_location("master_facts_hand", hp)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    facts.update(mod.HAND)
    (OUT / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1))
    from importlib import import_module  # noqa: F401
    spec2 = util.spec_from_file_location("master_facts_md", Path(__file__).with_name("master_facts_md_20261014.py"))
    mod2 = util.module_from_spec(spec2)
    spec2.loader.exec_module(mod2)
    (OUT / "FACTS.md").write_text(mod2.render(facts))
    print("wrote", OUT / "facts.json", OUT / "FACTS.md")


if __name__ == "__main__":
    main()
