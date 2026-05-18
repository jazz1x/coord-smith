"""Released-scope LangGraph wiring (scaffold hardening only).

This module wires the released mission sequence into a LangGraph StateGraph
while staying strictly at or below the released ceiling ``runCompletion``.

The graph topology, given an N-step recipe, is::

    START → attach_session → prepare_session
          → (step_observe_0 → step_dispatch_0 → step_capture_0)
          → (step_observe_1 → step_dispatch_1 → step_capture_1)
          → ...
          → (step_observe_{N-1} → step_dispatch_{N-1} → step_capture_{N-1})
          → run_completion → END

With ``N == 0`` (smoke target — no clicks), the per-step block collapses
and ``prepare_session`` connects directly to ``run_completion``.

This module does not provide a real OpenClaw transport implementation.
Tests use a fake adapter to validate wiring deterministically.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast

from coord_smith.adapters.execution.client import ExecutionAdapter
from coord_smith.config.click_recipe import Step
from coord_smith.graph.released_call_site import (
    ReleasedRunContext,
    execute_attach_session_node,
    execute_prepare_session_node,
    execute_run_completion_node,
    execute_step_capture_node,
    execute_step_dispatch_node,
    execute_step_observe_node,
)
from coord_smith.graph.released_run_root import create_run_root, generate_run_id
from coord_smith.models.errors import ConfigError, FlowError
from coord_smith.models.runtime import RuntimeState

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
    recipe_steps: list[Step] | None = None,
) -> CompiledStateGraph[
    _ReleasedGraphState, None, _ReleasedGraphState, _ReleasedGraphState
]:
    """Return a compiled released-scope graph that executes only released nodes.

    ``recipe_steps`` enumerates the per-step click sequence. When ``None`` or
    empty, the per-step loop is skipped (smoke target) and the graph runs
    only the four non-step nodes.
    """

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

    steps: list[Step] = list(recipe_steps) if recipe_steps else []

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

    _step_executors = {
        "observe": execute_step_observe_node,
        "dispatch": execute_step_dispatch_node,
        "capture": execute_step_capture_node,
    }

    def _make_step_node(
        idx: int, step: Step, kind: str
    ) -> Callable[[_ReleasedGraphState], Awaitable[_ReleasedGraphState]]:
        executor = _step_executors[kind]

        async def node(state: _ReleasedGraphState) -> _ReleasedGraphState:
            runtime = runtime_from_state(state)
            await executor(
                state=runtime,
                adapter=adapter,
                run=run,
                step_idx=idx,
                step=step,
            )
            return {"runtime": runtime}

        return node

    graph.add_node("attach_session_node", attach_session_node)
    graph.add_node("prepare_session_node", prepare_session_node)
    for idx, step in enumerate(steps):
        # add_node's overloads are tied to the file's local TypedDict; the
        # factory-produced node has the right runtime shape but mypy cannot
        # see it. Cast through Any for each insertion.
        graph.add_node(
            f"step_observe_{idx}_node",
            cast(Any, _make_step_node(idx, step, "observe")),
        )
        graph.add_node(
            f"step_dispatch_{idx}_node",
            cast(Any, _make_step_node(idx, step, "dispatch")),
        )
        graph.add_node(
            f"step_capture_{idx}_node",
            cast(Any, _make_step_node(idx, step, "capture")),
        )
    graph.add_node("run_completion_node", run_completion_node)

    graph.add_edge(START, "attach_session_node")
    graph.add_edge("attach_session_node", "prepare_session_node")

    if not steps:
        graph.add_edge("prepare_session_node", "run_completion_node")
    else:
        graph.add_edge("prepare_session_node", "step_observe_0_node")
        last_idx = len(steps) - 1
        for idx in range(len(steps)):
            graph.add_edge(
                f"step_observe_{idx}_node", f"step_dispatch_{idx}_node"
            )
            graph.add_edge(
                f"step_dispatch_{idx}_node", f"step_capture_{idx}_node"
            )
            if idx < last_idx:
                graph.add_edge(
                    f"step_capture_{idx}_node", f"step_observe_{idx + 1}_node"
                )
            else:
                graph.add_edge(
                    f"step_capture_{idx}_node", "run_completion_node"
                )

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
    recipe_steps: list[Step] | None = None,
) -> ReleasedLangGraphRunResult:
    """Run the released-scope mission sequence through LangGraph.

    This is scaffold hardening only. ``recipe_steps`` is forwarded to
    ``build_released_scope_execution_graph`` so the graph topology is
    fixed at build time to the exact step count.

    Input validation is delegated to
    :func:`build_released_scope_execution_graph`. We do not pre-validate
    here — that would parse the same strings twice (parse-don't-validate
    violation) and a single source of truth for the input contract is
    easier to evolve.
    """
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
        recipe_steps=recipe_steps,
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
