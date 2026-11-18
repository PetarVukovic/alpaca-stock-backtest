"""Merge numeric profiles with Croatian narrative into segments/network_servers/profile.json.

Run after lab.aichain.profile_network_servers:
    .venv/bin/python -m lab.aichain.profile_network_servers_build
All numbers in the text are pulled from profile_numbers.json; business facts are public context only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SEG_DIR = (
    ROOT / "reports" / "research" / "AICHAIN_20261014" / "segments" / "network_servers"
)
LABEL = "kontekst iz javnih izvora, nije iz naših podataka"
AI_NOTE = "Glavno mjerilo je AI era (od 2023-01-01); razdoblje 2016-2022 služi samo kao kontekst."

GLOSSARY = {
    "volatilnost": "Koliko cijena tipično njiše tijekom godine. Pri 50 % godišnje njihanje, 1.000 EUR se u običnoj godini može "
    "kretati otprilike između 500 i 1.500 EUR; to je mjera nemira, ne gubitka.",
    "beta": "Koliko se dionica pomakne kad se referenca (SMH ili NDX) pomakne za 1 %. Beta 1,4 znači: kad SMH padne 1 %, "
    "ova dionica u prosjeku padne 1,4 %, pa 1.000 EUR izgubi 14 EUR umjesto 10 EUR.",
    "korelacija": "Koliko se dva niza kreću zajedno, od -1 do 1. Blizu 0,6 znači da se često kreću u istom smjeru, ali ne uvijek.",
    "najveći pad (drawdown)": "Pad od najvišeg do najnižeg zatvaranja prije oporavka. -50 % znači da 1.000 EUR na vrhu postane 500 EUR na dnu.",
    "autokorelacija": "Je li današnji pomak povezan s jučerašnjim. Vrijednosti unutar zadanog 'šuma' (oko +-0,05 do +-0,07) "
    "ne znače ništa; to je slučajna razlika.",
    "omjer varijance (VR)": "Usporedba njihanja kroz 5 ili 20 dana s onim što bi bilo da je svaki dan neovisan. Oko 1 = slučajno kretanje; "
    "iznad 1 = pomaci se nastavljaju (trend); ispod 1 = pomaci se djelomično vraćaju (reverzija).",
    "SMA200": "Prosjek zadnjih 200 zatvaranja; grubo mjerilo dugoročnog smjera. Iznad njega je dionica u dugoročnom usponu.",
    "jaz (gap)": "Razlika između jučerašnjeg zatvaranja i današnjeg otvaranja, obično nakon vijesti ili rezultata preko noći.",
    "potpora/otpor": "Prethodno dno (potpora) ili vrh (otpor) na kojem je cijena već jednom obrnula. 'Drži' znači da u idućih 5 dana "
    "zatvaranje nije probilo razinu za više od 1,5 %.",
    "nezavisni događaji": "Isti pad često traje više dana; brojimo samo prvi dan, a idućih 20 dana preskačemo da isti događaj ne bi bio brojen dvaput.",
}

# Public-context mechanism text per company (Croatian). Sources fetched via web search on 2026-10-14.
MECH: dict[str, dict[str, Any]] = {
    "ANET": {
        "sells": "Mrežne preklopnike (switcheve) i softver za podatkovne centre; najveći kupci su golemi oblaci (Microsoft i Meta). "
        "Preklopnik je uređaj koji povezuje tisuće servera da razgovaraju jedan s drugim.",
        "revenue_drivers": "Narudžbe oblaka i AI klastera (otprilike 48 % prihoda iz 'Cloud and AI Titans' u zadnjem godišnjem izvješću). "
        "Microsoft je bio oko 20 %, a Meta oko 15 % prihoda u 2024.",
        "chain_position": "Mreža unutar AI klastera: GPU-ovi i memorija (HBM) bez brze mreže ne mogu raditi kao jedna cjelina. "
        "Arista je Ethernet alternativa Nvidijinoj vlastitoj mreži.",
        "cycle": "Prati kapitalna ulaganja (capex) oblaka. Kad oblaci rade nove AI klastere, narudžbe skaču; kad prave pauzu, "
        "narudžbe zastaju. Vrijeme narudžbi je nepredvidivo.",
        "hurts": "Koncentracija na nekoliko kupaca, pauza u capexu, Nvidijin integrirani paket, razočaravajuće smjernice.",
        "sources": [
            "https://www.sec.gov/Archives/edgar/data/1596532/000159653225000028/anet-20241231.htm"
        ],
    },
    "CRDO": {
        "sells": "Aktivne električne kabele (AEC) i čipove za brze veze unutar regala AI servera; mali bakreni kabel s ugrađenim čipom "
        "koji zamjenjuje skuplje optičke veze na do oko 7 metara.",
        "revenue_drivers": "Nekoliko hiperskalera, od kojih je u jednom izvještajnom kvartalu (fiskalni Q2 2026) svaki od četiri činio više od 10 % prihoda. "
        "Prihod je skočio s 437 milijuna USD (fiskalna 2025.) prema 800+ milijuna USD (smjernica za 2026.).",
        "chain_position": "Povezivanje GPU-ova i servera unutar istog regala, uz memoriju i mrežu; ovisna o brzini izgradnje AI klastera.",
        "cycle": "Narudžbe stižu u valovima s novim generacijama AI regala. Vrlo mala tvrtka s vrlo koncentriranim kupcima, pa su kvartalni skokovi veliki.",
        "hurts": "Gubitak jednog hiperskalera, prelazak na optiku ili Nvidijina rješenja, razočaravajuće smjernice (u našim podacima: -46,8 % u "
        "jednom danu 2023-02-15 i +47,9 % 2024-12-03; uzrok nismo provjeravali).",
        "sources": [
            "https://www.nasdaq.com/articles/credo-expects-revenues-top-800m-fy26-growth-sustainable",
            "https://www.nasdaq.com/articles/whats-driving-credos-explosive-revenue-growth-fy26",
        ],
    },
    "ALAB": {
        "sells": "Čipove i module za povezivanje unutar AI servera: PCIe retimere (pojačala signala između GPU-a i procesora), "
        "Scorpio preklopnike za povezivanje GPU-ova i optičke module.",
        "revenue_drivers": "Broj AI servera/GPU-ova u izgradnji kod hiperskalera; kvartalni prihod u Q1 2026 bio je 308,4 milijuna USD (+93 % na godinu), "
        "bruto marža oko 76 %.",
        "chain_position": "Veza između GPU-ova, memorije i mreže; nema svoj GPU, nego prodaje 'ljepilo' za Nvidijine i vlastite hiperskalerske čipove.",
        "cycle": "Prati generacije PCIe standarda i AI platformi; skokovi kad se uvede nova generacija.",
        "hurts": "Ovisnost o malom broju platformi i kupaca, konkurencija većih čipaša, visoka očekivanja (cijena već uračunava rast).",
        "sources": [
            "https://www.asteralabs.com/news/astera-labs-reports-first-quarter-2026-financial-results/"
        ],
    },
    "COHR": {
        "sells": "Optičke primopredajnike (modul koji pretvara električni signal u svjetlo za veze između servera i preklopnika), "
        "lasere i posebne materijale. Većinu komponenti (lasere, detektore) izrađuje sama.",
        "revenue_drivers": "Datacom (AI) primopredajnici, npr. 800G i 1,6T; u fiskalnom Q1 2025 prihod je bio 1,35 milijardi USD (+28 %), "
        "a 800G je prešao 100 milijuna USD kvartalno.",
        "chain_position": "Optičke veze između regala i redova servera u AI klasteru; kupci su hiperskaleri i proizvođači mreža.",
        "cycle": "Kapitalna ulaganja oblaka i prelazak na brže module; stariji industrijski i laserski poslovi prate industrijski ciklus.",
        "hurts": "Cjenovni pritisak azijskih proizvođača modula, ovisnost o malom broju kupaca, industrijski usporen dio posla, visok dug.",
        "sources": [
            "https://www.sec.gov/Archives/edgar/data/820318/000110465925096178/tm2527105d2_ars.pdf",
            "https://www.nasdaq.com/articles/coherent-sees-strong-ai-tailwinds-its-optical-business",
        ],
    },
    "LITE": {
        "sells": "Laserske čipove i optičke module za podatkovne centre (segment Cloud & Networking) te industrijske lasere (Industrial Tech). "
        "Cloud Light, optički moduli, kupljen je u studenom 2023.",
        "revenue_drivers": "Potražnja oblaka i AI/ML infrastrukture te telekom mreža. Lasere koriste i drugi proizvođači primopredajnika.",
        "chain_position": "Najniža razina optičkog lanca: izvor svjetla za veze između servera.",
        "cycle": "Vrlo cikličan: zalihe kod kupaca i capex oblaka; telekom dio je u prošlosti padao kad operateri smanje ulaganja.",
        "hurts": "Kupci s velikim pregovaračkim utjecajem, zalihe, kašnjenje novih generacija, cjenovni pritisak.",
        "sources": [
            "https://www.sec.gov/Archives/edgar/data/1633978/000162828025040830/lite-20250628.htm"
        ],
    },
    "SMCI": {
        "sells": "Servere i cijele regale za AI (GPU poslužitelji s Nvidijinim, AMD-ovim i drugim čipovima) te rješenja za napajanje i hlađenje.",
        "revenue_drivers": "Velike narudžbe AI servera od nekoliko kupaca (više od 80 % prihoda u fiskalnom Q3 2026 prema jednom izvoru). "
        "Marža je tanka i jako varira (od jednoznamenkastih do oko 17 % prema nedavnim smjernicama).",
        "chain_position": "Sklapanje: uzima Nvidijine GPU-ove, memoriju i mrežu i prodaje gotov server. Najbliži 'montažer' lanca.",
        "cycle": "Isporuke ovise o dostupnosti GPU-ova i memorije; prihod je neravnomjeran, marža pada kad se prodaju goli serveri.",
        "hurts": "Tanke marže, ovisnost o Nvidijinoj isporuci, računovodstvene i revizorske nedoumice u prošlosti, konkurencija Dellu i drugima.",
        "sources": [
            "https://www.thestar.com.my/tech/tech-news/2026/07/22/super-micro-expects-stronger-quarterly-margins-shares-jump",
            "https://www.fool.com/investing/2026/06/20/super-micro-jumped-more-than-10-is-the-ai-server-m/",
        ],
    },
    "DELL": {
        "sells": "Servere, pohranu, računala i usluge; AI optimizirani serveri su najbrže rastući dio (Infrastructure Solutions Group).",
        "revenue_drivers": "AI narudžbe i zaostale narudžbe (backlog): prema javnim vijestima rekordni backlog od oko 95 milijardi USD u kvartalu do 31. 7. 2026. "
        "Memorija je prema upravi glavno ograničenje isporuke.",
        "chain_position": "Gotovi serveri za poduzeća i oblak; više kupaca nego SMCI (uključujući poduzeća), ali s manjom maržom na AI serverima.",
        "cycle": "Isporuke 'nelinearne' (po riječima uprave) jer ovise o izgradnji podatkovnih centara, struji i dostupnosti čipova i memorije.",
        "hurts": "Nestašica memorije/GPU-ova, niska marža AI servera, spori PC dio, kašnjenja podatkovnih centara.",
        "sources": [
            "https://networkworld.com/article/4217691/dells-95b-ai-backlog-shows-the-infrastructure-crunch-is-far-from-over.html",
            "https://www.theregister.com/2025/05/30/dell_results/",
        ],
    },
    "HPE": {
        "sells": "Servere, hibridni oblak (GreenLake) i mrežnu opremu; kupnja Juniper Networks zatvorena je 2. 7. 2025 i otprilike udvostručuje mrežni posao.",
        "revenue_drivers": "Segmenti Cloud & AI i Networking. Mreže su procijenjene na oko 31 % pro forma prihoda i više od 56 % operativne dobiti.",
        "chain_position": "Poduzeća i državni kupci više nego hiperskaleri; AI serveri s hlađenjem tekućinom i mreža.",
        "cycle": "Sporiji, poslovni ciklus ulaganja poduzeća; AI dio izraženiji nego prije.",
        "hurts": "Integracija Juniper-a, dug, niža marža servera, konkurencija Dellu i Ciscu.",
        "sources": [
            "https://www.sec.gov/Archives/edgar/data/0001645590/000164559026000055/hpe-20260430.htm",
            "https://www.constellationr.com/insights/news/hpe-acquire-juniper-networks-14b-what-it-means",
        ],
    },
}


def fmt(x: float | None, nd: int = 1) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}".replace(".", ",")


def data_text(p: dict[str, Any]) -> list[str]:
    """Plain-Croatian sentences with a 1.000 EUR example, all numbers from the computed profile."""
    dd = p["worst_drawdowns"][0] if p["worst_drawdowns"] else None
    out = [
        f"Njihanje (volatilnost) je {fmt(p['ann_vol_pct'])} % godišnje: tipična godina može pomaknuti 1.000 EUR za oko "
        f"{fmt(p['ann_vol_pct'] * 10, 0)} EUR gore ili dolje.",
        f"Beta prema SMH je {fmt(p['beta_smh'], 2)} (korelacija {fmt(p['corr_smh'], 2)}), prema NDX {fmt(p['beta_ndx'], 2)}: "
        f"kad SMH padne 1 %, ova dionica u prosjeku padne {fmt(p['beta_smh'], 2)} %.",
    ]
    if dd:
        out.append(
            f"Najveći pad: {fmt(dd['depth_pct'])} % ({dd['start']} do dna {dd['bottom']}, oporavak "
            f"{dd['recovery'] or 'još nije u cijelosti'}); 1.000 EUR na vrhu bio bi "
            f"{fmt(1000 * (1 + dd['depth_pct'] / 100), 0)} EUR na dnu."
        )
    out.append(
        f"Karakter: {p['character']} (omjer varijance 5 dana {fmt(p['variance_ratio_5'], 2)}, 20 dana "
        f"{fmt(p['variance_ratio_20'], 2)}; autokorelacija lag-1 {fmt(p['autocorr_lag1_5']['1'], 3)}, šum +-"
        f"{fmt(p['autocorr_noise_band_2se'], 3)})."
    )
    out.append(
        f"Koncentracija: 10 najboljih dana čini {fmt(p['top10_days_log_share_pct'])} % ukupnog (logaritamskog) "
        f"rasta; bez njih bi ukupni prinos bio {fmt(p['return_without_10_best_days_pct'])} % umjesto "
        f"{fmt(p['total_return_pct'])} %."
    )
    return out


def pooled_c13c(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Event-weighted segment average of (conditional - unconditional) forward returns, AI era."""
    res: dict[str, Any] = {}
    for h in (1, 5, 10, 20):
        num_c = num_u = den = hit_c = hit_u = 0.0
        for p in profiles:
            t = p["after_5d_drop_ge5pct_above_sma200"][f"fwd{h}"]
            if p["window"] != "ai_era" or not t["n"]:
                continue
            num_c += t["mean_pct"] * t["n"]
            num_u += t["uncond_mean_pct"] * t["n"]
            hit_c += t["hit_rate_pct"] * t["n"]
            hit_u += t["uncond_hit_rate_pct"] * t["n"]
            den += t["n"]
        if den:
            res[f"fwd{h}"] = {
                "events": int(den),
                "mean_pct": round(num_c / den, 2),
                "uncond_mean_pct": round(num_u / den, 2),
                "hit_rate_pct": round(hit_c / den, 1),
                "uncond_hit_rate_pct": round(hit_u / den, 1),
            }
    return res


def main() -> None:
    num = json.loads((SEG_DIR / "profile_numbers.json").read_text())
    profiles = num["profiles"]
    pooled = pooled_c13c(profiles)
    c = pooled["fwd20"]
    c5 = pooled["fwd5"]
    c13c_text = (
        f"Premisa C13C (kupnja nakon pada od 5 % ili više u 5 dana dok je zatvaranje iznad SMA200): u AI eri, kroz svih osam dionica segmenta "
        f"({c5['events']} nezavisnih događaja), prosječni povrat nakon 5 dana je {fmt(c5['mean_pct'], 2)} % uz uspješnost "
        f"{fmt(c5['hit_rate_pct'])} %, a bezuvjetno je {fmt(c5['uncond_mean_pct'], 2)} % uz {fmt(c5['uncond_hit_rate_pct'])} %. "
        f"Nakon 20 dana: {fmt(c['mean_pct'], 2)} % (uspješnost {fmt(c['hit_rate_pct'])} %) naspram bezuvjetnih "
        f"{fmt(c['uncond_mean_pct'], 2)} % ({fmt(c['uncond_hit_rate_pct'])} %). Na 1.000 EUR to je razlika od otprilike "
        f"{fmt((c['mean_pct'] - c['uncond_mean_pct']) * 10, 0)} EUR nakon 20 dana u odnosu na bilo koji drugi dan. "
        "Tumačenje: slika je mješovita po dionicama (neke iznad, neke ispod bezuvjetnog), a pojedinačni uzorci su mali (14-26 događaja), "
        "pa je to opis, ne dokaz. Svaka ideja koja iz toga proiziđe postaje NOVA hipoteza s novim ID-em i ne smije se zvati Critic PASS."
    )
    # attach text per ticker
    by_t: dict[str, Any] = {}
    for p in profiles:
        by_t.setdefault(p["ticker"], {"windows": {}})["windows"][p["window"]] = {
            **p,
            "plain_text_hr": data_text(p),
        }
    for t, m in MECH.items():
        by_t[t]["mechanism_hr"] = {**m, "label": LABEL}
    caveats = [
        "NDX: dnevna serija ima nedosljedan OHLC (133 retka izvan low-high), pa je korišten samo close za betu i korelaciju. "
        "Raspon NDX podataka završava 2026-10-13; sve je odrezano na zajednički kraj 2026-10-05.",
        "SMCI: serija prije 2020-01-14 je zaustavljena trgovina, koristi se tek od 2020-01-14 (prvi povrat nakon pauze, +72,5 %, izbačen).",
        "CRDO: u pre-2023 kontekstu samo 234 dana (dionica na burzi od 2022-01-27); ALAB nema pre-2023 podataka (od 2024-03-20): "
        "AI era statistika je za oba kratka i stoga manje pouzdana.",
        "Udio 10 najboljih dana može prelaziti 100 % kad je ukupni prinos mali ili negativan; tada znači da je bez tih dana prinos negativan.",
        "Nema podataka o satnim ili 5-minutnim sesijama; sve je izračunato iz dnevnih podataka.",
        "Ovo je opis ponašanja, ne signal i ne strategija. Nema preporuke za kupnju. Svaka ideja zahtijeva novi freeze ID.",
        "Dostupnost za Petra preko Interactive Brokersa: sve su američke pojedinačne dionice (ne ETF), ali dostupnost i porezni tretman "
        "nisu provjereni: nepotvrđeno.",
    ]
    doc = {
        "segment": "network_servers",
        "segment_name_hr": "Mreže, optika i serveri za AI",
        "common_end": num["common_end"],
        "ai_era_start": num["ai_era_start"],
        "window_note_hr": AI_NOTE,
        "skipped_tickers": num["skipped"],
        "tickers": list(by_t.keys()),
        "glossary_hr": GLOSSARY,
        "c13c_premise_pooled_ai_era": pooled,
        "c13c_premise_text_hr": c13c_text,
        "caveats_hr": caveats,
        "profiles": by_t,
    }
    (SEG_DIR / "profile.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(c13c_text)


if __name__ == "__main__":
    main()
