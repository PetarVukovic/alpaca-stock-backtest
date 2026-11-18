# Autostart aplikacije na Macu (launchd)

Aplikacija iz `app/` može se pokretati sama svaki put kad se prijaviš na Mac i ostati upaljena u
pozadini. To radi macOS-ov sustav **launchd** preko „korisničkog agenta“: male datoteke s opisom
što pokrenuti, koja stoji u `~/Library/LaunchAgents/`. Nema instalacije dodatnih programa.

Što dobiješ: aplikacija na [http://127.0.0.1:8000](http://127.0.0.1:8000) uvijek radi, večernji i
jutarnji krug C13C odrađuju se sami (vidi `app/README.md`, „Dnevni ciklus“), a ako se proces sruši,
launchd ga podigne ponovno. Sve je i dalje **paper** (lažan novac) i auto-način je zadano
uključen prema Petrovoj odluci od 2026-10-06; vrijedi spremljeni prekidač i kill switch.

Datoteke (traka A ih održava):

| Datoteka | Što je |
|----------|--------|
| `app/autostart/com.memorylab.app.plist` | Opis za launchd: pokreće `bash app/run.sh` pri prijavi (`RunAtLoad`) i drži ga živim (`KeepAlive`). |
| `app/autostart/install.sh` | Kopira plist u `~/Library/LaunchAgents/` s točnim putanjama i učita ga. |
| `app/autostart/uninstall.sh` | Isključi agenta i makne plist. |
| `app/run.sh` | Ono što se zapravo pokreće: izgradi zaslon ako ga nema i pokrene pozadinu na portu 8000. |

## Prije instalacije

1. Python okolina postoji: `.venv/bin/python` (vidi [setup.md](setup.md)).
2. Node.js je instaliran (treba za izgradnju zaslona prvi put).
3. `.env` u korijenu ima `ALPACA_API_KEY` i `ALPACA_SECRET_KEY` (paper ključevi). Bez njih aplikacija radi
   u simulaciji.
4. Za *Chat*: Codex CLI je instaliran i prijavljen (`codex login` u terminalu, jednom). launchd procesi
   imaju vrlo kratak `PATH`, pa aplikacija Codex traži na `/opt/homebrew/bin/codex`; ako je negdje drugdje,
   stavi `CODEX_BIN=/puna/putanja/codex` u `.env`.
5. Prvo ručno provjeri da sve radi: `bash app/run.sh`, otvori [http://127.0.0.1:8000](http://127.0.0.1:8000),
   pa `Ctrl+C`.

## Instalacija

Iz korijena projekta:

```bash
bash app/autostart/install.sh
```

Skripta upiše plist s putanjom do ovog projekta u `~/Library/LaunchAgents/com.memorylab.app.plist` i
učita ga (`launchctl bootstrap gui/$(id -u) ...`). Aplikacija kreće odmah, bez odjave.

Ako je radije želiš učitati ručno:

```bash
cp app/autostart/com.memorylab.app.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.memorylab.app.plist
```

## Radi li?

```bash
launchctl list | grep memorylab
```

Ispis ima tri stupca: **PID**, zadnji izlazni kod, ime. Ako je u prvom stupcu broj, proces radi.
Ako piše `-`, ne radi; drugi stupac tada kaže s kojim je kodom završio (0 je uredno, sve drugo je greška,
pogledaj zapise).

Druge provjere:

```bash
curl -s http://127.0.0.1:8000/api/health        # pozadina odgovara
open http://127.0.0.1:8000                      # otvori u pregledniku
tail -f app/data/logs/app.log                   # zapisi aplikacije uživo (Ctrl+C za izlaz)
ls app/data/logs/                               # i launchd-ov stdout/stderr, ako ih plist tamo usmjerava
```

## Ponovno pokretanje (npr. nakon promjene koda)

```bash
launchctl kickstart -k gui/$(id -u)/com.memorylab.app
```

`-k` ugasi stari proces i odmah podigne novi. Zaslon (`app/frontend/dist`) se ne gradi iznova sam ako
već postoji; nakon promjene zaslona prvo `npm run build --prefix app/frontend`, pa kickstart.

## Privremeno zaustavljanje

```bash
launchctl bootout gui/$(id -u)/com.memorylab.app        # ugasi i ne diži do sljedeće prijave ili bootstrapa
```

Ponovno uključivanje bez reinstalacije:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.memorylab.app.plist
```

Napomena: obični `kill` na proces ne pomaže, jer ga `KeepAlive` odmah vrati. Koristi `bootout`.

## Uklanjanje

```bash
bash app/autostart/uninstall.sh
```

Ručno, ako skripte nema:

```bash
launchctl bootout gui/$(id -u)/com.memorylab.app
rm ~/Library/LaunchAgents/com.memorylab.app.plist
```

Baza (`app/data/app.db`) i zapisi ostaju; obriši ih sam ako želiš čist početak.

## Repozitorij na Desktopu: ikona i dozvola (2026-10-06)

macOS ne dopušta pozadinskim procesima (launchd) čitanje mapa Desktop, Documents i Downloads.
Ako je repozitorij tamo, `install.sh` pada s kodom 126 („Operation not permitted“). Tada koristi
drugu varijantu:

```bash
bash app/autostart/install_desktop.sh
```

Ona napravi aplikaciju `~/Applications/Memory Lab.app` (ikona), prečac `~/Desktop/Memory Lab` i
agent koji pri prijavi tiho pokrene tu aplikaciju; aplikacija pokrene server i, na dvoklik, otvori
zaslon. **Jednom** moraš dati dozvolu: Postavke sustava → Privatnost i sigurnost → Potpuni pristup
disku (Full Disk Access) → „+“ → odaberi `~/Applications/Memory Lab.app` i uključi prekidač. Ako je
macOS sam pokazao prozor „Memory Lab želi pristup mapi Desktop“, klikni Dopusti. Zatim:

```bash
launchctl kickstart -k gui/$(id -u)/com.memorylab.app
```

Trajno rješenje bez dozvola: preseli repozitorij izvan Desktopa (npr. `~/memory-chips-lab`) i
ponovno pokreni `install.sh`.

## Česti problemi

| Što vidiš | Zašto | Što napraviti |
|-----------|-------|---------------|
| `launchctl list` pokazuje `-` i kod 126, log kaže `Operation not permitted` | repozitorij je na Desktopu/Documents, launchd nema pristup | vidi odjeljak iznad (`install_desktop.sh` + dozvola) |
| `launchctl list` pokazuje `-` i kod 1 ili 78 | `app/run.sh` je odmah pao (nema `.venv`, nema Node-a, zauzet port 8000) | `tail app/data/logs/app.log`; pokreni `bash app/run.sh` ručno da vidiš grešku |
| Stalno se gasi i pali | isto kao gore; `KeepAlive` ga vrti u krug | `launchctl bootout ...`, popravi uzrok, pa `bootstrap` |
| Port 8000 zauzet | star ručni `dev.sh` ili `run.sh` još radi | `lsof -nP -iTCP:8000 -sTCP:LISTEN -t \| xargs kill` |
| Chat kaže da Codex nije pronađen | launchd nema tvoj `PATH` | `CODEX_BIN` u `.env` ili Codex na `/opt/homebrew/bin/codex` |
| Chat kaže da nije prijavljen | prijava je istekla ili nije napravljena | `codex login` u terminalu |
| Točkica brokera je siva / „simulacija“ | ključevi nisu u `.env` ili Alpaca ne odgovara | provjeri `.env`, pa kickstart |
| Nema `app/data/logs/app.log` | `run.sh` nije stigao do pokretanja ili mapa ne postoji | `mkdir -p app/data/logs`, pa kickstart |

Nakon `bootstrap` ili reinstalacije uvijek pogledaj `launchctl list | grep memorylab` još jednom.
