BEGIN;

INSERT INTO customer.party (
    id, party_type, display_name, status, created_at, created_by, updated_at,
    updated_by, version
)
VALUES
    ('50000000-0000-4000-8000-000000000001', 'PERSON', 'Khach hang Mau A', 'ACTIVE', CURRENT_TIMESTAMP, '10000000-0000-4000-8000-000000000001', CURRENT_TIMESTAMP, '10000000-0000-4000-8000-000000000001', 1),
    ('50000000-0000-4000-8000-000000000002', 'PERSON', 'Khach hang Mau B', 'ACTIVE', CURRENT_TIMESTAMP, '10000000-0000-4000-8000-000000000001', CURRENT_TIMESTAMP, '10000000-0000-4000-8000-000000000001', 1),
    ('50000000-0000-4000-8000-000000000003', 'PERSON', 'Khach hang Mau C', 'ACTIVE', CURRENT_TIMESTAMP, '10000000-0000-4000-8000-000000000007', CURRENT_TIMESTAMP, '10000000-0000-4000-8000-000000000007', 1)
ON CONFLICT (id) DO UPDATE
SET party_type = EXCLUDED.party_type,
    display_name = EXCLUDED.display_name,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP,
    updated_by = EXCLUDED.updated_by,
    version = customer.party.version + 1;

INSERT INTO customer.person_profile (
    party_id, full_name, date_of_birth, gender, nationality, marital_status,
    occupation, updated_at
)
VALUES
    ('50000000-0000-4000-8000-000000000001', 'Khach hang Mau A', DATE '1988-04-15', 'UNSPECIFIED', 'VN', 'MARRIED', 'Nhan vien van phong mau', CURRENT_TIMESTAMP),
    ('50000000-0000-4000-8000-000000000002', 'Khach hang Mau B', DATE '1991-09-20', 'UNSPECIFIED', 'VN', 'SINGLE', 'Ky su mau', CURRENT_TIMESTAMP),
    ('50000000-0000-4000-8000-000000000003', 'Khach hang Mau C', DATE '1985-02-10', 'UNSPECIFIED', 'VN', 'MARRIED', 'Quan ly kinh doanh mau', CURRENT_TIMESTAMP)
ON CONFLICT (party_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
    date_of_birth = EXCLUDED.date_of_birth,
    gender = EXCLUDED.gender,
    nationality = EXCLUDED.nationality,
    marital_status = EXCLUDED.marital_status,
    occupation = EXCLUDED.occupation,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO customer.customer (
    id, party_id, customer_number, customer_segment, home_branch_id,
    relationship_manager_id, onboarding_date, kyc_status, risk_rating,
    risk_rating_as_of, status, created_at, updated_at, version
)
VALUES
    ('51000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', 'CIF-DEMO-001', 'MASS_AFFLUENT', '30000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', DATE '2024-01-10', 'VERIFIED', 'MEDIUM', CURRENT_DATE, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('51000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000002', 'CIF-DEMO-002', 'MASS', '30000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', DATE '2024-03-15', 'VERIFIED', 'LOW', CURRENT_DATE, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('51000000-0000-4000-8000-000000000003', '50000000-0000-4000-8000-000000000003', 'CIF-DEMO-003', 'AFFLUENT', '30000000-0000-4000-8000-000000000003', NULL, DATE '2023-11-05', 'VERIFIED', 'LOW', CURRENT_DATE, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO UPDATE
SET party_id = EXCLUDED.party_id,
    customer_number = EXCLUDED.customer_number,
    customer_segment = EXCLUDED.customer_segment,
    home_branch_id = EXCLUDED.home_branch_id,
    relationship_manager_id = EXCLUDED.relationship_manager_id,
    kyc_status = EXCLUDED.kyc_status,
    risk_rating = EXCLUDED.risk_rating,
    risk_rating_as_of = EXCLUDED.risk_rating_as_of,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP,
    version = customer.customer.version + 1;

INSERT INTO customer.kyc_assessment (
    id, customer_id, assessment_date, kyc_status, aml_risk_level, pep_status,
    sanction_status, beneficial_owner_verified, source_system,
    assessment_payload, assessed_by, created_at
)
VALUES
    ('51100000-0000-4000-8000-000000000001', '51000000-0000-4000-8000-000000000001', CURRENT_TIMESTAMP, 'VERIFIED', 'MEDIUM', 'NOT_PEP', 'CLEAR', TRUE, 'DEMO_SEED', '{"synthetic":true}'::jsonb, '10000000-0000-4000-8000-000000000001', CURRENT_TIMESTAMP),
    ('51100000-0000-4000-8000-000000000002', '51000000-0000-4000-8000-000000000002', CURRENT_TIMESTAMP, 'VERIFIED', 'LOW', 'NOT_PEP', 'CLEAR', TRUE, 'DEMO_SEED', '{"synthetic":true}'::jsonb, '10000000-0000-4000-8000-000000000001', CURRENT_TIMESTAMP),
    ('51100000-0000-4000-8000-000000000003', '51000000-0000-4000-8000-000000000003', CURRENT_TIMESTAMP, 'VERIFIED', 'LOW', 'NOT_PEP', 'CLEAR', TRUE, 'DEMO_SEED', '{"synthetic":true}'::jsonb, '10000000-0000-4000-8000-000000000007', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET assessment_date = CURRENT_TIMESTAMP,
    kyc_status = EXCLUDED.kyc_status,
    aml_risk_level = EXCLUDED.aml_risk_level,
    pep_status = EXCLUDED.pep_status,
    sanction_status = EXCLUDED.sanction_status,
    beneficial_owner_verified = EXCLUDED.beneficial_owner_verified,
    assessment_payload = EXCLUDED.assessment_payload,
    assessed_by = EXCLUDED.assessed_by;

INSERT INTO storage.object_metadata (
    id, bucket_name, object_key, object_version_id, etag, sha256, size_bytes,
    mime_type, storage_class, encryption_type, retention_until, legal_hold,
    created_by, created_at, deleted_at
)
VALUES (
    '52000000-0000-4000-8000-000000000001',
    'customer-doc-original',
    'documents/52100000-0000-4000-8000-000000000001/versions/52200000-0000-4000-8000-000000000001/original',
    NULL,
    'seed-payslip-etag',
    repeat('b', 64),
    131072,
    'application/pdf',
    'STANDARD',
    'SSE-S3',
    NULL,
    FALSE,
    '10000000-0000-4000-8000-000000000001',
    CURRENT_TIMESTAMP,
    NULL
)
ON CONFLICT (id) DO UPDATE
SET bucket_name = EXCLUDED.bucket_name,
    object_key = EXCLUDED.object_key,
    object_version_id = EXCLUDED.object_version_id,
    etag = EXCLUDED.etag,
    sha256 = EXCLUDED.sha256,
    size_bytes = EXCLUDED.size_bytes,
    mime_type = EXCLUDED.mime_type,
    encryption_type = EXCLUDED.encryption_type,
    deleted_at = NULL;

INSERT INTO document.document (
    id, document_type, document_subtype, title, owner_party_id,
    classification, document_date, valid_from, valid_until,
    verification_status, processing_status, created_by, created_at,
    updated_at, version
)
VALUES (
    '52100000-0000-4000-8000-000000000001',
    'PAYSLIP',
    'MONTHLY_PAYSLIP',
    'Phieu luong Mau',
    '50000000-0000-4000-8000-000000000001',
    'CONFIDENTIAL',
    CURRENT_DATE - INTERVAL '1 month',
    NULL,
    NULL,
    'VERIFIED',
    'COMPLETED',
    '10000000-0000-4000-8000-000000000001',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    1
)
ON CONFLICT (id) DO UPDATE
SET owner_party_id = EXCLUDED.owner_party_id,
    document_date = EXCLUDED.document_date,
    verification_status = EXCLUDED.verification_status,
    processing_status = EXCLUDED.processing_status,
    updated_at = CURRENT_TIMESTAMP,
    version = document.document.version + 1;

INSERT INTO document.document_version (
    id, document_id, version_number, original_object_id, original_filename,
    mime_type, file_size, sha256, uploaded_by, uploaded_at, scan_status,
    is_current, created_at
)
VALUES (
    '52200000-0000-4000-8000-000000000001',
    '52100000-0000-4000-8000-000000000001',
    1,
    '52000000-0000-4000-8000-000000000001',
    'payslip-demo.pdf',
    'application/pdf',
    131072,
    repeat('b', 64),
    '10000000-0000-4000-8000-000000000001',
    CURRENT_TIMESTAMP,
    'CLEAN',
    TRUE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET original_object_id = EXCLUDED.original_object_id,
    original_filename = EXCLUDED.original_filename,
    mime_type = EXCLUDED.mime_type,
    file_size = EXCLUDED.file_size,
    sha256 = EXCLUDED.sha256,
    scan_status = EXCLUDED.scan_status,
    is_current = TRUE;

INSERT INTO document.extracted_field (
    id, document_version_id, field_name, value_type, ocr_value_text,
    normalized_value_text, corrected_value_text, value_number, value_date,
    page_number, bounding_box, source_text, confidence, verification_status,
    verified_by, verified_at, verification_reason, created_at, updated_at
)
VALUES (
    '52300000-0000-4000-8000-000000000001',
    '52200000-0000-4000-8000-000000000001',
    'net_monthly_salary',
    'MONEY',
    '28.000.000 VND',
    '28000000.0000',
    NULL,
    28000000.0000,
    NULL,
    1,
    '{"x":0.52,"y":0.42,"width":0.23,"height":0.04}'::jsonb,
    'Thu nhap thuc nhan: 28.000.000 VND',
    0.99000,
    'VERIFIED',
    '10000000-0000-4000-8000-000000000003',
    CURRENT_TIMESTAMP,
    'Synthetic payslip field checked for the demo.',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET ocr_value_text = EXCLUDED.ocr_value_text,
    normalized_value_text = EXCLUDED.normalized_value_text,
    value_number = EXCLUDED.value_number,
    confidence = EXCLUDED.confidence,
    verification_status = EXCLUDED.verification_status,
    verified_by = EXCLUDED.verified_by,
    verified_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO document.document_link (
    id, document_id, entity_type, entity_id, relationship_type, created_at
)
VALUES (
    '52400000-0000-4000-8000-000000000001',
    '52100000-0000-4000-8000-000000000001',
    'CUSTOMER',
    '51000000-0000-4000-8000-000000000001',
    'INCOME_EVIDENCE',
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET document_id = EXCLUDED.document_id,
    entity_type = EXCLUDED.entity_type,
    entity_id = EXCLUDED.entity_id,
    relationship_type = EXCLUDED.relationship_type;

INSERT INTO customer.employment (
    id, party_id, employer_name, position, employment_type, start_date,
    end_date, declared_monthly_income, currency, verification_status,
    source_document_id, created_at, updated_at, version
)
VALUES
    ('53000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', 'Cong ty Gia lap Alpha', 'Chuyen vien Mau', 'FULL_TIME', DATE '2020-01-01', NULL, 30000000.0000, 'VND', 'PARTIALLY_VERIFIED', '52100000-0000-4000-8000-000000000001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('53000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000002', 'Cong ty Gia lap Beta', 'Ky su Mau', 'FULL_TIME', DATE '2021-03-01', NULL, 18000000.0000, 'VND', 'VERIFIED', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('53000000-0000-4000-8000-000000000003', '50000000-0000-4000-8000-000000000003', 'Cong ty Gia lap Gamma', 'Quan ly Mau', 'FULL_TIME', DATE '2018-06-01', NULL, 35000000.0000, 'VND', 'VERIFIED', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO UPDATE
SET employer_name = EXCLUDED.employer_name,
    position = EXCLUDED.position,
    employment_type = EXCLUDED.employment_type,
    declared_monthly_income = EXCLUDED.declared_monthly_income,
    currency = EXCLUDED.currency,
    verification_status = EXCLUDED.verification_status,
    source_document_id = EXCLUDED.source_document_id,
    updated_at = CURRENT_TIMESTAMP,
    version = customer.employment.version + 1;

INSERT INTO customer.income_source (
    id, party_id, income_type, declared_amount, verified_amount,
    accepted_amount, frequency, currency, as_of_date, verification_method,
    verification_status, source_document_id, source_calculation_id,
    created_at, updated_at, version
)
VALUES
    ('54000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', 'SALARY', 30000000.0000, 28000000.0000, 22000000.0000, 'MONTHLY', 'VND', CURRENT_DATE, 'PAYSLIP_AND_BANK_TRANSACTION', 'VERIFIED_WITH_VARIANCE', '52100000-0000-4000-8000-000000000001', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('54000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000002', 'SALARY', 18000000.0000, 18000000.0000, 18000000.0000, 'MONTHLY', 'VND', CURRENT_DATE, 'BANK_TRANSACTION', 'VERIFIED', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('54000000-0000-4000-8000-000000000003', '50000000-0000-4000-8000-000000000003', 'SALARY', 35000000.0000, 35000000.0000, 35000000.0000, 'MONTHLY', 'VND', CURRENT_DATE, 'BANK_TRANSACTION', 'VERIFIED', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO UPDATE
SET declared_amount = EXCLUDED.declared_amount,
    verified_amount = EXCLUDED.verified_amount,
    accepted_amount = EXCLUDED.accepted_amount,
    as_of_date = EXCLUDED.as_of_date,
    verification_method = EXCLUDED.verification_method,
    verification_status = EXCLUDED.verification_status,
    source_document_id = EXCLUDED.source_document_id,
    updated_at = CURRENT_TIMESTAMP,
    version = customer.income_source.version + 1;

INSERT INTO banking.account (
    id, account_number_masked, account_number_hash, account_type, currency,
    branch_id, status, opened_at, closed_at, current_balance, balance_as_of,
    created_at, updated_at, version
)
VALUES
    ('60000000-0000-4000-8000-000000000001', '******1001', repeat('1', 64), 'PAYMENT', 'VND', '30000000-0000-4000-8000-000000000002', 'ACTIVE', TIMESTAMPTZ '2024-01-10 00:00:00+00', NULL, 45200000.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('60000000-0000-4000-8000-000000000002', '******1002', repeat('2', 64), 'SAVINGS', 'VND', '30000000-0000-4000-8000-000000000002', 'ACTIVE', TIMESTAMPTZ '2024-01-10 00:00:00+00', NULL, 120000000.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('60000000-0000-4000-8000-000000000003', '******2001', repeat('3', 64), 'PAYMENT', 'VND', '30000000-0000-4000-8000-000000000002', 'ACTIVE', TIMESTAMPTZ '2024-03-15 00:00:00+00', NULL, 19500000.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('60000000-0000-4000-8000-000000000004', '******2002', repeat('4', 64), 'SAVINGS', 'VND', '30000000-0000-4000-8000-000000000002', 'ACTIVE', TIMESTAMPTZ '2024-03-15 00:00:00+00', NULL, 68000000.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('60000000-0000-4000-8000-000000000005', '******3001', repeat('5', 64), 'PAYMENT', 'VND', '30000000-0000-4000-8000-000000000003', 'ACTIVE', TIMESTAMPTZ '2023-11-05 00:00:00+00', NULL, 71000000.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('60000000-0000-4000-8000-000000000006', '******3002', repeat('6', 64), 'SAVINGS', 'VND', '30000000-0000-4000-8000-000000000003', 'ACTIVE', TIMESTAMPTZ '2023-11-05 00:00:00+00', NULL, 240000000.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO UPDATE
SET account_number_masked = EXCLUDED.account_number_masked,
    account_number_hash = EXCLUDED.account_number_hash,
    account_type = EXCLUDED.account_type,
    currency = EXCLUDED.currency,
    branch_id = EXCLUDED.branch_id,
    status = EXCLUDED.status,
    current_balance = EXCLUDED.current_balance,
    balance_as_of = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP,
    version = banking.account.version + 1;

INSERT INTO banking.account_holder (
    id, account_id, party_id, holder_role, valid_from, valid_until, created_at
)
VALUES
    ('61000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', 'PRIMARY', DATE '2024-01-10', NULL, CURRENT_TIMESTAMP),
    ('61000000-0000-4000-8000-000000000002', '60000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000001', 'PRIMARY', DATE '2024-01-10', NULL, CURRENT_TIMESTAMP),
    ('61000000-0000-4000-8000-000000000003', '60000000-0000-4000-8000-000000000003', '50000000-0000-4000-8000-000000000002', 'PRIMARY', DATE '2024-03-15', NULL, CURRENT_TIMESTAMP),
    ('61000000-0000-4000-8000-000000000004', '60000000-0000-4000-8000-000000000004', '50000000-0000-4000-8000-000000000002', 'PRIMARY', DATE '2024-03-15', NULL, CURRENT_TIMESTAMP),
    ('61000000-0000-4000-8000-000000000005', '60000000-0000-4000-8000-000000000005', '50000000-0000-4000-8000-000000000003', 'PRIMARY', DATE '2023-11-05', NULL, CURRENT_TIMESTAMP),
    ('61000000-0000-4000-8000-000000000006', '60000000-0000-4000-8000-000000000006', '50000000-0000-4000-8000-000000000003', 'PRIMARY', DATE '2023-11-05', NULL, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET account_id = EXCLUDED.account_id,
    party_id = EXCLUDED.party_id,
    holder_role = EXCLUDED.holder_role,
    valid_from = EXCLUDED.valid_from,
    valid_until = EXCLUDED.valid_until;

INSERT INTO credit.loan_application (
    id, application_number, primary_customer_id, product_id, requested_amount,
    currency, requested_term_months, loan_purpose, interest_rate_assumption,
    repayment_method, status, assigned_employee_id, submitted_at, created_at,
    created_by, updated_at, updated_by, version
)
VALUES (
    '70000000-0000-4000-8000-000000000001',
    'LA-DEMO-700M-001',
    '51000000-0000-4000-8000-000000000001',
    '40000000-0000-4000-8000-000000000001',
    700000000.0000,
    'VND',
    60,
    'HOME_PURCHASE',
    0.08500000,
    'EQUAL_PRINCIPAL',
    'UNDER_ANALYSIS',
    '10000000-0000-4000-8000-000000000001',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    '10000000-0000-4000-8000-000000000001',
    CURRENT_TIMESTAMP,
    '10000000-0000-4000-8000-000000000001',
    1
)
ON CONFLICT (id) DO UPDATE
SET application_number = EXCLUDED.application_number,
    primary_customer_id = EXCLUDED.primary_customer_id,
    product_id = EXCLUDED.product_id,
    requested_amount = EXCLUDED.requested_amount,
    currency = EXCLUDED.currency,
    requested_term_months = EXCLUDED.requested_term_months,
    loan_purpose = EXCLUDED.loan_purpose,
    interest_rate_assumption = EXCLUDED.interest_rate_assumption,
    repayment_method = EXCLUDED.repayment_method,
    assigned_employee_id = EXCLUDED.assigned_employee_id,
    updated_at = CURRENT_TIMESTAMP,
    updated_by = EXCLUDED.updated_by,
    version = credit.loan_application.version + 1;

INSERT INTO credit.loan_party (
    id, loan_application_id, party_id, party_role, created_at
)
VALUES (
    '71000000-0000-4000-8000-000000000001',
    '70000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000001',
    'PRIMARY_BORROWER',
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET loan_application_id = EXCLUDED.loan_application_id,
    party_id = EXCLUDED.party_id,
    party_role = EXCLUDED.party_role;

INSERT INTO credit.existing_obligation (
    id, loan_application_id, party_id, lender_name, obligation_type,
    outstanding_balance, monthly_payment, credit_limit, currency,
    verified_status, source_type, source_id, as_of_date, created_at
)
VALUES (
    '72000000-0000-4000-8000-000000000001',
    '70000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000001',
    'Ngan hang Gia lap Delta',
    'PERSONAL_LOAN',
    180000000.0000,
    6000000.0000,
    NULL,
    'VND',
    'VERIFIED',
    'CREDIT_REPORT',
    NULL,
    CURRENT_DATE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET outstanding_balance = EXCLUDED.outstanding_balance,
    monthly_payment = EXCLUDED.monthly_payment,
    verified_status = EXCLUDED.verified_status,
    as_of_date = EXCLUDED.as_of_date;

INSERT INTO credit.loan_checklist_item (
    id, loan_application_id, requirement_code, document_type,
    requirement_status, mandatory_level, source_policy_clause_id,
    linked_document_id, waived_by, waiver_reason, created_at, updated_at
)
VALUES
    ('73000000-0000-4000-8000-000000000001', '70000000-0000-4000-8000-000000000001', 'PAYSLIP-LATEST', 'PAYSLIP', 'VALID', 'MANDATORY', '43200000-0000-4000-8000-000000000001', '52100000-0000-4000-8000-000000000001', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('73000000-0000-4000-8000-000000000002', '70000000-0000-4000-8000-000000000001', 'BANK-STATEMENT-12M', 'BANK_STATEMENT', 'RECEIVED', 'MANDATORY', '43200000-0000-4000-8000-000000000001', NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('73000000-0000-4000-8000-000000000003', '70000000-0000-4000-8000-000000000001', 'IDENTITY-DOC', 'IDENTITY_DOCUMENT', 'REQUIRED', 'MANDATORY', '43200000-0000-4000-8000-000000000001', NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET requirement_status = EXCLUDED.requirement_status,
    mandatory_level = EXCLUDED.mandatory_level,
    source_policy_clause_id = EXCLUDED.source_policy_clause_id,
    linked_document_id = EXCLUDED.linked_document_id,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO document.document_link (
    id, document_id, entity_type, entity_id, relationship_type, created_at
)
VALUES (
    '52400000-0000-4000-8000-000000000002',
    '52100000-0000-4000-8000-000000000001',
    'LOAN_APPLICATION',
    '70000000-0000-4000-8000-000000000001',
    'INCOME_EVIDENCE',
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET document_id = EXCLUDED.document_id,
    entity_type = EXCLUDED.entity_type,
    entity_id = EXCLUDED.entity_id,
    relationship_type = EXCLUDED.relationship_type;

INSERT INTO integration.background_job (
    id, job_type, resource_type, resource_id, status, progress_percent,
    current_step, correlation_id, requested_by, priority, attempt_count,
    max_attempts, scheduled_at, started_at, completed_at, error_code,
    error_message_safe, result_reference_type, result_reference_id,
    created_at, updated_at, version
)
VALUES (
    '80000000-0000-4000-8000-000000000001',
    'LOAN_ANALYSIS',
    'LOAN_APPLICATION',
    '70000000-0000-4000-8000-000000000001',
    'QUEUED',
    0,
    'AWAITING_PUBLICATION',
    '80100000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000001',
    5,
    0,
    5,
    CURRENT_TIMESTAMP,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    1
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO integration.event_outbox (
    id, aggregate_type, aggregate_id, event_type, event_version,
    partition_key, payload, headers, status, attempt_count, available_at,
    locked_at, locked_by, published_at, last_error, created_at
)
VALUES (
    '81000000-0000-4000-8000-000000000001',
    'LOAN_APPLICATION',
    '70000000-0000-4000-8000-000000000001',
    'analysis.requested',
    1,
    '70000000-0000-4000-8000-000000000001',
    jsonb_build_object(
        'event_id', '81000000-0000-4000-8000-000000000001',
        'event_type', 'analysis.requested',
        'event_version', 1,
        'occurred_at', to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
        'producer', 'bank-api',
        'correlation_id', '80100000-0000-4000-8000-000000000001',
        'causation_id', NULL,
        'partition_key', '70000000-0000-4000-8000-000000000001',
        'actor', jsonb_build_object(
            'type', 'EMPLOYEE',
            'id', '10000000-0000-4000-8000-000000000001'
        ),
        'resource', jsonb_build_object(
            'type', 'LOAN_APPLICATION',
            'id', '70000000-0000-4000-8000-000000000001'
        ),
        'payload', jsonb_build_object(
            'job_id', '80000000-0000-4000-8000-000000000001'
        ),
        'metadata', jsonb_build_object(
            'trace_id', '80100000-0000-4000-8000-000000000001',
            'schema', 'analysis.requested.v1'
        )
    ),
    '{"topic":"bank.analysis.commands.v1"}'::jsonb,
    'PENDING',
    0,
    CURRENT_TIMESTAMP,
    NULL,
    NULL,
    NULL,
    NULL,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
