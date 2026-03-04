# Jonas

Local development stack: FastAPI + Postgres + Redis + Qdrant.

## First-time setup

```bash
cp .env.example .env
# Edit .env and fill in any real values you need
```

## Commands

```bash
# Start the stack
docker compose up -d

# Stop the stack (data persists in named volumes)
docker compose down

# Tail logs
docker compose logs -f [service]
```

## Health check URLs

- API: http://localhost:8000/health
- Qdrant dashboard: http://localhost:6333/dashboard

## Hot reload

The `./api` directory is mounted into the `api` container. Saving any file in `api/` triggers an automatic uvicorn reload — no restart needed.
