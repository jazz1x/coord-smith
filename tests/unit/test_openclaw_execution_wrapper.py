from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.adapters.openclaw.execution import (
    action_log_artifact_path,
    execute_openclaw_within_scope,
    validate_action_log_artifacts_contain_ref_events,
    validate_action_log_artifacts_have_minimum_schema,
    validate_action_log_evidence_refs_resolvable,
    validate_release_ceiling_stop_action_log,
)
from ez_ax.models.errors import ExecutionTransportError, ValidationError


class FakeOpenClawAdapter:
    def __init__(self, *, result: OpenClawExecutionResult) -> None:
        self._result = result
        self.last_request: OpenClawExecutionRequest | None = None

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
        self.last_request = request
        return self._result


def test_action_log_artifact_path_rejects_invalid_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(run_root=tmp_path, key="Not-Kebab")

    assert "kebab-case" in str(excinfo.value)


def test_action_log_artifact_path_rejects_non_string_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(
            run_root=tmp_path,
            key=123,  # type: ignore[arg-type]
        )

    assert "key must be a string" in str(excinfo.value)


def test_action_log_artifact_path_rejects_empty_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(run_root=tmp_path, key="")

    assert "non-empty" in str(excinfo.value)


def test_action_log_artifact_path_rejects_whitespace_wrapped_key(  # noqa: E501
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(run_root=tmp_path, key=" prepare-session")

    assert "leading or trailing whitespace" in str(excinfo.value)


def test_action_log_artifact_path_rejects_whitespace_only_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(run_root=tmp_path, key="   ")

    assert "whitespace-only" in str(excinfo.value)


def test_action_log_artifact_path_rejects_non_path_run_root() -> None:
    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(
            run_root="not-a-path",  # type: ignore[arg-type]
            key="prepare-session",
        )

    assert "pathlib.Path" in str(excinfo.value)


def test_action_log_artifact_path_rejects_run_root_file(tmp_path: Path) -> None:
    run_root = tmp_path / "run-root.txt"
    run_root.write_text("not-a-dir", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(run_root=run_root, key="prepare-session")

    assert "directory" in str(excinfo.value)


def test_action_log_artifact_path_rejects_nonexistent_run_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing-run-root"

    with pytest.raises(ValidationError) as excinfo:
        action_log_artifact_path(run_root=missing, key="prepare-session")

    assert "must exist" in str(excinfo.value)


def test_validate_action_log_artifacts_contain_ref_events_rejects_missing_second_event(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    ref1 = "evidence://action-log/prepare-session"
    ref2 = "evidence://action-log/extra-event"

    artifact1 = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact1.parent.mkdir(parents=True, exist_ok=True)
    artifact1.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    artifact2 = action_log_artifact_path(run_root=run_root, key="extra-event")
    artifact2.parent.mkdir(parents=True, exist_ok=True)
    artifact2.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_contain_ref_events(
            evidence_refs=(ref1, ref2),
            run_root=run_root,
            expected_mission_name="prepare_session",
        )

    assert "extra-event" in str(excinfo.value)


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_resolves_action_log_refs(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result
    assert adapter.last_request is not None
    assert adapter.last_request.mission_name == "prepare_session"


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_accepts_benchmark_validation_action_log(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="enter-target-page")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"benchmark_validation","event":"enter-target-page"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://dom/target-page-entered",
            "evidence://action-log/enter-target-page",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="benchmark_validation",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_accepts_attach_session_action_log(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="attach-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"attach_session","event":"attach-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="attach_session",
        payload={
            "session_ref": "prepared-session",
            "expected_auth_state": "authenticated",
        },
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_mission_mismatch(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"benchmark_validation","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "matching event" in str(exc)
        assert "expected_mission_name='prepare_session'" in str(exc)
    else:
        raise AssertionError("Expected mismatched mission_name to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_missing_action_log_artifact(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "did not resolve" in str(exc)
        assert "prepare-session.jsonl" in str(exc)
    else:
        raise AssertionError("Expected missing action-log artifact to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_missing_minimum_schema(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "schema-valid JSON line" in str(exc)
        assert "prepare-session.jsonl" in str(exc)
    else:
        raise AssertionError("Expected invalid action-log schema to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_empty_action_log_artifact(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("", encoding="utf-8")

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "schema-valid JSON line" in str(exc)
        assert "prepare-session.jsonl" in str(exc)
    else:
        raise AssertionError("Expected empty action-log schema to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_with_non_iso8601_ts(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"not-a-timestamp","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "ISO-8601" in str(exc)
    else:
        raise AssertionError("Expected non-ISO-8601 ts to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_accepts_action_log_with_zulu_ts(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00Z","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_with_non_kebab_event(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"Not-Kebab"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "kebab-case" in str(exc)
    else:
        raise AssertionError("Expected non-kebab-case event to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_with_unknown_mission_name(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"not-a-mission","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "known mission_name" in str(exc)
    else:
        raise AssertionError("Expected unknown mission_name to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_with_whitespace_wrapped_mission_name(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00",'
        '"mission_name":"prepare_session ",'
        '"event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "schema-valid JSON line" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped mission_name to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_with_whitespace_wrapped_event(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00",'
        '"mission_name":"prepare_session",'
        '"event":"prepare-session "}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "schema-valid JSON line" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped event to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_action_log_without_matching_event(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session-other"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "matching event" in str(exc)
        assert "prepare-session" in str(exc)
    else:
        raise AssertionError("Expected missing matching event to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_accepts_action_log_with_eventual_matching_event(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        "\n"
        "not-json\n"
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session-other"}\n'
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_accepts_action_log_with_eventual_valid_line(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        "\n"
        "not-json\n"
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_does_not_require_run_root() -> None:
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_confirms_release_ceiling_stop_from_action_log(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="release-ceiling-stop")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"page_ready_observation","event":"release-ceiling-stop"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="page_ready_observation",
        payload={},
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


def test_release_ceiling_action_log_asserts_fields(tmp_path: Path) -> None:
    artifact = action_log_artifact_path(run_root=tmp_path, key="release-ceiling-stop")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": "2026-03-21T00:00:00+09:00",
        "mission_name": "page_ready_observation",
        "event": "release-ceiling-stop",
    }
    artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    last_line = artifact.read_text(encoding="utf-8").splitlines()[-1]
    data = json.loads(last_line)

    assert data["event"] == "release-ceiling-stop"
    assert data["mission_name"] == "page_ready_observation"
    datetime.fromisoformat(data["ts"])


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_accepts_release_ceiling_stop_with_eventual_confirming_line(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="release-ceiling-stop")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        "\n"
        "not-json\n"
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"page_ready_observation","event":"not-the-marker"}\n'
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"page_ready_observation","event":"release-ceiling-stop"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    observed = await execute_openclaw_within_scope(
        adapter=adapter,
        mission_name="page_ready_observation",
        payload={},
        approved_scope_ceiling="pageReadyObserved",
        run_root=run_root,
    )

    assert observed == result


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_release_ceiling_stop_without_confirming_event(  # noqa: E501
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="release-ceiling-stop")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"page_ready_observation","event":"not-the-marker"}\n',
        encoding="utf-8",
    )

    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    try:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="page_ready_observation",
            payload={},
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )
    except ValidationError as exc:
        assert "did not contain" in str(exc)
        assert "release-ceiling-stop" in str(exc)
    else:
        raise AssertionError("Expected missing confirming event to be rejected")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_wraps_invalid_result_as_typed_validation_error(  # noqa: E501
) -> None:
    adapter = FakeOpenClawAdapter(
        result=OpenClawExecutionResult(mission_name="prepare_session", evidence_refs=())
    )

    with pytest.raises(ValidationError) as excinfo:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
        )

    assert "evidence_refs must be non-empty" in str(excinfo.value)


class FakeInvalidReturnAdapter:
    async def execute(  # noqa: D102
        self, request: OpenClawExecutionRequest
    ) -> object:
        return {
            "mission_name": request.mission_name,
            "evidence_refs": (
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ),
        }


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_non_openclaw_result_type() -> None:
    adapter = FakeInvalidReturnAdapter()

    with pytest.raises(ValidationError) as excinfo:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
        )

    assert "invalid result type" in str(excinfo.value)


class FakeExplodingAdapter:
    async def execute(  # noqa: D102
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_wraps_untyped_adapter_errors() -> None:
    adapter = FakeExplodingAdapter()

    with pytest.raises(ExecutionTransportError) as excinfo:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
        )

    assert "adapter execution failed" in str(excinfo.value)


def test_validate_action_log_artifacts_contain_ref_events_wraps_invalid_ref(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_contain_ref_events(
            evidence_refs=("not-a-ref",),
            run_root=tmp_path,
            expected_mission_name="prepare_session",
        )

    assert "Invalid evidence ref" in str(excinfo.value)


def test_validate_action_log_artifacts_contain_ref_events_ignores_non_action_log_refs(
    tmp_path: Path,
) -> None:
    validate_action_log_artifacts_contain_ref_events(
        evidence_refs=("evidence://dom/page-shell-ready",),
        run_root=tmp_path,
        expected_mission_name="prepare_session",
    )


def test_validate_action_log_artifacts_contain_ref_events_rejects_unknown_expected_mission_name(  # noqa: E501
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_contain_ref_events(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root=tmp_path,
            expected_mission_name="not-a-mission",
        )

    assert "known mission" in str(excinfo.value)


def test_validate_action_log_evidence_refs_resolvable_rejects_non_path_run_root() -> (
    None
):
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_evidence_refs_resolvable(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root="not-a-path",  # type: ignore[arg-type]
        )

    assert "pathlib.Path" in str(excinfo.value)


def test_validate_action_log_evidence_refs_resolvable_rejects_run_root_file(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root.txt"
    run_root.write_text("not-a-dir", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_evidence_refs_resolvable(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root=run_root,
        )

    assert "directory" in str(excinfo.value)


def test_validate_action_log_evidence_refs_resolvable_wraps_invalid_ref(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_evidence_refs_resolvable(
            evidence_refs=("not-a-ref",),
            run_root=tmp_path,
        )

    assert "Invalid evidence ref" in str(excinfo.value)


def test_validate_action_log_evidence_refs_resolvable_ignores_non_action_log_refs(
    tmp_path: Path,
) -> None:
    validate_action_log_evidence_refs_resolvable(
        evidence_refs=("evidence://dom/page-shell-ready",),
        run_root=tmp_path,
    )


def test_validate_action_log_evidence_refs_resolvable_rejects_directory_artifact(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact_dir = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact_dir.mkdir(parents=True)

    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_evidence_refs_resolvable(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root=run_root,
        )

    assert "file artifact" in str(excinfo.value)


def test_validate_action_log_artifacts_have_minimum_schema_rejects_non_path_run_root(  # noqa: E501
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_have_minimum_schema(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root="not-a-path",  # type: ignore[arg-type]
        )

    assert "pathlib.Path" in str(excinfo.value)


def test_validate_action_log_artifacts_have_minimum_schema_rejects_run_root_file(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root.txt"
    run_root.write_text("not-a-dir", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_have_minimum_schema(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root=run_root,
        )

    assert "directory" in str(excinfo.value)


def test_validate_action_log_artifacts_have_minimum_schema_wraps_invalid_ref(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_have_minimum_schema(
            evidence_refs=("not-a-ref",),
            run_root=tmp_path,
        )

    assert "Invalid evidence ref" in str(excinfo.value)


def test_validate_action_log_artifacts_have_minimum_schema_ignores_non_action_log_refs(
    tmp_path: Path,
) -> None:
    validate_action_log_artifacts_have_minimum_schema(
        evidence_refs=("evidence://dom/page-shell-ready",),
        run_root=tmp_path,
    )


def test_validate_action_log_artifacts_have_minimum_schema_rejects_non_string_detail(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    artifact = action_log_artifact_path(run_root=run_root, key="prepare-session")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"prepare_session","event":"prepare-session","detail":{"oops":1}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_have_minimum_schema(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root=run_root,
        )

    assert "schema-valid" in str(excinfo.value)


def test_validate_action_log_artifacts_contain_ref_events_rejects_non_path_run_root(  # noqa: E501
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_contain_ref_events(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root="not-a-path",  # type: ignore[arg-type]
            expected_mission_name="prepare_session",
        )

    assert "pathlib.Path" in str(excinfo.value)


def test_validate_action_log_artifacts_contain_ref_events_rejects_run_root_file(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root.txt"
    run_root.write_text("not-a-dir", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        validate_action_log_artifacts_contain_ref_events(
            evidence_refs=("evidence://action-log/prepare-session",),
            run_root=run_root,
            expected_mission_name="prepare_session",
        )

    assert "directory" in str(excinfo.value)


def test_validate_release_ceiling_stop_action_log_rejects_non_path_run_root() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_release_ceiling_stop_action_log(
            evidence_refs=("evidence://action-log/release-ceiling-stop",),
            run_root="not-a-path",  # type: ignore[arg-type]
        )

    assert "pathlib.Path" in str(excinfo.value)


def test_validate_release_ceiling_stop_action_log_rejects_run_root_file(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root.txt"
    run_root.write_text("not-a-dir", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        validate_release_ceiling_stop_action_log(
            evidence_refs=("evidence://action-log/release-ceiling-stop",),
            run_root=run_root,
        )

    assert "directory" in str(excinfo.value)


def test_validate_release_ceiling_stop_action_log_rejects_missing_artifact(
    tmp_path: Path,
) -> None:
    expected_path = action_log_artifact_path(
        run_root=tmp_path, key="release-ceiling-stop"
    )
    with pytest.raises(ValidationError) as excinfo:
        validate_release_ceiling_stop_action_log(
            evidence_refs=("evidence://action-log/release-ceiling-stop",),
            run_root=tmp_path,
        )

    message = str(excinfo.value)
    assert "Failed to read release ceiling stop action-log artifact" in message
    assert str(expected_path) in message
    assert "prd-openclaw-e2e-validation.md" in message
    assert "prd-openclaw-computer-use-runtime.md" in message
    assert "prd-openclaw-evidence-model.md" in message
    assert "prd-python-validation-contract.md" in message
    assert "event" in message
    assert "mission_name" in message
    assert "ts" in message


def test_validate_release_ceiling_stop_action_log_error_mentions_expected_fields(
    tmp_path: Path,
) -> None:
    expected_path = action_log_artifact_path(
        run_root=tmp_path, key="release-ceiling-stop"
    )
    artifact = expected_path
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"page_ready_observation","event":"not-relevant"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as excinfo:
        validate_release_ceiling_stop_action_log(
            evidence_refs=("evidence://action-log/release-ceiling-stop",),
            run_root=tmp_path,
        )

    message = str(excinfo.value)
    assert "event='release-ceiling-stop'" in message
    assert "mission_name='page_ready_observation'" in message
    assert str(expected_path) in message
    assert "ts" in message
    assert "prd-openclaw-e2e-validation.md" in message
    assert "prd-openclaw-computer-use-runtime.md" in message
    assert "prd-openclaw-evidence-model.md" in message
    assert "prd-python-validation-contract.md" in message


def test_validate_release_ceiling_stop_action_log_read_failure_mentions_docs(
    tmp_path: Path,
) -> None:
    artifact = action_log_artifact_path(run_root=tmp_path, key="release-ceiling-stop")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00+09:00","mission_name":"page_ready_observation","event":"release-ceiling-stop"}\n',
        encoding="utf-8",
    )
    artifact.chmod(0o000)

    try:
        with pytest.raises(ValidationError) as excinfo:
            validate_release_ceiling_stop_action_log(
                evidence_refs=("evidence://action-log/release-ceiling-stop",),
                run_root=tmp_path,
            )
    finally:
        artifact.chmod(0o600)

    message = str(excinfo.value)
    assert "Failed to read release ceiling stop action-log artifact" in message
    assert "prd-openclaw-e2e-validation.md" in message
    assert "prd-openclaw-computer-use-runtime.md" in message
    assert "prd-openclaw-evidence-model.md" in message
    assert "prd-python-validation-contract.md" in message
    assert str(artifact) in message
    assert "event" in message
    assert "mission_name" in message
    assert "ts" in message


def test_validate_release_ceiling_stop_action_log_rejects_nonexistent_run_root(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-run-root"

    with pytest.raises(ValidationError) as excinfo:
        validate_release_ceiling_stop_action_log(
            evidence_refs=("evidence://action-log/release-ceiling-stop",),
            run_root=missing,
        )

    assert "run_root must exist" in str(excinfo.value)


def test_validate_release_ceiling_stop_action_log_accepts_zulu_timestamp(
    tmp_path: Path,
) -> None:
    artifact = action_log_artifact_path(run_root=tmp_path, key="release-ceiling-stop")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"ts":"2026-03-21T00:00:00Z","mission_name":"page_ready_observation","event":"release-ceiling-stop"}\n',
        encoding="utf-8",
    )

    validate_release_ceiling_stop_action_log(
        evidence_refs=("evidence://action-log/release-ceiling-stop",),
        run_root=tmp_path,
    )


def test_validate_release_ceiling_stop_action_log_noops_without_marker() -> None:
    validate_release_ceiling_stop_action_log(
        evidence_refs=("evidence://dom/page-shell-ready",),
        run_root="not-a-path",  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_nonexistent_run_root(
    tmp_path: Path,
) -> None:
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)
    missing = tmp_path / "missing-run-root"

    with pytest.raises(ValidationError) as excinfo:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=missing,
        )

    assert "run_root must exist" in str(excinfo.value)


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_run_root_file(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root.txt"
    run_root.write_text("not-a-dir", encoding="utf-8")

    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    with pytest.raises(ValidationError) as excinfo:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root=run_root,
        )

    assert "run_root must be a directory" in str(excinfo.value)


@pytest.mark.asyncio
async def test_execute_openclaw_within_scope_rejects_non_path_run_root(
    tmp_path: Path,
) -> None:
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeOpenClawAdapter(result=result)

    with pytest.raises(ValidationError) as excinfo:
        await execute_openclaw_within_scope(
            adapter=adapter,
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
            approved_scope_ceiling="pageReadyObserved",
            run_root="not-a-path",  # type: ignore[arg-type]
        )

    assert "pathlib.Path" in str(excinfo.value)
