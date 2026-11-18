"""Croatian text layer for the "cloud" profile: mechanism, interpretation, final files.

Step 2 of 2 (stats come from lab.aichain.profile_cloud). Writes
reports/research/AICHAIN_20261014/segments/cloud/profile.json and profile_stats.csv.
This is a description of behaviour, not a signal and not a Critic result.

Run:
    .venv/bin/python -m lab.aichain.cloud_text
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from lab.aichain.profile_cloud import OUT_ROOT, compute

CONTEXT_TAG = "kontekst iz javnih izvora, nije iz naših podataka"
UNVERIFIED = "nepotvrđeno"

MECHANISM: dict[str, dict[str, Any]] = {
    "MSFT": {
        "ime": "Microsoft",
        "sto_prodaje": "Softver i usluge: Azure (iznajmljivanje računalne snage u oblaku), Microsoft 365 s Copilot AI asistentom, Windows, LinkedIn, igre.",
        "sto_vozi_prihod": "Azure rast i broj plaćenih korisnika softvera. Prema javnim izvorima, u fiskalnoj 2026. Azure je prvi put prešao 100 milijardi USD godišnjeg prihoda uz rast oko 41 do 43 posto, a Copilot ima preko 30 milijuna plaćenih korisnika (sekundarni izvori, brojke se u izvorima razlikuju).",
        "mjesto_u_lancu": "Kupac čipova, ne proizvođač. Troši na GPU-ove i memoriju (HBM) i tako stvara potražnju za lancem iznad sebe (NVDA, MU). Dio kapaciteta iznajmljuje od drugih (npr. Nebius).",
        "ciklus": "Ciklus ulaganja (capex): kad Microsoft naglo povećava ulaganja u podatkovne centre, dobavljači čipova i opreme zarađuju prije njega, a sam Microsoft mora dokazati da prihod od AI-ja opravdava trošak. Prihod od pretplata je stabilan, pa je dionica mirnija od čipova.",
        "sto_steti": "Sumnja da AI ulaganja neće donijeti prihod, pad slobodnog novčanog toka zbog golemog capexa (prema izvorima FCF -23 posto u zadnjem kvartalu), nestašica struje i čipova, regulatorni pritisak.",
        "izvori": [
            "https://www.marketbeat.com/instant-alerts/microsoft-q4-earnings-call-highlights-2026-07-29/",
            "https://www.constellationr.com/insights/news/microsoft-azure-q4-revenue-surges-41-tops-100-billion-annual-revenue",
        ],
    },
    "AMZN": {
        "ime": "Amazon",
        "sto_prodaje": "Dva posla pod jednim imenom: internetska trgovina i logistika (većina prihoda) te AWS, najveći oblak na svijetu, koji daje većinu dobiti.",
        "sto_vozi_prihod": "Za AWS: koliko kupaca najmi računalnu snagu i koliko je ugovoreno unaprijed (backlog). Prema javnim izvorima, u drugom kvartalu 2026. AWS je narastao oko 37 posto (oko 42 milijarde USD u kvartalu), backlog oko 496 milijardi USD, marža AWS-a oko 39 posto (sekundarni izvori).",
        "mjesto_u_lancu": "Kupac čipova i memorije; uz to razvija vlastite AI čipove (Trainium) pa dio potražnje odlazi od NVDA. Veliki kupac DRAM-a i HBM-a posredno preko poslužitelja.",
        "ciklus": "Isti ciklus ulaganja kao kod ostalih oblaka: capex za 2026. podignut na oko 220 milijardi USD (prema sekundarnim izvorima), dobit AWS-a mora pratiti. Maloprodaja dodaje sezonalnost (blagdanski kvartal) i osjetljivost na potrošnju.",
        "sto_steti": "Pad potrošnje kupaca, slobodni novčani tok koji je pod pritiskom zbog capexa, cijene energije i čipova, gubitak velikog AI kupca prema konkurenciji.",
        "izvori": [
            "https://vectorshift.ai/research/companies/amazon-com/earnings/2026-q2",
            "https://letsdatascience.com/news/amazon-increases-capex-to-442b-in-q1-accelerating-ai-buildou-45ccd319",
        ],
    },
    "GOOGL": {
        "ime": "Alphabet (Google)",
        "sto_prodaje": "Oglase (Search i YouTube, otprilike pola ukupnog prihoda prema našem izračunu iz javnih brojki, nije službena brojka), Google Cloud, Android, pretplate i vlastite AI modele (Gemini).",
        "sto_vozi_prihod": "Oglašivački proračuni (osjetljivi na gospodarstvo) i rast Google Clouda. Prema javnim izvorima, u drugom kvartalu 2026. Cloud je narastao oko 82 posto na oko 24,8 milijardi USD, backlog oko 514 milijardi USD (sekundarni izvori).",
        "mjesto_u_lancu": "Kupac memorije i čipova, ali i proizvođač vlastitih AI čipova (TPU), pa je manje ovisan o NVDA nego ostali. Capex za 2026. prema izvorima oko 195 do 205 milijardi USD.",
        "ciklus": "Dva ciklusa u jednom: oglašavanje prati gospodarstvo (brzo se oporavlja), a Cloud prati AI ulaganja. Prijetnja je da AI chatbotovi izvuku promet iz pretraživanja.",
        "sto_steti": "Pad oglašavanja u recesiji, regulatorni procesi (antimonopolski), AI konkurencija pretraživanju, negativan slobodni tok zbog capexa (prema izvorima -5,9 milijardi USD u kvartalu).",
        "izvori": [
            "https://www.nasdaq.com/articles/alphabet-q2-earnings-call-highlights",
            "https://thenextweb.com/news/alphabet-q2-2026-capex-205bn-cloud-82",
        ],
    },
    "META": {
        "ime": "Meta Platforms",
        "sto_prodaje": "Gotovo isključivo oglase na Facebooku, Instagramu, WhatsAppu (oko 98 posto prihoda prema 10-Q podacima; Reality Labs, VR naočale, posluje s gubitkom).",
        "sto_vozi_prihod": "Broj prikazanih oglasa i cijena oglasa. Prema 10-Q za drugi kvartal 2026., prikazi su rasli oko 14 posto, cijena oglasa oko 12 posto (analiza treće strane, nepotvrđeno u primarnom dokumentu).",
        "mjesto_u_lancu": "Ne prodaje oblak drugima: gradi vlastite AI podatkovne centre (modeli Llama, preporuke oglasa) i najveći je potrošač GPU-ova i memorije među oglašivačkim tvrtkama. Capex 2026. prema vodstvu 125 do 145 milijardi USD, a vodstvo je dodalo da su viši i zbog skupljih komponenti (memorija).",
        "ciklus": "Oglasi prate gospodarstvo; capex se povećava u valovima, a svaki val dizanja capexa u prošlosti je dionicu povukao dolje jer ulagači sumnjaju u povrat.",
        "sto_steti": "Pad oglašavanja, regulativa (EU, SAD), odlazak mladih korisnika, skupi AI capex bez jasnog prihoda, skuplja memorija.",
        "izvori": [
            "https://www.investing.com/news/earnings/meta-stock-slips-more-than-6-after-hours-on-raised-capital-expenditure-guidance-4646698",
            "https://www.sec.gov/Archives/edgar/data/0001326801/000162828026050705/meta-20260630.htm",
        ],
    },
    "ORCL": {
        "ime": "Oracle",
        "sto_prodaje": "Baze podataka i poslovni softver (stabilan stari posao) te OCI, oblak za velike AI ugovore (OpenAI i drugi).",
        "sto_vozi_prihod": "Ugovoreni, još neostvareni prihod (RPO). Prema javnim izvorima, na kraju fiskalne 2026. (svibanj 2026.) RPO oko 638 milijardi USD, prihod OCI-ja oko 18,1 milijardi USD (+77 posto). Dio je ugovora u kojem kupac sam plati ili donese GPU-ove (sekundarni izvori).",
        "mjesto_u_lancu": "Najzaduženiji i najviše 'na kreditu' među oblacima: gradi podatkovne centre unaprijed, a kupac plaća kasnije. Kupac je GPU-ova i memorije; NVDA mu je glavni dobavljač.",
        "ciklus": "Klasični ciklus 'prvo ulaganje, pa prihod': slobodni novčani tok je jako negativan (prema izvorima oko -23,7 milijardi USD u fiskalnoj 2026.), financira se dugom i novim dionicama. Dionica reagira jako na izvješća o novim ugovorima, ali i na strah od duga.",
        "sto_steti": "Ovisnost o nekoliko golemih kupaca (posebno jedan AI laboratorij), rast duga i troškova kamata, kašnjenje isporuke podatkovnih centara, pad povjerenja u AI ulaganja.",
        "izvori": [
            "https://erp.today/oracle-q4-2026-earnings-ai-cloud-backlog-funding/",
            "https://www.techmarketview.com/ukhotviews/archive/2026/06/11/oracles-ai-cloud-bet-delivers-growth-and-debt-questions-in-fy26",
        ],
    },
    "NBIS": {
        "ime": "Nebius Group",
        "sto_prodaje": "Iznajmljuje GPU kapacitet (AI oblak) AI tvrtkama i velikim klijentima. Mlada tvrtka; povijest podataka koja nas zanima počinje tek 2024-10-21 (prije toga je trgovanje bilo zaustavljeno).",
        "sto_vozi_prihod": "Koliko struje (MW) ima spojeno i koliko je GPU-ova isporučeno u ugovorene podatkovne centre. Prema javnim izvorima, ugovoreni kapacitet preko 2 GW, cilj ARR-a krajem 2026. 7 do 9 milijardi USD, veliki ugovori s Microsoftom i Metom (iznosi se u izvorima razlikuju, nepotvrđeno).",
        "mjesto_u_lancu": "Dolje u lancu, uz CoreWeave: kupuje NVDA GPU-ove (memorija HBM unutar njih) i prodaje ih dalje kao uslugu. Njegovi veliki kupci su ujedno i najveći oblaci iz ovog segmenta.",
        "ciklus": "Izgradnja kapaciteta financirana zaduživanjem, uz ugovore s velikim kupcima kao jamstvo. Dok kupci plaćaju, brzo raste; ako kupac odgodi ili čipovi kasne, financiranje postaje problem.",
        "sto_steti": "Visok dug i razrjeđivanje dionica, ovisnost o malom broju kupaca, kašnjenje struje i čipova, pad cijena iznajmljivanja GPU-a.",
        "izvori": [
            "https://www.fool.com/earnings/call-transcripts/2026/05/13/nebius-nbis-q1-2026-earnings-transcript/",
            "https://www.nasdaq.com/articles/can-nebius-reach-its-2026-arr-target-amid-soaring-ai-demand",
        ],
    },
    "VRT": {
        "ime": "Vertiv",
        "sto_prodaje": "Opremu koja podatkovni centar drži živim: napajanje (UPS, razvodnici) i hlađenje (tekućinsko hlađenje GPU-ova). Naši podaci počinju 2018-07-30.",
        "sto_vozi_prihod": "Naručeno i neisporučeno (backlog). Prema javnim izvorima, krajem 2025. backlog oko 15 milijardi USD (+109 posto), a vodstvo je za 2026. najavilo prodaju oko 13,25 do 13,75 milijardi USD; tvrtka prestaje objavljivati kvartalne narudžbe (izvori se u nekim brojkama razlikuju).",
        "mjesto_u_lancu": "Dobavljač 'lopata' za podatkovne centre: ne ovisi o tome koji oblak pobijedi, nego o ukupnom capexu oblaka. Zarađuje kad Microsoft, Amazon, Google, Meta i Oracle grade.",
        "ciklus": "Prati capex ciklus oblaka s odmakom od nekoliko kvartala: narudžbe prve narastu, prihod slijedi. Ako oblaci smanje capex, pad narudžbi stiže brzo.",
        "sto_steti": "Smanjenje capexa oblaka, kašnjenje projekata (struja, dozvole), konkurencija u hlađenju, visoka vrednovanost nakon naglog rasta.",
        "izvori": [
            "https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-Fourth-Quarter-with-Organic-Orders-Growth-of-252-and-Diluted-EPS-Growth-of-200-Adjusted-Diluted-EPS-37/",
            "https://www.benzinga.com/markets/earnings/26/02/50545503/vertiv-backlog-hits-record-15-billion-on-strong-ai-demand",
        ],
    },
}

MONTHS = [
    "",
    "siječanj",
    "veljača",
    "ožujak",
    "travanj",
    "svibanj",
    "lipanj",
    "srpanj",
    "kolovoz",
    "rujan",
    "listopad",
    "studeni",
    "prosinac",
]


def pct(x: float | None, d: int = 1) -> str:
    """Format a fraction as a Croatian percentage string."""
    return "n/a" if x is None else f"{x * 100:.{d}f}".replace(".", ",") + " %"


def eur(x: float | None) -> str:
    """Show what a fraction means for 1.000 EUR."""
    return "n/a" if x is None else f"{1000 * x:+.0f} EUR".replace("+", "+")


def interpret(tk: str, t: dict[str, Any]) -> dict[str, Any]:
    """Build short Croatian explanations from the computed statistics of one ticker."""
    out: dict[str, Any] = {}
    ai = t["windows"]["ai"]
    ctx = t["windows"].get("ctx", {})
    ds = []
    ds.append(
        f"Volatilnost (koliko cijena njiše u godini) u AI eri je {pct(ai['ann_vol'], 0)}: "
        f"na 1.000 EUR to znači tipično njihanje od oko {1000 * ai['ann_vol']:.0f} EUR gore ili dolje tijekom godine."
    )
    mk = ai["market"]
    ds.append(
        f"Beta prema SMH (indeks čipova) je {mk['SMH']['beta']:.2f}, prema NDX {mk['NDX']['beta']:.2f}. "
        f"Beta 1,0 znači da se kreće jednako kao indeks; kad SMH padne 10 %, ova dionica u prosjeku padne {abs(mk['SMH']['beta']) * 10:.1f} %. "
        f"Korelacija sa SMH {mk['SMH']['corr']:.2f}, s NDX {mk['NDX']['corr']:.2f} (1 = potpuno isto kretanje, 0 = nepovezano)."
    )
    if ctx.get("available"):
        ds.append(
            f"Prije 2023. volatilnost je bila {pct(ctx['ann_vol'], 0)}, beta prema SMH {ctx['market']['SMH']['beta']:.2f}."
        )
    out["rizik_i_veza"] = ds
    dd = ai["drawdowns"][0]
    rec = dd["recovery"] or "još nije oporavljen"
    out["najgori_pad"] = (
        f"Najgori pad u AI eri: {pct(dd['depth'], 0)} od {dd['start']} do dna {dd['bottom']}; oporavak: {rec}. "
        f"Na 1.000 EUR to je gubitak od oko {abs(1000 * dd['depth']):.0f} EUR na papiru. Ovo opisuje stvarnost, ne snižava ocjenu."
    )
    ch = ai["character"]
    ac1 = ch["autocorr"]["1"]
    band = ch["autocorr_2se"]
    vr20 = ch["vr20"]
    if vr20["vr"] is not None and vr20["z"] is not None and vr20["z"] < -2:
        kar = "sklon vraćanju (statistički značajan)"
    elif vr20["z"] is not None and vr20["z"] > 2:
        kar = "sklon nastavku trenda (statistički značajan)"
    else:
        kar = "nema jasnog statističkog sklona ni vraćanju ni nastavku"
    out["karakter"] = (
        f"Korelacija današnjeg i jučerašnjeg prinosa (lag 1) je {ac1:.3f}; šum je do ±{band:.3f}. "
        f"Omjer varijance na 20 dana je {vr20['vr']:.2f} (z = {vr20['z']:.1f}; ispod 1 znači vraćanje, iznad 1 nastavak trenda): {kar}."
    )
    d = ai["after_drop5_above_sma200"]
    f5, f20 = d["f5"], d["f20"]
    better = (
        f20["mean"] > f20["base_mean"]
        and f20["hit"] > f20["base_hit"]
        and f5["mean"] > f5["base_mean"]
    )
    if better:
        verdict = (
            "mali uzorak, nedovoljno za zaključak (smjer bi ipak išao u prilog premisi)"
            if d["small_sample"]
            else "potvrđuje"
        )
    else:
        verdict = "ne potvrđuje (nakon pada nije bolje nego uobičajeno)"
    out["premisa_C13C"] = (
        f"Nakon pada od najmanje 5 % u 5 dana dok je cijena iznad SMA200 (dugi prosjek 200 dana): {d['n_events']} dana, "
        f"{d['n_episodes']} odvojenih epizoda{' (MALI UZORAK)' if d['small_sample'] else ''}. "
        f"Prosječan prinos nakon 5 dana {pct(f5['mean'], 2)} (uobičajeno {pct(f5['base_mean'], 2)}), nakon 20 dana {pct(f20['mean'], 2)} "
        f"(uobičajeno {pct(f20['base_mean'], 2)}); udio pozitivnih nakon 20 dana {pct(f20['hit'], 0)} naprema {pct(f20['base_hit'], 0)} uobičajeno. "
        f"Za 1.000 EUR: prosjek nakon 20 dana {eur(f20['mean'])}. Ocjena premise u AI eri: {verdict}. To je opis, ne dokaz."
    )
    out["premisa_C13C_verdict"] = verdict
    h = ai["after_52w_high"]
    u = ai["after_3_up_days"]
    out["vrhovi_i_rast"] = (
        f"Nakon novog 52-tjednog vrha ({h['n_events']} dana): prosjek nakon 20 dana {pct(h['f20']['mean'], 2)} "
        f"(uobičajeno {pct(h['f20']['base_mean'], 2)}). Nakon 3 uzastopna rasta ({u['n_events']} dana): prosjek nakon 5 dana "
        f"{pct(u['f5']['mean'], 2)} (uobičajeno {pct(u['f5']['base_mean'], 2)})."
    )
    se = ai["seasonality"]
    best = max(
        se.items(), key=lambda kv: -1 if kv[1]["mean"] is None else kv[1]["mean"]
    )
    worst = min(
        se.items(), key=lambda kv: 9 if kv[1]["mean"] is None else kv[1]["mean"]
    )
    out["sezonalnost"] = (
        f"Mjesečna sezonalnost u AI eri: najbolji mjesec {MONTHS[int(best[0])]} (prosjek {pct(best[1]['mean'])}, n = {best[1]['n']}), "
        f"najgori {MONTHS[int(worst[0])]} (prosjek {pct(worst[1]['mean'])}, n = {worst[1]['n']}). "
        "UPOZORENJE: po svakom mjesecu u AI eri imamo samo 3 do 4 opažanja; to je šum, ne obrazac."
    )
    g = ai["gaps"]["largest"][0]
    c = ai["concentration"]
    share = c["best10_log_share_of_total"]
    out["skokovi_i_koncentracija"] = (
        f"Najveći skok otvaranja: {pct(g['gap'])} dana {g['date']}. Ukupni prinos u AI eri {pct(c['total_return'], 0)}, "
        f"a bez 10 najboljih dana {pct(c['total_return_without_best10'], 0)}"
        + (
            f" (10 najboljih dana čini {pct(share, 0)} ukupnog logaritamskog prinosa)."
            if share is not None
            else "."
        )
        + f" Na 1.000 EUR: s tim danima {1000 * (1 + c['total_return']):.0f} EUR, bez njih {1000 * (1 + c['total_return_without_best10']):.0f} EUR. "
        "To pokazuje koliko zarada ovisi o malo dana; ovo ne snižava ocjenu."
    )
    ll = ai["lead_lag"]

    def ll_text(name: str, label: str) -> str:
        x = ll[name]
        if "lead_corr_k+1" not in x:
            return f"{label}: premalo podataka."
        return (
            f"{label}: ako ova dionica danas raste, sutrašnja korelacija s referencom je {x['lead_corr_k+1']:+.2f}, "
            f"a jučerašnja {x['follow_corr_k-1']:+.2f} (šum ±{x['noise_band_2se']:.2f})."
        )

    verd = {n: ll[n].get("verdict") for n in ("SMH", "peers")}
    jednak = all(v == "simultaneous" for v in verd.values())
    out["vodi_ili_slijedi"] = " ".join(
        [ll_text("SMH", "SMH"), ll_text("peers", "Ostali iz segmenta")]
    ) + (
        " Zaključak: kreće se istodobno s referencama (dnevni podaci ne vide kretanje unutar dana)."
        if jednak
        else " Zaključak: postoji slab odmak, ali korelacije su male; ne čitati kao signal."
    )
    s = ai["sma200"]
    b = s["buckets"]
    out["sma200"] = (
        f"Udio dana iznad SMA200: {pct(s['share_days_above'], 0)}; medijan udaljenosti {pct(s['p50'])}. Trenutno (do 2026-10-05) "
        f"{pct(s['latest_overall'])} od SMA200. Prosjek nakon 20 dana kad je cijena 25 % ili više iznad SMA200: {pct(b['over_25pct_above']['fwd20_mean'], 2)} "
        f"(n = {b['over_25pct_above']['n_days']} dana), a kad je ispod SMA200: {pct(b['below_sma200']['fwd20_mean'], 2)} (n = {b['below_sma200']['n_days']})."
    )
    sw = ai["swing"]
    out["podrska_otpor"] = (
        f"Podrška (prethodni lokalni minimum): {sw['support']['touches']} prvih dodira, zadržala u {pct(sw['support']['hold_rate'], 0)}. "
        f"Otpor (prethodni lokalni maksimum): {sw['resistance']['touches']} prvih dodira, zadržao u {pct(sw['resistance']['hold_rate'], 0)}. "
        "Zadržavanje = nema zatvaranja više od 1,5 % preko razine u 3 dana nakon dodira. Nema usporedbe sa slučajnim razinama, pa to nije dokaz da razine 'rade'."
        + (
            " MALI UZORAK."
            if sw["support"]["small_sample"] or sw["resistance"]["small_sample"]
            else ""
        )
    )
    return out


GLOSSARY = {
    "volatilnost": "Koliko se cijena njiše u godini. 30 % znači da je tipično kretanje oko 300 EUR na 1.000 EUR.",
    "beta": "Koliko se dionica miče kad se indeks pomakne 1 %. Beta 1,5 i pad indeksa 10 % znači pad od oko 15 %, odnosno 150 EUR na 1.000 EUR.",
    "korelacija": "Brojka između -1 i 1: koliko dva kretanja idu zajedno.",
    "drawdown": "Pad od vrha do dna. Pad od 35 % pretvara 1.000 EUR u 650 EUR na papiru.",
    "autokorelacija": "Je li današnji pomak povezan s jučerašnjim. Blizu nule = nema pamćenja.",
    "omjer varijance": "Ispod 1: kretanja se djelomično poništavaju (vraćanje). Iznad 1: kretanja se nastavljaju (trend).",
    "SMA200": "Prosjek zadnjih 200 zatvaranja, dugoročni trend.",
    "podrška i otpor": "Cijena na kojoj je pad (podrška) ili rast (otpor) prije stao.",
}


def main() -> None:
    """Compute stats, add Croatian text and write profile.json and profile_stats.csv."""
    raw = compute("cloud")
    tickers: dict[str, Any] = {}
    for tk, t in raw["tickers"].items():
        tickers[tk] = {
            **t,
            "tumacenje_hr": interpret(tk, t),
            "mehanizam_hr": MECHANISM[tk],
            "oznaka_mehanizma": CONTEXT_TAG,
        }
    # a ticker is flagged when its own data has quirks (from universe.json)
    uni = json.loads((OUT_ROOT / "universe.json").read_text())
    for row in uni["segments"]["cloud"]["tickers"]:
        if row["ticker"] in tickers:
            tickers[row["ticker"]]["napomene_podataka"] = row["issues"] + row["notes"]
    out = {
        "segment": "cloud",
        "naziv": raw["segment_name"],
        "common_end": raw["common_end"],
        "ai_era_start": raw["ai_era_start"],
        "iskljuceno": raw["excluded"],
        "napomene_metode_hr": [
            "Sve brojke izračunate su iz dnevnih CSV datoteka (data/ohlcv) do zajedničkog završnog datuma 2026-10-05. Mehanizam poslovanja je kontekst iz javnih izvora i označen je kao takav.",
            "AI era (od 2023-01-01) je glavni prozor; 2016 do 2022 je samo kontekst. NBIS ima podatke tek od 2024-10-21 (prije toga trgovanje je bilo zaustavljeno), VRT od 2018-07-30; CRWV je isključen jer ima premalo povijesti.",
            "NDX datoteka ima nedosljedne OHLC vrijednosti, pa se za NDX koristi samo zatvaranje (beta i korelacija).",
            "Događaji (pad 5 dana od najmanje 5 % uz zatvaranje iznad SMA200, novi 52-tjedni vrh = zatvaranje iznad najvišeg zatvaranja prethodnih 252 dana, 3 uzastopna rasta) imaju epizode spojene ako su bliže od 10 dana, da se isti pad ne broji više puta. Prikazan je i sirovi broj. Uzorak ispod 30 epizoda označen je kao mali.",
            "'Uobičajeno' je prosjek svih dana istog razdoblja; za premisu C13C usporedba je sa svim danima iznad SMA200.",
            "Lead/lag: korelacija prinosa dionice u danu t s prinosom reference u danu t+k. Pozitivno k znači da dionica 'ide prva'. Šum je približno ±2/sqrt(n).",
            "Podrška/otpor: lokalni minimum ili maksimum unutar ±5 dana, poznat tek 5 dana kasnije (bez gledanja u budućnost). Dodir = unutar 1,5 % razine, prvi dodir u 120 dana; proboj = zatvaranje više od 1,5 % preko razine u istom ili sljedeća 3 dana.",
            "Ovo je opis ponašanja, ne signal, ne strategija ni Critic PASS. Svaka ideja iz ovoga ide kao NOVA hipoteza s novim ID-em. Nema naloga.",
            "Provjera EU dostupnosti: pojedinačne američke dionice su općenito dostupne, ali dostupnost kod IBKR-a za svaki simbol je nepotvrđeno.",
        ],
        "pojmovnik_hr": GLOSSARY,
        "tickers": tickers,
    }
    d = OUT_ROOT / "segments" / "cloud"
    d.mkdir(parents=True, exist_ok=True)
    (d / "profile.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    rows = []
    for tk, t in tickers.items():
        for w, s in t["windows"].items():
            if not s.get("available"):
                continue
            d5, hi, up = (
                s["after_drop5_above_sma200"],
                s["after_52w_high"],
                s["after_3_up_days"],
            )
            mk, cc, sw, sm = s["market"], s["character"], s["swing"], s["sma200"]
            rows.append(
                {
                    "ticker": tk,
                    "window": "AI era 2023+" if w == "ai" else "context 2016-2022",
                    "start": s["start"],
                    "end": s["end"],
                    "bars": s["bars"],
                    "ann_vol": s["ann_vol"],
                    "total_return": s["total_return"],
                    "beta_smh": mk["SMH"]["beta"],
                    "corr_smh": mk["SMH"]["corr"],
                    "beta_ndx": mk["NDX"]["beta"],
                    "corr_ndx": mk["NDX"]["corr"],
                    "worst_dd": s["drawdowns"][0]["depth"],
                    "worst_dd_start": s["drawdowns"][0]["start"],
                    "worst_dd_bottom": s["drawdowns"][0]["bottom"],
                    "worst_dd_recovery": s["drawdowns"][0]["recovery"],
                    "autocorr_lag1": cc["autocorr"]["1"],
                    "vr5": cc["vr5"]["vr"],
                    "vr20": cc["vr20"]["vr"],
                    "vr20_z": cc["vr20"]["z"],
                    "drop5_events": d5["n_events"],
                    "drop5_episodes": d5["n_episodes"],
                    "drop5_f1_mean": d5["f1"]["mean"],
                    "drop5_f5_mean": d5["f5"]["mean"],
                    "drop5_f10_mean": d5["f10"]["mean"],
                    "drop5_f20_mean": d5["f20"]["mean"],
                    "drop5_f20_hit": d5["f20"]["hit"],
                    "base_f5_mean": d5["f5"]["base_mean"],
                    "base_f20_mean": d5["f20"]["base_mean"],
                    "base_f20_hit": d5["f20"]["base_hit"],
                    "high52_events": hi["n_events"],
                    "high52_f20_mean": hi["f20"]["mean"],
                    "high52_f20_hit": hi["f20"]["hit"],
                    "up3_events": up["n_events"],
                    "up3_f5_mean": up["f5"]["mean"],
                    "up3_f5_hit": up["f5"]["hit"],
                    "best10_log_share": s["concentration"]["best10_log_share_of_total"],
                    "return_without_best10": s["concentration"][
                        "total_return_without_best10"
                    ],
                    "largest_gap": s["gaps"]["largest"][0]["gap"],
                    "largest_gap_date": s["gaps"]["largest"][0]["date"],
                    "sma200_share_above": sm["share_days_above"],
                    "sma200_dist_latest": sm["latest_overall"],
                    "support_touches": sw["support"]["touches"],
                    "support_hold_rate": sw["support"]["hold_rate"],
                    "resist_touches": sw["resistance"]["touches"],
                    "resist_hold_rate": sw["resistance"]["hold_rate"],
                    "leadlag_smh_k+1": s["lead_lag"]["SMH"].get("lead_corr_k+1"),
                    "leadlag_smh_k-1": s["lead_lag"]["SMH"].get("follow_corr_k-1"),
                    "leadlag_peers_k+1": s["lead_lag"]["peers"].get("lead_corr_k+1"),
                    "leadlag_peers_k-1": s["lead_lag"]["peers"].get("follow_corr_k-1"),
                }
            )
    pd.DataFrame(rows).to_csv(d / "profile_stats.csv", index=False, float_format="%.4f")
    print("written", d)


if __name__ == "__main__":
    main()
