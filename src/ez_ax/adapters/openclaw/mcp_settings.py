"""Typed construction inputs for a modeled MCP-backed OpenClaw adapter.

This module is configuration-only scaffolding. It does not perform any MCP
invocation or browser-facing work.
"""

from __future__ import annotations

from dataclasses import dataclass

from ez_ax.models.errors import ConfigError


def _require_normalized_setting(*, label: str, value: str) -> str:
    if not isinstance(value, str):
        msg = f"OpenClaw MCP setting '{label}' must be a string"
        raise ConfigError(msg)
    if not value:
        msg = f"OpenClaw MCP setting '{label}' must be non-empty"
        raise ConfigError(msg)
    if not value.strip():
        msg = f"OpenClaw MCP setting '{label}' must not be whitespace-only"
        raise ConfigError(msg)
    if value != value.strip():
        msg = (
            f"OpenClaw MCP setting '{label}' must not have leading or trailing "
            "whitespace"
        )
        raise ConfigError(msg)
    return value


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Typed retry settings for modeled MCP transport failures."""

    max_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int):
            msg = "RetryPolicy.max_attempts must be an int"
            raise ConfigError(msg)
        if self.max_attempts < 1:
            msg = "RetryPolicy.max_attempts must be >= 1"
            raise ConfigError(msg)


@dataclass(frozen=True, slots=True)
class McpOpenClawAdapterSettings:
    """Required construction inputs for a modeled MCP-backed OpenClaw adapter."""

    mcp_server_name: str
    tool_name: str
    default_timeout_seconds: float
    retry_policy: RetryPolicy
    session_label: str | None = None

    def __post_init__(self) -> None:
        _require_normalized_setting(label="mcp_server_name", value=self.mcp_server_name)
        _require_normalized_setting(label="tool_name", value=self.tool_name)

        if not isinstance(self.default_timeout_seconds, (float, int)):
            msg = "OpenClaw MCP setting 'default_timeout_seconds' must be a number"
            raise ConfigError(msg)
        if self.default_timeout_seconds <= 0:
            msg = "OpenClaw MCP setting 'default_timeout_seconds' must be > 0"
            raise ConfigError(msg)

        if not isinstance(self.retry_policy, RetryPolicy):
            msg = "OpenClaw MCP setting 'retry_policy' must be a RetryPolicy"
            raise ConfigError(msg)

        if self.session_label is None:
            return
        _require_normalized_setting(label="session_label", value=self.session_label)
