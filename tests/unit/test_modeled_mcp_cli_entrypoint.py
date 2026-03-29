from __future__ import annotations

import json
from pathlib import Path

import pytest

from ez_ax.graph.modeled_mcp_cli_entrypoint import run_modeled_mcp_cli_entrypoint
from tests.fixtures.fake_mcp_sdk import install_fake_mcp_sdk


@pytest.mark.asyncio
async def test_modeled_mcp_cli_entrypoint_writes_summary_under_run_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch)

    summary = await run_modeled_mcp_cli_entrypoint(
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

    assert summary.run_root
    run_root = Path(summary.run_root)
    path = Path(summary.summary_path)
    assert path.exists()
    assert str(path).startswith(str(run_root))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["kind"] == "modeled-mcp-cli-run-summary"
    assert payload["run_id"] == summary.run_id
    assert payload["run_root"] == str(run_root)
    assert payload["approved_scope_ceiling"] == "runCompletion"
    assert payload["stopped_at_release_ceiling"] is True
