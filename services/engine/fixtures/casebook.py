"""Nạp 6 hồ sơ tín dụng mock + OCR thật → tra cứu theo customer_uuid / case_id.

- Dữ liệu tài chính/giao dịch: mock_6_credit_cases_full.json (thật về mặt cấu trúc,
  giả lập về số liệu — `is_simulated`).
- Dòng tài liệu (text + bbox): fixture OCR THẬT sinh bởi build_ocr_fixtures.py.
- customer_uuid = uuid5(customer_id) để khớp AuthorizedScope (UUID) của Platform.
"""

from __future__ import annotations

import functools
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_CASES_JSON = (_REPO / "Hồ sơ Doanh nghiệp, Khách hàng"
               / "mock_6_credit_cases_full_package" / "mock_6_credit_cases_full.json")
_OCR_DIR = _HERE / "ocr"
_NS = uuid.UUID("6f2df576-0504-4645-ae26-000000ca5e00")

# case_id → slug thư mục OCR (ổn định, không phụ thuộc thứ tự chạy OCR).
CASE_TO_SLUG = {
    "CR-A01": "cty-cp-vinanova",
    "CR-B02": "tnhh-mekong-flex",
    "CR-C03": "đại-thành-global",
    "CR-I01": "nguyễn-minh-khôi",
    "CR-I02": "lê-thị-thanh-hương",
    "CR-I03": "trần-quốc-bảo",
}


def customer_uuid(customer_id: str) -> uuid.UUID:
    return uuid.uuid5(_NS, customer_id)


@dataclass(frozen=True)
class OcrDocLine:
    document_id: uuid.UUID
    page: int
    text: str
    bbox: dict  # {page,x,y,w,h} chuẩn hoá 0..1
    confidence: float


@dataclass(frozen=True)
class CaseData:
    case_id: str
    customer_id: str
    customer_uuid: uuid.UUID
    customer_type: str          # CORPORATE | INDIVIDUAL
    name: str
    city: str
    risk_grade: str
    pd_12m: float
    decision_label: str
    kyc_status: str
    aml_status: str
    fraud_risk: str
    pep_flag: bool
    requested_limit: int
    recommended_limit: int
    metrics: dict | None        # doanh nghiệp
    income: dict | None         # cá nhân
    annual: dict
    months: list[dict]          # 12 tháng, đã sort theo period
    ocr_slug: str
    _ocr: dict = field(default=None, repr=False, compare=False)

    @property
    def latest_month(self) -> dict:
        return self.months[-1] if self.months else {}

    def document_lines(self, limit: int = 6) -> list[OcrDocLine]:
        """Trả các dòng OCR THẬT (ưu tiên tài liệu đầu — phiếu thông tin)."""
        if not self._ocr:
            return []
        out: list[OcrDocLine] = []
        for doc in self._ocr.get("documents", []):
            did = uuid.UUID(doc["document_id"])
            for page in doc.get("pages", []):
                for ln in page.get("lines", []):
                    b = ln["bbox"]
                    if ln.get("confidence", 0) < 0.5 or len(ln.get("text", "")) < 4:
                        continue
                    out.append(OcrDocLine(
                        document_id=did, page=int(b["page"]),
                        text=ln["text"], bbox=b, confidence=float(ln["confidence"])))
                    if len(out) >= limit:
                        return out
        return out


def _load_ocr(slug: str) -> dict | None:
    p = _OCR_DIR / f"{slug}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@functools.lru_cache(maxsize=1)
def _load() -> dict[uuid.UUID, CaseData]:
    raw = json.loads(_CASES_JSON.read_text(encoding="utf-8"))
    by_uuid: dict[uuid.UUID, CaseData] = {}
    for c in raw:
        cc, cu = c["credit_case"], c["customer"]
        cid = cu["customer_id"]
        case_id = cc["case_id"]
        slug = CASE_TO_SLUG.get(case_id, "")
        months = sorted(c.get("monthly_features", []), key=lambda m: m.get("period", ""))
        data = CaseData(
            case_id=case_id, customer_id=cid, customer_uuid=customer_uuid(cid),
            customer_type=cu["customer_type"],
            name=cu.get("legal_name") or cu.get("full_name") or cid,
            city=cu.get("city", ""),
            risk_grade=cc.get("risk_grade", ""), pd_12m=float(cc.get("pd_12m") or 0.0),
            decision_label=cc.get("decision_label", ""),
            kyc_status=cc.get("kyc_status", ""), aml_status=cc.get("aml_status", ""),
            fraud_risk=cc.get("fraud_risk", ""), pep_flag=bool(cu.get("pep_flag")),
            requested_limit=int(cc.get("requested_limit_vnd") or 0),
            recommended_limit=int(cc.get("recommended_limit_vnd") or 0),
            metrics=cc.get("metrics"), income=cc.get("income"),
            annual=cc.get("annual_transaction_summary", {}),
            months=months, ocr_slug=slug, _ocr=_load_ocr(slug))
        by_uuid[data.customer_uuid] = data
    return by_uuid


def all_cases() -> list[CaseData]:
    return list(_load().values())


def get_case(customer_uuid_: uuid.UUID) -> CaseData | None:
    return _load().get(customer_uuid_)


def by_case_id(case_id: str) -> CaseData | None:
    return next((c for c in _load().values() if c.case_id == case_id), None)


def reload() -> None:
    """Xoá cache (gọi sau khi OCR batch cập nhật fixture)."""
    _load.cache_clear()
