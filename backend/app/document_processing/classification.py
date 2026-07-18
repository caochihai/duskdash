"""Conservative deterministic document classification for mock mode."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Classification:
    document_type: str
    confidence: Decimal


class DeterministicClassifier:
    async def classify(self, text: str) -> Classification:
        normalized = text.casefold()
        candidates = (
            ("SALARY_SLIP", ("salary", "payslip", "bang luong", "phiếu lương")),
            ("BANK_STATEMENT", ("bank statement", "transaction", "sao ke", "sao kê")),
            ("IDENTITY_DOCUMENT", ("identity card", "passport", "citizen identification")),
            ("CREDIT_POLICY", ("credit policy", "loan policy", "chinh sach tin dung")),
        )
        for document_type, markers in candidates:
            if any(marker in normalized for marker in markers):
                return Classification(document_type, Decimal("0.95000"))
        return Classification("UNKNOWN", Decimal("0.40000"))
