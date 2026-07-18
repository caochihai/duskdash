CREATE TABLE customer.party (
    id UUID PRIMARY KEY,
    party_type VARCHAR(20) NOT NULL,
    display_name TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by UUID NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_party_type CHECK (party_type IN ('PERSON', 'ORGANIZATION')),
    CONSTRAINT ck_party_version_positive CHECK (version > 0)
);

CREATE TABLE customer.person_profile (
    party_id UUID PRIMARY KEY REFERENCES customer.party(id),
    full_name TEXT NOT NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(20) NULL,
    nationality CHAR(2) NULL,
    marital_status VARCHAR(30) NULL,
    occupation TEXT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE customer.organization_profile (
    party_id UUID PRIMARY KEY REFERENCES customer.party(id),
    legal_name TEXT NOT NULL,
    trading_name TEXT NULL,
    business_type VARCHAR(50) NULL,
    registration_number_hash CHAR(64) NULL,
    tax_code_hash CHAR(64) NULL,
    incorporation_date DATE NULL,
    industry_code VARCHAR(30) NULL,
    legal_representative_party_id UUID NULL REFERENCES customer.party(id),
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE customer.customer (
    id UUID PRIMARY KEY,
    party_id UUID NOT NULL UNIQUE REFERENCES customer.party(id),
    customer_number CITEXT NOT NULL UNIQUE,
    customer_segment VARCHAR(30) NULL,
    home_branch_id UUID NOT NULL REFERENCES identity.branch(id),
    relationship_manager_id UUID NULL REFERENCES identity.employee(id),
    onboarding_date DATE NULL,
    kyc_status VARCHAR(30) NOT NULL,
    risk_rating VARCHAR(20) NULL,
    risk_rating_as_of DATE NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_customer_version_positive CHECK (version > 0)
);

CREATE TABLE customer.party_identifier (
    id UUID PRIMARY KEY,
    party_id UUID NOT NULL REFERENCES customer.party(id),
    identifier_type VARCHAR(30) NOT NULL,
    encrypted_value BYTEA NOT NULL,
    value_hash CHAR(64) NOT NULL,
    last4 VARCHAR(4) NULL,
    issued_date DATE NULL,
    expiry_date DATE NULL,
    issuing_authority TEXT NULL,
    country_code CHAR(2) NULL,
    verification_status VARCHAR(30) NOT NULL,
    source_document_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_party_identifier_type_hash UNIQUE (identifier_type, value_hash),
    CONSTRAINT ck_party_identifier_dates CHECK (
        expiry_date IS NULL OR issued_date IS NULL OR expiry_date >= issued_date
    )
);

CREATE TABLE customer.party_contact (
    id UUID PRIMARY KEY,
    party_id UUID NOT NULL REFERENCES customer.party(id),
    contact_type VARCHAR(20) NOT NULL,
    encrypted_value BYTEA NOT NULL,
    value_hash CHAR(64) NOT NULL,
    masked_value TEXT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    verification_status VARCHAR(30) NOT NULL,
    verified_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE customer.party_address (
    id UUID PRIMARY KEY,
    party_id UUID NOT NULL REFERENCES customer.party(id),
    address_type VARCHAR(30) NOT NULL,
    address_line TEXT NOT NULL,
    ward TEXT NULL,
    district TEXT NULL,
    province TEXT NULL,
    country_code CHAR(2) NOT NULL,
    valid_from DATE NULL,
    valid_until DATE NULL,
    verification_status VARCHAR(30) NOT NULL,
    source_document_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_party_address_validity CHECK (
        valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from
    )
);

CREATE TABLE customer.employment (
    id UUID PRIMARY KEY,
    party_id UUID NOT NULL REFERENCES customer.party(id),
    employer_name TEXT NOT NULL,
    position TEXT NULL,
    employment_type VARCHAR(30) NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    declared_monthly_income NUMERIC(24,4) NULL,
    currency CHAR(3) NOT NULL DEFAULT 'VND',
    verification_status VARCHAR(30) NOT NULL,
    source_document_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_employment_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_employment_version_positive CHECK (version > 0)
);

CREATE TABLE customer.income_source (
    id UUID PRIMARY KEY,
    party_id UUID NOT NULL REFERENCES customer.party(id),
    income_type VARCHAR(30) NOT NULL,
    declared_amount NUMERIC(24,4) NULL,
    verified_amount NUMERIC(24,4) NULL,
    accepted_amount NUMERIC(24,4) NULL,
    frequency VARCHAR(20) NOT NULL,
    currency CHAR(3) NOT NULL,
    as_of_date DATE NOT NULL,
    verification_method VARCHAR(30) NULL,
    verification_status VARCHAR(30) NOT NULL,
    source_document_id UUID NULL,
    source_calculation_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_income_source_version_positive CHECK (version > 0)
);

CREATE TABLE customer.party_relationship (
    id UUID PRIMARY KEY,
    from_party_id UUID NOT NULL REFERENCES customer.party(id),
    to_party_id UUID NOT NULL REFERENCES customer.party(id),
    relationship_type VARCHAR(40) NOT NULL,
    valid_from DATE NULL,
    valid_until DATE NULL,
    source_document_id UUID NULL,
    verification_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_party_relationship_not_self CHECK (from_party_id <> to_party_id),
    CONSTRAINT ck_party_relationship_type CHECK (
        relationship_type IN (
            'SPOUSE', 'CO_BORROWER', 'GUARANTOR', 'LEGAL_REPRESENTATIVE',
            'DIRECTOR', 'SHAREHOLDER', 'RELATED_COMPANY'
        )
    ),
    CONSTRAINT ck_party_relationship_validity CHECK (
        valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from
    )
);

CREATE TABLE customer.kyc_assessment (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customer.customer(id),
    assessment_date TIMESTAMPTZ NOT NULL,
    kyc_status VARCHAR(30) NOT NULL,
    aml_risk_level VARCHAR(20) NULL,
    pep_status VARCHAR(20) NULL,
    sanction_status VARCHAR(20) NULL,
    beneficial_owner_verified BOOLEAN NULL,
    source_system TEXT NULL,
    assessment_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    assessed_by UUID NULL REFERENCES identity.employee(id),
    created_at TIMESTAMPTZ NOT NULL
);
