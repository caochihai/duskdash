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

_LEVEL_ICON = {"critical": "🔴", "warning": "🟠", "emphasis": "🟡", "pass": "✅"}
_LEVEL_LABEL = {
    "critical": "CẢNH BÁO",
    "warning": "CẦN CHÚ Ý",
    "emphasis": "NHẤN MẠNH",
    "pass": "ĐẠT ĐIỀU KIỆN",
}
_LEVEL_COLOR = {
    "critical": (220, 38, 38),
    "warning": (243, 112, 33),
    "emphasis": (234, 179, 8),
    "pass": (34, 197, 94),
}

_SYSTEM_PROMPT = (
    "Bạn là chuyên gia thẩm định hồ sơ ngân hàng SHB. Nhiệm vụ: đọc (các) ảnh "
    "hồ sơ đính kèm, trích xuất nội dung và ĐÁNH DẤU những phần đáng chú ý.\n"
    "Chọn mức độ highlight cho từng đoạn dựa trên cả ba nguồn:\n"
    "- CÂU HỎI của cán bộ (điều họ đang cần tìm);\n"
    "- DỮ LIỆU KHÁCH HÀNG trong hệ thống (đối chiếu khớp/lệch);\n"
    "- LỊCH SỬ HỘI THOẠI (những mối quan tâm đã nêu trước đó).\n"
    "Mức độ: 'critical' = sai lệch/rủi ro/vi phạm quy định; "
    "'warning' = cần kiểm tra thêm hoặc liên quan trực tiếp câu hỏi; "
    "'emphasis' = thông tin chính đáng lưu ý; "
    "'pass' = nội dung ĐÃ THOẢ MÃN điều kiện/quy định (hãy chủ động đánh dấu "
    "cả những phần đạt chuẩn để cán bộ yên tâm bỏ qua). Chỉ đánh dấu đoạn "
    "thực sự đáng chú ý, không đánh dấu tràn lan.\n"
    "MỌI highlight đều phải có CĂN CỨ PHÁP LÝ trong legal_basis: nêu văn bản "
    "pháp luật/quy định áp dụng (vd: Thông tư 39/2016/TT-NHNN về hoạt động "
    "cho vay; Thông tư 11/2021/TT-NHNN về phân loại nợ; Luật Các TCTD 2024; "
    "Luật Phòng chống rửa tiền 2022; chuẩn mực kế toán VAS). CHỈ nêu văn bản "
    "có thật và đúng phạm vi áp dụng; nếu không chắc văn bản nào, ghi "
    "'Cần đối chiếu quy định nội bộ SHB'.\n"
    "Với mỗi đoạn đánh dấu trên ảnh, cung cấp bbox_2d = [x1, y1, x2, y2] theo "
    "thang 0-1000 so với kích thước ảnh: (0,0) là góc trên-trái, x tăng sang "
    "phải, y tăng xuống dưới; y1/y2 phải bao TRỌN chiều cao của dòng chữ liên "
    "quan (vị trí dọc phải thật chính xác). Nếu không định vị được thì để "
    "bbox_2d = null.\n"
    "Nếu hồ sơ ghi rõ họ tên khách hàng, điền vào extracted_customer_name "
    "(đúng nguyên văn, không suy đoán).\n"
    "Luôn đề xuất 3-5 câu hỏi tiếp theo trong suggested_questions — những câu "
    "cán bộ NÊN hỏi dựa trên nội dung hồ sơ (đặc biệt quan trọng khi cán bộ "
    "gửi hồ sơ mà chưa kèm câu hỏi: hãy chủ động tóm tắt và dẫn dắt).\n"
    "KIỂM TRA TÍNH ĐẦY ĐỦ: xác định loại hồ sơ (vay cá nhân mua nhà, vay SME "
    "vốn lưu động, thế chấp...) rồi đối chiếu với checklist chuẩn — vd: "
    "CCCD/hộ chiếu, đăng ký kinh doanh, BCTC 2 năm gần nhất, sao kê tài "
    "khoản 6 tháng, hợp đồng/giấy tờ tài sản đảm bảo (sổ đỏ, đăng ký xe), "
    "chứng thư thẩm định giá, phương án sử dụng vốn & trả nợ (bắt buộc theo "
    "Thông tư 39/2016/TT-NHNN), giấy tờ chứng minh thu nhập. Giấy tờ nào "
    "checklist cần mà KHÔNG thấy trong (các) ảnh thì liệt kê vào "
    "missing_documents kèm lý do cần và căn cứ; hồ sơ đã đủ thì để trống. "
    "Trong answer, nếu thiếu thông tin để kết luận, hãy nói rõ đang thiếu gì "
    "và đề nghị cán bộ upload bổ sung để phân tích tiếp.\n"
    "TUYỆT ĐỐI không bịa nội dung không có trong ảnh."
)


class HighlightSegment(BaseModel):
    document_index: int = Field(ge=0, description="Ảnh thứ mấy (0-based)")
    text: str = Field(min_length=1, max_length=2000)
    level: str = Field(pattern="^(critical|warning|emphasis|pass)$")
    reason: str = Field(min_length=1, max_length=500)
    legal_basis: str | None = Field(
        default=None,
        max_length=300,
        description="Văn bản pháp luật/quy định làm căn cứ cho highlight này",
    )
    bbox_2d: list[int] | None = Field(default=None, description="[x1,y1,x2,y2] thang 0-1000")


class MissingDocument(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Tên giấy tờ còn thiếu")
    reason: str = Field(min_length=1, max_length=300, description="Vì sao cần giấy tờ này")
    legal_basis: str | None = Field(default=None, max_length=300)


class HighlightResult(BaseModel):
    document_summary: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000, description="Trả lời câu hỏi của cán bộ")
    segments: list[HighlightSegment] = Field(default_factory=list)
    extracted_customer_name: str | None = Field(
        default=None,
        max_length=200,
        description="Họ tên đầy đủ của khách hàng đọc được từ hồ sơ (null nếu không có)",
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="3-5 câu hỏi tiếp theo cán bộ nên hỏi dựa trên nội dung hồ sơ",
    )
    missing_documents: list[MissingDocument] = Field(
        default_factory=list,
        max_length=8,
        description="Giấy tờ còn thiếu so với checklist chuẩn của loại hồ sơ này",
    )


@dataclass(frozen=True)
class AnnotatedImage:
    key: str
    url: str


def render_highlight_markdown(result: HighlightResult, links: list[AnnotatedImage]) -> str:
    """Dựng nội dung trả lời: câu trả lời + bản trích xuất highlight + link ảnh."""
    # Các segment KHÔNG chèn vào text: client render danh sách dẫn chứng
    # tương tác từ metadata.highlight_segments (bấm mở đúng vùng trên ảnh).
    lines = [result.answer, "", "**📄 Tóm tắt hồ sơ:**", "", result.document_summary]
    # Ảnh đã highlight không chèn link vào text — client render gallery riêng
    # từ metadata.highlight_documents (chat giữ vai trò tương tác thuần).
    del links
    if result.missing_documents:
        lines.append("")
        lines.append("**📋 Hồ sơ còn thiếu — cần bổ sung để tiếp tục phân tích:**")
        for index, item in enumerate(result.missing_documents[:8], start=1):
            basis = f" _(⚖️ {item.legal_basis})_" if item.legal_basis else ""
            lines.append(f"{index}. **{item.name}** — {item.reason}{basis}")
        lines.append("")
        lines.append(
            "> 📎 Đính kèm các giấy tờ trên ngay trong hội thoại này, "
            "SH-AI sẽ phân tích tiếp và cập nhật kết luận."
        )
    if result.suggested_questions:
        lines.append("")
        lines.append("**💡 Gợi ý câu hỏi tiếp theo:**")
        lines.extend(
            f"{index}. {question}"
            for index, question in enumerate(result.suggested_questions[:5], start=1)
        )
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
        # Mỗi ảnh upload luôn có một bản output (kể cả khi model không định vị
        # được vùng nào) để danh sách nút ảnh khớp 1-1 với hồ sơ người dùng gửi.
        for index in range(len(images)):
            segments = by_image.get(index, [])
            try:
                image = Image.open(io.BytesIO(images[index])).convert("RGB")
                overlay = ImageDraw.Draw(image, "RGBA")
                width, height = image.size
                margin = max(4, width // 60)
                for segment in segments:
                    x1, y1, x2, y2 = segment.bbox_2d  # type: ignore[misc]
                    # Vision model bắt vị trí DỌC của dòng khá chuẩn nhưng hay
                    # lệch toạ độ ngang -> vẽ dải highlight full chiều ngang
                    # theo dòng (kiểu bút dạ quang), nới nhẹ chiều cao cho dễ đọc.
                    top = max(0, min(y1, y2) * height // 1000 - height // 200)
                    bottom = min(height, max(y1, y2) * height // 1000 + height // 200)
                    if bottom - top < 6:
                        bottom = min(height, top + max(6, height // 90))
                    band = (margin, top, width - margin, bottom)
                    color = _LEVEL_COLOR.get(segment.level, (243, 112, 33))
                    overlay.rectangle(band, fill=color + (46,))
                    # Vạch màu đậm sát mép trái như tab đánh dấu mức độ.
                    overlay.rectangle(
                        (margin, top, margin + max(6, width // 150), bottom),
                        fill=color + (230,),
                    )
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90)
                key = f"highlights/{conversation_id}/{uuid.uuid4().hex}-{index}.jpg"
                await self._storage.put_object(
                    "generated-reports", key, buffer.getvalue(), content_type="image/jpeg"
                )
                presigned = await self._storage.create_presigned_get(
                    "generated-reports", key, expires_in_seconds=600
                )
                url = presigned.url if hasattr(presigned, "url") else str(presigned)
                annotated.append(AnnotatedImage(key=key, url=url))
            except Exception:
                logger.exception("HIGHLIGHT_ANNOTATE_FAILED", image_index=index)
        return annotated
