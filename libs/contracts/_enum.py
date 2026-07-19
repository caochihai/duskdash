"""StrEnum tương thích (Python 3.11+ có sẵn; fallback cho môi trường cũ).

libs/contracts KHÔNG phụ thuộc vào code của backend (`app.*`) để 3 service
import độc lập được.
"""

from __future__ import annotations

try:  # Python 3.11+
    from enum import StrEnum
except ImportError:  # pragma: no cover
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        pass


__all__ = ["StrEnum"]
