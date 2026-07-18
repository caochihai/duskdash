BEGIN;

INSERT INTO identity.role (
    id, role_code, role_name, description, is_system_role, created_at
)
VALUES
    ('20000000-0000-4000-8000-000000000001', 'credit_officer', 'Credit Officer', 'Creates and analyzes credit applications.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000002', 'credit_manager', 'Credit Manager', 'Reviews credit work and manages a credit team.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000003', 'document_reviewer', 'Document Reviewer', 'Reviews and verifies submitted documents.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000004', 'compliance_officer', 'Compliance Officer', 'Performs policy and compliance review.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000005', 'risk_officer', 'Risk Officer', 'Reviews risk analysis and policy exceptions.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000006', 'loan_approver', 'Loan Approver', 'Records authorized human loan decisions.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000007', 'auditor', 'Auditor', 'Reads masked reporting and audit information.', TRUE, CURRENT_TIMESTAMP),
    ('20000000-0000-4000-8000-000000000008', 'admin', 'Administrator', 'Manages infrastructure-facing application configuration.', TRUE, CURRENT_TIMESTAMP)
ON CONFLICT (role_code) DO UPDATE
SET role_name = EXCLUDED.role_name,
    description = EXCLUDED.description,
    is_system_role = EXCLUDED.is_system_role;

INSERT INTO identity.permission (
    id, permission_code, resource_type, action, description, created_at
)
VALUES
    ('21000000-0000-4000-8000-000000000001', 'customer:read', 'customer', 'read', 'Read an authorized customer.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000002', 'customer:search', 'customer', 'search', 'Search customers within authorized scope.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000003', 'account:read', 'account', 'read', 'Read an authorized masked account.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000004', 'transaction:read', 'transaction', 'read', 'Read authorized account transactions.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000005', 'document:read', 'document', 'read', 'Read authorized document metadata.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000006', 'document:upload', 'document', 'upload', 'Create an upload session.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000007', 'document:download', 'document', 'download', 'Request an authorized download.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000008', 'document:verify', 'document', 'verify', 'Verify extracted document data.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000009', 'loan:read', 'loan', 'read', 'Read an authorized loan application.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000010', 'loan:create', 'loan', 'create', 'Create a loan application.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000011', 'loan:update', 'loan', 'update', 'Update an authorized loan application.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000012', 'loan:analyze', 'loan', 'analyze', 'Request analysis for a loan application.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000013', 'loan:submit', 'loan', 'submit', 'Submit a loan application for approval.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000014', 'loan:approve', 'loan', 'approve', 'Record an authorized human loan decision.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000015', 'policy:read', 'policy', 'read', 'Read effective policy clauses.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000016', 'report:read', 'report', 'read', 'Read an authorized report.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000017', 'report:generate', 'report', 'generate', 'Request report generation.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000018', 'report:review', 'report', 'review', 'Review an analysis report.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000019', 'report:export', 'report', 'export', 'Export an authorized report.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000020', 'audit:read', 'audit', 'read', 'Read audit records through approved access paths.', CURRENT_TIMESTAMP),
    ('21000000-0000-4000-8000-000000000021', 'admin:manage', 'admin', 'manage', 'Manage application authorization and reference data.', CURRENT_TIMESTAMP)
ON CONFLICT (permission_code) DO UPDATE
SET resource_type = EXCLUDED.resource_type,
    action = EXCLUDED.action,
    description = EXCLUDED.description;

WITH assignments(role_code, permission_code) AS (
    VALUES
        ('credit_officer', 'customer:read'),
        ('credit_officer', 'customer:search'),
        ('credit_officer', 'account:read'),
        ('credit_officer', 'transaction:read'),
        ('credit_officer', 'document:read'),
        ('credit_officer', 'document:upload'),
        ('credit_officer', 'document:download'),
        ('credit_officer', 'loan:read'),
        ('credit_officer', 'loan:create'),
        ('credit_officer', 'loan:update'),
        ('credit_officer', 'loan:analyze'),
        ('credit_officer', 'loan:submit'),
        ('credit_officer', 'policy:read'),
        ('credit_officer', 'report:read'),
        ('credit_officer', 'report:generate'),
        ('credit_manager', 'customer:read'),
        ('credit_manager', 'customer:search'),
        ('credit_manager', 'account:read'),
        ('credit_manager', 'transaction:read'),
        ('credit_manager', 'document:read'),
        ('credit_manager', 'document:download'),
        ('credit_manager', 'loan:read'),
        ('credit_manager', 'loan:update'),
        ('credit_manager', 'loan:analyze'),
        ('credit_manager', 'loan:submit'),
        ('credit_manager', 'policy:read'),
        ('credit_manager', 'report:read'),
        ('credit_manager', 'report:generate'),
        ('credit_manager', 'report:review'),
        ('credit_manager', 'report:export'),
        ('document_reviewer', 'customer:read'),
        ('document_reviewer', 'document:read'),
        ('document_reviewer', 'document:download'),
        ('document_reviewer', 'document:verify'),
        ('document_reviewer', 'loan:read'),
        ('compliance_officer', 'customer:read'),
        ('compliance_officer', 'document:read'),
        ('compliance_officer', 'document:download'),
        ('compliance_officer', 'document:verify'),
        ('compliance_officer', 'loan:read'),
        ('compliance_officer', 'loan:analyze'),
        ('compliance_officer', 'policy:read'),
        ('compliance_officer', 'report:read'),
        ('compliance_officer', 'report:review'),
        ('risk_officer', 'customer:read'),
        ('risk_officer', 'account:read'),
        ('risk_officer', 'transaction:read'),
        ('risk_officer', 'document:read'),
        ('risk_officer', 'loan:read'),
        ('risk_officer', 'loan:analyze'),
        ('risk_officer', 'policy:read'),
        ('risk_officer', 'report:read'),
        ('risk_officer', 'report:review'),
        ('loan_approver', 'customer:read'),
        ('loan_approver', 'account:read'),
        ('loan_approver', 'transaction:read'),
        ('loan_approver', 'document:read'),
        ('loan_approver', 'document:download'),
        ('loan_approver', 'loan:read'),
        ('loan_approver', 'loan:approve'),
        ('loan_approver', 'policy:read'),
        ('loan_approver', 'report:read'),
        ('loan_approver', 'report:review'),
        ('loan_approver', 'report:export'),
        ('auditor', 'customer:read'),
        ('auditor', 'account:read'),
        ('auditor', 'transaction:read'),
        ('auditor', 'document:read'),
        ('auditor', 'loan:read'),
        ('auditor', 'policy:read'),
        ('auditor', 'report:read'),
        ('auditor', 'report:export'),
        ('auditor', 'audit:read')
),
resolved AS (
    SELECT role.id AS role_id, permission.id AS permission_id
    FROM assignments
    JOIN identity.role AS role
      ON role.role_code = assignments.role_code
    JOIN identity.permission AS permission
      ON permission.permission_code = assignments.permission_code
)
INSERT INTO identity.role_permission(role_id, permission_id, created_at)
SELECT role_id, permission_id, CURRENT_TIMESTAMP
FROM resolved
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO identity.role_permission(role_id, permission_id, created_at)
SELECT role.id, permission.id, CURRENT_TIMESTAMP
FROM identity.role AS role
CROSS JOIN identity.permission AS permission
WHERE role.role_code = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;
