"""Regression tests for adversarial hardening CYCLE 4.

Cycle 4 (multi-agent, 19 hunted / 18 confirmed) hardened the typed-evidence
boundary around screenshot save, made --dry-run a no-permission validator,
turned a failed --target-window into a hard error, and mapped directory/
unreadable recipes + reserved-key step names to typed errors.
See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord, load_click_recipe
from coord_smith.graph.pyautogui_cli_entrypoint import _run, main
from coord_smith.models.errors import ConfigError, ScreenCaptureUnavailable

# ---------------------------------------------------------------------------
# screenshot-save-escapes-typed-evidence — save() failure → ScreenCaptureUnavailable
# ---------------------------------------------------------------------------


def test_screenshot_save_failure_raises_typed(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    fake_img = Image.new("RGB", (4, 4))
    with (
        patch("pyautogui.screenshot", return_value=fake_img),
        patch.object(Image.Image, "save", side_effect=OSError("No space left")),
        pytest.raises(ScreenCaptureUnavailable, match="save"),
    ):
        adapter._capture_screenshot("step-observed", step_idx=0)


# ---------------------------------------------------------------------------
# dry-run-blocked-by-permission-preflight — dry-run validates WITHOUT preflight
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_does_not_call_preflight(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    recipe = tmp_path / "r.yaml"
    recipe.write_text(
        "version: 1\nsteps:\n  - name: s\n    coord: {x: 1, y: 2}\n",
        encoding="utf-8",
    )
    # preflight would raise if called — assert dry-run never touches it.
    with patch.object(
        PyAutoGUIAdapter, "preflight",
        side_effect=AssertionError("preflight must NOT run on dry-run"),
    ):
        code = await _run(
            argv=[
                "--dry-run", "--click-recipe", str(recipe),
                "--session-ref", "s", "--expected-auth-state", "a",
                "--target-page-url", "https://x.invalid/p", "--site-identity", "x",
            ],
            base_dir=tmp_path,
        )
    assert code == 0


def test_dry_run_missing_input_exits_3_without_preflight(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    for k in (
        "COORDSMITH_SESSION_REF", "COORDSMITH_EXPECTED_AUTH_STATE",
        "COORDSMITH_TARGET_PAGE_URL", "COORDSMITH_SITE_IDENTITY",
    ):
        monkeypatch.delenv(k, raising=False)
    # No preflight patch: proves the exit-3 comes from input validation, not
    # a permission failure (which would be exit 2).
    with patch.object(
        PyAutoGUIAdapter, "preflight",
        side_effect=AssertionError("preflight must NOT run on dry-run"),
    ):
        code = main(argv=["--dry-run"])
    assert code == 3


# ---------------------------------------------------------------------------
# target-window-typo-silent-wrong-click — failed activation is fatal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_target_window_activation_failure_raises_config_error() -> None:
    import subprocess

    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    with (
        patch.object(cli.platform, "system", return_value="Darwin"),
        patch.object(
            cli.subprocess, "run",
            side_effect=subprocess.CalledProcessError(1, ["osascript"]),
        ),
        pytest.raises(ConfigError, match="Typo"),
    ):
        await cli._activate_target_window("Typo", settle_seconds=0.0)


# ---------------------------------------------------------------------------
# directory-or-unreadable-recipe-exits-1-not-3 — typed config error
# ---------------------------------------------------------------------------


def test_directory_recipe_raises_config_error(tmp_path: Path) -> None:
    a_dir = tmp_path / "recipe-dir"
    a_dir.mkdir()
    with pytest.raises(ConfigError, match="not a readable file"):
        load_click_recipe(a_dir)


# ---------------------------------------------------------------------------
# guard-log-reserved-key-collision — reserved canonical key as step name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reserved",
    ["step-observed", "step-dispatched", "step-captured",
     "attach-session", "prepare-session", "release-ceiling-stop"],
)
def test_step_name_rejects_reserved_action_log_key(reserved: str) -> None:
    with pytest.raises(ValueError, match="reserved action-log key"):
        Step(name=reserved, coord=StepCoord(x=1, y=1))


def test_step_name_allows_non_reserved() -> None:
    step = Step(name="confirm-purchase", coord=StepCoord(x=1, y=1))
    assert step.name == "confirm-purchase"
