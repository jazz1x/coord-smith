<!--
Thanks for the contribution! Before you click "Create pull request",
walk through the checklist below. The pre-commit hooks + CI will
re-verify, but doing this once locally saves a round trip.
-->

## What

<!-- One paragraph: what this PR changes, in plain terms. Link the
issue / PRD / ADR it implements or amends. -->

## Why

<!-- Why the change is worth shipping now. If a P0/P1 from
docs/backlog.md, name the ID (B-CA-3, B-PROD-2, etc.). -->

## How

<!-- The shape of the change — files touched, contracts updated,
notable design choices. If this is an SRP refactor or an API
extension, note the before/after at the surface level. -->

## Test plan

- [ ] `uv run ruff check .` — no errors
- [ ] `uv run mypy` — `Success: no issues found`
- [ ] `uv run pytest -q` — all green, expected count noted in commit message
- [ ] `uv run pre-commit run --all-files` — clean

## Invariant + ADR check

<!-- Tick all that apply OR confirm "this PR touches none of these". -->

- [ ] **Runtime stays LLM-free** (ADR-001). No model calls, no inference,
      no model SDK import.
- [ ] **Browser-internals forbidden** (ADR-001). No Playwright / CDP /
      Chromium driver / DOM access added.
- [ ] **`pyautogui.FAILSAFE = True`** still enforced in
      `PyAutoGUIAdapter.__init__`.
- [ ] **Coordinate priority** (ADR-003) unchanged or, if changed,
      requires a new ADR landing in this PR.
- [ ] **Recipe schema** changes are backwards-compatible at
      `version: 1`, or accompanied by a schema-version bump.
- [ ] **Public artifacts** (`run.json`, `failure.jsonl`, per-step JSONLs)
      schema unchanged, OR contract tests updated AND
      `docs/recipe-guide.md` / corresponding ADR amended in this PR.

## Docs

- [ ] CLAUDE.md / README.md / docs/* updated to match the new behaviour
- [ ] If a P2 backlog item lands, removed from `docs/backlog.md`
- [ ] If a new ADR is required, added under `adr/` with the next
      sequential number

## Breaking changes

<!-- If yes, name them explicitly and link the migration note in
CHANGELOG.md. -->

None / See `CHANGELOG.md` entry: <link>

---

🤖 If this PR was generated with the help of Claude Code, that is
fine — but please review every diff hunk yourself before merging.
