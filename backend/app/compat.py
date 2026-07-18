"""Python 3.10 compatibility shims.

Nguồn gốc: platform viết cho Python 3.12 (StrEnum, datetime.UTC đều là 3.11+).
Module này cho phép chạy trên 3.10 mà không đổi hành vi trên 3.11+/3.12
(trên bản mới dùng thẳng builtin).
"""
from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from datetime import UTC  # noqa: F401
    from enum import StrEnum  # noqa: F401
else:
    from datetime import timezone
    from enum import Enum

    UTC = timezone.utc

    class StrEnum(str, Enum):
        """Backport hành vi enum.StrEnum (3.11+): str()/format trả về value."""

        def __str__(self) -> str:  # noqa: D105
            return str(self.value)

        def __format__(self, format_spec: str) -> str:  # noqa: D105
            return format(str(self.value), format_spec)
