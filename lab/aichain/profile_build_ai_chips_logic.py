"""Assemble profile.json for segment ai_chips_logic: shared stats (profile_stats.py) + Croatian text.

Reads segments/ai_chips_logic/_stats_raw.json (written by `python -m lab.aichain.profile_stats ai_chips_logic`).
All numbers in the text are formatted from that file; business facts are hand-written from the
cited public pages and flagged as context, not data. Descriptive only: no signal, no strategy.
Run: .venv/bin/python -m lab.aichain.profile_build_ai_chips_logic
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SEG_DIR = (
    ROOT / "reports" / "research" / "AICHAIN_20261014" / "segments" / "ai_chips_logic"
)
CONTEXT_TAG = "kontekst iz javnih izvora, nije iz naših podataka"
WIKI = "https://en.wikipedia.org/wiki/"

# Business facts: each statement comes from the cited page (fetched 2026-10-14). Cycle remarks marked "opći kontekst".
MECH: dict[str, dict[str, Any]] = {
    "NVDA": {
        "sells": "Prodaje grafičke procesore (GPU) i cijele sustave za podatkovne centre, uz softversku platformu CUDA. Najveći dio prihoda dolazi iz podatkovnih centara (računanje i mreža: 89 posto prihoda u 2025. prema izvoru).",
        "drivers": "Prihod vuče potražnja velikih tehnoloških firmi i cloud pružatelja za AI hardverom. Izvor navodi da je rast prodaje podatkovnih centara posljedica izgradnje AI infrastrukture.",
        "chain": "Gornji dio lanca: kupac memorije (HBM) i napredne proizvodnje. Tvrtka je bez vlastitih tvornica; proizvodnju radi TSMC, a memoriju i podloge nabavlja od dobavljača. Dakle NVDA troši ono što memorijske tvrtke i TSMC proizvode.",
        "cycle": "Ciklus ovisi o investicijama cloud kupaca u podatkovne centre (opći kontekst): kad oni povećaju proračune, narudžbe rastu, kad ih uspore, rast se naglo gasi.",
        "hurts": "Američka ograničenja izvoza naprednih čipova u Kinu, antitrust istraga ministarstva pravosuđa iz 2024., ovisnost o jednom proizvođaču (TSMC).",
        "source": WIKI + "Nvidia",
    },
    "AMD": {
        "sells": "Prodaje procesore (Ryzen, Epyc), grafičke kartice (Radeon), AI ubrzivače (Instinct), FPGA čipove (Xilinx) i posebne čipove za igraće konzole.",
        "drivers": "Izvor navodi povratak tržišnog udjela zahvaljujući Ryzenu, rast udjela u poslužiteljskim procesorima od 2024. (36,5 posto u srpnju 2025. prema izvoru), ugovor s OpenAI-jem iz listopada 2025. i seriju AI poslužitelja MI400.",
        "chain": "Bez vlastitih tvornica (proizvodnju radi vanjski proizvođač, vidi TSMC). Glavni konkurent u procesorima je Intel, a u AI ubrzivačima Nvidia.",
        "cycle": "Dvije noge: računala i igrače konzole prate potrošački ciklus, a podatkovni centri investicijski ciklus cloud kupaca (opći kontekst).",
        "hurts": "Izvor spominje ponavljana otpuštanja u prošlosti i pogrešne proizvode (Bulldozer). Ovisnost o vanjskoj proizvodnji i jakoj konkurenciji je opći kontekst.",
        "source": WIKI + "AMD",
    },
    "AVGO": {
        "sells": "Prodaje poluvodiče (prilagođeni AI čipovi, Ethernet preklopnici, Wi-Fi i širokopojasni čipovi) i softver (VMware, Symantec). Prema izvoru, u 2025. oko 58 posto prihoda bila su poluvodiči, a 42 posto softver i usluge.",
        "drivers": "Prilagođeni AI čipovi (XPU) za velike cloud kupce: izvor navodi suradnju na Googleovim TPU čipovima i Metinim MTIA čipovima te rad s OpenAI-jem na čipu za inferenciju od 2024. Softverski dio daje stabilniji prihod nakon akvizicije VMwarea (2023.).",
        "chain": "Strana potražnje za AI mrežama i prilagođenim čipovima; ne proizvodi memoriju. Prodaje istim cloud kupcima koji kupuju od Nvidije.",
        "cycle": "Poluvodički dio prati investicije cloud kupaca u AI; softverski dio je stabilniji (opći kontekst).",
        "hurts": "Antitrust postupci EU-a oko VMwarea, ovisnost o malom broju velikih kupaca (opći kontekst).",
        "source": WIKI + "Broadcom_Inc.",
    },
    "MRVL": {
        "sells": "Prodaje podatkovne procesore, prilagođene čipove (custom ASIC), Ethernet preklopnike i kontrolere za diskove i SSD-ove; tržišta su podatkovni centri, operateri, poduzeća i automobili.",
        "drivers": "Izvor ne navodi pokretače izravno, ali prikazuje rast prihoda s 5,5 mlrd USD (FY2024) na 8,2 mlrd USD (FY2026) uz akvizicije u podatkovnim centrima i fotonici (Innovium, Celestial AI).",
        "chain": "Dobavljač mrežnih i prilagođenih čipova cloud kupcima; srodna uloga kao Broadcom, ali manji. Čipovi za pohranu (SSD/HDD kontroleri) dodiruju memorijski lanac.",
        "cycle": "Mješavina AI investicijskog ciklusa u podatkovnim centrima i sporijih tržišta (operateri, poduzeća), koja imaju vlastiti ciklus zaliha (opći kontekst).",
        "hurts": "Prema izvoru neto dobit je bila negativna u većini godina 2019.-2025. (računovodstveno, dijelom zbog akvizicija); povijest pravnih sporova.",
        "source": WIKI + "Marvell_Technology",
    },
    "TSM": {
        "sells": "Ugovorni proizvođač čipova (foundry): proizvodi čipove za druge tvrtke, uz napredno pakiranje i testiranje. Izvor ga navodi kao glavnog dobavljača Nvidije, Applea, Broadcoma i Qualcomma.",
        "drivers": "Potražnja za najnaprednijim procesima (3 nm od kraja 2022., 2 nm krajem 2025.). Prema izvoru, u srpnju 2026. podigao je plan ulaganja za 2026. na 60-64 mlrd USD zbog snažne potražnje za AI čipovima.",
        "chain": "Središnje usko grlo lanca: gotovo svi AI čipovi iz ovog segmenta (NVDA, AMD, AVGO, MRVL, ARM kupci, QCOM) prolaze kroz TSMC. TSM je dionica koja se kupuje u SAD-u kao ADR (američki certifikat na tajvansku dionicu).",
        "cycle": "Ciklus ovisi o iskorištenosti tvornica i velikim investicijama (capex); kad kupci smanje narudžbe, fiksni troškovi tvornica pritišću zaradu (opći kontekst).",
        "hurts": "Geopolitički rizik oko Tajvana (izvor navodi da gradi tvornice u Japanu i SAD-u radi smanjenja rizika) i izvozne kontrole.",
        "source": WIKI + "TSMC",
    },
    "INTC": {
        "sells": "Prodaje procesore za računala i poslužitelje, grafičke kartice (Arc), SSD-ove, FPGA te usluge ugovorne proizvodnje (Intel Foundry).",
        "drivers": "Izvor opisuje gubitak udjela u poslužiteljskim procesorima: udio Intela pao je s preko 90 posto 2020. na 63,3 posto u 3. tromjesečju 2025. Strategija IDM 2.0 gradi vlastitu ugovornu proizvodnju. U kolovozu 2025. američka je država kupila 9,9 posto udjela.",
        "chain": "Jedini u segmentu s vlastitim tvornicama za velik dio proizvodnje; konkurent AMD-u. Izvor navodi razgovore o AMD-u kao kupcu Intelove proizvodnje (listopad 2025.).",
        "cycle": "Ciklus računala i poslužitelja uz dugotrajne investicije u tvornice; zakašnjenja procesa (npr. 10 nm prema izvoru) odgađaju povrat (opći kontekst).",
        "hurts": "Prema izvoru: operativni gubitak 2,21 mlrd USD u 2025., otpuštanje oko 24.000 radnika, kašnjenja proizvodnih procesa, jaka konkurencija AMD-a i Appleovih čipova.",
        "source": WIKI + "Intel",
    },
    "ARM": {
        "sells": "Ne prodaje čipove nego licencira dizajn procesorskih jezgri i arhitekturu; kupci grade vlastite čipove. Prihod su licence i naknade po uređaju (royalties).",
        "drivers": "Broj uređaja i čipova koji koriste Arm dizajn (mobiteli, računala, poslužitelji). Izvor navodi da je 2023. planirao naknade vezati uz vrijednost uređaja, ne samo čipa. Prihod do 31.3.2026.: 4,92 mlrd USD.",
        "chain": "Sloj dizajna iznad proizvodnje: njegove licencije koriste Qualcomm, Samsung, Nvidia i drugi. Ne dodiruje memoriju izravno.",
        "cycle": "Prati prodaju pametnih uređaja i novih generacija čipova; licenčni prihod je stabilniji od prodaje čipova (opći kontekst).",
        "hurts": "Propao pokušaj preuzimanja od Nvidije (veljača 2022.), sporovi oko Arm Kine, konkurencija u poslužiteljima. U AI eri nema duge povijesti: uvršten na Nasdaq 14.9.2023.",
        "source": WIKI + "Arm_Holdings",
    },
    "TXN": {
        "sells": "Prodaje analogne čipove (pretvaraju stvarne signale poput napona i temperature u digitalne) i ugrađene procesore; preko 80 posto prihoda prema izvoru.",
        "drivers": "Tržišta: industrija (41 posto prihoda, podatak iz siječnja 2021.) i automobili (21 posto). Vlastite 300 mm tvornice daju troškovnu prednost (npr. otkup tvornice u Lehiju od Microna za 900 mil USD, 2021.).",
        "chain": "Gotovo nije vezan uz AI lanac; to je 'klasična' industrijska poluvodička tvrtka. Služi kao usporedba: kako se ponaša čip koji nije AI.",
        "cycle": "Klasični ciklus zaliha: kupci nakupe zalihe, pa ih godinu-dvije troše; izvor pokazuje pad prihoda 2009., 2013., 2019. i 2023. (17,5 mlrd USD s 20,0 mlrd USD).",
        "hurts": "Slaba industrijska i automobilska potražnja te visoka ulaganja u tvornice. Najavljeno preuzimanje Silicon Labsa (7,5 mlrd USD, veljača 2026.) prema izvoru.",
        "source": WIKI + "Texas_Instruments",
    },
    "MCHP": {
        "sells": "Prodaje mikrokontrolere (PIC, AVR), analogne čipove za napajanje, USB i CAN/LIN sučelja i srodne proizvode.",
        "drivers": "Izvor ne daje pokretače potražnje; navodi veće akvizicije (Atmel 3,56 mlrd USD, Microsemi 2018.) i prihod 4,40 mlrd USD u 2025.",
        "chain": "Slično kao TXN: nije u jezgri AI lanca. Prodaje industrijskoj i automobilskoj opremi (opći kontekst).",
        "cycle": "Izraziti ciklus zaliha: kupci naglo smanje narudžbe kad im zalihe narastu (opći kontekst). Izvor navodi zatvaranje tvornice Fab 2 u Tempeu (studeni 2024.) i povremena prisilna slobodna razdoblja radnika tijekom 2025.",
        "hurts": "Izvor: neto rezultat u 2025. oko nule (-2,7 mil USD), suspenzija prijave za američke poticaje (CHIPS Act), zatvaranje tvornice.",
        "source": WIKI + "Microchip_Technology",
    },
    "ON": {
        "sells": "Prodaje čipove za upravljanje snagom, diskretne komponente (uključujući silicijev karbid), logiku i prilagođene slikovne senzore.",
        "drivers": "Tržišta: automobili, industrija, komunikacije, računala i drugo. Izvor ne navodi pokretače; spominje preuzimanje Qorvoove SiC JFET jedinice (prosinac 2024.) i najavu preuzimanja Synapticsa (lipanj 2026., oko 7 mlrd USD u dionicama).",
        "chain": "Najvećim dijelom izvan AI lanca; veza je preko energije za podatkovne centre (opći kontekst).",
        "cycle": "Ciklus zaliha i automobilske/industrijske potražnje; silicijev karbid ovisi o brzini uvođenja električnih vozila (opći kontekst).",
        "hurts": "Izvor bilježi pad prihoda, operativne i neto dobiti u 2025.",
        "source": WIKI + "ON_Semiconductor",
    },
    "QCOM": {
        "sells": "Prodaje Snapdragon procesore i modeme za mobitele (odjel QCT, oko 80 posto prihoda prema izvoru) i licencira patente (QTL, oko 19 posto).",
        "drivers": "Prodaja pametnih telefona, 5G, automobili i IoT (izvor: automobili jedan od najbrže rastućih odjela) te računalstvo na rubu mreže. Apple je glavni imenovani kupac.",
        "chain": "Izvan jezgre AI lanca: proizvodi mobilne čipove (proizvodi ih TSMC), a koristi Arm licencu. Povezan je s AI-jem kroz AI na uređaju.",
        "cycle": "Ciklus pametnih telefona i zamjene uređaja; licenčni dio je stabilniji (opći kontekst).",
        "hurts": "Antitrust postupci u SAD-u, EU, Južnoj Koreji, Tajvanu i Kini, spor s Armom, ovisnost o Appleu (prema izvoru).",
        "source": WIKI + "Qualcomm",
    },
}

GLOSSARY = {
    "volatilnost": "Koliko cijena u godini tipično 'titra'. Ako je 48 posto, na 1.000 EUR običan raspon godine je otprilike od -480 do +480 EUR oko prosjeka; to nije prognoza nego mjera nemira.",
    "beta": "Koliko se dionica pomakne kad se cijeli sektor (SMH) pomakne za 1 posto. Beta 1,3 znači: sektor +1 posto, dionica u prosjeku +1,3 posto.",
    "korelacija": "Koliko se dvije cijene kreću u istom smjeru, od -1 do +1. Blizu 1 znači da ih ne možete tretirati kao dvije odvojene oklade.",
    "najveći pad od vrha": "Koliko je cijena pala od svog najvišeg vrha do dna prije nego se vratila. Pad od 37 posto znači da bi 1.000 EUR privremeno postalo 630 EUR.",
    "autokorelacija": "Je li dan nakon rasta češće opet rast (pozitivno) ili pad (negativno). Blizu nule znači da jučerašnji dan ne govori ništa o današnjem.",
    "omjer varijance (VR)": "Usporedba titranja kroz 5 ili 20 dana s titranjem jednog dana. Ispod 1: pomaci se djelomično poništavaju (sklonost vraćanju). Iznad 1: pomaci se nastavljaju (sklonost trendu). Oko 1: kao slučajno hodanje.",
    "SMA200": "Prosjek zadnjih 200 zaključnih cijena. Cijena iznad njega znači dugoročni uzlazni trend.",
    "stopa pogotka": "Udio slučajeva u kojima je cijena nakon događaja bila viša. U jakom uzlaznom razdoblju je i bez ikakvog uvjeta preko 55-60 posto, zato uvijek gledamo razliku prema svim danima.",
    "t-vrijednost": "Mjera je li razlika veća od slučajne. Okvirno: ispod 2 po apsolutnoj vrijednosti ne možemo je razlikovati od sreće.",
    "događaji se preklapaju": "Nakon pada od 5 posto često slijedi još padova pa se isti 'događaj' ponavlja nekoliko dana zaredom. Zato uz sve događaje navodimo i razrijeđene (barem 10 dana razmaka).",
}


def pct(x: float | None, nd: int = 0) -> str:
    return "nema podatka" if x is None else f"{x:.{nd}f}".replace(".", ",")


def character(w: dict[str, Any]) -> str:
    vr20, ac1 = w["var_ratio_20d"], w["autocorr_lag1_5"][0]
    if vr20 < 0.9:
        kind = "sklonost vraćanju (pomaci se kroz 20 dana djelomično poništavaju)"
    elif vr20 > 1.05:
        kind = "sklonost nastavku trenda"
    else:
        kind = "blizu slučajnog hoda (bez jasnog trenda ili vraćanja)"
    return f"{kind}; omjer varijance 5d {pct(w['var_ratio_5d'], 2)}, 20d {pct(vr20, 2)}; autokorelacija dan-na-dan {pct(ac1, 3)}."


def c13_text(w: dict[str, Any]) -> str:
    ev = w["after_5d_drop_ge5pct_above_sma200"]
    a, th = ev["all_events"], ev["thinned_events_10d_apart"]
    f5, t5 = a["fwd_5d"], th["fwd_5d"]
    f20 = th["fwd_20d"]
    return (
        f"Nakon pada od najmanje 5 posto u 5 dana uz cijenu iznad SMA200: {a['n_events']} dana, od toga {th['n_events']} razrijeđenih (10+ dana razmaka). "
        f"Za 5 dana: prosjek {pct(f5['mean_pct'], 1)} posto naprema {pct(f5['uncond_mean_pct'], 1)} posto u svim danima; stopa pogotka {pct(f5['hit_pct'])} posto naprema {pct(f5['uncond_hit_pct'])} posto "
        f"(razrijeđeno: {pct(t5['mean_pct'], 1)} posto, t={pct(t5['t_vs_uncond'], 1)}). Za 20 dana (razrijeđeno): {pct(f20['mean_pct'], 1)} posto naprema {pct(f20['uncond_mean_pct'], 1)} posto, t={pct(f20['t_vs_uncond'], 1)}."
    )


def narrative(tk: str, p: dict[str, Any]) -> str:
    w = p["ai_era"]
    dd = w["drawdowns"][0]
    best = w["top10_best_days"]
    lines = [
        f"U AI eri ({w['from']} do {w['to']}, {w['days']} dana) {tk} je donio {pct(w['total_return_pct'])} posto (1.000 EUR bi postalo oko {pct(1000 * (1 + w['total_return_pct'] / 100))} EUR u dolarskoj cijeni, bez tečaja i troškova, samo opis prošlosti), volatilnost {pct(w['ann_vol_pct'])} posto godišnje.",
        f"Beta prema SMH {pct(w['beta_smh'], 2)} (korelacija {pct(w['corr_smh'], 2)}), prema NDX {pct(w['beta_ndx'], 2)} (korelacija {pct(w['corr_ndx'], 2)}).",
        f"Najgori pad od vrha: {pct(dd['depth_pct'], 1)} posto ({dd['start']} do {dd['bottom']}; oporavak {dd['recovery'] or 'još nije'}); na 1.000 EUR to je privremeno oko {pct(1000 * (1 + dd['depth_pct'] / 100))} EUR.",
        f"Karakter: {character(w)}",
        c13_text(w),
        f"10 najboljih dana čine {pct(best['sum_logret_share_of_total_pct'])} posto ukupnog (logaritamskog) prinosa"
        + (
            " (preko 100 posto znači da su ostali dani zajedno bili u minusu)"
            if best["sum_logret_share_of_total_pct"] > 100
            else ""
        )
        + f"; bez tih dana ukupni prinos bio bi {pct(best['total_return_without_best10_pct'])} posto.",
        f"Vodi li ili kasni: prema SMH {w['lead_lag']['smh']['verdict']}, prema ostalima u segmentu {w['lead_lag']['peers']['verdict']}.",
    ]
    return " ".join(lines)


def summary(raw: dict[str, Any]) -> list[str]:
    """Segment-level findings in Croatian, formatted from the pooled numbers."""
    pc = raw["pooled_c13_premise_ai_era"]
    f5, f20 = pc["fwd_5d"], pc["fwd_20d"]
    return [
        f"Premisa C13C (pad od 5 posto uz cijenu iznad SMA200): skupno {f5['n_events_pooled']} dana kroz 11 dionica; za 5 dana prosjek {pct(f5['mean_pct'], 1)} posto naprema {pct(f5['uncond_mean_pct_avg_of_tickers'], 1)} posto u svim danima, stopa pogotka {pct(f5['hit_pct'])} naprema {pct(f5['uncond_hit_pct_avg_of_tickers'])} posto. Za 20 dana prosjek {pct(f20['mean_pct'], 1)} naprema {pct(f20['uncond_mean_pct_avg_of_tickers'], 1)} posto.",
        "Kratkoročno (1-5 dana) blago odbijanje je vidljivo, ali ne kod svake dionice, a za 20 dana nakon pada nema prednosti pred prosjekom; to je opis, ne dokaz, jer se događaji preklapaju (isti pad vuče više dana) i dolaze iz nekoliko velikih padova.",
        "Segment je jako povezan sa SMH (korelacija 0,6-0,8), pa se ne ponaša kao 11 neovisnih oklada. Analogni čipovi (TXN, MCHP, ON, QCOM) imaju slabiji AI prinos i veći udio prinosa u nekoliko dana.",
    ]


def main() -> None:
    raw = json.loads((SEG_DIR / "_stats_raw.json").read_text())
    tickers: dict[str, Any] = {}
    for tk in raw["tickers_used"]:
        p = raw["stats"][tk]
        entry: dict[str, Any] = {"stats": p, "opis_hr": narrative(tk, p)}
        m = MECH[tk]
        entry["mehanizam_hr"] = {
            "sto_prodaje": m["sells"],
            "sto_vodi_prihod": m["drivers"],
            "mjesto_u_lancu": m["chain"],
            "tipican_ciklus": m["cycle"],
            "sto_ga_boli": m["hurts"],
            "oznaka": CONTEXT_TAG,
            "izvor": m["source"],
        }
        if "skipped" in p.get("pre_2023", {}):
            entry["napomena_hr"] = (
                "Nema povijesti prije 2023. (uvrštena na burzu 14.9.2023.), pa prozor 2016.-2022. ne postoji; sve brojke su iz kratkog uzorka."
            )
        tickers[tk] = entry
    out = {
        "segment": "ai_chips_logic",
        "naslov_hr": "AI procesori, logika i analogni čipovi: profil ponašanja i mehanizma",
        "common_end": raw["common_end"],
        "tickers_used": raw["tickers_used"],
        "excluded": raw["excluded"],
        "ai_era_start": "2023-01-01",
        "rjecnik_hr": GLOSSARY,
        "sazetak_hr": summary(raw),
        "pooled_c13_premise_ai_era": raw["pooled_c13_premise_ai_era"],
        "ogranicenja_hr": [
            "Sve brojke su opis prošlosti izračunat iz dnevnih CSV-ova, nisu strategija, signal ni Critic PASS.",
            "AI era (od 2023.) je rast cijelog sektora: i bez ikakvog uvjeta većina dana, tjedana i mjeseci završava u plusu, pa stope pogotka treba čitati kao razliku prema svim danima.",
            "NDX datoteka ima nedosljedne unutardnevne cijene, korišten je samo zaključni tečaj za beta i korelaciju.",
            "Sezonalnost po mjesecu ima 3-4 opažanja u AI eri: samo opis, ne zaključak.",
            "Podrška i otpor: stvarne razine uspoređene su s proizvoljnim razinama (placebo) da se vidi je li reakcija išta više od slučajne.",
            "Poslovne činjenice dolaze s javnih stranica (Wikipedia) i označene su kao kontekst; nisu provjerene u godišnjim izvješćima, pa ih treba čitati kao okvirne.",
            "Dostupnost kod Interactive Brokersa i porezni tretman za Petra: nepotvrđeno. TSM je američki ADR, a ne izravna tajvanska dionica.",
        ],
        "tickers": tickers,
    }
    (SEG_DIR / "profile.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("written", SEG_DIR / "profile.json")


if __name__ == "__main__":
    main()
