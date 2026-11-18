"""Runner: `python -m lab.crypto_dt.run <module> [--dry] [--agent NAME]`.

Same contract as `lab.top10.run` (freeze, one ledger trial, results.json, six charts) on top of `lab.top10.core`, with
the bars supplied by `lab.crypto_dt.data` (4h from 1h) and the pre-registered criteria of
`docs/research/CRYPTO_DT_PREREGISTRATION.md` evaluated into `summary["prereg"]`.

--dry   evaluate and print only; nothing is written and no trial is logged (use while fixing bugs, never to tune on WF/HO).
default freeze the module (strategies/frozen), register ONE trial (K+1), write results and charts to
        reports/research/CRYPTO_DT_20261014/{ID}/. Afterwards the strategy file is immutable.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

import numpy as np
import pandas as pd

from lab import ledger
from lab.crypto_dt import data
from lab.top10 import core
from lab.top10.charts import make_charts

ROOT = core.ROOT
OUT = ROOT / "reports/research/CRYPTO_DT_20261014"
REQUIRED = ["ID", "HYPOTHESIS", "RULES", "UNIVERSE", "PARAMS", "SPLIT_KIND", "TIMEFRAME", "weights"]
MIN_TRADES = {  # pre-registered: per period (IS, WF, HO)
    "CDT_H1_TREND_4H": 10,
    "CDT_H1B_TREND_4H_NOVOL": 10,
    "CDT_H2_TREND_4H_CROWD": 10,
    "CDT_H2Q_TREND_4H_CROWD_QTL": 10,
    "CDT_H3_UTC2123_COND": 30,
    "CDT_H4_ID_MOM_VOL": 30,
    "CDT_H5_BTC_LEAD_5M": 30,
}
AMENDMENT = {  # ID -> amendment document that fixes the rule text for that ID
    "CDT_H2Q_TREND_4H_CROWD_QTL": "docs/research/CRYPTO_DT_PREREGISTRATION_AMENDMENT_1.md",
}
BREAK_EVEN_BPS = 20.0  # round-trip cost at 10 bps per side


def _sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _loader(tickers, cutoff: str = core.CUTOFF, timeframe: str = "1d"):
    return data.load_bars(tickers, timeframe, cutoff)


def _total(net: pd.Series) -> float:
    return float((1 + net).prod() - 1)


def _scaled_one(params: dict[str, Any], key: str, factor: float) -> dict[str, Any]:
    out = dict(params)
    value = params[key]
    out[key] = max(1, int(round(value * factor))) if isinstance(value, int) else value * factor
    return out


def _numeric_keys(params: dict[str, Any]) -> list[str]:
    return [k for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _contribution_ex_top3(bt: dict[str, Any], bounds: dict[str, tuple[str, str]]) -> float | None:
    """Mean net portfolio contribution per episode after removing the three best episodes (WF+HO entries).

    An episode is one continuous holding of one asset; its contribution is position * open-to-open return minus the
    turnover cost of every resize, with the exit cost booked on the episode it closes. Unlike the unweighted
    asset-price trade returns of `core.trades_from`, this follows deployed capital.
    """
    pos, ret, side = bt["pos"], bt["ret_oo"], bt["side"]
    gross = bt["gross"]
    drifted = (pos * (1 + ret)).div(1 + gross, axis=0).shift(1).fillna(0.0)
    contrib = pos * ret - (pos - drifted).abs() * side
    start, end = bounds["WF"][0], bounds["HO"][1]
    totals = []
    for asset in pos.columns:
        held = pos[asset] > 0
        begin = held & ~held.shift(1, fill_value=False)
        episode = begin.cumsum().where(begin.cumsum() > 0)  # flat bars (exit cost) join the preceding episode
        frame = pd.DataFrame({"c": contrib[asset], "e": episode}).dropna()
        sums = frame.groupby("e")["c"].sum()
        first = pos.index[begin.to_numpy()]
        entry = pd.Series(first, index=np.arange(1, len(first) + 1))
        keep = [e for e in sums.index if start <= str(entry.get(int(e), pd.Timestamp("1900-01-01")).date()) <= end]
        totals.extend(float(sums.loc[e]) for e in keep)
    totals.sort(reverse=True)
    return float(np.mean(totals[3:])) if len(totals) > 3 else None


def _buy_and_hold(pan: dict[str, pd.DataFrame], start: str) -> dict[str, float] | None:
    """Metrics of an equal-initial-capital, fixed-units basket from the first open at or after `start`.

    This is true buy-and-hold; `bt["bench"]` is an equal-weight basket rebalanced every bar without costs.
    """
    opens = pan["open"].loc[start:]
    basket = (opens / opens.iloc[0]).mean(axis=1)
    return core.metrics(basket.pct_change().dropna())


def prereg_block(module: Any, summary: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the pre-registered criteria and diagnostics for one run."""
    bt, pan, trades, bounds = bundle["bt"], bundle["pan"], bundle["trades"], bundle["bounds"]
    ai_window = (core.AI_ERA_START, bounds["HO"][1])
    net, bench = bt["net"], bt["bench"]
    side = bt["side"]
    by_period = {name: [] for name in bounds}
    for tr in trades:
        day = str(tr["entry"].date())
        for name, (a, b) in bounds.items():
            if a <= day <= b:
                by_period[name].append(tr)
    counts = {name: len(v) for name, v in by_period.items()}
    ai_trades = [t for p in ("WF", "HO") for t in by_period[p]]
    gross = [t["ret"] + (1 if t["open"] else 2) * float(side[t["ticker"]]) for t in ai_trades]
    gross_bps = float(np.mean(gross) * 1e4) if gross else None
    net_bps = float(np.mean([t["ret"] for t in ai_trades]) * 1e4) if ai_trades else None
    rets = sorted((t["ret"] for t in ai_trades), reverse=True)
    ex_top3 = float(np.mean(rets[3:])) if len(rets) > 3 else None
    contribution_ex_top3 = _contribution_ex_top3(bt, bounds)
    weights_now = module.weights(pan, module.PARAMS)
    cost_15 = _total(core.window(core.backtest(weights_now, pan, 1.5)["net"], ai_window))
    hold = _buy_and_hold(pan, core.AI_ERA_START)
    ai_net = core.window(net, ai_window)
    years = (1 + ai_net).groupby(ai_net.index.year).prod() - 1
    log_years = np.log1p(years)
    without_best_year = float(log_years.sum() - log_years.max()) if len(log_years) > 1 else None
    neighbours = []
    for key in _numeric_keys(module.PARAMS):
        for factor in (0.8, 1.2):
            try:
                weights = module.weights(pan, _scaled_one(module.PARAMS, key, factor))
                total = _total(core.window(core.backtest(weights, pan, 1.0)["net"], ai_window))
            except Exception:  # an invalid scaled parameter counts as a failed neighbour, not a crash
                total = None
            neighbours.append({"param": key, "factor": factor, "wf_ho_total": total})
    positive = sum(1 for n in neighbours if n["wf_ho_total"] is not None and n["wf_ho_total"] > 0)
    neighbour_share = positive / len(neighbours) if neighbours else None
    wf, ho = summary["splits"]["WF"], summary["splits"]["HO"]
    need = MIN_TRADES[module.ID]
    checks = {
        "lookahead_ok": bool(summary["lookahead_ok"]),
        "net_positive_wf_and_ho": bool(wf and ho and wf["total"] > 0 and ho["total"] > 0),
        "cost_2x_wf_ho_positive": bool((summary["cost_stress"]["2x"]["wf_ho_total"] or -1) > 0),
        f"trades_ge_{need}_per_period": all(c >= need for c in counts.values()),
        "neighbours_80pct_positive": bool(neighbour_share is not None and neighbour_share >= 0.8),
        "ex_top3_mean_positive": bool(ex_top3 is not None and ex_top3 > 0),
        "ex_top3_contribution_positive": bool(contribution_ex_top3 is not None and contribution_ex_top3 > 0),
        "not_one_year_dependent": bool(without_best_year is not None and without_best_year > 0),
    }
    ai = summary["eras"]["ai_era"]
    bai = summary["eras"]["benchmark_ai_era"]
    calmar = lambda m: (m["cagr"] / abs(m["maxdd"])) if m and m["maxdd"] else None  # noqa: E731
    all_ok = all(checks.values())
    near = checks["lookahead_ok"] and (_total(ai_net) > 0)
    verdict = "ZELENO" if all_ok else ("ŽUTO" if near else "CRVENO")
    block = {
        "verdict": verdict,
        "checks": checks,
        "trade_counts": counts,
        "gross_bps_per_trade_wf_ho": gross_bps,
        "net_bps_per_trade_wf_ho": net_bps,
        "break_even_bps_round_trip": BREAK_EVEN_BPS,
        "gross_over_break_even": (gross_bps / BREAK_EVEN_BPS) if gross_bps is not None else None,
        "ex_top3_mean_trade": ex_top3,
        "ex_top3_mean_contribution": contribution_ex_top3,
        "cost_1_5x_wf_ho_total": cost_15,
        "buy_and_hold_ai_era": hold,
        "log_return_wf_ho_without_best_year": without_best_year,
        "yearly_wf_ho": {int(y): float(v) for y, v in years.items()},
        "neighbours": neighbours,
        "neighbours_positive_share": neighbour_share,
        "ai_era_total": _total(ai_net),
        "equal_weight_rebalanced_ai_era_total": bai["total"] if bai else None,  # not buy-and-hold: see buy_and_hold_ai_era
        "calmar_ai_era": calmar(ai),
        "share_of_bars_with_any_position_full_sample": summary["exposure"],
        "mean_invested_weight_wf_ho": float(core.window(bt["pos"].sum(axis=1), ai_window).mean()),
    }
    beats_return = bool(hold and ai_net is not None and block["ai_era_total"] >= hold["total"])
    cs = block["calmar_ai_era"]
    cb = (hold["cagr"] / abs(hold["maxdd"])) if hold and hold["maxdd"] else None
    block["buy_and_hold_calmar_ai_era"] = cb
    smaller_dd = bool(ai and hold and abs(ai["maxdd"]) < abs(hold["maxdd"]))
    block["time_in_market_reducer"] = bool(not beats_return and cs is not None and cb is not None and cs > cb and smaller_dd)
    if hasattr(module, "diagnostics"):
        block["diagnostics"] = module.diagnostics(pan, module.PARAMS)
    return block


def _data_files(module: Any) -> dict[str, str]:
    base = {"4h": "1h"}.get(module.TIMEFRAME, module.TIMEFRAME)
    files = {t: _sha(core.data_path(t, base)) for t in module.UNIVERSE}
    if "funding_win" in module.PARAMS:
        for t in module.UNIVERSE:
            for kind in ("funding", "metrics_5m"):
                files[f"{t}_{kind}"] = _sha(data.DERIVS / f"{t}_{kind}.csv")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--agent", default="unknown")
    args = parser.parse_args(argv)
    module = importlib.import_module(f"lab.crypto_dt.strategies.{args.module}")
    missing = [n for n in REQUIRED if not hasattr(module, n)]
    if missing:
        raise SystemExit(f"strategy module is missing: {missing}")
    if module.ID not in MIN_TRADES:
        raise SystemExit(f"{module.ID} is not pre-registered (docs/research/CRYPTO_DT_PREREGISTRATION.md)")
    if args.dry:
        k = ledger.current_k() + 1
        with mock.patch.object(core, "load_frames", _loader):
            summary, bundle = core.evaluate(module, k)
        weights = module.weights(bundle["pan"], module.PARAMS)
        trades = bundle["trades"]
        print(  # structure only: dry runs must not expose WF/HO performance, so rules cannot be tuned on it
            json.dumps(
                {
                    "id": module.ID,
                    "lookahead_ok": summary["lookahead_ok"],
                    "data_range": summary["data_range"],
                    "bars": int(len(weights)),
                    "max_weight_sum": float(weights.sum(axis=1).max()),
                    "min_weight": float(weights.min().min()),
                    "weight_nan": int(weights.isna().sum().sum()),
                    "trades_total": len(trades),
                    "exposure": summary["exposure"],
                    "first_trade": str(trades[0]["entry"]) if trades else None,
                },
                indent=1,
            )
        )
        return 0
    existing = sorted((ROOT / "strategies/frozen").glob(f"*_{module.ID}.json"))
    frozen = existing[0] if existing else ROOT / f"strategies/frozen/{date.today().isoformat()}_{module.ID}.json"
    freeze = {
        "id": module.ID,
        "hypothesis": module.HYPOTHESIS,
        "rules": module.RULES,
        "universe": module.UNIVERSE,
        "params": module.PARAMS,
        "structure": getattr(module, "STRUCTURE", None),
        "split_kind": module.SPLIT_KIND,
        "splits": core.SPLITS[module.SPLIT_KIND],
        "costs_rt_bps": core.COST_RT_BPS,
        "execution": "decide at close, fill at next open, long-only, no leverage",
        "code_file": f"lab/crypto_dt/strategies/{args.module}.py",
        "code_sha256": _sha(module.__file__),
        "support_sha256": {f: _sha(ROOT / f"lab/crypto_dt/{f}") for f in ("data.py", "features.py", "run.py")},
        "timeframe": module.TIMEFRAME,
        "data_sha256": _data_files(module),
        "preregistration": "docs/research/CRYPTO_DT_PREREGISTRATION.md",
        "preregistration_sha256": _sha(ROOT / "docs/research/CRYPTO_DT_PREREGISTRATION.md"),
        "amendment": AMENDMENT.get(module.ID),
        "status": "research only; not a lab Critic PASS",
    }
    if frozen.exists():
        if json.loads(frozen.read_text()).get("code_sha256") != freeze["code_sha256"]:
            raise SystemExit("strategy code changed after freeze: use a NEW ID (frozen strategies are immutable)")
    else:
        frozen.write_text(json.dumps(freeze, indent=2, sort_keys=True))
    k = ledger.register_strategy(
        module.ID,
        _sha(frozen),
        agent=args.agent,
        purpose="crypto day trading research 2026-10-14; not Critic",
        unit="frozen_strategy_id",
    )
    with mock.patch.object(core, "load_frames", _loader):
        summary, bundle = core.evaluate(module, k)
    summary["prereg"] = prereg_block(module, summary, bundle)
    folder = OUT / module.ID
    folder.mkdir(parents=True, exist_ok=True)
    summary["charts"] = make_charts(summary, bundle, folder)
    summary.update(
        {
            "runner_sha256": _sha(ROOT / "lab/crypto_dt/run.py"),
            "hypothesis": module.HYPOTHESIS,
            "rules": module.RULES,
            "params": module.PARAMS,
            "freeze_file": str(frozen.relative_to(ROOT)),
        }
    )
    (folder / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    p = summary["prereg"]
    print(
        f"{module.ID}: prereg={p['verdict']} core_rating={summary['rating']} K={k} trades={p['trade_counts']} "
        f"gross_bps={p['gross_bps_per_trade_wf_ho']} failed={[c for c, ok in p['checks'].items() if not ok]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
