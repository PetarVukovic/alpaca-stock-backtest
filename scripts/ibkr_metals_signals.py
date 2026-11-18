#!/usr/bin/env python3
"""Read-only IBKR metals research adapter. Local snapshots only; no networking/orders."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/research/C35_METALS_20261013"
INSTRUMENTS = {"PHAU":{"conid":44216217,"exchange":"AEB","currency":"EUR"},
               "PHAG":{"conid":44216214,"exchange":"AEB","currency":"EUR"}}
MIN_ROWS = 303


def estimated_commission(notional):
    return max(1.25, notional*.0005) if notional > 0 else 0.


def affordable_units(budget, price):
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Cijena mora biti pozitivna i konačna")
    units=max(0,math.floor(budget/price))
    while units and units*price+estimated_commission(units*price)>budget:
        units-=1
    return units


def validate(rows, cutoff):
    errors=[]
    parsed=[]
    for i,row in enumerate(rows,2):
        try:
            date=dt.date.fromisoformat(str(row["date"])[:10])
            values={k:float(row[k]) for k in ("open","high","low","close","volume")}
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError("Nekonačan broj")
            if min(values[k] for k in ("open","high","low","close"))<=0 or values["volume"]<0:
                raise ValueError("Nevažeća cijena ili volumen")
            if not (values["low"]<=values["open"]<=values["high"] and values["low"]<=values["close"]<=values["high"]):
                raise ValueError("Open/close izvan low/high")
            if date>cutoff:
                raise ValueError("Budući red u odnosu na as-of; ne koristi se")
            parsed.append({"date":date,**values})
        except (KeyError,TypeError,ValueError) as exc:
            errors.append(f"Red {i}: {exc}")
    dates=[r["date"] for r in parsed]
    if dates != sorted(dates) or len(set(dates))!=len(dates):
        errors.append("Datumi nisu sortirani ili postoje duplikati")
    if len(parsed)<MIN_ROWS:
        errors.append(f"Nedovoljna povijest: {len(parsed)} valjanih redova; potrebno najmanje {MIN_ROWS}")
    if not dates:
        errors.append("Nema valjanih dnevnih podataka")
    elif (cutoff-max(dates)).days>7:
        errors.append("Posljednji zapis stariji je od sedam kalendarskih dana")
    if len(parsed)>=253:
        # Duplicate-free row count alone cannot certify a complete trading calendar.
        span=(parsed[-1]["date"]-parsed[-253]["date"]).days
        if span<300 or span>450:
            errors.append("252 sesije imaju neuobičajen kalendarski raspon; provjeriti pokriće")
    return parsed,errors


def inspect(path, symbol, cutoff, capital):
    warnings=["Snapshot nije neovisno verificiran izravnim broker podatkovnim auditom.",
              "Nema potvrde potpunosti burzovnog kalendara ni corporate-action prilagodbi.",
              "Conid i AEB/EUR mapiranje fiksirani su za istraživanje; nisu aktualna provjera izvršivosti kod brokera."]
    try:
        with path.open(newline="") as f:
            raw=list(csv.DictReader(f))
        rows,errors=validate(raw,cutoff)
    except (OSError,csv.Error) as exc:
        rows,errors=[],[f"Snapshot nije čitljiv: {exc}"]
    valid=not errors
    features=None
    affordability=None
    if valid:
        close=rows[-1]["close"]
        previous=rows[:-1]
        features={"last_close_eur":close,"last_date":str(rows[-1]["date"]),
                  "momentum_252_positive":close>rows[-253]["close"],
                  "momentum_252_reference_close":rows[-253]["close"],
                  "close_above_prior_55_closes":close>max(r["close"] for r in previous[-55:]),
                  "close_below_prior_20_closes":close<min(r["close"] for r in previous[-20:]),
                  "monthly_schedule":"Momentum je opisno stanje; mjesečna odluka zahtijeva potvrđen zadnji trgovinski dan mjeseca.",
                  "classification":"Značajke istraživanja, nisu kupovni signali"}
        budget=capital*.5
        units=affordable_units(budget,close)
        notional=units*close
        affordability={"illustrative_budget_eur":budget,"reference_close_eur":close,
                       "whole_units_mathematically_affordable":units,
                       "estimated_entry_cost_eur":notional+estimated_commission(notional),
                       "estimated_commission_eur":estimated_commission(notional),
                       "is_order":False,
                       "limitation":"Račun iz zadnje povijesne cijene; nema spreada, slippagea ni jamstva cijene. Nije nalog."}
    return {"symbol":symbol,**INSTRUMENTS[symbol],"snapshot":str(path),
            "data_status":"UNVERIFIED_VALID_SHAPE" if valid else "DATA_INVALID",
            "snapshot_valid_for_features":valid,"valid_rows":len(rows),
            "coverage_start":str(rows[0]["date"]) if rows else None,
            "coverage_end":str(rows[-1]["date"]) if rows else None,
            "errors":errors,"metadata_warnings":warnings,"features":features,
            "affordability_example":affordability,"planned_order_quantity":0,
            "action":"PRIČEKAJ","no_trade_authority":True,
            "research_candidates":{"MOM252":"research_failed_C35_WF","BREAKOUT55_20":"research_failed_C35_WF",
                                   "ORB30":"unavailable_daily_only; research_failed_C35_WF"}}


def self_test():
    cutoff=dt.date(2026,10,12)
    dates=[]; day=cutoff
    while len(dates)<310:
        if day.weekday()<5: dates.append(day)
        day-=dt.timedelta(days=1)
    rows=[dict(date=str(d),open=100,high=102,low=99,close=101,volume=500) for d in reversed(dates)]
    assert not validate(rows,cutoff)[1]
    bad=[dict(r) for r in rows]; bad[3]["close"]=103
    assert validate(bad,cutoff)[1]
    future=[dict(r) for r in rows]; future[-1]["date"]=str(cutoff+dt.timedelta(days=1))
    assert validate(future,cutoff)[1]
    assert validate(rows[:107],cutoff)[1]
    for budget in (250,500,1000):
        for price in (1.,49.9,100.,249.,500.):
            q=affordable_units(budget,price)
            assert q*price+estimated_commission(q*price)<=budget+1e-9
            assert (q+1)*price+estimated_commission((q+1)*price)>budget
    print("SELF-TEST PASS: valjana povijest, OHLC odbijanje, budući red, kratka povijest, izračun bez prekoračenja budžeta")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",help="Obvezan datum vrednovanja YYYY-MM-DD; ne pretpostavlja se danas")
    p.add_argument("--capital-eur",type=float,default=1000.)
    p.add_argument("--input-dir",type=Path,default=BASE)
    p.add_argument("--output",type=Path,default=BASE/"ibkr_readonly_signal.json")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:
        self_test(); return
    if not a.as_of: p.error("--as-of je obvezan")
    try: cutoff=dt.date.fromisoformat(a.as_of)
    except ValueError: p.error("--as-of mora biti YYYY-MM-DD")
    if not math.isfinite(a.capital_eur) or not 500<=a.capital_eur<=2000:
        p.error("--capital-eur mora biti u rasponu 500–2000 EUR")
    paths={s:a.input_dir/f"IBKR_UNVALIDATED_{s}.csv" for s in INSTRUMENTS}
    target=a.output.resolve()
    if target in {v.resolve() for v in paths.values()} or "approved_list" in target.name:
        p.error("Izlaz ne smije zamijeniti podatke ili approved_list")
    instruments=[inspect(path,s,cutoff,a.capital_eur) for s,path in paths.items()]
    report={"as_of":str(cutoff),"mode":"LOCAL_SNAPSHOT_READ_ONLY","action":"PRIČEKAJ",
            "no_trade_authority":True,"capital_eur":a.capital_eur,
            "cash_plan_eur":a.capital_eur,"planned_orders":[],
            "reason":"C35 WF kandidati nisu prošli istraživačka vrata; PHAU/PHAG nemaju validiran backtest.",
            "commission_assumption":"Ilustrativno po strani max(1.25 EUR, 0.05% vrijednosti); nije potvrđena aktualna IBKR tarifa. Burzovne/druge naknade isključene.",
            "instruments":instruments}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    print(f"PRIČEKAJ · lokalna simulacija · datum {cutoff} · kapital {a.capital_eur:.2f} EUR")
    print("Plan: sav kapital u gotovini; količina svih naloga 0. Nema ovlasti trgovanja.")
    for x in instruments:
        print(f"{x['symbol']}: {x['valid_rows']} valjanih redova · značajke {'dostupne' if x['snapshot_valid_for_features'] else 'BLOKIRANE'}")
        for error in x["errors"][:6]: print(f"  - {error}")
    print(f"JSON: {a.output}")


if __name__ == "__main__": main()
