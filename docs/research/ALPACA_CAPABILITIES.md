# Što Alpaca stvarno nudi (izmjereno)

Generirano 2026-10-05T22:47:13+02:00 skriptom `scripts/alpaca_probe.py` (samo GET zahtjevi, bez naloga). Račun: **paper**.

## Račun

- Status: ACTIVE, valuta USD, equity 100000, buying power 400000, multiplier 4, shorting True.
- Multiplier 4 i shorting su **svojstva paper računa** i nisu realni za EU malog ulagatelja (vidi `docs/guides/regulation-eu-hr.md`).

## Feedovi i cijene: što radi na ovom ključu

| Provjera | Rezultat |
|----------|----------|
| `sip` zadnji bar / kotacija | HTTP 403 / HTTP 403 |
| `sip` povijesni dnevni barovi (tjedan stariji) | HTTP 200, 5 barova |
| `iex` zadnji bar / kotacija | HTTP 200 / HTTP 200 |
| `iex` povijesni dnevni barovi (tjedan stariji) | HTTP 200, 5 barova |

Tumačenje: HTTP 200 radi, 403 znači da plan ne dopušta (besplatni plan nema SIP u realnom vremenu, a povijesni SIP stariji od 15 minuta radi). IEX je oko 2 % tržišnog volumena, pa se njegov volumen ne koristi.

## Dubina povijesti po dionici (najraniji bar)

| Dionica | Lokalno od | SIP dnevni | IEX dnevni | SIP satni | SIP 1 min |
|---------|------------|------------|------------|-----------|-----------|
| MU | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-01 | 2016-01-01 |
| WDC | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| STX | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| SMH | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| AMAT | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| LRCX | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| KLAC | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| SIMO | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| RMBS | 2016-01-04 | 2016-01-04 | 2020-07-27 | 2016-01-04 | 2016-01-04 |
| MRAM | 2016-10-07 | 2016-10-07 | 2020-07-27 | 2016-10-07 | 2016-10-07 |
| ACMR | 2017-11-03 | 2017-11-03 | 2020-07-27 | 2017-11-03 | 2017-11-03 |
| SNDK | 2025-02-13 | 2025-02-13 | 2025-02-13 | 2025-02-13 | 2025-02-13 |
| DRAM | 2026-04-02 | 2016-01-04 | 2026-04-02 | 2016-01-04 | 2016-01-04 |
| SKHY | 2026-07-10 | 2026-07-10 | 2026-07-10 | 2026-07-10 | 2026-07-10 |

## Prilagodbe cijena (WDC oko SanDisk spin-offa 2025-02-24)

| Prilagodba | Zatvaranje 2025-02-21 | 2025-02-24 | Promjena |
|------------|-----------------------|------------|----------|
| `raw` | 68.705 | 49.02 | -28.7 % |
| `split` | 68.705 | 49.02 | -28.7 % |
| `spin-off` | 46.81 | 49.02 | +4.7 % |
| `all` | 46.58 | 48.78 | +4.7 % |

Lab koristi `split` + ručni faktor 0.68132 za WDC (vidi `docs/architecture/data.md`).

## Popis instrumenata (assets)

- Aktivnih američkih dionica i ETF-ova: **14,388**, tradable: **13,506**.
- Po burzi: NASDAQ 5,598, NYSE 2,909, ARCA 2,744, BATS 1,655, OTC 309, AMEX 291.

| Simbol | U labu? | Postoji | Burza | Tradable | Shortable | Fractionable |
|--------|---------|---------|-------|----------|-----------|--------------|
| MU | da | da | NASDAQ | True | True | True |
| WDC | da | da | NASDAQ | True | True | True |
| STX | da | da | NASDAQ | True | True | True |
| SMH | da | da | NASDAQ | True | True | True |
| AMAT | da | da | NASDAQ | True | True | True |
| LRCX | da | da | NASDAQ | True | True | True |
| KLAC | da | da | NASDAQ | True | True | True |
| SIMO | da | da | NASDAQ | True | True | True |
| RMBS | da | da | NASDAQ | True | True | True |
| MRAM | da | da | NASDAQ | True | True | True |
| ACMR | da | da | NASDAQ | True | True | True |
| SNDK | da | da | NASDAQ | True | True | True |
| DRAM | da | da | BATS | True | True | True |
| SKHY | da | da | NASDAQ | True | True | True |
| NVDA | ne | da | NASDAQ | True | True | True |
| AMD | ne | da | NASDAQ | True | True | True |
| AVGO | ne | da | NASDAQ | True | True | True |
| TSM | ne | da | NYSE | True | True | True |
| ASML | ne | da | NASDAQ | True | True | True |
| INTC | ne | da | NASDAQ | True | True | True |
| QCOM | ne | da | NASDAQ | True | True | True |
| TXN | ne | da | NASDAQ | True | True | True |
| MRVL | ne | da | NASDAQ | True | True | True |
| ON | ne | da | NASDAQ | True | True | True |
| MCHP | ne | da | NASDAQ | True | True | True |
| NTAP | ne | da | NASDAQ | True | True | True |
| PSTG | ne | ne | - | - | - | - |
| NLST | ne | da | OTC | False | True | False |
| SMCI | ne | da | NASDAQ | True | True | True |
| DELL | ne | da | NYSE | True | True | True |
| HPE | ne | da | NYSE | True | True | True |
| MXL | ne | da | NASDAQ | True | True | True |
| COHU | ne | da | NASDAQ | True | True | True |
| FORM | ne | da | NASDAQ | True | True | True |
| ONTO | ne | da | NYSE | True | True | True |
| ENTG | ne | da | NASDAQ | True | True | True |
| MKSI | ne | da | NASDAQ | True | True | True |
| UCTT | ne | da | NASDAQ | True | True | True |
| ICHR | ne | da | NASDAQ | True | True | True |
| SOXX | ne | da | NASDAQ | True | True | True |
| XSD | ne | da | ARCA | True | False | True |
| SOXL | ne | da | ARCA | True | True | True |
| SOXS | ne | da | ARCA | True | False | True |
| USD | ne | da | ARCA | True | True | True |
| EWY | ne | da | ARCA | True | True | True |
| KORU | ne | da | ARCA | True | False | True |
| QQQ | ne | da | NASDAQ | True | True | True |
| SPY | ne | da | ARCA | True | True | True |
| XLK | ne | da | ARCA | True | True | True |
| VIX | ne | ne | - | - | - | - |
| VXX | ne | da | BATS | True | False | True |
| UVXY | ne | da | BATS | True | True | True |

## Vijesti

| Dionica | Najranija vijest | Uzorak naslova (najranija) |
|---------|------------------|----------------------------|
| MU | 2015-01-04 | Earnings Expectations For The Week Of January 5 |
| WDC | 2015-01-13 | Top 4 NASDAQ Stocks In The Data Storage Devices Industry With The High |
| STX | 2015-01-02 | Seagate Filing Says the Company Will Record An Additional $200M Tax Ex |
| SNDK | 2015-01-05 | SanDisk Unveils New USB Flash Drive for Android |
| SKHY | 2026-07-06 | SK Hynix Files Prospectus To Sell 177.9M ADSs, Each Representing One T |
| SMH | 2015-01-05 | Semiconductor ETFs Set to Continue Rally |

Puni tekst (`include_content`) za zadnje MU vijesti: [True, True, True]. Lokalni arhiv ima samo naslove.

## Korporativne akcije (splitovi, spin-off, dividende)

| Dionica | Vrste i broj (od 2016) |
|---------|------------------------|
| MU | cash_dividends 20 |
| WDC | cash_dividends 23, spin_offs 1 |
| STX | cash_dividends 42, cash_mergers 1 |
| SMH | cash_dividends 10, forward_splits 1 |
| AMAT | cash_dividends 43 |
| LRCX | cash_dividends 42, forward_splits 1 |
| KLAC | cash_dividends 43, forward_splits 1 |

## Opcije i screener

- Opcijski ugovori za MU: HTTP 200 (dostupno). Opcije se ne koriste u ovom labu.
- Screener most-actives: HTTP 200: WBD, BEAT, EWZ, CTVA, NU
- Screener movers: HTTP 200: gore MI, SAIQ, SSEAR, VJET, HSCSW; dolje NMCO.RT, CYCUW, WHLR, SDEV, DAAQW

## CLI i MCP: što stoji na raspolaganju

**Alpaca CLI** (`~/go/bin/alpaca`, v0.0.14): `data` (bars, multi-bars, quotes, trades, snapshots, news, screener, corporate-actions, options, crypto, forex, fixed-income, auctions), `asset`, `account`, `clock`, `calendar`, `corporate-action`, `watchlist`, `order`, `position`, `option`, `api` (sirovi pristup), `doctor`. Ključevi se čitaju iz `ALPACA_API_KEY` i `ALPACA_SECRET_KEY`. Zastavice `--csv`, `--jq`, `--schema` olakšavaju skripte.

**Alpaca MCP** (`uvx alpaca-mcp-server`): toolseti `account`, `trading`, `watchlists`, `assets`, `stock-data`, `crypto-data`, `options-data`, `corporate-actions`, `news`, `fixed-income-data`, `locates`. U ovom projektu uključeno je samo: `account, assets, stock-data, corporate-actions, news` (bez `trading`).
