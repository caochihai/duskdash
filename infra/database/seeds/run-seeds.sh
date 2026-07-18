#!/usr/bin/env sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

seed_directory="${SEED_DIRECTORY:-/opt/bank/seeds}"

for seed_file in \
    R__seed_roles_permissions.sql \
    R__seed_reference_data.sql \
    R__seed_demo_customers.sql \
    R__seed_demo_transactions.sql
do
    full_path="${seed_directory}/${seed_file}"
    if [ ! -r "${full_path}" ]; then
        echo "Required seed file is missing or unreadable: ${full_path}" >&2
        exit 1
    fi

    echo "Applying ${seed_file}"
    psql \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --dbname="${PGDATABASE}" \
        --username="${PGUSER}" \
        --set=ON_ERROR_STOP=1 \
        --file="${full_path}"
done

echo "All repeatable seed files applied successfully."

