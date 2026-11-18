"""C25 fixed priority sensitivity. Offline only; no winner selection or trading calls."""
from __future__ import annotations

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
from lab.ledger import current_k, read_trials
from lab.research.memory_swing import replay, metrics, benchmark
from scripts.run_memory_swing import fx_table, fx_rate, write_json

STUDY = 'C25_PRIORITY_AUDIT_20261006'


def check_baseline(actual, expected, actual_curve, expected_curve):
    """Priority audit must reproduce the original account path, not just final profit."""
    for key in ('final', 'return_pct', 'max_drawdown_pct', 'n_closed'):
        if not np.isclose(actual[key], expected[key], rtol=0, atol=1e-8):
            raise ValueError(f'C22 baseline mismatch: {key}')
    if not actual_curve.index.equals(expected_curve.index):
        raise ValueError('C22 baseline date mismatch')
    if not np.allclose(actual_curve, expected_curve, rtol=0, atol=1e-8):
        raise ValueError('C22 baseline equity path mismatch')


def evaluate(frames, rates, priority, period, config):
    start, end = period
    subset = {symbol: frames[symbol] for symbol in priority}
    first = next(iter(subset.values())).loc[start:end].index[0]
    initial_usd = config['initial_eur'] * fx_rate(rates, first, before=True)
    run = replay(subset, start, end, initial_usd, **config['parameters'])
    if run is None:
        raise ValueError('Priority replay produced no history')
    curve = run['curve']
    daily_fx = pd.Series([fx_rate(rates, day) for day in curve.index], index=curve.index)
    euros = curve / daily_fx
    summary = metrics(euros, config['initial_eur'], run['trades'])
    passive, holdings = benchmark(subset, curve.index, initial_usd, 'equal')
    usd_cash = pd.Series(initial_usd, index=curve.index) / daily_fx
    summary.update(initial_usd=initial_usd, currency='EUR', closed_trade_statistics_currency='USD',
                   priority=priority, collision_days=run['collision_days'],
                   costs_usd=run['costs_usd'], mean_exposure_pct=run['mean_exposure_pct'],
                   open_position=run['open_position'], skipped_count=len(run['skipped']),
                   fill_violations=run['fill_violations'],
                   max_daily_volume_fraction=run['max_daily_volume_fraction'],
                   usd_cash_benchmark=metrics(usd_cash,config['initial_eur']),
                   passive_basket=metrics(passive/daily_fx,config['initial_eur']) | {'holdings':holdings},
                   entries_by_symbol={s:sum(e[1]=='buy' and e[2]==s for e in run['events']) for s in priority},
                   closed_pnl_by_symbol_usd={s:float(sum(t['pnl_usd'] for t in run['trades'] if t['ticker']==s)) for s in priority})
    return summary,run,euros


def main():
    output = ROOT/'reports/backtest'/STUDY
    config = json.loads((output/'config.json').read_text())
    freeze = ROOT/'strategies/frozen'/f'2026-10-06_{STUDY}.md'
    frozen = json.loads(freeze.read_text().split('```json\n',1)[1].split('```',1)[0])
    if frozen != config:
        raise ValueError('Study config differs from freeze')
    if (output/'summary.json').exists():
        raise FileExistsError('Refusing to overwrite completed priority audit')
    for source_key, hash_key in [('source_freeze','source_freeze_sha256'),('source_baseline','source_baseline_sha256')]:
        if hashlib.sha256((ROOT/config[source_key]).read_bytes()).hexdigest() != config[hash_key]:
            raise ValueError(f'Frozen source changed: {source_key}')
    digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
    ledger = {row['strategy_id']:row for row in read_trials()}
    for priority in config['permutations']:
        if priority == config['baseline']:
            continue
        identifier = 'C25_PRIORITY_'+'_'.join(priority)
        if identifier not in ledger or ledger[identifier]['freeze_hash'] != digest:
            raise ValueError('Priority trial not registered before outcomes')
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--through',config['through'],
                    '--report',str(output/'DATA_CHECK.md')],cwd=ROOT,check=True)
    frames = {symbol:load_bars(symbol,through=config['through']) for symbol in config['baseline']}
    rates = fx_table(ROOT/config['fx_source'])
    baseline_path = ROOT/config['source_baseline']
    original = json.loads(baseline_path.read_text())
    results,rows,baseline_evidence = {},[],{}
    for priority in config['permutations']:
        name = '_'.join(priority)
        results[name] = {}
        for period, bounds in config['periods'].items():
            summary,run,euros = evaluate(frames,rates,priority,bounds,config)
            if priority == config['baseline']:
                key = f'CORE__SMALL_600EUR_ALL__{period}'
                expected = original['results'][key]
                csv = pd.read_csv(baseline_path.parent/f'{key}_equity.csv')
                reference = pd.Series(csv.equity_base.to_numpy(),index=pd.to_datetime(csv.iloc[:,0],utc=True))
                check_baseline(summary,expected,euros,reference)
                baseline_evidence[period] = dict(matches=True,n_days=len(euros),
                    max_equity_difference_eur=float(np.max(np.abs(euros.to_numpy()-reference.to_numpy()))))
            baseline = results['_'.join(config['baseline'])][period] if priority != config['baseline'] else summary
            summary['difference_from_baseline_eur'] = summary['final']-baseline['final']
            summary['difference_from_baseline_return_pp'] = summary['return_pct']-baseline['return_pct']
            results[name][period] = summary
            key = f'{name}__{period}'
            run['curve'].rename('equity_usd').to_frame().assign(equity_eur=euros).to_csv(output/f'{key}_equity.csv')
            pd.DataFrame(run['trades']).to_csv(output/f'{key}_trades.csv',index=False)
            rows.append(dict(priority=name,period=period,final_eur=summary['final'],return_pct=summary['return_pct'],
                max_drawdown_pct=summary['max_drawdown_pct'],n_closed=summary['n_closed'],collision_days=summary['collision_days'],
                difference_from_baseline_eur=summary['difference_from_baseline_eur'],
                usd_cash_return_pct=summary['usd_cash_benchmark']['return_pct'],
                passive_return_pct=summary['passive_basket']['return_pct']))
            if run['fill_violations']:
                raise ValueError(f'Fill audit failed: {key}')
        print('FINISHED',name,flush=True)
    paths = [Path(__file__),freeze,ROOT/config['source_baseline'],ROOT/config['source_freeze'],
             ROOT/config['fx_source'],ROOT/'lab/research/memory_swing.py']
    paths += [ROOT/f'data/ohlcv/{symbol}_1d.csv' for symbol in config['baseline']]
    write_json(output/'summary.json',dict(config=config,k=current_k(),results=results,baseline_parity=baseline_evidence,
        selected=None,approved=False,no_orders=True,
        manifest={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        note='Fixed priority paths interact. End-point differences are not additive sources of missed growth; hindsight best is not an executable selection rule. HO already seen; no profit guarantee.'))
    pd.DataFrame(rows).to_csv(output/'priority_comparison.csv',index=False)
    text=['# C25 — Koliko rezultat ovisi o redoslijedu dionica?', '',
          'Šest redoslijeda zamrznuto prije pokretanja. Pravila kupnje i prodaje ista; početnih 600 EUR, reinvestiranje, jedna pozicija, bez novih uplata.',
          'Nijedan redoslijed nije odabran ni odobren. Naknadno najbolji rezultat nije pravilo koje smo mogli znati unaprijed.', '',
          '| Prioritet | Razdoblje | Završno EUR | Prinos | Najveći pad | Zatvorenih trgovina | Sudari signala | Razlika prema izvornom EUR |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        text.append(f"| {row['priority']} | {row['period']} | {row['final_eur']:.2f} | {row['return_pct']:.2f}% | {row['max_drawdown_pct']:.2f}% | {row['n_closed']} | {row['collision_days']} | {row['difference_from_baseline_eur']:+.2f} |")
    text += ['', 'Sudari su dani kada je račun slobodan, a više dionica istodobno zadovoljava pravilo. Broj nije svaki signal propušten tijekom držanja pozicije.',
             'Jedan drukčiji ulaz mijenja datum sljedeće prodaje i sve kasnije prilike. Razlike se zato ne mogu zbrajati s zasebnim učincima stopa ili čekanja.',
             'WF je 2021.–2023.; POST_CHATGPT je od 1.12.2022. do 2.10.2026. Razdoblja se preklapaju i nisu dva neovisna dokaza.',
             'C22 osnovni redoslijed reproduciran na cijeloj dnevnoj putanji računa. Rezultati su hipotetski; nema dividendi, poreza, troškova pretvorbe ni usporedbe sa stvarnim izvršenjima.']
    (output/'IZVJESTAJ.md').write_text('\n'.join(text)+'\n')
    print(json.dumps(dict(cases=len(rows),k=current_k(),baseline_parity=baseline_evidence)))


if __name__ == '__main__':
    main()
