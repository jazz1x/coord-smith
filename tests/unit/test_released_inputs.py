from __future__ import annotations

import pytest

from coord_smith.config.released_inputs import resolve_released_scope_inputs


def test_resolve_released_scope_inputs_prefers_cli_args_over_env() -> None:
    result = resolve_released_scope_inputs(
        argv=[
            "--session-ref",
            "cli-session",
            "--expected-auth-state",
            "cli-auth",
            "--target-page-url",
            "https://example.invalid/goods/1",
            "--site-identity",
            "cli-site",
        ],
        env={
            "COORDSMITH_SESSION_REF": "env-session",
            "COORDSMITH_EXPECTED_AUTH_STATE": "env-auth",
            "COORDSMITH_TARGET_PAGE_URL": "https://env.invalid/goods/2",
            "COORDSMITH_SITE_IDENTITY": "env-site",
        },
    )

    assert result.session_ref == "cli-session"
    assert result.expected_auth_state == "cli-auth"
    assert result.target_page_url == "https://example.invalid/goods/1"
    assert result.site_identity == "cli-site"


def test_resolve_released_scope_inputs_falls_back_to_env() -> None:
    result = resolve_released_scope_inputs(
        argv=[],
        env={
            "COORDSMITH_SESSION_REF": "env-session",
            "COORDSMITH_EXPECTED_AUTH_STATE": "env-auth",
            "COORDSMITH_TARGET_PAGE_URL": "https://env.invalid/goods/2",
            "COORDSMITH_SITE_IDENTITY": "env-site",
        },
    )

    assert result.session_ref == "env-session"
    assert result.expected_auth_state == "env-auth"
    assert result.target_page_url == "https://env.invalid/goods/2"
    assert result.site_identity == "env-site"


def test_resolve_released_scope_inputs_rejects_missing_values() -> None:
    try:
        resolve_released_scope_inputs(
            argv=[],
            env={},
        )
    except ValueError as exc:
        message = str(exc)
        assert "Missing:" in message
        assert "session_ref" in message
    else:
        raise AssertionError("Expected missing inputs to be rejected")


def test_resolve_released_scope_inputs_rejects_whitespace_only_values() -> None:
    try:
        resolve_released_scope_inputs(
            argv=["--session-ref", "   "],
            env={
                "COORDSMITH_EXPECTED_AUTH_STATE": "env-auth",
                "COORDSMITH_TARGET_PAGE_URL": "https://env.invalid/goods/2",
                "COORDSMITH_SITE_IDENTITY": "env-site",
            },
        )
    except ValueError as exc:
        message = str(exc)
        assert "session_ref" in message
        assert "whitespace-only" in message
    else:
        raise AssertionError("Expected whitespace-only inputs to be rejected")


def test_resolve_released_scope_inputs_rejects_whitespace_wrapped_values() -> None:
    try:
        resolve_released_scope_inputs(
            argv=["--session-ref", " cli-session "],
            env={
                "COORDSMITH_EXPECTED_AUTH_STATE": "env-auth",
                "COORDSMITH_TARGET_PAGE_URL": "https://env.invalid/goods/2",
                "COORDSMITH_SITE_IDENTITY": "env-site",
            },
        )
    except ValueError as exc:
        message = str(exc)
        assert "session_ref" in message
        assert "leading or trailing whitespace" in message
    else:
        raise AssertionError("Expected whitespace-wrapped inputs to be rejected")


@pytest.mark.parametrize(
    ("argv", "expected_label"),
    [
        (["--expected-auth-state", " auth "], "expected_auth_state"),
        (["--target-page-url", " https://example.invalid/goods/1 "], "target_page_url"),
        (["--site-identity", " interpark "], "site_identity"),
    ],
)
def test_resolve_released_scope_inputs_rejects_whitespace_wrapped_values_for_all_fields(
    argv: list[str], expected_label: str
) -> None:
    try:
        resolve_released_scope_inputs(
            argv=["--session-ref", "cli-session", *argv],
            env={
                "COORDSMITH_EXPECTED_AUTH_STATE": "env-auth",
                "COORDSMITH_TARGET_PAGE_URL": "https://env.invalid/goods/2",
                "COORDSMITH_SITE_IDENTITY": "env-site",
            },
        )
    except ValueError as exc:
        message = str(exc)
        assert expected_label in message
        assert "leading or trailing whitespace" in message
    else:
        raise AssertionError("Expected whitespace-wrapped inputs to be rejected")
