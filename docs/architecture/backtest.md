# Backtest

## Redoslijed

1. **Freeze:** pravila ulaza, izlaza i veličine zamrznuta u `strategies/frozen/`, ID u `STRATEGY_CANDIDATES.md`.
2. **Ledger:** upiši pokušaj (K raste). Izvor K: `trading-lab/ledger/trials.jsonl`.
3. **WF + troškovi:** izvještaj ide u `reports/backtest/`.
4. **Critic:** verdikt u `reports/gate/`, kriteriji u [`../critic/CRITIC_CRITERIA.md`](../critic/CRITIC_CRITERIA.md).
5. Samo PASS ide u `approved_list.json`.

## Razdoblja

| Razdoblje | Godine | Uloga |
|-----------|--------|-------|
| IS (in-sample) | 2016–2020 | Pravilo se smije osmisliti i podesiti |
| WF (walk-forward) | 2021–2023 | Samo provjera, bez dorade |
| HO (holdout) | 2024 → | Zadnji ispit, otvara se jednom |

Holdout od 2024. obuhvaća veliki memorijski boom (2025–2026). Zato jak holdout bez čistog WF-a vrijedi malo.

## Troškovi

- **MU:** 5 bps round trip + 1 tick po strani.
- **Peers i tanki tickeri** (MRAM, ACMR, kratka povijest): stroži stres.
- Critic dodatno traži da rezultat preživi 2× trošak.

## Zastavice u izvještajima

n < 10 po razdoblju, promjena predznaka IS → WF, Sharpe ispod buy-and-holda, maxDD, koncentracija zarade u
top-3 trgovine. Zastavica ne znači automatski FAIL, ali ulazi u Critic.

## K i Deflated Sharpe

K je broj isprobanih pravila u kampanji (trenutno oko 46). Što je veći, to je veća šansa da je dobar rezultat
sreća. Zato sirovi Sharpe nikad nije dokaz PASS-a, nego se korigira (Deflated Sharpe, PBO).

## Što je zatvoreno

RSI / C10 familija je **zatvorena** nakon C10b FAIL-a (nema C10c). Popis svega što se ne oživljava je u
`AGENTS.md` ("What NOT to touch") i `PRIOR_ART.md`.

## Alati koji pomažu (savjetodavno)

Mapa korak → skill je u `AGENTS.md`, a izvori u [`../research/SKILLS_SHORTLIST.md`](../research/SKILLS_SHORTLIST.md).
Rezultat alata ili skilla nikad nije Critic PASS.
