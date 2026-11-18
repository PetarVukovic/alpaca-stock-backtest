# Što smo otkrili: rezultati za početnika

Stanje: 2026-10-06. Sve brojke dolaze iz podataka i koda u ovom repou (nijedna nije izmišljena). Backtest nije profit i ovdje
nema obećanja zarade. Detalji po strategiji su u `reports/gate/` i `reports/backtest/`.

## Kratki odgovor

**Nijedna strategija nije prošla strogu provjeru (Critic).** Popis odobrenih (`approved_list.json`) je prazan, pa je signal **PRIČEKAJ**.
Testirali smo 22 strategije iz 9 obitelji (uključujući jedan model strojnog učenja) na MU, WDC i STX i sve su pale. To nije neuspjeh laba nego njegov posao: bolje saznati u
simulaciji nego s pravim novcem.

**Usporedba:** kao da si pokušao 21 recepta za kolač i svaki put tri stroga kuhara kažu "nije dovoljno dobro". Najbliži je kolač
C13A: prošao je 13 od 15 kušanja, a pao je na dva: jedno mjeri koliko loše može ispasti, a drugo je završni neovisni pregled.

## Zašto je teško zaraditi na ovim dionicama

1. **Zarada je skupljena u vrlo malo dana.** Samo 10 najboljih dana od 2703 daje MU-u trećinu (34 %) cijelog rasta. Bez njih bi ×74,5 bilo ×17,6.
   Strategija koja je izvan tržišta u krivi dan propusti većinu zarade. *Usporedba: kao da ti cijela godišnja plaća dođe u 10 dana.*
2. **Padovi su duboki i dugi.** MU −54 % (2018, oporavak 483 trgovačka dana), −50 % (2022, 363 dana), −58 % (2024-25).
   WDC −73 % (2018–2020, oporavak 1349 dana). *Pad od 58 % znači da 500 USD postane oko 210 USD i da treba narasti za 138 % da se vrati.*
3. **Kupi-i-drži je visoka letvica.** U razdoblju 2024. → 2026. jedna kupnja na početku donijela je MU +1213 %, WDC +1196 %, STX +997 %,
   ali uz padove od −58 %, −45 % i −41 % usput. To je posljedica booma i činjenice da smo dionice izabrali znajući da su pobijedile
   (pristranost odabira). Nitko to nije znao 2016.
4. **Sektor se kreće zajedno.** Korelacije 0,49 do 0,78: kad padne jedna, padnu i druge. Tri dionice nisu tri zaštite.
5. **Day trade ne preživljava troškove.** Prosječan pomak po satu je najviše ~4 bps, a trošak jednog kruga je 5 bps + 2 ticka. Sva četiri
   day-trade testa (H4A, H4B, H5A, H5B) imaju negativan prosjek u holdoutu.

## Što smo testirali i što je ispalo

| Obitelj | Jednostavno | Rezultat |
|---------|-------------|----------|
| Osnovne linije (B1, B2, B3) | Kupi i drži; drži samo iznad 200-dnevnog prosjeka; košarica | Mjerila: s njima se uspoređuje sve ostalo |
| Pad u trendu (C13A/B/C) | Kupi pad od 5 ili 8 % dok je dionica u rastu | **Najbliže prolazu.** C13A: 13 od 15 provjera |
| Praćenje trenda (C14A/B, C20A) | Drži dok je iznad 50, 100 ili 200-dnevnog prosjeka | Pada. U holdoutu je pad od vrha jednak kupi-i-drži (MU −60 %) |
| Proboj (C15A/B/C) | Kupi kad probije najviše iz zadnjih N dana | Pada. Premalo trgovina ili nestabilan smjer |
| Relativna snaga (C16A/B) | Drži najjaču od tri | Pada. Nestabilan predznak |
| Kolebanje (C17A/B, C18A) | Proboj nakon smirenja; odskok nakon šoka | Pada. Premalo trgovina |
| Day trade (H4A/B, H5A/B) | Gap, zadnji sat, preokret otvaranja | Pada. Troškovi pojedu učinak |
| Strojno učenje (ML1) | Model uči iz prošlih dana kad kupiti | Pada. Izgleda dobro u holdoutu samo jer je tada bio boom: ulaz *svaki dan, bez ikakvog modela*, daje sličan prosjek (+1,9 %) |

Vodeći pokazatelj (strojevi za čipove najavljuju memoriju), zarade kao smjer i riječi u naslovima vijesti **nismo ni testirali**, jer su
istraživanja pokazala da za to nema dokaza (npr. 240 testova vodstva, svi |r| < 0,09).

## Najbliža kandidatkinja: C13A (pad od 5 % u trendu)

Pravilo: dionica je iznad 200-dnevnog prosjeka, padne 5 % u 5 dana → kupi do 500 USD, drži do 10 dana ili dok ne padne 8 % od ulaza.

| Provjera | Rezultat |
|----------|----------|
| Isti smjer u svim razdobljima | da (IS +2,27 %, WF +1,57 % po trgovini, HO +6,59 %) |
| Dovoljno trgovina | da (68 + 50 + 88) |
| Radi na više dionica | da, sva tri pozitivna |
| Ispravak za broj pokušaja (Deflated Sharpe) | prolazi, p = 0,0013 |
| Vjerojatnost da je rezultat slučajnost (PBO) | 0,20 (granica 0,5) |
| **Najgori realni pad (Monte Carlo)** | **pada**: 52,7 % naspram granice 50 % |
| **Neovisni pregled (red-team)** | **pada**: bez 5 najboljih trgovina u WF razdoblju prosjek postaje negativan |

*Usporedba: dobar učenik koji je prošao gotovo sve ispite, ali je na jednom pokazao da bi u lošem tjednu mogao pasti jače nego što smo spremni
tolerirati, a profesor je primijetio da je njegovih pet najboljih zadataka nosilo cijelu ocjenu.*

U holdoutu je C13A imao najveći pad od vrha oko −13 do −22 % (naspram −41 do −58 % kod kupi-i-drži) uz sličan omjer zarade i rizika.
To je dobro, ali zarada po trgovini je mala i drži se na nekoliko trgovina.

## Kako je test bio pošten, a gdje nije

Neovisni red-team napisao je vlastiti backtest bez korištenja našeg koda i ponovio **15 756 trgovina bez ijedne razlike**. Nije našao
korištenje budućih podataka. Našao je i stvari koje nisu u redu:
- **Holdout za day trade (H5) je "viđen":** hipotezu smo izveli iz istraživanja koje je uključivalo i godine 2024+. Zato rezultat nije čisti ispit
  (i svejedno je negativan).
- **Koncentracija:** bez 5 najboljih trgovina u razdoblju WF, svi dip/trend rezultati postaju negativni.
- **Ligaška tablica je zbunjujuća:** poredala je jednu 3-godišnju trgovinu (kupi-i-drži) uz stotine day-trade trgovina. Popravak je u radu (traka A).
- **Skraćeni dani na burzi** (dan nakon Thanksgivinga, Badnjak): satni podaci ih krivo označavaju. Popravak je u radu.

## Što napraviti sada (konkretni koraci)

1. **Ne ulaži pravi novac.** Nema strategije koja je dokazana, a EU pravila za pravi račun nisu riješena (`docs/guides/regulation-eu-hr.md`).
2. **Otvori aplikaciju** (`app/README.md`) i pogledaj ekran *Signali*: vidjet ćeš zašto je odgovor PRIČEKAJ.
3. **Prati C13A kao pokus** na paper računu: u aplikaciji uključi samo tu strategiju kao *EXPERIMENTAL* (mala veličina, automatska zaštita
   obavezna). To je jedini način da dobijemo dokaz koji backtest ne može dati: kako radi na podacima koji još ne postoje.
4. **Daj mu vremena:** za zaključak treba barem 30 stvarnih trgovina. Ako C13A u 3 do 6 mjeseci izgleda kao backtest, to je prva stvarna potvrda.
5. **Ne mijenjaj pravilo usput.** Svaka promjena je nova strategija s novim ID-em i resetira brojanje.
6. **Pravilo palca za veličinu:** rizikuj pojedinačnom trgovinom malen dio računa (npr. 1 do 2 %); automatska zaštita (stop) je obavezna.
7. **Sljedeća ideja:** istraži novu obitelj čiji mehanizam nije samo cijena (fundamentalni pokazatelji, `memory-lab-fundamentals` skill), uz isti
   postupak (`docs/guides/new-hypothesis.md`).

## Rječnik

Pojmovi su u `docs/glossary.md` (npr. holdout, K, Deflated Sharpe, PBO, Monte Carlo, koncentracija povrata, gap).
