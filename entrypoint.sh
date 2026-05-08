#!/usr/bin/env bash
set -euo pipefail

# Default values
: "${PORT:=8080}"
: "${UVICORN_WORKERS:=2}"
: "${UVICORN_LOG_LEVEL:=info}"
: "${RUN_MODE:=web}"
: "${CELERY_WORKER_CONCURRENCY:=4}"

# Show environment summary (without secrets)
echo "==> Starting LibraryConnekto Backend"
echo "MODE=${RUN_MODE} PORT=${PORT} WORKERS=${UVICORN_WORKERS} LOG_LEVEL=${UVICORN_LOG_LEVEL}"
echo "User: $(whoami)"

# Database connection test - Skip migrations if tables exist
echo "==> Testing database connection..."
python test_db_connection.py && {
  echo "✅ Database connection successful - skipping migrations"
} || {
  echo "⚠️  Database connection failed or no tables found"
  echo "==> Running Alembic migrations..."
  if [ -f "alembic.ini" ]; then
    python -m alembic upgrade head || {
      echo "❌ Alembic migration failed" >&2
      exit 1
    }
    echo "✅ Database migrations completed"
  else
    echo "⚠️  alembic.ini not found, skipping migrations"
  fi
}

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

if [ "${RUN_MODE}" = "worker" ]; then
  echo "==> Starting Celery worker..."
  exec celery -A app.celery_app:celery_app worker \
    --loglevel="${UVICORN_LOG_LEVEL}" \
    --concurrency="${CELERY_WORKER_CONCURRENCY}"
elif [ "${RUN_MODE}" = "beat" ]; then
  echo "==> Starting Celery beat..."
  exec celery -A app.celery_app:celery_app beat \
    --loglevel="${UVICORN_LOG_LEVEL}"
else
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
fi
