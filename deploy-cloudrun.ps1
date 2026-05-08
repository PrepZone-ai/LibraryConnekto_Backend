Param(
  [Parameter(Mandatory=$true)][string]$ProjectId,
  [Parameter(Mandatory=$true)][string]$Region,
  [Parameter(Mandatory=$true)][string]$Service,
  [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

# Example:
#   .\deploy-cloudrun.ps1 -ProjectId my-project -Region asia-south1 -Service libraryconnekto-api

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$image = "gcr.io/$ProjectId/${Service}:$timestamp"
$workerService = "$Service-worker"
$beatService = "$Service-beat"

function Get-EnvVarArgs {
  Param([string]$Path)

  if (-not (Test-Path $Path)) {
    return @()
  }

  $pairs = @()
  foreach ($line in Get-Content $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    if (-not $trimmed.Contains("=")) { continue }
    if ($trimmed.StartsWith("export ")) { $trimmed = $trimmed.Substring(7).Trim() }

    $split = $trimmed.Split("=", 2)
    $key = $split[0].Trim()
    if (-not $key) { continue }

    $value = $split[1].Trim().Trim("'`"")
    $pairs += "$key=$value"
  }

  if ($pairs.Count -eq 0) {
    return @()
  }

  return @("--set-env-vars", ($pairs -join ","))
}

function Invoke-GcloudRunDeploy {
  Param(
    [string]$Name,
    [string]$Cpu,
    [string]$Memory,
    [string]$MaxInstances,
    [string]$RunMode,
    [string]$SchedulerOwner,
    [string]$ExtraEnvVars,
    [switch]$Public
  )

  $args = @(
    "run", "deploy", $Name,
    "--image", $image,
    "--region", $Region,
    "--platform", "managed",
    "--cpu", $Cpu,
    "--memory", $Memory,
    "--max-instances", $MaxInstances,
    "--set-env-vars", "PYTHONDONTWRITEBYTECODE=1,PYTHONUNBUFFERED=1,RUN_MODE=$RunMode,SCHEDULER_OWNER=$SchedulerOwner",
    "--set-env-vars", $ExtraEnvVars
  )

  $args += Get-EnvVarArgs -Path $EnvFile

  if ($Public) {
    $args += "--allow-unauthenticated"
    if ($RunMode -eq "web") {
      $args += @("--port", "8080")
    }
  } else {
    $args += "--no-allow-unauthenticated"
  }

  & gcloud @args
}

Write-Host "==> Setting gcloud project" -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

Write-Host "==> Building Docker image: $image" -ForegroundColor Cyan
gcloud builds submit --tag $image .

Write-Host "==> Deploying to Cloud Run: $Service" -ForegroundColor Cyan
Invoke-GcloudRunDeploy `
  -Name $Service `
  -Cpu "1" `
  -Memory "512Mi" `
  -MaxInstances "5" `
  -RunMode "web" `
  -SchedulerOwner "worker" `
  -ExtraEnvVars "UVICORN_WORKERS=2,UVICORN_LOG_LEVEL=info" `
  -Public

Write-Host "==> Deploying worker service: $workerService" -ForegroundColor Cyan
Invoke-GcloudRunDeploy `
  -Name $workerService `
  -Cpu "1" `
  -Memory "512Mi" `
  -MaxInstances "3" `
  -RunMode "worker" `
  -SchedulerOwner "worker" `
  -ExtraEnvVars "UVICORN_LOG_LEVEL=info,CELERY_WORKER_CONCURRENCY=4"

Write-Host "==> Deploying beat service: $beatService" -ForegroundColor Cyan
Invoke-GcloudRunDeploy `
  -Name $beatService `
  -Cpu "1" `
  -Memory "256Mi" `
  -MaxInstances "1" `
  -RunMode "beat" `
  -SchedulerOwner "worker" `
  -ExtraEnvVars "UVICORN_LOG_LEVEL=info"

$serviceUrl = gcloud run services describe $Service --region $Region --format 'value(status.url)'
Write-Host "==> API Deployed: $serviceUrl" -ForegroundColor Green
