# Architecture Decision Records

Each ADR documents a durable architectural choice — a decision that
constrains downstream code and that we want to be able to recall in
six months without re-deriving the reasoning.

ADRs are numbered sequentially and never renumbered. Once *Accepted*,
the file is treated as append-only — superseding decisions land in a
new ADR that references the old one as `Supersedes ADR-NNN`.

## Format

MADR-light. Each file:

```
# ADR-NNN — Short title

- **Status**: Proposed | Accepted (date) | Superseded by ADR-NNN
- **Date**: ISO date
- **Deciders**: owners
- **Tags**: comma list (architecture | protocol | scope | invariant | ...)

## Context
Why this came up — what symptoms, what alternatives surfaced.

## Decision
The single sentence that constrains future code, followed by the
specifics.

## Consequences
- positive
- negative
- neutral / open

## References
Code paths, prior PRs, external docs.
```

## Index

| # | Title | Status |
|---|-------|--------|
| [001](ADR-001-llm-free-runtime-and-browser-ban.md) | LLM-free runtime + browser-internals forbidden | Accepted |
| [002](ADR-002-multi-step-recipe-dsl.md) | Multi-step recipe DSL as canonical (`steps:`) | Accepted |
| [003](ADR-003-coordinate-priority.md) | Coordinate priority `payload → step.coord → step.image → no-click` | Accepted |
| [004](ADR-004-failure-evidence-policy.md) | Failure evidence policy — phase-tagged `failure.jsonl` + screenshot | Accepted |
| [005](ADR-005-per-host-advisory-lock.md) | Per-host advisory lock for pyautogui process-globals | Accepted |
| [006](ADR-006-run-json-envelope.md) | `run.json` envelope as the single-file caller outcome contract | Accepted |
