Param(
  [Parameter(Mandatory=$true)][string]$ProjectId,
  [Parameter(Mandatory=$true)][string]$Region,
  [Parameter(Mandatory=$true)][string]$Service
)

$ErrorActionPreference = "Stop"

# Example:
#   .\deploy-cloudrun.ps1 -ProjectId my-project -Region asia-south1 -Service libraryconnekto-api

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$image = "gcr.io/$ProjectId/$Service:$timestamp"

Write-Host "==> Setting gcloud project" -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

Write-Host "==> Building Docker image: $image" -ForegroundColor Cyan
gcloud builds submit --tag $image .

Write-Host "==> Deploying to Cloud Run: $Service" -ForegroundColor Cyan
gcloud run deploy $Service `
  --image $image `
  --region $Region `
  --platform managed `
  --allow-unauthenticated `
  --port 8080 `
  --cpu 1 `
  --memory 512Mi `
  --max-instances 5 `
  --set-env-vars "PYTHONDONTWRITEBYTECODE=1,PYTHONUNBUFFERED=1" `
  --set-env-vars "UVICORN_WORKERS=2,UVICORN_LOG_LEVEL=info"
  # Add your env vars:
  # --set-env-vars "DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME" `
  # --set-env-vars "SECRET_KEY=...,JWT_ALGORITHM=HS256,ACCESS_TOKEN_EXPIRE_MINUTES=30" `
  # --set-env-vars "ALLOWED_ORIGINS=http://localhost:3000" `
  # --set-env-vars "SMTP_HOST=...,SMTP_PORT=465,SMTP_USERNAME=...,SMTP_PASSWORD=..." `
  # --set-env-vars "RAZORPAY_KEY_ID=...,RAZORPAY_KEY_SECRET=..."

$serviceUrl = gcloud run services describe $Service --region $Region --format 'value(status.url)'
Write-Host "==> Deployed: $serviceUrl" -ForegroundColor Green
