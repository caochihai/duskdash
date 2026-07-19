"""Azure Document Intelligence `prebuilt-read` — toạ độ dòng chữ chính xác.

Vai trò trong pipeline highlight: gemma-4-31B vẫn PHÂN TÍCH (mức độ, lý do,
căn cứ pháp lý, checklist thiếu) — Azure chỉ cung cấp bbox từng dòng để khung
đánh dấu khớp tuyệt đối với hồ sơ. Không có Azure (thiếu env/lỗi mạng) thì
pipeline giữ nguyên bbox do vision model ước lượng.
"""

from __future__ import annotations

import asyncio
import base64
import unicodedata
from dataclasses import dataclass

import httpx

from app.logging import get_logger

logger = get_logger(__name__)

_API_PATH = "/documentintelligence/documentModels/prebuilt-read:analyze"


@dataclass(frozen=True, slots=True)
class OcrLine:
    """Một dòng chữ với toạ độ chuẩn hoá 0..1 theo khổ trang."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


def fold_vietnamese(value: str) -> str:
    """Bỏ dấu + thường hoá để so khớp chuỗi tiếng Việt bền vững."""
    decomposed = unicodedata.normalize("NFD", value.lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").strip()


class AzureReadClient:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        api_version: str = "2024-11-30",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=endpoint.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Ocp-Apim-Subscription-Key": api_key},
        )
        self._api_version = api_version

    async def analyze(self, image: bytes) -> list[OcrLine]:
        """Trả về các dòng chữ kèm bbox chuẩn hoá; lỗi thì trả [] (fallback)."""
        try:
            submit = await self._client.post(
                _API_PATH,
                params={"api-version": self._api_version},
                json={"base64Source": base64.b64encode(image).decode()},
            )
            submit.raise_for_status()
            operation_url = submit.headers.get("operation-location")
            if not operation_url:
                return []

            payload: dict = {}
            for _ in range(30):
                await asyncio.sleep(1.5)
                poll = await self._client.get(operation_url)
                poll.raise_for_status()
                payload = poll.json()
                if payload.get("status") in ("succeeded", "failed"):
                    break
            if payload.get("status") != "succeeded":
                logger.warning("AZURE_READ_NOT_SUCCEEDED", status=payload.get("status"))
                return []

            lines: list[OcrLine] = []
            for page in payload.get("analyzeResult", {}).get("pages", []):
                width = float(page.get("width") or 1)
                height = float(page.get("height") or 1)
                for line in page.get("lines", []):
                    polygon = line.get("polygon") or []
                    if len(polygon) < 8 or not line.get("content"):
                        continue
                    xs = polygon[0::2]
                    ys = polygon[1::2]
                    lines.append(
                        OcrLine(
                            text=str(line["content"]),
                            x0=min(xs) / width,
                            y0=min(ys) / height,
                            x1=max(xs) / width,
                            y1=max(ys) / height,
                        )
                    )
            return lines
        except Exception:
            logger.exception("AZURE_READ_FAILED")
            return []

    async def aclose(self) -> None:
        await self._client.aclose()


def match_segment_bbox(segment_text: str, lines: list[OcrLine]) -> list[int] | None:
    """Tìm bbox 0-1000 cho đoạn trích bằng cách khớp với các dòng OCR.

    Ưu tiên: các dòng là chuỗi con của đoạn (đoạn dài gộp nhiều dòng) -> union
    bbox. Không có thì tìm dòng CHỨA đoạn. Không khớp -> None (giữ bbox model).
    """
    folded_segment = fold_vietnamese(segment_text)
    if len(folded_segment) < 4:
        return None

    contained = [
        line
        for line in lines
        if len(fold_vietnamese(line.text)) >= 4 and fold_vietnamese(line.text) in folded_segment
    ]
    if not contained:
        containing = [
            line
            for line in lines
            if folded_segment in fold_vietnamese(line.text)
        ]
        if not containing:
            return None
        best = min(containing, key=lambda line: len(line.text))
        contained = [best]

    # Cùng một chuỗi (vd. tên khách) có thể xuất hiện nhiều nơi trên trang;
    # union tất cả sẽ phủ gần cả trang. Gom các dòng thành cụm liền kề theo
    # trục dọc và chỉ lấy cụm khớp được nhiều ký tự nhất.
    contained.sort(key=lambda line: line.y0)
    clusters: list[list[OcrLine]] = [[contained[0]]]
    for line in contained[1:]:
        if line.y0 - clusters[-1][-1].y1 > 0.03:
            clusters.append([line])
        else:
            clusters[-1].append(line)
    cluster = max(clusters, key=lambda group: sum(len(fold_vietnamese(line.text)) for line in group))

    x0 = min(line.x0 for line in cluster)
    y0 = min(line.y0 for line in cluster)
    x1 = max(line.x1 for line in cluster)
    y1 = max(line.y1 for line in cluster)
    return [round(x0 * 1000), round(y0 * 1000), round(x1 * 1000), round(y1 * 1000)]
