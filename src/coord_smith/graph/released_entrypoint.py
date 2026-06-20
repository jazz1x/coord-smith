"""Released-scope graph entrypoint that sequences missions up to runCompletion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from coord_smith.adapters.execution.client import ExecutionAdapter
from coord_smith.config.click_recipe import Step
from coord_smith.graph.langgraph_released_execution import (
    run_released_scope_via_langgraph,
)
from coord_smith.graph.released_call_site import ReleasedRunContext
from coord_smith.models.identifiers import (
    ExpectedAuthState,
    SessionRef,
    SiteIdentity,
    TargetPageUrl,
)
from coord_smith.models.runtime import RuntimeState


@dataclass(frozen=True, slots=True)
class ReleasedEntrypointResult:
    state: RuntimeState
    run: ReleasedRunContext


async def run_released_scope(
    *,
    adapter: ExecutionAdapter,
    session_ref: SessionRef,
    expected_auth_state: ExpectedAuthState,
    target_page_url: TargetPageUrl,
    site_identity: SiteIdentity,
    base_dir: Path = Path("."),
    recipe_steps: list[Step] | None = None,
    on_run_root_created: Callable[[Path], None] | None = None,
) -> ReleasedEntrypointResult:
    """Run the released-scope mission sequence and stop at runCompletion.

    ``recipe_steps`` enumerates the per-step click sequence to execute
    inside the per-run setup/teardown frame. ``None`` or an empty list
    runs the smoke target (no clicks).

    ``on_run_root_created`` is forwarded to the graph so the run-summary writer
    can claim its own run root the moment it is created.
    """

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref=session_ref,
        expected_auth_state=expected_auth_state,
        target_page_url=target_page_url,
        site_identity=site_identity,
        base_dir=base_dir,
        recipe_steps=recipe_steps,
        on_run_root_created=on_run_root_created,
    )
    return ReleasedEntrypointResult(state=result.state, run=result.run)
