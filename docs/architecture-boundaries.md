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

## Host Exclusivity (★ critical contract)

**Only one coord-smith invocation may run on a given host at a time.**

PyAutoGUI is process-global on a given host: there is exactly one cursor
and one screen for the entire OS, shared across every running pyautogui
client. Two coord-smith processes running simultaneously would:

- Race on the preflight cursor probe (each process's `moveTo` competes
  with the other's clicks).
- Interleave clicks within their own `_dispatch_with_step` windows,
  producing entirely incorrect outcomes (a step in process A clicking
  while process B's cursor is at the wrong coordinate).
- Capture screenshots that include the other process's mid-flight
  cursor / overlay state, breaking image-template matching with
  invisible, hard-to-reproduce errors.

coord-smith enforces single-active-invocation via an advisory
``fcntl.flock`` on ``base_dir/artifacts/.coord-smith.lock``
(``coord_smith.graph.host_lock``). The lock is acquired before
preflight and released at the end of `_run`. A second invocation
that cannot acquire the lock within 10 seconds raises
``HostBusyError`` and exits with code **4** (`host busy`), giving
the caller a deterministic signal to back off and retry.

### Caller responsibilities (OpenClaw)

1. **Serialize coord-smith invocations on a host.** Do not launch
   parallel `coord-smith` processes that share the same `base_dir`
   (or, more conservatively, the same host). Treat exit code 4 as
   a back-off-and-retry signal, not as a failure of the work itself.
2. **For multi-tenant / multi-session scenarios, scope invocations to
   isolated workspaces.** The lock is per `base_dir`; different
   workspaces (separate trees) can run in parallel, but they still
   share the host cursor/screen — so the lock partitioning is only
   useful when the work is also physically isolated (e.g., separate
   Mac mini per session).
3. **Do not bypass the lock.** Removing ``.coord-smith.lock`` while
   a coord-smith process is running may produce inconsistent
   artifacts and silently incorrect dispatch.

### Why this is not coord-smith's responsibility to schedule

coord-smith is a single-invocation tool. Scheduling, queueing,
back-off, and retries are caller concerns (OpenClaw). The host-lock
is a safety net against accidents, not a queue manager.

## How callers should read a run result (★ critical contract)

Every coord-smith invocation writes exactly one
``run.json`` envelope. The caller (e.g. OpenClaw) should read it
**before** inspecting any other artifact. The decision tree:

```
1. Read run.json  (either runs/<run_id>/run.json
                   or base_dir/run.json when no run root exists yet)
2. Branch on run.json.status:
     "success"     → exit_code == 0 ; nothing else to do
     "failure"     → read run.json.failure for the compact diagnosis,
                     then dive into failure.jsonl + the matching
                     screenshot under runs/<run_id>/artifacts/failure/
     "interrupted" → user / supervisor sent SIGINT (Ctrl-C). Treat
                     like a transient failure; safe to retry once.
     "host_busy"   → another coord-smith process held the lock. Back
                     off (e.g. 1–5 s) and retry. Exit code 4.
```

Do not infer outcome from the *presence* of files alone:
``release-ceiling-stop.jsonl`` is created only on success, but its
absence does NOT uniquely mean "host busy" vs "permission failure"
vs "crash before any artifact was written". ``run.json`` is the
single source of truth — its `status` + `exit_code` are
authoritative.

The schema is documented in [docs/recipe-guide.md §Run summary
schema](recipe-guide.md#run-summary-schema).

## `verify_transition` settle timing (`Step.settle_ms`)

The Step-level ``verify_transition: true`` guard captures a baseline
frame immediately before the click and a post-click frame after a
configurable settle delay. The delay is set per step via
``Step.settle_ms`` (integer milliseconds; default **300 ms**, range
``0–10000``).

Recipe authors should pick a value to match the target UI:

| UI class | Suggested `settle_ms` |
|----------|----------------------|
| Native widgets that flip state synchronously (toggles, colour swaps) | `0` – `50` |
| Standard web pages (default React render cycle) | `300` (default) |
| Heavy SPAs with animation / virtualised lists | `500` – `1000` |

History: prior versions of this adapter used a hard-coded 50 ms settle.
Real web pages updating via React / DOM mutation frequently completed
their visual update *after* that window, producing a false-zero diff
and a spurious ``PageTransitionNotDetected`` raise on otherwise
successful clicks. The default was raised to 300 ms once
``Step.settle_ms`` made it configurable; recipes that previously worked
around the gap with ``post_click_signal`` can now choose either guard
based on intent (signal = "wait for X to appear", transition = "screen
changed at all").

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
