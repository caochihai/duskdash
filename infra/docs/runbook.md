# Local infrastructure runbook

Run commands from `D:\dushdask\infra` on Windows or the corresponding
`infra/` directory in WSL/Linux. `.env.local` contains secrets and must remain
untracked. Never paste its contents, tokens or presigned URLs into incident logs.

## Prerequisites and command forms

Windows uses Docker Desktop with the WSL2 engine and PowerShell 7 or Windows
PowerShell 5.1. WSL2/Linux uses Docker Engine with the Compose v2 plugin, Bash,
GNU Make, `curl` and standard Unix tools.

PowerShell actions:

```powershell
Set-Location D:\dushdask\infra
.\scripts\stack.ps1 secrets
.\scripts\stack.ps1 bootstrap
```

WSL2/Linux actions:

```bash
cd /path/to/dushdask/infra
make secrets
make bootstrap
```

`bootstrap` starts core services, migrates, seeds, initializes Kafka/MinIO/
Keycloak and runs verification. The operations are designed to be idempotent.

## Start

Generate secrets once:

```powershell
.\scripts\generate-secrets.ps1
```

```bash
./scripts/generate-secrets.sh
```

Then use the complete bootstrap above, or run stages:

```text
infra-up → db-migrate → db-seed → kafka-init → minio-init → keycloak-init → verify
```

PowerShell example:

```powershell
.\scripts\stack.ps1 infra-up
.\scripts\stack.ps1 db-migrate
.\scripts\stack.ps1 db-seed
.\scripts\stack.ps1 kafka-init
.\scripts\stack.ps1 minio-init
.\scripts\stack.ps1 keycloak-init
.\scripts\stack.ps1 verify
```

Start optional profiles only after the core stack is healthy:

```powershell
.\scripts\stack.ps1 tools-up
.\scripts\stack.ps1 observability-up
```

```bash
make tools-up
make observability-up
```

Inspect state/logs with `stack.ps1 infra-ps`, `make infra-ps`,
`stack.ps1 infra-logs`, or `make infra-logs`.

## Stop

`infra-down` stops/removes containers but preserves named volumes:

```powershell
.\scripts\stack.ps1 infra-down
```

```bash
make infra-down
```

For one service, use the common Compose file set and `stop <service>`; do not
remove a data volume during ordinary stop/restart.

## Reset local data

Reset permanently removes all local PostgreSQL, Kafka, Redis, MinIO, Keycloak,
PgAdmin, Prometheus and Grafana named-volume data. Back up anything needed first.
The normal command requires typing the exact confirmation `RESET`:

```powershell
.\scripts\stack.ps1 infra-reset
```

```bash
make infra-reset
```

PowerShell `-Force` bypasses the prompt and is suitable only for an already
approved disposable environment. After reset, rerun `bootstrap`. Never remove a
volume by a broad wildcard or outside this Compose project.

## PostgreSQL backup

Back up both databases while the service is healthy. The example writes custom
format dumps inside the container and copies them out without printing secrets:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = 'D:\bank-ai-secure-backups' # protected location outside the repository
$backupDir = Join-Path $backupRoot $stamp
New-Item -ItemType Directory -Force $backupDir | Out-Null
docker compose --env-file versions.env --env-file .env.local -f docker-compose.infra.yml exec -T postgres pg_dump -U postgres -d bank_ai -Fc -f /tmp/bank_ai.dump
docker compose --env-file versions.env --env-file .env.local -f docker-compose.infra.yml exec -T postgres pg_dump -U postgres -d keycloak -Fc -f /tmp/keycloak.dump
docker compose --env-file versions.env --env-file .env.local -f docker-compose.infra.yml cp postgres:/tmp/bank_ai.dump "$backupDir\bank_ai.dump"
docker compose --env-file versions.env --env-file .env.local -f docker-compose.infra.yml cp postgres:/tmp/keycloak.dump "$backupDir\keycloak.dump"
```

Equivalent Bash commands can use a protected timestamped directory outside the
repository and the same
`docker compose exec ... pg_dump` / `docker compose cp` sequence. Record image
versions and `SELECT version, description, checksum FROM flyway_schema_history`
with the backup. Encrypt and restrict backup files; they contain sensitive data.

## MinIO backup

Database dumps alone are incomplete because object bytes live in MinIO. For a
development copy, configure `mc` with credentials read from the secret store and
mirror each private bucket to an encrypted backup destination using `--preserve`.
For production/versioned data, configure MinIO bucket replication or a
version-aware backup product so non-current versions and Object Lock metadata
are retained. Verify object counts and SHA-256 values against
`storage.object_metadata`.

Do not put credentials on the command line or treat a filesystem copy of a live
MinIO volume as a consistent backup. Coordinate database and object-store backup
times and record the recovery point.

## Restore

Restore is destructive to the selected target. Confirm it is an isolated/new
environment, preserve the original backup, and stop future backend/workers first.

1. Start a compatible pinned PostgreSQL/MinIO version on empty volumes.
2. Create roles/databases via the bootstrap scripts.
3. Copy the dumps into the PostgreSQL container.
4. Restore `bank_ai` and `keycloak` with `pg_restore --clean --if-exists` only
   after confirming the exact target database.
5. Restore all MinIO buckets/versions with the approved version-aware process.
6. Run Flyway `validate`/`migrate`; never edit schema history to hide mismatch.
7. Verify extensions, RLS/role attributes, counts, object checksums/references,
   Keycloak discovery and service smoke tests before allowing clients.

Use a new Kafka/Redis state unless an explicit messaging recovery plan requires
otherwise: PostgreSQL is the source of truth, outbox rows can republish missing
events, and Redis is rebuildable.

## Re-run migration or seed

Flyway migration is idempotent for already-applied versioned migrations:

```powershell
.\scripts\stack.ps1 db-migrate
.\scripts\stack.ps1 db-seed
```

```bash
make db-migrate
make db-seed
```

Running seed twice is a required verification. Never modify an applied
versioned SQL migration; add the next `VNNN__description.sql`. Do not use Flyway
`repair` until a human has proved the checksum drift is metadata-only and has an
approved incident/change record.

## Migration failure

1. Capture the Flyway exit status and safe logs; do not disable validation.
2. Check PostgreSQL health, available disk, credentials, file naming/order and
   `flyway_schema_history` state.
3. Compare the failed migration with the exact pinned database/extension version.
4. On a disposable fresh environment, reset and reproduce from empty volumes.
5. If a transaction rolled back, fix by adding/correcting the unapplied migration
   and rerun. If DDL partially committed, back up, assess each object and write an
   explicit forward recovery migration.
6. Do not delete history rows or mark a failed change successful to bypass the
   error. Restore the last known-good backup when forward recovery is unsafe.

## Add or change a Kafka topic

Do not run an ad-hoc create command as the source of truth.

1. Add the exact topic name, 3 local partitions, replication factor 1, cleanup
   and retention to `kafka/topics/topics.yaml`.
2. Add least-privilege producer, consumer-topic and group ACLs to
   `kafka/acl/acl.yaml`.
3. Add/update its JSON Schema, event list, partition key and owner in
   [kafka-contract.md](kafka-contract.md).
4. Run `stack.ps1 kafka-init` / `make kafka-init`, then `kafka-describe` and
   `kafka-smoke`.
5. Prove the intended principal succeeds and an unprivileged principal is denied.

A breaking event change uses a new schema/event version and usually a new topic
suffix; never mutate a v1 contract incompatibly.

## Kafka consumer lag

1. Confirm broker health, offline/under-replicated partitions and disk capacity.
2. Identify the group/topic/partition and whether lag grows or is historical.
3. Check consumer error/retry/DLQ rate, processing latency and blocked database/
   MinIO dependencies using the shared correlation ID.
4. Scale the consumer group only up to the topic partition count; preserve the
   partition key ordering contract.
5. Correct poison messages through bounded retry/DLQ handling. Never skip offsets
   merely to make a graph green.
6. Before an intentional offset reset, stop the group, back up/record current
   offsets, assess `integration.event_inbox` behavior, obtain approval and audit
   the exact reset. Restart and verify durable results in PostgreSQL.

## MinIO capacity/full condition

1. Stop or throttle new uploads; do not bypass retention/legal holds.
2. Check MinIO health, disk free space, per-bucket/object/version usage and failed
   multipart uploads.
3. Abort only expired incomplete multipart uploads under the declared lifecycle.
4. Expire quarantine objects only according to its 3-day rule. Derived cleanup
   applies only to `retention-status=eligible` objects; the `bank-api` retention
   control plane may set that tag only after confirming the PostgreSQL deadline
   has passed and `legal_hold = FALSE`. Its storage policy can tag but cannot
   directly delete derived objects.
5. Add capacity or move data with a version-aware verified process. Never delete
   originals, reports or audit objects ad hoc.
6. Reconcile object count/checksum/version IDs with `storage.object_metadata`,
   then resume uploads and monitor request/error rate.

## Rotate credentials

General order: generate a new value securely, update the server-side identity,
update the secret store, roll only affected clients, prove the new credential,
prove old credential rejection, revoke old value and audit the change.

- PostgreSQL: an authorized administrator runs `ALTER ROLE ... PASSWORD` through
  a secure session; update `.env.local`/production secret and restart clients.
- Redis: perform a controlled maintenance restart with the new password, update
  exporter/clients together and verify unauthenticated rejection plus `PONG`.
- Kafka: change one SCRAM principal at a time with `kafka-configs`, update only
  that service and rerun allowed/denied ACL smoke tests.
- MinIO: rotate one service account secret or create/swap/revoke a replacement;
  verify its exact policy before revoking the old credential.
- Keycloak: rotate backend and worker client secrets independently via the admin
  API/CLI, update clients, verify `aud=bank-ai-api`, then revoke old values.
- Field encryption key: use a versioned dual-read/new-write re-encryption plan;
  never simply replace the key or old ciphertext becomes unrecoverable.

Do not print any new/old secret while troubleshooting.

## Old or incompatible volumes

Symptoms include database catalog-version errors, Kafka metadata-format errors,
MinIO startup failures after downgrade, or Keycloak schema mismatch. Stop the
stack, record current image tags and volume names, and back up/recover the data
with the old compatible image. Follow the vendor-supported upgrade path one
major version at a time. For disposable local data only, use the confirmed
`infra-reset` and rebuild; never delete a production or ambiguous volume.

## Port conflict

Find the owner before changing anything; the project ports are contractual and
must not be silently renumbered.

PowerShell:

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 5432,6379,29092,8085,9000,9001,8080,5050,9090,3001 |
  Select-Object LocalAddress,LocalPort,OwningProcess
Get-Process -Id <OwningProcess>
```

Linux/WSL:

```bash
ss -ltnp
```

Stop the conflicting local service/container if safe, then restart the stack.
Do not change a specified port without an approved contract change across
Compose, `.env.example`, contracts, tests and documentation.

## Fast diagnostic checklist

- `docker info` and `docker compose version` succeed.
- `.env.local` exists but is not Git tracked; `versions.env` contains no
  `latest`.
- `infra-ps` shows no restart loop; service health logs contain no secret.
- PostgreSQL has both databases, four extensions, all migrations and enabled RLS
  for non-owner runtime roles without `BYPASSRLS`.
- Redis rejects no-password access and authenticated `PING` returns `PONG`.
- Kafka KRaft metadata, topics, retention, ACL success/denial and smoke event pass.
- MinIO bucket, versioning, lifecycle and policy success/denial checks pass.
- Keycloak realm/clients/roles/users and validated audience token pass.
- Optional tools/observability services appear only under their profiles.

Only mark a check successful when its command was actually run and returned the
expected result.
