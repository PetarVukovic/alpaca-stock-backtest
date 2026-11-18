"""Frozen offline C29/C30 diagnostics. No brokers, no orders, no parameter search."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import scipy
from lab.data import load_bars
from lab.ledger import current_k, register_strategy
from lab.research.memory_swing import replay as original, metrics, benchmark
from lab.research.regime_swing import replay, wilder_atr
from lab.critic.stats import deflated_sharpe, pbo_cscv, monte_carlo_drawdown
from scripts.run_memory_swing import fx_table, fx_rate, write_json

STUDY = 'C29_C30_REGIMES_20261009'
FREEZE = ROOT / f'strategies/frozen/2026-10-09_{STUDY}.json'
OUT = ROOT / 'reports/backtest' / STUDY


def trend_basket(frames, dates, capital, stress=1):
    """Equal initial cash sleeves; close/SMA200 signal executes next open."""
    total = pd.Series(0., index=dates)
    for frame in frames.values():
        active = (frame.close > frame.close.rolling(200).mean()).shift(1).fillna(False)
        cash, qty = capital / len(frames), 0
        path = []
        for day in dates:
            raw = float(frame.loc[day, 'open'])
            allowed = bool(active.loc[day])
            if qty and not allowed:
                cash += qty * max(0., raw - stress*(raw*.00025+.01)); qty = 0
            if not qty and allowed:
                price = raw + stress*(raw*.00025+.01)
                qty = int(cash // price); cash -= qty*price
            path.append(cash + qty*float(frame.loc[day, 'close']))
        total += pd.Series(path, index=dates)
    return total


def passive_basket(frames, dates, capital, stress=1):
    cash=capital; holdings={}
    for symbol, frame in frames.items():
        raw=float(frame.loc[dates[0],'open'])
        price=raw+stress*(raw*.00025+.01)
        quantity=int((capital/len(frames))//price)
        cash-=quantity*price; holdings[symbol]=quantity
    curve=pd.Series(cash,index=dates)
    for symbol, quantity in holdings.items():
        curve+=quantity*frames[symbol].loc[dates,'close']
    return curve,holdings


def annual_continuous(curve, initial):
    prior = initial
    rows = []
    for year, part in curve.groupby(curve.index.year):
        last = float(part.iloc[-1])
        rows.append(dict(year=int(year), starting_value=prior, ending_value=last,
                         return_pct=100*(last/prior-1), first_session=str(part.index[0].date()),
                         last_session=str(part.index[-1].date()), partial_year=year == 2026))
        prior = last
    return rows


def attribution(trades, frames, contexts, events):
    """Labels are known by the completed session before entry; no predictive claim."""
    records = []
    for t in trades:
        symbol = t['ticker']; f = frames[symbol]
        entry = pd.Timestamp(t['entry_date'], tz='UTC')
        past = f.index[f.index < entry]
        if not len(past): continue
        day = past[-1]; atr = wilder_atr(f)
        a = float(atr.loc[day]/f.loc[day, 'close'])
        row = dict(ticker=symbol, entry_date=t['entry_date'], exit_date=t['exit_date'],
                   return_pct=t['return_pct'], pnl_usd=t['pnl_usd'],
                   atr_bucket='<=2%' if a <= .02 else '2-4%' if a <= .04 else '>4%')
        for name, cf in contexts.items():
            ma = cf.close.rolling(200).mean().get(day, np.nan)
            row[name+'_trend'] = 'UNKNOWN' if not np.isfinite(ma) else ('UP' if cf.close.get(day, np.nan)>ma else 'DOWN')
        # Existing archive has incomplete coverage. Absence is NOT proof of no event.
        window = set(past[-5:].strftime('%Y-%m-%d'))
        known = [r for r in events if symbol == 'MU' and r['type']=='earnings_MU'
                 and r['verified']=='yes' and r['us_reaction_date'] in window]
        row['past_event_archive'] = 'RECORDED_PAST_EVENT' if known else 'NO_RECORD_OR_UNKNOWN'
        records.append(row)
    groups = {}
    for field in ('ticker','SPY_trend','SMH_trend','atr_bucket','past_event_archive'):
        groups[field] = {}
        for label in sorted({r[field] for r in records}):
            selected = [r for r in records if r[field] == label]
            returns = np.array([r['return_pct'] for r in selected])
            groups[field][label] = dict(n=len(selected), mean_trade_pct=float(returns.mean()),
                median_trade_pct=float(np.median(returns)), win_pct=100*float(np.mean(returns>0)),
                pnl_usd=float(sum(r['pnl_usd'] for r in selected)),
                standard_error_mean=float(returns.std(ddof=1)/np.sqrt(len(returns))) if len(returns)>1 else None,
                min_trade_pct=float(returns.min()),max_trade_pct=float(returns.max()))
    return {'groups':groups,'trades':records,'note':'Descriptive correlated selected trades, no causal estimate; archive incomplete; categories not added as entry filters.'}


def audit_causality(frames, variant, through):
    p = params_for(variant)
    full = replay(frames,'2016-01-04',through,10000,sizing='one',cap=1e12,**p)
    rows = []
    for cut in ('2020-12-31','2023-12-29','2025-12-31'):
        stamp = pd.Timestamp(cut,tz='UTC')
        short = replay({s:f.loc[:cut].copy() for s,f in frames.items()},'2016-01-04',cut,10000,sizing='one',cap=1e12,**p)
        altered = {s:f.copy() for s,f in frames.items()}
        for f in altered.values(): f.loc[f.index>stamp,['open','high','low','close']] *= 3.17
        other = replay(altered,'2016-01-04',through,10000,sizing='one',cap=1e12,**p)
        idx = short['curve'].index
        prefix = lambda ev:[x for x in ev if x[0]<=cut]
        diffs = [float(np.max(np.abs(short['curve']-full['curve'].loc[idx]))), float(np.max(np.abs(other['curve'].loc[idx]-full['curve'].loc[idx])))]
        rows.append(dict(cutoff=cut,max_equity_differences=diffs,
            events_match=short['events']==prefix(full['events'])==prefix(other['events']),
            passed=max(diffs)<1e-8 and short['events']==prefix(full['events'])==prefix(other['events'])))
    return rows


def params_for(variant):
    return {k:v for k,v in variant.items() if k in ('mode','atr_period','atr_multiple','gap_multiple')}


def run():
    config = json.loads(FREEZE.read_text())
    if (OUT/'summary.json').exists(): raise FileExistsError('Completed results are immutable')
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT/config['source_freeze']
    for p,h in [(source,config['source_freeze_sha256']),(ROOT/'lab/research/memory_swing.py',config['baseline_engine_sha256'])]:
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h: raise ValueError('Frozen source changed')
    through = config['requested_through']
    # This is deliberately a hard gate, not a warning that can be bypassed.
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--through',through,'--report',str(OUT/'DATA_CHECK.md')],cwd=ROOT,check=True)
    symbols = sorted(set(config['single_checks']+config['context']))
    frames = {s:load_bars(s,through=through) for s in symbols}
    if any(str(f.index[-1].date())!=through for f in frames.values()): raise ValueError('Requested endpoint missing')
    fx_path = ROOT/'reports/research/C13C_20261009/ecb-history.xml'
    rates = fx_table(fx_path)
    if rates.index[-1] < pd.Timestamp(through,tz='UTC'): raise ValueError('ECB endpoint not current')
    periods = {k:[start,through if end=='cutoff' else end] for k,(start,end) in config['periods'].items()}
    events = pd.read_csv(ROOT/'data/news/events_calendar.csv').fillna('').to_dict('records')
    variants = config['variants']; raw_cache={}; results={}; case_audit={}
    freeze_hash = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    # Every changed sizing/universe and sensitivity configuration is charged to K.
    # Stress tests do not select parameters, but each is enumerated in output.
    groups={'CORE':config['core'],'EXPANDED':config['expanded']}
    all_profiles=[(g,600) for g in groups]+[('CORE',500)]
    for name in variants:
        for group,capital in all_profiles:
            register_strategy(f'{STUDY}_{name}_{group}_{capital}',freeze_hash,purpose='prespecified profile/universe diagnostic')
        for symbol in config['single_checks']:
            register_strategy(f'{STUDY}_{name}_{symbol}_600',freeze_hash,purpose='prespecified single-symbol diagnostic')
        for symbol in config['expanded']:
            register_strategy(f'{STUDY}_{name}_{symbol}_TV10000_ONE',freeze_hash,purpose='prespecified TradingView-parity profile')
    sensitivities={}
    for name in variants:
        base=dict(config['base_parameters'],**params_for(variants[name]))
        keys=['trend','bars','dip']+(['atr_period','atr_multiple'] if name=='C29_ATR_TRAIL' else ['trail'])
        if name=='C30_GAP_SHOCK': keys+=['atr_period','gap_multiple']
        sensitivities[name]={}
        for key in keys:
            for factor in (.8,1.2):
                value=base.get(key,20)*factor
                if key in ('trend','bars','atr_period'): value=int(round(value))
                label=f'{key}_{factor}'
                sensitivities[name][label]={key:value}
                register_strategy(f'{STUDY}_{name}_{label}',freeze_hash,purpose='prespecified sensitivity, not selectable',parameters={key:value})
    def evaluate(key, universe, variant, period, capital=600, currency='EUR',sizing='all',override=None,keep=True):
        subset={s:frames[s] for s in universe}; start,end=period
        first=max(pd.Timestamp(start,tz='UTC'),max(f.index[0] for f in subset.values()))
        first=next(iter(subset.values())).loc[first:pd.Timestamp(end,tz='UTC')].index[0]
        fx0=fx_rate(rates,first,before=True) if currency=='EUR' else 1.
        p=dict(config['base_parameters'],**params_for(variant)); p.update(override or {})
        # Thin side-check tickers always carry at least triple baseline modeled costs.
        if any(s in ('MRAM','ACMR') for s in universe): p['stress']=max(3,p.get('stress',1))
        raw=replay(subset,start,end,capital*fx0,sizing=sizing,cap=1e12,**p)
        fx=pd.Series([fx_rate(rates,d) if currency=='EUR' else 1. for d in raw['curve'].index],index=raw['curve'].index)
        curve=raw['curve']/fx
        row=metrics(curve,capital,raw['trades']); pnls=sorted(t['pnl_usd'] for t in raw['trades'])
        row.update(currency=currency,actual_start=str(curve.index[0].date()),actual_end=str(curve.index[-1].date()),
            initial_usd=capital*fx0,exposure_pct=raw['mean_exposure_pct'],costs_usd=raw['costs_usd'],
            skipped_count=len(raw['skipped']),fill_violations=raw['fill_violations'],
            max_volume_fraction=raw['max_daily_volume_fraction'],open_position=raw['open_position'],
            closed_trade_currency='USD',concentration={str(n):float(sum(pnls[:-n])) if len(pnls)>n else None for n in (3,5,10)},
            actual_parameters=p,thin_cost_stress=p.get('stress',1),n_entries=sum(e[1]=='buy' for e in raw['events']))
        cash=pd.Series(capital*fx0,index=curve.index)/fx
        bh,holdings=passive_basket(subset,curve.index,capital*fx0,p.get('stress',1))
        tr=trend_basket(subset,curve.index,capital*fx0,p.get('stress',1))
        row['benchmarks']={'cash':metrics(cash,capital),'buyhold':metrics(bh/fx,capital)|{'holdings':holdings},'trend200':metrics(tr/fx,capital)}
        if variant['mode']=='baseline':
            expected=original(subset,start,end,capital*fx0,sizing=sizing,cap=1e12,**{k:v for k,v in p.items() if k!='mode'})
            if not raw['curve'].equals(expected['curve']) or raw['events']!=expected['events']: raise ValueError('Baseline parity failed')
        stop_df=pd.DataFrame(raw['stop_history'])
        monotonic=True if stop_df.empty else all((g.stop.diff().dropna()>=-1e-8).all() for _,g in stop_df.groupby(['ticker','entry_date']))
        case_audit[key]=dict(fill_violations=raw['fill_violations'],max_volume_fraction=raw['max_daily_volume_fraction'],stops_monotonic=bool(monotonic))
        if raw['fill_violations'] or not monotonic or raw['max_daily_volume_fraction']>.01: raise ValueError(f'Execution audit failed {key}')
        if keep:
            raw['curve'].rename('equity_usd').to_frame().assign(equity_base=curve).to_csv(OUT/f'{key}_equity.csv')
            pd.DataFrame(raw['trades']).to_csv(OUT/f'{key}_trades.csv',index=False)
            raw_cache[key]=(raw,curve,capital*fx0)
        return row

    # First inspect IS/WF. No selection is made based on them or subsequent HO.
    for group,capital in all_profiles:
        for name,v in variants.items():
            for period in ('IS','WF'):
                key=f'{group}_{capital}__{name}__{period}'
                results[key]=evaluate(key,groups[group],v,periods[period],capital)
    write_json(OUT/'pre_holdout.json',{'results':results,'selected':None,'freeze_hash':freeze_hash,'note':'No tuning. Historical HO already seen in earlier campaigns.'})
    for group,capital in all_profiles:
        for name,v in variants.items():
            for period in ('HO_SEEN','SINCE_2022','POST_CHATGPT','ALL'):
                key=f'{group}_{capital}__{name}__{period}'
                results[key]=evaluate(key,groups[group],v,periods[period],capital)
            print('MAIN',group,capital,name,flush=True)
    singles={}; tv={}
    for name,v in variants.items():
        for symbol in config['single_checks']:
            for period in ('WF','SINCE_2022','POST_CHATGPT'):
                key=f'{symbol}_600__{name}__{period}'
                singles[key]=evaluate(key,[symbol],v,periods[period])
            if symbol in config['expanded']:
                key=f'TV_{symbol}__{name}'
                tv[key]=evaluate(key,[symbol],v,periods['SINCE_2022'],10000,'USD','one')
        print('SINGLES',name,flush=True)
    stresses={}; sensitivity={}
    for name,v in variants.items():
        for scenario,params in config['stresses'].items():
            key=f'STRESS__{name}__{scenario}'
            stresses[key]=evaluate(key,config['core'],v,periods['WF'],override=params)
        for scenario,params in sensitivities[name].items():
            key=f'SENS__{name}__{scenario}'
            sensitivity[key]=evaluate(key,config['core'],v,periods['WF'],override=params,keep=False)
    causality={n:audit_causality({s:frames[s] for s in config['core']},v,through) for n,v in variants.items()}
    if not all(c['passed'] for rows in causality.values() for c in rows): raise ValueError('Causality audit failed')
    diagnostics={}; daily_matrix={}
    for name in variants:
        chunks=[]; trades=[]; eur_chunks=[]
        for period in ('IS','WF'):
            raw,curve,usd=raw_cache[f'CORE_600__{name}__{period}']; trades+=raw['trades']
            ret=raw['curve'].pct_change(); ret.iloc[0]=raw['curve'].iloc[0]/usd-1; chunks.append(ret)
            eret=curve.pct_change(); eret.iloc[0]=curve.iloc[0]/600-1; eur_chunks.append(eret)
        daily_matrix[name]=pd.concat(chunks)
        tr=np.array([t['return_pct'] for t in trades])
        all_raw,all_curve,_=raw_cache[f'CORE_600__{name}__SINCE_2022']
        erets=pd.concat(eur_chunks).to_numpy()*100
        mc=asdict(monte_carlo_drawdown(erets,n_sims=2000,block_len=20,seed=29030))
        trade_mc=asdict(monte_carlo_drawdown(tr,n_sims=2000,block_len=5,seed=29030)) if len(tr)>1 else None
        diagnostics[name]=dict(dsr_approx=asdict(deflated_sharpe(tr,current_k())),
            monte_carlo_daily_eur=mc,monte_carlo_trade_full_allocation=trade_mc,
            annual_continuous=annual_continuous(all_curve,600),
            attribution=attribution(all_raw['trades'],frames,{s:frames[s] for s in config['context']},events))
    matrix=pd.concat(daily_matrix,axis=1).dropna()
    matrix.to_csv(OUT/'pbo_matrix_IS_WF.csv')
    pbo=asdict(pbo_cscv(matrix.to_numpy()))
    criteria={}
    base=results['CORE_600__BASE__WF']
    for name in ('C29_ATR_TRAIL','C30_GAP_SHOCK'):
        wf=results[f'CORE_600__{name}__WF']; cost=stresses[f'STRESS__{name}__COST2']
        checks={'WF_excess_cash_positive':wf['return_pct']>wf['benchmarks']['cash']['return_pct'],
                'WF_min10trades':wf['n_closed']>=10,'WF_drawdown_20percent_lower':wf['max_drawdown_pct']<=.8*base['max_drawdown_pct'],
                'WF_CAGR_not_lower':wf['cagr_pct']>=base['cagr_pct'],
                'WF_cost2_excess_cash_positive':cost['return_pct']>cost['benchmarks']['cash']['return_pct'],
                'WF_ex_top3_positive':wf['concentration']['3'] is not None and wf['concentration']['3']>0}
        for p in ('IS','HO_SEEN'):
            r=results[f'CORE_600__{name}__{p}'];checks[p+'_excess_cash_positive']=r['return_pct']>r['benchmarks']['cash']['return_pct']
        criteria[name]={'checks':checks,'research_interest':'PASS' if all(checks.values()) else 'FAIL','critic_approval':False,'activation':False}
    paths=[FREEZE,source,Path(__file__),ROOT/'lab/research/regime_swing.py',ROOT/'lab/research/memory_swing.py',fx_path,ROOT/'data/news/events_calendar.csv']+[ROOT/f'data/ohlcv/{s}_1d.csv' for s in frames]
    payload=dict(config=config,through=through,k=current_k(),results=results,singles=singles,tv_python=tv,stresses=stresses,sensitivity=sensitivity,
        diagnostics=diagnostics,pbo=pbo,criteria=criteria,audit={'cases':case_audit,'causality':causality,'baseline_parity':True},
        manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        environment={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__},
        limitations=config['limitations']+['Daily OHLC, no quotes/tick/depth or real-fill reconciliation; authenticity incomplete.','DSR per-trade approximation with dependent samples; PBO only3declared variants, not entire campaign.','Attribution categories overlap; past earnings archive incomplete.'])
    write_json(OUT/'summary.json',payload)
    compact={'through':through,'k':current_k(),'approved':False,'criteria':criteria,'core':{k:v for k,v in results.items() if k.startswith('CORE_600')},
        'capital500':{k:v for k,v in results.items() if k.startswith('CORE_500') and k.endswith('SINCE_2022')},
        'annual':{k:v['annual_continuous'] for k,v in diagnostics.items()},'pbo':pbo}
    write_json(ROOT/'reports/research/C13C_20261009/quant-results.json',compact)
    write_report(payload)
    print(json.dumps({'cases':len(case_audit),'k':current_k(),'criteria':criteria,'pbo':pbo}),flush=True)


def write_report(p):
    # Normalize numpy scalars for report rendering; numerical results are unchanged.
    p=json.loads(json.dumps(p,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
    lines=['# C13C: povijesni režimi i dvije unaprijed zamrznute hipoteze','',
        f"Podaci do {p['through']}; K={p['k']}. Samo lokalne povijesne simulacije, bez naloga. Nijedna strategija nije odobrena.",'',
        'Svaki red počinje zasebno sa600EUR. Cijele dionice, jedna pozicija, bez poluge/doplata. Završni račun uključuje otvorenu poziciju; ne predstavlja svu realiziranu zaradu.','',
        '| Pravilo | Razdoblje | Završno EUR | Prinos | CAGR | Najveći pad | Trgovine | Buyhold EUR | Trend200 EUR |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for key,r in p['results'].items():
        if not key.startswith('CORE_600'): continue
        _,name,period=key.split('__')
        lines.append(f"| {name} | {period} | {r['final']:.2f} | {r['return_pct']:.2f}% | {r['cagr_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | {r['n_closed']} | {r['benchmarks']['buyhold']['final']:.2f} | {r['benchmarks']['trend200']['final']:.2f} |")
    lines+=['','## Neprekidne godišnje promjene računa od2022.','', '| Pravilo | Godina | Početak EUR | Završno EUR | Prinos |','|---|---|---:|---:|---:|']
    for name,d in p['diagnostics'].items():
        for r in d['annual_continuous']:
            lines.append(f"| {name} | {r['year']}{' djelomična' if r['partial_year'] else ''} | {r['starting_value']:.2f} | {r['ending_value']:.2f} | {r['return_pct']:.2f}% |")
    lines+=['','## Kriteriji i ograničenja','',json.dumps(p['criteria'],ensure_ascii=False,indent=2),'',
        'C29 mijenja geometriju stopa prema WilderATR20×3. C30 izbjegava signal na dan downside gap-a većeg od prethodnogATR20. Parametri nisu odabrani prema rezultatu; nijedan kasniji osjetljivi parametar nije odabran za zamjenu.','',
        'IS2016–2020 / WF2021–2023 / HO2024+ već je viđena povijest; novi čisti holdout ne postoji. Datumi poslije1.12.2022. opisni su, ne dokaz uzroka ChatGPT-a.','',
        'Načelo: manje pada nije dovoljno ako kandidat samo ostaje u gotovini; uspoređuju se i prinos/exposure/trgovine. Sve varijante, uključujući loše, ostaju u rezultatu.','',
        'Troškovi su model5bpsroundtrip+1cent/side; MRAM/ACMR najmanje3×. Nema dividendi/poreza/FXnaknada, stvarnih minimalnih brokerskih provizija, intradaybidask ili neovisne povijesti delistiranih dionica. Zbog tih praznina završni authenticity audit nije PASS.','',
        f"PBO na tri varijante IS/WF: {p['pbo']}. DSR/MC su u summary.json; nisu prognoza gubitka ili zarade.",'',
        'Kompletni CSV računa, trgovina i matricaPBO nalaze se u reports/backtest/C29_C30_REGIMES_20261009/. Rezultati su reproduktivni iz zamrznutih pravila i manifesta.' ]
    (ROOT/'reports/research/C13C_20261009/QUANT.md').write_text('\n'.join(lines)+'\n')
    for name,criterion in p['criteria'].items():
        d=p['diagnostics'][name]
        verdict=['# '+name+' — Critic VERDICT','','**FAIL (fail closed)**. Eligible for approved_list: ne.',
            f"Datum2026-10-09; K={p['k']}; freeze={FREEZE.relative_to(ROOT)}.",'',
            '0. Podaci: validate_data exit0 do'+p['through']+'.',
            '1. Lookahead: tri presjeka i tri future-corruption testa; svi prolaze.',
            '2. Freeze integritet: izvorni C13C i baselineengine hash provjeren; novi freeze prije prvog rezultata.',
            '3–4. Predznak/uzorak: vidi IS/WF/HO tablice i broj trgovina; nije zamijenjeno ukupnim CAGR-om.',
            '5. Purge/embargo: bez fitanja modela, svaki period kreće prazno; ranija povijest samo zagrijavanje. Nema novog čistog holdouta — FAIL.',
            '6. Osjetljivost±20%: svaki parametar posebno; svi pokušaji u summary.json, bez odabira pobjednika.',
            '7. Stres:2×,3×,lošiji stop100bps i odgoda2sjednice; svi ishodi prikazani.',
            '8. Koncentracija/režimi: top3/5/10 closedPnL i SPY/SMH/ATR/event segmenti u summary.json.',
            '9. Višestruko testiranje: K='+str(p['k'])+'; dodatni profili i osjetljivosti upisani.',
            '10. DSRapprox='+json.dumps(d['dsr_approx'])+'; PBO='+json.dumps(p['pbo'])+'.',
            '11. MC:2000iid+2000block(20dnevnih) i block5trgovina; dailyEURp95='+str(d['monte_carlo_daily_eur']['block_dd_pct']['95'])+'.',
            '12. Izvedivost:0rawOHLCfill prekršaja, veličina<1%dnevnogvolumena, monotoni stopovi. Quote/tickdepth nisu dostupni.',
            '13. HOzadnji: novi rezultati izračunati poslije IS/WF datoteke, ali starija povijest već viđena — FAIL za čistu potvrdu.',
            '14. Završni audit: nema realfill/tick/spread reconciliation i nezavisnog kompletnog providera — NEPOTPUNO / FAIL.',
            '', 'Istraživački kriteriji: '+json.dumps(criterion,ensure_ascii=False), '',
            'Nije tvrdnja da nema nikakvog povijesnog profita; nije dovoljno dokazana prednost. C13C/app/approved_list nisu mijenjani. Signal PRIČEKAJ.']
        (ROOT/f'reports/gate/2026-10-09_{name}_VERDICT.md').write_text('\n'.join(verdict)+'\n')


if __name__=='__main__': run()
