"""Frozen C28 recovery re-entry experiment. Never imports brokers or changes app settings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from lab.data import load_bars
from lab.ledger import current_k
from lab.research.memory_swing import replay as baseline_replay, metrics, benchmark
from lab.research.reentry_swing import replay
from scripts.run_memory_swing import fx_table, fx_rate, write_json

STUDY='C28_RECOVERY_REENTRY_20261006'


def interest_checks(results, stresses):
    primary=results['SMALL_600EUR_ALL']
    candidate,base=primary['candidate'],primary['baseline']
    stress=stresses['SMALL_600EUR_ALL']['candidate']
    checks={
        'WF_return_above_baseline':candidate['WF']['return_pct']>base['WF']['return_pct'],
        'WF_drawdown_not_worse':candidate['WF']['max_drawdown_pct']<=base['WF']['max_drawdown_pct'],
        'IS_positive':candidate['IS']['return_pct']>0,
        'HO_seen_drawdown_not_worse':candidate['HO_SEEN']['max_drawdown_pct']<=base['HO_SEEN']['max_drawdown_pct'],
        'WF_cost3_above_USD_cash':stress['COST3']['WF']['return_pct']>stress['COST3']['WF']['usd_cash_benchmark']['return_pct'],
        'WF_exit100bps_above_USD_cash':stress['EXIT100BPS']['WF']['return_pct']>stress['EXIT100BPS']['WF']['usd_cash_benchmark']['return_pct'],
    }
    checks={name:bool(value) for name,value in checks.items()}
    return {'checks':checks,'research_interest':'PASS' if all(checks.values()) else 'FAIL',
            'critic_approval':False,'activation':False,'note':'Predeclared research-interest criteria only; no untouched holdout.'}


def assert_baseline_parity(actual, expected):
    if not actual['curve'].equals(expected['curve']):
        raise ValueError('Disabled candidate differs from original baseline equity')
    for key in ('trades','events','skipped','open_position'):
        if actual[key]!=expected[key]:
            raise ValueError(f'Disabled candidate differs from baseline {key}')


def causal_audit(frames, config):
    kwargs=dict(config['base_parameters'],sizing='one',cap=1200,reentry_enabled=True)
    full=replay(frames,'2016-01-04',config['through'],100000,**kwargs)
    checks=[]
    for cutoff in ('2020-12-31','2023-12-29','2025-12-31'):
        truncated={s:f.loc[:cutoff].copy() for s,f in frames.items()}
        short=replay(truncated,'2016-01-04',cutoff,100000,**kwargs)
        corrupt={s:f.copy() for s,f in frames.items()}
        boundary=pd.Timestamp(cutoff,tz='UTC')
        for frame in corrupt.values():
            frame.loc[frame.index>boundary,['open','high','low','close']]*=3.17
        altered=replay(corrupt,'2016-01-04',config['through'],100000,**kwargs)
        dates=short['curve'].index
        truncated_difference=float(np.max(np.abs(short['curve']-full['curve'].reindex(dates))))
        corrupt_difference=float(np.max(np.abs(altered['curve'].reindex(dates)-full['curve'].reindex(dates))))
        prefix=lambda events:[e for e in events if e[0]<=cutoff]
        record=dict(cutoff=cutoff,truncated_max_equity_difference=truncated_difference,
                    future_corruption_max_equity_difference=corrupt_difference,
                    truncated_events_match=short['events']==prefix(full['events']),
                    future_corruption_events_match=prefix(altered['events'])==prefix(full['events']))
        record['passed']=bool(truncated_difference<1e-8 and corrupt_difference<1e-8
                              and record['truncated_events_match'] and record['future_corruption_events_match'])
        checks.append(record)
    return checks


def run_case(frames,rates,profile,period,config,enabled,stress=None):
    start,end=period
    first=next(iter(frames.values())).loc[start:end].index[0]
    fx0=fx_rate(rates,first,before=True) if profile['currency']=='EUR' else 1.
    capital=profile['capital']*fx0
    params=dict(config['base_parameters'],sizing=profile['sizing'],cap=profile['cap'])
    params.update(stress or {})
    raw=replay(frames,start,end,capital,reentry_enabled=enabled,**params)
    if raw is None: raise ValueError('Missing requested history')
    parity=None
    if not enabled:
        original=baseline_replay(frames,start,end,capital,**params)
        assert_baseline_parity(raw,original)
        parity=True
    curve=raw['curve']
    fx=pd.Series([fx_rate(rates,day) for day in curve.index],index=curve.index) if profile['currency']=='EUR' else pd.Series(1.,index=curve.index)
    base_curve=curve/fx
    result=metrics(base_curve,profile['capital'],raw['trades'])
    passive,holdings=benchmark(frames,curve.index,capital,'equal')
    cash=pd.Series(capital,index=curve.index)/fx
    tags=raw.get('entry_tags',[])
    position=raw['open_position']
    open_pnl=(float(frames[position['ticker']].loc[curve.index[-1],'close'])-position['entry_price'])*position['quantity'] if position else 0.
    result.update(currency=profile['currency'],closed_trade_statistics_currency='USD',
        open_position_count=int(position is not None),open_unrealized_pnl_usd=open_pnl,
        closed_realized_pnl_usd=float(sum(t['pnl_usd'] for t in raw['trades'])),
        initial_usd=capital,initial_eurusd=fx0 if profile['currency']=='EUR' else None,
        n_entries=sum(e[1]=='buy' for e in raw['events']),
        n_reentry=sum(t['entry_reason']=='reentry_reclaim' for t in tags),
        n_normal_entries=sum(e[1]=='buy' for e in raw['events'])-sum(t['entry_reason']=='reentry_reclaim' for t in tags),
        open_position=raw['open_position'],exposure_pct=raw['mean_exposure_pct'],
        costs_usd=raw['costs_usd'],fill_violations=raw['fill_violations'],
        max_daily_volume_fraction=raw['max_daily_volume_fraction'],skipped_count=len(raw['skipped']),
        collision_days=raw['collision_days'],baseline_parity=parity,
        passive_basket=metrics(passive/fx,profile['capital'])|{'holdings':holdings},
        usd_cash_benchmark=metrics(cash,profile['capital']))
    return result,raw,base_curve


def main():
    output=ROOT/'reports/backtest'/STUDY
    config=json.loads((output/'config.json').read_text())
    freeze=ROOT/'strategies/frozen'/f'2026-10-06_{STUDY}.md'
    frozen=json.loads(freeze.read_text().split('```json\n',1)[1].split('```',1)[0])
    if frozen!=config: raise ValueError('Configuration differs from frozen protocol')
    if (output/'summary.json').exists(): raise FileExistsError('Refusing to overwrite finished C28')
    source=ROOT/config['source_freeze']
    engine=ROOT/'lab/research/memory_swing.py'
    for path,expected in ((source,config['source_freeze_sha256']),(engine,config['baseline_engine_sha256'])):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError(f'Frozen source changed: {path.name}')
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--through',config['through'],
                    '--report',str(output/'DATA_CHECK.md')],cwd=ROOT,check=True)
    frames={s:load_bars(s,through=config['through']) for s in config['universe']}
    fx_path=ROOT/'reports/backtest/C21_SWING_20261006/ecb-history.xml'
    rates=fx_table(fx_path)
    results,stresses,annual={}, {}, {}
    audit={}
    def evaluate(key,profile,period,enabled,stress=None):
        summary,raw,curve=run_case(frames,rates,profile,period,config,enabled,stress)
        raw['curve'].rename('equity_usd').to_frame().assign(equity_base=curve).to_csv(output/f'{key}_equity.csv')
        pd.DataFrame(raw['trades']).to_csv(output/f'{key}_trades.csv',index=False)
        pd.DataFrame(raw.get('entry_tags',[])).to_csv(output/f'{key}_entry_tags.csv',index=False)
        audit[key]={'fill_violations':raw['fill_violations'],'baseline_parity':summary['baseline_parity'],
                    'max_daily_volume_fraction':raw['max_daily_volume_fraction']}
        return summary
    for profile_name,profile in config['profiles'].items():
        results[profile_name]={};stresses[profile_name]={}
        for mode,enabled in [('baseline',False),('candidate',True)]:
            results[profile_name][mode]={period:evaluate(f'{profile_name}__{mode}__{period}',profile,bounds,enabled)
                for period,bounds in config['periods'].items()}
            stresses[profile_name][mode]={name:{period:evaluate(f'{profile_name}__{mode}__{name}__{period}',profile,
                config['periods'][period],enabled,params) for period in config['stress_periods']}
                for name,params in config['stresses'].items() if name!='BASE'}
        print('FINISHED',profile_name,flush=True)
    primary=config['profiles']['SMALL_600EUR_ALL']
    for mode,enabled in [('baseline',False),('candidate',True)]:
        annual[mode]={str(year):evaluate(f'ANNUAL_{year}__{mode}',primary,
            [f'{year}-01-01',min(f'{year}-12-31',config['through'])],enabled) for year in range(2021,2027)}
    causality=causal_audit(frames,config)
    if any(r['fill_violations'] for r in audit.values()) or not all(r['passed'] for r in causality):
        write_json(output/'FAILED_AUDIT.json',{'cases':audit,'causality':causality})
        raise ValueError('Audit failed; result is not trustworthy')
    criteria=interest_checks(results,stresses)
    paths=[source,engine,freeze,fx_path,Path(__file__),ROOT/'lab/research/reentry_swing.py']
    paths += [ROOT/f'data/ohlcv/{s}_1d.csv' for s in frames]
    summary=dict(config=config,k=current_k(),results=results,stresses=stresses,annual_reset600=annual,
        audit={'cases':audit,'causality':causality},criteria=criteria,
        manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        caveats=['All historical periods already seen; no clean out-of-sample claim or profit guarantee.',
                 'Candidate anchors reset at each independent period; yearly600reset diagnostics are not additive compounded years.',
                 'Account return includes marked open positions; trade statistics include closed USD trades only.',
                 'No dividends, taxes, FX conversion charges or real broker fill reconciliation. No application activation.'])
    write_json(output/'summary.json',summary)
    rows=[]
    for profile,modes in results.items():
        for period,base in modes['baseline'].items():
            candidate=modes['candidate'][period]
            rows.append(dict(profile=profile,period=period,currency=candidate['currency'],
                baseline_final=base['final'],candidate_final=candidate['final'],difference=candidate['final']-base['final'],
                baseline_return_pct=base['return_pct'],candidate_return_pct=candidate['return_pct'],
                baseline_drawdown_pct=base['max_drawdown_pct'],candidate_drawdown_pct=candidate['max_drawdown_pct'],
                baseline_n_closed=base['n_closed'],candidate_n_closed=candidate['n_closed'],
                candidate_reentries=candidate['n_reentry'],passive_final=candidate['passive_basket']['final'],
                cash_final=candidate['usd_cash_benchmark']['final']))
    pd.DataFrame(rows).to_csv(output/'comparison.csv',index=False)
    lines=['# C28 — Ponovni ulaz nakon oporavka iznad starog vrha','',
        'Usporedili smo što bi se dogodilo s početnih **600 EUR**, bez doplata, uz ponovno ulaganje dobiti. Aktivna aplikacija nije promijenjena.',
        'Nakon zaštitne prodaje kandidat pamti prethodni vrh. Kasnija završna cijena iznad tog vrha i SMA200 dopušta novu kupnju na sljedećem otvaranju.',
        'Oporavak može biti lažan i dovesti do dodatnih gubitaka. Rezultati nisu jamstvo.', '',
        f"Unaprijed zadani kriteriji istraživačkog interesa: **{criteria['research_interest']}**. To nije Critic PASS niti odobrenje trgovanja.",'',
        '| Razdoblje | Izvorno EUR | Novo pravilo EUR | Razlika EUR | Izvorni najveći pad | Novi najveći pad | Zatvorenih trgovina | Dodatnih ponovnih ulaza |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    labels={'IS':'2016.–2020.','WF':'2021.–2023.','HO_SEEN':'2024.–2.10.2026. (već pregledano)',
            'POST_CHATGPT':'1.12.2022.–2.10.2026.','ALL':'2016.–2.10.2026.'}
    for row in rows:
        if row['profile']!='SMALL_600EUR_ALL': continue
        lines.append(f"| {labels[row['period']]} | {row['baseline_final']:.2f} | {row['candidate_final']:.2f} | {row['difference']:+.2f} | {row['baseline_drawdown_pct']:.2f}% | {row['candidate_drawdown_pct']:.2f}% | {row['candidate_n_closed']} | {row['candidate_reentries']} |")
    lines += ['', 'Završna vrijednost uključuje i dionice koje još nisu prodane. To nije sve ostvarena zarada. Najveći pad označava pad računa od prethodnog vrha.',
              'Svi profili, uključujući100.000USD paper i600EUR po jednoj dionici, dostupni su u comparison.csv i summary.json.']
    lines += ['', '## Kriteriji', '']+[f"- {name}: {'PASS' if passed else 'FAIL'}" for name,passed in criteria['checks'].items()]
    lines += ['', '## Nepovoljna izvršenja — 600 EUR, cijela raspoloživa gotovina', '',
              '| Scenarij | Razdoblje | Izvorni prinos | Kandidat prinos | Kandidat pad | USD gotovina u EUR |',
              '|---|---|---:|---:|---:|---:|']
    for name,periods in stresses['SMALL_600EUR_ALL']['candidate'].items():
        for period,cand in periods.items():
            base=stresses['SMALL_600EUR_ALL']['baseline'][name][period]
            lines.append(f"| {name} | {period} | {base['return_pct']:.2f}% | {cand['return_pct']:.2f}% | {cand['max_drawdown_pct']:.2f}% | {cand['usd_cash_benchmark']['return_pct']:.2f}% |")
    lines += ['', 'Razdoblja ALL/POST_CHATGPT/HO_SEEN se preklapaju. Godišnji presjeci kreću ponovno sa600EUR i nisu zbroj kontinuiranog računa.',
              'Kandidat je prošao provjere uzročnosti na tri presjeka i original bez uključenog ponovnog ulaza ostao je potpuno jednak osnovnom modelu.',
              'Daljnji rad zahtijeva neovisni Critic i nove buduće podatke. Nijedan nalog nije poslan.']
    (output/'IZVJESTAJ.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'cases':len(audit),'criteria':criteria,'causality':causality},indent=2))


if __name__=='__main__': main()
