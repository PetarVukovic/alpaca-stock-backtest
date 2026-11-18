"""Study 4: event library. What MU/WDC/STX/SMH did on us_reaction_date, +1 and +5 days, per event type as labelled in the calendar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab.research.common import DATA, daily, md_table, num, write_report

TICKERS = ["MU", "WDC", "STX", "SMH"]


def event_returns(t: str, react: pd.Timestamp) -> dict:
    """Return day0 (close-to-close on reaction date), day+1 and cumulative +5 (from day0 close), all in %."""
    d = daily(t)
    if react not in d.index:
        return dict(d0=np.nan, d1=np.nan, d5=np.nan)
    i = d.index.get_loc(react)
    c = d.close
    return dict(
        d0=(c.iloc[i] / c.iloc[i - 1] - 1) * 100,
        d1=(c.iloc[i + 1] / c.iloc[i] - 1) * 100 if i + 1 < len(d) else np.nan,
        d5=(c.iloc[i + 5] / c.iloc[i] - 1) * 100 if i + 5 < len(d) else np.nan,
    )


def main() -> None:
    ev = pd.read_csv(DATA / "news" / "events_calendar.csv", parse_dates=["event_date", "us_reaction_date"])
    rows = []
    for e in ev.itertuples():
        for t in TICKERS:
            rows.append(dict(event_date=e.event_date, react=e.us_reaction_date, type=e.type, tickers=e.tickers, desc=e.description, ticker=t, **event_returns(t, e.us_reaction_date)))
    df = pd.DataFrame(rows)
    base = {t: dict(abs_day=(daily(t).close.pct_change().abs() * 100).mean()) for t in TICKERS}
    types = list(dict.fromkeys(ev.type))
    L = ["# Biblioteka događaja: što se dogodilo MU/WDC/STX/SMH\n"]
    L.append("## Sažetak u 5 redaka\n")
    non_e = df[(df.type != "earnings_MU")]
    big = non_e[non_e.ticker == "MU"].d0.abs().mean()
    ear = df[(df.type == "earnings_MU") & (df.ticker == "MU")].d0.abs().mean()
    L.append(
        f"1. Kalendar ima {len(ev)} događaja u {len(types)} tipova; 43 su MU izvještaji, ostalih {len(ev)-43} su pojedinačni događaji (1-4 po tipu). Tip je uzet doslovno iz kalendara, ne mijenjan nakon gledanja ishoda.\n"
        f"2. Dan reakcije na velike makro/sektorske događaje (bez MU izvještaja) je za MU prosječno {num(big,1)} % po apsolutnoj vrijednosti, naspram {num(base['MU']['abs_day'],1)} % na običan dan i {num(ear,1)} % na dan MU izvještaja.\n"
        f"3. Jedini tip s više od 4 slučaja je MU izvještaj (n=43; detalji u earnings_reaction.md). Za sve ostale tipove n je premalen za statistiku: to su anegdote, ne pravila.\n"
        f"4. Kalendar je sastavljen unatrag i sadrži 'poznate' događaje (selection bias): nije uzorak svih vijesti, pa 'prosjek po tipu' ne smije postati signal.\n"
        f"5. Što s tim: koristi biblioteku kao podsjetnik 'što se već događalo' (kontekst za rizik), ne kao okidač za trgovanje.\n"
    )
    L.append("## Pojmovi (laički)\n")
    L.append(
        "- **Tip događaja**: oznaka koju je netko dao događaju PRIJE nego što gledamo ishod (npr. 'macro_tariffs' = carine). Kad bismo tip mijenjali nakon ishoda, varali bismo sami sebe, kao da gađaš metu pa je naknadno nacrtaš oko strijele.\n"
        "- **us_reaction_date**: prvi američki trgovački dan u kojem cijena može reagirati. Vijest nakon zatvaranja burze reagira idući dan.\n"
        "- **Dan 0 / +1 / +5**: dan 0 = promjena na dan reakcije (zatvaranje u odnosu na prethodno zatvaranje); +1 = promjena idućeg dana; +5 = ukupna promjena od zatvaranja dana 0 do zatvaranja 5 trgovačkih dana kasnije.\n"
        "- **Selection bias (pristranost odabira)**: događaji su zapisani jer su bili važni i zapamćeni, što znači da su obično ekstremni. Kao da po lovačkim pričama zaključuješ koliko često se lovi veliki medvjed.\n"
    )
    L.append("## 1. Broj događaja po tipu\n")
    cnt = ev.groupby("type").agg(n=("type", "size"), od=("event_date", "min"), do=("event_date", "max"))
    cnt["od"] = cnt.od.dt.strftime("%Y-%m-%d")
    cnt["do"] = cnt.do.dt.strftime("%Y-%m-%d")
    cnt.index.name = "tip"
    L.append(md_table(cnt) + "\n")
    L.append("\n'peer_earnings_upcoming' je u budućnosti (reakcija 2026-10-08) i nema podataka; izostavljen iz tablica ishoda.\n")
    L.append("## 2. Prosjek po tipu i dionici (%)\n")
    out = []
    for ty in types:
        if ty == "peer_earnings_upcoming":
            continue
        for t in TICKERS:
            x = df[(df.type == ty) & (df.ticker == t)]
            out.append(dict(tip=ty, dionica=t, n=int(x.d0.notna().sum()), dan0_prosjek=x.d0.mean(), dan0_medijan=x.d0.median(), dan0_pozitivnih_pct=(x.d0 > 0).sum() / max(x.d0.notna().sum(), 1) * 100, dan1_prosjek=x.d1.mean(), dan5_prosjek=x.d5.mean(), n5=int(x.d5.notna().sum()), obican_abs_dan=base[t]["abs_day"]))
    ot = pd.DataFrame(out).set_index(["tip", "dionica"])
    ot.index = [f"{a} / {b}" for a, b in ot.index]
    ot.index.name = "tip / dionica"
    ot.columns = ["n", "dan 0 prosjek", "dan 0 medijan", "% dana 0 pozitivnih", "dan +1 prosjek", "dan +5 prosjek", "n za +5", "običan apsolutni dan"]
    L.append(md_table(ot, "{:.2f}") + "\n")
    L.append("\n**Što to znači:** kad je n=1 ili 2, 'prosjek' je samo taj jedan ili dva događaja. 'običan apsolutni dan' je prosječni pomak te dionice na bilo koji dan, pa vidiš je li događaj bio veći od normalnog (ne gledaj predznak nego veličinu).\n")
    L.append("## 3. Svi pojedinačni događaji osim MU izvještaja (jer ih je malo, prikazujemo ih svaki zasebno)\n")
    for ty in types:
        if ty in ("earnings_MU", "peer_earnings_upcoming"):
            continue
        sub = df[df.type == ty]
        L.append(f"\n**{ty}** (n={len(sub.groupby('react'))})\n")
        recs = []
        for (rd, tk, ds), g in sub.groupby(["react", "tickers", "desc"], sort=True):
            rec = {"react": rd, "tickers": tk, "desc": ds}
            for m, lab in [("d0", "dan 0"), ("d1", "+1"), ("d5", "+5")]:
                for t in TICKERS:
                    rec[f"{t} {lab}"] = g.loc[g.ticker == t, m].iloc[0]
            recs.append(rec)
        flat = pd.DataFrame(recs)
        flat["react"] = flat.react.dt.strftime("%Y-%m-%d")
        flat["desc"] = flat.desc.str.replace("|", "/", regex=False)
        flat = flat.rename(columns={"react": "reakcija", "tickers": "tickeri iz kalendara", "desc": "opis (iz kalendara)"}).set_index("reakcija")
        L.append(md_table(flat, "{:.1f}") + "\n")
    L.append("\n## 4. MU izvještaji kroz događajnu optiku (usporedi s earnings_reaction.md)\n")
    em = df[df.type == "earnings_MU"]
    et = []
    for t in TICKERS:
        x = em[em.ticker == t]
        et.append(dict(dionica=t, n=len(x), dan0=x.d0.mean(), dan1=x.d1.mean(), dan5=x.d5.mean(), dan0_abs=x.d0.abs().mean(), obican_abs=base[t]["abs_day"]))
    et = pd.DataFrame(et).set_index("dionica")
    et.columns = ["n", "dan 0 prosjek %", "+1 prosjek %", "+5 prosjek %", "dan 0 apsolutno %", "običan apsolutni dan %"]
    L.append(md_table(et, "{:.2f}") + "\n")
    L.append(
        "\n## Što napraviti / ne napraviti\n"
        "- **Ne** izvlači pravilo tipa 'nakon carina kupi' iz 2 događaja; to je anegdota.\n"
        "- Koristi biblioteku za **kontekst rizika**: na ovakve dane (makro šok, rotacija sektora) MU/WDC/STX se miču višestruko više od običnog dana; veličina pozicije i zaštita trebaju to podnijeti.\n"
        "- Kad nastane novi događaj, dodaj ga u kalendar s tipom odmah (prije gledanja ishoda) da biblioteka ostane poštena.\n"
        "- Za Codex: jedini tip s dovoljno slučajeva za test je 'earnings_MU' (n=43); sve ostalo je premalo za Critic.\n"
        "\n## Ograničenja\n- Kalendar je curiran (58 redaka), odabir događaja je subjektivan i napravljen unatrag.\n- Događaji se često poklapaju s velikim tržišnim danima (covid, carine), pa ne možemo odvojiti 'efekt događaja' od 'efekta tržišta'.\n- Događaji nisu neovisni: neki leže u istom tjednu (npr. carine 2025-04-03 i 2025-04-09; SK Hynix i Samsung 2026-07-29/30), pa se +1/+5 prozori preklapaju.\n- Za događaje blizu kraja podataka +5 dana još ne postoji (prazno).\n"
    )
    write_report("event_library.md", "\n".join(L))


if __name__ == "__main__":
    main()
