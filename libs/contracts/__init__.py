"""Shared cross-service contracts (Platform / Engine / OCR).

Nguồn chân lý duy nhất cho schema I/O giữa 3 máy. Cả 3 service import từ đây
để không lệch hợp đồng. Xem docs/redesign/api-contracts.md.
"""

from libs.contracts.analysis import (
    AgentRoute,
    AnalysisMode,
    AnalysisRequest,
    AnalysisResponse,
    AuthorizedScope,
)
from libs.contracts.citation import Citation, SourceType
from libs.contracts.document import (
    DOCUMENT_READY_STATES,
    DocumentStatus,
    OcrJob,
    documents_ready,
)
from libs.contracts.geometry import BBox
from libs.contracts.ocr import (
    DocumentOCR,
    OcrExtractRequest,
    OcrField,
    OcrLine,
    OcrPage,
    OcrWord,
    RedactionRequest,
    RedactionResult,
)
from libs.contracts.report import (
    Claim,
    ComposedClaim,
    ComposedReport,
    ComposedSection,
    Domain,
    DomainReport,
    ReportStatus,
    collect_citations,
)

__all__ = [
    "BBox",
    "Citation",
    "SourceType",
    "AgentRoute",
    "AnalysisMode",
    "AnalysisRequest",
    "AnalysisResponse",
    "AuthorizedScope",
    "Claim",
    "ComposedClaim",
    "ComposedReport",
    "ComposedSection",
    "Domain",
    "DomainReport",
    "ReportStatus",
    "collect_citations",
    "DocumentStatus",
    "DOCUMENT_READY_STATES",
    "documents_ready",
    "OcrJob",
    "DocumentOCR",
    "OcrExtractRequest",
    "OcrField",
    "OcrLine",
    "OcrPage",
    "OcrWord",
    "RedactionRequest",
    "RedactionResult",
]
