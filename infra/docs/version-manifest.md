# Container version manifest

Checked on **2026-07-18**. `infra/versions.env` is the single source for image
references consumed by Compose. Every reference uses an exact stable tag; no
service uses `latest`, beta or release-candidate tags. Digests were not recorded
in this local manifest because the selected registries publish platform-specific
manifests and the target architecture is chosen by Docker Desktop/Engine. For a
controlled deployment, resolve and lock the matching platform digest in the
release pipeline without changing the image/version contract below.

| Variable | Exact image | Source used for verification | Notes |
| --- | --- | --- | --- |
| `POSTGRES_IMAGE` | `pgvector/pgvector:0.8.5-pg18-bookworm` | [pgvector releases](https://github.com/pgvector/pgvector/releases/tag/v0.8.5), [pgvector image tags](https://hub.docker.com/r/pgvector/pgvector/tags) | pgvector 0.8.5 with PostgreSQL 18 on Debian Bookworm |
| `REDIS_IMAGE` | `redis:8.8.0-trixie` | [Redis official image](https://hub.docker.com/_/redis), [Redis releases](https://github.com/redis/redis/releases) | Official stable Redis image |
| `KAFKA_IMAGE` | `apache/kafka:4.3.1` | [Apache Kafka Docker documentation](https://kafka.apache.org/43/getting-started/docker/), [Apache Kafka downloads](https://kafka.apache.org/downloads) | Official Apache image; KRaft mode |
| `KAFKA_RUNTIME_IMAGE` | `bank-ai-kafka:4.3.1-jmx-1.5.0` | Built locally from the pinned `KAFKA_IMAGE` by `kafka/Dockerfile` | Deterministic local tag for the Kafka base plus the pinned JMX agent; never pulled as an external image |
| `JMX_EXPORTER_VERSION` | `1.5.0` | [Prometheus JMX Exporter 1.5.0 release](https://github.com/prometheus/jmx_exporter/releases/tag/1.5.0) | Java agent artifact; SHA-256 `0315f3f657876302c6205a98d4036ec775dca529c5d0419ca60ee669c688239f` is verified during the image build |
| `MINIO_IMAGE` | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | [MinIO image tags](https://hub.docker.com/r/minio/minio/tags), [MinIO releases](https://github.com/minio/minio/releases) | Exact stable release. The Docker Hub repository is archived; retain this verified tag and review migration/support risk before production use |
| `MINIO_MC_IMAGE` | `minio/mc:RELEASE.2025-08-13T08-35-41Z` | [MinIO Client image tags](https://hub.docker.com/r/minio/mc/tags), [MinIO Client releases](https://github.com/minio/mc/releases) | Exact stable client used only for bootstrap/verification |
| `KEYCLOAK_IMAGE` | `quay.io/keycloak/keycloak:26.7.0` | [Keycloak container guide](https://www.keycloak.org/server/containers), [Keycloak downloads](https://www.keycloak.org/downloads) | Official Quay image, stable release |
| `FLYWAY_IMAGE` | `flyway/flyway:12.11.0` | [Flyway Docker image documentation](https://documentation.red-gate.com/flyway/reference/usage/flyway-docker) | Official Flyway image, stable release |
| `CURL_IMAGE` | `curlimages/curl:8.21.0` | [curl container image](https://hub.docker.com/r/curlimages/curl), [curl-container releases](https://github.com/curl/curl-container/releases) | Minimal HTTP client used by Keycloak OIDC/admin smoke verification; exact stable tag |
| `KAFKA_UI_IMAGE` | `provectuslabs/kafka-ui:v0.7.2` | [Kafka UI releases](https://github.com/provectus/kafka-ui/releases/tag/v0.7.2) | Development tool profile only |
| `PGADMIN_IMAGE` | `dpage/pgadmin4:9.16` | [pgAdmin container deployment](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html) | Tools profile only |
| `PROMETHEUS_IMAGE` | `prom/prometheus:v3.11.3` | [Prometheus downloads](https://prometheus.io/download/), [Prometheus releases](https://github.com/prometheus/prometheus/releases) | Observability profile only |
| `GRAFANA_IMAGE` | `grafana/grafana:13.1.0` | [Grafana Docker installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/), [Grafana releases](https://github.com/grafana/grafana/releases) | Observability profile only |
| `POSTGRES_EXPORTER_IMAGE` | `prometheuscommunity/postgres-exporter:v0.19.1` | [postgres_exporter releases](https://github.com/prometheus-community/postgres_exporter/releases/tag/v0.19.1) | Internal metrics endpoint only |
| `REDIS_EXPORTER_IMAGE` | `oliver006/redis_exporter:v1.84.0` | [redis_exporter releases](https://github.com/oliver006/redis_exporter/releases/tag/v1.84.0) | Internal metrics endpoint only |
| `KAFKA_EXPORTER_IMAGE` | `danielqsj/kafka-exporter:v1.9.0` | [kafka_exporter releases](https://github.com/danielqsj/kafka_exporter/releases/tag/v1.9.0) | Internal metrics endpoint only |

## Update procedure

1. Review the upstream stable release notes and compatibility with the pinned
   PostgreSQL/Kafka/Keycloak data formats.
2. Change only the relevant value in `versions.env`; never insert a floating tag.
3. Pull the image, record its multi-architecture manifest digest and scan it.
4. Run `docker compose config`, bootstrap on clean volumes, migrations and every
   smoke test before merging.
5. Update the verification date and source/compatibility notes in this file.

Data-bearing services require a documented backup and restore test before any
major-version upgrade. Do not reuse a newer data volume with an older image.
