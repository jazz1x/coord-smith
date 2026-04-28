"""Bootstrap validation helpers for a fresh Python-first repository."""

from dataclasses import dataclass
from pathlib import Path

OPTIONAL_BOOTSTRAP_ASSETS: tuple[str, ...] = ()

REQUIRED_BOOTSTRAP_ASSETS: tuple[str, ...] = (
    "CLAUDE.md",
    "docs/prd.md",
    "docs/current-state.md",
    "pyproject.toml",
)


def missing_bootstrap_assets(root: Path) -> list[str]:
    """Return missing required files for a zero-code bootstrap."""

    missing = [path for path in REQUIRED_BOOTSTRAP_ASSETS if not (root / path).exists()]
    return sorted(missing)


@dataclass(frozen=True, slots=True)
class BootstrapAssetStatus:
    missing_required: tuple[str, ...]
    missing_optional: tuple[str, ...]


def bootstrap_asset_status(root: Path) -> BootstrapAssetStatus:
    """Return missing required/optional bootstrap assets for typed evidence."""

    missing_optional = tuple(sorted(path for path in OPTIONAL_BOOTSTRAP_ASSETS))
    return BootstrapAssetStatus(
        missing_required=tuple(missing_bootstrap_assets(root)),
        missing_optional=missing_optional,
    )
