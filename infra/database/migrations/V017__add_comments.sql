-- Apply an explicit business description to every required relation.
DO $comments$
DECLARE
    relation_record RECORD;
BEGIN
    FOR relation_record IN
        SELECT *
        FROM (VALUES
            ('identity', 'branch', 'Bank branch and branch hierarchy.'),
            ('identity', 'department', 'Department within a branch or central office.'),
            ('identity', 'employee', 'Employee business profile linked to the Keycloak subject.'),
            ('identity', 'role', 'Application authorization role.'),
            ('identity', 'permission', 'Atomic resource action permission.'),
            ('identity', 'role_permission', 'Permission assigned to an authorization role.'),
            ('identity', 'employee_role', 'Time-bounded role assignment for an employee.'),
            ('identity', 'employee_scope', 'Time-bounded authorization over a branch or business resource.'),
            ('customer', 'party', 'Base person or organization party record.'),
            ('customer', 'person_profile', 'Person-specific attributes for a party.'),
            ('customer', 'organization_profile', 'Organization-specific attributes for a party.'),
            ('customer', 'customer', 'Relationship between a party and the bank.'),
            ('customer', 'party_identifier', 'Encrypted and hashed regulated party identifier.'),
            ('customer', 'party_contact', 'Encrypted and masked party contact point.'),
            ('customer', 'party_address', 'Verified party address history.'),
            ('customer', 'employment', 'Party employment and declared income.'),
            ('customer', 'income_source', 'Declared, verified and accepted income values kept separately.'),
            ('customer', 'party_relationship', 'Verified relationship between two parties.'),
            ('customer', 'kyc_assessment', 'Point-in-time KYC and AML assessment.'),
            ('banking', 'account', 'Masked bank account metadata and current balance.'),
            ('banking', 'account_holder', 'Time-bounded relationship between an account and a party.'),
            ('banking', 'transaction', 'Monthly partitioned bank account transaction ledger.'),
            ('banking', 'account_monthly_summary', 'Derived monthly transaction totals for an account.'),
            ('banking', 'credit_report', 'Metadata and risk summary for an external credit report.'),
            ('banking', 'credit_facility', 'Credit facility reported by an external credit provider.'),
            ('storage', 'object_metadata', 'Metadata and immutable location of a MinIO object version.'),
            ('storage', 'upload_session', 'Idempotent presigned upload lifecycle.'),
            ('storage', 'retention_rule', 'Retention schedule definition by resource type.'),
            ('storage', 'resource_retention', 'Applied retention deadline or legal hold for a resource.'),
            ('document', 'document', 'Logical document independent of its file versions.'),
            ('document', 'document_version', 'Immutable uploaded file version of a document.'),
            ('document', 'document_link', 'Polymorphic link from a document to a business resource.'),
            ('document', 'processing_job', 'Document processing attempt and safe error status.'),
            ('document', 'document_page', 'Normalized OCR page content and page image reference.'),
            ('document', 'extracted_field', 'OCR, normalized and human-corrected field values kept separately.'),
            ('document', 'document_chunk', 'Document retrieval chunk and optional pgvector embedding.'),
            ('document', 'document_issue', 'Document quality, consistency or verification issue.'),
            ('credit', 'loan_product', 'Effective-dated loan product definition.'),
            ('credit', 'loan_application', 'Customer loan request and human-controlled workflow status.'),
            ('credit', 'loan_party', 'Party role in a loan application.'),
            ('credit', 'existing_obligation', 'Existing monthly obligation used by affordability analysis.'),
            ('credit', 'collateral', 'Collateral declared for a loan application.'),
            ('credit', 'collateral_valuation', 'Point-in-time independent collateral valuation.'),
            ('credit', 'loan_checklist_item', 'Required application document or policy checklist item.'),
            ('credit', 'calculation_record', 'Versioned inputs, formula and result for a material calculation.'),
            ('credit', 'affordability_assessment', 'Recorded income, debt and affordability metrics.'),
            ('credit', 'policy_check', 'Result of evaluating one policy rule or clause.'),
            ('credit', 'approval_request', 'Human approval request for a loan application.'),
            ('credit', 'loan_decision', 'Final decision recorded only by an authorized human.'),
            ('credit', 'disbursement', 'Approved loan drawdown record.'),
            ('credit', 'loan_account', 'Servicing account created after loan approval and disbursement.'),
            ('credit', 'repayment_schedule', 'Contractual installment schedule for a loan account.'),
            ('credit', 'loan_payment', 'Applied principal, interest and fee payment.'),
            ('policy', 'policy', 'Credit or compliance policy identity.'),
            ('policy', 'policy_version', 'Approved effective-dated policy document version.'),
            ('policy', 'policy_clause', 'Citable policy clause and optional pgvector embedding.'),
            ('policy', 'checklist_rule', 'Policy rule that generates checklist requirements.'),
            ('policy', 'checklist_rule_requirement', 'Document requirement emitted by a checklist rule.'),
            ('ai', 'conversation', 'Employee-owned assistant conversation context.'),
            ('ai', 'message', 'Conversation message without private chain-of-thought.'),
            ('ai', 'analysis_case', 'Traceable customer or loan analysis case.'),
            ('ai', 'analysis_task', 'Dependency-aware task delegated to an agent type.'),
            ('ai', 'agent_run', 'Versioned and hashed execution metadata for an agent.'),
            ('ai', 'finding', 'Agent finding, warning or recommendation.'),
            ('ai', 'evidence_link', 'Citation from a finding to a source record or locator.'),
            ('ai', 'validation_result', 'Citation, calculation and contradiction validation result.'),
            ('ai', 'report', 'Versioned analysis report metadata and object reference.'),
            ('ai', 'report_claim', 'Individually validated claim made by a report.'),
            ('ai', 'report_claim_evidence', 'Evidence supporting or contradicting a report claim.'),
            ('integration', 'background_job', 'Durable source of truth for background job status.'),
            ('integration', 'background_job_step', 'Durable progress for a background job step.'),
            ('integration', 'job_event', 'Ordered progress history used for SSE reconnect.'),
            ('integration', 'event_outbox', 'Transactional outbox awaiting controlled Kafka publication.'),
            ('integration', 'event_inbox', 'Consumer deduplication and processing record.'),
            ('integration', 'idempotency_record', 'Request idempotency key and cached response reference.'),
            ('integration', 'notification', 'Durable employee notification state.'),
            ('audit', 'audit_event', 'Append-only tamper-evident security and business audit event.')
        ) AS descriptions(schema_name, relation_name, description)
    LOOP
        EXECUTE format(
            'COMMENT ON TABLE %I.%I IS %L',
            relation_record.schema_name,
            relation_record.relation_name,
            relation_record.description
        );
    END LOOP;
END
$comments$;

-- Every data-dictionary column receives a database comment. The qualified
-- identifier in the comment makes automated dictionary audits unambiguous.
DO $column_comments$
DECLARE
    column_record RECORD;
BEGIN
    FOR column_record IN
        SELECT column_info.table_schema,
               column_info.table_name,
               column_info.column_name
        FROM information_schema.columns AS column_info
        WHERE column_info.table_schema IN (
            'identity', 'customer', 'banking', 'storage', 'document',
            'credit', 'policy', 'ai', 'integration', 'audit'
        )
          AND column_info.table_name NOT LIKE 'transaction\_%' ESCAPE '\'
        ORDER BY column_info.table_schema,
                 column_info.table_name,
                 column_info.ordinal_position
    LOOP
        EXECUTE format(
            'COMMENT ON COLUMN %I.%I.%I IS %L',
            column_record.table_schema,
            column_record.table_name,
            column_record.column_name,
            format(
                'Business field %s.%s.%s (%s).',
                column_record.table_schema,
                column_record.table_name,
                column_record.column_name,
                replace(column_record.column_name, '_', ' ')
            )
        );
    END LOOP;
END
$column_comments$;

COMMENT ON COLUMN identity.employee.identity_subject IS
    'Keycloak JWT sub claim; never a password or credential.';
COMMENT ON COLUMN customer.party_identifier.encrypted_value IS
    'Encrypted identifier ciphertext; never exposed through readonly views.';
COMMENT ON COLUMN customer.party_identifier.value_hash IS
    'SHA-256 lookup hash of the normalized identifier.';
COMMENT ON COLUMN customer.party_contact.encrypted_value IS
    'Encrypted contact ciphertext; never exposed through readonly views.';
COMMENT ON COLUMN banking.account.account_number_masked IS
    'Display-safe masked account number.';
COMMENT ON COLUMN banking.account.account_number_hash IS
    'SHA-256 lookup hash of the normalized account number.';
COMMENT ON COLUMN banking."transaction".raw_payload IS
    'Restricted source-system payload; excluded from readonly views.';
COMMENT ON COLUMN storage.object_metadata.object_key IS
    'Opaque MinIO object key that must not contain PII or an original filename.';
COMMENT ON COLUMN ai.message.content IS
    'User-visible message content; private chain-of-thought must never be stored.';
COMMENT ON COLUMN ai.agent_run.input_hash IS
    'Hash of agent input; raw secret or private reasoning is not stored.';
COMMENT ON COLUMN ai.agent_run.output_hash IS
    'Hash of agent output; raw private reasoning is not stored.';
COMMENT ON COLUMN integration.event_outbox.payload IS
    'Minimal event payload; tokens, secrets, full identifiers and document content are prohibited.';
COMMENT ON COLUMN audit.audit_event.metadata IS
    'Redacted audit metadata; tokens, secrets, full identifiers and document bodies are prohibited.';

COMMENT ON VIEW customer.v_customer_summary IS
    'Readonly customer summary with no encrypted identifier or contact value.';
COMMENT ON VIEW banking.v_account_masked IS
    'Readonly account view exposing only the masked account number.';
COMMENT ON VIEW banking.v_transaction_summary IS
    'Readonly transaction view excluding raw payload and counterparty account hash.';
COMMENT ON VIEW document.v_document_summary IS
    'Readonly logical document and current-version summary.';
COMMENT ON VIEW credit.v_loan_application_summary IS
    'Readonly loan application and product summary.';
COMMENT ON VIEW ai.v_report_summary IS
    'Readonly report metadata without report JSON content.';

-- Runtime grants. No runtime role owns a schema or table, can delete business
-- records, or can change the schema.
REVOKE ALL ON ALL TABLES IN SCHEMA identity, customer, banking, storage,
    document, credit, policy, ai, integration, audit
FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA identity, customer, banking, storage,
    document, credit, policy, ai, integration, audit
FROM PUBLIC;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA identity, customer,
    banking, storage, document, credit, policy, ai, integration
TO bank_app;
GRANT SELECT, INSERT ON audit.audit_event TO bank_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA integration TO bank_app;

-- Child partitions are an implementation detail. Runtime users use the
-- partitioned parent where RLS is enabled.
DO $partition_grants$
DECLARE
    partition_record RECORD;
BEGIN
    FOR partition_record IN
        SELECT child_namespace.nspname AS schema_name,
               child.relname AS table_name
        FROM pg_catalog.pg_inherits AS inheritance
        JOIN pg_catalog.pg_class AS child
          ON child.oid = inheritance.inhrelid
        JOIN pg_catalog.pg_namespace AS child_namespace
          ON child_namespace.oid = child.relnamespace
        JOIN pg_catalog.pg_class AS parent
          ON parent.oid = inheritance.inhparent
        JOIN pg_catalog.pg_namespace AS parent_namespace
          ON parent_namespace.oid = parent.relnamespace
        WHERE parent_namespace.nspname = 'banking'
          AND parent.relname = 'transaction'
    LOOP
        EXECUTE format(
            'REVOKE ALL ON TABLE %I.%I FROM bank_app, bank_worker, bank_readonly',
            partition_record.schema_name,
            partition_record.table_name
        );
    END LOOP;
END
$partition_grants$;
GRANT SELECT, INSERT, UPDATE ON banking."transaction" TO bank_app;

GRANT SELECT ON identity.branch, identity.department, identity.employee,
    identity.role, identity.permission, identity.role_permission,
    identity.employee_role, identity.employee_scope
TO bank_worker;
GRANT SELECT ON customer.customer TO bank_worker;
GRANT SELECT ON banking.account, banking.account_holder,
    banking."transaction", banking.account_monthly_summary,
    banking.credit_report, banking.credit_facility
TO bank_worker;
GRANT SELECT, INSERT, UPDATE ON storage.object_metadata, storage.upload_session
TO bank_worker;
GRANT SELECT ON storage.retention_rule, storage.resource_retention
TO bank_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA document TO bank_worker;
GRANT INSERT, UPDATE ON document.processing_job, document.document_page,
    document.extracted_field, document.document_chunk, document.document_issue
TO bank_worker;
GRANT SELECT ON credit.loan_product, credit.loan_application,
    credit.loan_party, credit.existing_obligation, credit.collateral,
    credit.collateral_valuation, credit.loan_checklist_item,
    credit.calculation_record, credit.affordability_assessment,
    credit.policy_check
TO bank_worker;
GRANT INSERT, UPDATE ON credit.calculation_record,
    credit.affordability_assessment, credit.policy_check
TO bank_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA policy TO bank_worker;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA ai TO bank_worker;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA integration TO bank_worker;
GRANT INSERT ON audit.audit_event TO bank_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA integration TO bank_worker;

REVOKE ALL ON credit.loan_decision FROM bank_worker;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON identity.role,
    identity.permission, identity.role_permission, identity.employee_role,
    identity.employee_scope
FROM bank_worker;
REVOKE UPDATE, DELETE, TRUNCATE ON audit.audit_event
FROM bank_app, bank_worker, bank_readonly;

REVOKE ALL ON ALL TABLES IN SCHEMA identity, customer, banking, storage,
    document, credit, policy, ai, integration, audit
FROM bank_readonly;
GRANT SELECT ON customer.v_customer_summary, banking.v_account_masked,
    banking.v_transaction_summary, document.v_document_summary,
    credit.v_loan_application_summary, ai.v_report_summary
TO bank_readonly;
