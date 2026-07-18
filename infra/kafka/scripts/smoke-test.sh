#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

for tool in \
  kafka-topics.sh \
  kafka-configs.sh \
  kafka-acls.sh \
  kafka-console-producer.sh \
  kafka-console-consumer.sh \
  kafka-consumer-groups.sh; do
  require_command "$KAFKA_BIN_DIR/$tool"
done

write_client_config kafka-admin "$KAFKA_ADMIN_CONFIG"
wait_for_kafka

mapfile -t records < <(topic_records "$BANK_KAFKA_ROOT/topics/topics.yaml")
[[ "${#records[@]}" -eq 12 ]] || fail 'topic manifest does not contain the required 12 topics'
topic_list="$($KAFKA_BIN_DIR/kafka-topics.sh \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --command-config "$KAFKA_ADMIN_CONFIG" --list)"

for record in "${records[@]}"; do
  IFS='|' read -r topic partitions replication retention cleanup maxbytes <<< "$record"
  grep -Fxq "$topic" <<< "$topic_list" || fail "required topic is missing: $topic"
  description="$($KAFKA_BIN_DIR/kafka-topics.sh \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" --describe --topic "$topic")"
  grep -q "PartitionCount: $partitions" <<< "$description" || fail "$topic has an unexpected partition count"
  grep -q "ReplicationFactor: $replication" <<< "$description" || fail "$topic has an unexpected replication factor"
  configs="$($KAFKA_BIN_DIR/kafka-configs.sh \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$KAFKA_ADMIN_CONFIG" \
    --describe --entity-type topics --entity-name "$topic")"
  grep -Fq "retention.ms=$retention" <<< "$configs" || fail "$topic has an unexpected retention"
  grep -Fq "cleanup.policy=$cleanup" <<< "$configs" || fail "$topic has an unexpected cleanup policy"
  grep -Fq "max.message.bytes=$maxbytes" <<< "$configs" || fail "$topic has an unexpected message-size limit"
done

acl_listing="$($KAFKA_BIN_DIR/kafka-acls.sh \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --command-config "$KAFKA_ADMIN_CONFIG" --list)"
for principal in bank-api document-worker analysis-orchestrator credit-worker compliance-worker report-worker notification-gateway audit-consumer; do
  username="$(principal_username "$principal")"
  grep -Fq "User:$username" <<< "$acl_listing" || fail "no ACL was found for $username"
done

bank_api_config="$KAFKA_RUNTIME_DIR/bank-api.properties"
document_worker_config="$KAFKA_RUNTIME_DIR/document-worker.properties"
write_client_config bank-api "$bank_api_config"
write_client_config document-worker "$document_worker_config"

event_id="$(< /proc/sys/kernel/random/uuid)"
correlation_id="$(< /proc/sys/kernel/random/uuid)"
partition_key="$(< /proc/sys/kernel/random/uuid)"
occurred_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
event_json="{\"event_id\":\"$event_id\",\"event_type\":\"document.processing.requested\",\"event_version\":1,\"occurred_at\":\"$occurred_at\",\"producer\":\"bank-api\",\"correlation_id\":\"$correlation_id\",\"causation_id\":null,\"partition_key\":\"$partition_key\",\"actor\":{\"type\":\"SERVICE\",\"id\":\"00000000-0000-4000-8000-000000000001\"},\"resource\":{\"type\":\"DOCUMENT_VERSION\",\"id\":\"$partition_key\"},\"payload\":{},\"metadata\":{\"trace_id\":\"$correlation_id\",\"schema\":\"document.processing.requested.v1\"}}"

# Keep the fixed worker group at the end of the test topic before starting the
# smoke consumer. Failure is expected when the group has never existed.
"$KAFKA_BIN_DIR/kafka-consumer-groups.sh" \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --command-config "$KAFKA_ADMIN_CONFIG" \
  --group document-worker-group \
  --topic bank.document.commands.v1 \
  --reset-offsets --to-latest --execute >/dev/null 2>&1 || true

consumer_output="$KAFKA_RUNTIME_DIR/smoke-consumer.out"
consumer_error="$KAFKA_RUNTIME_DIR/smoke-consumer.err"
rm -f "$consumer_output" "$consumer_error"
"$KAFKA_BIN_DIR/kafka-console-consumer.sh" \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --consumer.config "$document_worker_config" \
  --topic bank.document.commands.v1 \
  --group document-worker-group \
  --consumer-property auto.offset.reset=latest \
  --timeout-ms 15000 \
  --property print.key=true \
  --property 'key.separator=|' >"$consumer_output" 2>"$consumer_error" &
consumer_pid=$!
sleep 2

printf '%s|%s\n' "$partition_key" "$event_json" | \
  "$KAFKA_BIN_DIR/kafka-console-producer.sh" \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --producer.config "$bank_api_config" \
    --topic bank.document.commands.v1 \
    --property parse.key=true \
    --property 'key.separator=|' \
    --producer-property acks=all >/dev/null

wait "$consumer_pid" || true
grep -Fq "$event_id" "$consumer_output" || fail "authorized produce/consume smoke event was not observed"

denied_output="$KAFKA_RUNTIME_DIR/denied-consumer.out"
denied_error="$KAFKA_RUNTIME_DIR/denied-consumer.err"
rm -f "$denied_output" "$denied_error"
set +e
"$KAFKA_BIN_DIR/kafka-console-consumer.sh" \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --consumer.config "$bank_api_config" \
  --topic bank.document.events.v1 \
  --group document-worker-group \
  --timeout-ms 5000 >"$denied_output" 2>"$denied_error"
denied_status=$?
set -e
if (( denied_status == 0 )) && ! grep -Eqi '(authorization|not authorized|denied)' "$denied_error"; then
  fail 'bank-api unexpectedly consumed a worker event topic'
fi
grep -Eqi '(authorization|not authorized|denied)' "$denied_error" || \
  fail 'unauthorized consume failed for an unexpected reason'

log 'topic, retention, ACL denial, and produce/consume smoke tests passed'

