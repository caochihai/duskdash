BEGIN;

-- Twelve UTC calendar months of synthetic salary inflows. Customer A has an
-- exact average salary inflow of VND 22,000,000 as required by the demo case.
WITH month_series AS (
    SELECT
        month_offset,
        (
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            - make_interval(months => month_offset)
        ) AT TIME ZONE 'UTC' AS month_start
    FROM generate_series(0, 11) AS offsets(month_offset)
),
salary_accounts(account_id, salary_amount) AS (
    VALUES
        ('60000000-0000-4000-8000-000000000001'::UUID, 22000000.0000::NUMERIC(24,4)),
        ('60000000-0000-4000-8000-000000000003'::UUID, 18000000.0000::NUMERIC(24,4)),
        ('60000000-0000-4000-8000-000000000005'::UUID, 35000000.0000::NUMERIC(24,4))
)
INSERT INTO banking."transaction" (
    id, account_id, booking_time, value_date, direction, amount, currency,
    transaction_type, channel, description, balance_after,
    counterparty_name_masked, counterparty_account_hash, reference_number,
    status, raw_payload, created_at
)
SELECT
    uuid_generate_v5(
        '90000000-0000-4000-8000-000000000000'::UUID,
        format('salary:%s:%s', salary_accounts.account_id, to_char(month_series.month_start, 'YYYY-MM'))
    ),
    salary_accounts.account_id,
    month_series.month_start + INTERVAL '5 days 02 hours',
    (month_series.month_start + INTERVAL '5 days')::DATE,
    'CREDIT',
    salary_accounts.salary_amount,
    'VND',
    'SALARY',
    'TRANSFER',
    'Synthetic monthly salary credit',
    salary_accounts.salary_amount,
    'EMPLOYER-DEMO-***',
    repeat(substr(salary_accounts.account_id::TEXT, 1, 1), 64),
    format('SAL-DEMO-%s-%s', right(salary_accounts.account_id::TEXT, 4), to_char(month_series.month_start, 'YYYYMM')),
    'POSTED',
    '{"synthetic":true,"source":"demo-seed"}'::jsonb,
    month_series.month_start + INTERVAL '5 days 02 hours'
FROM month_series
CROSS JOIN salary_accounts
ON CONFLICT (id, booking_time) DO UPDATE
SET amount = EXCLUDED.amount,
    value_date = EXCLUDED.value_date,
    transaction_type = EXCLUDED.transaction_type,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    raw_payload = EXCLUDED.raw_payload;

-- Add a monthly debit to both accounts of every demo customer.
WITH month_series AS (
    SELECT
        month_offset,
        (
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            - make_interval(months => month_offset)
        ) AT TIME ZONE 'UTC' AS month_start
    FROM generate_series(0, 11) AS offsets(month_offset)
),
account_profiles(account_id, expense_amount, transaction_type) AS (
    VALUES
        ('60000000-0000-4000-8000-000000000001'::UUID, 8500000.0000::NUMERIC(24,4), 'LIVING_EXPENSE'::VARCHAR(50)),
        ('60000000-0000-4000-8000-000000000002'::UUID, 1000000.0000::NUMERIC(24,4), 'SAVINGS_TRANSFER'::VARCHAR(50)),
        ('60000000-0000-4000-8000-000000000003'::UUID, 7200000.0000::NUMERIC(24,4), 'LIVING_EXPENSE'::VARCHAR(50)),
        ('60000000-0000-4000-8000-000000000004'::UUID, 800000.0000::NUMERIC(24,4), 'SAVINGS_TRANSFER'::VARCHAR(50)),
        ('60000000-0000-4000-8000-000000000005'::UUID, 12500000.0000::NUMERIC(24,4), 'LIVING_EXPENSE'::VARCHAR(50)),
        ('60000000-0000-4000-8000-000000000006'::UUID, 1500000.0000::NUMERIC(24,4), 'SAVINGS_TRANSFER'::VARCHAR(50))
)
INSERT INTO banking."transaction" (
    id, account_id, booking_time, value_date, direction, amount, currency,
    transaction_type, channel, description, balance_after,
    counterparty_name_masked, counterparty_account_hash, reference_number,
    status, raw_payload, created_at
)
SELECT
    uuid_generate_v5(
        '90000000-0000-4000-8000-000000000000'::UUID,
        format('expense:%s:%s', account_profiles.account_id, to_char(month_series.month_start, 'YYYY-MM'))
    ),
    account_profiles.account_id,
    month_series.month_start + INTERVAL '18 days 08 hours',
    (month_series.month_start + INTERVAL '18 days')::DATE,
    'DEBIT',
    account_profiles.expense_amount,
    'VND',
    account_profiles.transaction_type,
    'TRANSFER',
    'Synthetic recurring monthly debit',
    NULL,
    'MERCHANT-DEMO-***',
    repeat('e', 64),
    format('EXP-DEMO-%s-%s', right(account_profiles.account_id::TEXT, 4), to_char(month_series.month_start, 'YYYYMM')),
    'POSTED',
    '{"synthetic":true,"source":"demo-seed"}'::jsonb,
    month_series.month_start + INTERVAL '18 days 08 hours'
FROM month_series
CROSS JOIN account_profiles
ON CONFLICT (id, booking_time) DO UPDATE
SET amount = EXCLUDED.amount,
    value_date = EXCLUDED.value_date,
    transaction_type = EXCLUDED.transaction_type,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    raw_payload = EXCLUDED.raw_payload;

WITH month_series AS (
    SELECT
        (
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            - make_interval(months => month_offset)
        )::DATE AS year_month
    FROM generate_series(0, 11) AS offsets(month_offset)
),
account_profiles(
    account_id,
    total_inflow,
    total_outflow,
    salary_inflow,
    loan_payment,
    cash_deposit,
    average_balance,
    minimum_balance,
    maximum_balance,
    transaction_count
) AS (
    VALUES
        ('60000000-0000-4000-8000-000000000001'::UUID, 22000000.0000::NUMERIC(24,4), 8500000.0000::NUMERIC(24,4), 22000000.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 30000000.0000::NUMERIC(24,4), 12000000.0000::NUMERIC(24,4), 48000000.0000::NUMERIC(24,4), 2),
        ('60000000-0000-4000-8000-000000000002'::UUID, 0.0000::NUMERIC(24,4), 1000000.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 110000000.0000::NUMERIC(24,4), 95000000.0000::NUMERIC(24,4), 125000000.0000::NUMERIC(24,4), 1),
        ('60000000-0000-4000-8000-000000000003'::UUID, 18000000.0000::NUMERIC(24,4), 7200000.0000::NUMERIC(24,4), 18000000.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 16000000.0000::NUMERIC(24,4), 6000000.0000::NUMERIC(24,4), 24000000.0000::NUMERIC(24,4), 2),
        ('60000000-0000-4000-8000-000000000004'::UUID, 0.0000::NUMERIC(24,4), 800000.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 64000000.0000::NUMERIC(24,4), 58000000.0000::NUMERIC(24,4), 70000000.0000::NUMERIC(24,4), 1),
        ('60000000-0000-4000-8000-000000000005'::UUID, 35000000.0000::NUMERIC(24,4), 12500000.0000::NUMERIC(24,4), 35000000.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 62000000.0000::NUMERIC(24,4), 35000000.0000::NUMERIC(24,4), 80000000.0000::NUMERIC(24,4), 2),
        ('60000000-0000-4000-8000-000000000006'::UUID, 0.0000::NUMERIC(24,4), 1500000.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 0.0000::NUMERIC(24,4), 225000000.0000::NUMERIC(24,4), 210000000.0000::NUMERIC(24,4), 245000000.0000::NUMERIC(24,4), 1)
)
INSERT INTO banking.account_monthly_summary (
    account_id, year_month, total_inflow, total_outflow, salary_inflow,
    loan_payment, cash_deposit, average_balance, minimum_balance,
    maximum_balance, transaction_count, computed_at
)
SELECT
    account_profiles.account_id,
    month_series.year_month,
    account_profiles.total_inflow,
    account_profiles.total_outflow,
    account_profiles.salary_inflow,
    account_profiles.loan_payment,
    account_profiles.cash_deposit,
    account_profiles.average_balance,
    account_profiles.minimum_balance,
    account_profiles.maximum_balance,
    account_profiles.transaction_count,
    CURRENT_TIMESTAMP
FROM month_series
CROSS JOIN account_profiles
ON CONFLICT (account_id, year_month) DO UPDATE
SET total_inflow = EXCLUDED.total_inflow,
    total_outflow = EXCLUDED.total_outflow,
    salary_inflow = EXCLUDED.salary_inflow,
    loan_payment = EXCLUDED.loan_payment,
    cash_deposit = EXCLUDED.cash_deposit,
    average_balance = EXCLUDED.average_balance,
    minimum_balance = EXCLUDED.minimum_balance,
    maximum_balance = EXCLUDED.maximum_balance,
    transaction_count = EXCLUDED.transaction_count,
    computed_at = EXCLUDED.computed_at;

DO $verify_seed$
DECLARE
    month_count INTEGER;
    average_salary NUMERIC(24,4);
BEGIN
    SELECT COUNT(*), AVG(salary_inflow)
    INTO month_count, average_salary
    FROM banking.account_monthly_summary
    WHERE account_id = '60000000-0000-4000-8000-000000000001'
      AND year_month >= (
          date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
          - INTERVAL '11 months'
      )::DATE;

    IF month_count <> 12 THEN
        RAISE EXCEPTION 'Demo customer A must have 12 monthly summaries, found %', month_count;
    END IF;

    IF average_salary <> 22000000.0000 THEN
        RAISE EXCEPTION 'Demo customer A salary average must be 22000000, found %', average_salary;
    END IF;
END
$verify_seed$;

COMMIT;
