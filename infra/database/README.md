# PostgreSQL infrastructure

This directory contains only database infrastructure for the AI Credit
Intelligence Workbench. PostgreSQL is the business source of truth; binary
documents remain in MinIO and durable asynchronous delivery uses the outbox
tables.

## Layout

- `bootstrap/create-databases.sh` creates `bank_ai`, `keycloak`, and the
  required extensions during first PostgreSQL volume initialization.
- `bootstrap/create-roles.sh` creates the five least-privilege login roles,
  isolates the two databases, and grants `pg_monitor` to `bank_readonly`.
- `migrations/V001...V017` are ordered Flyway versioned migrations.
- `seeds/run-seeds.sh` applies the four repeatable, idempotent seed files in
  their required dependency order.
- `partitions/create-future-partitions.sql` creates one future UTC calendar
  year of monthly transaction partitions.

The bootstrap scripts consume passwords only from environment variables. They
do not contain fallback passwords or print credentials.

## Roles

| Role | Purpose |
| --- | --- |
| `bank_migrator` | Owns `bank_ai` and all application schemas; runs Flyway and seeds only. |
| `bank_app` | Runtime read/insert/update access, constrained by RLS; no schema or role administration. |
| `bank_worker` | Reads assigned work and writes processing, AI, integration and audit results; cannot write `credit.loan_decision` or employee authorization. |
| `bank_readonly` | Reads only the six masked business views and PostgreSQL monitoring data through `pg_monitor`. |
| `keycloak_app` | Owns and accesses only the separate `keycloak` database. |

Every runtime role is explicitly `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOREPLICATION`, and `NOBYPASSRLS`.

## Migration

From the Compose project directory, use the repository migration command. A
direct Flyway equivalent is:

    flyway \
      -url=jdbc:postgresql://postgres:5432/bank_ai \
      -user=bank_migrator \
      -password=<from-environment> \
      -locations=filesystem:/flyway/sql migrate

V001 verifies the target database and extension contract. Database creation is
not attempted from Flyway because PostgreSQL does not allow `CREATE DATABASE`
inside a migration transaction.

## Seed

The Compose seed runner supplies `PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, and `PGPASSWORD` and runs:

    sh /opt/bank/seeds/run-seeds.sh

The four repeatable files seed synthetic data only:

1. roles, permissions, and role mappings;
2. three branches, four departments, seven employees, a loan product, policy,
   clauses, checklist rules, and retention rules;
3. three demo customers, two accounts each, one VND 700,000,000 / 60-month
   application, one job, and one pending outbox event;
4. twelve rolling UTC months of synthetic transactions and summaries.

The special demo case keeps the required values separate: VND 30,000,000
declared income, VND 28,000,000 payslip value, VND 22,000,000 average salary
inflow, and VND 6,000,000 monthly existing obligation.

## RLS session contract

The backend or worker must start a transaction and set all context values
before accessing protected data:

    SET LOCAL app.employee_id = '<employee-uuid>';
    SET LOCAL app.branch_id = '<branch-uuid>';
    SET LOCAL app.is_admin = 'false';

Missing, invalid, inactive, or inconsistent context denies access. The admin
flag is accepted only when the employee also has an active `admin` role.

## Verification queries

Run these as `bank_migrator` after Flyway and seed:

    SELECT extname
    FROM pg_extension
    WHERE extname IN ('vector', 'pgcrypto', 'citext', 'uuid-ossp')
    ORDER BY extname;

    SELECT version, success
    FROM flyway_schema_history
    ORDER BY installed_rank;

    SELECT schemaname, tablename
    FROM pg_tables
    WHERE schemaname IN (
      'identity', 'customer', 'banking', 'storage', 'document',
      'credit', 'policy', 'ai', 'integration', 'audit'
    )
    ORDER BY schemaname, tablename;

    SELECT schemaname, tablename, rowsecurity
    FROM pg_tables
    WHERE rowsecurity
    ORDER BY schemaname, tablename;

    SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication,
           rolbypassrls
    FROM pg_roles
    WHERE rolname IN (
      'bank_migrator', 'bank_app', 'bank_worker',
      'bank_readonly', 'keycloak_app'
    )
    ORDER BY rolname;

Run the seed command twice and require both invocations to exit zero. Counts
remain stable because every seed key is deterministic and all inserts use
conflict-safe upserts.

See `partitions/README.md` for yearly partition maintenance. Do not grant
runtime users direct access to child partitions; all transaction access must
flow through the RLS-protected parent.
