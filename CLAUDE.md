# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Linear Project
- workspace: odeloic-inc
- project: jonas-mvp-german-tutor-agent-374b0ae7ed5c

## Stack

FastAPI + Postgres + Redis + Qdrant, running via Docker Compose. The `api/` directory is mounted into the container — saving any file triggers uvicorn hot reload.

## Local dev commands

```bash
# Start full stack
docker compose up -d

# Tail API logs
docker compose logs -f api

# Stop (data persists in named volumes)
docker compose down
```

Health check URLs:
- API: http://localhost:8000/health
- Qdrant: http://localhost:6333/dashboard

## Database migrations (Alembic)

Alembic is configured with async SQLAlchemy (`asyncpg` driver). Migrations auto-run on container start via the Dockerfile entrypoint.

### Creating a new migration

1. Add/edit SQLAlchemy model in `api/models/`
2. **Import the model in `api/migrations/env.py`** — autogenerate only sees models attached to `Base.metadata`
3. Generate: `docker compose exec api alembic revision --autogenerate -m "description"`
4. **Sanity-check the generated file** in `api/migrations/versions/` — verify it has the expected `op.create_table()` / `op.add_column()` calls (not empty `pass`)
5. Apply: `docker compose exec api alembic upgrade head`
6. Verify: `docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c '\dt'`

### Common commands

```bash
docker compose exec api alembic upgrade head      # apply all pending
docker compose exec api alembic downgrade -1       # roll back one
docker compose exec api alembic current            # show current revision
docker compose exec api alembic history            # show all revisions
```

### Deleting / reverting a migration

```bash
# Roll back first, then delete the file
docker compose exec api alembic downgrade -1
rm api/migrations/versions/<revision>_<slug>.py

# If the migration was empty / broken and already applied, clear the stamp manually:
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'DELETE FROM alembic_version;'
```

### Gotchas

- **Missing model imports in `env.py`** → autogenerate produces empty migrations (`pass`). Always import new models there.
- `migrations/versions/` is excluded from ruff (configured in `api/pyproject.toml`).
- `api/db.py` — uses `expire_on_commit=False` (not `expires_on_commit`).

Key files:
- `api/db.py` — SQLAlchemy engine, async session factory, `Base` class
- `api/alembic.ini` — Alembic config (DB URL set from Python, not here)
- `api/migrations/env.py` — Async migration runner, imports models for autogenerate
- `api/migrations/versions/` — Migration scripts

## Python / dependency management

The project uses `uv` inside Docker (see `api/Dockerfile`). For local tooling, always activate the venv first:

```bash
cd api
source .venv/bin/activate
uv pip install <package>
```

Never use bare `pip` — use `uv pip`. Dependencies go in `api/requirements.txt`.

## Linting

```bash
cd api
source .venv/bin/activate
ruff check .          # lint
ruff format .         # format
ruff check --fix .    # lint + auto-fix
```

Config is in `api/pyproject.toml`. Pre-commit hooks run ruff automatically on every commit (installed via `pre-commit install`).

CI runs `ruff check .` and `ruff format --check .` on push/PR via `.github/workflows/lint.yml`.

## API module layout

```
api/
├── main.py           # App wiring only: lifespan, router registration
├── config.py         # All env vars via pydantic-settings (Settings singleton)
├── logging_config.py # structlog setup (JSON in prod, colored in dev)
├── channels/
│   └── telegram.py   # Telegram bot (ConversationHandler, /teach flow)
├── routers/
│   ├── health.py     # GET /health
│   ├── webhooks.py   # POST /webhook/whatsapp
│   └── dev.py        # POST /dev/llm-ping (LLM test endpoint)
├── models/
│   └── message.py    # Pydantic request/response models
└── services/
    └── llm.py        # LiteLLM async wrapper (provider-agnostic)
```

`main.py` owns no logic — only imports and wires. Logic belongs in its own module.

All configuration is read from environment variables via `config.settings`. The `.env` file (copied from `.env.example`) is loaded automatically by pydantic-settings.

## Key patterns

### LLM service (`services/llm.py`)
- `async def complete(messages, model=None, max_tokens=1024) -> str` — thin wrapper around `litellm.acompletion()`
- Falls back to `settings.default_model` (currently `claude-haiku-4-5-20251001`)
- Logs token usage via structlog; catches `AuthenticationError` and `APIError`

### Telegram bot (`channels/telegram.py`)
- Built with `python-telegram-bot>=21.0` (async, v21 API)
- Auth guard: `is_correct_chat()` checks `settings.telegram_allowed_chat_id`
- `/teach` flow uses `ConversationHandler` with states: `WAITING_FOR_PHOTOS → /done`
- Photos accumulated as `file_id` strings in `context.user_data`
- 5-minute conversation timeout
- Bot is initialized in `main.py` lifespan, runs via polling

### Logging
- structlog everywhere: `log = structlog.get_logger()` then `log.info("event_name", key=value)`
- Dev: colored console. Prod: JSON to stdout.

### Config (`config.py`)
- Pydantic `BaseSettings` singleton, all env vars
- Key settings: `default_model`, `telegram_bot_token`, `telegram_allowed_chat_id`, `anthropic_api_key`

## Async pattern

Webhook handlers return immediately (`{"received": True}`) — no blocking work in the request lifecycle. Background processing will be dispatched from `services/` in later milestones.

## User-facing language

The bot speaks German to the user. All user-facing messages (Telegram replies, error messages) should be in German.
