#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

KAFKA_DATA_DIR="${KAFKA_DATA_DIR:-/var/lib/kafka/data}"
KAFKA_SERVER_CONFIG="${KAFKA_SERVER_CONFIG:-$KAFKA_RUNTIME_DIR/server.properties}"

require_command "$KAFKA_BIN_DIR/kafka-storage.sh"
[[ -f "$KAFKA_SERVER_CONFIG" ]] || fail "rendered server config not found: $KAFKA_SERVER_CONFIG"

principals=(
  kafka-admin
  bank-api
  document-worker
  analysis-orchestrator
  credit-worker
  compliance-worker
  report-worker
  notification-gateway
  audit-consumer
)

mkdir -p "$KAFKA_DATA_DIR"
if [[ -f "$KAFKA_DATA_DIR/meta.properties" ]]; then
  log "KRaft storage is already formatted; leaving metadata unchanged"
  exit 0
fi

cluster_id="${KAFKA_CLUSTER_ID:-}"
if [[ -z "$cluster_id" ]]; then
  cluster_id="$($KAFKA_BIN_DIR/kafka-storage.sh random-uuid)"
fi
reject_multiline 'KRaft cluster ID' "$cluster_id"

format_args=(
  format
  --cluster-id "$cluster_id"
  --config "$KAFKA_SERVER_CONFIG"
)

for principal in "${principals[@]}"; do
  username="$(principal_username "$principal")"
  password="$(principal_password "$principal")"
  reject_multiline "Kafka username for $principal" "$username"
  reject_multiline "Kafka password for $principal" "$password"
  username="$(scram_escape "$username")"
  password="$(scram_escape "$password")"
  format_args+=(
    --add-scram
    "SCRAM-SHA-512=[name=\"$username\",password=\"$password\"]"
  )
done

log "formatting fresh KRaft storage with SCRAM credentials"
"$KAFKA_BIN_DIR/kafka-storage.sh" "${format_args[@]}"

