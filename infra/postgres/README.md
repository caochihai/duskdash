# PostgreSQL local configuration

The local instance listens on port 5432, requires SCRAM-SHA-256 for TCP
connections, logs slow statements without parameter values, and stores all
timestamps in UTC. The one local `postgres` trust rule is required only for the
official image's first-boot initialization scripts inside the container.

Runtime roles are created by `database/bootstrap`; Flyway owns schema objects.
PostgreSQL is attached only to `bank-data`, never to `bank-edge`.

