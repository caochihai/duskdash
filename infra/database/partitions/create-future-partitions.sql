\set ON_ERROR_STOP on

\if :{?target_year}
\else
    \echo 'target_year is required, for example: -v target_year=2027'
    \quit 2
\endif

WITH requested_year AS (
    SELECT :'target_year'::INTEGER AS target_year
),
monthly_bounds AS (
    SELECT
        requested_year.target_year,
        month_number,
        make_timestamptz(
            requested_year.target_year,
            month_number,
            1,
            0,
            0,
            0,
            'UTC'
        ) AS range_start
    FROM requested_year
    CROSS JOIN generate_series(1, 12) AS months(month_number)
)
SELECT format(
    'CREATE TABLE IF NOT EXISTS banking.%I PARTITION OF banking."transaction" FOR VALUES FROM (%L) TO (%L)',
    format(
        'transaction_%s_%s',
        target_year,
        lpad(month_number::TEXT, 2, '0')
    ),
    range_start,
    range_start + INTERVAL '1 month'
)
FROM monthly_bounds
ORDER BY month_number
\gexec

WITH child_partitions AS (
    SELECT child_namespace.nspname AS schema_name,
           child.relname AS table_name
    FROM pg_catalog.pg_inherits AS inheritance
    JOIN pg_catalog.pg_class AS child
      ON child.oid = inheritance.inhrelid
    JOIN pg_catalog.pg_namespace AS child_namespace
      ON child_namespace.oid = child.relnamespace
    JOIN pg_catalog.pg_class AS parent
      ON parent.oid = inheritance.inhparent
    JOIN pg_catalog.pg_namespace AS parent_namespace
      ON parent_namespace.oid = parent.relnamespace
    WHERE parent_namespace.nspname = 'banking'
      AND parent.relname = 'transaction'
      AND child.relname LIKE format('transaction_%s_%%', :'target_year')
)
SELECT format(
    'REVOKE ALL ON TABLE %I.%I FROM bank_app, bank_worker, bank_readonly',
    schema_name,
    table_name
)
FROM child_partitions
\gexec
