# Trgovanje iz Hrvatske: EU pravila (orijentacija)

Danas je sve **paper** (lažni novac), pa se ništa od ovoga još ne primjenjuje. Ovo je popis stvari na koje treba paziti
**prije** nego jednog dana uložiš pravi novac. Nije pravni ni porezni savjet. Pravila se mijenjaju, a pojedinosti treba
provjeriti kod brokera i poreznog savjetnika.

## Što treba provjeriti prije live tradinga

| Tema | Što to znači jednostavno | Što provjeriti |
|------|--------------------------|----------------|
| **Broker unutar EU pravila** | Broker mora smjeti poslovati s klijentima iz Hrvatske i podlijegati EU nadzoru (MiFID II) | Primaju li hrvatske rezidente za pravi račun? Alpaca radi s paper računom, ali dostupnost pravog računa iz Hrvatske nije potvrđena u ovom projektu |
| **Zaštita ulagatelja** | EU broker mora provjeriti znaš li što radiš (upitnik "primjerenosti"), a mala ulaganja imaju zaštitna pravila | Što broker traži od tebe i što ti smije ponuditi |
| **ETF-ovi iz SAD-a** | Mnogi američki ETF-ovi (npr. SMH) često se ne mogu kupiti iz EU bez dokumenta KID (PRIIPs pravilo). Pojedinačne dionice (MU, WDC, STX) obično nemaju taj problem | Može li se SMH ili slični ETF kupiti preko tvog brokera. Za strategije koristiti dionice ako ETF nije dostupan |
| **Poluga i CFD-ovi** | EU ograničava polugu za male ulagatelje. Alpaca paper račun ima "multiplier 4", što **nije** realno stanje stvari | Ne planirati strategije koje ovise o poluzi ni shortanju dok se ne provjeri što broker dopušta |
| **Porezi u Hrvatskoj** | Dobit od prodaje vrijednosnica oporezuje se; stope i pravila se mijenjaju | Aktualna pravila kod poreznog savjetnika. Američke dividende imaju i porez zadržan u SAD-u, često uz obrazac W-8BEN |
| **Valuta** | Dionice su u dolarima, a ti računaš u eurima. Tečaj može pojesti ili povećati dobit | Aplikacija mora prikazati i iznos u eurima |
| **Radno vrijeme** | Američka burza radi otprilike 15:30 do 22:00 po zagrebačkom vremenu | Sve je u aplikaciji prikazano po zagrebačkom vremenu |

## Što to znači za gradnju aplikacije već sada

1. **Zamjenjivi broker.** Aplikacija ovisi o sučelju `Broker`, a ne o Alpaci. Jednog dana se mijenja samo adapter.
2. **Dnevnik trgovanja za porez.** Svaka transakcija sprema se s datumom, količinom, cijenom, troškom i tečajem EUR/USD
   (kad bude dostupan), uz izvoz u CSV. To je ono što će trebati za poreznu prijavu.
3. **Prikaz u eurima** uz dolare.
4. **Dostupnost instrumenata.** Aplikacija označava instrumente koje broker možda neće moći ponuditi iz EU (npr. ETF bez KID-a).
5. **Nema poluge ni shorta** u zadanim postavkama aplikacije.
6. **Paper uvijek odvojen od pravog.** Jasno vidljiva oznaka "PAPER" na svakom ekranu.

## Odluka koja ostaje tvoja

Prijelaz na pravi novac je zasebna odluka (promjena `PAPER_ONLY`, drugi broker, porezno uređenje). Ovaj projekt do tada ostaje paper.
