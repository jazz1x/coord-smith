"""Released-scope graph call sites that wire OpenClaw execution below the ceiling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from ez_ax.adapters.execution.client import (
    ExecutionAdapter,
    ExecutionResult,
    action_log_artifact_path,
    execute_within_scope,
)
from ez_ax.missions.names import ALL_MISSIONS
from ez_ax.models.errors import ConfigError, FlowError
from ez_ax.models.runtime import RuntimeState


@dataclass(frozen=True, slots=True)
class ReleasedRunContext:
    """Minimal released-scope run context owned by the orchestrator/graph."""

    run_root: Path
    approved_scope_ceiling: Literal["pageReadyObserved", "runCompletion"] = "runCompletion"

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
        if self.approved_scope_ceiling not in ("pageReadyObserved", "runCompletion"):
            msg = (
                "ReleasedRunContext.approved_scope_ceiling must be pageReadyObserved or runCompletion"
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


def seed_action_log_marker(*, run_root: Path, mission_name: str, key: str) -> Path:
    """Seed a released-scope action-log JSONL artifact with a confirming marker."""

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
    payload = {
        "ts": datetime.now(tz=ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "mission_name": mission_name,
        "event": key,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


async def execute_prepare_session_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    target_page_url: str,
    site_identity: str,
) -> ExecutionResult:
    """Execute the released prepare_session node with strict ceiling enforcement."""

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
    return result


async def execute_attach_session_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    session_ref: str,
    expected_auth_state: str,
) -> ExecutionResult:
    """Execute the released attach_session node with strict ceiling enforcement."""

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
    return result


async def execute_benchmark_validation_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    target_page_url: str,
) -> ExecutionResult:
    """Execute benchmark_validation with strict ceiling enforcement."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("benchmark_validation")
    state.target_page = target_page_url

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="benchmark_validation",
        key="enter-target-page",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="benchmark_validation",
        payload={"target_page_url": target_page_url},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_page_ready_observation_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released page_ready_observation node and continue to sync observation."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("page_ready_observation")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="page_ready_observation",
        key="page-ready-observed",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="page_ready_observation",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_sync_observation_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released sync_observation node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("sync_observation")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="sync_observation",
        key="sync-observed",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="sync_observation",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_target_actionability_observation_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released target_actionability_observation node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("target_actionability_observation")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="target_actionability_observation",
        key="target-actionable-observed",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="target_actionability_observation",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_armed_state_entry_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released armed_state_entry node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("armed_state_entry")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="armed_state_entry",
        key="armed-state",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="armed_state_entry",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_trigger_wait_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released trigger_wait node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("trigger_wait")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="trigger_wait",
        key="trigger-wait-complete",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="trigger_wait",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_click_dispatch_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released click_dispatch node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("click_dispatch")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="click_dispatch",
        key="click-dispatched",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="click_dispatch",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_click_completion_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released click_completion node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("click_completion")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="click_completion",
        key="click-completed",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="click_completion",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_success_observation_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released success_observation node."""

    require_existing_run_root(run_root=run.run_root)
    state.set_current_mission("success_observation")

    seed_action_log_marker(
        run_root=run.run_root,
        mission_name="success_observation",
        key="success-observation",
    )

    result = await execute_within_scope(
        adapter=adapter,
        mission_name="success_observation",
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result


async def execute_run_completion_node(
    *,
    state: RuntimeState,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
) -> ExecutionResult:
    """Execute the released run_completion node and stop at the ceiling."""

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
        payload={},
        approved_scope_ceiling=run.approved_scope_ceiling,
        run_root=run.run_root,
    )
    state.mission_state.evidence_refs = result.evidence_refs
    return result
