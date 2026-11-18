# ML track — odvojena pravila (Memory Lab)

ML je **paralelni research track**, ne prečac do Signala.  
Rule-based C# / H# i dalje prolaze isti gate: freeze → WF → Critic → `approved_list` → Signal.

## Hard rules

1. **Walk-forward only** — nema full-sample “optimizacije pa report”. Nema look-ahead u labelama ni u featureima.
2. **Features must be lagged** — na baru *t* smiju ulaziti samo podaci dostupni na *t−1* (ili strogo zatvoreni bar).
3. **Train only on IS** — fit / hyperparametri samo na in-sample. Evaluacija na WF, zatim holdout (jednom).
4. **Never auto-trade** — model output ≠ order. Potreban **Critic PASS** + ID na **`approved_list`** prije bilo kojeg Signal KUPI.
5. Paper Alpaca only. Prazan `approved_list` → PRIČEKAJ.

## Universe

| Prioritet | Tickers | Napomena |
|-----------|---------|----------|
| **Primary** | **MU, WDC, STX** | Dovoljno duga povijest (~2016→) za IS/WF/HO |
| Context | AMAT, LRCX, KLAC, SMH, SIMO, RMBS | Feature / regime context, ne primarni target |
| **Ne primary za ML** | DRAM peers kratke povijesti, **SKHY**-like / kratki add-oni, **SNDK** | Premalo podataka za stabilan WF; ne koristiti kao ML primary |

## Starter plan

1. **sklearn baseline** — logistic (ili ridge) na **lagged** return/vol featureima (npr. ret_1d…ret_20d, vol_10/60), target = forward N-day znak/prinos s jasnim horizon lagom.
2. Isti cost model i split kao rule-based lab.
3. Critic checklist (n, Sharpe vs B&H, maxDD, concentration, IS→WF sign flip) — isti kao za C#.
4. Tek ako baseline preživi: opcionalno **qlib** / **FinRL** (`OSS_SHORTLIST.md`), i dalje bez auto-trade.

## Zabranjeno

- Train na cijelom uzorku pa “WF” samo za show
- Feature iz istog bara kao label (leak)
- KUPI iz notebooka / model.predict bez Critic + approved_list
- Tvrđenje da je ML edge dok je status RESEARCH / FAIL-like
