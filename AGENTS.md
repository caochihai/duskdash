# Agent Instructions

This is a multi-part project with separate backend, frontend, infrastructure, and business documentation.

## Read Order

Before editing code, read the most relevant files:

1. This `AGENTS.md`.
2. `docs/agent/project-overview.md`.
3. The nearest `AGENTS.md` in the area you are editing.
4. Relevant files under `docs/business/` when changing product behavior.

## Project Areas

- `backend/`: Backend application code.
- `frontend/`: Frontend application code.
- `infra/`: Infrastructure and deployment code.
- `infra/terraform/`: Terraform provisioning code.
- `docs/agent/`: Technical instructions for coding agents.
- `docs/business/`: Business and domain documentation.
- `secrets/`: Secret templates or encrypted secret files only.

## General Rules

- Keep backend, frontend, infrastructure, and business documentation separated.
- Do not commit real secrets, credentials, tokens, or local `.env` files.
- Follow the existing structure and naming conventions before adding new folders.
- If code behavior conflicts with business documentation, stop and ask before changing behavior.
