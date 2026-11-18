"""Run validated frozen research rules, then produce contract JSON and Croatian reports."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from lab.contracts import BacktestResult, FrozenStrategy
from lab.data import ROOT, load_bars, split_periods
from lab.engine import Simulation, backtest, backtest_rotation
from lab.ledger import current_k, register_strategy
from lab.metrics import summarize
from lab.strategies.registry import is_closed, signals, validate_strategy


def run_basket(strategy, context, k):
    if strategy.timeframe != "daily" or strategy.exit != {"type": "hold"}:
        raise ValueError("Basket supports daily buy-and-hold only")
    shared = context["MU"].index
    for frame in context.values():
        shared = shared.intersection(frame.index)
    frames = {s: f.loc[shared].copy() for s, f in context.items()}
    member = strategy.model_copy(deep=True)
    member.entry = {"type": "buy_hold"}
    member_results = {s: backtest(f, member, s, k_at_run=k) for s, f in frames.items()}
    details, stats, flags = (
        {},
        {},
        [
            "research_only",
            "equal_weight_initial_not_rebalanced",
            "period_boundary_liquidation",
            "price_only_no_dividends",
        ],
    )
    for period in ["IS", "WF", "HO"]:
        equity = sum(x[1][period].equity for x in member_results.values()) / 3
        member_trades = [x[1][period].trades for x in member_results.values()]
        trades = []
        if all(member_trades):
            first = [t[0] for t in member_trades]
            trades = [
                {
                    "entry_time": first[0]["entry_time"],
                    "exit_time": first[0]["exit_time"],
                    "notional_usd": sum(t["notional_usd"] for t in first) / 3,
                    "net_return": sum(t["net_return"] for t in first) / 3,
                    "reason": "period_end",
                    "components": first,
                }
            ]
        sample = split_periods(frames["MU"])[period]
        summary, warnings = summarize(trades, equity, sample.close)
        # Equal-weight benchmark uses member daily returns, not MU's Sharpe.
        from lab.metrics import sharpe

        prices = pd.concat(
            {s: split_periods(f)[period].close for s, f in frames.items()}, axis=1
        )
        if len(prices):
            benchmark = prices.div(prices.iloc[0]).mean(axis=1)
            summary.buy_hold_sharpe = sharpe(benchmark.pct_change())
        details[period] = Simulation(trades, equity)
        stats[period] = summary
        flags.extend(f"{period}:{w}" for w in warnings)
    return BacktestResult(
        strategy_id=strategy.id,
        ticker="BASKET",
        run_at=datetime.now(timezone.utc),
        costs=strategy.costs,
        k_at_run=k,
        periods=stats,
        flags=flags,
    ), details


def explanation(result):
    if result.strategy_id.startswith(("B1_", "B2_", "B3_")):
        return "MJERILO — usporedna osnovna linija."
    if result.periods["WF"].n < 10:
        return "Premalo WF trgovina; prednost nije dokazana."
    means = [result.periods[p].mean_pct for p in ("IS", "WF", "HO")]
    if any(v is None or v <= 0 for v in means):
        return "Prednost nije stabilna u svim razdobljima."
    return "Istraživački kandidat; prednost još nije potvrđena Criticom."


def league_metrics(strategy, context, details):
    """Account return and exposure on the actual WF bars; matched-cost benchmark."""
    metrics = {}
    for ticker, periods in details.items():
        sim = periods["WF"]
        frames = (
            {t: context[t] for t in strategy.universe}
            if ticker in {"BASKET", "ROTATION"}
            else {ticker: context[ticker]}
        )
        shared = sim.equity.index
        total = float((sim.equity.iloc[-1] / 500 - 1) * 100) if len(shared) else None
        exposure = pd.Series(False, index=shared)
        for trade in sim.trades:
            exposure |= (shared >= pd.Timestamp(trade["entry_time"])) & (
                shared <= pd.Timestamp(trade["exit_time"])
            )
        # Intraday: bar-duration exposure; daily: fraction of trading days touched.
        benchmark_returns = []
        for symbol, frame in frames.items():
            member = strategy.model_copy(deep=True)
            member.universe = [symbol]
            member.entry, member.exit = {"type": "buy_hold"}, {"type": "hold"}
            _result, benchmark = backtest(frame.loc[shared].copy(), member, symbol)
            eq = benchmark["WF"].equity
            if len(eq):
                benchmark_returns.append(float((eq.iloc[-1] / 500 - 1) * 100))
        metrics[ticker] = {
            "total_pct": total,
            "exposure_pct": float(exposure.mean() * 100) if len(shared) else None,
            "buy_hold_pct": float(np.mean(benchmark_returns))
            if benchmark_returns
            else None,
        }
    return metrics


def write_report(result, details, output, provenance=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f"{result.strategy_id}_{result.ticker}"
    stem.with_suffix(".json").write_text(result.model_dump_json(indent=2))
    audit = {
        p: {
            "trades": s.trades,
            "equity": [
                {"timestamp": t.isoformat(), "usd": v} for t, v in s.equity.items()
            ],
        }
        for p, s in details.items()
    }
    audit["_provenance"] = provenance or {}
    Path(str(stem) + "_audit.json").write_text(json.dumps(audit, indent=2))
    lines = [
        f"# {result.strategy_id} — {result.ticker}",
        "",
        "Povijesna simulacija nije obećanje zarade. Bez Critic PASS-a nema KUPI.",
        "",
        "IS je početni uzorak, WF provjera na sljedećim godinama, HO zadnja odvojena provjera.",
        "Kao učenje za ispit: rezultat na pitanjima za vježbu ne dokazuje uspjeh na novom ispitu.",
        "",
        "| Razdoblje | Trgovina | Prosjek po trgovini | Dobitnih | Zarada/rizik | Najveći pad | Kupi-i-drži zarada/rizik |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    def number(value, suffix=""):
        return "nema" if value is None else f"{value:.3f}{suffix}"

    for p, s in result.periods.items():
        lines.append(
            f"| {p} | {s.n} | {number(s.mean_pct, '%')} | {number(None if s.win_rate is None else s.win_rate * 100, '%')} | {number(s.sharpe)} | {number(s.max_dd_pct, '%')} | {number(s.buy_hold_sharpe)} |"
        )
    lines += [
        "",
        explanation(result),
        "",
        "Zarada/rizik je godišnji omjer dnevnih promjena vrijednosti i njihova kolebanja (Sharpe).",
        "Najveći pad je gubitak od prethodnog vrha, poput spuštanja nakon dosegnutog kata.",
        f"Trošak: {result.costs.round_trip_bps} baznih bodova za kupnju+prodaju (5 = 0,05 %), plus {result.costs.tick_per_side} × 0,01 USD po strani; množitelj {result.costs.stress_multiplier}.",
        f"Broj svih istraživačkih pokušaja K={result.k_at_run}.",
        "Početna vrijednost 500 USD, bez poluge. Granice razdoblja prisilno zatvaraju pozicije.",
        "Cijene ne uključuju reinvestirane dividende; nijedan nalog nije poslan.",
        "Zastavice: " + ", ".join(result.flags),
        "",
    ]
    stem.with_suffix(".md").write_text("\n".join(lines))


def evaluate(strategy, context, events, k):
    results, details = {}, {}
    for ticker in strategy.universe:
        results[ticker], details[ticker] = backtest(
            context[ticker], strategy, ticker, context, events, k
        )
    if strategy.entry["type"] == "equal_basket":
        results["BASKET"], details["BASKET"] = run_basket(strategy, context, k)
    if strategy.entry["type"] == "relative_strength":
        results["ROTATION"], details["ROTATION"] = backtest_rotation(
            context, strategy, k
        )
    return results, details


def trade_returns(details):
    return {
        ticker: {
            p: [t["net_return"] * 100 for t in sim.trades] for p, sim in periods.items()
        }
        for ticker, periods in details.items()
    }


def daily_returns(details, periods=("IS", "WF")):
    if "ROTATION" in details or "BASKET" in details:
        selected = {"PORTFOLIO": details.get("ROTATION", details.get("BASKET"))}
    else:
        selected = details
    pieces = []
    for period in periods:
        sleeves = []
        for per in selected.values():
            daily = per[period].equity.resample("D").last().dropna()
            changes = daily.pct_change()
            if len(changes):
                changes.iloc[0] = daily.iloc[0] / 500 - 1
            sleeves.append(changes)
        pieces.append(
            pd.concat(sleeves, axis=1).mean(axis=1).dropna()
            if sleeves
            else pd.Series(dtype=float)
        )
    return pd.concat(pieces).sort_index()


def sensitivity_variants(strategy):
    # Two perturbations per numeric parameter; no selected winner.
    keys = {
        "lookback",
        "trend_window",
        "dip_bars",
        "dip_pct",
        "vol_window",
        "compression",
        "shock_multiplier",
        "gap_pct",
        "drop_pct",
        "size_vol_target",
        "stop_pct",
        "target_pct",
        "trailing_pct",
        "hold_bars",
        "min_return",
    }
    variants = {}
    # Change one parameter at a time: simultaneous shifts can conceal fragility.
    for name in ["entry", "exit"]:
        for key, value in getattr(strategy, name).items():
            if key not in keys or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            for label, factor in [("minus20", 0.8), ("plus20", 1.2)]:
                shifted = max(1, round(value * factor)) if isinstance(value, int) else value * factor
                if shifted == value:
                    continue
                spec = strategy.model_copy(deep=True)
                getattr(spec, name)[key] = shifted
                variants[f"{name}.{key}.{label}"] = (
                    spec, {f"{name}.{key}": {"base": value, "shifted": shifted}}
                )
    return variants


def causality_evidence(strategy, context, events, k):
    checks = []
    for ticker in strategy.universe:
        frame = context[ticker]
        if len(frame) < 4:
            continue
        for cut in sorted({len(frame) // 2, len(frame) * 3 // 4}):
            truncated = {
                s: f.loc[f.index <= frame.index[cut - 1]].copy()
                for s, f in context.items()
            }
            corrupted = {s: f.copy() for s, f in context.items()}
            for f in corrupted.values():
                future = f.index >= frame.index[cut]
                f.loc[future, ["open", "high", "low", "close"]] *= 7
            full_signals = signals(frame, strategy, context, events)
            short_signals = signals(truncated[ticker], strategy, truncated, events)
            altered_signals = signals(corrupted[ticker], strategy, corrupted, events)
            signal_ok = all(
                a.iloc[:cut].equals(b) for a, b in zip(full_signals, short_signals)
            )
            future_ok = all(
                a.iloc[:cut].equals(b.iloc[:cut])
                for a, b in zip(full_signals, altered_signals)
            )
            # Verify execution on the prefix too; terminal liquidation is intentionally excluded.
            _, full = backtest(frame, strategy, ticker, context, events, k)
            _, short = backtest(
                truncated[ticker], strategy, ticker, truncated, events, k
            )
            _, altered = backtest(
                corrupted[ticker], strategy, ticker, corrupted, events, k
            )
            equity_ok = future_equity_ok = True
            for period in ["IS", "WF", "HO"]:
                end = short[period].equity
                compare = end.iloc[:-1].index
                equity_ok &= np.allclose(
                    full[period].equity.reindex(compare), end.reindex(compare)
                )
                future_equity_ok &= np.allclose(
                    full[period].equity.reindex(compare),
                    altered[period].equity.reindex(compare),
                )
            checks.append(
                {
                    "ticker": ticker,
                    "cut": frame.index[cut - 1].isoformat(),
                    "truncation_ok": bool(signal_ok and equity_ok),
                    "corrupt_future_ok": bool(future_ok and future_equity_ok),
                }
            )
    return {
        "checks": checks,
        "truncation_ok": bool(checks) and all(c["truncation_ok"] for c in checks),
        "corrupt_future_ok": bool(checks)
        and all(c["corrupt_future_ok"] for c in checks),
        "terminal_bar_excluded": True,
    }


def select_frozen_files(directory, strategy_ids=None):
    files = sorted(Path(directory).glob("*.json"))
    if strategy_ids is None:
        return files
    requested = set(strategy_ids)
    if not requested:
        raise ValueError("Empty strategy selection")
    selected = [
        p for p in files if any(p.name.endswith(f"_{sid}.json") for sid in requested)
    ]
    found = {
        sid
        for sid in requested
        if any(p.name.endswith(f"_{sid}.json") for p in selected)
    }
    if found != requested:
        raise ValueError(f"Unknown frozen IDs: {sorted(requested - found)}")
    return selected


def run_all(
    root=ROOT, stress=1.0, include_holdout=True, critic_inputs=True, strategy_ids=None, through=None, daily_only=False
):
    root = Path(root)
    if through is not None:
        from datetime import date
        through = date.fromisoformat(str(through)).isoformat()
    if stress < 1:
        raise ValueError("Stress must be >=1")
    validation = [sys.executable, str(root / "scripts/validate_data.py")]
    if through is not None:
        validation += ["--through", through]
    files = select_frozen_files(root / "strategies/frozen", strategy_ids)
    if daily_only:
        if not strategy_ids:
            raise ValueError("--daily-only requires explicit --ids")
        strategies = [FrozenStrategy.model_validate_json(path.read_text()) for path in files]
        if any(strategy.timeframe != "daily" for strategy in strategies):
            raise ValueError("--daily-only supports daily strategies only")
        symbols = set()
        for strategy in strategies:
            symbols.update(strategy.universe)
            symbols.update(strategy.entry.get(
                "leaders",
                ["AMAT", "LRCX", "KLAC"] if strategy.entry["type"] == "leader" else [],
            ))
        validation += ["--daily-symbols", *sorted(symbols)]
    subprocess.run(validation, cwd=root, check=True)
    output = root / "reports/backtest"
    output.mkdir(parents=True, exist_ok=True)
    calendar = root / "data/news/events_calendar.csv"
    events = pd.read_csv(calendar, dtype=str) if calendar.exists() else None
    results, skipped, registered, packages, daily = [], [], [], {}, {}
    ledger_path = root / "reports/ledger/trials.jsonl"
    for path in files:
        try:
            strategy = FrozenStrategy.model_validate_json(path.read_text())
            if is_closed(strategy):
                skipped.append(f"{path.name}: zatvorena linija")
                continue
            validate_strategy(strategy)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            register_strategy(
                strategy.id,
                digest,
                ledger_path,
                timeframe=strategy.timeframe,
                diagnostics=["cost2x", "one_parameter_minus20_plus20"],
            )
            registered.append((path, strategy, digest))
        except (ValueError, KeyError) as error:
            skipped.append(f"{path.name}: nevaljan ugovor ({type(error).__name__})")
    k = current_k(ledger_path)
    cache = {}
    for path, strategy, digest in registered:
        print(f"RUN {strategy.id}: K={k}", flush=True)
        required = set(strategy.universe) | set(
            strategy.entry.get(
                "leaders",
                ["AMAT", "LRCX", "KLAC"] if strategy.entry["type"] == "leader" else [],
            )
        )
        context, hashes = {}, {}
        try:
            for ticker in sorted(required):
                key = (ticker, strategy.timeframe)
                if key not in cache:
                    cache[key] = load_bars(ticker, strategy.timeframe, root, through=through)
                frame = cache[key]
                context[ticker] = (
                    frame
                    if include_holdout
                    else frame[frame.date < "2024-01-01"].copy()
                )
                folder, suffix = {
                    "daily": ("ohlcv", "1d"),
                    "hourly": ("hourly", "1h_clean"),
                    "5min": ("intraday", "5m_clean"),
                }[strategy.timeframe]
                hashes[ticker] = hashlib.sha256(
                    (root / f"data/{folder}/{ticker}_{suffix}.csv").read_bytes()
                ).hexdigest()
            strategy = strategy.model_copy(deep=True)
            strategy.costs.stress_multiplier *= stress
            base, details = evaluate(strategy, context, events, k)
            ml_metadata = (
                {t: f.attrs.get("ml_diagnostics") for t, f in context.items()}
                if strategy.entry["type"] == "ml_logit"
                else None
            )
            diagnostic_context = {
                t: f[f.date < "2024-01-01"].copy() for t, f in context.items()
            }
            if ml_metadata is not None:
                (output / f"{strategy.id}_model_diagnostics.json").write_text(
                    json.dumps(ml_metadata, indent=2, allow_nan=False) + "\n"
                )
            league = league_metrics(strategy, context, details)
            provenance = {
                "league_wf": league,
                "engine_revision": "pre_holdout_diagnostics_v2",
                "data_through": through,
                "diagnostic_holdout_excluded": True,
                "freeze_file": str(path.relative_to(root)),
                "freeze_sha256": digest,
                "data_sha256": hashes,
                "stress": stress,
                "holdout_included": include_holdout,
            }
            for ticker, result in base.items():
                if not include_holdout:
                    result.flags.append("holdout_not_opened")
                if strategy.id.startswith("H4"):
                    result.flags.append("engine_fix_early_close_v1")
                write_report(result, details[ticker], output, provenance)
                results.append(result)
            if not critic_inputs:
                continue
            # All diagnostics were declared before this run; no selection based on HO.
            two = strategy.model_copy(deep=True)
            two.costs.stress_multiplier *= 2
            stressed, stress_details = evaluate(two, diagnostic_context, events, k)
            sensitivity, diagnostics = {}, {}
            for label, (spec, changed) in sensitivity_variants(strategy).items():
                variant, variant_details = evaluate(spec, diagnostic_context, events, k)
                selected = {
                    t: p
                    for t, p in trade_returns(variant_details).items()
                    if t in strategy.universe
                }
                values = [v for per in selected.values() for v in per["WF"]]
                mean = float(np.mean(values)) if values else None
                sensitivity[label] = {
                    "wf_mean_pct": mean,
                    "edge_crushed": mean is None or mean <= 0,
                }
                diagnostics[label] = {
                    "parameters": changed,
                    "returns": selected,
                    "results": {
                        t: r.model_dump(mode="json") for t, r in variant.items()
                    },
                }
            evidence = causality_evidence(strategy, diagnostic_context, events, k)
            def fill_violations_for(periods):
                return sum(
                    t["notional_usd"] > 500.000001
                    or t["quantity"] <= 0
                    or t["reason"] == "missing_session_close"
                    for per in details.values()
                    for period, sim in per.items() if period in periods
                    for t in sim.trades if "quantity" in t
                )
            violations = fill_violations_for(("IS", "WF"))
            holdout_violations = fill_violations_for(("HO",))
            package = {
                "schema_version": 1,
                "strategy_id": strategy.id,
                "units": "percent_per_trade",
                "returns": {
                    t: p
                    for t, p in trade_returns(details).items()
                    if t in strategy.universe
                },
                "portfolio_returns": {
                    t: p
                    for t, p in trade_returns(details).items()
                    if t not in strategy.universe
                },
                "stressed_returns": {
                    t: p
                    for t, p in trade_returns(stress_details).items()
                    if t in strategy.universe
                },
                "stressed_results": {
                    t: r.model_dump(mode="json") for t, r in stressed.items()
                },
                "costs": strategy.costs.model_dump(),
                "k": current_k(ledger_path),
                "data_check_exit_code": 0,
                "wdc_spinoff_adjusted_once": True,
                "freeze_matches": hashlib.sha256(path.read_bytes()).hexdigest()
                == digest,
                "lookahead_truncation_ok": evidence["truncation_ok"],
                "lookahead_corrupt_future_ok": evidence["corrupt_future_ok"],
                "lookahead_evidence": evidence,
                "sensitivity": sensitivity or None,
                "sensitivity_diagnostics": diagnostics,
                "ledger_complete": True,
                "no_fitted_parameters": None,
                "data_through": through,
                "embargo_documented": False,
                "fill_violations": int(violations),
                "holdout_fill_violations": int(holdout_violations) if include_holdout else None,
                "diagnostic_holdout_excluded": True,
                "authenticity_audit_ok": None,
                "provenance": provenance,
                "notes": [
                    "Osjetljivost mijenja jedan brojčani parametar po dijagnostici; koristi samo IS/WF.",
                    "Nema posebnog embarga ni neovisnog završnog audita; Critic mora pasti ako ih traži.",
                    "Izvedivost likvidnosti i polovice sjednica nije neovisno potvrđena.",
                ],
            }
            if ml_metadata is not None:
                package.update(
                    no_fitted_parameters=False,
                    ml_diagnostics=ml_metadata,
                    purge_bars=5,
                    diagnostic_holdout_excluded=True,
                )
                package["notes"].append(
                    "Logit je učen: pet barova purge na granici; dodatni embargo i neovisni audit nisu potvrđeni. HO samo osnovni rezultat, bez dijagnostika."
                )
            packages[strategy.id] = package
            daily[strategy.id] = daily_returns(details)
        except (ValueError, FileNotFoundError) as error:
            skipped.append(
                f"{strategy.id}: nije dovršeno ({type(error).__name__}: {error})"
            )
    families = {}
    for strategy_id in daily:
        legacy_family = re.match(r"^(?:ML|[BCH])\d+", strategy_id)
        families[strategy_id] = legacy_family.group() if legacy_family else strategy_id
    for strategy_id, package in packages.items():
        family = families[strategy_id]
        members = {s: r for s, r in daily.items() if families[s] == family}
        matrix = pd.concat(members, axis=1).dropna()
        package["trials_matrix"] = (
            matrix.to_numpy().tolist() if len(members) >= 2 else None
        )
        package["trials_matrix_metadata"] = {
            "columns": list(matrix.columns),
            "timestamps": [t.isoformat() for t in matrix.index],
            "units": "daily_return_fraction",
            "periods": ["IS", "WF"],
            "holdout_excluded": True,
            "family": family,
        }
        (output / f"{strategy_id}_critic_inputs.json").write_text(
            json.dumps(package, indent=2, allow_nan=False) + "\n"
        )
    for package_path in output.glob("*_critic_inputs.json"):
        stored_package = json.loads(package_path.read_text())
        stored_package["k"] = current_k(ledger_path)
        package_path.write_text(
            json.dumps(stored_package, indent=2, allow_nan=False) + "\n"
        )
    lines = [
        "# Ligaška tablica povijesnih provjera",
        "",
        "Nijedan rezultat nije odobrenje za kupnju. Critic i approved_list su zasebna vrata.",
        "Rast dionice tijekom booma može izgledati kao uspješna strategija.",
        "",
        "| Strategija | Dionica | Broj trgovina WF | WF prosjek po trgovini | WF ukupna promjena računa | Udio vremena u tržištu | Kupi-i-drži isto razdoblje i troškovi | Što to znači |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    league_results = results
    if strategy_ids is not None:
        # Refresh the display from stored contracts without rerunning other strategies.
        stored = {}
        for result_path in output.glob("*.json"):
            try:
                row = BacktestResult.model_validate_json(result_path.read_text())
            except ValueError:
                continue
            stored[(row.strategy_id, row.ticker)] = row
        league_results = list(stored.values())
    league_values = {}
    signatures = {}
    for r in league_results:
        audit_path = output / f"{r.strategy_id}_{r.ticker}_audit.json"
        if audit_path.exists():
            audit = json.loads(audit_path.read_text())
            league_values[(r.strategy_id, r.ticker)] = (
                audit.get("_provenance", {}).get("league_wf", {}).get(r.ticker, {})
            )
            # Economic sizing may differ, but identical entry/exit paths have one interpretation.
            signature = tuple(
                (p, t["entry_time"], t["exit_time"], t["reason"])
                for p in ("IS", "WF", "HO")
                for t in audit[p]["trades"]
            )
            signatures[(r.strategy_id, r.ticker)] = (r.ticker, signature)
    labels = {}
    for r in league_results:
        key = signatures.get((r.strategy_id, r.ticker))
        if key is not None and r.strategy_id.startswith(("B1_", "B2_", "B3_")):
            labels[key] = explanation(r) + " Identične trgovine imaju istu oznaku."

    def total(r):
        return league_values.get((r.strategy_id, r.ticker), {}).get("total_pct") or 0

    ordered = sorted(league_results, key=total, reverse=True)
    benchmarks = [r for r in ordered if r.strategy_id.startswith(("B1_", "B2_", "B3_"))]
    research = [r for r in ordered if r not in benchmarks]
    for group in (benchmarks, research):
        for r in group:
            stat = r.periods["WF"]
            values = league_values.get((r.strategy_id, r.ticker), {})

            def number(v):
                return "nema" if v is None else f"{v:.3f} %"

            label = labels.get(
                signatures.get((r.strategy_id, r.ticker)), explanation(r)
            )
            if (
                "ticker_sleeve_not_combined_rotation_portfolio" in r.flags
                or r.strategy_id.startswith("B3_")
                and r.ticker != "BASKET"
            ):
                label += " Zaseban dio, nije zajednički portfelj."
            lines.append(
                f"| {r.strategy_id} | {r.ticker} | {stat.n} | {number(stat.mean_pct)} | {number(values.get('total_pct'))} | {number(values.get('exposure_pct'))} | {number(values.get('buy_hold_pct'))} | {label} |"
            )
        if group is benchmarks:
            lines.append("| **Istraživanja — zasebno od mjerila** | | | | | | | |")
    lines += [
        "",
        "Udio vremena: udio trgovinskih barova dotaknutih pozicijom (satni/5-min barovi ili dnevni dani); uključuje ulazni i izlazni bar. Mjerila su odvojena, obje skupine sortirane po ukupnoj WF promjeni računa. Kupi-i-drži ulazi na drugom baru razdoblja, uz iste troškove i datume; košarica koristi jednake početne udjele. Cijene bez dividendi; universe je odabran povijesno i može sadržavati pristranost preživjelih.",
    ]
    if not league_results:
        lines += ["", "Nema pokrenutih novih strategija. Signal PRIČEKAJ."]
    lines += ["", "## Što nije dovršeno", ""] + (
        skipped or ["Nema preskočenih strategija."]
    )
    (output / "LEAGUE_TABLE.md").write_text("\n".join(lines) + "\n")
    summary = {
        "frozen_count": len(files),
        "registered_count": len(registered),
        "result_count": len(results),
        "critic_package_count": len(packages),
        "k": k,
        "skipped": skipped,
    }
    if strategy_ids is not None:
        summary["selected_ids"] = sorted(set(strategy_ids))
    summary_name = (
        "RUN_SUMMARY.json" if strategy_ids is None else "RUN_SUMMARY_SELECTED.json"
    )
    (output / summary_name).write_text(json.dumps(summary, indent=2))
    print("RUN ALL:", json.dumps(summary), flush=True)
    return results, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily-only", action="store_true", help="Validate only the daily symbols used by the selected IDs")
    parser.add_argument("--ids", nargs="+", help="Run only these frozen IDs")
    parser.add_argument("--stress", type=float, default=1.0)
    parser.add_argument("--without-holdout", action="store_true")
    parser.add_argument("--through", help="Last independently completed session, YYYY-MM-DD")
    parser.add_argument("--without-critic-inputs", action="store_true")
    args = parser.parse_args()
    run_all(
        stress=args.stress,
        include_holdout=not args.without_holdout,
        critic_inputs=not args.without_critic_inputs,
        strategy_ids=args.ids,
        daily_only=args.daily_only,
        through=args.through,
    )


if __name__ == "__main__":
    main()
