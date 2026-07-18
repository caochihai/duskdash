#!/bin/sh

set -eu

MINIO_ROOT_DIR="${MINIO_ROOT_DIR:-/opt/bank/minio}"
MINIO_INTERNAL_ENDPOINT="${MINIO_INTERNAL_ENDPOINT:-http://minio:9000}"
MINIO_ALIAS="${MINIO_ALIAS:-bank-minio}"

log() {
  printf '[minio] %s\n' "$*"
}

fail() {
  printf '[minio] ERROR: %s\n' "$*" >&2
  exit 1
}

require_env() {
  for variable_name in "$@"; do
    eval "variable_value=\${$variable_name:-}"
    [ -n "$variable_value" ] || fail "required environment variable is empty: $variable_name"
  done
}

command -v mc >/dev/null 2>&1 || fail 'mc executable is required'
require_env \
  MINIO_ROOT_USER \
  MINIO_ROOT_PASSWORD \
  MINIO_BANK_API_SECRET_KEY \
  MINIO_DOCUMENT_WORKER_SECRET_KEY \
  MINIO_POLICY_WORKER_SECRET_KEY \
  MINIO_REPORT_WORKER_SECRET_KEY \
  MINIO_AUDIT_WRITER_SECRET_KEY \
  MINIO_DERIVED_RETENTION_DAYS

case "$MINIO_DERIVED_RETENTION_DAYS" in
  ''|*[!0-9]*) fail 'MINIO_DERIVED_RETENTION_DAYS must be a positive integer' ;;
esac
[ "$MINIO_DERIVED_RETENTION_DAYS" -gt 0 ] || fail 'MINIO_DERIVED_RETENTION_DAYS must be greater than zero'

MC_CONFIG_DIR="$(mktemp -d)"
export MC_CONFIG_DIR MC_NO_COLOR=1 MC_DISABLE_PAGER=1
cleanup_config() {
  if [ -n "${MC_CONFIG_DIR:-}" ] && [ -d "$MC_CONFIG_DIR" ]; then
    rm -rf -- "$MC_CONFIG_DIR"
  fi
}
trap cleanup_config EXIT HUP INT TERM

attempt=1
while [ "$attempt" -le 60 ]; do
  if mc alias set "$MINIO_ALIAS" "$MINIO_INTERNAL_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1 && \
     mc ready "$MINIO_ALIAS" >/dev/null 2>&1; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 2
done
[ "$attempt" -le 60 ] || fail 'MinIO did not become ready after 120 seconds'
log 'server is ready'

for bucket in upload-quarantine customer-doc-original policy-documents generated-reports; do
  mc mb --ignore-existing "$MINIO_ALIAS/$bucket" >/dev/null
done

# Object lock is enabled at creation time. It provides legal-hold semantics for
# derived objects and append-only version history for the audit archive.
for bucket in customer-doc-derived audit-archive; do
  mc mb --ignore-existing --with-lock "$MINIO_ALIAS/$bucket" >/dev/null
done

for bucket in customer-doc-original customer-doc-derived policy-documents generated-reports audit-archive; do
  mc version enable "$MINIO_ALIAS/$bucket" >/dev/null
done

for bucket in upload-quarantine customer-doc-original customer-doc-derived policy-documents generated-reports audit-archive; do
  mc anonymous set none "$MINIO_ALIAS/$bucket" >/dev/null
done

for bucket in upload-quarantine customer-doc-original customer-doc-derived policy-documents generated-reports; do
  mc cors set "$MINIO_ALIAS/$bucket" "$MINIO_ROOT_DIR/cors.json" >/dev/null
done

mc ilm rule import "$MINIO_ALIAS/upload-quarantine" < "$MINIO_ROOT_DIR/lifecycle/upload-quarantine.json" >/dev/null
derived_lifecycle="$(mktemp)"
sed "s/__RETENTION_DAYS__/$MINIO_DERIVED_RETENTION_DAYS/g" \
  "$MINIO_ROOT_DIR/lifecycle/customer-doc-derived.json.template" > "$derived_lifecycle"
mc ilm rule import "$MINIO_ALIAS/customer-doc-derived" < "$derived_lifecycle" >/dev/null
rm -f -- "$derived_lifecycle"

for identity in bank-api document-worker policy-worker report-worker audit-writer; do
  mc admin policy create "$MINIO_ALIAS" "$identity" "$MINIO_ROOT_DIR/policies/$identity.json" >/dev/null
done

reconcile_user() {
  identity="$1"
  secret="$2"
  mc admin user add "$MINIO_ALIAS" "$identity" "$secret" >/dev/null
  mc admin user enable "$MINIO_ALIAS" "$identity" >/dev/null
  mc admin policy attach "$MINIO_ALIAS" "$identity" --user "$identity" >/dev/null
}

reconcile_user bank-api "$MINIO_BANK_API_SECRET_KEY"
reconcile_user document-worker "$MINIO_DOCUMENT_WORKER_SECRET_KEY"
reconcile_user policy-worker "$MINIO_POLICY_WORKER_SECRET_KEY"
reconcile_user report-worker "$MINIO_REPORT_WORKER_SECRET_KEY"
reconcile_user audit-writer "$MINIO_AUDIT_WRITER_SECRET_KEY"

log 'buckets, lifecycle rules, CORS, users, and least-privilege policies were reconciled'
sh "$MINIO_ROOT_DIR/smoke-test.sh"

