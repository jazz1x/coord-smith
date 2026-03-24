"""Bootstrap validation helpers for a fresh Python-first repository."""

from dataclasses import dataclass
from pathlib import Path

OPTIONAL_BOOTSTRAP_ASSETS: tuple[str, ...] = ()

REQUIRED_BOOTSTRAP_ASSETS: tuple[str, ...] = (
    "AGENTS.md",
    "docs/prd.md",
    "docs/execution-model.md",
    "docs/current-state.md",
    "docs/llm/repo-autonomous-loop-adapter.yaml",
    "docs/llm/low-attention-execution-contract.json",
    "docs/llm/low-attention-coverage-ledger.json",
    "docs/llm/low-attention-slice-templates.json",
    ".codex/skills/ez-ax-low-attention-autoloop/SKILL.md",
    ".codex/skills/ez-ax-executable-autoloop/SKILL.md",
    "docs/llm/agents/contract-scope-guardian.md",
    "docs/llm/agents/assetization-pattern-promoter.md",
    "docs/codex-global-skills/ez-ax-task-slicer/SKILL.md",
    "docs/codex-global-skills/ez-ax-validation-picker/SKILL.md",
    "docs/codex-global-skills/ez-ax-rag-compactor/SKILL.md",
    "docs/codex-global-skills/ez-ax-released-scope-guard/SKILL.md",
    "scripts/install-codex-global-skills.sh",
    "docs/product/prd-e2e-orchestration.md",
    "docs/product/prd-python-langgraph-runtime.md",
    "docs/product/prd-python-runtime-reset.md",
    "docs/product/prd-runtime-missions.md",
    "docs/product/prd-langgraph-state-model.md",
    "docs/product/prd-python-runtime-layout.md",
    "docs/product/prd-langchain-tooling-policy.md",
    "docs/product/prd-python-validation-contract.md",
    "docs/product/prd-python-rag-operations.md",
    "docs/product/work-rag.json",
    "docs/product/rag.json",
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
