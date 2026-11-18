# Katalog podataka

Generirano 2026-10-14 14:40 UTC skriptom `scripts/data_catalog.py` (samo čitanje).

Cilj: imati što više kvalitetnih podataka za buduće backtestove, po klasi imovine i razini (dnevno, satno, 5 i 1 minuta).
Stupac **Rupe** broji propuštene radne dane (dnevno) ili prekide dulje od 3 koraka (intraday). Kod dionica to uglavnom su blagdani,
kod kripta (trguje 24/7) rupa je prava praznina. **Loši redovi** su barovi s nemogućim cijenama (high ispod low i slično).
Najnoviji datum kod većine dionica je 8. do 9. listopada: datoteke se ne dopunjavaju same, treba novi pull.

## Memorija i pohrana (primarno)

Porodice strategija koje tu imaju smisla: trend s filtrom, vodeći-pratitelj (oprema vodi memoriju), rotacija po relativnoj snazi, događaji (zarade), proboj nakon smirivanja volatilnosti.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| MU | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| MU | 1h | 40.870 | 2016-01-04 | 2026-10-05 | 4 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| MU | 5m | 404.898 | 2016-01-01 | 2026-10-05 | 9395 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| WDC | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| WDC | 1h | 32.564 | 2016-01-04 | 2026-10-05 | 76 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| WDC | 5m | 275.023 | 2016-01-04 | 2026-10-05 | 11937 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| STX | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| STX | 1h | 28.594 | 2016-01-04 | 2026-10-05 | 94 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| STX | 5m | 245.856 | 2016-01-04 | 2026-10-05 | 8415 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C5_ORB_5M, N1_SEMI_LEADLAG, N2_AI_CAPEX_BREADTH |
| RMBS | 1d | 2.708 | 2016-01-04 | 2026-10-09 | 102 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| RMBS | 1h | 25.195 | 2016-01-04 | 2026-10-05 | 72 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| RMBS | 5m | 224.880 | 2016-01-04 | 2026-10-14 | 4851 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| SIMO | 1d | 2.708 | 2016-01-04 | 2026-10-09 | 102 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| SIMO | 1h | 23.458 | 2016-01-04 | 2026-10-05 | 48 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| SIMO | 5m | 213.360 | 2016-01-04 | 2026-10-13 | 2786 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| SNDK | 1d | 415 | 2025-02-13 | 2026-10-08 | 16 | 0 | 0.0 % |  |
| DRAM | 1d | 131 | 2026-04-02 | 2026-10-08 | 5 | 0 | 0.0 % |  |
| DRAM | 1h | 2.038 | 2026-04-02 | 2026-10-05 | 0 | 0 | 0.0 % |  |
| SKHY | 1d | 64 | 2026-07-10 | 2026-10-08 | 1 | 0 | 0.0 % |  |
| SKHY | 1h | 964 | 2026-07-10 | 2026-10-05 | 0 | 0 | 0.0 % |  |
| MRAM | 1d | 2.514 | 2016-10-07 | 2026-10-08 | 96 | 0 | 0.0 % |  |
| MRAM | 1h | 22.187 | 2016-10-07 | 2026-10-05 | 47 | 0 | 0.0 % |  |
| ACMR | 1d | 2.243 | 2017-11-03 | 2026-10-08 | 87 | 0 | 0.0 % |  |
| ACMR | 1h | 22.610 | 2017-11-03 | 2026-10-05 | 93 | 0 | 0.0 % |  |
| NTAP | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| NTAP | 1h | 24.744 | 2016-01-04 | 2026-10-05 | 76 | 0 | 0.0 % |  |
| PSTG | 1d | 2.586 | 2016-01-04 | 2026-04-16 | 98 | 0 | 0.0 % |  |
| PSTG | 1h | 26.323 | 2016-01-04 | 2026-04-16 | 71 | 0 | 0.0 % |  |

## Poluvodiči i oprema

Porodice strategija koje tu imaju smisla: vodeći signal za memoriju, ciklus potražnje, relativna snaga unutar sektora, trend.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| NVDA | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| NVDA | 1h | 41.050 | 2016-01-04 | 2026-10-05 | 7 | 0 | 0.0 % |  |
| AMD | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| AMD | 1h | 41.562 | 2016-01-01 | 2026-10-05 | 5 | 0 | 0.0 % |  |
| AVGO | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| AVGO | 1h | 32.340 | 2016-01-04 | 2026-10-05 | 26 | 0 | 0.0 % |  |
| TSM | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| TSM | 1h | 36.501 | 2016-01-04 | 2026-10-05 | 30 | 0 | 0.0 % |  |
| ASML | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| ASML | 1h | 34.051 | 2016-01-04 | 2026-10-05 | 50 | 0 | 0.0 % |  |
| AMAT | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | N1_SEMI_LEADLAG |
| LRCX | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | N1_SEMI_LEADLAG |
| KLAC | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | N1_SEMI_LEADLAG |
| INTC | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| INTC | 1h | 40.245 | 2016-01-01 | 2026-10-05 | 22 | 0 | 0.0 % |  |
| MRVL | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| MRVL | 1h | 34.013 | 2016-01-04 | 2026-10-05 | 23 | 0 | 0.0 % |  |
| ENTG | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| ENTG | 1h | 23.636 | 2016-01-04 | 2026-10-05 | 84 | 0 | 0.0 % |  |
| FORM | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| FORM | 1h | 23.906 | 2016-01-04 | 2026-10-05 | 57 | 0 | 0.0 % |  |
| MKSI | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| MKSI | 1h | 23.112 | 2016-01-04 | 2026-10-05 | 74 | 0 | 0.0 % |  |
| ONTO | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| ONTO | 1h | 23.274 | 2016-01-04 | 2026-10-05 | 57 | 0 | 0.0 % |  |
| SMCI | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 12.9 % |  |
| SMCI | 1h | 26.266 | 2016-01-04 | 2026-10-05 | 14 | 0 | 0.0 % |  |
| QCOM | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| QCOM | 1h | 37.713 | 2016-01-01 | 2026-10-14 | 42 | 0 | 0.0 % |  |
| TXN | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| TXN | 1h | 29.390 | 2016-01-01 | 2026-10-13 | 111 | 0 | 0.0 % |  |
| MCHP | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| MCHP | 1h | 27.834 | 2016-01-04 | 2026-10-14 | 95 | 0 | 0.0 % |  |
| ON | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| ON | 1h | 31.766 | 2016-01-04 | 2026-10-14 | 38 | 0 | 0.0 % |  |
| SOXX | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| SOXX | 1h | 32.295 | 2016-01-04 | 2026-10-05 | 68 | 0 | 0.0 % |  |
| SOXL | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| SOXL | 1h | 36.964 | 2016-01-04 | 2026-10-05 | 22 | 0 | 0.0 % |  |
| SMH | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | C1_TSMOM_MULTI, C3_IBS_REVERT, N1_SEMI_LEADLAG |
| SMH | 5m | 286.035 | 2016-01-04 | 2026-10-05 | 10822 | 0 | 0.0 % | C1_TSMOM_MULTI, C3_IBS_REVERT, N1_SEMI_LEADLAG |
| EWY | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % |  |
| EWY | 1h | 27.993 | 2016-01-04 | 2026-10-05 | 123 | 0 | 0.0 % |  |

## Veliki tehnološki (AI potražnja)

Porodice strategija koje tu imaju smisla: širina trenda kao signal za AI potražnju, makro filtar rizika.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| MSFT | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| MSFT | 1h | 41.202 | 2016-01-01 | 2026-10-14 | 7 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| GOOGL | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| GOOGL | 1h | 36.231 | 2016-01-04 | 2026-10-14 | 34 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| AMZN | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| AMZN | 1h | 40.483 | 2016-01-01 | 2026-10-14 | 4 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| META | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| META | 1h | 42.046 | 2016-01-01 | 2026-10-14 | 0 | 0 | 0.0 % | N2_AI_CAPEX_BREADTH |
| ORCL | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| ORCL | 1h | 33.592 | 2016-01-04 | 2026-10-14 | 82 | 0 | 0.0 % |  |
| DELL | 1d | 1.958 | 2018-12-28 | 2026-10-13 | 75 | 0 | 0.0 % |  |
| DELL | 1h | 23.768 | 2018-12-28 | 2026-10-14 | 54 | 0 | 0.0 % |  |
| XLK | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| XLK | 1h | 34.845 | 2016-01-04 | 2026-10-14 | 40 | 0 | 0.0 % |  |
| QQQ | 1d | 2.704 | 2016-01-04 | 2026-10-05 | 102 | 0 | 0.0 % | C3_IBS_REVERT |
| QQQ | 1h | 42.347 | 2016-01-01 | 2026-10-05 | 0 | 0 | 0.0 % | C3_IBS_REVERT |

## Zlato i srebro (ETF)

Porodice strategija koje tu imaju smisla: trend uz filtar dolara i kamata, omjer zlato/srebro, rotacija zlato-srebro-novac.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| GLD | 1d | 2.709 | 2016-01-04 | 2026-10-12 | 102 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C3_IBS_REVERT, C4_GOLD_SILVER_RATIO, N3_GOLD_USD_REGIME |
| GLD | 5m | 386.237 | 2016-01-01 | 2026-10-12 | 12749 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C3_IBS_REVERT, C4_GOLD_SILVER_RATIO, N3_GOLD_USD_REGIME |
| SLV | 1d | 2.709 | 2016-01-04 | 2026-10-12 | 102 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C3_IBS_REVERT, C4_GOLD_SILVER_RATIO, N3_GOLD_USD_REGIME |
| SLV | 5m | 388.319 | 2016-01-04 | 2026-10-12 | 11370 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, C3_IBS_REVERT, C4_GOLD_SILVER_RATIO, N3_GOLD_USD_REGIME |
| IAU | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| IAU | 1h | 36.323 | 2016-01-04 | 2026-10-14 | 61 | 0 | 0.0 % |  |
| SGOL | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| SGOL | 1h | 28.021 | 2016-01-04 | 2026-10-14 | 97 | 0 | 0.0 % |  |
| PHAG | 1d | 509 | 2024-10-14 | 2026-10-12 | 12 | 0 | 0.0 % |  |
| PHAU | 1d | 509 | 2024-10-14 | 2026-10-12 | 12 | 0 | 0.0 % |  |
| PPLT | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| PPLT | 1h | 28.344 | 2016-01-04 | 2026-10-14 | 276 | 0 | 0.0 % |  |
| CPER | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 1.7 % |  |
| CPER | 1h | 21.394 | 2016-01-04 | 2026-10-13 | 226 | 0 | 0.0 % |  |

## Rudari metala

Porodice strategija koje tu imaju smisla: polugu na metal (rudari prate metal s pojačanjem), omjer rudari/metal kao signal raspoloženja.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| GDX | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| GDX | 1h | 40.937 | 2016-01-01 | 2026-10-14 | 3 | 0 | 0.0 % |  |
| GDXJ | 1d | 2.628 | 2016-05-02 | 2026-10-13 | 99 | 0 | 0.0 % |  |
| GDXJ | 1h | 36.536 | 2016-05-02 | 2026-10-14 | 25 | 0 | 0.0 % |  |
| SIL | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| SIL | 1h | 26.994 | 2016-01-04 | 2026-10-14 | 79 | 0 | 0.0 % |  |
| SILJ | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| SILJ | 1h | 29.058 | 2016-01-04 | 2026-10-14 | 70 | 0 | 0.0 % |  |
| NEM | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| NEM | 1h | 35.467 | 2016-01-01 | 2026-10-14 | 43 | 0 | 0.0 % |  |
| GOLD | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.4 % |  |
| GOLD | 1h | 20.948 | 2016-01-04 | 2026-10-13 | 100 | 0 | 0.0 % |  |
| PAAS | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| PAAS | 1h | 32.615 | 2016-01-01 | 2026-10-14 | 50 | 0 | 0.0 % |  |
| WPM | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| WPM | 1h | 30.257 | 2016-01-04 | 2026-10-14 | 123 | 0 | 0.0 % |  |
| FCX | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| FCX | 1h | 38.662 | 2016-01-01 | 2026-10-14 | 13 | 0 | 0.0 % |  |

## Energija i roba

Porodice strategija koje tu imaju smisla: trend i makro filtar, kontekst inflacije.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| USO | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| USO | 1h | 41.113 | 2016-01-01 | 2026-10-14 | 0 | 0 | 0.0 % |  |
| UNG | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| UNG | 1h | 39.369 | 2016-01-04 | 2026-10-14 | 4 | 0 | 0.0 % |  |
| DBC | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| DBC | 1h | 25.294 | 2016-01-04 | 2026-10-13 | 188 | 0 | 0.0 % |  |

## Kripto USD (Alpaca)

Porodice strategija koje tu imaju smisla: ista pravila kao USDT, ali kraća povijest (od 2021.); odgovara cijenama na IBKR-u.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| BTCUSD | 1d | 2.113 | 2021-01-01 | 2026-10-14 | 0 | 0 | 0.0 % |  |
| ETHUSD | 1d | 2.113 | 2021-01-01 | 2026-10-14 | 0 | 0 | 0.0 % |  |
| SOLUSD | 1d | 1.695 | 2021-01-01 | 2026-10-14 | 0 | 0 | 0.6 % |  |
| XRPUSD | 1d | 1.018 | 2024-01-01 | 2026-10-14 | 0 | 0 | 0.0 % |  |
| LTCUSD | 1d | 2.113 | 2021-01-01 | 2026-10-14 | 0 | 0 | 0.2 % |  |
| LINKUSD | 1d | 2.113 | 2021-01-01 | 2026-10-14 | 0 | 0 | 0.2 % |  |
| DOGEUSD | 1d | 2.113 | 2021-01-01 | 2026-10-14 | 0 | 0 | 0.1 % |  |
| AVAXUSD | 1d | 1.792 | 2021-11-18 | 2026-10-14 | 0 | 0 | 1.8 % |  |
| AVAXUSD | 1h | 42.972 | 2021-11-18 | 2026-10-14 | 1 | 0 | 31.6 % |  |

## Kripto USDT (Binance, duga povijest)

Porodice strategija koje tu imaju smisla: trend, proboj nakon smirivanja volatilnosti, satni trend uz filtar režima, jednodnevni obrasci (dan u tjednu, sat u danu).

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1d | 3.345 | 2017-08-17 | 2026-10-13 | 0 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, N4_BTC_VOL_COMPRESSION, N5_CRYPTO_HOURLY_TREND |
| BTCUSDT | 1h | 80.149 | 2017-08-17 | 2026-10-13 | 14 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, N4_BTC_VOL_COMPRESSION, N5_CRYPTO_HOURLY_TREND |
| BTCUSDT | 5m | 961.609 | 2017-08-17 | 2026-10-13 | 32 | 0 | 0.1 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, N4_BTC_VOL_COMPRESSION, N5_CRYPTO_HOURLY_TREND |
| BTCUSDT | 1m | 1.990.000 | 2023-01-01 | 2026-10-13 | 1 | 0 | 0.0 % |  |
| ETHUSDT | 1d | 3.345 | 2017-08-17 | 2026-10-13 | 0 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, N4_BTC_VOL_COMPRESSION, N5_CRYPTO_HOURLY_TREND |
| ETHUSDT | 1h | 80.149 | 2017-08-17 | 2026-10-13 | 14 | 0 | 0.0 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, N4_BTC_VOL_COMPRESSION, N5_CRYPTO_HOURLY_TREND |
| ETHUSDT | 5m | 961.609 | 2017-08-17 | 2026-10-13 | 32 | 0 | 0.2 % | C1_TSMOM_MULTI, C2_DONCHIAN_TURTLE, N4_BTC_VOL_COMPRESSION, N5_CRYPTO_HOURLY_TREND |
| ETHUSDT | 1m | 1.990.000 | 2023-01-01 | 2026-10-13 | 1 | 0 | 0.0 % |  |
| BNBUSDT | 1d | 3.264 | 2017-11-06 | 2026-10-13 | 0 | 0 | 0.0 % |  |
| BNBUSDT | 1h | 78.213 | 2017-11-06 | 2026-10-13 | 13 | 0 | 0.0 % |  |
| LTCUSDT | 1d | 3.227 | 2017-12-13 | 2026-10-13 | 0 | 0 | 0.0 % |  |
| LTCUSDT | 1h | 77.325 | 2017-12-13 | 2026-10-13 | 13 | 0 | 0.0 % |  |
| XRPUSDT | 1d | 3.085 | 2018-05-04 | 2026-10-13 | 0 | 0 | 0.0 % |  |
| XRPUSDT | 1h | 73.945 | 2018-05-04 | 2026-10-13 | 12 | 0 | 0.0 % |  |
| LINKUSDT | 1d | 2.828 | 2019-01-16 | 2026-10-13 | 0 | 0 | 0.0 % |  |
| LINKUSDT | 1h | 67.803 | 2019-01-16 | 2026-10-13 | 8 | 0 | 0.0 % |  |
| DOGEUSDT | 1d | 2.658 | 2019-07-05 | 2026-10-13 | 0 | 0 | 0.0 % |  |
| DOGEUSDT | 1h | 63.737 | 2019-07-05 | 2026-10-13 | 6 | 0 | 0.0 % |  |
| SOLUSDT | 1d | 2.255 | 2020-08-11 | 2026-10-13 | 0 | 0 | 0.0 % | N5_CRYPTO_HOURLY_TREND |
| SOLUSDT | 1h | 54.095 | 2020-08-11 | 2026-10-13 | 3 | 0 | 0.0 % | N5_CRYPTO_HOURLY_TREND |
| SOLUSDT | 5m | 649.085 | 2020-08-11 | 2026-10-13 | 10 | 0 | 0.0 % | N5_CRYPTO_HOURLY_TREND |
| AVAXUSDT | 1d | 2.213 | 2020-09-22 | 2026-10-13 | 0 | 0 | 0.0 % |  |
| AVAXUSDT | 1h | 53.087 | 2020-09-22 | 2026-10-13 | 3 | 0 | 0.0 % |  |

## Kripto dionice i ETF-ovi

Porodice strategija koje tu imaju smisla: razlika između ETF-a i spota, rizik-on signal, trend.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| IBIT | 1d | 691 | 2024-01-11 | 2026-10-13 | 28 | 0 | 0.0 % |  |
| IBIT | 1h | 11.038 | 2024-01-11 | 2026-10-14 | 0 | 0 | 0.0 % |  |
| ETHA | 1d | 559 | 2024-07-23 | 2026-10-13 | 22 | 0 | 0.0 % |  |
| ETHA | 1h | 8.893 | 2024-07-23 | 2026-10-14 | 1 | 0 | 0.0 % |  |
| MSTR | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| MSTR | 1h | 30.325 | 2016-01-04 | 2026-10-14 | 23 | 0 | 0.0 % |  |
| COIN | 1d | 1.382 | 2021-04-14 | 2026-10-13 | 53 | 0 | 0.0 % |  |
| COIN | 1h | 21.756 | 2021-04-14 | 2026-10-14 | 0 | 0 | 0.0 % |  |
| MARA | 1d | 2.250 | 2017-10-30 | 2026-10-13 | 87 | 0 | 0.0 % |  |
| MARA | 1h | 31.688 | 2017-10-30 | 2026-10-14 | 9 | 0 | 0.0 % |  |

## Širi indeksi, kamate, dolar

Porodice strategija koje tu imaju smisla: makro filtri (dolar, obveznice, kreditni rizik) za ostale klase.

| Instrument | Razina | Redaka | Od | Do | Rupe | Loši redovi | Bez volumena | Strategije u TOP10 |
|---|---|---|---|---|---|---|---|---|
| SPY | 1d | 2.707 | 2016-01-04 | 2026-10-08 | 102 | 0 | 0.0 % | C3_IBS_REVERT |
| SPY | 1h | 42.557 | 2016-01-01 | 2026-10-05 | 0 | 0 | 0.0 % | C3_IBS_REVERT |
| IWM | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| IWM | 1h | 41.971 | 2016-01-01 | 2026-10-14 | 1 | 0 | 0.0 % |  |
| DIA | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| DIA | 1h | 39.384 | 2016-01-01 | 2026-10-14 | 20 | 0 | 0.0 % |  |
| UUP | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % | N3_GOLD_USD_REGIME |
| UUP | 1h | 28.806 | 2016-01-04 | 2026-10-14 | 125 | 0 | 0.0 % | N3_GOLD_USD_REGIME |
| TLT | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % | N3_GOLD_USD_REGIME |
| TLT | 1h | 38.377 | 2016-01-01 | 2026-10-14 | 15 | 0 | 0.0 % | N3_GOLD_USD_REGIME |
| IEF | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| IEF | 1h | 28.207 | 2016-01-04 | 2026-10-14 | 91 | 0 | 0.0 % |  |
| HYG | 1d | 2.710 | 2016-01-04 | 2026-10-13 | 102 | 0 | 0.0 % |  |
| HYG | 1h | 27.956 | 2016-01-04 | 2026-10-14 | 112 | 0 | 0.0 % |  |
| EURUSD | 1d | 3.000 | 2015-03-19 | 2026-10-12 | 19 | 0 | – |  |

## Ukupno

Redaka u svim katalogiziranim datotekama: 11.886.555.

## Što dalje za kvalitetu podataka

- Dopuna do danas: `pull_alpaca.py` ne prepisuje postojeće datoteke, pa treba skripta koja dopisuje samo nove barove.
- Kripto USD na satnoj i 5-minutnoj razini nije povučen (Alpaca API je spor); Binance USDT to pokriva dublje.
- Fizičko zlato/srebro i futures (XAU, GC, SI) nisu u Alpaci; moguće preko IBKR-a kasnije.
- Prije svakog backtesta i dalje vrijedi `scripts/validate_data.py` (izlaz 1 znači: bez backtesta).
