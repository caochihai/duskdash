[CmdletBinding()]
param(
    [switch]$SkipProfiles
)

$ErrorActionPreference = 'Stop'
$infraRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $infraRoot '.env.local'
$script:failures = 0
$script:passes = 0

function Write-Pass([string]$Message) {
    $script:passes++
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    $script:failures++
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Test-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Body
    )
    try {
        & $Body
        Write-Pass $Name
    }
    catch {
        Write-Fail "$Name - $($_.Exception.Message)"
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

Assert-True (Test-Path -LiteralPath $envFile) "Missing $envFile; generate secrets first"

$compose = @(
    'compose', '--env-file', (Join-Path $infraRoot 'versions.env'),
    '--env-file', $envFile,
    '-f', (Join-Path $infraRoot 'docker-compose.infra.yml'),
    '-f', (Join-Path $infraRoot 'docker-compose.tools.yml'),
    '-f', (Join-Path $infraRoot 'docker-compose.observability.yml')
)

function Invoke-ComposeCapture {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandArgs)
    $output = & docker @compose @CommandArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        $safeSummary = ($output | Select-Object -Last 5) -join ' '
        throw "docker compose exited ${LASTEXITCODE}: $safeSummary"
    }
    return $output
}

function Invoke-PostgresScalar {
    param([Parameter(Mandatory = $true)][string]$Sql)
    $output = Invoke-ComposeCapture exec -T postgres psql -X -U postgres -d bank_ai -v ON_ERROR_STOP=1 -Atqc $Sql
    return (($output | Select-Object -Last 1).ToString()).Trim()
}

function Test-HttpEndpoint {
    param([string]$Uri, [int[]]$AllowedStatus = @(200))
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 15 -MaximumRedirection 0 -ErrorAction Stop
        Assert-True ($AllowedStatus -contains [int]$response.StatusCode) "HTTP $($response.StatusCode) from $Uri"
    }
    catch {
        if ($_.Exception.Response -and $AllowedStatus -contains [int]$_.Exception.Response.StatusCode) { return }
        throw
    }
}

Test-Step 'Required infrastructure files exist' {
    $required = @(
        '.env.example', 'versions.env', 'docker-compose.infra.yml', 'docker-compose.tools.yml',
        'docker-compose.observability.yml', 'Makefile', 'README.md',
        'database/migrations/V017__add_comments.sql', 'database/seeds/run-seeds.sh',
        'kafka/topics/topics.yaml', 'kafka/acl/acl.yaml', 'kafka/schemas/event-envelope.v1.json',
        'minio/buckets.yaml', 'keycloak/realm-bank-ai.json',
        'scripts/bootstrap.ps1', 'scripts/bootstrap.sh', 'scripts/verify-stack.sh',
        'docs/architecture.md', 'docs/data-dictionary.md', 'docs/runbook.md'
    )
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $infraRoot $_)) })
    Assert-True ($missing.Count -eq 0) "Missing: $($missing -join ', ')"
}

Test-Step 'PowerShell scripts parse successfully' {
    $parseFailures = @()
    Get-ChildItem -LiteralPath (Join-Path $infraRoot 'scripts') -Filter '*.ps1' | ForEach-Object {
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors)
        if ($errors.Count -gt 0) { $parseFailures += $_.Name }
    }
    Assert-True ($parseFailures.Count -eq 0) "Parse failure: $($parseFailures -join ', ')"
}

Test-Step 'Docker Compose config is valid for all profiles' {
    [void](Invoke-ComposeCapture --profile tools --profile observability config --quiet)
}

Test-Step 'No Compose image uses latest or an unpinned tag' {
    $images = @(Invoke-ComposeCapture --profile tools --profile observability config --images)
    foreach ($image in $images) {
        Assert-True ($image -notmatch '(^|:)latest(?:@|$)') "latest image found"
        Assert-True ($image -match '(:[^/]+$|@sha256:)') "untagged image found"
    }
}

Test-Step 'Profiles isolate tools and observability services' {
    $configText = (Invoke-ComposeCapture --profile tools --profile observability config --format json) -join "`n"
    $config = $configText | ConvertFrom-Json
    foreach ($service in @('pgadmin', 'kafka-ui')) {
        Assert-True ($config.services.$service.profiles -contains 'tools') "$service is not tools-only"
    }
    foreach ($service in @('postgres-exporter', 'redis-exporter', 'kafka-exporter', 'prometheus', 'grafana')) {
        Assert-True ($config.services.$service.profiles -contains 'observability') "$service is not observability-only"
    }
}

Test-Step 'Source configs contain no changeme placeholder' {
    $extensions = @('.yml', '.yaml', '.json', '.conf', '.properties', '.sql', '.sh', '.ps1', '.example')
    $files = Get-ChildItem -LiteralPath $infraRoot -Recurse -File | Where-Object {
        $_.FullName -ne $envFile -and $_.Name -ne 'intructions.md' -and
        ($extensions -contains $_.Extension -or $_.Name -in @('Dockerfile', 'Makefile'))
    }
    $hit = $files | Select-String -SimpleMatch -Pattern 'changeme' -List
    Assert-True ($null -eq $hit) 'changeme placeholder found in source config'
}

Test-Step 'Generated secret values do not appear in source files' {
    $secretKeys = @(
        'POSTGRES_SUPERUSER_PASSWORD', 'POSTGRES_MIGRATOR_PASSWORD', 'POSTGRES_APP_PASSWORD',
        'POSTGRES_WORKER_PASSWORD', 'POSTGRES_READONLY_PASSWORD', 'KEYCLOAK_DB_PASSWORD',
        'REDIS_PASSWORD', 'MINIO_ROOT_PASSWORD', 'MINIO_BANK_API_SECRET_KEY',
        'MINIO_DOCUMENT_WORKER_SECRET_KEY', 'MINIO_POLICY_WORKER_SECRET_KEY',
        'MINIO_REPORT_WORKER_SECRET_KEY', 'MINIO_AUDIT_WRITER_SECRET_KEY',
        'KEYCLOAK_ADMIN_PASSWORD', 'KEYCLOAK_BACKEND_CLIENT_SECRET', 'KEYCLOAK_WORKER_CLIENT_SECRET',
        'KAFKA_ADMIN_PASSWORD', 'KAFKA_BANK_API_PASSWORD', 'KAFKA_DOCUMENT_WORKER_PASSWORD',
        'KAFKA_ANALYSIS_ORCHESTRATOR_PASSWORD', 'KAFKA_CREDIT_WORKER_PASSWORD',
        'KAFKA_COMPLIANCE_WORKER_PASSWORD', 'KAFKA_REPORT_WORKER_PASSWORD',
        'KAFKA_NOTIFICATION_GATEWAY_PASSWORD', 'KAFKA_AUDIT_CONSUMER_PASSWORD',
        'FIELD_ENCRYPTION_KEY', 'SEED_USER_PASSWORD'
    )
    $localValues = @{}
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^([^#=]+)=(.*)$') { $localValues[$matches[1]] = $matches[2] }
    }
    $sourceFiles = Get-ChildItem -LiteralPath $infraRoot -Recurse -File | Where-Object {
        $_.FullName -ne $envFile -and $_.Name -ne 'intructions.md'
    }
    foreach ($file in $sourceFiles) {
        $content = [System.IO.File]::ReadAllText($file.FullName)
        foreach ($key in $secretKeys) {
            $value = $localValues[$key]
            if ($value -and $value.Length -ge 20 -and $content.Contains($value)) {
                throw "Generated value for $key appears in $($file.FullName)"
            }
        }
    }
}

Test-Step '.env.local is not tracked' {
    & git -C (Split-Path -Parent $infraRoot) rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -eq 0) {
        $tracked = & git -C (Split-Path -Parent $infraRoot) ls-files -- 'infra/.env.local'
        Assert-True ([string]::IsNullOrWhiteSpace(($tracked -join ''))) '.env.local is tracked by Git'
    }
}

Test-Step 'Docker engine is reachable' {
    $serverVersion = & docker info --format '{{.ServerVersion}}' 2>&1
    Assert-True ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($serverVersion -join ''))) 'Docker engine unavailable'
}

Test-Step 'Core services are running and healthy' {
    [void](Invoke-ComposeCapture up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak)
    $rows = @(Invoke-ComposeCapture ps --format json | ForEach-Object { $_ | ConvertFrom-Json })
    foreach ($service in @('postgres', 'redis', 'kafka', 'minio', 'keycloak')) {
        $row = $rows | Where-Object Service -eq $service | Select-Object -First 1
        Assert-True ($null -ne $row) "$service is absent"
        Assert-True ($row.State -eq 'running') "$service state is $($row.State)"
        Assert-True ($row.Health -eq 'healthy') "$service health is $($row.Health)"
    }
}

Test-Step 'Flyway migrations are complete' {
    [void](Invoke-ComposeCapture run --rm flyway)
    Assert-True ((Invoke-PostgresScalar "SELECT count(*) FROM public.flyway_schema_history WHERE success") -eq '17') 'Expected 17 successful migrations'
}

Test-Step 'PostgreSQL databases, extensions, schemas, comments, RLS, and roles are valid' {
    $checks = @{
        databases = "SELECT count(*) FROM pg_database WHERE datname IN ('bank_ai','keycloak')"
        extensions = "SELECT count(*) FROM pg_extension WHERE extname IN ('vector','pgcrypto','citext','uuid-ossp')"
        schemas = "SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('identity','customer','banking','storage','document','credit','policy','ai','integration','audit')"
        rls = "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('customer','banking','document','credit','ai') AND c.relrowsecurity"
        unsafe_roles = "SELECT count(*) FROM pg_roles WHERE rolname IN ('bank_app','bank_worker','bank_readonly','keycloak_app') AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)"
        missing_table_comments = "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','customer','banking','storage','document','credit','policy','ai','integration','audit') AND c.relkind='r' AND NOT c.relispartition AND obj_description(c.oid,'pg_class') IS NULL"
        missing_column_comments = "SELECT count(*) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','customer','banking','storage','document','credit','policy','ai','integration','audit') AND c.relkind IN ('r','p') AND NOT c.relispartition AND a.attnum>0 AND NOT a.attisdropped AND col_description(c.oid,a.attnum) IS NULL"
    }
    Assert-True ((Invoke-PostgresScalar $checks.databases) -eq '2') 'Required databases missing'
    Assert-True ((Invoke-PostgresScalar $checks.extensions) -eq '4') 'Required extensions missing'
    Assert-True ((Invoke-PostgresScalar $checks.schemas) -eq '10') 'Required schemas missing'
    Assert-True ([int](Invoke-PostgresScalar $checks.rls) -ge 14) 'RLS is not enabled on all required tables'
    Assert-True ((Invoke-PostgresScalar $checks.unsafe_roles) -eq '0') 'Runtime role has an unsafe attribute'
    Assert-True ((Invoke-PostgresScalar $checks.missing_table_comments) -eq '0') 'A required table lacks a comment'
    Assert-True ((Invoke-PostgresScalar $checks.missing_column_comments) -eq '0') 'A required column lacks a comment'
}

Test-Step 'Seed is idempotent and meets required cardinalities' {
    [void](Invoke-ComposeCapture run --rm db-seed)
    [void](Invoke-ComposeCapture run --rm db-seed)
    $seedSql = @"
SELECT CASE WHEN
 (SELECT count(*) FROM identity.branch)=3 AND
 (SELECT count(*) FROM identity.department)=4 AND
 (SELECT count(*) FROM identity.employee)=7 AND
 (SELECT count(*) FROM customer.customer)=3 AND
 (SELECT count(*) FROM banking.account)=6 AND
 (SELECT count(*) FROM credit.loan_application WHERE requested_amount=700000000.0000 AND requested_term_months=60)=1 AND
 (SELECT count(*) FROM integration.background_job)>=1 AND
 (SELECT count(*) FROM integration.event_outbox WHERE status='PENDING')>=1 AND
 (SELECT count(DISTINCT date_trunc('month', booking_time)) FROM banking."transaction")>=12
THEN 1 ELSE 0 END
"@
    Assert-True ((Invoke-PostgresScalar $seedSql) -eq '1') 'Seed cardinality or scenario mismatch'
}

Test-Step 'Redis rejects unauthenticated access and accepts the generated password' {
    $unauth = & docker @compose exec -T redis redis-cli PING 2>&1
    Assert-True (($unauth -join ' ') -match 'NOAUTH') 'Unauthenticated Redis PING was not rejected'
    $auth = Invoke-ComposeCapture exec -T redis sh -ec 'redis-cli --no-auth-warning -a "$REDIS_PASSWORD" PING'
    Assert-True ((($auth | Select-Object -Last 1).ToString()).Trim() -eq 'PONG') 'Authenticated Redis PING failed'
}

Test-Step 'Kafka topics, retention, SCRAM ACL denial, and produce/consume pass' {
    [void](Invoke-ComposeCapture run --rm kafka-init)
}

Test-Step 'MinIO buckets, versioning, lifecycle, privacy, and policy checks pass' {
    [void](Invoke-ComposeCapture run --rm minio-init)
}

Test-Step 'Keycloak realm, clients, roles, demo login, issuer, and audience pass' {
    [void](Invoke-ComposeCapture run --rm keycloak-init)
    [void](Invoke-ComposeCapture run --rm keycloak-smoke)
}

if (-not $SkipProfiles) {
    Test-Step 'Tools profile starts PgAdmin and Kafka UI' {
        [void](Invoke-ComposeCapture --profile tools up -d pgadmin kafka-ui)
        Start-Sleep -Seconds 10
        Test-HttpEndpoint 'http://localhost:5050/' @(200, 302)
        Test-HttpEndpoint 'http://localhost:8085/' @(200, 302)
    }

    Test-Step 'Observability profile starts and all scrape targets are healthy' {
        [void](Invoke-ComposeCapture --profile observability up -d prometheus grafana)
        $deadline = [DateTime]::UtcNow.AddMinutes(2)
        do {
            Start-Sleep -Seconds 5
            try {
                $targets = (Invoke-RestMethod -Uri 'http://localhost:9090/api/v1/targets' -TimeoutSec 15).data.activeTargets
                $requiredPools = @('postgres', 'redis', 'kafka', 'kafka-jmx', 'minio')
                $healthyPools = @($targets | Where-Object health -eq 'up' | ForEach-Object scrapePool)
                $allHealthy = @($requiredPools | Where-Object { $healthyPools -notcontains $_ }).Count -eq 0
            }
            catch { $allHealthy = $false }
        } until ($allHealthy -or [DateTime]::UtcNow -ge $deadline)
        Assert-True $allHealthy 'One or more required Prometheus scrape targets are down'
        Test-HttpEndpoint 'http://localhost:3001/api/health' @(200)
    }
}

Write-Host "Verification summary: $script:passes passed, $script:failures failed."
if ($script:failures -gt 0) { exit 1 }
exit 0
