# Inventar podataka

Generirano 2026-10-05T22:45:39+02:00 skriptom `scripts/data_inventory.py` (samo čitanje).

Što lab **stvarno ima** lokalno. Što Alpaca nudi povrh toga: [ALPACA_CAPABILITIES.md](ALPACA_CAPABILITIES.md).

## Dnevne cijene (`data/ohlcv/*_1d.csv`)

| Dionica | Uloga | Dana | Od | Do | Prvo zatvaranje | Zadnje | Rast | Dnevno kolebanje (god.) | Najveći pad | Prosj. dnevni volumen (zadnjih 250 d) |
|---------|-------|------|----|----|-----------------|--------|------|-------------------------|-------------|---------------------------------------|
| MU | primary | 2704 | 2016-01-04 | 2026-10-05 | 14.33 | 1067.05 | ×74.5 | 52% | -58% | 37,890,897 |
| WDC | primary | 2704 | 2016-01-04 | 2026-10-05 | 41.15 | 442.52 | ×10.8 | 51% | -73% | 8,625,831 |
| STX | primary | 2704 | 2016-01-04 | 2026-10-05 | 36.27 | 892.51 | ×24.6 | 45% | -58% | 4,346,295 |
| SMH | context (ETF) | 2704 | 2016-01-04 | 2026-10-05 | 26.36 | 631.06 | ×23.9 | 33% | -45% | 8,884,072 |
| AMAT | context | 2704 | 2016-01-04 | 2026-10-05 | 18.47 | 536.54 | ×29.0 | 44% | -55% | 7,784,927 |
| LRCX | context | 2704 | 2016-01-04 | 2026-10-05 | 7.77 | 344.40 | ×44.3 | 46% | -57% | 10,792,697 |
| KLAC | context | 2704 | 2016-01-04 | 2026-10-05 | 6.87 | 203.69 | ×29.7 | 42% | -45% | 10,854,746 |
| SIMO | context | 2704 | 2016-01-04 | 2026-10-05 | 30.92 | 281.68 | ×9.1 | 47% | -59% | 759,275 |
| RMBS | context | 2704 | 2016-01-04 | 2026-10-05 | 11.59 | 110.08 | ×9.5 | 47% | -53% | 2,400,939 |
| MRAM | side-check | 2511 | 2016-10-07 | 2026-10-05 | 8.02 | 18.07 | ×2.3 | 79% | -91% | 1,399,299 |
| ACMR | side-check | 2240 | 2017-11-03 | 2026-10-05 | 2.02 | 76.39 | ×37.9 | 84% | -87% | 1,346,397 |
| SNDK | watch only | 412 | 2025-02-13 | 2026-10-05 | 36.00 | 1712.53 | ×47.6 | 105% | -56% | 14,288,527 |
| DRAM | watch only (ETF) | 128 | 2026-04-02 | 2026-10-05 | 27.76 | 61.67 | ×2.2 | 88% | -44% | 42,492,151 |
| SKHY | watch only (ADR) | 61 | 2026-07-10 | 2026-10-05 | 168.01 | 194.72 | ×1.2 | 106% | -35% | 29,041,461 |

Napomena: za dionice s kratkom poviješću (SNDK, DRAM, SKHY) i za MRAM/ACMR (kasniji početak) rast nije usporediv s ostalima. WDC je prilagođen za SanDisk spin-off (×0.68132 prije 2025-02-24).

## Satne cijene (`data/hourly/*_1h_clean.csv`)

| Dionica | Satnih barova | Od toga regular | Od | Do |
|---------|---------------|-----------------|----|----|
| MU | 40,870 | 16,210 | 2016-01-04 | 2026-10-05 |
| WDC | 32,564 | 16,192 | 2016-01-04 | 2026-10-05 |
| STX | 28,594 | 16,186 | 2016-01-04 | 2026-10-05 |
| SIMO | 23,458 | 16,169 | 2016-01-04 | 2026-10-05 |
| RMBS | 25,195 | 16,174 | 2016-01-04 | 2026-10-05 |
| MRAM | 22,187 | 14,944 | 2016-10-07 | 2026-10-05 |
| ACMR | 22,610 | 13,272 | 2017-11-03 | 2026-10-05 |
| DRAM | 2,038 | 767 | 2026-04-02 | 2026-10-05 |
| SKHY | 964 | 364 | 2026-07-10 | 2026-10-05 |

Satni podaci postoje za 9 dionica (nema ih za SMH, AMAT, LRCX, KLAC, SNDK). Feed je SIP, `adjustment=split`; za testove `session == regular`.

## Vijesti (`data/news/archive/*.jsonl`)

Ukupno **12,457** jedinstvenih članaka, od 2015-12-17 do 2026-10-05. Izvor Alpaca / Benzinga, samo naslov i metapodaci (bez punog teksta).

| Dionica | Članaka koji je spominju | Od toga fokusirani (≤ 3 simbola) | Po godinama (od najstarije) |
|---------|--------------------------|----------------------------------|-----------------------------|
| MU | 6,508 | 3,159 | 15:1 16:278 17:333 18:357 19:407 20:278 21:511 22:629 23:573 24:797 25:715 26:1629 |
| WDC | 2,356 | 1,266 | 16:238 17:270 18:134 19:152 20:145 21:168 22:230 23:175 24:187 25:253 26:404 |
| STX | 1,729 | 952 | 16:159 17:134 18:94 19:75 20:100 21:157 22:207 23:150 24:135 25:192 26:326 |
| SMH | 177 | 6 | 16:1 17:3 18:2 19:1 21:4 22:6 23:16 24:38 25:13 26:93 |
| AMAT | 297 | 13 | 16:5 17:13 18:20 19:17 20:21 21:29 22:28 23:18 24:32 25:25 26:89 |
| LRCX | 312 | 12 | 16:3 17:8 18:19 19:25 20:27 21:14 22:46 23:31 24:29 25:34 26:76 |
| KLAC | 191 | 0 | 16:1 17:10 18:14 19:10 20:20 21:17 22:24 23:12 24:20 25:19 26:44 |
| SIMO | 512 | 316 | 16:39 17:34 18:39 19:34 20:35 21:62 22:59 23:69 24:51 25:42 26:48 |
| RMBS | 648 | 367 | 16:54 17:43 18:56 19:30 20:30 21:66 22:54 23:80 24:80 25:73 26:82 |
| MRAM | 342 | 162 | 16:10 17:12 18:30 19:22 20:53 21:46 22:39 23:19 24:25 25:27 26:59 |
| ACMR | 619 | 281 | 17:12 18:31 19:38 20:116 21:62 22:126 23:74 24:75 25:50 26:35 |
| SNDK | 1,062 | 389 | 15:1 16:105 17:1 25:158 26:797 |
| DRAM | 150 | 31 | 16:30 17:8 26:112 |
| SKHY | 344 | 117 | 26:344 |

Pokrivenost vijestima je neujednačena: mnogo za MU, malo za mali MRAM/ACMR. Prije studije događaja provjeri broj po godini.

## Kalendar događaja i zarade

- `events_calendar.csv`: 58 događaja, tipovi: earnings_MU (43), peer_earnings (4), macro (2), macro_tariffs (2), sector_selloff (2), ai_demand_shock (1), analyst (1), korea_overnight (1), supply (1), peer_earnings_upcoming (1).
- `MU_earnings_dates.csv`: 43 Micron izvještaja (2016-03-30 do 2026-09-30) s gapom otvaranja, reakcijom dana, +5 i +20 dana.

## Što lokalno NEMA

- Društvene mreže (Reddit/X): nema izvora.
- Puni tekst vijesti i transkripti poziva: nema.
- Fundamentalni podaci (prihodi, marže, zalihe, cijene DRAM/NAND): nema.
- Opcije, kripto, forex: nema (ne trebaju za sada).
- Šira memorijska i poluvodička sfera (npr. NVDA, AMD, AVGO, TSM, INTC, NTAP, PSTG, NLST): nije povučena. Dostupnost se provjerava preko Alpaca asset liste.
- Korejski i japanski memorijski lideri (Samsung, SK hynix na KRX, Kioxia): nisu na Alpaci, SK hynix samo kao ADR SKHY od 2026-07.
