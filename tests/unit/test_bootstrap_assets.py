from pathlib import Path

from ez_ax.validation.bootstrap import (
    OPTIONAL_BOOTSTRAP_ASSETS,
    REQUIRED_BOOTSTRAP_ASSETS,
    BootstrapAssetStatus,
    bootstrap_asset_status,
    missing_bootstrap_assets,
)


def test_required_bootstrap_assets_exist() -> None:
    project_root = Path(__file__).resolve().parents[2]

    assert missing_bootstrap_assets(project_root) == []


def test_bootstrap_assets_do_not_require_optional_pattern_cache() -> None:
    assert OPTIONAL_BOOTSTRAP_ASSETS == ()


def test_bootstrap_assets_require_repo_loop_adapter_and_tracked_skills() -> None:
    required = {
        "docs/llm/repo-autonomous-loop-adapter.yaml",
        "docs/llm/low-attention-execution-contract.json",
        "docs/llm/low-attention-coverage-ledger.json",
        ".claude/skills/ez-ax-autoloop/SKILL.md",
        ".claude/skills/ez-ax-executable-autoloop/SKILL.md",
        "docs/llm/agents/contract-scope-guardian.md",
        "docs/llm/agents/assetization-pattern-promoter.md",
    }

    assert required.issubset(set(REQUIRED_BOOTSTRAP_ASSETS))


def test_bootstrap_assets_have_no_duplicates() -> None:
    assert len(set(REQUIRED_BOOTSTRAP_ASSETS)) == len(REQUIRED_BOOTSTRAP_ASSETS)


def test_missing_bootstrap_assets_returns_sorted_paths(tmp_path: Path) -> None:
    missing = missing_bootstrap_assets(tmp_path)

    assert missing == sorted(missing)


def test_bootstrap_asset_status_reports_required_and_optional_missing(
    tmp_path: Path,
) -> None:
    status = bootstrap_asset_status(tmp_path)

    assert isinstance(status, BootstrapAssetStatus)
    assert len(status.missing_required) == len(REQUIRED_BOOTSTRAP_ASSETS)
    assert status.missing_optional == OPTIONAL_BOOTSTRAP_ASSETS
