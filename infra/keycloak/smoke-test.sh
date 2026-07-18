#!/bin/sh

set -eu

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
  for variable_name in "$@"; do
    eval "variable_value=\${$variable_name:-}"
    [ -n "$variable_value" ] || fail "required environment variable is empty: $variable_name"
  done
}

for command_name in curl base64 sed grep tr; do
  command -v "$command_name" >/dev/null 2>&1 || fail "required command is missing: $command_name"
done
require_env KEYCLOAK_ADMIN_PASSWORD KEYCLOAK_BACKEND_CLIENT_SECRET SEED_USER_PASSWORD

json_token() {
  sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
}

admin_response="$(curl --silent --show-error --fail \
  --request POST \
  "$KEYCLOAK_INTERNAL_URL/realms/master/protocol/openid-connect/token" \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=admin-cli' \
  --data-urlencode "username=$KEYCLOAK_ADMIN_USERNAME" \
  --data-urlencode "password=$KEYCLOAK_ADMIN_PASSWORD")"
admin_token="$(printf '%s' "$admin_response" | json_token)"
[ -n "$admin_token" ] || fail 'master admin token response did not contain an access token'

admin_get() {
  curl --silent --show-error --fail \
    --header "Authorization: Bearer $admin_token" \
    "$KEYCLOAK_INTERNAL_URL/admin/realms/$KEYCLOAK_REALM/$1"
}

discovery="$(curl --silent --show-error --fail \
  "$KEYCLOAK_INTERNAL_URL/realms/$KEYCLOAK_REALM/.well-known/openid-configuration")"
expected_issuer="$KEYCLOAK_PUBLIC_URL/realms/$KEYCLOAK_REALM"
compact_discovery="$(printf '%s' "$discovery" | tr -d '\r\n\t ')"
printf '%s' "$compact_discovery" | grep -Fq "\"issuer\":\"$expected_issuer\"" || \
  fail "OIDC discovery issuer does not match $expected_issuer"
printf '%s' "$compact_discovery" | grep -Fq "\"jwks_uri\":\"$expected_issuer/protocol/openid-connect/certs\"" || \
  fail 'OIDC discovery does not expose the required JWKS endpoint'

for client_id in bank-ai-frontend bank-ai-backend bank-ai-worker; do
  client_response="$(admin_get "clients?clientId=$client_id")"
  compact_client="$(printf '%s' "$client_response" | tr -d '\r\n\t ')"
  printf '%s' "$compact_client" | grep -Fq "\"clientId\":\"$client_id\"" || \
    fail "required client is missing: $client_id"
done

frontend="$(admin_get 'clients?clientId=bank-ai-frontend')"
compact_frontend="$(printf '%s' "$frontend" | tr -d '\r\n\t ')"
printf '%s' "$compact_frontend" | grep -Fq '"publicClient":true' || fail 'frontend client is not public'
printf '%s' "$compact_frontend" | grep -Fq '"directAccessGrantsEnabled":false' || \
  fail 'frontend direct grants are enabled'
printf '%s' "$compact_frontend" | grep -Fq '"pkce.code.challenge.method":"S256"' || \
  fail 'frontend PKCE S256 is not configured'

worker="$(admin_get 'clients?clientId=bank-ai-worker')"
compact_worker="$(printf '%s' "$worker" | tr -d '\r\n\t ')"
printf '%s' "$compact_worker" | grep -Fq '"serviceAccountsEnabled":true' || \
  fail 'worker service account is not enabled'

for role in credit_officer credit_manager document_reviewer compliance_officer risk_officer loan_approver auditor admin; do
  admin_get "roles/$role" >/dev/null || fail "required realm role is missing: $role"
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
access_token="$(printf '%s' "$token_response" | json_token)"
[ -n "$access_token" ] || fail 'demo-user token response did not contain an access token'

payload_segment="${access_token#*.}"
payload_segment="${payload_segment%%.*}"
case $((${#payload_segment} % 4)) in
  2) payload_segment="${payload_segment}==" ;;
  3) payload_segment="${payload_segment}=" ;;
esac
jwt_payload="$(printf '%s' "$payload_segment" | tr '_-' '/+' | base64 -d 2>/dev/null)" || \
  fail 'could not decode JWT payload'
compact_payload="$(printf '%s' "$jwt_payload" | tr -d '\r\n\t ')"

printf '%s' "$compact_payload" | grep -Fq "\"iss\":\"$expected_issuer\"" || \
  fail 'JWT issuer does not match the public realm URL'
printf '%s' "$compact_payload" | grep -Fq '"aud":"bank-ai-api"' || \
  printf '%s' "$compact_payload" | grep -Eq '"aud":\[[^]]*"bank-ai-api"' || \
  fail 'JWT audience does not contain bank-ai-api'
printf '%s' "$compact_payload" | grep -Fq '"sub":"10000000-0000-4000-8000-000000000001"' || \
  fail 'demo token subject does not match the PostgreSQL identity subject'
printf '%s' "$compact_payload" | grep -Fq 'credit_officer' || \
  fail 'demo token does not contain the credit_officer realm role'

unset admin_response admin_token token_response access_token jwt_payload payload_segment
log 'realm, discovery, clients, PKCE, roles, demo login, subject, issuer, and audience smoke tests passed'
