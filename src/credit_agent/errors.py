"""Internal exceptions used to map failures to safe public decisions."""

from __future__ import annotations


class CreditAgentError(Exception):
    """Base class for controlled agent failures."""


class ToolExecutionError(CreditAgentError):
    """A mandatory read tool failed or returned an error status."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"{tool_name}: {message}")


class ToolBudgetExceeded(CreditAgentError):
    """The configured maximum number of tool calls was exceeded."""


class AgentDeadlineExceeded(CreditAgentError):
    """The absolute task deadline elapsed."""


class PermissionScopeError(CreditAgentError):
    """The task does not authorize all required read operations."""

    def __init__(self, missing_scopes: set[str]) -> None:
        self.missing_scopes = frozenset(missing_scopes)
        super().__init__("Missing allowed scopes: " + ", ".join(sorted(missing_scopes)))

