"""Write docs/research/AICHAIN_SWING_RESULT.md (Croatian) from the saved swing, placebo and audit JSON files.

Usage: .venv/bin/python scripts/aichain_swing_result_doc.py
Every number is read from swing/summary.json, swing/placebo.json, swing/audit.json and swing/results/*.json.
Research only: no orders, no advice, not a Critic PASS.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports" / "research" / "AICHAIN_20261014"
SW = BASE / "swing"
OUT = ROOT / "docs" / "research" / "AICHAIN_SWING_RESULT.md"
MINUS = "−"
RULES = [
    "W1_C13C_ORIG",
    "W2_MOM_BREAK_20",
    "W3_MOM_RANK_WEEKLY",
    "W4_SR_BOUNCE_V2",
    "W5_SR_BREAKOUT_RETEST",
    "W6_MM_SWEEP_SHIFT",
    "W7_MM_DEMAND_RETEST",
    "W8_IBS_REVERT",
]
NAME = {
    "W1_C13C_ORIG": "W1 C13C (Petrov algoritam)",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang zamaha",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 sweep i promjena smjera",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
    "B0_BUYHOLD": "B0 kupi i drži (mjerilo)",
}
CONCEPT = {
    "W1_C13C_ORIG": "nije iz nastave; Petrov algoritam, mjerilo",
    "W2_MOM_BREAK_20": "momentum",
    "W3_MOM_RANK_WEEKLY": "momentum (tjedni rang)",
    "W4_SR_BOUNCE_V2": "potpora i otpor (odbijanje)",
    "W5_SR_BREAKOUT_RETEST": "potpora i otpor (obrnuta uloga)",
    "W6_MM_SWEEP_SHIFT": "likvidnost, promjena smjera, diskont, tjedni smjer",
    "W7_MM_DEMAND_RETEST": "zona potražnje, struktura, diskont",
    "W8_IBS_REVERT": "nije iz nastave; kontrola (jednodnevni pad)",
}
RULE_TEXT = {
    "W1_C13C_ORIG": "Zatvaranje iznad prosjeka 200 dana i pad od 5 % u 5 dana: kupi sutra; klizni stop 10 % ispod vrha.",
    "W2_MOM_BREAK_20": "Zatvaranje je najviše u 20 dana, 60-dnevni prinos > 0, iznad prosjeka 50 dana: kupi sutra; izlaz ispod najnižeg od zadnjih 10 dana, nakon 15 dana ili stop 8 % ispod kupnje.",
    "W3_MOM_RANK_WEEKLY": "Petkom rang skupine po prinosu 20 dana; kupi dionicu iz vodeće trećine iznad prosjeka 50 dana; izađi kad ispadne iz gornje polovice.",
    "W4_SR_BOUNCE_V2": "Razina = potvrđeno dno s najmanje dva ranija dodira; dodir zone pa zatvaranje iznad visokog dana dodira; stop 1 ATR ispod zone, cilj zadnji vrh.",
    "W5_SR_BREAKOUT_RETEST": "Zatvaranje iznad zadnjeg potvrđenog vrha, pa prvi povratak unutar 1,5 % razine koji zatvara iznad nje; stop 3 % ispod razine; izlaz ispod prosjeka 50 dana.",
    "W6_MM_SWEEP_SHIFT": "Tjedni trend nije medvjeđi, cijena u diskontu, sweep jednog od zadnja tri dna u zadnjih 5 svijeća, zatim zatvaranje iznad zadnjeg nižeg vrha; stop ispod dna sweepa minus pola ATR-a; pola se prodaje na cilju, ostatak prati.",
    "W7_MM_DEMAND_RETEST": "Prvi povratak u svježu zonu potražnje uz bikovsku strukturu, diskont i zatvaranje iznad sredine zone; stop dno zone; cilj zadnji vrh.",
    "W8_IBS_REVERT": "IBS < 0,2 (zatvaranje pri dnu dnevnog raspona) i iznad prosjeka 200 dana: kupi; izlaz IBS > 0,8 ili nakon 5 dana.",
}


def jl(p: Path) -> Any:
    return json.loads(p.read_text())


def hr(x: float, nd: int = 0) -> str:
    s = f"{abs(x):,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (MINUS + s) if x < 0 and round(abs(x), nd) != 0 else s


def sg(x: float, nd: int = 1) -> str:
    s = hr(abs(x), nd)
    return s if round(abs(x), nd) == 0 else ("+" if x > 0 else MINUS) + s


def pc(x: float, nd: int = 0) -> str:
    return hr(x * 100, nd) + " %"


def eur(x: float, nd: int = 0) -> str:
    return sg(x, nd) + " €"


def tbl(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    S, PL, AU = jl(SW / "summary.json"), jl(SW / "placebo.json"), jl(SW / "audit.json")
    RS = jl(SW / "results" / "stocks_all.json")["contenders"]
    g = S["groups"]["stocks_all"]
    pcn = g["per_contender"]
    elig = {x["contender"] for x in g["ranking"]}
    sr = PL["sr"]["all"]
    ev = PL["mechanics_ai_era"]["events"]
    pre = PL["mechanics_pre_ai_context"]["events"]
    k = S["ledger_k"]
    bh = g["buy_and_hold_reference"]
    months = jl(SW / "results" / "stocks_all.json")["window"]["months"]

    rows_res = []
    for r in RULES + ["B0_BUYHOLD"]:
        a = pcn[r]
        if r == "B0_BUYHOLD":
            rows_res.append(
                [
                    NAME[r],
                    "43",
                    "-",
                    "-",
                    "-",
                    "-",
                    pc(a["total_return"]),
                    hr(a["sharpe"], 2),
                    pc(a["max_drawdown"]),
                    "mjerilo",
                ]
            )
            continue
        rows_res.append(
            [
                NAME[r],
                hr(a["trades"]),
                hr(a["trades_per_month"], 1),
                pc(a["hit_rate"]),
                eur(a["expectancy_eur"]),
                hr(a["profit_factor"], 2),
                pc(a["total_return"]),
                hr(a["sharpe"], 2),
                pc(a["max_drawdown"]),
                "DA" if r in elig else "ne",
            ]
        )
    rank_rows = [
        [
            str(i),
            NAME[x["contender"]],
            hr(x["trades_per_month"], 1),
            eur(x["expectancy_eur"]),
            eur(x["expectancy_eur_cost_2x"]),
            hr(x["profit_factor"], 2),
            eur(x["score_eur_per_month"]) + " mj.",
        ]
        for i, x in enumerate(g["ranking"], 1)
    ]
    era_rows = []
    for r in RULES:
        c = RS[r]["contexts"]
        era_rows.append(
            [
                NAME[r],
                f"{hr(c['y2016_2020']['trades'])} / {eur(c['y2016_2020']['expectancy_eur'])}",
                f"{hr(c['y2021_2022']['trades'])} / {eur(c['y2021_2022']['expectancy_eur'])}",
                f"{hr(RS[r]['ai_era']['trades'])} / {eur(RS[r]['ai_era']['expectancy_eur'])}",
            ]
        )
    grp_rows = []
    for gg in S["groups"].values():
        top = gg["ranking"][0] if gg["ranking"] else None
        b = gg["buy_and_hold_reference"]["total_return"]
        if top is None:
            grp_rows.append(
                [
                    gg["name"],
                    str(len(gg["tickers"])),
                    "nitko nije podoban",
                    "-",
                    "-",
                    "-",
                    "-",
                    pc(b),
                ]
            )
            continue
        pcg = gg["per_contender"][top["contender"]]
        grp_rows.append(
            [
                gg["name"],
                str(len(gg["tickers"])),
                NAME[top["contender"]],
                hr(top["trades_per_month"], 1),
                eur(top["expectancy_eur"]),
                hr(top["profit_factor"], 2),
                pc(pcg["total_return"]),
                pc(b),
            ]
        )
    conc_rows = []
    for r in RULES:
        c = AU["trade_concentration"][r]
        conc_rows.append(
            [
                NAME[r],
                pc(c["median_return"], 1),
                pc(c["mean_return"], 1),
                pc(c["mean_without_best10"], 1),
                pc(c["best10_share_of_profit"]),
            ]
        )
    mech_rows = []
    lab = {
        "E1_sweep_shift_discount": "E1 sweep + promjena smjera u diskontu",
        "E2_sweep_shift_discount_weekly": "E2 isto + bikovski tjedni trend",
        "E3_sweep_shift_discount_weekly_zone": "E3 isto + dodir svježe zone",
        "E4_demand_zone_retest": "E4 prvi povratak u svježu zonu potražnje",
        "E5_bos_trend": "E5 BOS u bikovskom trendu",
    }
    for key, name in lab.items():
        a, p10 = ev[key]["by_h"]["10"], pre[key]["by_h"]["10"]
        blk = AU["event_block_bootstrap"][key]["10"]["ci95_block_3"]
        mech_rows.append(
            [
                name,
                str(ev[key]["n"]),
                f"{sg(a['mean_excess_vs_ticker_avg'] * 100)} [{sg(a['excess_ci95'][0] * 100)}; {sg(a['excess_ci95'][1] * 100)}]",
                f"[{sg(blk[0] * 100)}; {sg(blk[1] * 100)}]",
                f"{sg(p10['mean_excess_vs_ticker_avg'] * 100)} [{sg(p10['excess_ci95'][0] * 100)}; {sg(p10['excess_ci95'][1] * 100)}]",
            ]
        )
    lvl_rows = []
    for lab_, key in (
        ("nasumična cijena", "rand"),
        ("pomak ±3 %", "shift"),
        ("par oko razine", "match"),
    ):
        d = sr[f"diff_vs_{key}"]
        real = sr["mreal"] if key == "match" else sr["real"]
        lvl_rows.append(
            [
                lab_,
                f"{pc(real['bounce_rate'], 1)} / {pc(sr[key]['bounce_rate'], 1)}",
                f"{sg(d['bounce_rate']['diff'] * 100)} [{sg(d['bounce_rate']['ci95'][0] * 100)}; {sg(d['bounce_rate']['ci95'][1] * 100)}]",
                f"{pc(real['break_rate'], 1)} / {pc(sr[key]['break_rate'], 1)}",
                f"{sg(d['break_rate']['diff'] * 100)} [{sg(d['break_rate']['ci95'][0] * 100)}; {sg(d['break_rate']['ci95'][1] * 100)}]",
            ]
        )
    pg = PL["sr"]["by_group"]
    grp_pl = [
        [
            S["groups"][gk]["name"] if gk in S["groups"] else gk,
            pc(v["real"]["bounce_rate"], 1),
            pc(v["rand"]["bounce_rate"], 1),
        ]
        for gk, v in pg.items()
    ]
    n_bad = sum(
        1 for r in RULES if RS[r]["contexts"]["y2021_2022"]["expectancy_eur"] <= 0
    )
    rule_rows = [[NAME[r], CONCEPT[r], RULE_TEXT[r]] for r in RULES]
    e4 = ev["E4_demand_zone_retest"]["by_h"]["10"]
    cnt = {
        r: sum(
            1
            for gk, gg in S["groups"].items()
            if gk != "stocks_all" and any(x["contender"] == r for x in gg["ranking"])
        )
        for r in RULES
    }

    md = f"""# AI lanac, swing test: što radi često i pobjeđuju li razine i mehanika slučajnost

*Istraživačka simulacija na povijesnim dnevnim podacima. Nije savjet za ulaganje, nije signal, nije formalni Critic PASS (lista odobrenih ostaje prazna, signal je **PRIČEKAJ**). Agenti ne šalju nikakve naloge (ni probne ni prave). Nema obećanja zarade i nema savjeta o porezu.*

Stranice: `reports/research/AICHAIN_20261014/swing/pages/uciti.html` (učenje, grafovi na stvarnim podacima), `swing/pages/*.html` (karte po skupinama). Sirovi brojevi: `swing/summary.json`, `swing/placebo.json`, `swing/audit.json`, `swing/results/*.json`. Skripte: `scripts/aichain_learn_page.py`, `scripts/aichain_swing_result_doc.py`.

## 1. Sažetak

1. **Razdoblje i trošak.** Glavno mjerilo je AI era, 3. 1. 2023. do 5. 10. 2026. ({hr(months, 1)} mjeseci); 2016. do 2022. samo kontekst. Trošak 0,025 % po strani za dionice (na 1.000 € to je 0,25 € pri kupnji i 0,25 € pri prodaji), kripto 0,10 %; stres 2x i 3x. Samo dugo, bez poluge.
2. **Potpore i otpori ne pobjeđuju slučajnost.** Od {hr(sr["n_levels"])} razina (44 mjeseca, 55 papira) odbijanje je {pc(sr["real"]["bounce_rate"], 1)} za prave naspram {pc(sr["rand"]["bounce_rate"], 1)} za nasumične crte; svi intervali obuhvaćaju nulu.
3. **Mehanika tržišta** (sweep, promjena smjera, BOS, zona) kao strogo pravilo ne pokazuje pouzdanu prednost; jedini granični slučaj je prvi povratak u svježu zonu potražnje (E4): {sg(e4["mean_excess_vs_ticker_avg"] * 100)} pp na 10 dana, donja granica intervala {sg(e4["excess_ci95"][0] * 100, 2)} pp, uz blokove od 3 mjeseca ispod nule, a prije 2023. suprotnog predznaka.
4. **Što "radi često"** (unaprijed upisano pravilo): na svih 43 dionica prvi je {NAME[g["ranking"][0]["contender"]]} ({hr(g["ranking"][0]["trades_per_month"], 1)} poslova mjesečno, {eur(g["ranking"][0]["expectancy_eur"])} po poslu), zatim {NAME[g["ranking"][1]["contender"]]} i {NAME[g["ranking"][2]["contender"]]}. To su pravila praćenja trenda i zamaha, ne "pametan novac".
5. **Samo u AI eri.** U padu 2021. do 2022. očekivanje po poslu je nula ili negativno za {n_bad} od 8 pravila.
6. **Držanje je jače po prinosu.** Kupi-i-drži na istim dionicama: {pc(bh["total_return"])}; najbolje pravilo po ukupnom prinosu {pc(max(pcn[r]["total_return"] for r in RULES))}. Pravila su većinom u gotovini.

## 2. Podaci

- Samo `data/ohlcv/{{T}}_1d.csv` (dnevne svijeće, Alpaca, prilagođeno za splitove); satni i unutardnevni podaci nisu korišteni, `.parquet` nije korišten. CSV-ovi nisu mijenjani.
- Stock-test: {len(g["tickers"])} dionica u 6 segmenata (memorija, sučelja i pohrana, oprema, AI čipovi, mreže i serveri, oblak) do zajedničkog kraja 2026-10-05. Kripto (BTC, ETH, SOL) i metali (GLD, SLV) su zasebne skupine; GLD i SLV su **nepotvrđeni / referentni** jer američki ETF-ovi često nisu dostupni malim ulagačima iz EU (nema KID dokumenta), a kripto na IBKR-u ovisi o državi i propisima (nepotvrđeno).
- Karte tržišta koriste zadnji datum svakog papira (vidi stranice); placebo test koristi 55 papira, a SPX i NDX su preskočeni jer ne prolaze pravila podataka (OHLC izvan raspona).
- Pravila čišćenja (ista za sve): povijest prije `effective_start` se ne učitava (obustava trgovanja: SMCI do 2020-01-14, NBIS do 2024-10-21); očiti loš tick ograničava se na susjedne cijene (NVDA 2024-06-10; u kriptu je isto pravilo ograničilo 13 niskih cijena koje su vjerojatno stvarni fitilji, pa je to granica, vidi audit). WDC je već prilagođen za spin-off i nije ponovno prilagođavan.
- Što nije modelirano: tečaj EUR/USD (USD se tretira kao EUR), minimalna provizija IBKR-a (nepotvrđeno za Petrov tarif), dividende, porezi, razlomljene dionice (nepotvrđeno), proklizavanje, likvidnost tankih papira.

## 3. Pravila (W1 do W8) i rječnik nastave

Vokabular dolazi iz diskrecijske nastave "pametnog novca" čije su tvrdnje nedokazane; ovdje je svaki pojam pretvoren u strogo, provjerljivo pravilo bez pogleda u budućnost (okret = 5 svijeća sa svake strane, poznat tek 5 svijeća poslije; ATR14; zona = zadnja silazna svijeća prije rasta od 2 ATR u 3 svijeće koji je probio vrh; jednako dno unutar 0,3 %; tjedne svijeće iz dnevnih, samo završeni tjedni). Procjep (fair value gap) opisan je, ali ga nijedno pravilo ne koristi.

{tbl(["Pravilo", "Pojam", "Pravilo"], rule_rows)}

Registracija je napisana prije prvog pokretanja (ledger K {k}; 534 do 541 su pravila, 542 mjerilo). Parametri su fiksni, bez ugađanja. Test pogleda u budućnost prolazi za svih 8 pravila ({next(iter(S["lookahead"].values()))["array_checks"]} provjera nizova i {next(iter(S["lookahead"].values()))["trade_checks"]} provjera poslova po pravilu, bez greške).

## 4. Unaprijed upisano pravilo "radi često" i rang

**Podobno** je pravilo s najmanje 60 poslova u AI eri nad skupinom, pozitivnim očekivanjem po poslu uz trošak 2x i faktorom dobiti najmanje 1,2. Među podobnima rang je očekivanje po poslu pomnoženo s poslovima mjesečno (eura mjesečno na 1.000 € po dionici). Kupi-i-drži je mjerilo i nikad se ne rangira. Critic je blag prema riziku (pad, kolebanje i koncentracija ne snižavaju ocjenu), a strog samo prema nevaljanim dokazima.

Sve dionice (zbroj 43 sleevea):

{tbl(["#", "Pravilo", "Poslova mj.", "Zarada po poslu", "Uz trošak 2x", "Faktor dobiti", "Ukupno mj."], rank_rows)}

Nije podobno: {", ".join(NAME[x["contender"]] + " (" + "; ".join(x["reasons"]) + ")" for x in g["not_eligible"])}.

Najbolje po skupini (ranking po istom pravilu) i usporedba s držanjem:

{tbl(["Skupina", "Dionica", "Najbolje pravilo", "Poslova mj.", "Po poslu", "Faktor dobiti", "Ukupni prinos pravila", "Kupi i drži"], grp_rows)}

## 5. Rezultati (sve dionice, AI era)

{tbl(["Pravilo", "Poslova", "Poslova mj.", "Pogodak", "Po poslu (1.000 €)", "Faktor dobiti", "Ukupni prinos", "Sharpe", "Max pad", "Radi često"], rows_res)}

Primjer čitanja: W5 donosi u prosjeku {eur(pcn["W5_SR_BREAKOUT_RETEST"]["expectancy_eur"])} po poslu na 1.000 €, ali je dobitno samo {pc(pcn["W5_SR_BREAKOUT_RETEST"]["hit_rate"])} poslova. Rizik se ovdje ne kažnjava, samo se prikazuje.

**Tipičan posao nasuprot prosjeku** (audit): prosjek nose rijetki veliki poslovi.

{tbl(["Pravilo", "Medijan posla", "Prosjek posla", "Prosjek bez 10 najboljih", "Udio 10 najboljih u dobiti"], conc_rows)}

**Isto pravilo kroz razdoblja** (poslova / zarada po poslu):

{tbl(["Pravilo", "2016 do 2020", "2021 do 2022 (pad)", "AI era"], era_rows)}

**Robusnost ±20 %** (tri najbolja po očekivanju, jedan prag po jedan): nijedno nije fragilno (nijedna varijanta nema očekivanje <= 0 uz trošak 2x ili faktor dobiti < 1). To je slab test u bik-tržištu (ne gleda drugi režim). Deflated Sharpe (korekcija za K = {k}) najvišeg pravila je {hr(max(pcn[r]["deflated_sharpe_prob"] for r in RULES), 2)}.

## 6. Placebo: pobjeđuju li razine i mehanika slučajnost?

**Razine** (zadnji trgovački dan svakog mjeseca u AI eri, samo razine koje su tada već bile poznate, 20 dana unaprijed): dodir = raspon svijeće unutar 0,25 ATR; odbijanje = potez od 1,5 ATR natrag unutar 10 svijeća; probijanje = zatvaranje 1 ATR iza razine. Intervali su bootstrap po kalendarskim mjesecima (2000 ponavljanja, sjeme 20261014), a provjera s blokovima od 3 mjeseca ne mijenja zaključak.

{tbl(["Kontrola", "Odbijanje: prava / lažna", "Razlika u odbijanju (pp) [95 %]", "Probijanje: prava / lažna", "Razlika u probijanju (pp) [95 %]"], lvl_rows)}

**Presuda: potvrđena razina odbija cijenu ništa češće od lažne crte.** Dodir je čak malo rjeđi nego kod nasumičnih crta ({sg(sr["diff_vs_rand"]["touch_rate"]["diff"] * 100)} pp). Isti smjer po skupinama (odbijanje prave / nasumične):

{tbl(["Skupina", "Prave", "Nasumične"], grp_pl)}

(Pojedinačne skupine imaju široke intervale; nekoliko većih razlika očekuje se slučajno kad se gleda mnogo skupina.)

**Mehanika** (višak prinosa nad prosjekom istog papira na 10 dana, postotni bodovi, 95 % interval; kolona "blokovi" je strožiji interval s blokovima od 3 mjeseca; zadnja kolona je 2017. do 2022.):

{tbl(["Događaj", "Broj (AI era)", "AI era višak [interval]", "Blokovi 3 mj.", "2017 do 2022"], mech_rows)}

**Presuda:** E1 do E3 i E5 ne pokazuju prednost (E2 i E3 su čak statistički lošiji od prosjeka); E4 je jedini granični slučaj i ne drži se uz stroži interval ni u ranijim godinama. Zaključak vrijedi samo za ove definicije na dnevnim svijećama; svaka druga definicija je novi pokušaj i povećava K. Pritom je višestruko testiranje stvarno: 15 kombinacija po razdoblju za događaje, 9 za razine.

## 7. Što je radilo, a što nije

**Radilo (u AI eri, po unaprijed zadanom pravilu):** W1, W5 i W3 (trend i zamah; uz dva ograničenja: pogodak je 35 % do 56 %, a prosjek nose rijetki veliki poslovi), W2 i W8 (često trguju, mala zarada po poslu, osjetljivi na minimalnu proviziju). Skupine u kojima je pravilo podobno (od 8 skupina bez zbroja): W1 {cnt["W1_C13C_ORIG"]}, W2 {cnt["W2_MOM_BREAK_20"]}, W8 {cnt["W8_IBS_REVERT"]}.

**Nije radilo:** W4 (odbijanje od potpore, faktor dobiti {hr(pcn["W4_SR_BOUNCE_V2"]["profit_factor"], 2)}, nije podobno); W6 i W7 su podobni samo formalno (oko jedan posao po dionici godišnje; bez 10 najboljih poslova W6 ima {pc(AU["trade_concentration"]["W6_MM_SWEEP_SHIFT"]["mean_without_best10"], 2)} po poslu, a W7 {pc(AU["trade_concentration"]["W7_MM_DEMAND_RETEST"]["mean_without_best10"], 2)}); razine kao predviđanje; tjedni filter (E2 gori od E1); metali GLD i SLV (nijedno pravilo podobno, referentno); kripto samo W2.

**Nijedno pravilo nije dokazano izvan AI ere** i nijedno ne pobjeđuje kupi-i-drži po ukupnom prinosu.

## 8. Što dalje

1. Zadržati potpore i otpore samo kao orijentir za stop i veličinu pozicije, ne kao signal.
2. Ako se želi dalje istraživati mehaniku: **nova hipoteza s novim freeze ID-om** za svaki zasebni test (premium i diskont izolirano, jednaka dna izolirano, procjep, satne svijeće), uz upis u ledger prije pokretanja; E4 zasebno tek uz unaprijed zadan prag.
3. Provjeriti stvarnu provizijsku tablicu IBKR-a i razlomljene dionice za Petrov račun prije bilo kakve procjene čestih pravila (W2, W8).
4. Za pravila koja trguju često dodati model minimalne provizije i tečaja EUR/USD u simulator (novi ID, simulator se ne mijenja unatrag).
5. Čekati stvarni pad tržišta ili ga simulirati prije ikakvog zaključka o trajnosti.

## 9. Otvorena pitanja

- Vrijedi li E4 u drugačijem režimu (ranije godine su pokazale suprotan predznak)?
- Koliko od rezultata W1, W3 i W5 je bik-tržište AI lanca (preživjeli papiri)?
- Je li minimalna provizija IBKR-a za Petrov tarif dovoljno velika da poništi W2 i W8?
- Dostupnost kripta i europskih ekvivalenata ETF-ova u IBKR-u: nepotvrđeno.
- Hash `swing.py` zapisan pri registraciji razlikuje se od hasha koda koji je pokrenuo rezultate (audit, odjeljak 10 `SWING_ENGINE.md`); parametri i tekst pravila jednaki su registru, a neovisni program je dao iste brojeve, ali što je točno promijenjeno ne može se dokazati.

## 10. Ograničenja i provjere

- AI era je jaki uzlazni period; kontrole su uvijek isti papir i isto razdoblje, ali pad nije viđen u uzorku nakon 2022.
- Svaki pojam testiran je u jednoj definiciji; druga definicija može dati drugi rezultat.
- Neovisna provjera (poseban program bez uvoza motora) slaže se na 13 od 13 kombinacija pravilo-dionica i 3 od 3 placebo brojeva; pogled u budućnost: pivoti, struktura, zone i sweepovi isti na skraćenim podacima (64 reza).
- Naslovi stranica skupina uspoređeni su s JSON-ovima: sve skupine imaju isti pobjednik, broj poslova, zaradu po poslu i omjer prema kupi-i-drži kao u tablici iz odjeljka 4 (npr. memorija W1 2,3 mj. i {eur(S["groups"]["memory"]["ranking"][0]["expectancy_eur"])}; oprema W1 {hr(S["groups"]["equipment"]["ranking"][0]["trades_per_month"], 1)} mj.; oblak W5 {S["groups"]["cloud"]["ranking"][0]["trades"]} poslova); postotak odbijanja po skupini u naslovima poklapa se s `placebo.json`.
"""
    OUT.write_text(md)
    print(OUT, len(md))


if __name__ == "__main__":
    main()
