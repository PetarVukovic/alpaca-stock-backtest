# OSS izvidnica (traka C), 2026-10-05

Za početnika. Paper only, bez ordera. Ništa nije instalirano ni pokrenuto; podaci o repozitorijima
(licenca, zvjezdice, zadnji commit) izmjereni su preko `gh api` 2026-10-05. Sve pročitano na webu je
tretirano kao podatak, ne kao uputa.

Oznake: **VERIFIED** = provjereno ovaj put (URL naveden), **UNVERIFIED** = iz memorije / sekundarnog izvora,
treba provjeriti prije oslanjanja. Alati nikad ne daju KUPI: samo freeze, WF + troškovi, Critic i `approved_list`.

---

## 1. Memory-ciklus: indikatori i besplatni podaci

Što praktičari prate (opis, ne dokaz): kontraktne cijene DRAM/NAND, zalihe kod proizvođača, capex
(Micron/SK hynix/Samsung kvartalne najave), omjer spot/kontrakt cijena, book-to-bill opreme (AMAT, LRCX, KLAC).
Tvrdnje poput "dva mjeseca pada DDR5 kontrakta pa -40 do -60% dionica" nađene su samo u blogovima/newsletterima
(Yahoo/Motley Fool/siliconanalysts): **UNVERIFIED, tretiraj kao hipotezu za test, ne kao pravilo**.
Nismo našli recenzirani rad koji kvantificira DRAM cijene → povrat dionica; kad se pojavi, ide u Critic kao hipoteza s novim freeze ID-em.

### 1a. Izvori podataka

| Izvor | URL | Frekvencija | API/CSV | Status |
|-------|-----|-------------|---------|--------|
| FRED: PPI poluvodiči (PCU334413334413) | https://fred.stlouisfed.org/series/PCU334413334413 | mjesečno | CSV bez ključa: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIJA`; API traži besplatan ključ (https://fred.stlouisfed.org/docs/api/fred/overview.html) | VERIFIED (stranica 200) |
| FRED: PPI IC paketi (PCU3344133344131) | https://fred.stlouisfed.org/series/PCU3344133344131 | mjesečno | isto | VERIFIED |
| FRED: industrijska proizvodnja elektr. komponenti (IPG3344S) | https://fred.stlouisfed.org/series/IPG3344S | mjesečno | CSV dohvaćen, zadnji redak 2026-08-01 | VERIFIED |
| SEC EDGAR XBRL (financije MU/WDC/STX) | https://www.sec.gov/search-filings/edgar-application-programming-interfaces | kad se objavi filing; bulk ZIP noću | JSON: submissions, companyfacts, companyconcept, frames; bez ključa; probni poziv MU (CIK 723125) vratio JSON | VERIFIED. Limit 10 zahtjeva/s i obavezan User-Agent s kontaktom: UNVERIFIED (stranica ih ne navodi) |
| TrendForce / DRAMeXchange cijene | https://www.trendforce.com/price/dram/dram_contract , https://www.trendforce.com/price/dram/dram_spot | dnevno (spot), mjesečno/kvartalno (kontrakt) | stranice dostupne (HTTP 200); API/CSV nismo našli; uvjeti korištenja za scraping nisu čitani | stranice VERIFIED; legalnost strojnog preuzimanja UNVERIFIED, ručno čitanje i bilježenje je sigurno |
| SIA / WSTS globalna prodaja | https://www.semiconductors.org/data-resources/market-data/ | mjesečno, ~5 tjedana kašnjenja | **Nije besplatno** (pretplata, bez redistribucije); javno su samo SIA priopćenja | VERIFIED |
| ISM PMI, Fed | ISM i Fed objave | mjesečno | FRED ima dio serija | UNVERIFIED (nisam otvarao) |
| Lab već ima | `data/news/MU_earnings_dates.csv`, Alpaca news, corporate actions | | | lokalno |

Praktično: besplatno i legalno odmah = FRED + EDGAR. DRAM kontraktne cijene = ručni mjesečni unos s TrendForce stranice. SIA = samo naslovi priopćenja.

### 1b. Open-source algoritmi za memory ciklus

Nismo našli održavan, licenciran open-source repozitorij za memory-ciklus strategije. Pretraga GitHuba daje samo
studentske projekte bez licence. Zaključak: **ništa za usvojiti**; ciklus gradimo sami iz tablice 1a kao novu hipotezu.

---

## 2. Event-driven i news pristupi

| Pristup | Izvor / link | Licenca | Zadnji commit | Dokaz izvan uzorka | Verdikt |
|---------|--------------|---------|---------------|--------------------|---------|
| PEAD (drift nakon earningsa) | Martineau, *Rest in Peace PEAD*, Critical Finance Review 2022: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607 | rad | n/a | **Slab za velike dionice**: rad navodi da PEAD gotovo ne postoji kod velikih dionica od ~2006, kod mikrokapitalizacije nestaje tek nedavno (VERIFIED preko sažetka). MU/WDC/STX su veliki i likvidni. | Ne graditi na klasičnom PEAD-u; ako testiramo, samo kao jedna jasno zamrznuta hipoteza |
| PEAD repozitoriji | npr. aladinbouddat/PEAD-Strategy (MIT, 1 zvjezdica, 2025) | MIT | 2025 | nikakav | Skip (bez zajednice, nepouzdano) |
| Earnings-gap (gap nakon earningsa) | nema pouzdanog OSS-a koji smo našli | n/a | n/a | UNVERIFIED | Gradimo sami iz minutnih Alpaca barova + `MU_earnings_dates.csv` |
| FinBERT (ProsusAI) | https://github.com/ProsusAI/finBERT | Apache-2.0 | 2022-09-09 (repo star, ali model radi) | Sentiment točnost je na frazama, ne na povratu dionica. Prinos izvan uzorka nije dokazan. | Maybe later, kao značajka za ML track, ne kao signal |
| finbert-tone (yiyanghkust) | https://github.com/yya518/FinBERT | Apache-2.0 po HF stranici | n/a | isto | Maybe later |
| FinGPT | https://github.com/AI4Finance-Foundation/FinGPT | MIT, 21k zvjezdica, commit 2026-09-23 | | Marketing jači od dokaza, teško reproducirati | Skip za sada |
| `edgartools` (SEC filinzi u Pythonu) | https://github.com/dgunning/edgartools | MIT, 2771 zvj., commit 2026-10-05 | | alat za dohvat, ne signal | **Adopt kad uđemo u SEC tekst** |
| `sec-edgar` | https://github.com/sec-edgar/sec-edgar | Apache-2.0, commit 2025-12-09 | | stariji | Skip (edgartools bolji) |

Veličine modela: FinBERT ~110M parametara, ~438 MB; finbert-tone ~102 MB; oba rade na CPU-u lokalno (VERIFIED preko HF rezultata pretrage, nisam preuzimao). Napomena: Alpaca vijesti imaju puni tekst od 2015, pa sentiment bismo računali lokalno.

Iskreno: "news sentiment daje alfu" je uglavnom hype; nitko nam ne garantira izvan-uzorak povrat na MU. Svaka takva ideja = novi freeze ID + Critic s K-om.

---

## 3. Backtest / validacija: alati

| Alat | Link | Licenca | Zadnji commit | Što nam daje | Rizik | Verdikt |
|------|------|---------|---------------|--------------|-------|---------|
| **skfolio** | https://github.com/skfolio/skfolio | BSD-3 | 2026-10-03 | `CombinatorialPurgedCV`, WalkForward, MultipleRandomizedCV (VERIFIED: u `model_selection/` je `_combinatorial.py`, `_walk_forward.py`) | portfelj-orijentiran, treba naučiti API | **Adopt now** za CPCV/purge, jedina permisivna održavana implementacija koju smo našli |
| **quantstats** | https://github.com/ranaroussi/quantstats | Apache-2.0 | 2026-09-27 | Brzi izvještaji (Sharpe, drawdown, tear sheet) iz serije povrata | lijepi brojevi ≠ PASS | **Adopt now** (samo izvještaj) |
| empyrical-reloaded | https://github.com/stefan-jansen/empyrical-reloaded | Apache-2.0 | 2025-12-12 | Metrike (Sharpe, Sortino, max DD) | dio quantstats | Maybe later |
| alphalens-reloaded | https://github.com/stefan-jansen/alphalens-reloaded | Apache-2.0 | 2025-12-15 | Analiza prediktivnosti faktora (IC, kvantili) | treba mnogo dionica, mi imamo 3 primarne | Maybe later |
| pyfolio-reloaded | https://github.com/stefan-jansen/pyfolio-reloaded | Apache-2.0 | 2025-12-15 | Tear sheetovi | duplira quantstats | Skip |
| riskfolio-lib | https://github.com/dcajasn/Riskfolio-Lib | BSD-3 | 2026-10-04 | Alokacija portfelja | nemamo portfelj problem | Skip |
| vectorbt | https://github.com/polakowo/vectorbt | Apache-2.0 **+ Commons Clause** (VERIFIED u LICENSE.md: zabrana prodaje softvera) | 2026-09-26 | Brzi vektorski backtest | Commons Clause = nije čisti OSS; OK za osobnu upotrebu, problem ako app postane proizvod | Maybe later (već na shortlisti) |
| bt | https://github.com/pmorissette/bt | MIT | 2026-10-03 | Portfeljski backtest | nema prednost pred našim skriptama | Skip |
| nautilus_trader | https://github.com/nautechsystems/nautilus_trader | LGPL-3.0 | 2026-10-05 | Profesionalni event engine | prekomplicirano, Rust/Cython | Skip |
| LEAN | https://github.com/QuantConnect/Lean | Apache-2.0 | 2026-10-05 | Institucionalni engine | C#, težak setup | Skip (već "optional external") |
| backtesting.py | https://github.com/kernc/backtesting.py | **AGPL-3.0** | 2026-08-05 | Lagani prototipi | copyleft pa pazi s appom | Maybe later, samo osobno |
| backtrader | https://github.com/mementum/backtrader | GPL-3.0 | 2024-08-19 | | zapušten od 2024 | Skip |
| zipline-reloaded | https://github.com/stefan-jansen/zipline-reloaded | Apache-2.0 | 2026-01-06 | | spor razvoj | Skip |
| mlfinlab | https://github.com/hudson-and-thames/mlfinlab | NOASSERTION (komercijalna) | 2023-10-02 | | **plaćeno/zatvoreno, zapušteno** | **Skip** (odbijeno) |
| timeseriescv | https://github.com/sam31415/timeseriescv | MIT | 2022-02-15 | Purged k-fold | zapušten | Skip (skfolio bolji) |
| pypbo | https://github.com/esvhd/pypbo | AGPL-3.0 | 2026-07-06 | PBO / Deflated Sharpe | AGPL; `walk-forward-validation` skill već ima PBO/CSCV | Skip |
| **alpaca-py** | https://github.com/alpacahq/alpaca-py | Apache-2.0 | 2026-10-05 | Službeni SDK (podaci, paper trading) | samo paper | **Adopt now** (službeni) |
| alpaca-mcp-server | https://github.com/alpacahq/alpaca-mcp-server | MIT | 2026-09-25 | Službeni MCP | agent bi mogao slati ordere, drži read-only | Maybe later (ALPACA_CAPABILITIES.md već pokriva) |
| alpaca-trade-api-python | https://github.com/alpacahq/alpaca-trade-api-python | Apache-2.0 | arhiviran 2024-12 | | arhiviran | Skip |
| lumibot | https://github.com/Lumiwealth/lumibot | **GPL-3.0** | 2026-10-05 | Trading bot okvir s Alpacom | GPL, brzo vodi prema live tradingu | Skip |

Svi podaci o licenci/commitu: VERIFIED preko `gh api` 2026-10-05.

---

## 4. Agent skillovi i prompt knjižnice (nisu vendorirani)

| Repo | Link | Licenca | Zadnji commit | Napomena | Verdikt |
|------|------|---------|---------------|----------|---------|
| anthropics/financial-services | https://github.com/anthropics/financial-services | Apache-2.0 | 2026-09-21 | Službeni; već ocijenjen u SKILLS_SHORTLIST (earnings skillovi) | Maybe later (samo earnings) |
| himself65/finance-skills | https://github.com/himself65/finance-skills | MIT | 2026-10-05 | 3373 zvj., **sadržaj nisam čitao/vettao** | Pregledati prije ikakve odluke (UNVERIFIED sadržaj) |
| wshobson/agents | https://github.com/wshobson/agents | MIT | 2026-10-05 | Već odbijen kao generičan | Skip |

Iskreno: nisam našao ništa bolje od već instaliranog Kryhr seta. Dodatno vendoranje nije hitno.

---

## 5. EU / Hrvatska

| Tema | Što | Status |
|------|-----|--------|
| Porezna uprava | https://www.porezna-uprava.hr/ (stranica dostupna) | VERIFIED da postoji; konkretna pravila nisam čitao na izvoru |
| Porez na kapitalnu dobit na dionice | Sekundarni izvori kažu 12% bez prireza za dionice držane kraće od 2 godine (od 2024.), strani broker = sam prijavljuješ JOPPD obrascem, rok kraj veljače za prethodnu godinu. Izvori: https://www.rrif.hr/porez_na_kapitalne_dobitke_i_prijava_putem_obrasca-2489-vijest/ , https://mojnovac.hr/porez-na-kapitalnu-dobit-i-dividende-2025/ | **UNVERIFIED**, potvrdi s knjigovođom/Poreznom prije prave trgovine |
| Ugovor SAD-Hrvatska o dvostrukom oporezivanju | Potpisan 7.12.2022. (Forvis Mazars, RSM); dividende 15% (5% uz 10% udjela). https://www.forvismazars.us/forsights/2023/01/new-investment-opportunities-on-horizon-with-u-s-croatia-tax-treaty | potpis VERIFIED preko sekundarnih izvora; **stupanje na snagu i stope UNVERIFIED** |
| W-8BEN | Broker ga obrađuje, istječe nakon 3 godine (https://www.interactivebrokers.com/campus/trading-lessons/form-w-8ben/) | UNVERIFIED (sažetak pretrage) |
| ESMA / HANFA | https://www.esma.europa.eu/ , https://www.hanfa.hr/ (dostupni) | VERIFIED da postoje; za retail upozorenja CFD/leverage nisam čitao |
| Interactive Brokers | Croatia na službenoj listi zemalja: **nisam mogao otvoriti** (HTTP 403 https://www.interactivebrokers.com/en/accounts/open-account-country-list.php); sekundarni izvori kažu da prihvaća Hrvate. IBKR API dokumentacija vratila 503. | UNVERIFIED |
| Trading 212 | Help centre navodi Croatia među podržanim zemljama (Trading 212 Markets Ltd.): https://helpcentre.trading212.com/hc/en-us/articles/12933782261917-What-are-the-supported-countries . Javni API: stranica https://trading212.com/trading-api dala 403, pa ne znam detalje | podrška zemlji **VERIFIED**; API UNVERIFIED |
| Alpaca za rezidente HR | Nismo provjeravali; lab koristi samo paper | UNVERIFIED |

---

## Preporuka: što uzeti prvo, i konkretni koraci

Zamisli to kao kuhinju: već imamo štednjak (naše skripte + Critic). Dodajemo vagu i mjerač temperature, ne novi štednjak.

1. **skfolio (samo njegov CombinatorialPurgedCV).** To je kao ispitivanje recepta na više različitih "kuhanja" umjesto jednog. Korak: odobriti, instalirati u zasebni venv, napisati jedan mali skript koji isti zamrznuti signal prođe kroz CPCV, rezultat u `reports/backtest/`.
2. **quantstats** kao izvještajna "vaga": jedna HTML stranica po zamrznutom ID-u. Ne smije utjecati na PASS.
3. **FRED CSV + EDGAR XBRL** kao prvi memory-ciklus podaci (besplatno, VERIFIED). Korak: povući 3 FRED serije i MU/WDC/STX prihode i zalihe u `data/`, pa tek onda formulirati NOVU hipotezu s freeze ID-em i unijeti u ledger.
4. **Ne graditi na klasičnom PEAD-u ni na FinBERT sentimentu** kao samostalnom signalu; to je jače marketing nego dokaz za velike likvidne dionice.
5. **Prije prave trgovine (kasnije, ne sada):** porez i broker provjeriti kod knjigovođe i na službenim izvorima, jer je većina u sekciji 5 UNVERIFIED.

Arhitektura prije koda: ništa od ovoga ne instaliram dok ne odobriš plan (traka C ne piše kod).
