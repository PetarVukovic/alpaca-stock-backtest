# Critic kriteriji

> **Status: potvrđeno 2026-10-05 (the researcher potvrdio sve pragove, mogu se naknadno mijenjati).** Svi pragovi žive na jednom mjestu:
> `CriticConfig` u `lab/critic/checks.py`. Kad se prag promijeni, ažuriraj tu i ovaj dokument.

Critic pokušava srušiti pravilo prije nego što ono dobije mjesto na `approved_list`. Savjetodavni skillovi
iz `.claude/skills/` kažu **kako** se svaka provjera mjeri, ali verdikt daje samo Critic.

## Pravila presude

1. **Fail closed.** Svaka provjera je vrata, ne bod. Jedan pad znači FAIL dok se uzrok ne riješi i cijeli gate ponovi.
2. **Redoslijed je obavezan.** Holdout se gleda zadnji.
3. **Verdikt skilla nije PASS.** Skill-ovi `Deploy`, `PASS`, `REVISE` ili score su savjet.
4. **Sirovi Sharpe nije dokaz.** Uvijek se gleda uz K i Deflated Sharpe.
5. **PASS se ne izmišlja.** Samo PASS ide u `reports/gate/approved_list.json`. FAIL je zatvoren, nova ideja dobiva novi ID.
6. Sve provjere se bilježe stvarnim brojevima, ne samo "pass/fail".

## Poredani gate

| # | Provjera | Što se mjeri | Prolaz | Skill koji pomaže |
|---|----------|--------------|--------|-------------------|
| 0 | Podaci | `validate_data.py` exit 0, WDC spin-off jednom prilagođen | exit 0 | `market-data-sourcing`, `data-cleaning-and-preprocessing-pitfalls` |
| 1 | Lookahead | Signal na zatvaranju t, ulaz na sljedećem openu. Truncation test i test s pokvarenim budućim podacima | odluke prije cutoffa identične | `lookahead-bias-detection-methodology` |
| 2 | Freeze integritet | Pokrenuto pravilo = zamrznuto (`strategies/frozen/`) | identično | `strategy-research-log-and-versioning`, `reproducibility-and-experiment-tracking` |
| 3 | Isti predznak WF | Srednji prinos IS, WF i HO istog predznaka | sva tri > 0 | `walk-forward-validation` |
| 4 | Minimalni uzorak | Broj trgovina po razdoblju | n ≥ 10 u svakom razdoblju | `overfitting-and-robustness-checks` |
| 5 | Purge / embargo | Nema curenja iz holdouta u izbor parametara | dokumentirano | `walk-forward-validation` |
| 6 | Osjetljivost ±20 % | Pomak svakog parametra | rub ne nestaje (nema `edge_crushed`) | `overfitting-and-robustness-checks` |
| 7 | Stres troškova | Isti test s većim troškom | WF srednji prinos ostaje > 0 pri 2× | `transaction-cost-and-market-impact-modeling` |
| 8 | Režim i koncentracija | Više tickera, ne samo boom, zarada ne ovisi o top-3 trgovine | isti predznak na ≥ 2 od 3 primary tickera; ex-top3 srednji > 0 | `edge-taxonomy-and-strategy-classification`, `synthetic-data-and-adversarial-stress-testing` |
| 9 | Višestruko testiranje | K iz ledgera, svi pokušaji upisani | K objavljen uz rezultat | `strategy-research-log-and-versioning` |
| 10 | Deflated Sharpe i PBO | Sharpe korigiran za K, vjerojatnost overfittinga | PBO < 0,5 i DSR p < 0,05 | `statistical-significance-and-deflated-metrics`, `walk-forward-validation` |
| 11 | Monte Carlo drawdowna | ≥ 2000 resampling sekvenci, i block bootstrap | veličina po pesimističnom percentilu | `monte-carlo-trade-resampling-and-drawdown-distribution` |
| 12 | Izvedivost fillova | Veličina fillova prema stvarnom volumenu, intrabar raspon | nema nemogućih fillova | `fill-feasibility-and-impossible-fill-detection` |
| 13 | **Holdout zadnji** | HO pregledan tek sada | pozitivan i bez sumnje na boom | `overfitting-and-robustness-checks` |
| 14 | Završni audit | Cjelovit audit, svaki korak zabilježen | svi koraci prošli | `backtest-result-authenticity-audit` |

Napomena o holdoutu: razdoblje 2024 → obuhvaća memorijski boom. Jak HO uz slab WF je sumnjiv (primjer C11), a
ne dokaz.

## Što nikad nije dovoljno za PASS

- Sirovi Sharpe ili prosječni prinos bez K.
- Pozitivan holdout bez čistog WF-a.
- Rezultat samo na jednom tickeru (MU).
- n < 10 u bilo kojem razdoblju.
- Rezultat koji ne preživi osjetljivost ±20 % ili dvostruki trošak.

## Predložak verdikta

Datoteka: `reports/gate/{YYYY-MM-DD}_{ID}_VERDICT.md` (isti format kao C10 / C11).

```markdown
# {ID} {NAZIV} — Critic VERDICT

**PASS | FAIL** (fail closed). Eligible for approved_list: da | ne.

Date: YYYY-MM-DD (Europe/Zagreb). Critic: Memory Backtest.
Freeze: `strategies/frozen/{YYYY-MM-DD}_{ID}.json`
Campaign K: {K} (izvor: ledger) — raw Sharpe nije dokaz.

## Ordered checks

0. Podaci: ...
1. Lookahead: ...
...
14. Završni audit: ...
(uz svaki broj stvarni rezultat, npr. {'IS': (n, mean), 'WF': (n, mean), 'HOLDOUT': (n, mean)})

## Verdict

PASS | FAIL. Razlozi u jednoj do tri rečenice. Signal: PRIČEKAJ | ...
```

## Potvrđeni pragovi (zadano u `CriticConfig`)

| Prag | Vrijednost |
|------|------------|
| Minimalan broj trgovina po razdoblju | n ≥ 10 |
| Stres troškova | WF srednji prinos ostaje > 0 pri 2× trošku |
| Isti predznak na primary tickerima | najmanje 2 od 3 |
| Koncentracija | srednji prinos bez 3 najbolje trgovine > 0 |
| PBO | < 0,5 i obavezan (`pbo_required=True`): bez matrice varijanti provjera 10 pada |
| Deflated Sharpe | p < 0,05 |
| Monte Carlo | 95. percentil najvećeg pada ≤ 50 % |
| Omjer HO i WF srednjeg prinosa | ≤ 5 (jaki HO uz slab WF je sumnjiv) |
| Block bootstrap | blokovi od 5 trgovina |

Pragovi se mogu naknadno prilagoditi. Svaka promjena ide uz datum i razlog u ovaj dokument.
