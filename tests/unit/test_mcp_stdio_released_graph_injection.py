from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.mcp_stdio_client import open_mcp_stdio_execution_adapter
from ez_ax.graph.released_entrypoint import run_released_scope
from tests.fixtures.fake_mcp_sdk import install_fake_mcp_sdk


@pytest.mark.asyncio
async def test_stdio_mcp_execution_adapter_runs_released_scope_and_stops_at_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch)

    async with open_mcp_stdio_execution_adapter(
        command="uv",
        args=["run", "openclaw", "stdio"],
        env={},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.0,
    ) as adapter:
        result = await run_released_scope(
            adapter=adapter,
            session_ref="session-1",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )

    assert (
        "evidence://action-log/release-ceiling-stop"
        in result.state.mission_state.evidence_refs
    )
    run_root = result.run.run_root
    assert (
        run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    ).exists()
