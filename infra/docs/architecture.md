# Infrastructure architecture

This repository provisions only the local infrastructure for the AI Credit
Intelligence Workbench. Frontend, backend and worker boxes below are future
consumers shown to define trust boundaries and connection contracts; they are
not implemented by this infrastructure package. PostgreSQL is the business
source of truth. Kafka carries durable asynchronous events, MinIO stores binary
objects, and Redis stores only temporary coordination/cache data.

## Topology

```mermaid
flowchart TB
  Browser[Browser / future frontend]
  Backend[Future backend]
  Workers[Future workers]

  subgraph Edge[bank-edge]
    KC[Keycloak :8080]
    MinIOConsole[MinIO console :9001]
    KafkaExternal[Kafka external listener :29092]
    Tools[Kafka UI :8085 and PgAdmin :5050]
    Obs[Prometheus :9090 and Grafana :3001]
  end

  subgraph Application[bank-application]
    Kafka[Kafka KRaft internal :9092]
    Redis[Redis :6379]
    MinIO[MinIO S3 :9000]
    KCInternal[Keycloak internal :8080]
  end

  subgraph Data[bank-data]
    Postgres[(PostgreSQL :5432)]
    Flyway[Flyway migration runner]
    KeycloakDB[(keycloak database)]
  end

  Browser -->|OIDC Authorization Code and PKCE| KC
  Browser -->|HTTPS REST and SSE| Backend
  Browser -->|presigned GET PUT only| MinIO
  Backend -->|bank_app plus RLS context| Postgres
  Backend -->|temporary cache and fan-out| Redis
  Backend -->|outbox publisher| Kafka
  Backend -->|presigned URL management| MinIO
  Backend -->|JWT discovery and JWKS| KCInternal
  Workers -->|bank_worker plus RLS context| Postgres
  Workers -->|SASL SCRAM| Kafka
  Workers -->|least-privilege service accounts| MinIO
  Flyway -->|bank_migrator| Postgres
  KCInternal -->|keycloak_app only| KeycloakDB
  KafkaExternal --- Kafka
  MinIOConsole --- MinIO
  Tools -. tools profile .-> Kafka
  Tools -. tools profile .-> Postgres
  Obs -. observability profile .-> Postgres
  Obs -. observability profile .-> Kafka
  Obs -. observability profile .-> Redis
  Obs -. observability profile .-> MinIO
```

PostgreSQL is never attached to `bank-edge`. The local host mappings for
PostgreSQL and Redis are developer conveniences and must not be copied into a
production deployment. Tools and observability services are opt-in profiles.

## Document pipeline

```mermaid
sequenceDiagram
  actor User as Authorized employee
  participant FE as Future frontend
  participant API as Future backend
  participant DB as PostgreSQL
  participant S3 as MinIO
  participant OP as Outbox publisher
  participant K as Kafka
  participant DW as Document worker
  participant NG as Notification gateway

  User->>FE: Select PDF or image
  FE->>API: Create upload session
  API->>DB: Store upload_session
  API-->>FE: Presigned quarantine URL, TTL 600 seconds
  FE->>S3: PUT uploads/{upload_id}/incoming
  FE->>API: Confirm checksum and upload
  API->>DB: One transaction: status, background_job, event_outbox
  OP->>DB: SELECT pending FOR UPDATE SKIP LOCKED
  OP->>K: document.processing.requested
  DW->>K: Consume with document-worker-group
  DW->>DB: Insert event_inbox idempotency record
  DW->>S3: Read quarantine, write original and derived objects
  DW->>DB: Persist normalized OCR, fields and job status
  DW->>DB: Insert completed event in event_outbox
  OP->>K: document.processing.completed
  NG->>K: Consume notification/job status
  NG->>DB: Read durable state and append job_event
  NG-->>FE: Future SSE progress notification
```

Large OCR text, files and images stay in PostgreSQL/MinIO; Kafka messages contain
only identifiers, minimal state and correlation metadata.

## Credit analysis pipeline

```mermaid
flowchart LR
  Request[Authorized analysis request]
  TX[PostgreSQL transaction creates analysis_case, background_job and outbox]
  Kafka[(bank.analysis.commands.v1)]
  Orchestrator[Analysis orchestrator]
  DocAgent[Document agent task]
  CreditAgent[Credit agent task]
  Compliance[Compliance agent task]
  Validator[Evidence and calculation validator]
  Report[Report worker]
  DB[(PostgreSQL findings, evidence, calculations, reports)]
  S3[(MinIO generated-reports)]
  Completed[(bank.analysis.events.v1)]
  Human[Authorized human decision]

  Request --> TX --> Kafka --> Orchestrator
  Orchestrator --> DocAgent
  Orchestrator --> CreditAgent
  Orchestrator --> Compliance
  DocAgent --> Validator
  CreditAgent --> Validator
  Compliance --> Validator
  Validator -->|approved for synthesis| Report
  Validator -->|insufficient or conflicting| DB
  Report --> DB
  Report --> S3
  Report --> Completed
  DB --> Human
```

Agents create findings, analysis and recommendations only. They never write an
official `credit.loan_decision`; that record requires an authorized employee.

## Kafka event flow

```mermaid
flowchart TB
  Outbox[(integration.event_outbox)] --> Publisher[Outbox publisher]
  Publisher --> DocCmd[bank.document.commands.v1]
  Publisher --> AnalysisCmd[bank.analysis.commands.v1]
  Publisher --> ReportCmd[bank.report.commands.v1]

  DocCmd --> DW[document-worker-group]
  AnalysisCmd --> AO[analysis-orchestrator-group]
  AnalysisCmd --> CW[credit-worker-group]
  AnalysisCmd --> CoW[compliance-worker-group]
  ReportCmd --> RW[report-worker-group]

  DW --> DocEvents[bank.document.events.v1]
  AO --> AnalysisEvents[bank.analysis.events.v1]
  CW --> AnalysisEvents
  CoW --> AnalysisEvents
  RW --> ReportEvents[bank.report.events.v1]

  DocEvents --> Audit[audit-consumer-group]
  AnalysisEvents --> Audit
  ReportEvents --> Audit
  DocEvents --> Notify[bank.notification.events.v1]
  AnalysisEvents --> Notify
  ReportEvents --> Notify

  DW --> Retry1[bank.retry.1m.v1]
  Retry1 --> Retry10[bank.retry.10m.v1]
  Retry10 --> DLQ[bank.dead-letter.v1]

  DW -. insert before processing .-> Inbox[(integration.event_inbox)]
  AO -. insert before processing .-> Inbox
  CW -. insert before processing .-> Inbox
  CoW -. insert before processing .-> Inbox
  RW -. insert before processing .-> Inbox
```

Every topic has three partitions and replication factor one locally. Production
uses at least three brokers, replication factor three, `min.insync.replicas=2`,
SASL_SSL and hostname verification. Automatic topic creation is disabled.

## Notification flow

```mermaid
sequenceDiagram
  participant W as Worker
  participant DB as PostgreSQL
  participant OP as Outbox publisher
  participant K as Kafka
  participant NG as Notification gateway
  participant R as Redis
  participant FE as Future frontend

  W->>DB: Commit job state, job_event and event_outbox
  OP->>K: job.progress.updated or job.completed
  NG->>K: Consume notification-gateway-group
  NG->>DB: De-duplicate in event_inbox
  NG->>DB: Persist integration.notification
  NG->>R: Publish bank-ai:sse:employee:{employee_id}
  R-->>FE: Live SSE fan-out through backend instances
  Note over FE,DB: After reconnect, read background_job and job_event from PostgreSQL
```

Redis Pub/Sub is an optimization for live delivery. Missing a Pub/Sub message
does not lose state because reconnect and replay use PostgreSQL.

## Persistent boundaries

| Store | Authoritative for | Explicitly not used for |
| --- | --- | --- |
| PostgreSQL | Business records, job state, normalized extraction, findings, reports, outbox/inbox, notifications and audit | Large PDF/image binary |
| MinIO | Original and derived binary objects, generated reports, policy files and audit archive | Business authorization and searchable entity state |
| Kafka | Durable delivery, replay and consumer scaling | Business source of truth or large payload transport |
| Redis | Cache, locks, rate limits, session/JWKS cache and live fan-out | Sole job/result/audit storage |
| Keycloak | Authentication, tokens, realm/client roles | Employee business profile |
