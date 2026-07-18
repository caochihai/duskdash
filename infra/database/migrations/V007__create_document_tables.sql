CREATE TABLE document.document (
    id UUID PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL,
    document_subtype VARCHAR(50) NULL,
    title TEXT NULL,
    owner_party_id UUID NULL REFERENCES customer.party(id),
    classification VARCHAR(30) NOT NULL,
    document_date DATE NULL,
    valid_from DATE NULL,
    valid_until DATE NULL,
    verification_status VARCHAR(30) NOT NULL,
    processing_status VARCHAR(30) NOT NULL,
    created_by UUID NOT NULL REFERENCES identity.employee(id),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_document_validity CHECK (
        valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from
    ),
    CONSTRAINT ck_document_version_positive CHECK (version > 0)
);

CREATE TABLE document.document_version (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES document.document(id),
    version_number INTEGER NOT NULL,
    original_object_id UUID NOT NULL REFERENCES storage.object_metadata(id),
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    uploaded_by UUID NOT NULL REFERENCES identity.employee(id),
    uploaded_at TIMESTAMPTZ NOT NULL,
    scan_status VARCHAR(30) NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_document_version UNIQUE (document_id, version_number),
    CONSTRAINT ck_document_version_number CHECK (version_number > 0),
    CONSTRAINT ck_document_version_file_size CHECK (file_size >= 0)
);

CREATE TABLE document.document_link (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES document.document(id),
    entity_type VARCHAR(40) NOT NULL,
    entity_id UUID NOT NULL,
    relationship_type VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE document.processing_job (
    id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document.document_version(id),
    job_type VARCHAR(40) NOT NULL,
    status VARCHAR(30) NOT NULL,
    model_name TEXT NULL,
    model_version TEXT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_code VARCHAR(50) NULL,
    error_message_safe TEXT NULL,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_document_processing_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT ck_document_processing_times CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

CREATE TABLE document.document_page (
    id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document.document_version(id),
    page_number INTEGER NOT NULL,
    text_content TEXT NULL,
    ocr_confidence NUMERIC(6,5) NULL,
    page_image_object_id UUID NULL REFERENCES storage.object_metadata(id),
    width INTEGER NULL,
    height INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_document_page UNIQUE (document_version_id, page_number),
    CONSTRAINT ck_document_page_number CHECK (page_number > 0),
    CONSTRAINT ck_document_page_confidence CHECK (
        ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 1
    )
);

CREATE TABLE document.extracted_field (
    id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document.document_version(id),
    field_name CITEXT NOT NULL,
    value_type VARCHAR(20) NOT NULL,
    ocr_value_text TEXT NULL,
    normalized_value_text TEXT NULL,
    corrected_value_text TEXT NULL,
    value_number NUMERIC(24,4) NULL,
    value_date DATE NULL,
    page_number INTEGER NULL,
    bounding_box JSONB NULL,
    source_text TEXT NULL,
    confidence NUMERIC(6,5) NULL,
    verification_status VARCHAR(30) NOT NULL,
    verified_by UUID NULL REFERENCES identity.employee(id),
    verified_at TIMESTAMPTZ NULL,
    verification_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_extracted_field_page CHECK (page_number IS NULL OR page_number > 0),
    CONSTRAINT ck_extracted_field_confidence CHECK (
        confidence IS NULL OR confidence BETWEEN 0 AND 1
    )
);

CREATE TABLE document.document_chunk (
    id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document.document_version(id),
    page_from INTEGER NULL,
    page_to INTEGER NULL,
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    token_count INTEGER NULL,
    embedding VECTOR(1024) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_document_chunk UNIQUE (document_version_id, chunk_index),
    CONSTRAINT ck_document_chunk_index CHECK (chunk_index >= 0),
    CONSTRAINT ck_document_chunk_pages CHECK (
        page_to IS NULL OR page_from IS NULL OR page_to >= page_from
    )
);

CREATE TABLE document.document_issue (
    id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document.document_version(id),
    issue_type VARCHAR(40) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    field_id UUID NULL REFERENCES document.extracted_field(id),
    status VARCHAR(30) NOT NULL,
    detected_by VARCHAR(30) NOT NULL,
    resolved_by UUID NULL REFERENCES identity.employee(id),
    resolved_at TIMESTAMPTZ NULL,
    resolution_note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

