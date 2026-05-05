"""Real-environment released-path E2E verification.

Exercises the released path through the real PyAutoGUI adapter while keeping
the test deterministic by mocking pyautogui.screenshot() and pyautogui.click().
The current released ceiling is `runCompletion`.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import ClickRecipe, MissionClick
from coord_smith.evidence.envelope import enforce_evidence_priority_gate
from coord_smith.graph.released_entrypoint import (
    ReleasedEntrypointResult,
    run_released_scope,
)


def _load_jsonl_record(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, f"Expected at least one JSON line in {path}"
    return json.loads(lines[-1])


async def _run_real_environment_e2e(
    *, tmp_path: Path
) -> ReleasedEntrypointResult:
    """Run released-path E2E using the real PyAutoGUI adapter with mocked display.

    This exercises the real adapter code path while keeping the test
    deterministic by mocking pyautogui.screenshot() and pyautogui.click().
    """

    def fake_screenshot() -> Image.Image:
        """Return a minimal fake screenshot for testing."""
        img = Image.new("RGB", (800, 600), color="white")
        return img

    adapter = PyAutoGUIAdapter(run_root=tmp_path)

    with patch("pyautogui.screenshot", side_effect=fake_screenshot), patch(
        "pyautogui.click"
    ):
        result = await run_released_scope(
            adapter=adapter,
            session_ref="session-real-1",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    return result


@pytest.mark.asyncio
async def test_real_environment_released_path_e2e_stops_at_ceiling(
    tmp_path: Path,
) -> None:
    """Verify real-environment E2E stops at runCompletion."""
    result = await _run_real_environment_e2e(tmp_path=tmp_path)

    assert result.run.approved_scope_ceiling == "runCompletion"
    assert result.state.current_mission == "run_completion"
    assert "evidence://action-log/release-ceiling-stop" in (
        result.state.mission_state.evidence_refs or ()
    )

    action_log_dir = result.run.run_root / "artifacts" / "action-log"
    release_stop_path = action_log_dir / "release-ceiling-stop.jsonl"
    assert release_stop_path.exists()

    release_stop = _load_jsonl_record(release_stop_path)
    assert release_stop["event"] == "release-ceiling-stop"
    assert release_stop["mission_name"] == "run_completion"
    assert isinstance(release_stop["ts"], str)


@pytest.mark.asyncio
async def test_real_environment_generates_comparable_artifacts(
    tmp_path: Path,
) -> None:
    """Verify real-environment E2E generates comparable artifacts across runs."""
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


@pytest.mark.asyncio
async def test_click_recipe_coord_dispatches_to_pyautogui(tmp_path: Path) -> None:
    """Verify that click recipe coordinates are forwarded to pyautogui.click."""
    recipe = ClickRecipe(missions={"click_dispatch": MissionClick(x=400, y=300)})
    adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)

    click_calls: list[tuple[object, ...]] = []

    def fake_screenshot() -> Image.Image:
        return Image.new("RGB", (800, 600), color="white")

    def capture_click(x: object, y: object) -> None:
        click_calls.append((x, y))

    FakeSize = type("Point", (), {"width": 1920, "height": 1080})
    FakePos = type("Point", (), {"x": 400, "y": 300})

    with (
        patch("pyautogui.screenshot", side_effect=fake_screenshot),
        patch("pyautogui.click", side_effect=capture_click),
        patch("pyautogui.position", return_value=FakePos()),
        patch("pyautogui.size", return_value=FakeSize()),
    ):
        await run_released_scope(
            adapter=adapter,
            session_ref="session-recipe-1",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )

    assert (400, 300) in click_calls, (
        f"Expected pyautogui.click(400, 300) for click_dispatch recipe; got: {click_calls}"
    )


@pytest.mark.asyncio
async def test_evidence_priority_gate_passes_on_real_run(tmp_path: Path) -> None:
    """Verify enforce_evidence_priority_gate passes (>= action-log) on a real run."""
    result = await _run_real_environment_e2e(tmp_path=tmp_path)

    from coord_smith.adapters.execution.client import ExecutionResult

    final_result = ExecutionResult(
        mission_name=result.state.current_mission or "run_completion",
        evidence_refs=result.state.mission_state.evidence_refs or (),
    )
    top_kind = enforce_evidence_priority_gate(final_result)
    assert top_kind not in ("screenshot", "coordinate"), (
        f"Evidence gate should pass at action-log or higher; got: {top_kind}"
    )
