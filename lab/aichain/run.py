"""Run the AI-chain tournament: every ticker and segment x contender x window, plus diagnostics.

    .venv/bin/python -m lab.aichain.run --dry    # compute and write results, no freeze, no ledger
    .venv/bin/python -m lab.aichain.run          # also freeze specs and register the trials (K+1 each)

Research only. Agents never place orders. Outputs: reports/research/AICHAIN_20261014/.
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
from lab.aichain.contenders import CONTENDERS, make_rule, momentum_picker
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
    run_rotation,
    run_sleeve,
    stats,
    sum_sleeves,
)
from lab.top10.core import deflated_sharpe, psr

logger = logging.getLogger("aichain")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "AICHAIN_20261014"
RESULTS = OUT / "results"
COST_MULT = {"1x": 1.0, "2x": 2.0, "3x": 3.0}
SINGLE = [c for c in CONTENDERS if c != "K6_MOMENTUM_CS"]
SEED = 20261014
FREEZE_DATE = "2026-10-14"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_universe() -> dict[str, list[str]]:
    data = json.loads((OUT / "universe.json").read_text())
    return {
        seg: [t["ticker"] for t in v["tickers"] if t["usable"]]
        for seg, v in data["segments"].items()
    }


class Runner:
    """Caches every sleeve run so tickers, segments and diagnostics share the same numbers."""

    def __init__(self, segments: dict[str, list[str]]) -> None:
        self.segments = segments
        self.bars: dict[str, Bars] = {
            t: load_bars(t) for ts in segments.values() for t in ts
        }
        self.cache: dict[tuple[Any, ...], SleeveResult | None] = {}

    def sleeve(
        self, ticker: str, cid: str, window: str, mult: str, overrides: tuple = ()
    ) -> SleeveResult | None:
        key = (ticker, cid, window, mult, overrides)
        if key not in self.cache:
            start, end = WINDOWS[window]
            cost = Cost(bps=BASE_BPS * COST_MULT[mult])
            self.cache[key] = run_sleeve(
                self.bars[ticker], make_rule(cid, **dict(overrides)), start, end, cost
            )
        return self.cache[key]

    def segment(
        self, seg: str, cid: str, window: str, mult: str, overrides: tuple = ()
    ) -> tuple[SleeveResult, float] | None:
        if cid == "K6_MOMENTUM_CS":
            start, end = WINDOWS[window]
            data = {t: self.bars[t] for t in self.segments[seg]}
            kw = dict(overrides)
            picker = momentum_picker(**kw)
            cost = Cost(bps=BASE_BPS * COST_MULT[mult])
            cap = START_CAPITAL * len(data)
            return run_rotation(data, picker, start, end, cost, cap), cap
        parts = [
            self.sleeve(t, cid, window, mult, overrides) for t in self.segments[seg]
        ]
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        return sum_sleeves(parts), START_CAPITAL * len(parts)


def _curve(res: SleeveResult) -> list[list[Any]]:
    return [[str(d.date()), round(float(v), 2)] for d, v in zip(res.dates, res.equity)]


def _entry(get: Any, cid: str, extra_psr: bool) -> dict[str, Any]:
    """Result block for one contender: stats per window, cost stress, curves, trades."""
    out: dict[str, Any] = {"available": True, "windows": {}, "equity": {}, "trades": {}}
    for w in WINDOWS:
        got = get(cid, w, "1x")
        bh = get("B0_BUYHOLD", w, "1x")
        if got is None:
            out["windows"][w] = None
            continue
        res, cap = got
        st = stats(res, cap)
        for mult in ("2x", "3x"):
            g = get(cid, w, mult)
            st[f"total_return_cost_{mult}"] = (
                stats(g[0], g[1])["total_return"] if g else None
            )
        if bh is not None:
            bst = stats(bh[0], bh[1])
            st["buyhold_total_return"] = bst["total_return"]
            st["buyhold_sharpe"] = bst["sharpe"]
            st["excess_vs_buyhold"] = st["total_return"] - bst["total_return"]
        if w == "ai_era" and extra_psr:
            r = daily_returns(res, cap)
            st["psr"] = psr(r)
            st["deflated_sharpe_prob"] = deflated_sharpe(r, ledger.current_k())
        out["windows"][w] = st
        if w in ("full", "ai_era"):
            out["equity"][w] = _curve(res)
            out["trades"][w] = res.trades
    return out


def lookahead_test(runner: Runner) -> dict[str, Any]:
    """Truncate each ticker at a random cut date: earlier decisions and closed trades must not change."""
    rng = np.random.default_rng(SEED)
    report: dict[str, Any] = {
        cid: {"ok": True, "checked": 0, "failures": []} for cid in CONTENDERS
    }
    full_start, end = WINDOWS["full"]
    cost = Cost()

    def key(t: dict[str, Any]) -> tuple[Any, ...]:
        return (
            t["entry_date"],
            t["exit_date"],
            round(t["entry_price"], 9),
            round(t["exit_price"], 9),
            t["reason"],
        )

    for ticker, bars in runner.bars.items():
        n = len(bars)
        cut_i = int(rng.integers(int(n * 0.4), int(n * 0.9)))
        cut_date = bars.dates[cut_i]
        for cid in SINGLE:
            full = run_sleeve(bars, make_rule(cid), full_start, end, cost)
            part = run_sleeve(bars.cut(cut_date), make_rule(cid), full_start, end, cost)
            if full is None or part is None:
                continue
            a = [
                key(t)
                for t in full.trades
                if t["reason"] != "end" and pd.Timestamp(t["exit_date"]) <= cut_date
            ]
            b = [
                key(t)
                for t in part.trades
                if t["reason"] != "end" and pd.Timestamp(t["exit_date"]) <= cut_date
            ]
            same_dec = part.decisions == full.decisions[: len(part.decisions)]
            report[cid]["checked"] += 1
            if a != b or not same_dec:
                report[cid]["ok"] = False
                report[cid]["failures"].append(
                    {"ticker": ticker, "cut": str(cut_date.date())}
                )
    picker = momentum_picker()
    for seg, tickers in runner.segments.items():
        data = {t: runner.bars[t] for t in tickers}
        for _ in range(8):
            ref = data[tickers[0]]
            k = int(rng.integers(int(len(ref) * 0.4), int(len(ref) * 0.9)))
            day = ref.dates[k]
            trimmed = {t: b.cut(day) for t, b in data.items()}
            report["K6_MOMENTUM_CS"]["checked"] += 1
            if picker(day, trimmed) != picker(day, data):
                report["K6_MOMENTUM_CS"]["ok"] = False
                report["K6_MOMENTUM_CS"]["failures"].append(
                    {"segment": seg, "cut": str(day.date())}
                )
    return report


ARRAY_CUTS = 12


def _rule_arrays(rule: Any) -> dict[str, np.ndarray]:
    return {
        k: v
        for k, v in vars(rule).items()
        if isinstance(v, np.ndarray) and v.ndim == 1
    }


def lookahead_arrays_test(runner: Runner) -> dict[str, Any]:
    """Stronger lookahead check: every precomputed signal array must be identical on truncated data.

    The decision/trade comparison above only changes when a one-bar peek happens to flip a decision at the cut.
    Here each rule is prepared on the full bars and on bars truncated at ``ARRAY_CUTS`` random dates; every
    1-D array the rule built (entry/exit flags, levels, indicator copies) must match on the common prefix,
    including the last bar before the cut, whatever the account state was.
    """
    rng = np.random.default_rng(SEED + 1)
    report: dict[str, Any] = {
        cid: {"ok": True, "checked": 0, "failures": []} for cid in SINGLE
    }
    for ticker, bars in runner.bars.items():
        n = len(bars)
        cuts = rng.integers(int(n * 0.3), n - 1, ARRAY_CUTS)
        for cid in SINGLE:
            full_rule = make_rule(cid)
            full_rule.prepare(bars)
            full_arr = _rule_arrays(full_rule)
            for cut_i in cuts:
                part_bars = bars.cut(bars.dates[int(cut_i)])
                part_rule = make_rule(cid)
                part_rule.prepare(part_bars)
                m = len(part_bars)
                report[cid]["checked"] += 1
                for name, arr in _rule_arrays(part_rule).items():
                    ref = full_arr.get(name)
                    if ref is not None and len(ref) != n:
                        continue  # placeholder array the rule does not use (e.g. K1 keeps its flags elsewhere)
                    same = (
                        ref is not None
                        and len(arr) == m
                        and np.allclose(arr, ref[:m], rtol=1e-12, atol=0, equal_nan=True)
                    )
                    if not same:
                        report[cid]["ok"] = False
                        report[cid]["failures"].append(
                            {"ticker": ticker, "array": name, "cut": str(bars.dates[int(cut_i)].date())}
                        )
                        break
    return report


def _perturbed(contender: str) -> list[tuple[str, float, tuple]]:
    """One-at-a-time +/-20 percent variants of the numeric parameters (ints rounded)."""
    if contender == "K6_MOMENTUM_CS":
        base: dict[str, Any] = {"lookback": 126, "skip": 5}
    else:
        base = dict(CONTENDERS[contender]["cls"].DEFAULTS)
    variants = []
    for k, v in base.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        if contender.startswith("K1") and k not in ("sma", "dip", "trail"):
            continue
        for f in (0.8, 1.2):
            nv = max(1, round(v * f)) if isinstance(v, int) else v * f
            variants.append((k, f, ((k, nv),)))
    return variants


def robustness(runner: Runner, contender: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for seg in runner.segments:
        base = runner.segment(seg, contender, "ai_era", "1x")
        bst = stats(*base) if base else None
        rows = []
        for key, factor, ov in _perturbed(contender):
            got = runner.segment(seg, contender, "ai_era", "1x", ov)
            st = stats(*got) if got else None
            rows.append(
                {
                    "param": key,
                    "factor": factor,
                    "value": ov[0][1],
                    "total_return": st["total_return"] if st else None,
                    "sharpe": st["sharpe"] if st else None,
                }
            )
        rets = [r["total_return"] for r in rows if r["total_return"] is not None]
        out[seg] = {
            "base_total_return": bst["total_return"] if bst else None,
            "base_sharpe": bst["sharpe"] if bst else None,
            "variants": rows,
            "min_total_return": min(rets) if rets else None,
            "max_total_return": max(rets) if rets else None,
            "sign_flips": bool(
                bst
                and rets
                and (
                    (min(rets) > 0) != (bst["total_return"] > 0)
                    or (max(rets) > 0) != (bst["total_return"] > 0)
                )
            ),
        }
    return out


def freeze_and_register(dry: bool, segments: dict[str, list[str]]) -> dict[str, Any]:
    """Write strategies/frozen/2026-10-14_AICHAIN_{ID}.json and register one ledger trial per contender."""
    info: dict[str, Any] = {}
    for cid, spec in CONTENDERS.items():
        defaults = (
            {
                "lookback": 126,
                "skip": 5,
                "rebalance": "monthly first open",
                "keep": "better half, ceil",
            }
            if spec["cls"] is None
            else spec["cls"].DEFAULTS
        )
        freeze = {
            "id": f"AICHAIN_{cid}",
            "label": "extension / NEW hypothesis of K1"
            if cid.startswith("K7")
            else ("benchmark" if cid.startswith("B0") else "pre-registered contender"),
            "rules": spec["rules"],
            "params": defaults,
            "segments": segments,
            "windows": WINDOWS,
            "costs": {"bps_per_side": BASE_BPS, "stress": [2, 3], "tick": 0},
            "execution": "decide at close of day t, fill at open of day t+1, long-only, no leverage, "
            "fractional units, sleeve = one ticker with own capital, USD treated as EUR-equivalent",
            "code_files": ["lab/aichain/sim.py", "lab/aichain/contenders.py"],
            "universe_sha256": _sha(OUT / "universe.json"),
            "status": "research only; not a lab Critic PASS; no tuning",
        }
        text = json.dumps(freeze, indent=2, sort_keys=True, default=str)
        existing = sorted(
            (ROOT / "strategies" / "frozen").glob(f"*_AICHAIN_{cid}.json")
        )
        path = (
            existing[0]
            if existing
            else ROOT / "strategies" / "frozen" / f"{FREEZE_DATE}_AICHAIN_{cid}.json"
        )
        if dry:
            info[cid] = {"freeze_file": str(path.relative_to(ROOT)), "k": None}
            continue
        if path.exists():
            if json.loads(path.read_text()) != json.loads(text):
                raise SystemExit(
                    f"{path.name} differs from the contender spec: frozen specs are immutable, use a new ID"
                )
        else:
            path.write_text(text)
        k = ledger.register_strategy(
            f"AICHAIN_{cid}",
            _sha(path),
            agent="claude-aichain",
            purpose="AI-chain tournament 2026-10-14; not Critic",
            unit="frozen_strategy_id",
        )
        info[cid] = {"freeze_file": str(path.relative_to(ROOT)), "k": k}
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry", action="store_true", help="no freeze files, no ledger rows"
    )
    parser.add_argument("--agent", default="claude-aichain")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    segments = load_universe()
    reg = freeze_and_register(args.dry, segments)
    runner = Runner(segments)
    RESULTS.mkdir(parents=True, exist_ok=True)
    k_now = ledger.current_k()

    def seg_getter(seg: str) -> Any:
        return lambda cid, w, mult: runner.segment(seg, cid, w, mult)

    def tick_getter(t: str) -> Any:
        def get(cid: str, w: str, mult: str) -> Any:
            r = runner.sleeve(t, cid, w, mult)
            return (r, START_CAPITAL) if r is not None else None

        return get

    table: dict[str, dict[str, Any]] = {}
    ticker_table: dict[str, dict[str, Any]] = {}
    for seg, tickers in segments.items():
        block = {
            "name": seg,
            "kind": "segment",
            "tickers": tickers,
            "start_capital_per_sleeve": START_CAPITAL,
            "contenders": {},
        }
        get = seg_getter(seg)
        for cid in CONTENDERS:
            block["contenders"][cid] = _entry(get, cid, True)
        (RESULTS / f"{seg}.json").write_text(json.dumps(block, separators=(",", ":")))
        table[seg] = {
            cid: block["contenders"][cid]["windows"]["ai_era"] for cid in CONTENDERS
        }
        logger.info("segment %s done", seg)
        for t in tickers:
            tb = {
                "name": t,
                "kind": "ticker",
                "segment": seg,
                "start_capital": START_CAPITAL,
                "contenders": {},
            }
            g = tick_getter(t)
            for cid in CONTENDERS:
                if cid == "K6_MOMENTUM_CS":
                    tb["contenders"][cid] = {
                        "available": False,
                        "reason": "cross-sectional rule needs several tickers (segment only)",
                    }
                else:
                    tb["contenders"][cid] = _entry(g, cid, True)
            (RESULTS / f"{t}.json").write_text(json.dumps(tb, separators=(",", ":")))
            ticker_table[t] = {
                cid: tb["contenders"][cid].get("windows", {}).get("ai_era")
                for cid in CONTENDERS
                if cid != "K6_MOMENTUM_CS"
            }

    # pick diagnostics: K1 plus the two best others (mean AI-era Sharpe over segments; B0 and K1 excluded)
    def mean_sharpe(cid: str) -> float:
        xs = [
            table[s][cid]["sharpe"]
            for s in table
            if table[s][cid] and table[s][cid]["sharpe"] is not None
        ]
        return float(np.mean(xs)) if xs else -9.0

    others = sorted(
        (c for c in CONTENDERS if c not in ("B0_BUYHOLD", "K1_C13C_ORIG")),
        key=mean_sharpe,
        reverse=True,
    )
    diag_ids = ["K1_C13C_ORIG", *others[:2]]
    logger.info("robustness for %s", diag_ids)
    rob = {cid: robustness(runner, cid) for cid in diag_ids}
    look = lookahead_test(runner)
    look_arrays = lookahead_arrays_test(runner)
    summary = {
        "common_end": COMMON_END,
        "ai_era_start": AI_ERA_START,
        "cost_bps_per_side": BASE_BPS,
        "start_capital_per_sleeve": START_CAPITAL,
        "currency_note": "USD prices treated as EUR-equivalent; FX not modelled",
        "ledger_k_after_registration": k_now,
        "data_handling": {
            "first_bar_used": {
                t: str(b.dates[0].date()) for t, b in runner.bars.items()
            },
            "bad_tick_repairs": {t: b.repairs for t, b in runner.bars.items() if b.repairs},
            "end_of_window": "open positions are liquidated at the last close and pay the exit cost",
            "audit": "2026-10-14 independent audit: halted history dropped (SMCI, NBIS), NVDA bad high clamped, "
            "exit cost on the final liquidation",
        },
        "registered": reg,
        "segment_x_contender_ai_era": table,
        "ticker_x_contender_ai_era": ticker_table,
        "diagnostic_contenders": diag_ids,
        "diagnostic_selection_rule": "K1 plus the two contenders (not B0) with the highest mean AI-era Sharpe over segments",
        "robustness_pm20": rob,
        "lookahead": look,
        "lookahead_arrays": look_arrays,
        "multiple_testing_note": (
            f"{len(CONTENDERS)} contenders were run on {len(segments)} segments and "
            f"{sum(len(v) for v in segments.values())} tickers; ledger K is {k_now}. "
            "The best-looking cell of such a table is expected to beat zero by luck alone; deflated Sharpe "
            "probabilities (per segment result files) use this K and are informational, not a Critic verdict."
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, separators=(",", ":")))
    logger.info("done; K=%s", k_now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
