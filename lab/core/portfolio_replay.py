"""Single-capital C13C replay matching the app's priority, whole shares and caps.

This is an execution-parity illustration, not a new strategy trial or Critic verdict.
Daily OHLC cannot reproduce the exact 09:31 fill; next-open + disclosed costs is the proxy.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

from app.backend.money import decimal, text, ZERO
from app.backend.strategies.c13c import Bar, TICKERS, STRATEGY_ID, evaluate, pick_candidate, stop_for


def load_series(root: Path):
    series, hashes = {}, {}
    for symbol in TICKERS:
        path = root / 'data' / 'ohlcv' / f'{symbol}_1d.csv'
        raw = path.read_bytes(); hashes[symbol] = hashlib.sha256(raw).hexdigest()
        rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
        bars, previous = [], ''
        for row in rows:
            day = (row.get('date') or row.get('timestamp') or '')[:10]
            date.fromisoformat(day)
            values = [float(row.get(k, row.get(k.capitalize(), 'nan'))) for k in ('open','high','low','close')]
            if day <= previous or not all(math.isfinite(v) and v > 0 for v in values):
                raise ValueError(f'{symbol}: nevaljan redoslijed ili cijena.')
            o,h,l,c = values
            if h < max(o,c) or l > min(o,c) or h < l: raise ValueError(f'{symbol}: nevaljan OHLC.')
            bars.append(Bar(day,o,h,l,c)); previous = day
        series[symbol] = bars
    return series, hashes


def simulate_portfolio(series, start: str, end: str, initial_cash='100000', qty=1, cap='1200', exposure='2000', daily_loss='250'):
    capital, cap, exposure, daily_loss = map(decimal, (initial_cash, cap, exposure, daily_loss))
    if isinstance(qty, bool) or capital <= 0 or qty < 1 or qty > 100 or int(qty) != qty or cap <= 0 or cap > 1200 or exposure <= 0 or daily_loss <= 0:
        raise ValueError('Nevaljan kapital, količina ili granica.')
    if date.fromisoformat(start) > date.fromisoformat(end): raise ValueError('Nevaljano razdoblje.')
    # Validate callers supplying bars directly as strictly as the CSV loader. Ignore
    # future observations entirely so a prefix run cannot depend on future data.
    series = {symbol: [bar for bar in series[symbol] if bar.date <= end] for symbol in TICKERS}
    for symbol, bars in series.items():
        previous = ''
        for bar in bars:
            date.fromisoformat(bar.date)
            values = (bar.open, bar.high, bar.low, bar.close)
            if bar.date <= previous or not all(math.isfinite(value) and value > 0 for value in values):
                raise ValueError(f'{symbol}: nevaljan redoslijed ili cijena.')
            if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
                raise ValueError(f'{symbol}: nevaljan OHLC.')
            previous = bar.date
    by = {s:{b.date:(i,b) for i,b in enumerate(series[s])} for s in TICKERS}
    union = sorted(set().union(*(set(v) for v in by.values())))
    days = [d for d in union if start <= d <= end]
    if not days:
        raise ValueError('Nema dnevnih podataka u odabranom razdoblju.')
    if any(any(d not in by[s] for s in TICKERS) for d in days):
        raise ValueError('Nedostaje dnevna cijena jedne od tri dionice; simulacija je blokirana.')
    cash, peak_equity, worst = capital, capital, ZERO
    position = None
    trades, curve, skipped = [], [], []
    pending = None
    # Start flat, with signals computed only from observations before the first entry day.
    if days:
        previous_days = [d for d in union if d < days[0]]
        if previous_days and all(previous_days[-1] in by[s] for s in TICKERS):
            previous = previous_days[-1]
            candidate = pick_candidate([evaluate(s,series[s][:by[s][previous][0]+1]) for s in TICKERS])
            pending = candidate.ticker if candidate else None
    spread = decimal('.00025')  # 5bps RT / 2
    tick = decimal('.01')
    for day in days:
        if pending and position is None:
            b = by[pending][day][1]
            price = decimal(b.open) * (1 + spread) + tick
            notional = price * qty
            if notional <= min(cash, cap, exposure):
                cash -= notional
                position = {'ticker':pending,'entry_date':day,'qty':qty,'entry_price':price,'peak':float(price),'stop':stop_for(float(price))}
            else:
                skipped.append({'date':day,'ticker':pending,'reason':'Kupnja prelazi gotovinu, iznos naloga ili ukupnu izloženost.'})
            pending = None
        if position:
            b = by[position['ticker']][day][1]
            old_stop = decimal(position['stop'])
            if decimal(b.low) <= old_stop:
                raw_exit = min(decimal(b.open),old_stop)
                exit_price = max(ZERO, raw_exit * (1 - spread) - tick)
                cash += exit_price * qty
                trades.append({'ticker':position['ticker'],'entry_date':position['entry_date'],'exit_date':day,'qty':qty,'entry_price':text(position['entry_price']),'exit_price':text(exit_price),'pnl_usd':text((exit_price-position['entry_price'])*qty),'reason':'stop_gap' if decimal(b.open)<old_stop else 'stop'})
                position = None
            else:
                position['peak'] = max(position['peak'],b.high)
                position['stop'] = max(position['stop'],stop_for(position['peak']))
        equity = cash + (decimal(by[position['ticker']][day][1].close) * qty if position else ZERO)
        peak_equity = max(peak_equity,equity); worst = min(worst,equity/peak_equity-1)
        curve.append({'date':day,'equity_usd':text(equity),'cash_usd':text(cash),'ticker':position['ticker'] if position else None})
        if position is None:
            candidate = pick_candidate([evaluate(s,series[s][:by[s][day][0]+1]) for s in TICKERS])
            pending = candidate.ticker if candidate else None
    final = decimal(curve[-1]['equity_usd']) if curve else capital
    return {'strategy_id':STRATEGY_ID,'start':start,'end':end,'initial_cash_usd':text(capital),'final_equity_usd':text(final),'return_pct':text((final/capital-1)*100),'max_drawdown_pct':text(worst*100),
        'qty':qty,'cap_usd':text(cap),'max_exposure_usd':text(exposure),'daily_loss_limit_usd':text(daily_loss),'trades':trades,'curve':curve,'skipped':skipped,
        'open_position':{**position,'entry_price':text(position['entry_price'])} if position else None,
        'assumptions':['Početak s gotovinom, bez otvorene pozicije; raniji podaci služe samo zagrijavanju pokazatelja.', 'Prioritet MU, WDC, STX; jedna pozicija; cijeli broj dionica i iste granice kao aplikacija.', 'Izvršenje na sljedećem otvaranju je aproksimacija kupnje aplikacije nakon 60 sekundi. Trošak 5 bps RT + 1 cent po strani.', 'Stop iz prethodne večeri, početna zaštita na ulazu; novi dnevni vrh vrijedi tek za sljedeći dan.', 'Nema ponovne kupnje isti dan nakon izlaza. Dnevni limit zato ne mijenja rezultate ove jednopozicijske simulacije.', 'Bez ručnih intervencija, prekida veze i latencije. Ovo nije stvarni paper rezultat niti Critic PASS.']}


def replay(root, start, end, initial_cash, settings):
    series, hashes = load_series(root)
    result = simulate_portfolio(series,start,end,initial_cash,int(settings['qty_shares']),settings['c13c_max_notional_usd'],settings['max_exposure_usd'],settings['daily_loss_limit_usd'])
    config = {k:settings[k] for k in ('qty_shares','c13c_max_notional_usd','max_exposure_usd','daily_loss_limit_usd')}
    result['fingerprint'] = hashlib.sha256(json.dumps({'data':hashes,'settings':config,'start':start,'end':end,'capital':initial_cash,'strategy':STRATEGY_ID,'model':'daily-open-costs-v2', 'source_hashes':{name:hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in ('portfolio_replay.py', 'strategies/c13c.py', 'money.py')}},sort_keys=True).encode()).hexdigest()
    result['data_hashes'] = hashes
    return result
