"""Minimal runtime settings for the bootstrap package."""

from dataclasses import dataclass
from pathlib import Path

from ez_ax.models.runtime import effective_scope_ceiling


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    """Stable bootstrap settings for the Python runtime."""

    project_root: Path
    approved_scope_ceiling: str = "runCompletion"

    def __post_init__(self) -> None:
        """Clamp scope ceiling to the released boundary for bootstrap safety."""

        effective = effective_scope_ceiling(self.approved_scope_ceiling)
        object.__setattr__(self, "approved_scope_ceiling", effective)
