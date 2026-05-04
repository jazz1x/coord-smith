"""Typed runtime config + precedence resolution for MCP stdio acquisition.

.. note::
   **Inactive scaffold.** OpenClaw uses CLI subprocess transport, not MCP.
   The released path (``pyautogui_cli_entrypoint`` →
   ``run_released_scope_from_argv_env``) does not import any symbol from here.
   The scaffold is preserved per ``docs/prd.md`` Non-Goals: it documents the
   shape of an MCP transport if ever revived, but no MCP server is implemented.
   Do not add new dependencies on this module from the released path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ez_ax.models.errors import ConfigError


def require_normalized_str(*, label: str, value: object) -> str:
    if not isinstance(value, str):
        msg = f"MCP stdio constructor input '{label}' must be a string"
        raise ConfigError(msg)
    if not value:
        msg = f"MCP stdio constructor input '{label}' must be non-empty"
        raise ConfigError(msg)
    if not value.strip():
        msg = f"MCP stdio constructor input '{label}' must not be whitespace-only"
        raise ConfigError(msg)
    if value != value.strip():
        msg = (
            f"MCP stdio constructor input '{label}' must not have leading or trailing "
            "whitespace"
        )
        raise ConfigError(msg)
    return value


def require_args(*, label: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        msg = f"MCP stdio constructor input '{label}' must be a sequence of strings"
        raise ConfigError(msg)

    normalized: list[str] = []
    for idx, item in enumerate(value):
        normalized.append(require_normalized_str(label=f"{label}[{idx}]", value=item))
    return tuple(normalized)


def require_env(*, value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        msg = "MCP stdio constructor input 'env' must be a mapping of strings"
        raise ConfigError(msg)

    normalized: dict[str, str] = {}
    for key, env_value in value.items():
        env_key = require_normalized_str(label="env key", value=key)
        if not isinstance(env_value, str):
            msg = f"MCP stdio constructor env[{env_key}] must be a string"
            raise ConfigError(msg)
        normalized[env_key] = env_value
    return normalized


def require_timeout_seconds(*, value: object) -> float:
    if not isinstance(value, (float, int)):
        msg = "MCP stdio constructor input 'timeout_seconds' must be a number"
        raise ConfigError(msg)
    timeout = float(value)
    if timeout <= 0:
        msg = "MCP stdio constructor input 'timeout_seconds' must be > 0"
        raise ConfigError(msg)
    return timeout


@dataclass(frozen=True, slots=True)
class McpStdioConstructorConfig:
    """Typed constructor inputs for stdio-backed MCP acquisition."""

    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    tool_name: str
    timeout_seconds: float
    max_attempts: int = 1

    def __post_init__(self) -> None:
        require_normalized_str(label="command", value=self.command)
        require_args(label="args", value=self.args)
        require_env(value=self.env)
        require_normalized_str(label="tool_name", value=self.tool_name)
        require_timeout_seconds(value=self.timeout_seconds)
        if not isinstance(self.max_attempts, int):
            msg = "MCP stdio constructor input 'max_attempts' must be an int"
            raise ConfigError(msg)
        if self.max_attempts < 1:
            msg = "MCP stdio constructor input 'max_attempts' must be >= 1"
            raise ConfigError(msg)


def resolve_mcp_stdio_constructor_config(
    *,
    command: str | None = None,
    args: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    tool_name: str | None = None,
    timeout_seconds: float | None = None,
    max_attempts: int | None = None,
    config: McpStdioConstructorConfig | None = None,
) -> McpStdioConstructorConfig:
    """Resolve MCP stdio constructor inputs using approved precedence.

    Precedence order (highest first):
    1) explicit constructor arguments
    2) typed runtime config
    3) fail-fast ConfigError
    """

    if config is not None and not isinstance(config, McpStdioConstructorConfig):
        msg = (
            "MCP stdio constructor 'config' must be McpStdioConstructorConfig when "
            "provided"
        )
        raise ConfigError(msg)

    resolved_command = (
        command if command is not None else (config.command if config else None)
    )
    resolved_args = args if args is not None else (config.args if config else None)
    resolved_env = env if env is not None else (config.env if config else None)
    resolved_tool_name = (
        tool_name if tool_name is not None else (config.tool_name if config else None)
    )
    resolved_timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else (config.timeout_seconds if config else None)
    )
    resolved_attempts = (
        max_attempts
        if max_attempts is not None
        else (config.max_attempts if config else None)
    )

    if resolved_command is None:
        raise ConfigError("Missing required MCP stdio constructor input: command")
    if resolved_args is None:
        raise ConfigError("Missing required MCP stdio constructor input: args")
    if resolved_env is None:
        raise ConfigError("Missing required MCP stdio constructor input: env")
    if resolved_tool_name is None:
        raise ConfigError("Missing required MCP stdio constructor input: tool_name")
    if resolved_timeout is None:
        raise ConfigError(
            "Missing required MCP stdio constructor input: timeout_seconds"
        )

    return McpStdioConstructorConfig(
        command=require_normalized_str(label="command", value=resolved_command),
        args=require_args(label="args", value=resolved_args),
        env=require_env(value=resolved_env),
        tool_name=require_normalized_str(label="tool_name", value=resolved_tool_name),
        timeout_seconds=require_timeout_seconds(value=resolved_timeout),
        max_attempts=1 if resolved_attempts is None else int(resolved_attempts),
    )
