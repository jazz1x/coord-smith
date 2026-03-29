"""Released-scope LangGraph wiring (scaffold hardening only).

This module wires the released mission sequence into a LangGraph StateGraph
while staying strictly at or below the released ceiling `runCompletion`.

It does not provide a real OpenClaw transport implementation. Tests use a fake
adapter to validate wiring deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict, cast

from ez_ax.adapters.execution.client import ExecutionAdapter
from ez_ax.graph.released_call_site import (
    ReleasedRunContext,
    execute_armed_state_entry_node,
    execute_attach_session_node,
    execute_benchmark_validation_node,
    execute_click_completion_node,
    execute_click_dispatch_node,
    execute_page_ready_observation_node,
    execute_prepare_session_node,
    execute_run_completion_node,
    execute_success_observation_node,
    execute_sync_observation_node,
    execute_target_actionability_observation_node,
    execute_trigger_wait_node,
)
from ez_ax.graph.released_run_root import create_run_root, generate_run_id
from ez_ax.models.errors import ConfigError, FlowError
from ez_ax.models.runtime import RuntimeState

if TYPE_CHECKING:
    from langgraph.graph import StateGraph
    from langgraph.graph.state import CompiledStateGraph


@dataclass(frozen=True, slots=True)
class ReleasedLangGraphRunResult:
    state: RuntimeState
    run: ReleasedRunContext


class _WithRunRoot(Protocol):
    def __call__(self, *, run_root: Path) -> object: ...


class _ReleasedGraphState(TypedDict):
    runtime: RuntimeState


def _bind_adapter_run_root(
    *, adapter: ExecutionAdapter, run_root: Path
) -> ExecutionAdapter:
    with_run_root: object = getattr(adapter, "with_run_root", None)
    if with_run_root is None:
        return adapter
    if not callable(with_run_root):
        msg = "ExecutionAdapter.with_run_root must be callable when present"
        raise ConfigError(msg)
    try:
        bound = cast(_WithRunRoot, with_run_root)(run_root=run_root)
    except TypeError as exc:
        msg = "ExecutionAdapter.with_run_root must accept keyword argument 'run_root'"
        raise ConfigError(msg) from exc

    if not callable(getattr(bound, "execute", None)):
        msg = "ExecutionAdapter.with_run_root must return an ExecutionAdapter"
        raise ConfigError(msg)
    return cast(ExecutionAdapter, bound)


def _require_released_attach_inputs(
    *, session_ref: str, expected_auth_state: str
) -> None:
    for label, value in (
        ("session_ref", session_ref),
        ("expected_auth_state", expected_auth_state),
    ):
        if not isinstance(value, str):
            msg = f"Released-scope attach_session input '{label}' must be a string"
            raise ConfigError(msg)
        if not value:
            msg = f"Released-scope attach_session input '{label}' must be non-empty"
            raise ConfigError(msg)
        if not value.strip():
            msg = (
                f"Released-scope attach_session input '{label}' must not be "
                "whitespace-only"
            )
            raise ConfigError(msg)
        if value != value.strip():
            msg = (
                f"Released-scope attach_session input '{label}' must not have leading "
                "or trailing whitespace"
            )
            raise ConfigError(msg)


def _require_released_prepare_inputs(
    *, target_page_url: str, site_identity: str
) -> None:
    for label, value in (
        ("target_page_url", target_page_url),
        ("site_identity", site_identity),
    ):
        if not isinstance(value, str):
            msg = f"Released-scope prepare_session input '{label}' must be a string"
            raise ConfigError(msg)
        if not value:
            msg = f"Released-scope prepare_session input '{label}' must be non-empty"
            raise ConfigError(msg)
        if not value.strip():
            msg = (
                f"Released-scope prepare_session input '{label}' must not be "
                "whitespace-only"
            )
            raise ConfigError(msg)
        if value != value.strip():
            msg = (
                f"Released-scope prepare_session input '{label}' must not have leading "
                "or trailing whitespace"
            )
            raise ConfigError(msg)


def build_released_scope_execution_graph(
    *,
    adapter: ExecutionAdapter,
    run: ReleasedRunContext,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
) -> CompiledStateGraph[
    _ReleasedGraphState, None, _ReleasedGraphState, _ReleasedGraphState
]:
    """Return a compiled released-scope graph that executes only released nodes."""

    from langgraph.graph import END, START, StateGraph

    if not isinstance(run, ReleasedRunContext):
        raise ConfigError("Released-scope run must be a ReleasedRunContext")
    if not callable(getattr(adapter, "execute", None)):
        raise ConfigError("Released-scope adapter must provide a callable execute()")

    _require_released_attach_inputs(
        session_ref=session_ref,
        expected_auth_state=expected_auth_state,
    )
    _require_released_prepare_inputs(
        target_page_url=target_page_url,
        site_identity=site_identity,
    )

    graph: StateGraph[
        _ReleasedGraphState, None, _ReleasedGraphState, _ReleasedGraphState
    ]
    graph = StateGraph(_ReleasedGraphState)

    def runtime_from_state(state: _ReleasedGraphState) -> RuntimeState:
        runtime = state.get("runtime")
        if not isinstance(runtime, RuntimeState):
            msg = (
                "Released-scope graph state must include RuntimeState under key "
                "'runtime'"
            )
            raise FlowError(msg)
        return runtime

    async def attach_session_node(state: _ReleasedGraphState) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_attach_session_node(
            state=runtime,
            adapter=adapter,
            run=run,
            session_ref=session_ref,
            expected_auth_state=expected_auth_state,
        )
        return {"runtime": runtime}

    async def prepare_session_node(state: _ReleasedGraphState) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_prepare_session_node(
            state=runtime,
            adapter=adapter,
            run=run,
            target_page_url=target_page_url,
            site_identity=site_identity,
        )
        return {"runtime": runtime}

    async def benchmark_validation_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_benchmark_validation_node(
            state=runtime,
            adapter=adapter,
            run=run,
            target_page_url=target_page_url,
        )
        return {"runtime": runtime}

    async def page_ready_observation_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_page_ready_observation_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def sync_observation_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_sync_observation_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def target_actionability_observation_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_target_actionability_observation_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def armed_state_entry_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_armed_state_entry_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def trigger_wait_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_trigger_wait_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def click_dispatch_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_click_dispatch_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def click_completion_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_click_completion_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def success_observation_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_success_observation_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    async def run_completion_node(
        state: _ReleasedGraphState,
    ) -> _ReleasedGraphState:
        runtime = runtime_from_state(state)
        await execute_run_completion_node(
            state=runtime,
            adapter=adapter,
            run=run,
        )
        return {"runtime": runtime}

    graph.add_node("attach_session_node", attach_session_node)
    graph.add_node("prepare_session_node", prepare_session_node)
    graph.add_node("benchmark_validation_node", benchmark_validation_node)
    graph.add_node("page_ready_observation_node", page_ready_observation_node)
    graph.add_node("sync_observation_node", sync_observation_node)
    graph.add_node("target_actionability_observation_node", target_actionability_observation_node)
    graph.add_node("armed_state_entry_node", armed_state_entry_node)
    graph.add_node("trigger_wait_node", trigger_wait_node)
    graph.add_node("click_dispatch_node", click_dispatch_node)
    graph.add_node("click_completion_node", click_completion_node)
    graph.add_node("success_observation_node", success_observation_node)
    graph.add_node("run_completion_node", run_completion_node)

    graph.add_edge(START, "attach_session_node")
    graph.add_edge("attach_session_node", "prepare_session_node")
    graph.add_edge("prepare_session_node", "benchmark_validation_node")
    graph.add_edge("benchmark_validation_node", "page_ready_observation_node")
    graph.add_edge("page_ready_observation_node", "sync_observation_node")
    graph.add_edge("sync_observation_node", "target_actionability_observation_node")
    graph.add_edge("target_actionability_observation_node", "armed_state_entry_node")
    graph.add_edge("armed_state_entry_node", "trigger_wait_node")
    graph.add_edge("trigger_wait_node", "click_dispatch_node")
    graph.add_edge("click_dispatch_node", "click_completion_node")
    graph.add_edge("click_completion_node", "success_observation_node")
    graph.add_edge("success_observation_node", "run_completion_node")
    graph.add_edge("run_completion_node", END)

    return graph.compile()


async def run_released_scope_via_langgraph(
    *,
    adapter: ExecutionAdapter,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
    base_dir: Path,
) -> ReleasedLangGraphRunResult:
    """Run the released-scope mission sequence through LangGraph.

    This is scaffold hardening only.
    """

    _require_released_attach_inputs(
        session_ref=session_ref,
        expected_auth_state=expected_auth_state,
    )
    _require_released_prepare_inputs(
        target_page_url=target_page_url,
        site_identity=site_identity,
    )
    if not isinstance(base_dir, Path):
        raise ConfigError("Released-scope base_dir must be a pathlib.Path")
    run_id = generate_run_id()
    run_root = create_run_root(base_dir=base_dir, run_id=run_id)
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )
    adapter = _bind_adapter_run_root(adapter=adapter, run_root=run_root)
    state = RuntimeState(run_id=run_id)
    state.final_artifact_bundle_ref = str(run_root)

    compiled = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref=session_ref,
        expected_auth_state=expected_auth_state,
        target_page_url=target_page_url,
        site_identity=site_identity,
    )

    output = await compiled.ainvoke({"runtime": state})
    runtime = output.get("runtime")
    if not isinstance(runtime, RuntimeState):
        msg = (
            "Released-scope graph output did not contain RuntimeState under key "
            "'runtime'"
        )
        raise FlowError(msg)

    return ReleasedLangGraphRunResult(state=runtime, run=run)
