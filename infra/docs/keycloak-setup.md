# Keycloak setup

Keycloak provides authentication, OIDC tokens, realm roles and service accounts.
It does not store the workbench employee business profile. PostgreSQL
`identity.employee.identity_subject` links an employee to the immutable JWT
`sub` claim.

## Realm and endpoints

The realm name is exactly `bank-ai`.

| Endpoint | Local public URL | Docker-internal URL |
| --- | --- | --- |
| Issuer | `http://localhost:8080/realms/bank-ai` | `http://keycloak:8080/realms/bank-ai` |
| Authorization | `http://localhost:8080/realms/bank-ai/protocol/openid-connect/auth` | `http://keycloak:8080/realms/bank-ai/protocol/openid-connect/auth` |
| Token | `http://localhost:8080/realms/bank-ai/protocol/openid-connect/token` | `http://keycloak:8080/realms/bank-ai/protocol/openid-connect/token` |
| JWKS | `http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs` | `http://keycloak:8080/realms/bank-ai/protocol/openid-connect/certs` |
| Logout | `http://localhost:8080/realms/bank-ai/protocol/openid-connect/logout` | `http://keycloak:8080/realms/bank-ai/protocol/openid-connect/logout` |
| Discovery | `http://localhost:8080/realms/bank-ai/.well-known/openid-configuration` | `http://keycloak:8080/realms/bank-ai/.well-known/openid-configuration` |

Local HTTP is for Docker development. Production uses HTTPS and a public issuer
that exactly matches the token `iss` claim.

## Clients

| Client | Type and flow | Secret | Required configuration |
| --- | --- | --- | --- |
| `bank-ai-frontend` | Public; Authorization Code Flow with PKCE S256 | None | Redirect URI `http://localhost:3000/*`; web origin `http://localhost:3000`; Direct Access Grants disabled; service account disabled |
| `bank-ai-backend` | Confidential service client | `KEYCLOAK_BACKEND_CLIENT_SECRET` from `.env.local` | Service account enabled; token audience includes `bank-ai-api` |
| `bank-ai-worker` | Confidential service client | `KEYCLOAK_WORKER_CLIENT_SECRET` from `.env.local` | Service account enabled; token audience includes `bank-ai-api` |

The frontend must never receive either confidential client secret. Browser login
uses PKCE and validates `state`, `nonce`, issuer and token signature. Password
grant is not enabled for the public client. Demo-user Direct Access Grant, if
used solely by the infrastructure smoke test, must be constrained to a dedicated
confidential verification path and not weaken the public-client configuration.

## Realm roles

The realm contains exactly these business-facing roles:

```text
credit_officer
credit_manager
document_reviewer
compliance_officer
risk_officer
loan_approver
auditor
admin
```

Realm roles express coarse authorization claims. The backend must still resolve
`sub` to `identity.employee`, verify active employment and use PostgreSQL
branch/customer/loan scopes and RLS. A Keycloak `admin` realm role does not imply
PostgreSQL `SUPERUSER` or `BYPASSRLS`.

## Demo identities

Only synthetic local identities are bootstrapped:

```text
credit.officer@example.local
credit.manager@example.local
document.reviewer@example.local
compliance@example.local
approver@example.local
auditor@example.local
admin@example.local
```

Their password comes from `SEED_USER_PASSWORD` in untracked `.env.local` and is
injected by the user bootstrap script. Passwords are deliberately absent from
the realm JSON, logs and documentation. The seven corresponding employee rows
in PostgreSQL use each Keycloak subject as `identity_subject`.

## Bootstrap

1. Start PostgreSQL and confirm the `keycloak` database and `keycloak_app` role.
2. Start Keycloak with bootstrap administrator credentials from `.env.local`.
3. Import/update the realm definition idempotently.
4. Apply confidential client secrets at runtime from `.env.local`.
5. Create/update synthetic users and set `SEED_USER_PASSWORD` without printing it.
6. Verify realm, clients, roles, discovery/JWKS and token claims.

The realm export is declarative and contains no secret values. Bootstrap may
look up resource IDs by stable client/user/role names but must not create renamed
duplicates on repeated execution.

## Token validation contract

Every backend/worker validates all of the following before trusting claims:

- a supported signature algorithm and a key from the realm JWKS;
- exact issuer `http://localhost:8080/realms/bank-ai` for host-local tokens (or
  the environment-specific exact issuer in deployed environments);
- audience `bank-ai-api`;
- `exp`, `nbf` and reasonable clock skew;
- expected client/authorized-party context and required realm roles; and
- a valid, active PostgreSQL employee mapping for human requests.

JWKS may be cached in Redis with a bounded TTL. An unknown `kid` triggers one
safe refresh; it never disables signature, issuer or audience verification.
Tokens, authorization codes and client secrets must not be logged.

## Smoke verification

The stack verification checks:

1. realm discovery returns issuer `.../realms/bank-ai`;
2. all three clients and all eight roles exist;
3. the seven demo users exist;
4. a demo token can be obtained using the supported test path;
5. the signature validates against JWKS and `aud` contains `bank-ai-api`; and
6. the public frontend client has no secret, requires PKCE S256 and has Direct
   Access Grants disabled.

Never report token verification successful based only on an HTTP 200 response;
inspect and validate the token claims without printing the raw token.
