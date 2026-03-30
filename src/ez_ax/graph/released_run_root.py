"""Released-scope run id and run_root helpers owned by the orchestrator/graph."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from ez_ax.models.errors import ConfigError


def generate_run_id(*, now: datetime | None = None) -> str:
    """Generate a stable run id for released-scope artifact paths."""

    if now is None:
        now = datetime.now(tz=ZoneInfo("Asia/Seoul"))
    stamp = now.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid4().hex[:8]}"


def _require_safe_run_id(*, run_id: object) -> str:
    if not isinstance(run_id, str):
        raise ConfigError("Released-scope run_id must be a string")
    if not run_id:
        raise ConfigError("Released-scope run_id must be non-empty")
    if not run_id.strip():
        raise ConfigError("Released-scope run_id must not be whitespace-only")
    if run_id != run_id.strip():
        raise ConfigError(
            "Released-scope run_id must not have leading or trailing whitespace"
        )
    if "\x00" in run_id:
        raise ConfigError("Released-scope run_id must not contain NUL bytes")
    if "/" in run_id or "\\" in run_id:
        raise ConfigError("Released-scope run_id must not contain path separators")
    return run_id


def create_run_root(*, base_dir: Path, run_id: str) -> Path:
    """Create the released-scope run_root at artifacts/runs/{run_id}/ under base_dir."""

    if not isinstance(base_dir, Path):
        raise ConfigError("Released-scope base_dir must be a pathlib.Path")
    run_id = _require_safe_run_id(run_id=run_id)
    if base_dir.exists() and not base_dir.is_dir():
        msg = f"Released-scope base_dir must be a directory: base_dir='{base_dir}'"
        raise ConfigError(msg)
    run_root = base_dir / "artifacts" / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "artifacts" / "action-log").mkdir(parents=True, exist_ok=True)
    return run_root
