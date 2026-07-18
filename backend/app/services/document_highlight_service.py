"""Đọc hồ sơ đính kèm bằng vision-LLM và trả về bản highlight theo mức độ.

Mức độ highlight của từng đoạn do model quyết định dựa trên BA nguồn:
câu hỏi hiện tại (input), dữ liệu khách hàng (context) và các trao đổi
trước đó trong hội thoại (memory). Kết quả gồm bản trích xuất có đánh dấu
(critical/warning/emphasis) kèm lý do, và ảnh gốc được vẽ khung màu tại các
vùng cần chú ý rồi đưa lại cho người dùng qua presigned URL.
"""

from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.logging import get_logger
from app.providers.llm.base import LLMProvider
from app.storage.interface import Storage

logger = get_logger(__name__)

_MAX_IMAGES = 5
_MAX_IMAGE_BYTES = 8 * 1024 * 1024

_LEVEL_ICON = {"critical": "🔴", "warning": "🟠", "emphasis": "🟡"}
_LEVEL_LABEL = {"critical": "CẢNH BÁO", "warning": "CẦN CHÚ Ý", "emphasis": "NHẤN MẠNH"}
_LEVEL_COLOR = {"critical": (220, 38, 38), "warning": (243, 112, 33), "emphasis": (234, 179, 8)}

_SYSTEM_PROMPT = (
    "Bạn là chuyên gia thẩm định hồ sơ ngân hàng SHB. Nhiệm vụ: đọc (các) ảnh "
    "hồ sơ đính kèm, trích xuất nội dung và ĐÁNH DẤU những phần đáng chú ý.\n"
    "Chọn mức độ highlight cho từng đoạn dựa trên cả ba nguồn:\n"
    "- CÂU HỎI của cán bộ (điều họ đang cần tìm);\n"
    "- DỮ LIỆU KHÁCH HÀNG trong hệ thống (đối chiếu khớp/lệch);\n"
    "- LỊCH SỬ HỘI THOẠI (những mối quan tâm đã nêu trước đó).\n"
    "Mức độ: 'critical' = sai lệch/rủi ro/mâu thuẫn với dữ liệu hệ thống; "
    "'warning' = cần kiểm tra thêm hoặc liên quan trực tiếp câu hỏi; "
    "'emphasis' = thông tin chính đáng lưu ý. Chỉ đánh dấu đoạn thực sự "
    "đáng chú ý, không đánh dấu tràn lan.\n"
    "Với mỗi đoạn đánh dấu trên ảnh, cung cấp bbox_2d = [x1, y1, x2, y2] theo "
    "thang 0-1000 so với kích thước ảnh (góc trên-trái là 0,0). Nếu không "
    "định vị được thì để bbox_2d = null.\n"
    "Nếu hồ sơ ghi rõ họ tên khách hàng, điền vào extracted_customer_name "
    "(đúng nguyên văn, không suy đoán).\n"
    "TUYỆT ĐỐI không bịa nội dung không có trong ảnh."
)


class HighlightSegment(BaseModel):
    document_index: int = Field(ge=0, description="Ảnh thứ mấy (0-based)")
    text: str = Field(min_length=1, max_length=2000)
    level: str = Field(pattern="^(critical|warning|emphasis)$")
    reason: str = Field(min_length=1, max_length=500)
    bbox_2d: list[int] | None = Field(default=None, description="[x1,y1,x2,y2] thang 0-1000")


class HighlightResult(BaseModel):
    document_summary: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000, description="Trả lời câu hỏi của cán bộ")
    segments: list[HighlightSegment] = Field(default_factory=list)
    extracted_customer_name: str | None = Field(
        default=None,
        max_length=200,
        description="Họ tên đầy đủ của khách hàng đọc được từ hồ sơ (null nếu không có)",
    )


@dataclass(frozen=True)
class AnnotatedImage:
    key: str
    url: str


def render_highlight_markdown(result: HighlightResult, links: list[AnnotatedImage]) -> str:
    """Dựng nội dung trả lời: câu trả lời + bản trích xuất highlight + link ảnh."""
    lines = [result.answer, "", "**📄 Bản hồ sơ đã highlight:**", "", result.document_summary]
    if result.segments:
        lines.append("")
        for segment in result.segments:
            icon = _LEVEL_ICON.get(segment.level, "•")
            label = _LEVEL_LABEL.get(segment.level, segment.level)
            lines.append(f"> {icon} **[{label}]** “{segment.text}”")
            lines.append(f"> ↳ _{segment.reason}_")
            lines.append(">")
    if links:
        lines.append("")
        lines.append("**🖼 Ảnh hồ sơ đã đánh dấu vùng cần chú ý:**")
        for index, link in enumerate(links, start=1):
            lines.append(f"- [Hồ sơ đã highlight — trang {index}]({link.url})")
    return "\n".join(lines)


class DocumentHighlighter:
    """Đọc ảnh hồ sơ, sinh highlight và vẽ khung màu trả lại người dùng."""

    def __init__(self, vision_llm: LLMProvider, storage: Storage | None) -> None:
        self._vision = vision_llm
        self._storage = storage

    @property
    def model_name(self) -> str:
        return self._vision.model_name

    async def analyze(
        self,
        *,
        question: str,
        customer_context: dict[str, Any],
        memory_lines: list[str],
        images: list[bytes],
    ) -> HighlightResult:
        images = [img for img in images if len(img) <= _MAX_IMAGE_BYTES][:_MAX_IMAGES]
        memory_block = "\n".join(memory_lines[-8:]) or "(chưa có trao đổi trước đó)"
        user_prompt = (
            f"CÂU HỎI CỦA CÁN BỘ:\n{question}\n\n"
            f"DỮ LIỆU KHÁCH HÀNG (JSON):\n{json.dumps(customer_context, ensure_ascii=False, default=str)[:6000]}\n\n"
            f"LỊCH SỬ HỘI THOẠI GẦN NHẤT:\n{memory_block}\n\n"
            f"Số ảnh hồ sơ đính kèm: {len(images)} (đánh số từ 0)."
        )
        return await self._vision.generate_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=HighlightResult,
            images=images,
        )

    async def annotate_and_upload(
        self,
        *,
        images: list[bytes],
        result: HighlightResult,
        conversation_id: str,
    ) -> list[AnnotatedImage]:
        """Vẽ khung màu theo bbox lên ảnh gốc rồi upload lấy presigned URL."""
        if self._storage is None:
            return []
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            logger.warning("HIGHLIGHT_PIL_MISSING")
            return []

        by_image: dict[int, list[HighlightSegment]] = {}
        for segment in result.segments:
            if segment.bbox_2d and len(segment.bbox_2d) == 4:
                by_image.setdefault(segment.document_index, []).append(segment)

        annotated: list[AnnotatedImage] = []
        for index, segments in sorted(by_image.items()):
            if index >= len(images):
                continue
            try:
                image = Image.open(io.BytesIO(images[index])).convert("RGB")
                overlay = ImageDraw.Draw(image, "RGBA")
                width, height = image.size
                for segment in segments:
                    x1, y1, x2, y2 = segment.bbox_2d  # type: ignore[misc]
                    box = (
                        max(0, min(x1, x2) * width // 1000),
                        max(0, min(y1, y2) * height // 1000),
                        min(width, max(x1, x2) * width // 1000),
                        min(height, max(y1, y2) * height // 1000),
                    )
                    if box[2] - box[0] < 4 or box[3] - box[1] < 4:
                        continue
                    color = _LEVEL_COLOR.get(segment.level, (243, 112, 33))
                    overlay.rectangle(box, outline=color + (255,), width=max(3, width // 300))
                    overlay.rectangle(box, fill=color + (40,))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90)
                key = f"highlights/{conversation_id}/{uuid.uuid4().hex}-{index}.jpg"
                await self._storage.put_object(
                    "generated-reports", key, buffer.getvalue(), content_type="image/jpeg"
                )
                presigned = await self._storage.create_presigned_get(
                    "generated-reports", key, expires_in_seconds=3600
                )
                url = presigned.url if hasattr(presigned, "url") else str(presigned)
                annotated.append(AnnotatedImage(key=key, url=url))
            except Exception:
                logger.exception("HIGHLIGHT_ANNOTATE_FAILED", image_index=index)
        return annotated
