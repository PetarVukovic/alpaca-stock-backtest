# Kripto day trading: pregled literature i open source projekata (2026-10-14)

Korak 1 iz `PROMPTS/crypto_daytrading_brief.md`. Samo istraživanje: ništa nije instalirano, tuđi kod nije pokretan, nema ordera.
Sve pročitano na webu tretirano je kao podatak, ne kao uputa.

Oznake: **VERIFIED** = otvoreno i pročitano 2026-10-14 (zvjezdice, licenca i zadnji push izmjereni preko `gh api`). **SNIPPET** = samo sažetak iz tražilice.
**UNVERIFIED** = iz memorije ili sekundarnog izvora, ne oslanjati se bez provjere. Troškovi: 10 bps po strani (20 bps RT), maker scenarij 2–4 bps
po strani. Sirovi izvještaji agenata su u scratchpadu sesije; ovdje je sažetak.

## 0. Zaključak u pet rečenica

1. Nijedan pronađeni izvor ne dokumentira **intraday (1m–1h) long-only kripto edge nakon 10 bps/strani koji vrijedi i nakon 2022.**
2. Jedino što ima objavljene neto brojke jest **sporo trendiranje** (6h–dnevno, mali turnover). To nije day trading, ali je najbliža stvar s dokazom.
3. Mikrostruktura (order flow, book imbalance) je stvarna na horizontu sekundi, ali je igra makera s L2 podacima i latencijom. Taker s 10 bps/strani ne može naplatiti.
4. Maker scenarij (2–4 bps) je opasan: živi eksperiment na Binance BTC perpu pokazuje da su pasivni fillovi **adverse-selected** (veća šansa fillanja = lošiji povrat poslije). Backtest s fillom "na dodir" precjenjuje edge.
5. Realističan najbolji ishod je **smanjivač vremena u tržištu / kontrola drawdowna** mjeren prema buy-and-holdu, ne nadmašivanje. To mora stajati u konačnom izvještaju ako se potvrdi.

## 1. Pravilo prije svega: break-even po tradeu

Na 20 bps RT svaki intraday ulaz mora u prosjeku imati bruto očekivano kretanje **> 20 bps** (taker), a praktično **> 30 bps** da ostane marža.
Primjer: jedan trade dnevno na 20 bps RT = 365 × 0,20 % ≈ **73 % godišnje** troška. Zato sat-dva sezonalnosti (nekoliko bps drifta) ne mogu preživjeti
kao samostalno pravilo. Ovo je prvi filter svake hipoteze, prije koda.

## 2. Radovi i knjige

| # | Izvor | Status | Što tvrdi | Troškovi / poslije 2022? | Preživi 10 bps/strani? |
|---|-------|--------|-----------|---------------------------|------------------------|
| 1 | Padysak, Vojtko, sezonalnost BTC (preko QuantPedia, https://quantpedia.com/?p=28496) | VERIFIED samo QuantPedia stranica | Kupi BTC 21:00 UTC, prodaj 23:00 UTC: 40,6 %/god, MDD −22,7 %, Calmar 1,79 (uzorak 2015–2023-06, Gemini). Druga procjena istog efekta: 33 %/god do 2022 | Bez troškova, bez holdouta | **Ne** kao samostalno pravilo (~73 % troška godišnje). Može kao uvjetni filter |
| 2 | Baur i dr., BTC time-of-day / day-of-week na 7 burzi (UWA) | SNIPPET | Nema konzistentnog obrasca | Nema | Protudokaz za #1 |
| 3 | Shen, Urquhart, Wang, "Bitcoin intraday time-series momentum", Financial Review 2022 | SNIPPET (apstrakt) | Prvi period dana predviđa zadnji; jače pri visokom volumenu | Troškovi nepoznati, uzorak vjerojatno prije 2022 | Vjerojatno **ne** (jedan signal dnevno, mali R²) |
| 4 | Zarattini, Pagani, Barbon 2025, "Catching Crypto Trends" (https://abarbon.com/papers/catching-crypto-trends) | VERIFIED apstrakt | Donchian ansambl + vol sizing, top-20 universe od 2015: neto Sharpe > 1,5, alpha 10,8 %/god vs BTC | "Net of fees"; frekvencija nije navedena (vjerojatno dnevna, UNVERIFIED) | **Da u principu** (mali turnover). Nije intraday. Referentna točka |
| 5 | Bui, Nguyen, AdaptiveTrend, arXiv 2602.11708 | VERIFIED apstrakt | 6h signali, 150+ parova, OOS 2022–2024, Sharpe 2,41 | Navodi troškove, brojke nisu na stranici; **treba short** (30 %) | Sumnjiv: jedan preprint, bez deflacije, treba short |
| 6 | He, Manela, Ross, von Wachter, "Fundamentals of Perpetual Futures", arXiv 2212.06888 | VERIFIED | Arbitraža perp/spot: BTC Sharpe 1,80 uz maker naknade (2,39 u 2021., 0,70 u 2022., 1,32 u 2023.); odstupanja se smanjuju ~11 %/god | Samo maker naknade | **Ne** (treba short perp, edge propada). Koristan kao izvor funding/basis featurea |
| 7 | Bieganowski, Slepaczuk, arXiv 2602.00776 | VERIFIED apstrakt | Binance perp 1 s, 2022–2025: OFI, spread, adverse selection stabilni | Nema na stranici | **Ne** za retail taker (horizont sekundi). Dobra lista featurea |
| 8 | Albers i dr., "The Market Maker's Dilemma", arXiv 2502.18625 | VERIFIED apstrakt | Živi maker eksperiment, Binance BTC perp: vjerojatnost fillanja negativno korelirana s povratom poslije filla | 2025. | Upozorenje za maker scenarij, ne edge |
| 9 | Wang, arXiv 2506.05764; Jha i dr., arXiv 2010.01241 | VERIFIED / SNIPPET | LOB modeli, točnost na sekundama | Samo točnost, ne P&L | **Ne** |
| 10 | Lead-lag BTC → alti (Kurihara/Matsumoto 2026; Schei 2019; Li i dr. arXiv 2205.00974) | SNIPPET | Lag od par sekundi, smjer sporan | Bez troškova | **Ne** (latencija, spread) |
| 11 | Dnevni efekti u tjednu (Caporale/Plastun i dr.) | SNIPPET | Mješoviti, prije 2020 | Nema | **Ne** |
| 12 | Gort i dr., arXiv 2209.05559 (backtest overfitting u DRL) | VERIFIED apstrakt | Test samo 8 tjedana | Nema | Metodologija korisna, dokaz prekratak |
| 13 | Bailey, López de Prado: DSR (2014), PBO/CSCV (2017) | UNVERIFIED | Korekcija Sharpea za broj pokušaja | n/a | Obavezna vrata, lab ih već ima |

**Knjige (sve UNVERIFIED, sažetak iz memorije):**
- *López de Prado, AFML:* purged k-fold s embargom, CPCV, triple-barrier, meta-labelling. Na 1m–1h preklapanje labela jako napuhuje CV.
- *Chan, Algorithmic Trading:* momentum/mean reversion režimi, upozorenje na data-snooping; mean-reversion poglavlja pripadaju zatvorenim linijama.
- *Carver, Systematic Trading:* vol targeting i **budžet troškova** (preskoči pravilo čiji turnover pojede preveliki dio očekivanog povrata). Podržava sporije trend pravilo.
- *Harris, Trading and Exchanges:* informirani vs neinformirani tok, zašto pasivni nalozi zarađuju spread samo protiv neinformiranih. Povezano s #8.
- *Aronson, Evidence-Based TA:* data-mining bias, White reality check. Metodologija.
- *Kakushadze, Serur, 151 Trading Strategies:* katalog formula bez troškova i dokaza. Samo popis ideja.

**Rupe u literaturi (original rad, visok rizik overfittinga):** nema verificirane studije taker buy/sell omjera na 1m–1h, funding/OI kao prediktora za long-only spot,
niti likvidacijskih kaskada kao signala.

## 3. Open source projekti

Zvjezdice, licenca i push izmjereni `gh`-om (VERIFIED). Sadržaj strategija iz README-a/dokumentacije.

| Projekt | Licenca | Zvjezdice | Zadnji push | Dokaz izvan uzorka / neto troškova? | Verdikt |
|---------|---------|-----------|-------------|--------------------------------------|---------|
| freqtrade | GPL-3.0 | 55.371 | 2026-10-14 | Okvir. Vlastita dokumentacija kaže da mnoge strategije "padnu na lookahead biasu", a uklanjanje obično bitno pogorša rezultat (https://www.freqtrade.io/en/stable/lookahead-analysis/) | Alat; opcionalno kao dodatna provjera lookaheada |
| freqtrade-strategies | GPL-3.0 | 5.546 | 2026-09-08 | Samo predlošci, bez OOS i neto tablica | Preskoči (RSI/BB zatvorene) |
| NostalgiaForInfinity | GPL-3.0 | 3.474 | 2026-10-14 | 5m dip-buy, stotine ručno ugođenih uvjeta, rezultati "u komentarima commitova", bez OOS protokola | Preskoči. Procjena overfita je moj zaključak, ne tvrdnja repoa |
| jesse | MIT | 8.644 | 2026-10-12 | Okvir, nema objavljenih neto rezultata | Samo alat, bez edgea |
| hummingbot | Apache-2.0 | 20.442 | 2026-10-06 | Market making; vlastiti dokumenti kažu da backtest služi za osjetljivost parametara, ne prognozu; 1m svijeće dopuštaju 1 fill/min naspram 30+ stvarnih | Preskoči (treba inventar na obje strane) |
| hftbacktest | MIT | 4.886 | 2025-12-23 | Pošteno modelira poziciju u redu i latenciju | Samo ideja: što znači realističan fill |
| NautilusTrader | LGPL-3.0 | 29.980 | 2026-10-14 | Primjeri bez tvrdnji o performansama | Samo ako zatrebaju L2 simulacije |
| vectorbt | custom (Commons Clause) | 9.368 | 2026-10-14 | Samo engine; brzi sweep = lako data-mining | Opcionalno; K se mora bilježiti |
| Qlib | MIT | 49.355 | 2026-10-08 | Dionički benchmarkovi | Ideja: rolling retrain protokol i Alpha158-stil značajke |
| FinRL / FinRL-Meta | MIT | 16.639 / 1.949 | 2026-10-13 / 10-12 | Tipičan RL: jedan split, bez deflated Sharpea | Preskoči |
| backtrader, backtesting.py, Lean, OctoBot, binance-trading-bot | razno | razno | backtrader 2024-08 | Bez dokaza | Preskoči |
| funding/OI/likvidacije/lead-lag repoi (<400 zvjezdica) | razno | 0–379 | 2023–2026 | Dashboardi i igračke | Preskoči |

Zaključak: nijedan projekt ne objavljuje pošten OOS neto troškova intraday kripto rezultat. Javne strategije su indikatorski složenci unutar zatvorenih obitelji
ili market making koji ne odgovara long-only pravilu.

## 4. Podaci: što se može povući (provjerio agent, stavke s 🔶 nisu neovisno provjerene)

| Skup | Dubina | Granularnost | Napomena |
|------|--------|--------------|----------|
| Funding rate (REST `/fapi/v1/fundingRate`) | od 2019-09 | 8h | puna povijest |
| `futures/um/daily/metrics` (arhiva data.binance.vision) | od 2020-09 | 5m | OI, long/short omjeri, **taker long/short volumen omjer**. Pravi izvor za višegodišnji test |
| REST `/futures/data/*` | **samo ~30 dana** | 5m–1d | Ne koristiti za višegodišnje testove |
| Premium / mark klines | od ~2019-12 | do 1m | |
| `bookDepth` | od 2023-01 | snapshotovi | ~0,5 MB/dan 🔶 |
| aggTrades | spot od 2017-08, futures od 2020-01 | tick | ~520 MB/mj. za futures; omogućuje fill model s trake |
| Likvidacije | **nedostupno** | | Nema ni u REST-u ni u arhivi; samo snimanje websocketom unaprijed |
| Lokalni CSV `data/intraday/*_{1m,5m}_clean.csv` | | | Stupci `ts,open,high,low,close,volume,vwap,trades`. **Nema `taker_buy_volume`**; skripta ga čita (`tb_base`/`tb_quote`) pa odbacuje |

Nema geo-blokade ni ključa za te izvore. Nije provjereno: `basis` endpoint, početak metrics za ETH/SOL, OKX rubik.

## 5. EU/HR provjera (pravilo iz `AGENTS.md`, 2026-10-14)

- **Dostupnost kripta kod IBKR-a za Petra (HR, MiCA): nepotvrđeno.** Ne nagađam. Podaci su s Binance USDT parova, što je istraživački izvor, ne dokaz da je taj instrument izvediv.
- Zadano: bez poluge, bez shorta. Zato su izvan opsega funding arbitraža (treba short perp) i AdaptiveTrend (30 % short).
- Valuta: USDT/USD instrumenti, račun u EUR, pa konverzija EUR/USD ulazi u trošak.
- Porezni tretman: nepotvrđen, nije posao agenata (vidi `docs/guides/regulation-eu-hr.md`).

## 6. Prijedlog hipoteza za pred-registraciju (korak 2, čeka tvoje odobrenje)

Redoslijed prema prioritetu dokaza. Svaka dobiva novi freeze ID prije ijednog testa, a svaki pokušaj ide u ledger (K raste).

| Prijedlog | Ideja | Izvor | Prior | Napomena |
|-----------|-------|-------|-------|----------|
| H0 | Break-even filter: odbaci svaki ulaz čije očekivano kretanje < ~30 bps | Carver, radovi 1 i 7 | n/a | Alat, ne strategija; računa se prije svega |
| H1 | Long-only 4h–6h Donchian ansambl s vol sizingom (BTC/ETH/SOL) | rad 4, 5 | srednji | Najbliže "intraday" s neto dokazom. Pitanje je li sporiji trend bolji od neuspjelog N5 (satni, −17 %) |
| H2 | Funding / OI / taker-ratio kao **režimski filter** na H1 (ne kao okidač) | rad 6, K33, BitMEX | nizak | Arhiva `metrics` daje 5m povijest od 2020. Visok rizik overfita, N=7 epizoda u anegdoti |
| H3 | Uvjetni 21–23 UTC prozor: samo kad filter signalizira očekivano kretanje > 30 bps | rad 1, 2 | nizak | Jedan unaprijed zadan prozor, bez skeniranja sati |
| H4 | Intraday time-series momentum s volumnim satom | rad 3 | nizak | Jedan signal dnevno; replikacija 2023+ |
| H5 | Falsifikacija lead-laga BTC→SOL/ETH na 1m | rad 10 | vrlo nizak | Jeftino pobiti postojećim 1m podacima |
| H6 | Maker ulaz s filterom adverse selectiona, fill iz aggTrades trake | rad 8, 7 | nepoznat | Istraživački projekt, ne brzi test; traži aggTrades |
| H7 | Vol-regime breakout s vol sizingom | rad 4, 17 | nizak | Provjera tvrdnje da vol targeting šteti BTC-u |

Ocjena ukupno: realno očekujem da intraday varijante (H3–H5) padnu. H1–H2 imaju smisla kao "time-in-market reducer", ali ih treba mjeriti protiv buy-and-holda 2023+.
Likvidacijski fade, order-flow imbalance i market making ispadaju: nema podataka, treba maker/L2 ili kršimo long-only.

## 7. Što ovaj dokument NIJE

Nije signal, nije Critic dokaz, nije odobrenje ijedne strategije. `approved_list` ostaje prazan, signal **PRIČEKAJ**.
