from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.graph.modeled_mcp_entrypoint import run_released_scope_via_mcp_stdio_argv_env
from tests.fixtures.fake_mcp_sdk import install_fake_mcp_sdk


@pytest.mark.asyncio
async def test_modeled_mcp_entrypoint_argv_env_composes_released_inputs_and_mcp_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch)

    result = await run_released_scope_via_mcp_stdio_argv_env(
        argv=[
            "--session-ref",
            "session-1",
            "--expected-auth-state",
            "authenticated",
            "--target-page-url",
            "https://tickets.interpark.com/goods/26003199",
            "--site-identity",
            "interpark",
            "--mcp-command",
            "uv",
            "--mcp-arg",
            "run",
            "--mcp-arg",
            "openclaw",
            "--mcp-arg",
            "stdio",
            "--mcp-server-name",
            "stdio",
            "--mcp-tool-name",
            "openclaw.execute",
            "--mcp-timeout-seconds",
            "1.0",
        ],
        env={},
        base_dir=tmp_path,
    )

    assert (
        "evidence://action-log/run-completed"
        in result.state.mission_state.evidence_refs
    )
    assert (
        result.run.run_root / "artifacts" / "action-log" / "run-completed.jsonl"
    ).exists()
