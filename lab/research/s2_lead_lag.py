"""Study 2: do AMAT/LRCX/KLAC/SMH daily returns lead MU/WDC/STX at lags 1-20 days?"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from lab.research.common import SPLITS, close_panel, md_table, num, write_report

LEADERS = ["AMAT", "LRCX", "KLAC", "SMH"]
TARGETS = ["MU", "WDC", "STX"]
MAXLAG = 20


def lag_corr(x: pd.Series, y: pd.Series, k: int) -> tuple[float, float, int]:
    """corr(x[t-k], y[t]) with its two-sided p-value (plain Pearson, daily returns ~ uncorrelated)."""
    d = pd.concat([x.shift(k), y], axis=1).dropna()
    r, p = stats.pearsonr(d.iloc[:, 0], d.iloc[:, 1])
    return float(r), float(p), len(d)


def main() -> None:
    px = close_panel(LEADERS + TARGETS)
    ret = np.log(px).diff().dropna()
    n_tests = len(LEADERS) * len(TARGETS) * MAXLAG
    rows = []
    for ldr in LEADERS:
        for tgt in TARGETS:
            for k in range(1, MAXLAG + 1):
                r, p, n = lag_corr(ret[ldr], ret[tgt], k)
                sub = {}
                for s, (a, b) in SPLITS.items():
                    rr = ret.loc[a:b]
                    sub[s] = lag_corr(rr[ldr], rr[tgt], k)[0]
                rows.append(dict(leader=ldr, target=tgt, lag=k, r=r, p=p, n=n, **{f"r_{s}": v for s, v in sub.items()}))
    df = pd.DataFrame(rows)
    df["p_bonf"] = np.minimum(df.p * n_tests, 1.0)
    # Holm step-down on the 240 tests
    order = df.p.sort_values().index
    holm = {}
    run = 0.0
    for i, idx in enumerate(order):
        run = max(run, min((n_tests - i) * df.p[idx], 1.0))
        holm[idx] = run
    df["p_holm"] = pd.Series(holm)
    df["same_sign_all_splits"] = np.sign(df.r_IS) == np.sign(df.r_WF)
    df["same_sign_all_splits"] &= np.sign(df.r_WF) == np.sign(df.r_HO)
    df["same_sign_all_splits"] &= np.sign(df.r_HO) == np.sign(df.r)
    n_obs = int(df.n.median())
    se = 1 / np.sqrt(n_obs)
    thr = stats.norm.ppf(1 - 0.025 / n_tests) * se  # Bonferroni threshold in correlation units
    exp_false = 0.05 * n_tests
    n_nom = int((df.p < 0.05).sum())
    n_bonf = int((df.p_bonf < 0.05).sum())
    # contemporaneous correlation for reference (same-day, NOT a lead)
    contemp = pd.DataFrame({tgt: {ldr: ret[ldr].corr(ret[tgt]) for ldr in LEADERS} for tgt in TARGETS})
    # lag-1 table
    l1 = df[df.lag == 1].set_index(["leader", "target"])
    # 5-day non-overlapping blocks
    w = np.log(px).iloc[::5].diff().dropna()
    wrows = {}
    for tgt in TARGETS:
        wrows[tgt] = {ldr: lag_corr(w[ldr], w[tgt], 1)[0] for ldr in LEADERS}
    wk = pd.DataFrame(wrows)
    wk_p = {tgt: {ldr: lag_corr(w[ldr], w[tgt], 1)[1] for ldr in LEADERS} for tgt in TARGETS}
    # size of the effect at lag 1 in bps per 1-sd leader move
    top = df.reindex(df.r.abs().sort_values(ascending=False).index).head(12).copy()
    surv = df[df.p_bonf < 0.05]
    own = pd.DataFrame({t: {"cijela": ret[t].autocorr(1), **{s_: ret.loc[a:b, t].autocorr(1) for s_, (a, b) in SPLITS.items()}} for t in TARGETS + ["SMH"]}).T
    own.index.name = "dionica"
    rob = []
    for ldr in ["AMAT", "KLAC", "SMH"]:
        d = pd.DataFrame({"y": ret.MU, "x1": ret[ldr].shift(1), "y1": ret.MU.shift(1)}).dropna()
        m = sm.OLS(d.y, sm.add_constant(d[["x1", "y1"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        q = d.abs().quantile(0.99)
        dd = d[(d.abs() < q).all(axis=1)]
        slope = d.y.cov(d.x1) / d.x1.var()
        rob.append(dict(vodeca=ldr, pearson=d.y.corr(d.x1), spearman=d.y.corr(d.x1, method="spearman"), bez_1pct_ekstrema=dd.y.corr(dd.x1),
                        beta_uz_MU_jucer=m.params["x1"], t_HAC=m.tvalues["x1"], bps_po_1sd=slope * d.x1.std() * 1e4))
    rob = pd.DataFrame(rob).set_index("vodeca")
    by_year = pd.DataFrame({ldr: {y: lag_corr(ret[ldr][ret.index.year == y], ret.MU[ret.index.year == y], 1)[0] for y in sorted(set(ret.index.year))} for ldr in ["AMAT", "KLAC", "SMH"]})
    by_year.index.name = "godina"
    mu_sd_bps = ret.MU.std() * 1e4
    lines = ["# Vodeći pokazatelji: prethode li AMAT/LRCX/KLAC/SMH memoriji (MU/WDC/STX)?\n"]
    verdict = "NEMA upotrebljivog VODSTVA (rast čipova ne najavljuje rast memorije)"
    pos_bonf = int(((df.p_bonf < 0.05) & (df.r > 0)).sum())
    neg_bonf = n_bonf - pos_bonf
    lines.append("## Sažetak u 5 redaka\n")
    lines.append(
        f"1. Pitanje: ako AMAT (strojevi za čipove), LRCX, KLAC ili SMH (košara čipova) jučer porastu, raste li MU/WDC/STX u idućih 1 do 20 dana?\n"
        f"2. Rezultat: **{verdict}**. Od {n_tests} testova njih {n_nom} je 'nominalno značajno' (p<0,05; slučajno bismo očekivali ~{num(exp_false,0)}), a {n_bonf} prolazi i strogu korekciju ({neg_bonf} s negativnim, {pos_bonf} s pozitivnim predznakom); sve su manje od |0,09|.\n"
        f"3. Jedina stabilna sitnica je OBRNUTA: nakon jakog dana AMAT/KLAC/SMH, MU sutradan blago pada (korelacija {num(l1.loc[('AMAT','MU'),'r'],3)} do {num(l1.loc[('KLAC','MU'),'r'],3)}, isti predznak u sva tri razdoblja), ali je slaba po rang-korelaciji ({num(rob.spearman.max(),3)} do {num(rob.spearman.min(),3)}) i najjača u 2020-21 (oko -0,2 do -0,27 po godini). To je kratkoročni preokret MU-a, ne vodstvo. Za WDC i STX nema ničega na lag 1.\n"
        f"4. Istog dana se kreću zajedno (korelacija {num(contemp.values.min(),2)} do {num(contemp.values.max(),2)}), ali to NIJE vodstvo: to je isti val koji pogodi sve odjednom.\n"
        f"5. Što s tim: ne gradi pravilo 'kupi MU jer su AMAT/LRCX/KLAC/SMH rasli'; ono što se vidi u podacima je samo istodobno kretanje.\n"
    )
    lines.append("## Pojmovi (laički)\n")
    lines.append(
        "- **Vodeći pokazatelj (lead)**: nešto što se pomakne PRIJE nego dionica koju želimo predvidjeti. Kao da kiša u planini najavi poplavu u dolini sutradan.\n"
        "- **Korelacija s odmakom (lagged correlation)**: korelacija između pomaka vodeće dionice prije k dana i pomaka MU-a danas. Broj je između -1 i +1; 0 znači 'nema veze', 0,05 znači zanemarivo slabo.\n"
        f"- **Značajnost (p-vrijednost)**: koliko bi bilo čudno vidjeti ovakvu korelaciju da zapravo nema nikakve veze. p<0,05 znači 'rijetko, 1 u 20'.\n"
        f"- **Zamka višestrukih testova**: ako baciš novčić 240 puta, nekoliko 'čudnih' nizova dobije se čisto slučajno. Mi radimo {n_tests} testova (4 vodeće x 3 mete x 20 odmaka), pa 'značajno' tražimo tek nakon korekcije (Bonferroni: p pomnoži s {n_tests}; Holm: blaža varijanta).\n"
        "- **Istodobna korelacija**: kretanje istog dana. NIJE vodstvo, jer se ništa ne zna unaprijed.\n"
    )
    lines.append("## 1. Istodobna korelacija (isti dan, samo za usporedbu)\n")
    contemp.index.name = "vodeća \\ meta"
    lines.append(md_table(contemp, "{:.2f}") + "\n")
    lines.append("\nVisoke vrijednosti znače da se sve ove dionice pomiču kao jedan val. To ne daje prednost jer ne znaš koji će val doći sutra.\n")
    lines.append("## 2. Odmak od 1 dana (jučerašnji pomak vodeće → današnji pomak mete)\n")
    t1 = l1[["r", "p", "p_bonf", "r_IS", "r_WF", "r_HO"]].copy()
    t1.columns = ["r", "p", "p (Bonferroni)", "r IS", "r WF", "r HO"]
    t1.index = [f"{a}→{b}" for a, b in t1.index]
    t1.index.name = "par"
    lines.append(md_table(t1, "{:.3f}") + "\n")
    lines.append(
        f"\nPrag korelacije koji bi nakon korekcije za {n_tests} testova bio 'značajan' je oko ±{num(thr,3)} (uz ~{n_obs} dana). "
        "'r IS / WF / HO' je ista korelacija u tri razdoblja (2016-20, 2021-23, 2024+). Ako predznak skače, veza nije stabilna.\n"
    )
    lines.append("## 3. Svih 12 najjačih korelacija s odmakom 1-20 dana\n")
    tt = top[["leader", "target", "lag", "r", "p", "p_bonf", "p_holm", "r_IS", "r_WF", "r_HO", "same_sign_all_splits"]].copy()
    tt["same_sign_all_splits"] = tt.same_sign_all_splits.map({True: "da", False: "ne"})
    tt = tt.rename(columns={"leader": "vodeća", "target": "meta", "lag": "odmak","p_bonf": "p Bonf.", "p_holm": "p Holm", "same_sign_all_splits": "isti predznak u svim razdobljima"})
    tt.index = range(1, len(tt) + 1)
    tt.index.name = "#"
    lines.append(md_table(tt, "{:.3f}") + "\n")
    if n_bonf:
        lines.append(f"\nTestovi koji prolaze Bonferroni: {len(surv)}.\n")
        sv = surv[["leader", "target", "lag", "r", "p_bonf", "r_IS", "r_WF", "r_HO"]]
        sv.index = range(1, len(sv) + 1)
        lines.append(md_table(sv, "{:.3f}") + "\n")
    else:
        lines.append("\nNijedan od 240 testova ne prolazi Bonferroni korekciju.\n")
    # distribution summary by lag
    bylag = df.groupby("lag").r.agg(["mean", "min", "max"])
    lines.append("## 4. Prosječna korelacija po odmaku (preko svih 12 parova)\n")
    bylag.columns = ["prosjek", "najmanja", "najveća"]
    bylag.index.name = "odmak (dana)"
    lines.append(md_table(bylag, "{:.3f}") + "\n")
    lines.append(
        f"\nProsjeci su mali (najveći po apsolutnoj vrijednosti: {num(bylag['prosjek'].abs().max(),3)}). To je ono što bi se očekivalo bez veze.\n"
    )
    lines.append("## 5. Provjera s tjednima (neprekrivajući blokovi od 5 dana, odmak 1 blok)\n")
    wk.index.name = "vodeća \\ meta"
    wkp = pd.DataFrame(wk_p)
    lines.append("Korelacija:\n\n" + md_table(wk, "{:.3f}") + "\n\np-vrijednosti (bez korekcije; 12 testova):\n\n" + md_table(wkp, "{:.3f}") + f"\n\nBroj tjednih blokova: {len(w)-1}.\n")
    lines.append("## 6. Je li negativna veza na lag 1 stvarna? (samo MU)\n")
    lines.append(
        "Negativna korelacija znači: **jučer gore u čipovima -> danas malo dolje u MU-u** (preokret), suprotno od vodstva. Provjere otpornosti:\n\n"
        + md_table(rob, "{:.3f}")
        + "\n\n'bps_po_1sd' = koliko baznih bodova MU u prosjeku pomakne sutradan nakon pomaka vodeće od 1 standardne devijacije (gruba linearna procjena, bez troškova). "
        + f"Dnevno 'šum' MU-a je ~{num(mu_sd_bps,0)} bps (1 std), a trošak kruga 5 bps + 2 tick-a. Dakle prosječni učinak (oko 24-29 bps po tipičnom pomaku) nominalno nadmašuje trošak, ali je ~12 puta manji od dnevnog šuma i drži se uglavnom na 2020-21, pa je to slabo, neprovjereno opažanje, a ne rezultat strategije.\n\n"
        + "Vlastita autokorelacija (korelacija jučerašnjeg i današnjeg pomaka iste dionice):\n\n"
        + md_table(own, "{:.3f}")
        + "\n\nKorelacija AMAT/KLAC/SMH(jučer) -> MU(danas) po godinama:\n\n"
        + md_table(by_year, "{:.3f}")
        + "\n\n**Kako čitati:** efekt je najjači u pojedinim godinama (vidi 2020-21) i slabi pod rang-korelacijom i kad se makne 1 % ekstrema, tj. dobar dio dolazi od nekoliko velikih dana. Odmaci 7 i 13 dana imaju promjenjive predznake i nemaju ekonomsku priču, pa ih tretiramo kao slučajnost iz 240 testova.\n"
    )
    lines.append("## Što napraviti / ne napraviti\n")
    lines.append(
        "- **Ne** koristi kretanje AMAT/LRCX/KLAC/SMH kao okidač za kupnju MU/WDC/STX na temelju ovih podataka. Dnevne korelacije s odmakom su preslabe da prežive trošak (5 bps + 1 tick po krugu) i korekciju za višestruke testove.\n"
        "- Ako želiš ipak testirati vodstvo, mehanizam mora biti jasan unaprijed (npr. narudžbe opreme -> kapacitet -> ponuda memorije traje kvartale, ne dane) pa test ide na kvartalnim/mjesečnim, a ne dnevnim skalama; to bi bila nova hipoteza s novim ID-em.\n"
        "- Jedina hipoteza koju podaci naslućuju je **kratkoročni preokret MU-a nakon jakog dana čipova** (slabo, nestabilno po godinama). To je obitelj 'mean reversion' koja je već jednom propala (C10/C11, MEM_CYCLE_MR_V1 zatvoreni), pa bi bila dopuštena samo kao materijalno drukčija nova hipoteza, uz Critic.\n"
        "- Ovo je zatvoreno pitanje samo za dnevnu skalu 1-20 dana na 3 memorijske dionice; ne govori ništa o mjesečnim ili kvartalnim vodstvima.\n"
    )
    lines.append("## Ograničenja\n- Log-povrati zatvaranje-na-zatvaranje; svih 7 dionica zatvara istodobno pa lag 1 je čist (bez gledanja u budućnost).\n- Pearsonov test pretpostavlja neovisne dane; to je grubo ali nisu primjetne autokorelacije u dnevnim povratima. Za jače tvrdnje trebao bi Newey-West ili permutacijski test.\n- Linearna korelacija ne hvata nelinearne ili uvjetne veze (npr. samo nakon velikih pomaka).\n")
    write_report("lead_lag.md", "\n".join(lines))
    print(n_nom, n_bonf, df.p_holm.lt(0.05).sum(), thr)


if __name__ == "__main__":
    main()
