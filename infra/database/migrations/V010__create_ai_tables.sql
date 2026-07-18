CREATE TABLE ai.conversation (
    id UUID PRIMARY KEY,
    employee_id UUID NOT NULL REFERENCES identity.employee(id),
    active_customer_id UUID NULL REFERENCES customer.customer(id),
    active_loan_application_id UUID NULL REFERENCES credit.loan_application(id),
    title TEXT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_conversation_times CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE ai.message (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES ai.conversation(id),
    sender_type VARCHAR(20) NOT NULL,
    sender_id UUID NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    parent_message_id UUID NULL REFERENCES ai.message(id),
    route_type VARCHAR(30) NULL,
    complexity_level SMALLINT NULL,
    analysis_case_id UUID NULL,
    CONSTRAINT ck_message_complexity CHECK (
        complexity_level IS NULL OR complexity_level >= 0
    )
);

CREATE TABLE ai.analysis_case (
    id UUID PRIMARY KEY,
    case_type VARCHAR(40) NOT NULL,
    customer_id UUID NOT NULL REFERENCES customer.customer(id),
    loan_application_id UUID NULL REFERENCES credit.loan_application(id),
    conversation_id UUID NULL REFERENCES ai.conversation(id),
    created_by UUID NOT NULL REFERENCES identity.employee(id),
    status VARCHAR(30) NOT NULL,
    objective TEXT NOT NULL,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_analysis_case_times CHECK (
        completed_at IS NULL OR completed_at >= created_at
    )
);

CREATE TABLE ai.analysis_task (
    id UUID PRIMARY KEY,
    analysis_case_id UUID NOT NULL REFERENCES ai.analysis_case(id),
    task_code CITEXT NOT NULL,
    agent_type VARCHAR(30) NOT NULL,
    objective TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    depends_on JSONB NOT NULL DEFAULT '[]'::jsonb,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_code VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_analysis_task_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT ck_analysis_task_times CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

CREATE TABLE ai.agent_run (
    id UUID PRIMARY KEY,
    analysis_case_id UUID NOT NULL REFERENCES ai.analysis_case(id),
    analysis_task_id UUID NOT NULL REFERENCES ai.analysis_task(id),
    agent_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    model_provider TEXT NULL,
    model_name TEXT NULL,
    model_version TEXT NULL,
    prompt_version TEXT NULL,
    input_hash CHAR(64) NULL,
    output_hash CHAR(64) NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_agent_run_times CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

CREATE TABLE ai.finding (
    id UUID PRIMARY KEY,
    analysis_case_id UUID NOT NULL REFERENCES ai.analysis_case(id),
    agent_run_id UUID NOT NULL REFERENCES ai.agent_run(id),
    finding_type VARCHAR(40) NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    confidence NUMERIC(6,5) NULL,
    recommended_action TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_finding_confidence CHECK (
        confidence IS NULL OR confidence BETWEEN 0 AND 1
    )
);

CREATE TABLE ai.evidence_link (
    id UUID PRIMARY KEY,
    finding_id UUID NOT NULL REFERENCES ai.finding(id),
    source_type VARCHAR(40) NOT NULL,
    source_id UUID NOT NULL,
    source_locator JSONB NOT NULL,
    quoted_text TEXT NULL,
    evidence_role VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_evidence_source_type CHECK (
        source_type IN (
            'CUSTOMER_RECORD', 'TRANSACTION', 'TRANSACTION_QUERY', 'DOCUMENT_FIELD',
            'DOCUMENT_PAGE', 'DOCUMENT_CHUNK', 'CALCULATION', 'POLICY_CLAUSE',
            'LOAN_RECORD'
        )
    ),
    CONSTRAINT ck_evidence_role CHECK (
        evidence_role IN ('PRIMARY', 'SUPPORTING', 'CONTRADICTING')
    )
);

CREATE TABLE ai.validation_result (
    id UUID PRIMARY KEY,
    analysis_case_id UUID NOT NULL REFERENCES ai.analysis_case(id),
    validation_status VARCHAR(30) NOT NULL,
    citation_coverage NUMERIC(6,5) NULL,
    unsupported_claims JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_conflicts JSONB NOT NULL DEFAULT '[]'::jsonb,
    agent_contradictions JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_for_synthesis BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_validation_citation_coverage CHECK (
        citation_coverage IS NULL OR citation_coverage BETWEEN 0 AND 1
    )
);

CREATE TABLE ai.report (
    id UUID PRIMARY KEY,
    analysis_case_id UUID NOT NULL REFERENCES ai.analysis_case(id),
    report_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    generated_by_agent_run_id UUID NULL REFERENCES ai.agent_run(id),
    reviewed_by UUID NULL REFERENCES identity.employee(id),
    approved_by UUID NULL REFERENCES identity.employee(id),
    version_number INTEGER NOT NULL,
    json_payload JSONB NOT NULL,
    pdf_object_id UUID NULL REFERENCES storage.object_metadata(id),
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_report_version UNIQUE (analysis_case_id, version_number),
    CONSTRAINT ck_report_version_number CHECK (version_number > 0)
);

CREATE TABLE ai.report_claim (
    id UUID PRIMARY KEY,
    report_id UUID NOT NULL REFERENCES ai.report(id),
    section VARCHAR(50) NOT NULL,
    claim_text TEXT NOT NULL,
    claim_type VARCHAR(30) NOT NULL,
    confidence NUMERIC(6,5) NULL,
    validation_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_report_claim_confidence CHECK (
        confidence IS NULL OR confidence BETWEEN 0 AND 1
    )
);

CREATE TABLE ai.report_claim_evidence (
    claim_id UUID NOT NULL REFERENCES ai.report_claim(id),
    evidence_link_id UUID NOT NULL REFERENCES ai.evidence_link(id),
    support_type VARCHAR(20) NOT NULL,
    PRIMARY KEY (claim_id, evidence_link_id)
);

