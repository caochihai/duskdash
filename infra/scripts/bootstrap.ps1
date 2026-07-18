[CmdletBinding()]
param(
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
$infraRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $infraRoot '.env.local'

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing $envFile. Run scripts/generate-secrets.ps1 first."
}

$compose = @(
    'compose',
    '--env-file', (Join-Path $infraRoot 'versions.env'),
    '--env-file', $envFile,
    '-f', (Join-Path $infraRoot 'docker-compose.infra.yml'),
    '-f', (Join-Path $infraRoot 'docker-compose.tools.yml'),
    '-f', (Join-Path $infraRoot 'docker-compose.observability.yml')
)

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandArgs)
    & docker @compose @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
}

& docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker engine is not reachable. Start Docker Desktop and retry.'
}

Write-Host 'Starting core infrastructure and waiting for health checks...'
Invoke-Compose up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak

Write-Host 'Applying Flyway migrations...'
Invoke-Compose run --rm flyway

Write-Host 'Applying idempotent seed data...'
Invoke-Compose run --rm db-seed

Write-Host 'Bootstrapping Kafka topics, users, and ACLs...'
Invoke-Compose run --rm kafka-init

Write-Host 'Bootstrapping private MinIO buckets, policies, and service users...'
Invoke-Compose run --rm minio-init

Write-Host 'Bootstrapping Keycloak client secrets and demo users...'
Invoke-Compose run --rm keycloak-init

Write-Host 'Verifying the Keycloak OIDC contract and demo token...'
Invoke-Compose run --rm keycloak-smoke

if (-not $SkipVerify) {
    & (Join-Path $PSScriptRoot 'verify-stack.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw "Stack verification failed with exit code $LASTEXITCODE"
    }
}

Write-Host 'Infrastructure bootstrap completed.'
