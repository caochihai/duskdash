# Observability profile

Prometheus and Grafana are optional local services and must be started only with
the Compose `observability` profile. Prometheus scrapes PostgreSQL, Redis and
Kafka exporters, Kafka JMX metrics, and MinIO cluster metrics on internal Docker
networks. Grafana is provisioned with the Prometheus data source and the
`Bank AI / Infrastructure Overview` dashboard.

Start and inspect:

```bash
make observability-up
docker compose -f docker-compose.infra.yml \
  -f docker-compose.observability.yml --profile observability ps
```

Open Prometheus at <http://localhost:9090> and Grafana at
<http://localhost:3001>. Grafana credentials come from `GRAFANA_ADMIN_USER`
and `GRAFANA_ADMIN_PASSWORD` in `.env.local`; they are never stored here.

Expected internal scrape targets:

| Target | Port | Purpose |
| --- | ---: | --- |
| `postgres-exporter` | 9187 | Connections, transactions, active slow queries, cache and size |
| `redis-exporter` | 9121 | Memory, hit/miss, eviction, clients, latency |
| `kafka-exporter` | 9308 | Broker/topic/consumer-group state and lag |
| `kafka` | 7071 | JMX request, traffic and partition metrics |
| `minio` | 9000 | Storage, request, errors and object metrics |

If a target is down, first check the corresponding container and the
`bank-application`/`bank-data` network attachment. A healthy dashboard does not
replace service health checks or the stack smoke test.

`postgres-exporter-queries.yaml` adds a bounded diagnostic metric for currently
active queries older than one second. The exporter principal needs visibility of
`pg_stat_activity` through a least-privilege monitoring grant such as
`pg_read_all_stats`; it does not need business table write access.
