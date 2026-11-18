# Alpaca MCP + CLI inventory (Memory Lab)

**Aktualna provjera 2026-10-06:** vidi [pregled skillova i sustava](../research/ALPACA_SYSTEM_REVIEW.md). Dokumentacijski MCP `alpaca-us` i svih 14 Alpaca skillova instalirani su za Codex, Claude Code, Cursor, Windsurf i OpenCode. HTTP MCP handshake i pretraga rade; klijente treba ponovno učitati. CLI `~/go/bin/alpaca` je v0.0.14 (provjeren --help/version), izvan PATH-a ove sesije. Stanje profila nije ponovno provjeravano.

Donji inventar i tržišne cijene su **povijesna snimka od 2026-10-05**, ne trenutačno stanje.

Generated for Claude Code / Codex / Cloud agents. PAPER only. Do not invent prices; refresh via MCP or CLI.

## Alpaca MCP tools (Grok Bot connector `user-alpaca`)
account: get_account_info, get_account_config, update_account_config, get_account_activities, get_account_activities_by_type, get_portfolio_history
market: get_clock, get_calendar, get_stock_bars, get_stock_latest_bar, get_stock_quotes, get_stock_latest_quote, get_stock_trades, get_stock_latest_trade, get_stock_snapshot, get_most_active_stocks, get_market_movers
crypto: get_crypto_bars, get_crypto_quotes, get_crypto_trades
options: get_option_contract, get_option_contracts
assets/news: get_all_assets, get_asset, get_news, get_corporate_action_announcement(s)
watchlists: get_watchlists, get_watchlist_by_id, create_watchlist, update_watchlist_by_id, delete_watchlist_by_id, add/remove_asset
docs: list_alpaca_api_endpoints, search_alpaca_docs, fetch_alpaca_doc, get_alpaca_endpoint_docs, search_alpaca_api_specs


## Alpaca CLI
Binary: ~/go/bin/alpaca (installed). Status 2026-10-05: NO profile — run `alpaca profile login` (paper) once on Mac.
Commands: calendar, clock, data, locate, option, order, position, account, asset, corporate-action, wallet, watchlist, api, doctor, profile, update, version.
Agenti nikad ne šalju ni paper ni live naloge; iznimke vrijede samo za aplikaciju prema AGENTS.md.


## Paper account (Alpaca MCP, 2026-10-05 ~18:49 CE(S)T / market OPEN)
- Account: PA3GJDYHAQAV (paper), status ACTIVE, equity $100000, cash $100000, buying_power $400000, multiplier 4, shorting_enabled true, positions $0
- Clock: is_open true; next_close 2026-10-05 16:00 ET; next_open 2026-10-06 09:30 ET

## Snapshots (latestTrade ≈ last)
| Ticker | Last | Day open | Prev close | Day range |
|--------|------|----------|------------|-----------|
| MU | 1068.18 | 1069.02 | 1074.71 | 1055.75–1074.78 |
| WDC | 442.59 | 429.79 | 415.37 | 429.53–447.54 |
| STX | 892.24 | 877.50 | 848.78 | 875.42–902.87 |
| SMH | 631.22 | 631.31 | 630.63 | 627.30–632.19 |
| AMAT | 536.25 | 540.50 | 540.03 | 533.72–545.31 |
| LRCX | 344.30 | 346.87 | 347.46 | 341.72–351.37 |
| KLAC | 203.71 | 205.18 | 206.71 | 199.62–206.37 |

## OHLCV CSVs on disk
data/ohlcv/{MU,WDC,STX,SMH,AMAT,LRCX,KLAC}_1d.csv — MU/WDC/STX/SMH verified 2704 bars 2016-01-04→2026-10-05 (split-adjusted).


## Agent workflow
1. Read `PRIOR_ART.md` + `reports/gate/` (`approved_list` empty → no KUPI).
2. Nova hipoteza zahtijeva novi freeze ID; zatvorene FAIL linije ne oživljavati.
3. Backtest with walk-forward + costs; Critic gate; only then Signal call.
4. HR tax notes = orientation only.


## Claude Code MCP (spojeno 2026-10-05)

Server `alpaca` (`uvx alpaca-mcp-server`) registriran je na korisničkoj razini (`~/.claude.json`), paper račun.

- Ključevi su i u lokalnom `.env` (nije u repou, `.gitignore` ga isključuje, prava 600). Varijable: `ALPACA_API_KEY`,
  `ALPACA_SECRET_KEY`, `ALPACA_ENDPOINT`, `ALPACA_PAPER_TRADE=true`.
- `ALPACA_TOOLSETS=account,assets,stock-data,corporate-actions,news`: namjerno **bez** `trading`, pa agent tehnički
  ne može slati naloge ni zatvarati pozicije. Pravilo laba (paper only, bez naloga) tako vrijedi i na razini alata.
- Za dodatne alate (npr. `watchlists`, `options-data`) promijeni `ALPACA_TOOLSETS` i ponovno pokreni Claude Code.
- Uključivanje `trading` je Petrova izričita odluka i traži izmjenu `AGENTS.md`.
- Ključevi se nikad ne ispisuju niti spremaju u dokumente. Provjera: `claude mcp list`.
- Novi alati učitavaju se u sljedećoj sesiji.

### Codex CLI

Isti server je dodan i u Codex (`codex mcp add alpaca ...`, globalno, ista ograničena lista toolseta bez `trading`).
Provjera: `codex mcp get alpaca`. Uklanjanje: `codex mcp remove alpaca`. Novi alati se učitavaju u sljedećoj Codex sesiji.
