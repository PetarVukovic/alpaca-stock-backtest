"""Offline C13C account diagnostics with explicit order fees and fractional sizing."""
import math
import numpy as np
import pandas as pd
from app.backend.strategies.c13c import stop_for
from lab.research.memory_swing import entry_signals


def replay(frames, dates, capital, fractional=False, stress=1, exit_bps=0, passive=False):
    signals = {s: entry_signals(f) for s, f in frames.items()}
    cash, position, pending = float(capital), None, None
    trades, events, values, stops, skipped = [], [], [], [], []
    fees_total, slip_total, participation = 0., 0., 0.
    def candidate(day):
        return next((s for s in frames if bool(signals[s].get(day, False))), None)
    first = dates[0]
    previous = sorted({d for f in frames.values() for d in f.index if d < first})
    if previous and not passive:
        pending = candidate(previous[-1])
    if passive:
        assert len(frames) == 1
        pending = next(iter(frames))
    for i, day in enumerate(dates):
        if pending and position is None:
            s = pending
            if day in frames[s].index:
                bar = frames[s].loc[day]
                multiplier = stress * (3 if s in ('SNDK', 'MRAM') else 1)
                price = float(bar.open) + .01 * multiplier
                budget = cash * .95
                # Reserve both the proportional fee and minimum order fee.
                q = min(budget/(price*(1+.00025*multiplier)), (budget-multiplier)/price)
                q = max(0, math.floor(q*1e6)/1e6 if fractional else math.floor(q))
                if q > 0:
                    fee = max(1., q*price*.00025)*multiplier
                    assert q*price+fee <= cash+1e-8 and bar.volume > 0
                    participation = max(participation, q/float(bar.volume))
                    cash -= q*price+fee
                    fees_total += fee; slip_total += q*.01*multiplier
                    position = dict(ticker=s, entry_date=str(day.date()), entry_price=price,
                                    raw_entry=float(bar.open), quantity=q, entry_fee=fee,
                                    peak=price+fee/q, entry_i=i)
                    events.append(dict(date=str(day.date()), side='buy', ticker=s, qty=q, price=price, fee=fee, cash=cash))
                else:
                    skipped.append(dict(date=str(day.date()), ticker=s, cash=cash))
            pending = None
        if position:
            s = position['ticker']; bar = frames[s].loc[day]
            multiplier = stress*(3 if s in ('SNDK','MRAM') else 1)
            stop = stop_for(position['peak'])
            stops.append(dict(date=str(day.date()), entry_date=position['entry_date'], ticker=s, stop=stop))
            if not passive and float(bar.low) <= stop:
                raw = min(float(bar.open), stop)
                assert float(bar.low)-1e-8 <= raw <= float(bar.high)+1e-8 and bar.volume > 0
                price = max(0,raw-.01*multiplier-raw*exit_bps/10000)
                q=position['quantity']; fee=max(1.,q*price*.00025)*multiplier
                cash += q*price-fee; fees_total += fee; slip_total += q*(raw-price)
                participation=max(participation,q/float(bar.volume))
                pnl=q*(price-position['entry_price'])-fee-position['entry_fee']
                trades.append(position|dict(exit_date=str(day.date()),exit_price=price,raw_exit=raw,exit_fee=fee,
                    pnl_usd=pnl,return_pct=100*pnl/(q*position['entry_price']+position['entry_fee']),
                    sessions_held=i-position['entry_i']+1,reason='gap_stop' if float(bar.open)<stop else 'stop'))
                events.append(dict(date=str(day.date()),side='sell',ticker=s,qty=q,price=price,fee=fee,cash=cash))
                position=None
            elif not passive:
                position['peak']=max(position['peak'],float(bar.high))
        marked=position['quantity']*float(frames[position['ticker']].loc[day,'close']) if position else 0.
        values.append(cash+marked)
        assert cash >= -1e-7
        if position is None and not passive:
            pending=candidate(day)
    return dict(curve=pd.Series(values,index=dates),trades=trades,events=events,stops=stops,
                skipped=skipped,open_position=position,fees_usd=fees_total,slippage_usd=slip_total,
                max_volume_fraction=participation)
