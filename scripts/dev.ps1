[CmdletBinding()]
param(
    [switch]$Bootstrap,
    [switch]$Workers,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$infraRoot = Join-Path $projectRoot 'infra'
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$infraEnv = Join-Path $infraRoot '.env.local'
$versionsEnv = Join-Path $infraRoot 'versions.env'
$infraCompose = Join-Path $infraRoot 'docker-compose.infra.yml'
$backendCompose = Join-Path $backendRoot 'docker-compose.backend.yml'

if (-not (Test-Path -LiteralPath $infraEnv)) {
    throw "Missing $infraEnv. Run .\infra\scripts\stack.ps1 secrets first."
}

& docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Desktop is not reachable.'
}

if ($Bootstrap) {
    & (Join-Path $infraRoot 'scripts\bootstrap.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw "Infrastructure bootstrap failed with exit code $LASTEXITCODE."
    }
}

$compose = @(
    'compose',
    '--env-file', $versionsEnv,
    '--env-file', $infraEnv,
    '-f', $infraCompose,
    '-f', $backendCompose
)

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandArgs)
    & docker @compose @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE."
    }
}

Write-Host 'Starting infrastructure and waiting for health checks...'
Invoke-Compose up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak

$backendArguments = @('up', '-d')
if (-not $SkipBuild) {
    $backendArguments += '--build'
}
$backendArguments += 'backend-api'
Write-Host 'Starting backend API...'
Invoke-Compose @backendArguments

if ($Workers) {
    Write-Host 'Starting outbox publisher and backend workers...'
    Invoke-Compose --profile backend-workers up -d `
        backend-outbox-publisher `
        backend-document-worker `
        backend-analysis-worker `
        backend-credit-worker `
        backend-compliance-worker `
        backend-report-worker `
        backend-notification-worker
}

$frontendEnv = Join-Path $frontendRoot '.env'
if (-not (Test-Path -LiteralPath $frontendEnv)) {
    Copy-Item -LiteralPath (Join-Path $frontendRoot '.env.example') -Destination $frontendEnv
    Write-Host 'Created ignored frontend/.env from .env.example.'
}

Push-Location $frontendRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules'))) {
        Write-Host 'Installing frontend dependencies...'
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed with exit code $LASTEXITCODE."
        }
    }

    Write-Host ''
    Write-Host 'Keycloak: http://localhost:8080'
    Write-Host 'Backend:  http://localhost:8000'
    Write-Host 'Frontend: http://localhost:3000'
    Write-Host 'Press Ctrl+C to stop the frontend. Docker services remain running.'
    & npm.cmd run dev
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
