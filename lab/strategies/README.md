# Registar pravila — REGISTAR OBJAVLJEN

Signal koristi zatvoren bar; kupnja je tek na sljedećem otvaranju. Kao narudžba nakon čitanja jelovnika: ne možeš naručiti prije nego što si ga pročitao. Svi postoci u pravilima su razlomci: 0.05 znači 5 %.

## Ulaz: entry.type

| Tip | Parametri i značenje |
|---|---|
| buy_hold | Kupi jednom i drži do granice razdoblja. |
| equal_basket | Jednake trećine MU/WDC/STX, ukupno najviše 500 USD. Samo dnevno i exit.type=hold. |
| trend | trend_window=200; zatvaranje iznad prosjeka. |
| dip_in_trend | trend_window=200, dip_bars=5, dip_pct=0.05; pad dok je iznad prosjeka. |
| breakout | lookback=63; zatvaranje iznad prethodnih najviših cijena. |
| relative_strength | lookback=63; bira najjačeg iz universe, samo pozitivan rast. run_all računa i ROTATION: jedan zajednički novac i najviše jedna dionica u trenutku. Pojedinačni rezultat po tickeru ostaje samo zaseban dio portfelja. |
| leader | leaders=[AMAT,LRCX,KLAC], lookback=63, min_return=0, trend_window=200; vođe rastu, dionica iznad prosjeka. |
| earnings | Samo potvrđeni earnings_MU događaji; signal na zatvaranju dana reakcije, nikada povijesni podatak o kasnijoj zaradi. |
| event | Obavezni event_type, odabran prije testa; us_reaction_date i verified=yes. |
| volatility_breakout | vol_window=20, lookback=63, compression=0.8; stišavanje pa proboj. |
| volatility_shock | vol_window=20, lookback=63, shock_multiplier=2, trend_window=200; šok i pad u trendu. |
| day_trade | Satno; mode=first_hour/last_hour/gap, gap_pct=0.01. „Prvi sat” ovdje je prvi čisti sat 10–11 ET, ne miješani 9–10 bar. |

## Izlaz: exit.type

hold drži do kraja razdoblja; trend/rule izlazi na sljedećem otvaranju nakon zatvaranja ispod trend_window (zadano 200). Kod relative_strength rule znači prestanak vodstva.
risk koristi stop_pct, target_pct i/ili hold_bars; time traži hold_bars; trailing traži trailing_pct.
Zaštita koja preskoči cijenu pri otvaranju izvršava se po lošijem otvaranju. Ako su cilj i zaštita dodirnuti u istom baru, računa se zaštita.
Trailing koristi vrh iz prethodnih barova, a novi vrh vrijedi od sljedećeg bara.
size_vol_target u entry smanjuje ulaganje prema kolebanju zadnjih 20 povrata; nikada ne povećava iznad 500 USD.

## Primjeri oblika za traku C

Osnovna linija: entry={"type":"buy_hold"}, exit={"type":"hold"}.
Zaštita prosjekom: entry={"type":"trend","trend_window":200}, exit={"type":"trend","trend_window":200}.
Košarica: entry={"type":"equal_basket"}, exit={"type":"hold"}, universe=["MU","WDC","STX"].

Registar nije zamrznuta hipoteza. Traka C mora dodati novi ID, hipotezu, mehanizam i trajnost te deklarirati do 3 varijante.
Ne koristiti zatvorene RSI/C10/BB ili druge FAIL linije. Rezultat nije Critic PASS.

## Ograničenja

Ugovor prima timeframe="5min". Ne označavati 5-minutni test kao satni.
Satni povijesni feed preskače prvih pola sata. Učitavanje primary satnih CSV-ova sada dopunjuje kraj sjednice iz kanonskih 5-minutnih session_end oznaka.
Cijene su split/spin prilagođene bez dividendi, pa usporedba nije ukupni prinos s dividendama.

## open_reversal (novi tip za traku C)

entry={"type":"open_reversal","drop_pct":0.005}, timeframe="5min", universe=["WDC","STX"], exit={"type":"risk","stop_pct":0.02}.
Treba svih šest barova 09:30–09:55 ET: posljednji se zatvara u 10:00, kupnja je na 10:00 otvaranju. Prednost je tek hipoteza.
Izlaz na zatvaranju službene sjednice; stop može izaći ranije. Satni CSV nema čistih prvih 30 minuta i za taj ulaz javlja grešku.

## Critic paket: {ID}_critic_inputs.json (schema_version=1)

BacktestResult ostaje nepromijenjen. Dodatna datoteka je prijevod za lab.critic.checks.CriticInputs:
- returns i stressed_returns: ticker → IS/WF/HO → lista neto postotaka po trgovini. 2× uključuje i tick i postotni trošak, iz stvarnog ponovljenog stroja.
- portfolio_returns: stvarna zajednička ROTATION ili BASKET trgovina; pojedinačni ticker rezultati su dijelovi portfelja i nisu dodatne istodobne pozicije.
- sensitivity: minus20/plus20 → wf_mean_pct, edge_crushed; svi unaprijed odabrani brojčani parametri pomaknuti zajedno, najviše dvije dijagnostike. Cijeli pomaci i povrati su u sensitivity_diagnostics. Nije optimizacija ni odabir pobjednika.
- trials_matrix: redovi su zajednički trgovinski datumi IS+WF, stupci stvarni zamrznuti ID-evi iste obitelji (C13, C14...). Vrijednosti su dnevni neto razlomci, ne postotci po trgovini. Os i jedinice u trials_matrix_metadata. HO isključen. Jedna varijanta znači null: PBO nije moguće izračunati.
- k: 46 naslijeđenih + jedan redak po novom zamrznutom ID-u. Ponovljeni isti ID i hash ne povećavaju K. Promjena hasha pod istim ID-em je greška. Troškovni stres i dvije unaprijed deklarirane dijagnostike dio su istog pokušaja.
- lookahead_evidence: dva reza stvarnih podataka po tickeru, usporedba signala i vrijednosti portfelja prije zadnjeg prisilno zatvorenog bara, plus pokvareni budući OHLC ×7.
- provenance: hash zamrznute datoteke i cijena. ledger_complete se odnosi na registraciju nove kampanje uz LEGACY_K=46; puni naslijeđeni ledger nije lokalno dostupan.
- embargo_documented=false i authenticity_audit_ok=null: posebni embargo i neovisni završni audit nisu dokazani. To nisu PASS zastavice.
- fill_violations: računalna provjera veličine i količine; ne dokazuje likvidnost ni izvršenje kod brokera.

Za adapter u traci C: returns/stressed_returns pretvoriti u numpy polja, sensitivity u SensitivityResult, matrix u np.array. Dodatna polja su dokazi/metadata, ne argumenti konstruktora CriticInputs.
Ako u dijagnostici nema WF trgovina, srednji prinos je null i osjetljivost nema dokaz; adapter ne smije null zamijeniti profitom.

## Pokretanje odabranih zamrznutih ID-eva

`.venv/bin/python -m lab.run_all --ids H5A_OPEN_REVERSAL_05 H5B_OPEN_REVERSAL_10`
pokreće samo navedene strategije, uz sve njihove tickere, IS/WF/HO i Critic dijagnostike.
Nepostojeći ili prazan odabir je greška. Stariji rezultati se ne pokreću i ne prepisuju;
ligaška tablica se osvježava čitanjem postojećih BacktestResult datoteka.
Sažetak takvog pokretanja je `reports/backtest/RUN_SUMMARY_SELECTED.json`.

## ml_logit — ML1_LOGIT_5D

Dnevni statsmodels Logit, MU/WDC/STX. Pet značajki ret_1d/5d/20d, vol_10/60 i close/SMA200−1 pomaknuto jedan bar. Cilj: smjer za pet dana; prag p>0.55. Standardizacija samo treningom. IS se ocjenjuje godišnjim proširivim treningom iz prethodnih godina, s najmanje 100 redaka. Za WF i HO model se zaključa nakon IS 2016–2020; zadnjih pet trening barova uklonjeno zbog budućeg cilja. maxiter=100; neuspješan model ne daje signal. Jedna pozicija najviše 500 USD po zasebnom testu dionice, bez zajedničkog portfeljnog odobrenja. Exit time hold_bars=5; kupnja i prodaja na idućem otvaranju. Trošak 5 bps RT + 1 tick/side. Osjetljivost hold 4/6 i 2× troškovi koriste samo IS/WF. HO samo jedan osnovni prolaz. Model_diagnostics.json pohranjuje koeficijente, trening granice i točnost smjera, uključujući usporedbu s uvijek-rast prognozom. Točnost nije neto zarada; preklopljeni ciljevi nisu neovisni.

## Ispravci stroja nakon red-team audita

Satni gap koristi otvaranje prvog čistog redovnog bara u 10:00 ET, ne 09:30. Buy-hold ulazi na drugom baru razdoblja. Stop i cilj sidreni su na ulaznoj izvršnoj cijeni s troškom. Satni kraj sjednice preuzet je iz session_end kanonskih 5-minutnih podataka: završna oznaka + 5 minuta. Barovi počevši od zatvaranja izbačeni su; zadnji satni bar prije zatvaranja dobiva session_end. Dani ranog zatvaranja i izbačeni barovi broje se po razdoblju u flags. Nedostatak kalendarskog dokaza za primary znači grešku.

H4 ponovno računamo kao engine fix early_close_v1. Freeze hash ostaje nepromijenjen jer se pravila ne mijenjaju; hash engine.py se mijenja, stari/novi hash zapisani su u engine_fixes unutar postojećeg ledger retka. Time se K ne povećava. Paket k uvijek osvježava trenutni ledger K, dok BacktestResult k_at_run ostaje povijesni podatak. ROTATION mjerilo Sharpe koristi jednaku košaricu na istim datumima. Liga odvaja B1/B2/B3 kao MJERILO, sortira svaku skupinu po ukupnoj WF promjeni, i prikazuje stvarni buy-hold s istim datumima i troškovima.
