"""Rule-based account gate evaluated after token validation, before principal lookup."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


@dataclass(frozen=True, slots=True)
class LoginRuleVerdict:
    allowed: bool
    rule: str = ""
    reason: str = ""


_ALLOW = LoginRuleVerdict(allowed=True)


def _csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class LoginRuleEngine:
    """Declarative allow/deny rules for authenticated identities.

    Every rule is optional; an engine with no configured rules allows everyone.
    Evaluation order: deny list, allow patterns, required roles, access window.
    Usernames are compared case-insensitively.
    """

    deny_usernames: frozenset[str] = frozenset()
    allow_username_patterns: tuple[str, ...] = ()
    required_roles: frozenset[str] = frozenset()
    access_window_utc: tuple[time, time] | None = None

    @classmethod
    def from_settings(cls, settings: "Settings") -> "LoginRuleEngine":
        window: tuple[time, time] | None = None
        raw_window = settings.login_rules_access_window_utc.strip()
        if raw_window:
            start_raw, separator, end_raw = raw_window.partition("-")
            if not separator:
                raise ValueError(
                    "LOGIN_RULES_ACCESS_WINDOW_UTC must look like 'HH:MM-HH:MM'"
                )
            window = (time.fromisoformat(start_raw.strip()), time.fromisoformat(end_raw.strip()))
        return cls(
            deny_usernames=frozenset(
                name.casefold() for name in _csv(settings.login_rules_deny_usernames)
            ),
            allow_username_patterns=tuple(
                pattern.casefold() for pattern in _csv(settings.login_rules_allow_username_patterns)
            ),
            required_roles=frozenset(_csv(settings.login_rules_required_roles)),
            access_window_utc=window,
        )

    def evaluate(
        self,
        *,
        username: str | None,
        roles: frozenset[str],
        now: datetime | None = None,
    ) -> LoginRuleVerdict:
        normalized = (username or "").casefold()

        if normalized and normalized in self.deny_usernames:
            return LoginRuleVerdict(
                allowed=False,
                rule="deny_usernames",
                reason="This account is blocked by an access rule.",
            )

        if self.allow_username_patterns and not any(
            fnmatch.fnmatchcase(normalized, pattern)
            for pattern in self.allow_username_patterns
        ):
            return LoginRuleVerdict(
                allowed=False,
                rule="allow_username_patterns",
                reason="This account does not match the allowed account patterns.",
            )

        if self.required_roles and not roles.intersection(self.required_roles):
            return LoginRuleVerdict(
                allowed=False,
                rule="required_roles",
                reason="This account has none of the roles required to enter the system.",
            )

        if self.access_window_utc is not None:
            current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).time()
            start, end = self.access_window_utc
            inside = start <= current <= end if start <= end else current >= start or current <= end
            if not inside:
                return LoginRuleVerdict(
                    allowed=False,
                    rule="access_window_utc",
                    reason="Access is not allowed at this time of day.",
                )

        return _ALLOW
