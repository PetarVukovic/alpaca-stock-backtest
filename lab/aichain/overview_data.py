"""Cross-segment overview data for the AI chain tournament.

Reads only the finished result files (summary.json, universe.json, segments/*/analysis.json,
results/{segment}.json). Every number shown on the overview page and in the written report comes
from here, so nothing is typed by hand. No orders, no data downloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "reports/research/AICHAIN_20261014"

SEGMENTS: list[str] = [
    "memory",
    "mem_interface_storage",
    "equipment",
    "ai_chips_logic",
    "network_servers",
    "cloud",
]
SEGMENT_TITLE: dict[str, str] = {
    "memory": "Memorija (DRAM, NAND, diskovi)",
    "mem_interface_storage": "Memorijska sučelja, kontroleri i sustavi za pohranu",
    "equipment": "Oprema za proizvodnju čipova",
    "ai_chips_logic": "AI procesori, logika i analogni čipovi",
    "network_servers": "Mreže, optika i serveri za AI",
    "cloud": "Oblak i podatkovni centri",
}
SEGMENT_SHORT: dict[str, str] = {
    "memory": "Memorija",
    "mem_interface_storage": "Sučelja i pohrana",
    "equipment": "Oprema",
    "ai_chips_logic": "AI čipovi i logika",
    "network_servers": "Mreže i serveri",
    "cloud": "Oblak",
}
CONTENDERS: list[str] = [
    "B0_BUYHOLD",
    "K1_C13C_ORIG",
    "K2_SMA200_TREND",
    "K3_DONCHIAN_55_20",
    "K4_TSMOM_126",
    "K5_SUPPORT_RESISTANCE",
    "K5B_SR_BREAKOUT_RETEST",
    "K6_MOMENTUM_CS",
    "K7_C13C_PLUS_TREND_REENTRY",
]
RULES: list[str] = [c for c in CONTENDERS if c != "B0_BUYHOLD"]
CONTENDER_SHORT: dict[str, str] = {
    "B0_BUYHOLD": "Držanje",
    "K1_C13C_ORIG": "K1 C13C",
    "K2_SMA200_TREND": "K2 SMA200",
    "K3_DONCHIAN_55_20": "K3 proboj 55/20",
    "K4_TSMOM_126": "K4 zamah 126",
    "K5_SUPPORT_RESISTANCE": "K5 potpora",
    "K5B_SR_BREAKOUT_RETEST": "K5B proboj + povratak",
    "K6_MOMENTUM_CS": "K6 rotacija zamaha",
    "K7_C13C_PLUS_TREND_REENTRY": "K7 C13C + ponovni ulaz",
}
CONTENDER_PLAIN: dict[str, str] = {
    "B0_BUYHOLD": "Kupi na početku i drži. Mjerilo, ne strategija.",
    "K1_C13C_ORIG": "Tvoj C13C: kupi kad je cijena iznad prosjeka zadnjih 200 dana, a u 5 dana je pala 5 % ili više; klizni stop 10 % ispod vrha.",
    "K2_SMA200_TREND": "Drži dok je cijena iznad prosjeka zadnjih 200 dana, izađi kad padne ispod.",
    "K3_DONCHIAN_55_20": "Kupi kad cijena probije najviše od 55 dana, izađi kad padne ispod najnižeg od 20 dana.",
    "K4_TSMOM_126": "Drži dok je prinos zadnjih 126 dana pozitivan.",
    "K5_SUPPORT_RESISTANCE": "Kupi odbijanje od potpore u uzlaznom trendu; stop 3 % ispod potpore, cilj na zadnjem vrhu.",
    "K5B_SR_BREAKOUT_RETEST": "Kupi kad cijena nakon proboja otpora provjeri tu razinu odozgo; stop 3 % ispod razine, izlaz ispod prosjeka 50 dana.",
    "K6_MOMENTUM_CS": "Samo za skupinu dionica: svaki mjesec drži bolju polovicu po 126-dnevnom prinosu, a negativne zamijeni gotovinom.",
    "K7_C13C_PLUS_TREND_REENTRY": "C13C uz ponovni ulaz nakon izbijanja stopa (nova hipoteza, vlastiti ID).",
}

MIN_TRADES = 20


def _load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def summary() -> dict[str, Any]:
    return _load(RES / "summary.json")


@lru_cache(maxsize=1)
def universe() -> dict[str, Any]:
    return _load(RES / "universe.json")


@lru_cache(maxsize=None)
def analysis(segment: str) -> dict[str, Any]:
    return _load(RES / "segments" / segment / "analysis.json")


@lru_cache(maxsize=None)
def segment_results(segment: str) -> dict[str, Any]:
    return _load(RES / "results" / f"{segment}.json")


def cell(segment: str, contender: str) -> dict[str, Any]:
    return summary()["segment_x_contender_ai_era"][segment][contender]


def ticker_cell(ticker: str, contender: str) -> dict[str, Any] | None:
    return summary()["ticker_x_contender_ai_era"][ticker].get(contender)


def segment_tickers(segment: str) -> list[str]:
    """Usable tickers of a segment, in universe order."""
    return [t["ticker"] for t in universe()["segments"][segment]["tickers"] if t["usable"]]


def excluded() -> list[dict[str, str]]:
    return list(universe()["excluded"])


def per_1000(c: dict[str, Any]) -> float:
    """End value of 1.000 EUR invested at the window start."""
    return c["end_value"] / c["start_capital"] * 1000.0


def worst_loss_per_1000(c: dict[str, Any]) -> float:
    """Worst peak-to-trough loss in EUR for 1.000 EUR held at the peak."""
    return -c["max_drawdown"] * 1000.0


def is_eligible(c: dict[str, Any] | None) -> bool:
    return bool(c) and c["trades"] >= MIN_TRADES and c["total_return_cost_2x"] > 0


@dataclass(frozen=True)
class Winner:
    segment: str
    contender: str
    stats: dict[str, Any]
    hold: dict[str, Any]
    beats_hold_return: bool
    beats_hold_sharpe: bool
    smaller_drawdown: bool
    ineligible_better: list[str]  # rules with higher Sharpe that failed the trade or cost filter


def winner(segment: str) -> Winner:
    """Fixed definition: highest AI-era Sharpe, >= 20 trades, positive at cost 2x (hold excluded)."""
    cells = summary()["segment_x_contender_ai_era"][segment]
    elig = [k for k in RULES if is_eligible(cells.get(k))]
    best = max(elig, key=lambda k: cells[k]["sharpe"])
    hold = cells["B0_BUYHOLD"]
    c = cells[best]
    skipped = [
        k
        for k in RULES
        if cells.get(k) and not is_eligible(cells[k]) and cells[k]["sharpe"] > c["sharpe"]
    ]
    return Winner(
        segment=segment,
        contender=best,
        stats=c,
        hold=hold,
        beats_hold_return=c["total_return"] > hold["total_return"],
        beats_hold_sharpe=c["sharpe"] > hold["sharpe"],
        smaller_drawdown=c["max_drawdown"] > hold["max_drawdown"],
        ineligible_better=skipped,
    )


def winners() -> dict[str, Winner]:
    return {s: winner(s) for s in SEGMENTS}


def ratio_to_hold(segment: str, contender: str) -> float | None:
    """End value of the contender divided by end value of holding (both from the same capital)."""
    c = cell(segment, contender)
    if not c:
        return None
    return (1.0 + c["total_return"]) / (1.0 + c["buyhold_total_return"])


def mean_sharpe(contender: str) -> float:
    return sum(cell(s, contender)["sharpe"] for s in SEGMENTS) / len(SEGMENTS)


def overall_table() -> list[dict[str, Any]]:
    """One row per contender: wins, mean Sharpe, segments beating hold, mean drawdown, eligibility."""
    rows: list[dict[str, Any]] = []
    wins = winners()
    for k in CONTENDERS:
        cs = [cell(s, k) for s in SEGMENTS]
        rows.append(
            {
                "id": k,
                "wins": sum(1 for w in wins.values() if w.contender == k),
                "mean_sharpe": sum(c["sharpe"] for c in cs) / len(cs),
                "beats_hold_return": sum(
                    1 for s in SEGMENTS if cell(s, k)["total_return"] > cell(s, "B0_BUYHOLD")["total_return"]
                ),
                "beats_hold_sharpe": sum(
                    1 for s in SEGMENTS if cell(s, k)["sharpe"] > cell(s, "B0_BUYHOLD")["sharpe"]
                ),
                "smaller_dd": sum(
                    1 for s in SEGMENTS if cell(s, k)["max_drawdown"] > cell(s, "B0_BUYHOLD")["max_drawdown"]
                ),
                "mean_dd": sum(c["max_drawdown"] for c in cs) / len(cs),
                "eligible_segments": sum(1 for c in cs if is_eligible(c)),
                "min_trades": min(c["trades"] for c in cs),
                "max_dsr": max(c["deflated_sharpe_prob"] for c in cs),
            }
        )
    return rows


def norm_rating(raw: str | None) -> str:
    r = (raw or "").lower()
    if r in ("zeleno", "zelena", "green"):
        return "zeleno"
    if r in ("žuto", "žuta", "yellow", "zuto"):
        return "žuto"
    if r in ("crveno", "crvena", "red"):
        return "crveno"
    return "mjerilo" if r == "mjerilo" else (r or "nepoznato")


def ratings(segment: str) -> dict[str, str]:
    """Normalised evidence rating per contender, read from each segment's analysis.json (schemas differ)."""
    a = analysis(segment)
    out: dict[str, str] = {}
    if segment == "memory":
        for k, v in a["ratings"]["by_contender"].items():
            out[k] = norm_rating(v["rating"])
    elif segment == "mem_interface_storage":
        for v in a["ocjene"]["suparnici"]:
            out[v["suparnik"]] = norm_rating(v["ocjena"])
    elif segment == "equipment":
        for k, v in a["ratings"].items():
            if isinstance(v, dict) and "rating" in v:
                out[k] = norm_rating(v["rating"])
    elif segment == "ai_chips_logic":
        for k, v in a["ocjene"]["ocjene"].items():
            if isinstance(v, dict) and "ocjena" in v:
                out[k] = norm_rating(v["ocjena"])
    elif segment == "network_servers":
        for k, v in a["ocjene"]["po_suparniku"].items():
            out[k] = norm_rating(v["ocjena"])
    elif segment == "cloud":
        for v in a["ocjene"]:
            out[v["suparnik"]] = norm_rating(v["ocjena"])
    out["B0_BUYHOLD"] = "mjerilo"  # holding is the yardstick, never rated
    return out


@dataclass(frozen=True)
class TickerRow:
    ticker: str
    segment: str
    c13c_ret: float
    hold_ret: float
    c13c_dd: float
    hold_dd: float
    c13c_sharpe: float
    hold_sharpe: float
    trades: int


def ticker_rows() -> list[TickerRow]:
    rows: list[TickerRow] = []
    for seg in SEGMENTS:
        for t in segment_tickers(seg):
            k1 = ticker_cell(t, "K1_C13C_ORIG")
            b0 = ticker_cell(t, "B0_BUYHOLD")
            if not k1 or not b0:
                continue
            rows.append(
                TickerRow(
                    ticker=t,
                    segment=seg,
                    c13c_ret=k1["total_return"],
                    hold_ret=b0["total_return"],
                    c13c_dd=k1["max_drawdown"],
                    hold_dd=b0["max_drawdown"],
                    c13c_sharpe=k1["sharpe"],
                    hold_sharpe=b0["sharpe"],
                    trades=k1["trades"],
                )
            )
    return rows


def other_beats_hold_by_ticker() -> dict[str, list[str]]:
    """Per ticker: single-stock rules whose AI-era total return is above holding."""
    out: dict[str, list[str]] = {}
    for seg in SEGMENTS:
        for t in segment_tickers(seg):
            b0 = ticker_cell(t, "B0_BUYHOLD")
            if not b0:
                continue
            for k in RULES:
                c = ticker_cell(t, k)
                if c and c["total_return"] > b0["total_return"]:
                    out.setdefault(t, []).append(k)
    return out


def context_2021_2022(segment: str, contender: str) -> dict[str, float]:
    """Context window 2021-2022 (not the yardstick): return of the contender and of holding."""
    w = segment_results(segment)["contenders"][contender]["windows"]["y2021_2022"]
    return {
        "ret": w["total_return"],
        "hold": w["buyhold_total_return"],
        "dd": w["max_drawdown"],
    }


def equity_curve(segment: str, contender: str) -> list[tuple[str, float]]:
    pts = segment_results(segment)["contenders"][contender]["equity"]["ai_era"]
    return [(d, float(v)) for d, v in pts]


def robustness(contender: str, segment: str) -> dict[str, Any] | None:
    r = summary()["robustness_pm20"].get(contender, {}).get(segment)
    return r
