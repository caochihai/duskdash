#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BANK_KAFKA_ROOT="${BANK_KAFKA_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
KAFKA_BIN_DIR="${KAFKA_BIN_DIR:-/opt/kafka/bin}"
KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
KAFKA_RUNTIME_DIR="${KAFKA_RUNTIME_DIR:-/tmp/bank-kafka}"
KAFKA_ADMIN_CONFIG="${KAFKA_ADMIN_CONFIG:-$KAFKA_RUNTIME_DIR/admin.properties}"

log() {
  printf '[kafka] %s\n' "$*"
}

fail() {
  printf '[kafka] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local command_path="$1"
  [[ -x "$command_path" ]] || fail "required executable not found: $command_path"
}

require_env() {
  local variable_name
  for variable_name in "$@"; do
    [[ -n "${!variable_name:-}" ]] || fail "required environment variable is empty: $variable_name"
  done
}

reject_multiline() {
  local label="$1"
  local value="$2"
  [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || fail "$label must not contain a newline"
}

jaas_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "$value"
}

scram_escape() {
  jaas_escape "$1"
}

principal_username() {
  case "$1" in
    kafka-admin) printf '%s' "${KAFKA_ADMIN_USERNAME:-kafka-admin}" ;;
    bank-api) printf '%s' "${KAFKA_BANK_API_USERNAME:-bank-api}" ;;
    document-worker) printf '%s' "${KAFKA_DOCUMENT_WORKER_USERNAME:-document-worker}" ;;
    analysis-orchestrator) printf '%s' "${KAFKA_ANALYSIS_ORCHESTRATOR_USERNAME:-analysis-orchestrator}" ;;
    credit-worker) printf '%s' "${KAFKA_CREDIT_WORKER_USERNAME:-credit-worker}" ;;
    compliance-worker) printf '%s' "${KAFKA_COMPLIANCE_WORKER_USERNAME:-compliance-worker}" ;;
    report-worker) printf '%s' "${KAFKA_REPORT_WORKER_USERNAME:-report-worker}" ;;
    notification-gateway) printf '%s' "${KAFKA_NOTIFICATION_GATEWAY_USERNAME:-notification-gateway}" ;;
    audit-consumer) printf '%s' "${KAFKA_AUDIT_CONSUMER_USERNAME:-audit-consumer}" ;;
    *) fail "unknown Kafka principal: $1" ;;
  esac
}

principal_password_var() {
  case "$1" in
    kafka-admin) printf '%s' 'KAFKA_ADMIN_PASSWORD' ;;
    bank-api) printf '%s' 'KAFKA_BANK_API_PASSWORD' ;;
    document-worker) printf '%s' 'KAFKA_DOCUMENT_WORKER_PASSWORD' ;;
    analysis-orchestrator) printf '%s' 'KAFKA_ANALYSIS_ORCHESTRATOR_PASSWORD' ;;
    credit-worker) printf '%s' 'KAFKA_CREDIT_WORKER_PASSWORD' ;;
    compliance-worker) printf '%s' 'KAFKA_COMPLIANCE_WORKER_PASSWORD' ;;
    report-worker) printf '%s' 'KAFKA_REPORT_WORKER_PASSWORD' ;;
    notification-gateway) printf '%s' 'KAFKA_NOTIFICATION_GATEWAY_PASSWORD' ;;
    audit-consumer) printf '%s' 'KAFKA_AUDIT_CONSUMER_PASSWORD' ;;
    *) fail "unknown Kafka principal: $1" ;;
  esac
}

principal_password() {
  local variable_name
  variable_name="$(principal_password_var "$1")"
  require_env "$variable_name"
  printf '%s' "${!variable_name}"
}

write_client_config() {
  local principal="$1"
  local output_path="$2"
  local username password escaped_username escaped_password

  username="$(principal_username "$principal")"
  password="$(principal_password "$principal")"
  reject_multiline "Kafka username" "$username"
  reject_multiline "Kafka password" "$password"
  escaped_username="$(jaas_escape "$username")"
  escaped_password="$(jaas_escape "$password")"

  umask 077
  mkdir -p "$(dirname "$output_path")"
  cp "$BANK_KAFKA_ROOT/config/tools-client.properties" "$output_path"
  printf 'sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="%s" password="%s";\n' \
    "$escaped_username" "$escaped_password" >> "$output_path"
  chmod 600 "$output_path"
}

wait_for_kafka() {
  local attempts="${KAFKA_WAIT_ATTEMPTS:-60}"
  local delay_seconds="${KAFKA_WAIT_DELAY_SECONDS:-2}"
  local attempt

  require_command "$KAFKA_BIN_DIR/kafka-broker-api-versions.sh"
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if "$KAFKA_BIN_DIR/kafka-broker-api-versions.sh" \
      --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
      --command-config "$KAFKA_ADMIN_CONFIG" >/dev/null 2>&1; then
      log "broker metadata is reachable"
      return 0
    fi
    sleep "$delay_seconds"
  done
  fail "broker did not become ready after $((attempts * delay_seconds)) seconds"
}

topic_records() {
  local manifest="${1:-$BANK_KAFKA_ROOT/topics/topics.yaml}"
  awk '
    function emit() {
      if (name != "") {
        print name "|" partitions "|" replication "|" retention "|" cleanup "|" maxbytes
      }
    }
    /^  - name:[[:space:]]*/ {
      emit()
      name=$0
      sub(/^  - name:[[:space:]]*/, "", name)
      partitions=replication=retention=cleanup=maxbytes=""
      next
    }
    name != "" && /^    partitions:[[:space:]]*/ {
      partitions=$0; sub(/^    partitions:[[:space:]]*/, "", partitions); next
    }
    name != "" && /^    replication_factor:[[:space:]]*/ {
      replication=$0; sub(/^    replication_factor:[[:space:]]*/, "", replication); next
    }
    name != "" && /^    retention_ms:[[:space:]]*/ {
      retention=$0; sub(/^    retention_ms:[[:space:]]*/, "", retention); next
    }
    name != "" && /^    cleanup_policy:[[:space:]]*/ {
      cleanup=$0; sub(/^    cleanup_policy:[[:space:]]*/, "", cleanup); next
    }
    name != "" && /^    max_message_bytes:[[:space:]]*/ {
      maxbytes=$0; sub(/^    max_message_bytes:[[:space:]]*/, "", maxbytes); next
    }
    END { emit() }
  ' "$manifest"
}

