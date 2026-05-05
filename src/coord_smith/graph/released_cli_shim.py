"""Released-scope CLI shim for deterministic input resolution.

This module is intentionally a shim: it resolves released-scope inputs from
CLI args and environment variables, then invokes the released-scope graph
entrypoint using an OpenClaw adapter supplied by the caller/test harness.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from coord_smith.adapters.execution.client import ExecutionAdapter
from coord_smith.config.released_inputs import (
    ReleasedScopeInputs,
    resolve_released_scope_inputs,
)
from coord_smith.graph.released_entrypoint import (
    ReleasedEntrypointResult,
    run_released_scope,
)


def resolve_inputs_for_released_scope(
    *,
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> ReleasedScopeInputs:
    """Resolve released-scope inputs (CLI args then env vars)."""

    return resolve_released_scope_inputs(argv=argv, env=env)


async def run_released_scope_from_argv_env(
    *,
    adapter: ExecutionAdapter,
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    base_dir: Path = Path("."),
) -> ReleasedEntrypointResult:
    """Run the released-scope graph using inputs resolved from argv/env."""

    inputs = resolve_inputs_for_released_scope(argv=argv, env=env)
    return await run_released_scope(
        adapter=adapter,
        session_ref=inputs.session_ref,
        expected_auth_state=inputs.expected_auth_state,
        target_page_url=inputs.target_page_url,
        site_identity=inputs.site_identity,
        base_dir=base_dir,
    )
