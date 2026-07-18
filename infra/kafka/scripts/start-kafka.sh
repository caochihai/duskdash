#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

KAFKA_DATA_DIR="${KAFKA_DATA_DIR:-/var/lib/kafka/data}"
KAFKA_NODE_ID="${KAFKA_NODE_ID:-1}"
KAFKA_EXTERNAL_HOST="${KAFKA_EXTERNAL_HOST:-localhost}"
KAFKA_SERVER_CONFIG="$KAFKA_RUNTIME_DIR/server.properties"
admin_username="$(principal_username kafka-admin)"
admin_password="$(principal_password kafka-admin)"

require_command "$KAFKA_BIN_DIR/kafka-server-start.sh"
[[ "$KAFKA_NODE_ID" =~ ^[1-9][0-9]*$ ]] || fail 'KAFKA_NODE_ID must be a positive integer'
[[ "$KAFKA_EXTERNAL_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || fail 'KAFKA_EXTERNAL_HOST contains unsupported characters'
[[ "$admin_username" =~ ^[A-Za-z0-9._-]+$ ]] || fail 'KAFKA_ADMIN_USERNAME contains unsupported characters'
reject_multiline 'KAFKA_ADMIN_PASSWORD' "$admin_password"

mkdir -p "$KAFKA_RUNTIME_DIR" "$KAFKA_DATA_DIR"
umask 077

sed_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//&/\\&}"
  value="${value//|/\\|}"
  printf '%s' "$value"
}

sed \
  -e "s|__KAFKA_NODE_ID__|$(sed_escape "$KAFKA_NODE_ID")|g" \
  -e "s|__KAFKA_EXTERNAL_HOST__|$(sed_escape "$KAFKA_EXTERNAL_HOST")|g" \
  -e "s|__KAFKA_ADMIN_USERNAME__|$(sed_escape "$admin_username")|g" \
  -e "s|__KAFKA_DATA_DIR__|$(sed_escape "$KAFKA_DATA_DIR")|g" \
  "$BANK_KAFKA_ROOT/config/server.properties" > "$KAFKA_SERVER_CONFIG"

escaped_username="$(jaas_escape "$admin_username")"
escaped_password="$(jaas_escape "$admin_password")"
printf 'listener.name.internal.scram-sha-512.sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="%s" password="%s";\n' \
  "$escaped_username" "$escaped_password" >> "$KAFKA_SERVER_CONFIG"
printf 'listener.name.external.scram-sha-512.sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="%s" password="%s";\n' \
  "$escaped_username" "$escaped_password" >> "$KAFKA_SERVER_CONFIG"
chmod 600 "$KAFKA_SERVER_CONFIG"

write_client_config kafka-admin "$KAFKA_ADMIN_CONFIG"

export KAFKA_DATA_DIR KAFKA_SERVER_CONFIG
bash "$SCRIPT_DIR/format-storage.sh"

log 'starting Kafka KRaft broker/controller'
exec "$KAFKA_BIN_DIR/kafka-server-start.sh" "$KAFKA_SERVER_CONFIG"
