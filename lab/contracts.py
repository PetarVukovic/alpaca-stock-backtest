"""Shared contracts between the lab lanes (engine, critic, app). Change only via the orchestrator.

Everything that crosses a lane boundary is one of these models, serialized as JSON.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel, Field

Period = Literal["IS", "WF", "HO"]
PERIODS: dict[str, tuple[str, str]] = {  # fixed lab splits, inclusive dates
    "IS": ("2016-01-04", "2020-12-31"),
    "WF": ("2021-01-01", "2023-12-31"),
    "HO": ("2024-01-01", "2099-12-31"),
}
PRIMARY = ["MU", "WDC", "STX"]


class Costs(BaseModel):
    round_trip_bps: float = 5.0
    tick_per_side: float = 1.0
    stress_multiplier: float = 1.0


class FrozenStrategy(BaseModel):
    """strategies/frozen/{YYYY-MM-DD}_{ID}.json. Immutable after freezing; a change means a new id."""
    id: str = Field(description="C#, H#, H-N# ... never reuse an old number")
    created: date
    family: str = Field(description="dip | pullback | trend | breakout | relative_strength | event | earnings | other")
    hypothesis: str
    mechanism: str = Field(description="Why the edge should exist: who is on the other side and why")
    persistence: str = Field(description="Why it should keep working")
    universe: list[str]
    timeframe: Literal["daily", "hourly", "5min"] = "daily"
    entry: dict
    exit: dict
    max_notional_usd: float = 500.0
    max_positions: int = 1
    costs: Costs = Costs()


class PeriodStats(BaseModel):
    n: int
    mean_pct: float | None = None
    win_rate: float | None = None
    sharpe: float | None = None
    max_dd_pct: float | None = None
    buy_hold_sharpe: float | None = None


class BacktestResult(BaseModel):
    """reports/backtest/{ID}_{TICKER}.json next to the .md report."""
    strategy_id: str
    ticker: str
    run_at: datetime
    costs: Costs
    k_at_run: int = Field(description="Number of trials in the ledger at the time of the run")
    periods: dict[Period, PeriodStats]
    flags: list[str] = []


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class CriticCheck(BaseModel):
    number: int
    name: str
    passed: bool
    detail: str = Field(description="Actual numbers, not just pass/fail")


class CriticVerdict(BaseModel):
    """Written by lab.critic; rendered to reports/gate/{date}_{ID}_VERDICT.md."""
    strategy_id: str
    date: date
    k: int
    checks: list[CriticCheck]
    verdict: Verdict
    reasons: list[str]


class ApprovedEntry(BaseModel):
    strategy_id: str
    verdict_file: str
    approved_on: date


class ApprovedList(BaseModel):
    """reports/gate/approved_list.json. Only the critic writes it."""
    updated_at: datetime
    critic: str = "Trading Quant Critic"
    strategies: list[ApprovedEntry] = []
    note: str = ""


class SignalKind(str, Enum):
    BUY = "KUPI"
    WAIT = "PRIČEKAJ"
    DONT_BUY = "NE KUPUJ"


class Validation(str, Enum):
    APPROVED = "APPROVED"          # Critic PASS and on approved_list
    EXPERIMENTAL = "EXPERIMENTAL"  # research only, forward test, tiny size, per-strategy opt-in by the researcher


class Signal(BaseModel):
    strategy_id: str
    ticker: str
    kind: SignalKind
    validation: Validation
    reason: str
    created_at: datetime
    max_notional_usd: float


class OrderIntent(BaseModel):
    """What the app may ask a broker for. Always paper while PAPER_ONLY is true."""
    ticker: str
    side: Literal["buy", "sell"]
    notional_usd: float
    stop_pct: float = Field(gt=0, description="A protective stop is mandatory")
    target_pct: float | None = None
    max_hold_days: int | None = None
    validation: Validation
    strategy_id: str


PAPER_ONLY = True


class Broker(Protocol):
    """Broker adapter. Alpaca paper today; an EU-accessible broker may replace it for live trading.

    The app and engine must depend on this interface, never on alpaca-py directly.
    """
    def account(self) -> dict: ...
    def positions(self) -> list[dict]: ...
    def place(self, intent: OrderIntent) -> dict: ...
    def cancel_all(self) -> None: ...  # kill switch
