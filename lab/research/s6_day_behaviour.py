"""Study 6: intraday behaviour from hourly SIP bars (regular session) for MU/WDC/STX, with costs in mind."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from lab.research.common import (
    COST_BPS_RT,
    DATA,
    SPLITS,
    daily,
    md_table,
    num,
    split_of,
    write_report,
)

TICKERS = ["MU", "WDC", "STX"]
TICK = 0.01  # USD, one tick per side


def load_all(t: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (regular bars with ET hour, per-day frame: gap, open->10:00, 10:00->close, close-to-close)."""
    h = pd.read_csv(DATA / "hourly" / f"{t}_1h_clean.csv")
    h["ts"] = pd.to_datetime(h.ts, utc=True)
    h["et"] = h.ts.dt.tz_convert("America/New_York")
    h["hour"] = h.et.dt.hour
    h["date"] = pd.to_datetime(h.et.dt.date)
    reg = h[(h.session == "regular") & h.volume_ok].copy()
    reg["ret_bp"] = (reg.close / reg.open - 1) * 1e4
    om = h[h.session == "open_mixed"].set_index("date")
    d = daily(t)
    day = pd.DataFrame(index=d.index)
    day["gap"] = (d.open / d.close.shift(1) - 1) * 1e4
    day["first30"] = (om.close.reindex(day.index) / d.open - 1) * 1e4  # daily open -> 10:00 ET price
    last_close = reg.groupby("date").close.last()
    day["rest"] = (last_close.reindex(day.index) / om.close.reindex(day.index) - 1) * 1e4  # 10:00 -> last regular bar close
    day["intraday"] = (d.close / d.open - 1) * 1e4
    day["cc"] = (d.close / d.close.shift(1) - 1) * 1e4
    day["last_hour"] = reg[reg.hour == 15].set_index("date").ret_bp.reindex(day.index)
    day["px"] = d.close
    day["split"] = day.index.map(split_of)
    day["last_close_vs_daily_close_bp"] = (last_close.reindex(day.index) / d.close - 1) * 1e4
    return reg, day.dropna(subset=["gap"])


def hour_table(reg: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for hr, g in reg.groupby("hour"):
        x = g.ret_bp
        tt = stats.ttest_1samp(x, 0)
        rows[f"{hr}:00-{hr+1}:00"] = dict(n=len(x), prosjek_bp=x.mean(), medijan_bp=x.median(), std_bp=x.std(), t=tt.statistic, pozitivnih_pct=(x > 0).mean() * 100, prosj_abs_bp=x.abs().mean())
    out = pd.DataFrame(rows).T
    out["udio_varijance_pct"] = (out.std_bp**2 * out.n) / ((out.std_bp**2 * out.n).sum()) * 100
    return out


def main() -> None:
    L = ["# Ponašanje unutar dana (satni podaci, redovna sesija)\n"]
    data = {t: load_all(t) for t in TICKERS}
    ht = {t: hour_table(data[t][0]) for t in TICKERS}
    # costs
    cost_rows = {}
    for t in TICKERS:
        reg, day = data[t]
        px = reg.close
        cost = COST_BPS_RT + 2 * TICK / px * 1e4
        reg = reg.assign(cost_bp=cost)
        data[t] = (reg, day)
        yr = reg.groupby(reg.et.dt.year).cost_bp.mean()
        cost_rows[t] = yr
    cost_yr = pd.DataFrame(cost_rows)
    cost_yr.index.name = "godina"
    # survive table: share of bars where |ret| > cost, per hour
    surv = {}
    for t in TICKERS:
        reg = data[t][0]
        surv[t] = (reg.assign(s=reg.ret_bp.abs() > reg.cost_bp)).groupby("hour").s.mean() * 100
    surv = pd.DataFrame(surv)
    surv.index = [f"{h}:00" for h in surv.index]
    surv.index.name = "sat (ET)"
    # decomposition
    dec = {}
    for t in TICKERS:
        day = data[t][1]
        dec[t] = dict(
            n_dana=len(day),
            gap_prosjek=day.gap.mean(), gap_t=stats.ttest_1samp(day.gap.dropna(), 0).statistic,
            prvih30_prosjek=day.first30.mean(), prvih30_t=stats.ttest_1samp(day.first30.dropna(), 0).statistic,
            ostatak_prosjek=day.rest.mean(), ostatak_t=stats.ttest_1samp(day.rest.dropna(), 0).statistic,
            zadnji_sat_prosjek=day.last_hour.mean(), zadnji_sat_t=stats.ttest_1samp(day.last_hour.dropna(), 0).statistic,
            cc_prosjek=day.cc.mean(),
            std_gap=day.gap.std(), std_intraday=day.intraday.std(),
            abs_gap=day.gap.abs().mean(), abs_prvih30=day.first30.abs().mean(), abs_ostatak=day.rest.abs().mean(),
        )
    dec = pd.DataFrame(dec).T
    recon = {t: data[t][1].last_close_vs_daily_close_bp.abs().median() for t in TICKERS}
    recon_p95 = {t: data[t][1].last_close_vs_daily_close_bp.abs().quantile(0.95) for t in TICKERS}
    # first vs last hour relationships
    rel_rows = []
    for t in TICKERS:
        day = data[t][1].dropna(subset=["first30", "last_hour", "rest"])
        for lab, a, b in [("prvih 30 min -> zadnji sat", "first30", "last_hour"), ("gap -> ostatak dana (10:00-zatvaranje)", "gap", "rest"), ("gap -> otvaranje-zatvaranje", "gap", "intraday"), ("prvih 30 min -> ostatak dana", "first30", "rest")]:
            x = data[t][1].dropna(subset=[a, b])
            r, p = stats.pearsonr(x[a], x[b])
            sp = {s_: x[x.split == s_][a].corr(x[x.split == s_][b]) for s_ in SPLITS}
            slope = x[b].cov(x[a]) / x[a].var()
            rel_rows.append(dict(dionica=t, veza=lab, n=len(x), r=r, p=p, **{f"r {s_}": v for s_, v in sp.items()}, bps_po_1sd=slope * x[a].std(), cost_bp=float(data[t][0].cost_bp.iloc[-2000:].mean())))
    rel = pd.DataFrame(rel_rows)
    rel["p_bonf"] = np.minimum(rel.p * len(rel), 1)
    # gap conditional
    gc_rows = []
    for t in TICKERS:
        day = data[t][1].dropna(subset=["gap", "rest", "intraday"])
        for lab, m in [("gap gore >= +1 %", day.gap >= 100), ("gap dolje <= -1 %", day.gap <= -100), ("mali gap (manji od 1 %)", day.gap.abs() < 100)]:
            x = day[m]
            filled = np.nan
            if lab != "mali gap (manji od 1 %)":
                # share of days where the day's close moved against the gap (gap partly faded)
                filled = (np.sign(x.intraday) == -np.sign(x.gap)).mean() * 100
            gc_rows.append(dict(dionica=t, skupina=lab, n=len(x), prosjek_gap=x.gap.mean(), prosjek_otv_zatv=x.intraday.mean(), medijan_otv_zatv=x.intraday.median(), t=stats.ttest_1samp(x.intraday, 0).statistic if len(x) > 2 else np.nan, dan_protiv_gapa_pct=filled))
    gc = pd.DataFrame(gc_rows)
    # first-half-hour sign -> last hour by split
    fl_rows = []
    for t in TICKERS:
        day = data[t][1].dropna(subset=["first30", "last_hour"])
        for s_ in SPLITS:
            x = day[day.split == s_]
            up = x[x.first30 > 0].last_hour
            dn = x[x.first30 < 0].last_hour
            fl_rows.append(dict(dionica=t, razdoblje=s_, n_gore=len(up), zadnji_sat_nakon_gore=up.mean(), n_dolje=len(dn), zadnji_sat_nakon_dolje=dn.mean()))
    fl = pd.DataFrame(fl_rows)
    # numbers for summary
    mx = {t: ht[t].prosjek_bp.abs().max() for t in TICKERS}
    cost_now = {t: cost_yr[t].iloc[-1] for t in TICKERS}
    cost_avg = {t: cost_yr[t].mean() for t in TICKERS}
    n_sig = int((rel.p < 0.05).sum())
    share = {t: dec.loc[t, "gap_prosjek"] / dec.loc[t, "cc_prosjek"] * 100 for t in TICKERS}
    stab = rel[(rel.p_bonf < 0.05) & (np.sign(rel["r IS"]) == np.sign(rel["r WF"])) & (np.sign(rel["r WF"]) == np.sign(rel["r HO"]))]
    stab_txt = "; ".join(f"{r.dionica}: {r.veza} (r={num(r.r,3)}, {num(r.bps_po_1sd,1)} bps po 1 std signala, uz trošak ~{num(r.cost_bp,0)} bps)" for r in stab.itertuples()) or "nijedna"
    first_hr = {t: ht[t].loc["10:00-11:00"] for t in TICKERS}
    std_ratio = {t: ht[t].std_bp.iloc[0] / ht[t].std_bp.iloc[-1] for t in TICKERS}
    L.append("## Sažetak u 5 redaka\n")
    L.append(
        f"1. Prosječan povrat po satu je sitan prema šumu: najveći prosjek po satu je {num(mx['MU'],1)} bps (MU), {num(mx['WDC'],1)} (WDC), {num(mx['STX'],1)} (STX), dok je trošak jednog kruga (5 bps + 2 ticka) u povijesnom prosjeku {num(cost_avg['MU'],1)}, {num(cost_avg['WDC'],1)}, {num(cost_avg['STX'],1)} bps (u 2026. {num(cost_now['MU'],1)}, {num(cost_now['WDC'],1)}, {num(cost_now['STX'],1)}; 1 bps = 0,01 %).\n"
        f"2. Kolebanje nije jednako po satima: prvi sat (10-11) ima standardnu devijaciju {num(first_hr['MU'].std_bp,0)} bps za MU, naspram {num(ht['MU'].std_bp.iloc[-1],0)} bps u zadnjem satu ({num(std_ratio['MU'],1)}x). Veći pomaci znače da je trošak relativno manji u odnosu na pomak, ali smjer je jednako neodređen: nijedan sat nema prosjek koji bi pokrio trošak.\n"
        f"3. Gdje nastaje prosječni dnevni rast: noć/gap čini {num(share['MU'],0)} % prosječnog dnevnog povrata MU-a, {num(share['WDC'],0)} % WDC-a i {num(share['STX'],0)} % STX-a (STX raste više unutar dana, ali uz t={num(dec.loc['STX','ostatak_t'],1)}). To je opis gdje je dionica rasla, ne prednost nad 'kupi i drži', jer je dio istog rasta.\n"
        f"4. Od {len(rel)} testova veza (prvih 30 min -> zadnji sat, gap -> ostatak, itd.) nominalno značajnih je {n_sig}, a nakon korekcije {int((rel.p_bonf<0.05).sum())}. Jedina s istim predznakom u sva tri razdoblja i prolazom korekcije: {stab_txt}. Učinak je nominalno iznad troška, ali je mnogo puta manji od šuma jednog dana (std prvih 30 min je oko 100+ bps) i izdvojen je iz 12 pogledanih testova, pa je to hipoteza, ne dokaz (tablica 5).\n"
        f"5. Što s tim: day trade u ovim podacima ne pokazuje jednostavan satni obrazac koji preživljava trošak; jedino što treba iskoristiti je znanje GDJE je kolebanje (otvaranje) i gdje je trošak relativno malen/velik, ne smjer.\n"
    )
    L.append("## Pojmovi (laički)\n")
    L.append(
        "- **Satna svijeća (bar)**: sažetak jednog sata trgovanja: otvaranje, najviša, najniža, zatvaranje. Sat '10:00-11:00' je sat koji počinje u 10:00 po New Yorku (16:00 u Zagrebu).\n"
        "- **Redovna sesija**: trgovanje 9:30-16:00 po New Yorku. U satnim podacima prvi sat 9:00-10:00 miješa pretržišno trgovanje i prvih 30 minuta (oznaka 'open_mixed'); zato u tablici po satima počinjemo od 10:00, a prvih 30 minuta računamo posebno iz dnevnog otvaranja.\n"
        "- **Gap**: preskok između jučerašnjeg zatvaranja i današnjeg otvaranja. Kao da je trgovina preko noći promijenila cijenu.\n"
        "- **Bps (bazni bod)**: 0,01 %. 100 bps = 1 %.\n"
        "- **Trošak kruga**: kupiš i prodaš. Računamo 5 bps + 1 tick (najmanji korak cijene, 0,01 USD) po strani, tj. 2 ticka po krugu. Na jeftinoj dionici tick čini više bps, na skupoj manje.\n"
        "- **Varijanca / std**: mjera 'koliko skače'. Veći std = više šuma. Kao nemirno more naspram bonace.\n"
        "- **Preživjeti trošak**: pomak mora biti veći od troška da bi se uopće zaradilo; pomak od 5 bps uz trošak od 7 bps je gubitak.\n"
    )
    L.append("## 1. Prosječan povrat po satu (redovna sesija; bps)\n")
    for t in TICKERS:
        h = ht[t].copy()
        h["n"] = h.n.astype(int)
        h.columns = ["n", "prosjek bps", "medijan bps", "std bps", "t-statistika", "% pozitivnih", "prosj. apsolutni pomak bps", "udio varijance %"]
        h.index.name = t
        L.append(f"\n**{t}** ({len(data[t][0]):,} satnih barova)\n\n" + md_table(h, "{:.2f}") + "\n")
    L.append(
        "\n**Što to znači:** 't-statistika' veća od ~2 (ili manja od -2) znači da prosjek vjerojatno nije slučajan; ovdje je 18 testova, pa traži oko 3. 'udio varijance' pokazuje koji sat nosi koliki dio ukupnog šuma. Provjera podataka: zadnji redovni sat završava približno na dnevnom zatvaranju (medijan odstupanja "
        + ", ".join(f"{t} {num(recon[t],1)}" for t in TICKERS)
        + " bps; 95. percentil " + ", ".join(f"{t} {num(recon_p95[t],0)}" for t in TICKERS) + " bps).\n"
    )
    L.append("## 2. Razlaganje dana: noć, prvih 30 minuta, ostatak, zadnji sat (prosjek bps, t-statistika)\n")
    d2 = dec.copy()
    d2["n_dana"] = d2.n_dana.astype(int)
    d2 = d2[["n_dana", "gap_prosjek", "gap_t", "prvih30_prosjek", "prvih30_t", "ostatak_prosjek", "ostatak_t", "zadnji_sat_prosjek", "zadnji_sat_t", "cc_prosjek", "std_gap", "std_intraday"]]
    d2.columns = ["n dana", "noć/gap prosjek", "t", "otvaranje->10:00 prosjek", "t", "10:00->zatvaranje prosjek", "t", "zadnji sat prosjek", "t", "ukupno zatvaranje->zatvaranje prosjek", "std noći bps", "std otvaranje->zatvaranje bps"]
    d2.index.name = "dionica"
    L.append(md_table(d2, "{:.2f}") + "\n")
    L.append(
        "\n**Što to znači:** 'noć/gap' je promjena od jučerašnjeg zatvaranja do današnjeg otvaranja; 'ostatak' je od 10:00 do zatvaranja. Zbroj ova tri dijela približno daje cijeli dan. "
        "Koliko od prosječnog dnevnog rasta dolazi iz noći? To je pitanje o tome gdje se 'zarada' ostvaruje: ako dolazi iz noći, a ne iz sesije, onda je day trade (ulaz i izlaz isti dan) propušta. "
        "Dodatno apsolutni prosječni pomaci (bps): " + "; ".join(f"{t}: noć {num(dec.loc[t,'abs_gap'],0)}, prvih 30 min {num(dec.loc[t,'abs_prvih30'],0)}, ostatak dana {num(dec.loc[t,'abs_ostatak'],0)}" for t in TICKERS) + ".\n"
    )
    L.append("## 3. Trošak: koliko bps stoji jedan krug (5 bps + 2 ticka) po godini\n")
    L.append(md_table(cost_yr, "{:.1f}") + "\n")
    L.append(
        "\nTick od 0,01 USD na dionici od 15 USD je ~7 bps po strani, na dionici od 1000 USD samo 0,1 bps; zato je trošak veći u prvim godinama (niske cijene), a danas je blizu osnovnih 5 bps. "
        "Nije uračunat 'slippage' (proklizavanje, tj. gore od predviđene cijene izvršenja) niti spread širi od 1 ticka; stvarni trošak je zato veći.\n"
    )
    L.append("\n**Postotak satnih barova u kojima je pomak (po apsolutnoj vrijednosti) veći od troška kruga:**\n\n" + md_table(surv, "{:.0f}") + "\n")
    L.append(
        "\n**Što to znači:** ako je pomak jednog sata na pola slučajeva veći od troška, to ne znači zaradu: pola tih pomaka je u pogrešnom smjeru. Mora postojati prosjek u jednom smjeru veći od troška, a prosjeci iz tablice 1 su mnogo manji od troška.\n"
    )
    L.append("## 4. Gap-otvaranje: što se događa tog dana nakon gapa\n")
    gc2 = gc.copy()
    gc2["n"] = gc2.n.astype(int)
    gc2.columns = ["dionica", "skupina", "n", "prosj. gap bps", "prosj. otvaranje->zatvaranje bps", "medijan bps", "t", "% dana u smjeru protiv gapa"]
    gc2 = gc2.set_index("dionica")
    L.append(md_table(gc2, "{:.2f}") + "\n")
    L.append(
        "\n**Što to znači:** 'protiv gapa' = cijena se tijekom dana vraćala prema jučerašnjem zatvaranju (gap se djelomično popunjava). Brojka oko 50 % znači da nema ni nastavka ni vraćanja. "
        "Kategorije gapa (>= +1 %, <= -1 %) postavljene su unaprijed, ne prema ishodu.\n"
    )
    L.append("## 5. Prvi vs zadnji sat, gap vs ostatak: korelacije\n")
    rel2 = rel.set_index("dionica")[["veza", "n", "r", "p", "p_bonf", "r IS", "r WF", "r HO", "bps_po_1sd", "cost_bp"]]
    rel2 = rel2.rename(columns={"bps_po_1sd": "učinak bps po 1 std signala", "cost_bp": "trošak kruga bps (zadnjih ~2000 barova)"})
    rel2["n"] = rel2.n.astype(int)
    L.append(md_table(rel2, "{:.3f}") + "\n")
    L.append(
        f"\n**Što to znači:** korelacija blizu 0 znači 'ne predviđa'. {len(rel)} testova, prag značajnosti nakon korekcije je p<0,05/{len(rel)}. 'r IS/WF/HO' pokazuje isto u tri razdoblja: isti predznak kroz sva tri je nužan (ne dovoljan) uvjet da bi vrijedilo pratiti.\n"
    )
    L.append("## 6. Zadnji sat nakon smjera prvih 30 minuta (prosjek bps)\n")
    fl2 = fl.set_index("dionica")
    for c in ["n_gore", "n_dolje"]:
        fl2[c] = fl2[c].astype(int)
    fl2.columns = ["razdoblje", "n (prvih 30 gore)", "zadnji sat nakon gore", "n (dolje)", "zadnji sat nakon dolje"]
    L.append(md_table(fl2, "{:.2f}") + "\n")
    L.append("\n## Što napraviti / ne napraviti\n")
    L.append(
        "- **Ne** pretpostavljaj da je 'zadnji sat bullish' ili 'prvi sat bearish': prosjeci iz tablice 1 su manji od troška; prije bilo kakvog day tradea treba formalni test s troškom i Criticom.\n"
        "- Jedina veza koja se drži kroz razdoblja je blago PREOKRETANJE prvih 30 minuta kod WDC/STX (smjer prvih 30 min djelomično se poništava do zatvaranja). To je hipoteza za test (mehanizam: otvaranje u kojem likvidnost 'preskoči', pa se vraća), ne rezultat; učinak je u tablici 5 usporediv s troškom.\n"
        "- Day trade ima samo smisla ako očekivani pomak po trgovini prelazi trošak (5 bps + 2 ticka + proklizavanje) uz bar malo marže; na ovim podacima prosječni satni pomak u smjeru je daleko ispod toga.\n"
        "- Koristi tablicu 'udio varijance' da planiraš veličinu pozicije: početak dana je najnemirniji.\n"
        "- Za Codex: svaki intraday test mora koristiti `session == regular` i `volume_ok`, ulaz na otvaranju sljedećeg sata (ne na zatvaranju sata koji generira signal), trošak po strani, i izvještavati broj trgovina po razdoblju.\n"
        "\n## Ograničenja\n- Satne svijeće ne vide što se događa unutar sata (stop-lossovi, prekidi); 5-minutni podaci će biti u `data/intraday/` kad ih traka A povuče.\n- Prvih 30 minuta računamo iz dnevnog otvaranja i zatvaranja satne svijeće 9:00-10:00, koja uključuje i pretržišni dio, što je približno ali ne savršeno.\n- Poluskraćeni dani (dan nakon Thanksgivinga, Badnjak) nisu posebno označeni; imaju manje od 6 satnih barova.\n- Satni podaci iz 2016-2019 imaju manje trgovina po satu pa je spread vjerojatno širi nego što pretpostavljamo.\n"
    )
    write_report("day_behaviour.md", "\n".join(L))
    print(n_sig, recon, recon_p95)


if __name__ == "__main__":
    main()
