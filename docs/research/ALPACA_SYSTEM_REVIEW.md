# Alpaca skillovi: što unaprijediti u Memory Labu

Provjera 2026-10-06. Ovo je tehnički pregled lokalne paper aplikacije, nije Critic PASS niti odobrenje za pravi novac.

## Najvažniji zaključak

Koristimo **Trading API za vlastiti račun**, a većina `alpaca-broker-*` skillova opisuje **Broker API za račune drugih korisnika**. Preuzimamo obrasce pouzdanosti, ne njihove putanje `/v1/trading/accounts/{id}` ili HTTP Basic autentikaciju. Naš adapter ostaje na `https://paper-api.alpaca.markets/v2`.

| Skill / tema | Vrijednost za naš sustav | Stanje ove dorade |
|---|---|---|
| reconciliation-idempotency | Prekid veze ne dokazuje da nalog nije prihvaćen; pronađi ga po vlastitom ID-u | Sprema se namjera prije kupnje i `client_order_id`; nepoznat ishod blokira novu kupnju; usklađivanje traži postojeći nalog |
| trading-orders | Odvojiti zahtjev, prihvat i izvršenje; otkazivanje nije trenutačno | Prodaja čeka potvrdu otkazivanja stopa; djelomična prodaja nije zatvorena pozicija; stop bez potvrde daje upozorenje |
| rate-limits-resilience | Ograničene ponovne provjere, bez slijepog ponavljanja kupnje | Zaključavanje konkurentnih ciklusa i blokada neizvjesne kupnje; širi GET retry/backoff i circuit breaker ostaju za iduću fazu |
| sse-events | Brzo primijetiti djelomično izvršenje i promjene naloga | Za naš Trading API treba **WebSocket `trade_updates`**, ne Broker SSE. Još nije ugrađeno; periodično REST usklađivanje ostaje |
| money-precision | Decimalni iznosi i količine, izvorni brokerovi zapisi | Validacija konačnih brojeva i cijelih ulaznih količina; puni prijelaz novčanih putanja s float na Decimal još nije napravljen |
| market-data | Izvor, vremenska oznaka, pravo na feed, završene svijeće | UI objašnjava IEX, odgođeni SIP i lokalnu kopiju. Treba dodatna blokada kupnje prema svježini izvršne cijene i statusu instrumenta |
| trading-backtest | Ponovljivost, realna izvršenja, troškovi, odvojena pravila i rezultat računa | Povijesni graf jasno je označen kao simulacija pravila. Ostaje zajednička simulacija MU/WDC/STX s jednim kapitalom i veličinama iz aplikacije |
| paper-trading-cli / mcp | Dijagnostika i provjera statusa/okruženja | Dokumentacijski MCP provjeren; CLI lokalno postoji. Agenti ne izvršavaju order submit ni close/cancel preko CLI/MCP |
| onboarding, funding, journals | Otvaranje i financiranje računa klijenata brokerske platforme | Nije za ovu osobnu aplikaciju. Broker `journals` nisu naš dnevnik kupnji/prodaja |

## Implementirano i provjereno

- Kupnje, prodaje, usklađivanje, auto prekidač i otkazivanje zakazane kupnje dijele zaključavanje unutar procesa.
- Neizvjesna kupnja ostaje zabilježena prije slanja; broker se čita po istom ID-u. Čak ni kratkotrajni 404 ne pokreće automatsku ponovnu kupnju.
- Ponovna zaštita prvo provjerava postojeći stop; izgubljeni odgovor ne stvara drugi stop.
- Nedostajuća pozicija bez potvrđenog izvršenja ne dobiva izmišljenu izlaznu cijenu. Potvrđena izvršenja moraju pokriti količinu.
- Granica C13C ostaje najviše 1.200 USD. Postavke se provjeravaju prije jedne transakcije; nevaljana vrijednost ne sprema ostala polja.
- Lokalni API odbija udaljeni Origin / cross-site zahtjeve i nepoznate Host vrijednosti; odgovori API-ja nisu predmemorirani.
- Chat ima odvojene lokalne razgovore, Markdown, kopiranje odgovora, tipkovničko slanje i poveznicu na prijavu.
- Lokalni Codex app-server koristi `account/read` i službeni `account/login/start`; tokeni ne ulaze u SQLite ni browser odgovor. Ovo je integracija lokalnog Codexa, nije opći OAuth za proizvoljnu web aplikaciju.
- Chat radi iz prazne privremene mape, bez korisničkog MCP configa i bez shell/code-mode/web-search alata; Alpaca tajne nisu u njegovom procesnom okruženju.

## Otvorene stavke prije ozbiljnije uporabe

1. **Potpun dnevnik izvršenja**: jedinstveni ID po svakom fillu, naknadna djelomična punjenja, ispravci/bustovi, cursor/paginacija, ponovljiv obračun pozicije i P/L. Trenutni dnevnik na razini naloga/traila nije porezno računovodstvo. Nejasna stanja ostaju za ručnu provjeru.
2. **WebSocket + REST usklađivanje**: reconnect, duplikati i redoslijed događaja; vremenska oznaka zadnje potvrde; test prekida mreže. Periodično usklađivanje je sporije.
3. **Potpuna zaštita životnog ciklusa**: terminalni djelomični fill, race pri replace, timeout prodaje i kill switch sa 207 per-order rezultatima. Nema tvrdnje da stop jamči cijenu ili maksimalni gubitak.
4. **Decimal i FX**: novčani iznosi kao točni decimalni zapisi, stvarne naknade i dnevni dokumentirani tečaj; ručni EUR tečaj sada je informativan.
5. **Operativni rad**: backup/restore SQLitea, jedna instanca schedulera, nadzor i test restarta/mreže. Laptop u stanju mirovanja ne obavlja zakazane radnje.
6. **Vjerni backtest portfelja**: isti izbor kandidata, jedna pozicija, kapital, qty i granice kao aplikacija; fingerprint podataka/pravila; validacija podataka prije pokretanja; freeze/WF/costs/Critic i dalje obvezni.
7. **Pravi novac**: zasebna odluka, provjera dostupnosti brokera/instrumenata za HR/EU i nova sigurnosna provjera. Ova dorada to ne omogućuje.

## Instalacija i provjera alata

Instalirano svih 14 skillova iz `alpacahq/alpaca-skills` za Codex, Claude Code, Cursor, Windsurf i OpenCode. Zajednički izvor `~/.agents/skills/alpaca-*`; Claude i Windsurf imaju poveznice. To je instalacija smjernica, ne dodjela prava na trgovanje. Projektni AGENTS.md i zamrznuta strategija imaju prednost nad skillovima.

Dokumentacijski MCP `alpaca-us` upisan je u konfiguracije svih pet klijenata. HTTP initialize, tools/list i pretraga dokumentacije vraćaju uspješan odgovor. Aktivacija u svakom GUI/agent procesu traži ponovno učitavanje sesije i nije pojedinačno testirana.

CLI je `~/go/bin/alpaca`, verzija **v0.0.14**; nije na PATH-u ove sesije. Provjereni version i --help, bez slanja naloga i bez mijenjanja profila. CLI je u alpha fazi: prije uporabe čitati stvarni `--help`.

Lokalni Codex status prijave i jednostavan stvarni odgovor „Veza radi.” provjereni su. Novi interaktivni OAuth login nije dovršen jer je postojeći račun već povezan.

## Službeni izvori

- [Alpaca skills](https://github.com/alpacahq/alpaca-skills)
- [Rad s nalozima](https://docs.alpaca.markets/us/docs/working-with-orders)
- [Trading WebSocket](https://docs.alpaca.markets/us/docs/websocket-streaming)
- [CLI](https://github.com/alpacahq/cli)
- [MCP server](https://github.com/alpacahq/alpaca-mcp-server)
- [Codex app-server](https://developers.openai.com/codex/app-server)
- [Codex prijava](https://developers.openai.com/codex/auth)

## Završna verifikacija

- `pytest -q`: **208 passed**; jedno postojeće Starlette/httpx upozorenje.
- Frontend Vitest: **66 passed**; TypeScript i Vite produkcijska izgradnja prolaze.
- `scripts/check_layout.py`: **0 grešaka**, 3 postojeća upozorenja za stare duplikate.
- Aplikacija ponovno pokrenuta na `127.0.0.1:8000`; `/api/health` potvrđuje Alpaca paper vezu. Prije restarta čitanjem brokera potvrđeno 0 pozicija i 0 otvorenih naloga. Nije slan brokerski nalog.
- U pregledniku potvrđeni novi chat, očuvana povijest, novi razgovor i izravna poveznica na ChatGPT postavke; postojeća lokalna prijava radi.
- Sigurnosna kopija izvornog app/tests koda: `/tmp/memory-lab-before-hardening.tgz`; SQLite prije restarta: `/tmp/memory-lab-db-before-restart-20261006.sqlite`. To su privremene kopije, ne trajni backup sustav.
