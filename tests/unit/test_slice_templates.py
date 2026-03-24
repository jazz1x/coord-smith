from __future__ import annotations

from ez_ax.rag.slice_templates import load_slice_templates, match_slice_template


def test_load_slice_templates_includes_docs_sufficiency_template() -> None:
    templates = load_slice_templates()

    assert any(
        template.id == "docs_sufficiency_coverage_ledger_contract"
        for template in templates
    )


def test_match_slice_template_returns_docs_sufficiency_template() -> None:
    template = match_slice_template(
        next_action=(
            "Seed the earliest pending family from the active coverage ledger "
            "before honoring FINAL_STOP: close the docs-sufficiency family gap."
        )
    )

    assert template is not None
    assert template.id == "docs_sufficiency_coverage_ledger_contract"
