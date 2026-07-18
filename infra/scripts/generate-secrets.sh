#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INFRA_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
OUTPUT_FILE="$INFRA_ROOT/.env.local"

if [ -e "$OUTPUT_FILE" ] && [ "${1:-}" != "--force" ]; then
  echo "$OUTPUT_FILE already exists. Re-run with --force to replace it." >&2
  exit 1
fi

secure_value() {
  byte_count="${1:-36}"
  openssl rand -base64 "$byte_count" | tr -d '\r\n=' | tr '+/' '-_'
}

umask 077
{
  echo '# Generated locally. Do not commit or share this file.'
  echo '# Regenerate dependent service credentials before replacing an active file.'
  echo 'COMPOSE_PROJECT_NAME=bank-ai-workbench'
  echo 'TZ=UTC'
  echo 'POSTGRES_SUPERUSER=postgres'
  echo "POSTGRES_SUPERUSER_PASSWORD=$(secure_value)"
  echo 'POSTGRES_MIGRATOR_USER=bank_migrator'
  echo "POSTGRES_MIGRATOR_PASSWORD=$(secure_value)"
  echo 'POSTGRES_APP_USER=bank_app'
  echo "POSTGRES_APP_PASSWORD=$(secure_value)"
  echo 'POSTGRES_WORKER_USER=bank_worker'
  echo "POSTGRES_WORKER_PASSWORD=$(secure_value)"
  echo 'POSTGRES_READONLY_USER=bank_readonly'
  echo "POSTGRES_READONLY_PASSWORD=$(secure_value)"
  echo 'KEYCLOAK_DB_USER=keycloak_app'
  echo "KEYCLOAK_DB_PASSWORD=$(secure_value)"
  echo "REDIS_PASSWORD=$(secure_value)"
  echo 'MINIO_ROOT_USER=minio-root-admin'
  echo "MINIO_ROOT_PASSWORD=$(secure_value)"
  echo 'MINIO_BANK_API_ACCESS_KEY=bank-api'
  echo "MINIO_BANK_API_SECRET_KEY=$(secure_value)"
  echo 'MINIO_DOCUMENT_WORKER_ACCESS_KEY=document-worker'
  echo "MINIO_DOCUMENT_WORKER_SECRET_KEY=$(secure_value)"
  echo 'MINIO_POLICY_WORKER_ACCESS_KEY=policy-worker'
  echo "MINIO_POLICY_WORKER_SECRET_KEY=$(secure_value)"
  echo 'MINIO_REPORT_WORKER_ACCESS_KEY=report-worker'
  echo "MINIO_REPORT_WORKER_SECRET_KEY=$(secure_value)"
  echo 'MINIO_AUDIT_WRITER_ACCESS_KEY=audit-writer'
  echo "MINIO_AUDIT_WRITER_SECRET_KEY=$(secure_value)"
  echo 'MINIO_DERIVED_RETENTION_DAYS=90'
  echo 'KEYCLOAK_ADMIN=admin'
  echo "KEYCLOAK_ADMIN_PASSWORD=$(secure_value)"
  echo "KEYCLOAK_BACKEND_CLIENT_SECRET=$(secure_value)"
  echo "KEYCLOAK_WORKER_CLIENT_SECRET=$(secure_value)"
  echo "SEED_USER_PASSWORD=$(secure_value)"
  echo "KAFKA_CLUSTER_ID=$(secure_value 16)"
  echo 'KAFKA_ADMIN_USERNAME=kafka-admin'
  echo "KAFKA_ADMIN_PASSWORD=$(secure_value)"
  echo 'KAFKA_BANK_API_USERNAME=bank-api'
  echo "KAFKA_BANK_API_PASSWORD=$(secure_value)"
  echo 'KAFKA_DOCUMENT_WORKER_USERNAME=document-worker'
  echo "KAFKA_DOCUMENT_WORKER_PASSWORD=$(secure_value)"
  echo 'KAFKA_ANALYSIS_ORCHESTRATOR_USERNAME=analysis-orchestrator'
  echo "KAFKA_ANALYSIS_ORCHESTRATOR_PASSWORD=$(secure_value)"
  echo 'KAFKA_CREDIT_WORKER_USERNAME=credit-worker'
  echo "KAFKA_CREDIT_WORKER_PASSWORD=$(secure_value)"
  echo 'KAFKA_COMPLIANCE_WORKER_USERNAME=compliance-worker'
  echo "KAFKA_COMPLIANCE_WORKER_PASSWORD=$(secure_value)"
  echo 'KAFKA_REPORT_WORKER_USERNAME=report-worker'
  echo "KAFKA_REPORT_WORKER_PASSWORD=$(secure_value)"
  echo 'KAFKA_NOTIFICATION_GATEWAY_USERNAME=notification-gateway'
  echo "KAFKA_NOTIFICATION_GATEWAY_PASSWORD=$(secure_value)"
  echo 'KAFKA_AUDIT_CONSUMER_USERNAME=audit-consumer'
  echo "KAFKA_AUDIT_CONSUMER_PASSWORD=$(secure_value)"
  echo "FIELD_ENCRYPTION_KEY=$(secure_value 32)"
  echo 'PGADMIN_DEFAULT_EMAIL=admin@example.local'
  echo "PGADMIN_DEFAULT_PASSWORD=$(secure_value)"
  echo 'GRAFANA_ADMIN_USER=admin'
  echo "GRAFANA_ADMIN_PASSWORD=$(secure_value)"
} > "$OUTPUT_FILE"

echo "Created ignored environment file: $OUTPUT_FILE"
