# Poruke orkestratora (Claude) trakama

## Za traku A (Codex), 2026-10-05 23:10

1. **Ugovor dopunjen:** `FrozenStrategy.timeframe` sada prima `"5min"` (odobreno). Nemoj označavati 5-minutni test kao satni.
2. **Zamrznuto 19 strategija** u `strategies/frozen/2026-10-05_*.json` (baseline B1–B3, C13A–C, C14A–B, C15A–C, C16A–B, C17A–B, C18A, C20A, H4A–B). Sve prolaze `validate_strategy`. Pokreni `lab/run_all.py` na svima, **uključujući HO**, na svim tickerima iz `universe`, i napiši `reports/backtest/*.md|json` i `LEAGUE_TABLE.md`. Svaki ID je jedan pokušaj u ledgeru (K).
3. **Novi tip pravila koji tražim** (iz istraživanja, `reports/research/day_behaviour.md`): `open_reversal` za 5-min ili satne podatke: dugi ulaz u 10:00 ET samo ako je prvih 30 min dana bilo ≤ −X % (zadano 0.5 %), izlaz na zatvaranju sesije, uz stop. Samo WDC i STX. Dodaj u registar i README; ja ću zamrznuti `H5A_OPEN_REVERSAL` (najviše 3 varijante: X = 0.5 %, 1 %).
4. **Za Critic** (`lab/critic/`, gotov, 15 testova) treba mu iz `run_all` po strategiji: povrati po trgovini za IS/WF/HO po tickeru, isti rezultat pri 2× troškovima, rezultat osjetljivosti ±20 % (pomak parametara za 20 % gdje ima smisla), matrica povrata varijanti na zajedničkoj osi (za PBO), K iz ledgera, izvještaj o lookahead (truncation) testu. Implementiraj izlaz u `reports/backtest/{ID}_{TICKER}.json` u formatu `BacktestResult` + dodatno polje u zasebnoj datoteci `reports/backtest/{ID}_critic_inputs.json` (shemu opiši u `lab/strategies/README.md`). Ugovor ne mijenjaj, nego novu datoteku.
5. `scripts/pull_alpaca.py` dodaj u `scripts/README.md` (opis u jednoj rečenici).
6. Kad završiš, napiši `## POVRATAK` u `docs/team/STATUS_A.md`.

## Za traku A (Codex), 2026-10-06 00:20: ML baseline

Pročitaj `docs/research/ML_TRACK.md` (pravila su obavezna: walk-forward, lagirani featurei, treniranje samo na IS, nikad auto-trade).
1. Napravi **jednu** unaprijed deklariranu ML hipotezu `ML1_LOGIT_5D` (K +1): logistička regresija (sklearn nije instaliran: instaliraj `scikit-learn` u `.venv` i dodaj ga u `requirements.txt`, ili koristi statsmodels Logit), featurei samo lagirani (ret_1d, ret_5d, ret_20d, vol_10/vol_60, udaljenost od 200-d prosjeka), cilj je predznak 5-dnevnog budućeg prinosa s razmakom (purge 5 dana). Treniranje samo na IS (2016–2020). Prag signala fiksiran unaprijed (p > 0,55), long-only, 1 pozicija ≤ 500 USD, izlaz nakon 5 dana, isti troškovi kao ostalo. MU, WDC, STX.
2. Implementiraj kao novi tip ulaza `ml_logit` u registar (README), zamrznuti JSON ne pišeš ti nego ga napiši u `strategies/frozen/2026-10-06_ML1_LOGIT_5D.json` (iznimka za ovaj jedan ID; hipotezu i mehanizam napiši na hrvatskom: 'kratkoročni zamah i kolebanje donose slabu naznaku smjera').
3. Pokreni `lab.run_all --ids ML1_LOGIT_5D`, generiraj BacktestResult i critic_inputs paket. HO se gleda jednom.
4. Dodaj u `reports/backtest/ML1_REPORT.md` (hrvatski, za početnika) što model radi, koliko je preciznost naspram 50 % (bacanje novčića), i je li išta preživjelo troškove.
5. Testovi (`tests/engine`) i ruff za svoju traku, pa `## POVRATAK 3` u `STATUS_A.md` i stani.

## Za traku A (Codex), nakon ML1: ispravci iz red-team audita (`reports/research/redteam.md`)

Stroj je neovisno reproduciran bez razlike. Treba ispraviti tumačenje i dva pravila (ne mijenjaj rezultate zamrznutih ID-eva osim gdje je dolje izričito rečeno):
1. **Ligaška tablica** (`lab/run_all.py` oko 87–101 i 511–540): uz "WF prosjek po trgovini" dodaj stupce **WF ukupna promjena računa (%)**, **udio vremena u tržištu (%)**, **kupi-i-drži za isto razdoblje i iste troškove**, **broj trgovina**. Ne rangiraj B1/B3 (jedna trgovina od 3 godine) zajedno s day tradeom; B1/B2/B3 označi kao "MJERILO". Sortiraj po WF ukupnoj promjeni računa, a ne po prosjeku po trgovini. Tekst "istraživački kandidat" ne smije ovisiti samo o Sharpeu: dodaj uvjet n ≥ 10 i predznak u svim razdobljima, i ujedini oznake za strategije s identičnim trgovinama (B2 i C20A na WDC).
2. **Skraćeni dani** (`lab/engine.py` 137–140 i satni CSV): barovi 13:00–16:00 ET na dane ranog zatvaranja nisu redovni. Uzmi kraj sjednice iz kalendara ili `session_end` 5-min podataka, ne prodaji day trade po cijeni nakon zatvaranja i broji takve dane u `flags`. Ponovno pokreni H4A, H4B (K se ne povećava za isti ID, ali hash se mijenja zbog ispravka: zabilježi to u README i ledger kao 'engine fix', ne kao novi pokušaj).
3. **gap** (`registry.py` 228–230): dokumentiraj u README da se gap mjeri od otvaranja u 10:00 ET (prvi redoviti satni bar), ne od 9:30.
4. **Zaštita** (`engine.py:115`): dokumentiraj da je sidro ulazna cijena s troškom.
5. **K** u svim paketima mora biti trenutni K iz ledgera (ne vrijednost u trenutku pokretanja); ROTATION mjerilo neka bude jednaka košarica istih datuma.
6. Nakon ispravaka pokreni `lab.run_all` za sve ID-eve, `pytest`, `ruff` za svoju traku; javi u `## POVRATAK 4` s razlikama prije/poslije (stvarni brojevi).
