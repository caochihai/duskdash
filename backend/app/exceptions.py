"""Safe application exceptions and stable API error codes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AppError(Exception):
    """Base error whose message and details are safe to return to callers."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.status_code = status
        self.details = dict(details or {})


class AuthenticationError(AppError):
    def __init__(
        self,
        code: str = "AUTHENTICATION_FAILED",
        message: str = "Authentication is required.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, 401, details)


class AuthorizationError(AppError):
    def __init__(
        self,
        code: str = "ACCESS_DENIED",
        message: str = "You do not have permission to access this resource.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, 403, details)


class NotFoundError(AppError):
    def __init__(
        self,
        code: str = "RESOURCE_NOT_FOUND",
        message: str = "The requested resource was not found.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, 404, details)


class ConflictError(AppError):
    def __init__(
        self,
        code: str = "RESOURCE_CONFLICT",
        message: str = "The request conflicts with the current resource state.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, 409, details)


class ValidationError(AppError):
    def __init__(
        self,
        code: str = "VALIDATION_FAILED",
        message: str = "The request is invalid.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, 422, details)


class DependencyUnavailableError(AppError):
    def __init__(
        self,
        code: str = "DEPENDENCY_UNAVAILABLE",
        message: str = "A required dependency is unavailable.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, 503, details)
