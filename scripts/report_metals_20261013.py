"""Build Croatian C35 report from saved simulations; no network or trading."""
from pathlib import Path
import csv
import html
import json
import platform
import hashlib
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/research/C35_METALS_20261013'
BASE = ROOT/'reports/backtest/C35_METALS_20261013'
NAMES = {'MOM252':'Mjesečni trend 252', 'BREAKOUT':'Dnevni proboj 55/20',
         'ORB30':'Day trading: proboj 30 min', 'BUYHOLD':'Kupi i drži 50/50'}

def pct(x):
    return '—' if x is None else f'{100*x:,.2f}%'.replace(',', ' ').replace('.', ',')

def num(x):
    return '—' if x is None else f'{x:,.2f}'.replace(',', ' ').replace('.', ',')

def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,row))+' |' for row in rows])

def read_result(config, stage):
    paths=list((BASE/config).glob(f'{stage}_c*_p*.json'))
    if len(paths)!=1: raise ValueError((config,stage,paths))
    return json.loads(paths[0].read_text())

def main():
    dev=read_result('BASE','development'); ho=read_result('BASE','holdout')
    robust=json.loads((OUT/'robustness.json').read_text())
    selection=json.loads((BASE/'BASE/selection.json').read_text())
    winner=selection['winner']
    ranked=sorted((k for k in NAMES if k!='BUYHOLD'),key=lambda k:dev['results'][k]['WF']['sharpe'],reverse=True)
    candidate=winner or ranked[0]
    registration=json.loads((OUT/'registration.json').read_text())
    full=ho['results']; results=[]
    rows=[]
    for k in NAMES:
        x=full[k]['FULL']
        rows.append([NAMES[k],pct(x['total_return']),pct(x['cagr']),pct(x['max_drawdown']),num(x['sharpe']),x['trades'],pct(x['win_rate']),num(x['profit_factor'])])
    main_table=table(['Pravilo','Ukupno neto','Godišnje CAGR','Najveći pad','Sharpe','Trgovine','Dobitne','Profit factor'],rows)
    cost_rows=[]
    for k in NAMES:
        trades=pd.read_csv(BASE/f'BASE/holdout_{k}_FULL_c1_p1_trades.csv')
        friction_usd=(trades.shares*((trades.entry_price+trades.exit_price)*.00025+.02)).sum()
        cost_rows.append([NAMES[k],num(friction_usd),pct(full[k]['FULL']['exposure'])])
    verdict=(f'Prema unaprijed zadanom razvojnom kriteriju izabran je **{NAMES[winner]}**.' if winner
             else '**Nijedna aktivna strategija nije zadovoljila unaprijed zadani razvojni kriterij. Nema kvalificiranog pobjednika.**')
    lines=['# Zlato i srebro: desetogodišnje istraživanje za IBKR i mali račun',
           '', 'Datum: 13. listopada 2026. · Kapital korisnika: 500–2.000 EUR · Hrvatska · C35_METALS_20261013', '',
           verdict,
           'Ovo je rangiranje malog unaprijed određenog skupa pravila, a ne dokaz najbolje moguće strategije. Nijedan rezultat nije službeni Critic PASS niti signal za kupnju.', '',
           'Za početak istraživanja s ovim kapitalom praktičniji je rijetki swing bez poluge preko europskog fizički pokrivenog ETC-a nego učestalo trgovanje s minimalnim provizijama. To nije tvrdnja da je swing profitabilan.', '',
           '## Prototip za IBKR: signali i simulacija', '',
           'Izrađen je lokalni modul `scripts/ibkr_metals_signals.py` za PHAU/PHAG na AEB, s cijelim jedinicama u prikazu priuštivosti i provjerama kapitala od 500 do 2.000 EUR. Poveznica s brokerom u ovoj verziji jest preuzimanje snimke podataka preko IBKR MCP-a; skripta zatim radi lokalno. Nema trajne TWS veze, praćenja uživo ni slanja naloga.',
           '**Aktualno: PRIČEKAJ / DATA_INVALID.** Iz IBKR konektora dobiveno je 1.059 dovršenih dnevnih zapisa po instrumentu, od 22.8.2022. do 12.10.2026. PHAU ima 107, a PHAG 67 close vrijednosti izvan prijavljenog high/low raspona; dio je u aktualnom indikatorskom prozoru. Ponovljeni kraći PHAU upit također nije prošao provjeru. Nije utvrđeno koji je stupac pogrešan, pa podaci nisu popravljani nagađanjem.',
           'Te snimke izdvojene su u `IBKR_UNVALIDATED_*.csv`, izvan kanonskih ulaza za backtest. Modul ispravno blokira pouzdan signal, a ne prikazuje izmišljenu preporuku. Zasebno, sva tri testirana pravila nisu prošla razvojni kriterij čak ni na provjerenim Alpaca proxy podacima.',
           '[Upute za IBKR modul](READ_ONLY_IBKR.md) · [Problem IBKR podataka](DATA_ISSUES_IBKR.md) · [Trenutačna snimka signala](ibkr_signals_1000.json)', '',
           '## Rezultati u odnosu na kupi i drži', '',
           'Simulacija: 13.10.2016.–12.10.2026., početnih 10.000 USD, GLD/SLV, dva početna udjela od 50%, bez rebalansiranja. USD prinosi uključuju modelirane troškove, ali ne porez, tržišni utjecaj ili sve IBKR naknade. Broj trgovina uključuje prisilno zatvaranje na kraju uzorka.', '', main_table, '',
           'Sharpe je iz dnevnih neto prinosa, uz nultu referentnu kamatu. Najveći pad mjeri dnevno stanje portfelja; nije najgori intraday pad. Gotovina ne nosi kamatu. Profit factor je zbroj dobitaka podijeljen apsolutnim zbrojem gubitaka; nema smislenog omjera ako nema gubitaka.', '',
           table(['Pravilo','Ukupno modelirano trenje USD','Prosječna izloženost'],cost_rows), '',
           'Trošak u ovoj tablici je zbroj simuliranog klizanja/ticka svih dovršenih kupnji i prodaja; nije stvarno naplaćena brokerska provizija. Troškovni scenariji malih računa dodatno uključuju minimalnu/proporcionalnu proviziju.', '',
           '![Vrijednost portfelja](metals_equity.png)', '', '![Pad kapitala](metals_drawdown.png)', '',
           '## Kako je odabir odvojen od provjere', '',
           'IS: 13.10.2016.–2020.; WF: 2021.–2023.; HO: 2024.–12.10.2026. Parametri su fiksni, bez optimizacije. Ovo je vremenska validacija fiksnih pravila, a ne adaptivna walk-forward optimizacija.',
           'Razvojni uvjet: pozitivan WF ukupan prinos i Sharpe, najmanje deset zatvorenih trgovina u portfelju te najveći WF pad do 25%; zatim najveći WF Sharpe. Odabir je spremljen prije izvršavanja HO i vezan hashom uz simulator. Periodi IS/WF/HO zasebno počinju bez pozicija; puna desetogodišnja krivulja je zasebna kontinuirana simulacija.', '']
    periodrows=[]
    for k in NAMES:
        for period,source in [('IS',dev),('WF',dev),('HO',ho)]:
            m=source['results'][k][period]
            periodrows.append([NAMES[k],period,pct(m['total_return']),pct(m['max_drawdown']),num(m['sharpe']),m['trades']])
            results.append(dict(strategy=k,configuration='BASE',period=period,**{a:b for a,b in m.items() if a!='symbols'}))
    lines += [table(['Pravilo','Razdoblje','Neto prinos','Najveći pad','Sharpe','Trgovine'],periodrows),'',
              'Holdout je retrospektivan: pri provjeri kvalitete prije odabira pregledana je ekstremna SLV cijena iz siječnja 2026. Parametri i rangiranje nisu mijenjani prema HO rezultatu. Ne tvrdimo da je tržišna povijest bila potpuno nepoznata istraživačima.', '',
              '## Zlato i srebro pojedinačno', '']
    lines += [table(['Pravilo','Instrument','Puni neto prinos','Najveći pad','Trgovine'],[
        [NAMES[k],s,pct(full[k]['FULL']['symbols'][s]['total_return']),pct(full[k]['FULL']['symbols'][s]['max_drawdown']),full[k]['FULL']['symbols'][s]['trades']]
        for k in NAMES for s in ['GLD','SLV']]),'',
        'Pojedinačni rezultati odnose se na početnih 5.000 USD po instrumentu. GLD i SLV nisu dvije neovisne potvrde istog ruba. Pasivni portfelj ima različitu izloženost riziku od strategija koje borave u gotovini.', '',
        '## Troškovi i osjetljivost', '',
        'Osnovni model po kupnji i po prodaji: 2,5 bazna boda (0,025%) vrijednosti plus 0,01 USD po dionici. To je pretpostavka trenja, ne stvarna povijesna bid/ask rekonstrukcija. Testovi 2× i 3× povećavaju to trenje. Godišnji troškovi fonda već su sadržani u tržišnoj cijeni i nisu odbijeni drugi put.', '',
        'Osjetljivost je zajedničko skaliranje parametara: momentum 202/302 dana; proboj 44/16 i 66/24 dana; ORB 25/35 minuta zbog petominutne mreže. To nije iscrpna provjera svakog parametra zasebno. Dijagnostičke varijante ne zamjenjuju ranije odabranog kandidata.', '']
    stress=[]
    for config in ['BASE','COST2','COST3','SENS08','SENS12']:
        d=read_result(config,'development'); h=read_result(config,'holdout')
        for k in ['MOM252','BREAKOUT','ORB30']:
            stress.append([NAMES[k],config,pct(d['results'][k]['WF']['total_return']),num(d['results'][k]['WF']['sharpe']),pct(h['results'][k]['HO']['total_return'])])
    lines += [table(['Pravilo','Scenarij','WF neto','WF Sharpe','HO neto'],stress),'',
              '## Račun od 500, 1.000 i 2.000 EUR', '',
              'Provizijski scenarij: max(1,25 EUR, 0,05% naloga) po strani, uz osnovno trenje. U USD simulatoru koristi se stalni ilustrativni tečaj 1,10 USD/EUR: početnih 550/1.100/2.200 USD i minimum 1,375 USD. Ovo izolira učinak naknada; rezultati u tablici nisu povijesni EUR prinosi niti točan IBKR obračun. Vanjske burzovne naknade nisu uključene, a frakcijske jedinice europskog ETC-a nisu potvrđene.', '']
    fees=[]
    for cap in [500,1000,2000]:
        d=read_result(f'FEE{cap}','development'); h=read_result(f'FEE{cap}','holdout')
        for k in ['MOM252','BREAKOUT','ORB30']:
            m=h['results'][k]['FULL']; fees.append([f'{cap} €',NAMES[k],pct(d['results'][k]['WF']['total_return']),pct(h['results'][k]['HO']['total_return']),pct(m['total_return']),m['trades']])
    lines += [table(['Kapital za troškovni scenarij','Pravilo','WF neto','HO neto','Puni neto','Trgovine'],fees),'',
              'Kod ORB-a dopušteni planirani gubitak iznosi 0,5% kapitala pojedinačnog udjela, odnosno 0,25% ukupnog računa kada su udjeli jednaki. Ako dvije minimalne provizije već prelaze taj iznos, trgovina se preskače. Nula trgovina nije profitabilnost nego neizvedivost pod tim pravilima. Gap može uzrokovati gubitak veći od planiranog.', '',
              '[IBKR službeni cjenik](https://www.interactivebrokers.ie/en/pricing/commissions-stocks.php): Tiered osnovica za mala EUR trgovanja od 1,25 € po strani plus vanjske naknade; Fixed SMART tipično najmanje 3 € po strani za navedena europska tržišta. Dvadeset Fixed kupnja–prodaja ciklusa mjesečno iznosi 120 € osnovnih provizija: 24% računa od 500 € ili 6% računa od 2.000 €, prije spreadova.', '',
              '## Valuta i europski instrumenti', '',
              'PHAU (WisdomTree Physical Gold, ISIN JE00B1VS3770) i PHAG (WisdomTree Physical Silver, JE00B1VS3333) imaju europske EUR kotacije od 2007. IBKR MCP pronašao je amsterdamske ugovore 44216217 i 44216214. Pronalazak ugovora nije potvrda dozvola ni prihvaćenog naloga na korisnikovu računu.',
              'ETC je ovdje fizički pokriveni dužnički vrijednosni papir; nije UCITS fond samo zato što je UCITS eligible. Dostupnost treba provjeriti prema konkretnom ISIN-u, burzi, KID-u i IBKR dozvolama. EUR kotacija ne uklanja valutni rizik nehedgiranog metala.',
              'Alpaca GLD/SLV imaju druge sate, cijene, strukturu i naknade od PHAU/PHAG. Rezultati se ne prenose automatski. IBKR MCP zahtjev za 3.000 dnevnih barova odbijen je zbog limita 1.000; petogodišnji odgovor nije dao desetogodišnje pokriće i sadržavao je neusklađene metapodatke. Zato nije korišten za lažni europski backtest.', '',
              'ECB dnevni referentni tečajevi koriste se samo za dodatno vrednovanje USD portfelja u EUR, uz isti ili najbliži raniji datum. To nije izvršivi brokerski tečaj i ne uključuje naknade konverzije. Primjer: metal +10% u USD uz pad dolara 10% prema euru daje približno −1% u EUR (1,10 × 0,90 − 1).', '']
    eurpath=OUT/'eur_valuation.json'
    if eurpath.exists():
        eur=json.loads(eurpath.read_text())
        lines += ['Dodatni EUR prikaz spremljen je u `eur_valuation.json` i CSV-ove; grafikon je normaliziran na početnu vrijednost 100. To je vrednovanje američkog portfelja, ne rezultat europskog ETC-a.', '', '![EUR vrednovanje](metals_equity_eur.png)', '']
    lines += ['## Precizna pravila algoritama', '',
              '1. **Mjesečni trend 252:** na posljednjem zatvaranju mjeseca usporedi cijenu s cijenom prije 252 sesije. Ako je viša, drži instrument; inače gotovinu. Promjena na sljedećem otvaranju. Bez intraday zaštitnog stopa. Na početku nema 252 ranija dana, pa strategija ostaje u gotovini dok indikator ne postane dostupan.',
              '2. **Dnevni proboj 55/20:** kupnja na sljedećem otvaranju nakon zatvaranja iznad svih prethodnih 55 zatvaranja; izlaz na sljedećem otvaranju nakon zatvaranja ispod prethodnih 20 zatvaranja. Oba prozora isključuju signalni dan. Nema piramidiranja ni intraday stopa.',
              '3. **ORB30:** raspon 09:30–10:00 New York. Prvo kasnije potpuno zaključeno petominutno zatvaranje iznad gornje granice, prije podneva, daje ulaz na idućem openu. Stop je donja granica prvih 30 minuta. Najviše jedan pokušaj dnevno po instrumentu; izlaz na otvaranju posljednje petominutne sveće. Stop se može aktivirati u ulaznoj sveći. Gap kroz stop izlazi po lošijem openu. Planirani rizik uključuje troškove.', '',
              'Sva pravila koriste dva samofinancirajuća početna 50% udjela, bez poluge i shortanja. Udjeli tijekom vremena mogu odstupati od 50/50. Ovo su simulacijska pravila; nisu aktivirani u aplikaciji niti kod brokera.', '',
              '## Stvarni primjeri iz simulacije', '']
    examples=[]
    for k in ['MOM252','BREAKOUT','ORB30']:
        t=pd.read_csv(BASE/f'BASE/holdout_{k}_FULL_c1_p1_trades.csv').sort_values(['entry_date','symbol'])
        for label,r in [('Prva',t.iloc[0]),('Posljednja',t.iloc[-1])]:
            examples.append([NAMES[k],label,r.symbol,r.entry_date,r.exit_date,num(r.entry_price),num(r.exit_price),num(r.pnl),r.reason])
    lines += [table(['Pravilo','Primjer','Simbol','Ulaz','Izlaz','Ulaz USD','Izlaz USD','Neto PnL USD','Razlog'],examples),'',
              'PnL primjera proizlazi iz simuliranog broja frakcijskih dionica i tadašnje veličine udjela; nije zarada koju bi dobio račun od 500 €. Za ORB su točna vremena i broj dionica u CSV-u trgovina.', '',
              'Ilustracija plana rizika, ne preporuka naloga: račun 1.000 €, planirani maksimalni gubitak 10 €, pozicija 300 € i stop 2% ispod ulaza daju 6 € cjenovnog rizika. Dodavanjem najmanje 2,50 € osnovnih provizija dolazimo na 8,50 €, prije spreada, drugih naknada i gapa. Stop nije jamstvo tog maksimalnog gubitka.', '',
              '## Koncentracija i simulacija nepovoljnijih putanja', '']
    rr=[]
    for k in ['MOM252','BREAKOUT','ORB30']:
        for period in ['WF','HO']:
            r=robust['strategies'][k]['periods'][period]
            rr.append([NAMES[k],period,num(r['concentration']['ex_top3_total_pnl_usd']),pct(r['bootstrap']['max_drawdown_p95']),pct(r['bootstrap']['negative_total_return_fraction'])])
    lines += [table(['Pravilo','Razdoblje','PnL bez top-3, USD','95. percentil pada','Udio negativnih bootstrap putanja'],rr),'',
              'Bootstrap: 2.000 kružnih uzoraka dnevnih neto prinosa u blokovima od pet sesija, seed 20261013. Ne ponavlja strategiju i ne modelira sve buduće režime, nelikvidnost ili nove gapove. Udio negativnih putanja nije prognozirana vjerojatnost budućeg gubitka. Izbacivanje top-3 prikazuje opisni zbroj zatvorenih PnL-ova nejednakih veličina, ne ponovnu simulaciju portfelja bez tih trgovina.', '',
              f'Ledger prije kampanje K={registration["k_before"]}; nakon upisa 24 unaprijed planirane konfiguracije K={registration["k_after"]}. Benchmark nije novi optimizacijski pokušaj. **DSR i PBO nisu izračunati ni potvrđeni.** Sama pozitivna povijesna brojka ne prolazi statistički Critic.', '',
              '## Podaci, provjere i granice zaključka', '',
              '- Alpaca SIP, split-only; lokalni CSV i SHA256 otisci. Dnevni podaci počinju 4.1.2016.; 197 sesija prethodi početku evaluacije. Nema izmišljene povijesti za zagrijavanje indikatora.',
              '- Intraday se koristi samo unutar regular sesije prema kalendaru, uključujući skraćene dane. Nepotpune ili nevaljane sesije preskaču se; popis je u JSON rezultatima i podatkovnom manifestu.',
              '- Po instrumentu: 2.709 dnevnih zapisa, 210.531 regular petominutnih zapisa. Od 15 očekivanih intervala koji nedostaju, jedan je prije evaluacije. U evaluaciji je isključeno pet IS dana po instrumentu; WF i HO imaju nula isključenih dana. Nema sintetiziranih cijena unutar praznina.',
              '- **ORB retrospektivno filtrira kompletnost cijele sesije.** To je filtriranje kvalitete budućeg dijela dana i može proizvesti selekcijsku pristranost. Rezultat nije dokaz implementacije uživo bez lookahead rizika.',
              '- Petominutni OHLC ne otkriva stvarni redoslijed svake cijene, spread ni red čekanja. Fillovi su hipotetski. Izloženost ORB-a približna je na mreži od pet minuta.',
              '- Nije potvrđen puni trošak svake IBKR rute, mogućnost frakcija ETC-a, dozvole računa, porezni obračun ili stvarna izvršivost naloga.',
              '- Neovisni audit 16 osnovnih kombinacija strategija/razdoblja potvrdio je izvorne cijene, vremenski pomak i identitet početni kapital + zatvoreni PnL = završni kapital. Najveća količina prema volumenu ulaznog 5m bara bila je 2,077%; to nije potvrda fill-a po openu niti kalibracija tržišnog utjecaja.',
              '- Postojeći laboratorijski Critic traži provjeru primarnog univerzuma MU/WDC/STX i nije primjenjiv kao automatska potvrda metala. approved_list nije mijenjan.',
              '- Sintetičke provjere obuhvaćaju signalni pomak, truncation, pokvarene buduće podatke, gap/same-bar stop, skraćenu i nepotpunu sesiju, provizije i risk budget. Postojeći projektni testovi: 338 prošlo. To nije potvrda profitabilnosti.', '',
              '## Što slijedi prije primjene na IBKR-u', '',
              'Za kandidata koji bi se dalje istraživao potrebno je zasebno preuzeti i validirati podatke odabranog EUR ETC-a, koristiti stvarne cijele jedinice i provizijsku rutu, provjeriti KID/dozvole te odraditi nezavisnu simulaciju i forward test. GLD/SLV test nije dovoljan da se preskoče ti koraci. Za ovaj kapital futures/CFD poluga nije prečac oko provizija i rizika.', '',
              '## Izvori i reproduciranje', '',
              '[Izvori, instrumenti i otvoreni projekti](IZVORI_I_INSTRUMENTI.md) · [Neovisni audit](AUDIT.md) · [SLV podatkovno upozorenje](SLV_DATA_WARNING.md) · [Godišnji rezultati](yearly_metrics.csv) · [Robusnost](robustness.json)', '',
              'Otvoreni projekti pregledani su kao reference: QuantConnect LEAN (Apache-2.0) i backtesting.py (AGPL-3.0). Njihov kod nije preuzet ni izvršavan, a tuđi objavljeni prinosi nisu naši rezultati.', '',
              'Izvršavanje iz korijena projekta: prvo `scripts/validate_data.py --through 2026-10-12`, zatim provjera metalnih CSV-ova i manifest; `scripts/backtest_metals_20261013.py --self-test`; `scripts/run_metals_campaign_20261013.py --stage development`; pregled/pohrana izbora; tek onda `--stage holdout`. Postprocesor `scripts/analyze_metals_20261013.py --base reports/backtest/C35_METALS_20261013/BASE` generira grafikone. Simulator koristi pandas/numpy; grafikoni dodatno matplotlib.', '',
              '**Napomena:** ovo je hipotetska povijesna simulacija, a ne ostvareno trgovanje. Rezultati ne jamče buduće prinose; ovise o podacima, troškovima i pretpostavkama izvršenja. Materijal služi istraživanju i obrazovanju, nije nalog ni preporuka kupnje. [Alpaca objave o rizicima](https://alpaca.markets/disclosures). Nije poslan nijedan brokerski nalog.', '']
    (OUT/'IZVJESTAJ.md').write_text('\n'.join(lines))
    pd.DataFrame(results).to_csv(OUT/'summary_metrics.csv',index=False)
    env={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
         'files_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'scripts/backtest_metals_20261013.py',ROOT/'strategies/frozen/2026-10-13_C35_METALS_20261013.json']}}
    (OUT/'reproducibility.json').write_text(json.dumps(env,indent=2))
    # A self-contained report, including chart pixels; Markdown is the canonical full narrative.
    import base64
    images=''.join('<figure><img alt="'+html.escape(n)+'" src="data:image/png;base64,'+base64.b64encode((OUT/p).read_bytes()).decode()+'"></figure>'
                   for n,p in [('Vrijednost portfelja','metals_equity.png'),('Pad kapitala','metals_drawdown.png'),('EUR vrednovanje','metals_equity_eur.png')] if (OUT/p).exists())
    table_html='<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in ['Pravilo','Ukupno','Godišnje','Pad','Sharpe','Trgovine','Dobitne','PF'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    blocks=[]
    for cap in [500,1000,2000]:
        blocks.append(f'<section data-cap="{cap}"'+(' hidden' if cap!=1000 else '')+'><h2>Troškovni scenarij '+str(cap)+' €</h2><table><tr><th>Pravilo</th><th>WF neto</th><th>HO neto</th><th>Puni neto</th><th>Trgovine</th></tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in row[1:])+'</tr>' for row in fees if row[0]==f'{cap} €')+'</table></section>')
    document='''<!doctype html><html lang="hr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Zlato i srebro · C35</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1100px;margin:auto;padding:32px 20px;background:#f6f5f0;color:#182c32}h1{font-size:clamp(28px,5vw,48px);line-height:1.15}h2{margin-top:36px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:right;padding:10px;border-bottom:1px solid #ccd4d2}th:first-child,td:first-child{text-align:left}img{width:100%;height:auto}figure{margin:28px 0}select{font:inherit;padding:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.65 system-ui}a{color:#006451}.scroll{overflow-x:auto}.label{color:#4d645b;letter-spacing:2px;font-size:12px}details{margin-top:32px}summary{font-weight:600;cursor:pointer}</style><main><p class="label">ISTRAŽIVANJE / HRVATSKA / IBKR / 13.10.2026.</p><h1>Zlato i srebro:<br>što ostaje nakon troškova?</h1><p>''' + html.escape(verdict.replace('**',''))+'''</p><p>Američki GLD/SLV · 13.10.2016.–12.10.2026. · hipotetski USD portfelj · nije potvrđen EUR ETC backtest ni Critic PASS.</p><h2>Desetogodišnji rezultat</h2><div class="scroll">'''+table_html+'</div>'+images+'''<h2>Mali račun i minimalna provizija</h2><label for="capital">Kapital scenarija </label><select id="capital"><option>500</option><option selected>1000</option><option>2000</option></select><p>Stalni ilustrativni tečaj 1,10 USD/EUR služi samo za model naknada; ovo nisu povijesni EUR prinosi. Vanjske naknade i frakcije ETC-a nisu potvrđene.</p><div id="fees" class="scroll" aria-live="polite">'''+''.join(blocks)+'''</div><details><summary>Cijeli izvještaj i metodologija</summary><pre>'''+html.escape('\n'.join(lines))+'''</pre></details><p>Povijesna simulacija nije jamstvo buduće zarade. Nema naloga niti aktivacije strategije.</p></main><script>document.getElementById('capital').addEventListener('change',function(){document.querySelectorAll('[data-cap]').forEach(s=>s.hidden=s.dataset.cap!==this.value)});</script></html>'''
    (OUT/'analiza.html').write_text(document)
    print(json.dumps({'report':str(OUT/'IZVJESTAJ.md'),'html':str(OUT/'analiza.html'),'selection':selection},ensure_ascii=False))

if __name__=='__main__':
    main()
