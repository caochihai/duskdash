"""Document metadata, upload sessions and human verification persistence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import (
    Record,
    execute_returning,
    fetch_all,
    fetch_one,
    insert_sql,
    require_fields,
)

_UPLOAD_COLUMNS = frozenset(
    {
        "id",
        "customer_id",
        "loan_application_id",
        "expected_document_type",
        "original_filename",
        "expected_mime_type",
        "expected_size_bytes",
        "expected_sha256",
        "quarantine_object_key",
        "status",
        "expires_at",
        "completed_at",
        "created_by",
        "idempotency_key",
        "created_at",
    }
)
_UPLOAD_REQUIRED = (
    "id",
    "customer_id",
    "original_filename",
    "expected_mime_type",
    "expected_size_bytes",
    "expected_sha256",
    "quarantine_object_key",
    "status",
    "expires_at",
    "created_by",
    "idempotency_key",
    "created_at",
)
_DOCUMENT_COLUMNS = frozenset(
    {
        "id",
        "document_type",
        "document_subtype",
        "title",
        "owner_party_id",
        "classification",
        "document_date",
        "valid_from",
        "valid_until",
        "verification_status",
        "processing_status",
        "created_by",
        "created_at",
        "updated_at",
        "version",
    }
)
_VERSION_COLUMNS = frozenset(
    {
        "id",
        "document_id",
        "version_number",
        "original_object_id",
        "original_filename",
        "mime_type",
        "file_size",
        "sha256",
        "uploaded_by",
        "uploaded_at",
        "scan_status",
        "is_current",
        "created_at",
    }
)


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_upload(self, values: Mapping[str, Any]) -> Record:
        require_fields(values, _UPLOAD_REQUIRED)
        row = await execute_returning(
            self.session,
            insert_sql("storage.upload_session", values, _UPLOAD_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Upload session insert returned no row")
        return row

    async def get_upload(self, upload_id: UUID, actor_id: UUID | None = None) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT us.*
            FROM storage.upload_session AS us
            WHERE us.id = :upload_id
              AND (CAST(:actor_id AS UUID) IS NULL
                   OR us.created_by = CAST(:actor_id AS UUID))
              AND identity.can_access_customer(
                  identity.current_employee_id(), us.customer_id
              )
            """,
            {"upload_id": upload_id, "actor_id": actor_id},
        )

    async def complete_upload(
        self,
        *,
        upload_id: UUID,
        object_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        job_id: UUID,
        correlation_id: UUID,
        outbox_id: UUID,
        actor_id: UUID,
        steps: tuple[str, ...],
        event: Mapping[str, Any],
        headers: Mapping[str, Any],
    ) -> Record:
        now = datetime.now(UTC)
        upload = await execute_returning(
            self.session,
            """
            UPDATE storage.upload_session AS us
            SET status = 'COMPLETED', completed_at = :completed_at
            WHERE us.id = :upload_id
              AND us.created_by = :actor_id
              AND us.status IN ('CREATED', 'UPLOADING')
              AND us.expires_at > CURRENT_TIMESTAMP
              AND identity.can_access_customer(
                  identity.current_employee_id(), us.customer_id
              )
            RETURNING us.*
            """,
            {
                "upload_id": upload_id,
                "actor_id": actor_id,
                "completed_at": now,
            },
        )
        if upload is None:
            raise RuntimeError("Upload completion conflicted or was unauthorized")

        await execute_returning(
            self.session,
            """
            INSERT INTO storage.object_metadata (
                id, bucket_name, object_key, object_version_id, etag, sha256,
                size_bytes, mime_type, storage_class, encryption_type,
                retention_until, legal_hold, created_by, created_at, deleted_at
            ) VALUES (
                :object_id, 'upload-quarantine', :object_key, NULL, NULL,
                :sha256, :size_bytes, :mime_type, 'STANDARD', 'SSE-S3',
                NULL, FALSE, :actor_id, :now, NULL
            ) RETURNING id
            """,
            {
                "object_id": object_id,
                "object_key": upload["quarantine_object_key"],
                "sha256": upload["expected_sha256"],
                "size_bytes": upload["expected_size_bytes"],
                "mime_type": upload["expected_mime_type"],
                "actor_id": actor_id,
                "now": now,
            },
        )
        document = await execute_returning(
            self.session,
            """
            INSERT INTO document.document (
                id, document_type, document_subtype, title, owner_party_id,
                classification, document_date, valid_from, valid_until,
                verification_status, processing_status, created_by,
                created_at, updated_at, version
            )
            SELECT :document_id, COALESCE(:document_type, 'UNCLASSIFIED'),
                   NULL, :title, c.party_id, 'CONFIDENTIAL', NULL, NULL, NULL,
                   'UNVERIFIED', 'QUEUED', :actor_id, :now, :now, 1
            FROM customer.customer AS c WHERE c.id = :customer_id
            RETURNING *
            """,
            {
                "document_id": document_id,
                "document_type": upload["expected_document_type"],
                "title": upload["original_filename"],
                "actor_id": actor_id,
                "now": now,
                "customer_id": upload["customer_id"],
            },
        )
        if document is None:
            raise RuntimeError("Customer is missing or unauthorized")
        await execute_returning(
            self.session,
            """
            INSERT INTO document.document_version (
                id, document_id, version_number, original_object_id,
                original_filename, mime_type, file_size, sha256, uploaded_by,
                uploaded_at, scan_status, is_current, created_at
            ) VALUES (
                :version_id, :document_id, 1, :object_id, :filename,
                :mime_type, :file_size, :sha256, :actor_id, :now,
                'PENDING', TRUE, :now
            ) RETURNING id
            """,
            {
                "version_id": document_version_id,
                "document_id": document_id,
                "object_id": object_id,
                "filename": upload["original_filename"],
                "mime_type": upload["expected_mime_type"],
                "file_size": upload["expected_size_bytes"],
                "sha256": upload["expected_sha256"],
                "actor_id": actor_id,
                "now": now,
            },
        )
        await execute_returning(
            self.session,
            """
            INSERT INTO document.document_link (
                id, document_id, entity_type, entity_id,
                relationship_type, created_at
            ) VALUES (
                :link_id, :document_id, 'CUSTOMER', :customer_id,
                'SUBMITTED_DOCUMENT', :now
            ) RETURNING id
            """,
            {
                "link_id": uuid4(),
                "document_id": document_id,
                "customer_id": upload["customer_id"],
                "now": now,
            },
        )
        if upload.get("loan_application_id"):
            await execute_returning(
                self.session,
                """
                INSERT INTO document.document_link (
                    id, document_id, entity_type, entity_id,
                    relationship_type, created_at
                )
                SELECT :link_id, :document_id, 'LOAN_APPLICATION', la.id,
                       'SUBMITTED_DOCUMENT', :now
                FROM credit.loan_application AS la WHERE la.id = :loan_id
                RETURNING id
                """,
                {
                    "link_id": uuid4(),
                    "document_id": document_id,
                    "loan_id": upload["loan_application_id"],
                    "now": now,
                },
            )
        await execute_returning(
            self.session,
            """
            INSERT INTO integration.background_job (
                id, job_type, resource_type, resource_id, status,
                progress_percent, current_step, correlation_id, requested_by,
                priority, attempt_count, max_attempts, scheduled_at,
                created_at, updated_at, version
            ) VALUES (
                :job_id, 'DOCUMENT_PROCESSING', 'DOCUMENT_VERSION', :version_id,
                'QUEUED', 0, 'AWAITING_PUBLICATION', :correlation_id, :actor_id,
                5, 0, 5, :now, :now, :now, 1
            ) RETURNING id
            """,
            {
                "job_id": job_id,
                "version_id": document_version_id,
                "correlation_id": correlation_id,
                "actor_id": actor_id,
                "now": now,
            },
        )
        for order, step_code in enumerate(steps):
            await execute_returning(
                self.session,
                """
                INSERT INTO integration.background_job_step (
                    id, job_id, step_code, step_order, status,
                    progress_percent, attempt_count, created_at, updated_at
                ) VALUES (
                    :id, :job_id, :step_code, :step_order, 'QUEUED',
                    0, 0, :now, :now
                ) RETURNING id
                """,
                {
                    "id": uuid4(),
                    "job_id": job_id,
                    "step_code": step_code,
                    "step_order": order,
                    "now": now,
                },
            )
        await execute_returning(
            self.session,
            """
            INSERT INTO integration.event_outbox (
                id, aggregate_type, aggregate_id, event_type, event_version,
                partition_key, payload, headers, status, attempt_count,
                available_at, created_at
            ) VALUES (
                :outbox_id, 'DOCUMENT_VERSION', :version_id,
                'document.processing.requested', 1, :partition_key,
                CAST(:event AS jsonb), CAST(:headers AS jsonb),
                'PENDING', 0, :now, :now
            ) RETURNING id
            """,
            {
                "outbox_id": outbox_id,
                "version_id": document_version_id,
                # asyncpg suy kiểu theo THAM SỐ: dùng lại :version_id (uuid) trong
                # CAST(... AS text) sẽ gây AmbiguousParameterError, nên truyền chuỗi riêng.
                "partition_key": str(document_version_id),
                "event": event,
                "headers": headers,
                "now": now,
            },
        )
        return {
            **upload,
            "object_id": object_id,
            "document_id": document_id,
            "document_version_id": document_version_id,
            "job_id": job_id,
            "correlation_id": correlation_id,
            "outbox_id": outbox_id,
        }

    async def create_document(self, values: Mapping[str, Any]) -> Record:
        row = await execute_returning(
            self.session,
            insert_sql("document.document", values, _DOCUMENT_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Document insert returned no row")
        return row

    async def create_version(self, values: Mapping[str, Any]) -> Record:
        row = await execute_returning(
            self.session,
            insert_sql("document.document_version", values, _VERSION_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Document version insert returned no row")
        return row

    async def get_document(self, document_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT d.*, dv.id AS current_version_id,
                   dv.version_number AS current_version_number,
                   dv.mime_type AS current_mime_type,
                   dv.file_size AS current_file_size,
                   dv.scan_status AS current_scan_status
            FROM document.document AS d
            LEFT JOIN document.document_version AS dv
              ON dv.document_id = d.id AND dv.is_current
            WHERE d.id = :document_id
            """,
            {"document_id": document_id},
        )

    async def get_versions(self, document_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT dv.* FROM document.document_version AS dv
            JOIN document.document AS d ON d.id = dv.document_id
            WHERE d.id = :document_id
            ORDER BY dv.version_number DESC
            """,
            {"document_id": document_id},
        )

    async def get_version(self, document_version_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT dv.*, d.document_type, d.owner_party_id,
                   d.verification_status, d.processing_status,
                   om.bucket_name, om.object_key, om.object_version_id,
                   om.etag, om.encryption_type, om.legal_hold
            FROM document.document_version AS dv
            JOIN document.document AS d ON d.id = dv.document_id
            JOIN storage.object_metadata AS om ON om.id = dv.original_object_id
            WHERE dv.id = :version_id
            """,
            {"version_id": document_version_id},
        )

    async def get_processing(self, document_version_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT pj.* FROM document.document_version AS dv
            JOIN document.processing_job AS pj ON pj.document_version_id = dv.id
            WHERE dv.id = :version_id ORDER BY pj.created_at, pj.id
            """,
            {"version_id": document_version_id},
        )

    async def get_fields(self, document_version_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT ef.* FROM document.extracted_field AS ef
            JOIN document.document_version AS dv ON dv.id = ef.document_version_id
            WHERE dv.id = :version_id
            ORDER BY ef.page_number NULLS LAST, ef.field_name, ef.id
            """,
            {"version_id": document_version_id},
        )

    async def update_field(
        self,
        field_id: UUID,
        corrected_value_text: str | None,
        verification_status: str,
        verified_by: UUID,
        verification_reason: str,
    ) -> Record | None:
        """Store a correction without overwriting immutable OCR/source values."""
        if not verification_reason.strip():
            raise ValueError("verification_reason is required")
        return await execute_returning(
            self.session,
            """
            UPDATE document.extracted_field AS ef
            SET corrected_value_text = :corrected_value_text,
                verification_status = :verification_status,
                verified_by = :verified_by,
                verified_at = CURRENT_TIMESTAMP,
                verification_reason = :verification_reason,
                updated_at = CURRENT_TIMESTAMP
            FROM document.document_version AS dv
            WHERE ef.id = :field_id
              AND dv.id = ef.document_version_id
              AND EXISTS (
                  SELECT 1 FROM document.document AS d
                  WHERE d.id = dv.document_id
              )
            RETURNING ef.*
            """,
            {
                "field_id": field_id,
                "corrected_value_text": corrected_value_text,
                "verification_status": verification_status,
                "verified_by": verified_by,
                "verification_reason": verification_reason,
            },
        )

    async def list_pages(self, document_version_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT dp.* FROM document.document_page AS dp
            JOIN document.document_version AS dv ON dv.id = dp.document_version_id
            WHERE dv.id = :version_id
            ORDER BY dp.page_number
            """,
            {"version_id": document_version_id},
        )
