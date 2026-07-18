#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

psql --host=localhost --username="${POSTGRES_USER}" --dbname=postgres \
    --set=ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE DATABASE bank_ai WITH ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'bank_ai')
\gexec

SELECT 'CREATE DATABASE keycloak WITH ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'keycloak')
\gexec
SQL

# Extensions that can require elevated privileges are installed while the
# entrypoint is still running as the PostgreSQL bootstrap superuser.
psql --host=localhost --username="${POSTGRES_USER}" --dbname=bank_ai \
    --set=ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
SQL

