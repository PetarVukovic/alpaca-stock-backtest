"""Historical C13C single-account replay, using the existing lab fill engine."""
import sys
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from lab.contracts import FrozenStrategy
from lab.data import load_bars
from lab.engine import simulate
from lab.strategies.registry import signals


def replay(frames, strategy, fraction=1.0, fixed_cap=True, start='2021-01-01'):
    dates = frames['MU'].index
    for frame in frames.values():
        assert frame.index.equals(dates), 'Unequal calendars'
    entries = {s: signals(f, strategy)[0] for s, f in frames.items()}
    dates = dates[dates >= start]
    equity = pd.Series(600.0, index=dates)
    cash, i, trades = 600.0, 0, []
    while i < len(dates)-1:
        ts = dates[i]
        symbol = next((s for s in strategy.universe if entries[s].loc[ts]), None)
        if symbol is None:
            equity.iloc[i] = cash
            i += 1
            continue
        sample = frames[symbol].loc[ts:].copy()
        entry = pd.Series(False, index=sample.index)
        entry.iloc[0] = True
        sim = simulate(sample, entry, entry & False, strategy)
        if not sim.trades:
            break
        trade = sim.trades[0].copy()
        end = pd.Timestamp(trade['exit_time'])
        allocation = min(600.0, cash) if fixed_cap else cash*fraction
        # Engine uses a fixed 500 USD book. Scale its account path to a
        # constant-currency 600 EUR equivalent, retaining the frozen size cap.
        path = sim.equity.loc[:end]
        equity.loc[path.index] = cash + (path-500.0)*allocation/500.0
        trade.update(signal_time=ts.isoformat(), allocation_equivalent_eur=allocation,
                     pnl_equivalent_eur=allocation*trade['net_return'])
        cash += trade['pnl_equivalent_eur']
        trades.append(trade)
        i = dates.get_loc(end)
        # A signal on the exit-day close may schedule the next day's entry.
        # Even an entry-bar stop cannot create a second entry on the same day.
    equity.iloc[i:] = cash
    return equity, pd.DataFrame(trades)


def summary(equity, trades):
    peak = equity.cummax().clip(lower=600)
    annual, last = [], 600.0
    for year, sample in equity.groupby(equity.index.year):
        final = float(sample.iloc[-1])
        annual.append({'year':int(year), 'start':last, 'end':final,
                       'pnl':final-last, 'return_pct':(final/last-1)*100})
        last = final
    returns = trades.net_return
    wins = trades.loc[returns > 0, 'pnl_equivalent_eur'].sum()
    losses = -trades.loc[returns < 0, 'pnl_equivalent_eur'].sum()
    return {'start':str(equity.index[0].date()),'end':str(equity.index[-1].date()),
            'final':float(equity.iloc[-1]),'pnl':float(equity.iloc[-1]-600),
            'return_pct':float((equity.iloc[-1]/600-1)*100),
            'max_drawdown_pct':float((1-equity/peak).max()*100),
            'max_drawdown_eur':float((peak-equity).max()),
            'trades':len(trades),'win_rate_pct':float((returns>0).mean()*100),
            'best_trade_pct':float(returns.max()*100),'worst_trade_pct':float(returns.min()*100),
            'profit_factor':float(wins/losses), 'by_ticker':trades.ticker.value_counts().to_dict(),
            'forced_final_trades':int((trades.reason=='period_end').sum()),'annual':annual}


def main():
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py')],cwd=ROOT,check=True)
    freeze = ROOT/'strategies/frozen/2026-10-05_C13C_TREND_DIP5_TRAIL.json'
    strategy = FrozenStrategy.model_validate_json(freeze.read_text())
    frames = {s:load_bars(s) for s in strategy.universe}
    end = min(f.index[-1] for f in frames.values())
    frames = {s:f.loc[:end] for s,f in frames.items()}
    output = ROOT/'reports/backtest'
    results = {}
    for name, fraction, fixed in [('fixed_cap_600',1.0,True),('full_reinvestment',1.0,False),('risk2pct',0.2,False)]:
        equity,trades = replay(frames,strategy,fraction,fixed)
        results[name] = summary(equity,trades)
        trades.to_csv(output/f'C13C_2021_{name}_trades.csv',index=False)
        equity.rename('equivalent_eur').to_csv(output/f'C13C_2021_{name}_equity.csv')
    audit = {'signal_prefix_differences':{},'portfolio_prefix_differences':{},'fill_violations':0}
    full_equity, full_trades = replay(frames,strategy)
    for cutoff in ['2022-12-30','2023-12-29','2025-12-31']:
        cut = {s:f.loc[:cutoff].copy() for s,f in frames.items()}
        for s in frames:
            a=signals(frames[s],strategy)[0].loc[:cutoff]
            b=signals(cut[s],strategy)[0]
            audit['signal_prefix_differences'][s+cutoff]=int((a!=b).sum())
        e,t=replay(cut,strategy)
        # Terminal liquidation is an explicit reporting convention, not a decision.
        audit['portfolio_prefix_differences'][cutoff]=float((e.iloc[:-1]-full_equity.reindex(e.index).iloc[:-1]).abs().max())
    corrupt = {s:f.copy() for s,f in frames.items()}
    for f in corrupt.values():
        f.loc[f.index > '2024-01-01',['open','high','low','close']] *= 10
    e,t=replay(corrupt,strategy)
    audit['future_corruption_equity_diff_before_2024']=float((e.loc[:'2023-12-31']-full_equity.loc[:'2023-12-31']).abs().max())
    max_participation=0.0
    for row in full_trades.to_dict('records'):
        f=frames[row['ticker']]
        for key,side in [('entry_time','buy'),('exit_time','sell')]:
            bar=f.loc[pd.Timestamp(row[key])]
            price=row['entry_price' if side=='buy' else 'exit_price']
            delta=price*strategy.costs.round_trip_bps/20000+0.01
            raw=(price-0.01)/(1+strategy.costs.round_trip_bps/20000) if side=='buy' else (price+0.01)/(1-strategy.costs.round_trip_bps/20000)
            if not bar.low-1e-8 <= raw <= bar.high+1e-8 or bar.volume <= 0:
                audit['fill_violations']+=1
            max_participation=max(max_participation,row['quantity']/bar.volume)
    audit['max_fill_volume_fraction_engine500usd']=max_participation
    audit['limitations']='Daily OHLC; no historical quotes, ticks, depth or real broker fills. Gap stops use open; new highs affect next bar. No dividends, tax, FX changes or conversion fees. Fractional shares assumed. 600 EUR is a scaled constant-currency equivalent of the 500 USD frozen book, not actual historical EUR wealth.'
    results['audit']=audit
    results['provenance']={'freeze_sha256':hashlib.sha256(freeze.read_bytes()).hexdigest(),
                          'data_sha256':{s:hashlib.sha256((ROOT/f'data/ohlcv/{s}_1d.csv').read_bytes()).hexdigest() for s in frames}}
    (output/'C13C_2021_replay.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
