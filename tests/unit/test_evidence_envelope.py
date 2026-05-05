import tempfile
from pathlib import Path
from typing import get_args

import pytest

from coord_smith.evidence.envelope import (
    EvidenceEnvelope,
    EvidenceKind,
    enforce_evidence_priority,
    enforce_evidence_priority_gate,
    load_action_log_artifact,
    parse_released_evidence_ref,
    validate_release_ceiling_stop_proof,
)


def test_evidence_kind_taxonomy_matches_released_evidence_refs_kinds() -> None:
    kinds = set(get_args(EvidenceKind))

    assert "dom" in kinds
    assert "text" in kinds
    assert "clock" in kinds
    assert "action-log" in kinds
    assert "screenshot" in kinds
    assert "coordinate" in kinds

    assert "action_log" not in kinds


def test_evidence_kind_taxonomy_excludes_future_kind_vision() -> None:
    kinds = set(get_args(EvidenceKind))
    assert (
        "vision" not in kinds
    ), "Vision is mentioned in PRD as fallback-only but not in released scope"


def test_parse_released_evidence_ref_accepts_valid_ref() -> None:
    kind, key = parse_released_evidence_ref(
        "evidence://action-log/release-ceiling-stop"
    )

    assert kind == "action-log"
    assert key == "release-ceiling-stop"


def test_parse_released_evidence_ref_rejects_unknown_kind() -> None:
    try:
        parse_released_evidence_ref("evidence://video/clip")
    except ValueError as exc:
        assert "released-scope schema" in str(exc)
    else:
        raise AssertionError("Expected unknown kind to be rejected")


def test_parse_released_evidence_ref_rejects_whitespace_wrapped_ref() -> None:
    try:
        parse_released_evidence_ref(" evidence://dom/page-shell-ready")
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected whitespace-wrapped ref to be rejected")


def test_parse_released_evidence_ref_accepts_all_released_kinds() -> None:
    refs = (
        "evidence://dom/page-shell-ready",
        "evidence://text/session-viable",
        "evidence://clock/server-time",
        "evidence://action-log/release-ceiling-stop",
        "evidence://screenshot/page-shell-ready-fallback",
        "evidence://coordinate/click-target",
    )

    for ref in refs:
        kind, key = parse_released_evidence_ref(ref)
        assert ref == f"evidence://{kind}/{key}"


def test_parse_released_evidence_ref_rejects_non_kebab_key() -> None:
    bad_refs = (
        "evidence://dom/not_kebab_case",
        "evidence://dom/Not-Kebab",
        "evidence://dom/kebab--double",
        "evidence://dom/-leading-dash",
        "evidence://dom/trailing-dash-",
    )

    for ref in bad_refs:
        try:
            parse_released_evidence_ref(ref)
        except ValueError as exc:
            assert "released-scope schema" in str(exc)
        else:
            raise AssertionError(f"Expected non-kebab key to be rejected: {ref}")


def test_load_action_log_artifact_parses_valid_jsonl() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "action-log.jsonl"
        artifact_path.write_text(
            '{"event": "action", "ts": "2026-03-27T10:00:00Z"}\n'
            '{"event": "observation", "ts": "2026-03-27T10:00:01Z"}\n'
        )
        artifacts = load_action_log_artifact(artifact_path)
        assert len(artifacts) == 2
        assert artifacts[0]["event"] == "action"
        assert artifacts[1]["event"] == "observation"


def test_load_action_log_artifact_rejects_missing_file() -> None:
    missing_path = Path("/nonexistent/artifact.jsonl")
    try:
        load_action_log_artifact(missing_path)
    except FileNotFoundError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("Expected missing file to be rejected")


def test_load_action_log_artifact_rejects_invalid_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "bad.jsonl"
        artifact_path.write_text('{"valid": "json"}\n{invalid json}\n')
        try:
            load_action_log_artifact(artifact_path)
        except ValueError as exc:
            assert "invalid JSON" in str(exc)
        else:
            raise AssertionError("Expected invalid JSON to be rejected")


def test_load_action_log_artifact_rejects_empty_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "empty.jsonl"
        artifact_path.write_text("")
        try:
            load_action_log_artifact(artifact_path)
        except ValueError as exc:
            assert "empty" in str(exc)
        else:
            raise AssertionError("Expected empty file to be rejected")


def test_load_action_log_artifact_rejects_non_dict_lines() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "non-dict.jsonl"
        artifact_path.write_text('"a string"\n')
        try:
            load_action_log_artifact(artifact_path)
        except ValueError as exc:
            assert "not a JSON object" in str(exc)
        else:
            raise AssertionError("Expected non-dict JSON to be rejected")


def test_load_action_log_artifact_accepts_mixed_empty_lines() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "mixed.jsonl"
        artifact_path.write_text(
            '{"event": "action"}\n\n'
            '{"event": "observation"}\n'
            '\n'
        )
        artifacts = load_action_log_artifact(artifact_path)
        assert len(artifacts) == 2


def test_enforce_evidence_priority_returns_highest_priority() -> None:
    refs = {
        "evidence://screenshot/fallback",
        "evidence://dom/primary",
    }
    result = enforce_evidence_priority(refs)
    assert result == "dom"


def test_enforce_evidence_priority_respects_hierarchy() -> None:
    test_cases = [
        ({"evidence://coordinate/click"}, "coordinate"),
        ({"evidence://screenshot/page"}, "screenshot"),
        ({"evidence://action-log/log"}, "action-log"),
        ({"evidence://clock/time"}, "clock"),
        ({"evidence://text/msg"}, "text"),
        ({"evidence://dom/root"}, "dom"),
    ]

    for refs, expected_highest in test_cases:
        result = enforce_evidence_priority(refs)
        assert result == expected_highest


def test_enforce_evidence_priority_with_multiple_high_priority() -> None:
    refs = {
        "evidence://text/msg1",
        "evidence://text/msg2",
        "evidence://clock/time",
    }
    result = enforce_evidence_priority(refs)
    assert result == "text"


def test_enforce_evidence_priority_rejects_empty_refs() -> None:
    try:
        enforce_evidence_priority(set())
    except ValueError as exc:
        assert "must be non-empty" in str(exc)
    else:
        raise AssertionError("Expected empty refs to be rejected")


def test_enforce_evidence_priority_rejects_invalid_refs() -> None:
    try:
        enforce_evidence_priority({"invalid-ref"})
    except ValueError as exc:
        assert "Invalid evidence ref" in str(exc)
    else:
        raise AssertionError("Expected invalid ref to be rejected")


def test_validate_release_ceiling_stop_proof_accepts_valid_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "release-ceiling-stop.jsonl"
        artifact_path.write_text(
            '{"event": "release-ceiling-stop", "mission_name": "run_completion", "ts": "2026-03-27T10:00:00Z"}\n'
        )
        validate_release_ceiling_stop_proof(artifact_path)


def test_validate_release_ceiling_stop_proof_rejects_missing_file() -> None:
    missing_path = Path("/nonexistent/release-ceiling-stop.jsonl")
    try:
        validate_release_ceiling_stop_proof(missing_path)
    except FileNotFoundError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("Expected missing file to be rejected")


def test_validate_release_ceiling_stop_proof_rejects_missing_event_field() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "bad-event.jsonl"
        artifact_path.write_text(
            '{"mission_name": "page_ready_observation", "ts": "2026-03-27T10:00:00Z"}\n'
        )
        try:
            validate_release_ceiling_stop_proof(artifact_path)
        except ValueError as exc:
            assert "missing required entry" in str(exc)
        else:
            raise AssertionError("Expected missing event field to be rejected")


def test_validate_release_ceiling_stop_proof_rejects_wrong_mission() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "wrong-mission.jsonl"
        artifact_path.write_text(
            '{"event": "release-ceiling-stop", "mission_name": "attach_session", "ts": "2026-03-27T10:00:00Z"}\n'
        )
        try:
            validate_release_ceiling_stop_proof(artifact_path)
        except ValueError as exc:
            assert "missing required entry" in str(exc)
        else:
            raise AssertionError("Expected wrong mission to be rejected")


def test_validate_release_ceiling_stop_proof_rejects_missing_timestamp() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "no-ts.jsonl"
        artifact_path.write_text(
            '{"event": "release-ceiling-stop", "mission_name": "run_completion"}\n'
        )
        try:
            validate_release_ceiling_stop_proof(artifact_path)
        except ValueError as exc:
            assert "missing required entry" in str(exc)
        else:
            raise AssertionError("Expected missing timestamp to be rejected")


def test_validate_release_ceiling_stop_proof_accepts_artifact_with_extra_lines() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "with-context.jsonl"
        artifact_path.write_text(
            '{"event": "action", "mission_name": "prepare_session", "ts": "2026-03-27T10:00:00Z"}\n'
            '{"event": "release-ceiling-stop", "mission_name": "run_completion", "ts": "2026-03-27T10:00:01Z"}\n'
        )
        validate_release_ceiling_stop_proof(artifact_path)


def test_evidence_envelope_instantiation_with_primary_evidence() -> None:
    envelope = EvidenceEnvelope(kind="dom", ref="evidence://dom/page-shell-ready", primary=True)
    assert envelope.kind == "dom"
    assert envelope.ref == "evidence://dom/page-shell-ready"
    assert envelope.primary is True


def test_evidence_envelope_instantiation_with_fallback_evidence() -> None:
    envelope = EvidenceEnvelope(
        kind="screenshot", ref="evidence://screenshot/page-shell-ready-fallback", primary=False
    )
    assert envelope.kind == "screenshot"
    assert envelope.ref == "evidence://screenshot/page-shell-ready-fallback"
    assert envelope.primary is False


def test_evidence_envelope_is_frozen() -> None:
    envelope = EvidenceEnvelope(kind="text", ref="evidence://text/session-viable", primary=True)
    try:
        envelope.kind = "dom"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Expected EvidenceEnvelope to be frozen (immutable)")


def test_evidence_envelope_supports_all_evidence_kinds() -> None:
    kinds = get_args(EvidenceKind)
    for kind in kinds:
        envelope = EvidenceEnvelope(
            kind=kind,  # type: ignore[arg-type]
            ref=f"evidence://{kind}/test-key",
            primary=True,
        )
        assert envelope.kind == kind


def test_truth_priority_order_matches_prd_specification() -> None:
    """Verify that EVIDENCE_PRIORITY_ORDER enforces the PRD truth hierarchy.

    PRD Evidence Truth Model (lines 69-83):
    Truth priority:
    1. dom
    2. text
    3. clock
    4. action-log

    Fallback only:
    - screenshot
    - vision (not in released scope)

    Last-resort execution primitive only:
    - coordinate

    This test ensures the EVIDENCE_PRIORITY_ORDER constant is defined correctly
    to enforce this exact ordering for all released-scope decisions.
    """
    from coord_smith.evidence.envelope import EVIDENCE_PRIORITY_ORDER

    # Verify the order matches the PRD specification
    expected_order = ("dom", "text", "clock", "action-log", "screenshot", "coordinate")
    assert (
        EVIDENCE_PRIORITY_ORDER == expected_order
    ), f"EVIDENCE_PRIORITY_ORDER must match PRD specification. Expected {expected_order}, got {EVIDENCE_PRIORITY_ORDER}"

    # Verify primary types come before fallback types
    primary_types = ("dom", "text", "clock", "action-log")
    fallback_types = ("screenshot",)
    last_resort_types = ("coordinate",)

    primary_indices = {kind: EVIDENCE_PRIORITY_ORDER.index(kind) for kind in primary_types}
    fallback_indices = {kind: EVIDENCE_PRIORITY_ORDER.index(kind) for kind in fallback_types}
    last_resort_indices = {
        kind: EVIDENCE_PRIORITY_ORDER.index(kind) for kind in last_resort_types
    }

    # All primary types must come before all fallback types
    max_primary = max(primary_indices.values())
    min_fallback = min(fallback_indices.values())
    assert (
        max_primary < min_fallback
    ), "Primary evidence types must come before fallback types in priority order"

    # All fallback types must come before all last-resort types
    max_fallback = max(fallback_indices.values())
    min_last_resort = min(last_resort_indices.values())
    assert (
        max_fallback < min_last_resort
    ), "Fallback evidence types must come before last-resort types in priority order"

    # Verify the exact ordering of primary types (dom > text > clock > action-log)
    primary_order = [kind for kind in EVIDENCE_PRIORITY_ORDER if kind in primary_types]
    expected_primary_order = list(primary_types)
    assert (
        primary_order == expected_primary_order
    ), f"Primary types must maintain PRD order. Expected {expected_primary_order}, got {primary_order}"


def _make_result(
    mission_name: str, evidence_refs: tuple[str, ...]
) -> object:
    from coord_smith.adapters.execution.client import ExecutionResult
    return ExecutionResult(mission_name=mission_name, evidence_refs=evidence_refs)


def test_enforce_evidence_priority_gate_raises_on_empty_refs() -> None:
    from coord_smith.models.errors import FlowError
    result = _make_result("run_completion", ())
    with pytest.raises(FlowError, match="evidence_refs is empty"):
        enforce_evidence_priority_gate(result)  # type: ignore[arg-type]


def test_enforce_evidence_priority_gate_raises_on_screenshot_only_evidence() -> None:
    from coord_smith.models.errors import FlowError
    result = _make_result(
        "click_dispatch",
        ("evidence://screenshot/click-dispatched-fallback",),
    )
    with pytest.raises(FlowError, match="insufficient"):
        enforce_evidence_priority_gate(result)  # type: ignore[arg-type]


def test_enforce_evidence_priority_gate_raises_on_coordinate_only_evidence() -> None:
    from coord_smith.models.errors import FlowError
    result = _make_result(
        "click_dispatch",
        ("evidence://coordinate/click-target",),
    )
    with pytest.raises(FlowError, match="insufficient"):
        enforce_evidence_priority_gate(result)  # type: ignore[arg-type]


def test_enforce_evidence_priority_gate_passes_on_action_log_evidence() -> None:
    result = _make_result(
        "run_completion",
        ("evidence://action-log/release-ceiling-stop",),
    )
    top_kind = enforce_evidence_priority_gate(result)  # type: ignore[arg-type]
    assert top_kind == "action-log"
