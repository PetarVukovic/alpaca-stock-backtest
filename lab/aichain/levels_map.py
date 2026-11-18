"""Per-ticker market state ("map"): structure, swing range, S/R levels, liquidity, zones, plain-language reading.

Research only. Everything is computed as of the ticker's own last bar from the CSV via ``levels.prepare``.
Texts are Croatian (for the researcher); identifiers and comments stay English.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from lab.aichain import levels as lv
from lab.aichain import mechanics as mx

BIAS_HR = {
    1: "bikovski (viši vrhovi i više dna)",
    -1: "medvjeđi (niži vrhovi i niža dna)",
    0: "raspon (bez jasnog smjera)",
}
BIAS_SHORT = {1: "bullish", -1: "bearish", 0: "range"}


def hr_num(x: float, nd: int = 2) -> str:
    """Croatian number format: thousands dot, decimal comma."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def hr_pct(x: float, nd: int = 1) -> str:
    return hr_num(x, nd) + " %"


def hr_date(d: Any) -> str:
    d = pd.Timestamp(d)
    return f"{d.day}. {d.month}. {d.year}."


def clean(o: Any) -> Any:
    """Make nested data JSON-safe (numpy scalars to Python, NaN to None)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _structure_events(
    st: mx.Structure, t: int, date_of: Any, level_date_of: Any
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind in ("bos", "shift"):
        e = st.last(kind, t)
        out[f"last_{kind}"] = (
            None
            if e is None
            else {
                "date": str(date_of(e["idx"])),
                "direction": "bikovski" if e["dir"] == 1 else "medvjeđi",
                "broken_level": e["level"],
                "broken_level_date": str(level_date_of(e["level_idx"])),
            }
        )
    return out


def weekly_state(P: lv.Prepared) -> dict[str, Any]:
    w = P.weekly
    idx = np.flatnonzero(w.complete)
    st = P.wstruct
    t = len(idx) - 1
    date_of = lambda i: w.end[idx[i]].date()
    out = {
        "bias": BIAS_SHORT[int(st.bias[t])],
        "bias_hr": BIAS_HR[int(st.bias[t])],
        "last_complete_week_end": str(w.end[idx[t]].date()),
        "weeks_complete": len(idx),
        "pivot_rule": "5 tjedana sa svake strane (potvrda tek 5 tjedana nakon vrha ili dna)",
    }
    out.update(_structure_events(st, t, date_of, date_of))
    return out


def daily_state(P: lv.Prepared, t: int) -> dict[str, Any]:
    d = P.bars.dates
    out = {
        "bias": BIAS_SHORT[int(P.struct.bias[t])],
        "bias_hr": BIAS_HR[int(P.struct.bias[t])],
    }
    out.update(
        _structure_events(P.struct, t, lambda i: d[i].date(), lambda i: d[i].date())
    )
    return out


def swing_range_state(P: lv.Prepared, t: int) -> dict[str, Any] | None:
    lo, hi = P.lo_p[t], P.hi_p[t]
    if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo):
        return None
    d = P.bars.dates
    pos = float(P.pos[t])
    li, hi_i = int(P.lo_i[t]), int(P.hi_i[t])
    if pos < 0:
        where = "ispod raspona (probijeno dno)"
    elif pos > 1:
        where = "iznad raspona (probijen vrh)"
    else:
        where = (
            "diskont (jeftinija polovica)"
            if pos < 0.5
            else "premium (skuplja polovica)"
        )
    return {
        "low": float(lo),
        "low_date": str(d[li].date()),
        "high": float(hi),
        "high_date": str(d[hi_i].date()),
        "mid": float((lo + hi) / 2),
        "position_pct": pos * 100,
        "zone": "discount"
        if 0 <= pos < 0.5
        else "premium"
        if 0.5 <= pos <= 1
        else "outside",
        "zone_hr": where,
    }


def _dist(price: float, close: float, atr_t: float) -> tuple[float, float]:
    return (price / close - 1.0) * 100, (price - close) / atr_t


def level_records(P: lv.Prepared, t: int, placebo_note: str) -> list[dict[str, Any]]:
    close, a = float(P.bars.close[t]), float(P.atr[t])
    d = P.bars.dates
    recs = []
    for L in lv.cluster_levels(P.pivots, t, a, close):
        pct, atr_n = _dist(L.price, close, a)
        if abs(pct) > 40:
            continue
        rel = lv.pit_reliability(L, P, t)
        lt = lv.last_touch_idx(L.price, P, t)
        kind = "support" if L.price < close else "resistance"
        rec = {
            "price": L.price,
            "type": kind,
            "turning_points": L.touches,
            "last_touch_date": str(d[lt].date()) if lt is not None else None,
            "last_pivot_date": str(d[L.last_pivot_idx].date()),
            "strength": L.strength,
            "distance_pct": pct,
            "distance_atr": atr_n,
            "reliability": {
                **rel,
                "enough_touches": rel["n"] >= lv.MIN_TOUCHES_FOR_VERDICT,
            },
        }
        rec["reading"] = level_reading(rec, close, a, P.ticker, placebo_note)
        recs.append(rec)
    recs.sort(key=lambda r: r["price"])
    return recs


def level_reading(
    r: dict[str, Any], close: float, a: float, ticker: str, placebo_note: str
) -> str:
    """Plain-language reading of one level with a concrete 1.000 EUR example."""
    sup = r["type"] == "support"
    dist = abs(r["distance_pct"])
    word = "iznad potpore" if sup else "ispod otpora"
    s = (
        f"Cijena je {hr_pct(dist)} {word} {hr_num(r['price'])} "
        f"({hr_num(abs(r['distance_atr']), 1)} ATR; ATR je prosječni dnevni raspon, ovdje {hr_num(a)} ili {hr_pct(a / close * 100)} cijene). "
        f"Razina je nastala iz {r['turning_points']} okreta (okret je točka gdje je cijena stala i obrnula smjer), "
        f"zadnji dodir {hr_date(r['last_touch_date'])} "
    )
    rel = r["reliability"]
    if rel["enough_touches"]:
        s += (
            f"Povijesno, izvan uzorka: od {rel['n']} dodira odbila se {rel['bounce']} puta "
            f"({hr_pct(rel['rate'] * 100, 0)}), probijena je {rel['break']} puta, ostalo {rel['neither']}. "
        )
    else:
        s += f"Premalo dodira za zaključak o pouzdanosti (dodira nakon nastanka razine: {rel['n']}). "
    move = 1000 * (r["price"] / close - 1)
    if sup:
        s += f"Primjer: ako cijena padne do potpore, 1.000 EUR uložen sada postao bi oko {hr_num(1000 + move, 0)} EUR ({hr_num(move, 0)} EUR). "
    else:
        s += f"Primjer: ako cijena naraste do otpora, 1.000 EUR uložen sada postao bi oko {hr_num(1000 + move, 0)} EUR (+{hr_num(move, 0)} EUR). "
    return s + placebo_note


def build_map(
    P: lv.Prepared, group: str, placebo_note: str, last_label: str
) -> dict[str, Any]:
    b = P.bars
    t = len(b) - 1
    close, a = float(b.close[t]), float(P.atr[t])
    d = b.dates
    levels = level_records(P, t, placebo_note)
    sup = sorted(
        (x for x in levels if x["type"] == "support"), key=lambda x: -x["price"]
    )[:2]
    res = sorted(
        (x for x in levels if x["type"] == "resistance"), key=lambda x: x["price"]
    )[:2]

    sma50 = float(np.mean(b.close[t - 49 : t + 1])) if t >= 49 else None
    sma200 = float(np.mean(b.close[t - 199 : t + 1])) if t >= 199 else None
    w52 = slice(max(0, t - 251), t + 1)
    hi_i = int(np.argmax(b.high[w52])) + w52.start
    lo_i = int(np.argmin(b.low[w52])) + w52.start

    pools = mx.equal_pools(P.pivots, b.high, b.low, t)
    for side in pools.values():
        for p in side:
            p["distance_pct"] = (p["level"] / close - 1) * 100
            p["first_date"] = str(d[p["first_idx"]].date())
            p["last_date"] = str(d[p["last_idx"]].date())
    zones = []
    for z in mx.fresh_zones(P.zones, t):
        if abs(z["hi"] / close - 1) > 0.4 and abs(z["lo"] / close - 1) > 0.4:
            continue
        zones.append(
            {
                "kind": z["kind"],
                "base_date": str(d[z["base"]].date()),
                "known_date": str(d[z["known"]].date()),
                "low": z["lo"],
                "high": z["hi"],
                "body_low": z["body_lo"],
                "body_high": z["body_hi"],
                "distance_pct": (
                    (z["hi"] if z["kind"] == "demand" else z["lo"]) / close - 1
                )
                * 100,
            }
        )
    zones.sort(key=lambda z: z["known_date"], reverse=True)
    fvg = mx.fair_value_gaps(b.high, b.low, P.atr, t)
    fvg_out = {
        k: [
            {
                "date": str(d[g["idx"]].date()),
                "bottom": g["bottom"],
                "top": g["top"],
                "size_atr": g["size_atr"],
            }
            for g in sorted(v, key=lambda g: -g["idx"])
            if g["size_atr"] and g["size_atr"] >= 0.1
        ][:4]
        for k, v in fvg.items()
    }
    sweeps_recent = [
        {
            "date": str(d[e["idx"]].date()),
            "direction": "sweep dna (bikovski)"
            if e["dir"] == 1
            else "sweep vrha (medvjeđi)",
            "level": e["level"],
        }
        for e in P.sweeps
        if e["idx"] >= t - 20
    ]
    rn = lv.round_number_test(P.pivots, t, close)
    out = {
        "ticker": P.ticker,
        "group": group,
        "last_date": str(d[t].date()),
        "last_date_note": last_label,
        "last_close": close,
        "atr14": a,
        "atr14_pct": a / close * 100,
        "bar_repairs": P.notes,
        "weekly": weekly_state(P),
        "daily": daily_state(P, t),
        "swing_range": swing_range_state(P, t),
        "levels": levels,
        "nearest_supports": sup,
        "nearest_resistances": res,
        "round_numbers": {
            **rn,
            "note": "Okrugli brojevi navedeni jer se okreti nakupljaju oko njih"
            if rn["clusters"]
            else "Okrugli brojevi nisu navedeni: okreti se oko njih ne nakupljaju više nego slučajno",
        },
        "high_52w": {
            "price": float(b.high[hi_i]),
            "date": str(d[hi_i].date()),
            "distance_pct": (b.high[hi_i] / close - 1) * 100,
        },
        "low_52w": {
            "price": float(b.low[lo_i]),
            "date": str(d[lo_i].date()),
            "distance_pct": (b.low[lo_i] / close - 1) * 100,
        },
        "sma50": None
        if sma50 is None
        else {"value": sma50, "distance_pct": (close / sma50 - 1) * 100},
        "sma200": None
        if sma200 is None
        else {"value": sma200, "distance_pct": (close / sma200 - 1) * 100},
        "volume_profile": lv.volume_profile(P, t),
        "liquidity_pools": pools,
        "fresh_zones": {
            "demand": [z for z in zones if z["kind"] == "demand"][:4],
            "supply": [z for z in zones if z["kind"] == "supply"][:4],
        },
        "open_fvg": fvg_out,
        "recent_sweeps": sweeps_recent,
        "placebo_note": placebo_note,
    }
    out["reading"] = overall_reading(out)
    return out


def overall_reading(m: dict[str, Any]) -> list[str]:
    """Short Croatian reading of the whole map (a list of sentences)."""
    c = m["last_close"]
    lines = []
    wk, dy = m["weekly"], m["daily"]
    lines.append(
        f"Struktura (smjer kretanja gledan preko vrhova i dna): tjedni trend je {wk['bias_hr']}, dnevni trend je {dy['bias_hr']}."
    )
    sr = m["swing_range"]
    if sr:
        lines.append(
            f"Zadnji potvrđeni raspon ide od dna {hr_num(sr['low'])} ({hr_date(sr['low_date'])}) do vrha {hr_num(sr['high'])} ({hr_date(sr['high_date'])}); "
            f"cijena {hr_num(c)} je na {hr_num(sr['position_pct'], 0)} % raspona: {sr['zone_hr']}. "
            f"Primjer: raspon je širok {hr_pct((sr['high'] / sr['low'] - 1) * 100, 0)}, pa bi 1.000 EUR kupljenih na dnu raspona na vrhu bilo oko {hr_num(1000 * sr['high'] / sr['low'], 0)} EUR."
        )
    for key, word in (
        ("nearest_supports", "potpora"),
        ("nearest_resistances", "otpor"),
    ):
        for r in m[key]:
            lines.append(r["reading"])
    s200 = m["sma200"]
    if s200:
        lines.append(
            f"Cijena je {hr_pct(abs(s200['distance_pct']))} {'iznad' if s200['distance_pct'] > 0 else 'ispod'} prosjeka zadnjih 200 dana ({hr_num(s200['value'])})."
        )
    return lines
