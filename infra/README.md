# AI Credit Intelligence Workbench infrastructure

This directory provisions the infrastructure layer only: PostgreSQL 18 with
pgvector, Redis, Kafka KRaft, MinIO, Keycloak, Flyway, opt-in development tools,
and opt-in Prometheus/Grafana. It contains no frontend/backend business logic.

## Prerequisites

### Windows Docker Desktop

Install Docker Desktop, enable the WSL2 engine and start Docker Desktop. Use
PowerShell from `D:\dushdask\infra`:

```powershell
docker info
docker compose version
Set-Location D:\dushdask\infra
```

PowerShell scripts are the native Windows path and do not require GNU Make.

### WSL2

Enable Docker Desktop WSL integration for the distribution, then run inside the
WSL filesystem view:

```bash
cd /mnt/d/dushdask/infra
docker info
docker compose version
```

Install `make`, `openssl` and `curl` if missing. Keep Docker Desktop running.

### Linux

Install Docker Engine, the Docker Compose v2 plugin, GNU Make, OpenSSL and curl.
Ensure the current user can reach the Docker daemon, then `cd` into `infra/`.

## Environment and secrets

`.env.example` is the complete key/name template and contains placeholders only.
The recommended path, while `.env.local` does not yet exist, is to let the secure
generator create the complete file:

```powershell
.\scripts\generate-secrets.ps1
```

```bash
make secrets
```

If local policy requires a manually populated template instead, first confirm
`.env.local` does not exist, copy the example, then replace **every** placeholder
with an independently generated value before Compose is run:

```powershell
if (Test-Path -LiteralPath .env.local) { throw '.env.local exists; refusing to overwrite it.' }
Copy-Item -LiteralPath .env.example -Destination .env.local
```

```bash
test ! -e .env.local && cp .env.example .env.local
```

The generator refuses to overwrite `.env.local` unless explicitly forced and
does not print secrets. `.env.local` is ignored by Git; never commit or share it.
Image versions—not credentials—live in `versions.env`.

## Bootstrap the complete stack

Recommended one-command bootstrap:

```powershell
.\scripts\stack.ps1 bootstrap
```

```bash
make bootstrap
```

Bootstrap is idempotent and performs core startup, Flyway migration, idempotent
seed, Kafka topic/user/ACL initialization, private MinIO initialization, Keycloak
initialization and stack verification.

The equivalent explicit sequence is:

```powershell
.\scripts\stack.ps1 infra-up
.\scripts\stack.ps1 db-migrate
.\scripts\stack.ps1 db-seed
.\scripts\stack.ps1 kafka-init
.\scripts\stack.ps1 minio-init
.\scripts\stack.ps1 keycloak-init
.\scripts\stack.ps1 verify
```

```bash
make infra-up
make db-migrate
make db-seed
make kafka-init
make minio-init
make keycloak-init
make verify
```

Do not claim a stage passed unless its command was run and returned the expected
result. Seed verification deliberately runs the seed more than once.

## Services and URLs

| Service | Local endpoint | Startup |
| --- | --- | --- |
| PostgreSQL | `localhost:5432` | core |
| Redis | `localhost:6379` | core |
| Kafka external listener | `localhost:29092` | core |
| MinIO S3 API | <http://localhost:9000> | core |
| MinIO Console | <http://localhost:9001> | core |
| Keycloak | <http://localhost:8080> | core |
| Kafka UI | <http://localhost:8085> | tools profile |
| PgAdmin | <http://localhost:5050> | tools profile |
| Prometheus | <http://localhost:9090> | observability profile |
| Grafana | <http://localhost:3001> | observability profile |

Credentials are read from the local `.env.local`: `KEYCLOAK_ADMIN*` for local
Keycloak administration, `MINIO_ROOT_*` for local MinIO bootstrap/console,
`PGADMIN_DEFAULT_*` for PgAdmin and `GRAFANA_ADMIN_*` for Grafana. Runtime
services must use their dedicated connection contracts and least-privilege
accounts, not these bootstrap credentials.

## Optional tools and observability

```powershell
.\scripts\stack.ps1 tools-up
.\scripts\stack.ps1 observability-up
```

```bash
make tools-up
make observability-up
```

Kafka UI and PgAdmin do not start in the default profile. Prometheus, Grafana and
exporters do not start in the default profile. Grafana automatically provisions
the Prometheus data source and infrastructure dashboard.

## Smoke tests and inspection

Run the complete verification:

```powershell
.\scripts\verify-stack.ps1
```

```bash
make verify
```

Focused commands include:

```text
db-verify
kafka-describe
kafka-smoke
minio-verify
keycloak-verify
infra-ps
infra-logs
```

The verifier checks Compose/image/secret hygiene; PostgreSQL/pgvector/migrations
and idempotent seed; authenticated Redis; Kafka KRaft/topics/config/ACL allow and
deny/produce-consume; private MinIO buckets/versioning/lifecycle/policies;
Keycloak realm/clients/roles/token claims; profile isolation; and Git secret
hygiene.

## Stop and reset

Stop containers while preserving data:

```powershell
.\scripts\stack.ps1 infra-down
```

```bash
make infra-down
```

Reset destroys all project named volumes. The normal command requires typing
`RESET`; back up first:

```powershell
.\scripts\stack.ps1 infra-reset
```

```bash
make infra-reset
```

After a confirmed reset, rerun bootstrap.

## Troubleshooting

- Docker unreachable: start Docker Desktop/Engine and retry `docker info`.
- Port already in use: find and stop the owning process; do not silently change
  contractual ports. See the port-conflict procedure in the runbook.
- Existing `.env.local`: the generator intentionally refuses overwrite; rotate
  service credentials before using `-Force`/`--force` on an active stack.
- Unhealthy/restarting service: run `infra-ps`, then inspect only that service's
  logs without exposing secret environment values.
- Migration checksum/failure: do not edit applied migrations or disable Flyway
  validation; follow the forward-recovery steps in the runbook.
- Old data volume after an image change: recover with the compatible old image or
  use the approved upgrade path; reset only confirmed disposable local data.
- Kafka lag or MinIO capacity: preserve durable state/retention and follow the
  dedicated operational procedures rather than deleting offsets/objects.

## Documentation

- [Architecture](docs/architecture.md)
- [Ports and URLs](docs/ports-and-urls.md)
- [Version manifest](docs/version-manifest.md)
- [Database design](docs/database-design.md)
- [Data dictionary](docs/data-dictionary.md)
- [Kafka contract](docs/kafka-contract.md)
- [MinIO layout](docs/minio-layout.md)
- [Redis usage](docs/redis-usage.md)
- [Keycloak setup](docs/keycloak-setup.md)
- [Security model](docs/security.md)
- [Runbook](docs/runbook.md)
- [Backend, worker and frontend connection contracts](contracts/)
