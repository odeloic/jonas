# Jonas

Local development stack: FastAPI + Postgres + Redis + Qdrant.

## First-time setup

```bash
cp .env.example .env
# Edit .env and fill in any real values you need
```

## Commands

The `Makefile` is the primary entry point. Run `make help` for the full list.

```bash
make up       # start containers, run migrations, print diagnostics
make down     # stop containers (named volumes persist)
make migrate  # apply pending Alembic migrations
make logs     # tail all logs (use SERVICE=api to scope)
make web      # run the Vite dev server in web/
make diag     # compose ps + per-service health probes
```

Raw `docker compose` commands still work for one-offs:

```bash
docker compose up -d
docker compose down
docker compose logs -f [service]
```

## Health check URLs

- API: http://localhost:8000/health
- Qdrant dashboard: http://localhost:6333/dashboard

## Hot reload

The `./api` directory is mounted into the `api` container. Saving any file in `api/` triggers an automatic uvicorn reload — no restart needed.
