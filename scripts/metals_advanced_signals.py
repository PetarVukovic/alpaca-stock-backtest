#!/usr/bin/env python3
"""Offline C36 research snapshot. No broker connectivity, orders, or approved strategy."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/research/METALS_ADV_20261013'
ENGINE=ROOT/'scripts/backtest_metals_advanced_20261013.py'
SPEC=ROOT/'strategies/frozen/2026-10-13_C36_METALS_ADV_20261013.json'
AS_OF_CEILING=pd.Timestamp('2026-10-13')
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module():
    reg=json.loads((REPORT/'registration.json').read_text())
    if digest(ENGINE)!=reg['engine_sha256'] or digest(SPEC)!=reg['spec_sha256']: raise ValueError('Frozen engine/spec checksum mismatch')
    for path,expected in reg['ibkr_input_hashes'].items():
        if digest(ROOT/path)!=expected: raise ValueError(f'Registered data checksum mismatch: {path}')
    obj=importlib.util.spec_from_file_location('c36_research',ENGINE); eng=importlib.util.module_from_spec(obj); obj.loader.exec_module(eng); eng.SYMBOLS=('PHAU','PHAG'); return eng

def validate(data,asof):
    for s,x in data.items():
        if len(x)<303: raise ValueError(f'{s}: fewer than303completedbars')
        if x.index[-1]>asof: raise ValueError('Future input bar')
        if (asof-x.index[-1]).days>7: raise ValueError('Stale saved prices')
        if ((x.high<x[['open','close','low']].max(axis=1)) | (x.low>x[['open','close','high']].min(axis=1))).any(): raise ValueError('Invalid OHLC')

def describe(eng,data,asof,capital):
    validate(data,asof); output={}
    for family in ('KAMA','ENSEMBLE','ROTATE'):
        action=eng.targets(data,family).dropna()
        if action.empty: raise ValueError('No scheduled historical target')
        date=action.index[-1]; idx=data['PHAU'].index; inputdate=idx[idx.get_loc(date)-1]; weights=action.iloc[-1]
        cash=float(capital); sizes={}; closes={s:float(data[s].iloc[-1].close_eur) for s in eng.SYMBOLS}
        for s in eng.SYMBOLS:
            requested=int(float(weights[s])*capital/closes[s]); q=eng.affordable(cash,closes[s],1.,requested)
            cost=eng.buy_cost(q,closes[s],1.) if q else 0.; cash-=cost
            sizes[s]={'illustrative_units':q,'illustrative_cost_eur':cost,'last_close_eur':closes[s]}
        output[family]={'signal':'PRIČEKAJ','approved':False,'historical_target_weights':{s:float(weights[s]) for s in eng.SYMBOLS},'model_inputs_through':str(inputdate.date()),'historical_scheduled_execution_date':str(date.date()),'sizing_example_at_saved_close':sizes,'illustrative_remaining_cash_eur':cash,'sizing_note':'Fresh hypothetical cash account at saved closing prices; not current holdings, simulated strategy positions, live quotes, or an executable order.'}
    return output

def snapshot(as_of,capital):
    asof=pd.Timestamp(as_of)
    if pd.isna(asof) or asof.tzinfo is not None or asof!=asof.normalize() or asof>AS_OF_CEILING: raise ValueError('Use date YYYY-MM-DD at or before2026-10-13; snapshot has no future data')
    if capital not in (500,1000,2000): raise ValueError('Capital must be500,1000,2000')
    result={'as_of':str(asof.date()),'capital_eur':capital,'signal':'PRIČEKAJ','approved':False,'winner':None,'planned_orders':[],'broker_connected':False,'mode':'OFFLINE_RESEARCH_SNAPSHOT','research':{},'data_status':'BLOCKED'}
    try:
        eng=module(); data=eng.load_data(ROOT/'data/ohlcv',ROOT/'reports/research/C35_METALS_20261013/ecb_usd_per_eur.csv','EUR'); data={s:x.loc[:asof].copy() for s,x in data.items()}
        result['research']=describe(eng,data,asof,capital); last=data['PHAU'].index[-1]
        result.update(data_status='VALIDATED_SAVED_SNAPSHOT',latest_completed_saved_bar=str(last.date()),pending_data_update=last<asof,limitation='Only saved historical prices. No approved strategy; reused history is not independent validation; broker account availability unverified.')
    except (ValueError,KeyError,FileNotFoundError,IndexError) as exc: result['block_reason']=str(exc)
    return result

def self_test():
    eng=module(); data=eng.load_data(ROOT/'data/ohlcv',ROOT/'reports/research/C35_METALS_20261013/ecb_usd_per_eur.csv','EUR')
    for capital in (500,1000,2000):
        r=snapshot('2026-10-13',capital); assert r['signal']=='PRIČEKAJ' and not r['approved'] and r['planned_orders']==[] and r['research']
        for f in r['research'].values():
            assert f['illustrative_remaining_cash_eur']>=0
            assert sum(v['illustrative_cost_eur'] for v in f['sizing_example_at_saved_close'].values())<=capital+1e-8
    bad={s:x.copy() for s,x in data.items()}; bad['PHAU'].iloc[-1,bad['PHAU'].columns.get_loc('high')]=0
    try: describe(eng,bad,pd.Timestamp('2026-10-13'),500)
    except ValueError: pass
    else: raise AssertionError('Invalid OHLC accepted')
    try: snapshot('2026-10-14',500)
    except ValueError: pass
    else: raise AssertionError('Future asof accepted')
    print('SELF_TEST PASS: fail-closed data, future date, no approval/orders, whole-unit cash budget')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--as-of');p.add_argument('--capital-eur',type=int,choices=[500,1000,2000],default=1000);p.add_argument('--output');p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:self_test();return
    if not a.as_of:p.error('--as-of required')
    r=snapshot(a.as_of,a.capital_eur);text=json.dumps(r,indent=2,allow_nan=False)
    if a.output:Path(a.output).write_text(text+'\n')
    print(text)
if __name__=='__main__':main()
