# Codex CLI — Memory Chips backtest session

**Language:** Croatian or English OK. Write results to `reports/runs/codex_run.md`.

## Hard rules

1. **Read first:** `PRIOR_ART.md` and every file in `reports/gate/` (all FAIL; empty `approved_list.json`).
2. **Never** present gate-FAIL strategies as winners or trade recommendations.
3. **Critic PASS required** before any follow signal. Else stay idle (research only).
4. Use **local CSVs** in `data/ohlcv/` (Alpaca-sourced / trading-lab SIP copies). Do not invent prices.
5. Universe: MU, WDC, STX (+ AMAT, LRCX, KLAC, SMH context).
6. **Never** claim guaranteed profit. Backtests ≠ profit.
7. **Never** place brokerage orders.
8. Frozen hypothesis notional ≤ 500 USD, max 1 position.

## Task

- Inspect `strategies/frozen/mu_down5_hold10.md` and `scripts/backtest_swing.py`.
- Run or re-check swing candidates; cross-check against gate FAIL reasons.
- Write `reports/runs/codex_run.md` with metrics + explicit prior-art / FAIL labels. Research ranking only.

## Output

`reports/runs/codex_run.md` only. No emails, no orders.
