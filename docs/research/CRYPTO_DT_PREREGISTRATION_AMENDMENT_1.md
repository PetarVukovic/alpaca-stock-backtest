# Kripto day trading: amandman 1 pred-registracije (2026-10-14)

Izvorni dokument `docs/research/CRYPTO_DT_PREREGISTRATION.md` (SHA-256 `7afc2e0b…a1c1`) ostaje nepromijenjen. Ovaj amandman nastaje **nakon** neovisnog pregleda
(`reports/runs/codex_cdt_review.md`, codex-a) i pokrivaju ga samo točke ispod. Rezultati WF/HO se ne koriste za biranje pravila: pravilo je doslovan tekst izvorne registracije.

## Što je pregled našao

CDT_H2_TREND_4H_CROWD je implementirao uvjet "funding **≥ 95. percentila**" kao *prosječni rang (pandas `rank(pct=True)`) ≥ 0,95*. Registrirano pravilo je *vrijednost ≥ 95. percentil vrijednosti
zadnjih 270 fundinga*. Kod ponovljenih vrijednosti (funding često stoji na baznoj razini 0,01 %) to nisu isti uvjeti: pri 270 jednakih fundinga je vrijednost jednaka 95. percentilu
(uvjet istinit), a prosječni rang je 0,50 (uvjet lažan). Isto vrijedi za OI. Uz to je tolerancija starosti OI snimke brojana od `ts + 5 min`, pa je sirova starost mogla biti 20 min umjesto 15 min.

## Posljedica

- CDT_H2_TREND_4H_CROWD ostaje u ledgeru i `results.json`, ali se **ne smatra vjernom replikacijom registriranog pravila**. Njegov rezultat se ne koristi kao dokaz o filteru.
- Novi ID **CDT_H2Q_TREND_4H_CROWD_QTL** (7. trial) provodi izvorni tekst doslovno: `value >= rolling quantile` (pandas linearna interpolacija, prozor uključuje trenutnu vrijednost, minimalno cijeli prozor),
  snimka OI smije biti najviše 15 min stara (nakon 5 min zakašnjenja). Svi ostali parametri, kriteriji "radi" i troškovi isti su kao u izvornoj registraciji.
- Priznanje: codex je u pregledu naveo i brojke ispravljene varijante (WF +153,2 %, HO +14,7 %) prije nego što je H2Q pokrenut. Pravilo H2Q nije biran iz tih brojki, nego iz izvornog teksta, ali H2Q nije nezavisan od te informacije.

## Dijagnostike runnera (ne mijenjaju pravila strategija)

Ispravljeno u `lab/crypto_dt/run.py` nakon istog pregleda i svih šest rezultata ponovno je izračunato istim zamrznutim kodom strategija (nema novog trial-a, `register_strategy` je idempotentan):
1. Bruto bps po tradeu za još otvorene tradeove odbijao je jednu stranu troška manje (precjenjivao za 10 bps); ispravljeno.
2. "Ex-top3" na neponderiranim cijenama asset-tradea ne prati uloženi kapital. Dodan je kriterij `ex_top3_contribution_positive` (doprinos portfelju po epizodi, uključujući troškove prilagodbi). Verdikt zahtijeva **oba**.
3. Referenca "kupi i drži" u `core.py` je jednako ponderirani koš rebalansiran na svakom baru bez troška, a ne kupi-i-drži. Dodan je pravi kupi-i-drži (fiksne jedinice od prvog opena 2023). Oznaka "smanjivač vremena u tržištu" sad traži i manji drawdown.
4. Dodan stres troškova 1,5× (registriran u izvornom dokumentu, a nije se računao). Izloženost je sada prosječna uložena težina u WF+HO, ne udio svih barova s bilo kakvom pozicijom od 2020.
5. Dry run još interno računa cijeli `evaluate` (uključujući WF/HO), a ispisuje samo strukturne brojke.

## Poznata ograničenja koja ostaju (pregled, točke 6, 8, 9)

PBO koristi samo osnovnu i dvije istodobno skalirane varijante; pomaci ±20 % su po jedan parametar, a satni parametri H3/H4 su strukturne konstante; stopa fill-a pretpostavlja open sljedećeg bara bez latencije
(jedan bar kašnjenja: H1 WF +133,0 %, HO +8,9 %; H1B HO −3,5 %); univerzum BTC/ETH/SOL je izabran unaprijed, ali je preživjeli; zadnji bar nema sljedeći open pa se mjeri do opena 2026-10-09 20:00.
