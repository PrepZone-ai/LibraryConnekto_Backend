#!/usr/bin/env bash
set -euo pipefail

# Default values
: "${PORT:=8080}"
: "${UVICORN_WORKERS:=2}"
: "${UVICORN_LOG_LEVEL:=info}"

# Show environment summary (without secrets)
echo "==> Starting LibraryConnekto Backend (FastAPI)"
echo "PORT=${PORT}  WORKERS=${UVICORN_WORKERS}  LOG_LEVEL=${UVICORN_LOG_LEVEL}"
echo "User: $(whoami)"

# Database migrations
if [ -f "alembic.ini" ]; then
  echo "==> Running Alembic migrations"
  python -m alembic upgrade head || {
    echo "❌ Alembic migration failed" >&2
    exit 1
  }
  echo "✅ Database migrations completed"
else
  echo "⚠️  alembic.ini not found, skipping migrations"
fi

# Ensure uploads directory exists at runtime
mkdir -p uploads/profile_images || true
echo "✅ Upload directories created"

# Validate required environment variables
if [ -z "${DATABASE_URL:-}" ]; then
  echo "❌ DATABASE_URL environment variable is required" >&2
  exit 1
fi

if [ -z "${SECRET_KEY:-}" ] || [ "${SECRET_KEY}" = "change-me-in-prod" ]; then
  echo "❌ SECRET_KEY must be set and changed from default" >&2
  exit 1
fi

echo "✅ Environment validation passed"

# Start Uvicorn (Cloud Run passes $PORT)
echo "==> Starting Uvicorn server..."
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${UVICORN_WORKERS}" \
  --log-level "${UVICORN_LOG_LEVEL}" \
  --access-log \
  --loop uvloop \
  --http httptools
