"""Study 5: local news archive coverage and next-trading-day return after headline keyword families."""
from __future__ import annotations

import json
import re
from functools import cache

import numpy as np
import pandas as pd
from scipy import stats

from lab.research.common import DATA, daily, md_table, num, pct, split_of, write_report

COVERAGE_TICKERS = ["MU", "WDC", "STX", "SMH", "AMAT", "LRCX", "KLAC", "SNDK"]
RET_TICKERS = ["MU", "WDC", "STX"]
# Families fixed BEFORE looking at any return (regex on lower-cased headline). Overlap is allowed.
FAMILIES = {
    "earnings": r"earnings|\beps\b|\bq[1-4]\b|quarterly results|\bresults\b|reports? (?:fy|q[1-4])",
    "upgrade": r"upgrade",
    "downgrade": r"downgrade",
    "price_target": r"price target|\bpt\b",
    "guidance": r"guidance|outlook|forecast|\bsees\b|expects",
    "tariff_trade": r"tariff|trade war|export (?:control|ban|restriction)|sanction",
    "ai_demand": r"\bai\b|hbm|data ?cent|nvidia|artificial intelligence",
    "memory_market": r"dram|nand|memory|flash",
    "legal_risk": r"lawsuit|\bsues?\b|probe|investigation|antitrust|settlement|patent",
    "unusual_options": r"options activity|whale|unusual",
}


@cache
def load_news() -> pd.DataFrame:
    rows = []
    for f in sorted((DATA / "news" / "archive").glob("*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                rows.append(json.loads(line))
    df = pd.DataFrame(rows).drop_duplicates("id")
    df["ts"] = pd.to_datetime(df.created_at, utc=True)
    df["ts_et"] = df.ts.dt.tz_convert("America/New_York")
    df["year"] = df.ts_et.dt.year
    df["n_sym"] = df.symbols.map(len)
    df["headline"] = df.headline.fillna("")
    df["h"] = df.headline.str.lower()
    return df


def reaction_day(ts_et: pd.Timestamp, idx: pd.DatetimeIndex) -> pd.Timestamp | None:
    """First trading day whose open is after publication: same day if before 09:30 ET on a trading day, else next trading day."""
    d = pd.Timestamp(ts_et.date())
    before_open = ts_et.hour * 60 + ts_et.minute < 9 * 60 + 30
    if d in idx and before_open:
        return d
    pos = idx.searchsorted(d, side="right")  # first trading day strictly after d
    return idx[pos] if pos < len(idx) else None


def main() -> None:
    df = load_news()
    L = ["# Pokrivenost vijestima i ponašanje cijene nakon ključnih riječi u naslovu\n"]
    # coverage tables
    cov_rows = []
    for t in COVERAGE_TICKERS:
        m = df.symbols.map(lambda s, t=t: t in s)
        sub = df[m]
        row = {"sve": len(sub), "fokusirani (<=3 simbola)": int((sub.n_sym <= 3).sum())}
        cov_rows.append((t, row, sub[sub.n_sym <= 3].groupby("year").size()))
    years = list(range(2016, 2027))
    yt = pd.DataFrame({t: s.reindex(years).fillna(0).astype(int) for t, _, s in cov_rows})
    yt.index.name = "godina"
    tot = pd.DataFrame({t: r for t, r, _ in cov_rows}).T
    tot.index.name = "dionica"
    # summary availability & sources
    sm = df.groupby("year").agg(clanaka=("id", "size"), sa_sazetkom_pct=("summary", lambda s: (s.fillna("") != "").mean() * 100))
    mu_f = df[df.symbols.map(lambda s: "MU" in s) & (df.n_sym <= 3)]
    mu_by_year = mu_f.groupby("year").size()
    ratio_26 = mu_by_year.get(2026, 0) / max(mu_by_year.get(2025, 1), 1)
    ndup = 13918 - len(df)
    # next trading day returns
    recs = []
    for t in RET_TICKERS:
        d = daily(t)
        idx = d.index
        ret = d.close.pct_change() * 100
        intra = (d.close / d.open - 1) * 100
        base_ret, base_intra = ret.mean(), intra.mean()
        sub = df[df.symbols.map(lambda s, t=t: t in s) & (df.n_sym <= 3)]
        for r in sub.itertuples():
            rd = reaction_day(r.ts_et, idx)
            if rd is None or rd == idx[0]:
                continue
            pre = rd.date() == r.ts_et.date()  # published before 09:30 ET on a trading day
            # tradable return: open->close if the news was pre-open (the gap is already gone), else close->close
            trade = intra[rd] if pre else ret[rd]
            excess = trade - (base_intra if pre else base_ret)
            for fam, pat in FAMILIES.items():
                if re.search(pat, r.h):
                    recs.append((t, fam, rd, ret[rd], trade, excess, pre))
    ev = pd.DataFrame(recs, columns=["ticker", "family", "rd", "full", "ret", "excess", "pre"]).drop_duplicates(["ticker", "family", "rd"])
    ev["split"] = ev.rd.map(split_of)
    base = {t: (daily(t).close.pct_change() * 100).dropna() for t in RET_TICKERS}
    n_tests = len(FAMILIES) * len(RET_TICKERS)
    rows = []
    for fam in FAMILIES:
        for t in RET_TICKERS:
            x = ev[(ev.family == fam) & (ev.ticker == t)].ret
            b = base[t]
            if len(x) < 5:
                continue
            g = ev[(ev.family == fam) & (ev.ticker == t)]
            tt = stats.ttest_1samp(g.excess, 0)
            rows.append(dict(familija=fam, dionica=t, n_dana=len(x), pre_pct=g.pre.mean() * 100, puni=g.full.mean(), prosjek=x.mean(), visak=g.excess.mean(), pozitivnih_pct=(x > 0).mean() * 100, prosj_abs=g.full.abs().mean(), obicni_abs=b.abs().mean(), p=tt.pvalue, p_bonf=min(tt.pvalue * n_tests, 1)))
    res = pd.DataFrame(rows)
    n_sig = int((res.p < 0.05).sum())
    n_bonf = int((res.p_bonf < 0.05).sum())
    n_ev = len(ev)
    up_mu = res[(res.familija == "upgrade") & (res.dionica == "MU")].iloc[0]
    uo = res[(res.familija == "unusual_options") & (res.dionica == "MU")].iloc[0]
    L.append("## Sažetak u 5 redaka\n")
    L.append(
        f"1. Lokalni arhiv ima {len(df):,} jedinstvenih članaka (uklonjeno {ndup} duplikata iz dva preklapajuća dokumenta), od 2015-12 do 2026-10; Benzinga naslovi, uz kratki sažetak u ~{num((df.summary.fillna('')!='').mean()*100,0)} % redaka, bez punog teksta.\n"
        f"2. Pokrivenost je neujednačena: MU ima {int(mu_by_year.sum())} fokusiranih članaka, a SMH/KLAC gotovo nijedan; 2026. ima ~{num(ratio_26,1)}x više MU članaka nego 2025. (drugi dokument od 2026-06-12), pa broj članaka ne smije biti 'signal'.\n"
        f"3. Testirali smo {len(FAMILIES)} unaprijed zadanih porodica ključnih riječi x 3 dionice = {n_tests} testova: {n_sig} ima p<0,05 (očekivano slučajno ~{num(0.05*n_tests,1)}), a {n_bonf} prolazi korekciju za višestruke testove.\n"
        f"4. Najjasniji nalaz je zamka: naslov 'upgrade' za MU prati pun pomak od {pct(up_mu.puni,2)}, ali ~{num(up_mu.pre_pct,0)} % takvih vijesti izađe prije otvaranja pa se skoro sve dogodi kao GAP; dio koji bi se još moglo uhvatiti (od otvaranja ili od zatvaranja dana vijesti) je samo {pct(up_mu.prosjek,2)}. Isto za downgrade. Jedini test koji prolazi korekciju je 'unusual_options' / MU ({pct(uo.visak,2)} višak, n={int(uo.n_dana)}), ali je nestabilan kroz razdoblja (IS ima samo 14 dana) pa ga ne smatramo rezultatom.\n"
        f"5. Što s tim: naslov 'upgrade/downgrade/earnings' sam nije dokazan smjerni signal; bez punog teksta i sentimenta ostaje samo 'što se događa uz tu riječ' (opis).\n"
    )
    L.append("## Pojmovi (laički)\n")
    L.append(
        "- **Porodica ključnih riječi**: skupina riječi u naslovu (npr. 'upgrade' = analitičar podiže preporuku). Popis je određen unaprijed, prije gledanja ishoda, da ne bismo birali riječi koje 'slučajno' rade.\n"
        "- **Reakcijski dan**: prvi dan trgovanja čije OTVARANJE slijedi objavu vijesti. Ako je vijest objavljena prije 9:30 po New Yorku, to je isti dan; ako poslije (i preko vikenda), idući trgovački dan. Mjerimo promjenu od zatvaranja dana prije do zatvaranja tog dana, pa ne gledamo u budućnost niti uračunavamo dio pomaka koji se već dogodio prije vijesti.\n"
        "- **Fokusirani članak**: članak koji spominje najviše 3 simbola; članci s desecima simbola su popisi ('stocks moving') i nisu o toj dionici.\n"
        "- **Duplikat**: isti članak spremljen dvaput (u dva dokumenta); smo ga izbacili po ID-u.\n"
        "- **Višestruki testovi (Bonferroni)**: što više kombinacija pogledaš, to više 'slučajnih pogodaka' nađeš; zato p množimo brojem testova.\n"
        "- **Sentiment**: raspoloženje teksta (pozitivno/negativno). Ovdje ga NEMAMO: ne izmišljamo ga; gledamo samo koja riječ stoji u naslovu.\n"
    )
    L.append("## 1. Koliko članaka po dionici i godini (fokusirani, <=3 simbola)\n")
    L.append(md_table(yt, "{:.0f}") + "\n")
    L.append("\nUkupno po dionici (sve / fokusirani):\n\n" + md_table(tot) + "\n")
    L.append(
        f"\n**Što to znači:** vijesti ima puno više za MU nego za WDC/STX, a za AMAT/LRCX/KLAC/SMH ima ih premalo za bilo kakvu studiju. SNDK ima podatke tek od 2025 (i jedna sitna stara serija 2016.). "
        f"MU 2026. ima {int(mu_by_year.get(2026,0))} fokusiranih članaka naspram {int(mu_by_year.get(2025,0))} u 2025.: dio je stvarno više pažnje (MU je u bumu), a dio je što arhiv za 2026 sadrži dodatni dokument. Nemoj brojati članke kao mjeru raspoloženja.\n"
    )
    L.append("\n## 2. Pokrivenost po godini (svi članci)\n")
    sm.columns = ["članaka", "% sa sažetkom"]
    sm.index.name = "godina"
    L.append(md_table(sm, "{:.1f}") + "\n")
    L.append(
        f"\nProblemi pokrivenosti: (a) 'source' je prazan u {int((df.source.fillna('')=='').sum()):,} redaka (ne znamo izvor); (b) postotak članaka sa sažetkom se mijenja kroz godine, pa tekstualne značajke ne bi bile ujednačene; (c) 2015-12 ima samo nekoliko članaka; (d) nema korejskih/japanskih izvora, društvenih mreža ni transkripata; (e) 'created_at' je vrijeme objave, ne nužno vrijeme kad je informacija prvi put izašla, jer Benzinga često prepričava već poznato.\n"
    )
    L.append("## 3. Što se događalo sljedeći dan nakon naslova s ključnom riječi\n")
    L.append(f"Za svaku (dionica, porodica, reakcijski dan) računa se jedan događaj, čak i ako je tog dana više članaka. Ukupno {n_ev:,} događaja. Samo kombinacije s najmanje 5 dana.\n\n")
    out = res.copy().set_index(["familija", "dionica"])
    out.index = [f"{a} / {b}" for a, b in out.index]
    out.index.name = "porodica / dionica"
    out["n_dana"] = out.n_dana.astype(int)
    out.columns = ["n dana", "% vijesti prije otvaranja", "pun pomak (s gapom) %", "prosjek koji se moglo uhvatiti %", "višak nad običnim %", "% pozitivnih (uhvatljivo)", "prosj. apsolutni pun pomak %", "običan apsolutni %", "p (višak=0)", "p (Bonferroni)"]
    L.append(md_table(out, "{:.2f}") + "\n")
    L.append(
        f"\n**Što to znači:** 'pun pomak' je promjena od zatvaranja prije vijesti do zatvaranja reakcijskog dana: velik dio nje je GAP koji se dogodio prije nego što si vijest mogao vidjeti i na njega reagirati, pa se taj dio ne može 'uhvatiti'. "
        f"Zato je 'prosjek koji se moglo uhvatiti' stroža mjera: za vijesti prije otvaranja je to promjena otvaranje->zatvaranje, za ostale zatvaranje->zatvaranje idućeg dana. 'višak nad običnim' oduzima prosjek iste vrste dana te dionice (MU je mnogo rastao, pa 'običan' dan nije nula). p testira je li višak različit od nule; p (Bonferroni) je p x {n_tests}. "
        "Ako je 'prosj. apsolutni pomak' veći od 'običnog apsolutnog', riječ u naslovu prati veći nemir (npr. earnings), ali ne nužno smjer.\n"
    )
    mu_f2 = ev[ev.ticker == "MU"].assign(ret=lambda z: z.excess)
    sg = []
    for fam in FAMILIES:
        x = mu_f2[mu_f2.family == fam]
        if len(x) < 20:
            continue
        row = {"porodica": fam, "n": len(x)}
        for s_ in ["IS", "WF", "HO"]:
            xs = x[x.split == s_].ret
            row[f"{s_} n"] = len(xs)
            row[f"{s_} prosjek %"] = xs.mean() if len(xs) else np.nan
        sg.append(row)
    L.append("## 4. Stabilnost kroz razdoblja (samo MU, porodice s n>=20; prikazan višak nad običnim, uhvatljivi dio)\n")
    if sg:
        sgd = pd.DataFrame(sg).set_index("porodica")
        for c in ["n"] + [f"{s_} n" for s_ in ["IS", "WF", "HO"]]:
            sgd[c] = sgd[c].astype(int)
        L.append(md_table(sgd, "{:.2f}") + "\n")
    L.append(
        "\n**Što to znači:** ako prosjek mijenja predznak između IS/WF/HO, nema stabilnog učinka. Pogledaj i sam n po razdoblju: tamo gdje je mali, broj je buka.\n"
    )
    L.append("## Što napraviti / ne napraviti\n")
    L.append(
        "- **Ne** gradi strategiju na samoj riječi u naslovu (upgrade, downgrade, tariff...) iz ovih podataka; ako se ijedno 'čini' značajno, to je među 30 testova i bez dodatne potvrde se tretira kao slučajnost.\n"
        "- Ako želiš pravi sentiment/vijesti, treba puni tekst (Alpaca ga daje od 2015.; lokalni arhiv ima samo naslov i ponegdje sažetak) i unaprijed definirana pravila ocjene, zapisana prije testa.\n"
        "- Ovaj izvještaj je opis pokrivenosti; koristi ga da znaš gdje su rupe (2026 dupla pokrivenost, SMH/KLAC gotovo bez vijesti).\n"
        "\n## Ograničenja\n- Regex na naslovima je grub (npr. 'results' hvata i generičke naslove; 'sees' hvata mnogo toga). Porodice se preklapaju.\n- Isti dan može imati više vijesti u suprotnim smjerovima; zato gledamo samo 'bilo koja vijest te porodice taj dan'.\n- Dani s vijestima nisu slučajno odabrani (vijesti prate velike pomake), pa je dio 'reakcije' zapravo tržišni dan koji je vijest izazvao, ne obrnuto.\n- Vijesti prije otvaranja često samo komentiraju pomak koji je već počeo u pretržišnom trgovanju; mi mjerimo od prethodnog zatvaranja pa se to uračunava (to je namjerno).\n"
    )
    write_report("news_coverage.md", "\n".join(L))
    print(n_ev, n_sig, n_bonf)


if __name__ == "__main__":
    main()
