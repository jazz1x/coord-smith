# ruff: noqa: E501

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
    build_openclaw_execution_request,
    build_openclaw_execution_request_within_scope,
    build_openclaw_execution_result,
    build_openclaw_execution_result_within_scope,
    validate_openclaw_execution_request,
    validate_openclaw_execution_request_within_scope,
    validate_openclaw_execution_result,
    validate_openclaw_execution_result_within_scope,
    validate_openclaw_execution_roundtrip_within_scope,
    validate_openclaw_mission_name,
)
from ez_ax.missions.names import mission_is_browser_facing


def test_mission_is_browser_facing_accepts_released_and_modeled() -> None:
    assert mission_is_browser_facing("prepare_session") is True
    assert mission_is_browser_facing("sync_observation") is True


def test_mission_is_browser_facing_rejects_control_mission() -> None:
    assert mission_is_browser_facing("python_validation_execution") is False


def test_validate_openclaw_mission_name_rejects_control_mission() -> None:
    try:
        validate_openclaw_mission_name("python_validation_execution")
    except ValueError as exc:
        assert "not browser-facing" in str(exc)
    else:
        raise AssertionError("Expected control mission to be rejected")


def test_validate_openclaw_mission_name_rejects_non_string() -> None:
    try:
        validate_openclaw_mission_name(123)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "must be a string" in str(exc)
    else:
        raise AssertionError("Expected non-string mission_name to be rejected")


def test_validate_openclaw_mission_name_rejects_whitespace_wrapped() -> None:
    try:
        validate_openclaw_mission_name(" prepare_session")
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped mission_name to be rejected")


def test_validate_openclaw_mission_name_rejects_empty_string() -> None:
    try:
        validate_openclaw_mission_name("")
    except ValueError as exc:
        assert "must be non-empty" in str(exc)
    else:
        raise AssertionError("Expected empty mission_name to be rejected")


def test_validate_openclaw_mission_name_rejects_whitespace_only() -> None:
    try:
        validate_openclaw_mission_name("   ")
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only mission_name to be rejected")


def test_validate_openclaw_execution_request_rejects_non_dict_payload() -> None:
    request = OpenClawExecutionRequest(  # type: ignore[arg-type]
        mission_name="prepare_session", payload="not-a-dict"
    )

    try:
        validate_openclaw_execution_request(request)
    except TypeError as exc:
        assert "payload must be a dict" in str(exc)
    else:
        raise AssertionError("Expected payload type to be rejected")


def test_validate_openclaw_execution_request_rejects_whitespace_wrapped_mission_name() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name=" prepare_session", payload={"ready": True}
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped mission_name to be rejected")


def test_validate_openclaw_execution_request_accepts_empty_payload() -> None:
    request = OpenClawExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    validate_openclaw_execution_request(request)


def test_validate_openclaw_execution_request_rejects_attach_session_missing_required_payload() -> (
    None
):
    request = OpenClawExecutionRequest(mission_name="attach_session", payload={})

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "missing required key" in str(exc)
        assert "session_ref" in str(exc)
    else:
        raise AssertionError("Expected missing required key to be rejected")


def test_validate_openclaw_execution_request_rejects_attach_session_missing_expected_auth_state() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="attach_session",
        payload={"session_ref": "operator-prepared-session"},
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "missing required key" in str(exc)
        assert "expected_auth_state" in str(exc)
    else:
        raise AssertionError("Expected missing required key to be rejected")


def test_validate_openclaw_execution_request_rejects_attach_session_whitespace_session_ref() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="attach_session",
        payload={
            "session_ref": "   ",
            "expected_auth_state": "authenticated",
        },
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
        assert "session_ref" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only session_ref to be rejected")


def test_validate_openclaw_execution_request_rejects_attach_session_whitespace_wrapped_expected_auth_state() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="attach_session",
        payload={
            "session_ref": "operator-prepared-session",
            "expected_auth_state": " authenticated ",
        },
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
        assert "expected_auth_state" in str(exc)
    else:
        raise AssertionError(
            "Expected whitespace-wrapped expected_auth_state to be rejected"
        )


def test_validate_openclaw_execution_request_rejects_prepare_session_missing_required_payload() -> (
    None
):
    request = OpenClawExecutionRequest(mission_name="prepare_session", payload={})

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "missing required key" in str(exc)
        assert "target_page_url" in str(exc)
    else:
        raise AssertionError("Expected missing required key to be rejected")


def test_validate_openclaw_execution_request_rejects_prepare_session_missing_site_identity() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="prepare_session",
        payload={"target_page_url": "https://tickets.interpark.com/goods/26003199"},
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "missing required key" in str(exc)
        assert "site_identity" in str(exc)
    else:
        raise AssertionError("Expected missing required key to be rejected")


def test_validate_openclaw_execution_request_rejects_prepare_session_non_string_site_identity() -> (
    None
):
    request = OpenClawExecutionRequest(  # type: ignore[arg-type]
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": True,
        },
    )

    try:
        validate_openclaw_execution_request(request)
    except TypeError as exc:
        assert "must be a string" in str(exc)
        assert "site_identity" in str(exc)
    else:
        raise AssertionError("Expected non-string payload value to be rejected")


def test_validate_openclaw_execution_request_rejects_prepare_session_whitespace_site_identity() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "   ",
        },
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
        assert "site_identity" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only payload value to be rejected")


def test_validate_openclaw_execution_request_rejects_benchmark_validation_missing_target_page_url() -> (
    None
):
    request = OpenClawExecutionRequest(mission_name="benchmark_validation", payload={})

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "missing required key" in str(exc)
        assert "target_page_url" in str(exc)
    else:
        raise AssertionError("Expected missing required key to be rejected")


def test_validate_openclaw_execution_request_rejects_benchmark_validation_whitespace_target_page_url() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="benchmark_validation",
        payload={"target_page_url": "   "},
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
        assert "target_page_url" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only payload value to be rejected")


def test_validate_openclaw_execution_request_rejects_non_string_payload_key() -> None:
    request = OpenClawExecutionRequest(  # type: ignore[arg-type]
        mission_name="prepare_session", payload={1: "value"}
    )

    try:
        validate_openclaw_execution_request(request)
    except TypeError as exc:
        assert "payload keys must be strings" in str(exc)
    else:
        raise AssertionError("Expected payload key type to be rejected")


def test_validate_openclaw_execution_request_rejects_empty_payload_key() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session", payload={"": "value"}
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "payload keys must be non-empty" in str(exc)
    else:
        raise AssertionError("Expected empty payload key to be rejected")


def test_validate_openclaw_execution_request_rejects_whitespace_only_payload_key() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="prepare_session", payload={"   ": "value"}
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only payload key to be rejected")


def test_validate_openclaw_execution_request_rejects_whitespace_wrapped_payload_key() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="prepare_session", payload={" ready": True}
    )

    try:
        validate_openclaw_execution_request(request)
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped payload key to be rejected")


def test_validate_openclaw_execution_request_rejects_non_json_payload_value() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session", payload={"bad": object()}
    )

    try:
        validate_openclaw_execution_request(request)
    except TypeError as exc:
        assert "JSON-serializable" in str(exc)
    else:
        raise AssertionError("Expected non-JSON payload to be rejected")


def test_validate_openclaw_execution_request_rejects_non_json_float_values() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session", payload={"bad": float("nan")}
    )

    try:
        validate_openclaw_execution_request(request)
    except TypeError as exc:
        assert "JSON-serializable" in str(exc)
    else:
        raise AssertionError("Expected non-JSON float payload to be rejected")


def test_validate_openclaw_execution_request_rejects_infinite_float_values() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session", payload={"bad": float("inf")}
    )

    try:
        validate_openclaw_execution_request(request)
    except TypeError as exc:
        assert "JSON-serializable" in str(exc)
    else:
        raise AssertionError("Expected infinite float payload to be rejected")


def test_build_openclaw_execution_request_returns_request() -> None:
    request = build_openclaw_execution_request(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )

    assert request.mission_name == "prepare_session"
    assert request.payload["site_identity"] == "interpark"


def test_build_openclaw_execution_request_within_scope_returns_request() -> None:
    request = build_openclaw_execution_request_within_scope(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
        approved_scope_ceiling="pageReadyObserved",
    )

    assert request.mission_name == "prepare_session"
    assert request.payload["site_identity"] == "interpark"


def test_build_openclaw_execution_result_returns_result() -> None:
    result = build_openclaw_execution_result(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )

    assert result.mission_name == "prepare_session"
    assert result.evidence_refs == (
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    )


def test_build_openclaw_execution_result_within_scope_returns_result() -> None:
    result = build_openclaw_execution_result_within_scope(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
        approved_scope_ceiling="pageReadyObserved",
    )

    assert result.mission_name == "prepare_session"
    assert result.evidence_refs == (
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    )


def test_build_openclaw_execution_result_within_scope_rejects_modeled() -> None:
    try:
        build_openclaw_execution_result_within_scope(
            mission_name="sync_observation",
            evidence_refs=("evidence://clock/server-time",),
            approved_scope_ceiling="pageReadyObserved",
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
    else:
        raise AssertionError("Expected modeled mission to be rejected under ceiling")


def test_build_openclaw_request_within_scope_rejects_control_mission() -> None:
    try:
        build_openclaw_execution_request_within_scope(
            mission_name="python_validation_execution",
            payload={"ready": True},
            approved_scope_ceiling="pageReadyObserved",
        )
    except ValueError as exc:
        assert "not browser-facing" in str(exc)
    else:
        raise AssertionError("Expected control mission to be rejected")


def test_build_openclaw_request_within_scope_rejects_modeled_mission() -> None:
    try:
        build_openclaw_execution_request_within_scope(
            mission_name="sync_observation",
            payload={"target_page_url": "https://tickets.interpark.com/goods/26003199"},
            approved_scope_ceiling="pageReadyObserved",
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
    else:
        raise AssertionError("Expected modeled mission to be rejected under ceiling")


def test_build_openclaw_request_within_scope_rejects_modeled_unknown_ceiling() -> None:
    try:
        build_openclaw_execution_request_within_scope(
            mission_name="sync_observation",
            payload={"target_page_url": "https://tickets.interpark.com/goods/26003199"},
            approved_scope_ceiling="syncEstablished",
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
    else:
        raise AssertionError(
            "Expected modeled mission to be rejected under unknown ceiling"
        )


def test_build_openclaw_request_within_scope_rejects_unknown_mission() -> None:
    try:
        build_openclaw_execution_request_within_scope(
            mission_name="not_a_real_mission",
            payload={"ready": True},
            approved_scope_ceiling="pageReadyObserved",
        )
    except ValueError as exc:
        assert "Unknown mission name" in str(exc)
    else:
        raise AssertionError("Expected unknown mission to be rejected")


def test_validate_openclaw_request_within_scope_accepts_released_mission() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )

    validate_openclaw_execution_request_within_scope(
        request, approved_scope_ceiling="pageReadyObserved"
    )


def test_validate_openclaw_request_within_scope_accepts_attach_under_prepare_session_ceiling() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="attach_session",
        payload={
            "session_ref": "operator-prepared-session",
            "expected_auth_state": "authenticated",
        },
    )

    validate_openclaw_execution_request_within_scope(
        request, approved_scope_ceiling="prepareSession"
    )


def test_validate_openclaw_request_within_scope_accepts_prepare_session_under_prepare_session_ceiling() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )

    validate_openclaw_execution_request_within_scope(
        request, approved_scope_ceiling="prepareSession"
    )


def test_validate_openclaw_request_within_scope_rejects_benchmark_validation_under_prepare_session_ceiling() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="benchmark_validation",
        payload={"target_page_url": "https://tickets.interpark.com/goods/26003199"},
    )

    try:
        validate_openclaw_execution_request_within_scope(
            request, approved_scope_ceiling="prepareSession"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "'prepareSession'" in str(exc)
    else:
        raise AssertionError("Expected benchmark mission to be rejected under ceiling")


def test_validate_openclaw_request_within_scope_rejects_page_ready_under_prepare_session_ceiling() -> (
    None
):
    request = OpenClawExecutionRequest(
        mission_name="page_ready_observation", payload={"ready": True}
    )

    try:
        validate_openclaw_execution_request_within_scope(
            request, approved_scope_ceiling="prepareSession"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "'prepareSession'" in str(exc)
    else:
        raise AssertionError("Expected page-ready mission to be rejected under ceiling")


def test_validate_openclaw_request_within_scope_rejects_modeled_mission() -> None:
    request = OpenClawExecutionRequest(
        mission_name="sync_observation",
        payload={"target_page_url": "https://tickets.interpark.com/goods/26003199"},
    )

    try:
        validate_openclaw_execution_request_within_scope(
            request, approved_scope_ceiling="pageReadyObserved"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "defaulted to 'pageReadyObserved'" not in str(exc)
    else:
        raise AssertionError("Expected modeled mission to be rejected under ceiling")


def test_openclaw_request_within_scope_rejects_modeled_unknown_ceiling() -> None:
    request = OpenClawExecutionRequest(
        mission_name="sync_observation",
        payload={"target_page_url": "https://tickets.interpark.com/goods/26003199"},
    )

    try:
        validate_openclaw_execution_request_within_scope(
            request, approved_scope_ceiling="syncEstablished"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "defaulted to 'pageReadyObserved'" in str(exc)
    else:
        raise AssertionError(
            "Expected modeled mission to be rejected under unknown ceiling"
        )


def test_validate_openclaw_execution_result_accepts_tuple_refs() -> None:
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_primary_minimum_with_optional_extras() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
            "evidence://clock/server-time",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_rejects_non_schema_ref() -> None:
    result = OpenClawExecutionResult(
        mission_name="attach_session", evidence_refs=("evidence://text/not_kebab_case",)
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "released-scope schema" in str(exc)
        assert "not_kebab_case" in str(exc)
    else:
        raise AssertionError("Expected evidence ref schema violation to be rejected")


def test_validate_openclaw_execution_result_rejects_prepare_session_missing_minimum_keys() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=("evidence://text/session-viable",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "missing required minimum keys" in str(exc)
        assert "primary missing" in str(exc)
        assert "action-log/prepare-session" in str(exc)
    else:
        raise AssertionError("Expected missing minimum evidence keys to be rejected")


def test_validate_openclaw_execution_result_accepts_prepare_session_fallback_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://screenshot/prepare-session-fallback",
            "evidence://text/fallback-reason",
            "evidence://action-log/prepare-session",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_benchmark_validation_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_benchmark_validation_minimum_with_optional_extras() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
            "evidence://clock/server-time",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_benchmark_validation_fallback_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://action-log/enter-target-page",
            "evidence://screenshot/target-page-entered-fallback",
            "evidence://text/fallback-reason",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_page_ready_primary_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_page_ready_minimum_with_optional_extras() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
            "evidence://clock/server-time",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_accepts_page_ready_fallback_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://screenshot/page-shell-ready-fallback",
            "evidence://text/fallback-reason",
            "evidence://action-log/release-ceiling-stop",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_rejects_unknown_evidence_ref_kind() -> None:
    result = OpenClawExecutionResult(
        mission_name="attach_session", evidence_refs=("evidence://video/clip",)
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "released-scope schema" in str(exc)
    else:
        raise AssertionError("Expected unknown evidence ref kind to be rejected")


def test_validate_openclaw_execution_result_accepts_attach_session_primary_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_rejects_attach_session_missing_minimum_keys() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=("evidence://action-log/attach-session",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "missing required minimum keys" in str(exc)
        assert "attach_session" in str(exc)
    else:
        raise AssertionError("Expected missing minimum evidence to be rejected")


def test_validate_openclaw_execution_result_accepts_attach_session_fallback_minimum() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://screenshot/attach-session-fallback",
            "evidence://text/fallback-reason",
            "evidence://action-log/attach-session",
        ),
    )

    validate_openclaw_execution_result(result)


def test_validate_openclaw_execution_result_rejects_page_ready_missing_stop_confirmation() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=("evidence://dom/page-shell-ready",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "missing required minimum keys" in str(exc)
    else:
        raise AssertionError(
            "Expected missing stop-confirmation evidence to be rejected"
        )


def test_validate_openclaw_result_within_scope_rejects_benchmark_validation_under_prepare_session_ceiling() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
        ),
    )

    try:
        validate_openclaw_execution_result_within_scope(
            result, approved_scope_ceiling="prepareSession"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "'prepareSession'" in str(exc)
    else:
        raise AssertionError("Expected benchmark result to be rejected under ceiling")


def test_validate_openclaw_result_within_scope_rejects_page_ready_under_prepare_session_ceiling() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        ),
    )

    try:
        validate_openclaw_execution_result_within_scope(
            result, approved_scope_ceiling="prepareSession"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "'prepareSession'" in str(exc)
    else:
        raise AssertionError("Expected page-ready result to be rejected under ceiling")


def test_validate_openclaw_execution_result_rejects_non_tuple_refs() -> None:
    result = OpenClawExecutionResult(  # type: ignore[arg-type]
        mission_name="attach_session", evidence_refs=["not-a-tuple"]
    )

    try:
        validate_openclaw_execution_result(result)
    except TypeError as exc:
        assert "evidence_refs must be a tuple" in str(exc)
    else:
        raise AssertionError("Expected evidence_refs type to be rejected")


def test_validate_openclaw_execution_result_rejects_non_string_mission_name() -> None:
    result = OpenClawExecutionResult(  # type: ignore[arg-type]
        mission_name=123, evidence_refs=("evidence://text/session-viable",)
    )

    try:
        validate_openclaw_execution_result(result)
    except TypeError as exc:
        assert "mission_name must be a string" in str(exc)
    else:
        raise AssertionError("Expected non-string mission_name to be rejected")


def test_validate_openclaw_execution_result_rejects_whitespace_wrapped_mission_name() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name=" prepare_session",
        evidence_refs=("evidence://text/session-viable",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped mission_name to be rejected")


def test_validate_openclaw_execution_result_rejects_empty_refs() -> None:
    result = OpenClawExecutionResult(mission_name="attach_session", evidence_refs=())

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "must be non-empty" in str(exc)
    else:
        raise AssertionError("Expected empty evidence refs to be rejected")


def test_validate_openclaw_execution_result_rejects_duplicate_refs() -> None:
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://text/session-viable",
        ),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "entries must be unique" in str(exc)
    else:
        raise AssertionError("Expected duplicate evidence refs to be rejected")


def test_validate_openclaw_execution_result_rejects_screenshot_only() -> None:
    """Verify PRD clause: truth must not be derived from vision alone."""
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=("evidence://screenshot/page-shell-ready-fallback",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "missing required minimum keys" in str(exc)
    else:
        raise AssertionError(
            "Expected screenshot-only evidence to be rejected per PRD "
            "truth-must-not-be-vision-alone clause"
        )


def test_validate_openclaw_execution_result_rejects_coordinate_only() -> None:
    """Verify PRD clause: truth must not be derived from coordinates alone."""
    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=("evidence://coordinate/click-location",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "missing required minimum keys" in str(exc)
    else:
        raise AssertionError(
            "Expected coordinate-only evidence to be rejected per PRD "
            "truth-must-not-be-coordinate-alone clause"
        )


def test_validate_openclaw_execution_result_rejects_screenshot_and_coordinate_only() -> (
    None
):
    """Verify PRD clause: truth must not be derived from vision or coordinates alone."""
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://screenshot/prepare-session-fallback",
            "evidence://coordinate/click-location",
        ),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "missing required minimum keys" in str(exc)
    else:
        raise AssertionError(
            "Expected screenshot+coordinate-only evidence to be rejected per PRD "
            "truth-must-not-be-vision-or-coordinate-alone clause"
        )


def test_validate_openclaw_execution_result_rejects_empty_ref() -> None:
    result = OpenClawExecutionResult(mission_name="attach_session", evidence_refs=("",))

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "must be non-empty" in str(exc)
    else:
        raise AssertionError("Expected empty evidence ref to be rejected")


def test_validate_openclaw_execution_result_rejects_whitespace_only_ref() -> None:
    result = OpenClawExecutionResult(
        mission_name="attach_session", evidence_refs=("   ",)
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only evidence ref to be rejected")


def test_validate_openclaw_execution_result_rejects_whitespace_wrapped_ref() -> None:
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(" evidence://text/session-viable",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped evidence ref to be rejected")


def test_validate_openclaw_execution_result_rejects_non_string_ref() -> None:
    result = OpenClawExecutionResult(  # type: ignore[arg-type]
        mission_name="attach_session", evidence_refs=(123,)
    )

    try:
        validate_openclaw_execution_result(result)
    except TypeError as exc:
        assert "entries must be strings" in str(exc)
    else:
        raise AssertionError("Expected non-string evidence ref to be rejected")


def test_validate_openclaw_execution_result_rejects_unhashable_ref() -> None:
    result = OpenClawExecutionResult(  # type: ignore[arg-type]
        mission_name="attach_session", evidence_refs=({},)
    )

    try:
        validate_openclaw_execution_result(result)
    except TypeError as exc:
        assert "entries must be strings" in str(exc)
    else:
        raise AssertionError("Expected unhashable evidence ref to be rejected")


def test_validate_openclaw_execution_result_rejects_non_browser_mission() -> None:
    result = OpenClawExecutionResult(
        mission_name="python_validation_execution",
        evidence_refs=("evidence://text/session-viable",),
    )

    try:
        validate_openclaw_execution_result(result)
    except ValueError as exc:
        assert "not browser-facing" in str(exc)
    else:
        raise AssertionError("Expected non-browser-facing mission to be rejected")


def test_validate_openclaw_execution_result_within_scope_accepts_released() -> None:
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )

    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling="pageReadyObserved"
    )


def test_validate_openclaw_execution_result_within_scope_accepts_benchmark_validation_under_page_ready_ceiling() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
        ),
    )

    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling="pageReadyObserved"
    )


def test_validate_openclaw_execution_result_within_scope_accepts_page_ready_under_page_ready_ceiling() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        ),
    )

    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling="pageReadyObserved"
    )


def test_validate_openclaw_execution_result_within_scope_accepts_prepare_session_under_prepare_session_ceiling() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )

    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling="prepareSession"
    )


def test_validate_openclaw_execution_result_within_scope_accepts_attach_under_prepare_session_ceiling() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        ),
    )

    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling="prepareSession"
    )


def test_validate_openclaw_execution_result_within_scope_rejects_modeled() -> None:
    result = OpenClawExecutionResult(
        mission_name="sync_observation", evidence_refs=("evidence://clock/server-time",)
    )

    try:
        validate_openclaw_execution_result_within_scope(
            result, approved_scope_ceiling="pageReadyObserved"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "defaulted to 'pageReadyObserved'" not in str(exc)
    else:
        raise AssertionError("Expected modeled mission to be rejected under ceiling")


def test_validate_openclaw_execution_result_within_scope_unknown_ceiling_defaults() -> (
    None
):
    result = OpenClawExecutionResult(
        mission_name="sync_observation", evidence_refs=("evidence://clock/server-time",)
    )

    try:
        validate_openclaw_execution_result_within_scope(
            result, approved_scope_ceiling="syncEstablished"
        )
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "defaulted to 'pageReadyObserved'" in str(exc)
    else:
        raise AssertionError(
            "Expected modeled mission to be rejected under unknown ceiling"
        )


def test_validate_openclaw_roundtrip_within_scope_accepts_matching_mission() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )
    result = OpenClawExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )

    validate_openclaw_execution_roundtrip_within_scope(
        request=request,
        result=result,
        approved_scope_ceiling="pageReadyObserved",
    )


def test_validate_openclaw_roundtrip_within_scope_rejects_mission_mismatch() -> None:
    request = OpenClawExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        ),
    )

    try:
        validate_openclaw_execution_roundtrip_within_scope(
            request=request,
            result=result,
            approved_scope_ceiling="pageReadyObserved",
        )
    except ValueError as exc:
        assert "must match request mission_name" in str(exc)
    else:
        raise AssertionError("Expected mission mismatch to be rejected")
