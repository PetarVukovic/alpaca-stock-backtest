# Kripto day trading: rezultat (2026-10-14)

Završni dokument za `PROMPTS/crypto_daytrading_brief.md`. Samo istraživanje. Bez naloga. **Nije lab Critic PASS**, `approved_list` ostaje prazan, signal **PRIČEKAJ**.
Dostupnost kripta kod IBKR-a za Petra (HR, MiCA): **nepotvrđeno**. Podaci su Binance USDT spot barovi.

## Kratki odgovor

1. **Intraday day trading koji radi nakon troškova nismo našli.** Sve tri intraday hipoteze (H3, H4, H5) padaju i bruto zarada po tradeu ostaje ispod praga isplativosti od 20 bps.
2. **Preživio je spori trend, ne day trading:** long-only Donchian ansambl na 4h barovima (BTC, ETH, SOL). Medijan držanja je 5 dana. U AI eri (2023-01 do 2026-10-09) zarađuje manje od kupi-i-drži, ali uz oko trećinu drawdowna.
3. Dokaz je skroman. Deflated Sharpe uz K ≥ 518 je 33–40 %: **statistički ne možemo tvrditi pravi edge nad nulom**, samo da je smanjivač rizika u ovom uzorku bio koristan.
4. Ništa ovdje nije dokaz da će raditi unaprijed. Prije ikakve primjene treba potvrditi dostupnost instrumenta i proći formalni lab Critic.

## Što je napravljeno

- Literatura i open source (`CRYPTO_DAYTRADING_LITERATURE.md`): nema verificiranog neto intraday long-only edgea nakon 2022; samo spori trend ima objavljene neto brojke.
- Novi podaci: Binance funding i 5m metrics (OI, taker omjer), `data/derivs/` (poznati problemi u `DATA_NOTES.txt`; 2022 loše pokrivena).
- Pred-registracija prije testa (`CRYPTO_DT_PREREGISTRATION.md`, SHA-256 u `STRATEGY_CANDIDATES.md`), jedan zamrznuti run po ID-u, pa **neovisni adversarijalni pregled** (codex-a, `reports/runs/codex_cdt_review.md`) koji je nezavisno rekonstruirao rezultate (razlika ≤ 1e-12 postotnih bodova).
- Pregled je našao stvarne greške; popravljene su ili priznate u `CRYPTO_DT_PREREGISTRATION_AMENDMENT_1.md` (vidi odjeljak "Što je pregled srušio").

## Rezultati po ID-u (10 bps po strani, split IS 2021–22 / WF 2023–24 / HO 2025+)

| ID | Ideja | WF | HO | Tradeova (IS/WF/HO) | Bruto po tradeu (WF+HO) | Ishod |
|----|-------|----|----|---------------------|-------------------------|-------|
| CDT_H1_TREND_4H | 4h Donchian 20/40/80, vol-skaliran | +149,3 % | +12,6 % | 125 / 108 / 114 | 340 bps | **zadovoljava kriterije** |
| CDT_H1B_TREND_4H_NOVOL | isto bez vol skaliranja | +232,7 % | +0,7 % | 125 / 108 / 114 | 340 bps | zadovoljava kriterije; HO tanak, pri 2× trošku HO −6,3 % |
| CDT_H2_TREND_4H_CROWD | H1 + funding/OI "gužva" filter | +161,1 % | +14,8 % | 126 / 127 / 137 | 304 bps | **nevaljan kao replikacija** (pogrešno implementiran percentil), zamijenjen s H2Q |
| CDT_H2Q_TREND_4H_CROWD_QTL | isto, pravilo doslovno kao registrirano | +153,2 % | +14,7 % | 136 / 179 / 166 | 228 bps | zadovoljava kriterije; filter djeluje na 1–2 % barova |
| CDT_H3_UTC2123_COND | uvjetni prozor 21–23 UTC | −0,8 % | −1,1 % | 129 / 105 / **15** | 15,6 bps | pada (negativno, HO premalo tradeova) |
| CDT_H4_ID_MOM_VOL | intraday momentum + volumen | −4,4 % | −11,9 % | 144 / 283 / 186 | 9,4 bps | pada |
| CDT_H5_BTC_LEAD_5M | lead-lag BTC → ETH/SOL na 5m | −44,7 % | −33,1 % | 772 / 638 / 478 | 2,3 bps | pada, 2× trošak −88 % |

Razlog pada intraday: bruto očekivanje po tradeu (15,6 / 9,4 / 2,3 bps) je ispod break-evena od 20 bps. To je ono što je literatura predviđala, nije iznenađenje.

## Što je preživjelo, s brojkama (H1, vodeći kandidat)

AI era (2023-01-01 do 2026-10-09), uz pravi kupi-i-drži (fiksne jedinice, jednak početni kapital u tri coina) kao usporedbu:

| | H1 | Kupi i drži (BTC+ETH+SOL) |
|---|---|---|
| Ukupno | +180,7 % | +497,6 % |
| CAGR | 31,5 % | 60,7 % |
| Najveći drawdown | −21,9 % | −70,4 % |
| Calmar | 1,44 | 0,86 |

- **Primjer u eurima:** 1.000 € uloženo 2023-01-01 u H1 bilo bi oko **2.807 €** (prije poreza, bez tečaja EUR/USD, uz 10 bps po strani); kupi-i-drži oko **5.976 €**, ali uz pad od 70 % (iz npr. 5.000 € na ~1.500 €). H1 u najgorem trenutku gubi oko 22 % s vrha.
- **2025+ (holdout):** H1 +12,6 %, kupi-i-drži oko −26,8 % (iz pregleda, split-resetirani koš). H1 je tu bolji i po povratu, ali je to jedno razdoblje.
- **Primjer jednog tradea:** BTC, ulaz 2024-01-26 12:00 UTC na ~41.290 USDT, izlaz 2024-03-17 00:00 UTC na ~65.301 USDT, +58 % na cijeni (bez troškova prilagodbe). Samo 31 % tradeova je dobitnih; zarada dolazi od nekoliko velikih trendova. Medijan držanja je 5 dana.
- **Stres troškova (WF+HO ukupno):** 1× +180,7 %, 1,5× +162,4 %, 2× +145,3 %, 3× +114,4 %. Pomak parametara ±20 % (po jedan parametar): 12 od 12 susjeda pozitivno.
- **Što H1 zapravo radi:** prosječno je uloženo oko 35 % kapitala u WF+HO. To je filter trenda koji izlazi iz rizika u padovima, a ne pojačivač povrata.
- **Statistika:** PSR (AI era) 0,99, ali Deflated Sharpe 0,33 uz K = 518, PBO 0,27. Uz toliko isprobanih ideja u ledgeru, ne možemo isključiti da je dio rezultata sreća.
- Oznaka "smanjivač vremena u tržištu" = točna: manji povrat od kupi-i-drži, veći Calmar, manji drawdown.

Varijante H1B i H2Q daju sličnu sliku (AI era +235 % odnosno +191 %, drawdown −28,5 % odnosno −21,7 %). Vol skaliranje (H1 vs H1B) smanjuje povrat WF, ali bitno popravlja HO (+12,6 % vs +0,7 %) i drawdown. Filter funding/OI (H2Q) gotovo ne mijenja ništa (djeluje na 1–2 % barova), pa nema dokaza da pomaže.

## Što je pregled srušio (poštena lista)

1. **H2 nije provodio registrirano pravilo** (rang umjesto percentila vrijednosti; za ponovljene funding vrijednosti to nije isto). Popravljeno novim ID-om H2Q; H2 se ne koristi kao dokaz. Pregled je izvijestio brojke ispravljene varijante prije H2Q runa, pa H2Q nije potpuno nezavisan od te informacije.
2. **Referenca "kupi i drži" iz `core.py`** nije kupi-i-drži, nego jednako ponderirani koš rebalansiran na svakom baru bez troška. Zamijenjena pravom usporedbom (gornja tablica). Oznaka "smanjivač vremena u tržištu" sad se računa prema pravom kupi-i-drži; H1 zaostaje u povratu.
3. **"Ex-top3" na neponderiranim tradeovima** ne prati uloženi kapital; dodan je kriterij na doprinosu portfelju. Oba prolaze za H1, H1B, H2, H2Q.
4. **Bruto bps otvorenih tradeova** bio je precijenjen za 10 bps; ispravljeno (brojke gore su ispravljene).
5. Tolerancija starosti OI snimke dopuštala je 20 min umjesto 15 (jedna pojava u 2021, ne utječe na WF/HO); ispravljeno u H2Q.
6. **Čekaju ograničenja:** jedan bar kašnjenja izvršenja daje H1 WF +133,0 % / HO +8,9 % i H1B HO −3,5 %. PBO i DSR ne uzimaju u obzir serijsku ovisnost. Univerzum BTC/ETH/SOL je preživjeli. Dry-run interno računa i WF/HO (ispisuje samo strukturu). Jednakost "jedan run po ID-u" potvrđuju hashevi, ne dokazuje je kronologija.

## Poštena presuda

- **Day trading u smislu intraday (1m–1h) long-only taker strategije koja zarađuje nakon troškova u AI eri: nije pronađen.** Literatura i testovi se slažu.
- **Najbolja bliska alternativa:** spori trend (4h, držanje danima) kao alat za kontrolu drawdowna. Zarađuje manje od kupi-i-drži u povratu, ali uz otprilike trećinu pada. Dokaz je slab (DSR 0,33–0,40), pa je to hipoteza za dalje praćenje, ne odobrena strategija.
- Za Petrovu sklonost riziku vrijedi da je kupi-i-drži u ovom uzorku nadmašio sve, uz 70 % pad. Odluka što je prihvatljivo je Petrova.

## Isporuke (po brief točki 5)

| Što | Gdje |
|-----|------|
| Zamrznuti JSON | `strategies/frozen/2026-10-14_CDT_*.json` (7 komada) |
| results.json + 6 grafova po ID-u | `reports/research/CRYPTO_DT_20261014/{ID}/` |
| Pine v6 (H1), kompilira (`pine_check`) | `scripts/tradingview/CDT_H1_TREND_4H.pine` (H1B: postavi vol target na 0) |
| Kod i testovi | `lab/crypto_dt/`, `tests/crypto_dt/` (15 testova uzročnosti) |
| Neovisni pregled | `reports/runs/codex_cdt_review.md` |

Pine skripta je replika jednog coina na 4h grafu (svaki coin zasebno), ne cijelog portfelja; ponašanje nije uspoređeno trade po trade s lab motorom.

## Sljedeći koraci (traže Petrovu odluku)

1. **Formalni lab Critic za H1 je pokrenut: FAIL** (`reports/gate/2026-10-14_CDT_H1_TREND_4H_VERDICT.md`). Pale provjere 10 (Deflated Sharpe p = 0,9975, PBO 0,70), 11 (Monte Carlo pad trgovina, ograničenje: Critic gleda trgovine na 100 % kapitala), 13 (holdout: 0,04 % po trgovini, bez 3 najbolje −0,96 %) i 14. Provjere 0–9 i 12 prolaze. Time je zaključak iz ovog dokumenta stroži: spori trend nije dokazan edge, samo opis rizika u uzorku. `approved_list` ostaje prazan. Ako te zanima dalje, to je novi ID (drugi horizont ili sastav), ne popravak H1.
2. **Provjera instrumenta:** ima li IBKR kripto (ili kripto ETP na europskoj burzi) za HR rezident, i s kojim troškom. Bez toga nema smisla ići dalje (pravilo iz `AGENTS.md`).
3. **Ako ipak želiš intraday:** jedini preostali smjer je maker izvršenje (H6) s modelom fillova iz aggTrades trake. Literatura upozorava na adverse selection, pa je to zaseban istraživački projekt s niskim priorom, ne brzi test.
4. Ledger K je zajednički s drugim agentima (pri ovom runu 533); Deflated Sharpe treba računati s aktualnim K.
