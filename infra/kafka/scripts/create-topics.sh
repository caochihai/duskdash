#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command "$KAFKA_BIN_DIR/kafka-topics.sh"
require_command "$KAFKA_BIN_DIR/kafka-configs.sh"
write_client_config kafka-admin "$KAFKA_ADMIN_CONFIG"
wait_for_kafka

manifest="${KAFKA_TOPICS_MANIFEST:-$BANK_KAFKA_ROOT/topics/topics.yaml}"
[[ -f "$manifest" ]] || fail "topic manifest not found: $manifest"
mapfile -t records < <(topic_records "$manifest")
[[ "${#records[@]}" -eq 12 ]] || fail "topic manifest must contain exactly 12 topics; found ${#records[@]}"

for record in "${records[@]}"; do
  IFS='|' read -r topic partitions replication retention cleanup maxbytes <<< "$record"
  [[ -n "$topic" && "$partitions" =~ ^[1-9][0-9]*$ && "$replication" =~ ^[1-9][0-9]*$ ]] || \
    fail "invalid topic manifest record: $record"
  [[ "$retention" =~ ^[1-9][0-9]*$ && "$maxbytes" =~ ^[1-9][0-9]*$ ]] || \
    fail "invalid topic retention/message size for $topic"
  [[ "$cleanup" == 'delete' || "$cleanup" == 'compact,delete' ]] || \
    fail "unsupported cleanup policy for $topic: $cleanup"

  if description="$($KAFKA_BIN_DIR/kafka-topics.sh \
      --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
      --command-config "$KAFKA_ADMIN_CONFIG" \
      --describe --topic "$topic" 2>/dev/null)"; then
    current_partitions="$(sed -n 's/.*PartitionCount: *\([0-9][0-9]*\).*/\1/p' <<< "$description" | head -n 1)"
    current_replication="$(sed -n 's/.*ReplicationFactor: *\([0-9][0-9]*\).*/\1/p' <<< "$description" | head -n 1)"
    [[ -n "$current_partitions" && -n "$current_replication" ]] || fail "could not parse topic metadata for $topic"
    if (( current_partitions < partitions )); then
      log "increasing $topic from $current_partitions to $partitions partitions"
      "$KAFKA_BIN_DIR/kafka-topics.sh" \
        --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
        --command-config "$KAFKA_ADMIN_CONFIG" \
        --alter --topic "$topic" --partitions "$partitions" >/dev/null
    elif (( current_partitions > partitions )); then
      fail "$topic has $current_partitions partitions, greater than the required $partitions; Kafka cannot shrink partitions safely"
    fi
    [[ "$current_replication" == "$replication" ]] || \
      fail "$topic has replication factor $current_replication; expected $replication"
  else
    log "creating topic $topic"
    "$KAFKA_BIN_DIR/kafka-topics.sh" \
      --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
      --command-config "$KAFKA_ADMIN_CONFIG" \
      --create \
      --topic "$topic" \
      --partitions "$partitions" \
      --replication-factor "$replication" \
      --config "retention.ms=$retention" \
      --config "cleanup.policy=$cleanup" \
      --config "max.message.bytes=$maxbytes" >/dev/null
  fi

  cleanup_config="$cleanup"
  if [[ "$cleanup" == *,* ]]; then
    cleanup_config="[$cleanup]"
  fi
  "$KAFKA_BIN_DIR/kafka-configs.sh" \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" \
    --alter \
    --entity-type topics \
    --entity-name "$topic" \
    --add-config "retention.ms=$retention,cleanup.policy=$cleanup_config,max.message.bytes=$maxbytes" >/dev/null

  description="$($KAFKA_BIN_DIR/kafka-topics.sh \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" \
    --describe --topic "$topic")"
  grep -q "PartitionCount: $partitions" <<< "$description" || fail "$topic partition verification failed"
  grep -q "ReplicationFactor: $replication" <<< "$description" || fail "$topic replication verification failed"

  config_description="$($KAFKA_BIN_DIR/kafka-configs.sh \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" \
    --describe --entity-type topics --entity-name "$topic")"
  grep -Fq "retention.ms=$retention" <<< "$config_description" || fail "$topic retention verification failed"
  grep -Fq "max.message.bytes=$maxbytes" <<< "$config_description" || fail "$topic message-size verification failed"
  grep -Fq "cleanup.policy=$cleanup" <<< "$config_description" || fail "$topic cleanup-policy verification failed"
done

log 'all Kafka topics and topic-level configs match the manifest'

