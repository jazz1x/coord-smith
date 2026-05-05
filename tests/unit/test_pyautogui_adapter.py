"""Tests for PyAutoGUIAdapter protocol implementation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import UnidentifiedImageError

from coord_smith.adapters.execution.client import ExecutionRequest
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.models.errors import (
    AccessibilityPermissionDenied,
    ClickCoordinatesOutOfBounds,
    ClickExecutionUnverified,
    ScreenCapturePermissionDenied,
)


def test_pyautogui_adapter_has_execute_method() -> None:
    assert callable(getattr(PyAutoGUIAdapter, "execute", None))


async def test_execute_prepare_session_returns_fallback_evidence_refs(
    tmp_path: Path,
) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
            },
        )
        result = await adapter.execute(request)

    assert result.mission_name == "prepare_session"
    assert "evidence://action-log/prepare-session" in result.evidence_refs
    assert "evidence://screenshot/prepare-session-fallback" in result.evidence_refs


async def test_execute_clicks_when_coordinates_given(tmp_path: Path) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=mock_screenshot),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch(
            "pyautogui.position",
            return_value=MagicMock(x=100, y=200),
        ),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
                "x": 100,
                "y": 200,
            },
        )
        await adapter.execute(request)

    mock_click.assert_called_once_with(100, 200)


async def test_execute_skips_click_without_coordinates(tmp_path: Path) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
            },
        )
        await adapter.execute(request)

    mock_click.assert_not_called()


async def test_execute_writes_action_log_artifact(tmp_path: Path) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
            },
        )
        await adapter.execute(request)

    log_path = tmp_path / "artifacts" / "action-log" / "prepare-session.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["mission_name"] == "prepare_session"
    assert entry["event"] == "prepare-session"
    assert "ts" in entry


async def test_execute_page_ready_observation_writes_page_ready_observed(
    tmp_path: Path,
) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="page_ready_observation",
            payload={},
        )
        result = await adapter.execute(request)

    assert "evidence://action-log/page-ready-observed" in result.evidence_refs
    log_path = tmp_path / "artifacts" / "action-log" / "page-ready-observed.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["event"] == "page-ready-observed"
    assert entry["mission_name"] == "page_ready_observation"


async def test_pyautogui_adapter_uses_only_click_and_screenshot(tmp_path: Path) -> None:
    """Verify PyAutoGUIAdapter uses only pyautogui.click and screenshot operations.

    PRD requirement (System Boundary, line 35-36):
    'PyAutoGUIAdapter is the sole execution backend: coordinate-click and screenshot
     only, no LLM calls.'

    This test ensures no other pyautogui methods (moveTo, write, press, hotkey, etc.)
    are called during execution, constraining the adapter to coordinate-click and
    screenshot-only operations.
    """
    mock_screenshot = MagicMock()

    # Track which pyautogui methods are called
    called_methods: set[str] = set()

    def track_call(name: str) -> MagicMock:
        def wrapper(*args: object, **kwargs: object) -> object:
            called_methods.add(name)
            if name == "screenshot":
                return mock_screenshot
            return None

        return MagicMock(side_effect=wrapper)

    # Patch all common pyautogui methods to track if they're called.
    # size() and position() are read-only queries used by the adapter's
    # bounds check and post-click verification; they are not execution
    # primitives, so we mock their return values without tracking.
    with (
        patch.multiple(
            "pyautogui",
            click=track_call("click"),
            screenshot=track_call("screenshot"),
            moveTo=track_call("moveTo"),
            write=track_call("write"),
            press=track_call("press"),
            hotkey=track_call("hotkey"),
            scroll=track_call("scroll"),
            locateOnScreen=track_call("locateOnScreen"),
        ),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=200)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)

        # Test with coordinates to trigger click
        request_with_coords = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
                "x": 100,
                "y": 200,
            },
        )
        await adapter.execute(request_with_coords)

        # Test without coordinates
        request_without_coords = ExecutionRequest(
            mission_name="page_ready_observation",
            payload={},
        )
        await adapter.execute(request_without_coords)

    # Verify only click and screenshot were called
    assert "screenshot" in called_methods, "screenshot() should be called"
    assert "click" in called_methods, "click() should be called"

    # Verify no other pyautogui methods were called
    forbidden_methods = {
        "moveTo",
        "write",
        "press",
        "hotkey",
        "scroll",
        "locateOnScreen",
    }
    unwanted_calls = called_methods & forbidden_methods
    assert (
        not unwanted_calls
    ), f"PyAutoGUIAdapter must not call these pyautogui methods: {unwanted_calls}"


async def test_execute_raises_when_click_coordinates_out_of_bounds(tmp_path: Path) -> None:
    with (
        patch("pyautogui.click"),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=9999, y=9999)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={"target_page_url": "u", "site_identity": "s", "x": 9999, "y": 9999},
        )
        with pytest.raises(ClickCoordinatesOutOfBounds):
            await adapter.execute(request)


async def test_execute_raises_when_click_position_mismatch(tmp_path: Path) -> None:
    """Silent-no-op click (Accessibility denied) must raise, not return bogus success."""
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        # Cursor did not move to (100, 200) — simulated silent failure.
        patch("pyautogui.position", return_value=MagicMock(x=500, y=500)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={"target_page_url": "u", "site_identity": "s", "x": 100, "y": 200},
        )
        with pytest.raises(ClickExecutionUnverified):
            await adapter.execute(request)


async def test_capture_screenshot_raises_permission_error_on_unidentified_image(
    tmp_path: Path,
) -> None:
    """PIL UnidentifiedImageError (macOS zero-byte screencapture) -> typed error."""
    with patch(
        "pyautogui.screenshot",
        side_effect=UnidentifiedImageError("screencapture denied"),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        with pytest.raises(ScreenCapturePermissionDenied):
            adapter._capture_screenshot("test-key")


@pytest.mark.asyncio
async def test_preflight_raises_when_cursor_does_not_move(tmp_path: Path) -> None:
    """moveTo silent no-op must surface as AccessibilityPermissionDenied.

    Simulates the macOS-Accessibility-denied path: pyautogui.moveTo does not
    move the cursor, so position() returns the original coordinates after
    the probe instead of the target +10 offset.
    """
    start = MagicMock(x=100, y=100)
    # Two position() calls: first returns start; second (after moveTo) also
    # returns start (did not move) — should trigger the permission error.
    with (
        patch("pyautogui.position", side_effect=[start, start]),
        patch("pyautogui.moveTo"),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        with pytest.raises(AccessibilityPermissionDenied):
            await adapter.preflight()


@pytest.mark.asyncio
async def test_preflight_raises_when_screenshot_denied(tmp_path: Path) -> None:
    """Screen Recording permission missing -> typed error at preflight."""
    start = MagicMock(x=100, y=100)
    probed = MagicMock(x=110, y=100)  # +10 probe reached — Accessibility OK
    with (
        patch("pyautogui.position", side_effect=[start, probed]),
        patch("pyautogui.moveTo"),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch(
            "pyautogui.screenshot",
            side_effect=UnidentifiedImageError("screencapture denied"),
        ),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        with pytest.raises(ScreenCapturePermissionDenied):
            await adapter.preflight()


async def test_execute_uses_click_recipe_when_payload_lacks_coords(tmp_path: Path) -> None:
    """Adapter resolves click coords from recipe when payload is empty."""
    from coord_smith.config.click_recipe import ClickRecipe

    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 777, "y": 333}}}
    )
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=777, y=333)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="click_dispatch", payload={})
        await adapter.execute(request)

    mock_click.assert_called_once_with(777, 333)


async def test_execute_payload_coords_override_recipe(tmp_path: Path) -> None:
    """Payload-provided coords take precedence over recipe coords."""
    from coord_smith.config.click_recipe import ClickRecipe

    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 777, "y": 333}}}
    )
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=200)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(
            mission_name="click_dispatch", payload={"x": 100, "y": 200}
        )
        await adapter.execute(request)

    mock_click.assert_called_once_with(100, 200)


async def test_execute_no_click_when_recipe_has_no_entry(tmp_path: Path) -> None:
    """Missions absent from recipe + empty payload -> no click (pre-recipe default)."""
    from coord_smith.config.click_recipe import ClickRecipe

    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 777, "y": 333}}}
    )
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=MagicMock()),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="page_ready_observation", payload={})
        await adapter.execute(request)

    mock_click.assert_not_called()


@pytest.mark.asyncio
async def test_preflight_probes_left_near_right_screen_edge(tmp_path: Path) -> None:
    """Near the right screen edge the probe flips to −10 so it stays in bounds."""
    from PIL import Image

    # x=1918 → start.x + 10 = 1928 >= 1920 → probe_delta = -10 → probe_x = 1908
    start = MagicMock(x=1918, y=500)
    probed = MagicMock(x=1908, y=500)
    valid_screenshot = Image.new("RGB", (1920, 1080), color="black")
    with (
        patch("pyautogui.position", side_effect=[start, probed]),
        patch("pyautogui.moveTo"),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.screenshot", return_value=valid_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        await adapter.preflight()  # must NOT raise AccessibilityPermissionDenied


@pytest.mark.asyncio
async def test_preflight_screenshot_unexpected_type_raises(tmp_path: Path) -> None:
    """preflight() raises ScreenCaptureUnavailable when screenshot returns non-PIL."""
    from coord_smith.models.errors import ScreenCaptureUnavailable

    start = MagicMock(x=100, y=100)
    probed = MagicMock(x=110, y=100)
    with (
        patch("pyautogui.position", side_effect=[start, probed]),
        patch("pyautogui.moveTo"),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.screenshot", return_value="not-a-pil-image"),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        with pytest.raises(ScreenCaptureUnavailable, match="unexpected type"):
            await adapter.preflight()


def test_pyautogui_adapter_sets_failsafe_on_init(tmp_path: Path) -> None:
    import pyautogui

    pyautogui.FAILSAFE = False
    PyAutoGUIAdapter(run_root=tmp_path)
    assert pyautogui.FAILSAFE is True


def test_with_run_root_returns_new_adapter_bound_to_different_root(
    tmp_path: Path,
) -> None:
    from coord_smith.config.click_recipe import ClickRecipe

    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 1, "y": 2}}}
    )
    original_root = tmp_path / "original"
    original_root.mkdir()
    new_root = tmp_path / "new"
    new_root.mkdir()

    original = PyAutoGUIAdapter(run_root=original_root, click_recipe=recipe)
    rebound = original.with_run_root(run_root=new_root)

    assert rebound is not original
    assert rebound._run_root == new_root
    assert original._run_root == original_root
    assert rebound._click_recipe is recipe


async def test_resolve_click_coords_rejects_bool_payload_values(
    tmp_path: Path,
) -> None:
    """Booleans are int subclasses; the guard must reject them as click coords."""

    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=MagicMock()),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="click_dispatch",
            payload={"x": True, "y": False},
        )
        await adapter.execute(request)

    mock_click.assert_not_called()


def test_with_run_root_returns_new_adapter_with_new_root(tmp_path: Path) -> None:
    original = PyAutoGUIAdapter(run_root=tmp_path / "original")
    new_root = tmp_path / "new"
    cloned = original.with_run_root(run_root=new_root)

    assert cloned is not original
    assert cloned._run_root == new_root
    assert cloned._click_recipe is original._click_recipe


def test_with_run_root_preserves_click_recipe(tmp_path: Path) -> None:
    from coord_smith.config.click_recipe import ClickRecipe

    recipe = ClickRecipe.model_validate({"missions": {"click_dispatch": {"x": 10, "y": 20}}})
    original = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
    cloned = original.with_run_root(run_root=tmp_path / "other")

    assert cloned._click_recipe is recipe


def test_resolve_click_coords_rejects_bool_values(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    result = adapter._resolve_click_coords("click_dispatch", {"x": True, "y": False})
    assert result is None


def test_resolve_click_coords_accepts_int_and_float(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    assert adapter._resolve_click_coords("click_dispatch", {"x": 10, "y": 20}) == (10, 20)
    assert adapter._resolve_click_coords("click_dispatch", {"x": 1.5, "y": 2.7}) == (1, 2)


def _write_template(path: Path, *, color: str = "red") -> Path:
    from PIL import Image

    Image.new("RGB", (16, 16), color=color).save(path)
    return path


async def test_image_target_resolves_via_locate_center_on_screen(
    tmp_path: Path,
) -> None:
    """Image target dispatches to pyautogui.locateCenterOnScreen and clicks the result."""
    from coord_smith.config.click_recipe import ClickRecipe

    template = _write_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {"image": str(template), "confidence": 0.85},
            },
        }
    )
    located = MagicMock(x=512, y=384)
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=512, y=384)),
        patch(
            "pyautogui.locateCenterOnScreen", return_value=located
        ) as mock_locate,
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="click_dispatch", payload={})
        await adapter.execute(request)

    mock_click.assert_called_once_with(512, 384)
    locate_call = mock_locate.call_args
    assert locate_call.args[0] == str(template)
    assert locate_call.kwargs["confidence"] == 0.85


async def test_image_target_raises_when_template_file_missing(
    tmp_path: Path,
) -> None:
    """Recipe loaded with absolute path that later vanishes raises typed error."""
    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import ImageTemplateNotFound

    missing = tmp_path / "vanished.png"
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"image": str(missing)}}}
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="click_dispatch", payload={})
        with pytest.raises(ImageTemplateNotFound):
            await adapter.execute(request)


async def test_image_target_raises_when_match_fails(tmp_path: Path) -> None:
    """locateCenterOnScreen returning None raises ImageMatchConfidenceLow."""
    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import ImageMatchConfidenceLow

    template = _write_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"image": str(template)}}}
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.locateCenterOnScreen", return_value=None),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="click_dispatch", payload={})
        with pytest.raises(ImageMatchConfidenceLow):
            await adapter.execute(request)


async def test_image_target_raises_on_image_not_found_exception(
    tmp_path: Path,
) -> None:
    """pyautogui's ImageNotFoundException is converted to ImageMatchConfidenceLow."""
    import pyautogui

    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import ImageMatchConfidenceLow

    template = _write_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"image": str(template)}}}
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch(
            "pyautogui.locateCenterOnScreen",
            side_effect=pyautogui.ImageNotFoundException("not found"),
        ),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="click_dispatch", payload={})
        with pytest.raises(ImageMatchConfidenceLow):
            await adapter.execute(request)


async def test_image_match_writes_action_log_with_match_metadata(
    tmp_path: Path,
) -> None:
    """Image-resolved clicks record template, confidence, and matched coords."""
    from coord_smith.config.click_recipe import ClickRecipe

    template = _write_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {"image": str(template), "confidence": 0.95},
            },
        }
    )
    located = MagicMock(x=200, y=300)
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=200, y=300)),
        patch("pyautogui.locateCenterOnScreen", return_value=located),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(mission_name="click_dispatch", payload={})
        await adapter.execute(request)

    action_log = tmp_path / "artifacts" / "action-log" / "click-dispatched.jsonl"
    assert action_log.exists()
    lines = [
        json.loads(line)
        for line in action_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [line for line in lines if line.get("image_template")]
    assert len(matches) == 1
    record = matches[0]
    assert record["image_template"] == str(template)
    assert record["match_confidence"] == 0.95
    assert record["match_x"] == 200
    assert record["match_y"] == 300
    assert record["mission_name"] == "click_dispatch"


async def test_payload_coords_take_precedence_over_image_target(
    tmp_path: Path,
) -> None:
    """payload(x,y) wins over recipe(image) just like over recipe(coord)."""
    from coord_smith.config.click_recipe import ClickRecipe

    template = _write_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"image": str(template)}}}
    )
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=10, y=20)),
        patch("pyautogui.locateCenterOnScreen") as mock_locate,
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        request = ExecutionRequest(
            mission_name="click_dispatch", payload={"x": 10, "y": 20}
        )
        await adapter.execute(request)

    mock_click.assert_called_once_with(10, 20)
    mock_locate.assert_not_called()


async def test_verify_transition_passes_when_pixels_change(tmp_path: Path) -> None:
    """When verify_transition is True and pixels differ, the click succeeds."""
    from PIL import Image

    from coord_smith.config.click_recipe import ClickRecipe

    baseline = Image.new("RGB", (200, 200), color="white")
    post = Image.new("RGB", (200, 200), color="white")
    post.paste("black", (50, 50, 150, 150))

    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "x": 100,
                    "y": 100,
                    "verify_transition": True,
                    "transition_threshold": 0.01,
                },
            },
        }
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", side_effect=[baseline, post, post]),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=100)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        await adapter.execute(
            ExecutionRequest(mission_name="click_dispatch", payload={})
        )

    action_log = tmp_path / "artifacts" / "action-log" / "click-dispatched.jsonl"
    lines = [
        json.loads(line)
        for line in action_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    transitions = [line for line in lines if "transition_changed" in line]
    assert len(transitions) == 1
    assert transitions[0]["transition_changed"] is True
    assert transitions[0]["transition_change_ratio"] > 0.01


async def test_verify_transition_raises_when_pixels_unchanged(tmp_path: Path) -> None:
    """Identical pre/post screenshots raise PageTransitionNotDetected."""
    from PIL import Image

    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import PageTransitionNotDetected

    same = Image.new("RGB", (200, 200), color="white")

    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "x": 100,
                    "y": 100,
                    "verify_transition": True,
                    "transition_threshold": 0.01,
                },
            },
        }
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", side_effect=[same, same.copy(), same.copy()]),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=100)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        with pytest.raises(PageTransitionNotDetected):
            await adapter.execute(
                ExecutionRequest(mission_name="click_dispatch", payload={})
            )


async def test_verify_transition_skipped_when_disabled(tmp_path: Path) -> None:
    """verify_transition=False (default) bypasses the pre/post comparison."""
    from coord_smith.config.click_recipe import ClickRecipe

    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 100, "y": 100}}}
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()) as mock_screenshot,
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=100)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        await adapter.execute(
            ExecutionRequest(mission_name="click_dispatch", payload={})
        )

    # Only the evidence-gathering screenshot is captured (no baseline / no post).
    assert mock_screenshot.call_count == 1


@pytest.mark.asyncio
async def test_wait_for_image_returns_coords_on_first_match(tmp_path: Path) -> None:
    """wait_for_image returns immediately when locateCenterOnScreen succeeds."""
    located = MagicMock(x=42, y=84)
    with patch("pyautogui.locateCenterOnScreen", return_value=located):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        result = await adapter.wait_for_image(
            path="/fake/template.png", timeout=1.0, interval=0.01
        )
    assert result == (42, 84)


@pytest.mark.asyncio
async def test_wait_for_image_polls_until_match(tmp_path: Path) -> None:
    """wait_for_image keeps polling until a match appears."""
    located = MagicMock(x=10, y=20)
    side_effects: list[object] = [None, None, located]
    with patch(
        "pyautogui.locateCenterOnScreen", side_effect=side_effects
    ) as mock_locate:
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        result = await adapter.wait_for_image(
            path="/fake/template.png", timeout=1.0, interval=0.01
        )
    assert result == (10, 20)
    assert mock_locate.call_count == 3


@pytest.mark.asyncio
async def test_wait_for_image_raises_on_timeout(tmp_path: Path) -> None:
    """wait_for_image raises ImageWaitTimeout when no match appears in time."""
    from coord_smith.models.errors import ImageWaitTimeout

    with patch("pyautogui.locateCenterOnScreen", return_value=None):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        with pytest.raises(ImageWaitTimeout):
            await adapter.wait_for_image(
                path="/fake/template.png", timeout=0.05, interval=0.01
            )


async def test_post_click_signal_logs_match_and_continues(tmp_path: Path) -> None:
    """post_click_signal hit appends a structured signal record to action log."""
    from coord_smith.config.click_recipe import ClickRecipe

    template = _write_template(tmp_path / "loaded.png")
    located = MagicMock(x=400, y=500)
    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "x": 50,
                    "y": 60,
                    "post_click_signal": {
                        "image": str(template),
                        "confidence": 0.85,
                        "timeout": 1.0,
                        "interval": 0.01,
                    },
                },
            },
        }
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=50, y=60)),
        patch("pyautogui.locateCenterOnScreen", return_value=located),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        await adapter.execute(
            ExecutionRequest(mission_name="click_dispatch", payload={})
        )

    action_log = tmp_path / "artifacts" / "action-log" / "click-dispatched.jsonl"
    lines = [
        json.loads(line)
        for line in action_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    signals = [line for line in lines if "post_click_signal_template" in line]
    assert len(signals) == 1
    record = signals[0]
    assert record["post_click_signal_template"] == str(template)
    assert record["post_click_signal_confidence"] == 0.85
    assert record["post_click_signal_x"] == 400
    assert record["post_click_signal_y"] == 500


async def test_post_click_signal_timeout_raises(tmp_path: Path) -> None:
    """post_click_signal that never appears raises ImageWaitTimeout."""
    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import ImageWaitTimeout

    template = _write_template(tmp_path / "loaded.png")
    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "x": 50,
                    "y": 60,
                    "post_click_signal": {
                        "image": str(template),
                        "timeout": 0.05,
                        "interval": 0.01,
                    },
                },
            },
        }
    )
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=MagicMock()),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=50, y=60)),
        patch("pyautogui.locateCenterOnScreen", return_value=None),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        with pytest.raises(ImageWaitTimeout):
            await adapter.execute(
                ExecutionRequest(mission_name="click_dispatch", payload={})
            )


async def test_baseline_screenshot_unexpected_type_raises(tmp_path: Path) -> None:
    """execute() raises ScreenCaptureUnavailable when baseline screenshot is non-PIL."""
    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import ScreenCaptureUnavailable

    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "x": 100,
                    "y": 100,
                    "verify_transition": True,
                },
            },
        }
    )
    # First screenshot() call is the baseline — return a non-PIL value.
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value="not-a-pil-image"),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=100)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        with pytest.raises(ScreenCaptureUnavailable, match="unexpected type"):
            await adapter.execute(
                ExecutionRequest(mission_name="click_dispatch", payload={})
            )


async def test_post_click_screenshot_unexpected_type_raises(tmp_path: Path) -> None:
    """_verify_page_transition raises ScreenCaptureUnavailable for non-PIL post frame."""
    from PIL import Image

    from coord_smith.config.click_recipe import ClickRecipe
    from coord_smith.models.errors import ScreenCaptureUnavailable

    baseline = Image.new("RGB", (200, 200), color="white")

    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "x": 100,
                    "y": 100,
                    "verify_transition": True,
                    "transition_threshold": 0.01,
                },
            },
        }
    )
    # First screenshot() = valid PIL baseline; second = non-PIL post-click frame.
    with (
        patch("pyautogui.click"),
        patch(
            "pyautogui.screenshot", side_effect=[baseline, "not-a-pil-image"]
        ),
        patch("pyautogui.size", return_value=MagicMock(width=1920, height=1080)),
        patch("pyautogui.position", return_value=MagicMock(x=100, y=100)),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
        with pytest.raises(ScreenCaptureUnavailable, match="unexpected type"):
            await adapter.execute(
                ExecutionRequest(mission_name="click_dispatch", payload={})
            )


def test_fallback_refs_covers_exactly_released_missions() -> None:
    """_FALLBACK_REFS must stay in sync with RELEASED_MISSIONS.

    Each released mission must have a fallback evidence tuple so that
    standalone runs (without OpenClaw) produce a valid ExecutionResult.
    Any drift between _FALLBACK_REFS and RELEASED_MISSIONS would silently
    fall back to the generic action-log ref, bypassing per-mission validation.
    """
    from coord_smith.adapters.pyautogui_adapter import _FALLBACK_REFS
    from coord_smith.missions.names import RELEASED_MISSIONS

    expected = set(RELEASED_MISSIONS)
    actual = set(_FALLBACK_REFS.keys())
    assert actual == expected, (
        f"_FALLBACK_REFS keys must match RELEASED_MISSIONS exactly.\n"
        f"  Missing from _FALLBACK_REFS: {sorted(expected - actual)}\n"
        f"  Extra in _FALLBACK_REFS:     {sorted(actual - expected)}"
    )
