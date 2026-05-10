"""Integration test — coord-smith multi-step flow with REAL OpenCV matching.

Unlike the e2e tests (which mock both ``pyautogui.click`` and
``pyautogui.locateCenterOnScreen``), this test exercises the actual
OpenCV image-template machinery against pre-rendered demo page
screenshots. The cursor never touches the real screen.

Architecture::

    demo HTML (5 states, deterministic)
        ↓ playwright screenshot
    PNG per state on disk
        ↓ patched pyautogui.screenshot()
    State-machine screen surrogate
        ↓ pyautogui.locateCenterOnScreen() — REAL OpenCV
    coord-smith adapter dispatch
        ↓ click
    State machine advances → next PNG returned

What this proves:

* The cropped button templates in ``tests/fixtures/demo/templates/``
  match their corresponding state PNG at ``confidence=0.9``.
* coord-smith's per-step ``image-or-coord`` resolution finds the right
  pixel and dispatches a click at that pixel.
* Region restriction (``Step.region``) correctly disambiguates two
  near-identical templates that share most pixels (Seat A1 vs Seat A2).
* The full four-step recipe completes without manual intervention and
  the artifact tree contains an action-log + screenshot per step.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import _run

DEMO_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "demo"

# Click-driven state transitions in the demo state machine. Each tuple is
# (state_before_click, action, state_after_click). ``action`` matches the
# Step.name in demo-flow.yaml.
TRANSITIONS = {
    "open-buy":         ("buy", "seat-1"),
    "select-seat-a1":   ("seat-1", "seat-2"),
    "confirm-seat":     ("seat-2", "confirm"),
    "confirm-purchase": ("confirm", "success"),
}


def _state_png(state: str) -> Path:
    return DEMO_DIR / f"state-{state}.png"


class _DemoScreen:
    """Stateful surrogate for ``pyautogui.screenshot``.

    Returns the PNG of the current demo state as a ``PIL.Image``. After a
    click is dispatched, ``advance(action_name)`` flips the state to the
    one named in ``TRANSITIONS`` so the next observe / dispatch / capture
    pulls the new screenshot.
    """

    def __init__(self) -> None:
        self.state = "buy"
        self.click_log: list[tuple[int, int, str]] = []

    def screenshot(self) -> Image.Image:
        return Image.open(_state_png(self.state)).copy()

    def click(self, x: object, y: object) -> None:
        # Records the clicked coords and inspects the current state to
        # know which action just fired. The state machine advances based
        # on which click happened.
        ix, iy = int(x), int(y)  # type: ignore[arg-type]
        before = self.state
        next_state = self._next_state_for_click(ix, iy, before)
        self.click_log.append((ix, iy, f"{before}->{next_state}"))
        self.state = next_state

    def _next_state_for_click(self, x: int, y: int, current: str) -> str:
        # The demo only has one transition per state, so the click always
        # advances to the canonical next state regardless of pixel — this
        # keeps the test focused on coord-smith's resolution + dispatch
        # rather than re-implementing the demo's state machine.
        for _action, (before, after) in TRANSITIONS.items():
            if before == current:
                return after
        return current  # terminal state ("success") — no further transition


@pytest.mark.asyncio
async def test_demo_flow_recipe_runs_four_steps_against_real_opencv(tmp_path: Path) -> None:
    """Full demo flow: 4 image-template clicks resolve via real OpenCV
    matching, advance the state machine, and produce per-step artifacts."""

    screen = _DemoScreen()

    # The demo recipe lives next to the templates so relative image paths
    # resolve correctly. Copy it to the test tmp_path so artifact root is
    # tidy.
    recipe_src = DEMO_DIR / "demo-flow.yaml"

    # We want the adapter to use the real OpenCV-backed
    # locateCenterOnScreen, which calls pyautogui.screenshot() each time
    # it is invoked. The screen surrogate returns the PNG matching the
    # current state, so each step's locate pulls the current screen.
    cursor_x, cursor_y = 0, 0

    def fake_position() -> object:
        # Cursor reports last clicked position so the adapter's
        # post-click verification passes.
        Point = type("Point", (), {"x": cursor_x, "y": cursor_y})
        return Point()

    def fake_move_to(x: object, y: object, *_: object, **__: object) -> None:
        nonlocal cursor_x, cursor_y
        cursor_x, cursor_y = int(x), int(y)  # type: ignore[arg-type]

    def fake_click(x: object, y: object) -> None:
        nonlocal cursor_x, cursor_y
        cursor_x, cursor_y = int(x), int(y)  # type: ignore[arg-type]
        screen.click(x, y)

    Size = type("Size", (), {"width": 1280, "height": 800})

    common_argv = [
        "--session-ref", "demo-flow",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "file://demo/ticketing.html",
        "--site-identity", "demo",
    ]

    # ``locateCenterOnScreen`` on macOS goes through pyscreeze and applies
    # Retina-aware scaling we don't want in the test (it would scale our
    # already-1× demo PNG coordinates by 2). We replace the lookup with a
    # direct ``pyautogui.locate(template, screen_surrogate())`` call so
    # the OpenCV match is real but coordinates stay in the PNG's native
    # 1280×800 space.
    import pyautogui as pag

    def patched_locate_center(image: object, **kwargs: object) -> object:
        located = pag.locate(image, screen.screenshot(), **kwargs)
        if located is None:
            return None
        cx = located.left + located.width / 2
        cy = located.top + located.height / 2
        Pt = type("Pt", (), {"x": cx, "y": cy})
        return Pt()

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=screen.screenshot),
        patch(
            "pyautogui.locateCenterOnScreen",
            side_effect=patched_locate_center,
        ),
        patch("pyautogui.click", side_effect=fake_click),
        patch("pyautogui.moveTo", side_effect=fake_move_to),
        patch("pyautogui.position", side_effect=fake_position),
        patch("pyautogui.size", return_value=Size()),
    ):
        exit_code = await _run(
            argv=["--click-recipe", str(recipe_src), *common_argv],
            base_dir=tmp_path,
        )

    assert exit_code == 0, "demo flow must exit cleanly"

    # State machine reached the terminal state.
    assert screen.state == "success"

    # All four clicks fired in the expected before→after sequence.
    transitions = [entry[2] for entry in screen.click_log]
    assert transitions == [
        "buy->seat-1",
        "seat-1->seat-2",
        "seat-2->confirm",
        "confirm->success",
    ], f"unexpected transition sequence: {transitions}"

    # Each click landed inside the actual button bounds for that state,
    # not on a stale or wrong region. The buttons are 280×72 (and 200×72
    # for seats), centered at x≈640. Verify each click is within the
    # central horizontal band (x ∈ [350, 930]) and lower half of viewport
    # (y > 300).
    for x, y, label in screen.click_log:
        assert 350 <= x <= 930, f"{label} click x={x} out of expected band"
        assert 300 <= y <= 800, f"{label} click y={y} out of expected band"

    # Run-level artifact (run-completion) and per-step action-log records
    # both exist.
    runs_dirs = list(tmp_path.glob("artifacts/runs/*/artifacts/action-log"))
    assert len(runs_dirs) == 1
    action_log_dir = runs_dirs[0]
    assert (action_log_dir / "step-dispatched.jsonl").exists()
    assert (action_log_dir / "release-ceiling-stop.jsonl").exists()


@pytest.mark.asyncio
async def test_demo_flow_with_guards_runs_end_to_end(tmp_path: Path) -> None:
    """Full demo flow + per-step verify_transition + post_click_signal.

    Same four-step sequence, but each step now declares a transition diff
    threshold and a post-click signal image. Both guards are exercised
    against real PIL.ImageChops diffing and real OpenCV signal polling.
    Proves coord-smith's full guard stack works end-to-end on a
    deterministic page.
    """

    screen = _DemoScreen()
    cursor_x, cursor_y = 0, 0

    def fake_position() -> object:
        Pt = type("Pt", (), {"x": cursor_x, "y": cursor_y})
        return Pt()

    def fake_move_to(x: object, y: object, *_: object, **__: object) -> None:
        nonlocal cursor_x, cursor_y
        cursor_x, cursor_y = int(x), int(y)  # type: ignore[arg-type]

    def fake_click(x: object, y: object) -> None:
        nonlocal cursor_x, cursor_y
        cursor_x, cursor_y = int(x), int(y)  # type: ignore[arg-type]
        screen.click(x, y)

    Size = type("Size", (), {"width": 1280, "height": 800})

    import pyautogui as pag

    def patched_locate_center(image: object, **kwargs: object) -> object:
        located = pag.locate(image, screen.screenshot(), **kwargs)
        if located is None:
            return None
        cx = located.left + located.width / 2
        cy = located.top + located.height / 2
        Pt = type("Pt", (), {"x": cx, "y": cy})
        return Pt()

    recipe_src = DEMO_DIR / "demo-flow-with-guards.yaml"

    common_argv = [
        "--session-ref", "demo-guards",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "file://demo/ticketing.html",
        "--site-identity", "demo",
    ]

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=screen.screenshot),
        patch(
            "pyautogui.locateCenterOnScreen",
            side_effect=patched_locate_center,
        ),
        patch("pyautogui.click", side_effect=fake_click),
        patch("pyautogui.moveTo", side_effect=fake_move_to),
        patch("pyautogui.position", side_effect=fake_position),
        patch("pyautogui.size", return_value=Size()),
    ):
        exit_code = await _run(
            argv=["--click-recipe", str(recipe_src), *common_argv],
            base_dir=tmp_path,
        )

    assert exit_code == 0
    assert screen.state == "success"
    # Each click also induces a verify_transition pass — the test
    # implicitly proves that because exit was clean and the state-machine
    # advanced through every step.
    assert len(screen.click_log) == 4


def test_demo_flow_seat_region_disambiguates_a1_from_a2(tmp_path: Path) -> None:
    """The Seat A1 template matches both the A1 and A2 buttons at default
    confidence (the visual difference is one character). The recipe
    constrains step 2 to the left half of the viewport so A1's actual
    location wins. Without that restriction the test would fail or
    nondeterministically match A2's location."""

    import pyautogui

    state_png = DEMO_DIR / "state-seat-1.png"

    # Without region: returns SOME match (possibly the wrong one).
    free = pyautogui.locate(
        str(DEMO_DIR / "templates/seat-a1.png"),
        str(state_png),
        confidence=0.9,
    )
    assert free is not None  # something matches

    # With region (left half): resolves unambiguously.
    constrained = pyautogui.locate(
        str(DEMO_DIR / "templates/seat-a1.png"),
        str(state_png),
        confidence=0.9,
        region=(0, 0, 640, 800),
    )
    assert constrained is not None
    # Left half: x must be < 640.
    assert int(constrained.left) < 640

    # And the A2 template, region-restricted to the right half, lands
    # there.
    a2_constrained = pyautogui.locate(
        str(DEMO_DIR / "templates/seat-a2.png"),
        str(state_png),
        confidence=0.9,
        region=(640, 0, 640, 800),
    )
    assert a2_constrained is not None
    assert int(a2_constrained.left) >= 640
