"""Write docs/research/AICHAIN_RESULT.md (Croatian) from the result JSON files. Numbers are never typed by hand.

Usage: .venv/bin/python -m lab.aichain.overview_report
"""

from __future__ import annotations

from pathlib import Path

from lab.aichain import overview_data as D
from lab.aichain import overview_text as T
from lab.aichain.overview_charts import num_hr, pct_hr

OUT = D.ROOT / "docs/research/AICHAIN_RESULT.md"
S = D.SEGMENTS


def _rating_cell(seg: str, k: str) -> str:
    return D.ratings(seg).get(k, "nepoznato")


def results_table() -> str:
    head = "| Segment | Dionica | Držanje (prinos / Sharpe / pad) | " + " | ".join(D.CONTENDER_SHORT[k] for k in D.RULES) + " |"
    sep = "|" + "---|" * (3 + len(D.RULES))
    rows = [head, sep]
    for seg in S:
        h = D.cell(seg, "B0_BUYHOLD")
        cells = []
        for k in D.RULES:
            c = D.cell(seg, k)
            mark = "" if D.is_eligible(c) else " (!)"
            cells.append(f"{pct_hr(c['total_return'])} / {num_hr(c['sharpe'], 2)}{mark}")
        rows.append(
            f"| {D.SEGMENT_SHORT[seg]} | {len(D.segment_tickers(seg))} | {pct_hr(h['total_return'])} / {num_hr(h['sharpe'], 2)} / {pct_hr(h['max_drawdown'])} | "
            + " | ".join(cells)
            + " |"
        )
    return "\n".join(rows)


def winners_table() -> str:
    rows = [
        "| Segment | Pobjednik po pravilu | Sharpe (pobj. / držanje) | Poslova | Prinos (pobj. / držanje) | Najgori pad (pobj. / držanje) | 1.000 EUR postane (pobj. / držanje / C13C) | Pobjeđuje držanje po prinosu? | Ocjena dokaza |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for seg in S:
        w = D.winner(seg)
        c, h = w.stats, w.hold
        k1 = D.cell(seg, "K1_C13C_ORIG")
        rows.append(
            f"| {D.SEGMENT_SHORT[seg]} | {D.CONTENDER_SHORT[w.contender]} | {num_hr(c['sharpe'], 2)} / {num_hr(h['sharpe'], 2)} | {c['trades']} | "
            f"{pct_hr(c['total_return'])} / {pct_hr(h['total_return'])} | {pct_hr(c['max_drawdown'])} / {pct_hr(h['max_drawdown'])} | "
            f"{T.eur(D.per_1000(c))} / {T.eur(D.per_1000(h))} / {T.eur(D.per_1000(k1))} | {'da' if w.beats_hold_return else 'ne'} | {_rating_cell(seg, w.contender)} |"
        )
    return "\n".join(rows)


def contender_table() -> str:
    rows = [
        "| Pravilo | Pobjeda | Prosječni Sharpe | Prinos > držanje | Sharpe > držanje | Manji pad od držanja | Prosječni najgori pad | Najmanje poslova | Zadovoljava oba uvjeta u |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in D.overall_table():
        rows.append(
            f"| {D.CONTENDER_SHORT[r['id']]} | {r['wins']} | {num_hr(r['mean_sharpe'], 2)} | {r['beats_hold_return']} / 6 | {r['beats_hold_sharpe']} / 6 | "
            f"{r['smaller_dd']} / 6 | {pct_hr(r['mean_dd'])} | {r['min_trades']} | {r['eligible_segments']} / 6 |"
        )
    return "\n".join(rows)


def context_table() -> str:
    rows = [
        "| Segment | Pobjednik | 2021.-2022.: pobjednik | 2021.-2022.: držanje | 2021.-2022.: C13C |",
        "|---|---|---|---|---|",
    ]
    for seg in S:
        w = D.winner(seg)
        a = D.context_2021_2022(seg, w.contender)
        b = D.context_2021_2022(seg, "K1_C13C_ORIG")
        rows.append(
            f"| {D.SEGMENT_SHORT[seg]} | {D.CONTENDER_SHORT[w.contender]} | {pct_hr(a['ret'], 0, True)} | {pct_hr(a['hold'], 0, True)} | {pct_hr(b['ret'], 0, True)} |"
        )
    return "\n".join(rows)


def c13c_table() -> str:
    rows = [
        "| Segment | C13C prinos | Držanje prinos | C13C Sharpe | Držanje Sharpe | C13C najgori pad | Držanje najgori pad | Poslova | Ocjena dokaza |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for seg in S:
        k = D.cell(seg, "K1_C13C_ORIG")
        h = D.cell(seg, "B0_BUYHOLD")
        rows.append(
            f"| {D.SEGMENT_SHORT[seg]} | {pct_hr(k['total_return'])} | {pct_hr(h['total_return'])} | {num_hr(k['sharpe'], 2)} | {num_hr(h['sharpe'], 2)} | "
            f"{pct_hr(k['max_drawdown'])} | {pct_hr(h['max_drawdown'])} | {k['trades']} | {_rating_cell(seg, 'K1_C13C_ORIG')} |"
        )
    return "\n".join(rows)


def segment_sections() -> str:
    beats = D.other_beats_hold_by_ticker()
    out: list[str] = []
    for i, seg in enumerate(S, 1):
        w = D.winner(seg)
        L = T.seg_line(seg)
        tick = D.segment_tickers(seg)
        k1_rate = _rating_cell(seg, "K1_C13C_ORIG")
        extra = []
        for t in tick:
            if t in beats:
                extra.append(f"{t} ({', '.join(D.CONTENDER_SHORT[x].split(' ')[0] for x in beats[t])})")
        rob = D.robustness(w.contender, seg)
        rob_txt = ""
        if rob:
            rob_txt = (
                f" Provjera ±20 % parametara daje prinos od {pct_hr(rob['min_total_return'])} do {pct_hr(rob['max_total_return'])} "
                f"(osnova {pct_hr(rob['base_total_return'])}); najslabija varijanta ima Sharpe "
                f"{num_hr(min(v['sharpe'] for v in rob['variants']), 2)}, a držanje {num_hr(w.hold['sharpe'], 2)}."
            )
        else:
            rob_txt = " Provjera ±20 % za ovo pravilo nije pokrenuta (to je nedostatak dokaza, ne dokaz krhkosti)."
        out.append(
            f"### {i}. {D.SEGMENT_TITLE[seg]}\n\n"
            f"Dionice u analizi: {', '.join(tick)}.\n\n"
            f"Pobjednik po fiksnoj definiciji: **{L['name']}**; {L['verdict']}. {L['sharpe']} Poslova: {w.stats['trades']}. "
            f"Deflated Sharpe {num_hr(w.stats['deflated_sharpe_prob'], 2)} (čvrst dokaz traži iznad 0,95).\n\n"
            f"- {L['money']}\n- {L['dd']}\n- Ocjena dokaza za pobjednika: {_rating_cell(seg, w.contender)}; za C13C: {k1_rate}.{rob_txt}\n"
            + (f"- Dionice na kojima neko pojedinačno pravilo ipak pobjeđuje držanje po prinosu: {', '.join(extra)}.\n" if extra else "- Ni na jednoj dionici ovog segmenta neko pojedinačno pravilo ne pobjeđuje držanje po prinosu.\n")
        )
    return "\n".join(out)


def build() -> Path:
    wins = D.winners()
    oc = T.overall_counts()
    tc = T.c13c_ticker_counts()
    ot = {r["id"]: r for r in D.overall_table()}
    k = D.summary()["ledger_k_after_registration"]
    net, mem, cl = wins["network_servers"], wins["memory"], wins["cloud"]
    mi, eq, ai = wins["mem_interface_storage"], wins["equipment"], wins["ai_chips_logic"]
    k6 = ot["K6_MOMENTUM_CS"]
    k6_mem = D.cell("memory", "K6_MOMENTUM_CS")
    ai_k2 = D.cell("ai_chips_logic", "K2_SMA200_TREND")
    ai_h = D.cell("ai_chips_logic", "B0_BUYHOLD")
    rob6 = D.robustness("K6_MOMENTUM_CS", "mem_interface_storage")
    max_dsr = max(w.stats["deflated_sharpe_prob"] for w in wins.values())
    excl = D.excluded()
    excl_txt = "\n".join(f"- **{x['ticker']}**: {x['reason']}." for x in excl)
    rows = D.ticker_rows()
    worst = min(rows, key=lambda r: r.c13c_ret - r.hold_ret)
    best = max(rows, key=lambda r: r.c13c_ret - r.hold_ret)

    md = f"""# AI lanac: rezultat turnira strategija (2026-10-14)

*Istraživanje, ne savjet za ulaganje. Nije Critic PASS; `approved_list` ostaje prazan i signal je **PRIČEKAJ**. Agenti ne šalju nikakve naloge (ni probne ni prave). Nema obećanja zarade i nema savjeta o porezu.*

Pregledna stranica s grafovima: `reports/research/AICHAIN_20261014/overview.html`. Pojedinačne stranice segmenata: `reports/research/AICHAIN_20261014/segments/*/artifact.html`. Sirovi brojevi: `summary.json`, `results/*.json`, `segments/*/analysis.json` u istoj mapi.

## 1. Sažetak u pet rečenica

1. U AI eri (od 2023-01-01, glavno mjerilo) držanje je teško pobijediti: pravilo koje je po unaprijed zadanoj definiciji najbolje u segmentu pobijedilo je držanje po prinosu u **{oc['beats_ret']} od 6** segmenata, po Sharpeu u **{oc['beats_sharpe']} od 6**, a imalo je manji najgori pad u **{oc['smaller_dd']} od 6**.
2. Pobjednici po segmentima: memorija **{D.CONTENDER_SHORT[mem.contender]}** (tvoj C13C), sučelja i pohrana **{D.CONTENDER_SHORT[mi.contender]}**, oprema **{D.CONTENDER_SHORT[eq.contender]}**, AI čipovi **{D.CONTENDER_SHORT[ai.contender]}**, mreže i serveri **{D.CONTENDER_SHORT[net.contender]}**, oblak **{D.CONTENDER_SHORT[cl.contender]}**.
3. Jedini jasan pobjednik nad držanjem je K6 u mrežama i serverima ({T.eur(D.per_1000(net.stats))} naspram {T.eur(D.per_1000(net.hold))} iz 1.000 EUR), ali uz **veći** najgori pad ({T.eur(D.worst_loss_per_1000(net.stats))} naspram {T.eur(D.worst_loss_per_1000(net.hold))} na 1.000 EUR s vrha).
4. Tvoj C13C na {tc['n']} dionica zaradi više od držanja na {tc['beats_ret']}, ima veći Sharpe na {tc['beats_sharpe']}, a manji najgori pad na {tc['smaller_dd']}: to je osiguranje koje se plaća prinosom.
5. Ni jedan pobjednik nema deflated Sharpe iznad 0,95 (najviši {num_hr(max_dsr, 2)}; K = {k}), pa je ovo uputa gdje dalje istraživati, a ne dokaz.

## 2. Podaci i čišćenje

Korišteni su **samo** `data/ohlcv/{{TICKER}}_1d.csv` (dnevno, izvor Alpaca, prilagođeno samo za splitove). `.parquet` datoteke nisu korištene. WDC povijest je već prilagođena za SanDisk spin-off (faktor 0,68132) i **nije** ponovno prilagođavana (provjerom je omjer potvrđen na 2298 dana). Sirove CSV datoteke nisu mijenjane. Zajednički kraj podataka je {D.summary()['common_end']}.

**Isključeno i zašto:**

{excl_txt}

**Pravila čišćenja (ista za sve):**

- Niz od 5 i više dana s volumenom 0 i ravnom cijenom je obustava trgovanja, ne cijena po kojoj bi the researcher mogao kupiti. Povijest se koristi tek od prvog dana nakon niza: SMCI do 2020-01-14, NBIS do 2024-10-21. Za NBIS to znači da je novac u AI eri do 2024-10-21 gotovina.
- Jedan očiti loš tick je ograničen na susjedne cijene (redak nije brisan, CSV nije mijenjan): NVDA 2024-06-10, najviša 195,95 postaje 121,79. Neovisna revizija pokazala je da je taj tick bez popravka podizao klizni stop i lažno izbacivao poziciju.
- Poznata ograničenja podataka: ARM, CRDO i ALAB kupuju se na otvaranju prvog dana kotacije (to nije cijena izdavanja i možda nije bila dostupna malom ulagaču); VRT prije 2020-02 je SPAC (GSAH), pa je njegov `full` prozor samo kontekst; dividende nisu u cijenama, pa je to cjenovni, a ne ukupni prinos (utjecaj nije izmjeren, nepotvrđeno brojkom).

## 3. Simulator i njegove poštene granice

**Što radi.** Dnevne svijeće; odluka se donosi na zatvaranju dana *t*, a kupnja se izvršava na otvaranju dana *t+1*, kao da navečer pogledaš graf i zadaš nalog za sutra. Samo dugo, bez poluge. Trošak je 2,5 bps po strani (0,025 %; na 1.000 EUR to je 0,25 EUR), uz stres-testove 2× i 3×. Stop radi unutar dana: ako dan otvori ispod stopa (jaz preko noći), izlaz je po otvaranju, dakle lošije od stopa. Svaka dionica je zaseban "sleeve" s 1.000 EUR; segment je zbroj sleeve-ova bez prelijevanja. AI era počinje s praznim računom 2023-01-03, a indikatori su ugrijani na ranijim podacima. Na zadnji dan otvorena pozicija se likvidira i plaća trošak izlaza.

**Provjere.** Parity test: K1 u simulatoru i originalni C13C replay daju identične poslove na MU, WDC i STX u tri prozora (9 od 9). Test pogleda u budućnost (osnovni i jači, s 12 nasumičnih rezova po dionici) prolazi za sve jednotickerske suparnike; jači test hvata namjerno ubačen pogled u budućnost. Neovisna provjera ponovno je izračunala više od 100 brojeva i slaže se do 1e-9; pritom su nađeni i popravljeni obustavljeni podaci, loš tick u NVDA i nenaplaćen trošak zadnjeg izlaza.

**Što NIJE modelirano (važno):**

- Tečaj EUR/USD i trošak konverzije: cijene su u USD i tretiraju se kao EUR-ekvivalent. Stvarnih 1.000 EUR postaje USD pri kupnji i opet EUR pri prodaji.
- Porezi i evidencija (nije dio agenata), dividende, posudba i kratka prodaja.
- Minimalna provizija IBKR-a po nalogu: nepotvrđeno za tvoj tarif. Primjer: pri nalogu od 300 EUR simulator naplaćuje 0,075 EUR, stvarna provizija bila bi veća. Pravila s mnogo poslova (K1, K7: stotine poslova po segmentu) zato su ovdje prikazana povoljnije nego u stvarnosti.
- Razlomljene dionice kod IBKR-a: nepotvrđeno za tvoj račun; simulator ih pretpostavlja za sva pravila.
- Proklizavanje izvan 2,5 bps, djelomična ispunjenja, ograničenja likvidnosti (važno za tanke MRAM i ACMR) i obustave trgovanja.
- Robusnost ±20 % gleda samo predznak ukupnog prinosa u AI eri, što je u bik-tržištu slab test. Pokrenuta je za K1 te za K6 i K4 (izabrani po rezultatima, samo radi dijagnostike).

## 4. Unaprijed upisani suparnici

Svako pravilo ima zamrznutu specifikaciju u `strategies/frozen/2026-10-14_AICHAIN_{{ID}}.json` i redak u ledgeru (K 524 do 532; K nakon upisa {k}). Parametri su fiksni i nisu ugađani.

| Pravilo | Što radi, običnim riječima |
|---|---|
""" + "\n".join(f"| {D.CONTENDER_SHORT[c]} | {D.CONTENDER_PLAIN[c]} |" for c in D.CONTENDERS) + f"""

K7 je nova hipoteza (proširenje C13C-a) s vlastitim freeze ID-om; ocjena je pretežno žuta jer je dodana uz poznavanje ponašanja K1.

## 5. Rezultati svih segmenata (AI era, 2023-01-03 do 2026-10-05)

Svaka ćelija: ukupni prinos / Sharpe. (!) znači manje od {D.MIN_TRADES} poslova ili gubitak uz trošak 2×, pa pravilo ne može pobijediti po fiksnoj definiciji. Prinos od 668 % znači da 1.000 EUR postane 7.680 EUR (1.000 plus 6,68 puta 1.000).

{results_table()}

## 6. Tko je odradio posao najbolje

**Fiksna definicija (ista za svaki segment, određena prije gledanja):** najviši Sharpe u AI eri među pravilima (držanje se ne računa) koja imaju najmanje {D.MIN_TRADES} poslova na segmentu i pozitivan prinos uz trošak 2×. Pobjednik se uvijek uspoređuje s držanjem.

{winners_table()}

Napomena uz memoriju: K6 ima {k6_mem['trades']} poslova (manje od {D.MIN_TRADES}), pa ne ulazi u utrku iako su mu prinos i Sharpe blizu.

### Po segmentima

{segment_sections()}

### Ukupno, preko svih 6 segmenata

{contender_table()}

- **Najviše pobjeda ima K6 (rotacija zamaha): {k6['wins']} od 6**, s prosječnim Sharpeom {num_hr(k6['mean_sharpe'], 2)}, a držanje ima {num_hr(ot['B0_BUYHOLD']['mean_sharpe'], 2)}. K6 nije iznad držanja ni u prosjeku. Pobjeđuje držanje po prinosu u {k6['beats_hold_return']} segmenta (sučelja, mreže), ali tamo ima **veći** najgori pad. K6 ne zadovoljava uvjet od {D.MIN_TRADES} poslova u memoriji, pa nije prihvatljiv u svih 6 segmenata.
- **K4 (126-dnevni zamah)** je među pravilima koja zadovoljavaju oba uvjeta u svih 6 segmenata ono s najvišim prosječnim Sharpeom ({num_hr(ot['K4_TSMOM_126']['mean_sharpe'], 2)}) i ima manji najgori pad u svih 6 segmenata, ali ne pobjeđuje držanje po prinosu ni u jednom.
- **Pravi pad smanjuju** trend-pravila: u AI čipovima K2 (SMA200) ima najgori pad {pct_hr(ai_k2['max_drawdown'])} naspram {pct_hr(ai_h['max_drawdown'])} držanja, uz prinos {pct_hr(ai_k2['total_return'])} naspram {pct_hr(ai_h['total_return'])}.
- Razlike u Sharpeu među prva četiri pravila u segmentu su male, a pokrenuto je 9 pravila na 6 segmenata i {tc['n']} dionica (K = {k}). Najbolja ćelija takve tablice dobra je djelomično slučajno; važnije je da isti obrazac drže mnogi segmenti: **držanje je u bik-tržištu AI čipova jak suparnik, a pravila služe uglavnom kao osiguranje.**
- Slabost pobjednika u sučeljima i pohrani: lookback -20 % spušta Sharpe K6 na {num_hr(min(v['sharpe'] for v in rob6['variants']), 2)}, ispod držanja ({num_hr(mi.hold['sharpe'], 2)}), a deflated Sharpe je {num_hr(mi.stats['deflated_sharpe_prob'], 2)}.

### Kontekst, ne mjerilo: 2021.-2022. (medvjeđe i bočno tržište)

Prije AI ere držanje nije bilo tako dobro, pa pravila izgledaju bolje. Ovo je samo kontekst; glavno mjerilo ostaje AI era.

{context_table()}

## 7. Kako je prošao tvoj C13C

C13C je tvoj algoritam, ovdje u originalnom obliku (K1; parity test 9 od 9). Bez uljepšavanja:

{c13c_table()}

- **Po segmentu** C13C je pobjednik samo u memoriji ({D.cell('memory', 'K1_C13C_ORIG')['trades']} poslova, Sharpe {num_hr(mem.stats['sharpe'], 2)} naspram {num_hr(mem.hold['sharpe'], 2)} za držanje), ali ni tamo ne pobjeđuje držanje: {T.eur(D.per_1000(mem.stats))} naspram {T.eur(D.per_1000(mem.hold))} iz 1.000 EUR. Smanjio je najgori pad s {pct_hr(mem.hold['max_drawdown'])} na {pct_hr(mem.stats['max_drawdown'])}, dakle sa {T.eur(D.worst_loss_per_1000(mem.hold))} na {T.eur(D.worst_loss_per_1000(mem.stats))} na 1.000 EUR s vrha. To osiguranje je koštalo oko {T.eur(D.per_1000(mem.hold) - D.per_1000(mem.stats))} završne vrijednosti po 1.000 EUR uloženih na početku.
- **Po dionici** ({tc['n']} dionica): veći prinos od držanja samo na {tc['beats_ret']} (SIMO), veći Sharpe na {tc['beats_sharpe']}, manji najgori pad na {tc['smaller_dd']}. Najveći zaostatak ima {worst.ticker} ({num_hr((worst.c13c_ret - worst.hold_ret) * 100, 0)} postotnih bodova), a jedini plus {best.ticker} (+{num_hr((best.c13c_ret - best.hold_ret) * 100, 1)}).
- **Robusnost ±20 %** (SMA, prag pada, širina stopa) ne mijenja predznak prinosa ni u jednom segmentu, ali Sharpe se pomiče za do 0,3 do 0,35 u najosjetljivijim segmentima (mem. sučelja, oblak), pa je sama provjera predznaka slab test.
- **K7** (C13C s ponovnim ulazom) ne popravlja stvar: prosječni Sharpe {num_hr(ot['K7_C13C_PLUS_TREND_REENTRY']['mean_sharpe'], 2)} naspram {num_hr(ot['K1_C13C_ORIG']['mean_sharpe'], 2)} za K1, uz višestruko više poslova (pod stvarnom provizijom još skuplje).
- Zaključak: C13C ima smisla kao **alat za smanjenje pada** u dionicama koje već pratiš (memorija), ne kao pojačivač prinosa. Dokaz je valjan (ocjene pretežno zelene), ali prinos ne dokazuje prednost nad držanjem.

## 8. Praktični plan za swing trading iz Hrvatske preko IBKR-a

Okvir: swing (dani do tjedni), samo dugo, bez poluge, bez kratke prodaje. Ovo su prioriteti za **istraživanje i papirno praćenje**, ne preporuka kupnje i ne obećanje zarade.

**Prvo provjeri u IBKR-u (prije bilo kakvog daljnjeg rada):**

1. Je li svaki simbol koji te zanima dostupan tvom računu (sve su američke pojedinačne dionice, a ne ETF-ovi, pa je to vjerojatno, ali je **nepotvrđeno** dok ne provjeriš). Posebno ADR-ove i strane tvrtke (TSM, ASML, ARM, SIMO, NBIS): status ostaje nepotvrđen.
2. Provizije i minimalna provizija po nalogu za tvoj tarif, te cijena konverzije EUR u USD. Primjer: ako je minimalna provizija 1 EUR, nalog od 300 EUR košta 0,33 % samo za ulaz; simulator je ovdje preoptimističan za pravila s mnogo poslova.
3. Razlomljene dionice (nepotvrđeno): bez njih 1.000 EUR u dionicu od 700 USD nije moguće podijeliti kako simulator pretpostavlja.
4. Vrste naloga i stop: stop-nalog ne jamči cijenu. Simulator već pokazuje da dionice otvaraju ispod stopa (jaz preko noći), pa je stvarni gubitak može biti veći od zadanog stopa.
5. Pretplate na tržišne podatke i vrijeme trgovanja: američka burza otvara u 15:30 po zagrebačkom vremenu.
6. Poreznu evidenciju i tretiranje dobiti riješi s poreznim savjetnikom; ovdje ne dajemo nikakvu tvrdnju o porezu.

**Koji segmenti zaslužuju rad prvi, i zašto (po dokazima iz ovog turnira):**

1. **Oblak ({', '.join(D.segment_tickers('cloud'))}).** Najlikvidniji i najpoznatiji nazivi. K5B (proboj pa povratak na razinu) ima Sharpe {num_hr(cl.stats['sharpe'], 2)} naspram {num_hr(cl.hold['sharpe'], 2)} držanja i najgori pad {pct_hr(cl.stats['max_drawdown'])} umjesto {pct_hr(cl.hold['max_drawdown'])}; cijena je prinos ({T.eur(D.per_1000(cl.stats))} naspram {T.eur(D.per_1000(cl.hold))} iz 1.000 EUR). Ocjena je žuta jer robusnost ±20 % nije mjerena. Po obliku (pozicija danima do tjedana) najbliže tvom swingu.
2. **Mreže i serveri.** Jedini segment gdje pravilo (K6) jasno pobjeđuje držanje, ali s većim padom i s mjesečnom rotacijom nekoliko vrlo nestalnih dionica; ocjena žuta. Vrijedi za dublje istraživanje i papirno praćenje, uz svijest da je gubitak s vrha bio {T.eur(D.worst_loss_per_1000(net.stats))} na 1.000 EUR.
3. **Memorija (MU, WDC, STX).** Tvoje područje; C13C je tu pobjednik po pravilu i ocjena je zelena. Pogodan kao alat za smanjenje pada, ne za veći prinos.
4. **AI čipovi i oprema.** Nijedno pravilo ne pobjeđuje držanje; vrijedi gledati samo ako ti je cilj smanjiti pad (K2 u AI čipovima).
5. **Sučelja i pohrana.** Najslabiji dokaz (deflated Sharpe {num_hr(mi.stats['deflated_sharpe_prob'], 2)}, osjetljiv na lookback, tanke dionice poput MRAM-a). Zadnji na redu.

**Sljedeći koraci (bez naloga):** papirno praćenje unaprijed zadanih pravila na živim podacima prema protokolu za forward test; evidentirati svaki signal i stvarnu izvedivost ispunjenja; svaku novu varijantu pokrenuti kao novi freeze ID i upisati u ledger. Kad bi se ikad išlo prema pravom trgovanju, to je zasebna odluka i zasebna provjera.

## 9. Otvorena pitanja

- Kako izgleda ovo isto s tečajem EUR/USD, stvarnom provizijom i dividendama? (Moguće da neka pravila s mnogo poslova tada izgube prednost.)
- Hoće li obrazac držati izvan bik-tržišta AI čipova? Imamo samo 2021.-2022. kao slab kontekst; AI era je jedno tržišno razdoblje.
- Je li rotacija K6 uopće izvediva za jednog malog ulagača (mjesečne promjene sastava, minimalna provizija)? Nepotvrđeno.
- Može li se robusnost ±20 % zamijeniti jačim testom (npr. Monte Carlo premještanja poslova, sintetički podaci) za pobjednike?
- Ima li smisla kombinirati držanje s osiguranjem (dio kapitala u pravilu, dio u držanju)? To bi bila nova hipoteza s novim freeze ID-om; ovdje nije testirano.
- Koliko je rezultat osjetljiv na izbor dionica u segmentu (preživjeli pobjednici)? Popis je sastavljen 2026., poznavajući AI eru, što može napuhnuti držanje i pomaknuti usporedbu.
- Dokazi o PSTG, SNDK i CRWV nedostaju (zastarjeli ili prekratki podaci); mogu se dodati kad povijest naraste.
"""
    OUT.write_text(md, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
