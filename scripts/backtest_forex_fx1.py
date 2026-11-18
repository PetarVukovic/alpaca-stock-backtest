"""FX1 research-only EUR cash/USD cash simulator. No broker connectivity.

Midpoint OHLC is not executable bid/ask evidence. Financing is excluded; report
results as conditional on zero cash interest, never as an executable broker P&L.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Params:
    fast: int = 50
    slow: int = 200
    atr: int = 20
    stop_multiple: float = 2.0
    max_hold: int = 60
    risk: float = .005
    cap: float = .95
    adverse: float = .0001
    cost_multiplier: float = 1.0
    embargo: int = 5


def load_data(path, through=None):
    frame = pd.read_csv(path)
    frame.columns = frame.columns.str.lower()
    frame['date'] = pd.to_datetime(frame.date).dt.strftime('%Y-%m-%d')
    if through is not None:
        frame = frame.loc[frame.date <= through].copy()
    if frame.empty or not frame.date.is_monotonic_increasing:
        raise ValueError('Empty or unordered dates')
    if 'timestamp' in frame:
        timestamps = pd.to_datetime(frame.timestamp, utc=True, errors='raise')
        if timestamps.isna().any() or timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
            raise ValueError('Missing, duplicate, or unordered timestamps')
    elif frame.date.duplicated().any():
        raise ValueError('Duplicate dates without distinct provider timestamps')
    prices = frame[['open', 'high', 'low', 'close']].astype(float)
    if not np.isfinite(prices).all().all() or (prices <= 0).any().any():
        raise ValueError('Invalid prices')
    if ((prices.high < prices[['open', 'close', 'low']].max(axis=1)) |
            (prices.low > prices[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('Invalid OHLC envelope')
    frame[prices.columns] = prices
    return frame.reset_index(drop=True)


def fee_eur(notional_usd, midpoint, p):
    return max(2., abs(notional_usd) * .00002) * p.cost_multiplier / midpoint


def simulate(frame, start, end, initial=1000., params=None, liquidate=True):
    """Return daily and closed-trade frames; prior bars only warm indicators.

    Setting liquidate=False supports prefix-invariance audits. 60 held bars means
    entry day counts as the first bar, exit on next open after bar 60.
    """
    p = params or Params()
    if initial <= 0 or not 0 < p.cap < 1 or not 0 < p.risk < 1:
        raise ValueError('Invalid cash or sizing parameters')
    d = frame.copy().reset_index(drop=True)
    prev_close = d.close.shift(1)
    tr = pd.concat([d.high-d.low, (d.high-prev_close).abs(), (d.low-prev_close).abs()], axis=1).max(axis=1)
    d['atr_prev'] = tr.rolling(p.atr).mean().shift(1)
    fast = d.close.rolling(p.fast).mean()
    slow = d.close.rolling(p.slow).mean()
    d['ready'] = slow.shift(1).notna() & fast.shift(1).notna() & d.atr_prev.notna()
    d['enter'] = ((d.close < slow) & (fast < slow)).shift(1, fill_value=False)
    sample = d.loc[(d.date >= start) & (d.date <= end)]
    eur, usd, position = float(initial), 0., None
    daily, trades = [], []
    adverse = p.adverse * p.cost_multiplier

    def close_position(midpoint, reason, date, timestamp):
        nonlocal eur, usd, position
        ask = midpoint + adverse
        exit_fee = fee_eur(usd, midpoint, p)
        proceeds = usd / ask
        gross = position['units_eur'] * (position['entry_midpoint']/midpoint - 1)
        net = proceeds - position['units_eur'] - position['entry_fee_eur'] - exit_fee
        trades.append(dict(**position, exit_date=date, exit_timestamp=timestamp, exit_midpoint=midpoint,
                           exit_ask=ask, exit_fee_eur=exit_fee, reason=reason,
                           gross_eur=gross, net_eur=net,
                           spread_slippage_eur=gross-net-position['entry_fee_eur']-exit_fee,
                           return_on_entry_equity=net/position['entry_equity']))
        eur += proceeds-exit_fee
        usd, position = 0., None

    for bar, (_, row) in enumerate(sample.iterrows()):
        timestamp = row.get('timestamp', row.date)
        closed = False
        if position is not None:
            if row.open >= position['stop_midpoint']:
                close_position(row.open, 'stop_gap', row.date, timestamp)
                closed = True
            elif not row.enter or position['held_bars'] >= p.max_hold:
                close_position(row.open, 'signal' if not row.enter else 'max_hold', row.date, timestamp)
                closed = True
            elif row.high >= position['stop_midpoint']:
                close_position(position['stop_midpoint'], 'stop', row.date, timestamp)
                closed = True
        if position is None and not closed and bar >= p.embargo and row.ready and row.enter:
            bid = row.open-adverse
            stop = row.open+p.stop_multiple*row.atr_prev
            if bid <= 0:
                raise ValueError('Costs exceed price')
            def feasible(units):
                entry_fee = fee_eur(units*bid, row.open, p)
                exit_fee = fee_eur(units*bid, stop, p)
                loss = units*(1-bid/(stop+adverse))+entry_fee+exit_fee
                return units+entry_fee <= eur and loss <= p.risk*eur
            low, high = 0, int(np.floor(p.cap*eur))
            while low < high:
                middle = (low+high+1)//2
                if feasible(middle):
                    low = middle
                else:
                    high = middle-1
            units = low
            if units > 0:
                entry_fee = fee_eur(units*bid, row.open, p)
                position = dict(entry_date=row.date, entry_timestamp=timestamp, entry_midpoint=row.open,
                                entry_bid=bid, units_eur=units, entry_equity=eur,
                                entry_fee_eur=entry_fee, stop_midpoint=stop, held_bars=0)
                eur -= units+entry_fee
                usd = units*bid
                if row.high >= stop:
                    close_position(stop, 'entry_day_stop', row.date, timestamp)
        if position is not None:
            position['held_bars'] += 1
        if liquidate and bar == len(sample)-1 and position is not None:
            close_position(row.close, 'fold_end', row.date, timestamp)
        value = eur+usd/row.close
        if eur < -1e-8 or usd < -1e-8:
            raise AssertionError('Negative cash / leverage')
        daily.append(dict(date=row.date, timestamp=timestamp, eur_cash=eur, usd_cash=usd,
                          equity_eur=value, usd_exposure_eur=usd/row.close,
                          exposure=usd/row.close/value if value else 0.,
                          midpoint=row.close))
    return pd.DataFrame(daily), pd.DataFrame(trades)


def metrics(daily, trades, initial):
    if daily.empty:
        return {'error': 'empty fold'}
    equity = np.r_[initial, daily.equity_eur.to_numpy()]
    returns = equity[1:]/equity[:-1]-1
    years = max((pd.Timestamp(daily.date.iloc[-1])-pd.Timestamp(daily.date.iloc[0])).days/365.25, 1/365.25)
    pnl = trades.net_eur.to_numpy() if len(trades) else np.array([])
    loss = -pnl[pnl < 0].sum()
    return dict(initial_eur=initial, final_eur=float(equity[-1]),
                net_eur=float(equity[-1]-initial), total_return=float(equity[-1]/initial-1),
                cagr=float((equity[-1]/initial)**(1/years)-1),
                max_drawdown=float(np.min(equity/np.maximum.accumulate(equity)-1)),
                sharpe=float(np.mean(returns)/np.std(returns, ddof=1)*np.sqrt(252)) if len(returns)>1 and np.std(returns)>0 else None,
                trades=len(trades), profit_factor=float(pnl[pnl>0].sum()/loss) if loss>0 else None,
                ex_top3_net_eur=float(pnl.sum()-np.sort(pnl[pnl>0])[-3:].sum()),
                exposure_mean=float(daily.exposure.mean()), benchmark_eur_cash_return=0.)


def bootstrap(trades, seed=13102026, n=2000):
    """Trade-return bootstrap, approximate sizing; not a full path re-simulation."""
    if len(trades)<2:
        return {'warning': 'too_few_trades'}
    r = trades.return_on_entry_equity.to_numpy()
    rng = np.random.default_rng(seed)
    results = {}
    for block in (1, 5):
        starts = rng.integers(0, len(r), size=(n, int(np.ceil(len(r)/block))))
        indices = ((starts[:,:,None]+np.arange(block)) % len(r)).reshape(n,-1)[:,:len(r)]
        wealth = np.cumprod(1+r[indices], axis=1)
        peaks = np.maximum.accumulate(np.c_[np.ones(n), wealth], axis=1)[:,1:]
        dd = (wealth/peaks-1).min(axis=1)
        total = wealth[:,-1]-1
        results[f'block_{block}'] = dict(total_return_quantiles=np.quantile(total,[.05,.5,.95]).tolist(),
                                        max_drawdown_quantiles=np.quantile(dd,[.05,.5,.95]).tolist(),
                                        probability_negative=float(np.mean(total<0)))
    return dict(samples=n, seed=seed, caveat='Approximate trade-return resampling; no exact sizing/cash-path rerun', **results)


FOLDS = {'IS': ('2016-01-01','2020-12-31'), 'WF2021': ('2021-01-01','2021-12-31'),
         'WF2022': ('2022-01-01','2022-12-31'), 'WF2023': ('2023-01-01','2023-12-31'),
         'WF': ('2021-01-01','2023-12-31'), 'HO': ('2024-01-01','2026-10-09')}


def preflight(data_path, frozen_bytes, frozen, root):
    validation = json.loads((root/'reports/data/2026-10-13_forex_validation.json').read_text())
    registration = json.loads((root/'reports/data/2026-10-13_forex_registration.json').read_text())
    required = {'equal_arrays','sorted','unique','positive_finite','ohlc_range','no_large_gaps'}
    if not required.issubset(validation['checks']) or not all(v is True for v in validation['checks'].values()):
        raise ValueError('Forex data validation failed')
    if validation['csv_sha256'] != hashlib.sha256(Path(data_path).read_bytes()).hexdigest():
        raise ValueError('Validated CSV hash mismatch')
    if registration['freeze_sha256'] != hashlib.sha256(frozen_bytes).hexdigest():
        raise ValueError('Registered freeze hash mismatch')
    expected_sensitivity = dict(fast=[40,60],slow=[160,240],atr=[16,24],stop_atr=[1.6,2.4],max_hold=[48,72])
    if frozen['sensitivity'] != expected_sensitivity:
        raise ValueError('Frozen sensitivities mismatch')
    expected_scenarios = {'base','cost_1.5','cost_2','cost_3','capital_500','capital_2000'}
    expected_scenarios.update(f'{key}_{value}' for key,values in expected_sensitivity.items() for value in values)
    observed = [x['scenario'] for x in registration['scenarios']]
    if len(observed) != 16 or set(observed) != expected_scenarios:
        raise ValueError('Scenario registration mismatch')
    v=frozen['validation']
    if any(tuple(v[k]) != FOLDS[k] for k in ('IS','WF','HO')) or v['WF_annual'] != [2021,2022,2023]:
        raise ValueError('Frozen fold mismatch')
    if not all(v[k] is True for k in ('split_cash_reset','holdout_last','no_fitting')) or v['split_final_liquidation'] != 'last close adverse plus fee':
        raise ValueError('Frozen fold policy mismatch')
    subprocess.run([sys.executable,str(root/'scripts/validate_data.py'),'--through',
                    '2026-10-09','--report',str(root/'reports/data/2026-10-13_forex_lab_gate.md')],check=True,cwd=root)
    return registration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='data/ohlcv/EURUSD_1d.csv')
    parser.add_argument('--freeze', default='strategies/frozen/2026-10-13_FX1_EURUSD_CASH_TREND.json')
    parser.add_argument('--phase', choices=['pre','holdout'], required=True)
    parser.add_argument('--output', default='reports/backtest')
    args = parser.parse_args()
    frozen_bytes = Path(args.freeze).read_bytes()
    frozen = json.loads(frozen_bytes)
    if frozen.get('id') != 'FX1_EURUSD_CASH_TREND':
        raise ValueError('Wrong freeze')
    expected = dict(fast=50, slow=200, atr=20, stop_atr=2, max_hold=60,
                    risk_fraction=.005, cash_cap=.95, primary_capital_eur=1000,
                    capital_eur=[500,1000,2000], cutoff='2026-10-09')
    if any(frozen.get(k) != v for k,v in expected.items()):
        raise ValueError('Frozen strategy differs from implemented parameters')
    expected_costs = dict(commission_usd_min=2, commission_rate=.00002,
                          half_spread_pips=.5, slippage_pips=.5, pip=.0001,
                          stress=[1,1.5,2,3], interest_base=0)
    if any(frozen['costs'].get(k) != v for k,v in expected_costs.items()):
        raise ValueError('Frozen costs differ from implementation')
    if frozen['bootstrap'] != dict(runs=2000,block_trades=5,seed=13102026):
        raise ValueError('Frozen bootstrap differs from implementation')
    if frozen['validation']['embargo_bars'] != 5:
        raise ValueError('Frozen embargo differs from implementation')
    registration = preflight(args.data,frozen_bytes,frozen,Path(__file__).resolve().parents[1])
    frame = load_data(args.data, through='2023-12-31' if args.phase=='pre' else '2026-10-09')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    variants = [('base',Params(),1000.)]
    variants += [(f'cost{x}',replace(Params(),cost_multiplier=x),1000.) for x in (1.5,2.,3.)]
    variants += [(f'capital{x}',Params(),float(x)) for x in (500,2000)]
    variants += [(f'{key}{value}',replace(Params(),**{key:value}),1000.)
                 for key,values in dict(fast=(40,60),slow=(160,240),atr=(16,24),
                                        stop_multiple=(1.6,2.4),max_hold=(48,72)).items()
                 for value in values]
    records = {}
    folds = ['HO'] if args.phase=='holdout' else ['IS','WF2021','WF2022','WF2023','WF']
    for name,params,initial in variants:
        for fold in folds:
            daily,trades = simulate(frame,*FOLDS[fold],initial,params)
            key = f'{name}_{fold}'
            daily.to_csv(out/f'FX1_{key}_daily.csv',index=False)
            trades.to_csv(out/f'FX1_{key}_trades.csv',index=False)
            records[key] = dict(parameters=asdict(params),metrics=metrics(daily,trades,initial),
                                bootstrap=bootstrap(trades) if name=='base' else None)
    payload = dict(freeze_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
                   data_sha256=hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
                   registration=registration,
                   phase=args.phase, assumptions=['midpoint+modeled_costs','zero_cash_interest',
                   'no_executable_bid_ask_evidence','research_only','no_broker_orders'],results=records)
    (out/f'FX1_{args.phase}_results.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v['metrics'] for k,v in records.items() if k.startswith('base_')},indent=2))


if __name__ == '__main__':
    main()
