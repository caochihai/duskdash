CREATE TABLE identity.branch (
    id UUID PRIMARY KEY,
    branch_code CITEXT NOT NULL UNIQUE,
    branch_name TEXT NOT NULL,
    parent_branch_id UUID NULL REFERENCES identity.branch(id),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_branch_status CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT ck_branch_not_own_parent CHECK (parent_branch_id IS NULL OR parent_branch_id <> id)
);

CREATE TABLE identity.department (
    id UUID PRIMARY KEY,
    department_code CITEXT NOT NULL UNIQUE,
    department_name TEXT NOT NULL,
    branch_id UUID NULL REFERENCES identity.branch(id),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE identity.employee (
    id UUID PRIMARY KEY,
    identity_subject CITEXT NOT NULL UNIQUE,
    employee_code CITEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    email CITEXT NOT NULL UNIQUE,
    branch_id UUID NOT NULL REFERENCES identity.branch(id),
    department_id UUID NOT NULL REFERENCES identity.department(id),
    job_title TEXT NULL,
    manager_id UUID NULL REFERENCES identity.employee(id),
    employment_status VARCHAR(20) NOT NULL,
    last_synced_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_employee_not_own_manager CHECK (manager_id IS NULL OR manager_id <> id),
    CONSTRAINT ck_employee_version_positive CHECK (version > 0)
);

CREATE TABLE identity.role (
    id UUID PRIMARY KEY,
    role_code CITEXT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    description TEXT NULL,
    is_system_role BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE identity.permission (
    id UUID PRIMARY KEY,
    permission_code CITEXT NOT NULL UNIQUE,
    resource_type VARCHAR(50) NOT NULL,
    action VARCHAR(30) NOT NULL,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE identity.role_permission (
    role_id UUID NOT NULL REFERENCES identity.role(id),
    permission_id UUID NOT NULL REFERENCES identity.permission(id),
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE identity.employee_role (
    id UUID PRIMARY KEY,
    employee_id UUID NOT NULL REFERENCES identity.employee(id),
    role_id UUID NOT NULL REFERENCES identity.role(id),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NULL,
    assigned_by UUID NULL REFERENCES identity.employee(id),
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_employee_role_validity CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE TABLE identity.employee_scope (
    id UUID PRIMARY KEY,
    employee_id UUID NOT NULL REFERENCES identity.employee(id),
    scope_type VARCHAR(30) NOT NULL,
    scope_id UUID NOT NULL,
    permission_code CITEXT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NULL,
    assigned_by UUID NULL REFERENCES identity.employee(id),
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_employee_scope_type CHECK (
        scope_type IN ('BRANCH', 'CUSTOMER', 'LOAN_APPLICATION', 'ANALYSIS_CASE')
    ),
    CONSTRAINT ck_employee_scope_validity CHECK (valid_until IS NULL OR valid_until > valid_from)
);

