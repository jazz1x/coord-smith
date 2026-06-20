"""Typed identifier aliases (NewType) + boundary parsers.

`coord-smith` carries several string identifiers across many call
sites: ``mission_name``, ``session_ref``, ``expected_auth_state``,
``target_page_url``, ``site_identity``, plus image template paths
resolved at recipe-load time. Earlier these were all raw ``str``,
with the same shape validations re-run at multiple layers (the ROP
audit flagged this as a parse-don't-validate violation — once a
value is correctly parsed, it should not be re-validated at every
internal boundary).

This module defines:

- ``NewType`` aliases for each identifier kind. ``NewType`` is a
  mypy-only construct: at runtime each alias is the bare ``str``,
  so we pay zero overhead — only type-checked call sites benefit.
- Boundary parsers (``parse_*``) that validate a raw string once
  and return the typed form. Internal call sites consuming the
  parsed identifier annotate it as the ``NewType`` so a caller
  who forgot to parse fails mypy at the boundary, not at runtime.

The validation rules live locally in this module
(``_validate_non_empty_identifier`` and the ``parse_*`` functions); these
parsers are the single place released-scope identifiers are shaped. (The
historical ``langgraph_released_execution._require_released_*_inputs`` helpers
this module once mirrored have since been removed.)

## Why NewType and not Pydantic models?

These are single-string identifiers, not structured records. A
Pydantic model would force every consumer to call
``identifier.value`` to get the underlying string — noisy. NewType
keeps the runtime shape as a plain ``str`` and just refines the
type at static-check time. The "branding" pattern is conventional
in modern Python codebases (e.g. ``UserId = NewType("UserId", int)``).
"""

from __future__ import annotations

from typing import NewType

from coord_smith.missions.names import ALL_MISSIONS
from coord_smith.models.errors import ConfigError

# ---- NewTypes ---------------------------------------------------

MissionName = NewType("MissionName", str)
"""A validated mission name. Always one of ``ALL_MISSIONS``."""

SessionRef = NewType("SessionRef", str)
"""A validated session identifier. Non-empty, stripped of whitespace."""

ExpectedAuthState = NewType("ExpectedAuthState", str)
"""A validated expected-auth-state string. Same shape rules as SessionRef."""

TargetPageUrl = NewType("TargetPageUrl", str)
"""A validated target page URL string. Same shape rules — no URL parsing
done here; the runtime only treats it as an opaque identifier."""

SiteIdentity = NewType("SiteIdentity", str)
"""A validated site identifier. Same shape rules as SessionRef."""

ResolvedImagePath = NewType("ResolvedImagePath", str)
"""An image template path that ``load_click_recipe`` has resolved
against the recipe directory AND existence-checked on disk. The
NewType signals to downstream code (image matching, wait_for,
post_click_signal) that it can use the path directly without
re-checking ``Path(...).exists()``."""


# ---- Boundary parsers -------------------------------------------


def _validate_non_empty_identifier(*, label: str, value: object) -> str:
    """Shared shape check for the four "session-like" identifiers.

    Returns the validated string (unchanged) so callers can flow it
    into the ``NewType`` cast. Raises ``ConfigError`` on shape
    violations — caller maps to CLI exit code 3 (recipe-load /
    config error).
    """
    if not isinstance(value, str):
        raise ConfigError(
            f"Released-scope input '{label}' must be a string, "
            f"got {type(value).__name__}"
        )
    if not value:
        raise ConfigError(
            f"Released-scope input '{label}' must be non-empty"
        )
    if not value.strip():
        raise ConfigError(
            f"Released-scope input '{label}' must not be "
            "whitespace-only"
        )
    if value != value.strip():
        raise ConfigError(
            f"Released-scope input '{label}' must not have leading "
            "or trailing whitespace"
        )
    return value


def parse_mission_name(raw: str) -> MissionName:
    """Parse a raw mission name. Raises ``ConfigError`` if unknown.

    The check is a membership lookup against ``ALL_MISSIONS`` — no
    casing tolerance, no aliases. Mission names are part of the
    public artifact contract (ADR-006); accepting variants would
    let typos leak into ``run.json.run_id`` / failure paths.
    """
    if not isinstance(raw, str) or not raw:
        raise ConfigError(
            f"mission_name must be a non-empty string, got {raw!r}"
        )
    if raw not in ALL_MISSIONS:
        raise ConfigError(
            f"Unknown mission_name: {raw!r} "
            f"(known: {sorted(ALL_MISSIONS)})"
        )
    return MissionName(raw)


def parse_session_ref(raw: object) -> SessionRef:
    """Parse a raw session_ref string. Raises ``ConfigError`` on shape."""
    return SessionRef(
        _validate_non_empty_identifier(label="session_ref", value=raw)
    )


def parse_expected_auth_state(raw: object) -> ExpectedAuthState:
    """Parse a raw expected_auth_state string."""
    return ExpectedAuthState(
        _validate_non_empty_identifier(
            label="expected_auth_state", value=raw
        )
    )


def parse_target_page_url(raw: object) -> TargetPageUrl:
    """Parse a raw target_page_url string.

    Note: only the shape (non-empty, stripped) is checked. We do not
    parse URL syntax — the runtime treats it as an opaque identifier
    that the caller (e.g. OpenClaw) has already validated against
    its own URL rules.
    """
    return TargetPageUrl(
        _validate_non_empty_identifier(
            label="target_page_url", value=raw
        )
    )


def parse_site_identity(raw: object) -> SiteIdentity:
    """Parse a raw site_identity string."""
    return SiteIdentity(
        _validate_non_empty_identifier(label="site_identity", value=raw)
    )
