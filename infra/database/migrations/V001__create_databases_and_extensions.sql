-- Databases and login roles are provisioned by database/bootstrap before Flyway.
-- This migration owns the bank_ai extension contract and intentionally fails if
-- Flyway is pointed at the wrong database.
DO $migration$
BEGIN
    IF current_database() <> 'bank_ai' THEN
        RAISE EXCEPTION 'Flyway must run against bank_ai, current database is %',
            current_database();
    END IF;
END
$migration$;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

