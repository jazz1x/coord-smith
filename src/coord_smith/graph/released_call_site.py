"""Released-scope graph call sites that wire OpenClaw execution below the ceiling.

The released graph is six nodes:

* per-run setup (×1):  ``attach_session`` → ``prepare_session``
* per-step loop (×N):  ``step_observe`` → ``step_dispatch`` → ``step_capture``
* per-run teardown (×1): ``run_completion``

Each call-site here is the orchestrator's view: it seeds an action-log
marker, dispatches to the injected ``ExecutionAdapter``, records evidence
refs on state, and enforces the per-step evidence priority gate so a step
without action-log evidence cannot pass silently.

The legacy nine missions that orbited a single click event
(``benchmark_validation`` / ``page_ready_observation`` / ``sync_observation``
/ ``target_actionability_observation`` / ``armed_state_entry`` /
``trigger_wait`` / ``click_dispatch`` / ``click_completion`` /
``success_observation``) have been collapsed into the per-step trio; see
``docs/prd-multi-step-flow-recipe.md`` §2.4 D2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from coord_smith.adapters.execution.client import (
    ExecutionAdapter,
    ExecutionResult,
    action_log_artifact_path,
    execute_within_scope,
)
from coord_smith.config.click_recipe import Step
from coord_smith.evidence.envelope import enforce_evidence_priority_gate
from coord_smith.missions.names import ALL_MISSIONS
from coord_smith.models.errors import ConfigError, FlowError
from coord_smith.models.runtime import RuntimeState


@dataclass(frozen=True, slots=True)
class ReleasedRunContext:
    """Minimal released-scope run context owned by the orchestrator/graph.

    With the ceiling system collapsed (see ``models/runtime.py``), the only
    valid ceiling is ``runCompletion``. The field is preserved for payload
    backwards-compat; any other value is rejected at construction.
    """

    run_root: Path
    approved_scope_ceiling: Literal["runCompletion"] = "runCompletion"

    def __post_init__(self) -> None:
        if not isinstance(self.run_root, Path):
            raise ConfigError("ReleasedRunContext.run_root must be a pathlib.Path")
        if not self.run_root.exists():
            msg = (
                "ReleasedRunContext.run_root must exist before execution: "
                f"run_root='{self.run_root}'"
            )
            raise ConfigError(msg)
        if not self.run_root.is_dir():
            msg = (
                "ReleasedRunContext.run_root must be a directory: "
                f"run_root='{self.run_root}'"
            )
            raise ConfigError(msg)
        if self.approved_scope_ceiling != "runCompletion":
            msg = (
                "ReleasedRunContext.approved_scope_ceiling must be "
                "'runCompletion' (the released graph has a single ceiling)"
            )
            raise FlowError(msg)


def require_existing_run_root(*, run_root: Path) -> None:
    """Enforce released-scope contract that run_root exists before wrapper execution."""

    if not run_root.exists():
        msg = (
            "Released-scope run_root must exist before execution: "
            f"run_root='{run_root}'"
        )
        raise ConfigError(msg)
    if not run_root.is_dir():
        msg = f"Released-scope run_root must be a directory: run_root='{run_root}'"
        raise ConfigError(msg)


def seed_action_log_marker(
    *,
    run_root: Path,
    mission_name: str,
    key: str,
    step_idx: int | None = None,
    step_name: str | None = None,
) -> Path:
    """Seed a released-scope action-log JSONL artifact with a confirming marker.

    For per-step missions, ``step_idx`` and ``step_name`` are recorded in the
    payload so the action log contains enough context to reconstruct the
    step sequence after the run. The record is **appended** to the action-log
    file: per-step missions share a single file (``step-observed.jsonl`` etc.)
    across all step iterations, so every iteration must accumulate rather than
    overwrite.
    """

    require_existing_run_root(run_root=run_root)
    if not isinstance(mission_name, str):
        raise FlowError("Released-scope mission_name must be a string")
    if not mission_name:
        raise FlowError("Released-scope mission_name must be non-empty")
    if not mission_name.strip():
        raise FlowError("Released-scope mission_name must not be whitespace-only")
    if mission_name != mission_name.strip():
        raise FlowError(
            "Released-scope mission_name must not have leading or trailing whitespace"
        )
    if mission_name not in ALL_MISSIONS:
        raise FlowError(
            f"Released-scope mission_name is not a known mission: '{mission_name}'"
        )
    path = action_log_artifact_path(run_root=run_root, key=key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "ts": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "mission_name": mission_name,
        "event": key,
    }
    if step_idx is not None:
        payload["step_idx"] = step_idx
    if step_name is not None:
        payload["step_name"] = step_name
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


# ---- Per-run setup ----------------------------------------------------


async def execute_attach_session_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    session_ref: str,
    expected_auth_state: str,
) -> ExecutionResult:
    """Execute the released attach_session node (per-run, runs once)."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("attach_session")
    state.session_ref = session_ref

    seed_action_log_marker(
        run_root=run.run_root, mission_name="attach_session", key="attach-session"
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="attach_session",
        payload={
            "session_ref": session_ref,
            "expected_auth_state": expected_auth_state,
        },
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    enforce_evidence_priority_gate(result)
    return result


async def execute_prepare_session_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    target_page_url: str,
    site_identity: str,
) -> ExecutionResult:
    """Execute the released prepare_session node (per-run, runs once)."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("prepare_session")
    state.target_page = target_page_url
    state.site_identity = site_identity

    seed_action_log_marker(
        run_root=run.run_root, mission_name="prepare_session", key="prepare-session"
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="prepare_session",
        payload={"target_page_url": target_page_url, "site_identity": site_identity},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    enforce_evidence_priority_gate(result)
    return result


# ---- Per-step loop (executes N times for N-step recipe) ----------------


async def execute_step_observe_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    step_idx: int,
    step: Step,
) -> ExecutionResult:
    """Pre-click observation for one step.

    Captures the on-screen state immediately before dispatch (folds the
    legacy ``page_ready_observation``/``sync_observation``/
    ``target_actionability_observation`` lifecycle into a single
    pre-click checkpoint). If the step declares ``wait_for``, the adapter
    waits for the configured image to appear within timeout.
    """

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("step_observe")
    state.current_step_idx = step_idx

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="step_observe",
        key="step-observed",
        step_idx=step_idx,
        step_name=step.name,
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="step_observe",
        payload={"step_idx": step_idx, "step": step},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    enforce_evidence_priority_gate(result)
    return result


async def execute_step_dispatch_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    step_idx: int,
    step: Step,
) -> ExecutionResult:
    """Click dispatch for one step.

    Honors ``step.prefer`` to decide whether ``image`` or ``coord`` is the
    primary attempt; the other (when present) becomes the fallback. Folds
    the legacy ``armed_state_entry``/``trigger_wait``/``click_dispatch``
    sequence into a single dispatch event.
    """

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("step_dispatch")
    state.current_step_idx = step_idx

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="step_dispatch",
        key="step-dispatched",
        step_idx=step_idx,
        step_name=step.name,
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="step_dispatch",
        payload={"step_idx": step_idx, "step": step},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    enforce_evidence_priority_gate(result)
    return result


async def execute_step_capture_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    step_idx: int,
    step: Step,
) -> ExecutionResult:
    """Post-click capture for one step.

    Captures post-click screenshot, optional transition diff, and optional
    post-click signal polling. Folds the legacy ``click_completion`` and
    ``success_observation`` missions into a single capture event.
    """

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("step_capture")
    state.current_step_idx = step_idx

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="step_capture",
        key="step-captured",
        step_idx=step_idx,
        step_name=step.name,
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="step_capture",
        payload={"step_idx": step_idx, "step": step},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    enforce_evidence_priority_gate(result)
    return result


# ---- Per-run teardown -----------------------------------------------


async def execute_run_completion_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released run_completion node — sealed exit at the ceiling."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("run_completion")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="run_completion",
        key="release-ceiling-stop",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="run_completion",
        payload={"step_count": len(state.step_results)},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    enforce_evidence_priority_gate(result)
    return result
