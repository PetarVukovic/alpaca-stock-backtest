# Alpaca Stock Backtest

An MIT-licensed Python starter for building stock research tools with Alpaca. Run the CLI against historical US equity data using your own Alpaca credentials, or reuse the data-fetching and simulation functions in your own research SaaS.

The repository implements a daily-bar CLI and a moving-average example. The SaaS components and MCP tools below are an integration design.

## Quick start

Use Python 3.11 or later and an IANA time-zone database. On Windows, install it with `python -m pip install tzdata`. Provide credentials through your shell or secret manager.

```sh
export APCA_API_KEY_ID="your-key-id"
export APCA_API_SECRET_KEY="your-secret-key"
python backtest.py AAPL MSFT --start 2020-01-01 --end 2024-12-31 \
  --feed iex --fast 20 --slow 50 --cost-bps 5
```

Pass one or more US equity tickers available from your Alpaca feed. Each ticker gets an independent simulation. Use `--feed sip` with the appropriate entitlement and `python backtest.py --help` for all options. Date bounds are inclusive New York session dates. Select a completed historical interval. The CLI prints JSON with return, maximum closing-equity drawdown, fill count, number of bars, actual first and last sessions, and whether the simulation ends with an open position.

## Architecture

| Layer | Implementation or suggested extension |
| --- | --- |
| Market data | `fetch_bars` requests Alpaca's historical REST stock bars, follows pagination and converts timestamps to New York session dates. It requests split-adjusted daily prices. |
| Data validation | `validate_bars` sorts sessions and rejects duplicate dates and invalid open or close prices. Production workers should also verify exchange-calendar coverage and identify halts and stale or incomplete bars. |
| Strategy and simulation | `simulate` takes validated bars and parameters and returns metrics. It works independently of the network, which makes it suitable for offline tests and job workers. |
| SaaS API and workers | A backend authenticates users, validates bounded requests and creates backtest jobs. A worker retrieves market data and runs the simulation. The backend returns job status and results to the dashboard. |
| MCP and AI | An optional copilot uses constrained tools to fetch market context or read a completed backtest. The Python engine calculates metrics and the copilot explains them with the relevant run ID and dates. |

### Building a SaaS around the CLI

1. Start with a backend route such as `POST /backtests`. Accept a strategy ID, symbols, feed, date range and cost model. Validate all fields and scope job IDs and results to the authenticated tenant.
2. Send the job to a worker. Retrieve credentials from a server-side secret store. If users bring their own Alpaca keys, encrypt them per tenant and exclude them from logs, browser responses and model context.
3. Record the data source, feed, adjustments, requested and actual coverage, strategy settings, cost assumptions and code revision with each run. If your data terms permit storing snapshots, record a checksum so you can reproduce a run from the same inputs.
4. Expose read-only results to the dashboard. If you add charts or trade attribution, extend the simulator to return an equity series and fill ledger. The current CLI returns summary metrics.
5. Apply per-tenant quotas, request timeouts and bounded retries for rate limits and transient failures. Keep caches scoped to relevant data entitlements. Review your Alpaca plan and data terms before displaying, caching or redistributing quotes to SaaS users.

### Adding Alpaca MCP

The CLI uses the [Alpaca historical bars API](https://docs.alpaca.markets/us/reference/stockbars) directly. Users can run backtests without an MCP host or an LLM. To add a copilot, connect your MCP host to the [official Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server) using its current setup instructions. Configure `ALPACA_TOOLSETS=stock-data` and verify the enabled tools against a read-only allowlist before exposing them to the model.

Use the Alpaca tools for contextual questions about bars or snapshots. Expose your own read-only tool such as `get_backtest_result(run_id)` if you want the assistant to explain saved results. Enforce tenant authorization in the backend for every lookup. Treat tool output and external text as untrusted input. Keep both the CLI and copilot path free of brokerage order operations.

## Backtesting methodology

### Implemented example

- **Decision and execution.** After the daily close, compare simple moving averages over the last 20 and 50 closes by default. When the fast average exceeds the slow average, the strategy targets a long position. Otherwise it targets cash. A change fills at the next available bar's open. A signal on the final bar has no subsequent fill.
- **Sizing and costs.** Each symbol starts with one unit of simulated cash. A long entry uses available cash and allows fractional shares. The cost parameter applies on each buy and sell. Five basis points per side is approximately ten basis points for a round trip at unchanged prices. The example models a fixed proportional cost.
- **Valuation.** Holdings are marked at each close, including any open position on the last day. Maximum drawdown is calculated from closing equity and can miss intraday losses. The results exclude dividends, taxes and financing.
- **Coverage.** A missing day can shift a fill to the next available bar. Review feed coverage, corporate actions, symbol changes and delisted names before drawing conclusions, especially when comparing a historical stock universe.

### Extending the research workflow

1. **Freeze the rules.** Record the signal, execution timing, universe, sizing, cost model, benchmark, data policy and evaluation metric before testing.
2. **Use chronological validation.** Choose parameters on earlier data, then score them on later windows. In rolling walk-forward validation the training window stays fixed in length. In expanding walk-forward validation it grows. Carry historical bars into each window for indicator warm-up and clearly define how positions and overlapping observations are handled at boundaries.
3. **Stress the results.** Compare against a benchmark on the same dates and under comparable assumptions. Raise costs, perturb parameters, and break down results by symbol and regime. Record each trial so the number of attempts is visible when interpreting the best result.
4. **Reserve a final holdout.** Keep its dates out of tuning and inspect it after strategy choices are fixed. Report return, drawdown, turnover, trade count and exposure alongside any risk-adjusted metric. Add spread, slippage, liquidity and sizing constraints when the intended use calls for them.

Walk-forward orchestration, benchmarks and holdout reporting are extensions to implement on top of the example simulator.

## Contributing and license

See [AGENTS.md](AGENTS.md) for development and testing conventions. Use synthetic fixtures in contributions and keep keys, downloaded market data and private research outputs local. The source code is MIT-licensed. Alpaca data remains subject to the applicable account and market-data terms.
