#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INFRA_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$INFRA_ROOT/.env.local"

[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE" >&2; exit 1; }

compose() {
  docker compose \
    --env-file "$INFRA_ROOT/versions.env" \
    --env-file "$ENV_FILE" \
    -f "$INFRA_ROOT/docker-compose.infra.yml" \
    -f "$INFRA_ROOT/docker-compose.tools.yml" \
    -f "$INFRA_ROOT/docker-compose.observability.yml" \
    "$@"
}

pass() { printf '[PASS] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1" >&2; exit 1; }

compose --profile tools --profile observability config --quiet || fail 'Docker Compose config'
if compose --profile tools --profile observability config --images | grep -Eq '(^|:)latest($|@)'; then
  fail 'An image uses latest'
fi
pass 'Compose config and image pins'

if grep -Rin --exclude=intructions.md --exclude=.env.local --include='*.yml' --include='*.yaml' \
    --include='*.json' --include='*.conf' --include='*.properties' --include='*.sql' \
    --include='*.sh' --include='*.ps1' 'changeme' "$INFRA_ROOT" >/dev/null 2>&1; then
  fail 'changeme placeholder found in source config'
fi
pass 'No changeme placeholder'

docker info >/dev/null 2>&1 || fail 'Docker engine is unavailable'
compose up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak || fail 'Core service health'
pass 'Core services healthy'

compose run --rm flyway || fail 'Flyway migration'
[ "$(compose exec -T postgres psql -X -U postgres -d bank_ai -Atqc \
  "SELECT count(*) FROM public.flyway_schema_history WHERE success")" = 17 ] || fail 'Migration count'
pass '17 Flyway migrations complete'

compose run --rm db-seed || fail 'First seed run'
compose run --rm db-seed || fail 'Second seed run'
pass 'Seed is repeatable'

unauth=$(compose exec -T redis redis-cli PING 2>&1 || true)
printf '%s' "$unauth" | grep -q NOAUTH || fail 'Redis accepted unauthenticated access'
[ "$(compose exec -T redis sh -ec 'redis-cli --no-auth-warning -a "$REDIS_PASSWORD" PING')" = PONG ] || fail 'Redis authenticated PING'
pass 'Redis authentication'

compose run --rm kafka-init || fail 'Kafka smoke test'
pass 'Kafka topics, ACL, produce and consume'
compose run --rm minio-init || fail 'MinIO smoke test'
pass 'MinIO buckets, privacy, lifecycle and policies'
compose run --rm keycloak-init || fail 'Keycloak bootstrap'
compose run --rm keycloak-smoke || fail 'Keycloak smoke test'
pass 'Keycloak OIDC and demo token'

compose --profile tools up -d pgadmin kafka-ui || fail 'Tools profile'
compose --profile observability up -d prometheus grafana || fail 'Observability profile'
pass 'Optional profiles started'

echo 'All stack checks passed.'
