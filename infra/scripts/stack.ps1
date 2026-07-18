[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet(
        'secrets', 'infra-up', 'infra-down', 'infra-reset', 'infra-logs', 'infra-ps',
        'db-migrate', 'db-seed', 'db-shell', 'db-verify',
        'kafka-init', 'kafka-reset', 'kafka-topics', 'kafka-acls', 'kafka-smoke', 'kafka-describe',
        'minio-init', 'minio-verify', 'keycloak-init', 'keycloak-verify',
        'tools-up', 'observability-up', 'verify', 'bootstrap'
    )]
    [string]$Action,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$infraRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $infraRoot '.env.local'

if ($Action -eq 'secrets') {
    & (Join-Path $PSScriptRoot 'generate-secrets.ps1') -Force:$Force
    exit $LASTEXITCODE
}

if ($Action -eq 'bootstrap') {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
    exit $LASTEXITCODE
}

if ($Action -eq 'verify') {
    & (Join-Path $PSScriptRoot 'verify-stack.ps1')
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing $envFile. Run stack.ps1 secrets first."
}

$compose = @(
    'compose', '--env-file', (Join-Path $infraRoot 'versions.env'),
    '--env-file', $envFile,
    '-f', (Join-Path $infraRoot 'docker-compose.infra.yml'),
    '-f', (Join-Path $infraRoot 'docker-compose.tools.yml'),
    '-f', (Join-Path $infraRoot 'docker-compose.observability.yml')
)

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandArgs)
    & docker @compose @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed with exit code $LASTEXITCODE" }
}

switch ($Action) {
    'infra-up' { Invoke-Compose up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak }
    'infra-down' { Invoke-Compose down --remove-orphans }
    'infra-reset' {
        if (-not $Force) {
            $answer = Read-Host 'This removes all local infrastructure volumes. Type RESET to continue'
            if ($answer -cne 'RESET') { Write-Host 'Reset cancelled.'; exit 1 }
        }
        Invoke-Compose down --volumes --remove-orphans
    }
    'infra-logs' { Invoke-Compose logs --tail 200 -f }
    'infra-ps' { Invoke-Compose ps }
    'db-migrate' { Invoke-Compose run --rm flyway }
    'db-seed' { Invoke-Compose run --rm db-seed }
    'db-shell' {
        Invoke-Compose exec postgres psql -U bank_migrator -d bank_ai
    }
    'db-verify' {
        Invoke-Compose exec -T postgres psql -U postgres -d bank_ai -v ON_ERROR_STOP=1 -c "SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto','citext','uuid-ossp') ORDER BY extname;"
    }
    'kafka-init' { Invoke-Compose run --rm kafka-init }
    'kafka-reset' {
        if (-not $Force) {
            $answer = Read-Host 'This removes only the local Kafka volume. Type KAFKA_RESET to continue'
            if ($answer -cne 'KAFKA_RESET') { Write-Host 'Kafka reset cancelled.'; exit 1 }
        }

        Invoke-Compose stop kafka
        Invoke-Compose rm -f kafka

        $kafkaVolumes = @(
            & docker volume ls `
                --filter 'label=com.docker.compose.project=bank-ai-workbench' `
                --filter 'label=com.docker.compose.volume=kafka_data' `
                --format '{{.Name}}'
        )
        if ($LASTEXITCODE -ne 0) {
            throw "Could not resolve the Kafka volume (exit code $LASTEXITCODE)."
        }
        if ($kafkaVolumes.Count -ne 1) {
            throw "Expected exactly one Kafka volume, found $($kafkaVolumes.Count)."
        }

        $volumeName = $kafkaVolumes[0]
        $volumeLabels = & docker volume inspect $volumeName `
            --format '{{index .Labels "com.docker.compose.project"}}|{{index .Labels "com.docker.compose.volume"}}'
        if ($LASTEXITCODE -ne 0 -or $volumeLabels -ne 'bank-ai-workbench|kafka_data') {
            throw "Refusing to remove unexpected Docker volume: $volumeName"
        }

        & docker volume rm $volumeName
        if ($LASTEXITCODE -ne 0) {
            throw "Could not remove Kafka volume $volumeName."
        }
        Invoke-Compose up -d --wait --wait-timeout 180 kafka
        Invoke-Compose run --rm kafka-init
        Write-Host 'Kafka local data was reset and the required users, topics, and ACLs were recreated.'
    }
    'kafka-topics' { Invoke-Compose run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/create-topics.sh }
    'kafka-acls' { Invoke-Compose run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/create-acls.sh }
    'kafka-smoke' { Invoke-Compose run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/smoke-test.sh }
    'kafka-describe' { Invoke-Compose run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/describe.sh }
    'minio-init' { Invoke-Compose run --rm minio-init }
    'minio-verify' { Invoke-Compose run --rm --entrypoint /bin/sh minio-init /opt/bank/minio/smoke-test.sh }
    'keycloak-init' { Invoke-Compose run --rm keycloak-init }
    'keycloak-verify' { Invoke-Compose run --rm keycloak-smoke }
    'tools-up' { Invoke-Compose --profile tools up -d pgadmin kafka-ui }
    'observability-up' { Invoke-Compose --profile observability up -d prometheus grafana }
}
