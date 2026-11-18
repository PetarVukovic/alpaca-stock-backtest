# Repository layout

| Directory | Contents |
| --- | --- |
| `lab/` | Engine, shared contracts, strategy registry, costs, metrics, research modules and Critic. |
| `scripts/` | Market-data ingestion, validation, research tools and TradingView studies. |
| `strategies/frozen/` | Versioned strategy specifications. Use a new ID for changed rules. |
| `tests/` | Synthetic tests and optional historical parity checks. |
| `docs/`, `PROMPTS/` | Architecture, research documentation and reusable research prompts. Some historical notes describe the original lab's environment. |
| `data/` | User-provided daily, hourly and intraday bars, plus event and research inputs. |
| `reports/` | Locally generated validation reports, trial ledger, backtests and Critic evidence. |
| `gate/` | Historical location for gate artifacts. New verdicts live under `reports/gate/`. |
