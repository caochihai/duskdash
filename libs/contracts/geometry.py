"""Toạ độ chuẩn hoá để highlight/bôi đen bất kể kích thước hiển thị.

BBox dùng toạ độ chuẩn hoá 0..1 (gốc trên-trái) nên frontend highlight đúng vùng
ở mọi mức zoom, và service bôi đen quy đổi lại ra pixel/point theo trang thật.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


class BBox(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(ge=1)
    x: float = Field(ge=0.0, le=1.0)  # góc trái, chuẩn hoá theo chiều rộng trang
    y: float = Field(ge=0.0, le=1.0)  # góc trên, chuẩn hoá theo chiều cao trang
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)

    @classmethod
    def from_polygon(
        cls,
        *,
        page: int,
        polygon: Sequence[float],
        page_width: float,
        page_height: float,
    ) -> "BBox":
        """Dựng BBox từ polygon Azure (8 số: x1,y1,x2,y2,x3,y3,x4,y4) cùng đơn vị trang."""
        if page_width <= 0 or page_height <= 0:
            raise ValueError("page_width/page_height phải > 0")
        xs = [polygon[i] for i in range(0, len(polygon), 2)]
        ys = [polygon[i] for i in range(1, len(polygon), 2)]
        if not xs or not ys:
            raise ValueError("polygon rỗng")
        x0 = _clamp(min(xs) / page_width)
        y0 = _clamp(min(ys) / page_height)
        x1 = _clamp(max(xs) / page_width)
        y1 = _clamp(max(ys) / page_height)
        w = min(max(x1 - x0, 1e-6), 1.0 - x0) or 1e-6
        h = min(max(y1 - y0, 1e-6), 1.0 - y0) or 1e-6
        return cls(page=page, x=x0, y=y0, w=w, h=h)

    def to_pixels(self, page_width: float, page_height: float) -> tuple[float, float, float, float]:
        """Quy đổi ngược ra (x0, y0, x1, y1) theo pixel/point của trang thật."""
        x0 = self.x * page_width
        y0 = self.y * page_height
        return x0, y0, x0 + self.w * page_width, y0 + self.h * page_height
