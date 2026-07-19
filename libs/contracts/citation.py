"""Citation — hạt nhân provenance cho đánh nguồn kiểu NotebookLM.

Mỗi luận điểm của agent trỏ tới một hoặc nhiều Citation; Citation kiểu DOCUMENT
mang bbox (từ OCR) để frontend highlight đúng vùng trên tài liệu gốc.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from libs.contracts._enum import StrEnum
from libs.contracts.geometry import BBox


class SourceType(StrEnum):
    DOCUMENT = "DOCUMENT"  # trỏ vào tài liệu đã OCR (có bbox) → highlight được
    POLICY = "POLICY"      # trỏ vào điều khoản chính sách
    RECORD = "RECORD"      # bản ghi DB (financials, transaction)
    SQL = "SQL"            # kết quả truy vấn thống kê


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str                       # ổn định trong phạm vi một báo cáo
    source_type: SourceType
    quote: str                    # đoạn nguyên văn được trích

    # Trỏ nguồn — field nào có giá trị tuỳ source_type:
    document_id: UUID | None = None
    bbox: BBox | None = None                 # BẮT BUỘC khi source_type=DOCUMENT
    char_span: tuple[int, int] | None = None
    policy_clause_id: str | None = None      # khi source_type=POLICY
    record_id: UUID | None = None            # khi source_type=RECORD
    sql_query_id: str | None = None          # khi source_type=SQL
    confidence: float | None = None
