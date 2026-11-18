"""Reproduce the frozen C21 diagnostic study; never connect to a broker."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from lab.data import load_bars
from lab.ledger import current_k
from lab.research.memory_swing import replay, metrics, benchmark

OUTPUT = ROOT / "reports/backtest/C21_SWING_20261006"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False,
                               default=lambda x: x.item() if isinstance(x, np.generic) else str(x))+"\n")


def fx_table(path):
    rows = {}
    for node in ET.fromstring(path.read_bytes()).iter():
        if "time" in node.attrib:
            usd = next((child.attrib["rate"] for child in node if child.attrib.get("currency") == "USD"), None)
            if usd:
                rows[pd.Timestamp(node.attrib["time"], tz="UTC")] = float(usd)
    return pd.Series(rows).sort_index()


def fx_rate(rates, day, before=False):
    subset = rates.loc[rates.index < day] if before else rates.loc[rates.index <= day]
    if subset.empty or (day-subset.index[-1]).days > 7:
        raise ValueError(f"No timely historical ECB rate at {day}")
    return float(subset.iloc[-1])


def main(study="C21_SWING_20261006"):
    global OUTPUT
    import re
    if not re.fullmatch(r"[A-Z0-9_]+", study):
        raise ValueError("Invalid study id")
    OUTPUT = ROOT / "reports/backtest" / study
    config = json.loads((OUTPUT/"config.json").read_text())
    freeze = ROOT / f"strategies/frozen/2026-10-06_{study}.md"
    frozen_config = json.loads(freeze.read_text().split("```json\n",1)[1].split("```",1)[0])
    if config != frozen_config:
        raise ValueError("Study configuration differs from freeze")
    original = ROOT/config["source_freeze"]
    if hashlib.sha256(original.read_bytes()).hexdigest() != config["source_freeze_sha256"]:
        raise ValueError("Source C13C freeze changed")
    subprocess.run([sys.executable, str(ROOT/"scripts/validate_data.py"), "--through", config["through"],
                    "--report", str(OUTPUT/"DATA_CHECK.md")], cwd=ROOT, check=True)
    symbols = sorted({s for group in config["universes"].values() for s in group})
    frames = {s:load_bars(s, through=config["through"]) for s in symbols}
    rates = fx_table(OUTPUT/"ecb-history.xml")
    params = dict(trend=config["parameters"]["trend_window"], bars=config["parameters"]["dip_bars"],
                  dip=config["parameters"]["dip_pct"], trail=config["parameters"]["trailing_pct"])
    results, details = {}, {}

    def run_case(key, universe, profile, period, overrides=None):
        subset = {s:frames[s] for s in universe}
        start,end = period
        common_start = max(pd.Timestamp(start,tz="UTC"),max(f.index[0] for f in subset.values()))
        common_end = min(pd.Timestamp(end,tz="UTC"),min(f.index[-1] for f in subset.values()))
        common_dates = next(iter(subset.values())).loc[common_start:common_end].index
        if common_dates.empty:
            return {"status":"NO_HISTORY_FOR_PERIOD","requested_start":start,"requested_end":end}
        initial_fx = fx_rate(rates,common_dates[0],before=True) if profile["currency"] == "EUR" else None
        capital = profile["capital"]*(initial_fx or 1.)
        result = replay(subset,start,end,capital,sizing=profile["sizing"],cap=profile["cap"],**(params | (overrides or {})))
        if result is None:
            return {"status":"NO_HISTORY_FOR_PERIOD"}
        curve = result["curve"]
        curve_base = curve.copy()
        if profile["currency"] == "EUR":
            curve_base = curve/pd.Series([fx_rate(rates,d) for d in curve.index],index=curve.index)
        summary = metrics(curve_base,profile["capital"],result["trades"])
        summary.update(status="SIMULATED",base_currency=profile["currency"],closed_trade_statistics_currency="USD",initial_usd=capital,
                       entry_reference_eurusd=initial_fx,final_usd=float(curve.iloc[-1]),
                       requested_start=start,requested_end=end,actual_start=str(curve.index[0].date()),
                       actual_end=str(curve.index[-1].date()),partial_history=common_start>pd.Timestamp(start,tz="UTC"),
                       **{k:v for k,v in result.items() if k not in {"curve","trades","skipped","events"}})
        summary["n_skipped"] = len(result["skipped"])
        summary["n_entry_day_stops"] = sum(t["sessions_held"]==1 for t in result["trades"])
        summary["benchmarks"] = {}
        for mode in ["equal","one"]:
            bc,holdings = benchmark(subset,curve.index,capital,mode)
            if profile["currency"] == "EUR":
                bc = bc/pd.Series([fx_rate(rates,d) for d in curve.index],index=curve.index)
            summary["benchmarks"][mode] = metrics(bc,profile["capital"]) | {"holdings":holdings}
        # Fixed cash in USD can gain/lose in EUR independently of the strategy.
        cash_curve = pd.Series(capital,index=curve.index)
        if profile["currency"] == "EUR":
            cash_curve /= pd.Series([fx_rate(rates,d) for d in curve.index],index=curve.index)
        summary["usd_cash_benchmark"] = metrics(cash_curve,profile["capital"])
        curve.rename("equity_usd").to_frame().assign(equity_base=curve_base).to_csv(OUTPUT/f"{key}_equity.csv")
        pd.DataFrame(result["trades"]).to_csv(OUTPUT/f"{key}_trades.csv",index=False)
        pd.DataFrame(result["skipped"]).to_csv(OUTPUT/f"{key}_skipped.csv",index=False)
        details[key] = result
        return summary

    for group,universe in config["universes"].items():
        for profile_name,profile in config["profiles"].items():
            for period_name,period in config["periods"].items():
                key = f"{group}__{profile_name}__{period_name}"
                results[key] = run_case(key,universe,profile,period)
        print(f"FINISHED {group}",flush=True)
    diagnostics = {}
    for profile_name,profile in config["profiles"].items():
        for mult in [2,3]:
            for period in ["WF","POST_CHATGPT"]:
                key=f"COST{mult}__{profile_name}__{period}"
                diagnostics[key]=run_case(key,config["universes"]["CORE"],profile,config["periods"][period],{"stress":mult})
        for year in range(2021,2027):
            key=f"YEAR{year}__{profile_name}"
            diagnostics[key]=run_case(key,config["universes"]["CORE"],profile,[f"{year}-01-01",min(f"{year}-12-31",config["through"])])
    sensitivity={}
    profile=config["profiles"].get("SMALL_600EUR_RISK2",next(iter(config["profiles"].values())))
    for param,values in {"trend":[160,240],"bars":[4,6],"dip":[.04,.06],"trail":[.08,.12]}.items():
        for value in values:
            key=f"SENS_{param}_{value}"
            sensitivity[key]=run_case(key,config["universes"]["CORE"],profile,config["periods"]["WF"],{param:value})
    audit={"fill_violations":sum(r["fill_violations"] for r in details.values()),
           "max_daily_volume_fraction":max(r["max_daily_volume_fraction"] for r in details.values()),
           "curve_cases":len(details),"prefix":[],"no_broker_calls":True}
    # Validate causal execution and equity, using USD to avoid FX valuation differences.
    primary={s:frames[s] for s in config["universes"]["CORE"]}
    full=replay(primary,"2016-01-04",config["through"],100000)
    for cutoff in ["2020-12-31","2023-12-29","2025-12-31"]:
        cut=replay(primary,"2016-01-04",cutoff,100000)
        diff=float((cut["curve"]-full["curve"].reindex(cut["curve"].index)).abs().max())
        audit["prefix"].append({"cutoff":cutoff,"max_equity_difference":diff,
                                "events_match":cut["events"]==[e for e in full["events"] if e[0]<=cutoff]})
    if audit["fill_violations"] or any(z["max_equity_difference"]>1e-7 or not z["events_match"] for z in audit["prefix"]):
        raise ValueError("Replay audit failed; no result approved")
    manifest={f"data/ohlcv/{s}_1d.csv":hashlib.sha256((ROOT/f"data/ohlcv/{s}_1d.csv").read_bytes()).hexdigest() for s in symbols}
    manifest.update({f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ["lab/research/memory_swing.py","scripts/run_memory_swing.py","app/backend/strategies/c13c.py","app/backend/money.py"]})
    write_json(OUTPUT/"summary.json",dict(config=config,k=current_k(),results=results,diagnostics=diagnostics,
               sensitivity=sensitivity,audit=audit,manifest=manifest,
               fx_source="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml",
               fx_sha256=hashlib.sha256((OUTPUT/"ecb-history.xml").read_bytes()).hexdigest(),
               disclaimer="Hypothetical simulation, not actual trading performance or investment advice. Paper only; no orders. Prior holdout seen. No Critic approval. Whole adjusted share units and reference FX are approximations; no dividends, tax, funding/conversion charges or live fill reconciliation."))
    print(json.dumps({"cases":len(results),"diagnostics":len(diagnostics),"sensitivity":len(sensitivity),"audit":audit},indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="C21_SWING_20261006")
    main(parser.parse_args().study)
