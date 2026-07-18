CREATE TABLE banking.account (
    id UUID PRIMARY KEY,
    account_number_masked TEXT NOT NULL,
    account_number_hash CHAR(64) NOT NULL UNIQUE,
    account_type VARCHAR(30) NOT NULL,
    currency CHAR(3) NOT NULL,
    branch_id UUID NULL REFERENCES identity.branch(id),
    status VARCHAR(20) NOT NULL,
    opened_at TIMESTAMPTZ NULL,
    closed_at TIMESTAMPTZ NULL,
    current_balance NUMERIC(24,4) NULL,
    balance_as_of TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_account_dates CHECK (closed_at IS NULL OR opened_at IS NULL OR closed_at >= opened_at),
    CONSTRAINT ck_account_version_positive CHECK (version > 0)
);

CREATE TABLE banking.account_holder (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES banking.account(id),
    party_id UUID NOT NULL REFERENCES customer.party(id),
    holder_role VARCHAR(30) NOT NULL,
    valid_from DATE NULL,
    valid_until DATE NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_account_holder_validity CHECK (
        valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from
    )
);

CREATE TABLE banking."transaction" (
    id UUID NOT NULL,
    account_id UUID NOT NULL REFERENCES banking.account(id),
    booking_time TIMESTAMPTZ NOT NULL,
    value_date DATE NULL,
    direction VARCHAR(10) NOT NULL,
    amount NUMERIC(24,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    transaction_type VARCHAR(50) NULL,
    channel VARCHAR(30) NULL,
    description TEXT NULL,
    balance_after NUMERIC(24,4) NULL,
    counterparty_name_masked TEXT NULL,
    counterparty_account_hash CHAR(64) NULL,
    reference_number TEXT NULL,
    status VARCHAR(20) NOT NULL,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id, booking_time),
    CONSTRAINT ck_transaction_direction CHECK (direction IN ('CREDIT', 'DEBIT')),
    CONSTRAINT ck_transaction_amount_positive CHECK (amount > 0)
) PARTITION BY RANGE (booking_time);

-- Keep current and previous calendar years writable, one partition per UTC month.
DO $partition$
DECLARE
    target_year INTEGER;
    target_month INTEGER;
    range_start TIMESTAMPTZ;
    range_end TIMESTAMPTZ;
    partition_name TEXT;
BEGIN
    FOR target_year IN
        EXTRACT(YEAR FROM CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::INTEGER - 1
        .. EXTRACT(YEAR FROM CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::INTEGER
    LOOP
        FOR target_month IN 1..12 LOOP
            range_start := make_timestamptz(target_year, target_month, 1, 0, 0, 0, 'UTC');
            range_end := range_start + INTERVAL '1 month';
            partition_name := format('transaction_%s_%s', target_year, lpad(target_month::TEXT, 2, '0'));
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS banking.%I PARTITION OF banking."transaction" FOR VALUES FROM (%L) TO (%L)',
                partition_name,
                range_start,
                range_end
            );
        END LOOP;
    END LOOP;
END
$partition$;

CREATE TABLE banking.transaction_default
    PARTITION OF banking."transaction" DEFAULT;

CREATE TABLE banking.account_monthly_summary (
    account_id UUID NOT NULL REFERENCES banking.account(id),
    year_month DATE NOT NULL,
    total_inflow NUMERIC(24,4) NOT NULL,
    total_outflow NUMERIC(24,4) NOT NULL,
    salary_inflow NUMERIC(24,4) NOT NULL,
    loan_payment NUMERIC(24,4) NOT NULL,
    cash_deposit NUMERIC(24,4) NOT NULL,
    average_balance NUMERIC(24,4) NULL,
    minimum_balance NUMERIC(24,4) NULL,
    maximum_balance NUMERIC(24,4) NULL,
    transaction_count INTEGER NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (account_id, year_month),
    CONSTRAINT ck_account_monthly_summary_month CHECK (year_month = date_trunc('month', year_month)::DATE),
    CONSTRAINT ck_account_monthly_summary_count CHECK (transaction_count >= 0)
);

CREATE TABLE banking.credit_report (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customer.customer(id),
    provider VARCHAR(50) NOT NULL,
    report_reference TEXT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    report_as_of_date DATE NOT NULL,
    risk_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_object_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE banking.credit_facility (
    id UUID PRIMARY KEY,
    credit_report_id UUID NOT NULL REFERENCES banking.credit_report(id),
    lender_name TEXT NULL,
    facility_type VARCHAR(30) NOT NULL,
    credit_limit NUMERIC(24,4) NULL,
    outstanding_balance NUMERIC(24,4) NULL,
    monthly_obligation NUMERIC(24,4) NULL,
    overdue_days INTEGER NULL,
    debt_group VARCHAR(20) NULL,
    currency CHAR(3) NOT NULL,
    as_of_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

