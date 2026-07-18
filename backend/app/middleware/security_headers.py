"""Security headers and runtime CORS policy."""

from __future__ import annotations

from collections.abc import Iterable

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                application = scope.get("app")
                settings = getattr(getattr(application, "state", None), "settings", None)
                if getattr(settings, "is_production", False):
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RuntimeCORSMiddleware:
    """CORS middleware that reads validated origins after lifespan startup."""

    def __init__(self, app: ASGIApp, allow_methods: Iterable[str] = ("GET", "POST", "PATCH", "PUT", "HEAD")) -> None:
        self.app = app
        self.allow_methods = ", ".join(allow_methods)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        application = scope.get("app")
        settings = getattr(getattr(application, "state", None), "settings", None)
        allowed_origins = set(getattr(settings, "app_cors_origins", []))
        allowed_origin = origin if origin is not None and origin in allowed_origins else None

        if scope["method"] == "OPTIONS" and headers.get("access-control-request-method"):
            from starlette.responses import PlainTextResponse

            if allowed_origin is None:
                await PlainTextResponse("CORS origin denied", status_code=403)(scope, receive, send)
                return
            response = PlainTextResponse("OK", status_code=200)
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
            response.headers["Access-Control-Allow-Methods"] = self.allow_methods
            response.headers["Access-Control-Allow-Headers"] = headers.get(
                "access-control-request-headers", "Authorization, Content-Type, Idempotency-Key"
            )
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers["Vary"] = "Origin"
            await response(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if allowed_origin is not None and message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["Access-Control-Allow-Origin"] = allowed_origin
                response_headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                response_headers["Vary"] = "Origin"
            await send(message)

        await self.app(scope, receive, send_with_cors)
