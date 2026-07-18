BEGIN;

INSERT INTO identity.branch (
    id, branch_code, branch_name, parent_branch_id, status, created_at, updated_at
)
VALUES
    ('30000000-0000-4000-8000-000000000001', 'HO', 'Trung tam Dieu hanh Mau', NULL, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('30000000-0000-4000-8000-000000000002', 'HN-DEMO', 'Chi nhanh Ha Noi Mau', '30000000-0000-4000-8000-000000000001', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('30000000-0000-4000-8000-000000000003', 'HCM-DEMO', 'Chi nhanh Thanh pho Ho Chi Minh Mau', '30000000-0000-4000-8000-000000000001', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET branch_code = EXCLUDED.branch_code,
    branch_name = EXCLUDED.branch_name,
    parent_branch_id = EXCLUDED.parent_branch_id,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO identity.department (
    id, department_code, department_name, branch_id, status, created_at, updated_at
)
VALUES
    ('31000000-0000-4000-8000-000000000001', 'CREDIT-DEMO', 'Phong Tin dung Mau', '30000000-0000-4000-8000-000000000002', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('31000000-0000-4000-8000-000000000002', 'DOCOPS-DEMO', 'Phong Van hanh Ho so Mau', '30000000-0000-4000-8000-000000000002', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('31000000-0000-4000-8000-000000000003', 'COMPLIANCE-DEMO', 'Phong Tuan thu Mau', '30000000-0000-4000-8000-000000000001', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('31000000-0000-4000-8000-000000000004', 'RISK-AUDIT-DEMO', 'Phong Rui ro va Kiem toan Mau', '30000000-0000-4000-8000-000000000001', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET department_code = EXCLUDED.department_code,
    department_name = EXCLUDED.department_name,
    branch_id = EXCLUDED.branch_id,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO identity.employee (
    id, identity_subject, employee_code, full_name, email, branch_id,
    department_id, job_title, manager_id, employment_status, last_synced_at,
    created_at, updated_at, version
)
VALUES
    ('10000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'EMP-DEMO-001', 'Can bo Tin dung Mau', 'credit.officer@example.local', '30000000-0000-4000-8000-000000000002', '31000000-0000-4000-8000-000000000001', 'Credit Officer', '10000000-0000-4000-8000-000000000002', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('10000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', 'EMP-DEMO-002', 'Quan ly Tin dung Mau', 'credit.manager@example.local', '30000000-0000-4000-8000-000000000002', '31000000-0000-4000-8000-000000000001', 'Credit Manager', NULL, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('10000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000003', 'EMP-DEMO-003', 'Chuyen vien Ho so Mau', 'document.reviewer@example.local', '30000000-0000-4000-8000-000000000002', '31000000-0000-4000-8000-000000000002', 'Document Reviewer', '10000000-0000-4000-8000-000000000002', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('10000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000004', 'EMP-DEMO-004', 'Chuyen vien Tuan thu Mau', 'compliance@example.local', '30000000-0000-4000-8000-000000000001', '31000000-0000-4000-8000-000000000003', 'Compliance Officer', NULL, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('10000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000005', 'EMP-DEMO-005', 'Nguoi Phe duyet Mau', 'approver@example.local', '30000000-0000-4000-8000-000000000001', '31000000-0000-4000-8000-000000000004', 'Loan Approver', NULL, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('10000000-0000-4000-8000-000000000006', '10000000-0000-4000-8000-000000000006', 'EMP-DEMO-006', 'Kiem toan vien Mau', 'auditor@example.local', '30000000-0000-4000-8000-000000000001', '31000000-0000-4000-8000-000000000004', 'Auditor', NULL, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1),
    ('10000000-0000-4000-8000-000000000007', '10000000-0000-4000-8000-000000000007', 'EMP-DEMO-007', 'Quan tri vien Mau', 'admin@example.local', '30000000-0000-4000-8000-000000000001', '31000000-0000-4000-8000-000000000002', 'Administrator', NULL, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO UPDATE
SET identity_subject = EXCLUDED.identity_subject,
    employee_code = EXCLUDED.employee_code,
    full_name = EXCLUDED.full_name,
    email = EXCLUDED.email,
    branch_id = EXCLUDED.branch_id,
    department_id = EXCLUDED.department_id,
    job_title = EXCLUDED.job_title,
    manager_id = EXCLUDED.manager_id,
    employment_status = EXCLUDED.employment_status,
    last_synced_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP,
    version = identity.employee.version + 1;

WITH assignments(id, employee_id, role_code) AS (
    VALUES
        ('32000000-0000-4000-8000-000000000001'::UUID, '10000000-0000-4000-8000-000000000001'::UUID, 'credit_officer'::CITEXT),
        ('32000000-0000-4000-8000-000000000002'::UUID, '10000000-0000-4000-8000-000000000002'::UUID, 'credit_manager'::CITEXT),
        ('32000000-0000-4000-8000-000000000003'::UUID, '10000000-0000-4000-8000-000000000003'::UUID, 'document_reviewer'::CITEXT),
        ('32000000-0000-4000-8000-000000000004'::UUID, '10000000-0000-4000-8000-000000000004'::UUID, 'compliance_officer'::CITEXT),
        ('32000000-0000-4000-8000-000000000005'::UUID, '10000000-0000-4000-8000-000000000005'::UUID, 'loan_approver'::CITEXT),
        ('32000000-0000-4000-8000-000000000006'::UUID, '10000000-0000-4000-8000-000000000006'::UUID, 'auditor'::CITEXT),
        ('32000000-0000-4000-8000-000000000007'::UUID, '10000000-0000-4000-8000-000000000007'::UUID, 'admin'::CITEXT)
)
INSERT INTO identity.employee_role (
    id, employee_id, role_id, valid_from, valid_until, assigned_by, created_at
)
SELECT
    assignments.id,
    assignments.employee_id,
    role.id,
    TIMESTAMPTZ '2026-01-01 00:00:00+00',
    NULL,
    '10000000-0000-4000-8000-000000000007',
    CURRENT_TIMESTAMP
FROM assignments
JOIN identity.role AS role
  ON role.role_code = assignments.role_code
ON CONFLICT (id) DO UPDATE
SET employee_id = EXCLUDED.employee_id,
    role_id = EXCLUDED.role_id,
    valid_from = EXCLUDED.valid_from,
    valid_until = EXCLUDED.valid_until,
    assigned_by = EXCLUDED.assigned_by;

INSERT INTO identity.employee_scope (
    id, employee_id, scope_type, scope_id, permission_code, valid_from,
    valid_until, assigned_by, reason, created_at
)
VALUES
    ('33000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'BRANCH', '30000000-0000-4000-8000-000000000002', 'customer:read', TIMESTAMPTZ '2026-01-01 00:00:00+00', NULL, '10000000-0000-4000-8000-000000000007', 'Demo branch access.', CURRENT_TIMESTAMP),
    ('33000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', 'BRANCH', '30000000-0000-4000-8000-000000000002', 'customer:read', TIMESTAMPTZ '2026-01-01 00:00:00+00', NULL, '10000000-0000-4000-8000-000000000007', 'Demo branch access.', CURRENT_TIMESTAMP),
    ('33000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000003', 'BRANCH', '30000000-0000-4000-8000-000000000002', 'customer:read', TIMESTAMPTZ '2026-01-01 00:00:00+00', NULL, '10000000-0000-4000-8000-000000000007', 'Demo document review access.', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET employee_id = EXCLUDED.employee_id,
    scope_type = EXCLUDED.scope_type,
    scope_id = EXCLUDED.scope_id,
    permission_code = EXCLUDED.permission_code,
    valid_from = EXCLUDED.valid_from,
    valid_until = EXCLUDED.valid_until,
    assigned_by = EXCLUDED.assigned_by,
    reason = EXCLUDED.reason;

INSERT INTO credit.loan_product (
    id, product_code, product_name, customer_type, loan_purpose,
    min_amount, max_amount, min_term_months, max_term_months, status,
    effective_from, effective_until, created_at, updated_at
)
VALUES (
    '40000000-0000-4000-8000-000000000001',
    'HOME-LOAN-DEMO',
    'San pham Vay mua nha Mau',
    'PERSON',
    'HOME_PURCHASE',
    100000000.0000,
    3000000000.0000,
    12,
    240,
    'ACTIVE',
    DATE '2026-01-01',
    NULL,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET product_code = EXCLUDED.product_code,
    product_name = EXCLUDED.product_name,
    customer_type = EXCLUDED.customer_type,
    loan_purpose = EXCLUDED.loan_purpose,
    min_amount = EXCLUDED.min_amount,
    max_amount = EXCLUDED.max_amount,
    min_term_months = EXCLUDED.min_term_months,
    max_term_months = EXCLUDED.max_term_months,
    status = EXCLUDED.status,
    effective_from = EXCLUDED.effective_from,
    effective_until = EXCLUDED.effective_until,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO storage.object_metadata (
    id, bucket_name, object_key, object_version_id, etag, sha256, size_bytes,
    mime_type, storage_class, encryption_type, retention_until, legal_hold,
    created_by, created_at, deleted_at
)
VALUES (
    '41000000-0000-4000-8000-000000000001',
    'policy-documents',
    'policies/43000000-0000-4000-8000-000000000001/43100000-0000-4000-8000-000000000001/original.pdf',
    NULL,
    'seed-policy-etag',
    repeat('a', 64),
    245760,
    'application/pdf',
    'STANDARD',
    'SSE-S3',
    NULL,
    FALSE,
    '10000000-0000-4000-8000-000000000007',
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
    storage_class = EXCLUDED.storage_class,
    encryption_type = EXCLUDED.encryption_type,
    deleted_at = NULL;

INSERT INTO document.document (
    id, document_type, document_subtype, title, owner_party_id,
    classification, document_date, valid_from, valid_until,
    verification_status, processing_status, created_by, created_at,
    updated_at, version
)
VALUES (
    '42000000-0000-4000-8000-000000000001',
    'CREDIT_POLICY',
    'RETAIL_HOME_LOAN',
    'Chinh sach Tin dung Mau',
    NULL,
    'INTERNAL',
    DATE '2026-01-01',
    DATE '2026-01-01',
    NULL,
    'VERIFIED',
    'COMPLETED',
    '10000000-0000-4000-8000-000000000007',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    1
)
ON CONFLICT (id) DO UPDATE
SET title = EXCLUDED.title,
    verification_status = EXCLUDED.verification_status,
    processing_status = EXCLUDED.processing_status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO document.document_version (
    id, document_id, version_number, original_object_id, original_filename,
    mime_type, file_size, sha256, uploaded_by, uploaded_at, scan_status,
    is_current, created_at
)
VALUES (
    '42100000-0000-4000-8000-000000000001',
    '42000000-0000-4000-8000-000000000001',
    1,
    '41000000-0000-4000-8000-000000000001',
    'credit-policy-demo-v1.pdf',
    'application/pdf',
    245760,
    repeat('a', 64),
    '10000000-0000-4000-8000-000000000007',
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

INSERT INTO policy.policy (
    id, policy_code, policy_name, policy_type, owner_department_id, status,
    created_at, updated_at
)
VALUES (
    '43000000-0000-4000-8000-000000000001',
    'RETAIL-CREDIT-DEMO',
    'Chinh sach Tin dung Ban le Mau',
    'CREDIT',
    '31000000-0000-4000-8000-000000000004',
    'ACTIVE',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET policy_code = EXCLUDED.policy_code,
    policy_name = EXCLUDED.policy_name,
    policy_type = EXCLUDED.policy_type,
    owner_department_id = EXCLUDED.owner_department_id,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO policy.policy_version (
    id, policy_id, version_number, effective_from, effective_until,
    approved_by, approved_at, source_document_id, status, created_at
)
VALUES (
    '43100000-0000-4000-8000-000000000001',
    '43000000-0000-4000-8000-000000000001',
    '1.0',
    DATE '2026-01-01',
    NULL,
    '10000000-0000-4000-8000-000000000005',
    TIMESTAMPTZ '2026-01-01 00:00:00+00',
    '42000000-0000-4000-8000-000000000001',
    'ACTIVE',
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET policy_id = EXCLUDED.policy_id,
    version_number = EXCLUDED.version_number,
    effective_from = EXCLUDED.effective_from,
    effective_until = EXCLUDED.effective_until,
    approved_by = EXCLUDED.approved_by,
    approved_at = EXCLUDED.approved_at,
    source_document_id = EXCLUDED.source_document_id,
    status = EXCLUDED.status;

INSERT INTO policy.policy_clause (
    id, policy_version_id, clause_number, title, content, page_number,
    embedding, metadata, created_at
)
VALUES
    ('43200000-0000-4000-8000-000000000001', '43100000-0000-4000-8000-000000000001', '4.1', 'Ho so thu nhap', 'Khach hang phai cung cap tai lieu chung minh thu nhap hop le.', 4, NULL, '{"category":"income"}'::jsonb, CURRENT_TIMESTAMP),
    ('43200000-0000-4000-8000-000000000002', '43100000-0000-4000-8000-000000000001', '5.2', 'Danh gia nghia vu no', 'Danh gia phai bao gom tat ca nghia vu tra no hang thang da xac minh.', 5, NULL, '{"category":"obligation"}'::jsonb, CURRENT_TIMESTAMP),
    ('43200000-0000-4000-8000-000000000003', '43100000-0000-4000-8000-000000000001', '7.1', 'Quyet dinh cua con nguoi', 'Quyet dinh tin dung cuoi cung phai do nguoi co tham quyen ghi nhan.', 7, NULL, '{"category":"approval"}'::jsonb, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET policy_version_id = EXCLUDED.policy_version_id,
    clause_number = EXCLUDED.clause_number,
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    page_number = EXCLUDED.page_number,
    metadata = EXCLUDED.metadata;

INSERT INTO policy.checklist_rule (
    id, policy_version_id, rule_code, rule_name, conditions, status, created_at
)
VALUES (
    '43300000-0000-4000-8000-000000000001',
    '43100000-0000-4000-8000-000000000001',
    'PERSONAL-INCOME-DOCS',
    'Ho so thu nhap ca nhan',
    '{"customer_type":"PERSON","required":true}'::jsonb,
    'ACTIVE',
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET policy_version_id = EXCLUDED.policy_version_id,
    rule_code = EXCLUDED.rule_code,
    rule_name = EXCLUDED.rule_name,
    conditions = EXCLUDED.conditions,
    status = EXCLUDED.status;

INSERT INTO policy.checklist_rule_requirement (
    id, checklist_rule_id, requirement_code, document_type, mandatory_level,
    requirement_description, created_at
)
VALUES
    ('43400000-0000-4000-8000-000000000001', '43300000-0000-4000-8000-000000000001', 'PAYSLIP-LATEST', 'PAYSLIP', 'MANDATORY', 'Phieu luong gan nhat.', CURRENT_TIMESTAMP),
    ('43400000-0000-4000-8000-000000000002', '43300000-0000-4000-8000-000000000001', 'BANK-STATEMENT-12M', 'BANK_STATEMENT', 'MANDATORY', 'Sao ke tai khoan trong 12 thang.', CURRENT_TIMESTAMP),
    ('43400000-0000-4000-8000-000000000003', '43300000-0000-4000-8000-000000000001', 'IDENTITY-DOC', 'IDENTITY_DOCUMENT', 'MANDATORY', 'Giay to dinh danh con hieu luc.', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET checklist_rule_id = EXCLUDED.checklist_rule_id,
    requirement_code = EXCLUDED.requirement_code,
    document_type = EXCLUDED.document_type,
    mandatory_level = EXCLUDED.mandatory_level,
    requirement_description = EXCLUDED.requirement_description;

INSERT INTO storage.retention_rule (
    id, rule_code, resource_type, retention_years, retention_days,
    start_event, description, is_active, created_at, updated_at
)
VALUES
    ('44000000-0000-4000-8000-000000000001', 'CUSTOMER-DOCUMENT-10Y', 'DOCUMENT', 10, NULL, 'CASE_CLOSED', 'Retain customer credit documents for ten years after case closure.', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('44000000-0000-4000-8000-000000000002', 'UPLOAD-QUARANTINE-7D', 'UPLOAD_SESSION', NULL, 7, 'UPLOAD_CREATED', 'Expire abandoned quarantine uploads after seven days.', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('44000000-0000-4000-8000-000000000003', 'AUDIT-ARCHIVE-10Y', 'AUDIT_EVENT', 10, NULL, 'EVENT_CREATED', 'Retain archived audit events for ten years.', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE
SET rule_code = EXCLUDED.rule_code,
    resource_type = EXCLUDED.resource_type,
    retention_years = EXCLUDED.retention_years,
    retention_days = EXCLUDED.retention_days,
    start_event = EXCLUDED.start_event,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = CURRENT_TIMESTAMP;

COMMIT;
