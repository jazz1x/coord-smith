"""Modeled-only helper entrypoint for running released-scope missions via MCP stdio.

This module intentionally does not redefine the released-path contract: it is a
convenience wrapper for harnesses that want to acquire an MCP-backed OpenClaw
adapter (per the approved stdio acquisition contract) outside released-scope
graph wiring, then invoke the released-scope sequence and stop at
`pageReadyObserved`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ez_ax.adapters.openclaw.mcp_stdio_client import open_mcp_stdio_openclaw_adapter
from ez_ax.config.mcp_stdio import McpStdioConstructorConfig
from ez_ax.config.mcp_stdio_cli import (
    resolve_mcp_stdio_constructor_config_from_argv,
    resolve_mcp_stdio_server_name_from_argv,
)
from ez_ax.config.released_inputs import (
    ReleasedScopeInputs,
    resolve_released_scope_inputs,
)
from ez_ax.graph.released_entrypoint import (
    ReleasedEntrypointResult,
    run_released_scope,
)


async def run_released_scope_via_mcp_stdio(
    *,
    mcp_stdio: McpStdioConstructorConfig,
    mcp_server_name: str,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
    base_dir: Path = Path("."),
) -> ReleasedEntrypointResult:
    """Acquire an MCP stdio-backed adapter and run released scope up to the ceiling."""

    async with open_mcp_stdio_openclaw_adapter(
        config=mcp_stdio,
        mcp_server_name=mcp_server_name,
    ) as adapter:
        return await run_released_scope(
            adapter=adapter,
            session_ref=session_ref,
            expected_auth_state=expected_auth_state,
            target_page_url=target_page_url,
            site_identity=site_identity,
            base_dir=base_dir,
        )


async def run_released_scope_via_mcp_stdio_argv(
    *,
    argv: Sequence[str] | None = None,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
    base_dir: Path = Path("."),
) -> ReleasedEntrypointResult:
    """Acquire MCP stdio config from argv and run released scope up to the ceiling."""

    mcp_stdio = resolve_mcp_stdio_constructor_config_from_argv(argv=argv)
    mcp_server_name = resolve_mcp_stdio_server_name_from_argv(argv=argv)
    return await run_released_scope_via_mcp_stdio(
        mcp_stdio=mcp_stdio,
        mcp_server_name=mcp_server_name,
        session_ref=session_ref,
        expected_auth_state=expected_auth_state,
        target_page_url=target_page_url,
        site_identity=site_identity,
        base_dir=base_dir,
    )


async def run_released_scope_via_mcp_stdio_argv_env(
    *,
    argv: Sequence[str] | None = None,
    env: dict[str, str] | None = None,
    base_dir: Path = Path("."),
) -> ReleasedEntrypointResult:
    """Resolve released inputs from argv/env and MCP stdio config from argv.

    Then run released scope up to the ceiling.
    """

    released: ReleasedScopeInputs = resolve_released_scope_inputs(argv=argv, env=env)
    return await run_released_scope_via_mcp_stdio_argv(
        argv=argv,
        session_ref=released.session_ref,
        expected_auth_state=released.expected_auth_state,
        target_page_url=released.target_page_url,
        site_identity=released.site_identity,
        base_dir=base_dir,
    )
