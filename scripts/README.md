# scripts/

Izvršne skripte. Svaka nova skripta se opiše ovdje.

| Skripta | Što radi | Piše u |
|---------|----------|--------|
| `pull_alpaca.py` | Samo GET: dodaje nove SIP dnevne, satne i 5-minutne CSV-ove, uz kalendar sjednica i jednokratnu WDC prilagodbu; postojeće datoteke ne mijenja | `data/ohlcv/`, `data/hourly/`, `data/intraday/` |
| `validate_data.py` | Data gate: provjera dnevnih i satnih CSV-ova, exit 1 = nema backtesta | `reports/data/DATA_CHECK.md` |
| `replay_c13c.py` | C13C od 2021., jedan račun MU/WDC/STX, ekvivalent početnih 600 €; tri veličine pozicije i audit, bez naloga | `reports/backtest/C13C_2021_*` |
| `alpaca_probe.py` | Mjeri što Alpaca stvarno daje (samo GET), piše `docs/research/ALPACA_CAPABILITIES.md` | `docs/research/` |
| `data_inventory.py` | Inventar lokalnih podataka, piše `docs/research/DATA_INVENTORY.md` | `docs/research/` |
| `check_layout.py` | Provjera rasporeda datoteka (samo čita) | stdout |
| `run_claude_session.sh` | Pokreće Claude Code sesiju s `PROMPTS/claude-backtest.md` | `reports/runs/` |
| `run_codex_session.sh` | Pokreće Codex sesiju s `PROMPTS/codex-backtest.md` | `reports/runs/` |
| `pull_data.py` | Osvježava dnevne cijene preko Alpaca paper (starije, piše i parquet koji se ne koristi) | `data/ohlcv/` |
| `backtest_swing.py` | Stari swing screening na punom uzorku, `reports/leaderboard.md` | `reports/` (zastarjelo, vidi archive) |

Ne postoje lokalno, a spominju se u `AGENTS.md`: `pull_news.py`, `backtest_C*.py` (zamjenjuje ih novi stroj u `lab/`).
Skripte nikad ne šalju naloge. Okolina: [`docs/guides/setup.md`](../docs/guides/setup.md).

- `run_memory_swing.py` — ponovljiv C21 swing audit: cijele dionice, paper 100.000 USD, hipotetskih 600 EUR, povijesni ECB i razdoblja prije/poslije ChatGPT-a; nalozi se ne šalju. Zamrznuti protokol u `strategies/frozen/2026-10-06_C21_SWING_20261006.md`, rezultati u `reports/backtest/C21_SWING_20261006/`. Dodatni scenarij cijelog iznosa: `--study C22_FULL_CASH_SWING_20261006`.
- `run_swing_robustness.py` — C23: četiri unaprijed definirane varijante za 600 EUR bez doplata, stres izvršenja, tržišni režimi i statističke provjere; rezultati u `reports/backtest/C23_SWING_ROBUSTNESS_20261006/`. Samo simulacija.
- `analyze_swing_priority.py` — C25: šest zamrznutih redoslijeda MU/WDC/STX na zajedničkom računu 600 EUR; WF i razdoblje od 1.12.2022., isti C13C ulaz/stop, bez odabira pobjednika. Provjerava cijelu putanju prema C22; piše samo `reports/backtest/C25_PRIORITY_AUDIT_20261006/`. Ne šalje naloge i odbija prepisati dovršen izvještaj.

- `analyze_swing_attribution.py` — C24 opisna analiza stopova, čekanja i sukoba signala na nepromijenjenom C13C; izvještaji u `reports/backtest/C24_ATTRIBUTION_20261006/`, bez naloga i optimizacije.

- `audit_c26_integrity.py` — C26 provjera vremenskog rezanja, promjene budućih cijena i dnevnih izvršenja; samo čitanje, rezultat u `reports/research/`.

- `audit_random_swing.py` — C27 zamrznute slučajne kontrole i troškovni stres prenesenih C26 skupina, samo offline; rezultati u `reports/backtest/C27_RANDOM_COST_AUDIT_20261006/`.
- `run_recovery_reentry.py` — zamrznuti C28: usporedba izvornog C13C i jednokratno definirane hipoteze ponovnog ulaza nakon oporavka iznad prethodnog vrha; 600EUR s reinvestiranjem, jedna dionica i paper100k, stresovi te provjere uzročnosti. Piše `reports/backtest/C28_RECOVERY_REENTRY_20261006/`; ne mijenja aktivnu strategiju i ne šalje naloge.

- `c13c_data_audit_20261009.py` — lokalno spaja prethodno arhivirane Alpaca GET odgovore s kanonskim dnevnim CSV datotekama: zadržava raniju povijest, zamjenjuje nedovršeni 5. listopada dovršenim barom i dodaje 6.–8. listopada. Provjerava kalendar, preklop, korporativne akcije i hash vrijednosti; odbija nedovršeni 9. listopada. Čuva izvorne datoteke u `data/archive/c13c_20261009/`, piše `DATA.md`/`DATA.json` u `reports/research/C13C_20261009/`. Sama skripta nema mrežne pozive ni naloge.
- `run_c13c_regimes_20261009.py` — zamrznuto offline istraživanje C29/C30: C13C baseline, ATR stop i filtar velikog pada na otvaranju; računi 500/600 EUR, dodatne dionice, usporedbe za TradingView, tržišni režimi, kontinuirani godišnji prinosi, stres, osjetljivost i provjere uzročnosti. Podatkovni gate obavezan, nema odabira najboljeg parametra. Piše `reports/backtest/C29_C30_REGIMES_20261009/`, `reports/research/C13C_20261009/` i FAIL verdikte u `reports/gate/`; odbija prepisati dovršeni numerički rezultat. Ne mijenja aplikaciju ni `approved_list` i ne šalje naloge.
- `tradingview/C29_C30_research_replica.pine` — istraživačka Pine v6 replika BASE/C29/C30 za zasebni TradingView Strategy Tester; jedna dionica, 10.000 USD, dnevni završeni signali, zaštitni stop i eksplicitan vremenski prozor. Namijenjena brojčanoj usporedbi s lokalnim engineom, bez alertova ili veze s brokerom; razlike OHLC emulatora i troškova dokumentiraju se u zasebnom TradingView izvještaju.
- `compare_c13c_tradingview_20261009.py` — uspoređuje spremljene TradingView MCP JSON snimke s postojećim lokalnim rezultatima za jednu dionicu i 10.000 USD u 30 slučajeva. Čita saldo na presjeku iz Pine tablice, provjerava broj zatvorenih trgovina i dostupni završni niz akcija, odbija nevaljane snimke i označava nedostajuće datume. Piše `TRADINGVIEW_COMPARISON.md`/`.json` u `reports/research/C13C_20261009/`; može se ponovno pokrenuti nakon novih batch datoteka. Ne pokreće novi backtest, nema mrežnih poziva i ne šalje naloge.

- `tradingview/C31_C13C_cross_market_replica.pine`: C31 opisni prijenos C13C na forex i BTC perpetual, dnevni podaci, 90% quote kapitala bez poluge; funding/swap nisu uključeni.
- `tradingview/C31_C13C_cross_market_stress_replica.pine`: unaprijed definirana provjera s dvostrukom provizijom za C31; ostala pravila ista.
- `audit_c31_cross_market_20261009.py`: neovisna provjera 12 spremljenih TradingView MCP slučajeva C31, svih izvezenih trgovina i dnevnog računa; izrađuje SUMMARY.json i CSV izvode bez poziva brokeru.

- `backtest_c32_sndk.py`: zamrznuti offline C13C/SNDK pregled, 100/500/10000 USD, provjere truncation/future-corruption, bez brokerskih naloga.

- run_c34_memory600.py: zamrznut C13C backtest 600 EUR, pojedinacni i zajednicki racun, whole/fractional, IS/WF/recent i audit.
- report_c34_memory600.py: hrvatski izvjestaj, usporedni CSV i SVG iz C34 spremljenih rezultata.

## TradingView MCP bez restarta

`tradingview_mcp_client.mjs` izravno poziva instalirani iliaal MCP preko stdio protokola kada popis alata u otvorenom razgovoru ostane zastario. `node scripts/tradingview_mcp_client.mjs list` vraća aktualne sheme; drugi argument je naziv alata, treći JSON parametri. Ovo ne osvježava ugrađeni Codex registar alata. Projektna zabrana slanja naloga i dalje vrijedi.

- `replay_c34_rmbs_simo_20261012.py` — zamrznuti Alpaca RMBS/SIMO C13C/C34 dijagnostički test od početka 2024., s IS/WF kontrolama i auditom; bez naloga.

- `backtest_metals_20261013.py`: C35 istraživačka simulacija zlata/srebra, odvojeni razvoj/holdout, sintetičke provjere, troškovni stres; bez mreže i naloga.
- `analyze_metals_20261013.py`: C35 postprocesiranje godišnjih rezultata, koncentracije i block-bootstrap drawdowna; grafikoni kada je matplotlib dostupan.
- `run_metals_campaign_20261013.py`: pokreće 24 unaprijed zamrznute C35 konfiguracije u zasebnim direktorijima; hashom veže odabir i simulator prije holdouta.
- `report_metals_20261013.py`: hrvatski Markdown/HTML izvještaj i tablice iz pohranjenih C35 rezultata; ne mijenja strategije ni odabir.


### Forex istraživanje 2026-10-13

- `backtest_forex_fx1.py`: EUR/USD simulator gotovine bez poluge i bez broker alata; faze `pre` i `holdout`, zamrznuti FX1 i 16 unaprijed registriranih scenarija.
- `build_forex_report.py`: reproducibilni hrvatski dokument i grafovi iz verificiranih FX1 rezultata; bundled document Python runtime.
- `ibkr_metals_signals.py`: IBKR PHAU/PHAG lokalni read-only prototip; validacija snimke, opisne značajke, cijele jedinice, fail-closed PRIČEKAJ; bez mreže i naloga.

### Metali C36 — 2026-10-13

- `backtest_metals_advanced_20261013.py`: zamrznuti offline KAMA/ENSEMBLE/ROTATE, EUR cijele jedinice, troškovi i tri kapitala; odvojeni proxy i IBKR test.
- `metals_advanced_signals.py`: lokalni istraživački snapshot, obavezno PRIČEKAJ, nema brokerskih naloga.
- `report_metals_advanced_20261013.py`: izvještaj HR/HTML, grafovi i opisna statistička osjetljivost iz spremljenih rezultata; matplotlib u privremenom runtimeu.

- `tradingagents_worker.py`, `tradingagents_codex.py` — izolirane AI analize kroz Codex OAuth; vidi `docs/guides/tradingagents.md`. Ne šalju naloge.
| `pull_crypto_daily.py` | Samo GET: kripto barovi s Alpace (dnevni, satni, 5-minutni za BTC/ETH), od 2021. Postojeće datoteke prepisuje svojim novim izvozom | `data/ohlcv/`, `data/hourly/`, `data/intraday/`, `reports/data/2026-10-14_crypto_manifest.json` |
| `tradingagents_codex_transport.py` | Codex OAuth transport za TradingAgents analizu (`codex exec`, samo čitanje) | stdout |
| `pull_binance_klines.py` | Samo GET: duboka kripto povijest iz javnog Binance arhiva (USDT parovi, od 2017.; dnevni, satni, 5-min, 1-min za BTC/ETH). Bez ključeva | `data/ohlcv/`, `data/hourly/`, `data/intraday/`, `reports/data/2026-10-14_binance_manifest.json` |
| `pull_binance_derivs.py` | Samo GET: Binance funding rate (REST) i arhivski `metrics` (OI, long/short, taker omjer, 5 min) za BTC/ETH/SOL perp. Bez ključeva, novi izlazni fajlovi | `data/derivs/`, `reports/data/2026-10-14_binance_derivs_manifest.json` |

## Kronos lokalna demonstracija

`kronos_mu_demo.py`: izolirani runtime `.runtime/kronos/venv`, službeni upstream u `.runtime/kronos/upstream`; prethodnih 90 MU dnevnih svijeća prognozira sakrivenih zadnjih 10. Graf, prognoza, usporedba i konfiguracija: `reports/research/KRONOS_20261103/MU_MASKED10/`. Nije strategija, signal ni Critic dokaz. Pokretanje: `.runtime/kronos/venv/bin/python scripts/kronos_mu_demo.py`.

## Kronos MU 2026 sekvencijalni test

`kronos_mu_2026.py`: freeze KRONOS_MU_2026_V1, 19 uzastopnih 10-dnevnih prozora, isti model 90/10 bez retraininga. Izlazi `reports/research/KRONOS_20261103/MU_2026_WALKFORWARD/`: sve prognoze, CSV-ovi, audit i interaktivni HTML. Pokretanje `.runtime/kronos/venv/bin/python scripts/kronos_mu_2026.py`. Nije Critic PASS; ne šalje naloge.

## Day Trader offline demonstracija

`day_trader_demo_report.py` crta spremljeni upstream TSLA Time Machine primjer i ugrađuje graf u samostalni HTML. Ulazi/izlazi: `reports/research/DAY_TRADER_20261103/TSLA_DEMO/`. Nije lab backtest ni strategija, ne koristi nove lab cijene, bez naloga. Pokretanje `.runtime/kronos/venv/bin/python scripts/day_trader_demo_report.py`.
