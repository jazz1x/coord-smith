"""Modeled-only CLI parsing for MCP stdio constructor inputs.

.. note::
   **Inactive scaffold.** Companion to ``ez_ax.config.mcp_stdio`` — see that
   module's docstring. The released path does not invoke this CLI. Preserved
   for shape only.

This module does not widen released-scope argv/env contracts. It provides an
explicit argv-only helper so harnesses can build `McpStdioConstructorConfig`
deterministically without inventing environment variables.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from ez_ax.config.mcp_stdio import (
    McpStdioConstructorConfig,
    require_normalized_str,
    resolve_mcp_stdio_constructor_config,
)
from ez_ax.models.errors import ConfigError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mcp-command", dest="command")
    parser.add_argument("--mcp-arg", dest="args", action="append")
    parser.add_argument("--mcp-env", dest="env", action="append")
    parser.add_argument("--mcp-server-name", dest="server_name")
    parser.add_argument("--mcp-tool-name", dest="tool_name")
    parser.add_argument("--mcp-timeout-seconds", dest="timeout_seconds", type=float)
    parser.add_argument("--mcp-max-attempts", dest="max_attempts", type=int)
    return parser


def _parse_env_kv_entries(entries: list[str] | None) -> dict[str, str]:
    if not entries:
        return {}

    env: dict[str, str] = {}
    for raw in entries:
        if not isinstance(raw, str):
            msg = "MCP stdio CLI --mcp-env entries must be strings"
            raise ConfigError(msg)
        if "=" not in raw:
            msg = "MCP stdio CLI --mcp-env entries must be KEY=VALUE"
            raise ConfigError(msg)
        key, value = raw.split("=", 1)
        if not key:
            msg = "MCP stdio CLI --mcp-env key must be non-empty"
            raise ConfigError(msg)
        if key != key.strip():
            msg = "MCP stdio CLI --mcp-env key must be whitespace-normalized"
            raise ConfigError(msg)
        env[key] = value
    return env


def resolve_mcp_stdio_constructor_config_from_argv(
    *, argv: Sequence[str] | None = None
) -> McpStdioConstructorConfig:
    """Resolve MCP stdio constructor inputs from argv only (modeled-only helper)."""

    parsed, _ = _parser().parse_known_args([] if argv is None else list(argv))
    env = _parse_env_kv_entries(parsed.env)

    try:
        return resolve_mcp_stdio_constructor_config(
            command=parsed.command,
            args=parsed.args,
            env=env,
            tool_name=parsed.tool_name,
            timeout_seconds=parsed.timeout_seconds,
            max_attempts=parsed.max_attempts,
        )
    except ConfigError:
        raise
    except (TypeError, ValueError) as exc:
        msg = f"MCP stdio CLI failed to resolve constructor inputs: {exc}"
        raise ConfigError(msg) from exc


def resolve_mcp_stdio_server_name_from_argv(
    *, argv: Sequence[str] | None = None
) -> str:
    """Resolve required MCP server name from argv (modeled-only helper)."""

    parsed, _ = _parser().parse_known_args([] if argv is None else list(argv))
    if parsed.server_name is None:
        raise ConfigError("Missing required MCP stdio setting: mcp_server_name")
    return require_normalized_str(label="mcp_server_name", value=parsed.server_name)
