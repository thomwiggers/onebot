# CLAUDE.md

Guidance for Claude Code when working in this repo.

## Project Overview

OneBot = IRC bot on **irc3** framework. Plugin architecture — each feature = self-contained irc3 plugin in `onebot/plugins/`.

## Development Commands

```bash
uv sync                          # Install all dependencies (including dev)
uv run pytest                    # Run tests (includes doctests via --doctest-modules)
uv run pytest tests/test_plugin_psa.py  # Run a single test file
uv run pytest -k test_psa        # Run tests matching a pattern
uv run pytest --cov=onebot       # Run tests with coverage
uv run ruff format .             # Format code
uv run ruff check .              # Lint
uv run tox                       # Test across Python 3.11-3.14
```

**Before every commit:** run `uv run ruff format .` then `uv run ruff check --fix .` (auto-fixes most issues) then `uv run ruff check .` to verify no remaining errors.

```bash
uv run tox -e py312              # Test a specific Python version
```

CI: ruff format --check, ruff check, pytest with coverage.

## Architecture

**Entry point:** `onebot:run` — parses CLI args, loads INI config, starts bot.

**Plugin system:** Each plugin = class with `@irc3.plugin` in `onebot/plugins/`. Declare deps via `requires` list. Use `@command` / `@event` decorators from irc3. Bot injected via `__init__(self, bot)`.

Key plugins:

- **users.py** — User management, NickServ integration, permission system
- **acl.py** — Access control lists for permission checks
- **urlinfo.py** — Extracts/displays info from URLs in channels
- **lastfm.py / trakt.py / spotify.py** — Music/TV integrations
- **python.py** — Executes Python in Docker sandbox (`python-sandbox/`)
- **antispam.py** — Rate limiting, spam protection

**Testing pattern:** Extend `onebot.testing.BotTestCase` (wraps `irc3.testing.BotTestCase`). Config via `config` dict, call `self.callFTU()` in setUp, simulate IRC with `self.bot.dispatch()`, verify with `self.assertSent()`. HTTP via betamax cassettes in `tests/fixtures/cassettes/`.

**Deployment:** Docker image from `python:3.14-slim` + `uv`. `compose.yaml` runs bot + Redis + sandboxed Python container with resource limits.

## Code Style

- Line length: 88 (ruff)
- Target: Python 3.11
- Doctests auto-collected (`--doctest-modules`) — keep module-level examples valid

