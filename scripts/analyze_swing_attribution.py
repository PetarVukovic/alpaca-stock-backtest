"""Descriptive, retrospective attribution; never changes strategy or calls a broker."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from lab.data import load_bars
from lab.research.memory_swing import replay,entry_signals

OUT = ROOT / 'reports/backtest/C24_ATTRIBUTION_20261006'


def forward_excursions(frame, exit_day, reference, horizons=(5,20,60)):
    """Exclude exit bar: its high/low cannot be ordered after the stop with daily OHLC."""
    future = frame.loc[frame.index > pd.Timestamp(exit_day,tz='UTC')]
    rows=[]
    for horizon in horizons:
        sample=future.iloc[:horizon]
        rows.append(dict(horizon=horizon,observed_sessions=len(sample),censored=len(sample)<horizon,
            terminal_return_pct=100*(float(sample.close.iloc[-1])/reference-1) if len(sample) else None,
            favorable_excursion_pct=100*(float(sample.high.max())/reference-1) if len(sample) else None,
            adverse_excursion_pct=100*(float(sample.low.min())/reference-1) if len(sample) else None))
    return rows


def attribute(frames, result, start, end, horizons=(5,20,60)):
    dates=result['curve'].index
    frames={s:f.loc[:end] for s,f in frames.items()}
    signals={s:entry_signals(f) for s,f in frames.items()}
    trends={s:(f.close > f.close.rolling(200).mean()) for s,f in frames.items()}
    events={str(d.date()):[] for d in dates}
    for event in result['events']:events[event[0]].append(event)
    entries=[e for e in result['events'] if e[1]=='buy']
    positions={d:i for i,d in enumerate(dates)}
    future_rows=[]; waits=[]
    for number,trade in enumerate(result['trades']):
        symbol=trade['ticker'];day=pd.Timestamp(trade['exit_date'],tz='UTC');i=positions[day]
        for row in forward_excursions(frames[symbol],trade['exit_date'],trade['raw_exit'],horizons):
            future_rows.append(dict(trade=number,ticker=symbol,exit_date=trade['exit_date'],raw_exit=trade['raw_exit'],trade_pnl_usd=trade['pnl_usd'],**row))
        later=dates[i:]
        matches=[d for d in later if signals[symbol].loc[d]]
        signal_day=matches[0] if matches else None
        entry=next((e for e in entries if e[0]>trade['exit_date']),None)
        waits.append(dict(trade=number,ticker=symbol,exit_date=trade['exit_date'],
            next_same_ticker_signal=str(signal_day.date()) if signal_day is not None else None,
            same_ticker_signal_wait_sessions=positions[signal_day]-i if signal_day is not None else None,
            signal_wait_censored=signal_day is None,observed_remaining_sessions=len(dates)-i-1,
            next_portfolio_entry=entry[0] if entry else None,next_portfolio_ticker=entry[2] if entry else None,
            portfolio_entry_wait_sessions=positions[pd.Timestamp(entry[0],tz='UTC')]-i if entry else None,
            portfolio_wait_censored=entry is None))
    daily=[]; collisions=[]; held=None
    for day in dates:
        stamp=str(day.date())
        for event in events[stamp]: held=event[2] if event[1]=='buy' else None
        candidates=[s for s in frames if signals[s].loc[day]]
        row=dict(date=stamp,held_at_close=held,flat_at_close=held is None,candidates=','.join(candidates))
        for symbol in frames:
            enough=len(frames[symbol].loc[:day])>=200
            row[symbol+'_reason']=('insufficient_history' if not enough else 'trend_false' if not trends[symbol].loc[day]
                                   else 'valid_signal' if signals[symbol].loc[day] else 'trend_true_dip_false')
        row['portfolio_reason']=('held' if held else 'valid_signal_pending_next_open' if candidates
            else 'no_trend_in_core' if not any(trends[s].loc[day] for s in frames) else 'trend_present_no_dip')
        row['other_signals_while_held']=','.join(s for s in candidates if s!=held) if held else ''
        daily.append(row)
        if held is None and len(candidates)>1:
            collisions.append(dict(date=stamp,candidates=','.join(candidates),chosen=candidates[0],suppressed=','.join(candidates[1:])))
    return dict(forward=future_rows,waits=waits,daily=daily,collisions=collisions)


def flat_spells(daily,frames,rates=None):
    spells=[]; active=[]
    for row in daily+[{'flat_at_close':False}]:
        if row['flat_at_close']:
            active.append(row['date'])
        elif active:
            a,b=pd.Timestamp(active[0],tz='UTC'),pd.Timestamp(active[-1],tz='UTC')
            returns={symbol:100*(float(frame.loc[b,'close'])/float(frame.loc[a,'close'])-1) for symbol,frame in frames.items()}
            fx_change=None
            if rates is not None:
                from scripts.run_memory_swing import fx_rate
                fx_change=100*(fx_rate(rates,a)/fx_rate(rates,b)-1)
            spells.append(dict(start=active[0],end=active[-1],flat_closes=len(active),
                **{symbol+'_price_return_pct':value for symbol,value in returns.items()},
                mean_stock_price_return_pct=float(np.mean(list(returns.values()))),usd_cash_eur_translation_pct=fx_change))
            active=[]
    return sorted(spells,key=lambda item:item['flat_closes'],reverse=True)


def summarize(rows,result):
    forward=pd.DataFrame(rows['forward']);waits=pd.DataFrame(rows['waits']);daily=pd.DataFrame(rows['daily'])
    flat=daily[daily.flat_at_close]
    summary=dict(n_trades=len(result['trades']),n_days=len(daily),flat_closes=len(flat),
        flat_close_pct=100*len(flat)/len(daily),invested_closes=len(daily)-len(flat),invested_close_pct=100*(len(daily)-len(flat))/len(daily),longest_flat_spells=rows['flat_spells'][:5],flat_reasons=flat.portfolio_reason.value_counts().to_dict(),
        ticker_reasons_while_flat={s:flat[s+'_reason'].value_counts().to_dict() for s in ['MU','WDC','STX']},
        collision_count=len(rows['collisions']),collisions_chosen=pd.Series([r['chosen'] for r in rows['collisions']],dtype=str).value_counts().to_dict(),
        held_days_with_competing_signals=int((daily.other_signals_while_held!='').sum()),
        skipped_unaffordable=len(result['skipped']),forward={},waits={})
    for h in [5,20,60]:
        sample=forward[forward.horizon==h];complete=sample[~sample.censored]
        summary['forward'][h]=dict(total=len(sample),complete=len(complete),censored=int(sample.censored.sum()),
            fraction_positive_pct=100*float((complete.terminal_return_pct>0).mean()),
            median_return_pct=float(complete.terminal_return_pct.median()),mean_return_pct=float(complete.terminal_return_pct.mean()),
            median_favorable_excursion_pct=float(complete.favorable_excursion_pct.median()),
            median_adverse_excursion_pct=float(complete.adverse_excursion_pct.median()))
    for field in ['same_ticker_signal_wait_sessions','portfolio_entry_wait_sessions']:
        valid=waits[field].dropna()
        summary['waits'][field]=dict(observed=len(valid),censored=len(waits)-len(valid),median=float(valid.median()),max=float(valid.max()))
    return summary


def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    if hashlib.sha256((ROOT/protocol['source_strategy']).read_bytes()).hexdigest()!=protocol['source_sha256']:
        raise ValueError('Frozen rule changed')
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--through',protocol['through'],'--report',str(OUT/'DATA_CHECK.md')],check=True,cwd=ROOT)
    baseline=json.loads((ROOT/protocol['baseline_source']).read_text())
    frames={s:load_bars(s,through=protocol['through']) for s in protocol['core']}
    from scripts.run_memory_swing import fx_table
    rates=fx_table(ROOT/'reports/backtest/C22_FULL_CASH_SWING_20261006/ecb-history.xml')
    summary={}
    for label,(start,end) in protocol['periods'].items():
        expected=baseline['results'][f'CORE__SMALL_600EUR_ALL__{label}']
        result=replay(frames,start,end,expected['initial_usd'],sizing='all',cap=1e12)
        if abs(float(result['curve'].iloc[-1])-expected['final_usd'])>1e-7 or len(result['trades'])!=expected['n_closed']:
            raise ValueError('C22 baseline no longer reproduces')
        rows=attribute(frames,result,start,end,protocol['horizons_sessions'])
        rows['flat_spells']=flat_spells(rows['daily'],frames,rates)
        for spell in rows['flat_spells']:
            within=[r for r in rows['daily'] if spell['start'] <= r['date'] <= spell['end']]
            spell['reason_counts']=pd.Series([r['portfolio_reason'] for r in within]).value_counts().to_dict()
            exits=[e for e in result['events'] if e[1]=='sell' and e[0] <= spell['start']]
            later_entries=[e for e in result['events'] if e[1]=='buy' and e[0] > spell['end']]
            spell['preceding_exit_date']=exits[-1][0] if exits else None
            spell['preceding_exit_ticker']=exits[-1][2] if exits else None
            spell['next_entry_date']=later_entries[0][0] if later_entries else None
            spell['next_entry_ticker']=later_entries[0][2] if later_entries else None
        for kind,content in rows.items():pd.DataFrame(content).to_csv(OUT/f'{label}_{kind}.csv',index=False)
        summary[label]=summarize(rows,result)
    package=dict(protocol=protocol,results=summary,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/analyze_swing_attribution.py','lab/research/memory_swing.py',protocol['baseline_source']]},
                 data_hashes={s:hashlib.sha256((ROOT/f'data/ohlcv/{s}_1d.csv').read_bytes()).hexdigest() for s in frames})
    (OUT/'summary.json').write_text(json.dumps(package,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x),allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
