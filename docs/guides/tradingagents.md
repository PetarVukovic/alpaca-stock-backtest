# TradingAgents uz C13C

Integracija je informativna. Izvršenje C13C ostaje u postojećoj aplikaciji; AI nema broker vjerodajnice ni naredbe za naloge. Ovo nije nova odobrena strategija.

Izvor: https://github.com/TauricResearch/TradingAgents
Verzija: 0.6.0, commit `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.

## Postavljanje

Zasebni interpreter: `app/data/tradingagents/.venv/bin/python`. Instalacija odvojena od glavnog `.venv`:

```sh
uv venv app/data/tradingagents/.venv --python 3.12
uv pip install --python app/data/tradingagents/.venv/bin/python 'tradingagents @ git+https://github.com/TauricResearch/TradingAgents.git@1394a3f72aa4393e1a98f51b382434c4b4c2d972'
```

Koristi se **Codex CLI i postojeća ChatGPT OAuth prijava**, bez OpenAI API ključa. Adapter `scripts/tradingagents_codex.py` prevodi LangChain poruke, pozive alata i strukturirane odgovore u `codex exec --output-schema`. Upstream paket ostaje neizmijenjen; provider se registrira u zasebnom worker procesu.

Provjera prijave: `codex login status`. Ako treba, prijava kroz službeni `codex login`. Integracija nikad ne čita ni kopira tokene. Ograničenja korištenja Codex računa i dalje vrijede; ovo nije neograničena API usluga.

`C13C_AI_MODEL` i `C13C_AI_FAST_MODEL` su opcionalni: bez njih koristi se zadani model Codex CLI-ja uz ignoriranje korisničke konfiguracije. `C13C_AI_AUTO=0` isključuje automatiku; zadano se novi završeni dnevni snapshotovi analiziraju. Nema pokretanja scheduler-a tijekom testiranja integracije. Restart postojeće aplikacije može pokrenuti paper automatiku i nije dio testova.

## Rad

Ekran **AI analiza** (`/analiza`), `GET /api/analysis` i `POST /api/analysis/run`. Automatski pregled svakih pet minuta pokreće pozadinsku obradu samo za novi snapshot nakon `last_completed_session`; nema naloga iz ovog modula. Izvještaji su `app/data/tradingagents/{MU,WDC,STX}.json`, odvojeni od C13C stanja. Izvještaj pokazuje datum izvornog C13C signala i vrijeme AI obrade.

Upstream agenti koriste Yahoo/SEC za informativnu analizu; C13C i dalje koristi vlastiti postojeći izvor podataka. AI prijedlog kupnje/prodaje je tekst, nikad naredba. Njihovo standardno petodnevno mjerenje rezultata nije C13C izlaz. Historijske AI analize nisu dokaz backtesta C13C.

Jedan ciklus obrađuje tri simbola redom, do trideset minuta po simbolu. Isti snapshot obrađuje se jednom, uključujući grešku, da ne bi nastalo beskonačno naplaćivanje. Za ponavljanje nakon popravka konfiguracije ukloni odgovarajući izvještaj uz prethodnu arhivu. Ograničenja broja koraka i tokena smanjuju trošak, ali nisu novčani limit.

Proces ne dobiva API ključeve. Codex upravlja vlastitom prijavom, a njegovi shell, code i web alati su isključeni. Upstream TradingAgents poziva samo svoje alate za podatke. Automatsko učitavanje `.env` je isključeno. Nema promjene zamrznutih pravila, odobrenih strategija ili brokera.

## Trenutna provjera

Runtime nije aktiviran dok ne prođe import TradingAgents grafa i test adaptera. Datoteka `app/data/tradingagents/runtime-ready.json` postoji samo nakon uspješne provjere, inače UI ostaje nespreman i nema AI procesa. macOS je tijekom postavljanja odbio nativne biblioteke; zato se instalacija paketa ne smatra uspješnim pokretanjem.
