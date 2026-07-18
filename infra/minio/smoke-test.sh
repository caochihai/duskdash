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
command -v curl >/dev/null 2>&1 || fail 'curl executable is required'
require_env \
  MINIO_ROOT_USER \
  MINIO_ROOT_PASSWORD \
  MINIO_BANK_API_ACCESS_KEY \
  MINIO_BANK_API_SECRET_KEY \
  MINIO_DOCUMENT_WORKER_ACCESS_KEY \
  MINIO_POLICY_WORKER_ACCESS_KEY \
  MINIO_REPORT_WORKER_ACCESS_KEY \
  MINIO_AUDIT_WRITER_ACCESS_KEY \
  MINIO_DERIVED_RETENTION_DAYS \
  MINIO_EXPECTED_CORS_ALLOW_ORIGIN \
  MINIO_EXPECTED_STALE_UPLOADS_EXPIRY

if [ -z "${MC_CONFIG_DIR:-}" ]; then
  MC_CONFIG_DIR="$(mktemp -d)"
  export MC_CONFIG_DIR
  REMOVE_MC_CONFIG=true
else
  REMOVE_MC_CONFIG=false
fi
export MC_NO_COLOR=1 MC_DISABLE_PAGER=1

smoke_id=''
derived_smoke_object=''
cleanup() {
  if [ -n "$smoke_id" ]; then
    mc rm --force "$MINIO_ALIAS/upload-quarantine/uploads/$smoke_id/incoming" >/dev/null 2>&1 || true
  fi
  if [ -n "$derived_smoke_object" ]; then
    mc rm --force "$MINIO_ALIAS/$derived_smoke_object" >/dev/null 2>&1 || true
  fi
  if [ "$REMOVE_MC_CONFIG" = true ] && [ -n "${MC_CONFIG_DIR:-}" ] && [ -d "$MC_CONFIG_DIR" ]; then
    rm -rf -- "$MC_CONFIG_DIR"
  fi
}
trap cleanup EXIT HUP INT TERM

mc alias set "$MINIO_ALIAS" "$MINIO_INTERNAL_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc ready "$MINIO_ALIAS" >/dev/null || fail 'MinIO health check failed'

for bucket in upload-quarantine customer-doc-original customer-doc-derived policy-documents generated-reports audit-archive; do
  mc stat "$MINIO_ALIAS/$bucket" >/dev/null || fail "required bucket is missing: $bucket"
  anonymous_status="$(mc anonymous get "$MINIO_ALIAS/$bucket" 2>&1 || true)"
  printf '%s' "$anonymous_status" | grep -qi private || fail "bucket is not private: $bucket"
done

for bucket in customer-doc-original policy-documents generated-reports audit-archive; do
  version_status="$(mc version info "$MINIO_ALIAS/$bucket")"
  printf '%s' "$version_status" | grep -qi 'versioning is enabled' || fail "versioning is not enabled for $bucket"
done
derived_version_status="$(mc version info "$MINIO_ALIAS/customer-doc-derived" 2>&1 || true)"
printf '%s' "$derived_version_status" | grep -Eqi \
  '(versioning is (not enabled|suspended)|is un-versioned)' || \
  fail 'versioning must remain disabled for customer-doc-derived'

quarantine_ilm="$(mc ilm rule export "$MINIO_ALIAS/upload-quarantine")"
printf '%s' "$quarantine_ilm" | grep -q 'expire-quarantine-after-3-days' || fail 'quarantine expiration lifecycle rule is missing'
printf '%s' "$quarantine_ilm" | grep -Eq '"Days"[[:space:]]*:[[:space:]]*3' || fail 'quarantine lifecycle is not set to 3 days'
[ "$MINIO_EXPECTED_STALE_UPLOADS_EXPIRY" = '24h' ] || \
  fail 'stale multipart cleanup expiry must remain 24h'

cors_headers="$(curl --silent --show-error --fail \
  --request OPTIONS \
  --dump-header - \
  --output /dev/null \
  --header "Origin: $MINIO_EXPECTED_CORS_ALLOW_ORIGIN" \
  --header 'Access-Control-Request-Method: PUT' \
  "$MINIO_INTERNAL_ENDPOINT/upload-quarantine/cors-smoke")"
printf '%s' "$cors_headers" | grep -Fqi \
  "access-control-allow-origin: $MINIO_EXPECTED_CORS_ALLOW_ORIGIN" || \
  fail 'MinIO CORS origin does not allow the local frontend'
printf '%s' "$cors_headers" | grep -Eqi 'access-control-allow-methods:.*PUT' || \
  fail 'MinIO CORS preflight does not allow PUT'

derived_ilm="$(mc ilm rule export "$MINIO_ALIAS/customer-doc-derived")"
printf '%s' "$derived_ilm" | grep -q 'expire-derived-after-configured-retention' || fail 'derived retention lifecycle rule is missing'
printf '%s' "$derived_ilm" | grep -Eq "\"Days\"[[:space:]]*:[[:space:]]*$MINIO_DERIVED_RETENTION_DAYS" || \
  fail 'derived retention does not match MINIO_DERIVED_RETENTION_DAYS'
printf '%s' "$derived_ilm" | grep -Fq 'retention-status' || fail 'derived lifecycle tag key is missing'
printf '%s' "$derived_ilm" | grep -Fq 'eligible' || fail 'derived lifecycle tag value is missing'
if printf '%s' "$derived_ilm" | grep -q 'NoncurrentVersionExpiration'; then
  fail 'derived lifecycle must not expire noncurrent versions'
fi

for identity in bank-api document-worker policy-worker report-worker audit-writer; do
  mc admin policy info "$MINIO_ALIAS" "$identity" >/dev/null || fail "policy is missing: $identity"
done
for access_key in \
  "$MINIO_BANK_API_ACCESS_KEY" \
  "$MINIO_DOCUMENT_WORKER_ACCESS_KEY" \
  "$MINIO_POLICY_WORKER_ACCESS_KEY" \
  "$MINIO_REPORT_WORKER_ACCESS_KEY" \
  "$MINIO_AUDIT_WRITER_ACCESS_KEY"; do
  mc admin user svcacct info "$MINIO_ALIAS" "$access_key" >/dev/null || \
    fail "service account is missing: $access_key"
done

smoke_id="$(date -u +%Y%m%d%H%M%S)-$$"
api_alias='bank-api-smoke'
mc alias set "$api_alias" "$MINIO_INTERNAL_ENDPOINT" "$MINIO_BANK_API_ACCESS_KEY" "$MINIO_BANK_API_SECRET_KEY" >/dev/null
printf 'bank-ai-minio-smoke\n' | mc pipe "$api_alias/upload-quarantine/uploads/$smoke_id/incoming" >/dev/null
object_contents="$(mc cat "$api_alias/upload-quarantine/uploads/$smoke_id/incoming")"
[ "$object_contents" = 'bank-ai-minio-smoke' ] || fail 'bank-api could not read its smoke object'

if mc rm --force "$api_alias/upload-quarantine/uploads/$smoke_id/incoming" >/dev/null 2>&1; then
  fail 'bank-api unexpectedly deleted a quarantine object'
fi

derived_smoke_object="customer-doc-derived/documents/$smoke_id/versions/$smoke_id/ocr/result.json"
printf '{"smoke":true}\n' | mc pipe "$MINIO_ALIAS/$derived_smoke_object" >/dev/null
mc tag set "$api_alias/$derived_smoke_object" 'retention-status=eligible' >/dev/null
derived_tags="$(mc tag list "$api_alias/$derived_smoke_object")"
printf '%s' "$derived_tags" | grep -Fq 'retention-status' || fail 'bank-api could not read the retention tag'
printf '%s' "$derived_tags" | grep -Fq 'eligible' || fail 'bank-api could not mark a derived object eligible'
if mc rm --force "$api_alias/$derived_smoke_object" >/dev/null 2>&1; then
  fail 'bank-api unexpectedly deleted a derived object'
fi

log 'health, CORS, buckets, privacy, versioning, lifecycle, service-account, and denied-delete smoke tests passed'
