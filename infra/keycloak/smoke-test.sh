#!/usr/bin/env bash

set -Eeuo pipefail

KCADM_BIN="${KCADM_BIN:-/opt/keycloak/bin/kcadm.sh}"
KEYCLOAK_INTERNAL_URL="${KEYCLOAK_INTERNAL_URL:-http://keycloak:8080}"
KEYCLOAK_PUBLIC_URL="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
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

for command_name in curl base64 sed grep; do
  command -v "$command_name" >/dev/null 2>&1 || fail "required command is missing: $command_name"
done
[[ -x "$KCADM_BIN" ]] || fail "kcadm executable not found: $KCADM_BIN"
require_env KEYCLOAK_ADMIN_PASSWORD KEYCLOAK_BACKEND_CLIENT_SECRET SEED_USER_PASSWORD

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

discovery="$(curl --silent --show-error --fail \
  "$KEYCLOAK_INTERNAL_URL/realms/$KEYCLOAK_REALM/.well-known/openid-configuration")"
expected_issuer="$KEYCLOAK_PUBLIC_URL/realms/$KEYCLOAK_REALM"
printf '%s' "$discovery" | grep -Fq "\"issuer\":\"$expected_issuer\"" || \
  fail "OIDC discovery issuer does not match $expected_issuer"
printf '%s' "$discovery" | grep -Fq "$expected_issuer/protocol/openid-connect/certs" || \
  fail 'OIDC discovery does not expose the required JWKS endpoint'

for client_id in bank-ai-frontend bank-ai-backend bank-ai-worker; do
  response="$(kcadm get clients -r "$KEYCLOAK_REALM" -q "clientId=$client_id" --fields id,clientId,publicClient,serviceAccountsEnabled,protocolMappers)"
  printf '%s' "$response" | grep -Fq "\"clientId\" : \"$client_id\"" || fail "required client is missing: $client_id"
done

frontend="$(kcadm get clients -r "$KEYCLOAK_REALM" -q clientId=bank-ai-frontend --fields publicClient,directAccessGrantsEnabled,attributes)"
printf '%s' "$frontend" | grep -Eq '"publicClient"[[:space:]]*:[[:space:]]*true' || fail 'frontend client is not public'
printf '%s' "$frontend" | grep -Eq '"directAccessGrantsEnabled"[[:space:]]*:[[:space:]]*false' || fail 'frontend direct grants are enabled'
printf '%s' "$frontend" | grep -Fq 'S256' || fail 'frontend PKCE S256 is not configured'

for role in credit_officer credit_manager document_reviewer compliance_officer risk_officer loan_approver auditor admin; do
  kcadm get "roles/$role" -r "$KEYCLOAK_REALM" >/dev/null || fail "required realm role is missing: $role"
done

token_response="$(curl --silent --show-error --fail \
  --request POST \
  "$KEYCLOAK_INTERNAL_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=bank-ai-backend' \
  --data-urlencode "client_secret=$KEYCLOAK_BACKEND_CLIENT_SECRET" \
  --data-urlencode 'username=credit.officer@example.local' \
  --data-urlencode "password=$SEED_USER_PASSWORD")"
access_token="$(printf '%s' "$token_response" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
[[ -n "$access_token" ]] || fail 'demo-user token response did not contain an access token'

payload_segment="${access_token#*.}"
payload_segment="${payload_segment%%.*}"
case $((${#payload_segment} % 4)) in
  2) payload_segment="${payload_segment}==" ;;
  3) payload_segment="${payload_segment}=" ;;
esac
jwt_payload="$(printf '%s' "$payload_segment" | tr '_-' '/+' | base64 -d 2>/dev/null)" || fail 'could not decode JWT payload'

printf '%s' "$jwt_payload" | grep -Fq '"aud":"bank-ai-api"' || \
  printf '%s' "$jwt_payload" | grep -Eq '"aud":\[[^]]*"bank-ai-api"' || \
  fail 'JWT audience does not contain bank-ai-api'
printf '%s' "$jwt_payload" | grep -Fq '"sub":"10000000-0000-4000-8000-000000000001"' || \
  fail 'demo token subject does not match the PostgreSQL identity subject'
printf '%s' "$jwt_payload" | grep -Fq 'credit_officer' || fail 'demo token does not contain the credit_officer realm role'

unset access_token token_response jwt_payload payload_segment
log 'realm, discovery, clients, PKCE, roles, demo login, subject, and audience smoke tests passed'

