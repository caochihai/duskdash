[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$infraRoot = Split-Path -Parent $PSScriptRoot
$outputPath = Join-Path $infraRoot '.env.local'

if ((Test-Path -LiteralPath $outputPath) -and -not $Force) {
    throw "$outputPath already exists. Re-run with -Force to replace it."
}

function New-SecureValue {
    param([int]$ByteCount = 36)

    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }

    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

$values = [ordered]@{
    COMPOSE_PROJECT_NAME                         = 'bank-ai-workbench'
    TZ                                           = 'UTC'
    POSTGRES_SUPERUSER                           = 'postgres'
    POSTGRES_SUPERUSER_PASSWORD                  = New-SecureValue
    POSTGRES_MIGRATOR_USER                       = 'bank_migrator'
    POSTGRES_MIGRATOR_PASSWORD                   = New-SecureValue
    POSTGRES_APP_USER                            = 'bank_app'
    POSTGRES_APP_PASSWORD                        = New-SecureValue
    POSTGRES_WORKER_USER                         = 'bank_worker'
    POSTGRES_WORKER_PASSWORD                     = New-SecureValue
    POSTGRES_READONLY_USER                       = 'bank_readonly'
    POSTGRES_READONLY_PASSWORD                   = New-SecureValue
    KEYCLOAK_DB_USER                             = 'keycloak_app'
    KEYCLOAK_DB_PASSWORD                         = New-SecureValue
    REDIS_PASSWORD                               = New-SecureValue
    MINIO_ROOT_USER                              = 'minio-root-admin'
    MINIO_ROOT_PASSWORD                          = New-SecureValue
    MINIO_BANK_API_ACCESS_KEY                    = 'bank-api'
    MINIO_BANK_API_SECRET_KEY                    = New-SecureValue
    MINIO_DOCUMENT_WORKER_ACCESS_KEY             = 'document-worker'
    MINIO_DOCUMENT_WORKER_SECRET_KEY             = New-SecureValue
    MINIO_POLICY_WORKER_ACCESS_KEY               = 'policy-worker'
    MINIO_POLICY_WORKER_SECRET_KEY               = New-SecureValue
    MINIO_REPORT_WORKER_ACCESS_KEY               = 'report-worker'
    MINIO_REPORT_WORKER_SECRET_KEY               = New-SecureValue
    MINIO_AUDIT_WRITER_ACCESS_KEY                = 'audit-writer'
    MINIO_AUDIT_WRITER_SECRET_KEY                = New-SecureValue
    MINIO_DERIVED_RETENTION_DAYS                 = '90'
    KEYCLOAK_ADMIN                               = 'admin'
    KEYCLOAK_ADMIN_PASSWORD                      = New-SecureValue
    KEYCLOAK_BACKEND_CLIENT_SECRET               = New-SecureValue
    KEYCLOAK_WORKER_CLIENT_SECRET                = New-SecureValue
    SEED_USER_PASSWORD                           = New-SecureValue
    KAFKA_CLUSTER_ID                             = New-SecureValue -ByteCount 16
    KAFKA_ADMIN_USERNAME                         = 'kafka-admin'
    KAFKA_ADMIN_PASSWORD                         = New-SecureValue
    KAFKA_BANK_API_USERNAME                      = 'bank-api'
    KAFKA_BANK_API_PASSWORD                      = New-SecureValue
    KAFKA_DOCUMENT_WORKER_USERNAME               = 'document-worker'
    KAFKA_DOCUMENT_WORKER_PASSWORD               = New-SecureValue
    KAFKA_ANALYSIS_ORCHESTRATOR_USERNAME         = 'analysis-orchestrator'
    KAFKA_ANALYSIS_ORCHESTRATOR_PASSWORD         = New-SecureValue
    KAFKA_CREDIT_WORKER_USERNAME                 = 'credit-worker'
    KAFKA_CREDIT_WORKER_PASSWORD                 = New-SecureValue
    KAFKA_COMPLIANCE_WORKER_USERNAME             = 'compliance-worker'
    KAFKA_COMPLIANCE_WORKER_PASSWORD             = New-SecureValue
    KAFKA_REPORT_WORKER_USERNAME                 = 'report-worker'
    KAFKA_REPORT_WORKER_PASSWORD                 = New-SecureValue
    KAFKA_NOTIFICATION_GATEWAY_USERNAME          = 'notification-gateway'
    KAFKA_NOTIFICATION_GATEWAY_PASSWORD          = New-SecureValue
    KAFKA_AUDIT_CONSUMER_USERNAME                = 'audit-consumer'
    KAFKA_AUDIT_CONSUMER_PASSWORD                = New-SecureValue
    FIELD_ENCRYPTION_KEY                         = New-SecureValue -ByteCount 32
    PGADMIN_DEFAULT_EMAIL                        = 'admin@example.local'
    PGADMIN_DEFAULT_PASSWORD                     = New-SecureValue
    GRAFANA_ADMIN_USER                           = 'admin'
    GRAFANA_ADMIN_PASSWORD                       = New-SecureValue
}

$lines = @(
    '# Generated locally. Do not commit or share this file.'
    '# Regenerate dependent service credentials before replacing an active file.'
)
foreach ($entry in $values.GetEnumerator()) {
    $lines += ('{0}={1}' -f $entry.Key, $entry.Value)
}

$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($outputPath, (($lines -join "`n") + "`n"), $utf8WithoutBom)
Write-Host "Created ignored environment file with $($values.Count) values: $outputPath"
