"""Croatian sentences for the overview page and the written report, built from overview_data numbers."""

from __future__ import annotations

from lab.aichain import overview_data as D
from lab.aichain.overview_charts import num_hr, pct_hr


def eur(x: float) -> str:
    return num_hr(x, 0) + " EUR"


def seg_line(seg: str) -> dict[str, str]:
    """Plain-language facts for one segment: winner vs holding vs C13C, with the 1.000 EUR example."""
    w = D.winner(seg)
    c, h = w.stats, w.hold
    k1 = D.cell(seg, "K1_C13C_ORIG")
    name = D.CONTENDER_SHORT[w.contender]
    verdict_ret = "pobjeđuje držanje po prinosu" if w.beats_hold_return else "ne pobjeđuje držanje po prinosu"
    verdict_dd = "ima manji najgori pad" if w.smaller_drawdown else "ima veći najgori pad"
    return {
        "name": name,
        "verdict": f"{verdict_ret}, {verdict_dd}",
        "money": (
            f"Od 1.000 EUR ulaganja na početku 2023. držanje završi s {eur(D.per_1000(h))}, "
            f"{name} s {eur(D.per_1000(c))}, a C13C s {eur(D.per_1000(k1))}."
        ),
        "dd": (
            f"Najgori pad od vrha, računato na 1.000 EUR kupljenih na vrhu: držanje {eur(D.worst_loss_per_1000(h))}, "
            f"{name} {eur(D.worst_loss_per_1000(c))}, C13C {eur(D.worst_loss_per_1000(k1))}."
        ),
        "sharpe": (
            f"Sharpe: {name} {num_hr(c['sharpe'], 2)}, držanje {num_hr(h['sharpe'], 2)}, C13C {num_hr(k1['sharpe'], 2)}."
        ),
    }


def c13c_ticker_counts() -> dict[str, int]:
    rows = D.ticker_rows()
    return {
        "n": len(rows),
        "beats_ret": sum(1 for r in rows if r.c13c_ret > r.hold_ret),
        "beats_sharpe": sum(1 for r in rows if r.c13c_sharpe > r.hold_sharpe),
        "smaller_dd": sum(1 for r in rows if r.c13c_dd > r.hold_dd),
    }


def overall_counts() -> dict[str, int]:
    w = D.winners()
    return {
        "beats_ret": sum(1 for x in w.values() if x.beats_hold_return),
        "beats_sharpe": sum(1 for x in w.values() if x.beats_hold_sharpe),
        "smaller_dd": sum(1 for x in w.values() if x.smaller_drawdown),
    }
