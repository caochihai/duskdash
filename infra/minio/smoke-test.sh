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
require_env MINIO_ROOT_USER MINIO_ROOT_PASSWORD MINIO_BANK_API_SECRET_KEY MINIO_DERIVED_RETENTION_DAYS

if [ -z "${MC_CONFIG_DIR:-}" ]; then
  MC_CONFIG_DIR="$(mktemp -d)"
  export MC_CONFIG_DIR
  REMOVE_MC_CONFIG=true
else
  REMOVE_MC_CONFIG=false
fi
export MC_NO_COLOR=1 MC_DISABLE_PAGER=1

smoke_id=''
cleanup() {
  if [ -n "$smoke_id" ]; then
    mc rm --force "$MINIO_ALIAS/upload-quarantine/uploads/$smoke_id/incoming" >/dev/null 2>&1 || true
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

for bucket in customer-doc-original customer-doc-derived policy-documents generated-reports audit-archive; do
  version_status="$(mc version info "$MINIO_ALIAS/$bucket")"
  printf '%s' "$version_status" | grep -qi enabled || fail "versioning is not enabled for $bucket"
done

quarantine_ilm="$(mc ilm rule export "$MINIO_ALIAS/upload-quarantine")"
printf '%s' "$quarantine_ilm" | grep -q 'expire-quarantine-after-3-days' || fail 'quarantine expiration lifecycle rule is missing'
printf '%s' "$quarantine_ilm" | grep -Eq '"Days"[[:space:]]*:[[:space:]]*3' || fail 'quarantine lifecycle is not set to 3 days'
printf '%s' "$quarantine_ilm" | grep -Eq '"DaysAfterInitiation"[[:space:]]*:[[:space:]]*1' || fail 'multipart abort lifecycle is not set to 1 day'

derived_ilm="$(mc ilm rule export "$MINIO_ALIAS/customer-doc-derived")"
printf '%s' "$derived_ilm" | grep -q 'expire-derived-after-configured-retention' || fail 'derived retention lifecycle rule is missing'
printf '%s' "$derived_ilm" | grep -Eq "\"Days\"[[:space:]]*:[[:space:]]*$MINIO_DERIVED_RETENTION_DAYS" || \
  fail 'derived retention does not match MINIO_DERIVED_RETENTION_DAYS'

for identity in bank-api document-worker policy-worker report-worker audit-writer; do
  mc admin policy info "$MINIO_ALIAS" "$identity" >/dev/null || fail "policy is missing: $identity"
  user_info="$(mc admin user info "$MINIO_ALIAS" "$identity")"
  printf '%s' "$user_info" | grep -Fq "$identity" || fail "policy is not attached to service user: $identity"
done

smoke_id="$(date -u +%Y%m%d%H%M%S)-$$"
api_alias='bank-api-smoke'
mc alias set "$api_alias" "$MINIO_INTERNAL_ENDPOINT" bank-api "$MINIO_BANK_API_SECRET_KEY" >/dev/null
printf 'bank-ai-minio-smoke\n' | mc pipe "$api_alias/upload-quarantine/uploads/$smoke_id/incoming" >/dev/null
object_contents="$(mc cat "$api_alias/upload-quarantine/uploads/$smoke_id/incoming")"
[ "$object_contents" = 'bank-ai-minio-smoke' ] || fail 'bank-api could not read its smoke object'

if mc rm --force "$api_alias/upload-quarantine/uploads/$smoke_id/incoming" >/dev/null 2>&1; then
  fail 'bank-api unexpectedly deleted a quarantine object'
fi

log 'health, buckets, privacy, versioning, lifecycle, policy, and denied-delete smoke tests passed'

