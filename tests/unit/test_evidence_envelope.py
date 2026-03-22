from typing import get_args

from ez_ax.evidence.envelope import EvidenceKind, parse_released_evidence_ref


def test_evidence_kind_taxonomy_matches_released_evidence_refs_kinds() -> None:
    kinds = set(get_args(EvidenceKind))

    assert "dom" in kinds
    assert "text" in kinds
    assert "clock" in kinds
    assert "action-log" in kinds
    assert "screenshot" in kinds
    assert "coordinate" in kinds

    assert "action_log" not in kinds


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
