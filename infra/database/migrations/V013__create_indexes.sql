-- Identity access paths.
CREATE INDEX idx_branch_parent_branch_id ON identity.branch(parent_branch_id);
CREATE INDEX idx_branch_status ON identity.branch(status);
CREATE INDEX idx_department_branch_id ON identity.department(branch_id);
CREATE INDEX idx_department_status ON identity.department(status);
CREATE INDEX idx_employee_branch_id ON identity.employee(branch_id);
CREATE INDEX idx_employee_department_id ON identity.employee(department_id);
CREATE INDEX idx_employee_manager_id ON identity.employee(manager_id);
CREATE INDEX idx_employee_employment_status ON identity.employee(employment_status);
CREATE INDEX idx_role_permission_permission_id ON identity.role_permission(permission_id);
CREATE INDEX idx_employee_role_employee_validity
    ON identity.employee_role(employee_id, valid_from, valid_until);
CREATE INDEX idx_employee_role_role_id ON identity.employee_role(role_id);
CREATE INDEX idx_employee_scope_employee_validity
    ON identity.employee_scope(employee_id, valid_from, valid_until);
CREATE INDEX idx_employee_scope_target
    ON identity.employee_scope(scope_type, scope_id, permission_code);

-- Customer access paths.
CREATE INDEX idx_party_type_status ON customer.party(party_type, status);
CREATE INDEX idx_organization_legal_representative
    ON customer.organization_profile(legal_representative_party_id);
CREATE INDEX idx_customer_home_branch ON customer.customer(home_branch_id);
CREATE INDEX idx_customer_relationship_manager ON customer.customer(relationship_manager_id);
CREATE INDEX idx_customer_kyc_status ON customer.customer(kyc_status);
CREATE INDEX idx_customer_status ON customer.customer(status);
CREATE INDEX idx_party_identifier_party_id ON customer.party_identifier(party_id);
CREATE INDEX idx_party_contact_party_type ON customer.party_contact(party_id, contact_type);
CREATE UNIQUE INDEX uq_party_contact_primary_type
    ON customer.party_contact(party_id, contact_type)
    WHERE is_primary;
CREATE INDEX idx_party_address_party_type ON customer.party_address(party_id, address_type);
CREATE INDEX idx_employment_party_id ON customer.employment(party_id);
CREATE INDEX idx_income_source_party_date ON customer.income_source(party_id, as_of_date DESC);
CREATE INDEX idx_party_relationship_from ON customer.party_relationship(from_party_id);
CREATE INDEX idx_party_relationship_to ON customer.party_relationship(to_party_id);
CREATE INDEX idx_kyc_assessment_customer_date
    ON customer.kyc_assessment(customer_id, assessment_date DESC);

-- Banking access paths. PostgreSQL propagates partitioned indexes to every
-- existing partition and creates matching indexes for future partitions.
CREATE INDEX idx_account_branch_status ON banking.account(branch_id, status);
CREATE INDEX idx_account_holder_account ON banking.account_holder(account_id);
CREATE INDEX idx_account_holder_party ON banking.account_holder(party_id);
CREATE INDEX idx_transaction_account_booking
    ON banking."transaction"(account_id, booking_time DESC);
CREATE INDEX idx_transaction_type_booking
    ON banking."transaction"(transaction_type, booking_time DESC);
CREATE INDEX idx_transaction_counterparty_hash
    ON banking."transaction"(counterparty_account_hash);
CREATE INDEX idx_transaction_booking_brin
    ON banking."transaction" USING BRIN(booking_time);
CREATE INDEX idx_monthly_summary_year_month
    ON banking.account_monthly_summary(year_month);
CREATE INDEX idx_credit_report_customer_date
    ON banking.credit_report(customer_id, report_as_of_date DESC);
CREATE INDEX idx_credit_facility_report ON banking.credit_facility(credit_report_id);

-- Object storage and upload coordination.
CREATE INDEX idx_object_metadata_active_location
    ON storage.object_metadata(bucket_name, object_key)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_object_metadata_sha256 ON storage.object_metadata(sha256);
CREATE INDEX idx_upload_session_customer_status
    ON storage.upload_session(customer_id, status, created_at DESC);
CREATE INDEX idx_upload_session_loan_application ON storage.upload_session(loan_application_id);
CREATE INDEX idx_upload_session_expiry ON storage.upload_session(expires_at)
    WHERE status IN ('CREATED', 'UPLOADING', 'UPLOADED', 'VERIFYING');
CREATE INDEX idx_upload_session_idempotency ON storage.upload_session(idempotency_key);
CREATE INDEX idx_retention_rule_resource_active
    ON storage.retention_rule(resource_type, is_active);
CREATE INDEX idx_resource_retention_resource
    ON storage.resource_retention(resource_type, resource_id);
CREATE INDEX idx_resource_retention_until ON storage.resource_retention(retention_until)
    WHERE legal_hold = FALSE;

-- Document processing and vector retrieval.
CREATE INDEX idx_document_owner ON document.document(owner_party_id);
CREATE INDEX idx_document_processing_status
    ON document.document(processing_status, verification_status);
CREATE INDEX idx_document_version_document ON document.document_version(document_id);
CREATE UNIQUE INDEX uq_document_current_version
    ON document.document_version(document_id)
    WHERE is_current;
CREATE INDEX idx_document_link_entity ON document.document_link(entity_type, entity_id);
CREATE INDEX idx_document_link_document ON document.document_link(document_id);
CREATE INDEX idx_processing_job_document_status
    ON document.processing_job(document_version_id, status);
CREATE INDEX idx_processing_job_correlation ON document.processing_job(correlation_id);
CREATE INDEX idx_document_page_object ON document.document_page(page_image_object_id);
CREATE INDEX idx_extracted_field_document_name
    ON document.extracted_field(document_version_id, field_name);
CREATE INDEX idx_extracted_field_verification
    ON document.extracted_field(verification_status);
CREATE INDEX idx_document_chunk_version ON document.document_chunk(document_version_id);
CREATE INDEX idx_document_chunk_metadata
    ON document.document_chunk USING GIN(metadata);
CREATE INDEX idx_document_chunk_embedding_hnsw
    ON document.document_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_document_issue_version_status
    ON document.document_issue(document_version_id, status);
CREATE INDEX idx_document_issue_field ON document.document_issue(field_id);

-- Credit workflow.
CREATE INDEX idx_loan_product_status_effective
    ON credit.loan_product(status, effective_from, effective_until);
CREATE INDEX idx_loan_application_customer
    ON credit.loan_application(primary_customer_id, created_at DESC);
CREATE INDEX idx_loan_application_assignee_status
    ON credit.loan_application(assigned_employee_id, status);
CREATE INDEX idx_loan_application_product ON credit.loan_application(product_id);
CREATE INDEX idx_loan_party_application ON credit.loan_party(loan_application_id);
CREATE INDEX idx_loan_party_party ON credit.loan_party(party_id);
CREATE INDEX idx_existing_obligation_application
    ON credit.existing_obligation(loan_application_id);
CREATE INDEX idx_existing_obligation_party ON credit.existing_obligation(party_id);
CREATE INDEX idx_collateral_application ON credit.collateral(loan_application_id);
CREATE INDEX idx_collateral_owner ON credit.collateral(owner_party_id);
CREATE INDEX idx_collateral_valuation_collateral
    ON credit.collateral_valuation(collateral_id, valuation_date DESC);
CREATE INDEX idx_loan_checklist_application_status
    ON credit.loan_checklist_item(loan_application_id, requirement_status);
CREATE INDEX idx_calculation_application_type
    ON credit.calculation_record(loan_application_id, calculation_type, calculated_at DESC);
CREATE INDEX idx_calculation_analysis_case ON credit.calculation_record(analysis_case_id);
CREATE INDEX idx_affordability_application
    ON credit.affordability_assessment(loan_application_id, calculated_at DESC);
CREATE INDEX idx_policy_check_application_status
    ON credit.policy_check(loan_application_id, status);
CREATE INDEX idx_policy_check_analysis_case ON credit.policy_check(analysis_case_id);
CREATE INDEX idx_approval_request_application
    ON credit.approval_request(loan_application_id, requested_at DESC);
CREATE INDEX idx_loan_decision_application
    ON credit.loan_decision(loan_application_id, decision_at DESC);
CREATE INDEX idx_disbursement_application ON credit.disbursement(loan_application_id);
CREATE INDEX idx_repayment_schedule_due
    ON credit.repayment_schedule(loan_account_id, due_date);
CREATE INDEX idx_loan_payment_account_date
    ON credit.loan_payment(loan_account_id, payment_date DESC);

-- Policy lookup and vector retrieval.
CREATE INDEX idx_policy_owner_department ON policy.policy(owner_department_id);
CREATE INDEX idx_policy_status ON policy.policy(status);
CREATE INDEX idx_policy_version_effective
    ON policy.policy_version(policy_id, effective_from, effective_until);
CREATE INDEX idx_policy_clause_embedding_hnsw
    ON policy.policy_clause USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_policy_clause_metadata ON policy.policy_clause USING GIN(metadata);
CREATE INDEX idx_checklist_rule_policy ON policy.checklist_rule(policy_version_id);
CREATE INDEX idx_checklist_requirement_rule
    ON policy.checklist_rule_requirement(checklist_rule_id);

-- AI analysis lineage.
CREATE INDEX idx_conversation_employee_started
    ON ai.conversation(employee_id, started_at DESC);
CREATE INDEX idx_conversation_customer ON ai.conversation(active_customer_id);
CREATE INDEX idx_message_conversation_created ON ai.message(conversation_id, created_at);
CREATE INDEX idx_message_parent ON ai.message(parent_message_id);
CREATE INDEX idx_analysis_case_customer_status
    ON ai.analysis_case(customer_id, status, created_at DESC);
CREATE INDEX idx_analysis_case_loan ON ai.analysis_case(loan_application_id);
CREATE INDEX idx_analysis_case_correlation ON ai.analysis_case(correlation_id);
CREATE INDEX idx_analysis_task_case_status ON ai.analysis_task(analysis_case_id, status);
CREATE INDEX idx_agent_run_case_status ON ai.agent_run(analysis_case_id, status);
CREATE INDEX idx_agent_run_task ON ai.agent_run(analysis_task_id);
CREATE INDEX idx_finding_case_severity ON ai.finding(analysis_case_id, severity);
CREATE INDEX idx_finding_agent_run ON ai.finding(agent_run_id);
CREATE INDEX idx_evidence_finding ON ai.evidence_link(finding_id);
CREATE INDEX idx_evidence_source ON ai.evidence_link(source_type, source_id);
CREATE INDEX idx_validation_case ON ai.validation_result(analysis_case_id);
CREATE INDEX idx_report_case_status ON ai.report(analysis_case_id, status);
CREATE INDEX idx_report_claim_report ON ai.report_claim(report_id);
CREATE INDEX idx_report_claim_evidence_link
    ON ai.report_claim_evidence(evidence_link_id);

-- Durable job, outbox, inbox, notification and audit access paths.
CREATE INDEX idx_background_job_status_schedule
    ON integration.background_job(status, scheduled_at, priority, created_at);
CREATE INDEX idx_background_job_resource
    ON integration.background_job(resource_type, resource_id);
CREATE INDEX idx_background_job_correlation ON integration.background_job(correlation_id);
CREATE INDEX idx_background_job_requested_by
    ON integration.background_job(requested_by, created_at DESC);
CREATE INDEX idx_background_job_step_job_order
    ON integration.background_job_step(job_id, step_order);
CREATE INDEX idx_job_event_job_created ON integration.job_event(job_id, created_at);
CREATE INDEX idx_event_outbox_pending
    ON integration.event_outbox(status, available_at, created_at);
CREATE INDEX idx_event_outbox_aggregate
    ON integration.event_outbox(aggregate_type, aggregate_id);
CREATE INDEX idx_event_inbox_status_received
    ON integration.event_inbox(consumer_name, status, received_at);
CREATE INDEX idx_idempotency_expiry ON integration.idempotency_record(expires_at);
CREATE INDEX idx_notification_employee_status
    ON integration.notification(employee_id, status, created_at DESC);
CREATE INDEX idx_audit_event_time_brin ON audit.audit_event USING BRIN(event_time);
CREATE INDEX idx_audit_event_actor ON audit.audit_event(actor_type, actor_id, event_time DESC);
CREATE INDEX idx_audit_event_resource
    ON audit.audit_event(resource_type, resource_id, event_time DESC);
CREATE INDEX idx_audit_event_customer ON audit.audit_event(customer_id, event_time DESC);
CREATE INDEX idx_audit_event_loan ON audit.audit_event(loan_application_id, event_time DESC);
CREATE INDEX idx_audit_event_correlation ON audit.audit_event(correlation_id);

