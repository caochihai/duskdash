"""Mock OCR — sinh bbox giả nhưng HỢP LỆ để chạy/test highlight khi chưa có Azure.

Tách text theo dòng, mỗi dòng một dải y, mỗi từ một bbox con — đủ để toàn bộ
luồng (lưu toạ độ → resolve citation → highlight → bôi đen) chạy end-to-end.
"""

from __future__ import annotations

from uuid import UUID

from libs.contracts.geometry import BBox
from libs.contracts.ocr import DocumentOCR, OcrLine, OcrPage, OcrWord

_PAGE_W = 1000.0
_PAGE_H = 1400.0


def _clamp01(v: float) -> float:
    return 0.001 if v <= 0 else 0.999 if v >= 1 else v


class MockOcrProvider:
    provider = "mock"
    model = "mock-ocr-1"

    async def extract(
        self, content: bytes, *, mime_type: str, document_id: UUID
    ) -> DocumentOCR:
        text = content.decode("utf-8", errors="replace")
        if not text.strip() or text.count("�") > max(3, len(text) // 4):
            text = "MOCK OCR DOCUMENT\nDòng ví dụ số 1\nDòng ví dụ số 2"

        page_texts = text.split("\f")
        pages: list[OcrPage] = []
        for pi, ptext in enumerate(page_texts, start=1):
            raw = [ln for ln in ptext.splitlines() if ln.strip()] or ["MOCK OCR"]
            band = 1.0 / (len(raw) + 1)
            lines: list[OcrLine] = []
            for li, line in enumerate(raw):
                y = _clamp01((li + 0.3) * band)
                h = max(min(band * 0.6, 0.999 - y), 0.005)
                line_w = min(0.9, 0.012 * len(line) + 0.05)
                lines.append(
                    OcrLine(
                        text=line,
                        bbox=BBox(page=pi, x=0.05, y=y, w=max(line_w, 0.02), h=h),
                        confidence=0.99,
                        words=tuple(self._words(line, pi, y, h, line_w)),
                    )
                )
            pages.append(
                OcrPage(page=pi, width=_PAGE_W, height=_PAGE_H, unit="pixel",
                        lines=tuple(lines))
            )

        full_text = "\n".join(ln.text for p in pages for ln in p.lines)
        return DocumentOCR(
            document_id=document_id, provider=self.provider, model=self.model,
            full_text=full_text, pages=tuple(pages),
        )

    @staticmethod
    def _words(line: str, page: int, y: float, h: float, total_w: float) -> list[OcrWord]:
        tokens = line.split()
        if not tokens:
            return []
        total_chars = sum(len(t) for t in tokens)
        gap = total_w * 0.02
        cur = 0.05
        out: list[OcrWord] = []
        for t in tokens:
            frac = (len(t) / total_chars) if total_chars else 1.0 / len(tokens)
            x = _clamp01(cur)
            w = max(min(total_w * frac, 0.999 - x), 0.005)
            out.append(
                OcrWord(text=t, bbox=BBox(page=page, x=x, y=y, w=w, h=h), confidence=0.99)
            )
            cur = x + w + gap
            if cur >= 0.999:
                break
        return out
