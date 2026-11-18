# Podaci

Ovaj dokument objašnjava **što** se koristi i **zašto**. Detaljne bilješke po izvoru su u
`data/ohlcv/DATA_NOTES.txt` i `data/hourly/DATA_NOTES.txt`.

## Što se smije koristiti

| Vrsta | Datoteke | Napomena |
|-------|----------|----------|
| Dnevne cijene | `data/ohlcv/{TICKER}_1d.csv` | OHLCV + vwap + trades, split-adjusted |
| Satne cijene | `data/hourly/{TICKER}_1h_clean.csv` | SIP, `adjustment=split` |
| Vijesti | `data/news/archive/*.jsonl` | bez punog teksta |
| Događaji | `data/news/events_calendar.csv`, `MU_earnings_dates.csv` | filtriraj po `us_reaction_date` |

**`.parquet` su zastarjeli i ne koriste se.** Stari parquet i izvorne kopije iz trading-laba su u
`data/archive/from_trading_lab/` samo kao dokaz porijekla, nikad ulaz u test.

## Univerzum

| Uloga | Simboli |
|-------|---------|
| Primary | MU, WDC, STX |
| Context | SIMO, RMBS, AMAT, LRCX, KLAC, SMH |
| Side-check (tanki, viši trošak) | MRAM, ACMR |
| Samo praćenje (kratka povijest) | DRAM (Roundhill Memory ETF, od 2026-04-02), SKHY (SK hynix ADR, od 2026-07-10), SNDK (od 2025-02-13) |

Dnevna povijest za primary i context je 2016-01-04 → 2026-10-05 (2704 dana).

## WDC i SanDisk spin-off

Dana 2025-02-24 WDC je izdvojio SanDisk (SNDK). Sirova serija tada pokazuje lažnih −28,7 % u jednom danu.

- Cijene **prije 2025-02-24** množe se faktorom **0.68132** (Alpaca SIP `spin-off` adjustment: 46.81 / 68.705).
- Volumen i broj trgovina se ne diraju.
- Nakon prilagodbe pomak 2025-02-24 je +4,7 %, najgori WDC dan je −20,4 % (2020-03-16), a najveći pad je −72,6 %.
- **Ne prilagođavati dvaput.**

> **Ispravljeno 2026-10-05:** lokalni `WDC_1d.csv` bio je neprilagođen (2025-02-24 pokazivao je lažnih −28,7 %).
> Primijenjen je dokumentirani faktor 0.68132 (uz Petrovo odobrenje), sirova kopija je u
> `WDC_1d.raw_unadjusted_spinoff.csv`. Nakon ispravka pomak je +4,7 %, najgori dan −20,4 %, 115 dana ≤ −5 %.
> Faktor se **ne primjenjuje ponovno**.

## Satni podaci

- Feed je SIP, `adjustment=split` (ne `all`: `all` je ranije napravio lažne skokove i dvostruku prilagodbu WDC-a).
- Stupac `session` određuje se po **New York** vremenu: `regular`, `open_mixed`, `extended`. Za testove `session == regular`.
- `volume_ok=False` znači da se volumen ne koristi (IEX redovi).
- Poluskraćeni dani (dan nakon Thanksgivinga, Badnjak) nisu posebno označeni.

## Validacija prije svakog backtesta

```bash
python scripts/validate_data.py
```

Piše `reports/data/DATA_CHECK.md`. **Exit code 1 znači: nema backtesta.** Nove jednodnevne promjene veće od
25 % moraju se provjeriti i dodati u `KNOWN_REAL` s razlogom. (Skripta trenutno ne postoji lokalno, vidi
poznate praznine u [overview.md](overview.md).)

## Vijesti

Pogledaj [`docs/news/NEWS_PIPELINE.md`](../news/NEWS_PIPELINE.md). Ukratko: vijest nakon 22:00 po zagrebačkom
vremenu računa se kao reakcija sljedećeg američkog dana (`us_reaction_date`), a **tip događaja određuje se
prije testa, ne poslije**. Izmišljanje sentimenta s društvenih mreža je zabranjeno.

## Dovršenost dnevnih svijeća (provjera 2026-10-06)

Validator odbija posljednji dnevni redak ako je datoteka spremljena prije konzervativnog zatvaranja u 16:00 New York. Kasniji timestamp kopije nije pozitivan dokaz dovršenosti. Za audit na dokazanom ranijem presjeku koristi `scripts/validate_data.py --through YYYY-MM-DD`; isti datum proslijedi `lab.run_all --through` i loaderu. Glavni C21/C22 rezultati koriste 2026-10-02. Bez presjeka trenutačni lokalni skup ispravno pada zbog nepotpunih zadnjih redaka. Izvorne cijene nisu prepisivane. Rana zatvaranja zahtijevaju stvarni kalendar; sadašnji kriterij je namjerno konzervativan.
