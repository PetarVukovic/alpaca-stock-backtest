"""Single-window masked MU forecast demonstration; not a trading backtest."""
from pathlib import Path
import os
import sys
import json
import hashlib
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/kronos"
OUT = ROOT / "reports/research/KRONOS_20261103/MU_MASKED10"
os.environ.setdefault("HF_HOME", str(RUNTIME / "hf_cache"))
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME / "matplotlib"))
sys.path.insert(0, str(RUNTIME / "upstream"))

import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from model import Kronos, KronosTokenizer, KronosPredictor


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / "data/ohlcv/MU_1d.csv"
    data = pd.read_csv(source, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    assert not data.date.duplicated().any()
    history = data.iloc[-100:-10].copy().reset_index(drop=True)
    future_dates = data.iloc[-10:].date.reset_index(drop=True)
    features = history[["open", "high", "low", "close", "volume"]].copy()
    assert np.isfinite(features.to_numpy()).all()
    assert (features[["open", "high", "low", "close"]] > 0).all().all()
    assert (features.volume >= 0).all()
    # Use observed turnover proxy only from historical rows, never holdout values.
    features["amount"] = history.vwap * history.volume
    assert np.isfinite(features.to_numpy()).all()
    history.to_csv(OUT / "input_90_days.csv", index=False)
    config = dict(model="NeoQuasar/Kronos-small", tokenizer="NeoQuasar/Kronos-Tokenizer-base",
                  lookback=90, horizon=10, temperature=0.6, top_p=0.9, sample_count=20,
                  seed=20261103, input_end=str(history.date.iloc[-1].date()),
                  hidden_start=str(future_dates.iloc[0].date()), hidden_end=str(future_dates.iloc[-1].date()),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  upstream_commit=subprocess.check_output(["git", "-C", str(RUNTIME / "upstream"), "rev-parse", "HEAD"], text=True).strip(),
                  purpose="Single historical forecast demo; no strategy, orders, Critic PASS or current recommendation",
                  amount="historical vwap * volume", device="mps" if torch.backends.mps.is_available() else "cpu")
    (OUT / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config), flush=True)
    torch.manual_seed(config["seed"])
    np.random.seed(config["seed"])
    tokenizer = KronosTokenizer.from_pretrained(config["tokenizer"])
    model = Kronos.from_pretrained(config["model"])
    model.eval()
    tokenizer.eval()
    predictor = KronosPredictor(model, tokenizer, device=config["device"], max_context=512)
    start = time.monotonic()
    prediction = predictor.predict(df=features, x_timestamp=history.date,
                                   y_timestamp=future_dates, pred_len=10, T=0.6,
                                   top_p=0.9, sample_count=20, verbose=True)
    prediction.index.name = "date"
    prediction.to_csv(OUT / "forecast_before_comparison.csv")
    assert prediction.shape[0] == 10 and np.isfinite(prediction.to_numpy()).all()
    # Reveal holdout prices only after the model output is persisted.
    actual = data.iloc[-10:].reset_index(drop=True)
    last = float(history.close.iloc[-1])
    predicted = prediction.close.to_numpy()
    observed = actual.close.to_numpy()
    comparison = pd.DataFrame(dict(date=future_dates, actual=observed, forecast=predicted, unchanged=last))
    comparison.to_csv(OUT / "comparison.csv", index=False)
    metrics = dict(last_known_close=last, forecast_final=float(predicted[-1]), actual_final=float(observed[-1]),
                   predicted_return_pct=float((predicted[-1]/last-1)*100), actual_return_pct=float((observed[-1]/last-1)*100),
                   forecast_mae_usd=float(np.abs(predicted-observed).mean()),
                   unchanged_mae_usd=float(np.abs(last-observed).mean()),
                   forecast_mape_pct=float((np.abs(predicted-observed)/observed).mean()*100),
                   inference_seconds=time.monotonic()-start, device=config["device"])
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":11})
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw={"height_ratios":[1,1.35]}, layout="constrained")
    fig.patch.set_facecolor("#f7f8fc")
    for ax in axes:
        ax.set_facecolor("white")
        ax.grid(alpha=.16)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylabel("Cijena zatvaranja (USD)")
    shown = history.iloc[-30:]
    axes[0].plot(shown.date, shown.close, color="#27364b", lw=2, label="Poznata povijest")
    dates = pd.concat([history.date.iloc[-1:], future_dates])
    for ax in axes:
        ax.axvspan(future_dates.iloc[0], future_dates.iloc[-1], color="#edf1fb", alpha=.8)
        ax.plot(dates, np.r_[last, observed], color="#078474", marker="o", ms=4, lw=2, label="Stvarno kretanje")
        ax.plot(dates, np.r_[last, predicted], color="#dd7831", marker="o", ms=4, lw=2, label="Kronos prognoza (prosjek 20 putanja)")
        ax.axvline(history.date.iloc[-1], color="#748197", ls=":")
        ax.tick_params(axis="x", rotation=25)
    axes[0].set_title("MU / Micron — poznata povijest i skrivenih 10 dana", loc="left", fontsize=17, weight="bold")
    axes[0].legend(fontsize=9, loc="upper left")
    axes[1].axhline(last, color="#748197", ls="--", lw=1, label="Jednostavna prognoza: nepromijenjena cijena")
    axes[1].set_title(f"Povećani prikaz: {future_dates.iloc[0]:%d.%m.} – {future_dates.iloc[-1]:%d.%m.%Y.}", loc="left", fontsize=14)
    axes[1].legend(fontsize=9, loc="best")
    fig.suptitle(f"Prognoza: {metrics['predicted_return_pct']:+.1f}%  |  Stvarno: {metrics['actual_return_pct']:+.1f}%", fontsize=21, weight="bold")
    fig.supxlabel("Povijesni demonstracijski test • ulaz: 90 dana • horizont: 10 dana • nije aktualna preporuka", fontsize=10)
    fig.savefig(OUT / "MU_kronos_vs_actual.png", dpi=180)
    plt.close(fig)
    report = f"""# Kronos / MU — skrivenih 10 dana

Jednokratna demonstracija prognoze, nije backtest strategije ni Critic dokaz.
Ulaz završava {config['input_end']}; skriveno {config['hidden_start']} – {config['hidden_end']}.
Model prima samo prethodnih 90 OHLCV svijeća, povijesni vwap × volume i buduće datume.
Prognoza je spremljena prije usporedbe sa stvarnim cijenama; bez podešavanja nakon rezultata.
Temperatura 0.6, top_p 0.9, 20 putanja prosječenih upstream sučeljem; seed 20261103.
Prosjek putanja nije interval pouzdanosti. Datum pretraininga konkretnog checkpointa nije neovisno potvrđen.
MU dostupnost na korisnikovu IBKR računu: nepotvrđeno; bez naloga.
Validator: exit 0, 0 grešaka, 22 upozorenja (vidi reports/data/DATA_CHECK.md).

```json
{json.dumps(metrics, indent=2)}
```

Ponavljanje: `.runtime/kronos/venv/bin/python scripts/kronos_mu_demo.py`
"""
    (OUT / "REPORT.md").write_text(report)
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
