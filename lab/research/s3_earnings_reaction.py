"""Study 3: MU earnings reaction (gap, reaction day, +5d, +20d), by IS/WF/HO, and peer moves on MU earnings days."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from lab.research.common import DATA, daily, md_table, num, pct, split_of, write_report

PEERS = ["WDC", "STX", "SMH"]


def reaction_metrics(t: str, react: pd.Timestamp) -> dict:
    """Gap, reaction-day, +5d and +20d returns (%) for ticker t around a reaction date; 5d/20d start at reaction close."""
    d = daily(t)
    if react not in d.index:
        return {}
    i = d.index.get_loc(react)
    out = {
        "gap": (d.open.iloc[i] / d.close.iloc[i - 1] - 1) * 100,
        "day": (d.close.iloc[i] / d.close.iloc[i - 1] - 1) * 100,
        "intra": (d.close.iloc[i] / d.open.iloc[i] - 1) * 100,
    }
    out["d5"] = (d.close.iloc[i + 5] / d.close.iloc[i] - 1) * 100 if i + 5 < len(d) else np.nan
    out["d20"] = (d.close.iloc[i + 20] / d.close.iloc[i] - 1) * 100 if i + 20 < len(d) else np.nan
    return out


def summarize(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = {}
    for c in cols:
        x = df[c].dropna()
        rows[c] = dict(n=len(x), prosjek=x.mean(), medijan=x.median(), std=x.std(), pozitivnih_pct=(x > 0).mean() * 100 if len(x) else np.nan, prosj_apsolutno=x.abs().mean())
    return pd.DataFrame(rows).T


def baseline_abs(t: str, split: str | None = None) -> tuple[float, float]:
    """Typical absolute close-to-close move and absolute gap (%) on all days (the 'normal day' yardstick)."""
    d = daily(t)
    day = (d.close.pct_change() * 100).abs()
    gap = ((d.open / d.close.shift(1) - 1) * 100).abs()
    if split:
        m = d.index.map(split_of) == split
        day, gap = day[m], gap[m]
    return float(day.mean()), float(gap.mean())


def main() -> None:
    e = pd.read_csv(DATA / "news" / "MU_earnings_dates.csv", parse_dates=["announce_date_after_close", "reaction_date"])
    mu = pd.DataFrame([reaction_metrics("MU", r) for r in e.reaction_date], index=e.reaction_date)
    # consistency check against the supplied file
    diff = pd.DataFrame(
        {
            "gap": (mu.gap.values - e.gap_open_pct.values),
            "day": (mu.day.values - e.reaction_day_pct.values),
            "d5": (mu.d5.values - e.next5d_from_reaction_close_pct.values),
            "d20": (mu.d20.values - e.next20d_pct.values),
        }
    )
    maxdiff = diff.abs().max()
    mu["split"] = [split_of(r) for r in mu.index]
    cols = ["gap", "day", "intra", "d5", "d20"]
    names = {"gap": "gap otvaranja", "day": "dan reakcije", "intra": "otvaranje->zatvaranje tog dana", "d5": "+5 dana", "d20": "+20 dana"}
    all_s = summarize(mu, cols)
    base_day, base_gap = baseline_abs("MU")
    ratio_day = all_s.loc["day", "prosj_apsolutno"] / base_day
    ratio_gap = all_s.loc["gap", "prosj_apsolutno"] / base_gap
    t_day = stats.ttest_1samp(mu.day, 0)
    t_d5 = stats.ttest_1samp(mu.d5.dropna(), 0)
    t_d20 = stats.ttest_1samp(mu.d20.dropna(), 0)
    # unconditional mean 5d / 20d forward returns for MU (any day) as yardstick
    d = daily("MU")
    f5 = (d.close.shift(-5) / d.close - 1).dropna() * 100
    f20 = (d.close.shift(-20) / d.close - 1).dropna() * 100
    t_intra = stats.ttest_1samp(mu.intra, 0)
    base_intra = ((d.close / d.open - 1) * 100).mean()
    corr_gap_intra = mu.gap.corr(mu.intra)
    corr_day_d5 = mu.day.corr(mu.d5)
    corr_day_d20 = mu.day.corr(mu.d20)
    pr_same, pr_ratio = {}, {}
    for p_ in PEERS:
        pm_ = pd.DataFrame([reaction_metrics(p_, r) for r in e.reaction_date], index=e.reaction_date)
        pr_same[p_] = (np.sign(pm_.day.values) == np.sign(mu.day.values)).mean() * 100
        pr_ratio[p_] = pm_.day.abs().mean() / baseline_abs(p_)[0]
    up = mu[mu.day > 0]
    dn = mu[mu.day < 0]
    L = ["# MU izvještaji o zaradama: što se događa s cijenom\n"]
    L.append("## Sažetak u 5 redaka\n")
    L.append(
        f"1. Micron objavljuje rezultate poslije zatvaranja burze; cijena reagira idući dan. Imamo {len(mu)} izvještaja (2016-2026), što je MALI uzorak.\n"
        f"2. Dan reakcije je velik: prosječni pomak MU-a je {num(all_s.loc['day','prosj_apsolutno'],1)} % (po apsolutnoj vrijednosti), što je {num(ratio_day,1)}x običan dan ({num(base_day,1)} %). Smjer je ipak neodređen: prosjek {pct(all_s.loc['day','prosjek'],1)}, a gore je završilo {num(all_s.loc['day','pozitivnih_pct'],0)} % dana (p={num(t_day.pvalue,2)}, nije značajno različito od nule).\n"
        f"3. Nakon reakcije: prosječno {pct(all_s.loc['d5','prosjek'],1)} u idućih 5 dana (p={num(t_d5.pvalue,2)}) i {pct(all_s.loc['d20','prosjek'],1)} u 20 (p={num(t_d20.pvalue,2)}); medijan 5d je {pct(all_s.loc['d5','medijan'],1)}. Nema pouzdanog nastavka ni preokreta. Jedina doslijedna sitnica: ostatak dana reakcije (otvaranje->zatvaranje) je u prosjeku {pct(all_s.loc['intra','prosjek'],1)}, negativan u sva tri razdoblja (p={num(t_intra.pvalue,2)}), tj. gap se često djelomično povuče (običan dan MU-a ima otvaranje->zatvaranje {pct(base_intra,2)}); p nije korigiran za ~15 pogledanih mjera i n je mali, pa je to hipoteza, ne rezultat.\n"
        f"4. Isti dan se miču i WDC, STX i SMH: u istom smjeru kao MU u {num(pr_same['WDC'],0)} %, {num(pr_same['STX'],0)} % i {num(pr_same['SMH'],0)} % slučajeva, i to {num(pr_ratio['WDC'],1)}x, {num(pr_ratio['STX'],1)}x i {num(pr_ratio['SMH'],1)}x jače od običnog dana. Na dane zarade nisu povezaniji s MU-om nego inače, dakle samo prate isti val.\n"
        f"5. Što s tim: izvještaj je događaj velikog RIZIKA (velik pomak u oba smjera), ne događaj s dokazanim smjerom. Ne kupuj 'uoči zarade' u nadi rasta; moguće je jedino pravilo o veličini pozicije oko izvještaja.\n"
    )
    L.append("## Pojmovi (laički)\n")
    L.append(
        "- **Izvještaj o zaradama (earnings)**: firma četiri puta godišnje objavi koliko je zaradila i što očekuje. Kao školska svjedodžba: iznenađenje (bolje ili gore od očekivanog) pomiče cijenu.\n"
        "- **Gap otvaranja**: razlika između jučerašnjeg zatvaranja i današnjeg otvaranja. Kao da trgovina preko noći promijeni cijenu na vratima: nema prometa između, cijena 'preskoči'.\n"
        "- **Dan reakcije**: prvi dan trgovanja nakon objave (zatvaranje tog dana naspram prethodnog zatvaranja).\n"
        "- **+5 dana / +20 dana**: promjena od zatvaranja dana reakcije do zatvaranja 5 odnosno 20 trgovačkih dana kasnije. Pokazuje nastavlja li se pomak ili se vraća.\n"
        "- **Medijan**: srednja vrijednost kad poredaš sve slučajeve; manje je osjetljiv na jedan ekstremni dan od prosjeka.\n"
        "- **p-vrijednost**: koliko je vjerojatno da bi se ovakav prosjek vidio i kad je pravi prosjek nula. Mali p (npr. <0,05) znači 'teško da je slučajno'; veliki p znači 'ne možemo reći'.\n"
        f"- **Provjera podataka**: izračunali smo gap/dan/+5/+20 iz dnevnih cijena i usporedili s `MU_earnings_dates.csv`; najveća razlika u postotnim bodovima: gap {num(maxdiff['gap'],3)}, dan {num(maxdiff['day'],3)}, +5d {num(maxdiff['d5'],3)}, +20d {num(maxdiff['d20'],3)} (0 znači potpuno isto).\n"
    )
    L.append("## 1. Svi izvještaji (n = %d)\n" % len(mu))
    t = all_s.copy()
    t["n"] = t["n"].astype(int)
    t.index = [names[i] for i in t.index]
    t.columns = ["n", "prosjek %", "medijan %", "std %", "% pozitivnih", "prosj. apsolutni pomak %"]
    t.index.name = "mjera"
    L.append(md_table(t, "{:.2f}") + "\n")
    L.append(
        f"\n**Što to znači:** običan dan MU-a ima prosječni |pomak| {num(base_day,2)} % (gap otvaranja {num(base_gap,2)} %), dakle dan reakcije je ~{num(ratio_day,1)}x veći, a gap ~{num(ratio_gap,1)}x. "
        f"Za usporedbu: prosječni 5-dnevni i 20-dnevni pomak MU-a na SVAKI dan je {pct(f5.mean(),1)} i {pct(f20.mean(),1)} (zbog golemog rasta MU-a 2016-26), pa je prosjek nakon izvještaja ispod ili oko običnog. "
        f"Nastavlja li se pomak? Korelacija dan reakcije s +5d je {num(corr_day_d5,2)} (s +20d {num(corr_day_d20,2)}); korelacija gapa i ostatka dana (otvaranje->zatvaranje) je {num(corr_gap_intra,2)}. Brojevi blizu 0 znače da jedno ne predviđa drugo.\n"
    )
    L.append("## 2. Podjela na razdoblja IS / WF / HO\n")
    L.append("IS = 2016-2020, WF = 2021-2023, HO = 2024+. Razdoblja su ista kao u cijelom labu. Svaki red ima <30 slučajeva: čitaj kao opis, ne kao dokaz.\n")
    for sp in ["IS", "WF", "HO"]:
        sub = mu[mu.split == sp]
        s2 = summarize(sub, cols)
        s2["n"] = s2["n"].astype(int)
        s2.index = [names[i] for i in s2.index]
        s2.columns = ["n", "prosjek %", "medijan %", "std %", "% pozitivnih", "prosj. apsolutni pomak %"]
        s2.index.name = sp
        L.append(f"\n**{sp}** (n = {len(sub)})\n\n" + md_table(s2, "{:.2f}") + "\n")
    gr = mu.groupby("split")[cols].mean()
    signs = {c: [np.sign(gr.loc[s, c]) for s in ["IS", "WF", "HO"] if s in gr.index] for c in cols}
    stable = [names[c] for c, v in signs.items() if len(set(v)) == 1]
    L.append(f"\n**Što to znači:** predznak prosjeka je isti u sva tri razdoblja samo za: {', '.join(stable) if stable else 'ništa'}. Ostalo mijenja predznak, pa nema stabilnog obrasca.\n")
    L.append("## 3. Poslije dobre i poslije loše reakcije\n")
    ud = pd.DataFrame(
        {
            "reakcija dana gore (n=%d)" % len(up): [up.d5.mean(), up.d20.mean(), up.d5.median(), up.d20.median()],
            "reakcija dana dolje (n=%d)" % len(dn): [dn.d5.mean(), dn.d20.mean(), dn.d5.median(), dn.d20.median()],
        },
        index=["prosjek +5d %", "prosjek +20d %", "medijan +5d %", "medijan +20d %"],
    )
    L.append(md_table(ud, "{:.2f}") + "\n")
    t_ud = stats.ttest_ind(up.d5.dropna(), dn.d5.dropna(), equal_var=False)
    L.append(f"\nRazlika +5d između gore i dolje: p={num(t_ud.pvalue,2)}. Uzorak je mali, pa čak i velika razlika može biti slučajna.\n")
    # peers
    L.append("## 4. Ostale memorijske dionice na dan MU izvještaja\n")
    prow = {}
    mu_day = mu.day
    for p in PEERS:
        pm = pd.DataFrame([reaction_metrics(p, r) for r in e.reaction_date], index=e.reaction_date)
        bd, _ = baseline_abs(p)
        prow[p] = dict(
            n=len(pm.day.dropna()),
            prosjek_dan=pm.day.mean(),
            prosj_abs_dan=pm.day.abs().mean(),
            obican_abs_dan=bd,
            omjer=pm.day.abs().mean() / bd,
            corr_s_MU_na_dane_zarade=pm.day.corr(mu_day),
            prosjek_d5=pm.d5.mean(),
            prosjek_d20=pm.d20.mean(),
            pozitivni_isti_smjer_kao_MU=((np.sign(pm.day.values) == np.sign(mu_day.values)).mean()) * 100,
        )
    pr = pd.DataFrame(prow).T
    pr["n"] = pr["n"].astype(int)
    pr.columns = ["n", "prosj. dan %", "prosj. apsolutni dan %", "običan apsolutni dan %", "omjer apsolutni/običan", "korelacija s MU danom", "prosj. +5d %", "prosj. +20d %", "% istog smjera kao MU"]
    pr.index.name = "dionica"
    L.append(md_table(pr, "{:.2f}") + "\n")
    # baseline correlation of peers to MU on all days
    allc = {p: daily(p).close.pct_change().corr(daily("MU").close.pct_change()) for p in PEERS}
    L.append(
        "\n**Što to znači:** 'omjer apsolutni/običan' veći od 1 znači da se dionica na dan MU zarade miče više nego inače. "
        "'korelacija s MU danom' je povezanost s MU-om samo na ta dana; za usporedbu, korelacija na SVE dane je "
        + ", ".join(f"{p} {num(v,2)}" for p, v in allc.items())
        + ". Ako je na dane zarade slična ili manja, peers se ponašaju kao inače (prate isto tržište); ako je veća, MU zarada 'povlači' sektor. "
        "Gdje je smjer isti kao MU u ~50 % slučajeva, nema veze.\n"
    )
    # last row
    last = e.iloc[-1]
    L.append(f"\nZadnji izvještaj ({last.announce_date_after_close.date()}, reakcija {last.reaction_date.date()}) nema još +5/+20 dana pa nije u tim stupcima.\n")
    L.append("## Što napraviti / ne napraviti\n")
    L.append(
        "- **Ne** pretpostavljaj smjer: dan reakcije je velik ali dobar/loš ishod nije predvidljiv iz ovih podataka.\n"
        "- Moguće je korisno: **ne držati veliku poziciju preko noći uoči izvještaja** ili smanjiti veličinu (to je pravilo rizika, ne ulaz). Kalendar izvještaja je poznat unaprijed, pa je to bez gledanja u budućnost.\n"
        "- Svako pravilo o zaradama mora imati unaprijed zadanu veličinu i izlaz; s ~43 slučaja i 3 razdoblja nema statističke snage za fino podešavanje.\n"
        "- C6 (GapFill_Earn) je već FAIL-like (n premalen); ne oživljavati istu liniju.\n"
    )
    L.append("## Ograničenja\n- n = 43 ukupno (~14 po razdoblju); standardne pogreške su velike.\n- 'Prosječni običan dan' računat je na svim danima, uključujući dane zarade.\n- Nema podataka o očekivanjima analitičara (iznenađenje), pa ne znamo je li 'dobar' izvještaj bio bolji od očekivanog.\n- Hourly/intraday reakcija nije analizirana ovdje.\n")
    write_report("earnings_reaction.md", "\n".join(L))
    print(maxdiff.to_dict())


if __name__ == "__main__":
    main()
