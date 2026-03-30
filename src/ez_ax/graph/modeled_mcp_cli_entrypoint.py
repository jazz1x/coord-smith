"""Modeled-only CLI entrypoint for running released scope via MCP stdio injection.

This entrypoint is explicitly *modeled-only*: it composes existing released-scope
input resolution (argv/env) with MCP stdio constructor config parsing (argv only),
then runs the released-scope mission sequence up to `runCompletion`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ez_ax.graph.modeled_mcp_entrypoint import run_released_scope_via_mcp_stdio_argv_env


@dataclass(frozen=True, slots=True)
class ModeledMcpCliRunSummary:
    run_id: str
    run_root: str
    approved_scope_ceiling: str
    stopped_at_release_ceiling: bool
    recorded_at: str
    summary_path: str


def _summary_artifact_path(*, run_root: Path) -> Path:
    return run_root / "artifacts" / "summary" / "modeled-mcp-run-summary.json"


def _is_iso8601_timestamp(value: str) -> bool:
    if not isinstance(value, str):
        return False
    if not value:
        return False
    if value != value.strip():
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


async def run_modeled_mcp_cli_entrypoint(
    *,
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    base_dir: Path = Path("."),
) -> ModeledMcpCliRunSummary:
    """Run released scope via MCP stdio injection and persist a minimal summary file."""

    result = await run_released_scope_via_mcp_stdio_argv_env(
        argv=argv,
        env={} if env is None else dict(env),
        base_dir=base_dir,
    )

    run_id = result.state.run_id
    run_root = result.run.run_root
    approved_scope_ceiling = result.run.approved_scope_ceiling
    stopped_at_release_ceiling = (
        "evidence://action-log/release-ceiling-stop"
        in result.state.mission_state.evidence_refs
    )

    recorded_at = datetime.now(tz=ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    if not _is_iso8601_timestamp(recorded_at):
        raise AssertionError(  # pragma: no cover
            "recorded_at must be isoformat timestamp"
        )

    summary_path = _summary_artifact_path(run_root=run_root)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "modeled-mcp-cli-run-summary",
        "run_id": run_id,
        "run_root": str(run_root),
        "approved_scope_ceiling": approved_scope_ceiling,
        "stopped_at_release_ceiling": stopped_at_release_ceiling,
        "recorded_at": recorded_at,
    }
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ModeledMcpCliRunSummary(
        run_id=run_id,
        run_root=str(run_root),
        approved_scope_ceiling=approved_scope_ceiling,
        stopped_at_release_ceiling=stopped_at_release_ceiling,
        recorded_at=recorded_at,
        summary_path=str(summary_path),
    )
