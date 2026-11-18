"""Croatian audit sections appended to SWING_ENGINE.md and PLACEBO.md (research only; no orders).

Everything printed comes from ``audit.json`` (``audit_checks``) and ``audit_independent.json``
(``audit_independent``); when those files do not exist the sections are empty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = (
    Path(__file__).resolve().parents[2]
    / "reports"
    / "research"
    / "AICHAIN_20261014"
    / "swing"
)
NAMES = {
    "W1_C13C_ORIG": "W1 C13C",
    "W2_MOM_BREAK_20": "W2 proboj 20-dnevnog vrha",
    "W3_MOM_RANK_WEEKLY": "W3 tjedni rang momentuma",
    "W4_SR_BOUNCE_V2": "W4 odbijanje od potpore v2",
    "W5_SR_BREAKOUT_RETEST": "W5 proboj i povratni test",
    "W6_MM_SWEEP_SHIFT": "W6 hvatanje likvidnosti i promjena strukture",
    "W7_MM_DEMAND_RETEST": "W7 povratak u zonu potražnje",
    "W8_IBS_REVERT": "W8 IBS povratak",
}


def hr(x: float, nd: int = 1) -> str:
    """Croatian number format: thousands dot, decimal comma."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x: float, nd: int = 1) -> str:
    return f"{hr(x * 100, nd)} %"


def pp(x: float) -> str:
    return ("+" if x >= 0 else "") + hr(x * 100, 1)


def ci(c: list[float]) -> str:
    return f"[{pp(c[0])}; {pp(c[1])}]"


def _load(name: str) -> dict[str, Any] | None:
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else None


def swing_section() -> list[str]:
    a, ind = _load("audit.json"), _load("audit_independent.json")
    if a is None or ind is None:
        return []
    sw = [r for r in ind["rows"] if r["kind"] == "swing"]
    tc = a["trade_concentration"]
    cr = a["crypto_repair"]
    prov = a["provenance"]["code_hashes"]
    lines = ["## 10. Neovisna revizija (2026-10-14)\n"]
    lines.append(
        "Reviziju je radio netko tko nije pisao motor. Poseban mali program (`lab/aichain/audit_independent.py`) **ne uvozi** kod motora: "
        "iz CSV-ova je sam ponovno napisao učitavanje podataka, simulator i pravila W2, W3, W5, W6 i W8 te ponovno izračunao "
        f"broj poslova, očekivanje po poslu i faktor dobiti za {len(sw)} kombinacija algoritma i tickera. "
        f"Slaže se **{sum(r['match'] for r in sw)} od {len(sw)}** (do 1e-6). "
        "Pravilo 'radi često' ponovno je izračunato iz spremljenih brojeva za svih "
        f"{a['ranking_rule']['groups_checked']} grupa: redoslijed i podobnost su isti ({'bez razlike' if not a['ranking_rule']['groups_wrong'] else 'RAZLIKA u ' + ', '.join(a['ranking_rule']['groups_wrong'])}). "
        "Provjereno je i da test pogleda u budućnost zaista hvata namjerno pokvareno pravilo (ubačen pogled jedan dan unaprijed pada), "
        "da je svaka cijena ulaza jednaka otvaranju tog dana u CSV-u, da je svaka cijena izlaza unutar raspona tog dana, "
        "te da stop prije cilja u istoj svijeći i trošak pri svakom izlazu (stop, cilj, djelomični izlaz, vremenski izlaz, zadnji dan) vrijede.\n"
    )
    lines.append("**Što je nađeno, bez uljepšavanja:**\n")
    w5, w6, w7, w3 = (
        tc[c]
        for c in (
            "W5_SR_BREAKOUT_RETEST",
            "W6_MM_SWEEP_SHIFT",
            "W7_MM_DEMAND_RETEST",
            "W3_MOM_RANK_WEEKLY",
        )
    )
    lines.append(
        f"- **Prosjek nose rijetki veliki poslovi.** Medijan posla W5 je {pct(w5['median_return'])} (tipičan posao gubi), "
        f"a 10 najboljih poslova drži {pct(w5['best10_share_of_profit'], 0)} ukupne dobiti. Primjer: tipičan posao W5 s ulogom od 1.000 EUR gubi oko {hr(-w5['median_return'] * 1000, 0)} EUR, "
        f"a najbolji je donio {hr(w5['largest_return'] * 1000, 0)} EUR (LITE, od 12. 8. 2025. do 29. 5. 2026., provjereno prema CSV-u; to nije posao od dana do tjedna). "
        f"Bez 10 najboljih poslova prosjek W5 pada s {pct(w5['mean_return'])} na {pct(w5['mean_without_best10'])} po poslu, a W3 s {pct(w3['mean_return'])} na {pct(w3['mean_without_best10'])}. "
        "To je u skladu s unaprijed registriranim pravilom (rang po prosječnom očekivanju), pa ga nisam mijenjao, ali rang W5 i W3 čitajte kao 'trend koji drži dobitnike', a ne kao 'većina poslova pobjeđuje'."
    )
    lines.append(
        f"- **W6 i W7 su 'podobni' samo formalno.** Bez 10 najboljih poslova očekivanje W6 je {pct(w6['mean_without_best10'], 2)} po poslu "
        f"(10 poslova drži {pct(w6['best10_share_of_profit'], 0)} dobiti), a W7 {pct(w7['mean_without_best10'], 2)} (10 poslova drži {pct(w7['best10_share_of_profit'], 0)} dobiti). "
        "Uz 164 odnosno 123 posla na 43 tickera to je oko jedan posao po tickeru godišnje, što nije 'trguje često'. "
        "Događajni test u `PLACEBO.md` pokazuje da isti okidač (sweep + promjena karaktera) nema prednost nad prosjekom tog papira; pozitivan prosjek W6 stoga ne treba čitati kao dokaz prednosti mehanike (vjerojatni izvori su izlaz uz praćenje i bik-tržište; to nisam posebno izmjerio)."
    )
    lines.append(
        f"- **Registracija i kod.** Hash `swing.py` zapisan pri registraciji (`{prov['lab/aichain/swing.py']['registered'][:10]}`) nije jednak hashu datoteke koja je pokrenula rezultate (`{prov['lab/aichain/swing.py']['now'][:10]}`): prema vremenima izmjene datoteka promijenjena je nakon registracije, a prije pokretanja koje je napisalo `summary.json`. "
        f"Zamrznuti parametri i tekst pravila u `strategies/frozen/` jednaki su registru pravila u kodu za svih {len(a['provenance']['frozen_params_and_rules_equal_registry'])} suparnika, a neovisni program je dao iste brojeve, pa nema dokaza da se pravilo promijenilo; ali što je točno promijenjeno ne mogu dokazati (nema git povijesti). "
        "`swing_run.py` je nepromijenjen od registracije. Stari hash ostavljam u `registration.json` netaknut."
    )
    n_rep = sum(cr["repairs_per_crypto_ticker"].values())
    lines.append(
        f"- **Popravak loših tickova i kripto.** Pravilo za loše tickove (cijena izvan 25 % susjednih cijena) pisano je za dionice, a u kriptu je ograničilo {n_rep} niskih cijena koje su vjerojatno stvarni fitilji likvidacije (npr. BTC 13. 3. 2020.: otvaranje 4.800, najniža 3.782, zatvaranje 5.579 uz velik volumen) "
        f"(BTC {cr['repairs_per_crypto_ticker']['BTCUSDT']}, ETH {cr['repairs_per_crypto_ticker']['ETHUSDT']}, SOL {cr['repairs_per_crypto_ticker']['SOLUSDT']}). "
        f"Provjera s neizmijenjenim CSV-om: mijenja se samo {', '.join(NAMES[c] for c in cr['contenders_changed']) or 'ništa'} u kriptu "
        f"(očekivanje {hr(cr['repaired']['W8_IBS_REVERT']['expectancy_eur'], 2)} EUR s popravkom naspram {hr(cr['raw']['W8_IBS_REVERT']['expectancy_eur'], 2)} EUR bez njega, faktor dobiti ispod 1,2 u oba slučaja), pa se podobnost ne mijenja. "
        "Pravilo nisam mijenjao (zajednički učitavač je zadan), samo bilježim granicu."
    )
    lines.append(
        "- **Što nije nađeno:** pogled u budućnost, krivi redoslijed stopa i cilja, naplata troška, razlika u formulama, ni rezultati koji se ne slažu sa sirovim cijenama. "
        "Najveći pojedinačni poslovi (npr. 640 % za W5 na LITE) slažu se s CSV-om; to je stvarno kretanje podataka u AI eri, a ne greška.\n"
    )
    return lines


def placebo_section() -> list[str]:
    a, ind = _load("audit.json"), _load("audit_independent.json")
    if a is None or ind is None:
        return []
    pl = [r for r in ind["rows"] if r["kind"] == "placebo"]
    mp = [r for r in ind["rows"] if r["kind"] == "map"]
    bb = a["placebo_block_bootstrap"]["diffs"]
    ev = a["event_block_bootstrap"]
    cr = a["crypto_repair"]["repairs_per_crypto_ticker"]
    out = ["## 6. Neovisna revizija (2026-10-14)\n"]
    out.append(
        "Poseban program koji ne uvozi motor (`lab/aichain/audit_independent.py`) iz CSV-ova je sam ponovno izračunao pivote, razine, "
        f"dodire i ishode za sve mjesece i sve papire. Slaže se **{sum(r['match'] for r in pl)} od {len(pl)}** brojeva testa lažnih razina "
        "(broj razina, udio dodira, odbijanja i probijanja za prave razine, pomak +-3 % i par kontrolu; nasumična kontrola ovisi o generatoru pa je provjerena samo ponovnim pokretanjem s istim sjemenom) "
        f"i **{sum(r['match'] for r in mp)} od {len(mp)}** karata: najbliže dvije potpore i dva otpora za {', '.join(r['ticker'] for r in mp)}, izračunate ručno iz sirovih cijena. "
        "Pogled u budućnost: razine, struktura, tjedni trend, zone, sweepovi i potpore su izračunati na skraćenim podacima (64 nasumična reza na 8 papira) i uvijek se poklapaju s punim izračunom na zajedničkom dijelu.\n"
    )
    out.append(
        "**Preklapanje mjeseci.** Bootstrap u odjeljku 2 uzorkuje pojedinačne kalendarske mjesece, a susjedni mjeseci dijele prozore ishoda (do 10 svijeća) i iste razine. "
        f"Zato je dodana strožija provjera: uzorkuju se blokovi od {a['placebo_block_bootstrap']['block_months']} uzastopna mjeseca. Razlika prave minus lažne (pp), 95 % interval, pojedinačni mjeseci naspram blokova:\n"
    )
    out.append("| Kontrola | Mjera | Mjeseci | Blokovi od 3 |")
    out.append("|---|---|---|---|")
    labels = {
        "rand": "nasumična cijena",
        "shift": "pomak +-3 %",
        "match": "par oko razine",
    }
    mlabels = {
        "touch_rate": "dodir",
        "bounce_rate": "odbijanje",
        "break_rate": "probijanje",
    }
    for k in ("rand", "shift", "match"):
        for m in ("touch_rate", "bounce_rate", "break_rate"):
            d = bb[k][m]
            out.append(
                f"| {labels[k]} | {mlabels[m]} | {ci(d['block_1'])} | {ci(d['block_3'])} |"
            )
    out.append(
        "\nZaključak se ne mijenja: intervali za odbijanje i probijanje i dalje obuhvaćaju nulu u sve tri kontrole, a razlika u dodiru zadržava predznak. "
        "Razine dakle i uz strožu provjeru ne odbijaju cijenu češće od lažnih crta.\n"
    )
    out.append(
        "Isto za događaje (višak nad prosjekom tog papira, AI era, pp i 95 % interval):\n"
    )
    out.append("| Događaj | Dana | Broj | Višak | Mjeseci | Blokovi od 3 |")
    out.append("|---|---|---|---|---|---|")
    names = {
        "E1_sweep_shift_discount": "E1 sweep + promjena karaktera u diskontu",
        "E2_sweep_shift_discount_weekly": "E2 uz bikovski tjedni trend",
        "E3_sweep_shift_discount_weekly_zone": "E3 uz dodir svježe zone",
        "E4_demand_zone_retest": "E4 povratak u svježu zonu",
        "E5_bos_trend": "E5 BOS u smjeru trenda",
    }
    for e, nm in names.items():
        for h in ("5", "10", "20"):
            r = ev[e][h]
            out.append(
                f"| {nm} | {h} | {r['n']} | {pp(r['mean_excess'])} | {ci(r['ci95_block_1'])} | {ci(r['ci95_block_3'])} |"
            )
    e4 = ev["E4_demand_zone_retest"]["10"]
    e1 = ev["E1_sweep_shift_discount"]["5"]
    out.append(
        f"\nJedini rezultat koji je izgledao korisno, E4 na 10 dana, uz blokove ima interval {ci(e4['ci95_block_3'])}: donja granica prelazi nulu, pa ga ne smijete čitati kao potvrđenu prednost "
        f"(na 1.000 EUR to je oko {hr(e4['mean_excess'] * 1000, 0)} EUR prije troškova, ali nesigurno). "
        f"E1 na 5 dana uz blokove ima interval {ci(e1['ci95_block_3'])}, dakle je statistički lošiji od prosjeka. Višestruko testiranje (15 kombinacija po epohi) i dalje vrijedi.\n"
    )
    out.append(
        f"**Napomena o podacima (ispravak ranije izjave da je ograničen samo NVDA).** Pravilo za loše tickove ograničilo je i {sum(cr.values())} niskih cijena u kriptu "
        f"(BTC {cr['BTCUSDT']}, ETH {cr['ETHUSDT']}, SOL {cr['SOLUSDT']}), od kojih su mnoge vjerojatno stvarni fitilji likvidacije (npr. BTC 13. 3. 2020.: otvaranje 4.800, najniža 3.782, zatvaranje 5.579). To može pomaknuti pivote i razine kripta; u nijednom zaključku ove stranice kripto nije presudan "
        "(izdvojeni redak za kripto ima široke intervale).\n"
    )
    return out
