# coord-smith Recipe Guide — Agent Edition

This document is the single reference an autonomous agent (e.g. OpenClaw) needs
to operate coord-smith correctly. Read this before writing or modifying any recipe.

---

## Agent Contract

What you **can** do:

- Read any file under `docs/` and `src/` (read-only reference).
- Write or modify `*.yaml` / `*.yml` / `*.json` recipe files anywhere on disk.
- Invoke the `coord-smith` CLI with a recipe path.
- Read exit codes and artifacts to decide what to do next.

What you **must never** do:

- Modify any file under `src/coord_smith/` — that is a contract violation.
- Touch browser internals (DOM, CDP, Playwright) — coord-smith owns the OS layer only.
- Decide *where* to click inside coord-smith — the recipe is the only channel for that.

---

## CLI Invocation

```bash
coord-smith \
  --session-ref        <session-id>        \
  --expected-auth-state authenticated      \
  --target-page-url    <url>               \
  --site-identity      <site-name>         \
  --click-recipe       <path/to/recipe.yaml>
```

All flags are optional, including `--click-recipe`. Omitting the recipe runs
the pipeline with no click (useful for smoke-testing the evidence pipeline).

---

## Exit Codes

| Code | Meaning | Agent action |
|------|---------|--------------|
| `0` | Success — pipeline reached `runCompletion` | Read artifacts, proceed |
| `1` | Unhandled runtime error | Inspect `artifacts/action-log/` for the last event |
| `2` | macOS Accessibility or Screen Recording permission denied | Cannot fix via recipe; escalate |
| `3` | Recipe file missing or schema invalid | Fix the recipe and retry |

---

## Coordinate Priority (fixed — do not try to override)

```
payload coords (injected by caller)
  └─ recipe coord  (x / y in recipe)
       └─ recipe image  (template match)
            └─ no click
```

The priority order is enforced by the runtime and cannot be changed by a recipe.

---

## Recipe Format

Recipes are YAML (preferred) or JSON. The file extension determines the parser:
`.yaml` / `.yml` → YAML, anything else → JSON.

### Minimal structure (multi-step — preferred)

```yaml
version: 1
steps:
  - name: <step_name>
    image: <path>      # at least one of image / coord required per step
    coord: { x, y }    # optional; presence forms an implicit fallback chain
    # ... per-step options ...
```

Each step is one click. Steps execute serially within a single
`coord-smith` invocation; per-run setup (`attach_session`, `prepare_session`)
and teardown (`run_completion`) frame the step list automatically. An empty
or omitted `steps` list is a smoke target — the run completes without any
click.

### Legacy single-mission structure (backwards-compat)

```yaml
version: 1
missions:
  click_dispatch: <target>
```

The legacy `missions: {name: target}` shape is auto-normalized to a
single-step recipe at load time. This emits a one-shot `DeprecationWarning`
and is preserved only for existing recipes; new recipes should use `steps:`.

### Released pipeline (per-run + per-step)

```
attach_session → prepare_session → (step_observe → step_dispatch →
step_capture)×N → run_completion
```

The per-step block runs N times for an N-step recipe; with N=0 the per-step
block is skipped and `prepare_session` connects directly to `run_completion`.

---

## Target Types

### A. Coordinate click (single-step example)

```yaml
steps:
  - name: click-buy
    coord:
      x: 800      # required — pixel X from left edge
      y: 500      # required — pixel Y from top edge
```

Use when the caller (OpenClaw) already knows the exact pixel position and
the screen layout is fixed across runs. Coord-only steps are brittle to
DPI / resolution changes; prefer image-anchored or hybrid forms when the
recipe is shared across machines.

### B. Image-template click

```yaml
steps:
  - name: click-buy
    image: templates/buy-button.png   # required — path relative to recipe file
    confidence: 0.9                   # 0.0–1.0, default 0.9
    region: [0, 400, 1920, 400]       # optional — [left, top, width, height]
    grayscale: false                  # optional — match in grayscale (faster)
```

Use when the target button moves between runs (responsive layout, scroll).
`region` restricts the search rectangle for speed and accuracy.

Failure modes:
- `ImageTemplateNotFound` (exit 1) — template file does not exist.
- `ImageMatchConfidenceLow` (exit 1) — template on screen but below `confidence`.

### C. Hybrid — image primary with coord fallback

```yaml
steps:
  - name: click-buy
    image: templates/buy-button.png
    coord: { x: 800, y: 500 }       # implicit fallback when image misses
    confidence: 0.9
    # prefer: image                  # default; explicit prefer only when flipping
```

When a step declares both `image` and `coord`, the runtime forms an implicit
fallback chain: the field named in `prefer` (default `image`) is tried first,
the other is tried if the primary fails. Set `prefer: coord` per step to
flip the order (rare — only when image matching is known to be noisy on a
particular target while the coord is stable).

There is no separate `fallback:` field. The chain is derived from which
fields the step declares.

### D. Image click + post-click verification

```yaml
steps:
  - name: click-buy
    image: templates/buy-button.png
    confidence: 0.9

    # Optional — verify the page changed after click
    verify_transition: true
    transition_threshold: 0.02        # fraction of region that must change (0–1)
    transition_region: [0, 100, 1920, 800]  # restrict diff to this area

    # Optional — poll for a signal image to appear after click
    post_click_signal:
      image: templates/loading-spinner.png
      confidence: 0.85
      timeout: 5.0     # seconds to wait before giving up
      interval: 0.1    # polling interval in seconds
```

`verify_transition` diffs a pre-click and post-click screenshot. If the changed
area is below `transition_threshold`, `PageTransitionNotDetected` is raised
(exit 1).

`post_click_signal` polls `locateCenterOnScreen` until the signal image appears.
Timeout raises `ImageWaitTimeout` (exit 1).

### E. Pre-click guard (`wait_for`)

```yaml
steps:
  - name: select-seat
    wait_for:
      image: templates/seat-panel.png   # poll until visible before clicking
      timeout: 5.0
      interval: 0.1
    image: templates/available-seat.png
    region: [200, 300, 800, 600]
```

`wait_for` blocks the step until the named image appears on screen, then
proceeds with the click. Replaces the legacy `trigger_wait` mission and
binds the wait to the step that needs it.

---

## Full Field Reference

### `ClickRecipe`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | int | `1` | Schema version. Always `1` for now. |
| `steps` | list of Step | `null` | Multi-step click sequence (preferred). |
| `missions` | map | `{}` | **Deprecated.** Legacy single-mission map; auto-normalized to a single-step recipe with a one-shot `DeprecationWarning`. |

### `Step` (multi-step recipe entry — at least one of `image` or `coord` required)

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `name` | str | — | yes (unique within recipe) |
| `image` | str (path) | `null` | one of `image`/`coord` |
| `coord` | StepCoord | `null` | one of `image`/`coord` |
| `region` | [int×4] | `null` | image-only |
| `confidence` | float 0–1 | `null` (= 0.9) | image-only |
| `grayscale` | bool | `null` (= false) | image-only |
| `prefer` | `"image"` \| `"coord"` | resolved by validator | when both are declared |
| `wait_for` | WaitFor | `null` | no — pre-click guard |
| `verify_transition` | bool | `false` | no |
| `transition_threshold` | float 0–1 | `0.01` | no |
| `transition_region` | [int×4] | `null` | no |
| `post_click_signal` | PostClickSignal | `null` | no |

### `StepCoord`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `x` | int | — | yes |
| `y` | int | — | yes |

### `WaitFor` (pre-click guard — wait until image appears on screen)

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `image` | str (path) | — | yes |
| `confidence` | float 0–1 | `0.9` | no |
| `timeout` | float > 0 | `5.0` | no |
| `interval` | float > 0 | `0.1` | no |
| `region` | [int×4] | `null` | no |

### `PostClickSignal`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `image` | str (path) | — | yes |
| `confidence` | float 0–1 | `0.9` | no |
| `timeout` | float > 0 | `5.0` | no |
| `interval` | float > 0 | `0.1` | no |

> Image paths are resolved relative to the recipe file's directory.
> Absolute paths are accepted unchanged.

### Legacy `MissionClick` / `MissionImageClick` (deprecated)

The legacy `missions: {name: target}` shape still loads — the runtime
auto-normalizes it to `steps: [Step]` at parse time. New recipes should use
`steps:` directly. The legacy field schemas remain in
`coord_smith.config.click_recipe` only for backwards-compat parsing; do
not author new recipes against them.

---

## Artifacts Output

After a successful run (`exit 0`), artifacts appear under the path passed as
`run_root` (defaults to `artifacts/runs/<run_id>/`):

```
artifacts/
  action-log/
    attach-session.jsonl
    prepare-session.jsonl
    step-observed.jsonl         ← per-step pre-click observation
    step-dispatched.jsonl       ← per-step click event
    step-captured.jsonl         ← per-step post-click capture
    release-ceiling-stop.jsonl  ← final proof of runCompletion
  screenshot/
    attach-session-fallback.png
    step-dispatched.png
    ...
```

Each `.jsonl` file contains one JSON object per line. Per-step events also
carry `step_idx` and `step_name`:

```json
{"ts": "2026-05-02T11:00:00+00:00", "mission_name": "step_dispatch", "event": "step-dispatched", "step_idx": 0, "step_name": "open-buy"}
```

The `release-ceiling-stop.jsonl` file is the authoritative proof that the run
reached `runCompletion`. If it is absent after exit 0, the run was incomplete.

### Failure Artifacts

When a step's dispatch fails with a typed adapter error
(`ImageMatchConfidenceLow`, `ImageTemplateNotFound`,
`ClickCoordinatesOutOfBounds`, `ClickExecutionUnverified`,
`PageTransitionNotDetected`, `ImageWaitTimeout`), the run aborts at that
step but evidence of the failure is captured before the exit:

```
artifacts/
  failure/
    01-confirm-purchase-ImageMatchConfidenceLow.png   ← screen at failure
  action-log/
    failure.jsonl                                      ← structured record
```

`failure.jsonl` carries a single JSON object per failure with:

```json
{
  "ts": "2026-05-02T11:00:00+00:00",
  "mission_name": "step_dispatch",
  "event": "step-dispatch-failed",
  "step_idx": 1,
  "step_name": "confirm-purchase",
  "error_class": "ImageMatchConfidenceLow",
  "error_message": "image template not matched at confidence>=0.9: ...",
  "screenshot": "/abs/path/to/01-confirm-purchase-ImageMatchConfidenceLow.png"
}
```

Earlier steps' artifacts (`step-dispatched.jsonl` records, screenshots)
are preserved — the failure record is appended, not overwritten. The
caller (e.g. OpenClaw) can read this record to diagnose why the step
failed and decide what to do next (retry with adjusted confidence,
re-crop the template against the captured failure screenshot,
escalate, etc.).

The CLI maps any of the above typed errors to **exit code 1** (runtime
error). `exit 0` always means the run reached `runCompletion`.

---

## Decision Guide for Agents

```
Do I know the exact pixel coordinates?
  yes → use coord click (x / y)
  no  → use image click (image + confidence)

Does the UI animate or scroll after the click?
  yes → add verify_transition: true + transition_threshold
  no  → omit

Do I need to confirm a specific element appeared (e.g. spinner, toast)?
  yes → add post_click_signal
  no  → omit
```

---

## Getting the Schema Programmatically

```bash
uv run python -c "
import json
from coord_smith.config.click_recipe import ClickRecipe
print(json.dumps(ClickRecipe.model_json_schema(), indent=2))
"
```

---

## Sample Recipes

| File | Use case |
|------|----------|
| [`docs/recipes/multi-step-flow.yaml`](recipes/multi-step-flow.yaml) | **Multi-step happy path** — three sequential image-anchored clicks |
| [`docs/recipes/multi-step-with-fallback.yaml`](recipes/multi-step-with-fallback.yaml) | **Multi-step + fallback** — image primary, coord fallback per step (with per-step `prefer: coord` override) |
| [`docs/recipes/datepicker-pattern.yaml`](recipes/datepicker-pattern.yaml) | **Datepicker / grid widget** — wide-context template + region restriction for visually-similar cells |
| [`tests/fixtures/demo/demo-flow.yaml`](../tests/fixtures/demo/demo-flow.yaml) | **End-to-end tutorial** — four-step recipe against the bundled demo page (see Tutorial below) |
| [`tests/fixtures/demo/demo-flow-with-guards.yaml`](../tests/fixtures/demo/demo-flow-with-guards.yaml) | **End-to-end tutorial + guards** — same flow with `verify_transition` + `post_click_signal` per step |
| [`docs/recipes/coord-click.yaml`](recipes/coord-click.yaml) | Single-step (legacy `missions:` shape) — fixed pixel coordinate |
| [`docs/recipes/image-click.yaml`](recipes/image-click.yaml) | Single-step (legacy) — template match + transition check |
| [`docs/recipes/image-click-with-signal.yaml`](recipes/image-click-with-signal.yaml) | Single-step (legacy) — template match + post-click signal polling |

---

## Tutorial — End-to-End on the Bundled Demo Page

The repo ships a deterministic 5-state demo page at
[`tests/fixtures/demo/ticketing.html`](../tests/fixtures/demo/ticketing.html)
(fixed 1280×800 viewport, no animations, distinct background tint per
state). It exists to let you exercise the complete coord-smith loop —
template extraction → recipe authoring → multi-step dispatch → guard
validation — without an external service.

### 1. Render each state to PNG

```bash
for state in buy seat-1 seat-2 confirm success; do
  npx playwright screenshot --viewport-size=1280,800 \
    "file://$(pwd)/tests/fixtures/demo/ticketing.html?state=${state}" \
    "tests/fixtures/demo/state-${state}.png"
done
```

The page accepts a `?state=<name>` query param so the renderer can jump
directly to each state without simulating clicks.

### 2. Crop button templates from the rendered states

The button positions are stable across states (the panel switches but
the layout grid does not). A short Python script crops each step's
target button into `tests/fixtures/demo/templates/`:

```python
from PIL import Image
from pathlib import Path

DEMO = Path("tests/fixtures/demo")
crops = [
    ("state-buy.png",     "buy-button.png",       (495, 460, 785, 530)),
    ("state-seat-1.png",  "seat-a1.png",          (370, 460, 580, 530)),
    ("state-seat-1.png",  "seat-a2.png",          (700, 460, 910, 530)),
    ("state-seat-2.png",  "confirm-seat.png",     (495, 540, 785, 615)),
    ("state-confirm.png", "confirm-purchase.png", (495, 600, 785, 675)),
]
for src, dst, box in crops:
    Image.open(DEMO / src).crop(box).save(DEMO / "templates" / dst)
```

### 3. Write the recipe

[`tests/fixtures/demo/demo-flow.yaml`](../tests/fixtures/demo/demo-flow.yaml)
is the canonical four-step recipe. Note the `region:` constraint on
step 2 — the Seat A1 and Seat A2 templates differ by one character, so
without a search restriction OpenCV can match the wrong button at
default `confidence=0.9`.

### 4. Disambiguation pitfall — region restriction

When two on-screen buttons share most pixels (`Seat A1` vs `Seat A2`,
two list items with the same shape), the template match is ambiguous.
Three ways to disambiguate, in increasing strength:

1. Raise `confidence` (e.g. `0.97`) — usually enough but brittle to
   font hinting changes.
2. Add `region: [x, y, w, h]` to the step — restrict the search to the
   half / quadrant where the intended button lives. **Preferred.**
3. Use a more distinctive template — crop a wider area that includes
   surrounding text (e.g., the seat row's row-label).

### 5. Run the recipe (or the integration test)

```bash
# Real run — moves the live cursor (macOS Accessibility required).
uv run coord-smith --click-recipe tests/fixtures/demo/demo-flow.yaml \
  --session-ref demo --expected-auth-state authenticated \
  --target-page-url file://demo --site-identity demo

# Or run the integration test — never touches the real cursor.
uv run pytest tests/integration/test_demo_flow_with_real_opencv.py -v
```

The integration test uses `pyautogui.locate(template, screenshot_file)`
in place of `pyautogui.locateCenterOnScreen`, so OpenCV matching is
real but the screen surrogate returns the next state's PNG after each
click. This is the recommended pattern for testing recipes against a
fixed demo without disturbing the real screen.
