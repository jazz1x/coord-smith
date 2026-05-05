"""Released-scope graph entrypoint that sequences missions up to runCompletion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from coord_smith.adapters.execution.client import ExecutionAdapter
from coord_smith.graph.langgraph_released_execution import (
    run_released_scope_via_langgraph,
)
from coord_smith.graph.released_call_site import ReleasedRunContext
from coord_smith.models.runtime import RuntimeState


@dataclass(frozen=True, slots=True)
class ReleasedEntrypointResult:
    state: RuntimeState
    run: ReleasedRunContext


async def run_released_scope(
    *,
    adapter: ExecutionAdapter,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
    base_dir: Path = Path("."),
) -> ReleasedEntrypointResult:
    """Run the released-scope mission sequence and stop at runCompletion."""

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref=session_ref,
        expected_auth_state=expected_auth_state,
        target_page_url=target_page_url,
        site_identity=site_identity,
        base_dir=base_dir,
    )
    return ReleasedEntrypointResult(state=result.state, run=result.run)
