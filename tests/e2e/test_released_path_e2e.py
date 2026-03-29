"""Synthetic released-path E2E verification for the current approved ceiling.

This suite exercises the released path through the stdio-backed OpenClaw
adapter boundary while keeping execution deterministic with the fake MCP SDK.
It is the first runnable E2E scaffold under the current released ceiling:
`pageReadyObserved`.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from ez_ax.adapters.execution.mcp_stdio_client import open_mcp_stdio_execution_adapter
from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.graph.released_entrypoint import ReleasedEntrypointResult, run_released_scope
from tests.fixtures.fake_mcp_sdk import install_fake_mcp_sdk


def _load_jsonl_record(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, f"Expected at least one JSON line in {path}"
    return json.loads(lines[-1])


async def _run_released_path_e2e(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ReleasedEntrypointResult:
    install_fake_mcp_sdk(monkeypatch)

    async with open_mcp_stdio_execution_adapter(
        command="uv",
        args=["run", "openclaw", "stdio"],
        env={},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.0,
    ) as adapter:
        return await run_released_scope(
            adapter=adapter,
            session_ref="session-1",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_released_path_e2e_emits_release_ceiling_stop_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _run_released_path_e2e(tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert result.run.approved_scope_ceiling == "pageReadyObserved"
    assert result.state.current_mission == "page_ready_observation"
    assert "evidence://action-log/release-ceiling-stop" in (
        result.state.mission_state.evidence_refs or ()
    )

    action_log_dir = result.run.run_root / "artifacts" / "action-log"
    release_stop_path = action_log_dir / "release-ceiling-stop.jsonl"
    assert release_stop_path.exists()

    release_stop = _load_jsonl_record(release_stop_path)
    assert release_stop["event"] == "release-ceiling-stop"
    assert release_stop["mission_name"] == "page_ready_observation"
    assert isinstance(release_stop["ts"], str)


@pytest.mark.asyncio
async def test_released_path_e2e_repeated_runs_keep_comparable_action_log_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = await _run_released_path_e2e(
        tmp_path=tmp_path / "first-run",
        monkeypatch=monkeypatch,
    )
    second = await _run_released_path_e2e(
        tmp_path=tmp_path / "second-run",
        monkeypatch=monkeypatch,
    )

    def artifact_names(result: ReleasedEntrypointResult) -> set[str]:
        action_log_dir = result.run.run_root / "artifacts" / "action-log"
        return {path.name for path in action_log_dir.glob("*.jsonl")}

    assert artifact_names(first) == artifact_names(second) == {
        "attach-session.jsonl",
        "prepare-session.jsonl",
        "enter-target-page.jsonl",
        "release-ceiling-stop.jsonl",
    }

    first_stop = _load_jsonl_record(
        first.run.run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    )
    second_stop = _load_jsonl_record(
        second.run.run_root
        / "artifacts"
        / "action-log"
        / "release-ceiling-stop.jsonl"
    )
    assert first_stop["event"] == second_stop["event"] == "release-ceiling-stop"
    assert (
        first_stop["mission_name"]
        == second_stop["mission_name"]
        == "page_ready_observation"
    )


async def _run_real_environment_e2e(
    *, tmp_path: Path
) -> ReleasedEntrypointResult:
    """Run released-path E2E using the real PyAutoGUI adapter with mocked display.

    This exercises the real adapter code path (not fake SDK) while keeping the test
    deterministic by mocking pyautogui.screenshot() and pyautogui.click().
    """

    def fake_screenshot() -> Image.Image:
        """Return a minimal fake screenshot for testing."""
        img = Image.new("RGB", (800, 600), color="white")
        return img

    adapter = PyAutoGUIAdapter(run_root=tmp_path)

    with patch("pyautogui.screenshot", side_effect=fake_screenshot), patch(
        "pyautogui.click", new_callable=AsyncMock
    ):
        return await run_released_scope(
            adapter=adapter,
            session_ref="session-real-1",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_real_environment_released_path_e2e_stops_at_ceiling(
    tmp_path: Path,
) -> None:
    """Verify real-environment E2E stops at pageReadyObserved."""
    result = await _run_real_environment_e2e(tmp_path=tmp_path)

    assert result.run.approved_scope_ceiling == "pageReadyObserved"
    assert result.state.current_mission == "page_ready_observation"
    assert "evidence://action-log/release-ceiling-stop" in (
        result.state.mission_state.evidence_refs or ()
    )

    action_log_dir = result.run.run_root / "artifacts" / "action-log"
    release_stop_path = action_log_dir / "release-ceiling-stop.jsonl"
    assert release_stop_path.exists()

    release_stop = _load_jsonl_record(release_stop_path)
    assert release_stop["event"] == "release-ceiling-stop"
    assert release_stop["mission_name"] == "page_ready_observation"
    assert isinstance(release_stop["ts"], str)


@pytest.mark.asyncio
async def test_real_environment_generates_comparable_artifacts(
    tmp_path: Path,
) -> None:
    """Verify real-environment E2E generates comparable artifacts to synthetic tests."""
    first = await _run_real_environment_e2e(tmp_path=tmp_path / "first")
    second = await _run_real_environment_e2e(tmp_path=tmp_path / "second")

    def action_log_files(result: ReleasedEntrypointResult) -> set[str]:
        action_log_dir = result.run.run_root / "artifacts" / "action-log"
        return {path.name for path in action_log_dir.glob("*.jsonl")}

    first_files = action_log_files(first)
    second_files = action_log_files(second)

    # Both runs should produce consistent action-log artifacts
    assert "release-ceiling-stop.jsonl" in first_files
    assert "release-ceiling-stop.jsonl" in second_files

    # Verify the structured content is comparable
    first_stop = _load_jsonl_record(
        first.run.run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    )
    second_stop = _load_jsonl_record(
        second.run.run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    )

    assert first_stop["event"] == second_stop["event"]
    assert first_stop["mission_name"] == second_stop["mission_name"]
