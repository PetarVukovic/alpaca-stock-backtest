"""C13C rule (``strategies/frozen/2026-10-05_C13C_TREND_DIP5_TRAIL.json``), computed from daily bars.

Mirrors ``lab/strategies/registry.py`` (``dip_in_trend``) and the trailing exit in ``lab/engine.py``:
signal on the completed daily bar, peak tracked from the fill, stop at 90 % of the peak, never lowered.
Pure functions only; the broker and the database live elsewhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.backend.money import cents, decimal

STRATEGY_ID = "2026-10-05_C13C_TREND_DIP5_TRAIL"
TICKERS: tuple[str, ...] = ("MU", "WDC", "STX")  # also the priority order
TREND_WINDOW = 200
DIP_BARS = 5
DIP_PCT = 0.05
TRAILING_PCT = 0.10
MIN_BARS = max(TREND_WINDOW, DIP_BARS + 1)

REASON_TOO_FEW = "premalo podataka"


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class SignalResult:
    ticker: str
    date: str
    close: float
    sma200: float
    drop5_pct: float
    signal: bool
    reason: str


def evaluate(ticker: str, bars: Sequence[Bar]) -> SignalResult:
    """Signal on the last completed bar: close above SMA200 and down 5 % or more over 5 bars.

    Fewer than ``MIN_BARS`` bars gives no signal with the reason "premalo podataka"; ``sma200`` and
    ``drop5_pct`` are then 0.
    """
    symbol = ticker.upper()
    if len(bars) < MIN_BARS:
        last_date = bars[-1].date if bars else ""
        last_close = bars[-1].close if bars else 0.0
        return SignalResult(symbol, last_date, last_close, 0.0, 0.0, False, REASON_TOO_FEW)
    last = bars[-1]
    window = bars[-TREND_WINDOW:]
    sma200 = sum(bar.close for bar in window) / TREND_WINDOW
    reference = bars[-1 - DIP_BARS].close
    drop5 = last.close / reference - 1.0 if reference else 0.0
    above = last.close > sma200
    dipped = drop5 <= -DIP_PCT
    drop_text = f"{drop5 * 100:+.1f} %".replace(".", ",")
    if above and dipped:
        reason = f"Cijena je iznad prosjeka 200 dana i pala je {drop_text} u 5 dana. Pravilo daje signal za prvo otvaranje nakon tog završenog dana."
    elif not above:
        reason = "Cijena je ispod prosjeka 200 dana, pa pravilo ne kupuje ni kad padne."
    else:
        reason = f"Pad u 5 dana je {drop_text}, treba -5 % ili više."
    return SignalResult(
        ticker=symbol,
        date=last.date,
        close=last.close,
        sma200=round(sma200, 4),
        drop5_pct=round(drop5 * 100.0, 3),
        signal=above and dipped,
        reason=reason,
    )


def next_peak(peak: float, bar: Bar) -> float:
    return max(float(peak), float(bar.high))


def stop_for(peak: float) -> float:
    return float(cents(decimal(peak) * (decimal(1) - decimal(TRAILING_PCT))))


def initial_peak(fill_price: float, entry_bar_high: float | None) -> float:
    if entry_bar_high is None:
        return float(fill_price)
    return max(float(fill_price), float(entry_bar_high))


def pick_candidate(results: Sequence[SignalResult]) -> SignalResult | None:
    """First signalling ticker in ``TICKERS`` order (MU, then WDC, then STX)."""
    by_ticker = {item.ticker.upper(): item for item in results if item.signal}
    for ticker in TICKERS:
        if ticker in by_ticker:
            return by_ticker[ticker]
    return None
