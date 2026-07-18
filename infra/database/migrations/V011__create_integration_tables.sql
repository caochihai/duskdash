CREATE TABLE integration.background_job (
    id UUID PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(40) NOT NULL,
    resource_id UUID NOT NULL,
    status VARCHAR(30) NOT NULL,
    progress_percent SMALLINT NOT NULL DEFAULT 0,
    current_step VARCHAR(50) NULL,
    correlation_id UUID NOT NULL,
    requested_by UUID NULL REFERENCES identity.employee(id),
    priority SMALLINT NOT NULL DEFAULT 5,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    scheduled_at TIMESTAMPTZ NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_code VARCHAR(50) NULL,
    error_message_safe TEXT NULL,
    result_reference_type VARCHAR(40) NULL,
    result_reference_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_background_job_status CHECK (
        status IN ('QUEUED', 'PUBLISHED', 'RUNNING', 'WAITING', 'RETRYING', 'COMPLETED', 'FAILED', 'CANCELLED')
    ),
    CONSTRAINT ck_background_job_progress CHECK (progress_percent BETWEEN 0 AND 100),
    CONSTRAINT ck_background_job_priority CHECK (priority >= 0),
    CONSTRAINT ck_background_job_attempts CHECK (
        attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts
    ),
    CONSTRAINT ck_background_job_times CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    ),
    CONSTRAINT ck_background_job_version CHECK (version > 0)
);

CREATE TABLE integration.background_job_step (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES integration.background_job(id),
    step_code CITEXT NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    progress_percent SMALLINT NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_code VARCHAR(50) NULL,
    error_message_safe TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_background_job_step UNIQUE (job_id, step_code),
    CONSTRAINT ck_background_job_step_order CHECK (step_order >= 0),
    CONSTRAINT ck_background_job_step_progress CHECK (progress_percent BETWEEN 0 AND 100),
    CONSTRAINT ck_background_job_step_attempts CHECK (attempt_count >= 0),
    CONSTRAINT ck_background_job_step_times CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

CREATE TABLE integration.job_event (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES integration.background_job(id),
    event_type VARCHAR(50) NOT NULL,
    sequence_number BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_job_event_sequence UNIQUE (job_id, sequence_number),
    CONSTRAINT ck_job_event_sequence CHECK (sequence_number >= 0)
);

CREATE TABLE integration.event_outbox (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER NOT NULL,
    partition_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL,
    locked_at TIMESTAMPTZ NULL,
    locked_by TEXT NULL,
    published_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_event_outbox_status CHECK (
        status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED')
    ),
    CONSTRAINT ck_event_outbox_version CHECK (event_version > 0),
    CONSTRAINT ck_event_outbox_attempts CHECK (attempt_count >= 0)
);

CREATE TABLE integration.event_inbox (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL,
    consumer_name TEXT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ NULL,
    status VARCHAR(20) NOT NULL,
    result_reference_id UUID NULL,
    error_code VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_event_inbox_consumer UNIQUE (event_id, consumer_name),
    CONSTRAINT ck_event_inbox_times CHECK (
        processed_at IS NULL OR processed_at >= received_at
    )
);

CREATE TABLE integration.idempotency_record (
    id UUID PRIMARY KEY,
    idempotency_key UUID NOT NULL,
    actor_id UUID NOT NULL,
    operation_name VARCHAR(100) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    response_status INTEGER NULL,
    response_payload JSONB NULL,
    resource_type VARCHAR(40) NULL,
    resource_id UUID NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_idempotency_record UNIQUE (actor_id, operation_name, idempotency_key)
);

CREATE TABLE integration.notification (
    id UUID PRIMARY KEY,
    employee_id UUID NOT NULL REFERENCES identity.employee(id),
    notification_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    resource_type VARCHAR(40) NULL,
    resource_id UUID NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    read_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_notification_status CHECK (status IN ('UNREAD', 'READ', 'DISMISSED')),
    CONSTRAINT ck_notification_read_at CHECK (
        status = 'UNREAD' OR read_at IS NOT NULL
    )
);

