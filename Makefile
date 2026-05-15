# Jonas dev stack orchestration.
# Run `make help` for the target list.

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
SERVICE ?=

.PHONY: help up down restart migrate logs web diag

help:
	@printf "Jonas dev stack targets:\n\n"
	@printf "  make up       Start all containers, run migrations, print diagnostics\n"
	@printf "  make down     Stop containers (named volumes persist)\n"
	@printf "  make restart  Restart all containers (volumes persist)\n"
	@printf "  make migrate  Apply pending Alembic migrations (alembic upgrade head)\n"
	@printf "  make logs     Tail logs for all services. Use SERVICE=api to scope.\n"
	@printf "  make web      Run the Vite dev server in web/ (blocks until Ctrl-C)\n"
	@printf "  make diag     Print compose ps + per-service health probes\n"

up:
	@echo "==> Starting containers..."
	@$(COMPOSE) up -d
	@echo "==> Waiting for api to become healthy..."
	@for i in $$(seq 1 30); do \
		if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then \
			echo "    api is healthy"; \
			break; \
		fi; \
		if [ $$i -eq 30 ]; then \
			echo "    api did not respond within 30s"; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory diag

down:
	@echo "==> Stopping containers (volumes persist)..."
	@$(COMPOSE) down

restart:
	@echo "==> Restarting containers..."
	@$(COMPOSE) restart

migrate:
	@echo "==> Applying Alembic migrations..."
	@$(COMPOSE) exec -T api alembic upgrade head

logs:
	@$(COMPOSE) logs -f $(SERVICE)

web:
	@echo "==> Starting Vite dev server (Ctrl-C to stop)..."
	@cd web && npm install --silent && npm run dev

diag:
	@echo "==> docker compose ps"
	@$(COMPOSE) ps
	@echo ""
	@echo "==> Health probes"
	@printf "  %-10s " "api"; \
		if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then echo "PASS"; else echo "FAIL"; fi
	@printf "  %-10s " "qdrant"; \
		if curl -fsS http://localhost:6333/readyz >/dev/null 2>&1; then echo "PASS"; else echo "FAIL"; fi
	@printf "  %-10s " "langfuse"; \
		code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000"); \
		if [ "$$code" -ge 200 ] && [ "$$code" -lt 400 ]; then echo "PASS ($$code)"; else echo "FAIL ($$code)"; fi
	@printf "  %-10s " "postgres"; \
		if $(COMPOSE) exec -T postgres pg_isready >/dev/null 2>&1; then echo "PASS"; else echo "FAIL"; fi
	@printf "  %-10s " "redis"; \
		if $(COMPOSE) exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then echo "PASS"; else echo "FAIL"; fi
