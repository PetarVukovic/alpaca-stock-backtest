"""Frozen SNDK transfer diagnostic. Offline only; no orders."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.research.memory_swing import replay, metrics, entry_signals, benchmark


def main():
    cfg = json.loads((ROOT/'strategies/frozen/2026-10-11_C32_C13C_SNDK.json').read_text())
    for path, key in [(cfg['data'], 'data_sha256'), ('lab/research/memory_swing.py', 'engine_sha256')]:
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == cfg[key]
    out = ROOT/'reports/backtest/C32_C13C_SNDK_20261011'
    out.mkdir(exist_ok=True)
    d = pd.read_csv(ROOT/cfg['data'])
    d.index = pd.to_datetime(d.pop('date'), utc=True)
    result = {'config':cfg, 'rows':len(d), 'sma200_first':str(d.index[199].date()), 'cases':{}}
    for profile in cfg['profiles']:
        for stress in cfg['stress']:
            capital = profile['capital']
            args = dict(start=cfg['start'], end=cfg['end'], capital=capital,
                        cap=profile['cap'], sizing='all', stress=stress)
            r = replay({'SNDK':d}, **args)
            key = f'USD{capital}_COST{stress}'
            audit = {'truncation':{}, 'future_corruption':{}}
            for cutoff in ['2025-12-31','2026-03-31','2026-06-30']:
                t = pd.Timestamp(cutoff, tz='UTC')
                truncated = replay({'SNDK':d.loc[:t]}, **(args|{'end':cutoff}))
                assert truncated['events'] == [e for e in r['events'] if e[0] <= cutoff]
                assert truncated['curve'].equals(r['curve'].loc[:t])
                audit['truncation'][cutoff] = '0 event/equity differences'
                changed = d.copy()
                mask = changed.index > t
                rng = np.random.default_rng(32)
                changed.loc[mask,['open','high','low','close']] *= rng.uniform(.2,5,(sum(mask),1))
                corrupted = replay({'SNDK':changed}, **args)
                assert [e for e in corrupted['events'] if e[0] <= cutoff] == truncated['events']
                assert corrupted['curve'].loc[:t].equals(truncated['curve'])
                audit['future_corruption'][cutoff] = '0 prior event/equity differences'
            assert r['fill_violations'] == 0 and r['max_daily_volume_fraction'] < .01
            audit.update(fill_violations=r['fill_violations'], max_daily_volume_fraction=r['max_daily_volume_fraction'],
                         gaps=[t['exit_date'] for t in r['trades'] if t['reason']=='gap_stop'],
                         limitations='Daily OHLC only; no quotes, tick path, depth or real fills. Next-day peak stop; gaps use opening price minus costs. No external joins. No complete Critic or Monte Carlo; short history.')
            row = metrics(r['curve'], capital, r['trades'])
            row.update(open_position=r['open_position'], skipped=len(r['skipped']), costs_usd=r['costs_usd'], audit=audit)
            row['annual_pct'] = {}
            previous = capital
            for year, curve in r['curve'].groupby(r['curve'].index.year):
                row['annual_pct'][str(year)] = 100*(float(curve.iloc[-1])/previous-1)
                previous = float(curve.iloc[-1])
            result['cases'][key] = row
            r['curve'].to_csv(out/f'{key}_equity.csv')
            pd.DataFrame(r['trades']).to_csv(out/f'{key}_trades.csv',index=False)
            (out/f'{key}_events.json').write_text(json.dumps(r['events']))
    signals = entry_signals(d)
    result['signal_dates'] = [str(x.date()) for x in d.index[signals]]
    result['price_return_since_listing_pct'] = 100*(d.close.iloc[-1]/d.loc['2025-02-24','open']-1)
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
