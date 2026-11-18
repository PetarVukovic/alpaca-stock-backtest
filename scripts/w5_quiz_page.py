"""HTML renderer for the W5 vs C13C quiz page (used by ``w5_quiz_build.py``). Research only, no orders."""

from __future__ import annotations

import html
from typing import Any


def hr(x: float, nd: int = 0) -> str:
    return f"{x:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def pc(x: float, nd: int = 0, sign: bool = False) -> str:
    s = hr(abs(x) * 100, nd)
    if sign:
        return f"{'+' if x >= 0 else '-'}{s} %"
    return f"{'-' if x < 0 else ''}{s} %"


EXTRA_CSS = """
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:1em 0}
.kpi{border:2px solid var(--accent);border-radius:6px;padding:10px 14px;background:var(--example-bg);font-family:var(--ui-font);display:flex;flex-direction:column;gap:4px;min-width:0}
.kpi b{font-family:var(--hand-font);font-size:2rem;color:var(--hand);line-height:1}
.kpi span{font-size:.82rem;color:var(--muted);line-height:1.35}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.two{grid-template-columns:1fr}}
.card{border:1px solid var(--line);border-radius:6px;padding:12px 16px;background:var(--paper);font-family:var(--ui-font);font-size:.93rem;line-height:1.5;min-width:0}
.card h3{margin-top:.2em}
svg.sk{width:100%;height:auto;display:block;background:#fffdf6;border:1px solid var(--line);border-radius:4px}
.q{border:2px solid var(--line);border-radius:8px;padding:14px 16px;margin:20px 0;background:var(--paper);font-family:var(--ui-font);min-width:0}
.q .qn{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.q .qt{font-size:1.02rem;margin:.4em 0 .8em;line-height:1.5}
.q img{display:block;max-width:100%;height:auto;margin:0 auto 10px;border:1px solid var(--line);border-radius:4px;background:#fff}
.opts{display:grid;gap:8px}
button.opt{font-family:var(--ui-font);font-size:.95rem;text-align:left;border:1.5px solid var(--accent);background:transparent;color:var(--ink);border-radius:6px;padding:10px 12px;cursor:pointer;min-height:44px;line-height:1.4}
button.opt:hover{background:var(--teacher-bg)}
button.opt.right{background:var(--good-bg);border-color:var(--good-bd)}
button.opt.wrong{background:var(--bad-bg);border-color:var(--bad-bd)}
button.opt[disabled]{cursor:default;opacity:.95}
.fb{display:none;margin-top:12px;border-radius:6px;padding:10px 14px;font-size:.93rem;line-height:1.55}
.fb.show{display:block}
.fb.ok{background:var(--good-bg);border-left:5px solid var(--good-bd)}
.fb.no{background:var(--bad-bg);border-left:5px solid var(--bad-bd)}
.after{display:none;margin-top:10px}
.after.show{display:block}
.score{position:sticky;bottom:0;z-index:15;background:var(--paper);border:2px solid var(--accent);border-radius:8px;padding:8px 14px;font-family:var(--ui-font);font-size:.9rem;display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;box-shadow:var(--shadow)}
.bar{flex:1 1 140px;height:10px;background:var(--line);border-radius:5px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--good-bd);transition:width .3s}
#result{display:none}
#result.show{display:block}
table.t td,table.t th{vertical-align:top}
"""

QUIZ_JS = """
(function(){
  var qs=[].slice.call(document.querySelectorAll('.q'));
  var total=qs.length, done=0, right=0, parts={}, wrongIds=[];
  var key='w5quiz-v1';
  function upd(){
    document.getElementById('sc').textContent=right+' / '+done+' točno ('+total+' pitanja)';
    document.getElementById('bar').style.width=(100*done/total)+'%';
    if(done===total){showResult();}
  }
  function showResult(){
    var r=document.getElementById('result');r.classList.add('show');
    var html='<h3>Rezultat: '+right+' od '+total+'</h3><ul>';
    Object.keys(parts).forEach(function(p){var o=parts[p];html+='<li><b>'+p+':</b> '+o.r+' / '+o.n+'</li>';});
    html+='</ul>';
    if(wrongIds.length){html+='<p>Ponovi pitanja: '+wrongIds.map(function(i){return '<a href="#q'+i+'">'+(i+1)+'</a>';}).join(', ')+'.</p>';}
    else{html+='<p>Sve točno. Sljedeći korak je pokazati ta pravila na vlastitoj dionici (Pine skripta MASTER_W5_BREAKOUT_RETEST).</p>';}
    document.getElementById('res-body').innerHTML=html;
    r.scrollIntoView({behavior:'smooth',block:'center'});
  }
  qs.forEach(function(q,idx){
    var ok=parseInt(q.getAttribute('data-ok'),10), part=q.getAttribute('data-part');
    parts[part]=parts[part]||{r:0,n:0}; parts[part].n++;
    var btns=[].slice.call(q.querySelectorAll('button.opt'));
    btns.forEach(function(b,i){b.addEventListener('click',function(){
      if(q.getAttribute('data-done'))return;
      q.setAttribute('data-done','1');
      btns.forEach(function(x){x.disabled=true;});
      btns[ok].classList.add('right');
      var good=(i===ok);
      if(!good){b.classList.add('wrong');wrongIds.push(idx);}
      else{right++;parts[part].r++;}
      var fb=q.querySelector('.fb');fb.classList.add('show',good?'ok':'no');
      fb.insertAdjacentHTML('afterbegin','<b>'+(good?'Točno. ':'Nije točno. ')+'</b>');
      var a=q.querySelector('.after');if(a)a.classList.add('show');
      done++;upd();
    });});
  });
  document.getElementById('reset').addEventListener('click',function(){location.reload();});
  upd();
})();
"""


def svg_w5() -> str:
    return """<svg class="sk" viewBox="0 0 520 260" role="img" aria-label="Shema W5: proboj otpora i povratak">
<line x1="20" y1="110" x2="500" y2="110" stroke="#d9822b" stroke-width="3"/><text x="24" y="102" font-size="14" fill="#d9822b">otpor (razina)</text>
<polyline points="20,200 70,150 100,170 150,105 175,135 205,100" fill="none" stroke="#25262b" stroke-width="3"/>
<text x="30" y="225" font-size="13" fill="#5d5f68">1. cijena stalno staje na otporu</text>
<polyline points="205,100 250,60 290,75 330,112 360,70 440,30 500,20" fill="none" stroke="#25262b" stroke-width="3"/>
<text x="232" y="48" font-size="13" fill="#2a4d8f">2. PROBOJ (zatvaranje iznad)</text>
<circle cx="330" cy="112" r="9" fill="none" stroke="#c2321f" stroke-width="3"/><text x="270" y="140" font-size="13" fill="#c2321f">3. RETEST: dodir razine,</text><text x="270" y="156" font-size="13" fill="#c2321f">zatvara iznad</text>
<polygon points="360,70 352,86 368,86" fill="#17803d"/><text x="342" y="102" font-size="13" fill="#17803d">4. kupnja</text>
<line x1="330" y1="126" x2="500" y2="126" stroke="#c2321f" stroke-width="2" stroke-dasharray="6 4"/><text x="372" y="142" font-size="12" fill="#c2321f">stop: 3 % ispod razine</text>
<text x="360" y="12" font-size="12" fill="#5d5f68">izlaz: zatvaranje ispod SMA50</text>
</svg>"""


def svg_c13c() -> str:
    return """<svg class="sk" viewBox="0 0 520 260" role="img" aria-label="Shema C13C: pad u usponu">
<polyline points="20,215 120,180 200,150 260,120 300,90" fill="none" stroke="#2a4d8f" stroke-width="3" stroke-dasharray="8 5"/><text x="24" y="238" font-size="13" fill="#2a4d8f">prosjek 200 dana (dugi uspon)</text>
<polyline points="20,190 80,160 130,130 170,100 210,70 240,60 265,95 285,115" fill="none" stroke="#25262b" stroke-width="3"/>
<text x="170" y="48" font-size="13" fill="#5d5f68">cijena iznad prosjeka 200 dana</text>
<rect x="240" y="55" width="50" height="70" fill="#ffe9a8" opacity=".6"/><text x="238" y="145" font-size="13" fill="#d9822b">pad -5 % u 5 dana</text>
<polygon points="300,118 292,134 308,134" fill="#17803d"/><text x="262" y="165" font-size="13" fill="#17803d">kupnja (idući dan)</text>
<polyline points="300,118 330,85 370,60 420,38 450,48 475,75" fill="none" stroke="#25262b" stroke-width="3"/>
<polyline points="300,150 330,150 370,115 420,90 450,90 475,90" fill="none" stroke="#c2321f" stroke-width="2.5"/><text x="325" y="172" font-size="13" fill="#c2321f">stop: 90 % vrha, samo se diže</text>
<text x="380" y="30" font-size="13" fill="#5d5f68">izlaz: cijena probije stop</text>
</svg>"""


def render(all_q: list[dict[str, Any]], st: dict[str, Any], w5: dict[str, Any], c13: dict[str, Any], mw5: dict[str, Any], mc: dict[str, Any], css: str, js: str) -> str:
    kp = [
        (f"{hr(w5['trades_per_month'])} naspram {hr(c13['trades_per_month'])}", "trgovina mjesečno: W5 naspram C13C (43 dionice, AI era)"),
        (f"{pc(w5['hit_rate'])} naspram {pc(c13['hit_rate'])}", "udio dobitnih trgovina"),
        (f"{hr(w5['expectancy_eur'])} € naspram {hr(c13['expectancy_eur'])} €", "očekivanje po trgovini na 1.000 €"),
        (f"{pc(w5['max_drawdown'])} naspram {pc(c13['max_drawdown'])}", "najveći pad računa"),
    ]
    cards = "".join(f'<div class="kpi"><b>{v}</b><span>{t}</span></div>' for v, t in kp)
    by = st["by"]
    rows = [
        ("Ideja", "Kupi nakon što bivši otpor postane potpora", "Kupi korekciju u dugoročnom usponu"),
        ("Ulaz", "Proboj otpora, pa retest: dodir razine (do 1,5 % iznad) i zatvaranje iznad; kupnja idući dan", "Zatvaranje iznad prosjeka 200 dana i pad ≥ 5 % u 5 dana; kupnja idući dan"),
        ("Kada ne kupuje", "Poništen proboj (zatvaranje ispod razine) ili istek 40 dana; već imaš poziciju", "Ispod prosjeka 200 dana ili pad manji od 5 %; već imaš poziciju"),
        ("Stop", "Fiksno 3 % ispod RAZINE", "10 % ispod najvišeg vrha, samo se diže"),
        ("Izlaz s dobiti", "Zatvaranje ispod prosjeka 50 dana (SMA50)", "Stop koji prati vrh"),
        ("Trgovina mjesečno", hr(w5["trades_per_month"]), hr(c13["trades_per_month"])),
        ("Uspješnih", pc(w5["hit_rate"]), pc(c13["hit_rate"])),
        ("€ po trgovini (1.000 €)", hr(w5["expectancy_eur"]), hr(c13["expectancy_eur"])),
        ("Profit factor", hr(w5["profit_factor"], 2), hr(c13["profit_factor"], 2)),
        ("Ukupni prinos", pc(w5["total_return"], 0, True), pc(c13["total_return"], 0, True)),
        ("Najveći pad", pc(w5["max_drawdown"]), pc(c13["max_drawdown"])),
        ("Medijan držanja (dani)", hr(w5["median_hold_days"]), hr(c13["median_hold_days"])),
        ("Memorija MU WDC STX: € po trgovini", hr(mw5["expectancy_eur"]), hr(mc["expectancy_eur"])),
        ("Memorija: prinos", pc(mw5["total_return"], 0, True), pc(mc["total_return"], 0, True)),
    ]
    tbl = '<div class="tw"><table class="t"><thead><tr><th></th><th>W5 (proboj i retest)</th><th>C13C (pad u usponu)</th></tr></thead><tbody>' + "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows) + "</tbody></table></div>"

    qhtml = ""
    last_part = ""
    for q in all_q:
        if q["part"] != last_part:
            qhtml += f'<h3>{html.escape(q["part"])}</h3>'
            last_part = q["part"]
        img = f'<img src="{q["img"]}" alt="Graf za pitanje {q["id"] + 1}" loading="lazy">' if q.get("img") else ""
        after = f'<div class="after"><img src="{q["after"]}" alt="Što se stvarno dogodilo" loading="lazy"></div>' if q.get("after") else ""
        opts = "".join(f'<button type="button" class="opt">{o}</button>' for o in q["opts"])
        qhtml += f'''<section class="q" id="q{q["id"]}" data-ok="{q["ok"]}" data-part="{html.escape(q["part"])}">
<div class="qn">Pitanje {q["id"] + 1} od {len(all_q)}</div>{img}<div class="qt">{q["q"]}</div>
<div class="opts">{opts}</div><div class="fb">{q["why"]}</div>{after}</section>'''

    glossary = [
        ("Otpor", "razina cijene do koje je dionica više puta došla pa se vratila; \"strop\"."),
        ("Potpora", "razina na kojoj je cijena više puta stala u padu; \"pod\". Probijen otpor često postaje potpora."),
        ("Proboj", "zatvaranje dana iznad otpora (zatvaranje, ne samo dodir tijekom dana)."),
        ("Retest", "povratak cijene na probijenu razinu da se vidi drži li."),
        ("Swing vrh", "dan čija je najviša cijena veća od 5 dana prije i 5 dana poslije."),
        ("SMA (jednostavni prosjek)", "prosjek zatvaranja zadnjih N dana; SMA50 prati srednji, SMA200 dugoročni trend."),
        ("Stop", "unaprijed zadana cijena na kojoj izlaziš iz trgovine da gubitak ostane ograničen."),
        ("Gap", "otvaranje daleko od jučerašnjeg zatvaranja (npr. nakon izvještaja); stop tada puca po lošijoj cijeni."),
        ("Profit factor", "zbroj dobitaka podijeljen sa zbrojem gubitaka; 2 znači dva eura dobitka na svaki euro gubitka."),
        ("Očekivanje po trgovini", "prosječna zarada jedne trgovine; ovdje u eurima na 1.000 € uloga."),
    ]
    gl = "".join(f"<li><b>{a}:</b> {b}</li>" for a, b in glossary)
    check_w5 = [
        "Je li razina potvrđeni swing vrh (5 dana s obje strane)?",
        "Je li dan zatvorio IZNAD razine (proboj)?",
        "Je li se cijena vratila: najniža cijena na razini ili do 1,5 % iznad, a zatvaranje iznad nje?",
        "Je li retest došao u 40 dana i nije li cijena prije toga zatvorila ispod razine?",
        "Nemaš li već poziciju u toj dionici?",
        "Stop 3 % ispod razine; izlaz kad zatvori ispod SMA50.",
    ]
    check_c = [
        "Zatvaranje iznad prosjeka 200 dana?",
        "Pad od najmanje 5 % u zadnjih 5 trgovinskih dana?",
        "Nemaš li već poziciju u toj dionici?",
        "Kupnja na otvaranju idućeg dana, stop 10 % ispod najvišeg vrha, samo ga podižeš.",
    ]
    ul = lambda xs: "<ol>" + "".join(f"<li>{x}</li>" for x in xs) + "</ol>"  # noqa: E731

    body = f"""
<h1>W5 naspram C13C: kviz na stvarnim podacima</h1>
<p class="sub">Za početnika. Svi grafovi i brojke su iz stvarnih dnevnih podataka (43 dionice, 1. 1. 2023. do 5. 10. 2026.). Istraživanje, ne savjet.</p>
<section id="uvod"><h2>Ukratko</h2>
<div class="kpis">{cards}</div>
<p class="lead"><b>C13C</b> kupuje <i>popust</i> u dionici koja je inače u dugom usponu. <b>W5</b> kupuje <i>potvrđeni proboj</i>: kad cijena probije strop, vrati se na njega i drži ga kao pod. Obje drže najviše jednu poziciju po dionici, bez poluge, a odluka pada na kraju dana uz kupnju idući dan po otvaranju.</p></section>
<section id="osnove"><h2>Objašnjeno za početnika</h2>
<div class="two">
<div class="card"><h3>W5: strop koji postaje pod</h3>
<p>Zamisli lopticu u sobi. Cijena odskače od <b>stropa</b> (otpor) i vraća se dolje. Jednom prođe kroz strop (proboj), ali većina probojeva su lažni: lopta se vrati ispod. Zato W5 ne kupuje odmah. Čeka da lopta padne natrag do tog istog mjesta i odskoči: sada je bivši strop postao <b>pod</b>. Ako drži, W5 kupuje. Ako lopta propadne ispod, proboj je poništen, nema trgovine.</p>{svg_w5()}</div>
<div class="card"><h3>C13C: popust u rastućoj dionici</h3>
<p>Dionica kojoj je prosjek 200 dana u stalnom usponu je "zdrava". Kad u 5 dana padne bar 5 %, to je kratka rasprodaja: <b>popust</b>. C13C kupuje taj popust. Zaštita je stop 10 % ispod najvišeg vrha, koji se podiže s rastom cijene, a nikad ne spušta. Ako se pad nastavi, stop te izbaci; ako cijena nastavi rasti, stop te prati.</p>{svg_c13c()}</div>
</div>
<div class="example"><b>Primjer u eurima (izmišljen).</b> W5: razina 100 $, kupnja na 102 $, stop 97 $. Ako stop pukne, gubiš oko 5 %, na 1.000 € to je oko 49 €. Ako cijena naraste na 125 $ prije nego što zatvori ispod SMA50, dobit je oko 22 %, oko 225 €. C13C: kupnja na 80 $, stop na 72 $ (90 % od 80). Cijena naraste na 100 $, stop se podigne na 90 $. Ako pukne tu, dobit je oko 12 %.</div>
<h3>Usporedba pravila i stvarnih rezultata</h3>
{tbl}
<div class="callout warn"><b>Kako čitati brojke.</b> To su rezultati simulacije na povijesnim podacima u razdoblju snažnog rasta (AI era), uz trošak 2,5 baznih bodova po strani. Nijedna strategija nema Critic PASS. W5 ima rijetke velike pobjede (10 najboljih trgovina nosi oko {hr(st['top10_gross'] * 100)} % svih dobitaka), a placebo test pokazuje da razine nisu bolje od slučajnih.</div>
<h3>Rječnik</h3><ul>{gl}</ul>
</section>
<section id="kviz"><h2>Kviz ({len(all_q)} pitanja)</h2>
<p>Klikni odgovor. Odmah vidiš objašnjenje s brojkama. Na grafovima iznad pitanja vidiš samo prošlost do dana odluke (sivo je budućnost). Nakon odgovora, gdje postoji, otvori se i graf onoga što se <b>stvarno dogodilo</b>.</p>
{qhtml}
<div id="result" class="callout good"><div id="res-body"></div><p><button type="button" class="copy" id="reset">Ponovi kviz</button></p></div>
<div class="score"><span id="sc">0 / 0</span><div class="bar"><i id="bar"></i></div></div>
</section>
<section id="listovi"><h2>Podsjetnik prije prave odluke</h2>
<div class="two"><div class="card"><h3>W5: pet pitanja</h3>{ul(check_w5)}</div><div class="card"><h3>C13C: četiri pitanja</h3>{ul(check_c)}</div></div>
<p class="small">Pine skripte za TradingView: <code>MASTER_W5_BREAKOUT_RETEST.pine</code> i <code>MASTER_W1_C13C.pine</code> u <code>scripts/tradingview/</code>. Nijedan nalog se ne šalje.</p>
</section>
<footer>Istraživanje, ne ulagački, porezni ni pravni savjet i ne obećava zaradu. Troškovi 2,5 bps po strani; tečaj EUR/USD, dividende, porezi i minimalna provizija nisu modelirani. Dostupnost kod IBKR-a, KID i hrvatski porez nepotvrđeni. Sastavljeno skriptom <code>scripts/w5_quiz_build.py</code>.</footer>
"""
    return f"""<!DOCTYPE html>
<html lang="hr"><head><meta charset="utf-8"><title>W5 Kviz</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Inter:wght@400;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>{css}{EXTRA_CSS}</style></head><body><div class="wrap"><div class="layout"><main><div class="page">
<div class="topbar"><span>Istraživanje, ne savjet. Bez naloga.</span><button type="button" class="theme" aria-label="Promijeni svijetlu i tamnu temu">Svijetlo / tamno</button></div>
{body}
</div></main></div></div><script>{js}{QUIZ_JS}</script></body></html>"""
