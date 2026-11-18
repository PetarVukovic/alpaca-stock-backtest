# AI lanac, swing test: što radi često i pobjeđuju li razine i mehanika slučajnost

*Istraživačka simulacija na povijesnim dnevnim podacima. Nije savjet za ulaganje, nije signal, nije formalni Critic PASS (lista odobrenih ostaje prazna, signal je **PRIČEKAJ**). Agenti ne šalju nikakve naloge (ni probne ni prave). Nema obećanja zarade i nema savjeta o porezu.*

Stranice: `reports/research/AICHAIN_20261014/swing/pages/uciti.html` (učenje, grafovi na stvarnim podacima), `swing/pages/*.html` (karte po skupinama). Sirovi brojevi: `swing/summary.json`, `swing/placebo.json`, `swing/audit.json`, `swing/results/*.json`. Skripte: `scripts/aichain_learn_page.py`, `scripts/aichain_swing_result_doc.py`.

## 1. Sažetak

1. **Razdoblje i trošak.** Glavno mjerilo je AI era, 3. 1. 2023. do 5. 10. 2026. (45,1 mjeseci); 2016. do 2022. samo kontekst. Trošak 0,025 % po strani za dionice (na 1.000 € to je 0,25 € pri kupnji i 0,25 € pri prodaji), kripto 0,10 %; stres 2x i 3x. Samo dugo, bez poluge.
2. **Potpore i otpori ne pobjeđuju slučajnost.** Od 24.510 razina (44 mjeseca, 55 papira) odbijanje je 47,3 % za prave naspram 48,7 % za nasumične crte; svi intervali obuhvaćaju nulu.
3. **Mehanika tržišta** (sweep, promjena smjera, BOS, zona) kao strogo pravilo ne pokazuje pouzdanu prednost; jedini granični slučaj je prvi povratak u svježu zonu potražnje (E4): +1,8 pp na 10 dana, donja granica intervala +0,06 pp, uz blokove od 3 mjeseca ispod nule, a prije 2023. suprotnog predznaka.
4. **Što "radi često"** (unaprijed upisano pravilo): na svih 43 dionica prvi je W1 C13C (Petrov algoritam) (30,8 poslova mjesečno, +34 € po poslu), zatim W5 proboj i povratni test i W3 tjedni rang zamaha. To su pravila praćenja trenda i zamaha, ne "pametan novac".
5. **Samo u AI eri.** U padu 2021. do 2022. očekivanje po poslu je nula ili negativno za 6 od 8 pravila.
6. **Držanje je jače po prinosu.** Kupi-i-drži na istim dionicama: 643 %; najbolje pravilo po ukupnom prinosu 179 %. Pravila su većinom u gotovini.

## 2. Podaci

- Samo `data/ohlcv/{T}_1d.csv` (dnevne svijeće, Alpaca, prilagođeno za splitove); satni i unutardnevni podaci nisu korišteni, `.parquet` nije korišten. CSV-ovi nisu mijenjani.
- Stock-test: 43 dionica u 6 segmenata (memorija, sučelja i pohrana, oprema, AI čipovi, mreže i serveri, oblak) do zajedničkog kraja 2026-10-05. Kripto (BTC, ETH, SOL) i metali (GLD, SLV) su zasebne skupine; GLD i SLV su **nepotvrđeni / referentni** jer američki ETF-ovi često nisu dostupni malim ulagačima iz EU (nema KID dokumenta), a kripto na IBKR-u ovisi o državi i propisima (nepotvrđeno).
- Karte tržišta koriste zadnji datum svakog papira (vidi stranice); placebo test koristi 55 papira, a SPX i NDX su preskočeni jer ne prolaze pravila podataka (OHLC izvan raspona).
- Pravila čišćenja (ista za sve): povijest prije `effective_start` se ne učitava (obustava trgovanja: SMCI do 2020-01-14, NBIS do 2024-10-21); očiti loš tick ograničava se na susjedne cijene (NVDA 2024-06-10; u kriptu je isto pravilo ograničilo 13 niskih cijena koje su vjerojatno stvarni fitilji, pa je to granica, vidi audit). WDC je već prilagođen za spin-off i nije ponovno prilagođavan.
- Što nije modelirano: tečaj EUR/USD (USD se tretira kao EUR), minimalna provizija IBKR-a (nepotvrđeno za Petrov tarif), dividende, porezi, razlomljene dionice (nepotvrđeno), proklizavanje, likvidnost tankih papira.

## 3. Pravila (W1 do W8) i rječnik nastave

Vokabular dolazi iz diskrecijske nastave "pametnog novca" čije su tvrdnje nedokazane; ovdje je svaki pojam pretvoren u strogo, provjerljivo pravilo bez pogleda u budućnost (okret = 5 svijeća sa svake strane, poznat tek 5 svijeća poslije; ATR14; zona = zadnja silazna svijeća prije rasta od 2 ATR u 3 svijeće koji je probio vrh; jednako dno unutar 0,3 %; tjedne svijeće iz dnevnih, samo završeni tjedni). Procjep (fair value gap) opisan je, ali ga nijedno pravilo ne koristi.

| Pravilo | Pojam | Pravilo |
|---|---|---|
| W1 C13C (Petrov algoritam) | nije iz nastave; Petrov algoritam, mjerilo | Zatvaranje iznad prosjeka 200 dana i pad od 5 % u 5 dana: kupi sutra; klizni stop 10 % ispod vrha. |
| W2 proboj 20-dnevnog vrha | momentum | Zatvaranje je najviše u 20 dana, 60-dnevni prinos > 0, iznad prosjeka 50 dana: kupi sutra; izlaz ispod najnižeg od zadnjih 10 dana, nakon 15 dana ili stop 8 % ispod kupnje. |
| W3 tjedni rang zamaha | momentum (tjedni rang) | Petkom rang skupine po prinosu 20 dana; kupi dionicu iz vodeće trećine iznad prosjeka 50 dana; izađi kad ispadne iz gornje polovice. |
| W4 odbijanje od potpore | potpora i otpor (odbijanje) | Razina = potvrđeno dno s najmanje dva ranija dodira; dodir zone pa zatvaranje iznad visokog dana dodira; stop 1 ATR ispod zone, cilj zadnji vrh. |
| W5 proboj i povratni test | potpora i otpor (obrnuta uloga) | Zatvaranje iznad zadnjeg potvrđenog vrha, pa prvi povratak unutar 1,5 % razine koji zatvara iznad nje; stop 3 % ispod razine; izlaz ispod prosjeka 50 dana. |
| W6 sweep i promjena smjera | likvidnost, promjena smjera, diskont, tjedni smjer | Tjedni trend nije medvjeđi, cijena u diskontu, sweep jednog od zadnja tri dna u zadnjih 5 svijeća, zatim zatvaranje iznad zadnjeg nižeg vrha; stop ispod dna sweepa minus pola ATR-a; pola se prodaje na cilju, ostatak prati. |
| W7 povratak u zonu potražnje | zona potražnje, struktura, diskont | Prvi povratak u svježu zonu potražnje uz bikovsku strukturu, diskont i zatvaranje iznad sredine zone; stop dno zone; cilj zadnji vrh. |
| W8 IBS povratak | nije iz nastave; kontrola (jednodnevni pad) | IBS < 0,2 (zatvaranje pri dnu dnevnog raspona) i iznad prosjeka 200 dana: kupi; izlaz IBS > 0,8 ili nakon 5 dana. |

Registracija je napisana prije prvog pokretanja (ledger K 542; 534 do 541 su pravila, 542 mjerilo). Parametri su fiksni, bez ugađanja. Test pogleda u budućnost prolazi za svih 8 pravila (576 provjera nizova i 48 provjera poslova po pravilu, bez greške).

## 4. Unaprijed upisano pravilo "radi često" i rang

**Podobno** je pravilo s najmanje 60 poslova u AI eri nad skupinom, pozitivnim očekivanjem po poslu uz trošak 2x i faktorom dobiti najmanje 1,2. Među podobnima rang je očekivanje po poslu pomnoženo s poslovima mjesečno (eura mjesečno na 1.000 € po dionici). Kupi-i-drži je mjerilo i nikad se ne rangira. Critic je blag prema riziku (pad, kolebanje i koncentracija ne snižavaju ocjenu), a strog samo prema nevaljanim dokazima.

Sve dionice (zbroj 43 sleevea):

| # | Pravilo | Poslova mj. | Zarada po poslu | Uz trošak 2x | Faktor dobiti | Ukupno mj. |
|---|---|---|---|---|---|---|
| 1 | W1 C13C (Petrov algoritam) | 30,8 | +34 € | +33 € | 1,99 | +1.045 € mj. |
| 2 | W5 proboj i povratni test | 13,1 | +77 € | +76 € | 3,62 | +999 € mj. |
| 3 | W3 tjedni rang zamaha | 14,2 | +65 € | +65 € | 2,60 | +926 € mj. |
| 4 | W2 proboj 20-dnevnog vrha | 27,1 | +21 € | +21 € | 1,60 | +574 € mj. |
| 5 | W8 IBS povratak | 77,1 | +7 € | +7 € | 1,44 | +557 € mj. |
| 6 | W6 sweep i promjena smjera | 3,6 | +21 € | +21 € | 1,75 | +78 € mj. |
| 7 | W7 povratak u zonu potražnje | 2,7 | +14 € | +14 € | 1,52 | +39 € mj. |

Nije podobno: W4 odbijanje od potpore (profit factor < 1.2).

Najbolje po skupini (ranking po istom pravilu) i usporedba s držanjem:

| Skupina | Dionica | Najbolje pravilo | Poslova mj. | Po poslu | Faktor dobiti | Ukupni prinos pravila | Kupi i drži |
|---|---|---|---|---|---|---|---|
| Memorija | 3 | W1 C13C (Petrov algoritam) | 2,3 | +77 € | 3,52 | 668 % | 1.837 % |
| Sučelja memorije i pohrana | 4 | W1 C13C (Petrov algoritam) | 3,0 | +28 € | 1,83 | 124 % | 260 % |
| Oprema za proizvodnju čipova | 10 | W1 C13C (Petrov algoritam) | 7,4 | +32 € | 1,92 | 155 % | 419 % |
| AI čipovi i logika | 11 | W5 proboj i povratni test | 3,4 | +56 € | 3,02 | 80 % | 456 % |
| Mreže i serveri | 8 | W3 tjedni rang zamaha | 2,6 | +109 € | 3,01 | 252 % | 931 % |
| Oblak i podatkovni centri | 7 | W5 proboj i povratni test | 2,0 | +80 € | 4,14 | 165 % | 633 % |
| Kripto (zasebna grupa) | 3 | W2 proboj 20-dnevnog vrha | 2,3 | +40 € | 2,08 | 186 % | 551 % |
| Metali (nepotvrđeno / referentno) | 2 | nitko nije podoban | - | - | - | - | 133 % |
| Sve dionice (zbroj segmenata) | 43 | W1 C13C (Petrov algoritam) | 30,8 | +34 € | 1,99 | 179 % | 643 % |

## 5. Rezultati (sve dionice, AI era)

| Pravilo | Poslova | Poslova mj. | Pogodak | Po poslu (1.000 €) | Faktor dobiti | Ukupni prinos | Sharpe | Max pad | Radi često |
|---|---|---|---|---|---|---|---|---|---|
| W1 C13C (Petrov algoritam) | 1.390 | 30,8 | 45 % | +34 € | 1,99 | 179 % | 1,39 | −20 % | DA |
| W2 proboj 20-dnevnog vrha | 1.223 | 27,1 | 47 % | +21 € | 1,60 | 61 % | 0,96 | −16 % | DA |
| W3 tjedni rang zamaha | 639 | 14,2 | 56 % | +65 € | 2,60 | 137 % | 1,36 | −19 % | DA |
| W4 odbijanje od potpore | 347 | 7,7 | 61 % | +1 € | 1,06 | 1 % | 0,20 | −2 % | ne |
| W5 proboj i povratni test | 589 | 13,1 | 35 % | +77 € | 3,62 | 123 % | 1,44 | −12 % | DA |
| W6 sweep i promjena smjera | 164 | 3,6 | 55 % | +21 € | 1,75 | 8 % | 0,81 | −5 % | DA |
| W7 povratak u zonu potražnje | 123 | 2,7 | 33 % | +14 € | 1,52 | 4 % | 0,75 | −2 % | DA |
| W8 IBS povratak | 3.476 | 77,1 | 59 % | +7 € | 1,44 | 98 % | 1,27 | −21 % | DA |
| B0 kupi i drži (mjerilo) | 43 | - | - | - | - | 643 % | 1,53 | −40 % | mjerilo |

Primjer čitanja: W5 donosi u prosjeku +77 € po poslu na 1.000 €, ali je dobitno samo 35 % poslova. Rizik se ovdje ne kažnjava, samo se prikazuje.

**Tipičan posao nasuprot prosjeku** (audit): prosjek nose rijetki veliki poslovi.

| Pravilo | Medijan posla | Prosjek posla | Prosjek bez 10 najboljih | Udio 10 najboljih u dobiti |
|---|---|---|---|---|
| W1 C13C (Petrov algoritam) | −1,2 % | 3,4 % | 2,5 % | 26 % |
| W2 proboj 20-dnevnog vrha | −1,1 % | 2,1 % | 1,6 % | 27 % |
| W3 tjedni rang zamaha | 1,3 % | 6,5 % | 4,4 % | 34 % |
| W4 odbijanje od potpore | 0,8 % | 0,1 % | −0,2 % | 279 % |
| W5 proboj i povratni test | −2,5 % | 7,7 % | 3,9 % | 50 % |
| W6 sweep i promjena smjera | 1,0 % | 2,1 % | 0,2 % | 92 % |
| W7 povratak u zonu potražnje | −2,0 % | 1,4 % | −0,4 % | 126 % |
| W8 IBS povratak | 0,8 % | 0,7 % | 0,6 % | 13 % |

**Isto pravilo kroz razdoblja** (poslova / zarada po poslu):

| Pravilo | 2016 do 2020 | 2021 do 2022 (pad) | AI era |
|---|---|---|---|
| W1 C13C (Petrov algoritam) | 702 / +28 € | 408 / +1 € | 1.390 / +34 € |
| W2 proboj 20-dnevnog vrha | 1.385 / +11 € | 447 / −3 € | 1.223 / +21 € |
| W3 tjedni rang zamaha | 731 / +32 € | 301 / −9 € | 639 / +65 € |
| W4 odbijanje od potpore | 489 / +2 € | 225 / −6 € | 347 / +1 € |
| W5 proboj i povratni test | 659 / +26 € | 293 / −9 € | 589 / +77 € |
| W6 sweep i promjena smjera | 166 / +26 € | 80 / −7 € | 164 / +21 € |
| W7 povratak u zonu potražnje | 92 / +12 € | 61 / −16 € | 123 / +14 € |
| W8 IBS povratak | 3.481 / +6 € | 1.494 / +2 € | 3.476 / +7 € |

**Robusnost ±20 %** (tri najbolja po očekivanju, jedan prag po jedan): nijedno nije fragilno (nijedna varijanta nema očekivanje <= 0 uz trošak 2x ili faktor dobiti < 1). To je slab test u bik-tržištu (ne gleda drugi režim). Deflated Sharpe (korekcija za K = 542) najvišeg pravila je 0,36.

## 6. Placebo: pobjeđuju li razine i mehanika slučajnost?

**Razine** (zadnji trgovački dan svakog mjeseca u AI eri, samo razine koje su tada već bile poznate, 20 dana unaprijed): dodir = raspon svijeće unutar 0,25 ATR; odbijanje = potez od 1,5 ATR natrag unutar 10 svijeća; probijanje = zatvaranje 1 ATR iza razine. Intervali su bootstrap po kalendarskim mjesecima (2000 ponavljanja, sjeme 20261014), a provjera s blokovima od 3 mjeseca ne mijenja zaključak.

| Kontrola | Odbijanje: prava / lažna | Razlika u odbijanju (pp) [95 %] | Probijanje: prava / lažna | Razlika u probijanju (pp) [95 %] |
|---|---|---|---|---|
| nasumična cijena | 47,3 % / 48,7 % | −1,4 [−2,9; 0,0] | 44,5 % / 43,2 % | +1,4 [−0,1; +2,9] |
| pomak ±3 % | 47,3 % / 47,9 % | −0,6 [−1,6; +0,3] | 44,5 % / 43,7 % | +0,8 [−0,1; +1,8] |
| par oko razine | 47,8 % / 48,8 % | −1,0 [−2,5; +0,6] | 44,1 % / 43,1 % | +1,0 [−0,6; +2,4] |

**Presuda: potvrđena razina odbija cijenu ništa češće od lažne crte.** Dodir je čak malo rjeđi nego kod nasumičnih crta (−1,1 pp). Isti smjer po skupinama (odbijanje prave / nasumične):

| Skupina | Prave | Nasumične |
|---|---|---|
| AI čipovi i logika | 48,2 % | 47,6 % |
| Oblak i podatkovni centri | 46,8 % | 49,8 % |
| Kripto (zasebna grupa) | 48,9 % | 47,2 % |
| Oprema za proizvodnju čipova | 47,6 % | 46,7 % |
| Sučelja memorije i pohrana | 49,3 % | 54,8 % |
| Memorija | 48,6 % | 55,2 % |
| metals_indices | 44,5 % | 47,3 % |
| Mreže i serveri | 45,3 % | 48,6 % |

(Pojedinačne skupine imaju široke intervale; nekoliko većih razlika očekuje se slučajno kad se gleda mnogo skupina.)

**Mehanika** (višak prinosa nad prosjekom istog papira na 10 dana, postotni bodovi, 95 % interval; kolona "blokovi" je strožiji interval s blokovima od 3 mjeseca; zadnja kolona je 2017. do 2022.):

| Događaj | Broj (AI era) | AI era višak [interval] | Blokovi 3 mj. | 2017 do 2022 |
|---|---|---|---|---|
| E1 sweep + promjena smjera u diskontu | 152 | −1,5 [−3,9; +1,2] | [−3,9; +0,4] | −0,3 [−2,2; +1,6] |
| E2 isto + bikovski tjedni trend | 103 | −2,5 [−5,3; +0,8] | [−5,5; +0,6] | +0,1 [−1,6; +1,9] |
| E3 isto + dodir svježe zone | 27 | −4,5 [−7,0; −1,6] | [−6,6; −1,4] | +0,1 [−2,8; +2,3] |
| E4 prvi povratak u svježu zonu potražnje | 686 | +1,8 [+0,1; +3,5] | [−0,1; +4,0] | −0,3 [−1,6; +0,9] |
| E5 BOS u bikovskom trendu | 855 | −0,3 [−1,4; +0,8] | [−1,6; +0,8] | +0,3 [−0,6; +1,1] |

**Presuda:** E1 do E3 i E5 ne pokazuju prednost (E2 i E3 su čak statistički lošiji od prosjeka); E4 je jedini granični slučaj i ne drži se uz stroži interval ni u ranijim godinama. Zaključak vrijedi samo za ove definicije na dnevnim svijećama; svaka druga definicija je novi pokušaj i povećava K. Pritom je višestruko testiranje stvarno: 15 kombinacija po razdoblju za događaje, 9 za razine.

## 7. Što je radilo, a što nije

**Radilo (u AI eri, po unaprijed zadanom pravilu):** W1, W5 i W3 (trend i zamah; uz dva ograničenja: pogodak je 35 % do 56 %, a prosjek nose rijetki veliki poslovi), W2 i W8 (često trguju, mala zarada po poslu, osjetljivi na minimalnu proviziju). Skupine u kojima je pravilo podobno (od 8 skupina bez zbroja): W1 6, W2 7, W8 6.

**Nije radilo:** W4 (odbijanje od potpore, faktor dobiti 1,06, nije podobno); W6 i W7 su podobni samo formalno (oko jedan posao po dionici godišnje; bez 10 najboljih poslova W6 ima 0,18 % po poslu, a W7 −0,41 %); razine kao predviđanje; tjedni filter (E2 gori od E1); metali GLD i SLV (nijedno pravilo podobno, referentno); kripto samo W2.

**Nijedno pravilo nije dokazano izvan AI ere** i nijedno ne pobjeđuje kupi-i-drži po ukupnom prinosu.

## 8. Što dalje

1. Zadržati potpore i otpore samo kao orijentir za stop i veličinu pozicije, ne kao signal.
2. Ako se želi dalje istraživati mehaniku: **nova hipoteza s novim freeze ID-om** za svaki zasebni test (premium i diskont izolirano, jednaka dna izolirano, procjep, satne svijeće), uz upis u ledger prije pokretanja; E4 zasebno tek uz unaprijed zadan prag.
3. Provjeriti stvarnu provizijsku tablicu IBKR-a i razlomljene dionice za Petrov račun prije bilo kakve procjene čestih pravila (W2, W8).
4. Za pravila koja trguju često dodati model minimalne provizije i tečaja EUR/USD u simulator (novi ID, simulator se ne mijenja unatrag).
5. Čekati stvarni pad tržišta ili ga simulirati prije ikakvog zaključka o trajnosti.

## 9. Otvorena pitanja

- Vrijedi li E4 u drugačijem režimu (ranije godine su pokazale suprotan predznak)?
- Koliko od rezultata W1, W3 i W5 je bik-tržište AI lanca (preživjeli papiri)?
- Je li minimalna provizija IBKR-a za Petrov tarif dovoljno velika da poništi W2 i W8?
- Dostupnost kripta i europskih ekvivalenata ETF-ova u IBKR-u: nepotvrđeno.
- Hash `swing.py` zapisan pri registraciji razlikuje se od hasha koda koji je pokrenuo rezultate (audit, odjeljak 10 `SWING_ENGINE.md`); parametri i tekst pravila jednaki su registru, a neovisni program je dao iste brojeve, ali što je točno promijenjeno ne može se dokazati.

## 10. Ograničenja i provjere

- AI era je jaki uzlazni period; kontrole su uvijek isti papir i isto razdoblje, ali pad nije viđen u uzorku nakon 2022.
- Svaki pojam testiran je u jednoj definiciji; druga definicija može dati drugi rezultat.
- Neovisna provjera (poseban program bez uvoza motora) slaže se na 13 od 13 kombinacija pravilo-dionica i 3 od 3 placebo brojeva; pogled u budućnost: pivoti, struktura, zone i sweepovi isti na skraćenim podacima (64 reza).
- Naslovi stranica skupina uspoređeni su s JSON-ovima: sve skupine imaju isti pobjednik, broj poslova, zaradu po poslu i omjer prema kupi-i-drži kao u tablici iz odjeljka 4 (npr. memorija W1 2,3 mj. i +77 €; oprema W1 7,4 mj.; oblak W5 90 poslova); postotak odbijanja po skupini u naslovima poklapa se s `placebo.json`.
