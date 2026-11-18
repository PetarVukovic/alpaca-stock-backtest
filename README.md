# Alpaca Stock Backtest

A small Python CLI for backtesting US equities with your own Alpaca Market Data account. Pass one or more tickers supported by your feed. Each ticker gets an independent simulation and a JSON result. The tool calls only the historical market-data endpoint.

## Quick start

Use Python 3.11 or newer with an IANA time zone database. On Windows, install the database with `python -m pip install tzdata`.

Set your credentials in your shell. These are placeholder values.

```sh
export APCA_API_KEY_ID="your-key-id"
export APCA_API_SECRET_KEY="your-secret-key"
python backtest.py AAPL MSFT --start 2020-01-01 --end 2024-12-31
```

Use `python backtest.py --help` for options. Dates are inclusive New York session dates. The default feed is IEX. Use `--feed sip` if your account has SIP access. See the [Alpaca historical bars documentation](https://docs.alpaca.markets/us/reference/stockbars).

## Simulation

The example holds a long position when the fast simple moving average is above the slow one. It observes the signal at the close and trades at the next available open. Defaults are 20 and 50 bars with a simulated cost of 5 basis points per fill. A position uses all available simulated cash and allows fractional shares.

Daily prices are split-adjusted. The results exclude dividends, taxes and financing. A position still open at the end is marked at the final close. Drawdown uses daily closing equity. Review feed coverage and missing sessions before using results for research. The example is a single-period simulation. For strategy selection, freeze rules before evaluation, then use time-ordered out-of-sample splits, cost stress and an untouched holdout.

## License

MIT. Alpaca data is fetched by each user under their own account terms.
