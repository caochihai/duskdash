"""Safe deterministic checks used before persisting an uploaded object."""

from __future__ import annotations


class DocumentSecurityError(ValueError):
    """Raised for a failed content/security gate with a safe message."""


class DeterministicSecurityScanner:
    allowed_mime_types = frozenset({"application/pdf", "image/png", "image/jpeg", "image/tiff"})

    def __init__(self, *, max_size_bytes: int = 50 * 1024 * 1024) -> None:
        if max_size_bytes < 1:
            raise ValueError("max document size must be positive")
        self._max_size = max_size_bytes

    async def scan(self, content: bytes, *, declared_mime_type: str) -> None:
        if not content:
            raise DocumentSecurityError("uploaded document is empty")
        if len(content) > self._max_size:
            raise DocumentSecurityError("uploaded document exceeds the configured size limit")
        if declared_mime_type not in self.allowed_mime_types:
            raise DocumentSecurityError("uploaded document MIME type is not allowed")
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
            raise DocumentSecurityError("security scan rejected the uploaded document")
