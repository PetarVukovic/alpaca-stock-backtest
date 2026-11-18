# Claude Code — Memory Chips backtest session

**Language:** odgovaraj na hrvatskom ili engleskom (mješovito OK). Piši rezultat u `reports/runs/claude_run.md`.

## Hard rules

1. **Prvo pročitaj** `PRIOR_ART.md` i **sve** datoteke u `reports/gate/` (svi VERDICT = FAIL; `approved_list.json` prazan).
2. **Nikad** ne prezentiraj FAIL strategije kao pobjednike / KUPI / follow.
3. **Critic PASS** obavezan prije bilo kakvog follow signala. Bez PASS → idle / research only.
4. Koristi **lokalne** CSV-ove u `data/ohlcv/` (Alpaca/trading-lab sourced). Ne izmišljaj cijene.
5. Univerzum: MU, WDC, STX (+ kontekst AMAT, LRCX, KLAC, SMH).
6. **NE** tvrdi zajamčeni profit. Backtest ≠ profit.
7. **NE** postavljaj brokerage ordere (paper ili live).
8. Max notional istraživanja ≤ 500 USD, max 1 pozicija ako modeliraš frozen hipotezu.

## Task

- Pregledaj frozen hipotezu `strategies/frozen/mu_down5_hold10.md`.
- Pokreni ili reproduciraj swing screen (dip −5/−7/−10% hold 10d; pullback −15% od 20d high).
- Usporedi s gate FAIL razlozima (sample size, WF, regime).
- U `reports/runs/claude_run.md` navedi: što si testirao, n, win%, mean, max DD, i jasno **FAIL/prior-art** oznake. Top liste samo kao research ranking uz ogradu.

## Output

Write `reports/runs/claude_run.md` only. No emails, no orders.
