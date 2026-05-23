# ADR-001 — LLM-free runtime + browser-internals forbidden

- **Status**: Accepted (2026-05-13)
- **Date**: 2026-05-13
- **Deciders**: coord-smith core
- **Tags**: architecture, invariant, scope

## Context

`coord-smith` exists as the **hand** in a two-actor system: an external
LLM orchestrator (today: OpenClaw; tomorrow: any agent that follows the
same CLI contract) decides what to click, and `coord-smith` executes
that decision at the OS level. The runtime invariant question — "what
is `coord-smith` allowed to do during a run?" — recurred at every
scope-expansion temptation:

- "Could we just add a small Playwright dependency to detect modals?"
- "Could the adapter call an LLM when image matching is ambiguous?"
- "Could we install a CDP listener to capture the DOM as auxiliary
  evidence?"

Each of these is locally attractive but globally destructive: the
moment `coord-smith` reasons at runtime or peers into the browser, the
orchestration boundary collapses, the caller cannot replace
`coord-smith` independently, and the deterministic-evidence promise is
gone. The system stops being a hand and becomes a head — duplicated
with the actual head that already lives in the caller.

## Decision

Two paired hard invariants, enforced at PR-review and by repository
contract:

1. **LLM-free runtime.** The `coord-smith` runtime graph performs no
   LLM inference at execution time. All reasoning happens outside the
   runtime — in the caller. The runtime is allowed to embed model
   schemas (Pydantic) and validators (deterministic) but never to
   invoke a model.
2. **Browser-internals forbidden.** No Playwright, CDP, Chromium
   driver, DOM access, browser console hook, or HTTP intercept inside
   the runtime. The runtime sees only OS-level pixels and coordinates.
   Image matching uses OpenCV (deterministic pixel matching, not
   reasoning).

These two invariants are co-equal. Violating either is a PR-reject
condition (no warning loop, no exception list).

## Consequences

- **Positive.** The orchestration boundary stays clean: the caller can
  swap `coord-smith` for any other "OS click executor" implementation
  that honors the same CLI contract. The deterministic-evidence
  promise (every click produces a typed artifact) holds because no
  step contains nondeterministic reasoning.
- **Positive.** The runtime stays small, fast, and reviewable. Today
  ~35 source files; no model client, no async browser pool, no
  long-lived sessions.
- **Negative.** Some scenarios that a browser-internal tool could
  handle (CAPTCHAs, dynamic per-session selectors) are explicitly out
  of scope — the caller must solve them upstream or accept failure
  evidence and re-decide.
- **Open.** Pure deterministic enhancements that look LLM-adjacent
  (e.g. a layout heuristic that picks between two coords based on
  pixel-distance to a known landmark) are allowed because they are
  not inference. The line is "did we call an external model or
  consult browser-internal state?"

## References

- `docs/prd.md` §System Boundary, §Runtime inference boundary
- `docs/architecture-boundaries.md` §System Actors
- `src/coord_smith/adapters/pyautogui_adapter.py` (the entire adapter
  consists of `pyautogui.click` + `pyautogui.screenshot` + OpenCV
  template match — nothing else)
- `CLAUDE.md` §Invariants
