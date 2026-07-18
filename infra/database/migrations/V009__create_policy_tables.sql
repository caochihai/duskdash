CREATE TABLE policy.policy (
    id UUID PRIMARY KEY,
    policy_code CITEXT NOT NULL UNIQUE,
    policy_name TEXT NOT NULL,
    policy_type VARCHAR(40) NOT NULL,
    owner_department_id UUID NULL REFERENCES identity.department(id),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE policy.policy_version (
    id UUID PRIMARY KEY,
    policy_id UUID NOT NULL REFERENCES policy.policy(id),
    version_number VARCHAR(30) NOT NULL,
    effective_from DATE NOT NULL,
    effective_until DATE NULL,
    approved_by UUID NULL REFERENCES identity.employee(id),
    approved_at TIMESTAMPTZ NULL,
    source_document_id UUID NOT NULL REFERENCES document.document(id),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_policy_version UNIQUE (policy_id, version_number),
    CONSTRAINT ck_policy_version_dates CHECK (
        effective_until IS NULL OR effective_until >= effective_from
    )
);

CREATE TABLE policy.policy_clause (
    id UUID PRIMARY KEY,
    policy_version_id UUID NOT NULL REFERENCES policy.policy_version(id),
    clause_number TEXT NOT NULL,
    title TEXT NULL,
    content TEXT NOT NULL,
    page_number INTEGER NULL,
    embedding VECTOR(1024) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_policy_clause_number UNIQUE (policy_version_id, clause_number),
    CONSTRAINT ck_policy_clause_page CHECK (page_number IS NULL OR page_number > 0)
);

CREATE TABLE policy.checklist_rule (
    id UUID PRIMARY KEY,
    policy_version_id UUID NOT NULL REFERENCES policy.policy_version(id),
    rule_code CITEXT NOT NULL,
    rule_name TEXT NOT NULL,
    conditions JSONB NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_checklist_rule_code UNIQUE (policy_version_id, rule_code)
);

CREATE TABLE policy.checklist_rule_requirement (
    id UUID PRIMARY KEY,
    checklist_rule_id UUID NOT NULL REFERENCES policy.checklist_rule(id),
    requirement_code CITEXT NOT NULL,
    document_type VARCHAR(50) NULL,
    mandatory_level VARCHAR(30) NOT NULL,
    requirement_description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

