# Redis local configuration

Redis is an authenticated, temporary cache and fan-out service. The password is
in the ignored `.env.local`; Compose supplies it with `--requirepass`. AOF and
periodic snapshots improve local restart behavior, but PostgreSQL remains the
source of truth. Keys must use the `bank-ai:` namespaces documented in
`docs/redis-usage.md`.

