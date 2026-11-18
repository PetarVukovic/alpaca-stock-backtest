"""Offline C36 evidence report; reads saved simulations, never places orders."""
from pathlib import Path
import base64
import hashlib
import itertools
import json
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis, rankdata

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/research/METALS_ADV_20261013'
RUN = ROOT / 'reports/backtest/C36_METALS_ADV_20261013'
FAMILIES = ['KAMA', 'ENSEMBLE', 'ROTATE']
LABELS = {'KAMA':'Adaptivni trend KAMA', 'ENSEMBLE':'Tri horizonta + volatilnost',
          'ROTATE':'Rotacija zlato/srebro/gotovina', 'BUYHOLD':'Drži: cilj 50:50', 'CASH':'Gotovina'}

def returns(path, capital=1000):
    x = pd.read_csv(path)
    e = np.r_[capital, x.equity_eur.to_numpy()]
    return e[1:] / e[:-1] - 1

def sharpe(x):
    return np.mean(x, axis=0) / np.std(x, axis=0, ddof=1)

def uncertainty():
    rng = np.random.default_rng(20261013)
    paths = [RUN/'PROXY'/f'{f}_{v}_1000_WF_equity.csv'
             for f in FAMILIES for v in ['BASE','PARAM08','PARAM12']]
    mat = np.column_stack([returns(p) for p in paths])
    blocks = [b[5:-5] for b in np.array_split(np.arange(len(mat)), 8)]
    ranks = []
    for chosen in itertools.combinations(range(8), 4):
        train = np.concatenate([blocks[i] for i in chosen])
        test = np.concatenate([blocks[i] for i in range(8) if i not in chosen])
        winner = int(np.argmax(sharpe(mat[train])))
        relative_rank = rankdata(sharpe(mat[test]), method='average')[winner] / (mat.shape[1]+1)
        ranks.append(float(relative_rank))
    result = {'pbo_diagnostic':float(np.mean(np.array(ranks)<=.5)), 'cscv_splits':len(ranks),
              'cscv_relative_ranks':ranks, 'matrix_columns':[p.stem for p in paths],
              'warning':'Descriptive CSCV on realized WF returns, 5-day trimmed block edges. Not independent holdout or full purged strategy refitting.',
              'families':{}}
    for family in FAMILIES:
        r = returns(RUN/'PROXY'/f'{family}_BASE_1000_WF_equity.csv')
        n = len(r)
        starts = rng.integers(0,n,size=(2000,(n+4)//5))
        indices = ((starts[:,:,None]+np.arange(5))%n).reshape(2000,-1)[:,:n]
        e = np.cumprod(1+r[indices],axis=1)
        e = np.column_stack([np.ones(2000),e])
        dd = (1-e/np.maximum.accumulate(e,axis=1)).max(axis=1)
        sr = float(sharpe(r)); gamma = .5772156649015329
        # Approximate expected maximum under nominal independent trials.
        variance_sr = max(float(np.var(sharpe(mat),ddof=1)), 1/(n-1))
        dsr = {}
        for count in [9,507]:
            benchmark = np.sqrt(variance_sr)*((1-gamma)*norm.ppf(1-1/count)+gamma*norm.ppf(1-1/(count*np.e)))
            denom = np.sqrt(1-float(skew(r,bias=False))*sr+(float(kurtosis(r,fisher=False,bias=False))-1)/4*sr*sr)
            probability = float(norm.cdf((sr-benchmark)*np.sqrt(n-1)/denom))
            dsr[str(count)] = {'nominal_probability_above_deflated_threshold':probability,
                               'one_minus_probability':1-probability,'daily_sharpe_threshold':float(benchmark)}
        result['families'][family] = {'bootstrap_dd95':float(np.quantile(dd,.95)),
            'bootstrap_fraction_positive_total':float(np.mean(e[:,-1]>1)),
            'dsr_sensitivity':dsr, 'n_days':n}
    result['dsr_warning'] = 'Nominal sensitivity, not certified p-values: trials correlated, total507 includes other campaigns, serial dependence not fully corrected. No Critic PASS inferred.'
    (OUT/'uncertainty.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def pct(x): return f'{100*x:.2f}%'.replace('.',',')
def eur(x): return f'{x:,.2f} €'.replace(',',' ').replace('.',',')
def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])

def main():
    proxy = pd.concat([pd.read_csv(RUN/'PROXY'/f'{stage}_metrics.csv') for stage in ['development','exposed']],ignore_index=True)
    target = pd.read_csv(RUN/'IBKR/diagnostic_metrics.csv')
    proxy.assign(dataset='GLD/SLV proxy').to_csv(OUT/'proxy_results.csv',index=False)
    target.assign(dataset='PHAU/PHAG IBKR').to_csv(OUT/'ibkr_results.csv',index=False)
    selection=json.loads((OUT/'selection.json').read_text())
    stats=uncertainty()
    def get(frame,family,cap,period,variant='BASE'):
        return frame[(frame.strategy==family)&(frame.capital==cap)&(frame.period==period)&(frame.variant==variant)].iloc[0]
    summary=[]
    for f in FAMILIES+['BUYHOLD','CASH']:
        a=get(proxy,f,1000,'FULL'); b=get(proxy,f,1000,'WF')
        summary.append([LABELS[f],eur(a.final_eur),pct(a.total_return),pct(a.cagr),pct(a.max_drawdown),pct(b.total_return),f'{a.sharpe:.2f}' if pd.notna(a.sharpe) else '—',int(a.orders),eur(a.fees_eur+a.slippage_eur)])
    doc=['# Napredni algoritmi za zlato i srebro — C36',
         'Datum: 13. listopada 2026. • Hrvatska / EUR • samo signali i simulacija.',
         '**Zaključak: '+('nijedna strategija nije prošla unaprijed zadani razvojni odabir.' if selection['winner'] is None else f"Razvojni kandidat: {selection['winner']}; to nije Critic PASS.")+' Trenutačni status: PRIČEKAJ.**',
         'Istražena su tri složenija pravila uz 90 unaprijed registriranih scenarija: 3 algoritma × 3 veličine računa × 5 postavki × 2 skupa podataka. To nisu 90 neovisnih ideja. Lokalni ledger narastao je s 417 na 507. Obitelji su povezane s trendom; složenost nije dokaz prednosti.',
         '## 1. Desetogodišnji američki proxy, račun 1.000 €',
         'GLD/SLV, 13.10.2016.–12.10.2026. Stvarni povijesni ECB tečaj, strogo prethodni dostupni dan; cijele jedinice. Model europskih naknada na američkim instrumentima služi istraživanju. Ovo nije desetogodišnji rezultat PHAU/PHAG niti potvrda dostupnosti GLD/SLV hrvatskom malom ulagatelju.',
         table(['Pravilo','Završno','Ukupno','CAGR','Najveći pad','Provjera 2021.–2023.','Sharpe','Transakcije','Naknade + odstupanje'],summary),
         'Sharpe je iz dnevnih neto prinosa, bez nerizične stope; gotovina nema kamatu. Najveći pad mjeri se iz dnevnog zatvaranja, ne najgora unutardnevna točka. Broj transakcija uključuje kupnje, prodaje, djelomične prilagodbe i završnu likvidaciju; nije broj neovisnih trgovina. C36 nije izravno usporediv s prethodnim C35: ovdje su stvarna povijesna EUR konverzija, cijele jedinice i minimum3 € po nalogu, dok je C35 osnovni test koristio frakcije i drugi troškovni model.',
         '## 2. Stvarni IBKR instrumenti: PHAU i PHAG',
         'Koriste se ugovori PHAU 44216217 i PHAG 44216214, primarni listing AEB, EUR prema izdavateljevu listingu. SMART TWO_YEARS daje 509 završenih dnevnih zapisa od 14.10.2024. do 12.10.2026. Svih 12 izostavljenih radnih dana odgovara burzovnim praznicima; nema OHLC nepravilnosti. Sama povijesna poruka nema polje valute, pa identitet povezujemo s listingom. Kupovna dozvola na osobnom računu nije potvrđena.',
         '**Simulacija je samo 1.10.2025.–12.10.2026.** Raniji zapisi služe zagrijavanju indikatora, uključujući najdulji pomaknuti prozor od 240 sesija. Dugački odgovor FIVE_YEARS nije korišten zbog proturječnih metapodataka. Kratko, već viđeno razdoblje nije neovisna potvrda strategije.',
         '**Cijele jedinice mijenjaju usporedbu:** 50:50 je ciljani početni omjer, a ne zajamčena realizirana raspodjela. Na IBKR računu500 € polovica kapitala nije dovoljna za jednu PHAU jedinicu; usporedni portfelj zato kupuje samo6 PHAG jedinica i ostatak drži u gotovini. Na drugim računima omjer također odstupa zbog zaokruživanja. Nisu modelirane frakcije ETC-a.']
    for cap in [500,1000,2000]:
        rows=[]
        for f in FAMILIES+['BUYHOLD','CASH']:
            a=get(target,f,cap,'DIAGNOSTIC')
            rows.append([LABELS[f],eur(a.final_eur),pct(a.total_return),pct(a.max_drawdown),int(a.orders),eur(a.fees_eur+a.slippage_eur),pct(a.mean_exposure)])
        doc += [f'### Početni račun {cap} €',table(['Pravilo','Završno','Prinos','Najveći pad','Transakcije','Troškovi','Prosječni uloženi udio'],rows)]
    doc += ['## 3. Precizna pravila',
      '**KAMA:** Kaufmanov adaptivni prosjek, ER10, brzi period2 i spori30. Početna vrijednost SMA prvih10 zatvaranja. SC=(ER×(2/3−2/31)+2/31)²; ER=apsolutna promjena kroz10 sesija / zbroj apsolutnih dnevnih promjena. Na prvom danu tjedna: ako je prethodno zatvaranje iznad KAMA i KAMA iznad vrijednosti prije5 sesija, cilj po metalu je 50% × min(1,10%/vol20). Inače gotovina.',
      '**ENSEMBLE:** na prvom danu tjedna broj pozitivnih uvjeta C>SMA50, C>SMA100 i C>SMA200 dijeli se s3. Cilj po metalu: 50% × taj udio × min(1,10%/vol60). Traži se cijeli najdulji prozor. Bez signala nema pozicije.',
      '**ROTATE:** na prvom danu mjeseca prihvatljiv je metal s pozitivnim prinosom126 sesija i C>SMA200. Bira se veći prinos. Postojeći izbor zadržava se ako je prihvatljiv, osim kad drugi ima više od2 postotna boda bolji prinos. Ciljni udio pobjednika min(1,10%/vol60); ostalo gotovina. Ako nijedan nije prihvatljiv, sve gotovina. Model pamti prethodni izbor i prije početka segmenta, ali račun svaki segment počinje bez pozicije.',
      'Volatilnost je uzoračka standardna devijacija dnevnih logaritamskih EUR prinosa ×√252. Nula, nevaljana vrijednost ili nedovoljno podataka daju nulti udio. Ciljana volatilnost nije obećanje da gubitak neće premašiti10%. Nema poluge, shortanja ni zaštitnog naloga između zakazanih prilagodbi.',
      'Zatvorena svijeća određuje signal. Izvršenje je sljedeće zakazano otvaranje uz trošak. Količina je cijeli broj iz ciljnog udjela i početne vrijednosti portfelja na otvaranju, uz prodaju prije kupnje i provjeru raspoložive gotovine. Taj model pretpostavlja izvršenje blizu otvaranja; bez tickova ne dokazuje stvarnu cijenu ni dostupnost količine. Na zadnji dan testa sve se modelirano prodaje po zatvaranju uz iste troškove.',
      '## 4. Troškovi i razlike između veličina računa',
      'Osnova: max(3 €,0,05% vrijednosti naloga) provizije +0,05% odstupanja cijene po strani. To je model Fixed SMART za europske proizvode, a ne izvadak stvarno plaćenih naknada. Dvostruki i trostruki stres množe i proviziju i odstupanje. Porez, pretplate na podatke i kamate nisu uključeni. Trošak upravljanja proizvodom nije dodan drugi put jer je već u povijesnoj cijeni.',
      'Kupnja i prodaja zajedno počinju od6 €: 1,2% računa500 €,0,6% računa1.000 € i0,3% računa2.000 €, prije odstupanja. Kod dvaju metala i čestog prilagođavanja plaća se više naloga. Zato složenije upravljanje rizikom može smanjiti bruto izloženost, a povećati neto gubitak.',
      '[IBKR službene provizije](https://www.interactivebrokers.ie/en/pricing/commissions-stocks.php) • [AEB naknade](https://www.interactivebrokers.ie/en/accounts/fees/combinedEurStkFees.php?nhf=T).',
      '### Utjecaj troškova i parametara — proxy WF, 1.000 €']
    doc += [table(['Pravilo','Osnovno','Trošak ×2','Trošak ×3','Prozori ×0,8','Prozori ×1,2'],[[LABELS[f]]+[pct(get(proxy,f,1000,'WF',v).total_return) for v in ['BASE','COST2','COST3','PARAM08','PARAM12']] for f in FAMILIES])]
    doc += ['## 5. Provjera pouzdanosti',
      'Pravila i pokušaji zabilježeni su prije simulacije. Jedina ranija izmjena specifikacije pomaknula je početak IBKR testa nakon provjere dostupnih podataka, prije gledanja rezultata. IS je2016.–2020., razvojna provjera2021.–2023.; rezultat odabira pohranjen je prije ostalih simulacija. **Cijelu povijest već smo vidjeli u prethodnom istraživanju, pa2024.–2026. nije čist holdout.** Nema tvrdnje da su ovo neovisni prospektivni testovi.',
      'Uvjeti odabira na računu1.000 €: pozitivan IS i WF, WF pad≤25%, najmanje10 događaja prodaje u oba razdoblja, pozitivan WF pri dvostrukom trošku i oba pomaka parametara. To je razvojni filtar; događaji prodaje nisu neovisne zatvorene trgovine, pa sami ne zadovoljavaju Critic uzorak.',
      f"Opisni CSCV/PBO: {stats['pbo_diagnostic']:.3f}, iz70 kombinacija8 vremenskih blokova i9 povezanih varijanti. Rubovi blokova skraćeni su za5 dana. Ovo je analiza ostvarenih dnevnih prinosa, bez ponovnog treniranja modela, a ne potpuni purged cross-validation. Nizak PBO može se pojaviti i među gubitničkim strategijama; nije dokaz pozitivne prednosti.",
      table(['Pravilo','Bootstrap 95. percentil pada','Udio ponovljenih uzoraka s pozitivnim ukupnim prinosom'],[[LABELS[f],pct(stats['families'][f]['bootstrap_dd95']),pct(stats['families'][f]['bootstrap_fraction_positive_total'])] for f in FAMILIES]),
      'Bootstrap:2.000 kružnih preslagivanja dnevnih prinosa u blokovima5 dana, WF račun1.000 €, seed20261013. To nisu ponovo izvršene strategije ni procjene vjerojatnosti buduće zarade. DSR osjetljivost za nominalnih9 i507 pokušaja nalazi se u uncertainty.json; korelacije pokušaja i serijska ovisnost nisu potpuno obrađene, stoga nema potvrđenog statističkog PASS-a.',
      '## 6. Open-source projekti i što je stvarno upotrijebljeno',
      'Pregledani su QuantConnect LEAN, TA-Lib, River, FinRL-X i vectorbt. Njihove licence, izvori i ograničenja dokumentirani su u OSS_RESEARCH.md. Backtest je naš čitljiv Python skript s NumPy/Pandas, ne preuzet navodni profitabilni bot. Projekti služe kao tehnička referenca; njihovo postojanje ne dokazuje profitabilnost na zlatu/srebru.',
      'ML/RL nije dodan samo radi složenosti: dva korelirana instrumenta i ponovljeno gledanje iste povijesti daju mnogo prostora za preprilagodbu. Adaptivni prosjek, kombinacija vremenskih prozora i dinamički udjeli već uvode složenije ponašanje koje se može mehanički provjeriti.',
      '## 7. Signali i praktični sljedeći korak',
      'Lokalni modul prikazuje istraživački status i ciljane udjele iz zamrznutih pravila. Status ostaje PRIČEKAJ, nema prihvaćene strategije, nema veze za slanje naloga ni aktivnog nadzora. Povijesna ciljana težina nije današnja preporuka za kupnju.',
      'Najmanje loš razvojni rezultat nije isto što i najbolji algoritam za stvarni novac. Sljedeća odvojena hipoteza mogla bi istražiti znatno rjeđe promjene ili minimalni prag promjene pozicije, ali to ovdje nije optimizirano nakon rezultata. Potvrda bi zahtijevala nove buduće podatke i praćenje stvarnih troškova u simulaciji.',
      '## 8. Datoteke i ponavljanje',
      '- Pravila: strategies/frozen/2026-10-13_C36_METALS_ADV_20261013.json\n- Skript: scripts/backtest_metals_advanced_20261013.py\n- Rezultati, dnevna vrijednost, gotovina, količine i transakcije: reports/backtest/C36_METALS_ADV_20261013/\n- Podaci/izvori: DATA_FEASIBILITY.md i canonical_validation.json\n- Istraživanje projekata: OSS_RESEARCH.md\n- Neovisna provjera: AUDIT.md\n- Status signala: README_PROTOTYPE.md\n- Registracija, hashovi i izbor: registration.json, registration_amendment.json, selection.json, selection_binding.json',
      'Svaki segment simulacije kreće iz početne gotovine; FULL je zaseban kontinuirani račun. Izlazne datoteke namjerno se ne prepisuju. Za ponavljanje se navodi nova izlazna mapa, ista specifikacija, registracija i nepromijenjeni podaci.',
      '## Obvezna napomena',
      'Ovo je hipotetska povijesna simulacija, a ne stvarno trgovanje. Povijesni rezultat ne jamči budući. Rezultati ovise o kvaliteti podataka, naknadama, spreadu, likvidnosti, porezu i izvedbi. Namijenjeno istraživanju i obrazovanju; nije investicijski savjet, ponuda ni preporuka kupnje/prodaje. Ulaganja mogu izgubiti vrijednost. [Alpaca disclosures](https://alpaca.markets/disclosures). Lokalna simulacija ne uključuje pravi novac niti stvarne brokerske naloge.']
    (OUT/'IZVJESTAJ.md').write_text('\n\n'.join(doc)+'\n')
    # Standalone charts and HTML; optional isolated plotting dependency, not project installation.
    sys.path.append('/private/tmp/c35-metals-plot')
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/c36-metals-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    images=[]
    for dataset,period,title in [('PROXY','FULL','Desetogodišnji proxy GLD/SLV'),('IBKR','DIAGNOSTIC','IBKR PHAU/PHAG: kratka simulacija')]:
        fig,ax=plt.subplots(figsize=(12,5.5))
        for f in FAMILIES+['BUYHOLD','CASH']:
            x=pd.read_csv(RUN/dataset/f'{f}_BASE_1000_{period}_equity.csv')
            ax.plot(pd.to_datetime(x.date),x.equity_eur,label=LABELS[f])
        ax.set(title=title+' · početno 1.000 €',ylabel='Simulirana vrijednost (€)');ax.grid(alpha=.2);ax.legend(fontsize=8);fig.tight_layout()
        path=OUT/f'{dataset.lower()}_equity.png';fig.savefig(path,dpi=160);plt.close(fig)
        images.append('<img alt="'+title+'" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'">')
    import html
    htmltables={}
    for cap in [500,1000,2000]:
        d=target[(target.variant=='BASE')&(target.capital==cap)].copy()
        rows=''.join('<tr><td>'+LABELS[r.strategy]+'</td><td>'+eur(r.final_eur)+'</td><td>'+pct(r.total_return)+'</td><td>'+pct(r.max_drawdown)+'</td><td>'+str(int(r.orders))+'</td></tr>' for _,r in d.iterrows())
        htmltables[str(cap)]='<table><thead><tr><th>Pravilo</th><th>Završno</th><th>Prinos</th><th>Najveći pad</th><th>Transakcije</th></tr></thead><tbody>'+rows+'</tbody></table>'
    page='''<!doctype html><html lang="hr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Zlato i srebro · C36</title><style>body{font:17px/1.6 system-ui;max-width:1100px;margin:36px auto;padding:0 20px;background:#f5f3ed;color:#152c36}h1{font-size:38px;line-height:1.2}.notice{background:#fff0cf;padding:20px;border-left:5px solid #b88213;border-radius:8px}img{max-width:100%;background:white;margin:18px 0}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left}select{font:inherit;padding:8px}pre{white-space:pre-wrap;font:15px/1.65 system-ui}a{color:#155c78}.scroll{overflow-x:auto}</style><h1>Zlato i srebro: napredniji algoritmi</h1><p>90 scenarija · 3 algoritma · 500–2.000 € · 13.10.2026.</p><div class="notice"><b>PRIČEKAJ — nijedan kandidat nije prošao razvojni odabir.</b><br>Složeniji algoritam nije automatski isplativiji. Ovo je povijesna simulacija, bez brokerskih naloga.</div>'''
    page+=''.join(images)+'<h2>Stvarni IBKR instrumenti, kraća povijest</h2><p>PHAU/PHAG · 1.10.2025.–12.10.2026. · min.3 € po nalogu +0,05% odstupanja. Kratka, već viđena povijest; nije neovisna potvrda.</p><label>Početni račun <select id="capital"><option>500</option><option selected>1000</option><option>2000</option></select> €</label><div class="scroll" id="results"></div>'
    page+='<details><summary>Cijeli hrvatski izvještaj, pravila i ograničenja</summary><pre>'+html.escape('\n\n'.join(doc))+'</pre></details><p>Hipotetski rezultati ne jamče buduće. Bez naloga i bez uključenog automatskog trgovanja.</p><script>const tables='+json.dumps(htmltables,ensure_ascii=False)+'; const sel=document.getElementById("capital");const render=()=>document.getElementById("results").innerHTML=tables[sel.value];sel.addEventListener("change",render);render();</script></html>'
    (OUT/'analiza.html').write_text(page)
    print(json.dumps({'report':str(OUT/'IZVJESTAJ.md'),'winner':selection['winner'],'pbo_diagnostic':stats['pbo_diagnostic']}))

if __name__=='__main__': main()
