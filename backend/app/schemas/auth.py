"""Authentication-facing response schemas."""

from uuid import UUID

from app.schemas.common import APIModel


class MeResponse(APIModel):
    employee_id: UUID
    subject: str
    branch_id: UUID
    roles: list[str]
    permissions: list[str]
    is_admin: bool
