"""Bounded, frozen C23 research: regime attribution and adverse execution, never orders."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from lab.data import load_bars
from lab.ledger import current_k
from lab.research.memory_swing import replay, metrics, benchmark
from scripts.run_memory_swing import fx_table, fx_rate, write_json


def regime_labels(smh):
    """Entry-day labels from prior completed SMH close; thresholds never fitted."""
    trend = smh.close.rolling(200, min_periods=200).mean()
    volatility = smh.close.pct_change().rolling(20, min_periods=20).std(ddof=1)
    valid = trend.notna() & volatility.notna()
    labels = pd.Series(np.where(smh.close > trend, 'UP', 'DOWN'), index=smh.index)
    labels = labels.mask(volatility > .02, 'HIGH_VOL')
    return labels.where(valid, 'UNKNOWN').shift(1).fillna('UNKNOWN')


def regime_attribution(trades, labels):
    groups = {}
    for trade in trades:
        regime = str(labels.get(pd.Timestamp(trade['entry_date'], tz='UTC'), 'UNKNOWN'))
        groups.setdefault(regime, []).append(trade)
    return {regime: {
        'n_closed': len(rows), 'pnl_usd': float(sum(t['pnl_usd'] for t in rows)),
        'mean_trade_return_pct': float(np.mean([t['return_pct'] for t in rows])),
        'median_trade_return_pct': float(np.median([t['return_pct'] for t in rows])),
        'win_rate_pct': 100 * sum(t['pnl_usd'] > 0 for t in rows) / len(rows),
        'worst_trade_return_pct': float(min(t['return_pct'] for t in rows)),
    } for regime, rows in sorted(groups.items())}


def select_pre_holdout(results, baseline):
    """No HO argument/access: reject candidates that cannot beat uninvested USD in EUR."""
    decisions = {}
    baseline_dd = results[baseline]['WF']['max_drawdown_pct']
    for variant, periods in results.items():
        reasons = []
        for period in ('IS', 'WF'):
            row = periods[period]
            if row['return_pct'] <= 0:
                reasons.append(f'{period}: nonpositive EUR return')
            if row['return_pct'] <= row['usd_cash_benchmark']['return_pct']:
                reasons.append(f'{period}: no excess over USD cash converted to EUR')
        wf = periods['WF']
        if wf['n_closed'] < 10:
            reasons.append('WF: fewer than 10 closed trades')
        if wf['max_drawdown_pct'] > baseline_dd:
            reasons.append('WF: drawdown exceeds baseline')
        if wf['sharpe'] is None or not np.isfinite(wf['sharpe']):
            reasons.append('WF: Sharpe unavailable')
        decisions[variant] = {'eligible': not reasons, 'reasons': reasons, 'wf_sharpe': wf['sharpe']}
    eligible = [v for v, d in decisions.items() if d['eligible']]
    chosen = max(eligible, key=lambda v: (decisions[v]['wf_sharpe'], v)) if eligible else None
    return {'selected': chosen, 'decisions': decisions,
            'criterion': 'Positive EUR and above USD cash in IS+WF, WF>=10 closed, WF DD<=baseline, highest WF Sharpe',
            'prior_holdout_seen': True, 'approval': False}


def run_case(frames, smh, rates, variant, period, config, stress=None):
    start, end = period
    subset = {s: frames[s] for s in config['universe']}
    index = next(iter(subset.values())).loc[start:end].index
    if index.empty:
        raise ValueError('No history for requested study period')
    initial_fx = fx_rate(rates, index[0], before=True)
    initial_eur = float(config['initial_eur'])
    capital = initial_eur * initial_fx
    parameters = dict(config['base_parameters'], sizing=variant['sizing'], cap=config['research_cap_usd'])
    parameters.update({k:v for k,v in variant.items() if k in ('trend','bars','dip','trail')})
    if variant.get('market_filter'):
        parameters['market_filter'] = (smh.close > smh.close.rolling(200).mean()).fillna(False)
    parameters.update(stress or {})
    result = replay(subset, start, end, capital, **parameters)
    if result is None:
        raise ValueError('Study replay produced no curve')
    curve = result['curve']
    fx = pd.Series([fx_rate(rates, day) for day in curve.index], index=curve.index)
    euro = curve / fx
    summary = metrics(euro, initial_eur, result['trades'])
    cash = pd.Series(capital, index=curve.index) / fx
    passive, holdings = benchmark(subset, curve.index, capital, 'equal')
    summary.update(initial_usd=capital, initial_eurusd=initial_fx,
                   usd_cash_benchmark=metrics(cash, initial_eur),
                   passive_equal_benchmark=metrics(passive / fx, initial_eur) | {'holdings': holdings},
                   currency='EUR', trade_statistics_currency='USD',
                   exposure_pct=result['mean_exposure_pct'], costs_usd=result['costs_usd'],
                   fill_violations=result['fill_violations'],
                   max_daily_volume_fraction=result['max_daily_volume_fraction'],
                   open_position=result['open_position'], skipped_count=len(result['skipped']),
                   regimes=regime_attribution(result['trades'], regime_labels(smh)),
                   excess_cash_return_pct=summary['return_pct']-metrics(cash, initial_eur)['return_pct'])
    return summary, result, euro


def block_bootstrap_account(returns, n_sims=5000, block_len=20, seed=42):
    """Circular daily blocks of actual account returns; conditional, never a forecast."""
    r = np.asarray(returns, dtype=float)
    if not len(r) or not np.isfinite(r).all() or (r <= -1).any():
        raise ValueError('Invalid account returns for bootstrap')
    rng = np.random.default_rng(seed)
    drawdowns, finals = [], []
    for offset in range(0, n_sims, 100):
        batch = min(100, n_sims-offset)
        starts = rng.integers(0, len(r), size=(batch, int(np.ceil(len(r)/block_len))))
        indices = (starts[...,None]+np.arange(block_len)) % len(r)
        sampled = r[indices.reshape(batch,-1)[:,:len(r)]]
        equity = np.cumprod(1+sampled, axis=1)
        peak = np.maximum.accumulate(np.column_stack([np.ones(batch),equity]), axis=1)[:,1:]
        drawdowns.extend(np.max(1-equity/peak,axis=1)*100)
        finals.extend((equity[:,-1]-1)*100)
    return dict(n_sims=n_sims, block_len=block_len, n_days=len(r), seed=seed,
                drawdown_p50_pct=float(np.percentile(drawdowns,50)),
                drawdown_p95_pct=float(np.percentile(drawdowns,95)),
                total_return_p05_pct=float(np.percentile(finals,5)),
                total_return_p50_pct=float(np.percentile(finals,50)),
                loss_frequency_pct=100*float(np.mean(np.asarray(finals)<0)),
                note='Conditional resampling of IS/WF daily account EUR returns; not future probability, no unseen crises.')


def statistical_diagnostics(raw, variants, k):
    from dataclasses import asdict
    from lab.critic.stats import deflated_sharpe, pbo_cscv
    results, daily_variants = {}, {}
    for name in variants:
        trades, usd_parts, eur_parts = [], [], []
        for period in ('IS','WF'):
            result, euro, initial_usd = raw[f'{name}__{period}']
            trades += result['trades']
            usd = result['curve'].pct_change()
            usd.iloc[0] = result['curve'].iloc[0]/initial_usd-1
            eur = euro.pct_change()
            eur.iloc[0] = euro.iloc[0]/600-1
            usd_parts.append(usd)
            eur_parts.append(eur)
        daily_variants[name] = pd.concat(usd_parts)
        returns = np.array([t['return_pct'] for t in trades])
        pnl = np.array([t['pnl_usd'] for t in trades])
        results[name] = dict(dsr_approx_usd_per_trade=asdict(deflated_sharpe(returns,k)),
                            pnl_without_best3_usd=float(pnl.sum()-np.sort(pnl)[-3:].sum()),
                            n_closed=len(trades), account_eur_block_bootstrap=block_bootstrap_account(pd.concat(eur_parts)))
    matrix = pd.concat(daily_variants,axis=1).dropna()
    if (matrix.index>=pd.Timestamp('2024-01-01',tz='UTC')).any():
        raise ValueError('Holdout leaked into statistical diagnostic matrix')
    return dict(k=k, variants=results, pbo=asdict(pbo_cscv(matrix.to_numpy())),
                pbo_n_common_days=len(matrix), pbo_columns=list(matrix.columns),
                pbo_first_day=str(matrix.index[0]),pbo_last_day=str(matrix.index[-1]),
                limitations='DSR uses per-trade correlated returns and approximate null variance; PBO only these four declared variants; no formal Critic approval.')


def main(study='C23_SWING_ROBUSTNESS_20261006'):
    if not study.replace('_', '').isalnum() or study != study.upper():
        raise ValueError('Invalid study id')
    output = ROOT / 'reports/backtest' / study
    config = json.loads((output/'config.json').read_text())
    freeze = ROOT / f'strategies/frozen/2026-10-06_{study}.md'
    frozen_config = json.loads(freeze.read_text().split('```json\n', 1)[1].split('```', 1)[0])
    if config != frozen_config:
        raise ValueError('Study config differs from immutable freeze')
    source = ROOT / config['source_freeze']
    if config.get('source_freeze_sha256') and hashlib.sha256(source.read_bytes()).hexdigest() != config['source_freeze_sha256']:
        raise ValueError('Original source rule changed')
    # Never overwrite a completed run, its selection, or its audit evidence.
    if (output/'summary.json').exists() or (output/'selection_pre_holdout.json').exists():
        raise FileExistsError('Completed/partially sealed study exists; use a new frozen study ID')
    subprocess.run([sys.executable, str(ROOT/'scripts/validate_data.py'), '--through', config['through'],
                    '--report', str(output/'DATA_CHECK.md')], cwd=ROOT, check=True)
    frames = {s: load_bars(s, through=config['through']) for s in config['universe']}
    smh = load_bars('SMH', through=config['through'])
    import shutil
    if not (output/'ecb-history.xml').exists():
        shutil.copyfile(ROOT/'reports/backtest/C21_SWING_20261006/ecb-history.xml', output/'ecb-history.xml')
    rates = fx_table(output/'ecb-history.xml')
    variants = config['variants']
    results, stresses, years = {}, {}, {}
    case_audit = {}
    pre_holdout_raw = {}

    def evaluate(key, variant, period, stress=None):
        summary, raw, euro = run_case(frames, smh, rates, variant, period, config, stress)
        raw['curve'].rename('equity_usd').to_frame().assign(equity_eur=euro).to_csv(output/f'{key}_equity.csv')
        pd.DataFrame(raw['trades']).to_csv(output/f'{key}_trades.csv', index=False)
        if key.endswith(('__IS', '__WF')) and key.count('__') == 1:
            pre_holdout_raw[key] = (raw, euro, summary['initial_usd'])
        case_audit[key] = {'fill_violations':raw['fill_violations'],
                           'max_daily_volume_fraction':raw['max_daily_volume_fraction']}
        return summary

    # Selection is written before any HO or yearly retrospective result is evaluated here.
    for name, variant in variants.items():
        results[name] = {period: evaluate(f'{name}__{period}', variant, config['periods'][period])
                         for period in ('IS', 'WF')}
    selection = select_pre_holdout(results, 'BASE')
    write_json(output/'selection_pre_holdout.json', selection)
    selection_hash = hashlib.sha256((output/'selection_pre_holdout.json').read_bytes()).hexdigest()
    print('SEALED SELECTION', json.dumps(selection), flush=True)
    for name, variant in variants.items():
        results[name]['HO_SEEN'] = evaluate(f'{name}__HO_SEEN', variant, config['periods']['HO_SEEN'])
        results[name]['POST_CHATGPT'] = evaluate(f'{name}__POST_CHATGPT', variant, config['periods']['POST_CHATGPT'])
        stresses[name] = {}
        for stress_name, stress in config['stresses'].items():
            stresses[name][stress_name] = {
                period: evaluate(f'{name}__{stress_name}__{period}', variant, config['periods'][period], stress)
                for period in ('IS', 'WF', 'HO_SEEN')}
        years[name] = {str(year): evaluate(f'{name}__YEAR{year}', variant,
                             [f'{year}-01-01', min(f'{year}-12-31', config['through'])])
                       for year in range(2016, 2027)}
        print('FINISHED', name, flush=True)
    if any(a['fill_violations'] for a in case_audit.values()):
        raise ValueError('Execution feasibility check failed; no robustness claim')
    statistical = statistical_diagnostics(pre_holdout_raw, list(variants), current_k())
    write_json(output/'statistical_diagnostics.json', statistical)
    paths = [source, freeze, ROOT/'lab/research/memory_swing.py', Path(__file__), output/'ecb-history.xml']
    paths += [ROOT/f'data/ohlcv/{s}_1d.csv' for s in list(config['universe'])+['SMH']]
    summary = dict(config=config, k=current_k(), selection=selection, selection_sha256=selection_hash,
                   results=results, stresses=stresses, yearly_reset600=years, audit=case_audit, statistical_diagnostics=statistical,
                   manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                   limitations=['Prior HO already seen; retrospective confirmation, not untouched out-of-sample.',
                     'Yearly results reset to 600 EUR and flat positions each January, not additive compounded years.',
                     'Regimes use lagged SMH indicators; descriptive attribution, not future regime prediction.',
                     'OHLC fill assumptions, reference FX, adjusted whole shares; no dividends, taxes, funding/conversion charges or broker-fill reconciliation.',
                     'No Critic PASS, no orders, no promise of future profitability.'])
    write_json(output/'summary.json', summary)
    lines = ['# Otpornost swing metode — 600 EUR', '',
             'Istraživanje bez naloga i bez odobrenja strategije. Završno razdoblje već je ranije pregledano.', '',
             f"Prethodno definirani odabir na IS/WF: **{selection['selected'] or 'NIJEDNA VARIJANTA'}**.", '',
             '| Varijanta | Razdoblje | Prinos EUR | USD gotovina u EUR | Kupi i drži | Najveći pad | Trgovina |',
             '|---|---|---:|---:|---:|---:|---:|']
    for name, periods in results.items():
        for period, row in periods.items():
            lines.append(f"| {name} | {period} | {row['return_pct']:.2f}% | {row['usd_cash_benchmark']['return_pct']:.2f}% | {row['passive_equal_benchmark']['return_pct']:.2f}% | {row['max_drawdown_pct']:.2f}% | {row['n_closed']} |")
    lines += ['', '## Nepovoljna izvršenja', '', '| Varijanta | Stres | WF prinos EUR | WF najveći pad | HO prinos EUR |', '|---|---|---:|---:|---:|']
    for name, scenarios in stresses.items():
        for label, periods in scenarios.items():
            lines.append(f"| {name} | {label} | {periods['WF']['return_pct']:.2f}% | {periods['WF']['max_drawdown_pct']:.2f}% | {periods['HO_SEEN']['return_pct']:.2f}% |")
    lines += ['', 'Nijedan opis tržišnog režima ne predviđa sljedeću krizu. Pozitivan povijesni rezultat nije jamstvo.',
              'Godišnje tablice u summary.json počinju iznova sa 600 EUR; nisu kontinuirano ulaganje.',
              'Dio promjene vrijednosti u eurima dolazi od tečaja USD/EUR, pa je prikazana i gotovina u dolarima.']
    (output/'IZVJESTAJ.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'study':study,'cases':len(case_audit),'selected':selection['selected']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', default='C23_SWING_ROBUSTNESS_20261006')
    main(parser.parse_args().study)
