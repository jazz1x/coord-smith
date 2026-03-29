from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.graph.modeled_mcp_entrypoint import run_released_scope_via_mcp_stdio_argv
from tests.fixtures.fake_mcp_sdk import install_fake_mcp_sdk


@pytest.mark.asyncio
async def test_modeled_mcp_entrypoint_argv_runs_released_scope_to_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch)

    result = await run_released_scope_via_mcp_stdio_argv(
        argv=[
            "--mcp-command",
            "uv",
            "--mcp-arg",
            "run",
            "--mcp-arg",
            "openclaw",
            "--mcp-arg",
            "stdio",
            "--mcp-server-name",
            "openclaw",
            "--mcp-tool-name",
            "openclaw.execute",
            "--mcp-timeout-seconds",
            "1.0",
        ],
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
    assert (
        result.run.run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    ).exists()
