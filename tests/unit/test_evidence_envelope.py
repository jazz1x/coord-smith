from typing import get_args

from coord_smith.evidence.envelope import (
    EvidenceKind,
    enforce_evidence_priority,
    parse_released_evidence_ref,
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
