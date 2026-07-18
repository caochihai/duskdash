#!/usr/bin/env bash

set -Eeuo pipefail

KCADM_BIN="${KCADM_BIN:-/opt/keycloak/bin/kcadm.sh}"
KEYCLOAK_INTERNAL_URL="${KEYCLOAK_INTERNAL_URL:-http://keycloak:8080}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-bank-ai}"
KEYCLOAK_ADMIN_USERNAME="${KEYCLOAK_ADMIN_USERNAME:-${KEYCLOAK_ADMIN:-admin}}"

log() {
  printf '[keycloak] %s\n' "$*"
}

fail() {
  printf '[keycloak] ERROR: %s\n' "$*" >&2
  exit 1
}

require_env() {
  local variable_name
  for variable_name in "$@"; do
    [[ -n "${!variable_name:-}" ]] || fail "required environment variable is empty: $variable_name"
  done
}

[[ -x "$KCADM_BIN" ]] || fail "kcadm executable not found: $KCADM_BIN"
[[ "$KEYCLOAK_REALM" == 'bank-ai' ]] || fail 'KEYCLOAK_REALM must remain bank-ai'
require_env \
  KEYCLOAK_ADMIN_PASSWORD \
  KEYCLOAK_BACKEND_CLIENT_SECRET \
  KEYCLOAK_WORKER_CLIENT_SECRET \
  SEED_USER_PASSWORD

# --no-config avoids persisting admin access/refresh tokens or secrets in the
# container filesystem. Each command authenticates against the master realm.
kcadm() {
  local operation="$1"
  shift
  "$KCADM_BIN" "$operation" "$@" \
    --no-config \
    --server "$KEYCLOAK_INTERNAL_URL" \
    --realm master \
    --user "$KEYCLOAK_ADMIN_USERNAME" \
    --password "$KEYCLOAK_ADMIN_PASSWORD"
}

attempt=1
until kcadm get "realms/$KEYCLOAK_REALM" >/dev/null 2>&1; do
  if (( attempt >= 60 )); then
    fail "realm $KEYCLOAK_REALM was not available after 120 seconds"
  fi
  attempt=$((attempt + 1))
  sleep 2
done
log "realm $KEYCLOAK_REALM is available"

extract_first_id() {
  sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

client_internal_id() {
  local client_id="$1"
  local response internal_id
  response="$(kcadm get clients -r "$KEYCLOAK_REALM" -q "clientId=$client_id" --fields id,clientId)"
  internal_id="$(printf '%s\n' "$response" | extract_first_id)"
  [[ -n "$internal_id" ]] || fail "required client is missing: $client_id"
  printf '%s' "$internal_id"
}

frontend_id="$(client_internal_id bank-ai-frontend)"
backend_id="$(client_internal_id bank-ai-backend)"
worker_id="$(client_internal_id bank-ai-worker)"

kcadm update "clients/$frontend_id" -r "$KEYCLOAK_REALM" \
  -s enabled=true \
  -s publicClient=true \
  -s standardFlowEnabled=true \
  -s directAccessGrantsEnabled=false \
  -s serviceAccountsEnabled=false >/dev/null

kcadm update "clients/$backend_id" -r "$KEYCLOAK_REALM" \
  -s enabled=true \
  -s publicClient=false \
  -s serviceAccountsEnabled=true \
  -s directAccessGrantsEnabled=true \
  -s "secret=$KEYCLOAK_BACKEND_CLIENT_SECRET" >/dev/null

kcadm update "clients/$worker_id" -r "$KEYCLOAK_REALM" \
  -s enabled=true \
  -s publicClient=false \
  -s serviceAccountsEnabled=true \
  -s directAccessGrantsEnabled=false \
  -s "secret=$KEYCLOAK_WORKER_CLIENT_SECRET" >/dev/null

roles=(
  credit_officer
  credit_manager
  document_reviewer
  compliance_officer
  risk_officer
  loan_approver
  auditor
  admin
)
for role in "${roles[@]}"; do
  kcadm get "roles/$role" -r "$KEYCLOAK_REALM" >/dev/null || fail "required realm role is missing: $role"
done

user_specs=(
  '10000000-0000-4000-8000-000000000001|credit.officer@example.local|credit_officer|Credit|Officer'
  '10000000-0000-4000-8000-000000000002|credit.manager@example.local|credit_manager|Credit|Manager'
  '10000000-0000-4000-8000-000000000003|document.reviewer@example.local|document_reviewer|Document|Reviewer'
  '10000000-0000-4000-8000-000000000004|compliance@example.local|compliance_officer|Compliance|Officer'
  '10000000-0000-4000-8000-000000000005|approver@example.local|loan_approver|Loan|Approver'
  '10000000-0000-4000-8000-000000000006|auditor@example.local|auditor|Audit|Officer'
  '10000000-0000-4000-8000-000000000007|admin@example.local|admin|System|Administrator'
)

for specification in "${user_specs[@]}"; do
  IFS='|' read -r expected_id username role first_name last_name <<< "$specification"
  response="$(kcadm get users -r "$KEYCLOAK_REALM" -q "username=$username" -q exact=true --fields id,username)"
  user_id="$(printf '%s\n' "$response" | extract_first_id)"

  if [[ -z "$user_id" ]]; then
    log "creating demo identity $username"
    kcadm create users -r "$KEYCLOAK_REALM" \
      -s "id=$expected_id" \
      -s "username=$username" \
      -s "email=$username" \
      -s enabled=true \
      -s emailVerified=true >/dev/null
    response="$(kcadm get users -r "$KEYCLOAK_REALM" -q "username=$username" -q exact=true --fields id,username)"
    user_id="$(printf '%s\n' "$response" | extract_first_id)"
  fi

  [[ "$user_id" == "$expected_id" ]] || \
    fail "identity subject mismatch for $username: expected $expected_id, got ${user_id:-missing}"

  kcadm update "users/$user_id" -r "$KEYCLOAK_REALM" \
    -s "username=$username" \
    -s "email=$username" \
    -s "firstName=$first_name" \
    -s "lastName=$last_name" \
    -s enabled=true \
    -s emailVerified=true \
    -s 'requiredActions=[]' >/dev/null
  kcadm set-password -r "$KEYCLOAK_REALM" \
    --userid "$user_id" \
    --new-password "$SEED_USER_PASSWORD" >/dev/null
  kcadm add-roles -r "$KEYCLOAK_REALM" \
    --uid "$user_id" \
    --rolename "$role" >/dev/null
done

log 'client secrets and seven demo identities were reconciled without storing passwords in realm JSON'
