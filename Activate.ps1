<#
.SYNOPSIS
    Dựng dậy toàn bộ dự án AI Credit Intelligence Workbench.

.DESCRIPTION
    Khởi động cả 3 phần của dự án theo đúng thứ tự:
      1. Infrastructure  — Docker containers (PostgreSQL, Redis, Kafka, MinIO, Keycloak)
      2. Backend          — FastAPI Python API server (port 8000)
      3. Frontend         — Vite React dev server (port 3000)

    Chạy lần đầu sẽ tự động sinh secrets, cài đặt dependencies, và tạo file .env.local cho
    cả backend lẫn frontend.

.PARAMETER MockMode
    Chỉ chạy frontend ở chế độ mock (không cần infra hay backend).
    Dữ liệu demo được lấy từ src/services/mockApi.ts.

.PARAMETER SkipInfra
    Bỏ qua bước khởi động Docker infrastructure (khi infra đã chạy sẵn).

.PARAMETER SkipBackend
    Bỏ qua bước khởi động backend API server.

.PARAMETER Force
    Được giữ để tương thích; script không tự xoay secret của volume đang hoạt động.

.PARAMETER ResetKafka
    Xóa riêng local Kafka volume và tạo lại users/topics/ACLs. Chỉ dùng khi
    credential trong infra/.env.local không còn khớp với Kafka volume.

.EXAMPLE
    .\Activate.ps1                  # Khởi động đầy đủ cả 3 phần
    .\Activate.ps1 -MockMode        # Chỉ chạy frontend demo (không cần Docker)
    .\Activate.ps1 -SkipInfra       # Bỏ qua infra, chạy backend + frontend
    .\Activate.ps1 -ResetKafka      # Khôi phục Kafka local rồi chạy full-stack
#>
[CmdletBinding()]
param(
    [switch]$MockMode,
    [switch]$SkipInfra,
    [switch]$SkipBackend,
    [switch]$Force,
    [switch]$ResetKafka
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ── Paths ────────────────────────────────────────────────────────────────────
$projectRoot  = $PSScriptRoot
$infraRoot    = Join-Path $projectRoot 'infra'
$backendRoot  = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'

# ── Banner ───────────────────────────────────────────────────────────────────
function Write-Banner {
    Write-Host ''
    Write-Host '  ╔══════════════════════════════════════════════════════════╗' -ForegroundColor Cyan
    Write-Host '  ║      AI Credit Intelligence Workbench — Activate        ║' -ForegroundColor Cyan
    Write-Host '  ║              SHB AI Assistant v1.0.0                    ║' -ForegroundColor Cyan
    Write-Host '  ╚══════════════════════════════════════════════════════════╝' -ForegroundColor Cyan
    Write-Host ''
}

function Write-Phase {
    param([string]$Number, [string]$Title)
    Write-Host ''
    Write-Host "  ── Phase $Number : $Title ──────────────────────────────────" -ForegroundColor Yellow
    Write-Host ''
}

function Write-Step {
    param([string]$Message)
    Write-Host "    ➤ $Message" -ForegroundColor Green
}

function Write-Skip {
    param([string]$Message)
    Write-Host "    ⊘ $Message" -ForegroundColor DarkGray
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    ⚠ $Message" -ForegroundColor DarkYellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "    ✗ $Message" -ForegroundColor Red
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    ✓ $Message" -ForegroundColor Green
}

# ── Prerequisite checks ─────────────────────────────────────────────────────
function Test-Prerequisites {
    Write-Phase '0' 'Prerequisite Checks'

    # Docker (unless MockMode)
    if (-not $MockMode -and -not $SkipInfra) {
        $dockerInfo = docker info --format '{{.ServerVersion}}' 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Err 'Docker Desktop is not running. Start Docker Desktop and retry.'
            Write-Err 'Or use -MockMode to run frontend-only demo without Docker.'
            throw 'Docker engine is not reachable.'
        }
        Write-Ok "Docker Desktop detected (v$dockerInfo)"
    }

    # Node.js
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err 'Node.js not found. Install from https://nodejs.org/'
        throw 'Node.js is required.'
    }
    Write-Ok "Node.js detected ($nodeVersion)"

    # npm
    $npmVersion = npm --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err 'npm not found.'
        throw 'npm is required.'
    }
    Write-Ok "npm detected (v$npmVersion)"
}

# ── Phase 1: Infrastructure ─────────────────────────────────────────────────
function Start-Infrastructure {
    if ($MockMode -or $SkipInfra) {
        Write-Phase '1' 'Infrastructure (SKIPPED)'
        if ($MockMode) { Write-Skip 'MockMode: infrastructure not required.' }
        else { Write-Skip 'SkipInfra: assuming infrastructure is already running.' }
        return
    }

    Write-Phase '1' 'Infrastructure'
    $infraEnvLocal = Join-Path $infraRoot '.env.local'

    # Generate secrets
    if (-not (Test-Path -LiteralPath $infraEnvLocal)) {
        Write-Step 'Generating infrastructure secrets...'
        & (Join-Path $infraRoot 'scripts\generate-secrets.ps1')
        Write-Ok 'Secrets generated → infra/.env.local'
    }
    else {
        Write-Skip 'infra/.env.local already exists.'
        if ($Force) {
            Write-Warn '-Force does not rotate secrets while persistent volumes are active.'
        }
    }

    if ($ResetKafka) {
        Write-Step 'Resetting only the local Kafka volume and rebuilding its contract...'
        & (Join-Path $infraRoot 'scripts\stack.ps1') kafka-reset -Force
        if ($LASTEXITCODE -ne 0) {
            throw 'Kafka reset failed.'
        }
        Write-Ok 'Kafka users, topics, and ACLs were recreated.'
    }
    else {
        $infraComposeArgs = @(
            'compose',
            '--env-file', (Join-Path $infraRoot 'versions.env'),
            '--env-file', $infraEnvLocal,
            '-f', (Join-Path $infraRoot 'docker-compose.infra.yml')
        )
        $kafkaStateJson = & docker @infraComposeArgs ps kafka --format json 2>$null
        if ($LASTEXITCODE -eq 0 -and $kafkaStateJson) {
            $kafkaState = $kafkaStateJson | ConvertFrom-Json
            if ($kafkaState.Health -eq 'unhealthy') {
                Write-Err 'Kafka is unhealthy because its persisted SCRAM credentials are stale.'
                throw 'Re-run .\Activate.ps1 -ResetKafka to reset only local Kafka data.'
            }
        }
    }

    # Bootstrap infrastructure
    Write-Step 'Bootstrapping Docker infrastructure (this may take a few minutes on first run)...'
    & (Join-Path $infraRoot 'scripts\bootstrap.ps1') -SkipVerify
    if ($LASTEXITCODE -ne 0) {
        throw 'Infrastructure bootstrap failed.'
    }
    Write-Ok 'Infrastructure is running and initialized.'
}

# ── Phase 2: Backend ────────────────────────────────────────────────────────
function Initialize-BackendEnv {
    $infraEnvLocal = Join-Path $infraRoot '.env.local'
    $backendEnvLocal = Join-Path $backendRoot '.env.local'

    if (Test-Path -LiteralPath $backendEnvLocal) {
        Write-Skip 'backend/.env.local already exists.'
        return
    }

    if (-not (Test-Path -LiteralPath $infraEnvLocal)) {
        Write-Err 'infra/.env.local not found. Cannot generate backend/.env.local.'
        throw 'Run infrastructure phase first or provide backend/.env.local manually.'
    }

    Write-Step 'Generating backend/.env.local from infrastructure secrets...'

    # Parse infra secrets
    $infraSecrets = @{}
    Get-Content $infraEnvLocal | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $eqIndex = $line.IndexOf('=')
            if ($eqIndex -gt 0) {
                $key = $line.Substring(0, $eqIndex)
                $val = $line.Substring($eqIndex + 1)
                $infraSecrets[$key] = $val
            }
        }
    }

    # Build backend .env.local
    $dbPassword    = $infraSecrets['POSTGRES_APP_PASSWORD']
    $dbUser        = $infraSecrets['POSTGRES_APP_USER']
    $redisPassword = $infraSecrets['REDIS_PASSWORD']
    $kafkaPassword = $infraSecrets['KAFKA_BANK_API_PASSWORD']
    $minioSecret   = $infraSecrets['MINIO_BANK_API_SECRET_KEY']
    $fieldEncKey   = $infraSecrets['FIELD_ENCRYPTION_KEY']

    $backendEnv = @"
# Auto-generated by Activate.ps1 from infra/.env.local — Do not commit.
APP_NAME=bank-ai-backend
APP_ENV=development
APP_PROCESS_TYPE=api
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=false
APP_CORS_ORIGINS=http://localhost:3000

# PostgreSQL
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=bank_ai
DATABASE_USER=$dbUser
DATABASE_PASSWORD=$dbPassword
DATABASE_URL=postgresql://${dbUser}:${dbPassword}@localhost:5432/bank_ai
DATABASE_POOL_SIZE=20
DATABASE_POOL_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_ECHO=false

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_EXTERNAL_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_SECURITY_PROTOCOL=SASL_PLAINTEXT
KAFKA_SASL_MECHANISM=SCRAM-SHA-512
KAFKA_SASL_USERNAME=bank-api
KAFKA_SASL_PASSWORD=$kafkaPassword
KAFKA_CLIENT_ID=bank-api
KAFKA_ENABLE_AUTO_COMMIT=false
KAFKA_AUTO_OFFSET_RESET=earliest

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=$redisPassword
REDIS_URL=redis://:${redisPassword}@localhost:6379/0
REDIS_KEY_PREFIX=bank-ai
CUSTOMER_ASSIGNMENT_LEASE_TTL_SECONDS=300

# MinIO
MINIO_INTERNAL_ENDPOINT=http://localhost:9000
MINIO_PUBLIC_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=bank-api
MINIO_SECRET_KEY=$minioSecret
MINIO_SECURE=false
MINIO_PRESIGNED_TTL_SECONDS=600

# Keycloak/OIDC
KEYCLOAK_INTERNAL_URL=http://localhost:8080
KEYCLOAK_PUBLIC_URL=http://localhost:8080
KEYCLOAK_REALM=bank-ai
KEYCLOAK_ISSUER_URL=http://localhost:8080/realms/bank-ai
KEYCLOAK_JWKS_INTERNAL_URL=http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs
KEYCLOAK_TOKEN_URL=http://localhost:8080/realms/bank-ai/protocol/openid-connect/token
OIDC_EXPECTED_AUDIENCE=bank-ai-api
OIDC_ALLOWED_ALGORITHMS=RS256
OIDC_JWKS_CACHE_TTL_SECONDS=300
OIDC_CLOCK_SKEW_SECONDS=30

# AI Providers (mock for local development)
OCR_PROVIDER=mock
LLM_PROVIDER=mock
LLM_MODEL_NAME=mock-model
EMBEDDING_PROVIDER=mock
EMBEDDING_DIMENSION=1024
EMBEDDING_MODEL_NAME=mock-embedding

# Security/Logging
FIELD_ENCRYPTION_KEY=$fieldEncKey
MAX_UPLOAD_SIZE_BYTES=52428800
RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO
LOG_FORMAT=console
"@

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($backendEnvLocal, $backendEnv, $utf8NoBom)
    Write-Ok 'backend/.env.local generated with infrastructure secrets.'
}

function Initialize-FrontendEnv {
    param([bool]$UseMock = $false)

    $frontendEnvLocal = Join-Path $frontendRoot '.env.local'

    if (Test-Path -LiteralPath $frontendEnvLocal) {
        Write-Step 'Reconciling frontend/.env.local for the selected mode...'
    }
    else {
        Write-Step 'Generating frontend/.env.local...'
    }

    $mockValue = if ($UseMock) { 'true' } else { 'false' }

    $frontendEnv = @"
# Auto-generated by Activate.ps1 — Do not commit.
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_USE_MOCK_API=$mockValue
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=bank-ai
VITE_KEYCLOAK_CLIENT_ID=bank-ai-frontend
VITE_APP_NAME=SHB AI Assistant
VITE_APP_ENV=development
"@

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($frontendEnvLocal, $frontendEnv, $utf8NoBom)
    Write-Ok "frontend/.env.local generated (MOCK_API=$mockValue)."
}

function Start-Backend {
    if ($MockMode -or $SkipBackend) {
        Write-Phase '2' 'Backend (SKIPPED)'
        if ($MockMode) { Write-Skip 'MockMode: backend not required.' }
        else { Write-Skip 'SkipBackend: backend startup skipped.' }
        return
    }

    Write-Phase '2' 'Backend'

    $composeArgs = @(
        'compose',
        '--env-file', (Join-Path $infraRoot 'versions.env'),
        '--env-file', (Join-Path $infraRoot '.env.local'),
        '-f', (Join-Path $infraRoot 'docker-compose.infra.yml'),
        '-f', (Join-Path $backendRoot 'docker-compose.backend.yml')
    )

    Write-Step 'Building and starting backend API container (port 8000)...'
    & docker @composeArgs up -d --build backend-api
    if ($LASTEXITCODE -ne 0) {
        Write-Err 'Backend container could not start. Check Kafka health or use -ResetKafka for stale local credentials.'
        throw 'Backend startup failed.'
    }

    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Seconds 2
        try {
            $health = Invoke-RestMethod -Uri 'http://localhost:8000/health/live' -TimeoutSec 3
        }
        catch {
            $health = $null
        }
    } while ($null -eq $health -and (Get-Date) -lt $deadline)

    if ($null -eq $health) {
        throw 'Backend did not pass its liveness check within 90 seconds.'
    }

    Write-Ok 'Backend API container is healthy.'
    Write-Ok 'API docs: http://localhost:8000/docs'
    Write-Ok 'Health:   http://localhost:8000/health/live'
}

# ── Phase 3: Frontend ───────────────────────────────────────────────────────
function Start-Frontend {
    Write-Phase '3' 'Frontend'

    # Generate .env.local
    Initialize-FrontendEnv -UseMock:$MockMode

    # Install dependencies
    $nodeModules = Join-Path $frontendRoot 'node_modules'
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        Write-Step 'Installing npm dependencies (first run)...'
        Push-Location $frontendRoot
        try {
            & npm install
            if ($LASTEXITCODE -ne 0) {
                throw 'npm install failed.'
            }
        }
        finally {
            Pop-Location
        }
        Write-Ok 'npm dependencies installed.'
    }
    else {
        Write-Skip 'node_modules already exists.'
    }

    # Start frontend dev server in foreground
    Write-Step 'Starting frontend dev server (port 3000)...'
    Write-Host ''
    Write-Host '  ╔══════════════════════════════════════════════════════════╗' -ForegroundColor Green
    Write-Host '  ║                 All services started!                   ║' -ForegroundColor Green
    Write-Host '  ╠══════════════════════════════════════════════════════════╣' -ForegroundColor Green
    if (-not $MockMode -and -not $SkipInfra) {
        Write-Host '  ║  Infrastructure:                                        ║' -ForegroundColor Green
        Write-Host '  ║    PostgreSQL   → localhost:5432                         ║' -ForegroundColor White
        Write-Host '  ║    Redis        → localhost:6379                         ║' -ForegroundColor White
        Write-Host '  ║    Kafka        → localhost:29092                        ║' -ForegroundColor White
        Write-Host '  ║    MinIO        → http://localhost:9000  (console :9001) ║' -ForegroundColor White
        Write-Host '  ║    Keycloak     → http://localhost:8080                  ║' -ForegroundColor White
        Write-Host '  ║                                                          ║' -ForegroundColor Green
    }
    if (-not $MockMode -and -not $SkipBackend) {
        Write-Host '  ║  Backend API    → http://localhost:8000/docs             ║' -ForegroundColor White
        Write-Host '  ║                                                          ║' -ForegroundColor Green
    }
    Write-Host '  ║  Frontend       → http://localhost:3000                  ║' -ForegroundColor White
    if ($MockMode) {
        Write-Host '  ║  Mode           → MOCK (demo data, no backend needed)   ║' -ForegroundColor DarkYellow
    }
    Write-Host '  ║                                                          ║' -ForegroundColor Green
    Write-Host '  ║  Press Ctrl+C to stop the frontend dev server.           ║' -ForegroundColor DarkGray
    Write-Host '  ╚══════════════════════════════════════════════════════════╝' -ForegroundColor Green
    Write-Host ''

    Push-Location $frontendRoot
    try {
        & npm run dev
    }
    finally {
        Pop-Location
        # Backend and infrastructure remain detached so the next run is fast.
    }
}

# ── Main ─────────────────────────────────────────────────────────────────────
try {
    Write-Banner
    Test-Prerequisites
    Start-Infrastructure
    Start-Backend
    Start-Frontend
}
catch {
    Write-Host ''
    Write-Err "Activation failed: $_"
    Write-Host ''
    exit 1
}
