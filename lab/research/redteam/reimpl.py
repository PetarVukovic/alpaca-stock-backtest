"""Independent plain pandas/numpy implementation of the documented lab rules.

Spec: lab/strategies/README.md and the red-team brief. This module deliberately does NOT import
lab.engine, lab.strategies.registry, lab.costs or lab.data, so any shared bug cannot hide here.

Rules implemented from the spec:
- signal is evaluated on the closed bar t, the fill happens at the open of bar t+1;
- costs per side: price * (round_trip_bps / 2 / 1e4) + 0.01 USD * tick_per_side, all times the stress
  multiplier (doubled for thin tickers);
- at most one long position, notional = min(500, cash);
- exits: hold / risk (stop, target, hold_bars) / trend / rule / trailing / time;
  gap through a level fills at the open, stop wins if stop and target touch in the same bar,
  the trailing peak comes from previous bars (a new high counts from the next bar);
- periods IS 2016-01-04..2020-12-31, WF 2021-01-01..2023-12-31, HO 2024-01-01..; every period
  starts flat and is force-liquidated at the close of its last bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PERIODS = {
    "IS": ("2016-01-04", "2020-12-31"),
    "WF": ("2021-01-01", "2023-12-31"),
    "HO": ("2024-01-01", "2099-12-31"),
}
THIN = {"MRAM", "ACMR", "DRAM", "SKHY", "SNDK"}
TICK = 0.01
NY = "America/New_York"


# --------------------------------------------------------------------------- data


@cache
def daily(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data/ohlcv" / f"{ticker}_1d.csv")
    df["day"] = df["date"].astype(str).str[:10]
    df = df.set_index(pd.DatetimeIndex(pd.to_datetime(df["day"]), name="ts"))
    return df[["day", "open", "high", "low", "close", "volume"]].sort_index()


@cache
def hourly(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data/hourly" / f"{ticker}_1h_clean.csv")
    df = df[df["session"] == "regular"].copy()
    ts = pd.to_datetime(df["ts"], utc=True)
    df["day"] = df["date_et"].astype(str)
    df["ny_hour"] = ts.dt.tz_convert(NY).dt.hour.to_numpy()
    df["ny_minute"] = (
        ts.dt.tz_convert(NY).dt.hour * 60 + ts.dt.tz_convert(NY).dt.minute
    ).to_numpy()
    # Hourly session close = the 15:00-16:00 ET bar (the old CSV has no half-day marker).
    df["session_end"] = df["ny_hour"] == 15
    df = df.set_index(pd.DatetimeIndex(ts, name="ts"))
    cols = [
        "day",
        "ny_hour",
        "ny_minute",
        "session_end",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades",
    ]
    return df[cols].sort_index()


@cache
def five_minute(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data/intraday" / f"{ticker}_5m_clean.csv")
    df = df[df["session"] == "regular"].copy()
    ts = pd.to_datetime(df["ts"], utc=True)
    local = ts.dt.tz_convert(NY)
    df["day"] = local.dt.strftime("%Y-%m-%d").to_numpy()
    df["ny_hour"] = local.dt.hour.to_numpy()
    df["ny_minute"] = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    df["session_end"] = df["session_end"].astype(str).str.lower().isin(["true", "1"])
    df = df.set_index(pd.DatetimeIndex(ts, name="ts"))
    cols = [
        "day",
        "ny_hour",
        "ny_minute",
        "session_end",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades",
    ]
    return df[cols].sort_index()


def period_slices(days: np.ndarray) -> dict[str, np.ndarray]:
    return {p: np.where((days >= a) & (days <= b))[0] for p, (a, b) in PERIODS.items()}


# --------------------------------------------------------------------------- costs


@dataclass(frozen=True)
class CostModel:
    round_trip_bps: float = 5.0
    tick_per_side: float = 1.0
    stress: float = 1.0

    def for_ticker(self, ticker: str) -> CostModel:
        return CostModel(
            self.round_trip_bps,
            self.tick_per_side,
            self.stress * (2 if ticker in THIN else 1),
        )

    def side_cost(self, price: float) -> float:
        return (
            price * self.round_trip_bps / 2 / 1e4 + TICK * self.tick_per_side
        ) * self.stress

    def buy(self, price: float) -> float:
        return price + self.side_cost(price)

    def sell(self, price: float) -> float:
        return price - self.side_cost(price)


# --------------------------------------------------------------------------- signals


def sma(x: pd.Series, n: int) -> pd.Series:
    # Plain cumulative-sum moving average, written differently from rolling().mean().
    values = x.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) >= n:
        csum = np.concatenate([[0.0], np.cumsum(values)])
        out[n - 1 :] = (csum[n:] - csum[:-n]) / n
    return pd.Series(out, index=x.index)


def prior_max(x: pd.Series, n: int) -> pd.Series:
    """Max of the n values strictly before t."""
    values = x.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for i in range(n, len(values)):
        out[i] = values[i - n : i].max()
    return pd.Series(out, index=x.index)


def entry_signal(
    df: pd.DataFrame,
    entry: dict,
    context: dict | None = None,
    ticker: str | None = None,
) -> pd.Series:
    kind = entry["type"]
    c = df["close"]
    tw = entry.get("trend_window", 200)
    above = c > sma(c, tw)
    if kind in {"buy_hold", "equal_basket"}:
        return pd.Series(True, index=df.index)
    if kind == "trend":
        return above.fillna(False)
    if kind == "dip_in_trend":
        k = entry.get("dip_bars", 5)
        drop = c / c.shift(k) - 1
        return (above & (drop <= -entry.get("dip_pct", 0.05))).fillna(False)
    if kind == "breakout":
        return (c > prior_max(df["high"], entry.get("lookback", 63))).fillna(False)
    if kind in {"volatility_breakout", "volatility_shock"}:
        vw, lb = entry.get("vol_window", 20), entry.get("lookback", 63)
        ret = c / c.shift(1) - 1
        vol = ret.rolling(vw).std(ddof=1)
        # Average of the lb volatility readings up to and including yesterday.
        base = vol.shift(1).rolling(lb).mean()
        if kind == "volatility_breakout":
            quiet = vol.shift(1) < base * entry.get("compression", 0.8)
            return (quiet & (c > prior_max(df["high"], lb))).fillna(False)
        return (
            (vol > base * entry.get("shock_multiplier", 2)) & (ret < 0) & above
        ).fillna(False)
    if kind == "relative_strength":
        lb = entry.get("lookback", 63)
        mom = pd.DataFrame(
            {s: context[s]["close"].reindex(df.index, method="ffill") for s in context}
        )
        mom = mom / mom.shift(lb) - 1
        best = mom.max(axis=1)
        leader = mom.apply(
            lambda row: row.idxmax() if row.notna().any() else None, axis=1
        )
        return ((leader == ticker) & (best > 0)).fillna(False).astype(bool)
    if kind == "open_reversal":
        minute = df["ny_minute"]
        opening = (minute >= 570) & (minute <= 595)
        bars_so_far = opening.astype(int).groupby(df["day"]).cumsum()
        open_930 = df["open"].where(minute == 570).groupby(df["day"]).transform("max")
        move = c / open_930 - 1
        return (
            (minute == 595)
            & (bars_so_far == 6)
            & (move <= -entry.get("drop_pct", 0.005))
        ).fillna(False)
    if kind == "day_trade":
        mode = entry.get("mode", "first_hour")
        hour = df["ny_hour"]
        if mode == "last_hour":
            return hour == 14
        sig = hour == 10
        if mode == "gap":
            last_close = df.groupby("day")["close"].last()
            first_open = df.groupby("day")["open"].first()
            gap = first_open / last_close.shift(1) - 1
            sig &= df["day"].map(gap) >= entry.get("gap_pct", 0.01)
        return sig.fillna(False)
    raise NotImplementedError(kind)


def exit_signal(
    df: pd.DataFrame, entry: dict, exit_rule: dict, entry_sig: pd.Series
) -> pd.Series:
    if exit_rule["type"] not in {"trend", "rule"}:
        return pd.Series(False, index=df.index)
    if entry["type"] == "relative_strength":
        return ~entry_sig
    n = exit_rule.get("trend_window", entry.get("trend_window", 200))
    return (df["close"] < sma(df["close"], n)).fillna(False)


# --------------------------------------------------------------------------- simulation


@dataclass
class Trade:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_fill: float
    exit_fill: float
    notional: float
    reason: str
    symbol: str = ""

    @property
    def net(self) -> float:
        return self.exit_fill / self.entry_fill - 1


@dataclass
class Book:
    trades: list = field(default_factory=list)
    equity: list = field(default_factory=list)


def simulate_single(
    df,
    entry_sig,
    exit_sig,
    exit_rule,
    cost: CostModel,
    *,
    day_trade=False,
    vol_target=None,
    symbol="",
):
    """One period, one ticker. All arrays are already restricted to the period."""
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    days = df["day"].to_numpy()
    hours = df["ny_hour"].to_numpy() if "ny_hour" in df else None
    ends = df["session_end"].to_numpy(bool) if "session_end" in df else None
    ts = df.index
    es, xs = entry_sig.to_numpy(bool), exit_sig.to_numpy(bool)
    stop_pct, target_pct = exit_rule.get("stop_pct"), exit_rule.get("target_pct")
    trail_pct, hold_bars = exit_rule.get("trailing_pct"), exit_rule.get("hold_bars")
    cash, pos = 500.0, None
    want_in = want_out = False
    signal_day = None
    book = Book()

    def close_pos(i, raw, reason):
        nonlocal cash, pos
        fill = cost.sell(raw)
        cash += pos["qty"] * fill
        book.trades.append(
            Trade(pos["ts"], ts[i], pos["fill"], fill, pos["notional"], reason, symbol)
        )
        pos = None

    for i in range(len(df)):
        if day_trade and pos is not None and days[i] != pos["day"]:
            close_pos(i, o[i], "missing_session_close")
            want_out = False
        if pos is not None and want_out:
            close_pos(i, o[i], "rule")
        if pos is None and want_in and (not day_trade or signal_day == days[i]):
            notional = min(500.0, cash)
            if vol_target is not None:
                window = c[max(0, i - 21) : i]
                rets = window[1:] / window[:-1] - 1
                if len(rets) >= 2:
                    sd = float(np.std(rets, ddof=1))
                    if sd > 0:
                        notional *= min(1.0, vol_target / sd)
            fill = cost.buy(o[i])
            pos = {
                "ts": ts[i],
                "fill": fill,
                "qty": notional / fill,
                "notional": notional,
                "start": i,
                "peak": o[i],
                "day": days[i],
            }
            cash -= notional
        want_in = want_out = False
        if pos is not None:
            levels = []
            if stop_pct is not None:
                levels.append(pos["fill"] * (1 - stop_pct))
            if trail_pct is not None:
                levels.append(pos["peak"] * (1 - trail_pct))
            stop = max(levels) if levels else None
            target = pos["fill"] * (1 + target_pct) if target_pct is not None else None
            if stop is not None and o[i] <= stop:
                close_pos(i, o[i], "stop_gap")
            elif target is not None and o[i] >= target:
                close_pos(i, o[i], "target_gap")
            elif stop is not None and lo[i] <= stop:
                close_pos(i, stop, "stop")
            elif target is not None and h[i] >= target:
                close_pos(i, target, "target")
        if pos is not None:
            pos["peak"] = max(pos["peak"], h[i])
            held = i - pos["start"] + 1
            want_out = bool(xs[i]) or (hold_bars is not None and held >= hold_bars)
            if day_trade and ends is not None and ends[i]:
                close_pos(i, c[i], "session_close")
                want_out = False
        if pos is None and es[i]:
            want_in = True
            signal_day = days[i]
            if day_trade and hours is not None and (hours[i] >= 16 or ends[i]):
                want_in = False
        if i == len(df) - 1 and pos is not None:
            close_pos(i, c[i], "period_end")
        book.equity.append(cash + (pos["qty"] * c[i] if pos is not None else 0.0))
    return book


def run_single(
    strategy: dict,
    ticker: str,
    cost: CostModel | None = None,
    frames: dict | None = None,
):
    """Return {period: Book} for one frozen strategy on one ticker."""
    tf = strategy.get("timeframe", "daily")
    loader = {"daily": daily, "hourly": hourly, "5min": five_minute}[tf]
    df = frames[ticker] if frames else loader(ticker)
    context = None
    if strategy["entry"]["type"] == "relative_strength":
        context = {
            s: (frames[s] if frames else loader(s)) for s in strategy["universe"]
        }
    base = cost or CostModel(
        **{k: strategy["costs"][k] for k in ("round_trip_bps", "tick_per_side")},
        stress=strategy["costs"]["stress_multiplier"],
    )
    cm = base.for_ticker(ticker)
    es = entry_signal(df, strategy["entry"], context, ticker)
    xs = exit_signal(df, strategy["entry"], strategy["exit"], es)
    out = {}
    for p, idx in period_slices(df["day"].to_numpy()).items():
        part = df.iloc[idx]
        out[p] = simulate_single(
            part,
            es.iloc[idx],
            xs.iloc[idx],
            strategy["exit"],
            cm,
            day_trade=strategy["entry"]["type"] in {"day_trade", "open_reversal"},
            vol_target=strategy["entry"].get("size_vol_target"),
            symbol=ticker,
        )
    return out


def run_rotation(strategy: dict, cost: CostModel | None = None):
    """Shared cash, at most one of the universe held; switch at next open after leadership changes."""
    syms = strategy["universe"]
    frames = {s: daily(s) for s in syms}
    shared = frames[syms[0]].index
    for f in frames.values():
        shared = shared.intersection(f.index)
    frames = {s: f.loc[shared] for s, f in frames.items()}
    lb = strategy["entry"].get("lookback", 63)
    closes = pd.DataFrame({s: frames[s]["close"] for s in syms})
    mom = closes / closes.shift(lb) - 1
    choice = [
        None if not r.notna().any() or r.max() <= 0 else r.idxmax()
        for _, r in mom.iterrows()
    ]
    choice = pd.Series(choice, index=shared, dtype=object)
    base = cost or CostModel(stress=strategy["costs"]["stress_multiplier"])
    days = frames[syms[0]]["day"].to_numpy()
    out = {}
    for p, idx in period_slices(days).items():
        book, cash, pos, target = Book(), 500.0, None, None
        for j, i in enumerate(idx):
            t = shared[i]
            if pos is not None and target != pos["sym"]:
                bar = frames[pos["sym"]].iloc[i]
                fill = base.for_ticker(pos["sym"]).sell(bar["open"])
                cash += pos["qty"] * fill
                book.trades.append(
                    Trade(
                        pos["ts"],
                        t,
                        pos["fill"],
                        fill,
                        pos["notional"],
                        "rule",
                        pos["sym"],
                    )
                )
                pos = None
            if pos is None and target is not None:
                bar = frames[target].iloc[i]
                fill = base.for_ticker(target).buy(bar["open"])
                notional = min(500.0, cash)
                pos = {
                    "sym": target,
                    "ts": t,
                    "fill": fill,
                    "qty": notional / fill,
                    "notional": notional,
                }
                cash -= notional
            target = choice.iloc[i]
            if j == len(idx) - 1 and pos is not None:
                bar = frames[pos["sym"]].iloc[i]
                fill = base.for_ticker(pos["sym"]).sell(bar["close"])
                cash += pos["qty"] * fill
                book.trades.append(
                    Trade(
                        pos["ts"],
                        t,
                        pos["fill"],
                        fill,
                        pos["notional"],
                        "period_end",
                        pos["sym"],
                    )
                )
                pos = None
        out[p] = book
    return out


def run_basket(strategy: dict):
    """Equal thirds of MU/WDC/STX bought once per period; basket return = mean member return."""
    syms = ["MU", "WDC", "STX"]
    frames = {s: daily(s) for s in syms}
    shared = frames["MU"].index
    for f in frames.values():
        shared = shared.intersection(f.index)
    hold = {"type": "buy_hold"}
    members = {
        s: run_single({**strategy, "entry": hold}, s, frames={s: frames[s].loc[shared]})
        for s in syms
    }
    return {
        p: [float(np.mean([members[s][p].trades[0].net for s in syms]))]
        for p in PERIODS
    }, members
