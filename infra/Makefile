SHELL := /bin/sh

COMPOSE = docker compose --env-file versions.env --env-file .env.local \
	-f docker-compose.infra.yml -f docker-compose.tools.yml -f docker-compose.observability.yml

.PHONY: secrets bootstrap infra-up infra-down infra-reset infra-logs infra-ps \
	db-migrate db-seed db-shell db-verify kafka-init kafka-topics kafka-acls \
	kafka-smoke kafka-describe minio-init minio-verify keycloak-init keycloak-verify \
	tools-up observability-up verify clean

secrets:
	./scripts/generate-secrets.sh

bootstrap:
	./scripts/bootstrap.sh

infra-up:
	$(COMPOSE) up -d --wait --wait-timeout 300 postgres redis kafka minio keycloak

infra-down:
	$(COMPOSE) down --remove-orphans

infra-reset:
	@printf 'This removes every local infrastructure volume. Type RESET to continue: '; \
	read answer; [ "$$answer" = RESET ] || { echo 'Reset cancelled.'; exit 1; }; \
	$(COMPOSE) down --volumes --remove-orphans

infra-logs:
	$(COMPOSE) logs --tail 200 -f

infra-ps:
	$(COMPOSE) ps

db-migrate:
	$(COMPOSE) run --rm flyway

db-seed:
	$(COMPOSE) run --rm db-seed

db-shell:
	$(COMPOSE) exec postgres psql -U bank_migrator -d bank_ai

db-verify:
	$(COMPOSE) exec -T postgres psql -U postgres -d bank_ai -v ON_ERROR_STOP=1 \
		-c "SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto','citext','uuid-ossp') ORDER BY extname;"

kafka-init:
	$(COMPOSE) run --rm kafka-init

kafka-topics:
	$(COMPOSE) run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/create-topics.sh

kafka-acls:
	$(COMPOSE) run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/create-acls.sh

kafka-smoke:
	$(COMPOSE) run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/smoke-test.sh

kafka-describe:
	$(COMPOSE) run --rm --entrypoint /bin/bash kafka-init /opt/bank/kafka/scripts/describe.sh

minio-init:
	$(COMPOSE) run --rm minio-init

minio-verify:
	$(COMPOSE) run --rm --entrypoint /bin/sh minio-init /opt/bank/minio/smoke-test.sh

keycloak-init:
	$(COMPOSE) run --rm keycloak-init

keycloak-verify:
	$(COMPOSE) run --rm keycloak-smoke

tools-up:
	$(COMPOSE) --profile tools up -d pgadmin kafka-ui

observability-up:
	$(COMPOSE) --profile observability up -d prometheus grafana

verify:
	./scripts/verify-stack.sh

clean:
	@find . -type f \( -name '*.log' -o -name '*.tmp' \) -delete
