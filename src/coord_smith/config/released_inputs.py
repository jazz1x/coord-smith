"""Released-scope input resolution helpers (CLI args then env vars).

This module is a deterministic input resolver used by future user-facing
entrypoints. It does not execute the released workflow by itself.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from coord_smith.models.errors import ConfigError
from coord_smith.models.identifiers import (
    ExpectedAuthState,
    SessionRef,
    SiteIdentity,
    TargetPageUrl,
    parse_expected_auth_state,
    parse_session_ref,
    parse_site_identity,
    parse_target_page_url,
)

ENV_SESSION_REF = "COORDSMITH_SESSION_REF"
ENV_EXPECTED_AUTH_STATE = "COORDSMITH_EXPECTED_AUTH_STATE"
ENV_TARGET_PAGE_URL = "COORDSMITH_TARGET_PAGE_URL"
ENV_SITE_IDENTITY = "COORDSMITH_SITE_IDENTITY"

# Maps each required input's internal label to the CLI flag + env var an
# operator would set, so the "missing input" error names the actual fix
# instead of an internal field name.
_INPUT_REMEDY: dict[str, tuple[str, str]] = {
    "session_ref": ("--session-ref", ENV_SESSION_REF),
    "expected_auth_state": ("--expected-auth-state", ENV_EXPECTED_AUTH_STATE),
    "target_page_url": ("--target-page-url", ENV_TARGET_PAGE_URL),
    "site_identity": ("--site-identity", ENV_SITE_IDENTITY),
}


@dataclass(frozen=True, slots=True)
class ReleasedScopeInputs:
    session_ref: SessionRef
    expected_auth_state: ExpectedAuthState
    target_page_url: TargetPageUrl
    site_identity: SiteIdentity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--session-ref", dest="session_ref")
    parser.add_argument("--expected-auth-state", dest="expected_auth_state")
    parser.add_argument("--target-page-url", dest="target_page_url")
    parser.add_argument("--site-identity", dest="site_identity")
    return parser


def _pick_value(
    *, arg_value: str | None, env: Mapping[str, str], env_key: str
) -> str | None:
    if arg_value is not None:
        return arg_value
    return env.get(env_key)


def _require_present(*, label: str, value: str | None) -> str:
    """Raise ``ConfigError`` when a resolved CLI/env value is absent (None).

    ``ConfigError`` (not a bare ``ValueError``) so the CLI maps a missing
    required input to exit code 3 (recipe/config error) instead of the
    generic exit 1 (runtime). A caller branching on the exit code can then
    distinguish "you invoked me wrong" from "a click failed at runtime". The
    message names the exact flag + env var to set.
    """
    if value is None:
        flag, env_var = _INPUT_REMEDY[label]
        raise ConfigError(
            f"Missing required input '{label}'. "
            f"Pass {flag} or set {env_var}."
        )
    return value


def resolve_released_scope_inputs(
    *,
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> ReleasedScopeInputs:
    """Resolve released-scope inputs using CLI args then env vars.

    Precedence order:
    1) CLI args
    2) environment variables
    3) error

    Each resolved string is run through the canonical boundary parser
    (``parse_*`` from ``models.identifiers``) exactly once. Downstream
    code that accepts ``ReleasedScopeInputs`` can treat the fields as
    already-validated typed identifiers and skip redundant checks.
    """

    effective_env: Mapping[str, str] = {} if env is None else env
    parsed, _ = _parser().parse_known_args([] if argv is None else list(argv))

    raw_session_ref = _pick_value(
        arg_value=parsed.session_ref, env=effective_env, env_key=ENV_SESSION_REF
    )
    raw_expected_auth_state = _pick_value(
        arg_value=parsed.expected_auth_state,
        env=effective_env,
        env_key=ENV_EXPECTED_AUTH_STATE,
    )
    raw_target_page_url = _pick_value(
        arg_value=parsed.target_page_url,
        env=effective_env,
        env_key=ENV_TARGET_PAGE_URL,
    )
    raw_site_identity = _pick_value(
        arg_value=parsed.site_identity,
        env=effective_env,
        env_key=ENV_SITE_IDENTITY,
    )

    return ReleasedScopeInputs(
        session_ref=parse_session_ref(
            _require_present(label="session_ref", value=raw_session_ref)
        ),
        expected_auth_state=parse_expected_auth_state(
            _require_present(label="expected_auth_state", value=raw_expected_auth_state)
        ),
        target_page_url=parse_target_page_url(
            _require_present(label="target_page_url", value=raw_target_page_url)
        ),
        site_identity=parse_site_identity(
            _require_present(label="site_identity", value=raw_site_identity)
        ),
    )
