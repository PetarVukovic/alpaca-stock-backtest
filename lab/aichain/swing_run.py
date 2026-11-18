"""Run the swing-frequency test: register first, then run. Research only; agents never place orders.

    .venv/bin/python -m lab.aichain.swing_run --register   # registration.json + freeze files + ledger rows (no backtest)
    .venv/bin/python -m lab.aichain.swing_run --run        # all results, diagnostics, summary.json, SWING_ENGINE.md

Outputs: reports/research/AICHAIN_20261014/swing/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lab import ledger
from lab.aichain import swing as S
from lab.aichain.run import load_universe
from lab.aichain.sim import (
    AI_ERA_START,
    BASE_BPS,
    COMMON_END,
    START_CAPITAL,
    WINDOWS,
    Bars,
    Cost,
    SleeveResult,
    daily_returns,
    load_bars,
    stats,
    sum_sleeves,
)
from lab.top10.core import deflated_sharpe, psr

logger = logging.getLogger("swing")
ROOT = Path(__file__).resolve().parents[2]
AICHAIN = ROOT / "reports" / "research" / "AICHAIN_20261014"
OUT = AICHAIN / "swing"
RESULTS = OUT / "results"
FREEZE_DATE = "2026-10-14"
SEED = 20261014
MIN_TRADES = 60
MIN_PF = 1.2
COST_MULT = {"1x": 1.0, "2x": 2.0, "3x": 3.0}
CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
METALS = ["GLD", "SLV"]
CRYPTO_BPS = 10.0
SEGMENT_NAMES = {
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja memorije i pohrana",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Oblak i podatkovni centri",
    "crypto": "Kripto (zasebna grupa)",
    "metali_referentno": "Metali (nepotvrđeno / referentno)",
}
ARRAY_CUTS = 12


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peer_groups() -> dict[str, list[str]]:
    """The peer groups: six stock segments, crypto and metals (reference only)."""
    groups = dict(load_universe())
    groups["crypto"] = CRYPTO
    groups["metali_referentno"] = METALS
    return groups


def group_bps(group: str) -> float:
    return CRYPTO_BPS if group == "crypto" else BASE_BPS


def months_of(window: str) -> float:
    start, end = WINDOWS[window]
    return (pd.Timestamp(end) - pd.Timestamp(start)).days / 30.4375


# --------------------------------------------------------------------------------------------------
# registration
# --------------------------------------------------------------------------------------------------
INTERPRETATIONS = [
    "Pivot: low (high) strictly below (above) the 5 bars on each side, usable only 5 bars after it formed.",
    "Trade normalisation: a trade return times 1.000 EUR is the 'expectancy in EUR on 1.000 EUR' (trades do not compound).",
    "W3 decides on Friday close (Sunday close for crypto) and fills at the next open; a week with a holiday Friday has no decision.",
    "W3 ranks inside the peer group (segment, crypto, metals); 'stocks_all' pools the segment sleeves, it does not re-rank.",
    "W4 zone qualification, touch definition and expiry, and W6/W7 completions are written in each contender's rules and are fixed.",
    "W6 half exit is modelled as a real partial sale at the target (half of the units); the rest is trailed under the prior 10-bar low.",
    "ATR14 is the simple mean of the true range over 14 bars.",
    "If stop and target are touched in one bar the stop is assumed first. Time exits fill at the next open.",
    "All tickers use the common end 2026-10-05 (crypto and metals too) so groups are comparable.",
    "Sharpe uses sqrt(252) for every group, including crypto (which trades every calendar day).",
]


def freeze_specs(groups: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for cid, spec in S.CONTENDERS.items():
        params = (
            {k: v for k, v in spec["cls"].DEFAULTS.items()}
            if hasattr(spec["cls"], "DEFAULTS") and spec["cls"].DEFAULTS
            else {}
        )
        specs[cid] = {
            "id": f"SWING_{cid}",
            "label": "benchmark"
            if cid.startswith("B0")
            else "pre-registered contender",
            "rules": spec["rules"],
            "params": params,
            "perturbed_thresholds": spec["perturb"],
            "interpretations": INTERPRETATIONS,
            "groups": groups,
            "windows": WINDOWS,
            "costs": {
                "bps_per_side_stocks_and_metals": BASE_BPS,
                "bps_per_side_crypto": CRYPTO_BPS,
                "stress": [2, 3],
                "tick": 0,
            },
            "execution": "decide at close of day t, fill at open of day t+1, long-only, no leverage, "
            "fractional units, sleeve = one ticker with own capital, USD treated as EUR-equivalent",
            "code_files": ["lab/aichain/swing.py", "lab/aichain/swing_run.py"],
            "status": "research only; not a lab Critic PASS; no tuning",
        }
    return specs


def register() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    groups = peer_groups()
    k_before = ledger.current_k()
    info: dict[str, Any] = {}
    for cid, spec in freeze_specs(groups).items():
        text = json.dumps(spec, indent=2, sort_keys=True, default=str)
        path = ROOT / "strategies" / "frozen" / f"{FREEZE_DATE}_SWING_{cid}.json"
        if path.exists():
            if json.loads(path.read_text()) != json.loads(text):
                raise SystemExit(
                    f"{path.name} differs from the contender spec: use a new ID"
                )
        else:
            path.write_text(text)
        k = ledger.register_strategy(
            f"SWING_{cid}",
            sha(path),
            agent="claude-aichain-swing",
            purpose="swing-frequency test 2026-10-14; not Critic",
            unit="frozen_strategy_id",
        )
        info[cid] = {
            "freeze_file": str(path.relative_to(ROOT)),
            "freeze_sha256": sha(path),
            "k": k,
        }
    reg = {
        "registered_at_before_any_run": True,
        "date": FREEZE_DATE,
        "purpose": "Which pre-registered swing algorithm works AND trades often (AI era 2023-01-01 .. 2026-10-05).",
        "ledger_k_before": k_before,
        "ledger_k_after": ledger.current_k(),
        "contenders": {
            cid: {
                "params": s["params"],
                "rules": s["rules"],
                "perturbed_thresholds": s["perturbed_thresholds"],
                **info[cid],
            }
            for cid, s in freeze_specs(groups).items()
        },
        "groups": groups,
        "windows": WINDOWS,
        "costs": {
            "stocks_metals_bps_per_side": BASE_BPS,
            "crypto_bps_per_side": CRYPTO_BPS,
            "stress_multipliers": [2, 3],
        },
        "works_often_rule": {
            "eligible": f"at least {MIN_TRADES} trades in the AI era over the group; expectancy per trade > 0 at cost 2x; profit factor >= {MIN_PF} (cost 1x)",
            "rank": "among eligible: expectancy per trade (EUR on 1.000 EUR, cost 1x) times trades per month of the group",
            "buy_and_hold": "always shown for reference, never ranked",
        },
        "robustness": {
            "rule": "+-20 percent on every threshold, one at a time, on the pooled stock universe (AI era)",
            "selected": "top 3 contenders (not B0) by expectancy per trade at cost 1x with at least 60 trades on the pooled stock universe",
            "fragile_if": "any variant has expectancy per trade <= 0 at cost 2x or profit factor < 1.0",
        },
        "lookahead": f"array identity on {ARRAY_CUTS} random truncations per ticker for every contender, plus decision/closed-trade identity at one random cut; seed {SEED}",
        "statistics": "PSR and deflated Sharpe on the daily returns of each group (AI era) with the ledger K after registration",
        "interpretations": INTERPRETATIONS,
        "code_sha256_at_registration": {
            "lab/aichain/swing.py": sha(ROOT / "lab/aichain/swing.py"),
            "lab/aichain/swing_run.py": sha(ROOT / "lab/aichain/swing_run.py"),
        },
        "no_tuning": True,
    }
    (OUT / "registration.json").write_text(json.dumps(reg, indent=2, sort_keys=True))
    return reg


# --------------------------------------------------------------------------------------------------
# running
# --------------------------------------------------------------------------------------------------
class Runner:
    """Caches every sleeve run so groups, tickers and diagnostics share the same numbers."""

    def __init__(self, groups: dict[str, list[str]]) -> None:
        self.groups = groups
        self.group_of = {t: g for g, ts in groups.items() for t in ts}
        self.bars: dict[str, Bars] = {t: load_bars(t) for t in self.group_of}
        self.cache: dict[tuple[Any, ...], SleeveResult | None] = {}

    def rule(self, ticker: str, cid: str, overrides: dict[str, Any]) -> Any:
        group = self.group_of[ticker]
        peers = {t: self.bars[t] for t in self.groups[group]}
        ov = dict(overrides)
        if cid == "W3_MOM_RANK_WEEKLY" and group == "crypto":
            ov.setdefault("weekday", 6)
        return S.make_rule(cid, peers=peers, **ov)

    def sleeve(
        self, ticker: str, cid: str, window: str, mult: str, overrides: tuple = ()
    ) -> SleeveResult | None:
        key = (ticker, cid, window, mult, overrides)
        if key not in self.cache:
            start, end = WINDOWS[window]
            cost = Cost(bps=group_bps(self.group_of[ticker]) * COST_MULT[mult])
            self.cache[key] = S.run_swing_sleeve(
                self.bars[ticker],
                self.rule(ticker, cid, dict(overrides)),
                start,
                end,
                cost,
            )
        return self.cache[key]

    def sleeves(
        self,
        tickers: list[str],
        cid: str,
        window: str,
        mult: str,
        overrides: tuple = (),
    ) -> list[SleeveResult]:
        got = [self.sleeve(t, cid, window, mult, overrides) for t in tickers]
        return [g for g in got if g is not None]


def sleeve_years(parts: list[SleeveResult]) -> float:
    return sum(max((p.dates[-1] - p.dates[0]).days, 1) / 365.25 for p in parts)


def all_trades(parts: list[SleeveResult]) -> list[dict[str, Any]]:
    return [t for p in parts for t in p.trades]


def block(
    runner: Runner, tickers: list[str], cid: str, window: str, deep: bool, k: int
) -> dict[str, Any] | None:
    """Group result for one contender and window: trade feel, risk numbers, cost stress, PSR."""
    parts = runner.sleeves(tickers, cid, window, "1x")
    if not parts:
        return None
    cap = START_CAPITAL * len(parts)
    agg = sum_sleeves(parts)
    st = stats(agg, cap)
    months = months_of(window)
    m = S.trade_metrics(all_trades(parts), months, sleeve_years(parts))
    out: dict[str, Any] = {
        **m,
        "sleeves": len(parts),
        "total_return": st["total_return"],
        "sharpe": st["sharpe"],
        "max_drawdown": st["max_drawdown"],
        "exposure_pct": st["exposure_pct"],
        "months": months,
    }
    for mult in ("2x", "3x"):
        p2 = runner.sleeves(tickers, cid, window, mult)
        out[f"total_return_cost_{mult}"] = stats(
            sum_sleeves(p2), START_CAPITAL * len(p2)
        )["total_return"]
        m2 = S.trade_metrics(all_trades(p2), months, sleeve_years(p2))
        out[f"expectancy_eur_cost_{mult}"] = m2["expectancy_eur"]
        out[f"profit_factor_cost_{mult}"] = m2["profit_factor"]
    if deep:
        r = daily_returns(agg, cap)
        out["psr"] = psr(r)
        out["deflated_sharpe_prob"] = deflated_sharpe(r, k)
        out["per_ticker"] = {}
        for t in tickers:
            r1 = runner.sleeve(t, cid, window, "1x")
            if r1 is None:
                out["per_ticker"][t] = None
                continue
            s1 = stats(r1, START_CAPITAL)
            mt = S.trade_metrics(
                r1.trades, months, max((r1.dates[-1] - r1.dates[0]).days, 1) / 365.25
            )
            out["per_ticker"][t] = {
                **mt,
                "total_return": s1["total_return"],
                "sharpe": s1["sharpe"],
                "max_drawdown": s1["max_drawdown"],
                "exposure_pct": s1["exposure_pct"],
                "first_bar": str(r1.dates[0].date()),
                "total_return_cost_2x": stats(
                    runner.sleeve(t, cid, window, "2x"), START_CAPITAL
                )["total_return"],
                "total_return_cost_3x": stats(
                    runner.sleeve(t, cid, window, "3x"), START_CAPITAL
                )["total_return"],
            }
    return out


def verdict(b: dict[str, Any] | None) -> dict[str, Any]:
    """Eligibility for the 'works often' ranking and the score (EUR per month on 1.000 EUR per sleeve)."""
    if b is None or not b["trades"]:
        return {
            "eligible": False,
            "reasons": ["no trades"],
            "score_eur_per_month": None,
        }
    reasons = []
    if b["trades"] < MIN_TRADES:
        reasons.append(f"only {b['trades']} trades (< {MIN_TRADES})")
    e2 = b.get("expectancy_eur_cost_2x")
    if e2 is None or e2 <= 0:
        reasons.append("expectancy <= 0 at cost 2x")
    pf = b.get("profit_factor")
    if pf is None or pf < MIN_PF:
        reasons.append(f"profit factor < {MIN_PF}")
    score = b["expectancy_eur"] * b["trades_per_month"]
    return {"eligible": not reasons, "reasons": reasons, "score_eur_per_month": score}


def rank_table(per_cid: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    rows = []
    for cid in S.SINGLE_IDS:
        b = per_cid[cid]
        v = verdict(b)
        rows.append(
            {
                "contender": cid,
                "trades": b["trades"] if b else 0,
                "trades_per_month": b["trades_per_month"] if b else None,
                "expectancy_eur": b["expectancy_eur"] if b else None,
                "expectancy_eur_cost_2x": b["expectancy_eur_cost_2x"] if b else None,
                "profit_factor": b["profit_factor"] if b else None,
                **v,
            }
        )
    eligible = sorted(
        (r for r in rows if r["eligible"]), key=lambda r: -r["score_eur_per_month"]
    )
    rest = sorted(
        (r for r in rows if not r["eligible"]),
        key=lambda r: (
            -(r["expectancy_eur"] if r["expectancy_eur"] is not None else -1e9)
        ),
    )
    bh = per_cid["B0_BUYHOLD"]
    return {
        "ranking": eligible,
        "not_eligible": rest,
        "buy_and_hold_reference": {
            k: bh.get(k) if bh else None
            for k in (
                "total_return",
                "sharpe",
                "max_drawdown",
                "exposure_pct",
                "total_return_cost_2x",
            )
        },
    }


# --------------------------------------------------------------------------------------------------
# diagnostics
# --------------------------------------------------------------------------------------------------
def _arrays(rule: Any) -> dict[str, np.ndarray]:
    return {
        k: v for k, v in vars(rule).items() if isinstance(v, np.ndarray) and v.ndim == 1
    }


def _tkey(t: dict[str, Any]) -> tuple[Any, ...]:
    return (
        t["entry_date"],
        t["exit_date"],
        round(t["entry_price"], 9),
        round(t["exit_price"], 9),
        t["reason"],
    )


def lookahead(runner: Runner) -> dict[str, Any]:
    """Every signal array must be identical on truncated data; decisions and closed trades too at one cut."""
    rng = np.random.default_rng(SEED)
    rep: dict[str, Any] = {
        cid: {"ok": True, "array_checks": 0, "trade_checks": 0, "failures": []}
        for cid in S.SINGLE_IDS
    }
    for ticker, bars in runner.bars.items():
        n = len(bars)
        cuts = rng.integers(int(n * 0.3), n - 1, ARRAY_CUTS)
        trade_cut = int(rng.integers(int(n * 0.4), int(n * 0.9)))
        for cid in S.SINGLE_IDS:
            full = runner.rule(ticker, cid, {})
            full.prepare(bars)
            fa = _arrays(full)
            for c in cuts:
                pb = bars.cut(bars.dates[int(c)])
                part = runner.rule(ticker, cid, {})
                part.prepare(pb)
                m = len(pb)
                rep[cid]["array_checks"] += 1
                for name, arr in _arrays(part).items():
                    ref = fa.get(name)
                    if ref is None or len(ref) != n:
                        continue
                    if not np.allclose(
                        arr, ref[:m], rtol=1e-12, atol=0, equal_nan=True
                    ):
                        rep[cid]["ok"] = False
                        rep[cid]["failures"].append(
                            {
                                "ticker": ticker,
                                "array": name,
                                "cut": str(bars.dates[int(c)].date()),
                            }
                        )
                        break
            cut_date = bars.dates[trade_cut]
            a = S.run_swing_sleeve(
                bars,
                runner.rule(ticker, cid, {}),
                WINDOWS["full"][0],
                WINDOWS["full"][1],
                Cost(bps=group_bps(runner.group_of[ticker])),
            )
            b = S.run_swing_sleeve(
                bars.cut(cut_date),
                runner.rule(ticker, cid, {}),
                WINDOWS["full"][0],
                WINDOWS["full"][1],
                Cost(bps=group_bps(runner.group_of[ticker])),
            )
            if a is None or b is None:
                continue
            ta = [
                _tkey(t)
                for t in a.trades
                if t["reason"] != "end" and pd.Timestamp(t["exit_date"]) <= cut_date
            ]
            tb = [
                _tkey(t)
                for t in b.trades
                if t["reason"] != "end" and pd.Timestamp(t["exit_date"]) <= cut_date
            ]
            rep[cid]["trade_checks"] += 1
            if ta != tb or b.decisions != a.decisions[: len(b.decisions)]:
                rep[cid]["ok"] = False
                rep[cid]["failures"].append(
                    {"ticker": ticker, "trade_cut": str(cut_date.date())}
                )
    return rep


def robustness(runner: Runner, tickers: list[str], cid: str, k: int) -> dict[str, Any]:
    base = block(runner, tickers, cid, "ai_era", False, k)
    rows = []
    for key, factor, value in S.perturbed(cid):
        ov = ((key, value),)
        parts1 = runner.sleeves(tickers, cid, "ai_era", "1x", ov)
        parts2 = runner.sleeves(tickers, cid, "ai_era", "2x", ov)
        m1 = S.trade_metrics(
            all_trades(parts1), months_of("ai_era"), sleeve_years(parts1)
        )
        m2 = S.trade_metrics(
            all_trades(parts2), months_of("ai_era"), sleeve_years(parts2)
        )
        rows.append(
            {
                "param": key,
                "factor": factor,
                "value": value,
                "trades": m1["trades"],
                "expectancy_eur": m1["expectancy_eur"],
                "expectancy_eur_cost_2x": m2["expectancy_eur"],
                "profit_factor": m1["profit_factor"],
                "total_return": stats(sum_sleeves(parts1), START_CAPITAL * len(parts1))[
                    "total_return"
                ],
            }
        )
    bad = [
        r
        for r in rows
        if r["expectancy_eur_cost_2x"] is None
        or r["expectancy_eur_cost_2x"] <= 0
        or (r["profit_factor"] is not None and r["profit_factor"] < 1.0)
    ]
    return {
        "base_expectancy_eur": base["expectancy_eur"] if base else None,
        "base_trades": base["trades"] if base else None,
        "variants": rows,
        "fragile": bool(bad),
        "fragile_variants": [f"{r['param']} x{r['factor']}" for r in bad],
        "min_expectancy_eur_cost_2x": min(
            (
                r["expectancy_eur_cost_2x"]
                for r in rows
                if r["expectancy_eur_cost_2x"] is not None
            ),
            default=None,
        ),
    }


# --------------------------------------------------------------------------------------------------
# main run
# --------------------------------------------------------------------------------------------------
def run() -> None:
    reg_path = OUT / "registration.json"
    if not reg_path.exists():
        raise SystemExit(
            "registration.json missing: run --register before any backtest"
        )
    reg = json.loads(reg_path.read_text())
    groups = peer_groups()
    stock_tickers = [
        t
        for g, ts in groups.items()
        if g not in ("crypto", "metali_referentno")
        for t in ts
    ]
    k = ledger.current_k()
    runner = Runner(groups)
    RESULTS.mkdir(parents=True, exist_ok=True)
    cids = list(S.CONTENDERS)
    targets: dict[str, list[str]] = {**groups, "stocks_all": stock_tickers}
    summary_tables: dict[str, Any] = {}
    for gname, tickers in targets.items():
        per_cid: dict[str, dict[str, Any] | None] = {}
        contexts: dict[str, dict[str, Any]] = {}
        for cid in cids:
            per_cid[cid] = block(runner, tickers, cid, "ai_era", True, k)
            contexts[cid] = {
                w: block(runner, tickers, cid, w, False, k)
                for w in ("y2016_2020", "y2021_2022")
            }
        table = rank_table(per_cid)
        data = {
            "group": gname,
            "name": SEGMENT_NAMES.get(
                gname,
                "Sve dionice (zbroj segmenata)" if gname == "stocks_all" else gname,
            ),
            "tickers": tickers,
            "cost_bps_per_side": group_bps(gname) if gname in groups else BASE_BPS,
            "window": {"ai_era": WINDOWS["ai_era"], "months": months_of("ai_era")},
            "start_capital_per_sleeve": START_CAPITAL,
            "contenders": {
                cid: {
                    "ai_era": per_cid[cid],
                    "contexts": contexts[cid],
                    "verdict": verdict(per_cid[cid]) if cid != "B0_BUYHOLD" else None,
                }
                for cid in cids
            },
            "ranking": table,
        }
        (RESULTS / f"{gname}.json").write_text(json.dumps(data, separators=(",", ":")))
        summary_tables[gname] = {
            "name": data["name"],
            "tickers": tickers,
            **table,
            "per_contender": {
                cid: {
                    kk: vv
                    for kk, vv in (per_cid[cid] or {}).items()
                    if kk != "per_ticker"
                }
                for cid in cids
            },
        }
        logger.info("group %s done", gname)

    # top 3 by expectancy on the pooled stock universe (rule pre-registered)
    pooled = summary_tables["stocks_all"]["per_contender"]
    cands = [c for c in S.SINGLE_IDS if pooled[c] and pooled[c]["trades"] >= MIN_TRADES]
    top3 = sorted(cands, key=lambda c: -pooled[c]["expectancy_eur"])[:3]
    logger.info("robustness for %s", top3)
    rob = {cid: robustness(runner, stock_tickers, cid, k) for cid in top3}
    look = lookahead(runner)
    summary = {
        "common_end": COMMON_END,
        "ai_era_start": AI_ERA_START,
        "ledger_k": k,
        "cost_note": "stocks and metals 2.5 bps per side, crypto 10 bps per side; stress 2x and 3x",
        "registration_sha256": sha(reg_path),
        "registered": {cid: reg["contenders"][cid]["k"] for cid in cids},
        "groups": summary_tables,
        "robustness_top3": {
            "selected": top3,
            "selection_rule": reg["robustness"]["selected"],
            "results": rob,
        },
        "lookahead": look,
        "data_handling": {
            "first_bar_used": {
                t: str(b.dates[0].date()) for t, b in runner.bars.items()
            },
            "last_bar_used": {
                t: str(b.dates[-1].date()) for t, b in runner.bars.items()
            },
            "bad_tick_repairs": {
                t: b.repairs for t, b in runner.bars.items() if b.repairs
            },
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, separators=(",", ":")))
    from lab.aichain.swing_doc import write_doc

    write_doc(summary, reg)
    logger.info("done; K=%s", k)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.register:
        reg = register()
        logger.info(
            "registered; K %s -> %s", reg["ledger_k_before"], reg["ledger_k_after"]
        )
    if args.run:
        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
