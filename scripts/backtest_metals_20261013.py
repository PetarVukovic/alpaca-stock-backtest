#!/usr/bin/env python3
"""Deterministic GLD/SLV research only; never connects to a broker.

Signals use completed bars. Two self-financing 50% sleeves, no leverage.
Incomplete intraday sessions are skipped, not imputed.
Terminal positions are liquidated at the final close with modeled costs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

START = "2016-10-13"
END = "2026-10-12"
SYMBOLS = ("GLD", "SLV")
MIN_FEE = 0.
COMMISSION_BPS = 0.

def commission(qty, price):
    return max(MIN_FEE, qty*price*COMMISSION_BPS/10000) if qty else 0.

def affordable(cash, price, multiplier):
    if cash <= MIN_FEE: return 0.
    return max(0., min((cash-MIN_FEE)/(price+friction(price,multiplier)),
                     cash/(price+friction(price,multiplier)+price*COMMISSION_BPS/10000)))


def load_daily(path):
    x = pd.read_csv(path)
    key = "date" if "date" in x else "timestamp" if "timestamp" in x else "ts"
    x["date"] = x[key].astype(str).str[:10]
    return x.set_index("date").sort_index()


def load_intraday(path):
    x = pd.read_csv(path)
    key = "ts" if "ts" in x else "timestamp"
    x["ts"] = pd.to_datetime(x[key], utc=True)
    local = x.ts.dt.tz_convert("America/New_York")
    x["date"] = local.dt.strftime("%Y-%m-%d")
    x["minute"] = local.dt.hour * 60 + local.dt.minute
    regular = x["session"].eq("regular") if "session" in x else pd.Series(True,index=x.index)
    return x[regular & (x.minute >= 570) & (x.minute < 960)].sort_values("ts")


def signals(x, kind, factor=1.):
    kind = "BREAKOUT" if kind == "BREAKOUT55" else kind
    if kind not in ("MOM252", "BREAKOUT", "BUYHOLD"):
        raise ValueError(f"Unknown swing strategy: {kind}")
    c = x.close
    if kind == "MOM252":
        n = round(252 * factor)
        desired = c > c.shift(n)
        # First session of a new month executes the preceding month's signal.
        month = pd.Index(x.index).str[:7]
        return pd.Series([np.nan if i == 0 or month[i] == month[i-1]
                          else float(desired.iloc[i-1]) if i-1 >= n else np.nan
                          for i in range(len(x))], index=x.index)
    if kind == "BREAKOUT":
        entry = c > c.shift(1).rolling(round(55*factor)).max()
        leave = c < c.shift(1).rolling(round(20*factor)).min()
        return pd.Series(np.where(entry, 1., np.where(leave, 0., np.nan)), index=x.index).shift(1)
    return pd.Series(1., index=x.index)


def friction(price, multiplier):
    return multiplier * (price * .00025 + .01)


def swing(x, kind, first, last, capital, multiplier=1., factor=1.):
    action = signals(x, kind, factor)
    cash, qty, entry = capital, 0., None
    rows, trades = [], []
    for date, bar in x.loc[first:last].iterrows():
        price = float(bar.open)
        signal = action.loc[date]
        if signal == 0 and qty:
            proceeds = qty*(price-friction(price, multiplier))-commission(qty,price)
            pnl = proceeds-entry["cost"]
            cash += proceeds
            trades.append(dict(entry_date=entry["date"], exit_date=date, entry_price=entry["price"],
                               exit_price=price, shares=qty, pnl=pnl, return_net=pnl/entry["cost"], reason="signal"))
            qty, entry = 0., None
        elif signal == 1 and qty == 0:
            qty = affordable(cash,price,multiplier)
            cost = qty*(price+friction(price,multiplier))+commission(qty,price)
            entry = dict(date=date, price=price, cost=cost) if qty else None
            cash -= cost
        value = cash + qty*float(bar.close)
        rows.append(dict(date=date, equity=value, exposure=qty*float(bar.close)/value if value else 0))
    if qty:
        price = float(x.loc[rows[-1]["date"],"close"])
        proceeds = qty*(price-friction(price,multiplier))-commission(qty,price)
        pnl = proceeds-entry["cost"]
        cash += proceeds
        trades.append(dict(entry_date=entry["date"],exit_date=rows[-1]["date"],entry_price=entry["price"],exit_price=price,shares=qty,pnl=pnl,return_net=pnl/entry["cost"],reason="terminal_close"))
        rows[-1]["equity"] = cash
    return pd.DataFrame(rows).set_index("date"), trades, {"open_position": False}


def orb(x, calendar, first, last, capital, multiplier=1., factor=1.):
    cash, rows, trades, skipped = capital, [], [], 0
    skipped_details = []
    groups = {d:g for d,g in x.groupby("date")}
    opening_bars = round(6*factor)
    for date in calendar:
        if not first <= date <= last:
            continue
        g = groups.get(date)
        exposure = 0.
        complete = False
        reasons = []
        if g is not None and len(g):
            last_minute = int(g.iloc[-1].minute)
            end_flag = str(g.iloc[-1].get("session_end", last_minute == 955)).lower() in ("true","1","1.0")
            if not end_flag: reasons.append("missing_session_end")
            if last_minute not in (775,955): reasons.append("unexpected_last_bar")
            if g.minute.tolist() != list(range(570,last_minute+1,5)):
                reasons.append("missing_duplicate_or_off_grid_bars")
            if not (g.volume>0).all(): reasons.append("nonpositive_or_missing_volume")
            complete = not reasons
        else:
            reasons.append("no_regular_bars")
        if not complete:
            skipped += 1
            skipped_details.append({"date":str(date), "reasons":reasons,
                                    "observed_bars":0 if g is None else len(g)})
        else:
            g = g.reset_index(drop=True)
            high, stop = float(g.iloc[:opening_bars].high.max()), float(g.iloc[:opening_bars].low.min())
            for i in range(opening_bars, len(g)-1):
                # Close timestamp must precede noon; next bar executes signal.
                if int(g.iloc[i].minute)+5 >= 720:
                    break
                if float(g.iloc[i].close) <= high:
                    continue
                j = i+1
                entry = float(g.iloc[j].open)
                if entry <= stop:
                    break
                per_share_risk = entry-stop + friction(entry,multiplier)+friction(stop,multiplier)
                # Sleeve starts at half portfolio: 0.5% sleeve risk ~0.25% portfolio.
                qty = min(affordable(cash,entry,multiplier), cash*.005/per_share_risk)
                # Include commissions in risk sizing; solve monotone risk inequality.
                lo,hi = 0.,qty
                for _ in range(40):
                    mid=(lo+hi)/2
                    risk=mid*per_share_risk+commission(mid,entry)+commission(mid,stop)
                    if risk <= cash*.005: lo=mid
                    else: hi=mid
                qty=lo
                if qty < 1e-12: break
                cost = qty*(entry+friction(entry,multiplier))+commission(qty,entry)
                exit_price, k, reason = float(g.iloc[-1].open), len(g)-1, "session_end"
                for k0 in range(j, len(g)-1):
                    b = g.iloc[k0]
                    if float(b.open) <= stop:
                        exit_price, k, reason = float(b.open), k0, "gap_stop"
                        break
                    if float(b.low) <= stop:
                        exit_price, k, reason = stop, k0, "stop"
                        break
                pnl = qty*(exit_price-friction(exit_price,multiplier))-commission(qty,exit_price)-cost
                before = cash
                cash += pnl
                # Same-bar stops have unknown intrabar duration: use one bar proxy.
                exposure = cost/before * max(1,k-j)/len(g)
                trades.append(dict(entry_date=date, exit_date=date, entry_time=str(g.iloc[j].ts),
                                   exit_time=str(g.iloc[k].ts), entry_price=entry, exit_price=exit_price,
                                   shares=qty, pnl=pnl, return_net=pnl/cost, reason=reason))
                break
        rows.append(dict(date=date, equity=cash, exposure=exposure))
    return pd.DataFrame(rows).set_index("date"), trades, {
        "skipped_sessions": skipped, "skipped_session_details":skipped_details,
        "open_position": False}


def metrics(e, trades, capital):
    returns = e.equity.pct_change()
    returns.iloc[0] = e.equity.iloc[0]/capital-1
    years = max((pd.Timestamp(e.index[-1])-pd.Timestamp(e.index[0])).days/365.25, 1/365.25)
    wealth = np.r_[capital, e.equity.to_numpy()]
    drawdown = wealth/np.maximum.accumulate(wealth)-1
    pnl = np.array([t["pnl"] for t in trades])
    loss = -pnl[pnl<0].sum()
    return dict(start=e.index[0], end=e.index[-1], total_return=float(wealth[-1]/capital-1),
                cagr=float((wealth[-1]/capital)**(1/years)-1),
                sharpe=float(returns.mean()/returns.std(ddof=1)*np.sqrt(252)) if returns.std(ddof=1)>0 else 0.,
                max_drawdown=float(-drawdown.min()), trades=len(trades),
                win_rate=float((pnl>0).mean()) if len(pnl) else None,
                profit_factor=float(pnl[pnl>0].sum()/loss) if loss else None,
                exposure=float(e.exposure.mean()), ending_equity=float(wealth[-1]))


def run(args):
    global MIN_FEE, COMMISSION_BPS
    MIN_FEE, COMMISSION_BPS = args.min_fee, args.commission_bps
    if args.only_strategy == "BREAKOUT55": args.only_strategy = "BREAKOUT"
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    selection_path = Path(args.selection_file or out/"selection.json")
    if args.stage == "holdout":
        selection = json.loads(selection_path.read_text())
        if selection.get("stage") != "development":
            raise ValueError("Selection must come from development")
    daily = {s:load_daily(Path(args.daily_dir)/f"{s}_1d.csv") for s in SYMBOLS}
    intraday = {}
    intraday_paths = {}
    for s in SYMBOLS:
        options = [Path(args.intraday_dir)/f"{s}_{suffix}.csv" for suffix in ("5m_clean", "5min", "5m")]
        p = next((p for p in options if p.exists()), None)
        if p is not None:
            intraday[s] = load_intraday(p)
            intraday_paths[s] = p
    if (not args.only_strategy or args.only_strategy == "ORB30") and len(intraday) != len(SYMBOLS):
        raise ValueError("Missing intraday data for ORB; refusing incomplete candidate selection")
    periods = {"IS":(START,"2020-12-31"), "WF":("2021-01-01","2023-12-31")} if args.stage == "development" else {"HO":("2024-01-01",END), "FULL":(START,END)}
    result = {"stage":args.stage, "capital":args.capital, "cost_multiplier":args.cost_multiplier,
              "min_fee":MIN_FEE,"commission_bps":COMMISSION_BPS,"parameter_factor":args.sensitivity, "results":{}, "limitations":[
                  "Self-financing 50% initial sleeves; weights drift, no portfolio rebalancing.",
                  "ORB risk is 0.5% current sleeve equity; equals 0.25% total only when sleeves equal.",
                  "ORB exposure is a coarse 5-minute duration proxy; same-entry-bar stops count one bar because exact intrabar duration is unknown.",
                  "Only complete regular sessions with 42 or 78 bars; incomplete sessions skipped.",
                  "ORB uses retrospective whole-session data-quality filtering: later missing/invalid bars can exclude an earlier trade. This is complete-case selection bias, not a live-executable filter; excluded dates/reasons are recorded.",
                  "Fractional shares; zero cash yield; taxes and FX excluded; OHLC fills are uncertain.",
                  "Terminal positions liquidated at last close with fees; idealized known boundary execution.",
                  "Independent segment runs start flat; FULL is descriptive, never selection evidence. Exchange fees excluded."]}
    candidates = ["MOM252", "BREAKOUT", "ORB30", "BUYHOLD"]
    if args.only_strategy:
        candidates = [args.only_strategy, "BUYHOLD"]
    for kind in candidates:
        if kind == "ORB30" and len(intraday) != 2: continue
        result["results"][kind] = {}
        for period,(first,last) in periods.items():
            curves, all_trades, details = [], [], {}
            for s in SYMBOLS:
                if kind == "ORB30":
                    e, ts, extra = orb(intraday[s], daily[s].index, first,last,args.capital/2,args.cost_multiplier,args.sensitivity)
                else:
                    e, ts, extra = swing(daily[s], kind, first,last,args.capital/2,args.cost_multiplier,args.sensitivity)
                if e.empty: raise ValueError(f"No rows: {s} {period}")
                for t in ts: t["symbol"] = s
                all_trades += ts
                details[s] = {**metrics(e,ts,args.capital/2), **extra}
                curves.append(e)
            if not curves[0].index.equals(curves[1].index):
                raise ValueError("Daily calendars mismatch: validate data first")
            combined = pd.DataFrame({"equity":curves[0].equity+curves[1].equity,
                         "exposure":(curves[0].exposure*curves[0].equity+curves[1].exposure*curves[1].equity)/(curves[0].equity+curves[1].equity)})
            stem = f"{args.stage}_{kind}_{period}_c{args.cost_multiplier:g}_p{args.sensitivity:g}"
            combined.to_csv(out/f"{stem}_equity.csv")
            pd.DataFrame(all_trades).to_csv(out/f"{stem}_trades.csv",index=False)
            annual = combined.equity.groupby(combined.index.str[:4]).last()
            yr = annual.pct_change(); yr.iloc[0] = annual.iloc[0]/args.capital-1
            yr.rename("return").to_csv(out/f"{stem}_yearly.csv")
            result["results"][kind][period] = {**metrics(combined,all_trades,args.capital),"symbols":details}
    if args.stage == "development" and args.cost_multiplier == 1 and args.sensitivity == 1 and not args.only_strategy and MIN_FEE == 0 and COMMISSION_BPS == 0:
        eligible = [[v["WF"]["sharpe"],k] for k,v in result["results"].items()
                    if k != "BUYHOLD" and v["WF"]["sharpe"]>0 and v["WF"]["total_return"]>0 and v["WF"]["max_drawdown"]<=.25 and v["WF"]["trades"]>=10]
        selection = dict(stage="development", winner=max(eligible)[1] if eligible else None,
                         rule="WF total return>0, Sharpe>0, max drawdown<=25%, closed trades>=10; rank Sharpe", eligible=eligible)
        if selection_path.exists():
            old = json.loads(selection_path.read_text())
            if old != selection: raise ValueError("Refusing to overwrite changed frozen selection")
        else:
            selection_path.write_text(json.dumps(selection,indent=2))
    result["selection"] = locals().get("selection")
    result["source_sha256"] = {s:hashlib.sha256((Path(args.daily_dir)/f"{s}_1d.csv").read_bytes()).hexdigest() for s in SYMBOLS}
    result["intraday_sha256"] = {s:hashlib.sha256(p.read_bytes()).hexdigest() for s,p in intraday_paths.items()}
    target = out/f"{args.stage}_c{args.cost_multiplier:g}_p{args.sensitivity:g}.json"
    target.write_text(json.dumps(result,indent=2,allow_nan=False))
    print(target)


def self_test():
    dates = pd.bdate_range("2018-01-01",periods=500).strftime("%Y-%m-%d")
    x = pd.DataFrame({"open":np.arange(500)+100., "close":np.arange(500)+100.},index=dates)
    for kind in ("MOM252","BREAKOUT"):
        whole=signals(x,kind)
        pd.testing.assert_series_equal(whole.iloc[:350],signals(x.iloc[:350],kind))
        changed=x.copy(); changed.iloc[350:]=1e9
        pd.testing.assert_series_equal(whole.iloc[:350],signals(changed,kind).iloc[:350])
    sig=signals(x,"BREAKOUT")
    assert sig.iloc[:56].isna().all() and sig.iloc[56] == 1
    ts=pd.date_range("2020-01-02 14:30",periods=78,freq="5min",tz="UTC")
    g=pd.DataFrame({"ts":ts,"date":"2020-01-02","minute":range(570,960,5),"open":101.,"high":102.,"low":100.,"close":101.,"volume":1000})
    g.loc[6,"close"]=103.; g.loc[7,["open","high","low"]]=[103.,104.,102.]
    g.loc[8,["open","high","low"]]=[99.,100.,98.]
    _,tr,_=orb(g,["2020-01-02"],"2020-01-02","2020-01-02",5000)
    assert tr[0]["entry_time"] == str(ts[7]) and tr[0]["exit_price"] == 99 and tr[0]["reason"] == "gap_stop"
    early=g.iloc[:42].copy(); early["session_end"]=False; early.loc[41,"session_end"]=True
    _,et,extra=orb(early,["2020-01-02"],"2020-01-02","2020-01-02",5000)
    assert len(et)==1 and extra["skipped_sessions"]==0
    _,_,extra=orb(early.iloc[:-1],["2020-01-02"],"2020-01-02","2020-01-02",5000)
    assert extra["skipped_sessions"]==1
    global MIN_FEE,COMMISSION_BPS
    MIN_FEE,COMMISSION_BPS=1.375,5
    q=affordable(275.,100.,1.)
    assert q*(100.+friction(100.,1.))+commission(q,100.) <= 275.+1e-9
    # A full simulated trade must remain affordable after entry AND exit fees.
    fee_curve,fee_trades,_=orb(g,["2020-01-02"],"2020-01-02","2020-01-02",1100.)
    t=fee_trades[0]
    entry_cost=t["shares"]*(t["entry_price"]+friction(t["entry_price"],1.))+commission(t["shares"],t["entry_price"])
    assert entry_cost <= 1100.+1e-9 and fee_curve.equity.min()>=0
    risk=t["shares"]*(t["entry_price"]-100.+friction(t["entry_price"],1.)+friction(100.,1.))+commission(t["shares"],t["entry_price"])+commission(t["shares"],100.)
    assert risk <= 1100.*.005+1e-9
    MIN_FEE,COMMISSION_BPS=0.,0.
    samebar=g.copy(); samebar.loc[7,"low"]=99.
    _,st,_=orb(samebar,["2020-01-02"],"2020-01-02","2020-01-02",5000)
    assert st[0]["entry_time"]==st[0]["exit_time"] and st[0]["exit_price"]==100. and st[0]["reason"]=="stop"
    print("Self-test PASS: signal lag, truncation, future corruption, next-bar ORB, gap/same-bar stop, early close, incomplete session, commission affordability/risk")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--daily-dir",default="data/ohlcv")
    p.add_argument("--intraday-dir",default="data/intraday")
    p.add_argument("--output-dir",default="reports/backtest/metals_20261013")
    p.add_argument("--selection-file")
    p.add_argument("--stage",choices=["development","holdout"],default="development")
    p.add_argument("--capital","--initial-cash",dest="capital",type=float,default=10000)
    p.add_argument("--min-fee",type=float,default=0)
    p.add_argument("--commission-bps",type=float,default=0)
    p.add_argument("--only-strategy",choices=["MOM252","BREAKOUT","BREAKOUT55","ORB30"])
    p.add_argument("--cost-multiplier",type=float,default=1)
    p.add_argument("--sensitivity",type=float,default=1)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.capital <= 0 or min(a.min_fee,a.commission_bps,a.cost_multiplier) < 0 or a.sensitivity <= 0:
        p.error("Capital and sensitivity must be positive; costs nonnegative")
    self_test() if a.self_test else run(a)
