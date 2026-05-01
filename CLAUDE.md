# CLAUDE

Operational entrypoint for agents working in this repository.

## Bootstrap

Fresh checkouts run, in order:

1. `uv sync --extra dev` — installs runtime + dev deps from `pyproject.toml`.
2. `uv run pytest -q` — expected: 703 passing, 1 skipped, 4 deselected.

If pytest collection fails with `ModuleNotFoundError: PIL|pyautogui`, step 1
did not complete.

The 4 deselected items are real-binary integration tests (`pytest -m real`)
that require macOS Accessibility + Screen Recording permission on the host
terminal. Without those permissions, the `ez-ax` console script exits at
`preflight()` with code 2 instead of producing silent no-op clicks.

## Real clicks without OpenClaw

The released-scope graph dispatches click-bearing missions with empty
payloads. In the documented architecture an external actor (OpenClaw)
populates `x` / `y`. When that actor is absent, `ez-ax` accepts a
**click recipe** (`--click-recipe PATH` or `EZAX_CLICK_RECIPE` env) that
maps `mission_name` → coordinates or template image. The adapter resolves
click coords with priority: payload → recipe coord → recipe image → no
click. See `README.md` §Click Recipes for schema and examples.

## Primary Source Documents

Agents must read in this order:

1. [docs/prd.md](docs/prd.md) — invariant system truth
2. [docs/current-state.md](docs/current-state.md) — implementation snapshot
3. [README.md](README.md) — pipeline + invariants overview

Source code under `src/ez_ax/` is authoritative for runtime contracts
(missions, state model, adapters, evidence envelope). Read code, not historical
design docs.

## Priority Order

1. Repository-specific instructions in this file.
2. Layered entrypoint documents:
   [docs/prd.md](docs/prd.md), [docs/current-state.md](docs/current-state.md).
3. Source code under `src/ez_ax/` for runtime contracts.
4. Repository base config: `pyproject.toml`, `.pre-commit-config.yaml`,
   `.gitignore`.
5. For Python code writing / review / refactoring, follow
   `.claude/python-engineering.md` unless it conflicts with higher-priority
   sources. The same guidance is available as the `python-engineering` skill
   at `.claude/skills/python-engineering/SKILL.md`.

## Invariants

- **LLM-free runtime.** The ez-ax runtime graph contains no LLM inference.
  Reasoning lives outside (e.g. OpenClaw).
- **Browser-internals forbidden.** No Playwright, CDP, or Chromium driver.
  Only OS-level coordinates and pixels.
- **`pyautogui.FAILSAFE = True`** is enforced in `PyAutoGUIAdapter.__init__`.
- **Coordinate priority is fixed.** payload → recipe coord → recipe image →
  no click. Never the other way.
- **OpenClaw calls ez-ax**, not the reverse.

## Agent Expectations

- Keep `ez-ax` orchestration-centric.
- Prefer event-based waits over sleep-based timing.
- Prefer typed evidence over intuition.
- Do not introduce anti-detection logic.
- Do not describe modeled behavior as released behavior.
- Do not change anything above the current approved release ceiling
  (`runCompletion`) unless the PRD explicitly allows it.
- Use relevant available skills actively when they fit. Skills are
  execution aids, not scope authority — if a skill conflicts with the PRD,
  follow the PRD.

## Working Rules

- Each autonomous task must end with applicable validation
  (`pytest` / `mypy` / `ruff`) and a git commit before the next task begins.
- If a task cannot be validated or committed honestly, it must not be
  reported as complete.
- When the PRD and remembered prior repository state differ, follow the PRD
  and the currently existing files; ignore deleted or historical structure.

## Guardrails

- Planned or modeled features must not be presented as implemented or
  released.
- The active canonical implementation path is Python-only (3.14). Do not
  recreate `package.json`, `bun.lock`, `tsconfig.json`, or `biome.json` as
  active toolchain files.
- Do not add new TypeScript runtime source under `src/` or any alternate
  package root.
- If a proposed change would restore a removed execution path, stop and
  treat it as a policy violation unless the PRD explicitly changes.
