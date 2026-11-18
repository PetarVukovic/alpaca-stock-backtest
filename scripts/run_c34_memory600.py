"""Reproducible, offline frozen 600 EUR C13C comparison."""
import sys, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from lab.data import load_bars
from lab.research.c34_accounts import replay
from lab.research.memory_swing import metrics
from scripts.run_memory_swing import fx_table,fx_rate,write_json
from lab.ledger import current_k

OUT=ROOT/'reports/backtest/C34_MEMORY_600EUR'

def main():
    cfg=json.loads((ROOT/'strategies/frozen/2026-10-11_C34_MEMORY_600EUR.json').read_text())
    for name,h in cfg['hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    OUT.mkdir(exist_ok=True)
    frames={s:load_bars(s,through='2026-10-08') for s in cfg['symbols']}
    rates=fx_table(ROOT/'reports/research/C13C_20261009/ecb-history.xml')
    results={}; audits={}
    for group in cfg['symbols']+['PORTFOLIO']:
      for size in cfg['sizes']:
       for period,(start,end) in cfg['periods'].items():
        if group=='SNDK' and period!='RECENT': continue
        dates=frames['MU'].loc[start:end].index
        subset={s:frames[s] for s in (cfg['symbols'] if group=='PORTFOLIO' else [group])}
        initial_fx=fx_rate(rates,dates[0],before=True)
        capital=599.4*initial_fx
        fx=pd.Series([fx_rate(rates,d) for d in dates],index=dates)
        for case in (cfg['recent_cases'] if period=='RECENT' else ['BASE']):
          key=f'{group}_{size}_{period}_{case}'
          args=dict(capital=capital,fractional=size=='fractional',stress=2 if case=='COST2' else 1,exit_bps=100 if case=='STOP100BPS' else 0)
          raw=replay(subset,dates,**args)
          eur=raw['curve']/fx
          row=metrics(eur,600,raw['trades'])
          row.update(group=group,size=size,period=period,case=case,initial_fx=initial_fx,final_usd=float(raw['curve'].iloc[-1]),
            costs_usd=raw['fees_usd']+raw['slippage_usd'],fees_usd=raw['fees_usd'],slippage_usd=raw['slippage_usd'],
            skipped=len(raw['skipped']),open_position=raw['open_position'],max_volume_fraction=raw['max_volume_fraction'],
            after_terminal_fx_fee_eur=float(eur.iloc[-1])*.999,realized_pnl_usd=sum(t['pnl_usd'] for t in raw['trades']))
          row['annual']=[]; previous=600
          for year,part in eur.groupby(eur.index.year):
            row['annual'].append(dict(year=int(year),final=float(part.iloc[-1]),return_pct=100*(float(part.iloc[-1])/previous-1)))
            previous=float(part.iloc[-1])
          row['usd_cash_final_eur']=capital/float(fx.iloc[-1])
          pnls=sorted(t['pnl_usd'] for t in raw['trades'])
          row['best_trade_usd']=max(pnls) if pnls else None
          row['ex_top3_usd']=sum(pnls[:-3]) if len(pnls)>3 else None
          if group!='PORTFOLIO':
            eligible=dates[dates>=max(subset[group].index[0],pd.Timestamp('2025-02-24',tz='UTC') if group=='SNDK' else dates[0])]
            b=replay(subset,eligible,**args,passive=True)
            row['buyhold_final_eur']=float(b['curve'].iloc[-1])/float(fx.iloc[-1])
          if period=='RECENT' and case=='BASE':
            checks=[]
            for cut in ['2025-03-31','2025-12-31','2026-06-30']:
              stamp=pd.Timestamp(cut,tz='UTC'); past=dates[dates<=stamp]
              short=replay({s:f.loc[:stamp] for s,f in subset.items()},past,**args)
              changed={s:f.copy() for s,f in subset.items()}
              rng=np.random.default_rng(34)
              for f in changed.values():
                mask=f.index>stamp
                f.loc[mask,['open','high','low','close']]*=rng.uniform(2.,4.)
              other=replay(changed,dates,**args)
              ev=[e for e in raw['events'] if e['date']<=cut]
              diff=max(float((short['curve']-raw['curve'].loc[past]).abs().max()),float((other['curve'].loc[past]-raw['curve'].loc[past]).abs().max()))
              assert diff<1e-8 and ev==short['events']==[e for e in other['events'] if e['date']<=cut]
              checks.append(dict(cut=cut,max_equity_difference=diff,events_equal=True))
            st=pd.DataFrame(raw['stops'])
            assert st.empty or all((g.stop.diff().dropna()>=-1e-8).all() for _,g in st.groupby(['ticker','entry_date']))
            cash=capital
            for e in raw['events']:
                cash+=(-e['qty']*e['price']-e['fee']) if e['side']=='buy' else (e['qty']*e['price']-e['fee'])
                assert abs(cash-e['cash'])<1e-7
            pos=raw['open_position']; marked=pos['quantity']*float(subset[pos['ticker']].loc[dates[-1],'close']) if pos else 0
            assert abs(cash+marked-float(raw['curve'].iloc[-1]))<1e-7
            assert raw['max_volume_fraction']<.01
            audits[key]=dict(causality=checks,monotonic_stops=True,cash_reconciled=True,max_participation=raw['max_volume_fraction'],
                            gaps=[t['exit_date'] for t in raw['trades'] if t['reason']=='gap_stop'])
            # Descriptive block bootstrap of daily EUR returns, not a forecast.
            ret=eur.pct_change().dropna().to_numpy(); rng=np.random.default_rng(340)
            dd=[]
            for _ in range(1000):
                starts=rng.integers(0,len(ret),int(np.ceil(len(ret)/20)))
                sampled=np.concatenate([ret[(a+np.arange(20))%len(ret)] for a in starts])[:len(ret)]
                path=np.r_[1,np.cumprod(1+sampled)]; dd.append(100*np.max(1-path/np.maximum.accumulate(path)))
            row['block_bootstrap_dd_p95']=float(np.percentile(dd,95))
          results[key]=row
          raw['curve'].rename('USD').to_frame().assign(EUR=eur).to_csv(OUT/f'{key}_equity.csv')
          pd.DataFrame(raw['trades']).to_csv(OUT/f'{key}_trades.csv',index=False)
          write_json(OUT/f'{key}_events.json',raw['events'])
    payload=dict(config=cfg,k=current_k(),results=results,audit=audits,
      limitations=['Alpaca CSV through Oct8; no new Oct9 bars','Hypothetical fractional eligibility and stop support','Generic fees, not verified IBKR tariff','Daily OHLC not historical bid/ask or tick path; no real fill reconciliation','No dividends/taxes/interest; adjusted WDC spin-off synthetic series, not actual SNDK distribution accounting','Seen history and selected surviving universe; not independent holdout','95% equity research sizing differs from original500USD cap; no leverage','No full DSR/PBO/sensitivity Critic PASS'])
    write_json(OUT/'summary.json',payload)
    print(json.dumps({k:{x:v[x] for x in ['final','return_pct','max_drawdown_pct','n_closed','costs_usd']} for k,v in results.items() if '_RECENT_BASE' in k},indent=2))

if __name__=='__main__': main()
