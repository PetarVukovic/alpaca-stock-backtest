"""Common daily simulator for the AI-chain tournament. Research only: it never places orders.

Conventions (identical for every contender):
- Daily bars. A decision is made at the close of day t and filled at the open of day t+1.
- Long only, no leverage, fractional units (a sleeve always invests its whole cash).
- Cost per side in basis points of the fill price (optionally plus a fixed tick, used only by the
  parity test against the original C13C replay). Buy fill = open * (1 + c), sell fill = price * (1 - c).
- Open positions at the end of a window are liquidated at the last close and pay the exit cost.
- Data rules (``load_bars``): halted/frozen history before ``effective_start`` is dropped, bad ticks are clamped.
- Intraday stops: if low <= stop the position is closed at the stop price, or at the open if the bar
  gapped below the stop. A stop that is set or raised on a bar only acts from the next bar.
- A sleeve is one ticker with its own capital. Prices are USD, treated as EUR-equivalent (FX not modelled).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
COMMON_END = "2026-10-05"
AI_ERA_START = "2023-01-01"
START_CAPITAL = 1000.0
BASE_BPS = 2.5
WINDOWS: dict[str, tuple[str, str]] = {
    "full": ("2016-01-01", COMMON_END),
    "ai_era": (AI_ERA_START, COMMON_END),
    "y2016_2020": ("2016-01-01", "2020-12-31"),
    "y2021_2022": ("2021-01-01", "2022-12-31"),
}


@dataclass(frozen=True)
class Cost:
    """Cost per side: ``bps`` of the price plus ``tick`` currency units (tick is 0 except in the parity test)."""

    bps: float = BASE_BPS
    tick: float = 0.0

    def buy(self, price: float) -> float:
        return price * (1.0 + self.bps / 1e4) + self.tick

    def sell(self, price: float) -> float:
        return max(0.0, price * (1.0 - self.bps / 1e4) - self.tick)


DEFAULT_COST = Cost()


@dataclass
class Bars:
    ticker: str
    dates: pd.DatetimeIndex
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    repairs: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.dates)

    def cut(self, end: str | pd.Timestamp) -> Bars:
        n = int(
            np.searchsorted(
                self.dates.values, np.datetime64(pd.Timestamp(end)), side="right"
            )
        )
        return Bars(
            self.ticker,
            self.dates[:n],
            self.open[:n],
            self.high[:n],
            self.low[:n],
            self.close[:n],
            [r for r in self.repairs if r[:10] <= str(self.dates[n - 1].date())]
            if n
            else [],
        )


BAD_TICK_RATIO = 1.25


def repair_bad_ticks(
    raw: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Clamp an intraday high/low print that is far outside every neighbouring price (a bad tick).

    A high is bad when it exceeds ``BAD_TICK_RATIO`` times the largest of the bar's open, close, the previous
    close and the next close (a low: below 1 / ``BAD_TICK_RATIO`` of the smallest). The value is clamped to
    that reference, never invented. Rows are never dropped and the CSV on disk is never touched. Each repair
    is returned as ``"YYYY-MM-DD high 195.95 -> 121.79"`` so the report can list it.
    """
    raw = raw.reset_index(drop=True).copy()
    ref = pd.concat(
        [raw["open"], raw["close"], raw["close"].shift(1), raw["close"].shift(-1)],
        axis=1,
    )
    hi_ref, lo_ref = ref.max(axis=1), ref.min(axis=1)
    notes: list[str] = []
    for i in raw.index[raw["high"] > hi_ref * BAD_TICK_RATIO]:
        notes.append(
            f"{raw['date'][i].date()} high {raw['high'][i]:g} -> {hi_ref[i]:g}"
        )
        raw.loc[i, "high"] = hi_ref[i]
    for i in raw.index[raw["low"] < lo_ref / BAD_TICK_RATIO]:
        notes.append(f"{raw['date'][i].date()} low {raw['low'][i]:g} -> {lo_ref[i]:g}")
        raw.loc[i, "low"] = lo_ref[i]
    return raw, notes


def load_bars(ticker: str, end: str = COMMON_END) -> Bars:
    """Daily bars from ``data/ohlcv/{ticker}_1d.csv`` up to and including ``end`` (no parquet).

    Two data-quality rules apply to every ticker, identically:
    - History before ``effective_start`` is dropped: a run of >= 5 zero-volume bars is a trading halt with a
      frozen price (SMCI before 2020-01-14, NBIS before 2024-10-21), not tradable data.
    - Bad intraday ticks are clamped, see ``repair_bad_ticks`` (NVDA 2024-06-10 high).
    """
    from lab.aichain.universe import effective_start

    raw = pd.read_csv(
        ROOT / "data" / "ohlcv" / f"{ticker}_1d.csv", parse_dates=["date"]
    )
    raw = raw.drop_duplicates("date").sort_values("date")
    raw = raw[raw["date"] <= pd.Timestamp(end)]
    first = pd.Timestamp(effective_start(raw))
    raw = raw[raw["date"] >= first]
    raw, notes = repair_bad_ticks(raw)
    return Bars(
        ticker,
        pd.DatetimeIndex(raw["date"]),
        raw["open"].to_numpy(float),
        raw["high"].to_numpy(float),
        raw["low"].to_numpy(float),
        raw["close"].to_numpy(float),
        notes,
    )


def cents(value: float) -> float:
    """Round to whole cents like the original C13C (decimal, half-even)."""
    return float(Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN))


@dataclass
class Position:
    entry_i: int
    entry_price: float  # fill price including cost
    raw_entry: float
    units: float
    peak: float
    stop: float | None = None
    target: float | None = None
    bars: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


class Rule(Protocol):
    """A single-ticker rule. All hooks may only look at data up to the bar index they are given."""

    id: str
    enter_at_first_bar: bool

    def prepare(self, bars: Bars) -> None: ...

    def entry(self, i: int) -> bool: ...

    def on_fill(self, i: int, pos: Position) -> None: ...

    def exit_signal(self, i: int, pos: Position) -> str | None: ...

    def after_bar(self, i: int, pos: Position) -> None: ...

    def on_exit(self, i: int, reason: str) -> None: ...


@dataclass
class SleeveResult:
    ticker: str
    dates: pd.DatetimeIndex
    equity: np.ndarray
    exposure: np.ndarray  # fraction of equity invested at each close
    trades: list[dict[str, Any]]
    decisions: list[tuple[str, bool]]  # (date, entry decision) for the lookahead test


def run_sleeve(
    bars: Bars,
    rule: Rule,
    start: str,
    end: str,
    cost: Cost = DEFAULT_COST,
    capital: float = START_CAPITAL,
) -> SleeveResult | None:
    """Simulate one sleeve over ``[start, end]`` with an empty account at ``start``.

    Indicators are computed on all bars (warm-up before ``start`` is allowed, nothing after ``end``).
    A signal on the bar just before ``start`` schedules the first fill at the open of ``start``.
    """
    bars = bars.cut(end)
    rule.prepare(bars)
    idx = np.nonzero(bars.dates.values >= np.datetime64(pd.Timestamp(start)))[0]
    if len(idx) == 0:
        return None
    i0 = int(idx[0])
    n = len(bars)
    cash, pos = capital, None
    pending_entry = False
    pending_exit: str | None = None
    if i0 == 0:
        pending_entry = bool(rule.enter_at_first_bar)
    else:
        pending_entry = bool(rule.entry(i0 - 1))
    equity = np.empty(n - i0)
    exposure = np.zeros(n - i0)
    trades: list[dict[str, Any]] = []
    decisions: list[tuple[str, bool]] = []

    def close_pos(i: int, raw_exit: float, reason: str, detail: str = "") -> None:
        nonlocal cash, pos
        assert pos is not None
        sell = cost.sell(raw_exit)
        cash += pos.units * sell
        trades.append(
            {
                "entry_date": str(bars.dates[pos.entry_i].date()),
                "entry_price": pos.entry_price,
                "raw_entry": pos.raw_entry,
                "exit_date": str(bars.dates[i].date()),
                "exit_price": sell,
                "raw_exit": raw_exit,
                "reason": reason,
                "detail": detail,
                "return": sell / pos.entry_price - 1.0,
                "bars_held": i - pos.entry_i + 1,
            }
        )
        rule.on_exit(i, reason)
        pos = None

    for i in range(i0, n):
        o, h, lo, c = bars.open[i], bars.high[i], bars.low[i], bars.close[i]
        if pending_exit is not None and pos is not None:
            close_pos(i, o, "signal", pending_exit)
        pending_exit = None
        if pending_entry and pos is None:
            buy = cost.buy(o)
            pos = Position(i, buy, o, cash / buy, buy)
            cash = 0.0
            rule.on_fill(i, pos)
        pending_entry = False
        if pos is not None:
            pos.bars += 1
            if pos.stop is not None and lo <= pos.stop:
                gap = o < pos.stop
                close_pos(i, min(o, pos.stop), "stop", "gap_stop" if gap else "stop")
            elif pos.target is not None and h >= pos.target:
                close_pos(i, max(o, pos.target), "target", "target")
            else:
                pos.peak = max(pos.peak, h)
                rule.after_bar(i, pos)
        equity[i - i0] = cash + (pos.units * c if pos is not None else 0.0)
        exposure[i - i0] = (pos.units * c) / equity[i - i0] if pos is not None else 0.0
        if i == n - 1 and pos is not None:
            # forced liquidation at the last close: the exit cost is paid, so the last equity point is net of it
            equity[i - i0] = cash + pos.units * cost.sell(c)
        if pos is not None:
            reason = rule.exit_signal(i, pos)
            if reason is not None:
                pending_exit = reason
            decisions.append((str(bars.dates[i].date()), False))
        else:
            take = bool(rule.entry(i))
            pending_entry = take
            decisions.append((str(bars.dates[i].date()), take))
    if pos is not None:
        last = n - 1
        trades.append(
            {
                "entry_date": str(bars.dates[pos.entry_i].date()),
                "entry_price": pos.entry_price,
                "raw_entry": pos.raw_entry,
                "exit_date": str(bars.dates[last].date()),
                "exit_price": cost.sell(float(bars.close[last])),
                "raw_exit": float(bars.close[last]),
                "reason": "end",
                "detail": "liquidated at last close, exit cost paid",
                "return": cost.sell(float(bars.close[last])) / pos.entry_price - 1.0,
                "bars_held": last - pos.entry_i + 1,
            }
        )
    return SleeveResult(
        bars.ticker, bars.dates[i0:], equity, exposure, trades, decisions
    )


def run_rotation(
    bars: dict[str, Bars],
    picker: Any,
    start: str,
    end: str,
    cost: Cost = DEFAULT_COST,
    capital: float = START_CAPITAL,
) -> SleeveResult:
    """Pooled portfolio rebalanced at the first open of each month (used by K6).

    ``picker(day_i, calendar, bars)`` returns target weights per ticker (sum <= 1, rest is cash) using only
    data up to the close before the rebalance open. Trading to the targets costs ``cost`` on each traded value.
    """
    cal = pd.DatetimeIndex(
        sorted(set().union(*[set(b.cut(end).dates) for b in bars.values()]))
    )
    cal = cal[cal >= pd.Timestamp(start)]
    full_cal = pd.DatetimeIndex(
        sorted(set().union(*[set(b.cut(end).dates) for b in bars.values()]))
    )
    pos_in_full = {d: k for k, d in enumerate(full_cal)}
    cut = {t: b.cut(end) for t, b in bars.items()}
    lookup = {t: {d: k for k, d in enumerate(b.dates)} for t, b in cut.items()}
    units = {t: 0.0 for t in cut}
    cash = capital
    equity = np.empty(len(cal))
    exposure = np.zeros(len(cal))
    trades: list[dict[str, Any]] = []
    last_close = {t: None for t in cut}
    prev_month = None
    holds: dict[str, tuple[str, float, float]] = {}
    for k, day in enumerate(cal):
        month = (day.year, day.month)
        first_of_month = month != prev_month
        prev_month = month
        if first_of_month:
            prior_day = full_cal[pos_in_full[day] - 1] if pos_in_full[day] > 0 else None
            weights = picker(prior_day, cut) if prior_day is not None else {}
            opens = {t: cut[t].open[lookup[t][day]] for t in cut if day in lookup[t]}
            nav = cash + sum(
                units[t] * opens[t] for t in cut if t in opens and units[t] > 0
            )
            nav += sum(
                units[t] * last_close[t] for t in cut if t not in opens and units[t] > 0
            )
            for t in cut:  # sells first
                if t not in opens:
                    continue
                want = weights.get(t, 0.0) * nav / opens[t]
                if want < units[t] - 1e-12:
                    sold = units[t] - want
                    cash += sold * cost.sell(opens[t])
                    if want <= 1e-12 and t in holds:
                        ed, ep, eu = holds.pop(t)
                        trades.append(
                            {
                                "entry_date": ed,
                                "entry_price": ep,
                                "exit_date": str(day.date()),
                                "exit_price": cost.sell(opens[t]),
                                "reason": "signal",
                                "return": cost.sell(opens[t]) / ep - 1.0,
                                "ticker": t,
                            }
                        )
                    units[t] = want
            for t in cut:  # buys: scale down if cash is short (costs eat into the cash)
                if t not in opens:
                    continue
                want = weights.get(t, 0.0) * nav / opens[t]
                if want > units[t] + 1e-12:
                    add = min(want - units[t], cash / cost.buy(opens[t]))
                    if add > 0:
                        cash -= add * cost.buy(opens[t])
                        if t not in holds:
                            holds[t] = (str(day.date()), cost.buy(opens[t]), add)
                        units[t] += add
        value = 0.0
        for t in cut:
            if day in lookup[t]:
                last_close[t] = cut[t].close[lookup[t][day]]
            if units[t] > 0 and last_close[t] is not None:
                value += units[t] * last_close[t]
        equity[k] = cash + value
        exposure[k] = value / equity[k] if equity[k] > 0 else 0.0
    # forced liquidation at the last close: exit cost on every open holding, last equity point is net of it
    for t, (ed, ep, eu) in holds.items():
        px = float(last_close[t])
        trades.append(
            {
                "entry_date": ed,
                "entry_price": ep,
                "exit_date": str(cal[-1].date()),
                "exit_price": cost.sell(px),
                "reason": "end",
                "return": cost.sell(px) / ep - 1.0,
                "ticker": t,
            }
        )
    equity[-1] -= sum(
        units[t] * (last_close[t] - cost.sell(float(last_close[t])))
        for t in cut
        if units[t] > 0 and last_close[t] is not None
    )
    return SleeveResult("PORTFOLIO", cal, equity, exposure, trades, [])


def sum_sleeves(
    results: list[SleeveResult], capital: float = START_CAPITAL
) -> SleeveResult:
    """Segment portfolio: sleeves share nothing. Before a ticker exists its sleeve is idle cash."""
    cal = pd.DatetimeIndex(sorted(set().union(*[set(r.dates) for r in results])))
    total = np.zeros(len(cal))
    expo_num = np.zeros(len(cal))
    trades: list[dict[str, Any]] = []
    for r in results:
        s = pd.Series(r.equity, index=r.dates).reindex(cal).ffill().fillna(capital)
        e = (
            pd.Series(r.exposure * r.equity, index=r.dates)
            .reindex(cal)
            .ffill()
            .fillna(0.0)
        )
        total += s.to_numpy()
        expo_num += e.to_numpy()
        trades += [{**t, "ticker": r.ticker} for t in r.trades]
    trades.sort(key=lambda t: t["entry_date"])
    return SleeveResult("SEGMENT", cal, total, expo_num / total, trades, [])


def _max_drawdown(values: np.ndarray, capital: float) -> float:
    peak = np.maximum.accumulate(np.r_[capital, values])[1:]
    return float((values / peak - 1.0).min())


def stats(res: SleeveResult, capital: float) -> dict[str, Any]:
    """Window statistics from the equity curve (start capital counts as the first peak)."""
    v = res.equity
    rets = np.diff(np.r_[capital, v]) / np.r_[capital, v[:-1]]
    days = max((res.dates[-1] - res.dates[0]).days, 1)
    years = days / 365.25
    total = float(v[-1] / capital - 1.0)
    cagr = (
        float((v[-1] / capital) ** (1 / years) - 1.0)
        if years >= 1 / 12 and v[-1] > 0
        else None
    )
    sd = float(rets.std(ddof=1)) if len(rets) > 2 else 0.0
    sharpe = float(rets.mean() / sd * np.sqrt(252)) if sd > 0 else None
    tr = [t["return"] for t in res.trades]
    wins = [x for x in tr if x > 0]
    losses = [x for x in tr if x <= 0]
    return {
        "start": str(res.dates[0].date()),
        "end": str(res.dates[-1].date()),
        "bars": len(v),
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(v, capital),
        "trades": len(tr),
        "hit_rate": float(len(wins) / len(tr)) if tr else None,
        "avg_win": float(np.mean(wins)) if wins else None,
        "avg_loss": float(np.mean(losses)) if losses else None,
        "exposure_pct": float(res.exposure.mean() * 100.0),
        "time_in_market_pct": float((res.exposure > 0).mean() * 100.0),
        "end_value": float(v[-1]),
        "start_capital": capital,
    }


def daily_returns(res: SleeveResult, capital: float) -> pd.Series:
    v = res.equity
    return pd.Series(
        np.diff(np.r_[capital, v]) / np.r_[capital, v[:-1]], index=res.dates
    )
