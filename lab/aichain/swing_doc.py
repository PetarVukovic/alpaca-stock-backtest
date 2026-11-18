"""Write SWING_ENGINE.md (Croatian) from summary.json. Every number comes from the computed results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "research" / "AICHAIN_20261014" / "swing"

NAMES = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang momentuma",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore v2",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 hvatanje likvidnosti i promjena strukture",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
    "B0_BUYHOLD": "B0 kupi i drži (mjerilo)",
}
GROUP_ORDER = [
    "stocks_all",
    "memory",
    "mem_interface_storage",
    "equipment",
    "ai_chips_logic",
    "network_servers",
    "cloud",
    "crypto",
    "metali_referentno",
]
GROUP_TITLES = {
    "stocks_all": "Sve dionice (zbroj svih šest segmenata)",
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja memorije i pohrana",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Oblak i podatkovni centri",
    "crypto": "Kripto (zasebna grupa, trošak 10 bps)",
    "metali_referentno": "Metali GLD i SLV (nepotvrđeno / referentno)",
}


def num(x: float | None, d: int = 2) -> str:
    if x is None:
        return "-"
    s = f"{x:,.{d}f}"
    return s.replace(",", "#").replace(".", ",").replace("#", ".")


def pct(x: float | None, d: int = 1) -> str:
    return "-" if x is None else num(x * 100, d) + " %"


def eur(x: float | None, d: int = 0) -> str:
    return "-" if x is None else num(x, d) + " EUR"


def table(header: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def feel_rows(per: dict[str, Any], rank: dict[str, Any]) -> list[list[str]]:
    status = {r["contender"]: r for r in rank["ranking"] + rank["not_eligible"]}
    rows = []
    for cid, label in NAMES.items():
        b = per.get(cid)
        if not b or not b.get("trades"):
            rows.append([label, "0"] + ["-"] * 11)
            continue
        if cid == "B0_BUYHOLD":
            ver = "mjerilo"
            exp = "-"
        else:
            r = status[cid]
            ver = "DA" if r["eligible"] else "ne"
            exp = eur(b["expectancy_eur"])
        rows.append(
            [
                label,
                str(b["trades"]),
                num(b["trades_per_month"], 1),
                num(b["trades_per_ticker_year"], 1),
                pct(b["hit_rate"], 0),
                eur(b["avg_win_eur"]),
                eur(b["avg_loss_eur"]),
                exp,
                num(b["profit_factor"], 2) if cid != "B0_BUYHOLD" else "-",
                f"{num(b['median_hold_days'], 0)} / {num(b['mean_hold_days'], 1)}",
                str(b["longest_losing_streak"]),
                pct(b["top5_profit_share"], 0),
                ver,
            ]
        )
    return rows


FEEL_HEAD = [
    "Algoritam",
    "Poslova",
    "Poslova / mj. (grupa)",
    "Poslova / ticker / god.",
    "Pogodak",
    "Prosj. dobitak",
    "Prosj. gubitak",
    "Očekivanje / posao",
    "Faktor dobiti",
    "Držanje (medijan / prosjek, dana)",
    "Najdulji niz gubitaka",
    "Udio 5 najboljih u dobiti",
    "Radi često?",
]


def risk_rows(per: dict[str, Any]) -> list[list[str]]:
    rows = []
    for cid, label in NAMES.items():
        b = per.get(cid)
        if not b:
            continue
        rows.append(
            [
                label,
                pct(b["exposure_pct"] / 100, 0),
                pct(b["total_return"], 0),
                num(b["sharpe"], 2),
                pct(b["max_drawdown"], 0),
                pct(b["total_return_cost_2x"], 0),
                pct(b["total_return_cost_3x"], 0),
                eur(b.get("expectancy_eur_cost_2x")) if cid != "B0_BUYHOLD" else "-",
                num(b.get("psr"), 2) if b.get("psr") is not None else "-",
                num(b.get("deflated_sharpe_prob"), 2)
                if b.get("deflated_sharpe_prob") is not None
                else "-",
            ]
        )
    return rows


RISK_HEAD = [
    "Algoritam",
    "Izloženost",
    "Ukupni prinos",
    "Sharpe",
    "Max pad",
    "Prinos uz trošak 2x",
    "Prinos uz trošak 3x",
    "Očekivanje / posao uz 2x",
    "PSR",
    "Deflated Sharpe",
]


def leader_line(g: dict[str, Any]) -> str:
    rk = g["ranking"]
    if not rk:
        return "nitko ne zadovoljava pravilo"
    parts = []
    for r in rk[:3]:
        parts.append(
            f"{NAMES[r['contender']]}: {num(r['trades_per_month'], 1)} poslova mj., "
            f"{eur(r['expectancy_eur'])} po poslu, ukupno {eur(r['score_eur_per_month'])} mj."
        )
    return "; ".join(parts)


def summary_section(groups: dict[str, Any], results_dir: Path) -> list[str]:
    """Plain-language findings computed from the results (no hand-typed numbers)."""
    import json

    out: list[str] = []
    sa = groups["stocks_all"]
    rk = sa["ranking"]
    out.append("## 0. Sažetak: što je ispalo (AI era, sve dionice)\n")
    out.append(
        f"Rang po pravilu 'radi često' (očekivanje po poslu x poslova mjesečno, eura mjesečno na 1.000 EUR po sleeveu uz {len(sa['tickers'])} sleeve-a):\n"
    )
    out.append(
        table(
            [
                "#",
                "Algoritam",
                "Poslova / mj.",
                "Očekivanje / posao",
                "Uz trošak 2x",
                "Faktor dobiti",
                "EUR / mj.",
            ],
            [
                [
                    str(i + 1),
                    NAMES[r["contender"]],
                    num(r["trades_per_month"], 1),
                    eur(r["expectancy_eur"]),
                    eur(r["expectancy_eur_cost_2x"]),
                    num(r["profit_factor"], 2),
                    eur(r["score_eur_per_month"]),
                ]
                for i, r in enumerate(rk)
            ],
        )
    )
    out.append("")
    if sa["not_eligible"]:
        out.append(
            "Nisu podobni: "
            + "; ".join(
                f"{NAMES[r['contender']]} ({', '.join(r['reasons'])})"
                for r in sa["not_eligible"]
            )
            + ".\n"
        )
    bh = sa["buy_and_hold_reference"]
    best = max(
        (
            sa["per_contender"][c]
            for c in NAMES
            if c != "B0_BUYHOLD" and sa["per_contender"].get(c)
        ),
        key=lambda b: b["total_return"],
    )
    out.append(
        f"Kupi-i-drži na istim dionicama: ukupni prinos {pct(bh['total_return'], 0)}, Sharpe {num(bh['sharpe'], 2)}. "
        f"Najbolji algoritam po ukupnom prinosu ima {pct(best['total_return'], 0)}. Ukupni prinos je sekundaran; pitanje je što trguje često i radi.\n"
    )
    names = [r["contender"] for r in rk]
    mm = []
    for cid in ("W6_MM_SWEEP_SHIFT", "W7_MM_DEMAND_RETEST"):
        b = sa["per_contender"][cid]
        pos = names.index(cid) + 1 if cid in names else None
        mm.append(
            f"{NAMES[cid]}: {b['trades']} poslova ({num(b['trades_per_month'], 1)} mj.), očekivanje {eur(b['expectancy_eur'])}, "
            f"faktor dobiti {num(b['profit_factor'], 2)}, "
            + (f"mjesto {pos} od {len(names)} podobnih" if pos else "nije podoban")
        )
    out.append(
        "Tržišna mehanika (W6, W7), pretvorena u stroga pravila: "
        + "; ".join(mm)
        + ".\n"
    )
    base = [g for g in GROUP_ORDER if g != "stocks_all" and g in groups]
    cnt = {
        cid: sum(
            1 for g in base if cid in [r["contender"] for r in groups[g]["ranking"]]
        )
        for cid in NAMES
        if cid != "B0_BUYHOLD"
    }
    out.append(
        f"Dosljednost: u koliko od {len(base)} grupa je algoritam podoban (obrazac koji drže mnoge grupe vrijedi više od jedne ćelije):\n"
    )
    out.append(
        table(
            ["Algoritam", "Podoban u grupama"],
            [[NAMES[c], f"{n} / {len(base)}"] for c, n in cnt.items()],
        )
    )
    out.append("")
    ctx = json.loads((results_dir / "stocks_all.json").read_text())["contenders"]
    rows = []
    for cid, label in NAMES.items():
        row = [label]
        for w in ("y2016_2020", "y2021_2022"):
            b = ctx[cid]["contexts"].get(w)
            row += (
                [
                    str(b["trades"]),
                    eur(b["expectancy_eur"]) if cid != "B0_BUYHOLD" else "-",
                    num(b["profit_factor"], 2) if cid != "B0_BUYHOLD" else "-",
                    pct(b["total_return"], 0),
                ]
                if b and b["trades"]
                else ["-"] * 4
            )
        rows.append(row)
    neg = [
        NAMES[c]
        for c in NAMES
        if c != "B0_BUYHOLD"
        and (b := ctx[c]["contexts"].get("y2021_2022"))
        and b["trades"]
        and b["expectancy_eur"] <= 0
    ]
    out.append(
        f"U razdoblju 2021-2022 (pad tržišta) očekivanje po poslu je nula ili negativno za {len(neg)} od {len(NAMES) - 1} algoritama"
        + (f" ({', '.join(neg)})" if neg else "")
        + ". Zato 'radi' vrijedi samo za AI eru dok se ne pokaže suprotno u drugom režimu.\n"
    )
    out.append(
        "Kontekst (isti algoritmi, isti fiksni parametri, sve dionice): predznak očekivanja u ranijim režimima:\n"
    )
    out.append(
        table(
            [
                "Algoritam",
                "2016-2020 poslova",
                "očekivanje",
                "faktor dobiti",
                "prinos",
                "2021-2022 poslova",
                "očekivanje",
                "faktor dobiti",
                "prinos",
            ],
            rows,
        )
    )
    out.append("")
    return out


def write_doc(summary: dict[str, Any], reg: dict[str, Any]) -> None:
    groups = summary["groups"]
    k = summary["ledger_k"]
    look = summary["lookahead"]
    rob = summary["robustness_top3"]
    lines: list[str] = []
    add = lines.append
    add("# Test učestalosti: koji swing algoritam radi i trguje često\n")
    add(
        "Ovo je istraživanje. Nije savjet za ulaganje, nije Critic PASS i agenti ne šalju nikakve naloge "
        "(ni probne ni prave). Kod: `lab/aichain/swing.py` (pravila i simulator s djelomičnim izlazom), "
        "`lab/aichain/swing_run.py` (pokretač), `lab/aichain/swing_doc.py` (ova stranica), testovi "
        "`tests/aichain/test_swing.py`. Rezultati: `reports/research/AICHAIN_20261014/swing/`.\n"
    )
    add(
        "the researcher trguje iz Hrvatske preko Interactive Brokersa, swing (dani do tjedni), samo dugo, bez poluge. "
        "Američke pojedinačne dionice su općenito u redu. Američki ETF-ovi (GLD, SLV, SMH, SOXX) često **nisu** "
        "dostupni malim ulagačima iz EU (nema KID dokumenta), pa su GLD i SLV ovdje samo **nepotvrđeni / referentni** "
        "nizovi. Dostupnost kripta na IBKR-u ovisi o državi i regulativi: **nepotvrđeno**. Dozvole brokera i porez "
        "nisu pretpostavljeni.\n"
    )
    lines.extend(summary_section(groups, OUT / "results"))
    add("## 1. Pitanje i mjerilo\n")
    add(
        "Petrov cilj nije najveći ukupni prinos, nego algoritam koji **stvarno radi** i **često trguje** "
        "(dani do tjedni). Mjerilo je **AI era** (2023-01-01 do 2026-10-05); 2016-2020 i 2021-2022 "
        "su samo kontekst. Critic je blag prema riziku (pad, volatilnost i koncentracija ne snižavaju ocjenu) "
        "a strog samo prema **nevaljanim dokazima**: pogled u budućnost, ugađanje (fragilnost), premalo poslova, trošak.\n"
    )
    add("## 2. Kako simulator radi, običnim riječima\n")
    add(
        "- **Odluka na zatvaranju dana, kupnja sutra na otvaranju.** Navečer pogledate graf i zadate nalog za sutrašnje "
        "otvaranje; pravilo nikad ne vidi budućnost.\n"
        "- **Samo dugo, bez posuđenog novca, razlomljene jedinice.** 1.000 EUR i cijena 300 daje 3,33 dionice "
        "(stvarni IBKR: nepotvrđeno za svaku dionicu).\n"
        "- **Trošak po strani.** Dionice i metali 2,5 bps = 0,025 % (na 1.000 EUR to je 0,25 EUR pri kupnji i 0,25 EUR pri prodaji). "
        "Kripto 10 bps = 0,10 % (1,00 EUR po strani). Stres: 2x i 3x trošak.\n"
        "- **Stop unutar dana.** Stop je automatska prodaja ako cijena padne na određenu razinu. Ako dan otvori ispod stopa "
        "(jaz preko noći), izlaz je po otvaranju, dakle gore od stopa. Ako se u istoj svijeći dotaknu stop i cilj, vrijedi stop (oprezno).\n"
        "- **Sleeve** je jedan ticker s vlastitih 1.000 EUR. Grupa je zbroj sleeve-ova bez prelijevanja kapitala.\n"
        "- **Očekivanje po poslu u eurima** = prosječan prinos posla x 1.000 EUR. Primjer: prosjek +2 % po poslu znači +20 EUR po poslu "
        "na uloženih 1.000 EUR. Svaki posao se normalizira na cijelih 1.000 EUR, pa se poslovi ne složeno kamate i usporedivi su.\n"
        "- **Djelomični izlaz (samo W6):** pri cilju se stvarno proda polovica jedinica, ostatak se prati ispod najnižeg dna zadnjih 10 svijeća. "
        "Posao se računa kao cjelina (ukupna otkupnina / ulaganje).\n"
        f"- **Prozori:** `ai_era` {summary['ai_era_start']} do {summary['common_end']} je glavno mjerilo (indikatori se griju na ranijim podacima, račun počinje prazan). "
        "Svi tickeri (i kripto, i metali) koriste isti kraj podataka 2026-10-05 da bi grupe bile usporedive.\n"
    )
    add("## 3. Pojmovi tržišne mehanike pretvoreni u stroga pravila\n")
    add(
        "Neslužbena ('smart money') nastava koju the researcher prati vrlo je opisna i često nejasna. Ovdje je svaki pojam preveden u "
        "**strogo, provjerljivo, bez pogleda u budućnost** pravilo i testiran pošteno, bez pretpostavke da radi:\n\n"
        "- **Swing pivot:** najviša (najniža) točka koja je viša (niža) od 5 svijeća sa svake strane. Upotrebljiva tek **5 svijeća nakon** nastanka "
        "(prije toga ne znamo da je pivot). Primjer: dno od 90 EUR s 5 viših svijeća lijevo i desno postaje poznato tek 5 dana kasnije.\n"
        "- **Struktura tržišta:** niz potvrđenih pivota. Bikovska = viši vrhovi i više dna; medvjeđa = niži vrhovi i niža dna.\n"
        "- **Proboj strukture (BOS)** je zatvaranje iznad zadnjeg vrha u smjeru trenda; **promjena strukture (market shift)** je zatvaranje iznad "
        "zadnjeg potvrđenog **nižeg vrha** (prvi znak da se silazni trend okreće). U W6 je to okidač.\n"
        "- **Raspon, premium i diskont:** od zadnjeg potvrđenog dna do zadnjeg potvrđenog vrha. Gornja polovica je premium, donja diskont. "
        "Primjer: raspon 80 do 120 EUR, sredina 100: cijena 90 je u diskontu. Dugo se traži samo u diskontu.\n"
        "- **Likvidnost i 'sweep':** stop-nalozi se skupljaju ispod očitih dna. Sweep = svijeća probije takvo dno (fitilj), ali **zatvori natrag iznad**. "
        "Primjer: dno 90, svijeća dođe na 88 i zatvori na 91.\n"
        "- **Zona potražnje / order block:** zadnja crvena svijeća prije snažnog rasta (barem 2 ATR14 unutar 3 svijeće) koji je probio swing vrh. "
        "ATR14 je prosječni dnevni raspon zadnjih 14 dana. Zona je 'svježa' dok joj se cijena prvi put ne vrati.\n"
        "- **Fair value gap (FVG)** je opisan u uputi (bar1 high < bar3 low), ali **nijedan suparnik ga ne koristi** u pravilima; nije testiran.\n"
        "- **Top-down:** tjedna struktura daje smjer (tjedne svijeće građene iz dnevnih; koristi se tjedni SMA10 s tekućim zatvaranjem + 9 završenih tjedana), "
        "dnevna daje zone i okidač. Satni podaci nisu korišteni.\n"
    )
    add("## 4. Suparnici (fiksni parametri, bez ugađanja)\n")
    rows = []
    for cid, r in reg["contenders"].items():
        rows.append([NAMES[cid], "<br>".join(r["rules"])])
    add(table(["Algoritam", "Pravilo"], rows))
    add(
        f"\nSvaki suparnik je jedan pokušaj u `reports/ledger/trials.jsonl` (K {reg['ledger_k_before'] + 1} do {reg['ledger_k_after']}, 9 redaka) i zamrznut u "
        "`strategies/frozen/2026-10-14_SWING_{ID}.json`. `registration.json` je napisan **prije** prvog pokretanja. "
        f"Ledger K u trenutku analize: **{k}**. Dopune specifikacije koje sam morao odabrati (unaprijed, bez gledanja rezultata) nalaze se u `registration.json` pod `interpretations`:\n"
    )
    for t in reg["interpretations"]:
        add(f"- {t}")
    add("")
    add("## 5. Pravilo 'radi često' (fiksno)\n")
    add(
        f"**Podoban** je algoritam s **najmanje {60} poslova** u AI eri nad grupom, **pozitivnim očekivanjem po poslu uz trošak 2x** i "
        "**faktorom dobiti >= 1,2**. Faktor dobiti = zbroj dobitaka / zbroj gubitaka: 1,5 znači da na svaki izgubljeni euro dobijete 1,50 EUR. "
        "Među podobnima rang je **očekivanje po poslu x poslova mjesečno** (eura mjesečno na 1.000 EUR po sleeveu, uz trošak 1x). "
        "Kupi-i-drži je uvijek prikazan kao mjerilo i nikad se ne rangira.\n"
    )
    add(
        "Kako čitati stupce: **pogodak** je udio dobitnih poslova; **prosj. dobitak/gubitak** je u eurima na 1.000 EUR; **najdulji niz gubitaka** je najviše uzastopnih "
        "gubitnih poslova (grupa: poredano po datumu izlaza); **udio 5 najboljih u dobiti** je zbroj pet najboljih poslova / ukupna neto dobit "
        "(iznad 100 % znači da ostali poslovi zajedno gube, pa rezultat visi na nekoliko sreće); **izloženost** je prosječni dio kapitala koji je u dionicama; "
        "**Sharpe** je prosječni dnevni prinos / njegovo treskanje x korijen iz 252; **max pad** je najveći pad od vrha (2.000 EUR na 1.200 EUR je -40 %).\n"
    )
    add("## 6. Rezultati po grupama (AI era)\n")
    add("### Najbolji po grupi (pravilo 'radi često')\n")
    lead_rows = []
    for g in GROUP_ORDER:
        if g in groups:
            lead_rows.append([GROUP_TITLES[g], leader_line(groups[g])])
    add(table(["Grupa", "Rang (do 3)"], lead_rows))
    add("")
    for g in GROUP_ORDER:
        if g not in groups:
            continue
        gd = groups[g]
        add(f"### {GROUP_TITLES[g]}\n")
        add(f"Tickeri: {', '.join(gd['tickers'])}.\n")
        if g == "metali_referentno":
            add(
                "**Nepotvrđeno / referentno:** GLD i SLV su američki ETF-ovi, često nedostupni EU malim ulagačima. Služe samo kao referentni niz.\n"
            )
        if g == "crypto":
            add(
                "Kripto trguje svaki kalendarski dan (3 sleeve-a), trošak 10 bps po strani, tjedna odluka je nedjeljno zatvaranje. Sharpe je ovdje s korijenom iz 252 kao i drugdje.\n"
            )
        add(table(FEEL_HEAD, feel_rows(gd["per_contender"], gd)))
        add("\nRizik i trošak (Critic ih ne kažnjava, prikazani su da ih vidite):\n")
        add(table(RISK_HEAD, risk_rows(gd["per_contender"])))
        bh = gd["buy_and_hold_reference"]
        why = {r["contender"]: ", ".join(r["reasons"]) for r in gd["not_eligible"]}
        if why:
            add(
                "\nZašto nisu podobni: "
                + "; ".join(f"{NAMES[c]}: {w}" for c, w in why.items())
                + "."
            )
        add(
            f"\nMjerilo kupi-i-drži: ukupni prinos {pct(bh['total_return'], 0)}, Sharpe {num(bh['sharpe'], 2)}, max pad {pct(bh['max_drawdown'], 0)}.\n"
        )
    add("## 7. Dijagnostike\n")
    add("### Pogled u budućnost (lookahead)\n")
    add(
        f"Svi signalni nizovi svakog suparnika moraju biti **potpuno isti** na podacima odsječenima na {12} nasumičnih datuma po tickeru (sjeme 20261014), "
        "a odluke i zatvoreni poslovi isti na jednom nasumičnom rezu. Test ne dokazuje da je pravilo dobro, samo da ne koristi budućnost.\n"
    )
    add(
        table(
            ["Algoritam", "Prolazi", "Provjera nizova", "Provjera poslova", "Greške"],
            [
                [
                    NAMES[c],
                    "DA" if v["ok"] else "NE",
                    str(v["array_checks"]),
                    str(v["trade_checks"]),
                    str(len(v["failures"])),
                ]
                for c, v in look.items()
            ],
        )
    )
    add("\n### Robusnost +-20 % (tri najbolja po očekivanju na zbroju dionica)\n")
    add(
        f"Odabrani (pravilo unaprijed): {', '.join(NAMES[c] for c in rob['selected'])}. Svaki prag se mijenja za -20 % i +20 % (jedan po jedan, ostali fiksni). "
        "**Fragilno** = bilo koja varijanta ima očekivanje <= 0 uz trošak 2x ili faktor dobiti < 1,0. Ništa se ne ugađa; ovo samo kaže koliko je rezultat krhak.\n"
    )
    for cid in rob["selected"]:
        r = rob["results"][cid]
        add(
            f"**{NAMES[cid]}**: osnovno očekivanje {eur(r['base_expectancy_eur'])} po poslu, {r['base_trades']} poslova; "
        )
        add(
            f"fragilno: **{'DA' if r['fragile'] else 'NE'}**"
            + (f" ({', '.join(r['fragile_variants'])})" if r["fragile"] else "")
            + f"; najlošije očekivanje uz 2x trošak među varijantama: {eur(r['min_expectancy_eur_cost_2x'])}.\n"
        )
        add(
            table(
                [
                    "Prag",
                    "Faktor",
                    "Vrijednost",
                    "Poslova",
                    "Očekivanje / posao",
                    "Uz trošak 2x",
                    "Faktor dobiti",
                ],
                [
                    [
                        v["param"],
                        num(v["factor"], 1),
                        (
                            num(v["value"], 0)
                            if float(v["value"]).is_integer()
                            else num(v["value"], 3)
                        ),
                        str(v["trades"]),
                        eur(v["expectancy_eur"]),
                        eur(v["expectancy_eur_cost_2x"]),
                        num(v["profit_factor"], 2),
                    ]
                    for v in r["variants"]
                ],
            )
        )
        add("")
    add("### PSR i deflated Sharpe\n")
    add(
        "**PSR** je vjerojatnost da je pravi Sharpe iznad nule (uzima u obzir iskrivljenost i debele repove). **Deflated Sharpe** je ista vjerojatnost "
        f"korigirana za broj pokušaja K = {k}: kad pokrenete mnogo pokušaja, najbolji izgleda dobro i slučajno. "
        "Obje su u tablicama rizika gore (stupci PSR i Deflated Sharpe) i informativne su; ne snižavaju ocjenu.\n"
    )
    add("## 8. Što NIJE modelirano\n")
    add(
        "- **Tečaj EUR/USD:** cijene su u USD i tretiraju se kao EUR-ekvivalent. Stvarni 1.000 EUR se pri kupnji pretvara u USD i natrag; tečaj se miče i konverzija ima trošak (ovdje 0).\n"
        "- **Dividende:** cijene su prilagođene samo za splitove, pa je to cjenovni, a ne ukupni prinos.\n"
        "- **Porezi:** nema poreza ni evidencije; savjet o porezu nije dio agenata.\n"
        "- **Minimalna provizija:** IBKR ima minimalnu proviziju po nalogu (nepotvrđeno za Petrov tarif). Ovdje je samo 2,5 bps (za 300 EUR to je 0,075 EUR). "
        "Algoritmi s mnogo malih poslova (W8, W2) su ovdje **povoljnije prikazani** nego u stvarnosti; uz trošak 2x i 3x vidite osjetljivost.\n"
        "- **Stvarna izvršenja:** nema proklizavanja izvan zadanog troška, djelomičnih ispunjenja ni ograničenja likvidnosti (važno za MRAM i ACMR); stop u jazu se ispunjava po otvaranju, a stvarni jaz na lošim vijestima može biti gori.\n"
        "- **Razlomljene dionice** i **kripto na IBKR-u**: nepotvrđeno. Kratka prodaja i poluga: nema.\n"
        "- **Podatkovna pravila** ista kao u glavnom simulatoru (povijest prije `effective_start` se ne koristi; očiti loši tickovi se ograničavaju na susjednu cijenu, popis u `summary.json`).\n"
    )
    add("## 9. Poštena upozorenja\n")
    add(
        f"- **Višestruko testiranje.** Ledger K je {k}. Devet pravila na devet grupa i mnogo tickera: najbolja ćelija tablice često je sreća. Važniji je obrazac koji drže mnoge grupe.\n"
        "- **Bik-tržište.** AI era je jaki uzlazni period; kupi-i-drži je tu težak za pobijediti, a ukupni prinos algoritama koji su većinom u gotovini je nužno manji.\n"
        "- **Grupa nije portfelj.** Zbroj sleeve-ova pretpostavlja po 1.000 EUR na svakom tickeru; to je puno veći ulog od jednog računa. Zato su 'poslova mjesečno' i 'eura mjesečno' mjera učestalosti, a ne obećanje zarade.\n"
        "- **W3** rangira unutar vlastite grupe (segment, kripto, metali); 'Sve dionice' zbraja sleeve-ove segmenata, ne rangira ponovno. Tjedna odluka je petak (nedjelja za kripto); tjedan s praznikom u petak nema odluku.\n"
        "- **Critic PASS ne postoji.** Ništa na ovoj stranici nije Critic PASS niti signal; `approved_list` ostaje prazan, Signal: PRIČEKAJ.\n"
    )
    from lab.aichain.audit_text import swing_section

    lines.extend(swing_section())
    (OUT / "SWING_ENGINE.md").write_text("\n".join(lines) + "\n")
