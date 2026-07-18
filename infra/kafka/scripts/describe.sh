#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

write_client_config kafka-admin "$KAFKA_ADMIN_CONFIG"
wait_for_kafka

"$KAFKA_BIN_DIR/kafka-topics.sh" \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --command-config "$KAFKA_ADMIN_CONFIG" \
  --describe

