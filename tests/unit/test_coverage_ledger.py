from __future__ import annotations

import json
from pathlib import Path

from ez_ax.rag.coverage_ledger import first_pending_family, load_coverage_ledger


def test_load_coverage_ledger_includes_test_fixture_family() -> None:
    families = load_coverage_ledger()

    assert any(
        family.family == "test fixture module importability"
        for family in families
    )


def _write_ledger(tmp_path: Path, families: list[dict]) -> Path:  # type: ignore[type-arg]
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "active_phase": "Phase R5 — Integration",
                "active_milestone": "milestone",
                "active_anchor": "anchor",
                "families": families,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_first_pending_family_returns_none_when_all_covered(tmp_path: Path) -> None:
    ledger_path = _write_ledger(
        tmp_path,
        [{"family": "a", "status": "covered", "evidence_or_reason": "done",
          "next_slice_hint": "", "template_id": "", "first_validation": "",
          "mypy_target": "", "ruff_target": "", "done_when": []}],
    )

    assert first_pending_family(ledger_path=ledger_path) is None


def test_first_pending_family_returns_first_pending(tmp_path: Path) -> None:
    ledger_path = _write_ledger(
        tmp_path,
        [
            {"family": "covered-one", "status": "covered", "evidence_or_reason": "done",
             "next_slice_hint": "", "template_id": "", "first_validation": "",
             "mypy_target": "", "ruff_target": "", "done_when": []},
            {"family": "pending-one", "status": "pending", "evidence_or_reason": "todo",
             "next_slice_hint": "hint", "template_id": "", "first_validation": "",
             "mypy_target": "", "ruff_target": "", "done_when": []},
        ],
    )

    result = first_pending_family(ledger_path=ledger_path)

    assert result is not None
    assert result.family == "pending-one"
