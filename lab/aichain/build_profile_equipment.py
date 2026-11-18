"""Merge computed stats with Croatian mechanism text into profile.json (equipment segment)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from lab.aichain.mechanism_equipment import COMPANIES, GLOSSARY, LABEL
from lab.aichain.profile_stats import OUT_BASE

SEG = OUT_BASE / "segments" / "equipment"


def mean_col(df: pd.DataFrame, win: str, col: str) -> float:
    return float(df[df.window == win][col].astype(float).mean())


def findings(df: pd.DataFrame, raw: dict) -> list[str]:
    p = raw["pooled_c13_premise_ai_era"]
    a, b = "ai_era", "pre_2023"
    sup_real = mean_col(df, a, "support_hold_pct")
    sup_pl = mean_col(df, a, "support_hold_placebo_pct")
    res_real = mean_col(df, a, "resist_hold_pct")
    res_pl = mean_col(df, a, "resist_hold_placebo_pct")
    n_lead = int((df[(df.window == a)]["leadlag_vs_smh"] == "vodi").sum())
    return [
        f"Volatilnost u AI eri (2023+) u prosjeku {mean_col(df, a, 'ann_vol_pct'):.0f}% godišnje (prije 2023.: {mean_col(df, b, 'ann_vol_pct'):.0f}%). "
        f"Na 1.000 EUR to znači tipičan godišnji raspon od oko {1000 * mean_col(df, a, 'ann_vol_pct') / 100:.0f} EUR gore ili dolje. Najgori pad od vrha u AI eri prosječno je "
        f"{mean_col(df, a, 'worst_dd_pct'):.0f}%, tj. 1.000 EUR bi u najgorem trenutku bio oko {1000 * (1 + mean_col(df, a, 'worst_dd_pct') / 100):.0f} EUR.",
        f"Zajedno s poluvodičima: prosječna korelacija prema SMH je {mean_col(df, a, 'corr_smh'):.2f}, beta prema SMH {mean_col(df, a, 'beta_smh'):.2f}. "
        "Ove dionice nisu zasebna oklada, nego pojačana verzija cijelog poluvodičkog tržišta (ACMR je najslobodnija).",
        f"Karakter: autokorelacija prvog dana je blago negativna (prosjek {mean_col(df, a, 'ac1'):.3f}) i omjer varijance je ispod 1 "
        f"(5 dana {mean_col(df, a, 'vr5'):.2f}, 20 dana {mean_col(df, a, 'vr20'):.2f}). Znači blaga sklonost vraćanju nakon kratkih skokova, nikako uporan trend dan za danom. "
        f"Prije 2023. je isto bilo izraženije (autokorelacija {mean_col(df, b, 'ac1'):.3f}).",
        f"Premisa C13C (pad 5 dana od barem 5% dok je cijena iznad SMA200): združeno {p['fwd_20d']['n_events_pooled']} događaja u AI eri (razmak 10 dana) daje prosječno "
        f"{p['fwd_5d']['mean_pct']}% za 5 dana i {p['fwd_20d']['mean_pct']}% za 20 dana, uz uspješnost {p['fwd_20d']['hit_pct']}%. "
        f"Bezuvjetni prosjek za 20 dana je {p['fwd_20d']['uncond_mean_pct_avg_of_tickers']}% uz {p['fwd_20d']['uncond_hit_pct_avg_of_tickers']}%. "
        "Razlika je mala za 20 dana, a veća za 5 do 10 dana. UPOZORENJE: dionice padaju istih dana (korelacija je visoka), pa je broj neovisnih događaja bitno manji od zbroja, "
        "a AI era je jako rastuće razdoblje. Ovo je opis, ne dokaz prednosti i ne strategija.",
        f"Potpora i otpor: u AI eri cijena je zadržala prijašnje dno u {sup_real:.0f}% dodira, a kontrolne proizvoljne razine u {sup_pl:.0f}%. "
        f"Za prijašnje vrhove: {res_real:.0f}% naspram {res_pl:.0f}% kod kontrolnih razina. Dakle prijašnja dna i vrhovi nisu pokazali posebnost u odnosu na slučajne razine. "
        "(Kontrola je nesavršena, uzorak po dionici je mali.)",
        f"Tko je prvi: prema SMH-u kao vodeći je označeno {n_lead} od 10 dionica (LRCX, ASML), većina se kreće istodobno. Razlike u koeficijentima su male, pa to ne tumačimo kao pouzdan signal.",
        "Koncentracija: u AI eri velik dio povrata dolazi od 10 najboljih dana (ENTG preko 100%, što znači da je bez tih dana povrat negativan). "
        "To je opis ovisnosti o rijetkim danima, ne razlog za nižu ocjenu.",
        "Sezonalnost: u AI eri svaki kalendarski mjesec ima samo 3 do 4 opažanja po dionici, pa je ne koristiti za zaključke.",
    ]


def main() -> None:
    raw = json.load(open(SEG / "_stats_raw.json"))
    df = pd.read_csv(SEG / "profile_stats.csv")
    companies = {}
    for tk in raw["tickers_used"]:
        c = COMPANIES[tk]
        companies[tk] = {
            "mechanism_hr": {
                k: c[k] for k in ("sells", "drivers", "chain", "cycle", "hurts")
            },
            "mechanism_label": LABEL,
            "sources": c["sources"],
            "stats": raw["stats"][tk],
        }
    out = {
        "segment": "equipment",
        "segment_name_hr": "Oprema za proizvodnju čipova",
        "common_end": raw["common_end"],
        "main_window": "AI era 2023-01-01 do common_end; 2016-2022 samo kontekst",
        "excluded": raw["excluded"],
        "data_note": "Sve statistike izračunate iz data/ohlcv/{TICKER}_1d.csv, SMH i NDX iz istog direktorija. Opis, ne strategija; nije Critic PASS.",
        "method_notes": {
            "events_thinned": "Događaji se prorjeđuju (najmanje 10 barova razmaka) jer se inače preklapaju; prikazano i bez prorjeđivanja.",
            "support_resistance": "Zaokret = najniža/najviša cijena u 5 barova s obje strane, poznata tek 5 barova kasnije (bez gledanja u budućnost). Dodir = prvi ulazak u pojas 1,5%; zadržano ako zatvaranje u idućih 5 dana ne probije pojas. Kontrola: razina na proizvoljnom danu pomaknutom 7 barova.",
            "lead_lag": "Korelacija dnevnog povrata dionice s povratom reference od jedan do tri dana ranije i obrnuto.",
            "top10": "Udio 10 najboljih dana računa se na log-povratima; kad je ukupni povrat blizu nule ili negativan, udio je besmislen (npr. preko 100%).",
        },
        "pooled_c13_premise_ai_era": raw["pooled_c13_premise_ai_era"],
        "glossary_hr": GLOSSARY,
        "findings_hr": findings(df, raw),
        "companies": companies,
    }
    json.dump(out, open(SEG / "profile.json", "w"), ensure_ascii=False, indent=1)
    (SEG / "_stats_raw.json").unlink()
    print("ok")


if __name__ == "__main__":
    main()
