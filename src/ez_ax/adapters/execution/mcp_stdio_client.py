"""Real stdio-backed MCP client acquisition (modeled-only scaffolding).

This module introduces a concrete MCP stdio constructor boundary per
`docs/product/prd-python-mcp-client-acquisition.md`.

Released-scope wiring must still inject an adapter; this code exists so a
graph entrypoint can own MCP client/session lifecycle and inject a concrete
MCP-backed OpenClaw adapter without transport guesswork.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from ez_ax.adapters.execution.mcp_adapter import (
    McpBackedExecutionAdapter,
    McpClient,
)
from ez_ax.adapters.execution.mcp_settings import (
    McpExecutionAdapterSettings,
    RetryPolicy,
)
from ez_ax.config.mcp_stdio import (
    McpStdioConstructorConfig,
    require_normalized_str,
    require_timeout_seconds,
    resolve_mcp_stdio_constructor_config,
)
from ez_ax.models.errors import ConfigError, ExecutionTransportError


def _import_mcp_stdio_symbols() -> tuple[Any, Any, Any]:
    """Import MCP stdio symbols and map import failures to ExecutionTransportError."""

    try:
        mcp_mod = importlib.import_module("mcp")
    except ImportError as exc:  # pragma: no cover
        msg = "MCP python package import failed (import_path='mcp')"
        raise ExecutionTransportError(msg) from exc

    try:
        stdio_mod = importlib.import_module("mcp.client.stdio")
    except ImportError as exc:  # pragma: no cover
        msg = "MCP stdio transport import failed (import_path='mcp.client.stdio')"
        raise ExecutionTransportError(msg) from exc

    session_mod: Any | None = None
    try:
        session_mod = importlib.import_module("mcp.client.session")
    except ImportError:
        session_mod = None

    client_session = getattr(mcp_mod, "ClientSession", None)
    if client_session is None and session_mod is not None:
        client_session = getattr(session_mod, "ClientSession", None)

    server_params = getattr(mcp_mod, "StdioServerParameters", None)
    if server_params is None:
        server_params = getattr(stdio_mod, "StdioServerParameters", None)

    stdio_client = getattr(stdio_mod, "stdio_client", None)

    missing: list[str] = []
    if client_session is None:
        missing.append("ClientSession")
    if server_params is None:
        missing.append("StdioServerParameters")
    if stdio_client is None:
        missing.append("stdio_client")
    if missing:
        msg = "MCP stdio client acquisition missing required SDK symbols: " + ", ".join(
            missing
        )
        raise ExecutionTransportError(msg)

    return client_session, server_params, stdio_client


@dataclass(frozen=True, slots=True)
class _McpStdioSessionClient(McpClient):
    """McpClient adapter over an MCP ClientSession."""

    session: Any
    expected_server_name: str

    async def call_tool(
        self,
        *,
        server_name: str,
        tool_name: str,
        tool_input: dict[str, object],
        timeout_seconds: float,
    ) -> object:
        server_name = require_normalized_str(label="server_name", value=server_name)
        if server_name != self.expected_server_name:
            msg = (
                "MCP stdio client received unexpected server_name: "
                f"expected='{self.expected_server_name}', got='{server_name}'"
            )
            raise ConfigError(msg)
        require_normalized_str(label="tool_name", value=tool_name)
        timeout = require_timeout_seconds(value=timeout_seconds)

        try:
            coro = self.session.call_tool(tool_name, arguments=tool_input)
        except TypeError:
            coro = self.session.call_tool(tool_name, tool_input)

        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
        except TimeoutError as exc:
            msg = (
                f"MCP tool call timed out after {timeout} seconds: "
                f"tool_name='{tool_name}'"
            )
            raise ExecutionTransportError(msg) from exc
        except Exception as exc:  # noqa: BLE001
            msg = f"MCP tool call failed: tool_name='{tool_name}', error='{exc}'"
            raise ExecutionTransportError(msg) from exc

        structured = getattr(result, "structured_content", None)
        if hasattr(result, "structured_content") and structured is None:
            msg = (
                "MCP tool result structured_content was None; expected structured tool "
                "output"
            )
            raise ExecutionTransportError(msg)
        return result if structured is None else structured


@asynccontextmanager
async def open_mcp_stdio_execution_adapter(
    *,
    command: str | None = None,
    args: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    tool_name: str | None = None,
    timeout_seconds: float | None = None,
    max_attempts: int | None = None,
    config: McpStdioConstructorConfig | None = None,
    mcp_server_name: str | None = None,
    session_label: str | None = None,
) -> AsyncIterator[McpBackedExecutionAdapter]:
    """Acquire an stdio-backed MCP session and yield an MCP-backed OpenClaw adapter."""

    resolved = resolve_mcp_stdio_constructor_config(
        command=command,
        args=args,
        env=env,
        tool_name=tool_name,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        config=config,
    )

    if mcp_server_name is None:
        raise ConfigError("Missing required OpenClaw MCP setting: mcp_server_name")

    client_session, server_params, stdio_client = _import_mcp_stdio_symbols()
    try:
        params = server_params(
            command=resolved.command,
            args=list(resolved.args),
            env=dict(resolved.env),
        )
    except TypeError:
        try:
            params = server_params(
                resolved.command,
                list(resolved.args),
                dict(resolved.env),
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"MCP stdio server parameter construction failed: {exc}"
            raise ExecutionTransportError(msg) from exc
    except Exception as exc:  # noqa: BLE001
        msg = f"MCP stdio server parameter construction failed: {exc}"
        raise ExecutionTransportError(msg) from exc

    retry_policy = RetryPolicy(max_attempts=resolved.max_attempts)
    normalized_server_name = require_normalized_str(
        label="mcp_server_name", value=mcp_server_name
    )
    settings = McpExecutionAdapterSettings(
        mcp_server_name=normalized_server_name,
        tool_name=resolved.tool_name,
        default_timeout_seconds=resolved.timeout_seconds,
        retry_policy=retry_policy,
        session_label=session_label,
    )

    try:
        async with stdio_client(params) as (read, write):
            async with client_session(read, write) as session:
                await session.initialize()
                mcp_client: McpClient = _McpStdioSessionClient(
                    session=session,
                    expected_server_name=normalized_server_name,
                )
                yield McpBackedExecutionAdapter(
                    settings=settings, mcp_client=mcp_client
                )
    except ExecutionTransportError:
        raise
    except Exception as exc:  # noqa: BLE001
        msg = f"MCP stdio client acquisition failed: {exc}"
        raise ExecutionTransportError(msg) from exc
