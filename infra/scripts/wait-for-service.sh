#!/usr/bin/env sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Usage: $0 HOST PORT [TIMEOUT_SECONDS]" >&2
  exit 2
fi

host="$1"
port="$2"
timeout_seconds="${3:-120}"
started_at=$(date +%s)

while ! nc -z "$host" "$port" >/dev/null 2>&1; do
  now=$(date +%s)
  if [ $((now - started_at)) -ge "$timeout_seconds" ]; then
    echo "Timed out waiting for $host:$port" >&2
    exit 1
  fi
  sleep 2
done

echo "$host:$port is reachable"

