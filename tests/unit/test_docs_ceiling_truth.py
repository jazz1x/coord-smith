"""Drift guard: ceiling-context in docs must name runCompletion, not pageReadyObserved.

The released ceiling was expanded from `pageReadyObserved` to `runCompletion`
on 2026-03-26 (see `docs/prd.md`). Autonomous agents read many docs and must
see a single consistent ceiling. This test prevents regression to the older
ceiling name in any sentence that explicitly talks about the "released
ceiling".

Policy:
- Transition notes that mention both names (e.g. "expanded from
  pageReadyObserved to runCompletion") are allowed — the presence of the
  canon name `runCompletion` in the same window signals the text is
  explaining history, not asserting the old ceiling.
- Mission-name uses of `pageReadyObserved` are unaffected because the
  regex targets the words "ceiling" adjacent to the ceiling name.
- Housekeeping PRDs that quote the drift strings as examples, and
  historical artifacts (coverage-ledger, rag-archive) are excluded.
"""
from __future__ import annotations

import re
from pathlib import Path

CEILING_CONTEXT = re.compile(
    # Match the phrase "<something> ceiling" where <something> is the
    # kind of ceiling being claimed. Negative lookahead `(?!-)` excludes
    # artifact filename uses like "release-ceiling-stop.jsonl".
    r"(?:released\s+ceiling|release\s+ceiling|scope\s+ceiling|current\s+released\s+ceiling|enclosed\s+ceiling)(?!-)",
    re.IGNORECASE,
)
FORBIDDEN = "pageReadyObserved"
CANON = "runCompletion"
# Forward window (chars after the ceiling-context match) that must not contain
# the forbidden ceiling name. Transition notes naming both ceilings in the
# surrounding context are permitted — we look backward too so that the canon
# name before the match counts as a transition note.
WINDOW_AFTER = 120
WINDOW_BEFORE = 80

EXCLUDE_PATHS = {
    Path("docs/llm/low-attention-coverage-ledger.json"),
    Path("docs/product/rag-archive.json"),
    Path("docs/prd-direction-realignment.md"),
    Path("docs/prd-direction-realignment-impl.md"),
}

DOCS_ROOT = Path(__file__).resolve().parent.parent.parent / "docs"
REPO_ROOT = DOCS_ROOT.parent


def _scan_files() -> list[Path]:
    paths: list[Path] = []
    for p in DOCS_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in {".md", ".yaml", ".yml", ".json"}:
            continue
        rel = p.relative_to(REPO_ROOT)
        if rel in EXCLUDE_PATHS:
            continue
        paths.append(p)
    return paths


def test_ceiling_context_never_names_pageReadyObserved() -> None:
    violations: list[str] = []
    for path in _scan_files():
        text = path.read_text(encoding="utf-8")
        for match in CEILING_CONTEXT.finditer(text):
            forward = text[match.start() : match.start() + WINDOW_AFTER]
            if FORBIDDEN not in forward:
                continue
            backward = text[max(0, match.start() - WINDOW_BEFORE) : match.start()]
            if CANON in forward or CANON in backward:
                # Transition note — the canon name on either side of the
                # match is how docs preserve history while naming the new
                # ceiling.
                continue
            line_no = text[: match.start()].count("\n") + 1
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}:{line_no}  {text.splitlines()[line_no-1][:160]}")

    assert not violations, (
        "ceiling-context sentences must not name pageReadyObserved without "
        "also naming runCompletion. Offenders:\n  " + "\n  ".join(violations)
    )


def test_ceiling_context_file_mentions_runCompletion() -> None:
    """Files that discuss the released ceiling must at least name runCompletion."""
    offenders: list[str] = []
    for path in _scan_files():
        text = path.read_text(encoding="utf-8")
        if not CEILING_CONTEXT.search(text):
            continue
        if CANON not in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, (
        "files that discuss the released ceiling must mention the canon "
        f"ceiling name ({CANON}). Offenders:\n  " + "\n  ".join(offenders)
    )
