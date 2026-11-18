"""Read-only C26 causal-execution checks. No broker access or strategy changes."""
from pathlib import Path
import sys, json, hashlib, subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lab.data import load_bars
from lab.research.memory_swing import replay

def main():
    config=json.loads((ROOT/'reports/backtest/C26_BASKET_20261006/config.json').read_text())
    supplemental=json.loads((ROOT/'reports/research/C26_SUPPLEMENTAL_DATA_CHECK_20261006.json').read_text())
    assert supplemental['errors']==[]
    for symbol,digest in supplemental['source_hashes'].items():
        assert hashlib.sha256((ROOT/f'data/ohlcv/{symbol}_1d.csv').read_bytes()).hexdigest()==digest
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--through',config['through'],'--report',str(ROOT/'reports/research/C26_INTEGRITY_DATA_CHECK_20261006.md')],check=True,cwd=ROOT)
    rows=[]
    for group in ['CORE','EQUIPMENT','SEMI_LARGE','ETF_CONTROL','ALL_NEW']:
        frames={s:load_bars(s,through=config['through']) for s in config['universes'][group]}
        full=replay(frames,'2016-01-04',config['through'],100000)
        for cutoff in ['2020-12-31','2023-12-29','2025-12-31']:
            cut=replay(frames,'2016-01-04',cutoff,100000)
            changed={s:f.copy() for s,f in frames.items()}
            for frame in changed.values():
                mask=frame.index.strftime('%Y-%m-%d')>cutoff
                frame.loc[mask,['open','high','low','close']]*=1.73
            corrupt=replay(changed,'2016-01-04',config['through'],100000)
            expected=[e for e in full['events'] if e[0]<=cutoff]
            entry=dict(group=group,cutoff=cutoff,truncation_events_match=cut['events']==expected,
                       corruption_events_match=[e for e in corrupt['events'] if e[0]<=cutoff]==expected,
                       truncation_equity_max_diff=float((cut['curve']-full['curve'].reindex(cut['curve'].index)).abs().max()),
                       corruption_equity_max_diff=float((cut['curve']-corrupt['curve'].reindex(cut['curve'].index)).abs().max()),
                       baseline_fill_violations=full['fill_violations'],baseline_max_daily_volume_fraction=full['max_daily_volume_fraction'])
            assert entry['truncation_events_match'] and entry['corruption_events_match']
            assert entry['truncation_equity_max_diff']<1e-7 and entry['corruption_equity_max_diff']<1e-7
            assert full['fill_violations']==0 and full['max_daily_volume_fraction']<.001
            rows.append(entry)
    output=dict(checks=rows,volume_threshold_fraction=.001,scope='five baskets, PAPER_100K_ONE; other profiles covered by source engine regression tests, not all combinations independently retested here',
        signal_audit='Only completed close and backward SMA200/5-bar change. Next-open entry; prior peak stop, entry-day stop allowed. High updates stop only after current-day exit check.',
        merge_audit='Exact shared daily calendars. Initial EUR exchange uses earlier ECB date; end-day valuations use contemporaneous ECB reference, not tradable FX quotes.',
        limitations=['Daily OHLC, not tick/orderbook reconstruction','Gap exits at worse opening price plus modeled adverse cost, not guaranteed stop price','No broker-fill reconciliation','No bid-ask quote or halt audit','Split-adjusted whole-share units are not literal historical whole shares; actual split events/quantities not replayed','Price-only benchmarks omit dividend cashflows','Changing future magnitude by a fixed factor is one perturbation; not exhaustive adversarial testing'],
        verdict='REPRODUCIBLE_DAILY_MODEL_NOT_LIVE_VALIDATION')
    (ROOT/'reports/research/C26_INTEGRITY_AUDIT_20261006.json').write_text(json.dumps(output,indent=2))
    print('15 cutoff/corruption checks passed; no baseline fill violations; not full execution validation')

if __name__=='__main__':main()
