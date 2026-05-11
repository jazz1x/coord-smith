"""Contract: ``failure.jsonl`` record schema.

External callers (OpenClaw and any future orchestrator) read
``runs/<id>/artifacts/action-log/failure.jsonl`` to diagnose a failed
run. The set of keys, their types, and their semantics are documented
in ``docs/recipe-guide.md`` and must not change silently — a missing
or renamed key would break those callers.

This test locks the documented schema directly against the adapter's
emit. It runs a single failing step end-to-end (via the unit-level
adapter, not the CLI) so the assertion stays close to the data
producer.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord, WaitFor
from coord_smith.models.errors import ImageWaitTimeout

# The exact keys (and their types) callers depend on. Documented in
# docs/recipe-guide.md §Failure Artifacts.
REQUIRED_KEYS: dict[str, type] = {
    "ts": str,
    "mission_name": str,
    "event": str,
    "step_idx": int,
    "step_name": str,
    "error_class": str,
    "error_message": str,
    # screenshot is documented as a path-or-null, so we accept both.
}


def _write_template(tmp_path: Path, name: str = "anchor.png") -> Path:
    p = tmp_path / name
    Image.new("RGB", (8, 8), color="black").save(p)
    return p


@pytest.mark.asyncio
async def test_failure_jsonl_record_matches_documented_schema(
    tmp_path: Path,
) -> None:
    """A single failure record must contain every documented key with the
    documented type."""
    template = _write_template(tmp_path, "never.png")

    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(
        name="confirm-purchase",
        coord=StepCoord(x=10, y=20),
        wait_for=WaitFor(image=str(template), timeout=0.05, interval=0.01),
    )
    payload = {"step": step.model_dump(), "step_idx": 1}

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            return_value=None,
        ),
        patch(
            "pyautogui.screenshot",
            return_value=Image.new("RGB", (50, 50), color="gray"),
        ),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ImageWaitTimeout):
            await adapter._execute_step_dispatch(payload)

    failure_log = tmp_path / "artifacts" / "action-log" / "failure.jsonl"
    assert failure_log.is_file(), (
        "failure.jsonl must exist after a typed dispatch failure"
    )
    line = failure_log.read_text(encoding="utf-8").strip()
    assert line, "failure.jsonl must contain at least one record"

    record = json.loads(line)

    # All documented required keys present with the documented type.
    for key, expected_type in REQUIRED_KEYS.items():
        assert key in record, (
            f"failure.jsonl is missing documented key '{key}' "
            f"(see docs/recipe-guide.md §Failure Artifacts)"
        )
        assert isinstance(record[key], expected_type), (
            f"failure.jsonl key '{key}' must be {expected_type.__name__}, "
            f"got {type(record[key]).__name__}: {record[key]!r}"
        )

    # screenshot is documented as either an absolute path or null.
    assert "screenshot" in record, (
        "failure.jsonl must include the 'screenshot' key "
        "(null when capture failed, else absolute path)"
    )
    if record["screenshot"] is not None:
        assert isinstance(record["screenshot"], str)
        assert Path(record["screenshot"]).is_absolute(), (
            "screenshot path must be absolute so callers can read it without "
            "knowing the run-root: "
            f"{record['screenshot']!r}"
        )

    # Semantic invariants — small handful that callers cannot work around.
    assert record["mission_name"] == "step_dispatch", (
        "failure.jsonl mission_name must be 'step_dispatch' (the mission "
        "where dispatch errors originate)"
    )
    assert record["event"] == "step-dispatch-failed", (
        "failure.jsonl event must be the canonical 'step-dispatch-failed' "
        "literal — callers grep for it"
    )
    assert record["step_idx"] == 1
    assert record["step_name"] == "confirm-purchase"
    assert record["error_class"] == "ImageWaitTimeout"
    assert record["error_message"], "error_message must be non-empty"


@pytest.mark.asyncio
async def test_failure_jsonl_record_has_no_unknown_keys_documented_set(
    tmp_path: Path,
) -> None:
    """The documented schema is a fixed key set. If the adapter starts
    emitting a NEW key, that's a public-API change and the docs must
    catch up first — this test fails so it can't slip in unnoticed.

    Allowed superset: REQUIRED_KEYS + 'screenshot'.
    """
    template = _write_template(tmp_path, "never.png")
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(
        name="x",
        coord=StepCoord(x=10, y=20),
        wait_for=WaitFor(image=str(template), timeout=0.05, interval=0.01),
    )
    payload = {"step": step.model_dump(), "step_idx": 0}

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            return_value=None,
        ),
        patch(
            "pyautogui.screenshot",
            return_value=Image.new("RGB", (50, 50), color="gray"),
        ),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ImageWaitTimeout):
            await adapter._execute_step_dispatch(payload)

    failure_log = tmp_path / "artifacts" / "action-log" / "failure.jsonl"
    record = json.loads(failure_log.read_text(encoding="utf-8").strip())

    allowed = set(REQUIRED_KEYS.keys()) | {"screenshot"}
    extra = set(record.keys()) - allowed
    assert not extra, (
        f"failure.jsonl gained undocumented keys {sorted(extra)} — "
        "update docs/recipe-guide.md §Failure Artifacts before adding new "
        "keys so external callers know what they can rely on"
    )
