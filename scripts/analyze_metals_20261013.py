#!/usr/bin/env python3
"""Postprocess C35 frozen research; never rerun/select a strategy or contact a broker.

Bootstrap resamples observed DAILY portfolio returns in circular blocks of five
sessions. It is NOT strategy re-execution and NOT trade-level resampling.
It preserves only short local dependence, not complete regimes or execution paths.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

STRATEGIES = ("MOM252", "BREAKOUT", "ORB30", "BUYHOLD")
SEED = 20261013


def curve(path):
    x = pd.read_csv(path, index_col="date")
    x.index = x.index.astype(str)
    if x.empty or x.index.has_duplicates or not x.index.is_monotonic_increasing:
        raise ValueError(f"Invalid curve: {path}")
    if not np.isfinite(x.equity).all() or (x.equity <= 0).any():
        raise ValueError(f"Invalid equity: {path}")
    return x


def returns(x, capital):
    return np.diff(np.r_[capital, x.equity.to_numpy()]) / np.r_[capital, x.equity.to_numpy()[:-1]]


def block_bootstrap(r, rng, samples=2000, block=5):
    """Circular moving-block bootstrap of realized daily net portfolio returns."""
    n = len(r)
    if n < block:
        return {"available": False, "reason": "Fewer observations than block length"}
    drawdowns, totals = [], []
    offsets = np.arange(block)
    for _ in range(samples):
        starts = rng.integers(0, n, size=(n+block-1)//block)
        indices = ((starts[:,None]+offsets[None,:]) % n).ravel()[:n]
        wealth = np.r_[1., np.cumprod(1+r[indices])]
        drawdowns.append(float(1-np.min(wealth/np.maximum.accumulate(wealth))))
        totals.append(float(wealth[-1]-1))
    return {"available": True, "method": "circular moving blocks of realized daily portfolio returns",
            "samples": samples, "block_sessions": block, "observations": n,
            "max_drawdown_p05": float(np.quantile(drawdowns,.05)),
            "max_drawdown_median": float(np.quantile(drawdowns,.5)),
            "max_drawdown_p95": float(np.quantile(drawdowns,.95)),
            "total_return_p05": float(np.quantile(totals,.05)),
            "total_return_median": float(np.quantile(totals,.5)),
            "total_return_p95": float(np.quantile(totals,.95)),
            "negative_total_return_fraction": float(np.mean(np.array(totals)<0))}


def concentration(path):
    try:
        t = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        t = pd.DataFrame(columns=["pnl"])
    pnl = t.pnl.to_numpy(dtype=float) if len(t) else np.array([])
    kept = np.sort(pnl)[:-3] if len(pnl)>3 else np.array([])
    top = np.sort(pnl)[-min(3,len(pnl)):] if len(pnl) else np.array([])
    return {"closed_trades":len(pnl), "total_pnl_usd":float(pnl.sum()),
            "top3_pnl_usd":float(top.sum()), "remaining_trades":len(kept),
            "ex_top3_total_pnl_usd":float(kept.sum()) if len(kept) else None,
            "ex_top3_mean_pnl_usd":float(kept.mean()) if len(kept) else None,
            "ex_top3_positive":bool(kept.mean()>0) if len(kept) else None,
            "limitation":"Descriptive closed-trade dollar PnL; unequal compounded sizes. Not equity replay without top trades."}


def yearly(x, capital, strategy):
    r = returns(x, capital)
    rows = []
    prior = capital
    for year, group in x.groupby(x.index.str[:4]):
        mask = x.index.str[:4] == year
        rr = r[mask]
        wealth = np.r_[prior, group.equity.to_numpy()]
        sd = np.std(rr,ddof=1) if len(rr)>1 else 0.
        rows.append({"strategy":strategy,"year":year,"return_net":float(wealth[-1]/prior-1),
                     "max_drawdown_within_year":float(1-np.min(wealth/np.maximum.accumulate(wealth))),
                     "sharpe_daily":float(np.mean(rr)/sd*np.sqrt(252)) if sd>0 else 0.,
                     "sessions":len(group),"ending_equity_usd":float(wealth[-1]),
                     "exposure":float(group.exposure.mean()) if "exposure" in group else None})
        prior = float(wealth[-1])
    return rows


def figures(curves, out, capital):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        return {"available":False,"reason":str(exc)}
    colors = {"MOM252":"#137c66","BREAKOUT":"#e99634","ORB30":"#486bb0","BUYHOLD":"#757575"}
    labels = {"MOM252":"Mjesečni momentum","BREAKOUT":"Proboj 55/20","ORB30":"Proboj prvih 30 min","BUYHOLD":"Kupi i drži 50/50"}
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    outputs=[]
    for metric in ("equity","drawdown"):
        fig,ax=plt.subplots(figsize=(12,6),layout="constrained")
        for strategy,x in curves.items():
            if metric == "equity":
                y=x.equity
            else:
                wealth=np.r_[capital,x.equity.to_numpy()]
                y=(wealth/np.maximum.accumulate(wealth)-1)[1:]*100
            ax.plot(pd.to_datetime(x.index),y,label=labels[strategy],color=colors[strategy],lw=1.5)
        ax.set_title("Zlato i srebro · neto simulirana vrijednost portfelja" if metric=="equity" else "Zlato i srebro · pad od prethodnog vrha")
        ax.set_ylabel("USD" if metric=="equity" else "Pad (%)")
        ax.grid(alpha=.15)
        ax.legend(loc="best",frameon=False)
        fig.text(.01,-.025,"Istraživanje · frakcijske dionice · gotovina bez kamata · povijesni rezultat nije prognoza",fontsize=8,color="#555555")
        for extension in ("png","svg"):
            path=out/f"metals_{metric}.{extension}"
            fig.savefig(path,dpi=180,bbox_inches="tight")
            outputs.append(str(path))
        plt.close(fig)
    return {"available":True,"files":outputs}


def euro_valuation(curves, fx_path, out, capital):
    """Ex-post end-of-day valuation; no strategy signal or ranking changes."""
    fx=pd.read_csv(fx_path)
    fx["fx_date"]=pd.to_datetime(fx["date"])
    fx=fx[["fx_date","usd_per_eur"]].sort_values("fx_date")
    if fx.fx_date.duplicated().any() or not np.isfinite(fx.usd_per_eur).all() or (fx.usd_per_eur<=0).any():
        raise ValueError("Invalid or duplicate ECB FX data")
    result={"method":"USD equity / nearest same-or-earlier ECB USD per EUR; end-of-day valuation only",
            "initial_usd":capital,"strategies":{},
            "example_limitation":"Proportional EUR examples include baseline modeled trading friction only. Actual fixed/minimum commissions, share indivisibility, FX conversion fees and taxes are excluded; these are descriptive historical scale examples, not forecasts.",
            "initial_valuation_limitation":"Initial USD is converted at first sample day's ECB reference rate, treated as valuation anchor; no executable open-time FX conversion is assumed."}
    plots={}
    for strategy,x in curves.items():
        left=x.reset_index(); left["date"]=pd.to_datetime(left["date"])
        joined=pd.merge_asof(left.sort_values("date"),fx,left_on="date",right_on="fx_date",direction="backward",allow_exact_matches=True)
        lag=(joined.date-joined.fx_date).dt.days
        if joined.usd_per_eur.isna().any() or (lag<0).any() or (lag>7).any():
            raise ValueError(f"Missing, future or >7-day-stale FX for {strategy}")
        initial_eur=capital/float(joined.usd_per_eur.iloc[0])
        eur=joined.equity.to_numpy()/joined.usd_per_eur.to_numpy()
        wealth=np.r_[initial_eur,eur]
        years=max((joined.date.iloc[-1]-joined.date.iloc[0]).days/365.25,1/365.25)
        joined=joined.rename(columns={"equity":"equity_usd"})
        joined["fx_lag_days"]=lag
        joined["equity_eur"]=eur
        joined["eur_index_100"]=eur/initial_eur*100
        for initial in (500,1000,2000):
            joined[f"example_initial_{initial}_eur"]=eur/initial_eur*initial
        joined.to_csv(out/f"{strategy}_full_eur_valuation.csv",index=False)
        result["strategies"][strategy]={"initial_equivalent_eur":initial_eur,
            "initial_fx_date":str(joined.fx_date.iloc[0].date()),"initial_usd_per_eur":float(joined.usd_per_eur.iloc[0]),
            "final_equity_eur":float(eur[-1]),"total_return_eur":float(eur[-1]/initial_eur-1),
            "cagr_eur":float((eur[-1]/initial_eur)**(1/years)-1),
            "max_drawdown_eur":float(1-np.min(wealth/np.maximum.accumulate(wealth))),
            "maximum_fx_lag_days":int(lag.max()),
            "descriptive_examples_final_eur":{str(v):float(eur[-1]/initial_eur*v) for v in (500,1000,2000)}}
        plots[strategy]=joined
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(12,6),layout="constrained")
        for strategy,j in plots.items():
            ax.plot(j.date,j.eur_index_100,label=strategy,lw=1.5)
        ax.axhline(100,color="#999999",lw=.7,ls="--")
        ax.set_title("Zlato i srebro · vrijednost u eurima, početna vrijednost 100")
        ax.set_ylabel("Indeks vrijednosti u EUR")
        ax.grid(alpha=.15); ax.legend(frameon=False)
        fig.text(.01,-.025,"ECB tečaj istog ili ranijeg datuma · naknadno vrednovanje · ne mijenja strategiju ni izbor",fontsize=8)
        for extension in ("png","svg"):
            fig.savefig(out/f"metals_equity_eur.{extension}",dpi=180,bbox_inches="tight")
        plt.close(fig)
        result["figure_available"]=True
    except ImportError as exc:
        result["figure_available"]=False
        result["figure_error"]=str(exc)
    (out/"eur_valuation.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",default="reports/backtest/C35_METALS_20261013")
    p.add_argument("--output",default="reports/research/C35_METALS_20261013")
    p.add_argument("--capital",type=float,default=10000.)
    p.add_argument("--fx",default="reports/research/C35_METALS_20261013/ecb_usd_per_eur.csv")
    p.add_argument("--samples",type=int,default=2000)
    args=p.parse_args()
    if args.samples<2000 or args.capital<=0:
        p.error("At least 2000 bootstrap samples and positive capital required")
    base,out=Path(args.base),Path(args.output)
    # Both stages must exist before any postprocessing or output write.
    for stage in ("development","holdout"):
        if not (base/f"{stage}_c1_p1.json").is_file():
            raise FileNotFoundError(f"Missing completed baseline stage: {stage}")
    result={"seed":SEED,"capital":args.capital,"strategies":{},
            "DSR":{"computed":False,"local_K_before":377,"registered_configs":24,"local_K_after":401,"reason":"Not computed: no validated statistical implementation; global campaign multiplicity and independent parameter-trial accounting are unresolved. Local ledger K does not resolve those assumptions."},
            "PBO":{"computed":False,"reason":"Not computed: no validated purged combinatorial variant-matrix selection analysis."},
            "bootstrap_limitation":"Daily realized portfolio return blocks of length5, not trade bootstrap or strategy re-execution; does not model full regimes, liquidity, future gaps or new execution costs. Descriptive uncertainty only, not Critic PASS."}
    rng=np.random.default_rng(SEED)
    curves,year_rows={},[]
    for strategy in STRATEGIES:
        full_path=base/f"holdout_{strategy}_FULL_c1_p1_equity.csv"
        if not full_path.exists():
            result["strategies"][strategy]={"available":False,"reason":"Baseline full curve missing"}
            continue
        x=curve(full_path); curves[strategy]=x
        year_rows.extend(yearly(x,args.capital,strategy))
        item={"available":True,"periods":{}}
        for stage,period in (("development","WF"),("holdout","HO"),("holdout","FULL")):
            stem=base/f"{stage}_{strategy}_{period}_c1_p1"
            e=curve(Path(str(stem)+"_equity.csv"))
            item["periods"][period]={"start":e.index[0],"end":e.index[-1],
                "bootstrap":block_bootstrap(returns(e,args.capital),rng,args.samples),
                "concentration":concentration(Path(str(stem)+"_trades.csv"))}
        result["strategies"][strategy]=item
    out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(year_rows).to_csv(out/"yearly_metrics.csv",index=False)
    result["figures"]=figures(curves,out,args.capital)
    result["eur_valuation"]=euro_valuation(curves,Path(args.fx),out,args.capital)
    (out/"robustness.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps({"output":str(out),"figures":result["figures"],"strategies":list(curves)},indent=2))


if __name__ == "__main__":
    main()
