# Naming Conventions

## Folders

- Use lowercase folder names.
- Use clear domain or technology names, for example `backend`, `frontend`, `infra`, `terraform`, `docs`.
- Keep Terraform under `infra/terraform/`.
- Keep agent-facing technical documentation under `docs/agent/`.
- Keep business documentation under `docs/business/`.

## Files

- Use `README.md` as the entry point for a folder.
- Use `AGENTS.md` for coding-agent instructions.
- Use kebab-case for documentation files, for example `user-flows.md`.

## Secrets

- Do not store real secret values in Git.
- Use `.example` or `.sample` files for templates.
