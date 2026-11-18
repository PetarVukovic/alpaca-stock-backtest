#!/usr/bin/env python3
"""EUR whole-unit GLD/SLV proxy research. Offline; no broker/order capabilities."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
SYMBOLS = ('GLD','SLV')
PERIODS = {'IS':('2016-10-13','2020-12-31'),'WF':('2021-01-01','2023-12-31'),'EXPOSED':('2024-01-01','2026-10-12'),'FULL':('2016-10-13','2026-10-12')}
VARIANTS = {'BASE':(1.,1.),'COST2':(2.,1.),'COST3':(3.,1.),'PARAM08':(1.,.8),'PARAM12':(1.,1.2)}
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_data(root, fx_path, currency='USD'):
    fx=pd.read_csv(fx_path); fx['date']=pd.to_datetime(fx.date)
    if fx.date.duplicated().any() or not (fx.usd_per_eur>0).all(): raise ValueError('Invalid FX')
    fx=fx.sort_values('date').rename(columns={'date':'fx_date'})
    data={}
    for symbol in SYMBOLS:
        x=pd.read_csv(Path(root)/f'{symbol}_1d.csv'); x['date']=pd.to_datetime(x.date)
        if x.date.duplicated().any() or not x.date.is_monotonic_increasing: raise ValueError('Invalid dates')
        a=x[['open','high','low','close']]
        if not np.isfinite(a).all().all() or (a<=0).any().any() or ((x.high<x[['open','close','low']].max(axis=1)) | (x.low>x[['open','close','high']].min(axis=1))).any(): raise ValueError('Invalid OHLC')
        x=pd.merge_asof(x,fx,left_on='date',right_on='fx_date',allow_exact_matches=False,direction='backward')
        if currency=='EUR': x['usd_per_eur']=1.; x['fx_date']=x.date-pd.Timedelta(days=1)
        if x.usd_per_eur.isna().any() or ((x.date-x.fx_date).dt.days>7).any(): raise ValueError('Missing/stale FX')
        x['open_eur']=x.open/x.usd_per_eur; x['close_eur']=x.close/x.usd_per_eur; x['currency_mode']=currency
        data[symbol]=x.set_index('date')
    if not data[SYMBOLS[0]].index.equals(data[SYMBOLS[1]].index): raise ValueError('Unmatched calendars')
    return data

def kama(c,n,slow):
    out=pd.Series(np.nan,index=c.index); seed=n-1
    if len(c)<=seed: return out
    out.iloc[seed]=c.iloc[:n].mean()
    noise=c.diff().abs().rolling(n).sum(); change=(c-c.shift(n)).abs()
    for i in range(n,len(c)):
        er=change.iloc[i]/noise.iloc[i] if noise.iloc[i]>0 else 0.
        sc=(er*(2/3-2/(slow+1))+2/(slow+1))**2
        out.iloc[i]=out.iloc[i-1]+sc*(c.iloc[i]-out.iloc[i-1])
    return out

def targets(data, family, scale=1.):
    idx=data[SYMBOLS[0]].index; out=pd.DataFrame(np.nan,index=idx,columns=SYMBOLS)
    n=lambda v:max(2,round(v*scale)); features={}
    for s,x in data.items():
        c=x.close_eur; vol=np.log(c).diff().rolling(n(20 if family=='KAMA' else 60)).std(ddof=1)*np.sqrt(252)
        sizing=(.10/vol).clip(upper=1).where(vol>0,0).fillna(0)
        if family=='KAMA':
            k=kama(c,n(10),n(30)); w=.5*((c>k)&(k>k.shift(n(5))))*sizing
            features[s]={'weight':w}
        elif family=='ENSEMBLE':
            mas=[c.rolling(n(v)).mean() for v in (50,100,200)]
            score=sum((c>ma).astype(float) for ma in mas)/3
            w=.5*score*sizing; w[mas[-1].isna()]=0
            features[s]={'weight':w}
        elif family=='ROTATE':
            r=c.pct_change(n(126),fill_method=None)
            features[s]={'return':r,'eligible':(c>c.rolling(n(200)).mean())&(r>0),'weight':sizing}
        else: raise ValueError(family)
    incumbent=None
    for i in range(1,len(idx)):
        schedule=(idx[i].strftime('%G-%V')!=idx[i-1].strftime('%G-%V')) if family!='ROTATE' else idx[i].to_period('M')!=idx[i-1].to_period('M')
        if not schedule: continue
        j=i-1; row={s:0. for s in SYMBOLS}
        if family!='ROTATE': row={s:float(features[s]['weight'].iloc[j]) for s in SYMBOLS}
        else:
            eligible=[s for s in SYMBOLS if features[s]['eligible'].iloc[j]]
            if eligible:
                best=max(eligible,key=lambda s:features[s]['return'].iloc[j])
                if incumbent not in eligible or features[best]['return'].iloc[j]-features[incumbent]['return'].iloc[j]>.02: incumbent=best
                row[incumbent]=float(features[incumbent]['weight'].iloc[j])
            else: incumbent=None
        out.loc[idx[i]]=row
    return out

def fee(notional,mult): return mult*max(3.,notional*.0005) if notional>0 else 0.
def buy_cost(q,p,mult): return q*p*(1+.0005*mult)+fee(q*p,mult)
def affordable(cash,p,mult,limit):
    q=max(0,min(int(limit),int(max(0,cash)/p)))
    while q and buy_cost(q,p,mult)>cash+1e-10: q-=1
    return q

def simulate(data,action,first,last,capital,mult=1.,benchmark=False):
    idx=data[SYMBOLS[0]].loc[first:last].index; cash=float(capital); qty={s:0 for s in SYMBOLS}; basis={s:0. for s in SYMBOLS}
    rows=[]; trades=[]; realized=[]
    def transact(s,q,p,date,side,reason):
        nonlocal cash
        gross=q*p; f=fee(gross,mult); slip=gross*.0005*mult
        if side=='buy':
            paid=gross+f+slip; cash-=paid; qty[s]+=q; basis[s]+=paid; pnl=None
        else:
            proceeds=gross-f-slip; cost=basis[s]*q/qty[s]; basis[s]-=cost; qty[s]-=q; cash+=proceeds; pnl=proceeds-cost; realized.append(pnl)
        trades.append(dict(date=str(date.date()),symbol=s,side=side,qty=q,price_eur=p,fee_eur=f,slippage_eur=slip,net_pnl_eur=pnl,reason=reason,cash_after=cash))
    for i,date in enumerate(idx):
        op={s:float(data[s].loc[date,'open_eur']) for s in SYMBOLS}; cl={s:float(data[s].loc[date,'close_eur']) for s in SYMBOLS}
        w=action.loc[date]
        if benchmark: w=pd.Series({s:.5 for s in SYMBOLS}) if i==0 else pd.Series({s:np.nan for s in SYMBOLS})
        if w.notna().all():
            eq=cash+sum(qty[s]*op[s] for s in SYMBOLS); desired={s:int(np.floor(float(w[s])*eq/op[s])) for s in SYMBOLS}
            for s in SYMBOLS:
                if qty[s]>desired[s]: transact(s,qty[s]-desired[s],op[s],date,'sell','rebalance')
            for s in SYMBOLS:
                q=affordable(cash,op[s],mult,max(0,desired[s]-qty[s]))
                if q: transact(s,q,op[s],date,'buy','rebalance')
        if cash< -1e-8 or any(q<0 or not isinstance(q,int) for q in qty.values()): raise AssertionError('Cash/whole-unit constraint')
        eq=cash+sum(qty[s]*cl[s] for s in SYMBOLS)
        rows.append(dict(date=str(date.date()),equity_eur=eq,cash_eur=cash,asset1_qty=qty[SYMBOLS[0]],asset2_qty=qty[SYMBOLS[1]],exposure=1-cash/eq,fx_date=str(data[SYMBOLS[0]].loc[date,'fx_date'].date()) if data[SYMBOLS[0]].loc[date].get('currency_mode','USD')=='USD' else None,usd_per_eur=float(data[SYMBOLS[0]].loc[date,'usd_per_eur'])))
    if len(idx):
        for s in SYMBOLS:
            if qty[s]: transact(s,qty[s],float(data[s].loc[idx[-1],'close_eur']),idx[-1],'sell','terminal_close')
        rows[-1].update(equity_eur=cash,cash_eur=cash,asset1_qty=0,asset2_qty=0,exposure=0.)
    curve=pd.DataFrame(rows); t=pd.DataFrame(trades); e=np.r_[capital,curve.equity_eur.to_numpy()]; r=e[1:]/e[:-1]-1; years=(idx[-1]-idx[0]).days/365.25
    loss=-sum(p for p in realized if p<0)
    metrics=dict(initial_eur=capital,final_eur=float(e[-1]),total_return=float(e[-1]/capital-1),cagr=float((e[-1]/capital)**(1/years)-1),max_drawdown=float(1-np.min(e/np.maximum.accumulate(e))),sharpe=float(np.mean(r)/np.std(r,ddof=1)*np.sqrt(252)) if np.std(r)>0 else None,orders=len(trades),sell_events=len(realized),profit_factor=sum(p for p in realized if p>0)/loss if loss else None,fees_eur=sum(v['fee_eur'] for v in trades),slippage_eur=sum(v['slippage_eur'] for v in trades),mean_exposure=float(curve.exposure.mean()))
    return curve,t,metrics

def self_test():
    idx=pd.bdate_range('2015-01-01',periods=800); c=100*np.exp(np.arange(800)*.001+np.sin(np.arange(800)/17)*.04)
    data={s:pd.DataFrame({'open_eur':c,'close_eur':c,'fx_date':idx-pd.Timedelta(days=1),'usd_per_eur':1.},index=idx) for s in SYMBOLS}
    for family in ('KAMA','ENSEMBLE','ROTATE'):
        a=targets(data,family)
        for cut in (300,500,700):
            short=targets({s:x.iloc[:cut] for s,x in data.items()},family)
            pd.testing.assert_frame_equal(a.iloc[:cut],short)
            bad={s:x.copy() for s,x in data.items()}
            for x in bad.values(): x.loc[idx[cut]:,'close_eur']*=100
            pd.testing.assert_frame_equal(a.iloc[:cut+1],targets(bad,family).iloc[:cut+1])
        e,t,m=simulate(data,a,str(idx[0].date()),str(idx[-1].date()),500)
        assert (e.cash_eur>=-1e-8).all() and (e[['asset1_qty','asset2_qty']]%1==0).all().all()
        assert abs(sum(t.net_pnl_eur.dropna())-(m['final_eur']-500))<1e-7
    assert affordable(103.,100,1,2)==0 and affordable(103.05,100,1,2)==1
    assert fee(100,2)==6. and abs(buy_cost(1,100,1)-103.05)<1e-10
    # Strictly prior FX: same-day rates cannot be used at an opening decision.
    l=pd.DataFrame({'date':pd.to_datetime(['2020-01-02'])}); f=pd.DataFrame({'fx_date':pd.to_datetime(['2020-01-01','2020-01-02']),'rate':[1.,9.]})
    assert pd.merge_asof(l,f,left_on='date',right_on='fx_date',allow_exact_matches=False).rate.iloc[0]==1.
    print('SELF_TEST PASS: causality, truncation, future corruption, whole units, fees, cash, PnL, FX timing')

def main():
    global SYMBOLS
    p=argparse.ArgumentParser(); p.add_argument('--self-test',action='store_true'); p.add_argument('--spec'); p.add_argument('--registration'); p.add_argument('--phase',choices=['development','exposed','diagnostic']); p.add_argument('--output'); p.add_argument('--data',default='data/ohlcv'); p.add_argument('--fx',default='reports/research/C35_METALS_20261013/ecb_usd_per_eur.csv'); p.add_argument('--symbols',nargs=2,default=list(SYMBOLS)); p.add_argument('--currency',choices=['USD','EUR'],default='USD'); a=p.parse_args(); SYMBOLS=tuple(a.symbols)
    if a.self_test: self_test(); return
    if not all((a.spec,a.registration,a.phase,a.output)): p.error('spec, registration, phase, output required')
    spec=json.loads(Path(a.spec).read_text()); reg=json.loads(Path(a.registration).read_text())
    if reg.get('spec_sha256')!=digest(a.spec): raise ValueError('Registration hash mismatch')
    if reg.get('engine_sha256')!=digest(__file__): raise ValueError('Engine registration hash mismatch')
    if spec.get('engine_contract')!='METALS_ADV_V1': raise ValueError('Unrecognized frozen contract')
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    if (out/f'{a.phase}_metrics.json').exists(): raise ValueError('Refuse output overwrite')
    data=load_data(a.data,a.fx,a.currency); periods=['IS','WF'] if a.phase=='development' else ['EXPOSED','FULL'] if a.phase=='exposed' else ['DIAGNOSTIC']; PERIODS['DIAGNOSTIC']=tuple(spec['datasets']['IBKR']['DIAGNOSTIC']); results=[]
    expected_start=PERIODS[periods[0]][0]; expected_end=PERIODS[periods[-1]][1]
    if data[SYMBOLS[0]].index[0]>=pd.Timestamp(expected_start) or data[SYMBOLS[0]].index[-1]<pd.Timestamp(expected_end): raise ValueError('Insufficient requested data range')
    for family in ('KAMA','ENSEMBLE','ROTATE','BUYHOLD','CASH'):
        for variant,(mult,scale) in VARIANTS.items():
            if family=='BUYHOLD' and variant.startswith('PARAM'): continue
            if family=='CASH' and variant!='BASE': continue
            action=targets(data,family,scale) if family not in ('BUYHOLD','CASH') else pd.DataFrame(np.nan,index=data[SYMBOLS[0]].index,columns=SYMBOLS)
            for capital in (500,1000,2000):
                for period in periods:
                    curve,trades,m=simulate(data,action,*PERIODS[period],capital,mult,family=='BUYHOLD')
                    stem=f'{family}_{variant}_{capital}_{period}'; curve.to_csv(out/f'{stem}_equity.csv',index=False); trades.to_csv(out/f'{stem}_trades.csv',index=False)
                    results.append(dict(strategy=family,variant=variant,capital=capital,period=period,**m))
    (out/f'{a.phase}_metrics.json').write_text(json.dumps(results,indent=2,allow_nan=False)); pd.DataFrame(results).to_csv(out/f'{a.phase}_metrics.csv',index=False)
    print(json.dumps({'phase':a.phase,'rows':len(results),'output':str(out)}))
if __name__=='__main__': main()
