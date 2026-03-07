# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
├── routers/
│   ├── health.py     # GET /health
│   └── webhooks.py   # POST /webhook/whatsapp
├── models/
│   └── message.py    # Pydantic request/response models
└── services/         # Business logic (agent integration lives here in M2+)
```

`main.py` owns no logic — only imports and wires. Logic belongs in its own module.

All configuration is read from environment variables via `config.settings`. The `.env` file (copied from `.env.example`) is loaded automatically by pydantic-settings.

## Async pattern

Webhook handlers return immediately (`{"received": True}`) — no blocking work in the request lifecycle. Background processing will be dispatched from `services/` in later milestones.
