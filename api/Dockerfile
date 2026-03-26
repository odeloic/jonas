FROM node:22-slim AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY api/requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY --from=frontend /build/dist /srv/spa

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]
