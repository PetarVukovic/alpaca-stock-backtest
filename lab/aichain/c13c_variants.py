"""Pre-declared C13C improvement variants for the C13C notebook. Research only; agents never place orders.

Every variant changes exactly one idea of the original C13C (``contenders.C13C``): the entry stays
"close above SMA200 and down 5 % over 5 bars", fills at the next open, long only. Variants are frozen and
registered in the trial ledger BEFORE any result is computed (``register``), so K stays honest.

Acceptance rule written before the run (see ``ACCEPTANCE``): a variant is only called an improvement when it
beats the original in BOTH halves of the AI era, in the 2021-2022 context and under 2x costs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from lab import ledger
from lab.aichain.contenders import C13C, trail_stop
from lab.aichain.sim import Bars, Position
from lab.aichain.swing import atr

ROOT = Path(__file__).resolve().parents[2]
FREEZE_DATE = "2026-10-14"
MOM_BARS = 126
ATR_BARS = 14
PEER_STALE_DAYS = 5

ACCEPTANCE = (
    "A variant counts as an improvement only if, versus the original C13C on the 43-stock pool, "
    "expectancy per trade AND profit factor are higher in both AI-era halves (2023-2024 and 2025-2026), "
    "total return is not lower in 2021-2022, and expectancy stays positive at 2x costs."
)


class X1Trail15(C13C):
    id = "C13CX1_TRAIL15"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "trail": 0.15}


class X2Trail20(C13C):
    id = "C13CX2_TRAIL20"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "trail": 0.20}


class X3AtrTrail(C13C):
    """Stop = peak - mult * ATR14 (volatility-adapted), never lowered."""

    id = "C13CX3_ATR_TRAIL"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "atr_mult": 3.0}

    def prepare(self, bars: Bars) -> None:
        super().prepare(bars)
        self.atr_arr = atr(bars, ATR_BARS)

    def _stop(self, i: int, peak: float) -> float | None:
        a = self.atr_arr[i]
        if np.isnan(a):
            return None
        return peak - self.params["atr_mult"] * float(a)

    def on_fill(self, i: int, pos: Position) -> None:
        self.armed = False
        stop = self._stop(i - 1, pos.peak)
        pos.stop = stop if stop is not None else trail_stop(pos.peak, self.params["trail"])

    def after_bar(self, i: int, pos: Position) -> None:
        stop = self._stop(i, pos.peak)
        if stop is not None:
            pos.stop = max(pos.stop or 0.0, stop)


class X4MomConfirm(C13C):
    """Entry additionally needs a positive 126-day return and a place in the upper half of the peer group."""

    id = "C13CX4_MOM_CONFIRM"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "mom_bars": MOM_BARS}

    def __init__(self, **params: Any) -> None:
        super().__init__(**params)
        self.peers: dict[str, Bars] = {}

    def prepare(self, bars: Bars) -> None:
        super().prepare(bars)
        n = int(self.params["mom_bars"])
        own = pd.Series(bars.close, index=bars.dates)
        own_ret = own / own.shift(n) - 1
        below = np.zeros(len(bars))
        valid = np.zeros(len(bars))
        for ticker, other in self.peers.items():
            if ticker == bars.ticker:
                continue
            c = pd.Series(other.close, index=other.dates)
            r = (c / c.shift(n) - 1).reindex(bars.dates, method="ffill")
            stale = (
                bars.dates.to_series()
                - pd.Series(other.dates, index=other.dates).reindex(
                    bars.dates, method="ffill"
                )
            ).dt.days > PEER_STALE_DAYS
            ok = (~stale.to_numpy()) & r.notna().to_numpy()
            valid += ok
            below += ok & (r.to_numpy() < own_ret.to_numpy())
        share_below = np.where(valid > 0, below / np.maximum(valid, 1), np.nan)
        confirm = (own_ret.to_numpy() > 0) & (share_below >= 0.5)
        self.base = self.base & np.nan_to_num(confirm, nan=0).astype(bool)


class X5Dip3(C13C):
    id = "C13CX5_DIP3"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "dip": 0.03}


class X6Sma100(C13C):
    id = "C13CX6_SMA100"
    DEFAULTS: ClassVar[dict[str, Any]] = {**C13C.DEFAULTS, "sma": 100}


VARIANTS: dict[str, dict[str, Any]] = {
    "X1_TRAIL15": {
        "cls": X1Trail15,
        "idea": "Trailing stop 15 % below the peak instead of 10 %: fewer shake-outs, bigger give-back.",
    },
    "X2_TRAIL20": {
        "cls": X2Trail20,
        "idea": "Trailing stop 20 % below the peak: lets winners run, accepts deeper pullbacks.",
    },
    "X3_ATR_TRAIL": {
        "cls": X3AtrTrail,
        "idea": "Stop at peak minus 3 x ATR14: wide stop for volatile names, tight for calm ones.",
    },
    "X4_MOM_CONFIRM": {
        "cls": X4MomConfirm,
        "idea": "Buy the dip only if the 126-day return is positive and in the upper half of the peer group.",
    },
    "X5_DIP3": {
        "cls": X5Dip3,
        "idea": "Smaller dip trigger (-3 % over 5 days instead of -5 %): more trades.",
    },
    "X6_SMA100": {
        "cls": X6Sma100,
        "idea": "Trend filter SMA100 instead of SMA200: earlier entries after a trend change.",
    },
}


def freeze_spec(vid: str) -> dict[str, Any]:
    spec = VARIANTS[vid]
    cls = spec["cls"]
    return {
        "id": f"C13CX_{vid}",
        "label": "pre-registered improvement variant of C13C",
        "idea": spec["idea"],
        "base": "contenders.C13C (K1_C13C_ORIG), one change only",
        "params": dict(cls.DEFAULTS),
        "acceptance_rule": ACCEPTANCE,
        "execution": "decide at close of day t, fill at open of t+1, long only, no leverage, "
        "2.5 bps per side, fractional units, one sleeve per ticker",
        "code_files": ["lab/aichain/c13c_variants.py"],
        "status": "research only; not a lab Critic PASS; no tuning",
    }


def register() -> dict[str, Any]:
    """Write the freeze files and ledger rows for all variants; idempotent, refuses a changed spec."""
    info: dict[str, Any] = {}
    for vid in VARIANTS:
        spec = freeze_spec(vid)
        text = json.dumps(spec, indent=2, sort_keys=True, default=str)
        path = ROOT / "strategies" / "frozen" / f"{FREEZE_DATE}_C13CX_{vid}.json"
        if path.exists():
            if json.loads(path.read_text()) != json.loads(text):
                raise SystemExit(f"{path.name} differs from the variant spec: use a new ID")
        else:
            path.write_text(text)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        k = ledger.register_strategy(
            f"C13CX_{vid}",
            digest,
            agent="claude-c13c-notebook",
            purpose="C13C notebook improvement variants 2026-10-14; not Critic",
            unit="frozen_strategy_id",
        )
        info[vid] = {"freeze_file": str(path.relative_to(ROOT)), "sha256": digest, "k": k}
    return info


if __name__ == "__main__":
    print(json.dumps(register(), indent=2))
