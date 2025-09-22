#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./deploy-cloudrun.sh <GCP_PROJECT_ID> <REGION> <SERVICE_NAME>
# Example:
#   ./deploy-cloudrun.sh my-project asia-south1 libraryconnekto-api

PROJECT_ID=${1:-}
REGION=${2:-}
SERVICE=${3:-}

if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ] || [ -z "$SERVICE" ]; then
  echo "Usage: $0 <GCP_PROJECT_ID> <REGION> <SERVICE_NAME>" >&2
  exit 1
fi

IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}:$(date +%Y%m%d-%H%M%S)"

echo "==> Verifying gcloud auth & project"
gcloud config set project "$PROJECT_ID"

echo "==> Building Docker image: ${IMAGE}"
gcloud builds submit --tag "$IMAGE" .

# Required env vars for app (set your values or pass via --set-env-vars)
# DATABASE_URL must be available at runtime. Example (replace with Secret Manager ref if needed):
#   --set-env-vars DATABASE_URL=postgresql://user:pass@host:5432/db \

echo "==> Deploying to Cloud Run: ${SERVICE}"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 512Mi \
  --max-instances 5 \
  --set-env-vars "PYTHONDONTWRITEBYTECODE=1,PYTHONUNBUFFERED=1" \
  --set-env-vars "UVICORN_WORKERS=2,UVICORN_LOG_LEVEL=info" \
  # Add your required environment values here, e.g.:
  # --set-env-vars "DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME" \
  # --set-env-vars "SECRET_KEY=...,JWT_ALGORITHM=HS256,ACCESS_TOKEN_EXPIRE_MINUTES=30" \
  # --set-env-vars "ALLOWED_ORIGINS=http://localhost:3000" \
  # --set-env-vars "SMTP_HOST=...,SMTP_PORT=465,SMTP_USERNAME=...,SMTP_PASSWORD=..." \
  # --set-env-vars "RAZORPAY_KEY_ID=...,RAZORPAY_KEY_SECRET=..."

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')
echo "==> Deployed: $URL"
