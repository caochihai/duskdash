# Security model

The local stack is intentionally developer-oriented but preserves the critical
authorization and data-boundary controls needed by later application code. Local
HTTP/SASL_PLAINTEXT are not production transport choices; the production
template requires TLS and private network exposure.

## Network isolation

| Network | Members / purpose | Prohibited exposure |
| --- | --- | --- |
| `bank-edge` | Keycloak, MinIO host endpoints, Kafka external listener, opt-in tools and observability UIs | PostgreSQL is never attached; production Redis is never attached |
| `bank-application` | Future backend/workers, Kafka, Redis, MinIO, Keycloak and required exporters | Database administration is not exposed through it |
| `bank-data` | PostgreSQL, Flyway, PgAdmin, Keycloak and future database clients | No browser-facing service or arbitrary public ingress |

Compose host bindings for PostgreSQL, Redis, Kafka, MinIO and Keycloak support
local development. Production uses private subnets/firewalls for databases,
caches and brokers, places TLS ingress in front of public OIDC/API endpoints,
and restricts Kafka UI, PgAdmin, Prometheus and Grafana to an operator channel.

## Secret management

- `.env.example` and connection-contract examples contain placeholders only.
- `generate-secrets.ps1`/`.sh` produce secure random values in untracked
  `.env.local`, refuse overwrite without `--force`, and do not print values.
- Compose interpolates secrets; YAML, realm JSON, policy files, scripts, logs and
  command histories never embed real values.
- Root/superuser credentials are bootstrap-only. Runtime services use separate
  database, Kafka, MinIO and OIDC identities.
- Production should move values from `.env.local` to an approved secret manager
  or Docker/Kubernetes secret mechanism and provide audit-controlled rotation.
- Image references are exact stable versions from `versions.env`; floating
  `latest`, beta and release-candidate tags are prohibited.

The source/CI secret scan must reject passwords, access/refresh tokens, API keys,
private keys and committed `.env.local` files. A successful scan supplements,
not replaces, code review.

## Encryption and sensitive data

Production encrypts network traffic and data volumes/backups at rest. Kafka uses
SASL_SSL with certificate/hostname verification; public Keycloak/MinIO/API URLs
use HTTPS; database and Redis TLS follow platform capabilities.

Identity/contact values use application-level authenticated encryption in
`BYTEA` plus a deterministic keyed hash for lookup. Full account numbers are not
stored in display fields; only a masked value and hash are retained. The
`FIELD_ENCRYPTION_KEY` is generated outside SQL and never logged. Key rotation
uses versioned ciphertext/key identifiers and an audited, resumable re-encryption
process; do not overwrite data without a verified backup.

Kafka events, Redis keys, MinIO keys and audit metadata exclude direct PII.
Presigned URLs expire after 600 seconds and must not appear in logs. Large PDF,
image and OCR content never enters Kafka.

## PostgreSQL authorization and RLS

`bank_migrator` performs schema changes only. `bank_app`, `bank_worker`,
`bank_readonly` and `keycloak_app` are non-superuser, non-owner runtime roles
without `CREATEDB`, `CREATEROLE`, `REPLICATION` or `BYPASSRLS`. `keycloak_app`
can access only the `keycloak` database. `bank_worker` cannot insert/update
`credit.loan_decision` or employee authorization records. `bank_readonly` sees
business data only through masked views; `pg_monitor` membership is limited to
system statistics required by the PostgreSQL exporter.

Protected business tables enable RLS. Runtime roles are non-owners without
`BYPASSRLS`; each application transaction sets employee, branch and
administrator context with `SET LOCAL`, and missing or invalid context denies
access. Scope helper functions combine active employee roles/scopes with
branch/customer/loan relationships. An application admin claim is still
evaluated by policy and is not a PostgreSQL bypass attribute.

Schema/table ownership remains with the migration owner. Grants are explicit,
and default privileges must not silently expose future tables.

## Kafka authentication and authorization

Local internal/external listeners use SCRAM-SHA-512 and a unique credential for
`kafka-admin`, `bank-api`, each worker, notification gateway and audit consumer.
ACLs grant only the topic direction and consumer group listed in
[kafka-contract.md](kafka-contract.md). Automatic topic creation is disabled;
bootstrap creates declared topics/configuration and ACLs. Verification proves
both an allowed action and a denied unauthorized action.

Production uses SASL_SSL, trusted certificates, hostname verification, a
three-node KRaft topology, replication factor three and
`min.insync.replicas=2`. Kafka is durable transport, not the business database.

## MinIO isolation

All six buckets are private. Anonymous list/get/put/delete is denied. Separate
service accounts have bucket/path-specific policies; runtime never uses MinIO
root credentials. Browser access is only an exact, short-lived presigned GET/PUT
issued after backend authorization. CORS permits the local frontend origin but
does not grant object access.

Lifecycle never overrides a PostgreSQL legal hold. Derived expiry matches only
objects tagged `retention-status=eligible`; the `bank-api` retention control
plane sets that tag only after the database deadline/hold check. Its policy
limits tag get/put to `customer-doc-derived/documents/*` and grants no object
delete. Original documents and audit archive are not automatically deleted
locally. Local MinIO exposes its public metrics path through the loopback-bound
S3 port as well as the internal observability network; this grants no S3 object
permission but is still local operational data. Production should use
authenticated metrics where supported and restrict the endpoint at the network
layer.

## Keycloak

The browser client `bank-ai-frontend` is public, has no client secret, uses
Authorization Code with PKCE S256 and disables Direct Access Grants. Backend and
worker clients are confidential service accounts with separate injected secrets.
Tokens are accepted only after signature, exact issuer, `bank-ai-api` audience,
time and authorization checks. Realm roles do not replace PostgreSQL employee
status, scope or RLS.

Demo passwords come from `.env.local`; realm JSON contains none. Keycloak admin
credentials are bootstrap/operator-only and not application credentials.

## Audit and logging

`audit.audit_event` is append-only for runtime roles and uses previous/event
hashes for tamper evidence. A trigger rejects update/delete; application roles
cannot truncate. Audit may be exported to the versioned `audit-archive` bucket.

Use structured logs with UTC timestamp, severity, service, safe event name,
request/correlation/trace IDs and opaque resource IDs. Redact or omit:

- passwords, database/Kafka/MinIO/client secrets and encryption keys;
- access/refresh tokens, cookies, authorization codes and presigned URLs;
- full identity/account/contact values, raw customer payloads and document/OCR
  content; and
- private chain-of-thought.

Log safe error codes instead of sensitive exception payloads. Limit access,
retention and export of logs; security-sensitive administration, access denials,
decisions and retention operations create audit events.

## Backup, restore and rotation

Backups are encrypted, access-controlled and tested. PostgreSQL backups include
both `bank_ai` and `keycloak`; MinIO backup/replication preserves object versions
and is coordinated with database metadata. Redis/Kafka local volumes are not a
substitute for the business backup. Restore into an isolated environment,
validate checksums/migrations/object references and record the exercise.

Credential rotation is per principal. Update the authoritative secret store,
apply the server-side credential, restart/reload only affected clients, verify
old credential rejection and new credential success, then revoke the old value.
Kafka/MinIO/OIDC rotations must preserve least-privilege policies and must never
temporarily use a shared root credential in runtime.

## Mandatory negative tests

The verification suite must demonstrate unauthenticated Redis rejection,
unauthorized Kafka operation rejection, anonymous/cross-policy MinIO rejection,
RLS denial without session context, worker denial on `loan_decision`, audit
mutation denial, and an invalid Keycloak issuer/audience rejection. A control is
not considered working merely because its configuration file exists.
