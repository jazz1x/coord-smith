# ADR-002 — Multi-step recipe DSL (`steps:` as canonical)

- **Status**: Accepted (2026-05-13)
- **Date**: 2026-05-13
- **Deciders**: coord-smith core
- **Tags**: dsl, recipe, scope, deprecation

## Context

The original recipe schema declared a single mission target:

```yaml
version: 1
missions:
  click_dispatch:
    image: templates/buy.png
    confidence: 0.9
```

This shape carried two practical defects:

- **One click per `coord-smith` invocation.** Multi-step flows
  (ticketing buy → seat → confirm) required N CLI subprocess
  invocations from the caller, each paying preflight cost.
- **Mission-name coupling.** The recipe field name (`click_dispatch`)
  echoed an internal mission name from the 12-mission graph; renaming
  the graph mission would have broken every published recipe.

A new DSL was needed that (a) expressed an ordered click sequence in
one invocation, (b) decoupled the recipe shape from the internal
mission graph, and (c) carried per-step pre-/post-click guards.

## Decision

The canonical recipe shape is:

```yaml
version: 1
steps:
  - name: <unique-within-recipe>
    image: <path>   # and/or
    coord: { x: <int>, y: <int> }
    prefer: image | coord  # when both declared
    wait_for: { image, timeout, interval, region }   # pre-click guard
    settle_ms: <int>    # post-click pause; default 300
    verify_transition: <bool>
    transition_threshold: <float>
    transition_region: [x, y, w, h]
    post_click_signal: { image, confidence, timeout, interval }
```

Authoring rules:

- `name` is the per-step identifier; recipe-wide uniqueness is
  enforced at parse time (action-log JSONL files are named after the
  step — duplicates would silently collide).
- At least one of `image` or `coord` must be declared.
- The legacy `missions: {name: target}` shape continues to load but
  auto-normalizes to a one-step recipe and emits a one-shot
  `DeprecationWarning`. New recipes MUST use `steps:`.
- `wait_for` runs before coord resolution, so timing-sensitive
  anchors get a chance to appear before the matcher even looks at
  the click target.

## Consequences

- **Positive.** A multi-step flow runs in a single `coord-smith`
  invocation, paying preflight once. Per-step evidence is preserved
  in the same run root.
- **Positive.** Recipe authors compose flows from a small fixed
  vocabulary (`image` / `coord` / `wait_for` / `verify_transition`
  / `post_click_signal` / `settle_ms`) — no escape hatch into runtime
  internals.
- **Positive.** Decoupling from mission names means the per-run
  graph (`step_observe` / `step_dispatch` / `step_capture`) can
  evolve without breaking recipes.
- **Negative.** Multi-step flows are atomic: one step's failure aborts
  the run (fail-fast — see ADR-004). Callers that want partial
  rollback or per-step retry must split the flow across multiple
  invocations.
- **Open.** The schema is `version: 1`. Backwards-incompatible
  changes (e.g. mandatory new field on every step) require bumping
  the version and writing a migration ADR.

## References

- `src/coord_smith/config/click_recipe.py` (`ClickRecipe`, `Step`,
  `StepCoord`, `WaitFor`, `PostClickSignal`)
- `docs/recipe-guide.md` (canonical schema documentation)
- `docs/recipes/multi-step-flow.yaml`,
  `docs/recipes/multi-step-with-wait-for.yaml` (example recipes)
- `docs/history/prd-multi-step-flow-recipe.md` (PRD that introduced
  the DSL)
