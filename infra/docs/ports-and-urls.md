# Ports and URLs

The local connection contract is fixed by `intructions.md`. Values under
**Credential keys** name variables in `.env.local` or the connection contract;
the documentation never contains their secret values.

| Service | Host URL / port | Internal Docker address | Protocol | Credential keys | Used by | Profile |
| --- | --- | --- | --- | --- | --- | --- |
| PostgreSQL | `localhost:5432` | `postgres:5432` | PostgreSQL wire, TCP | `POSTGRES_*_PASSWORD`; runtime `DATABASE_USER`, `DATABASE_PASSWORD` | Flyway, future backend/workers; PgAdmin | default; PgAdmin in `tools` |
| Redis | `localhost:6379` | `redis:6379` | RESP over TCP, password required | `REDIS_PASSWORD` | Future backend/workers; Redis exporter | default |
| Kafka external | `localhost:29092` | Do not use internally | Kafka over `SASL_PLAINTEXT`, SCRAM-SHA-512 | `KAFKA_*_USERNAME`, `KAFKA_*_PASSWORD` | Host-side administration and smoke tests | default |
| Kafka internal | Not exposed separately | `kafka:9092` | Kafka over `SASL_PLAINTEXT`, SCRAM-SHA-512 | Per-service `KAFKA_*_USERNAME`, `KAFKA_*_PASSWORD` | Future backend/workers, Kafka UI/exporter | default; UI in `tools` |
| Kafka controller | Not exposed | `kafka:9093` | KRaft controller over private PLAINTEXT | KRaft node/controller configuration | Kafka process only | default |
| Kafka UI | <http://localhost:8085> | `kafka-ui:8080` | HTTP | Kafka admin client configuration; no browser Kafka secret | Developers | `tools` only |
| MinIO S3 API | <http://localhost:9000> | `http://minio:9000` | S3-compatible HTTP | `MINIO_*_ACCESS_KEY`, `MINIO_*_SECRET_KEY`; root only for bootstrap | Future backend/workers, Prometheus | default |
| MinIO Console | <http://localhost:9001> | `http://minio:9001` | HTTP | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Local administrator | default |
| Keycloak | <http://localhost:8080> | `http://keycloak:8080` | OIDC/OAuth 2.0 over local HTTP | `KEYCLOAK_ADMIN_*`, confidential client secrets; public client has none | Browser, future backend/workers | default |
| PgAdmin | <http://localhost:5050> | `http://pgadmin:80` | HTTP | `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`; DB role credentials | Developers | `tools` only |
| Prometheus | <http://localhost:9090> | `prometheus:9090` | HTTP | None for local UI; target credentials stay inside profile configuration | Operators, Grafana | `observability` only |
| Grafana | <http://localhost:3001> | `grafana:3000` | HTTP | `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Operators | `observability` only |

Exporter endpoints are internal-only implementation endpoints; they are not part
of the application connection contract:

| Exporter | Internal address | Protocol | Data source |
| --- | --- | --- | --- |
| PostgreSQL exporter | `postgres-exporter:9187` | Prometheus HTTP | `postgres:5432` using a monitoring connection |
| Redis exporter | `redis-exporter:9121` | Prometheus HTTP | `redis:6379` using `REDIS_PASSWORD` |
| Kafka exporter | `kafka-exporter:9308` | Prometheus HTTP | `kafka:9092` using a dedicated SCRAM client |
| Kafka JMX agent | `kafka:7071` | Prometheus HTTP | In-process Kafka broker/controller metrics |
| MinIO metrics | `minio:9000/minio/v2/metrics/cluster` | Prometheus HTTP | MinIO cluster metrics on the private network |

## Keycloak public endpoints

| Purpose | URL |
| --- | --- |
| Issuer | <http://localhost:8080/realms/bank-ai> |
| Authorization | <http://localhost:8080/realms/bank-ai/protocol/openid-connect/auth> |
| Token | <http://localhost:8080/realms/bank-ai/protocol/openid-connect/token> |
| JWKS | <http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs> |
| Logout | <http://localhost:8080/realms/bank-ai/protocol/openid-connect/logout> |

The frontend public contract contains only public OIDC settings, the public
MinIO endpoint used by presigned URLs and a deployment-supplied backend URL.
Browser code must never receive database, Redis, Kafka, MinIO service-account or
confidential OIDC credentials.

## Production boundary

Local HTTP and host mappings support development only. Production must terminate
TLS, use Kafka SASL_SSL with certificate/hostname verification, keep PostgreSQL
and Redis private, restrict administration UIs, and expose object access only via
short-lived presigned URLs issued after backend authorization.
