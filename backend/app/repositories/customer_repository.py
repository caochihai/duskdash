"""Customer queries rooted in the RLS-protected customer table."""

from __future__ import annotations

import builtins
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import (
    Record,
    database_params,
    execute_returning,
    fetch_all,
    fetch_one,
    pagination,
    rows_with_total,
)


DRAFT_CUSTOMER_NAME = "Khách hàng mới (hồ sơ đang trích xuất)"


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_draft(self, *, employee_id: UUID, branch_id: UUID) -> Record:
        """Tạo khách hàng nháp khi upload hồ sơ chưa gắn khách hàng.

        Tên hiển thị dùng placeholder DRAFT_CUSTOMER_NAME; vision-LLM sẽ cập
        nhật lại từ nội dung hồ sơ sau khi trích xuất. RLS insert policy yêu
        cầu khách hàng thuộc chi nhánh của nhân viên đang thao tác.
        """
        party_id = uuid4()
        customer_id = uuid4()
        cif = f"CIF-AUTO-{uuid4().hex[:8].upper()}"

        await execute_returning(
            self.session,
            """
            INSERT INTO customer.party (
                id, party_type, display_name, status, created_at, created_by,
                updated_at, updated_by, version
            ) VALUES (
                :party_id, 'PERSON', :display_name, 'ACTIVE',
                CURRENT_TIMESTAMP, :employee_id, CURRENT_TIMESTAMP, :employee_id, 1
            ) RETURNING id
            """,
            {"party_id": party_id, "display_name": DRAFT_CUSTOMER_NAME, "employee_id": employee_id},
        )
        await execute_returning(
            self.session,
            """
            INSERT INTO customer.person_profile (
                party_id, full_name, date_of_birth, gender, nationality,
                marital_status, occupation, updated_at
            ) VALUES (
                :party_id, :display_name, NULL, 'UNSPECIFIED', 'VN',
                'UNSPECIFIED', NULL, CURRENT_TIMESTAMP
            ) RETURNING party_id
            """,
            {"party_id": party_id, "display_name": DRAFT_CUSTOMER_NAME},
        )
        # KHÔNG dùng RETURNING: SELECT policy của customer tự tra lại bảng bằng
        # hàm STABLE nên không thấy row đang chèn trong cùng câu lệnh — RETURNING
        # sẽ luôn bị RLS chặn. SELECT lại bằng câu lệnh riêng thì qua bình thường
        # (nhân viên là relationship manager + cùng chi nhánh).
        await self.session.execute(
            text(
                """
            INSERT INTO customer.customer (
                id, party_id, customer_number, customer_segment, home_branch_id,
                relationship_manager_id, onboarding_date, kyc_status, risk_rating,
                risk_rating_as_of, status, created_at, updated_at, version
            ) VALUES (
                :customer_id, :party_id, :cif, 'MASS', :branch_id,
                :employee_id, CURRENT_DATE, 'PENDING', 'UNRATED',
                CURRENT_DATE, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
            )
            """
            ),
            database_params(
                {
                    "customer_id": customer_id,
                    "party_id": party_id,
                    "cif": cif,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                }
            ),
        )
        row = await self.get(customer_id)
        if row is None:
            raise RuntimeError("Draft customer creation failed")
        return row

    async def rename_draft_party(self, party_id: UUID, full_name: str) -> None:
        """Đặt tên thật cho khách hàng nháp sau khi vision trích xuất hồ sơ.

        Có guard LIKE để không bao giờ ghi đè tên của khách hàng thật.
        """
        await execute_returning(
            self.session,
            """
            UPDATE customer.party
            SET display_name = :full_name, updated_at = CURRENT_TIMESTAMP
            WHERE id = :party_id AND display_name LIKE 'Khách hàng mới%'
            RETURNING id
            """,
            {"party_id": party_id, "full_name": full_name},
        )
        await execute_returning(
            self.session,
            """
            UPDATE customer.person_profile
            SET full_name = :full_name, updated_at = CURRENT_TIMESTAMP
            WHERE party_id = :party_id AND full_name LIKE 'Khách hàng mới%'
            RETURNING party_id
            """,
            {"party_id": party_id, "full_name": full_name},
        )

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> tuple[builtins.list[Record], int]:
        limit, offset = pagination(page, page_size)
        term = search.strip() if search else None
        rows = await fetch_all(
            self.session,
            """
            SELECT c.id AS customer_id, c.party_id, c.customer_number,
                   c.customer_segment, c.home_branch_id,
                   c.relationship_manager_id, c.onboarding_date, c.kyc_status,
                   c.risk_rating, c.risk_rating_as_of, c.status, c.updated_at, c.version,
                   p.party_type, p.display_name, pp.full_name,
                   count(*) OVER () AS total_count
            FROM customer.customer AS c
            JOIN customer.party AS p ON p.id = c.party_id
            LEFT JOIN customer.person_profile AS pp ON pp.party_id = p.id
            WHERE (CAST(:term AS TEXT) IS NULL
                   OR c.customer_number ILIKE CAST(:pattern AS TEXT)
                   OR p.display_name ILIKE CAST(:pattern AS TEXT)
                   OR pp.full_name ILIKE CAST(:pattern AS TEXT))
            ORDER BY c.updated_at DESC, c.id
            LIMIT :limit OFFSET :offset
            """,
            {"term": term, "pattern": f"%{term}%" if term else None, "limit": limit, "offset": offset},
        )
        return rows_with_total(rows)

    async def get(self, customer_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT c.*, p.party_type, p.display_name, p.status AS party_status,
                   pp.full_name, pp.date_of_birth, pp.gender, pp.nationality,
                   pp.marital_status, pp.occupation
            FROM customer.customer AS c
            JOIN customer.party AS p ON p.id = c.party_id
            LEFT JOIN customer.person_profile AS pp ON pp.party_id = p.id
            WHERE c.id = :customer_id
            """,
            {"customer_id": customer_id},
        )

    async def overview(self, customer_id: UUID) -> Record | None:
        customer = await self.get(customer_id)
        if customer is None:
            return None
        party_id = customer["party_id"]
        customer["employment"] = await fetch_all(
            self.session,
            """SELECT * FROM customer.employment
               WHERE party_id = :party_id ORDER BY start_date DESC NULLS LAST, id""",
            {"party_id": party_id},
        )
        customer["income_sources"] = await fetch_all(
            self.session,
            """SELECT * FROM customer.income_source
               WHERE party_id = :party_id ORDER BY as_of_date DESC, id""",
            {"party_id": party_id},
        )
        customer["kyc_assessments"] = await fetch_all(
            self.session,
            """SELECT * FROM customer.kyc_assessment
               WHERE customer_id = :customer_id ORDER BY assessment_date DESC, id""",
            {"customer_id": customer_id},
        )
        return customer

    async def list_documents(self, customer_id: UUID) -> builtins.list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT DISTINCT d.*
            FROM customer.customer AS c
            JOIN document.document AS d
              ON d.owner_party_id = c.party_id
              OR EXISTS (
                  SELECT 1 FROM document.document_link AS dl
                  WHERE dl.document_id = d.id
                    AND dl.entity_type = 'CUSTOMER'
                    AND dl.entity_id = c.id
              )
            WHERE c.id = :customer_id
            ORDER BY d.updated_at DESC, d.id
            """,
            {"customer_id": customer_id},
        )

    async def list_loans(self, customer_id: UUID) -> builtins.list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT la.*, lp.product_code, lp.product_name
            FROM credit.loan_application AS la
            JOIN credit.loan_product AS lp ON lp.id = la.product_id
            WHERE la.primary_customer_id = :customer_id
            ORDER BY la.created_at DESC, la.id
            """,
            {"customer_id": customer_id},
        )

    async def can_access(self, customer_id: UUID) -> bool:
        row = await fetch_one(
            self.session,
            """
            SELECT identity.can_access_customer(
                identity.current_employee_id(), :customer_id
            ) AS allowed
            """,
            {"customer_id": customer_id},
        )
        return bool(row and row["allowed"])

    async def get_assignment(self, customer_id: UUID) -> Record | None:
        """Return the PostgreSQL-authoritative handler and optimistic version."""

        return await fetch_one(
            self.session,
            """
            SELECT id AS customer_id, relationship_manager_id AS assigned_employee_id,
                   version AS assignment_version, updated_at
            FROM customer.customer
            WHERE id = :customer_id
            """,
            {"customer_id": customer_id},
        )

    async def claim_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        expected_version: int,
    ) -> Record | None:
        """Atomically claim an unassigned customer or renew the same employee's claim."""

        return await execute_returning(
            self.session,
            """
            UPDATE customer.customer
            SET relationship_manager_id = :employee_id,
                updated_at = CURRENT_TIMESTAMP,
                version = version + 1
            WHERE id = :customer_id
              AND version = :expected_version
              AND (
                  relationship_manager_id IS NULL
                  OR relationship_manager_id = :employee_id
              )
            RETURNING id AS customer_id,
                      relationship_manager_id AS assigned_employee_id,
                      version AS assignment_version,
                      updated_at
            """,
            {
                "customer_id": customer_id,
                "employee_id": employee_id,
                "expected_version": expected_version,
            },
        )

    async def takeover_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        expected_version: int,
    ) -> Record | None:
        """Optimistically replace the handler; authorization is enforced by the service."""

        return await execute_returning(
            self.session,
            """
            WITH previous_assignment AS MATERIALIZED (
                SELECT id, relationship_manager_id AS previous_assigned_employee_id
                FROM customer.customer
                WHERE id = :customer_id AND version = :expected_version
                FOR UPDATE
            ), updated_assignment AS (
                UPDATE customer.customer AS customer_record
                SET relationship_manager_id = :employee_id,
                    updated_at = CURRENT_TIMESTAMP,
                    version = customer_record.version + 1
                FROM previous_assignment
                WHERE customer_record.id = previous_assignment.id
                  AND customer_record.version = :expected_version
                RETURNING customer_record.id AS customer_id,
                          customer_record.relationship_manager_id AS assigned_employee_id,
                          customer_record.version AS assignment_version,
                          customer_record.updated_at
            )
            SELECT updated_assignment.*,
                   previous_assignment.previous_assigned_employee_id
            FROM updated_assignment
            JOIN previous_assignment
              ON previous_assignment.id = updated_assignment.customer_id
            """,
            {
                "customer_id": customer_id,
                "employee_id": employee_id,
                "expected_version": expected_version,
            },
        )

    async def release_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        assignment_version: int,
    ) -> Record | None:
        """Release only the matching persistent owner and assignment generation."""

        return await execute_returning(
            self.session,
            """
            UPDATE customer.customer
            SET relationship_manager_id = NULL,
                updated_at = CURRENT_TIMESTAMP,
                version = version + 1
            WHERE id = :customer_id
              AND relationship_manager_id = :employee_id
              AND version = :assignment_version
            RETURNING id AS customer_id,
                      relationship_manager_id AS assigned_employee_id,
                      version AS assignment_version,
                      updated_at
            """,
            {
                "customer_id": customer_id,
                "employee_id": employee_id,
                "assignment_version": assignment_version,
            },
        )
