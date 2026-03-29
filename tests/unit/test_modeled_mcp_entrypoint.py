from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.config.mcp_stdio import McpStdioConstructorConfig
from ez_ax.graph.modeled_mcp_entrypoint import run_released_scope_via_mcp_stdio
from tests.fixtures.fake_mcp_sdk import install_fake_mcp_sdk


@pytest.mark.asyncio
async def test_modeled_mcp_entrypoint_runs_released_scope_and_stops_at_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch)
    config = McpStdioConstructorConfig(
        command="uv",
        args=("run", "openclaw", "stdio"),
        env={},
        tool_name="openclaw.execute",
        timeout_seconds=1.0,
    )

    result = await run_released_scope_via_mcp_stdio(
        mcp_stdio=config,
        mcp_server_name="stdio",
        session_ref="session-1",
        expected_auth_state="authenticated",
        target_page_url="https://tickets.interpark.com/goods/26003199",
        site_identity="interpark",
        base_dir=tmp_path,
    )

    assert (
        "evidence://action-log/run-completed"
        in result.state.mission_state.evidence_refs
    )
    assert (
        result.run.run_root / "artifacts" / "action-log" / "run-completed.jsonl"
    ).exists()
