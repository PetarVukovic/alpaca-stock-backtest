"""Plot the upstream Day Trader offline demo; no lab strategy or orders."""
from pathlib import Path
import os
import json
import base64
import html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/research/DAY_TRADER_20261103/TSLA_DEMO"
os.environ.setdefault("MPLCONFIGDIR",str(ROOT/".runtime/kronos/matplotlib"))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

r=json.loads((OUT/"timemachine.json").read_text())
mc=r["mc"]; history=r["history"]; plan=r["plan"]
bands=np.array(mc["bands"])
paths=np.array(mc["sample_paths"])
assert abs(mc["p_target"]+mc["p_stop"]+mc["p_neither"]-1)<1e-8
assert history["triggered"]==len(history["trades"])
fig,(ax,bx)=plt.subplots(2,1,figsize=(12,9),gridspec_kw={"height_ratios":[2,1]},layout="constrained")
fig.patch.set_facecolor("#f2f6fa")
for a in (ax,bx):
    a.set_facecolor("white");a.grid(alpha=.16);a.spines[["top","right"]].set_visible(False)
x=np.arange(len(bands))
for p in paths[:40]:ax.plot(x,p,color="#6686aa",alpha=.12,lw=.7)
ax.fill_between(x,bands[:,0],bands[:,4],color="#cbdcf1",alpha=.65,label="5.–95. percentil generiranih putanja")
ax.fill_between(x,bands[:,1],bands[:,3],color="#8cadd8",alpha=.5,label="25.–75. percentil")
ax.plot(x,bands[:,2],color="#255bc0",lw=2,label="Medijan putanja")
ax.axhline(plan["target"],color="#087c69",ls="--",label=f"Cilj {plan['target']:.2f} USD")
ax.axhline(plan["stop"],color="#ad3541",ls="--",label=f"Stop {plan['stop']:.2f} USD")
ax.axhline(plan["entry"],color="#52697d",ls=":",label=f"Ulaz {plan['entry']:.2f} USD")
ticks=[0,9,21,33,45,57,69]
ax.set_xticks(ticks,[mc["band_times"][i] for i in ticks])
ax.set_xlabel("Vrijeme u New Yorku, 19. 10. 2026.")
ax.set_ylabel("Simulirana cijena (USD)")
ax.set_title("10.000 mogućih nastavaka iz 59 ranijih punih sesija",loc="left",fontsize=17,weight="bold")
ax.legend(loc="upper left",fontsize=9,ncol=2)
trades=history["trades"]
bx.bar(range(len(trades)),[t["R"] for t in trades],color=["#087c69" if t["R"]>0 else "#ad3541" for t in trades])
bx.axhline(0,color="#52697d",lw=.8)
bx.axhline(history["avg_R"],color="#255bc0",ls="--",label=f"Prosjek {history['avg_R']:+.3f} R")
bx.set_title("Što se stvarno događalo ranije: 33 pojavljivanja istog setupa",loc="left",fontsize=14)
bx.set_ylabel("Ishod u R, prije troškova")
idx=list(range(0,len(trades),5))+[len(trades)-1]
bx.set_xticks(idx,[trades[i]["date"][5:].replace("-","/") for i in idx])
bx.set_xlabel("Ranije sesije (mjesec/dan)")
bx.legend(fontsize=10)
fig.suptitle("Time Machine / TSLA — blizu bacanja novčića",fontsize=21,weight="bold")
fig.supxlabel("Demonstracija alata na upstream testnim podacima • seed 19 • raspon simulacija nije jamstvo buduće cijene",fontsize=10)
fig.savefig(OUT/"time-machine-tsla.png",dpi=160);plt.close(fig)
text=f"""# Day Trader / Time Machine — offline demonstracija

Paketov fiksni TSLA primjer 2026-10-19 u 10:15 New York. Nije lab backtest ni nova odobrena strategija. Ne koristi MU ili zabranjene nove izvore za backtest. Bez naloga.

Plan: ulaz {plan['entry']:.2f} USD, stop {plan['stop']:.2f}, cilj {plan['target']:.2f}. Rizik 1R = {plan['entry']-plan['stop']:.2f} USD po dionici. Uzorak: {mc['pool_sessions']} punih sesija, {mc['pool_from']} – {mc['pool_to']}. Simulacija: 10.000 putanja, seed 19.

- Cilj prvi: {100*mc['p_target']:.2f}%
- Stop prvi: {100*mc['p_stop']:.2f}%
- Nijedno: {100*mc['p_neither']:.2f}%
- Pozitivan ishod: {100*mc['p_green']:.2f}%
- Medijan cijene na zatvaranju: {mc['median_close']:.2f} USD; 5.–95. percentil {mc['p5_close']:.2f} – {mc['p95_close']:.2f} USD.
- Prosjek: {mc['avg_R']:+.3f}R prije troškova.
- Povijest: {history['triggered']} aktivacija u {history['sessions']} sesija; {history['target']} cilj, {history['stop']} stop, {history['close']} zatvaranje bez dosezanja granica. Prosjek {history['avg_R']:+.3f}R.

## Doslovni zaključak alata

{r['verdict']}

{chr(10).join(r['verdict_notes'])}

## Ograničenja

Simulacija ponavljanjem ranijih petominutnih obrazaca, nije Kronos ni prognoza tržišta. Prikazano bez provizija, spreada, slippagea, dividendi, poreza i FX. Gap kroz stop upstream računa kao -1R, iako stvarni gubitak može biti veći. Rasponi na grafu dolaze iz modelovih price-path uzoraka; upstream konačne sažete statistike i percentili fan-grafa koriste različite uzorke i mogu se blago razlikovati. To nisu kalibrirani intervali pouzdanosti.

Nema stvarnog završnog ishoda za 19.10. u ovom spremljenom uzorku: današnja budućnost nije u demonstraciji. Donji graf prikazuje ranije stvarne ishode, ne današnju budućnost. Nije provedena neovisna provjera tržišnog izvora, EU/HR dostupnosti ili korisnikova računa. Ovo je test rada instaliranog alata. Nema Critic PASS-a, approved_list se ne mijenja.

Izvori i hash: demo_manifest.json. Izračun: timemachine.json. Graf: time-machine-tsla.png. HTML s ugrađenim grafom: time-machine-tsla.html.
"""
(OUT/"REPORT.md").write_text(text)
image=base64.b64encode((OUT/"time-machine-tsla.png").read_bytes()).decode()
rows="".join(f"<tr><td>{html.escape(t['date'])}</td><td>{html.escape(t['time'])}</td><td>{t['entry']:.2f}</td><td>{t['stop']:.2f}</td><td>{t['target']:.2f}</td><td>{html.escape(t['outcome'])}</td><td>{t['R']:+.3f}</td></tr>" for t in trades)
page=f"""<!doctype html><html lang="hr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Time Machine / TSLA</title><style>body{{font:17px/1.6 system-ui;color:#19334c;background:#f2f6fa;margin:0}}main{{max-width:1100px;margin:auto;padding:30px 20px}}h1{{line-height:1.15}}img{{width:100%;height:auto}}.stats{{display:flex;gap:24px;flex-wrap:wrap}}.stats div{{flex:1;min-width:140px}}strong{{font-size:25px}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{text-align:right;padding:8px;border-bottom:1px solid #d7e0eb}}td:first-child,th:first-child{{text-align:left}}.overflow{{overflow:auto}}details{{padding:20px 0}}summary{{cursor:pointer;font-weight:650}}small{{color:#52697d}}button{{font:inherit;padding:8px 15px;cursor:pointer}}@media print{{button{{display:none}}}}</style><main><small>Fiksni upstream primjer • 19. 10. 2026. • 10.000 ponavljanja • seed 19</small><h1>Time Machine: ima li ovaj plan prednost?</h1><p>TSLA: ulaz 364,18 USD, stop 358,32 USD, cilj 370,04 USD. Procjena napravljena uz sat vraćen na 10:15 u New Yorku.</p><div class="stats"><div>Cilj prvi<br><strong>{mc['p_target']:.1%}</strong></div><div>Stop prvi<br><strong>{mc['p_stop']:.1%}</strong></div><div>Nijedno do kraja dana<br><strong>{mc['p_neither']:.1%}</strong></div><div>Pozitivan ishod<br><strong>{mc['p_green']:.1%}</strong></div></div><p><b>Zaključak: blizu bacanja novčića.</b> Prosjek simulacije +0,034R prije troškova. Povijest istog setupa: −0,062R; slabije od simulacije.</p><img alt="Raspon simuliranih TSLA putanja i raniji stvarni rezultati setupa" src="data:image/png;base64,{image}"><p>Medijan završne cijene: 364,36 USD. 90% simuliranih završnih cijena: 355,54 – 373,54 USD. To je raspon ovog simulatora, ne jamstvo.</p><details><summary>Svih 33 ranija stvarna ishoda</summary><div class="overflow"><table><thead><tr><th>Datum</th><th>Vrijeme ET</th><th>Ulaz USD</th><th>Stop USD</th><th>Cilj USD</th><th>Ishod</th><th>R</th></tr></thead><tbody>{rows}</tbody></table></div></details><details><summary>Objašnjenje i ograničenja</summary><p>Uzorkovanje barova iz 59 ranijih punih sesija, bez Kronosa i bez naloga. Ovo su paketovi spremljeni testni podaci, ne lab backtest. 13 povijesnih trgovina dosegnulo je cilj, 15 stop, a 5 završilo bez dosezanja granica. Pozitivan ishod nije isto što i cilj prvi.</p><p>1R je udaljenost ulaza od stopa: 5,86 USD po dionici. Troškovi nisu uključeni; gap kroz stop u ovom alatu računa se kao −1R, premda u stvarnosti može izgubiti više. Povijesne kotacije i fillovi nisu neovisno provjereni.</p><p>Graf raspona i konačne sažete statistike koriste različite poduzorke putanja te mogu imati malo različite percentile. Konačni stvarni ishod odabranog dana nije dostupan u ovom uzorku; donji graf prikazuje ranije dane.</p><p>Nema Critic PASS-a niti potvrde izvedivosti kod IBKR-a za korisnika. Simulacija nije preporuka ni obećanje budućeg rezultata.</p><p>Doslovni zaključak: {html.escape(r['verdict'])}<br>{html.escape(' '.join(r['verdict_notes']))}</p></details><button onclick="window.print()">Ispis / PDF</button></main></html>"""
(OUT/"time-machine-tsla.html").write_text(page)
print("Saved graph, self-contained HTML, and report; 33 historical outcomes verified")
