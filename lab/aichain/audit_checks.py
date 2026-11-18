"""Audit checks that need the engine itself (research only; agents never place orders).

    .venv/bin/python -m lab.aichain.audit_checks

1. Provenance: registered code hashes against the files now, frozen specs against the contender registry.
2. The pre-registered 'works often' ranking recomputed from the stored numbers of every group.
3. Block-bootstrap sensitivity: the placebo and the event study resample single calendar months; neighbouring
   months share outcome windows and levels, so 3-month moving blocks are used as a more conservative check.
4. Crypto bar repair: how much the stock-style bad-tick clamp changes the crypto swing results.

Output: reports/research/AICHAIN_20261014/swing/audit.json, appended to the two Croatian pages by their writers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import levels as lv
from lab.aichain import levels_run as lr
from lab.aichain import levels_study as ls
from lab.aichain import swing as S
from lab.aichain import swing_run as R
from lab.aichain.sim import COMMON_END, WINDOWS, Bars, Cost

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing"
BLOCK = 3
BOOT = 4000
SEED = 20261014


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance() -> dict[str, Any]:
    reg = json.loads((OUT / "registration.json").read_text())
    files = {}
    for rel, registered in reg["code_sha256_at_registration"].items():
        now = sha(ROOT / rel)
        files[rel] = {
            "registered": registered,
            "now": now,
            "same": registered == now,
        }
    frozen_ok = {}
    for cid, spec in S.CONTENDERS.items():
        f = json.loads(
            (
                ROOT / "strategies" / "frozen" / f"2026-10-14_SWING_{cid}.json"
            ).read_text()
        )
        defaults = dict(getattr(spec["cls"], "DEFAULTS", {}) or {})
        frozen_ok[cid] = bool(f["params"] == defaults and f["rules"] == spec["rules"])
    return {
        "code_hashes": files,
        "frozen_params_and_rules_equal_registry": frozen_ok,
        "all_frozen_equal": all(frozen_ok.values()),
    }


def ranking_rule() -> dict[str, Any]:
    """Recompute eligibility and order for every group from the stored per-contender numbers."""
    s = json.loads((OUT / "summary.json").read_text())
    bad = []
    for g, v in s["groups"].items():
        rows = []
        for cid, b in v["per_contender"].items():
            if cid == "B0_BUYHOLD" or not b:
                continue
            ok = (
                b["trades"] >= R.MIN_TRADES
                and (b["expectancy_eur_cost_2x"] or -1) > 0
                and (b["profit_factor"] or 0) >= R.MIN_PF
            )
            rows.append((cid, ok, b["expectancy_eur"] * b["trades"] / b["months"]))
        want = [
            c for c, ok, _ in sorted((r for r in rows if r[1]), key=lambda r: -r[2])
        ]
        got = [r["contender"] for r in v["ranking"]]
        if want != got:
            bad.append(g)
    return {"groups_checked": len(s["groups"]), "groups_wrong": bad}


def _month_blocks(m: int, length: int, rng: np.random.Generator) -> np.ndarray:
    nb = int(np.ceil(m / length))
    starts = rng.integers(0, m - length + 1, nb)
    return np.concatenate([np.arange(a, a + length) for a in starts])[:m]


def _preps() -> dict[str, tuple[lv.Prepared, str, int]]:
    use, _ = lr.select_universe()
    preps = {}
    for tk, g in use.items():
        p = lv.prepare(tk, crypto=g == "crypto")
        n = len(p.bars)
        if g in lr.STOCK_GROUPS:
            cut = (
                int(
                    np.searchsorted(
                        p.bars.dates.values, np.datetime64(COMMON_END), side="right"
                    )
                )
                - 1
            )
        else:
            cut = n - 1
        preps[tk] = (p, g, cut)
    return preps


def placebo_blocks(preps: dict[str, tuple[lv.Prepared, str, int]]) -> dict[str, Any]:
    df = ls.sr_placebo_rows(preps, np.random.default_rng(ls.SEED))
    for x in "ntbk":
        df[f"shift_{x}"] = df[f"up_{x}"] + df[f"dn_{x}"]
        df[f"mreal_{x}"] = np.where(df["match_n"] > 0, df[f"real_{x}"], 0)
    variants = ("real", "rand", "shift", "match", "mreal")
    cols = [f"{v}_{x}" for v in variants for x in "ntbk"]
    sums = df.groupby("month")[cols].sum().to_numpy(float)

    def rates(s: np.ndarray, v: str) -> np.ndarray:
        n, t, b, k = (s[cols.index(f"{v}_{x}")] for x in "ntbk")
        return np.array([t / n, b / t, k / t])

    pairs = (
        ("rand", "real", "rand"),
        ("shift", "real", "shift"),
        ("match", "mreal", "match"),
    )
    out: dict[str, Any] = {"block_months": BLOCK, "months": len(sums), "diffs": {}}
    for length in (1, BLOCK):
        rng = np.random.default_rng(SEED)
        boot = []
        for _ in range(BOOT):
            s = sums[_month_blocks(len(sums), length, rng)].sum(axis=0)
            boot.append([rates(s, ref) - rates(s, c) for _, ref, c in pairs])
        arr = np.array(boot)
        for j, (name, _, _) in enumerate(pairs):
            for q, m in enumerate(("touch_rate", "bounce_rate", "break_rate")):
                out["diffs"].setdefault(name, {}).setdefault(m, {})[
                    f"block_{length}"
                ] = [
                    float(np.percentile(arr[:, j, q], 2.5)),
                    float(np.percentile(arr[:, j, q], 97.5)),
                ]
    return out


def event_blocks(preps: dict[str, tuple[lv.Prepared, str, int]]) -> dict[str, Any]:
    start, end = pd.Timestamp(WINDOWS["ai_era"][0]), pd.Timestamp(COMMON_END)
    recs: dict[str, list[dict[str, Any]]] = {k: [] for k in ls.EVENT_NAMES}
    for p, _g, cut in preps.values():
        d = p.bars.dates
        valid = np.asarray((d >= start) & (d <= end)) & (
            np.arange(len(d)) + 1 + max(ls.HORIZONS) <= cut
        )
        if not valid.any():
            continue
        fr = ls.forward_returns(p, cut)
        month = d.to_period("M").astype(str).to_numpy()
        mean_h = {h: float(np.nanmean(fr[h][valid])) for h in ls.HORIZONS}
        for name, flag in ls.event_flags(p, cut).items():
            for t in ls.declustered(flag, valid):
                recs[name].append(
                    {
                        "month": month[t],
                        **{f"x{h}": fr[h][t] - mean_h[h] for h in ls.HORIZONS},
                    }
                )
    all_months = pd.period_range("2023-01", COMMON_END[:7], freq="M").astype(str)
    out: dict[str, Any] = {}
    for name, rows in recs.items():
        df = pd.DataFrame(rows)
        out[name] = {}
        for h in ls.HORIZONS:
            g = (
                df.groupby("month")[f"x{h}"]
                .agg(["sum", "count"])
                .reindex(all_months, fill_value=0)
            )
            sums = g.to_numpy(float)
            res: dict[str, Any] = {
                "n": len(df),
                "mean_excess": float(df[f"x{h}"].mean()),
            }
            for length in (1, BLOCK):
                rng = np.random.default_rng(SEED)
                draws = []
                for _ in range(BOOT):
                    s = sums[_month_blocks(len(sums), length, rng)].sum(axis=0)
                    if s[1] > 0:
                        draws.append(s[0] / s[1])
                res[f"ci95_block_{length}"] = [
                    float(np.percentile(draws, 2.5)),
                    float(np.percentile(draws, 97.5)),
                ]
            out[name][str(h)] = res
    return out


def crypto_repair_effect() -> dict[str, Any]:
    """Swing results of the crypto group with repaired bars (as reported) and with the raw CSV bars."""
    runner = R.Runner({"crypto": R.CRYPTO})
    raw: dict[str, Bars] = {}
    for t in R.CRYPTO:
        d = pd.read_csv(ROOT / "data" / "ohlcv" / f"{t}_1d.csv", parse_dates=["date"])
        d = d.drop_duplicates("date").sort_values("date")
        d = d[
            (d["date"] <= pd.Timestamp(COMMON_END))
            & (d["date"] >= runner.bars[t].dates[0])
        ]
        raw[t] = Bars(
            t,
            pd.DatetimeIndex(d["date"]),
            *(d[x].to_numpy(float) for x in ("open", "high", "low", "close")),
        )

    def run(bars: dict[str, Bars]) -> dict[str, Any]:
        res = {}
        for cid in S.SINGLE_IDS:
            trades: list[dict[str, Any]] = []
            for t in R.CRYPTO:
                r = S.run_swing_sleeve(
                    bars[t],
                    runner.rule(t, cid, {}),
                    *WINDOWS["ai_era"],
                    Cost(bps=R.CRYPTO_BPS),
                )
                trades += r.trades if r else []
            m = S.trade_metrics(trades, R.months_of("ai_era"), 1.0)
            res[cid] = {
                "trades": m["trades"],
                "expectancy_eur": m["expectancy_eur"],
                "profit_factor": m["profit_factor"],
            }
        return res

    rep, rw = run(runner.bars), run(raw)
    repairs = {t: len(b.repairs) for t, b in runner.bars.items()}
    return {
        "repairs_per_crypto_ticker": repairs,
        "contenders_changed": [c for c in rep if rep[c] != rw[c]],
        "repaired": rep,
        "raw": rw,
    }


def trade_concentration() -> dict[str, Any]:
    """Median trade, share of profit in the 10 best trades and holding time on the pooled stock universe."""
    groups = R.peer_groups()
    runner = R.Runner(groups)
    stocks = [
        t
        for g, ts in groups.items()
        if g not in ("crypto", "metali_referentno")
        for t in ts
    ]
    out: dict[str, Any] = {}
    for cid in S.SINGLE_IDS:
        trades = R.all_trades(runner.sleeves(stocks, cid, "ai_era", "1x"))
        rets = np.sort(np.array([t["return"] for t in trades]))
        total = float(rets.sum())
        out[cid] = {
            "trades": len(trades),
            "median_return": float(np.median(rets)),
            "mean_return": float(rets.mean()),
            "best10_share_of_profit": float(rets[-10:].sum() / total)
            if total > 0
            else None,
            "mean_without_best10": float(rets[:-10].mean()),
            "largest_return": float(rets[-1]),
        }
    return out


def main() -> int:
    preps = _preps()
    audit = {
        "date": "2026-10-14",
        "provenance": provenance(),
        "ranking_rule": ranking_rule(),
        "placebo_block_bootstrap": placebo_blocks(preps),
        "event_block_bootstrap": event_blocks(preps),
        "crypto_repair": crypto_repair_effect(),
        "trade_concentration": trade_concentration(),
    }
    (OUT / "audit.json").write_text(json.dumps(audit, indent=1))
    print(json.dumps(audit["provenance"]["code_hashes"], indent=1))
    print(audit["ranking_rule"], audit["crypto_repair"]["contenders_changed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
