# Dokumentacija

Indeks svega u `docs/`. Redoslijed čitanja za nekoga tko prvi put otvara projekt:
**overview → pipeline → data → backtest → Critic → signal**.

## architecture/ — kako lab radi

| Dokument | Tema |
|----------|------|
| [overview.md](architecture/overview.md) | Cijela slika: komponente, tok podataka, uloge agenata |
| [pipeline.md](architecture/pipeline.md) | Lanac od šest koraka (freeze → backtest → Critic → signal) |
| [data.md](architecture/data.md) | Izvori, pravila, WDC spin-off, satni podaci, validacija |
| [backtest.md](architecture/backtest.md) | IS / WF / HO, troškovi, K i Deflated Sharpe |
| [signal.md](architecture/signal.md) | Kako nastaje KUPI / PRIČEKAJ / NE KUPUJ |
| [layout.md](architecture/layout.md) | **Obavezan raspored datoteka** i imenovanje |
| [contracts.md](architecture/contracts.md) | Zajednički ugovori između traka tima (modeli, tok) |
| [roadmap.md](architecture/roadmap.md) | Uloge agenata i plan (izvorni dokument) |
| [c13c_auto_app.md](architecture/c13c_auto_app.md) | Ugovor traka za auto-način C13C u aplikaciji (paper) |

| [swing_parity.md](architecture/swing_parity.md) | Usklađenje swing pravila, veličine računa i ograničenja TradingView replike |
| [local-production.md](architecture/local-production.md) | Opseg lokalnog učvršćivanja aplikacije i kriteriji provjere |

## critic/

| Dokument | Tema |
|----------|------|
| [CRITIC_CRITERIA.md](critic/CRITIC_CRITERIA.md) | Poredani gate, predložak verdikta (pragovi potvrđeni 2026-10-05) |

## guides/ — kako nešto napraviti

| Dokument | Tema |
|----------|------|
| [setup.md](guides/setup.md) | Python okolina, ključevi, pokretanje sesija |
| [new-hypothesis.md](guides/new-hypothesis.md) | Korak po korak: nova hipoteza od ideje do verdikta |
| [alpaca.md](guides/alpaca.md) | Alpaca MCP i CLI (samo paper) |
| [alpaca-inventory.md](guides/alpaca-inventory.md) | Popis svega što imamo za Alpacu (MCP, CLI, REST klijent) i provjerene činjenice API-ja (2026-10-06) |
| [rezultati-za-pocetnike.md](guides/rezultati-za-pocetnike.md) | Što smo otkrili: rezultati testiranja za početnika, korak po korak |
| [regulation-eu-hr.md](guides/regulation-eu-hr.md) | Trgovanje iz Hrvatske: EU pravila i što paziti prije live tradinga |
| [app-autostart.md](guides/app-autostart.md) | Autostart aplikacije na Macu (launchd): instalacija, provjera, zapisi, uklanjanje |

## research/ — istraživanje i alati

| Dokument | Tema |
|----------|------|
| [OSS_SHORTLIST.md](research/OSS_SHORTLIST.md) | Python stackovi (vectorbt, backtesting.py, qlib, ...) |
| [CRYPTO_DAYTRADING_LITERATURE.md](research/CRYPTO_DAYTRADING_LITERATURE.md) | kripto day trading: literatura, open source, dostupni podaci, prijedlog hipoteza (2026-10-14) |
| [CRYPTO_DT_PREREGISTRATION.md](research/CRYPTO_DT_PREREGISTRATION.md) | kripto day trading: unaprijed zamrznute hipoteze, kriteriji i pravila (2026-10-14) |
| [CRYPTO_DT_PREREGISTRATION_AMENDMENT_1.md](research/CRYPTO_DT_PREREGISTRATION_AMENDMENT_1.md) | amandman: H2 pravilo doslovno, ispravci dijagnostika nakon neovisnog pregleda |
| [CRYPTO_DAYTRADING_RESULT.md](research/CRYPTO_DAYTRADING_RESULT.md) | kripto day trading: završni rezultat, što je palo, što je preživjelo, presuda (2026-10-14) |
| [SKILLS_SHORTLIST.md](research/SKILLS_SHORTLIST.md) | Instalirani open-source skillovi, izvori i vetting |
| [ML_TRACK.md](research/ML_TRACK.md) | Pravila za paralelni ML track |
| [DATA_INVENTORY.md](research/DATA_INVENTORY.md) | Što lab lokalno ima: cijene, satni podaci, vijesti, događaji (generirano) |
| [ALPACA_CAPABILITIES.md](research/ALPACA_CAPABILITIES.md) | Što Alpaca CLI, API i MCP stvarno daju na ovom računu (izmjereno) |
| [OSS_SCOUT_2026-10.md](research/OSS_SCOUT_2026-10.md) | Izvidnica otvorenog koda: memory-ciklus podaci, event/news pristupi, alati za validaciju, EU/HR kontekst |

| [MEMORY_SWING_UNIVERSE_20261006.md](research/MEMORY_SWING_UNIVERSE_20261006.md) | Memorijski proizvođači, dostupnost povijesti i opis AI razdoblja |
| [ALPACA_SYSTEM_REVIEW.md](research/ALPACA_SYSTEM_REVIEW.md) | Alpaca skillovi: provedene dorade i prioriteti prije stvarnog novca |

## news/

| Dokument | Tema |
|----------|------|
| [NEWS_PIPELINE.md](news/NEWS_PIPELINE.md) | Kako vijesti ulaze u lab bez gledanja u budućnost |
| [H-N2_SKHY_PRACENJE.md](news/H-N2_SKHY_PRACENJE.md) | Praćenje SKHY → MU (samo opis) |

## team/ — AI tim

| Dokument | Tema |
|----------|------|
| [BRIEF.md](team/BRIEF.md) | Brief tima: pravila, trake, vlasništvo nad datotekama, redoslijed |
| STATUS_A.md, STATUS_B.md, STATUS_C.md | Stanje svake trake (ažuriraju trake) |
| [ORCHESTRATOR.md](team/ORCHESTRATOR.md) | Poruke glavnog (Claude) trakama: ugovori, zadaci, zamrznute strategije |

## Ostalo

- [glossary.md](glossary.md): rječnik pojmova.
- Pojednostavljeno objašnjenje za početnike postoji kao zasebna stranica izvan repoa (artefakt).

## Kako se dokumentacija održava

- Jedna tema = jedan dokument. Ne dupliciraj, nego linkaj.
- Pravila projekta žive samo u `AGENTS.md`. Ovdje se objašnjava **kako** i **zašto**, a ne uvode se nova pravila.
- Kad promijeniš put ili ime datoteke, pretraži `docs/` i `AGENTS.md` za staru putanju.


### Forex istraživanje

- [FOREX_2026-10-13.md](research/FOREX_2026-10-13.md): EUR/USD metodologija, provjereni izvori, rezultati i ograničenja; uz DOCX dokument FOREX_2026-10-13.docx. Nije odobrenje trgovanja.

- [TradingAgents uz C13C](guides/tradingagents.md) — zasebne informativne AI analize.
