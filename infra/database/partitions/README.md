# Transaction partitions

`banking.transaction` is range-partitioned by the UTC `booking_time` month.
Migration V005 creates all monthly partitions for the current and previous
calendar years plus a default partition.

Create the next year before traffic reaches it:

    psql -v ON_ERROR_STOP=1 -v target_year=2027 \
      -f database/partitions/create-future-partitions.sql

Run the script as `bank_migrator`. It is idempotent, preserves the required
parent indexes on new partitions, and revokes direct child-table access so all
runtime queries continue through the RLS-protected parent.

Rows that reached `banking.transaction_default` must be moved in a controlled
maintenance window before creating an overlapping partition; PostgreSQL will
reject an overlapping partition while matching rows remain in the default
partition.
