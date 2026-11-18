"""Behaviour profile for one AI-chain segment, computed only from raw daily CSVs.

Usage: .venv/bin/python -m lab.aichain.profile mem_interface_storage
No orders, no network, no hourly data. Every number comes from data/ohlcv/*_1d.csv.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "reports/research/AICHAIN_20261014"
AI_START = pd.Timestamp("2023-01-01")
HORIZONS = (1, 5, 10, 20)


def load(ticker: str, end: pd.Timestamp) -> pd.DataFrame:
    df = (
        pd.read_csv(ROOT / f"data/ohlcv/{ticker}_1d.csv", parse_dates=["date"])
        .set_index("date")
        .sort_index()
    )
    return df.loc[:end, ["open", "high", "low", "close"]].astype(float)


def r4(x: float | int | None) -> float | None:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), 4)


def drawdowns(close: pd.Series, top: int = 5) -> list[dict]:
    """Non-overlapping drawdown episodes: peak -> bottom -> recovery (new close >= peak)."""
    peak_val = close.iloc[0]
    peak_dt = close.index[0]
    episodes: list[dict] = []
    cur: dict | None = None
    for dt, px in close.items():
        if px >= peak_val:
            if cur is not None:
                cur["recovery"] = str(dt.date())
                episodes.append(cur)
                cur = None
            peak_val, peak_dt = px, dt
        else:
            dd = px / peak_val - 1
            if cur is None:
                cur = {
                    "start": str(peak_dt.date()),
                    "bottom": str(dt.date()),
                    "size": dd,
                    "recovery": None,
                }
            elif dd < cur["size"]:
                cur["bottom"], cur["size"] = str(dt.date()), dd
    if cur is not None:
        episodes.append(cur)
    episodes.sort(key=lambda e: e["size"])
    return [{**e, "size": r4(e["size"])} for e in episodes[:top]]


def autocorr_vr(ret: pd.Series) -> dict:
    out = {f"ac{k}": r4(ret.autocorr(k)) for k in range(1, 6)}
    lr = np.log1p(ret.dropna())
    v1 = lr.var(ddof=1)
    for q in (5, 20):
        sq = lr.rolling(q).sum().dropna()
        out[f"vr{q}"] = r4(sq.var(ddof=1) / (q * v1))
    out["ac_band_95"] = r4(1.96 / np.sqrt(len(ret.dropna())))
    return out


def decluster(mask: pd.Series, lockout: int) -> list[int]:
    idx = np.flatnonzero(mask.values)
    keep: list[int] = []
    last = -(10**9)
    for i in idx:
        if i - last >= lockout:
            keep.append(int(i))
            last = int(i)
    return keep


def forward_table(
    close: pd.Series, mask: pd.Series, lockout: int, win: pd.Series
) -> dict:
    """Forward returns after events vs unconditional, restricted to window `win` (bool index)."""
    res: dict = {"n_raw": int((mask & win).sum())}
    pos = [i for i in decluster(mask & win, lockout)]
    res["n_independent"] = len(pos)
    for h in HORIZONS:
        fwd = close.shift(-h) / close - 1
        uncond = fwd[win].dropna()
        ev = fwd.iloc[pos].dropna() if pos else pd.Series(dtype=float)
        res[f"fwd{h}"] = {
            "n": int(len(ev)),
            "mean": r4(ev.mean()) if len(ev) else None,
            "median": r4(ev.median()) if len(ev) else None,
            "hit": r4((ev > 0).mean()) if len(ev) else None,
            "uncond_mean": r4(uncond.mean()),
            "uncond_hit": r4((uncond > 0).mean()),
        }
    return res


def seasonality(close: pd.Series, win_mask: pd.Series) -> dict:
    m = close.resample("ME").last().pct_change()
    first = close[win_mask].index[0]
    m = m[m.index >= first.to_period("M").to_timestamp("M")].dropna()
    out = {}
    for mo in range(1, 13):
        s = m[m.index.month == mo]
        out[str(mo)] = {
            "n": int(len(s)),
            "mean": r4(s.mean()) if len(s) else None,
            "hit": r4((s > 0).mean()) if len(s) else None,
        }
    out["warning"] = (
        "Mali uzorak: svaki mjesec ima samo %d-%d opažanja; ne tumačiti kao pravilo."
        % (
            min(v["n"] for v in out.values() if isinstance(v, dict)),
            max(v["n"] for v in out.values() if isinstance(v, dict)),
        )
    )
    return out


def sr_behaviour(
    df: pd.DataFrame,
    win: pd.Series,
    k: int = 5,
    tol: float = 0.015,
    life: int = 60,
    look: int = 5,
) -> dict:
    """Swing low/high = extreme within +-k bars, known only k bars later (no lookahead).
    Touch = first later day whose low (high) comes within tol of the level, before it expired or was closed through.
    Break = a close beyond level by more than tol within `look` days from the touch day; otherwise hold."""
    out = {}
    for side in ("support", "resistance"):
        col = "low" if side == "support" else "high"
        s = df[col].values
        cl = df["close"].values
        n = len(df)
        touches = holds = breaks = 0
        for i in range(k, n - k):
            seg = s[i - k : i + k + 1]
            lvl = s[i]
            if (side == "support" and lvl != seg.min()) or (
                side == "resistance" and lvl != seg.max()
            ):
                continue
            conf = i + k
            for j in range(conf + 1, min(n - look, conf + life)):
                # level already violated by a close beyond tolerance -> dead level
                if side == "support":
                    near = s[j] <= lvl * (1 + tol)
                    brk = cl[j : j + look + 1].min() < lvl * (1 - tol)
                else:
                    near = s[j] >= lvl * (1 - tol)
                    brk = cl[j : j + look + 1].max() > lvl * (1 + tol)
                if near:
                    if win.iloc[j]:
                        touches += 1
                        breaks += int(brk)
                        holds += int(not brk)
                    break
        out[side] = {
            "touches": touches,
            "hold": holds,
            "break": breaks,
            "hold_share": r4(holds / touches) if touches else None,
        }
    return out


def profile_ticker(
    t: str, df: pd.DataFrame, ref: dict[str, pd.Series], peers_ret: dict[str, pd.Series]
) -> dict:
    close = df["close"]
    ret = close.pct_change()
    sma200 = close.rolling(200).mean()
    dist = close / sma200 - 1
    drop5 = (close / close.shift(5) - 1 <= -0.05) & (close > sma200)
    hi52 = close > close.shift(1).rolling(252).max()
    up = ret > 0
    up3 = up & up.shift(1, fill_value=False) & up.shift(2, fill_value=False)
    gap = df["open"] / close.shift(1) - 1
    res: dict = {}
    for wname, wmask in (
        ("ai_2023plus", close.index >= AI_START),
        ("context_2016_2022", close.index < AI_START),
    ):
        win = pd.Series(wmask, index=close.index)
        r = ret[win].dropna()
        w: dict = {
            "bars": int(win.sum()),
            "first": str(close[win].index[0].date()),
            "last": str(close[win].index[-1].date()),
        }
        w["total_return"] = r4(close[win].iloc[-1] / close[win].iloc[0] - 1)
        w["ann_vol"] = r4(r.std(ddof=1) * np.sqrt(252))
        for name, rr in ref.items():
            a = pd.concat([r, rr.reindex(r.index)], axis=1, join="inner").dropna()
            c = a.cov().iloc[0, 1]
            w[f"beta_{name}"] = r4(c / a.iloc[:, 1].var())
            w[f"corr_{name}"] = r4(a.corr().iloc[0, 1])
        w["worst_drawdowns"] = drawdowns(close[win])
        w["autocorr_vr"] = autocorr_vr(r)
        w["after_5d_drop_ge5pct_above_sma200"] = forward_table(close, drop5, 5, win)
        w["after_new_52w_high"] = forward_table(close, hi52, 5, win)
        w["after_3_up_days"] = forward_table(close, up3, 3, win)
        w["seasonality"] = seasonality(close, win)
        g = gap[win].dropna()
        top = g.reindex(g.abs().sort_values(ascending=False).index)[:5]
        w["largest_gaps"] = [
            {"date": str(d.date()), "gap": r4(v)} for d, v in top.items()
        ]
        lr = np.log1p(r)
        best = lr.nlargest(10)
        tot = lr.sum()
        w["top10_days"] = {
            "share_of_total_log_return": r4(best.sum() / tot) if tot > 0 else None,
            "total_return_without_top10": r4(np.exp(tot - best.sum()) - 1),
            "total_return": r4(np.exp(tot) - 1),
            "best_days": [
                {"date": str(d.date()), "ret": r4(np.expm1(v))} for d, v in best.items()
            ],
        }
        # lead/lag: corr(ret_t, ref_{t+k}); k>0 positive means this ticker moves first
        ll = {}
        for name, rr in {
            **ref,
            **{p: x for p, x in peers_ret.items() if p != t},
        }.items():
            ll[name] = {
                str(k): r4(r.corr(rr.shift(-k).reindex(r.index)))
                for k in (-3, -2, -1, 0, 1, 2, 3)
            }
        w["lead_lag_corr_ret_t_vs_ref_t_plus_k"] = ll
        d = dist[win].dropna()
        buckets = {
            "below_sma200": d < 0,
            "0_15pct": (d >= 0) & (d < 0.15),
            "15_40pct": (d >= 0.15) & (d < 0.40),
            "above_40pct": d >= 0.40,
        }
        f20 = close.shift(-20) / close - 1
        w["sma200_distance"] = {
            "current_pct": r4(dist.iloc[-1]) if wname.startswith("ai") else None,
            "median": r4(d.median()),
            "p10": r4(d.quantile(0.1)),
            "p90": r4(d.quantile(0.9)),
            "buckets_fwd20": {
                b: {
                    "days": int(m.sum()),
                    "mean_fwd20": r4(f20.reindex(d.index)[m].mean()),
                    "hit_fwd20": r4((f20.reindex(d.index)[m].dropna() > 0).mean()),
                }
                for b, m in buckets.items()
            },
        }
        w["support_resistance"] = sr_behaviour(df, win)
        res[wname] = w
    return res


MECH = {
    "RMBS": {
        "ime": "Rambus",
        "tekst": (
            "Rambus je tvrtka bez vlastitih tvornica koja prodaje dvije stvari. Prvo, čipove za sučelje memorije na poslužiteljskim memorijskim modulima (DDR5): "
            "čipove koji upravljaju taktom, napajanjem i prijenosom podataka između procesora i memorijskih čipova. Drugo, licencira dizajne (silicijski IP) za brze veze i sigurnost, "
            "koje drugi proizvođači ugrađuju u svoje čipove. Proizvode kupuju proizvođači memorijskih modula, veliki proizvođači poslužitelja i veliki oblačni davatelji usluga. "
            "Prihod prati broj prodanih DDR5 poslužiteljskih modula i količinu memorije po poslužitelju; što više memorije AI poslužitelj ima, to više takvih čipova treba. "
            "U lancu je mala karika između procesora i memorije: ne ovisi izravno o cijeni DRAM-a, nego o broju i složenosti modula. "
            "Ciklus: prelazak s jedne generacije memorije na drugu (DDR4 na DDR5 pa dalje) i ulaganja u podatkovne centre; kad se prelazak uspori ili poslužitelji zastoje, prihod pada. "
            "Šteti mu: usporavanje ulaganja u poslužitelje, jača konkurencija na istim čipovima i zalihe kod kupaca. Za 1.000 EUR u dionici, ovakav model znači da je dionica osjetljivija na vijesti o poslužiteljima nego na cijenu memorije. "
            "Napomena: kontekst iz javnih izvora, nije iz naših podataka."
        ),
        "izvori": [
            "https://www.sec.gov/Archives/edgar/data/917273/000119312526057101/rmbs-20251231.htm",
            "https://www.sec.gov/Archives/edgar/data/917273/000091727325000021/rmbs-20241231.htm",
        ],
    },
    "SIMO": {
        "ime": "Silicon Motion",
        "tekst": (
            "Silicon Motion proizvodi kontrolere: čipove koji su 'mozak' SSD diska i memorijskih kartica. Kontroler upravlja NAND flash memorijom (ispravlja greške, rasporeduje zapise, brine o trajnosti). "
            "Prodaje ih proizvođačima NAND memorije, proizvođačima modula, velikim oblačnim kupcima i proizvođačima uređaja; tvrtka sama navodi da njezini kontroleri podržavaju gotovo sve veće NAND proizvođače. "
            "Ima i vlastitu liniju ugrađene pohrane (Ferri) za industriju i automobile. Prihod ovisi o broju prodanih SSD-ova i mobilne pohrane (eMMC/UFS) te o ciklusu NAND memorije: kad NAND postane skup, kupci kupuju manje, kad zalihe presuše, narudžbe naglo skaču. "
            "U lancu je između NAND čipa i računala, dakle u pohrani, a ne u DRAM-u ni HBM-u. Šteti mu: pad potražnje za računalima i telefonima, višak zaliha NAND-a, cjenovni pritisak i ovisnost o nekoliko velikih kupaca. "
            "U našim podacima vidi se dnevni skok od +45,8% (2026-04-29); javni izvori taj skok povezuju s rezultatima prvog kvartala 2026. (zarada i prihod iznad očekivanja, bolja prognoza); točan postotak u tim izvorima se razlikuje pa ga ne uzimamo iz njih. "
            "Za 1.000 EUR u dionici, takav jedan dan znači dobitak od oko 458 EUR, ali jedan dan ne smijemo čitati kao pravilo. "
            "Napomena: kontekst iz javnih izvora, nije iz naših podataka."
        ),
        "izvori": [
            "https://www.arrow.com/en/manufacturers/s/silicon-motion-technology.html",
            "https://www.itiger.com/news/1143217001",
        ],
    },
    "MRAM": {
        "ime": "Everspin Technologies",
        "tekst": (
            "Everspin je mala tvrtka koja prodaje MRAM, vrstu memorije koja zadržava podatke i kad nestane struje (za razliku od DRAM-a), a brza je. "
            "Koristi se tamo gdje se podaci ne smiju izgubiti: industrija, automobili, medicina, zrakoplovstvo, podatkovni centri. Prihod je reda veličine desetaka milijuna dolara godišnje (javni izvor: 63,8 milijuna USD u 2023.), "
            "dakle ona je neusporedivo manja od Microna. Proizvodi ne prati DRAM ciklus nego narudžbe industrijskih kupaca, a velik dio je i državni ugovor: u svibnju 2026. objavljen je ugovor vrijedan oko 40 milijuna USD za proizvodnju u SAD-u, raspodijeljen do 2028. "
            "U našim podacima to odgovara dnevnom skoku od oko +47,7% (2026-05-11). U lancu AI memorije nije izravni dobavljač, nego rubna, specijalna niša. "
            "Šteti joj: mali prihod, ovisnost o malom broju kupaca, tanka trgovina (veliki rasponi cijena, veći trošak ulaska i izlaska) i činjenica da MRAM zamjenjuje druge memorije samo u uskim primjenama. "
            "Za 1.000 EUR u ovoj dionici, jedan loš dan lako može odnijeti stotinu EUR i više. Dionicu tretiramo kao tanku (thin), s oštrijim troškovima. "
            "Napomena: kontekst iz javnih izvora, nije iz naših podataka; navod o ugovoru potječe iz jednog sekundarnog izvora."
        ),
        "izvori": [
            "https://www.sec.gov/Archives/edgar/data/1438423/000155837024002185/mram-20231231x10k.htm",
            "https://ts2.tech/en/everspin-stock-jumps-after-40-million-defense-mram-deal-what-changed/",
        ],
    },
    "NTAP": {
        "ime": "NetApp",
        "tekst": (
            "NetApp prodaje sustave za pohranu podataka u poduzećima i softver za upravljanje podacima (ONTAP), te usluge u oblaku. Najveći dio prihoda dolazi od sustava s flash (SSD) memorijom, "
            "a uz to prodaje pretplate i podršku. Javni podaci za fiskalnu 2026. (kraj travnja 2026.): ukupni prihod oko 6,93 milijardi USD, od toga oko 4,2 milijarde all-flash sustavi. "
            "Prihod prati proračune IT odjela u poduzećima (obnova poslužitelja i pohrane, AI podaci), a flash komponente su mu ulazni trošak: kad NAND poskupi, mora povisiti cijene ili mu pada marža. "
            "U lancu je na kraju: kupuje memorijske čipove i prodaje gotov proizvod, pa je potrošač memorije, a ne njezin proizvođač. To znači da ima drukčiji ciklus od MU: stabilniji prihod od pretplata, manje oštri vrhunci. "
            "Šteti mu: usporavanje IT proračuna, pritisak oblačnih usluga (kupci prelaze u oblak), poskupljenje NAND-a i konkurencija. "
            "Za 1.000 EUR u dionici, očekujemo da se kreće sporije od memorijskih proizvođača; u našim podacima to provjeravamo kroz volatilnost i korelaciju s SMH. "
            "Napomena: kontekst iz javnih izvora, nije iz naših podataka."
        ),
        "izvori": [
            "https://www.sec.gov/Archives/edgar/data/0001002047/000119312526259683/ntap-20260424.htm",
            "https://www.blocksandfiles.com/flash/2026/05/29/ai-and-all-flash-demand-send-netapp-revenues-to-record-heights/5248292",
        ],
    },
}


def main(segment: str) -> None:
    uni = json.loads((OUT_ROOT / "universe.json").read_text())
    end = pd.Timestamp(uni["common_end"])
    seg = uni["segments"][segment]
    usable = [x["ticker"] for x in seg["tickers"] if x["usable"]]
    excluded = {
        x["ticker"]: x.get("exclude_reason") for x in seg["tickers"] if not x["usable"]
    }
    ndx = load("NDX", end)["close"].pct_change()
    smh = load("SMH", end)["close"].pct_change()
    data = {t: load(t, end) for t in usable}
    peers_ret = {t: d["close"].pct_change() for t, d in data.items()}
    ref = {"SMH": smh, "NDX": ndx}
    tickers = {}
    for t in usable:
        p = profile_ticker(t, data[t], ref, peers_ret)
        p["data_flags"] = [
            i for x in seg["tickers"] if x["ticker"] == t for i in x["issues"]
        ]
        for gp in p["ai_2023plus"]["largest_gaps"]:
            if abs(gp["gap"]) > 0.4:
                p["data_flags"].append(
                    "open/prev close gap %+.0f%% on %s: one-day outlier, kept (unverified, spans open 94.2 vs close 65.35 on SIMO 2023-07-26 type spikes)"
                    % (gp["gap"] * 100, gp["date"])
                    if t == "SIMO"
                    else "open/prev close gap %+.0f%% on %s: one-day outlier, kept"
                    % (gp["gap"] * 100, gp["date"])
                )
        p["mechanism_hr"] = MECH[t]
        tickers[t] = p
    out = {
        "segment": segment,
        "segment_name": seg.get("name"),
        "common_end": uni["common_end"],
        "ai_era_start": uni["ai_era_start"],
        "excluded": excluded,
        "method_notes_hr": [
            "Sve brojke izračunate su iz dnevnih CSV datoteka (data/ohlcv), do zajedničkog završnog datuma.",
            "Događaji (pad od 5 dana, novi 52-tjedni vrh, 3 uzastopna rasta) razrijeđeni su: brojimo samo događaje međusobno udaljene barem 5 (odnosno 3) dana, da se isti pad ne računa više puta. Prikazan je i sirovi broj.",
            "Odgovor na pitanje 'što se događa nakon pada' uspoređen je s bezuvjetnim prosjekom istog razdoblja. Mali broj događaja znači slab dokaz; ovo je opis, ne strategija.",
            "Lead/lag: korelacija prinosa tickera u danu t s prinosom reference u danu t+k. Pozitivna vrijednost za k>0 znači da ticker 'ide prvi'. Dnevni podaci ne vide kretanje unutar dana.",
            "Podrška/otpor: swing minimum/maksimum unutar +-5 dana, poznat tek 5 dana kasnije; 'dodir' = cijena dođe unutar 1,5% razine, 'proboj' = zatvaranje više od 1,5% preko razine unutar 5 dana. Nema usporedne vrijednosti za slučajne razine.",
            "Ovo je opis ponašanja, ne signal ni Critic PASS. Svaka ideja iz ovoga ide kao NOVA hipoteza s novim ID-em.",
        ],
        "tickers": tickers,
    }
    d = OUT_ROOT / "segments" / segment
    d.mkdir(parents=True, exist_ok=True)
    (d / "profile.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    rows = []
    for t, p in tickers.items():
        for wn in ("ai_2023plus", "context_2016_2022"):
            w = p[wn]
            row = {
                "ticker": t,
                "window": wn,
                "bars": w["bars"],
                "total_return": w["total_return"],
                "ann_vol": w["ann_vol"],
                "beta_SMH": w["beta_SMH"],
                "corr_SMH": w["corr_SMH"],
                "beta_NDX": w["beta_NDX"],
                "corr_NDX": w["corr_NDX"],
                "worst_dd": w["worst_drawdowns"][0]["size"]
                if w["worst_drawdowns"]
                else None,
                "top10_share_log_ret": w["top10_days"]["share_of_total_log_return"],
                "ret_without_top10": w["top10_days"]["total_return_without_top10"],
            }
            row.update({k: v for k, v in w["autocorr_vr"].items()})
            for key, lab in (
                ("after_5d_drop_ge5pct_above_sma200", "drop5"),
                ("after_new_52w_high", "hi52"),
                ("after_3_up_days", "up3"),
            ):
                row[f"{lab}_n_indep"] = w[key]["n_independent"]
                for h in (5, 20):
                    f = w[key][f"fwd{h}"]
                    row[f"{lab}_fwd{h}_mean"], row[f"{lab}_fwd{h}_hit"] = (
                        f["mean"],
                        f["hit"],
                    )
                    (
                        row[f"{lab}_fwd{h}_uncond_mean"],
                        row[f"{lab}_fwd{h}_uncond_hit"],
                    ) = f["uncond_mean"], f["uncond_hit"]
            for s in ("support", "resistance"):
                row[f"{s}_touches"], row[f"{s}_hold_share"] = (
                    w["support_resistance"][s]["touches"],
                    w["support_resistance"][s]["hold_share"],
                )
            row["dist_sma200_median"] = w["sma200_distance"]["median"]
            rows.append(row)
    pd.DataFrame(rows).to_csv(d / "profile_stats.csv", index=False)
    print("written", d)


if __name__ == "__main__":
    main(sys.argv[1])
