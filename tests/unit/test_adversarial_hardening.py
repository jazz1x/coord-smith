"""Regression tests for the adversarial bug-hunt + usability hardening pass.

Each test pins a specific finding so the fix cannot silently regress. Findings
were surfaced by independent adversarial review agents (concurrency/resources,
input/parsing, error-handling/ROP, domain-correctness, usability) and verified
before fixing. Grouped by the source file they exercise.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.action_log_writer import ActionLogWriter
from coord_smith.adapters.page_transition import PageTransitionVerifier
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord
from coord_smith.config.released_inputs import resolve_released_scope_inputs
from coord_smith.models.errors import ConfigError, ValidationError

# ---------------------------------------------------------------------------
# Finding A — Step.name path traversal into action-log JSONL filenames
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil_name",
    [
        "../../../../tmp/pwned",
        "/abs/path/escape",
        "a/b/c",
        "back\\slash",
        "..",
        ".",
        "",
    ],
)
def test_step_name_rejects_filesystem_escaping_names(evil_name: str) -> None:
    """A step name that could escape the run root when used as a filename is
    rejected at parse time (path-traversal write vector)."""
    with pytest.raises(ValueError):  # noqa: PT011 — pydantic wraps as ValueError
        Step(name=evil_name, coord=StepCoord(x=1, y=1))


@pytest.mark.parametrize(
    "ok_name",
    ["open-buy", "click_dispatch", "step1", "a..b", "héllo", "confirm-purchase"],
)
def test_step_name_allows_safe_names(ok_name: str) -> None:
    """Underscores, mid-token dots, digits, and unicode remain valid — only
    filesystem-escaping shapes are forbidden."""
    step = Step(name=ok_name, coord=StepCoord(x=1, y=1))
    assert step.name == ok_name


def test_action_log_path_rejects_escaping_key(tmp_path: Path) -> None:
    """Defense-in-depth: even a model_construct bypass cannot make the writer
    create a JSONL file outside the run-root action-log directory."""
    writer = ActionLogWriter(tmp_path)
    with pytest.raises(ValidationError):
        writer.action_log_path("../escape")


def test_action_log_path_accepts_normal_key(tmp_path: Path) -> None:
    path = writer_path = ActionLogWriter(tmp_path).action_log_path("step-dispatched")
    assert path.name == "step-dispatched.jsonl"
    assert writer_path.parent == tmp_path / "artifacts" / "action-log"


# ---------------------------------------------------------------------------
# Finding D — recipe models forbid unknown keys (typo'd fields)
# ---------------------------------------------------------------------------


def test_step_rejects_unknown_key() -> None:
    """A typo'd optional field (confidance vs confidence) fails loudly instead
    of being silently dropped and clicking with the default."""
    with pytest.raises(ValueError):  # noqa: PT011
        Step.model_validate(
            {"name": "x", "coord": {"x": 1, "y": 2}, "confidance": 0.5}
        )


def test_stepcoord_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        Step.model_validate({"name": "x", "coord": {"x": 1, "y": 2, "z": 3}})


# ---------------------------------------------------------------------------
# Finding E — region must have positive width/height
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_region",
    [
        [0, 0, 0, 0],  # zero extent
        [10, 10, -5, 5],  # negative width
        [10, 10, 5, -5],  # negative height
        [0, 0, 1920, 0],  # zero height
    ],
)
def test_step_rejects_nonpositive_region(bad_region: list[int]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        Step(name="x", image="t.png", region=tuple(bad_region))  # type: ignore[arg-type]


def test_step_rejects_nonpositive_transition_region() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        Step(
            name="x",
            coord=StepCoord(x=1, y=1),
            verify_transition=True,
            transition_region=(0, 0, 0, 0),
        )


def test_step_accepts_valid_region() -> None:
    step = Step(name="x", image="t.png", region=(0, 100, 1920, 800))
    assert step.region == (0, 100, 1920, 800)


# ---------------------------------------------------------------------------
# Finding (version) — schema version constrained to the supported set
# ---------------------------------------------------------------------------


def test_recipe_rejects_unsupported_version() -> None:
    from coord_smith.config.click_recipe import ClickRecipe

    with pytest.raises(ValueError):  # noqa: PT011
        ClickRecipe.model_validate(
            {"version": 2, "steps": [{"name": "x", "coord": {"x": 1, "y": 2}}]}
        )


# ---------------------------------------------------------------------------
# Finding (interval>timeout) — degenerate single-poll guard
# ---------------------------------------------------------------------------


def test_wait_for_rejects_interval_exceeding_timeout() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        Step.model_validate(
            {
                "name": "x",
                "image": "t.png",
                "wait_for": {"image": "a.png", "timeout": 1.0, "interval": 99.0},
            }
        )


# ---------------------------------------------------------------------------
# Finding C — missing required input raises ConfigError (exit 3), names the fix
# ---------------------------------------------------------------------------


def test_missing_input_raises_config_error_with_remedy() -> None:
    with pytest.raises(ConfigError) as exc_info:
        resolve_released_scope_inputs(argv=[], env={})
    msg = str(exc_info.value)
    assert "--session-ref" in msg
    assert "COORDSMITH_SESSION_REF" in msg


# ---------------------------------------------------------------------------
# Finding F — payload (x, y) override wins over recipe coords (ADR-003 level 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payload_coords_override_recipe_coord(tmp_path: Path) -> None:
    """A caller-injected payload (x, y) is clicked instead of step.coord."""
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(name="x", coord=StepCoord(x=42, y=99))

    with (
        patch.object(PyAutoGUIAdapter, "_validate_bounds"),
        patch.object(
            PyAutoGUIAdapter, "_verified_click", new_callable=AsyncMock
        ) as mock_click,
    ):
        await adapter._execute_step_dispatch(
            {"step": step, "step_idx": 0, "x": 700, "y": 300}
        )

    mock_click.assert_called_once()
    args, _ = mock_click.call_args
    assert args[:2] == (700, 300)  # payload coords, NOT the recipe's (42, 99)


@pytest.mark.asyncio
async def test_recipe_coord_used_when_no_payload_override(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(name="x", coord=StepCoord(x=42, y=99))

    with (
        patch.object(PyAutoGUIAdapter, "_validate_bounds"),
        patch.object(
            PyAutoGUIAdapter, "_verified_click", new_callable=AsyncMock
        ) as mock_click,
    ):
        await adapter._execute_step_dispatch({"step": step, "step_idx": 0})

    args, _ = mock_click.call_args
    assert args[:2] == (42, 99)


@pytest.mark.asyncio
async def test_partial_payload_override_raises(tmp_path: Path) -> None:
    """x without y is a caller bug — reject, do not fall through to recipe."""
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(name="x", coord=StepCoord(x=42, y=99))

    with pytest.raises(ConfigError):
        await adapter._execute_step_dispatch({"step": step, "step_idx": 0, "x": 700})


# ---------------------------------------------------------------------------
# Finding (change_ratio) — fraction of CHANGED pixels, not bbox coverage
# ---------------------------------------------------------------------------


def test_change_ratio_is_pixel_fraction_not_bbox_area() -> None:
    """Two tiny scattered changes span a huge bbox but change ~no pixels.
    change_ratio must reflect the changed-pixel count, not the bbox area."""
    size = (100, 100)
    baseline = Image.new("RGB", size, color="white")
    post = baseline.copy()
    # Two single-pixel changes at opposite corners → bbox ≈ whole frame,
    # but only 2 of 10_000 pixels actually changed.
    post.putpixel((0, 0), (0, 0, 0))
    post.putpixel((99, 99), (0, 0, 0))

    verifier = PageTransitionVerifier()
    result = verifier.verify_changed(baseline=baseline, post=post, threshold=0.5)

    # Old bbox-area logic would report ~1.0 → falsely "changed" at 0.5.
    assert result.change_ratio == pytest.approx(2 / 10_000)
    assert result.changed is False  # 0.0002 < 0.5 threshold


def test_change_ratio_full_swap_is_one() -> None:
    size = (10, 10)
    baseline = Image.new("RGB", size, color="white")
    post = Image.new("RGB", size, color="black")
    verifier = PageTransitionVerifier()
    result = verifier.verify_changed(baseline=baseline, post=post, threshold=0.01)
    assert result.change_ratio == pytest.approx(1.0)
    assert result.changed is True
