# Terraform Agent Instructions

Follow Terraform-specific module, provider, variable, and state-management rules here.

Rules:

- Keep Terraform configuration inside `infra/terraform/`.
- Do not commit `terraform.tfstate`, `.tfvars`, plan files, or real credentials.
- Prefer explicit variables and outputs.
- Keep provider and backend configuration easy to find.
