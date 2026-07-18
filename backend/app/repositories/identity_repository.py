"""JWT subject to active employee/authorization resolution."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import EmployeeAccessRecord, PrincipalResolver
from app.repositories.base import fetch_one


class IdentityRepository(PrincipalResolver):
    """Resolve only the non-sensitive identity data needed by authentication."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, subject: str) -> EmployeeAccessRecord | None:
        normalized = subject.strip()
        if not normalized:
            return None
        row = await fetch_one(
            self.session,
            """
            SELECT e.id AS employee_id, e.identity_subject AS subject,
                   e.branch_id, e.employment_status AS status,
                   COALESCE(
                       array_agg(DISTINCT r.role_code::text)
                           FILTER (WHERE r.id IS NOT NULL), ARRAY[]::text[]
                   ) AS roles,
                   COALESCE(
                       array_agg(DISTINCT p.permission_code::text)
                           FILTER (WHERE p.id IS NOT NULL), ARRAY[]::text[]
                   ) AS permissions
            FROM identity.employee AS e
            LEFT JOIN identity.employee_role AS er
              ON er.employee_id = e.id
             AND er.valid_from <= CURRENT_TIMESTAMP
             AND (er.valid_until IS NULL OR er.valid_until > CURRENT_TIMESTAMP)
            LEFT JOIN identity.role AS r ON r.id = er.role_id
            LEFT JOIN identity.role_permission AS rp ON rp.role_id = r.id
            LEFT JOIN identity.permission AS p ON p.id = rp.permission_id
            WHERE e.identity_subject = :subject
              AND e.employment_status = 'ACTIVE'
            GROUP BY e.id, e.identity_subject, e.branch_id, e.employment_status
            """,
            {"subject": normalized},
        )
        if row is None:
            return None
        return EmployeeAccessRecord(
            employee_id=row["employee_id"],
            subject=str(row["subject"]),
            branch_id=row["branch_id"],
            status=str(row["status"]),
            roles=frozenset(str(value) for value in row["roles"]),
            permissions=frozenset(str(value) for value in row["permissions"]),
        )

