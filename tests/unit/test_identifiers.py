"""Tests for typed identifier parsers (parse-don't-validate boundary)."""

from __future__ import annotations

import pytest

from coord_smith.models.errors import ConfigError
from coord_smith.models.identifiers import (
    parse_expected_auth_state,
    parse_mission_name,
    parse_session_ref,
    parse_site_identity,
    parse_target_page_url,
)

# ---- Happy paths ----------------------------------------------


def test_parse_session_ref_accepts_well_formed_string() -> None:
    assert parse_session_ref("my-session") == "my-session"


def test_parse_expected_auth_state_accepts_well_formed_string() -> None:
    assert parse_expected_auth_state("authenticated") == "authenticated"


def test_parse_target_page_url_accepts_url_string() -> None:
    # Shape-only — no URL syntax parsing performed by the parser.
    assert parse_target_page_url("https://example.com") == "https://example.com"


def test_parse_site_identity_accepts_well_formed_string() -> None:
    assert parse_site_identity("example") == "example"


def test_parse_mission_name_accepts_known_mission() -> None:
    # step_dispatch is one of the 6 released missions (ADR-002).
    assert parse_mission_name("step_dispatch") == "step_dispatch"


# ---- Shape violations -----------------------------------------


@pytest.mark.parametrize(
    "parser",
    [
        parse_session_ref,
        parse_expected_auth_state,
        parse_target_page_url,
        parse_site_identity,
    ],
)
def test_session_like_parsers_reject_non_string(parser: object) -> None:
    with pytest.raises(ConfigError) as exc_info:
        parser(123)  # type: ignore[operator]
    assert "must be a string" in str(exc_info.value)


@pytest.mark.parametrize(
    "parser",
    [
        parse_session_ref,
        parse_expected_auth_state,
        parse_target_page_url,
        parse_site_identity,
    ],
)
def test_session_like_parsers_reject_empty(parser: object) -> None:
    with pytest.raises(ConfigError) as exc_info:
        parser("")  # type: ignore[operator]
    assert "must be non-empty" in str(exc_info.value)


@pytest.mark.parametrize(
    "parser",
    [
        parse_session_ref,
        parse_expected_auth_state,
        parse_target_page_url,
        parse_site_identity,
    ],
)
def test_session_like_parsers_reject_whitespace_only(parser: object) -> None:
    with pytest.raises(ConfigError) as exc_info:
        parser("   ")  # type: ignore[operator]
    assert "whitespace-only" in str(exc_info.value)


@pytest.mark.parametrize(
    "parser",
    [
        parse_session_ref,
        parse_expected_auth_state,
        parse_target_page_url,
        parse_site_identity,
    ],
)
def test_session_like_parsers_reject_leading_trailing_whitespace(
    parser: object,
) -> None:
    with pytest.raises(ConfigError) as exc_info:
        parser(" hello ")  # type: ignore[operator]
    assert "leading or trailing whitespace" in str(exc_info.value)


# ---- Mission name parser specifics ----------------------------


def test_parse_mission_name_rejects_unknown_name() -> None:
    with pytest.raises(ConfigError) as exc_info:
        parse_mission_name("not_a_real_mission")
    msg = str(exc_info.value)
    assert "Unknown mission_name" in msg
    # Error message helps the caller by listing known names.
    assert "step_dispatch" in msg


def test_parse_mission_name_rejects_empty() -> None:
    with pytest.raises(ConfigError):
        parse_mission_name("")
