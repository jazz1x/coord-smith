# coord-smith Architecture Boundaries

## Purpose

This document defines who owns what and who calls whom. It exists because
naming confusion between OpenClaw, coord-smith, and PyAutoGUI caused repeated
implementation misdirection.

## System Actors

```
OpenClaw  (external caller)
    |
    |  invokes via skill / CLI
    v
coord-smith CLI  (`coord-smith` console script)
    |
    |  owns and operates
    v
PyAutoGUI  (OS-level CUA engine)
    |
    |  coordinate-click + screenshot
    v
OS display server
    |
    |  results: stdout + artifacts/
    v
OpenClaw  (reads results, decides next step)
```

### Actor Definitions

| Actor | What It Is | What It Owns | Calls | Called By |
|-------|-----------|-------------|-------|----------|
| **OpenClaw** | External orchestration system | Task selection, high-level workflow | coord-smith CLI (via skill) | (external trigger) |
| **coord-smith** | Python orchestration runtime | CUA engine (PyAutoGUI), mission graph, validation, stopping | PyAutoGUI | OpenClaw (via CLI) |
| **PyAutoGUI** | OS-level CUA engine | `click(x, y)` + `screenshot()` | OS display server | coord-smith |

### Key Facts

- **OpenClaw calls coord-smith.** coord-smith does not call OpenClaw.
- **OpenClaw has no MCP server.** It invokes coord-smith through skill-based CLI execution.
- **coord-smith owns the CUA engine.** PyAutoGUI runs inside coord-smith, not inside OpenClaw.
- **Communication is ping-pong:** OpenClaw invokes `coord-smith` CLI, coord-smith writes
  results to stdout and `artifacts/`, OpenClaw reads them and decides next step.

## Integration Pattern

```
1. OpenClaw decides to run a mission
2. OpenClaw ensures the target window is foreground (see §Window Ownership)
3. OpenClaw invokes: coord-smith --session-ref ... --target-page-url ...
4. coord-smith runs the released-scope LangGraph (6 missions, ceiling = run_completion).
5. Each node calls PyAutoGUIAdapter.execute():
   - pyautogui.click(x, y)
   - pyautogui.screenshot()
   - writes action-log JSONL to artifacts/
6. coord-smith exits, leaving artifacts and stdout output
7. OpenClaw reads artifacts (including failure/ subtree on non-zero exit),
   decides next action
8. Repeat (ping-pong)
```

## Window Ownership (★ critical contract)

**coord-smith does not own the target window. The caller does.**

At dispatch time, ``pyautogui.screenshot()`` captures the entire physical
display. ``pyautogui.locateCenterOnScreen()`` then searches that capture
for the recipe's image template. If the target window (typically the
browser showing the target page) is not the front-most window at that
moment, the template will not be found and the run will fail with
``ImageMatchConfidenceLow``. The failure is recorded under
``runs/<id>/artifacts/failure/`` so the caller can diagnose.

### Caller responsibilities (OpenClaw)

1. **Activate the target window before invocation.** On macOS:
   ``osascript -e 'tell application "Google Chrome" to activate'`` or
   equivalent for the target app. Verify the activation took effect
   (e.g., by a smoke screenshot) before issuing the recipe.
2. **Keep the target window foreground for the duration of the run.**
   If the calling environment (e.g., an IDE) competes for focus, run
   the target in a separate macOS Space, fullscreen, or on a separate
   physical display. coord-smith does not arbitrate focus.
3. **For multi-step recipes, factor invocation length.** A four-step
   recipe takes roughly 1–2 seconds. If the calling environment is
   prone to focus theft within that window, chunk the flow into
   single-step invocations and re-activate the target between calls.
4. **Templates must be cropped from the target environment.** Templates
   cropped from a Playwright headless render will often fail to match
   the same page rendered in the user's real Chrome (font hinting,
   subpixel anti-aliasing, OS-level rendering differ). Crop fresh on
   the production host.

### Why this is not coord-smith's responsibility

Window activation requires platform-specific APIs (AppleScript on macOS,
``xdotool`` on Linux, Win32 on Windows). Embedding any of them in
coord-smith would create a hard platform dependency and conflict with
the released-scope invariant *"OS coordinates and pixels only — no app
control."* The current `pyautogui` surface stays in that lane;
activation belongs to whoever orchestrates the screen.

## Known Constraints in `verify_transition`

The Step-level ``verify_transition: true`` guard captures a baseline
frame immediately before the click and a post-click frame after the
adapter's fixed ``_POST_CLICK_SETTLE_SECONDS`` (50 ms) sleep. Real web
pages updating via React / DOM mutation frequently complete their visual
update *after* that 50 ms window — leading to a false-zero diff and a
``PageTransitionNotDetected`` raise even on a successful click.

**Workaround until a configurable settle is added:**
- Prefer ``post_click_signal`` over ``verify_transition`` for any
  recipe that targets dynamic web UI. The signal polls for an image
  to appear and naturally accommodates render latency up to ``timeout``.
- Use ``verify_transition`` only for instantaneous-visual-feedback
  scenarios (e.g., button press toggling its own colour).

A follow-up PRD should add ``Step.settle_ms: int = 300`` (or similar)
and remove the hard-coded constant.

## Templates That Look Alike — Disambiguation Patterns

Image-template matching at the default ``confidence: 0.9`` fails when
the target visually resembles other on-screen elements (date picker
cells with single-digit text, list rows with repeating shape, etc.).
Three patterns, in increasing strength:

1. **Region restriction** — ``region: [x, y, w, h]`` narrows the search
   to a known sub-rectangle. Cheapest when layout is stable.
2. **Wider context crop** — include adjacent elements in the template
   so the unique combination matches. Example: instead of cropping a
   3-cell row including its neighbours so the
   sequence is unique.
3. **Caller-computed coordinates** — for fully formulaic grids (date
   pickers with fixed cell sizes), the caller can compute the exact
   pixel coordinate of the target cell and ship a coord-only Step.
   No image matching needed. Best when the grid math is known.

## Code Namespace Clarification

### `adapters/execution/` (formerly `adapters/openclaw/`)

This package defines coord-smith's **internal execution adapter protocol**. It is
**not** an API client that connects to OpenClaw.

| File | Purpose |
|------|---------|
| `client.py` | `ExecutionAdapter` Protocol, `ExecutionRequest`, `ExecutionResult`, validation |
| `execution.py` | Re-export shim over `client.py` for back-compat imports |

### `adapters/pyautogui_adapter.py`

The **real CUA engine**. Implements `ExecutionAdapter` Protocol using
`pyautogui.click()` and `pyautogui.screenshot()` exclusively. No LLM calls.

## Naming History

The `adapters/openclaw/` directory was originally named when the execution
boundary was conceptualized as "a connection to OpenClaw." In reality, the
protocol defines coord-smith's internal pluggable execution backend. The rename to
`adapters/execution/` reflects this correction.

| Old Name | New Name | Reason |
|----------|----------|--------|
| `OpenClawAdapter` | `ExecutionAdapter` | It is coord-smith's internal protocol, not an OpenClaw API |
| `OpenClawExecutionRequest` | `ExecutionRequest` | Request is from coord-smith graph to its own adapter |
| `OpenClawExecutionResult` | `ExecutionResult` | Result is from adapter back to coord-smith graph |
| `adapters/openclaw/` | `adapters/execution/` | Package defines execution protocol, not OpenClaw client |
