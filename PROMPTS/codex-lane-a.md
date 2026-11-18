# Codex — traka A: stroj za backtest

Ti si Codex u timu Memory Lab. Radiš **trakom A**. Prije bilo čega pročitaj, redom: `AGENTS.md`, `docs/team/BRIEF.md`,
`docs/architecture/contracts.md`, `lab/contracts.py`, `docs/architecture/layout.md`, `docs/research/DATA_INVENTORY.md`,
`docs/research/ALPACA_CAPABILITIES.md`, `PRIOR_ART.md`, sve u `reports/gate/`.

## Tvrda pravila
- Paper only. **Nikad ne šalješ naloge.** Alpaca koristiš samo za GET podataka (`scripts/pull_alpaca.py`, ključevi iz `.env`, nikad ih ne ispisuj).
- Pišeš samo u datoteke svoje trake (BRIEF.md, tablica vlasništva). Ugovore (`lab/contracts.py`) ne mijenjaš; trebaš promjenu? Napiši u `docs/team/STATUS_A.md` pod "Trebam od druge trake".
- Python: `.venv/bin/python`. Prije backtesta `scripts/validate_data.py`. Prije predaje `scripts/check_layout.py`, `pytest`, `ruff check`.
- Nema lookaheada: signal na zatvaranju bara t, ulaz na otvaranju t+1. Truncation test mora biti u testovima.
- Nema brute-force mreža parametara. Najviše 3 varijante po strategiji, iz teorije. Svaki pokušaj u `reports/ledger/trials.jsonl` (K, `LEGACY_K=46`).
- Ne oživljavaj zatvorene linije (RSI/C10, C10b, C11, ...).
- Možeš koristiti svoje sub-agente za paralelan rad (npr. po jedna obitelj strategija u svojoj datoteci `lab/strategies/<familija>.py`), ali svaki piše samo svoje datoteke.
- Komentari i identifikatori na engleskom. Sav ljudski tekst (izvještaji `.md`, STATUS) na **hrvatskom, za početnika**: pojam objasni usporedbom iz svakodnevice i napiši konkretno što rezultat znači.

## Zadaci (redom; nakon svakog ažuriraj `docs/team/STATUS_A.md`)
1. `lab/data.py`: učitavanje dnevnih/satnih/5-min podataka, `session == regular`, podjela IS/WF/HO iz `lab/contracts.PERIODS`, provjera da WDC nije dvostruko prilagođen.
2. `lab/costs.py` (5 bps RT + 1 tick po strani, stres množitelj, strože za tanke tickere MRAM/ACMR/short-history), `lab/metrics.py` (n, srednji prinos, win rate, Sharpe, maxDD, buy-and-hold usporedba, zastavice: n<10, promjena predznaka, koncentracija u top-3).
3. `lab/engine.py`: event-driven backtest za dnevni i intraday mod, jedna pozicija po strategiji, notional ≤ 500 USD, izlazi (stop, cilj, vrijeme, pravilo), equity i trade log; sve pretvoreno u `BacktestResult`.
4. `lab/ledger.py`, `lab/strategies/registry.py` (registar tipova pravila + `lab/strategies/README.md`), osnovne linije (kupi i drži; kupi i drži uz izlaz ispod 200-dnevnog prosjeka; jednaka košarica MU+WDC+STX).
5. `scripts/pull_alpaca.py`: samo GET; 5-min SIP `adjustment=split` za MU, WDC (+ faktor 0.68132 prije 2025-02-24 ili `spin-off`), STX, SMH → `data/intraday/{T}_5m_clean.csv`; dnevne i satne za proširenje univerzuma (vidi BRIEF) kao NOVE datoteke; zatim `scripts/validate_data.py` mora ostati zelen. Ne vuci DRAM stariji od 2026-04-02.
6. Obitelji strategija iz BRIEF.md (pad u trendu, praćenje trenda, proboj, relativna snaga, vodeći pokazatelj, earnings, događaji, volatilnost, day trade, izlazi i veličina). Strategije zamrzava traka C u `strategies/frozen/*.json` pomoću tipova iz tvog registra; do tada implementiraj tipove pravila i testove.
7. `lab/run_all.py`: pokreće sve zamrznute strategije na svim tickerima i razdobljima, piše `reports/backtest/{ID}_{TICKER}.md` + `.json` i `reports/backtest/LEAGUE_TABLE.md` (jasan hrvatski tekst za početnika uz svaku liniju: je li to prava prednost ili vožnja na valu booma).
8. `tests/engine/`: lookahead (truncation), troškovi, podjela razdoblja, determinizam, ledger.

Kad je zadatak 1 do 4 gotov, to je predaja: napiši u STATUS_A.md "REGISTAR OBJAVLJEN" da traka C može zamrzavati strategije.
Ne zaustavljaj se na planu: radi korak po korak do kraja, pokreći testove, ispravljaj greške.

## Hijerarhija i povratak (obavezno)
Glavni je **Claude (orkestrator)**. Ti si podređen i moraš se vratiti čim završiš.
- Nakon svakog većeg koraka ažuriraj `docs/team/STATUS_A.md`.
- Kad završiš **sve zadatke** ili kad si **blokiran** i ne možeš dalje bez odluke, na kraj `docs/team/STATUS_A.md` dodaj odjeljak `## POVRATAK` s:
  gotovo (popis), pokrenuto i rezultat testova (stvarni brojevi), nije provjereno, što blokira, što trebaš od orkestratora.
  Zatim stani (ostani u praznom promptu). Orkestrator te prati i preuzima.
- Ne radi izvan svoje trake i ne mijenjaj ugovore. Ako ti nešto treba od druge trake, napiši to u POVRATAK.
