"""Test that coord-smith normalizes and validates typed evidence.

PRD Purpose section (line 11):
'normalize and validate typed evidence'

This means:
1. Evidence refs must be validated against the released-scope schema
2. Evidence types must be normalized to known types (dom, text, clock, action-log, screenshot, coordinate)
3. Invalid or malformed evidence refs must be rejected
4. Evidence values must be non-empty after normalization (whitespace-trimmed)
"""

from __future__ import annotations

import pytest

from coord_smith.adapters.execution.client import (
    ExecutionResult,
    validate_execution_result,
)
from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.models.errors import ValidationError


def test_normalize_evidence_ref_rejects_empty_ref() -> None:
    """Verify that empty evidence refs are rejected after normalization.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    Empty refs represent invalid evidence.
    """
    try:
        parse_released_evidence_ref("")
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("Empty evidence ref should be rejected")


def test_normalize_evidence_ref_rejects_whitespace_only_ref() -> None:
    """Verify that whitespace-only refs are rejected after normalization.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    After trimming, whitespace-only refs become empty and invalid.
    """
    try:
        parse_released_evidence_ref("   ")
    except ValueError as exc:
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Whitespace-only ref should be rejected")


def test_validate_evidence_ref_enforces_typed_schema() -> None:
    """Verify that evidence refs must match the typed schema.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    Typed evidence requires the format: evidence://<kind>/<key>
    Invalid formats must be rejected.
    """
    invalid_refs = [
        "evidence://unknown-kind/key",  # unknown kind
        "evidence:///missing-kind",  # missing kind
        "untyped-ref",  # no evidence:// prefix
        "evidence://dom",  # missing key
        "evidence:///key",  # missing kind
    ]

    for invalid_ref in invalid_refs:
        try:
            parse_released_evidence_ref(invalid_ref)
        except ValueError as exc:
            assert "released-scope schema" in str(exc) or "Invalid" in str(exc)
        else:
            raise AssertionError(
                f"Invalid evidence ref should be rejected: {invalid_ref}"
            )


def test_normalize_evidence_ref_accepts_valid_typed_refs() -> None:
    """Verify that valid typed evidence refs are accepted.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    Valid released-scope evidence refs must conform to schema.
    """
    valid_refs = [
        "evidence://dom/page-ready",
        "evidence://text/session-active",
        "evidence://clock/time-sync",
        "evidence://action-log/mission-complete",
        "evidence://screenshot/fallback",
        "evidence://coordinate/click-target",
    ]

    for valid_ref in valid_refs:
        kind, key = parse_released_evidence_ref(valid_ref)
        assert kind is not None
        assert key is not None
        assert kind in {"dom", "text", "clock", "action-log", "screenshot", "coordinate"}
        assert key != ""


def test_evidence_validation_rejects_invalid_key_format() -> None:
    """Verify that evidence keys must conform to kebab-case.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    Keys must be properly formatted (kebab-case) to be valid.
    """
    invalid_key_refs = [
        "evidence://dom/not_underscore_case",  # underscore not allowed
        "evidence://dom/NotKebabCase",  # mixed case not allowed
        "evidence://dom/-leading-dash",  # leading dash not allowed
        "evidence://dom/trailing-dash-",  # trailing dash not allowed
    ]

    for invalid_ref in invalid_key_refs:
        try:
            parse_released_evidence_ref(invalid_ref)
        except ValueError as exc:
            assert "released-scope schema" in str(exc) or "kebab" in str(exc).lower()
        else:
            raise AssertionError(f"Invalid key format should be rejected: {invalid_ref}")


def test_evidence_kind_must_be_from_released_types() -> None:
    """Verify that evidence kinds are limited to released types.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    Evidence types must be one of the released types: dom, text, clock,
    action-log, screenshot, coordinate. Future types like vision must be
    rejected in the current released scope.
    """
    # Vision is mentioned in PRD as future-only, not in released scope
    invalid_future_refs = [
        "evidence://vision/modeled-future",
    ]

    for invalid_ref in invalid_future_refs:
        try:
            parse_released_evidence_ref(invalid_ref)
        except ValueError as exc:
            assert "released-scope schema" in str(exc)
        else:
            raise AssertionError(
                f"Future evidence type should be rejected in current scope: {invalid_ref}"
            )


@pytest.mark.asyncio
async def test_evidence_validation_in_adapter_contract() -> None:
    """Verify that OpenClaw adapter contract validates evidence typing.

    PRD Purpose (line 11): 'normalize and validate typed evidence'
    The OpenClaw adapter result validation must enforce typed evidence
    schema for all execution results.
    """
    # Valid evidence refs should be accepted
    valid_result = ExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        ),
    )

    # Should not raise
    validate_execution_result(valid_result)

    # Invalid evidence refs are rejected at construction (__post_init__)
    with pytest.raises(ValidationError, match="invalid ref"):
        ExecutionResult(
            mission_name="attach_session",
            evidence_refs=("not-a-valid-evidence-ref",),
        )
