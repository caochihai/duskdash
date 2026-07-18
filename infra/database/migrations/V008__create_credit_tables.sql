CREATE TABLE credit.loan_product (
    id UUID PRIMARY KEY,
    product_code CITEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    customer_type VARCHAR(20) NOT NULL,
    loan_purpose VARCHAR(40) NULL,
    min_amount NUMERIC(24,4) NULL,
    max_amount NUMERIC(24,4) NULL,
    min_term_months INTEGER NULL,
    max_term_months INTEGER NULL,
    status VARCHAR(20) NOT NULL,
    effective_from DATE NOT NULL,
    effective_until DATE NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_loan_product_amounts CHECK (
        max_amount IS NULL OR min_amount IS NULL OR max_amount >= min_amount
    ),
    CONSTRAINT ck_loan_product_terms CHECK (
        max_term_months IS NULL OR min_term_months IS NULL OR max_term_months >= min_term_months
    ),
    CONSTRAINT ck_loan_product_effective_dates CHECK (
        effective_until IS NULL OR effective_until >= effective_from
    )
);

CREATE TABLE credit.loan_application (
    id UUID PRIMARY KEY,
    application_number CITEXT NOT NULL UNIQUE,
    primary_customer_id UUID NOT NULL REFERENCES customer.customer(id),
    product_id UUID NOT NULL REFERENCES credit.loan_product(id),
    requested_amount NUMERIC(24,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    requested_term_months INTEGER NOT NULL,
    loan_purpose VARCHAR(40) NOT NULL,
    interest_rate_assumption NUMERIC(12,8) NULL,
    repayment_method VARCHAR(40) NULL,
    status VARCHAR(30) NOT NULL,
    assigned_employee_id UUID NULL REFERENCES identity.employee(id),
    submitted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by UUID NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_loan_application_status CHECK (
        status IN (
            'DRAFT', 'DOCUMENT_COLLECTION', 'UNDER_ANALYSIS', 'NEEDS_INFORMATION',
            'READY_FOR_REVIEW', 'SUBMITTED_FOR_APPROVAL', 'APPROVED',
            'APPROVED_WITH_CONDITIONS', 'REJECTED', 'WITHDRAWN'
        )
    ),
    CONSTRAINT ck_loan_application_amount CHECK (requested_amount > 0),
    CONSTRAINT ck_loan_application_term CHECK (requested_term_months > 0),
    CONSTRAINT ck_loan_application_version CHECK (version > 0)
);

CREATE TABLE credit.loan_party (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    party_id UUID NOT NULL REFERENCES customer.party(id),
    party_role VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_loan_party_role CHECK (
        party_role IN (
            'PRIMARY_BORROWER', 'CO_BORROWER', 'GUARANTOR', 'SPOUSE',
            'COLLATERAL_OWNER', 'LEGAL_REPRESENTATIVE'
        )
    )
);

CREATE TABLE credit.existing_obligation (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    party_id UUID NOT NULL REFERENCES customer.party(id),
    lender_name TEXT NULL,
    obligation_type VARCHAR(30) NOT NULL,
    outstanding_balance NUMERIC(24,4) NULL,
    monthly_payment NUMERIC(24,4) NULL,
    credit_limit NUMERIC(24,4) NULL,
    currency CHAR(3) NOT NULL,
    verified_status VARCHAR(30) NOT NULL,
    source_type VARCHAR(30) NOT NULL,
    source_id UUID NULL,
    as_of_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE credit.collateral (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    owner_party_id UUID NOT NULL REFERENCES customer.party(id),
    collateral_type VARCHAR(40) NOT NULL,
    description TEXT NULL,
    declared_value NUMERIC(24,4) NULL,
    appraised_value NUMERIC(24,4) NULL,
    eligible_value NUMERIC(24,4) NULL,
    currency CHAR(3) NOT NULL,
    valuation_date DATE NULL,
    valuation_status VARCHAR(30) NULL,
    ownership_verification_status VARCHAR(30) NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_collateral_version CHECK (version > 0)
);

CREATE TABLE credit.collateral_valuation (
    id UUID PRIMARY KEY,
    collateral_id UUID NOT NULL REFERENCES credit.collateral(id),
    valuation_date DATE NOT NULL,
    market_value NUMERIC(24,4) NOT NULL,
    eligible_value NUMERIC(24,4) NULL,
    currency CHAR(3) NOT NULL,
    valuation_method VARCHAR(50) NULL,
    valuer_name TEXT NULL,
    source_document_id UUID NULL REFERENCES document.document(id),
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE credit.loan_checklist_item (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    requirement_code CITEXT NOT NULL,
    document_type VARCHAR(50) NULL,
    requirement_status VARCHAR(30) NOT NULL,
    mandatory_level VARCHAR(30) NOT NULL,
    source_policy_clause_id UUID NULL,
    linked_document_id UUID NULL REFERENCES document.document(id),
    waived_by UUID NULL REFERENCES identity.employee(id),
    waiver_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_loan_checklist_status CHECK (
        requirement_status IN (
            'REQUIRED', 'RECEIVED', 'VALID', 'EXPIRED', 'INCOMPLETE',
            'INCONSISTENT', 'WAIVED', 'NOT_APPLICABLE'
        )
    ),
    CONSTRAINT ck_loan_checklist_waiver CHECK (
        requirement_status <> 'WAIVED' OR (waived_by IS NOT NULL AND waiver_reason IS NOT NULL)
    )
);

CREATE TABLE credit.calculation_record (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    analysis_case_id UUID NULL,
    calculation_type VARCHAR(40) NOT NULL,
    calculation_version VARCHAR(20) NOT NULL,
    inputs JSONB NOT NULL,
    formula TEXT NOT NULL,
    result_value NUMERIC(30,10) NULL,
    result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    unit VARCHAR(30) NULL,
    calculated_at TIMESTAMPTZ NOT NULL,
    created_by_type VARCHAR(20) NOT NULL,
    created_by_id UUID NULL
);

CREATE TABLE credit.affordability_assessment (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    calculation_version VARCHAR(20) NOT NULL,
    monthly_declared_income NUMERIC(24,4) NULL,
    monthly_verified_income NUMERIC(24,4) NULL,
    monthly_accepted_income NUMERIC(24,4) NULL,
    monthly_existing_obligations NUMERIC(24,4) NULL,
    projected_monthly_payment NUMERIC(24,4) NULL,
    dti NUMERIC(12,8) NULL,
    dscr NUMERIC(12,8) NULL,
    ltv NUMERIC(12,8) NULL,
    net_disposable_income NUMERIC(24,4) NULL,
    stress_interest_rate NUMERIC(12,8) NULL,
    stress_dti NUMERIC(12,8) NULL,
    result VARCHAR(30) NOT NULL,
    calculation_payload JSONB NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE credit.policy_check (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    analysis_case_id UUID NULL,
    policy_version_id UUID NOT NULL,
    clause_id UUID NULL,
    rule_code CITEXT NULL,
    status VARCHAR(30) NOT NULL,
    actual_value TEXT NULL,
    required_value TEXT NULL,
    explanation TEXT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_policy_check_status CHECK (
        status IN ('PASS', 'FAIL', 'CONDITIONAL', 'INSUFFICIENT_DATA', 'NOT_APPLICABLE')
    )
);

CREATE TABLE credit.approval_request (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    requested_by UUID NOT NULL REFERENCES identity.employee(id),
    requested_at TIMESTAMPTZ NOT NULL,
    requested_authority_level VARCHAR(30) NULL,
    status VARCHAR(30) NOT NULL,
    request_note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE credit.loan_decision (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    approval_request_id UUID NULL REFERENCES credit.approval_request(id),
    decision_type VARCHAR(40) NOT NULL,
    approved_amount NUMERIC(24,4) NULL,
    approved_term_months INTEGER NULL,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    rationale TEXT NOT NULL,
    decision_maker_id UUID NOT NULL REFERENCES identity.employee(id),
    decision_at TIMESTAMPTZ NOT NULL,
    is_override BOOLEAN NOT NULL DEFAULT FALSE,
    override_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_loan_decision_override CHECK (
        is_override = FALSE OR override_reason IS NOT NULL
    )
);

CREATE TABLE credit.disbursement (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL REFERENCES credit.loan_application(id),
    drawdown_number INTEGER NOT NULL,
    amount NUMERIC(24,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    beneficiary_name_masked TEXT NULL,
    beneficiary_account_hash CHAR(64) NULL,
    purpose_reference TEXT NULL,
    payment_transaction_id UUID NULL,
    status VARCHAR(30) NOT NULL,
    approved_by UUID NULL REFERENCES identity.employee(id),
    disbursed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_disbursement_drawdown CHECK (drawdown_number > 0),
    CONSTRAINT ck_disbursement_amount CHECK (amount > 0)
);

CREATE TABLE credit.loan_account (
    id UUID PRIMARY KEY,
    loan_application_id UUID NOT NULL UNIQUE REFERENCES credit.loan_application(id),
    account_number_masked TEXT NOT NULL,
    account_number_hash CHAR(64) NOT NULL UNIQUE,
    principal_amount NUMERIC(24,4) NOT NULL,
    outstanding_principal NUMERIC(24,4) NOT NULL,
    interest_rate NUMERIC(12,8) NOT NULL,
    disbursement_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_loan_account_dates CHECK (maturity_date >= disbursement_date)
);

CREATE TABLE credit.repayment_schedule (
    id UUID PRIMARY KEY,
    loan_account_id UUID NOT NULL REFERENCES credit.loan_account(id),
    installment_number INTEGER NOT NULL,
    due_date DATE NOT NULL,
    principal_due NUMERIC(24,4) NOT NULL,
    interest_due NUMERIC(24,4) NOT NULL,
    fee_due NUMERIC(24,4) NOT NULL DEFAULT 0,
    total_due NUMERIC(24,4) NOT NULL,
    payment_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_repayment_schedule_installment UNIQUE (loan_account_id, installment_number),
    CONSTRAINT ck_repayment_installment_number CHECK (installment_number > 0)
);

CREATE TABLE credit.loan_payment (
    id UUID PRIMARY KEY,
    loan_account_id UUID NOT NULL REFERENCES credit.loan_account(id),
    transaction_id UUID NULL,
    payment_date TIMESTAMPTZ NOT NULL,
    principal_paid NUMERIC(24,4) NOT NULL,
    interest_paid NUMERIC(24,4) NOT NULL,
    fee_paid NUMERIC(24,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL
);
