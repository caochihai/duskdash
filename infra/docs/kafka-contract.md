# Kafka contract

Kafka runs as one combined broker/controller in KRaft mode locally. Internal
clients use `kafka:9092`; host clients use `localhost:29092`. Both listeners use
SASL_PLAINTEXT with SCRAM-SHA-512. The controller listener is PLAINTEXT only on
the private Docker network at `kafka:9093`. Automatic topic creation is disabled.

## Topic catalogue

All local topics have 3 partitions and replication factor 1. Message size is
limited to 1 MiB. `retention.ms` values below are exact local targets.

| Topic | Producers | Consumer groups | Partition key | Cleanup / retention | Event types |
| --- | --- | --- | --- | --- | --- |
| `bank.document.commands.v1` | `bank-api` | `document-worker-group` | `document_version_id` | delete / 7 days (`604800000`) | `document.processing.requested`, `document.security-scan.requested`, `document.ocr.requested`, `document.classification.requested`, `document.extraction.requested`, `document.embedding.requested` |
| `bank.document.events.v1` | `document-worker` | `analysis-orchestrator-group`, `audit-consumer-group` | `document_version_id` | delete / 30 days (`2592000000`) | `document.processing.started`, `document.security-scan.completed`, `document.ocr.completed`, `document.classification.completed`, `document.extraction.completed`, `document.embedding.completed`, `document.processing.completed`, `document.processing.failed` |
| `bank.analysis.commands.v1` | `bank-api`, `analysis-orchestrator` | `analysis-orchestrator-group`, `credit-worker-group`, `compliance-worker-group` | `analysis_case_id` | delete / 7 days (`604800000`) | `analysis.requested`, `analysis.document-agent.requested`, `analysis.credit-agent.requested`, `analysis.compliance-agent.requested`, `analysis.validation.requested`, `analysis.synthesis.requested` |
| `bank.analysis.events.v1` | `analysis-orchestrator`, `credit-worker`, `compliance-worker` | `report-worker-group`, `audit-consumer-group` | `analysis_case_id` | delete / 30 days (`2592000000`) | `analysis.started`, `analysis.plan.created`, `analysis.task.started`, `analysis.task.completed`, `finding.created`, `analysis.validation.completed`, `analysis.completed`, `analysis.failed` |
| `bank.report.commands.v1` | `bank-api` | `report-worker-group` | `report_id` | delete / 7 days (`604800000`) | `report.generation.requested`, `report.pdf.requested` |
| `bank.report.events.v1` | `report-worker` | `audit-consumer-group` | `report_id` | delete / 30 days (`2592000000`) | `report.generation.started`, `report.generated`, `report.pdf.generated`, `report.generation.failed` |
| `bank.notification.events.v1` | `document-worker`, `analysis-orchestrator`, `credit-worker`, `compliance-worker`, `report-worker` | `notification-gateway-group` | `employee_id` or `job_id` | delete / 3 days (`259200000`) | `job.progress.updated`, `job.completed`, `job.failed`, `notification.created` |
| `bank.job-status.v1` | `document-worker` and authorized job-status publishers | `notification-gateway-group` | `job_id` | compact,delete / 7 days (`604800000`), tombstones retained per broker config | Latest minimal job status only |
| `bank.audit.events.v1` | No runtime producer in the current ACL manifest; a future audited outbox publisher requires an explicit grant | `audit-consumer-group` | resource/correlation identifier | delete / 30 days (`2592000000`) | Minimal audit projection events; never substitutes for `audit.audit_event` |
| `bank.retry.1m.v1` | `document-worker` in the current ACL manifest | No current consume ACL; a future retry dispatcher requires an explicit group/topic grant | Original partition key | delete / 7 days (`604800000`) | Original envelope plus retry metadata, next attempt about 1 minute later |
| `bank.retry.10m.v1` | `document-worker` in the current ACL manifest | No current consume ACL; a future retry dispatcher requires an explicit group/topic grant | Original partition key | delete / 7 days (`604800000`) | Original envelope plus retry metadata, next attempt about 10 minutes later |
| `bank.dead-letter.v1` | `document-worker`, `credit-worker`, `compliance-worker` | No current consume ACL; operational tooling/consumer must be explicitly granted | Original partition key | delete / 30 days (`2592000000`) | Terminal failure metadata and original event reference |

Topic bootstrap is declarative and idempotent. Any future topic must be added to
the topic manifest, ACL manifest, documentation, and verification script before
creation; never enable broker auto-create.

## Envelope v1

Every event validates against `infra/kafka/schemas/event-envelope.v1.json` before
publication and after consumption. Required fields are:

```json
{
  "event_id": "uuid",
  "event_type": "document.processing.requested",
  "event_version": 1,
  "occurred_at": "2026-07-18T07:00:00Z",
  "producer": "bank-api",
  "correlation_id": "uuid",
  "causation_id": null,
  "partition_key": "uuid",
  "actor": {"type": "EMPLOYEE", "id": "uuid"},
  "resource": {"type": "DOCUMENT_VERSION", "id": "uuid"},
  "payload": {},
  "metadata": {
    "trace_id": "uuid",
    "schema": "document.processing.requested.v1"
  }
}
```

`actor.type` is one of `EMPLOYEE`, `SERVICE`, or `AGENT`. The envelope and nested
objects reject missing required fields. Domain-specific schemas narrow
`event_type`, resource type and payload references for document, analysis,
report and notification events.

Events contain identifiers, state, minimal metadata, correlation and resource
references only. They must never contain access/refresh tokens, API keys,
passwords, full identity/account numbers, PDF/image bytes or base64, complete
OCR text, or a complete customer dossier.

## Schema evolution

- `event_version` and the final `.v1` in `metadata.schema` identify the payload
  contract; the topic suffix identifies the topic generation.
- Add optional fields compatibly within v1. Existing required fields cannot be
  removed, renamed or change type.
- A breaking change requires a v2 schema, event version and, when routing or
  retention semantics change, a new `.v2` topic. Run old/new consumers during a
  controlled transition.
- Producers validate before inserting/publishing and consumers validate before
  performing effects. Invalid events go to a bounded failure path, not silently
  accepted.

## Delivery, ordering and idempotency

Ordering is guaranteed only within a partition. Producers must use the exact
resource key shown in the catalogue so all state changes for a document,
analysis case, report or job stay ordered.

The database transaction writes business state and `integration.event_outbox`.
The outbox publisher leases pending rows with `FOR UPDATE SKIP LOCKED`, publishes
and marks them published. Delivery is therefore at least once. Before handling,
each consumer inserts `(event_id, consumer_name)` into
`integration.event_inbox`; the unique constraint makes duplicate deliveries a
no-op or return the stored result reference. Offset commit happens only after
the durable database transaction completes. Do not rely on Kafka exactly-once
semantics to replace database idempotency.

## Retry and dead letter

Retries are finite. A transient failure records a safe error and attempt count,
then schedules the 1-minute retry; a subsequent transient failure may use the
10-minute topic. After `max_attempts`, non-retryable validation/security errors,
or exhaustion of the bounded retry policy, publish a minimal terminal record to
`bank.dead-letter.v1` and mark PostgreSQL job state failed. Never place secrets,
full payloads containing PII, or large content in retry/DLQ records.

DLQ replay is an operator action: identify and correct the cause, confirm the
target schema/version and idempotency record, then republish using a new
`event_id` with the failed event as `causation_id`. Record the action in audit.

## ACL matrix

| Principal | Consume | Produce |
| --- | --- | --- |
| `bank-api` | None of the worker topics | `bank.document.commands.v1`, `bank.analysis.commands.v1`, `bank.report.commands.v1` |
| `document-worker` | `bank.document.commands.v1` | `bank.document.events.v1`, `bank.notification.events.v1`, `bank.job-status.v1`, both retry topics, DLQ |
| `analysis-orchestrator` | `bank.analysis.commands.v1`, `bank.document.events.v1` | `bank.analysis.commands.v1`, `bank.analysis.events.v1`, `bank.notification.events.v1` |
| `credit-worker` | `bank.analysis.commands.v1` | `bank.analysis.events.v1`, `bank.notification.events.v1`, DLQ |
| `compliance-worker` | `bank.analysis.commands.v1` | `bank.analysis.events.v1`, `bank.notification.events.v1`, DLQ |
| `report-worker` | `bank.report.commands.v1`, `bank.analysis.events.v1` | `bank.report.events.v1`, `bank.notification.events.v1` |
| `notification-gateway` | `bank.notification.events.v1`, `bank.job-status.v1` | No business commands |
| `audit-consumer` | `bank.audit.events.v1`, document/analysis/report event topics | No business commands |

ACLs also bind each consumer principal to its named group:
`document-worker-group`, `analysis-orchestrator-group`, `credit-worker-group`,
`compliance-worker-group`, `report-worker-group`,
`notification-gateway-group`, and `audit-consumer-group`. The smoke test must
prove an allowed operation succeeds and a forbidden operation is denied.

## High-availability template

Production uses at least three KRaft nodes, at least three partitions per topic,
replication factor 3, and `min.insync.replicas=2`, with SASL_SSL, certificates
from an approved trust chain and hostname verification. Separate controller
quorum and broker sizing should be selected from measured load; the local
single-node profile is not an HA design.
