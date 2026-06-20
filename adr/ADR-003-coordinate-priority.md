# ADR-003 — Coordinate priority: `payload → step.coord → step.image → no-click`

- **Status**: Accepted (2026-05-13)
- **Date**: 2026-05-13
- **Deciders**: coord-smith core
- **Tags**: dispatch, contract, invariant

## Context

A single step can carry multiple click-target sources:

1. The caller (OpenClaw) may inject `x` / `y` into the dispatch
   payload at runtime ("OpenClaw computed the coordinate from a
   model-driven layout solver").
2. The recipe step may declare `coord: { x, y }` ("the author
   hard-coded a known position").
3. The recipe step may declare `image: templates/buy.png`
   ("locate the button by template match").
4. The step may declare none of the above ("smoke target — preflight
   only, no click").

The earlier scaffold had three places that independently chose which
source wins, sometimes silently falling through. A caller could not
predict what would actually be clicked, and the runtime could swap
priorities across versions without notice.

## Decision

The dispatch priority is **fixed and global**:

```
payload(x, y)  >  step.coord  >  step.image  >  no-click
```

> **Note on level 1 (payload):** the `payload` x/y is the **OpenClaw transport
> hook** and is *not wired through the current CLI graph* — the released
> `execute_step_dispatch_node` builds a fixed `{step_idx, step}` payload with no
> x/y, so in a CLI-only run (OpenClaw absent) priority 1 is never populated and
> `step.coord` / `step.image` decide the click. The priority *order* is the
> fixed contract; populating level 1 is the integration point for an external
> reasoner, exercised today only by direct-adapter tests. See CLAUDE.md
> §"Real clicks without OpenClaw".

Specifically:

1. If `ExecutionRequest.payload` carries non-None `x` / `y`, those
   coordinates are clicked.
2. Otherwise, if `Step.coord` is declared, those coordinates are
   clicked.
3. Otherwise, if `Step.image` is declared, the runtime calls
   `locateCenterOnScreen` and clicks the matched center.
4. Otherwise, the step is a no-op (preflight + evidence only).

When a step declares **both** `image` and `coord`, `Step.prefer`
chooses the primary; the other becomes the implicit fallback (image
match fails → coord is used). The default for dual-declared steps is
`prefer: image` (image is more layout-tolerant).

The priority is enforced in source code (`_resolve_step_click_coords`)
and locked by tests. No code path may reorder it; no field may
override it from outside the runtime.

## Consequences

- **Positive.** Callers reason about a single, named ordering when
  injecting payloads. OpenClaw's runtime decision (priority 1) always
  wins, while a deterministic recipe (priorities 2–3) remains the
  fallback baseline.
- **Positive.** The "no-click smoke target" (priority 4) is a
  first-class outcome, not an accident — useful for preflight tests,
  permission checks, and recipe validation.
- **Negative.** Priority is fixed *globally*; per-step overrides are
  not allowed (only the in-step `prefer` for dual-declared targets).
  A caller that needs the opposite ordering must transform the recipe
  before invocation.
- **Open.** Future schema versions may add a fifth source (e.g.
  payload-image, "here is a template you crop at runtime") — that
  insertion must be a new ADR that names where in the chain it lands.

## References

- `docs/prd.md` §Coordinate Priority (fixed — do not try to override)
- `src/coord_smith/adapters/pyautogui_adapter.py` —
  `_resolve_step_click_coords`
- `tests/unit/test_step_fallback_chain.py`
- `docs/recipe-guide.md` §Coordinate Priority
