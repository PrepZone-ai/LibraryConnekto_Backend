#!/usr/bin/env bash
set -euo pipefail

# Default values
: "${PORT:=8080}"
: "${UVICORN_WORKERS:=2}"
: "${UVICORN_LOG_LEVEL:=info}"

# Show environment summary (without secrets)
echo "==> Starting Backend (FastAPI)"
echo "PORT=${PORT}  WORKERS=${UVICORN_WORKERS}  LOG_LEVEL=${UVICORN_LOG_LEVEL}"

# Database migrations
if [ -f "alembic.ini" ]; then
  echo "==> Running Alembic migrations"
  python -m alembic upgrade head || {
    echo "Alembic migration failed" >&2
    exit 1
  }
else
  echo "==> alembic.ini not found, skipping migrations"
fi

# Ensure uploads directory exists at runtime
mkdir -p uploads/profile_images || true

# Start Uvicorn (Cloud Run passes $PORT)
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${UVICORN_WORKERS}" \
  --log-level "${UVICORN_LOG_LEVEL}"
