"""Stable, non-leaking error responses."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppError
from app.logging import get_logger
from app.schemas.common import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


def _trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", uuid4()))


def _response(request: Request, *, status: int, code: str, message: str, details: dict[str, Any]) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            trace_id=_trace_id(request),
        )
    )
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content=payload.model_dump(mode="json"), headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _response(
            request,
            status=exc.status,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        safe_errors = [
            {"location": list(error.get("loc", ())), "message": error.get("msg"), "type": error.get("type")}
            for error in exc.errors()
        ]
        return _response(
            request,
            status=422,
            code="REQUEST_VALIDATION_FAILED",
            message="The request is invalid.",
            details={"errors": safe_errors},
        )

    @app.exception_handler(PermissionError)
    async def handle_permission_error(request: Request, exc: PermissionError) -> JSONResponse:
        del exc
        return _response(
            request,
            status=403,
            code="ACCESS_DENIED",
            message="You do not have permission to access this resource.",
            details={},
        )

    @app.exception_handler(LookupError)
    async def handle_lookup_error(request: Request, exc: LookupError) -> JSONResponse:
        del exc
        return _response(
            request,
            status=404,
            code="RESOURCE_NOT_FOUND",
            message="The requested resource was not found.",
            details={},
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        # ValueError trong service là thông điệp validation viết cho người dùng
        # (không chứa nội bộ hệ thống) — trả về cho client và ghi log để trace
        # được nguyên nhân 422 từ phía server.
        logger.info("VALIDATION_REJECTED", path=request.url.path, reason=str(exc))
        return _response(
            request,
            status=422,
            code="VALIDATION_FAILED",
            message="The request is invalid.",
            details={"reason": str(exc)},
        )

    @app.exception_handler(TimeoutError)
    async def handle_timeout_error(request: Request, exc: TimeoutError) -> JSONResponse:
        del exc
        return _response(
            request,
            status=410,
            code="RESOURCE_EXPIRED",
            message="The requested operation has expired.",
            details={},
        )

    @app.exception_handler(RuntimeError)
    async def handle_runtime_error(request: Request, exc: RuntimeError) -> JSONResponse:
        del exc
        return _response(
            request,
            status=409,
            code="INVALID_STATE_TRANSITION",
            message="The operation is not valid in the current state.",
            details={},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        return _response(
            request,
            status=exc.status_code,
            code="HTTP_ERROR",
            message=message,
            details={},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("UNHANDLED_APPLICATION_ERROR", exc_info=exc)
        return _response(
            request,
            status=500,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            details={},
        )
