from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import cast

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import (
    _ReleasedGraphState,
    build_released_scope_execution_graph,
    run_released_scope_via_langgraph,
)
from ez_ax.graph.released_call_site import ReleasedRunContext
from ez_ax.models.errors import ConfigError, FlowError
from ez_ax.models.runtime import RuntimeState


class FakeExecutionAdapter:
    def __init__(self) -> None:
        self.requests: list[ExecutionRequest] = []

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        self.requests.append(request)
        if request.mission_name == "attach_session":
            return ExecutionResult(
                mission_name="attach_session",
                evidence_refs=(
                    "evidence://text/session-attached",
                    "evidence://text/auth-state-confirmed",
                    "evidence://action-log/attach-session",
                ),
            )
        if request.mission_name == "prepare_session":
            return ExecutionResult(
                mission_name="prepare_session",
                evidence_refs=(
                    "evidence://text/session-viable",
                    "evidence://action-log/prepare-session",
                ),
            )
        if request.mission_name == "benchmark_validation":
            return ExecutionResult(
                mission_name="benchmark_validation",
                evidence_refs=(
                    "evidence://action-log/enter-target-page",
                    "evidence://dom/target-page-entered",
                ),
            )
        if request.mission_name == "page_ready_observation":
            return ExecutionResult(
                mission_name="page_ready_observation",
                evidence_refs=(
                    "evidence://dom/page-shell-ready",
                    "evidence://action-log/page-ready-observed",
                ),
            )
        if request.mission_name == "sync_observation":
            return ExecutionResult(
                mission_name="sync_observation",
                evidence_refs=(
                    "evidence://dom/sync-check",
                    "evidence://action-log/sync-observed",
                ),
            )
        if request.mission_name == "target_actionability_observation":
            return ExecutionResult(
                mission_name="target_actionability_observation",
                evidence_refs=(
                    "evidence://dom/target-actionable",
                    "evidence://action-log/target-actionable-observed",
                ),
            )
        if request.mission_name == "armed_state_entry":
            return ExecutionResult(
                mission_name="armed_state_entry",
                evidence_refs=(
                    "evidence://dom/armed-state",
                    "evidence://action-log/armed-state",
                ),
            )
        if request.mission_name == "trigger_wait":
            return ExecutionResult(
                mission_name="trigger_wait",
                evidence_refs=(
                    "evidence://dom/trigger-fired",
                    "evidence://action-log/trigger-wait-complete",
                ),
            )
        if request.mission_name == "click_dispatch":
            return ExecutionResult(
                mission_name="click_dispatch",
                evidence_refs=(
                    "evidence://dom/click-sent",
                    "evidence://action-log/click-dispatched",
                ),
            )
        if request.mission_name == "click_completion":
            return ExecutionResult(
                mission_name="click_completion",
                evidence_refs=(
                    "evidence://dom/click-done",
                    "evidence://action-log/click-completed",
                ),
            )
        if request.mission_name == "success_observation":
            return ExecutionResult(
                mission_name="success_observation",
                evidence_refs=(
                    "evidence://dom/success",
                    "evidence://action-log/success-observation",
                ),
            )
        if request.mission_name == "run_completion":
            return ExecutionResult(
                mission_name="run_completion",
                evidence_refs=(
                    "evidence://action-log/release-ceiling-stop",
                ),
            )
        raise AssertionError(f"Unexpected mission: {request.mission_name}")


class FakeExecutionAdapterWithRunRoot(FakeExecutionAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.bound_run_root: Path | None = None

    def with_run_root(
        self,
        *,
        run_root: Path,
    ) -> FakeExecutionAdapterWithRunRoot:
        self.bound_run_root = run_root
        return self


class FakeExecutionAdapterWithNonCallableRunRoot(FakeExecutionAdapter):
    with_run_root = "not-callable"


class FakeExecutionAdapterWithBadRunRootReturn(FakeExecutionAdapter):
    def with_run_root(
        self,
        *,
        run_root: Path,  # noqa: ARG002
    ) -> object:
        return object()


@pytest.mark.asyncio
async def test_run_released_scope_via_langgraph_sequences_to_ceiling(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="operator-prepared-session",
        expected_auth_state="authenticated",
        target_page_url="https://tickets.interpark.com/goods/26003199",
        site_identity="interpark",
        base_dir=tmp_path,
    )

    assert result.state.current_mission == "run_completion"
    run_root = Path(result.state.final_artifact_bundle_ref or "")
    assert run_root.exists()

    stop_path = run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    stop_payload = json.loads(stop_path.read_text(encoding="utf-8").splitlines()[0])
    assert stop_payload["event"] == "release-ceiling-stop"
    assert stop_payload["mission_name"] == "run_completion"

    assert [req.mission_name for req in adapter.requests] == [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    ]


@pytest.mark.asyncio
async def test_run_released_scope_via_langgraph_rejects_non_path_base_dir() -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir="not-a-path",  # type: ignore[arg-type]
        )
    except ConfigError as exc:
        assert "base_dir" in str(exc)
    else:
        raise AssertionError("Expected non-Path base_dir to raise ConfigError")


@pytest.mark.asyncio
async def test_run_released_scope_via_langgraph_binds_run_root_when_adapter_supports_it(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapterWithRunRoot()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="operator-prepared-session",
        expected_auth_state="authenticated",
        target_page_url="https://tickets.interpark.com/goods/26003199",
        site_identity="interpark",
        base_dir=tmp_path,
    )

    run_root = Path(result.state.final_artifact_bundle_ref or "")
    assert adapter.bound_run_root == run_root


@pytest.mark.asyncio
async def test_run_released_scope_via_langgraph_rejects_non_callable_with_run_root(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapterWithNonCallableRunRoot()

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "with_run_root" in str(exc)
    else:
        raise AssertionError("Expected non-callable with_run_root to raise ConfigError")

    assert adapter.requests == []


@pytest.mark.asyncio
async def test_run_released_scope_rejects_with_run_root_return_without_execute(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapterWithBadRunRootReturn()

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "return" in str(exc).lower() or "with_run_root" in str(exc)
    else:
        raise AssertionError(
            "Expected invalid with_run_root return to raise ConfigError"
        )

    assert adapter.requests == []


@pytest.mark.asyncio
async def test_released_scope_graph_rejects_missing_runtime_state(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )
    compiled = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="operator-prepared-session",
        expected_auth_state="authenticated",
        target_page_url="https://tickets.interpark.com/goods/26003199",
        site_identity="interpark",
    )

    invalid_state: _ReleasedGraphState = {
        "runtime": cast(RuntimeState, object()),
    }

    with pytest.raises(FlowError) as excinfo:
        await compiled.ainvoke(invalid_state)

    assert "RuntimeState" in str(excinfo.value)
    assert adapter.requests == []


def test_build_released_scope_graph_rejects_whitespace_session_ref(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )

    with pytest.raises(ConfigError) as excinfo:
        build_released_scope_execution_graph(
            adapter=adapter,
            run=run,
            session_ref="  ",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
        )

    assert "session_ref" in str(excinfo.value)


def test_build_released_scope_graph_rejects_non_context_run(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    with pytest.raises(ConfigError) as excinfo:
        build_released_scope_execution_graph(
            adapter=adapter,
            run=object(),  # type: ignore[arg-type]
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
        )

    assert "ReleasedRunContext" in str(excinfo.value)


def test_build_released_scope_graph_rejects_adapter_without_execute(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")

    class NoExecuteAdapter:
        pass

    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )

    with pytest.raises(ConfigError) as excinfo:
        build_released_scope_execution_graph(
            adapter=NoExecuteAdapter(),  # type: ignore[arg-type]
            run=run,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
        )

    assert "execute" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_run_released_scope_via_langgraph_rejects_missing_runtime_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    class FakeCompiled:
        async def ainvoke(
            self,
            _state: dict[str, object],
        ) -> dict[str, object]:
            return {}

    import ez_ax.graph.langgraph_released_execution as mod

    monkeypatch.setattr(
        mod,
        "build_released_scope_execution_graph",
        lambda **_: FakeCompiled(),
    )

    with pytest.raises(FlowError) as excinfo:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )

    assert "graph output" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_released_scope_via_langgraph_rejects_whitespace_session_ref(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="   ",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "session_ref" in str(exc)
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only session_ref to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
async def test_run_released_scope_rejects_whitespace_target_page_url_before_artifacts(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="   ",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "target_page_url" in str(exc)
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only target_page_url to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
async def test_run_released_scope_rejects_whitespace_site_identity_before_artifacts(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="   ",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "site_identity" in str(exc)
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only site_identity to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "expected_label"),
    [
        ({"session_ref": " operator-prepared-session "}, "session_ref"),
        ({"expected_auth_state": " authenticated "}, "expected_auth_state"),
        (
            {"target_page_url": " https://tickets.interpark.com/goods/26003199 "},
            "target_page_url",
        ),
        ({"site_identity": " interpark "}, "site_identity"),
    ],
)
async def test_run_released_scope_rejects_whitespace_wrapped_inputs_before_artifacts(
    tmp_path: Path,
    kwargs: dict[str, str],
    expected_label: str,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    session_ref = kwargs.get("session_ref", "operator-prepared-session")
    expected_auth_state = kwargs.get("expected_auth_state", "authenticated")
    target_page_url = kwargs.get(
        "target_page_url", "https://tickets.interpark.com/goods/26003199"
    )
    site_identity = kwargs.get("site_identity", "interpark")

    try:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref=session_ref,
            expected_auth_state=expected_auth_state,
            target_page_url=target_page_url,
            site_identity=site_identity,
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        message = str(exc)
        assert expected_label in message
        assert "leading or trailing whitespace" in message
    else:
        raise AssertionError("Expected whitespace-wrapped input to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()
