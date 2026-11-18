# Rječnik

| Pojam | Značenje |
|-------|----------|
| **Ticker** | Kratka oznaka dionice (MU = Micron). |
| **ETF** | Fond kojim se trguje kao dionicom (SMH, DRAM). |
| **OHLCV** | Open, High, Low, Close, Volume. Otvaranje, najviša, najniža, zatvaranje, količina. |
| **SIP / IEX** | Alpaca feedovi cijena. SIP je cijelo tržište, IEX je oko 2 % volumena (volumen nepouzdan). |
| **Split-adjusted** | Cijene prilagođene za podjelu dionica. |
| **Spin-off** | Izdvajanje dijela firme (WDC → SanDisk, 2025-02-24, faktor 0.68132). |
| **Paper trading** | Trgovanje lažnim novcem na pravom tržištu. |
| **Swing** | Držanje pozicije dane do tjedana. |
| **Backtest** | Simulacija pravila na prošlim cijenama. |
| **Freeze** | Zamrzavanje pravila prije testa, da se poslije ne podešavaju. |
| **Freeze ID** | Ime zamrznutog pravila (C#, H#, H-N#). |
| **IS / WF / HO** | In-sample (2016–2020), walk-forward (2021–2023), holdout (2024 →). |
| **bps** | Bazni bod, 0,01 %. 5 bps = 0,05 %. |
| **Tick** | Najmanji korak cijene. |
| **RT** | Round trip: kupnja i prodaja. |
| **n** | Broj trgovina u razdoblju. |
| **K** | Broj isprobanih pravila u kampanji (oko 46). |
| **Sharpe** | Zarada u odnosu na rizik. |
| **Deflated Sharpe** | Sharpe umanjen za broj pokušaja K. |
| **PBO** | Probability of Backtest Overfitting, vjerojatnost da je pobjednik rezultat prilagodbe. |
| **Drawdown / maxDD** | Pad od prethodnog vrha. |
| **Buy and hold (B&H)** | Kupi jednom i drži. Usporedna mjera. |
| **Lookahead** | Greška kad test koristi informaciju iz budućnosti. |
| **Overfitting** | Pravilo prilagođeno prošlosti tako da ne radi na novom. |
| **Critic / Quant Critic** | Strogi pregled koji pokušava srušiti pravilo. |
| **PASS / FAIL** | Ishod Critica. FAIL je zatvoren. |
| **approved_list** | Popis ID-eva s Critic PASS-om. Danas prazan. |
| **KUPI / PRIČEKAJ / NE KUPUJ** | Tri moguća signala. Bez PASS-a uvijek PRIČEKAJ. |
| **FAIL-like** | Oznaka za istraživačku liniju koja nije prošla, a nije formalni Critic FAIL. |
| **us_reaction_date** | Prvi američki dan u kojem cijena može reagirati na vijest. |
| **Engram** | Lokalna dugoročna memorija agenata. |
| **Skill** | Paket uputa koji agent učitava za određenu vrstu posla. |
| **Epizoda pada** | Razdoblje od vrha, preko dna, do ponovnog dostizanja starog vrha. Kao spuštanje s planine i ponovni uspon na istu visinu. |
| **Koncentracija povrata** | Koliko ukupne zarade dolazi iz malo najboljih dana. Kao plaća koja stigne u 10 dana, a ostatak godine je nula. |
| **Kolebanje (volatilnost)** | Koliko cijena skače; godišnje = dnevna std × √252. Mirna rijeka naspram divlje. |
| **Lead / lag (vodstvo i odmak)** | Pomiče li se jedna dionica prije druge za k dana. Kiša u planini koja najavi poplavu u dolini. |
| **Korelacija s odmakom** | Povezanost jučerašnjeg pomaka jedne dionice s današnjim pomakom druge; 0 znači nikakva veza. |
| **p-vrijednost** | Koliko je vjerojatno da bi se ovakav rezultat vidio i bez prave veze. Mali p = teško da je slučajno. |
| **Bonferroni korekcija** | p se množi brojem testova jer među puno testova neki 'pogode' slučajno. Kao 240 bacanja novčića: nekoliko čudnih nizova je normalno. |
| **Gap otvaranja** | Preskok od jučerašnjeg zatvaranja do današnjeg otvaranja. Trgovina preko noći promijeni cijenu. |
| **Dan reakcije** | Prvi trgovački dan nakon objave; mjeri se zatvaranje naspram prethodnog zatvaranja. |
| **Medijan** | Srednja vrijednost kad poredaš sve slučajeve; manje je osjetljiva na jedan ekstrem od prosjeka. |
| **Selection bias (pristranost odabira)** | Događaji su zapisani jer su bili važni, pa su obično ekstremni. Kao zaključivanje o lovu iz lovačkih priča. |
| **Reakcijski dan vijesti** | Prvi dan čije otvaranje slijedi objavi vijesti; vijest prije 9:30 NY isti dan, inače idući. |
| **Uhvatljivi dio pomaka** | Dio pomaka nakon što si vijest mogao vidjeti; gap prije otvaranja se ne može uhvatiti. Kao kupnja karte nakon što je vlak otišao. |
| **Satna svijeća (bar)** | Sažetak jednog sata trgovanja: otvaranje, najviša, najniža, zatvaranje. |
| **open_mixed** | Satni bar 9:00-10:00 NY koji miješa pretržišno i prvih 30 min redovne sesije; zato ne ulazi u 'regular'. |
| **Slippage (proklizavanje)** | Razlika između cijene koju očekuješ i one po kojoj se naredba stvarno izvrši. Kao kad robu platiš više jer je cijena u međuvremenu porasla. |
| **Std (standardna devijacija)** | Mjera 'koliko skače' oko prosjeka; veća = nemirnije. |
| **Preokret (reversal)** | Pomak koji se djelomično vraća (jutarnji rast se poništi do zatvaranja). Kao gumica koja se vraća. |
