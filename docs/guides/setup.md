# Postavljanje okoline

## Python

Lokalni sistemski Python nema `numpy`, `pandas` ni `scipy`. Za pokretanje skripti napravi virtualnu okolinu:

```bash
cd memory-chips-lab        # korijen repoa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt`: `vectorbt`, `pandas`, `numpy`, `pyarrow`, `python-dotenv`, `requests`, `alpaca-py`.
Skripte iz skillova `walk-forward-validation` i `backtest-expert` trebaju još `scipy`.

## Ključevi

- Alpaca **paper** ključevi idu u `.env` u korijenu (ili kao shell varijable). `.env` je u `.gitignore`.
- **Nikad** ključevi u repo, u zip ni u dokumentaciju.
- `scripts/pull_news.py` čita ključeve iz shell okoline.

## Pokretanje sesija

```bash
bash scripts/run_claude_session.sh   # Claude Code, prompt: PROMPTS/claude-backtest.md
bash scripts/run_codex_session.sh    # Codex, prompt: PROMPTS/codex-backtest.md
```

Izlazi idu u `reports/runs/` (`claude_run.md`, `codex_run.md`).

## Skripte

| Skripta | Što radi | Napomena |
|---------|----------|----------|
| `scripts/pull_data.py` | Osvježava dnevne cijene preko Alpaca paper | stariji; piše CSV i parquet, **parquet se ne koristi** |
| `scripts/backtest_swing.py` | Stari swing screening, piše `reports/leaderboard.md` | puni uzorak, **nije** Critic |
| `scripts/run_*_session.sh` | Pokreću Claude / Codex sesije | |

Ostale skripte iz `AGENTS.md` (`validate_data.py`, `pull_news.py`, `backtest_C*.py`) trenutno nisu u ovom folderu.

## Alpaca

Alpaca MCP i CLI (samo paper): [alpaca.md](alpaca.md). Alpaca MCP je od 2026-10-05 spojen u Claude Code
(korisnička razina), ograničen na alate samo za čitanje.

## Skillovi

19 savjetodavnih skillova je u `.claude/skills/` (učitavaju se u novoj sesiji). Izvori i vetting:
[../research/SKILLS_SHORTLIST.md](../research/SKILLS_SHORTLIST.md).

## Memorija

Dugoročna memorija (odluke, handoffovi) je u Engramu, projekt `memory-chips-lab`.
