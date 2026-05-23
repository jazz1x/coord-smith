# Contributing to coord-smith

Thank you for considering a contribution! coord-smith is a small,
opinionated runtime — the contribution surface is correspondingly
narrow. This page tells you where the lines are.

## Where the truth lives

In priority order:

1. **`docs/prd.md`** — system invariants. Do not violate.
2. **[`adr/`](adr/README.md)** — durable architectural decisions
   (LLM-free runtime, recipe DSL, coordinate priority, failure
   evidence policy, host lock, run.json envelope). Decisions
   recorded here cannot be silently reversed in a single PR.
3. **`docs/current-state.md`** — what's actually released today.
4. **`docs/architecture-boundaries.md`** — caller / runtime
   contracts (window ownership, host exclusivity, run-result
   reading).
5. **Source code under `src/coord_smith/`** — authoritative for
   the runtime contracts (mission graph, evidence envelope,
   adapter protocol).
6. **`CLAUDE.md`** — agent-facing operational entrypoint. Keep it
   in sync with the canonical recipe shape.

When the PRD and a prior assumption disagree, follow the PRD.
When the PRD and an ADR disagree, the more recent ADR wins (and
the PRD must be reconciled in the same PR).

## Hard invariants (PR rejected on violation)

- **LLM-free runtime.** The coord-smith runtime graph contains no
  LLM inference. Reasoning lives outside.
- **Browser-internals forbidden.** No Playwright / CDP / Chromium
  driver. OS coordinates and pixels only.
- **`pyautogui.FAILSAFE = True`** stays enforced in
  `PyAutoGUIAdapter.__init__`.
- **Coordinate priority is fixed.** `payload → step.coord →
  step.image → no-click`. Never reordered.
- **OpenClaw calls coord-smith**, not the reverse.

## Local development

```bash
# Python 3.14 required (uv installs it if absent).
uv sync --extra dev

# Run the full test suite (real-binary tests auto-excluded).
uv run pytest -q

# Lint + type check.
uv run ruff check .
uv run mypy

# Install pre-commit hooks (one-time per clone).
uv run pre-commit install
```

Real-binary tests (`pytest -m real`) require macOS Accessibility +
Screen Recording permission for the host terminal. They move the
real cursor — do not run them in a loop.

## Before you open a PR

1. **Tests** must accompany behaviour changes. Recipe schema
   changes need parse-level + adapter-level coverage.
2. **`uv run pytest -q`** is green and reports the expected pass
   count (currently ~280).
3. **`uv run ruff check .`** and **`uv run mypy`** are both clean.
4. **`uv run pre-commit run --all-files`** has nothing to fix.
5. If you touched `docs/recipe-guide.md` schema sections, the
   contract tests under `tests/contract/` still pass.
6. If you changed a public field on `Step` / `ClickRecipe`, you
   updated `CLAUDE.md`'s recipe example AND added the field name
   to `tests/contract/test_claude_md_recipe_example.py`'s
   `field_token` parametrize list.
7. **No new dependencies** in `[project.dependencies]` without a
   PRD discussion. Dev deps are looser.

## Commit messages

Conventional Commits style is preferred but not enforced:
`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`. Keep
the subject line under 80 characters; use the body for the
"why".

Co-author attribution is welcome but not required.

## Versioning / release

This project uses Semantic Versioning. The path from 0.0.1 →
0.1.0 → 1.0.0 is documented in `docs/backlog.md`. Until a
CI/release workflow lands (see B-PROD-2), version bumps are
manual: edit `pyproject.toml`'s `[project].version` and the
matching `__version__` in `src/coord_smith/__init__.py`, then
tag the commit.

## Questions

For larger changes (adding a Step field, expanding the mission
graph, changing the evidence envelope), open an issue first.
Drive-by SRP refactors of the heavy modules are also welcome —
see `docs/backlog.md` §B-CA-* for known targets.
