from __future__ import annotations

from ez_ax.rag.coverage_ledger import first_pending_family, load_coverage_ledger


def test_load_coverage_ledger_includes_docs_sufficiency_family() -> None:
    families = load_coverage_ledger()

    assert any(
        family.family == "docs-sufficiency family for lower-capacity continuation"
        for family in families
    )


def test_first_pending_family_returns_transport_boundary_reopen_slice() -> None:
    pending = first_pending_family()

    assert pending is not None
    assert pending.family == "released OpenClaw transport-boundary family"
    assert "Item 27" in pending.next_slice_hint
