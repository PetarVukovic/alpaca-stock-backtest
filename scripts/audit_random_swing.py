"""Frozen C27 null-entry and cost audit; offline, no broker imports or orders."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from lab.data import load_bars
from lab.research import memory_swing as engine
from scripts.run_memory_swing import fx_table, fx_rate, write_json
from scripts import validate_data as validator

STUDY = 'C27_RANDOM_COST_AUDIT_20261006'
OUTPUT = ROOT/'reports/backtest'/STUDY
CONTEXT = {}


def calibrated_probabilities(frame):
    eligible = frame.close.rolling(200).count().ge(200)
    trend = eligible & frame.close.gt(frame.close.rolling(200).mean())
    original = engine.entry_signals(frame)
    insample = (frame.index >= pd.Timestamp('2016-01-04',tz='UTC')) & (frame.index <= pd.Timestamp('2020-12-31',tz='UTC'))
    numerator = int(original.loc[insample].sum())
    counts = {'trend_conditional':int(trend.loc[insample].sum()),'unconditional':int(eligible.loc[insample].sum())}
    if any(n == 0 for n in counts.values()):
        raise ValueError('Insufficient calibration history')
    return {'numerator':numerator, 'denominators':counts,
            'probability':{k:numerator/n for k,n in counts.items()}}, eligible, trend


def random_pattern(frame, symbol, seed, null, calibration):
    # Stable symbol seeds avoid process-dependent Python hash() and preserve prefixes.
    entropy = int.from_bytes(hashlib.sha256(f'{seed}:{symbol}'.encode()).digest()[:8], 'big')
    uniforms = np.random.Generator(np.random.PCG64(entropy)).random(len(frame))
    eligible = frame.close.rolling(200).count().ge(200)
    mask = eligible & frame.close.gt(frame.close.rolling(200).mean()) if null == 'trend_conditional' else eligible
    return pd.Series(uniforms < calibration['probability'][null], index=frame.index) & mask


@contextmanager
def patched_signals(patterns):
    original = engine.entry_signals
    def replacement(frame, trend=200, bars=5, dip=.05):
        return patterns[frame.attrs['symbol']].reindex(frame.index,fill_value=False)
    engine.entry_signals = replacement
    try:
        yield
    finally:
        engine.entry_signals = original


def initialize():
    config = json.loads((OUTPUT/'config.json').read_text())
    symbols = sorted({s for group in config['universes'].values() for s in group})
    frames = {s:load_bars(s,through=config['through']) for s in symbols}
    for s,f in frames.items(): f.attrs['symbol'] = s
    rates = fx_table(ROOT/'reports/backtest/C26_BASKET_20261006/ecb-history.xml')
    calibration = {s:calibrated_probabilities(f)[0] for s,f in frames.items()}
    conversions = {}
    for period,(start,end) in config['periods'].items():
        dates = next(iter(frames.values())).loc[start:end].index
        conversions[period] = (fx_rate(rates,dates[0],before=True),pd.Series([fx_rate(rates,d) for d in dates],index=dates))
    CONTEXT.update(config=config,frames=frames,calibration=calibration,conversions=conversions,patterns={})


def run_case(group,profile_name,period,stress=1,seed=None,null=None):
    cfg=CONTEXT['config']; profile=cfg['profiles'][profile_name]
    frames={s:CONTEXT['frames'][s] for s in cfg['universes'][group]}
    start,end=cfg['periods'][period]
    initial_fx,conversion=CONTEXT['conversions'][period]
    capital=profile['capital']*(initial_fx if profile['currency']=='EUR' else 1.)
    kwargs=dict(sizing=profile['sizing'],cap=profile['cap'],stress=stress)
    if null:
        patterns={}
        for s,f in frames.items():
            key=(s,seed,null)
            if key not in CONTEXT['patterns']:
                CONTEXT['patterns'][key]=random_pattern(f,s,seed,null,CONTEXT['calibration'][s])
            patterns[s]=CONTEXT['patterns'][key]
        with patched_signals(patterns):
            result=engine.replay(frames,start,end,capital,**kwargs)
    else:
        result=engine.replay(frames,start,end,capital,**kwargs)
    curve=result['curve']; base=curve/conversion if profile['currency']=='EUR' else curve
    summary=engine.metrics(base,profile['capital'],result['trades'])
    summary.update(group=group,profile=profile_name,period=period,stress=stress,seed=seed,null=null,
                   costs_usd=result['costs_usd'],mean_exposure_pct=result['mean_exposure_pct'],
                   mean_cash_pct=100-result['mean_exposure_pct'],n_skipped=len(result['skipped']),
                   n_entries=sum(e[1]=='buy' for e in result['events']),fill_violations=result['fill_violations'],
                   mean_closed_trade_return_pct=float(np.mean([t['return_pct'] for t in result['trades']])) if result['trades'] else None,
                   initial_usd=capital,final_usd=float(curve.iloc[-1]),base_currency=profile['currency'])
    return summary,curve


def worker(job):
    group,profile,period,seed,null=job
    return run_case(group,profile,period,seed=seed,null=null)[0]


def distribution(values,observed):
    values=np.asarray(values,float)
    values=values[np.isfinite(values)]
    if not len(values):
        return {'q05':None,'median':None,'q95':None,'observed_percentile':None,'smoothed_upper_tail':None,'n_valid':0}
    return {'q05':float(np.quantile(values,.05)),'median':float(np.median(values)),
            'q95':float(np.quantile(values,.95)),
            'observed_percentile':100*float((np.sum(values<observed)+.5*np.sum(values==observed))/len(values)) if observed is not None else None,
            'smoothed_upper_tail':float((1+np.sum(values>=observed))/(len(values)+1)) if observed is not None else None,
            'n_valid':len(values)}


def data_gate():
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--through','2026-10-02','--report',str(OUTPUT/'DATA_CHECK.md')],check=True,cwd=ROOT)
    exceptions_path=ROOT/'reports/research/C26_SUPPLEMENTAL_DATA_CHECK_20261006.json'
    exceptions=json.loads(exceptions_path.read_text())
    verified=exceptions['verified_study_local_exceptions']
    known=validator.load_known_real() | {(r['ticker'],r['date']) for r in verified}
    if exceptions['errors'] or any(not r.get('event_source') or not r.get('price_source') or not r.get('note') for r in verified):
        raise ValueError('Study-specific data exceptions need sources and reasons')
    for symbol,digest in exceptions['source_hashes'].items():
        if hashlib.sha256((ROOT/f'data/ohlcv/{symbol}_1d.csv').read_bytes()).hexdigest()!=digest:
            raise ValueError('Data changed since verified exceptions')
    write_json(OUTPUT/'verified_data_exceptions.json',exceptions)
    symbols=sorted({s for x in CONTEXT['config']['universes'].values() for s in x})
    previous=validator.STRICT
    findings=validator.Findings();stats=[]
    try:
        validator.STRICT=sorted(set(previous)|set(symbols))
        for symbol in symbols: validator.check_daily(symbol,findings,known,stats,through='2026-10-02')
    finally:
        validator.STRICT=previous
    write_json(OUTPUT/'SUPPLEMENTAL_DATA_CHECK.json',{'errors':findings.errors,'warnings':findings.warnings,'stats':stats,'verified_exceptions':exceptions})
    if findings.errors: raise ValueError(str(findings.errors))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    initialize();cfg=CONTEXT['config']
    freeze=ROOT/f'strategies/frozen/2026-10-06_{STUDY}.md'
    frozen=json.loads(freeze.read_text().split('```json\n',1)[1].split('```',1)[0])
    if cfg!=frozen: raise ValueError('Freeze/config mismatch')
    if hashlib.sha256((ROOT/'lab/research/memory_swing.py').read_bytes()).hexdigest()!=cfg['source_engine_sha256']:
        raise ValueError('Engine changed since freeze')
    data_gate()
    old_raw=(ROOT/'reports/backtest/C26_BASKET_20261006/summary.json').read_bytes()
    old=json.loads(old_raw)
    results={};verification=[];t0=time.monotonic()
    for group in cfg['universes']:
        for profile in cfg['profiles']:
            for period in cfg['periods']:
                key=f'{group}__{profile}__{period}'
                row,curve=run_case(group,profile,period)
                previous=old['results'][key]
                for field in ['final','return_pct','max_drawdown_pct','n_closed','mean_exposure_pct']:
                    if not np.isclose(row[field],previous[field],rtol=1e-11,atol=1e-9):
                        raise ValueError(f'C26 mismatch {key} {field}')
                reference=pd.read_csv(ROOT/f'reports/backtest/C26_BASKET_20261006/{key}_equity.csv')
                if len(reference)!=len(curve) or not np.allclose(reference.equity_usd,curve,rtol=1e-12,atol=1e-8):
                    raise ValueError(f'C26 equity mismatch {key}')
                results[key]=row;verification.append(key)
    write_json(OUTPUT/'baseline_verification.json',{'matched_cases':len(verification),'cases':verification,'elapsed_seconds':time.monotonic()-t0})
    print(f'Baseline verified {len(verification)} cases in {time.monotonic()-t0:.1f}s',flush=True)
    write_json(OUTPUT/'calibration.json',CONTEXT['calibration'])
    costs=list(results.values())
    for stress in [2,3]:
        for group in cfg['universes']:
            for profile in cfg['profiles']:
                for period in cfg['periods']:
                    costs.append(run_case(group,profile,period,stress=stress)[0])
    pd.DataFrame(costs).to_csv(OUTPUT/'cost_stress.csv',index=False)
    print('Cost stress completed',flush=True)
    jobs=[(g,p,t,s,n) for g in cfg['random_groups'] for p in cfg['random_profiles'] for t in cfg['periods'] for n in cfg['nulls'] for s in cfg['seeds']]
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize) as pool:
        for i,row in enumerate(pool.map(worker,jobs,chunksize=16),1):
            rows.append(row)
            if i%512==0: print(f'Random replays {i}/{len(jobs)}',flush=True)
    table=pd.DataFrame(rows);table.to_csv(OUTPUT/'random_seeds.csv',index=False)
    aggregates=[]
    for (group,profile,period,null),part in table.groupby(['group','profile','period','null'],sort=False):
        observed=results[f'{group}__{profile}__{period}']
        row=dict(group=group,profile=profile,period=period,null=null,n_seeds=len(part),observed_return=observed['return_pct'],
                 observed_n_closed=observed['n_closed'],observed_exposure=observed['mean_exposure_pct'])
        row.update(observed_mean_closed_trade_return_pct=observed['mean_closed_trade_return_pct'],observed_profit_factor=observed['profit_factor'])
        for metric in ['return_pct','max_drawdown_pct','n_closed','mean_exposure_pct','n_skipped','mean_closed_trade_return_pct','profit_factor']:
            row.update({f'{metric}_{k}':v for k,v in distribution(part[metric],observed[metric]).items()})
        aggregates.append(row)
    pd.DataFrame(aggregates).to_csv(OUTPUT/'random_comparison.csv',index=False)
    manifest={s:hashlib.sha256((ROOT/f'data/ohlcv/{s}_1d.csv').read_bytes()).hexdigest() for s in CONTEXT['frames']}
    write_json(OUTPUT/'summary.json',{'study':STUDY,'baseline_verified':len(verification),'cost_cases':len(costs),'random_cases':len(rows),
        'random_comparisons':aggregates,'data_hashes':manifest,'source_engine_sha256':cfg['source_engine_sha256'],
        'source_c26_summary_sha256':hashlib.sha256(old_raw).hexdigest(),
        'elapsed_seconds':time.monotonic()-t0,'disclaimer':'Hypothetical historical simulation; HO seen; ALL includes IS calibration. Null counts/exposure not matched; no statistical PASS, no strategy selection, no orders.'})
    print(f'Done in {time.monotonic()-t0:.1f}s',flush=True)

if __name__=='__main__': main()
