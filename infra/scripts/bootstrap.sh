#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INFRA_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$INFRA_ROOT/.env.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Run scripts/generate-secrets.sh first." >&2
  exit 1
fi

compose() {
  docker compose \
    --env-file "$INFRA_ROOT/versions.env" \
    --env-file "$ENV_FILE" \
    -f "$INFRA_ROOT/docker-compose.infra.yml" \
    -f "$INFRA_ROOT/docker-compose.tools.yml" \
    -f "$INFRA_ROOT/docker-compose.observability.yml" \
    "$@"
}

docker info >/dev/null
compose up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak
compose run --rm flyway
compose run --rm db-seed
compose run --rm kafka-init
compose run --rm minio-init
compose run --rm keycloak-init
compose run --rm keycloak-smoke

if [ "${1:-}" != "--skip-verify" ]; then
  "$SCRIPT_DIR/verify-stack.sh"
fi

echo 'Infrastructure bootstrap completed.'
