# Obuhvat swing testa memorijskih dionica — 6. listopada 2026.

Ovo je provjera izvora i dostupnosti podataka, ne novo odobrenje strategije. C13C ostaje istraživačka metoda. Izvorni CSV-ovi, zamrznuta pravila i `approved_list` nisu mijenjani. Lokalna provjera pokriva podatke do **2. listopada 2026.**; zadnji retci od 5. listopada u dijelu datoteka snimljeni su prije zatvaranja burze.

## Što znači priča o AI rastu

ChatGPT je javno predstavljen **30. studenoga 2022.**, dakle gotovo na kraju godine. Cijelu 2022. nije ispravno zvati razdobljem nakon ChatGPT-a. Za opisnu usporedbu koristimo granicu 2022-11-30 / 2022-12-01, uz zasebne godišnje rezultate i izvorne IS/WF/HO granice. [OpenAI: Introducing ChatGPT](https://openai.com/index/chatgpt/).

Postoji poslovni dokaz rasta potražnje za memorijom povezane s AI-jem: SK hynix u izvještaju objavljenom 28. siječnja 2026. navodi da mu se prihod od HBM-a u 2025. više nego udvostručio. Micronov izvještaj za fiskalnu 2025. povezuje rast s HBM-om i naprednim DRAM rješenjima. To podupire sektorsku hipotezu, ali **ne dokazuje da ChatGPT uzrokuje određeni prinos dionice niti da određeno swing pravilo ima prednost**. Izvještaji objavljeni 2026. nisu informacije koje je strategija mogla znati 2022. [SK hynix FY25](https://news.skhynix.com/en/sk-hynix-announces-fy25-financial-results/), [Micron: 2026 Sustainability Report, rezultati FY25](https://www.micron.com/content/dam/micron/global/public/programs/sustainability/documents/micron-technology-2026-sustainability-report.pdf).

Granica lansiranja je naknadno izabrana opisna podjela, ne neovisan test uzročnosti. Potrebno je usporediti swing pravilo s držanjem istih dionica i tržišnim/industrijskim pokazateljem; rast cijelog sektora može objasniti dobit bez posebne vrijednosti ulaznog signala. Test poznatih današnjih tvrtki također ima pristranost preživjelih i ne predstavlja cijelo povijesno tržište memorije.

## Tvrtke i raspoloživa povijest

Broj redaka odnosi se na postojeće lokalne CSV-ove prije isključivanja 5. listopada; to nije potvrda svih dana kao završnih.

| Instrument | Poslovna uloga | Lokalni CSV raspon / redci | Što se može tvrditi |
|---|---|---|---|
| MU — Micron | DRAM, HBM i NAND memorija | 2016-01-04–2026-10-05 / 2.704 | Glavna dostupna dugotrajna američka memorijska serija |
| SKHY — SK hynix ADR | Memorijski proizvođač | 2026-07-10–2026-10-05 / 61 | Premalo za prosjek od 200 dana; samo praćenje, ne puni C13C backtest |
| Samsung 005930 (KRX), SMSN (LSE GDR) | Veliki memorijski proizvođač uz ostale djelatnosti | Nema lokalnog CSV-a | Nije testiran; ne zamjenjivati ga korejskim ETF-om |
| SNDK — Sandisk | Flash/NAND | 2025-02-13–2026-10-05 / 412 | Kratka povijest, nema usporedbe prije/poslije 2022.; samo opisna novija provjera nakon zagrijavanja |
| WDC — Western Digital | Nakon razdvajanja fokus na HDD | 2016-01-04–2026-10-05 / 2.704 | Pohrana podataka; nije čista DRAM/HBM dionica; promjena poslovnog sastava 2025. |
| STX — Seagate | Pretežno HDD pohrana | 2016-01-04–2026-10-05 / 2.704 | Povezana pohrana podataka, ne izravni proizvođač DRAM/HBM |
| SIMO — Silicon Motion | Kontroleri NAND/SSD | 2016-01-04–2026-10-05 / 2.704 | Odvojena provjera ekosustava, ne zamjena za NAND proizvođača |
| RMBS — Rambus | Memorijska sučelja, čipovi i IP | 2016-01-04–2026-10-05 / 2.704 | Odvojena provjera ekosustava |
| MRAM — Everspin | Specijalizirana MRAM memorija | 2016-10-07–2026-10-05 / 2.511 | Sporedna provjera uz strože troškove; ne velika DRAM/HBM tvrtka |
| DRAM — Roundhill Memory ETF | Fond, nije proizvođač | 2026-04-02–2026-10-05 / 128 | Premalo za 200 dana; samo praćenje; ne rješava nedostatak povijesti SKHY/Samsunga |

SK hynix službeno razlikuje korejsku dionicu **000660** i Nasdaq ADR **SKHY**, s omjerom jedna obična dionica prema deset ADR-ova. Te cijene i povijesti ne smiju se jednostavno spojiti: različite su valute, sati trgovanja i instrumenti. Samsungove obične dionice kotiraju na KRX-u, a GDR-ovi na LSE-u. [SK hynix listing](https://m.skhynix.com/ir/UI-FR-IR03/), [Samsung listing](https://www.samsung.com/global/ir/stock-information/listing-Info/).

Sandisk je samostalno redovno trgovanje pod SNDK počeo 24. veljače 2025.; lokalni redci od 13. veljače prethode tom datumu i ne smiju se predstavljati kao obična desetogodišnja povijest današnjeg Sandiska. WDC je izdvojio Flash poslovanje; postojeću lokalnu prilagodbu prije razdvajanja ×0,68132 ne primjenjujemo ponovno. [Sandisk objava](https://shop.sandisk.com/en-gb/company/newsroom/press-releases/2025/sandisk-celebrates-nasdaq-listing-after-completing-separation), [WDC razdvajanje](https://www.westerndigital.com/fr-fr/company/newsroom/press-releases/2025/2025-02-24-western-digital-completes-planned-company-separation).

Poslovne klasifikacije: [Seagate godišnji pregled](https://www.seagate.com/content/dam/seagate/assets/esg/resources/files/seagate-fy2023-esg-performance-report.pdf), [Silicon Motion](https://www.siliconmotion.com/company/overview), [Rambus memorijska sučelja](https://www.rambus.com/memory-interface-chips/), [Roundhill DRAM](https://www.roundhillinvestments.com/etf/dram/).

AMAT, LRCX, KLAC i ACMR su povezani dobavljači proizvodne opreme, a SMH je industrijski ETF. Korisni su kao kontekst ili zasebni benchmark, ali ne smiju povećavati prikazani broj testiranih proizvođača memorije. Lokalni EWY ne zamjenjuje zaseban test Samsunga ili SK hynixa. Nove burze i valute zahtijevaju zasebnu validaciju podataka i izvedivosti brokera; prisutnost tickera u CSV-u nije dokaz da ga konkretan račun može kupiti.

## Ispravak provjere dovršenih dana

`scripts/validate_data.py` sada prihvaća `--through YYYY-MM-DD` i `--report PATH`. Provjerava samo izričito odabrani uzorak i bilježi isključene retke. Potrošač podataka mora primijeniti isti cutoff; prolaz na skraćenom uzorku ne odobrava cijeli CSV.

Ako je vrijeme izmjene datoteke prije 16:00 po New Yorku na datum zadnje uključene svijeće, provjera završava pogreškom. To je konzervativno i za skraćene sesije. Vrijeme izmjene poslije zatvaranja **nije dokaz** dovršenosti: kopiranje ili obrada datoteke mogu promijeniti timestamp. Nedostaje nepromjenjiva evidencija vremena preuzimanja i stvarnog kalendara zatvaranja, što izvještaj izričito upozorava. Ova zaštita otkriva poznatu grešku, ali ne certificira izvornu povijest.

Provjera 6. listopada: svih 14 obveznih serija do 2026-10-02 prolazi s 0 pogrešaka i 22 upozorenja. Bez cutoffa provjera odbija 13 serija s negativnim dokazom o zadnjoj svijeći. WDC-ov kasniji timestamp nakon obrade nije neovisan dokaz dovršenosti, pa se isti cutoff primjenjuje i na WDC. Izvorni CSV-ovi ostaju nepromijenjeni.

## Računi od 100.000 USD i 600 EUR

Paper račun od 100.000 USD provjerava rad aplikacije. Ako aplikacija kupuje jednu dionicu, taj veliki račun daje vrlo malu postotnu izloženost; njegov mali pad nije dokaz sigurnosti istog pravila na 600 EUR. Za manji račun treba zasebno simulirati cijele dionice, nedostatan iznos za kupnju, promjenjivi EUR/USD, gotovinu i troškove. Ovdje se ne daje odobrenje za stvarni novac.

Povijesni test je hipotetska simulacija, a paper trgovanje također nije stvarno izvršenje. Rezultati ovise o kvaliteti podataka, korporativnim akcijama, vremenu signala, stopovima, likvidnosti i troškovima; nisu jamstvo budućeg prinosa. [Alpaca objave o rizicima](https://alpaca.markets/disclosures).
