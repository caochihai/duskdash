"""One-line structured logging with context propagation and secret redaction."""

from __future__ import annotations

import logging as stdlib_logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

_SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|token|password|passwd|secret|api[_-]?key|credential|database_url|redis_url|presigned)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_QUERY_SECRET = re.compile(
    r"(?i)(X-Amz-(?:Signature|Credential|Security-Token)|token|api_key|password)=([^&\s]+)"
)
_ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(password|secret|token|api[_-]?key)\s*[=:]\s*([^,;\s]+)"
)


def redact_text(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _QUERY_SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return _ASSIGNMENT_SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def redact_value(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(item_key): redact_value(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact_value(item) for item in value]
    return value


def redact_sensitive(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor that removes secrets recursively."""

    for key in list(event_dict):
        event_dict[key] = redact_value(event_dict[key], key)
    return event_dict


def configure_logging(level: str = "INFO", output_format: str = "json") -> None:
    """Configure stdlib logging and structlog exactly once per process setup."""

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp")
    shared_processors: list[Any] = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        redact_sensitive,
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: Any
    if output_format == "console":
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    stdlib_logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(stdlib_logging, level.upper(), stdlib_logging.INFO),
        force=True,
    )
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(stdlib_logging, level.upper(), stdlib_logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)


__all__ = [
    "bind_contextvars",
    "clear_contextvars",
    "configure_logging",
    "get_logger",
    "redact_sensitive",
    "redact_text",
    "redact_value",
]
