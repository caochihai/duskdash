CREATE TABLE storage.object_metadata (
    id UUID PRIMARY KEY,
    bucket_name TEXT NOT NULL,
    object_key TEXT NOT NULL,
    object_version_id TEXT NULL,
    etag TEXT NULL,
    sha256 CHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    storage_class VARCHAR(30) NULL,
    encryption_type VARCHAR(30) NULL,
    retention_until TIMESTAMPTZ NULL,
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT uq_object_metadata_location UNIQUE NULLS NOT DISTINCT (
        bucket_name, object_key, object_version_id
    ),
    CONSTRAINT ck_object_metadata_size CHECK (size_bytes >= 0)
);

CREATE TABLE storage.upload_session (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customer.customer(id),
    loan_application_id UUID NULL,
    expected_document_type VARCHAR(50) NULL,
    original_filename TEXT NOT NULL,
    expected_mime_type TEXT NOT NULL,
    expected_size_bytes BIGINT NOT NULL,
    expected_sha256 CHAR(64) NOT NULL,
    quarantine_object_key TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    created_by UUID NOT NULL REFERENCES identity.employee(id),
    idempotency_key UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_upload_session_status CHECK (
        status IN ('CREATED', 'UPLOADING', 'UPLOADED', 'VERIFYING', 'COMPLETED', 'EXPIRED', 'FAILED')
    ),
    CONSTRAINT ck_upload_session_size CHECK (expected_size_bytes >= 0),
    CONSTRAINT ck_upload_session_completion CHECK (
        completed_at IS NULL OR completed_at >= created_at
    )
);

CREATE TABLE storage.retention_rule (
    id UUID PRIMARY KEY,
    rule_code CITEXT NOT NULL UNIQUE,
    resource_type VARCHAR(50) NOT NULL,
    retention_years INTEGER NULL,
    retention_days INTEGER NULL,
    start_event VARCHAR(50) NOT NULL,
    description TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_retention_rule_duration CHECK (
        (retention_years IS NOT NULL AND retention_years > 0)
        OR (retention_days IS NOT NULL AND retention_days > 0)
    )
);

CREATE TABLE storage.resource_retention (
    id UUID PRIMARY KEY,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID NOT NULL,
    retention_rule_id UUID NOT NULL REFERENCES storage.retention_rule(id),
    retention_start_date DATE NULL,
    retention_until DATE NULL,
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    legal_hold_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_resource_retention_dates CHECK (
        retention_until IS NULL OR retention_start_date IS NULL OR retention_until >= retention_start_date
    ),
    CONSTRAINT ck_resource_retention_legal_hold_reason CHECK (
        legal_hold = FALSE OR legal_hold_reason IS NOT NULL
    )
);

