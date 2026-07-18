#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

printf '[kafka] reconciling SCRAM credentials\n'
bash "$SCRIPT_DIR/create-users.sh"
printf '[kafka] reconciling topics\n'
bash "$SCRIPT_DIR/create-topics.sh"
printf '[kafka] reconciling ACLs\n'
bash "$SCRIPT_DIR/create-acls.sh"
printf '[kafka] running Kafka smoke test\n'
bash "$SCRIPT_DIR/smoke-test.sh"
printf '[kafka] bootstrap completed successfully\n'

