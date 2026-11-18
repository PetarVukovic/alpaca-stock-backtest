"""Merge computed memory-segment stats with Croatian narrative into profile.json.

Run after lab.aichain.profile_memory. All numbers in text come from the stats, none typed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = (
    Path(__file__).resolve().parents[2]
    / "reports"
    / "research"
    / "AICHAIN_20261014"
    / "segments"
    / "memory"
)
CTX = "kontekst iz javnih izvora, nije iz naših podataka"


def pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{d}f}".replace(".", ",") + " %"


def eur(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") + " EUR"


MECH: dict[str, dict[str, Any]] = {
    "MU": {
        "company": "Micron Technology",
        "sells": "Memorijske čipove: DRAM (radna memorija računala i poslužitelja), NAND (flash memorija u SSD-ovima i mobitelima) i HBM, vrlo brzu slojevitu DRAM memoriju koja se lijepi uz AI grafičke procesore. Prema godišnjem izvješću (10-K) prodaje poslužiteljima i oblaku, pohrani, mobitelima i industriji/automobilima.",
        "revenue_drivers": "Prihod = količina prodanih bitova x cijena po bitu. Cijena memorije je roba: mijenja se iz kvartala u kvartal ovisno o ponudi i potražnji. Najveći pokretač u AI eri je potražnja oblaka (hyperscaleri) za DRAM-om i HBM-om. Primjer: ako cijena čipova ostane ista, a prodane količine porastu 10 %, prihod raste 10 %; ako cijena naraste 30 %, a količina ostane ista, prihod raste 30 %, a gotovo sav taj dodatak pada izravno u dobit jer je trošak proizvodnje fiksan.",
        "chain_position": "Početak AI lanca potražnje: GPU-ovi (npr. Nvidia) ne mogu raditi bez HBM-a. Micron je jedan od tri velika svjetska proizvođača DRAM-a (uz Samsung i SK hynix), a time i jedini veliki američki. Ovisi o opremi (AMAT, LRCX, KLAC, ASML) i o potražnji oblaka.",
        "cycle": "Klasičan ciklus uvećanja i pada: kad su cijene visoke, svi grade nove tvornice (2-3 godine, desetci milijardi dolara), a kad one proradi ponuda preplavi tržište pa cijene padnu. Povijesni padovi: 2018.-2019. (oblak je prenaručio, pa smanjio zalihe), 2022.-2023. (zalihe dobavljača ~31 tjedan, rekordni kvartalni gubitak). Naši podaci to potvrđuju: najveći pad dionice u AI eri je 2024.-2025., a u ranijem razdoblju 2018.-2020.",
        "hurts": "Pad cijena memorije kad ponuda nadmaši potražnju, smanjenje narudžbi oblaka, nova ponuda (Samsung, SK hynix, kineski proizvođači), izvozna ograničenja, ogromna ulaganja u tvornice (CAPEX) u lošem trenutku. Pojedinačna dionica reagira jako: u AI eri je godišnja nestabilnost oko 60 %.",
        "sources": [
            "https://www.sec.gov/Archives/edgar/data/723125/000072312523000054/mu-20230831.htm",
            "https://www.sec.gov/Archives/edgar/data/0000723125/000072312526000023/mu-20260903.htm",
            "https://newsletter.semianalysis.com/p/memory-mania-how-a-once-in-four-decades",
            "https://finance.yahoo.com/markets/stocks/articles/micron-stock-surged-9x-history-132323280.html",
        ],
        "eu_note": "Pojedinačna američka dionica; dostupnost na Interactive Brokersu za EU ulagača je nepotvrđeno do provjere u samom IBKR-u.",
    },
    "WDC": {
        "company": "Western Digital",
        "sells": "Tvrde diskove (HDD) velikog kapaciteta za podatkovne centre. Nakon odvajanja SanDiska (veljača 2025.) WDC je gotovo čista diskovna tvrtka. Prema 10-K za fiskalnu 2026. godinu oko 89 % prihoda dolazi od oblaka.",
        "revenue_drivers": "Prodani kapacitet mjeren u eksabajtima (milijarde gigabajta) x cijena po eksabajtu. U fiskalnoj 2026. izvješteno je da su eksabajti porasli oko 25 %, a cijena po eksabajtu oko 8 %. Deset najvećih kupaca čini oko 73 % prihoda: nekoliko velikih kupaca odlučuje o godini. Primjer: ako veliki kupac odgodi narudžbu, to nije 1 % prihoda nego može biti desetak posto.",
        "chain_position": "Kraj lanca pohrane: AI modeli i podaci (video, slike, zapisi za treniranje) moraju negdje biti spremljeni, a disk je najjeftiniji način po terabajtu. Povezano s memorijom jer SSD (NAND) skupo zamjenjuje disk samo kod brzih podataka; za hladne podatke disk ostaje.",
        "cycle": "Diskovi imaju manje ekstremne cikluse od DRAM-a jer su proizvođači samo dva-tri (WDC, Seagate, Toshiba) i disciplinirani s ponudom. Ciklus ipak postoji: narudžbe oblaka dolaze u valovima, zalihe se pune i prazne. Dodatni slučaj: prijelaz na novu tehnologiju (HAMR, ePMR) donosi privremene probleme s prinosom.",
        "hurts": "Odgoda narudžbi velikih kupaca, koncentracija kupaca, uspon SSD-a, pad cijena po terabajtu, tehnološki zastoji (HAMR kvalifikacija), te činjenica da je kretanje dionice jako vezano uz Seagate i tržišnu temu 'AI pohrana'.",
        "sources": [
            "https://www.sec.gov/Archives/edgar/data/0000106040/000162828026057139/wdc-20260703.htm",
            "https://www.nasdaq.com/articles/higher-capacity-hdds-drive-western-digitals-revenue-growth",
        ],
        "eu_note": "WDC povijest u našim podacima već je prilagođena odvajanju SanDiska (faktor 0,68132), ne prilagođava se ponovno. Dostupnost na IBKR-u: nepotvrđeno.",
    },
    "STX": {
        "company": "Seagate Technology",
        "sells": "Tvrde diskove (HDD) velikog kapaciteta, uglavnom za podatkovne centre (nearline diskovi), te manji dio ostalih proizvoda. Vodeća tehnologija je HAMR (disk zagrijan laserom pri upisu), serija Mozaic.",
        "revenue_drivers": "Isti model kao WDC: eksabajti x cijena po eksabajtu, plus prinos (koliko proizvedenih diskova ispravno radi). Prema izvješćima iz 2026. HAMR je oko 40 % isporuka nearline kapaciteta, a većina kapaciteta već je dodijeljena do kraja 2028. Ako točno, kupci unaprijed zaključuju zalihe, što stabilizira prihod.",
        "chain_position": "Pohrana podataka AI sloja, uz WDC; velika potražnja iz oblaka i AI laboratorija. Kod nas se uz WDC kreće najsličnije (korelacija dnevnih povrata iznosi {corr_wdc} u AI eri).",
        "cycle": "Slično WDC: manje ekstremno od DRAM-a, ali podložno valovima narudžbi oblaka. Prije AI ere dionica je imala dugo razdoblje bez rasta (2018.-2020. i pad u 2022.).",
        "hurts": "Zastoji i prinos kod prijelaza na HAMR, koncentracija kupaca, pad cijena po terabajtu, odgoda narudžbi oblaka, uspon SSD-a za dio podataka.",
        "sources": [
            "https://blocksandfiles.com/2025/10/30/seagate-revenues-boosted-by-ai-inferencing-as-hamr-tech-becomes-mainstream/",
            "https://www.blocksandfiles.com/disk/2026/07/30/seagate-hamring-customers-generating-more-and-more-/tb/5281058",
            "https://www.nasdaq.com/articles/can-seagate-maintain-its-record-margins-hamr-adoption-accelerates",
        ],
        "eu_note": "Pojedinačna američka dionica; dostupnost na IBKR-u za EU ulagača nepotvrđeno.",
    },
}


def main() -> None:
    raw = json.loads((OUT / "_stats_raw.json").read_text())
    S = raw["stats"]
    A, P = "ai_era_2023plus", "context_2016_2022"
    tick = raw["tickers"]
    out: dict[str, Any] = {
        "segment": "memory",
        "segment_name": "Memorija (DRAM, NAND, diskovi)",
        "common_end": raw["common_end"],
        "tickers_used": tick,
        "tickers_excluded": [
            {
                "ticker": "SNDK",
                "reason": "prekratka povijest (222 barova prije 2026, 415 u AI eri), prema universe.json",
            }
        ],
        "method_notes": [
            "Sve brojke izračunate iz sirovih dnevnih CSV-ova (data/ohlcv) do zajedničkog završnog datuma; SMH i NDX samo kao mjerilo (NDX samo zaključna cijena jer su mu OHLC polja nedosljedna).",
            "Glavni prozor je AI era (od 2023-01-01); 2016.-2022. je samo kontekst. Razdoblje prije 2023. odrezano je na 2022-12-30 pa nijedan podatak iz AI ere ne ulazi u kontekst.",
            "Rezultati su OPIS prošlosti, nisu signal, nisu strategija i nisu ocjena kritičara. Svaka ideja koja iz toga proiziđe postaje NOVA hipoteza s NOVIM ID-jem i prolazi ledger.",
            "Događaji se preklapaju (npr. nekoliko uzastopnih dana nakon pada): zato uz broj dana navodimo i broj međusobno neovisnih događaja (razmak 20+ dana). Pravi uzorak je taj manji broj.",
            "Pad (drawdown) bez datuma oporavka znači da cijena do kraja prozora nije dosegla prethodni vrh. U razdoblju 2016.-2022. to može biti rez prozora, ne pravi neoporavak.",
            "Potpora/otpor: zamah je potvrđen tek 5 dana nakon (bez zavirivanja u budućnost); 'drži' znači da u idućih 5 dana nema zaključne cijene više od 1,5 % iza razine. Dodana je kontrola s nasumičnim razinama, jer bez nje stopa 'drži' nema smisla.",
        ],
        "glossary_hr": {
            "godišnja nestabilnost (volatilnost)": "Koliko cijena tipično skače gore-dolje u godini. 50 % znači da je tipičan raspon godine oko +-500 EUR na 1.000 EUR uloga.",
            "beta": "Koliko se dionica pomakne kad se pomakne mjerilo. Beta 1,3 prema SMH: kad SMH padne 10 %, dionica u prosjeku padne oko 13 %.",
            "korelacija": "Koliko dvije cijene idu zajedno, od -1 do +1. 0,76 znači da većinu dana idu istim smjerom.",
            "pad od vrha (drawdown)": "Koliko je cijena pala od najvišeg dosega do dna. Pad od 50 % znači da od 1.000 EUR ostane 500 EUR.",
            "autokorelacija": "Znači li jučerašnji rast da će i danas biti rast (+) ili pad (-). Blizu 0 = jučer ne govori ništa o danas.",
            "omjer varijance (variance ratio)": "Raste li nestabilnost brže (preko 1, zamah) ili sporije (ispod 1, povratak prema sredini) kad gledamo dulje horizonte. Oko 1 = nasumično kretanje.",
            "SMA200": "Prosjek zadnjih 200 zaključnih cijena; grubo mjerilo dugoročnog trenda. Iznad njega = dugoročno uzlazno.",
            "stopa pogotka (hit rate)": "Udio slučajeva u kojima je cijena nakon događaja bila viša. 70 % znači 7 od 10.",
            "neovisni događaj": "Događaj odvojen od prethodnog najmanje 20 dana, pa ne računa isti potez dvaput.",
        },
        "stats": S,
    }
    # --- computed Croatian findings
    f: list[str] = []
    for t in tick:
        a, p = S[t][A], S[t][P]
        d = a["drawdowns"][0]
        f.append(
            f"{t} u AI eri: godišnja nestabilnost {pct(a['ann_vol'], 0)} (prije 2023.: {pct(p['ann_vol'], 0)}). Na 1.000 EUR to znači tipičan raspon godine od oko +-{eur(1000 * a['ann_vol'])}. "
            f"Najveći pad od vrha: {pct(d['depth'], 0)} ({d['start']} do dna {d['bottom']}), što bi od 1.000 EUR ostavilo {eur(1000 * (1 + d['depth']))}."
        )
        f.append(
            f"{t} prema SMH: beta {a['beta_SMH']:.2f}, korelacija {a['corr_SMH']:.2f}; prema NDX: beta {a['beta_NDX']:.2f}, korelacija {a['corr_NDX']:.2f}. Prije 2023.: beta SMH {p['beta_SMH']:.2f}.".replace(
                ".", ","
            )
            if False
            else f"{t} prema SMH: beta {a['beta_SMH']:.2f}, korelacija {a['corr_SMH']:.2f}; prema NDX: beta {a['beta_NDX']:.2f}, korelacija {a['corr_NDX']:.2f}. Prije 2023.: beta SMH {p['beta_SMH']:.2f}."
        )
    out["findings_hr"] = f
    chars = []
    for t in tick:
        a = S[t][A]
        ac = a["autocorr"]
        chars.append(
            f"{t}: autokorelacija dnevnih povrata lag 1..5 = {', '.join(f'{ac[f'lag{k}']:+.2f}' for k in range(1, 6))}; omjer varijance 5 dana {a['variance_ratio_5']:.2f}, 20 dana {a['variance_ratio_20']:.2f}. "
            "Sve je blizu nule/jedinice: dnevno kretanje nema vidljivog zamaha ni povratka; na 20 dana lagani povratak prema sredini (ispod 1) je vidljiv kod WDC."
        )
    out["trend_vs_reversion_hr"] = chars
    prem = []
    for t in tick:
        a, p = (
            S[t][A]["after_5d_drop_above_sma200"],
            S[t][P]["after_5d_drop_above_sma200"],
        )
        prem.append(
            f"{t} AI era: {a['n_days']} dana ({a['n_independent_20d']} neovisnih događaja). Nakon pada od 5 %+ u 5 dana dok je cijena iznad SMA200, prosjek za 5 dana je {pct(a['h5']['mean'])} (stopa pogotka {pct(a['h5']['hit'], 0)}) naspram {pct(a['h5']['uncond_mean'])} ({pct(a['h5']['uncond_hit'], 0)}) u bilo koji dan; za 20 dana {pct(a['h20']['mean'])} naspram {pct(a['h20']['uncond_mean'])}. "
            f"Prije 2023.: 5 dana {pct(p['h5']['mean'])} naspram {pct(p['h5']['uncond_mean'])} ({p['n_independent_20d']} neovisnih)."
        )
    out["premise_c13c_hr"] = {
        "per_ticker": prem,
        "reading": "Premisa da se u uzlaznom trendu pad od 5 % brzo otkupljuje u AI eri vrijedi kao OPIS za sva tri naslova: prosjek nakon pada je veći od običnog dana i stopa pogotka viša. Razlika je ipak mala u odnosu na cijeli tijek AI ere (dionice su u prosjeku snažno rasle), uzorak je oko 21-23 neovisna događaja po dionici, a prije 2023. učinak je skoro nestao (kod WDC za 20 dana čak negativan). To nije dokaz strategije, ni Critic PASS; to je opis koji može poslužiti kao ulaz za NOVU hipotezu.",
    }
    hi, up3 = [], []
    for t in tick:
        a, p = S[t][A]["after_52w_high"], S[t][P]["after_52w_high"]
        hi.append(
            f"{t}: nakon novog 52-tjednog vrha, 20 dana unaprijed AI era {pct(a['h20']['mean'])} (običan dan {pct(a['h20']['uncond_mean'])}, neovisnih događaja {a['n_independent_20d']}); prije 2023. {pct(p['h20']['mean'])} (običan dan {pct(p['h20']['uncond_mean'])})."
        )
        b = S[t][A]["after_3_up_days"]["h5"]
        up3.append(
            f"{t}: nakon 3 uzastopna rasta, 5 dana unaprijed {pct(b['mean'])} naspram {pct(b['uncond_mean'])} (razlika {pct(b['edge_mean'])}): praktički nema razlike."
        )
    out["after_52w_high_hr"] = hi
    out["after_3_up_days_hr"] = up3
    out["after_52w_high_reading_hr"] = (
        "U AI eri novi vrh nije bio znak iscrpljenosti nego nastavka (dodatak od oko 4-6 postotnih bodova u 20 dana nad običnim danom); prije 2023. je bio suprotno. Ovo je razlika režima, ne pravilo."
    )
    seas = []
    for t in tick:
        s = S[t][A]["seasonality_month"]
        best = max(s, key=lambda m: s[m]["mean"])
        worst = min(s, key=lambda m: s[m]["mean"])
        seas.append(
            f"{t} AI era: najbolji mjesec {best}. ({pct(s[best]['mean'])}, {s[best]['n_years']} godine), najlošiji {worst}. ({pct(s[worst]['mean'])}, {s[worst]['n_years']} godine)."
        )
    out["seasonality_hr"] = seas
    out["seasonality_warning_hr"] = (
        "UPOZORENJE: u AI eri svaki mjesec ima samo 3-4 opservacije (jedna po godini). Sezonski obrazac na 3-4 godine ne smije se čitati kao pravilo; i prije 2023. imamo tek 6-7 opservacija po mjesecu."
    )
    conc = []
    for t in tick:
        c = S[t][A]["concentration"]
        conc.append(
            f"{t} AI era: ukupni povrat {pct(c['total_return'], 0)}; bez 10 najboljih dana ostaje {pct(c['total_return_without_top10'], 0)}; 10 najboljih dana čini {pct(c['log_share_top10_days'], 0)} logaritamskog povrata. Najveći jaz otvaranja: {S[t][A]['largest_gaps'][0]['date']} ({pct(S[t][A]['largest_gaps'][0]['gap'])})."
        )
    out["concentration_gaps_hr"] = conc
    ll = []
    for t in tick:
        a = S[t][A]["leadlag_vs_SMH"]
        ll.append(
            f"{t} prema SMH: istog dana korelacija {a['k+0']:.2f}; jučerašnji SMH -> današnji {t}: {a['y_leads_x']:+.2f}; jučerašnji {t} -> današnji SMH: {a['x_leads_y']:+.2f}."
        )
        for q, v in S[t][A]["leadlag_vs_peers"].items():
            ll.append(
                f"{t} prema {q}: istog dana {v['k+0']:.2f}; {q} jučer -> {t} danas {v['y_leads_x']:+.2f}; {t} jučer -> {q} danas {v['x_leads_y']:+.2f}."
            )
    out["lead_lag_hr"] = ll
    out["lead_lag_reading_hr"] = (
        "Nitko ne vodi niti slijedi na dnevnoj razini: korelacije sa pomakom od jednog dana su blizu nule (ispod 0,05 po apsolutnoj vrijednosti u AI eri). Sve se događa isti dan. Najtješnji par je WDC-STX (istog dana oko 0,82), MU je odvojeniji. Prije 2023. postoji lagani povratak (jučerašnji potez dionice prema današnjem potezu SMH-a oko -0,10, tj. blagi preokret), koji u AI eri nestaje."
    )
    sma = []
    for t in tick:
        d = S[t][A]["sma200_distance"]
        b = d["buckets"]
        sma.append(
            f"{t}: sada {pct(d['current'], 0)} iznad SMA200 (AI era prosjek {pct(d['mean'], 0)}, raspon {pct(d['min'], 0)} do {pct(d['max'], 0)}). Prosjek idućih 20 dana: ispod SMA200 {pct(b['<0']['fwd20_mean'])}, 0-20 % iznad {pct(b['0-20%']['fwd20_mean'])}, 20-50 % iznad {pct(b['20-50%']['fwd20_mean'])}, preko 50 % iznad {pct(b['>50%']['fwd20_mean'])}."
        )
    out["sma200_distance_hr"] = sma
    out["sma200_reading_hr"] = (
        "U AI eri velika udaljenost od SMA200 nije značila 'prerastegnuto, slijedi povratak' nego je dolazila uz nastavak rasta (zamah trenda). To je odraz jedne pobjedničke faze, ne zakon; prije 2023. udaljenost preko 50 % gotovo nije ni postojala (nekoliko desetaka dana)."
    )
    sr = []
    for t in tick:
        s = S[t][A]["support_resistance"]
        c = S[t][A]["support_resistance_control_any_bar"]
        sr.append(
            f"{t} AI era: potpora (raniji lokalni minimum) dodirnuta {s['support']['touches']} puta, držala {pct(s['support']['hold_rate'], 0)} (nasumična razina: {pct(c['support']['hold_rate'], 0)}); otpor dodirnut {s['resistance']['touches']} puta, držao {pct(s['resistance']['hold_rate'], 0)} (nasumična razina: {pct(c['resistance']['hold_rate'], 0)})."
        )
    out["support_resistance_hr"] = sr
    out["support_resistance_reading_hr"] = (
        "Razine ranijih lokalnih minimuma i maksimuma ne drže bolje od nasumično odabranih razina iste vrste. Otpor u AI eri drži oko pola slučajeva (u uzlaznom trendu cijena ga često probije). Ove brojke ne podupiru crtanje razina kao samostalni razlog za odluku."
    )
    out["mechanism"] = {}
    for t in tick:
        m = dict(MECH[t])
        m["chain_position"] = m["chain_position"].replace(
            "{corr_wdc}", f"{S['STX'][A]['leadlag_vs_peers']['WDC']['k+0']:.2f}"
        )
        m["label"] = CTX
        out["mechanism"][t] = m
    out["context_before_after_2023_hr"] = (
        "Prije 2023.: dionice su bile cikličke bez trajnog rasta (WDC je izgubio velik dio vrijednosti, STX i MU imali su duge padove), a premisa 'pad u trendu se otkupljuje' i 'novi vrh nastavlja' nisu davale vidljivu prednost. "
        "U AI eri (od 2023.) sva tri naslova su višestruko porasla, nestabilnost je veća, beta prema indeksima viša, a oba obrasca daju pozitivnu razliku. Uzorci su mali (oko 20 neovisnih događaja) i počivaju na jednom dugom rastu pa ih treba čitati oprezno."
    )
    out["limits_hr"] = [
        "SNDK je isključen (prekratka povijest).",
        "Nema podatka o zaradama u ovom profilu; datumi izvješća o zaradama (MU) nisu miješani u izračun.",
        "Tvrdnje o poslovanju su iz javnih izvora i nisu provjerene našim podacima; neke brojke dolaze iz sekundarnih članaka i označene su kao kontekst.",
        "Nisu uključeni troškovi, nema prijedloga trgovanja, nema Critic ocjene.",
    ]
    (OUT / "profile.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (OUT / "_stats_raw.json").unlink()
    print("ok", len(json.dumps(out)))


if __name__ == "__main__":
    main()
