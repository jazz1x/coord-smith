"""Unit tests for the in-step image↔coord fallback chain.

A step that declares both ``image`` and ``coord`` forms an implicit
fallback chain: the field named in ``prefer`` (default ``image``) is
attempted first, the other is the fallback. These tests cover the
adapter's ``_resolve_step_click_coords`` directly so the logic is
verified without invoking the full graph.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord


def _make_adapter(tmp_path: Path) -> PyAutoGUIAdapter:
    return PyAutoGUIAdapter(run_root=tmp_path)


def _write_template_png(tmp_path: Path, name: str = "btn.png") -> Path:
    path = tmp_path / name
    Image.new("RGB", (10, 10), color="black").save(path)
    return path


def test_image_only_step_resolves_via_image_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An image-only step resolves coords via locateCenterOnScreen."""
    template = _write_template_png(tmp_path)

    def fake_locate(*args: object, **kwargs: object) -> object:
        Located = type("L", (), {"x": 123, "y": 456})
        return Located()

    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
        fake_locate,
    )
    adapter = _make_adapter(tmp_path)
    step = Step(name="x", image=str(template))
    assert adapter._resolve_step_click_coords(step) == (123, 456)


def test_coord_only_step_returns_step_coord(tmp_path: Path) -> None:
    """A coord-only step returns its declared (x, y)."""
    adapter = _make_adapter(tmp_path)
    step = Step(name="x", coord=StepCoord(x=42, y=99))
    assert adapter._resolve_step_click_coords(step) == (42, 99)


def test_both_targets_default_prefer_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both image and coord are present, image is tried first by default."""
    template = _write_template_png(tmp_path)

    def fake_locate(*args: object, **kwargs: object) -> object:
        Located = type("L", (), {"x": 100, "y": 200})
        return Located()

    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
        fake_locate,
    )
    adapter = _make_adapter(tmp_path)
    step = Step(name="x", image=str(template), coord=StepCoord(x=999, y=888))
    # Image succeeds, so we never see the coord.
    assert adapter._resolve_step_click_coords(step) == (100, 200)


def test_image_failure_falls_back_to_coord(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When image matching fails, the declared coord is used as fallback."""
    template = _write_template_png(tmp_path)

    def fake_locate(*args: object, **kwargs: object) -> None:
        return None  # image not matched

    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
        fake_locate,
    )
    adapter = _make_adapter(tmp_path)
    step = Step(name="x", image=str(template), coord=StepCoord(x=42, y=99))
    assert adapter._resolve_step_click_coords(step) == (42, 99)


def test_prefer_coord_override_tries_coord_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``prefer: coord`` flips the chain so coord is the primary attempt."""
    template = _write_template_png(tmp_path)
    locate_called: list[bool] = []

    def fake_locate(*args: object, **kwargs: object) -> object:
        locate_called.append(True)
        Located = type("L", (), {"x": 100, "y": 200})
        return Located()

    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
        fake_locate,
    )
    adapter = _make_adapter(tmp_path)
    step = Step(
        name="x",
        image=str(template),
        coord=StepCoord(x=42, y=99),
        prefer="coord",
    )
    # Coord wins because prefer flipped the order; image is never consulted.
    assert adapter._resolve_step_click_coords(step) == (42, 99)
    assert not locate_called, "image matching must not run when coord is primary"


def test_prefer_coord_with_image_fallback_path_is_unused_on_coord_success(
    tmp_path: Path,
) -> None:
    """``prefer: coord`` returns coord when coord exists; image is fallback only."""
    adapter = _make_adapter(tmp_path)
    step = Step(name="x", coord=StepCoord(x=7, y=8), prefer="coord")
    # No image declared; coord-only path covered by other test, but verify
    # the explicit prefer override still returns the same result.
    assert adapter._resolve_step_click_coords(step) == (7, 8)


def test_no_target_returns_none(tmp_path: Path) -> None:
    """A step with no resolvable target returns None.

    In normal usage the Step Pydantic validator rejects the no-target case,
    so this guard only fires for synthesized steps that bypass validation.
    The adapter must not crash.
    """
    # Construct via the model_construct escape hatch to bypass validation.
    step = Step.model_construct(
        name="x",
        image=None,
        coord=None,
        prefer=None,
    )
    adapter = _make_adapter(tmp_path)
    assert adapter._resolve_step_click_coords(step) is None
