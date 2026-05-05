"""Released-scope input resolution helpers (CLI args then env vars).

This module is a deterministic input resolver used by future user-facing
entrypoints. It does not execute the released workflow by itself.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

ENV_SESSION_REF = "COORDSMITH_SESSION_REF"
ENV_EXPECTED_AUTH_STATE = "COORDSMITH_EXPECTED_AUTH_STATE"
ENV_TARGET_PAGE_URL = "COORDSMITH_TARGET_PAGE_URL"
ENV_SITE_IDENTITY = "COORDSMITH_SITE_IDENTITY"


@dataclass(frozen=True, slots=True)
class ReleasedScopeInputs:
    session_ref: str
    expected_auth_state: str
    target_page_url: str
    site_identity: str


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


def _require_normalized(*, label: str, value: str | None) -> str:
    if value is None:
        msg = (
            "Released-scope inputs are required (CLI args then env vars). Missing: "
            + label
        )
        raise ValueError(msg)
    if not value:
        msg = f"Released-scope input '{label}' must be non-empty"
        raise ValueError(msg)
    if not value.strip():
        msg = f"Released-scope input '{label}' must not be whitespace-only"
        raise ValueError(msg)
    if value != value.strip():
        msg = (
            f"Released-scope input '{label}' must not have leading or trailing "
            "whitespace"
        )
        raise ValueError(msg)
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
    """

    effective_env: Mapping[str, str] = {} if env is None else env
    parsed, _ = _parser().parse_known_args([] if argv is None else list(argv))

    session_ref = _pick_value(
        arg_value=parsed.session_ref, env=effective_env, env_key=ENV_SESSION_REF
    )
    expected_auth_state = _pick_value(
        arg_value=parsed.expected_auth_state,
        env=effective_env,
        env_key=ENV_EXPECTED_AUTH_STATE,
    )
    target_page_url = _pick_value(
        arg_value=parsed.target_page_url,
        env=effective_env,
        env_key=ENV_TARGET_PAGE_URL,
    )
    site_identity = _pick_value(
        arg_value=parsed.site_identity,
        env=effective_env,
        env_key=ENV_SITE_IDENTITY,
    )

    return ReleasedScopeInputs(
        session_ref=_require_normalized(label="session_ref", value=session_ref),
        expected_auth_state=_require_normalized(
            label="expected_auth_state", value=expected_auth_state
        ),
        target_page_url=_require_normalized(
            label="target_page_url", value=target_page_url
        ),
        site_identity=_require_normalized(label="site_identity", value=site_identity),
    )
