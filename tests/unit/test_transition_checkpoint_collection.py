from ez_ax.models.checkpoint import TransitionCheckpointCollection
from ez_ax.models.transition import TransitionArtifact, build_transition_artifact


def test_checkpoint_collection_appends_ordered_transitions() -> None:
    collection = TransitionCheckpointCollection()
    first = build_transition_artifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=True,
        stop_reason="none",
    )
    second = build_transition_artifact(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        allowed=True,
        stop_reason="none",
    )

    updated = collection.append(first).append(second)

    assert len(updated.transitions) == 2
    assert updated.transitions[1].predecessor_mission == "attach_session"
    assert updated.transitions[1].target_mission == "prepare_session"


def test_checkpoint_collection_rejects_first_transition_with_predecessor() -> None:
    collection = TransitionCheckpointCollection()
    first = build_transition_artifact(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        allowed=False,
        stop_reason="missing_predecessor_checkpoint",
    )

    try:
        collection.append(first)
    except ValueError as exc:
        assert "must not declare a predecessor mission" in str(exc)
    else:
        raise AssertionError(
            "Expected predecessor validation error for first transition"
        )


def test_checkpoint_collection_rejects_out_of_order_transition() -> None:
    collection = TransitionCheckpointCollection().append(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    invalid_next = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        allowed=False,
        stop_reason="missing_predecessor_checkpoint",
    )

    try:
        collection.append(invalid_next)
    except ValueError as exc:
        assert "Transition order violation" in str(exc)
    else:
        raise AssertionError("Expected transition order violation")


def test_checkpoint_collection_rejects_duplicate_target_mission() -> None:
    collection = (
        TransitionCheckpointCollection()
        .append(
            build_transition_artifact(
                predecessor_mission=None,
                target_mission="attach_session",
                allowed=True,
                stop_reason="none",
            )
        )
        .append(
            build_transition_artifact(
                predecessor_mission="attach_session",
                target_mission="prepare_session",
                allowed=True,
                stop_reason="none",
            )
        )
    )
    duplicate = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="prepare_session",
        allowed=True,
        stop_reason="none",
    )

    try:
        collection.append(duplicate)
    except ValueError as exc:
        assert "Duplicate mission checkpoint" in str(exc)
    else:
        raise AssertionError("Expected duplicate mission checkpoint rejection")


def test_checkpoint_collection_allows_duplicate_target_for_failed_transition() -> None:
    collection = (
        TransitionCheckpointCollection()
        .append(
            build_transition_artifact(
                predecessor_mission=None,
                target_mission="attach_session",
                allowed=True,
                stop_reason="none",
            )
        )
        .append(
            build_transition_artifact(
                predecessor_mission="attach_session",
                target_mission="prepare_session",
                allowed=True,
                stop_reason="none",
            )
        )
    )
    failed_duplicate = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="prepare_session",
        allowed=False,
        stop_reason="missing_required_evidence",
    )

    updated = collection.append(failed_duplicate)
    assert len(updated.transitions) == 3
    assert updated.transitions[-1].allowed is False


def test_checkpoint_collection_allows_unknown_target_mission_stop_reason() -> None:
    collection = TransitionCheckpointCollection()
    artifact = build_transition_artifact(
        predecessor_mission=None,
        target_mission="not_a_real_mission",
        allowed=False,
        stop_reason="unknown_target_mission",
    )

    updated = collection.append(artifact)
    assert updated.transitions[0].target_mission == "not_a_real_mission"


def test_build_transition_artifact_rejects_non_string_predecessor() -> None:
    try:
        build_transition_artifact(  # type: ignore[arg-type]
            predecessor_mission=123,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    except TypeError as exc:
        assert "predecessor_mission must be a string" in str(exc)
    else:
        raise AssertionError("Expected non-string predecessor_mission to be rejected")


def test_build_transition_artifact_rejects_whitespace_only_predecessor() -> None:
    try:
        build_transition_artifact(
            predecessor_mission="   ",
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError(
            "Expected whitespace-only predecessor_mission to be rejected"
        )


def test_build_transition_artifact_rejects_whitespace_wrapped_target_mission() -> None:
    try:
        build_transition_artifact(
            predecessor_mission=None,
            target_mission=" not_a_real_mission",
            allowed=False,
            stop_reason="unknown_target_mission",
        )
    except ValueError as exc:
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError(
            "Expected whitespace-wrapped target_mission to be rejected"
        )


def test_build_transition_artifact_rejects_empty_target_mission() -> None:
    try:
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="",
            allowed=False,
            stop_reason="unknown_target_mission",
        )
    except ValueError as exc:
        assert "must be non-empty" in str(exc)
    else:
        raise AssertionError("Expected empty target_mission to be rejected")


def test_build_transition_artifact_rejects_whitespace_only_target_mission() -> None:
    try:
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="   ",
            allowed=False,
            stop_reason="unknown_target_mission",
        )
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only target_mission to be rejected")


def test_checkpoint_collection_rejects_unknown_target_mission_without_stop_reason() -> (
    None
):
    collection = TransitionCheckpointCollection()
    artifact = TransitionArtifact(
        predecessor_mission=None,
        target_mission="not_a_real_mission",
        allowed=False,
        stop_reason="missing_required_evidence",
        failure_code="GRAPH_MISSING_REQUIRED_EVIDENCE",
        detail=None,
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "Unknown mission name" in str(exc)
    else:
        raise AssertionError("Expected unknown mission target to be rejected")


def test_build_transition_artifact_rejects_allowed_with_failure_stop_reason() -> None:
    try:
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="missing_required_evidence",
        )
    except ValueError as exc:
        assert "Allowed transition artifacts must use stop_reason" in str(exc)
    else:
        raise AssertionError("Expected allowed=True mismatch to be rejected")


def test_build_transition_artifact_rejects_disallowed_with_none_stop_reason() -> None:
    try:
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=False,
            stop_reason="none",
        )
    except ValueError as exc:
        assert "Disallowed transition artifacts must not use stop_reason" in str(exc)
    else:
        raise AssertionError("Expected allowed=False mismatch to be rejected")


def test_checkpoint_collection_rejects_unknown_predecessor_mission() -> None:
    collection = TransitionCheckpointCollection().append(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    artifact = TransitionArtifact(
        predecessor_mission="not_a_real_mission",
        target_mission="prepare_session",
        allowed=False,
        stop_reason="missing_predecessor_checkpoint",
        failure_code="GRAPH_MISSING_PREDECESSOR_CHECKPOINT",
        detail=None,
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "Unknown mission name" in str(exc)
    else:
        raise AssertionError("Expected unknown predecessor to be rejected")


def test_checkpoint_collection_rejects_missing_predecessor_after_first() -> None:
    collection = TransitionCheckpointCollection().append(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    artifact = build_transition_artifact(
        predecessor_mission=None,
        target_mission="prepare_session",
        allowed=False,
        stop_reason="missing_predecessor_checkpoint",
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "must declare a predecessor" in str(exc)
    else:
        raise AssertionError("Expected missing predecessor to be rejected")


def test_checkpoint_collection_rejects_disallowed_artifact_with_none_stop() -> None:
    collection = TransitionCheckpointCollection()
    artifact = TransitionArtifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=False,
        stop_reason="none",
        failure_code="NONE",
        detail=None,
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "Disallowed transition artifacts must not use stop_reason" in str(exc)
    else:
        raise AssertionError("Expected invariant violation to be rejected")


def test_checkpoint_collection_rejects_allowed_artifact_with_failure_stop() -> None:
    collection = TransitionCheckpointCollection()
    artifact = TransitionArtifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=True,
        stop_reason="missing_required_evidence",
        failure_code="GRAPH_MISSING_REQUIRED_EVIDENCE",
        detail=None,
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "Allowed transition artifacts must use stop_reason" in str(exc)
    else:
        raise AssertionError("Expected invariant violation to be rejected")


def test_checkpoint_collection_rejects_failure_code_mismatch() -> None:
    collection = TransitionCheckpointCollection()
    artifact = TransitionArtifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=False,
        stop_reason="missing_required_evidence",
        failure_code="NONE",
        detail=None,
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "failure_code consistent with stop_reason" in str(exc)
    else:
        raise AssertionError("Expected failure_code mismatch to be rejected")


def test_checkpoint_collection_rejects_allowed_failure_code_mismatch() -> None:
    collection = TransitionCheckpointCollection()
    artifact = TransitionArtifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=True,
        stop_reason="none",
        failure_code="GRAPH_MISSING_REQUIRED_EVIDENCE",
        detail=None,
    )

    try:
        collection.append(artifact)
    except ValueError as exc:
        assert "failure_code consistent with stop_reason" in str(exc)
    else:
        raise AssertionError("Expected failure_code mismatch to be rejected")
