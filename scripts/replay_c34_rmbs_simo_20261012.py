"""Fixed-window C34/C13C diagnostic; no brokerage calls or parameter search."""
import sys, json, hashlib, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from lab.data import load_bars
from lab.research.c34_accounts import replay
from lab.research.memory_swing import metrics
from scripts.run_memory_swing import fx_table,fx_rate,write_json
from lab.ledger import register_strategy,current_k
ID='C34_RMBS_SIMO_20261012'
OUT=ROOT/'reports/backtest'/ID
FREEZE=ROOT/'strategies/frozen/2026-10-12_C34_RMBS_SIMO.json'

def main():
 cfg=json.loads(FREEZE.read_text())
 for p,h in cfg['hashes'].items():
  assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
 OUT.mkdir(exist_ok=True)
 subprocess.run([sys.executable,'scripts/validate_data.py','--through','2026-10-09','--report',str(OUT/'DATA_CHECK.md')],cwd=ROOT,check=True)
 digest=hashlib.sha256(FREEZE.read_bytes()).hexdigest()
 for s in cfg['symbols']:
  for size in cfg['sizes']:
   register_strategy(ID+'_'+s+'_'+size,digest,purpose='fixed-window diagnostic, no parameter change, research only')
 rates=fx_table(ROOT/cfg['fx'])
 assert str(rates.index[-1].date())>='2026-10-09'
 result={};audit={}
 for s in cfg['symbols']:
  frame=load_bars(s,through='2026-10-09')
  assert str(frame.index[-1].date())=='2026-10-09'
  for period,(start,end) in cfg['periods'].items():
   dates=frame.loc[start:end].index
   fx=pd.Series([fx_rate(rates,d) for d in dates],index=dates)
   capital=599.4*fx_rate(rates,dates[0],before=True)
   for size in cfg['sizes']:
    for case in (['BASE','COST2','STOP100BPS'] if period=='RECENT' else ['BASE']):
     key=f'{s}_{size}_{period}_{case}'
     args=dict(capital=capital,fractional=size=='fractional',stress=2 if case=='COST2' else 1,exit_bps=100 if case=='STOP100BPS' else 0)
     raw=replay({s:frame},dates,**args);eur=raw['curve']/fx
     row=metrics(eur,600,raw['trades'])
     row.update(start=str(dates[0].date()),end=str(dates[-1].date()),open_position=raw['open_position'],costs_usd=raw['fees_usd']+raw['slippage_usd'])
     previous=600;row['annual']=[]
     for year,part in eur.groupby(eur.index.year):
      row['annual'].append(dict(year=int(year),return_pct=100*(part.iloc[-1]/previous-1),final=float(part.iloc[-1])))
      previous=float(part.iloc[-1])
     bh=replay({s:frame},dates,**args,passive=True)
     row['buyhold_final_eur']=float(bh['curve'].iloc[-1]/fx.iloc[-1])
     if period=='RECENT' and case=='BASE':
      checks=[]
      for cut in ['2024-12-31','2025-12-31','2026-06-30']:
       stamp=pd.Timestamp(cut,tz='UTC');past=dates[dates<=stamp]
       short=replay({s:frame.loc[:stamp]},past,**args)
       changed=frame.copy();changed.loc[changed.index>stamp,['open','high','low','close']]*=2.713
       other=replay({s:changed},dates,**args)
       diff=max(float((short['curve']-raw['curve'].loc[past]).abs().max()),float((other['curve'].loc[past]-raw['curve'].loc[past]).abs().max()))
       events=[e for e in raw['events'] if e['date']<=cut]
       assert diff<1e-8 and events==short['events']==[e for e in other['events'] if e['date']<=cut]
       checks.append(dict(cut=cut,difference=diff))
      stops=pd.DataFrame(raw['stops'])
      assert stops.empty or all((g.stop.diff().dropna()>=-1e-8).all() for _,g in stops.groupby('entry_date'))
      cash=capital
      for e in raw['events']:
       cash+=(-e['qty']*e['price']-e['fee']) if e['side']=='buy' else e['qty']*e['price']-e['fee']
       assert abs(cash-e['cash'])<1e-7
      pos=raw['open_position'];marked=pos['quantity']*float(frame.loc[dates[-1],'close']) if pos else 0
      assert abs(cash+marked-float(raw['curve'].iloc[-1]))<1e-7
      audit[key]=dict(causality=checks,cash_reconciled=True,stop_monotonic=True,max_volume_fraction=raw['max_volume_fraction'],gap_dates=[t['exit_date'] for t in raw['trades'] if t['reason']=='gap_stop'])
     result[key]=row
     raw['curve'].rename('USD').to_frame().assign(EUR=eur).to_csv(OUT/f'{key}_equity.csv')
     pd.DataFrame(raw['trades']).to_csv(OUT/f'{key}_trades.csv',index=False)
     write_json(OUT/f'{key}_events.json',raw['events'])
 write_json(OUT/'summary.json',dict(config=cfg,k=current_k(),results=result,audit=audit,status='RESEARCH ONLY / NO PASS'))
 print(json.dumps({k:v for k,v in result.items() if '_RECENT_BASE' in k},indent=2,default=str))

if __name__=='__main__': main()
