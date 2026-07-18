#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command "$KAFKA_BIN_DIR/kafka-configs.sh"
write_client_config kafka-admin "$KAFKA_ADMIN_CONFIG"
wait_for_kafka

# Update the administrator last so every preceding request continues to use the
# credential that authenticated this run. On a normal idempotent run the value
# is unchanged; credential rotation must restart the broker with the same env.
principals=(
  bank-api
  document-worker
  analysis-orchestrator
  credit-worker
  compliance-worker
  report-worker
  notification-gateway
  audit-consumer
  kafka-admin
)

for principal in "${principals[@]}"; do
  username="$(principal_username "$principal")"
  password="$(principal_password "$principal")"
  reject_multiline "Kafka username for $principal" "$username"
  reject_multiline "Kafka password for $principal" "$password"
  escaped_password="$(scram_escape "$password")"

  log "reconciling SCRAM-SHA-512 credential for $username"
  "$KAFKA_BIN_DIR/kafka-configs.sh" \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" \
    --alter \
    --entity-type users \
    --entity-name "$username" \
    --add-config "SCRAM-SHA-512=[iterations=8192,password=\"$escaped_password\"]" >/dev/null
done

log 'all Kafka SCRAM users are present'

