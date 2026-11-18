"""Execute frozen C35 configurations; no data fetch, no broker access."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'reports/backtest/C35_METALS_20261013'
CONFIGS = [('BASE', 1, 1, 10000, 0, 0), ('COST2', 2, 1, 10000, 0, 0),
           ('COST3', 3, 1, 10000, 0, 0), ('SENS08', 1, .8, 10000, 0, 0),
           ('SENS12', 1, 1.2, 10000, 0, 0), ('FEE500', 1, 1, 550, 1.375, 5),
           ('FEE1000', 1, 1, 1100, 1.375, 5), ('FEE2000', 1, 1, 2200, 1.375, 5)]

def run(config, stage):
    name, cost, sensitivity, capital, fee, bps = config
    out = BASE / name
    out.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(ROOT/'scripts/backtest_metals_20261013.py'),
               '--stage', stage, '--output-dir', str(out), '--selection-file', str(BASE/'BASE/selection.json'),
               '--cost-multiplier', str(cost), '--sensitivity', str(sensitivity),
               '--initial-cash', str(capital), '--min-fee', str(fee), '--commission-bps', str(bps)]
    with (out/f'{stage}.log').open('w') as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    print(f'{stage}: {name} complete', flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['development', 'holdout'], required=True)
    args = parser.parse_args()
    if args.stage == 'development':
        run(CONFIGS[0], args.stage)
        selection = BASE/'BASE/selection.json'
        binding = {'selection_sha256': hashlib.sha256(selection.read_bytes()).hexdigest(),
                   'engine_sha256': hashlib.sha256((ROOT/'scripts/backtest_metals_20261013.py').read_bytes()).hexdigest()}
        (BASE/'selection_binding.json').write_text(json.dumps(binding, indent=2))
        remaining = CONFIGS[1:]
    else:
        binding = json.loads((BASE/'selection_binding.json').read_text())
        assert binding['selection_sha256'] == hashlib.sha256((BASE/'BASE/selection.json').read_bytes()).hexdigest()
        assert binding['engine_sha256'] == hashlib.sha256((ROOT/'scripts/backtest_metals_20261013.py').read_bytes()).hexdigest()
        remaining = CONFIGS
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda cfg: run(cfg, args.stage), remaining))

if __name__ == '__main__':
    main()
