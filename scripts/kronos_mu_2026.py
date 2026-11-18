"""Frozen, sequential 2026 Kronos experiment; research only, never orders."""
from pathlib import Path
import os
import sys
import json
import hashlib
import time
import shutil
import csv

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/kronos"
OUT = ROOT / "reports/research/KRONOS_20261103/MU_2026_WALKFORWARD"
FREEZE = ROOT / "strategies/frozen/2026-11-03_KRONOS_MU_2026_V1.json"
os.environ.setdefault("HF_HOME", str(RUNTIME / "hf_cache"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME / "matplotlib"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME / "upstream"))
import numpy as np
import pandas as pd
import torch
from model import Kronos, KronosTokenizer, KronosPredictor


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def window_starts(data):
    indices = data.index[data.date.dt.year == 2026].tolist()
    return [i for i in indices[::10] if i + 10 <= len(data)]


def model_inputs(data, start):
    # No future OHLCV columns are ever read in this function.
    hist = data.iloc[start-90:start].reset_index(drop=True).copy()
    assert len(hist) == 90
    frame = hist[["open", "high", "low", "close", "volume"]].copy()
    frame["amount"] = hist.vwap * hist.volume
    times = data.iloc[start:start+10].date.reset_index(drop=True).copy()
    assert hist.date.max() < times.min()
    raw = frame.to_csv(index=False) + hist.date.to_csv(index=False) + times.to_csv(index=False)
    return frame, hist.date, times, hashlib.sha256(raw.encode()).hexdigest()


def infer(predictor, inputs, seed):
    frame, dates, future, _hash = inputs
    torch.manual_seed(seed)
    np.random.seed(seed)
    with torch.inference_mode():
        pred = predictor.predict(df=frame, x_timestamp=dates, y_timestamp=future,
                                 pred_len=10, T=.6, top_p=.9, sample_count=20, verbose=False)
    assert len(pred) == 10 and np.isfinite(pred.to_numpy()).all()
    return pred


def replay(data, decisions, multiplier=1.0, capital=10000.0):
    c = 2.5e-4 * multiplier
    tick = .01 * multiplier
    usd = capital * 1.1
    rows, windows = [], []
    first = int(data.index[data.date.dt.year == 2026][0])
    bench_q = usd / ((float(data.iloc[first].open) + tick) * (1+c))
    decisions_by_start = {r["start_index"]: r for r in decisions}
    active = None
    for i in range(first, len(data)):
        bar = data.iloc[i]
        if i in decisions_by_start:
            decision = decisions_by_start[i]
            end = i + 9
            entry, exit_ = float(bar.open), float(data.iloc[end].close)
            hypothetical_return = ((exit_-tick)*(1-c))/((entry+tick)*(1+c))-1
            record = dict(decision, entry_date=str(bar.date.date()),
                          exit_date=str(data.iloc[end].date.date()), entry_open=entry,
                          exit_close=exit_, net_return_if_bought=hypothetical_return,
                          gross_return=exit_/entry-1, equity_before_eur=usd/1.1,
                          pnl_eur=0.0, fee_usd=0.0, shares=0.0)
            if decision["buy"]:
                q = usd / ((entry+tick)*(1+c))
                record["shares"] = q
                record["fee_usd"] = usd-q*entry
                active = (q, end, record)
            windows.append(record)
        if active:
            q, end, record = active
            mark = q*float(bar.close)
            if i == end:
                net = q*(float(bar.close)-tick)*(1-c)
                record["fee_usd"] += mark-net
                record["pnl_eur"] = net/1.1-record["equity_before_eur"]
                usd = net
                mark = net
                record["equity_after_eur"] = usd/1.1
                active = None
        else:
            mark = usd
        if windows and "equity_after_eur" not in windows[-1] and not windows[-1]["buy"]:
            windows[-1]["equity_after_eur"] = usd/1.1
        bench = bench_q*float(bar.close)
        if i == len(data)-1:
            bench = bench_q*(float(bar.close)-tick)*(1-c)
        rows.append(dict(date=str(bar.date.date()), strategy_eur=mark/1.1,
                         benchmark_eur=bench/1.1, cash_eur=capital, close_usd=float(bar.close)))
    assert active is None
    trades = [r for r in windows if r["buy"]]
    wealth = np.array([capital]+[r["strategy_eur"] for r in rows])
    dd = float((wealth/np.maximum.accumulate(wealth)-1).min())
    bw = np.array([capital]+[r["benchmark_eur"] for r in rows])
    summary = dict(capital_eur=capital, end_eur=usd/1.1, profit_eur=usd/1.1-capital,
                   return_pct=(usd/1.1/capital-1)*100,
                   benchmark_end_eur=rows[-1]["benchmark_eur"],
                   benchmark_profit_eur=rows[-1]["benchmark_eur"]-capital,
                   benchmark_return_pct=(rows[-1]["benchmark_eur"]/capital-1)*100,
                   max_drawdown_pct=dd*100,
                   benchmark_drawdown_pct=float((bw/np.maximum.accumulate(bw)-1).min()*100),
                   decisions=len(windows), buys=len(trades), skips=len(windows)-len(trades),
                   wins=sum(r["pnl_eur"]>0 for r in trades), losses=sum(r["pnl_eur"]<0 for r in trades),
                   flat=sum(abs(r["pnl_eur"])<1e-10 for r in trades),
                   skipped_losses=sum(not r["buy"] and r["net_return_if_bought"]<0 for r in windows),
                   skipped_gains=sum(not r["buy"] and r["net_return_if_bought"]>0 for r in windows),
                   exposure_days=10*len(trades), total_days=len(rows),
                   cost_multiplier=multiplier, fees_usd=sum(r["fee_usd"] for r in trades),
                   start=rows[0]["date"], end=rows[-1]["date"], last_complete_exit=windows[-1]["exit_date"],
                   tail_cash_days=sum(r["date"]>windows[-1]["exit_date"] for r in rows))
    return dict(summary=summary, daily=rows, windows=windows)


def audit(data, decisions, predictor, result):
    checks = []
    starts = window_starts(data)
    for j in [0, len(starts)//2, len(starts)-1]:
        i = starts[j]
        base = model_inputs(data, i)
        truncated = model_inputs(data.iloc[:i+10], i)
        corrupt = data.copy()
        corrupt.loc[i:, ["open", "high", "low", "close", "volume", "vwap"]] = 123456.0
        altered = model_inputs(corrupt, i)
        assert base[3] == truncated[3] == altered[3]
        repeated = infer(predictor, altered, 20261103+j)
        saved = np.array(decisions[j]["forecast_closes"])
        delta = float(np.abs(repeated.close.to_numpy()-saved).max())
        assert delta < 1e-7, (j, delta)
        checks.append(dict(window=j+1, cutoff=decisions[j]["signal_date"],
                           identical_input_hash=True, max_forecast_diff_usd=delta,
                           decision_unchanged=bool(float(repeated.close.iloc[-1])>decisions[j]["signal_close"]) == decisions[j]["buy"]))
    assert all(c["decision_unchanged"] for c in checks)
    # Independent cash-flow reconstruction; do not reuse replay() formulas.
    cash = 11000.0
    max_participation = 0.0
    fill_checks, gaps = [], []
    indexed = data.set_index(data.date.dt.strftime("%Y-%m-%d"))
    for w in result["windows"]:
        if not w["buy"]:
            continue
        q = cash / ((w["entry_open"]+.01)*1.00025)
        cash = q*(w["exit_close"]-.01)*.99975
        for dt, raw in [(w["entry_date"], w["entry_open"]),(w["exit_date"], w["exit_close"])]:
            bar = indexed.loc[dt]
            assert bar.low <= raw <= bar.high and bar.volume > 0
            participation = q/float(bar.volume)
            assert participation < .001
            max_participation = max(max_participation, participation)
            fill_checks.append(dict(date=dt, price_in_ohlc=True, positive_volume=True, participation=participation))
        idx = int(data.index[data.date.dt.strftime("%Y-%m-%d")==w["entry_date"]][0])
        gap = float(data.iloc[idx].open/data.iloc[idx-1].close-1)
        if abs(gap) > .02:
            gaps.append(dict(date=w["entry_date"], gap_pct=gap*100, treatment="actual next open; no fill at prior close"))
    assert abs(cash/1.1-result["summary"]["end_eur"]) < 1e-8
    return dict(truncation_and_corruption=checks, input_only_past_ohlcv=True,
                data_merges="none; only scheduled future dates passed to model", fill_count=len(fill_checks),
                max_daily_volume_participation=max_participation, participation_threshold=.001,
                fills=fill_checks, gap_entries=gaps, cashflow_reconciliation_diff_eur=abs(cash/1.1-result["summary"]["end_eur"]),
                quote_depth_tick_data="unavailable; daily open/close plus adverse tick and costs, no stops or limits",
                broker_fill_reconciliation="not applicable: no orders or real fills",
                pretraining_checkpoint_history="not independently confirmed; paper states through June 2024",
                full_critic="NOT COMPLETED; research only, approved_list unchanged")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"forecasts").mkdir(exist_ok=True)
    freeze = json.loads(FREEZE.read_text())
    source = ROOT/freeze["source"]
    assert digest(source) == freeze["source_sha256"]
    data = pd.read_csv(source, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    assert not data.date.duplicated().any()
    assert np.isfinite(data[["open","high","low","close","volume","vwap"]].to_numpy()).all()
    from lab.ledger import read_trials
    registered = [r for r in read_trials() if r["strategy_id"]==freeze["id"]]
    assert len(registered)==1 and registered[0]["freeze_hash"]==digest(FREEZE)
    shutil.copy2(FREEZE, OUT/FREEZE.name)
    shutil.copy2(__file__, OUT/"runner_snapshot.py")
    starts = window_starts(data)
    print(f"Frozen experiment: {len(starts)} complete windows; K={registered[0]['k']}", flush=True)
    model = Kronos.from_pretrained(freeze["model"], revision=freeze["model_revision"], local_files_only=True)
    tokenizer = KronosTokenizer.from_pretrained(freeze["tokenizer"], revision=freeze["tokenizer_revision"], local_files_only=True)
    model.eval(); tokenizer.eval()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    predictor = KronosPredictor(model, tokenizer, device=device, max_context=512)
    decisions = []
    start_time = time.monotonic()
    for j, i in enumerate(starts):
        inputs = model_inputs(data, i)
        fp = OUT/"forecasts"/f"{j+1:02d}_{data.iloc[i-1].date.date()}.json"
        seed = 20261103+j
        if fp.exists():
            record = json.loads(fp.read_text())
            assert record["input_sha256"]==inputs[3] and record["freeze_sha256"]==digest(FREEZE)
        else:
            pred = infer(predictor, inputs, seed)
            last = float(data.iloc[i-1].close)
            predicted = float(pred.close.iloc[-1])
            record = dict(window=j+1, start_index=i, signal_date=str(data.iloc[i-1].date.date()),
                          signal_close=last, forecast_final=predicted, forecast_return_pct=(predicted/last-1)*100,
                          forecast_closes=[float(x) for x in pred.close], future_dates=[str(x.date()) for x in inputs[2]],
                          buy=predicted>last, input_sha256=inputs[3], freeze_sha256=digest(FREEZE), seed=seed)
            # Forecast and decision persisted before realized prices enter P&L evaluation.
            fp.write_text(json.dumps(record, indent=2))
        decisions.append(record)
        print(f"{j+1:02d}/{len(starts)} {record['signal_date']} forecast {record['forecast_return_pct']:+.2f}% -> {'SIMULATED BUY' if record['buy'] else 'CASH'}", flush=True)
    result = replay(data, decisions)
    stresses = [replay(data, decisions, m)["summary"] for m in [1,1.5,2,3]]
    verification = audit(data, decisions, predictor, result)
    result.update(cost_stress=stresses, audit=verification, freeze=freeze,
                  metadata=dict(k=registered[0]["k"], device=device, seconds=time.monotonic()-start_time,
                                source_sha256=digest(source), runner_sha256=digest(__file__), freeze_sha256=digest(FREEZE)))
    (OUT/"results.json").write_text(json.dumps(result, indent=2))
    for name, rows in [("decisions_and_trades",result["windows"]),("daily_equity",result["daily"])]:
        with (OUT/f"{name}.csv").open("w") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/"audit.json").write_text(json.dumps(verification, indent=2))
    print("RESULT",json.dumps(result["summary"],indent=2),flush=True)
    print("AUDIT",json.dumps({"checks":verification["truncation_and_corruption"],"max_volume_participation":verification["max_daily_volume_participation"]}),flush=True)


if __name__=="__main__":
    main()
