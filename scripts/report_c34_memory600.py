"""Render the saved C34 numerical evidence as a Croatian report and CSV."""
import sys,json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
OUT=ROOT/'reports/backtest/C34_MEMORY_600EUR'
p=json.loads((OUT/'summary.json').read_text()); r=p['results']; syms=p['config']['symbols']
fmt=lambda v: '—' if v is None else f'{v:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
lines=['# C13C: kompletan pregled s početnih 600 €','',
'Izrađeno 11.10.2026. Podaci: 11.10.2024.–8.10.2026. (zadnji dostupni kanonski Alpaca CSV; 9.10. nije uključen). Lokalni Python backtest, NE novi TradingView Strategy Tester rezultat. TradingView MCP/CLI nije vratio stanje grafa iako launcher potvrđuje otvoren CDP port.','',
'**Status: istraživanje, bez Critic PASS-a i bez brokerskih naloga.** Svaki red u pojedinačnoj usporedbi predstavlja zaseban hipotetski račun od 600 €. Zajednički račun je prikazan zasebno; ne zbrajamo zarade sedam računa kao zaradu jednog.','',
'## Što je testirano','',
'MU proizvodi memoriju DRAM/NAND/HBM; SNDK flash/SSD; SIMO kontrolere memorije (tajvanska tvrtka, američki listing); RMBS memorijska sučelja; MRAM specijaliziranu memoriju; WDC/STX diskove i pohranu. To nije sedam identičnih proizvođača čipova niti široka sektorska diversifikacija.','',
'Izvorni C13C signal ostaje: zaključna cijena > SMA200 i pad barem 5% u pet sesija; ulaz iduće otvaranje; zaštita 10% ispod poznatog vrha, samo gore. Novi vrh dana vrijedi iduću sesiju. Gap ispod stopa izlazi po lošijem otvaranju uz troškove.','',
'**Veličina je novi istraživački profil:** najviše 95% raspoloživog kapitala u jednoj poziciji, bez poluge i bez izvornog limita 500 USD. Reinvestira se rastući kapital. Zato rezultati nisu izravno usporedivi s ranijim SNDK testom koji je imao limit 500 USD. Nisu izmijenjeni originalni C13C ni aplikacija.','',
'Cijele dionice zaokružuju količinu dolje. Frakcije se modeliraju na šest decimala; to je HIPOTETSKI profil, bez provjere dostupnosti frakcija i stopova za svaki simbol u tvojem IBKR računu.','',
'## Rezultat po dionici','',
'| Dionica | Cijele: završno € | Frakcije: završno € | Frakcije: dobit € | Prinos frakcija | Maks. dnevni pad € računa | Zatvorene trgovine | Otvorena pozicija |',
'|---|---:|---:|---:|---:|---:|---:|---|']
for s in syms:
 a=r[f'{s}_whole_RECENT_BASE']; b=r[f'{s}_fractional_RECENT_BASE']
 lines.append(f"| {s} | {fmt(a['final'])} | {fmt(b['final'])} | {fmt(b['final']-600)} | {fmt(b['return_pct'])}% | {fmt(b['max_drawdown_pct'])}% | {b['n_closed']} | {'DA' if b['open_position'] else 'NE'} |")
lines+=['','Završna vrijednost uključuje tržišnu vrijednost otvorene pozicije; nije sve realizirana dobit. Postoci su ukupni kroz razdoblje, ne godišnje obećanje. Kod SNDK novac čeka dok podaci od 2025. ne omoguće SMA200; prvi ulaz tek 3.12.2025.','',
'## Jedan zajednički račun od 600 €','',
'U svakom trenutku najviše jedna pozicija. Kada više dionica istodobno ima signal, unaprijed je zadan prioritet MU → WDC → STX → SIMO → RMBS → MRAM → SNDK. To je pravilo odabira, ne optimizirani poredak i ne ravnomjerno raspoređen portfelj.','',
'| Profil | Završno € | Dobit € | Prinos | Najveći pad | Zatvorene trgovine |','|---|---:|---:|---:|---:|---:|']
for size in ['whole','fractional']:
 a=r[f'PORTFOLIO_{size}_RECENT_BASE']
 lines.append(f"| {size} | {fmt(a['final'])} | {fmt(a['final']-600)} | {fmt(a['return_pct'])}% | {fmt(a['max_drawdown_pct'])}% | {a['n_closed']} |")
lines+=['','**Dodavanje više simbola nije poboljšalo rezultat niti smanjilo pad:** zajednički frakcijski račun pada 55,78% od svojeg vrha. To je važnije od samog pozitivnog završetka.','',
'## Troškovi i EUR/USD','',
'Model svakog naloga: max(1 USD, 0,025% vrijednosti) + klizanje 0,01 USD po dionici. Za MRAM i kratku povijest SNDK sve množimo s 3: najmanje 3 USD po nalogu. To je konzervativna laboratorijska pretpostavka, NE verificirani IBKR cjenik. ADR naknade nisu uključene.','',
'Početna konverzija 600 € u USD uključuje 0,1% pretpostavljenog FX troška. Upotrijebljen je zadnji ranije poznati ECB tečaj 1,0932 USD/EUR; u USD odlazi 655,26408. Dnevno stanje u EUR vrednuje se po ECB tečaju toga dana, koji je dostupan prije američkog zatvaranja; ne koristi se za signale ili veličinu naloga. Završni tečaj 1,1186.','',
'Gotovina koja bi cijelo razdoblje samo stajala u USD završila bi na 585,79 €, bez kamata. Glavne tablice su vrijednosti prije završne konverzije; summary.json sadrži i dodatnih 0,1% izlaznog FX troška. Kod otvorene pozicije nisu odbijene buduće prodajne provizije. Dividende, porez i kamata na gotovinu nisu uključeni.','',
'## Stres troškova i izvršenja — frakcije','',
'| Dionica | Osnovno završno € | Dvostruki troškovi € | Svaki stop dodatno 1% lošiji € | Kupnja-držanje € |','|---|---:|---:|---:|---:|']
for s in syms+['PORTFOLIO']:
 a=r[f'{s}_fractional_RECENT_BASE']; b=r[f'{s}_fractional_RECENT_COST2']; c=r[f'{s}_fractional_RECENT_STOP100BPS']
 lines.append(f"| {s} | {fmt(a['final'])} | {fmt(b['final'])} | {fmt(c['final'])} | {fmt(a.get('buyhold_final_eur'))} |")
lines+=['','Kupnja-držanje koristi isti početni kapital, 95% ulaganja, frakcije, model ulaznih troškova i EUR/USD. Za SNDK kupnja tek 24.2.2025.; prije toga USD gotovina. Benchmark nije zatvoren na kraju, pa nema završnih prodajnih troškova. **Svih sedam pojedinačnih buy-and-hold računa ovdje završava iznad C13C-a.** To je naknadno promatrana snažno rastuća skupina, ne dokaz da će pasivna kupnja biti bolja ubuduće.','',
'WDC je posebno ograničenje: lokalna povijest prije izdvajanja SanDiska već je prilagođena faktorom 0,68132 i nije ponovno prilagođavana. Simulira se prilagođena serija, ne stvarna povijest novčanog računa s distribucijom SNDK dionica.','',
'## Starija kontrolna razdoblja — frakcijski račun resetiran na 600 €','',
'| Dionica | IS 2016–2020 prinos | Broj trgovina | WF 2021–2023 prinos | Broj trgovina |','|---|---:|---:|---:|---:|']
for s in syms+['PORTFOLIO']:
 a=r.get(f'{s}_fractional_IS_BASE'); b=r.get(f'{s}_fractional_WF_BASE')
 lines.append(f"| {s} | {fmt(a['return_pct'])+'%' if a else 'nema povijesti'} | {a['n_closed'] if a else '—'} | {fmt(b['return_pct'])+'%' if b else 'nema povijesti'} | {b['n_closed'] if b else '—'} |")
lines+=['','MRAM počinje tek u listopadu 2016.; do tada nema signala. SNDK nema stare periode. Ovo su vremenske provjere zamrznutog pravila, ne treniranje novog modela. Budući da je povijest već promatrana, ne predstavljaju novi neovisni holdout.','',
'## Promjene po kalendarskoj godini — isti neprekinuti frakcijski račun','',
'| Dionica | 2024. od 11.10. | 2025. | 2026. do 8.10. |','|---|---:|---:|---:|']
for s in syms+['PORTFOLIO']:
 a=r[f'{s}_fractional_RECENT_BASE']
 lines.append('| '+s+' | '+' | '.join(fmt(x['return_pct'])+'%' for x in a['annual'])+' |')
lines+=['','## Kvaliteta i ograničenja dokaza','',
f"Unaprijed registrirano 76 profila/provjera, K={p['k']}. SHA256 svih CSV-ova, izvornog freezea, novog enginea i ECB serije nalazi se u freeze datoteci. Validator cijena: 0 pogrešaka, 22 postojeća upozorenja.",
'',
'Za 16 novijih osnovnih profila: truncation na 31.3.2025., 31.12.2025., 30.6.2026. i mijenjanje budućih cijena zajedničkim nasumičnim faktorom daju 0 razlika u ranijim odlukama/equityju. Monotoni stopovi i cash ledger usklađeni; svi raw fillovi unutar OHLC i s pozitivnim volumenom, količina ispod 1% dnevnog volumena. Svi konkretni gap izlazi zapisani su u summary.json.','',
'**Neuspjela ekstremna provjera ostaje zabilježena:** početni adversarial test mijenjao je svaku buduću svijeću neovisnim faktorom 0,3–4. Takva sintetička serija dovela je račun do stanja u kojem minimalna prodajna provizija prelazi ostatak gotovine; engine je prekinuo assertom. To nije neuspjeh na stvarnim OHLC podacima, ali znači da model nema potpunu obradu bankrota pri ekstremnom sintetičkom stresu. Slabiji test s jednim faktorom prošao je; on NE poništava tu prazninu. Zato puni authenticity audit nije PASS.','',
'Block bootstrap: 1000 preslagivanja blokova po 20 dnevnih EUR prinosa; p95 pada spremljen po profilu. To je opisna osjetljivost uz postojeće podatke, ne prognoza. Nema potpune korekcije za multiple testing/DSR/PBO, ±20% parametarske osjetljivosti, tick/depth/spread ili real-fill reconciliation. Provjera intradnevnih obustava nije provedena.','',
'Prošla su 334 postojeća testa i 4 nova ciljana testa (frakcijska dostupnost, iduće otvaranje/gap, zabrana retroaktivnog stopa iz entry-bar higha, čekanje 200 barova). Testovi i osnovni audit ne znače da je strategija odobrena.','',
'## Zaključak','',
'U promatranom nedavnom razdoblju MU daje najveći frakcijski završni račun. SIMO je među dodatnim kandidatima zanimljiviji od RMBS/MRAM prema ovoj kombinaciji prinosa, pada i starije kontrole, ali to je naknadno opažanje, ne novo odobrenje. MRAM ne podnosi dvostruke troškove i vrlo loše prolazi starije WF razdoblje. SNDK ima prekratku povijest. Zajednički račun ne rješava rizik: noviji pad preko 50%, stariji WF minus.','',
'**Ne preporučuje se promjena stvarnog ulaganja na temelju ove tablice.** Originalni C13C, approved_list, paper aplikacija i brokerski računi ostali su nepromijenjeni. Nema naloga.','',
'## Datoteke i reprodukcija','',
'- summary.json: svih 76 slučajeva, godišnji rezultati, otvorene pozicije i audit.','- summary.csv: usporedna tablica za Excel.','- *_equity.csv: dnevno stanje u USD i EUR.','- *_trades.csv i *_events.json: svi ulazi, izlazi, količine, troškovi i saldo.','- equity_fractional.svg: pregled frakcijskih računa s istih početnih 600 €.','- Freeze: strategies/frozen/2026-10-11_C34_MEMORY_600EUR.json.','- Pokretanje: scripts/validate_data.py --through 2026-10-08, scripts/run_c34_memory600.py, scripts/report_c34_memory600.py (repo .venv/bin/python).']
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
pd.DataFrame([{k:v for k,v in a.items() if not isinstance(v,(dict,list))} for a in r.values()]).to_csv(OUT/'summary.csv',index=False)
colors=['#1668dc','#c47b16','#2b8a6e','#824acc','#c63c5c','#778325','#159baa','#111827']
paths=[]; maxv=max(pd.read_csv(OUT/f'{s}_fractional_RECENT_BASE_equity.csv').EUR.max() for s in syms+['PORTFOLIO'])
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="650" viewBox="0 0 1100 650"><rect width="1100" height="650" fill="white"/><g font-family="Arial" fill="#182333"><text x="65" y="35" font-size="24">C13C · svaki račun počinje sa 600 €</text><text x="65" y="62" font-size="15">Hipotetske frakcije · 11.10.2024.–8.10.2026. · modelirani troškovi i EUR/USD</text>']
for n in range(6):
 val=maxv*n/5; y=530-420*n/5
 svg.append(f'<path d="M70 {y}H1060" stroke="#e5e7eb"/><text x="5" y="{y+5}" font-size="13">{val:.0f} €</text>')
for s,color in zip(syms+['PORTFOLIO'],colors):
 d=pd.read_csv(OUT/f'{s}_fractional_RECENT_BASE_equity.csv'); pts=' '.join(f'{70+990*i/(len(d)-1):.1f},{530-420*v/maxv:.1f}' for i,v in enumerate(d.EUR))
 svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>')
 idx=(syms+['PORTFOLIO']).index(s); x=70+(idx%4)*250;y=580+(idx//4)*27
 svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="15">{html.escape(s)}: {r[s+"_fractional_RECENT_BASE"]["final"]:.2f} €</text>')
svg.append('<text x="70" y="552" font-size="13">11.10.2024.</text><text x="960" y="552" font-size="13">8.10.2026.</text></g></svg>')
(OUT/'equity_fractional.svg').write_text(''.join(svg))
print(OUT/'REPORT.md')
