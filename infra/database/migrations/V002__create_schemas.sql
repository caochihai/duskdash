CREATE SCHEMA IF NOT EXISTS identity AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS customer AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS banking AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS storage AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS document AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS credit AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS policy AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS ai AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS integration AUTHORIZATION bank_migrator;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION bank_migrator;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA identity, customer, banking, storage, document,
    credit, policy, ai, integration, audit
TO bank_app, bank_worker;

GRANT USAGE ON SCHEMA identity, customer, banking, storage, document,
    credit, policy, ai, integration, audit
TO bank_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE bank_migrator
    IN SCHEMA identity, customer, banking, storage, document,
        credit, policy, ai, integration, audit
    REVOKE ALL ON TABLES FROM PUBLIC;

ALTER DEFAULT PRIVILEGES FOR ROLE bank_migrator
    IN SCHEMA identity, customer, banking, storage, document,
        credit, policy, ai, integration, audit
    REVOKE ALL ON SEQUENCES FROM PUBLIC;

