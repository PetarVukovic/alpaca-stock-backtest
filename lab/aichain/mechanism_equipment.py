"""Croatian mechanism text for the equipment segment (prose for the researcher; sources are public pages)."""

from __future__ import annotations

LABEL = "kontekst iz javnih izvora, nije iz naših podataka"
WIKI = "https://en.wikipedia.org/wiki/"

GLOSSARY: dict[str, str] = {
    "volatilnost": "Koliko cijena u godini tipično 'divlja'. Volatilnost 50% na 1.000 EUR znači da je godišnji raspon tipično oko 500 EUR gore ili dolje.",
    "beta": "Koliko se dionica pomakne kad se indeks pomakne. Beta 1,2 prema SMH: kad poluvodički indeks padne 10%, ova dionica u prosjeku padne oko 12% (na 1.000 EUR to je 120 EUR).",
    "korelacija": "Koliko se dvije cijene kreću zajedno, od -1 do +1. Blizu 0,85 znači da se gotovo uvijek miču u istom smjeru istog dana.",
    "pad od vrha (drawdown)": "Pad od najviše točke do najniže prije oporavka. Pad od 50% znači da 1.000 EUR postane 500 EUR.",
    "autokorelacija": "Nastavlja li se jučerašnji smjer danas. Blago negativna vrijednost znači da se dan nakon rasta cijena malo vraća, a ne nastavlja.",
    "omjer varijance (VR)": "Mjeri nastavlja li se kretanje kroz 5 ili 20 dana. Ispod 1 znači više vraćanja prema sredini nego nastavljanja trenda, iznad 1 obratno.",
    "SMA200": "Prosjek zadnjih 200 dnevnih zatvaranja, grubi pokazatelj dugoročnog trenda. Iznad njega je dugoročni trend rastući.",
    "praznina (gap)": "Razlika između jučerašnjeg zatvaranja i današnjeg otvaranja, obično zbog vijesti preko noći.",
    "potpora i otpor": "Prijašnje dno (potpora) ili vrh (otpor) na kojem se cijena možda zaustavi. Mi mjerimo koliko često je to stvarno bilo tako, uz kontrolu s proizvoljnim razinama.",
}

COMPANIES: dict[str, dict[str, object]] = {
    "AMAT": {
        "name": "Applied Materials",
        "sells": "Strojeve kojima se čip gradi sloj po sloj: nanošenje slojeva (taloženje), jetkanje, poliranje, ionska implantacija, plus mjerenje i pregled te servis postojećih strojeva. Prodaje i opremu za zaslone.",
        "drivers": "Prihod prati koliko tvornice čipova (logika, DRAM, NAND) ulažu u nove linije i unaprjeđenja te koliko servisa plaćaju na već instaliranim strojevima. Servis je stabilniji dio, novi strojevi cikličniji.",
        "chain": "Najšira oprema u lancu: gotovo svaki proizvođač čipova, uključujući memoriju (MU, SK hynix), kupuje njihove strojeve.",
        "cycle": "Ciklus prati ulaganja tvornica: kad proizvođači memorije i logike podižu izdatke za opremu, narudžbe rastu, a kad se ulaganja zaustave, prihod padne. Izvor spominje padove prihoda 2009., 2012.-2013. i 2019.",
        "hurts": "Slaba potražnja iz Kine i američko-kineske trgovinske napetosti (izvor: dionica je u kolovozu 2025. pala 12% nakon slabe prognoze), izvozna ograničenja te kazna od 252 milijuna USD zbog isporuka prema SMIC-u (veljača 2026.).",
        "sources": [WIKI + "Applied_Materials"],
    },
    "LRCX": {
        "name": "Lam Research",
        "sells": "Strojeve za jetkanje (rezanje uzoraka u čip pomoću plazme), taloženje tankih slojeva i čišćenje pločice, uz dio opreme za pakiranje čipova.",
        "drivers": "Prihod ovisi o tome koliko tvornice ulažu u linije kod kojih ima mnogo slojeva i dubokih struktura. Izvor navodi da njihovi alati služe izradi DRAM i NAND memorije, ali udio memorije u prihodu izvor ne kvantificira.",
        "chain": "Opskrbljuje proizvođače čipova, uključujući memorijske. Ovdje je najizravnija veza prema memoriji među većim proizvođačima opreme, ali točan udio nije potvrđen u pregledanim izvorima: nepotvrđeno.",
        "cycle": "Isti ciklus ulaganja kao kod cijele opreme. Memorijski ciklus (višak ili manjak DRAM i NAND čipova, cijene) utječe na to kad će Micron i drugi naručivati strojeve: nepotvrđeno kao točan mehanizam u pregledanim izvorima.",
        "hurts": "Pauza u ulaganjima proizvođača memorije i izvozna ograničenja prema Kini. Detalji o udjelu Kine: nepotvrđeno.",
        "sources": [WIKI + "Lam_Research"],
    },
    "KLAC": {
        "name": "KLA",
        "sells": "Sustave za kontrolu procesa: pregled pločica i maski te mjerenje (nalaze greške i mjere dimenzije) kako bi tvornica povećala udio ispravnih čipova.",
        "drivers": "Prema jednom pregledanom izvoru oko 91% prihoda u drugom kvartalu fiskalne 2026. dolazilo je iz kontrole procesa. Što su čipovi složeniji, to se više provjerava, pa složenost raste brže od ukupnih ulaganja.",
        "chain": "Potreban svakome tko proizvodi napredne čipove, pa i kod memorije i naprednog pakiranja.",
        "cycle": "Prati ulaganja tvornica, ali je tipično stabilniji od jetkanja i taloženja jer treba i na postojećim linijama (ocjena iz opisa izvora, ne iz naših podataka).",
        "hurts": "Pad ulaganja u opremu, izvozna ograničenja i konkurencija većih igrača (izvor navodi ASML i AMAT).",
        "sources": [
            WIKI + "KLA_Corporation",
            "https://finance.yahoo.com/quote/KLAC?p=KLAC",
        ],
    },
    "ASML": {
        "name": "ASML",
        "sells": "Litografske strojeve koji 'otiskuju' uzorak čipa na pločicu, uključujući EUV (jedini proizvođač na svijetu) i novu High-NA generaciju.",
        "drivers": "Broj isporučenih EUV strojeva po cijeni do oko 200 milijuna USD (High-NA oko 370-400 milijuna USD) i servis. Zbog cijene je jedan stroj velik dio prihoda u kvartalu.",
        "chain": "Najuzvodnije u lancu: bez ASML-a nema najnaprednije logike ni DRAM-a. Izvor navodi da SK hynix već ugrađuje High-NA za DRAM.",
        "cycle": "Narudžbe stižu unaprijed, pa dionica često reagira na najave narudžbi, a ne na isporuke. Izvor (rujan 2026.) kaže da su postojeći EUV strojevi gotovo rasprodani do 2027.",
        "hurts": "Izvozna ograničenja prema Kini (nizozemska pravila od 2023. nadalje), odgode kupaca i visoka cijena High-NA. ASML je u SAD-u kotiran kao ADR, pa vrijedi isto kao dionica, ali uvijek provjeri valutu i dostupnost u IBKR-u: nepotvrđeno.",
        "sources": [
            WIKI + "ASML_Holding",
            "https://www.thestar.com.my/tech/tech-news/2026/09/14/analysis-asml-extends-chipmaking-dominance-as-customers-embrace-high-na",
        ],
    },
    "ONTO": {
        "name": "Onto Innovation",
        "sells": "Opremu i softver za mjerenje i pregled pločica i paketa čipova te litografiju za napredno pakiranje.",
        "drivers": "Ulaganja u napredno pakiranje (slaganje čipova, HBM) i kontrolu procesa. Prihod 2025. oko 1,01 milijardu USD, što je mala tvrtka u usporedbi s AMAT-om.",
        "chain": "Veza s HBM-om preko naprednog pakiranja je logična, ali udio nije potvrđen u pregledanim izvorima: nepotvrđeno.",
        "cycle": "Manja tvrtka s koncentriranim kupcima pa su pomaci narudžbi vidljivi u dionici. Točna struktura kupaca nije potvrđena.",
        "hurts": "Odgode ulaganja kupaca i jaka konkurencija većih igrača u kontroli procesa.",
        "sources": [WIKI + "Onto_Innovation"],
    },
    "MKSI": {
        "name": "MKS Instruments",
        "sells": "Komponente i podsustave unutar strojeva: mjerenje tlaka u vakuumu, isporuka plinova, napajanje plazme, laseri, a nakon preuzimanja Atotecha i kemikalije za oplemenjivanje površina.",
        "drivers": "Oko 60% prodaje (stanje 2021.) dolazilo je iz poluvodiča, ostatak iz tiskanih pločica i industrije. Prodaje stroj-proizvođačima poput AMAT-a i LRCX-a, pa je 'oprema opreme'.",
        "chain": "Posredno: njihovi dijelovi ulaze u strojeve koje kupuju proizvođači čipova.",
        "cycle": "Pojačava ciklus kupaca jer prvi osjeti kad Lam ili Applied smanje narudžbe, ali dio prihoda iz industrije ga ublažava.",
        "hurts": "Pad narudžbi proizvođača opreme.",
        "sources": [WIKI + "MKS_Instruments"],
    },
    "ENTG": {
        "name": "Entegris",
        "sells": "Filtere, materijale i sustave koji štite čip od nečistoća: filtracija plinova i tekućina, nosači pločica, specijalni plinovi i materijali.",
        "drivers": "Oko 80% proizvoda ide u poluvodiče (izvor). Dio prihoda je potrošni materijal koji se troši koliko tvornice rade, a ne samo kad grade nove linije.",
        "chain": "Uzvodni dobavljač za sve proizvođače čipova, pa i memorijske.",
        "cycle": "Manje ciklično od strojeva jer prati iskorištenost tvornica; prihod za 2025. oko 3,2 milijarde USD uz pad, nakon prodaja dijelova poslovanja 2023. i 2024.",
        "hurts": "Niska iskorištenost tvornica i smanjenje opsega poslovanja zbog prodaja.",
        "sources": [WIKI + "Entegris"],
    },
    "ACMR": {
        "name": "ACM Research",
        "sells": "Strojeve za mokro čišćenje pločica (tehnologija SAPS) i elektroplatiranje za pakiranje.",
        "drivers": "Prema izvoru većina poslovanja je u Kini; kupci uključuju SK hynix, SMIC, Hua Hong i YMTC. Prihod 2023. oko 558 milijuna USD.",
        "chain": "Mala oprema za čišćenje u kineskim i korejskim tvornicama, uključujući memoriju.",
        "cycle": "Ovisi o kineskim ulaganjima u tvornice i političkim pravilima. Podružnice su u prosincu 2024. stavljene na američki popis ograničenja (Entity List).",
        "hurts": "Geopolitika (američki popis ograničenja), koncentracija u Kini, vrlo visoka volatilnost dionice. Za Petra: mala i tanko trgovana dionica, strožiji trošak.",
        "sources": [WIKI + "ACM_Research"],
    },
    "FORM": {
        "name": "FormFactor",
        "sells": "Sonde i probne kartice kojima se čipovi testiraju dok su još na pločici, te sustave za mjerenje i testiranje.",
        "drivers": "Broj novih čipova koje treba testirati, posebno složenijih. Izvor o udjelu DRAM-a ili HBM-a nema podataka: nepotvrđeno.",
        "chain": "Test čipova prije rezanja; veza s memorijom moguća, ali nije potvrđena u pregledanim izvorima.",
        "cycle": "Prati lansiranja novih čipova i ulaganja u testiranje.",
        "hurts": "Odgode novih generacija čipova i pad ulaganja u test.",
        "sources": [WIKI + "FormFactor,_Inc."],
    },
    "TER": {
        "name": "Teradyne",
        "sells": "Automatsku opremu za testiranje čipova (ATE), testiranje fleša i analognih čipova, robote (Universal Robots) i ostale testne sustave.",
        "drivers": "Broj i složenost čipova koji se testiraju. Prihod 2024. oko 2,82 milijarde USD. Veza s HBM-om i AI-jem nije potvrđena u pregledanim izvorima: nepotvrđeno.",
        "chain": "Zadnja stanica prije pakiranja: svaki čip se mora testirati, pa raste s brojem proizvedenih čipova.",
        "cycle": "Ciklus prati lansiranja AI čipova, mobilnu i auto-elektroniku; robotika dodaje drugi izvor prihoda.",
        "hurts": "Slabija potražnja za mobilnim i autoindustrijskim čipovima i padovi narudžbi.",
        "sources": [WIKI + "Teradyne"],
    },
}
