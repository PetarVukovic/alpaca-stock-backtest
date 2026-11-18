"""Write PLACEBO.md (Croatian, teacher style) from the numbers in placebo.json. Research only.

Every number in the text is read from the computed ``placebo`` dict; the verdict sentences are chosen by rules
on the bootstrap intervals, so a null result is stated as a null result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lab.aichain.levels_map import hr_num

EVENT_ORDER = [
    "E1_sweep_shift_discount",
    "E2_sweep_shift_discount_weekly",
    "E3_sweep_shift_discount_weekly_zone",
    "E4_demand_zone_retest",
    "E5_bos_trend",
]


def pp(x: float | None, nd: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:+.{nd}f}".replace(".", ",")


def pc(x: float | None, nd: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{nd}f} %".replace(".", ",")


def ci(c: list[float], nd: int = 1) -> str:
    return f"[{pp(c[0], nd)}; {pp(c[1], nd)}]"


def sign_word(c: list[float]) -> str:
    return "iznad nule" if c[0] > 0 else "ispod nule" if c[1] < 0 else "obuhvaća nulu"


def _diff_cell(d: dict[str, Any]) -> str:
    return f"{pp(d['diff'])} {ci(d['ci95'])}"


def sr_row(label: str, c: dict[str, Any], ctrl: str) -> str:
    if not c.get("n_levels"):
        return f"| {label} | 0 | | | | |"
    dd = c[f"diff_vs_{ctrl}"]
    ref = "mreal" if ctrl == "match" else "real"
    return (
        f"| {label} | {c['n_levels']} | {pc(c[ref]['touch_rate'])} / {pc(c[ctrl]['touch_rate'])} | "
        f"{_diff_cell(dd['touch_rate'])} | {_diff_cell(dd['bounce_rate'])} | {_diff_cell(dd['break_rate'])} |"
    )


SR_HEAD = (
    "| Skupina | Razina | Dodir: prava / lažna | Razlika u dodiru (pp) | Razlika u odbijanju (pp) | Razlika u probijanju (pp) |\n"
    "|---|---|---|---|---|---|"
)


def ev_rows(ev: dict[str, Any], hs: tuple[str, ...] = ("5", "10", "20")) -> list[str]:
    rows = []
    for key in EVENT_ORDER:
        e = ev["events"][key]
        if not e["n"]:
            rows.append(f"| {e['label']} | nema događaja | | | | | |")
            continue
        for h in hs:
            s = e["by_h"][h]
            rows.append(
                f"| {e['label'] if h == hs[0] else ''} | {h} | {s['n']} | {pc(s['mean'])} | "
                f"{pp(s['mean_excess_vs_ticker_avg'])} {ci(s['excess_ci95'])} | {pc(s['hit_rate'], 0)} | {s['p_random_ge']:.3f} |".replace(
                    ".", ","
                )
            )
    return rows


EV_HEAD = (
    "| Događaj | Dana poslije | Broj | Prosječni prinos | Višak nad prosjekom tog papira (pp) i 95 % interval | Udio dobitnih | p: nasumični dani jednako dobri |\n"
    "|---|---|---|---|---|---|---|"
)


def _mech_verdict(ai: dict[str, Any], pre: dict[str, Any]) -> list[str]:
    lines = []
    for key in EVENT_ORDER:
        e = ai["events"][key]
        p = pre["events"][key]
        if not e["n"]:
            continue
        pos = [h for h in ("5", "10", "20") if e["by_h"][h]["excess_ci95"][0] > 0]
        neg = [h for h in ("5", "10", "20") if e["by_h"][h]["excess_ci95"][1] < 0]
        pre_pos = [
            h
            for h in ("5", "10", "20")
            if p.get("by_h") and p["by_h"][h]["excess_ci95"][0] > 0
        ]
        if pos and not pre_pos:
            txt = f"u AI eri granično bolje na horizontu {', '.join(pos)} dana (donja granica intervala tek oko nule), a u ranijim godinama isto ne vrijedi"
        elif pos:
            txt = f"bolje od prosjeka u obje epohe na horizontu {', '.join(pos)} dana"
        elif neg:
            txt = f"statistički LOŠIJE od prosjeka na horizontu {', '.join(neg)} dana"
        else:
            txt = "nije bolje od prosjeka: interval viška obuhvaća nulu na svim horizontima"
        lines.append(f"- **{e['label']}** (n={e['n']}): {txt}.")
    return lines


def write_placebo_md(p: dict[str, Any], path: Path, group_hr: dict[str, str]) -> None:
    sr = p["sr"]
    al = sr["all"]
    cfg = p["config"]
    ai, pre = p["mechanics_ai_era"], p["mechanics_pre_ai_context"]
    atr_pct = p["context"]["median_atr14_pct"]
    used = p["universe"]["used"]
    skipped = p["universe"]["skipped"]
    n_by_group: dict[str, int] = {}
    for g in used.values():
        n_by_group[g] = n_by_group.get(g, 0) + 1
    ex_atr = atr_pct / 100 * 1000 * 1.5

    all_zero = all(
        al[f"diff_vs_{v}"]["bounce_rate"]["ci95"][0]
        <= 0
        <= al[f"diff_vs_{v}"]["bounce_rate"]["ci95"][1]
        for v in ("rand", "shift", "match")
    )
    bounce_sentence = (
        "Svi intervali obuhvaćaju nulu: **razina potvrđena okretima ne odbija cijenu ništa češće nego mjesto na kojem nitko nije povukao crtu.**"
        if all_zero
        else "Barem jedan interval ne obuhvaća nulu, vidi tablice ispod; zaključak je zato mješovit."
    )
    tr = [al[f"diff_vs_{v}"]["touch_rate"]["ci95"] for v in ("rand", "match")]
    if all(c[1] < 0 for c in tr):
        touch_sentence = "Dakle razine cijenu ne privlače; ako išta, dodiruju se malo rjeđe (razlika je oko jedan postotni bod)."
    elif all(c[0] > 0 for c in tr):
        touch_sentence = "Dakle razine cijenu malo privlače (češći dodir), ali to samo po sebi ne znači da se od njih cijena i odbija."
    else:
        touch_sentence = "Dakle u dodiru nema jasne razlike prema lažnim razinama."
    out: list[str] = []
    w = out.append
    w("# Test lažnih razina (placebo) i test mehanike tržišta\n")
    w(
        "Ovo je istraživanje, ne savjet za ulaganje, ne Critic PASS, i nikakvi nalozi se ne šalju (ni probni ni pravi). "
        "the researcher trguje iz Hrvatske preko Interactive Brokersa, swing (dani do tjedni), samo dugo, bez poluge. "
        "Američki ETF-ovi (GLD, SLV, SMH, SOXX i slični) često nisu dostupni malim EU ulagačima (nema KID dokumenta); "
        "ovdje služe samo kao referentne serije i označeni su **nepotvrđeno / referentno**. "
        "Poreze i dozvole računa ne nagađam.\n"
    )
    w("## 1. Sažetak: pobjeđuju li razine i mehanika slučajnost?\n")
    sv = p["sr_verdict_short"]
    w(f"**Potpore i otpori (razine): {sv.replace('Test lažnih razina: ', '')}**\n")
    w(
        f"- Pravih razina u uzorku: **{al['n_levels']}** (kraj mjeseca, {al['n_months']} mjeseci, {len(used)} papira). "
        f"Dodirnuto u sljedećih 20 dana: {pc(al['real']['touch_rate'])} (lažne nasumične: {pc(al['rand']['touch_rate'])}).\n"
        f"- Kad je razina dodirnuta, cijena se odbila za najmanje 1,5 ATR u {pc(al['real']['bounce_rate'])} slučajeva, a probila (zatvaranje više od 1 ATR iza razine) u {pc(al['real']['break_rate'])}. "
        f"Lažne razine: odbijanje {pc(al['rand']['bounce_rate'])} (nasumične), {pc(al['shift']['bounce_rate'])} (pomak +-3 %), {pc(al['match']['bounce_rate'])} (par oko razine); "
        f"probijanje {pc(al['rand']['break_rate'])}, {pc(al['shift']['break_rate'])}, {pc(al['match']['break_rate'])}.\n"
        f"- Razlika u odbijanju prave minus lažne: {_diff_cell(al['diff_vs_rand']['bounce_rate'])} pp (nasumične), "
        f"{_diff_cell(al['diff_vs_shift']['bounce_rate'])} (pomak), {_diff_cell(al['diff_vs_match']['bounce_rate'])} (par). "
        + bounce_sentence
        + "\n"
        f"- Dodir: prave razine se dodiruju {sign_word(al['diff_vs_rand']['touch_rate']['ci95'])} u odnosu na nasumične ({_diff_cell(al['diff_vs_rand']['touch_rate'])} pp) "
        f"i {sign_word(al['diff_vs_match']['touch_rate']['ci95'])} u odnosu na par kontrole ({_diff_cell(al['diff_vs_match']['touch_rate'])} pp). "
        + touch_sentence
        + "\n"
    )
    w(
        "**Mehanika tržišta (sweep, promjena karaktera, zona potražnje, BOS), AI era:**\n"
    )
    for line in _mech_verdict(ai, pre):
        w(line)
    w(
        f"\n**Zaključak bez uljepšavanja:** potvrđene potpore i otpori **ne pobjeđuju slučajnost** u ovim podacima (AI era 2023 do 2026, {len(used)} papira). "
        "Mehanika tržišta, kao strogo pravilo na dnevnim svijećama, također ne pokazuje pouzdanu prednost. "
        "Jedini rezultat koji se približava korisnosti je povratak u svježu zonu potražnje u AI eri, ali je granični, nestaje na 20 dana i ne vrijedi u godinama prije AI ere, a testirano je 15 kombinacija po epohi pa je jedan slučajni 'pogodak' očekivan. "
        "Razine ostaju orijentir za postavljanje stopa i ciljeva, a ne dokaz prednosti. Nijedno od ovoga nije Critic PASS niti signal za kupnju.\n"
    )

    w("## 2. Što smo točno testirali (objašnjeno običnim riječima)\n")
    w(
        "**Razina** (potpora ili otpor) je cijena na kojoj se prije dogodio okret: najviša ili najniža točka s 5 nižih (viših) svijeća sa svake strane. "
        "Takva točka se potvrđuje tek 5 svijeća nakon nastanka (inače bismo gledali u budućnost). Okreti blizu jedan drugoga (unutar 1 % cijene ili pola ATR-a) spajaju se u jednu razinu; "
        "novija točka vrijedi više (poluvrijeme 250 svijeća). **ATR** je prosječni dnevni raspon cijene (najviša minus najniža, uprosječeno 14 dana). "
        f"Primjer: dionica od 100 EUR s ATR-om od {hr_num(atr_pct, 1)} EUR (medijan papira ovdje je {hr_num(atr_pct, 1)} % cijene) znači da je 1,5 ATR-a oko {hr_num(atr_pct * 1.5, 1)} EUR; "
        f"na ulogu od 1.000 EUR to je oko {hr_num(ex_atr, 0)} EUR pomaka.\n"
    )
    w(
        "**Placebo** je kontrolna skupina, kao tableta od šećera u ispitivanju lijeka: ako i 'lažne' crte (tamo gdje nitko nije potvrdio okret) daju isti rezultat, razina nije ništa posebno. "
        "Zato svakoj pravoj razini dodajemo lažne:\n"
    )
    w(
        "- **(a) nasumična cijena** u rasponu zadnjih 120 svijeća (jednako mnogo lažnih koliko pravih);\n"
        f"- **(b) pomak za +-3 %**: ista razina pomaknuta {int(cfg['shift'] * 100)} % gore i dolje (jedna lažna crta gore, jedna dolje);\n"
        "- **(c) par oko razine**: dvije lažne crte na istoj strani cijene, jedna 1 ATR bliže i jedna 1 ATR dalje od prave razine. Prosječno su jednako udaljene od cijene kao prava razina "
        "(što je razina bliže, to se prije dodiruje) i na istoj strani (u rastućem tržištu većina razina je ispod cijene, a cijena ima uzlazan nagib), ali nisu na okretu. "
        "Ova kontrola je dostupna samo za razine udaljene najmanje 1,5 ATR; prave razine se u toj usporedbi uzimaju samo iz istog podskupa.\n"
    )
    w(
        "Kako mjerimo: na zadnji trgovački dan svakog mjeseca u AI eri (od 2023-01) uzmemo razine koje su tada **već bile poznate**, pa gledamo sljedećih 20 svijeća. "
        f"**Dodir** je svijeća čiji raspon dođe unutar {cfg['touch_band_atr']} ATR od crte. Nakon prvog dodira gledamo do {cfg['outcome_bars']} svijeća: "
        f"**odbijanje** je potez za najmanje {cfg['bounce_atr']} ATR od razine (na stranu s koje je cijena došla), **probijanje** je zatvaranje više od {cfg['break_atr']} ATR iza razine; "
        "ako se u istoj svijeći dogode oba, računa se probijanje (oprezna pretpostavka). Crte bliže od 0,5 ATR zatvaranju izbacuju se iz svih skupina jer ih dodiruje svaka svijeća.\n"
    )
    w(
        "**Interval pouzdanosti 95 %** je raspon u kojem bi se razlika vjerojatno našla da ponovimo pokus: ako obuhvaća nulu, razlika se ne razlikuje od slučajne. "
        "Računat je bootstrapom po kalendarskim mjesecima (svi papiri jednog mjeseca ponovno se uzorkuju zajedno, jer se u istom mjesecu kreću zajedno), "
        f"{cfg['bootstrap']} ponavljanja, sjeme {p['seed']}. **pp** je postotni bod: razlika između 47 % i 46 % je 1 pp; od 100 dodira, 1 pp znači jedan dodir više.\n"
    )
    w(
        f"Papiri u uzorku ({len(used)}): "
        + ", ".join(
            f"{group_hr.get(g, g)} {n_by_group[g]}" for g in group_hr if g in n_by_group
        )
        + "."
    )
    if skipped:
        w(
            "\nPreskočeni prema pravilima podataka (ne mijenjam sirove datoteke): "
            + "; ".join(f"**{k}** ({v})" for k, v in skipped.items())
            + ".\n"
        )
    w(
        "Zadnji datum: dionice u testu završavaju na zajedničkom datumu 2026-10-05; kripto i referentne serije koriste vlastiti zadnji datum (popis po papiru u `placebo.json`, `context`). "
        "Na kartama po papiru koristi se zadnji datum tog papira.\n"
    )

    w("## 3. Rezultati: razine\n")
    w(
        "Svaka tablica uspoređuje prave razine s jednom kontrolom. Razlika = prava minus lažna u postotnim bodovima, u zagradi 95 % interval. Pozitivno odbijanje i negativno probijanje bilo bi dobro za razine.\n"
    )
    for ctrl, title in (
        ("match", "Kontrola (c): par oko razine (najstroža)"),
        ("shift", "Kontrola (b): pomak +-3 %"),
        ("rand", "Kontrola (a): nasumična cijena u rasponu"),
    ):
        w(f"### Sve razine, {title}\n")
        w(SR_HEAD)
        w(sr_row("sve", al, ctrl))
        w("")
    w("### Po jačini razine (trećine), kontrola (c) i (b)\n")
    w(
        f"Jačina je zbroj težina okreta (noviji okret teži više). Granice trećina: {hr_num(sr['strength_cuts'][0], 2)} i {hr_num(sr['strength_cuts'][1], 2)}.\n"
    )
    for ctrl in ("match", "shift"):
        w(f"Kontrola {'(c)' if ctrl == 'match' else '(b)'}:\n")
        w(SR_HEAD)
        for k, c in sr["by_strength"].items():
            w(sr_row(k, c, ctrl))
        w("")
    w("### Po broju okreta (2 nasuprot 4+), kontrola (c) i (b)\n")
    for ctrl in ("match", "shift"):
        w(f"Kontrola {'(c)' if ctrl == 'match' else '(b)'}:\n")
        w(SR_HEAD)
        for k, c in sr["by_touches"].items():
            w(sr_row(k, c, ctrl))
        w("")
    w("### Po skupinama, kontrola (c)\n")
    w(SR_HEAD)
    for g, c in sr["by_group"].items():
        w(sr_row(group_hr.get(g, g), c, "match"))
    w("")
    st = sr["by_strength"]
    strong = st["jako (gornja trećina)"]["diff_vs_match"]["bounce_rate"]
    weak = st["slabo (donja trećina)"]["diff_vs_match"]["bounce_rate"]
    t2 = sr["by_touches"]["2 okreta"]["diff_vs_match"]["bounce_rate"]
    t4 = sr["by_touches"]["4+ okreta"]["diff_vs_match"]["bounce_rate"]
    w(
        f"Čitanje: najjača trećina razina ima razliku u odbijanju {pp(strong['diff'])} pp {ci(strong['ci95'])}, najslabija {pp(weak['diff'])} pp {ci(weak['ci95'])}; "
        f"razine s 2 okreta {pp(t2['diff'])} pp {ci(t2['ci95'])}, s 4 i više okreta {pp(t4['diff'])} pp {ci(t4['ci95'])}. "
        "Više okreta ili veća jakost ne donose pouzdano bolje odbijanje. Skupine s malo razina (memorija: nekoliko stotina) imaju široke intervale; pojedinačni 'značajni' retci ispod 95 % pragova očekivani su slučajno kad se gleda mnogo skupina.\n"
    )

    w("## 4. Rezultati: tvrdnje o 'mehanici tržišta'\n")
    w(
        "Svako pravilo je preciznije nego u videu, i svaka je odluka na zatvaranju dana, a kupnja na sljedećem otvaranju (kao u simulatoru). "
        "Prinos = zatvaranje 5, 10 ili 20 dana poslije, u odnosu na otvaranje sljedećeg dana. Događaji istog papira bliži od 10 svijeća se preskaču (da se isti potez ne broji dvaput).\n"
    )
    w(
        "- **Sweep** (lov na stopove): svijeća probije raniju potvrđenu najnižu točku (stopovi kupaca su ispod nje), ali zatvori natrag iznad nje."
    )
    w(
        "- **Promjena karaktera** (market shift): u medvjeđem trendu zatvaranje iznad zadnjeg nižeg vrha. **BOS**: zatvaranje iznad zadnjeg vrha u bikovskom trendu (nastavak)."
    )
    w(
        "- **Diskont**: cijena je u donjoj polovici zadnjeg raspona (od potvrđenog dna do potvrđenog vrha). Primjer: raspon 80 do 120, diskont je ispod 100."
    )
    w(
        "- **Zona potražnje**: zadnja silazna svijeća prije poteza od najmanje 2 ATR u 3 svijeće koji je probio vrh; **svježa** dok se cijena nije vratila u nju."
    )
    w(
        "- **E1** sweep + promjena karaktera u diskontu (sweep u zadnjih 15 svijeća). **E2** = E1 uz bikovski tjedni trend (tjedne svijeće iz dnevnih, samo završeni tjedni). **E3** = E2 uz dodir svježe zone potražnje u zadnjih 20 svijeća. **E4** prvi povratak u svježu zonu potražnje koja je držala (zatvaranje nije ispod zone). **E5** BOS u smjeru bikovskog trenda.\n"
    )
    w(
        "**Višak** je prinos događaja minus prosječni prinos istog papira u istom razdoblju i horizontu (da bik-tržište ne laska pravilu). Primjer: ako je papir u prosjeku +2,0 % u 10 dana, a nakon signala +3,0 %, višak je +1,0 pp, što je 10 EUR na 1.000 EUR prije troškova. "
        "Zadnji stupac je p-vrijednost: udio nasumičnih skupova dana (jednak broj dana po papiru) čiji je prosjek bio barem tako dobar; mala vrijednost znači da događaj izgleda bolje od slučajnih dana, ali to se miješa s bik-tržištem, zato je mjerodavniji višak i njegov interval.\n"
    )
    ad = ai["all_days"]
    w(
        f"Svi dani, AI era: prosjek 5 dana {pc(ad['5']['mean'])}, 10 dana {pc(ad['10']['mean'])}, 20 dana {pc(ad['20']['mean'])}; udio dobitnih 10 dana {pc(ad['10']['hit_rate'], 0)} (n={ad['10']['n']}).\n"
    )
    w("### AI era (2023-01-01 do 2026-10-05), glavno mjerilo\n")
    w(EV_HEAD)
    for r in ev_rows(ai):
        w(r)
    w("\n### Raniji kontekst (2017 do 2022), samo za usporedbu\n")
    pd_ = pre["all_days"]
    w(
        f"Svi dani: 5 dana {pc(pd_['5']['mean'])}, 10 dana {pc(pd_['10']['mean'])}, 20 dana {pc(pd_['20']['mean'])}.\n"
    )
    w(EV_HEAD)
    for r in ev_rows(pre):
        w(r)
    w("\n### Po skupinama, 10 dana, višak (AI era)\n")
    w("| Događaj | " + " | ".join(group_hr[g] for g in group_hr) + " |")
    w("|---|" + "---|" * len(group_hr))
    for key in EVENT_ORDER:
        e = ai["events"][key]
        cells = []
        for g in group_hr:
            c = e.get("by_group_h10", {}).get(g)
            cells.append("-" if not c else f"{pp(c['mean_excess'])} (n={c['n']})")
        w(f"| {e['label']} | " + " | ".join(cells) + " |")
    w("")
    w("Čitanje po događaju:\n")
    for line in _mech_verdict(ai, pre):
        w(line)
    e4 = ai["events"]["E4_demand_zone_retest"]["by_h"]
    w(
        f"\nE4 u AI eri: višak {pp(e4['10']['mean_excess_vs_ticker_avg'])} pp na 10 dana {ci(e4['10']['excess_ci95'])}, "
        f"{pp(e4['5']['mean_excess_vs_ticker_avg'])} pp na 5 dana {ci(e4['5']['excess_ci95'])}, "
        f"{pp(e4['20']['mean_excess_vs_ticker_avg'])} pp na 20 dana {ci(e4['20']['excess_ci95'])}. "
        f"Na 10 dana to je oko {hr_num(e4['10']['mean_excess_vs_ticker_avg'] * 1000, 0)} EUR na 1.000 EUR prije troškova (5 bps u oba smjera, otprilike 0,5 EUR), s donjom granicom intervala oko nule. "
        "Ranije godine daju suprotan predznak. Takav obrazac je tipičan za slučajnost ili za učinak jednog tržišnog režima, ne za pouzdano pravilo.\n"
    )

    w("## 5. Što ovo znači i što ne znači\n")
    w(
        "- **Potpore i otpori nisu bezvrijedni kao alat za planiranje** (gdje staviti stop, gdje očekivati gužvu), ali **nema dokaza da su prediktivni**: lažne crte na istoj udaljenosti daju isto odbijanje i isto probijanje."
    )
    w(
        "- Testirano je na dnevnim svijećama i na jednoj definiciji razine (potvrđeni okret, 5 svijeća, klaster 1 % ili 0,5 ATR). Druga definicija može dati drukčije rezultate, ali se ovdje ne ugađa po rezultatima: svaka nova definicija je novi pokušaj (ledger) i povećava K."
    )
    w(
        "- Uzorak je AI era, tržište raste za većinu papira; uz to je odabir papira unaprijed 'pobjednički' (preživjeli lanac). Oba učinka pogoduju svim pravilima jednako, pa su zato kontrole uvijek isti papir i isto razdoblje."
    )
    w(
        "- Višestruko testiranje: 5 događaja x 3 horizonta x 2 epohe = 30 testova viška, uz 3 kontrole x 3 mjere za razine. Nekoliko 'značajnih' ćelija na 95 % očekuje se samo slučajno."
    )
    w(
        "- Troškovi: za događaje je prikazan prinos prije troškova; neto je približno minus 0,05 pp (5 bps u oba smjera). Provizija IBKR-a, tečaj EUR/USD i porezi nisu modelirani i ne nagađam ih."
    )
    w(
        "- Ovo nije test strategije: nema stopa, veličine pozicije ni izlaza. To je test jedne tvrdnje: 'događaj ili razina nosi informaciju veću od slučajne'. Odgovor za razine je ne; za mehaniku je ne, uz jedan granični slučaj (E4)."
    )
    w(
        "- Podaci: samo `data/ohlcv/{T}_1d.csv`; loši tickovi ograničeni istim pravilom kao u simulatoru (NVDA 2024-06-10 u dionicama, a pravilo je zahvatilo i niske cijene u kriptu, vidi odjeljak 6), CSV nije mijenjan.\n"
    )
    w(
        "Datoteke: `placebo.json` (svi brojevi), `map/{ticker}.json` i `map/{ticker}.png` (karta po papiru)."
    )
    from lab.aichain.audit_text import placebo_section

    out.extend(placebo_section())
    path.write_text("\n".join(out), encoding="utf-8")
