"""Study 1: memory cycle in prices (yearly returns, drawdown episodes, phases, return concentration)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab.research.common import daily, md_table, num, pct, split_of, write_report

TICKERS = ["MU", "WDC", "STX", "SMH"]
MIN_DD = 0.25  # episodes deeper than 25 % peak-to-trough
PHASES = {  # fixed in advance from the brief (named market phases), not tuned on outcomes
    "Pad 2018 (cijela 2018.)": ("2018-01-01", "2018-12-31"),
    "Covid 2020 (19.2.-23.3.)": ("2020-02-19", "2020-03-23"),
    "Pad 2022 (cijela 2022.)": ("2022-01-01", "2022-12-31"),
    "Boom 2025-26 (1.1.2025.-danas)": ("2025-01-01", "2026-10-05"),
}


def yearly_returns() -> pd.DataFrame:
    out = {}
    for t in TICKERS:
        c = daily(t)["close"]
        ye = c.groupby(c.index.year).last()
        prev = ye.shift(1)
        prev.iloc[0] = c.iloc[0]  # first year starts from first available close
        out[t] = (ye / prev - 1) * 100
    return pd.DataFrame(out)


def drawdown_episodes(c: pd.Series, min_dd: float) -> pd.DataFrame:
    peak = c.cummax()
    dd = c / peak - 1
    rows = []
    in_ep = False
    for d in c.index:
        if not in_ep and dd[d] < 0:
            in_ep = True
            peak_date = c[:d].idxmax()
        if in_ep and dd[d] == 0:  # recovered to prior peak
            seg = dd[peak_date:d]
            tr = seg.idxmin()
            rows.append((peak_date, tr, seg.min(), d))
            in_ep = False
    if in_ep:
        seg = dd[peak_date:]
        rows.append((peak_date, seg.idxmin(), seg.min(), pd.NaT))
    ep = pd.DataFrame(rows, columns=["peak", "trough", "depth", "recovered"])
    ep = ep[ep.depth <= -min_dd].copy()
    bd = lambda a, b: len(c[a:b]) - 1
    ep["days_down"] = [bd(r.peak, r.trough) for r in ep.itertuples()]
    ep["days_recover"] = [bd(r.trough, r.recovered) if pd.notna(r.recovered) else np.nan for r in ep.itertuples()]
    return ep.reset_index(drop=True)


def phase_stats() -> pd.DataFrame:
    rows = []
    for name, (a, b) in PHASES.items():
        for t in TICKERS:
            c = daily(t)["close"]
            prev = c[:a].iloc[:-1]
            base = prev.iloc[-1] if len(prev) else c[a:b].iloc[0]
            seg = c[a:b]
            r = seg.pct_change().dropna()
            mdd = (seg / np.maximum.accumulate(np.r_[base, seg.values])[1:] - 1).min()
            rows.append((name, t, (seg.iloc[-1] / base - 1) * 100, mdd * 100, r.std() * np.sqrt(252) * 100, (r > 0).mean() * 100))
    return pd.DataFrame(rows, columns=["faza", "dionica", "povrat_%", "najveci_pad_%", "kolebanje_god_%", "dana_u_plusu_%"])


def concentration(t: str) -> dict:
    c = daily(t)["close"]
    r = c.pct_change().dropna()
    lr = np.log1p(r)
    tot = lr.sum()
    res = {"ticker": t, "n_days": len(r), "total_x": float(np.exp(tot))}
    for k in (10, 20):
        best = lr.nlargest(k)
        res[f"best{k}_share"] = float(best.sum() / tot * 100)
        res[f"x_without_best{k}"] = float(np.exp(lr.drop(best.index).sum()))
        worst = lr.nsmallest(k)
        res[f"x_without_worst{k}"] = float(np.exp(lr.drop(worst.index).sum()))
        res[f"best{k}_pct_of_days"] = k / len(r) * 100
    best20 = lr.nlargest(20)
    res["best20_by_year"] = best20.groupby(best20.index.year).size().to_dict()
    res["best20_by_split"] = best20.index.map(split_of).value_counts().to_dict()
    res["best_days"] = [(d.strftime("%Y-%m-%d"), float(np.expm1(v) * 100)) for d, v in lr.nlargest(10).items()]
    return res


def main() -> None:
    yr = yearly_returns()
    yr.index.name = "godina"
    out = ["# Ciklus memorije u cijenama (MU, WDC, STX, SMH)\n"]
    cons = {t: concentration(t) for t in TICKERS}
    mu = cons["MU"]
    ph = phase_stats().set_index(["faza", "dionica"])
    out.append("## Sažetak u 5 redaka\n")
    out.append(
        f"1. Memorijske dionice rastu u valovima, ne ravnomjerno: MU je u cijelom razdoblju narastao ×{num(mu['total_x'],1)}, ali kroz nekoliko dubokih padova.\n"
        f"2. Svaka od tri memorijske dionice (MU, WDC, STX) je barem jednom izgubila više od polovice vrijednosti od vrha; SMH (košara čipova) je padao manje.\n"
        f"3. Najboljih 10 dana (od {mu['n_days']}) daje MU-u {num(mu['best10_share'],0)} % cjelokupnog (logaritamskog) povrata; bez njih bi ×{num(mu['total_x'],1)} bio samo ×{num(mu['x_without_best10'],1)}.\n"
        f"4. Faze se razlikuju: 2018. i 2022. su dugi padovi kroz mjesece (MU {pct(yr.loc[2018,'MU'],0)} i {pct(yr.loc[2022,'MU'],0)}), covid je pad od ~mjesec dana (MU {pct(ph.loc[('Covid 2020 (19.2.-23.3.)','MU'),'povrat_%'],0)}), a boom od 2025. je MU-u donio {pct(ph.loc[('Boom 2025-26 (1.1.2025.-danas)','MU'),'povrat_%'],0)} uz ipak dva pada od ~30-40 % usred booma.\n"
        f"5. Što s tim: WDC bez svojih 20 najboljih dana ima ×{num(cons['WDC']['x_without_best20'],2)} (tj. praktički nula), a MU ×{num(mu['x_without_best20'],1)} umjesto ×{num(mu['total_x'],1)}: rezultat visi na nekoliko dana, i ravnomjernu zaradu ne treba očekivati. Ovo je opis prošlosti, ne signal.\n"
    )
    out.append("## Pojmovi (laički)\n")
    out.append(
        "- **Godišnji povrat**: za koliko je posto dionica porasla/pala od zadnjeg zatvaranja prošle godine do zadnjeg zatvaranja te godine. Kao da gledaš stanje štednje svakog 31.12. (2016. se mjeri od prvog dana u podacima, 2026. je tek do 5.10.2026.).\n"
        "- **Pad od vrha (drawdown)**: koliko je dionica pala od svog najvišeg dotadašnjeg zatvaranja. Kao da si na planini popeo do vrha pa si siđao 400 m: pad je 400 m, a 'oporavak' je tek kad ponovno stigneš na staru visinu.\n"
        "- **Epizoda pada**: razdoblje od vrha, preko dna, do ponovnog dostizanja starog vrha. Ovdje prikazujemo samo padove dublje od 25 %.\n"
        "- **Kolebanje (volatilnost)**: koliko dnevni pomaci 'skaču'. Zapisano kao godišnje (dnevna std × √252). Kao razlika između mirne rijeke i divlje rijeke.\n"
        "- **Koncentracija povrata**: koliko cjelokupne zarade dolazi iz malo najboljih dana. Kao da cijela godišnja plaća stigne u 10 dana, a ostatak godine je gotovo nula.\n"
    )
    out.append("## 1. Godišnji povrati (%)\n")
    out.append(md_table(yr, "{:+.1f}") + "\n")
    best_mu = yr["MU"].idxmax()
    worst_mu = yr["MU"].idxmin()
    neg = {t: int((yr[t] < 0).sum()) for t in TICKERS}
    out.append(
        f"\n**Što to znači:** MU je imao najbolju godinu {best_mu}. ({pct(yr['MU'].max(),0)}) i najgoru {worst_mu}. ({pct(yr['MU'].min(),0)}). "
        f"Broj godina s minusom (od {len(yr)}): MU {neg['MU']}, WDC {neg['WDC']}, STX {neg['STX']}, SMH {neg['SMH']}. "
        "Godine se jako razlikuju, pa je jedna godina loš uzorak za zaključak.\n"
    )
    out.append("## 2. Epizode pada dublje od 25 % (od vrha do dna do oporavka)\n")
    for t in TICKERS:
        ep = drawdown_episodes(daily(t)["close"], MIN_DD)
        out.append(f"\n### {t}\n")
        tb = pd.DataFrame(
            {
                "vrh": ep.peak.dt.strftime("%Y-%m-%d"),
                "dno": ep.trough.dt.strftime("%Y-%m-%d"),
                "pad_%": ep.depth * 100,
                "trgovačkih dana do dna": ep.days_down,
                "dana do oporavka": ep.days_recover.map(lambda v: "još nije" if pd.isna(v) else f"{int(v)}"),
            }
        )
        tb.index = range(1, len(tb) + 1)
        tb.index.name = "#"
        out.append(md_table(tb, "{:.1f}") + "\n")
    out.append(
        "\n**Što to znači:** 'trgovački dani' su dani kad burza radi (oko 21 u mjesecu, 252 u godini). Dugi oporavci (stotine dana) znače da je dioničar koji je kupio na vrhu čekao godinu-dvije samo da izađe na nulu. "
        "Ako je epizoda označena 'još nije', dionica danas još nije dosegnula taj stari vrh (ili je epizoda u tijeku).\n"
    )
    out.append("## 3. Faze ciklusa: kako su se razlikovale\n")
    out.append("Faze su zadane unaprijed iz Petrovog opisa tržišta (2018., covid, 2022., boom), ne podešene prema ishodu.\n\n")
    ps = phase_stats()
    for name in PHASES:
        sub = ps[ps.faza == name].set_index("dionica").drop(columns="faza")
        out.append(f"\n**{name}**\n\n" + md_table(sub, "{:.1f}") + "\n")
    out.append(
        "\n**Što to znači:** 'povrat' je promjena od zadnjeg zatvaranja prije faze do kraja faze; 'najveći pad' je najgori pad od vrha unutar faze (vrh se računa i od zadnjeg dana prije faze); "
        "'kolebanje' je godišnje, 'dana u plusu' je postotak dana s rastom. Usporedi retke: kad je kolebanje visoko a povrat negativan, to je panika; kad je kolebanje visoko a povrat pozitivan, to je boom s trzajima. "
        "Covid je trajao ~mjesec dana: premalo za zaključke o 'tipičnom' padu. 2018 i 2022 su po jedan primjer svaki.\n"
    )
    out.append("## 4. Koncentracija: koliko povrata dolazi iz najboljih dana\n")
    rows = []
    for t in TICKERS:
        c = cons[t]
        rows.append((t, int(c["n_days"]), c["total_x"], c["best10_share"], c["x_without_best10"], c["best20_share"], c["x_without_best20"], c["x_without_worst10"]))
    ct = pd.DataFrame(rows, columns=["dionica", "dana", "ukupno ×", "10 najboljih: udio povrata %", "× bez 10 najboljih", "20 najboljih: udio %", "× bez 20 najboljih", "× bez 10 najgorih"]).set_index("dionica")
    out.append(md_table(ct, "{:.2f}") + "\n")
    out.append(
        "\n**Kako čitati:** udio se računa na logaritamskom povratu (zbrajanje dnevnih log-povrata je ono što dava ukupni povrat). '× bez 10 najboljih' = što bi dobio da si *propustio* tih 10 dana, a imao sve ostale. "
        "Usporedi s '× bez 10 najgorih' = što bi dobio da si izbjegao 10 najgorih. 10 dana je samo oko 0,4 % svih dana.\n"
    )
    out.append("\n**10 najboljih dana MU-a:** " + ", ".join(f"{d} ({v:+.1f} %)" for d, v in mu["best_days"]) + "\n")
    out.append(f"\n**Gdje se najboljih 20 dana MU-a nalazi (po godini):** {dict(sorted(mu['best20_by_year'].items()))}; po razdobljima: {mu['best20_by_split']}.\n")
    out.append(
        "\n**Što napraviti / ne napraviti:** nemoj graditi pravilo koje 'misli' da zna unaprijed koji su dani najbolji; neki od najboljih dana dolaze usred panike (npr. 2020-03-24 odmah nakon covid dna, 2025-04-09 kad su carine odgođene), pa izlazak iz tržišta u panici znači propuštanje i oporavka. "
        "Svaku strategiju treba mjeriti i bez nekoliko najboljih dana (Critic to već radi kroz test koncentracije). Za Codex: svaki rezultat mora preživjeti uklanjanje 5-10 najboljih trgovina/dana.\n"
    )
    out.append("\n## Ograničenja\n- Deset godina je malo za 'ciklus' memorije: u podacima su otprilike 2-3 puna ciklusa. Zaključci o fazama su opisi, ne zakoni.\n- WDC je prilagođen za SanDisk spin-off (faktor 0,68132), pa WDC-ova povijest nije 'prava' cijena nego korigirana; nije dvaput prilagođeno.\n- Sve cijene su dnevna zatvaranja; unutardnevni pad nije prikazan.\n")
    write_report("memory_cycle.md", "\n".join(out))


if __name__ == "__main__":
    main()
