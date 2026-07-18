#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_MIGRATOR_PASSWORD:?POSTGRES_MIGRATOR_PASSWORD is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"
: "${POSTGRES_WORKER_PASSWORD:?POSTGRES_WORKER_PASSWORD is required}"
: "${POSTGRES_READONLY_PASSWORD:?POSTGRES_READONLY_PASSWORD is required}"
: "${KEYCLOAK_DB_PASSWORD:?KEYCLOAK_DB_PASSWORD is required}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

psql --host=localhost --username="${POSTGRES_USER}" --dbname=postgres \
    --set=ON_ERROR_STOP=1 \
    --set=migrator_password="${POSTGRES_MIGRATOR_PASSWORD}" \
    --set=app_password="${POSTGRES_APP_PASSWORD}" \
    --set=worker_password="${POSTGRES_WORKER_PASSWORD}" \
    --set=readonly_password="${POSTGRES_READONLY_PASSWORD}" \
    --set=keycloak_password="${KEYCLOAK_DB_PASSWORD}" <<'SQL'
SELECT format(
    'CREATE ROLE bank_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'migrator_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_migrator')
\gexec
SELECT format(
    'ALTER ROLE bank_migrator WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'migrator_password'
) \gexec

SELECT format(
    'CREATE ROLE bank_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_app')
\gexec
SELECT format(
    'ALTER ROLE bank_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'app_password'
) \gexec

SELECT format(
    'CREATE ROLE bank_worker LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'worker_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_worker')
\gexec
SELECT format(
    'ALTER ROLE bank_worker WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'worker_password'
) \gexec

SELECT format(
    'CREATE ROLE bank_readonly LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'readonly_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_readonly')
\gexec
SELECT format(
    'ALTER ROLE bank_readonly WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'readonly_password'
) \gexec

SELECT format(
    'CREATE ROLE keycloak_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'keycloak_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keycloak_app')
\gexec
SELECT format(
    'ALTER ROLE keycloak_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'keycloak_password'
) \gexec

GRANT pg_monitor TO bank_readonly;

ALTER DATABASE bank_ai OWNER TO bank_migrator;
ALTER DATABASE keycloak OWNER TO keycloak_app;

REVOKE CONNECT ON DATABASE bank_ai FROM PUBLIC;
REVOKE CONNECT ON DATABASE keycloak FROM PUBLIC;
GRANT CONNECT ON DATABASE bank_ai TO bank_migrator, bank_app, bank_worker, bank_readonly;
GRANT CONNECT ON DATABASE keycloak TO keycloak_app;
REVOKE CONNECT ON DATABASE bank_ai FROM keycloak_app;
REVOKE CONNECT ON DATABASE keycloak
    FROM bank_migrator, bank_app, bank_worker, bank_readonly;
SQL

psql --host=localhost --username="${POSTGRES_USER}" --dbname=bank_ai \
    --set=ON_ERROR_STOP=1 <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE bank_ai FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE bank_ai
    TO bank_migrator, bank_app, bank_worker, bank_readonly;
SQL

psql --host=localhost --username="${POSTGRES_USER}" --dbname=keycloak \
    --set=ON_ERROR_STOP=1 <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE keycloak FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE keycloak TO keycloak_app;
GRANT USAGE, CREATE ON SCHEMA public TO keycloak_app;
SQL

