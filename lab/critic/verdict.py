"""Runs the ordered gate, renders the Croatian verdict .md, and guards approved_list.json."""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from lab.contracts import (
    ApprovedEntry,
    ApprovedList,
    CriticCheck,
    CriticVerdict,
    Verdict,
)
from lab.critic import checks as c
from lab.critic.checks import CriticConfig, CriticInputs

# Everyday one-sentence explanation per check, shown in the verdict (Croatian, beginner level).
EXPLANATIONS: dict[int, str] = {
    0: "Kao da prije kuhanja provjeriš jesu li namirnice svježe: ako su podaci kvarni, rezultat ne vrijedi.",
    1: "Kao da ti na ispitu nitko ne smije šapnuti odgovore: pravilo smije koristiti samo ono što se tada znalo.",
    2: "Kao da pri ispitu ne smiješ potajno promijeniti odgovor nakon predaje: pravilo je zamrznuto prije testa.",
    3: "Kao da kruh mora biti dobar i u svibnju i u listopadu: zarada mora imati isti smjer u starom i novijem razdoblju.",
    4: "Kao da ne ocjenjuješ restoran po jednom ručku: treba dovoljno trgovina da to nije slučajnost.",
    5: "Kao da učenik ne smije vidjeti ispitna pitanja dok uči: završno razdoblje nije smjelo utjecati na postavke.",
    6: "Kao da recept mora uspjeti i s malo više ili manje soli: mali pomak postavki ne smije uništiti zaradu.",
    7: "Kao da računaš put i kad gorivo poskupi dvostruko: zarada mora preživjeti dvostruke troškove.",
    8: "Kao da dobar nogometaš mora igrati i na tuđem terenu: pravilo mora raditi na više dionica, a ne ovisiti o tri sretna poteza.",
    9: "Kao da brojiš koliko si puta bacio kocku: što si više pokušavao, to je veća šansa da je uspjeh sreća.",
    10: "Kao da od pobjednika na lotu tražiš dokaz da nije samo sretan: korigiramo uspjeh za broj pokušaja i šansu da je sve slučajnost.",
    11: "Kao da isti tjedan kupovine promiješaš na tisuću načina da vidiš koliko loše može ispasti: gledamo najgori realni pad.",
    12: "Kao da provjeriš može li se stvarno kupiti toliko robe po toj cijeni: nema trgovina koje u praksi ne bi prošle.",
    13: "Kao da zadnje pogledaš ispitni zadatak koji nitko nije vidio: zadnje razdoblje mora potvrditi, ne pretjerati.",
    14: "Kao završni pregled automobila prije tehničkog: svi prethodni koraci moraju biti zabilježeni i prošli.",
}


def run_critic(
    strategy_id: str,
    inputs: CriticInputs,
    config: CriticConfig | None = None,
    today: date | None = None,
) -> CriticVerdict:
    """Run checks 0-14 in documented order (holdout, check 13, after everything else).

    Fail closed: any failed check makes the verdict FAIL; all checks still run so the
    report carries every number.
    """
    cfg = config or CriticConfig()
    r = inputs.returns
    rp = inputs.portfolio_returns or r  # joint ROTATION/BASKET trades when present
    results: list[CriticCheck] = [
        c.check_0_data(inputs.data_check_exit_code, inputs.wdc_spinoff_adjusted_once),
        c.check_1_lookahead(inputs.lookahead_truncation_ok, inputs.lookahead_corrupt_future_ok),
        c.check_2_freeze(inputs.freeze_matches),
        c.check_3_same_sign(rp),
        c.check_4_min_sample(rp, cfg),
        c.check_5_purge_embargo(inputs.no_fitted_parameters, inputs.period_boundary_liquidation),
        c.check_6_sensitivity(inputs.sensitivity),
        c.check_7_cost_stress(r, inputs.costs, cfg, inputs.stressed_returns),
        c.check_8_regime_concentration(r, cfg),
        c.check_9_multiple_testing(inputs.k, inputs.ledger_complete),
        c.check_10_dsr_pbo(rp, inputs.k, inputs.trials_matrix, cfg, inputs.trials_matrix_metadata),
        c.check_11_monte_carlo(rp, cfg),
        c.check_12_fills(inputs.fill_violations),
    ]
    results.append(c.check_13_holdout(rp, cfg, inputs.holdout_fill_violations))
    results.append(c.check_14_final_audit(
        results, inputs.audit, inputs.rule_types, inputs.lookahead_evidence_ok
    ))
    failed = [x for x in results if not x.passed]
    reasons = [f"{x.number}. {x.name}: {x.detail}" for x in failed]
    return CriticVerdict(
        strategy_id=strategy_id,
        date=today or datetime.now(UTC).date(),
        k=inputs.k,
        checks=results,
        verdict=Verdict.FAIL if failed else Verdict.PASS,
        reasons=reasons,
    )


def render_verdict_md(
    verdict: CriticVerdict,
    name: str = "",
    freeze_file: str | None = None,
    benchmark: bool = False,
) -> str:
    """Render the verdict in the CRITIC_CRITERIA.md template, in Croatian.

    Each check line carries the real numbers and an everyday comparison; the filename to use
    is `{date}_{ID}_VERDICT.md`.
    """
    passed = verdict.verdict == Verdict.PASS and not benchmark
    title = f"{verdict.strategy_id} {name}".strip()
    lines = [
        f"# {title} — Critic VERDICT",
        "",
        (f"**MJERILO** (benchmark, rezultat gate-a: {verdict.verdict.value}). "
         "Nikad nije kandidat za approved_list: služi samo kao letvica za usporedbu."
         if benchmark else
         f"**{verdict.verdict.value}** (fail closed). Eligible for approved_list: {'da' if passed else 'ne'}."),
        "",
        f"Date: {verdict.date.isoformat()} (Europe/Zagreb). Critic: Memory Backtest.",
        f"Freeze: `{freeze_file or 'strategies/frozen/{YYYY-MM-DD}_' + verdict.strategy_id + '.json'}`",
        f"Campaign K: {verdict.k} (izvor: ledger) — raw Sharpe nije dokaz.",
        "",
        "## Ordered checks",
        "",
    ]
    for chk in verdict.checks:
        status = "PASS" if chk.passed else "FAIL"
        lines.append(f"{chk.number}. {chk.name}: **{status}** — {chk.detail}")
        lines.append(f"   - Laički: {EXPLANATIONS.get(chk.number, '')}")
    lines += ["", "## Verdict", ""]
    if benchmark:
        lines.append("MJERILO. Brojke gore pokazuju koliko je teško nadmašiti jednostavnu strategiju; "
                     "ovaj ID nikad ne ulazi na approved_list. Signal: PRIČEKAJ.")
    elif passed:
        lines.append("PASS. Sve provjere su prošle; strategija smije na approved_list. "
                     "Backtest nije obećanje zarade. Signal: tek uz setup i kontrolu rizika.")
    else:
        why = "; ".join(f"{x.number}. {x.name}" for x in verdict.checks if not x.passed)
        lines.append(f"FAIL. Nisu prošle provjere: {why}. Nema mjesta na approved_list. Signal: PRIČEKAJ.")
    return "\n".join(lines) + "\n"


def update_approved_list(
    verdict: CriticVerdict, gate_dir: Path, verdict_file: str, today: date | None = None
) -> bool:
    """Add the strategy to `gate_dir/approved_list.json` only if verdict is PASS.

    Returns True when an entry was added. Raises if a PASS verdict contains a failed check
    (inconsistent input must never reach the approved list). Never touches the list on FAIL.
    """
    if verdict.verdict != Verdict.PASS:
        return False
    if any(not x.passed for x in verdict.checks) or len(verdict.checks) != 15:
        raise ValueError(f"inconsistent PASS verdict for {verdict.strategy_id}: failed or missing checks")
    path = gate_dir / "approved_list.json"
    if path.exists():
        current = ApprovedList.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        current = ApprovedList(updated_at=datetime.now(UTC))
    if any(e.strategy_id == verdict.strategy_id for e in current.strategies):
        return False
    current.strategies.append(
        ApprovedEntry(strategy_id=verdict.strategy_id, verdict_file=verdict_file,
                      approved_on=today or verdict.date)
    )
    current.updated_at = datetime.now(UTC)
    path.write_text(current.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return True
