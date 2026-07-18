#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command "$KAFKA_BIN_DIR/kafka-acls.sh"
write_client_config kafka-admin "$KAFKA_ADMIN_CONFIG"
wait_for_kafka

grant_produce() {
  local principal="$1"
  shift
  local username topic
  username="$(principal_username "$principal")"
  for topic in "$@"; do
    "$KAFKA_BIN_DIR/kafka-acls.sh" \
      --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
      --command-config "$KAFKA_ADMIN_CONFIG" \
      --add \
      --allow-principal "User:$username" \
      --operation WRITE \
      --operation DESCRIBE \
      --topic "$topic" >/dev/null
  done
}

grant_consume() {
  local principal="$1"
  local group="$2"
  shift 2
  local username topic
  username="$(principal_username "$principal")"
  for topic in "$@"; do
    "$KAFKA_BIN_DIR/kafka-acls.sh" \
      --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
      --command-config "$KAFKA_ADMIN_CONFIG" \
      --add \
      --allow-principal "User:$username" \
      --operation READ \
      --operation DESCRIBE \
      --topic "$topic" >/dev/null
  done
  "$KAFKA_BIN_DIR/kafka-acls.sh" \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" \
    --add \
    --allow-principal "User:$username" \
    --operation READ \
    --group "$group" >/dev/null
}

grant_produce bank-api \
  bank.document.commands.v1 \
  bank.analysis.commands.v1 \
  bank.report.commands.v1

grant_consume document-worker document-worker-group \
  bank.document.commands.v1
grant_produce document-worker \
  bank.document.events.v1 \
  bank.notification.events.v1 \
  bank.job-status.v1 \
  bank.retry.1m.v1 \
  bank.retry.10m.v1 \
  bank.dead-letter.v1

grant_consume analysis-orchestrator analysis-orchestrator-group \
  bank.analysis.commands.v1 \
  bank.document.events.v1
grant_produce analysis-orchestrator \
  bank.analysis.commands.v1 \
  bank.analysis.events.v1 \
  bank.notification.events.v1

grant_consume credit-worker credit-worker-group bank.analysis.commands.v1
grant_produce credit-worker \
  bank.analysis.events.v1 \
  bank.notification.events.v1 \
  bank.dead-letter.v1

grant_consume compliance-worker compliance-worker-group bank.analysis.commands.v1
grant_produce compliance-worker \
  bank.analysis.events.v1 \
  bank.notification.events.v1 \
  bank.dead-letter.v1

grant_consume report-worker report-worker-group \
  bank.report.commands.v1 \
  bank.analysis.events.v1
grant_produce report-worker \
  bank.report.events.v1 \
  bank.notification.events.v1

grant_consume notification-gateway notification-gateway-group \
  bank.notification.events.v1 \
  bank.job-status.v1

grant_consume audit-consumer audit-consumer-group \
  bank.audit.events.v1 \
  bank.document.events.v1 \
  bank.analysis.events.v1 \
  bank.report.events.v1

log 'Kafka ACLs were reconciled with the least-privilege manifest'

