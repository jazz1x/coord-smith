# ez-ax Recipe Guide — Agent Edition

This document is the single reference an autonomous agent (e.g. OpenClaw) needs
to operate ez-ax correctly. Read this before writing or modifying any recipe.

---

## Agent Contract

What you **can** do:

- Read any file under `docs/` and `src/` (read-only reference).
- Write or modify `*.yaml` / `*.yml` / `*.json` recipe files anywhere on disk.
- Invoke the `ez-ax` CLI with a recipe path.
- Read exit codes and artifacts to decide what to do next.

What you **must never** do:

- Modify any file under `src/ez_ax/` — that is a contract violation.
- Touch browser internals (DOM, CDP, Playwright) — ez-ax owns the OS layer only.
- Decide *where* to click inside ez-ax — the recipe is the only channel for that.

---

## CLI Invocation

```bash
ez-ax \
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

### Minimal structure

```yaml
version: 1
missions:
  <mission_name>: <target>
```

Only `click_dispatch` is the typical mission to configure. Other missions in the
12-step pipeline do not perform clicks and ignore recipe entries.

### Mission names (released pipeline order)

```
attach_session → prepare_session → benchmark_validation → page_ready_observation
→ sync_observation → target_actionability_observation → armed_state_entry
→ trigger_wait → click_dispatch → click_completion → success_observation
→ run_completion
```

---

## Target Types

### A. Coordinate click

```yaml
missions:
  click_dispatch:
    x: 800      # required — pixel X from left edge
    y: 500      # required — pixel Y from top edge
```

Use when the caller (OpenClaw) already knows the exact pixel position.

### B. Image-template click

```yaml
missions:
  click_dispatch:
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

### C. Hybrid — image click + post-click verification

```yaml
missions:
  click_dispatch:
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

---

## Full Field Reference

### `ClickRecipe`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | int | `1` | Schema version. Always `1` for now. |
| `missions` | map | `{}` | Mission name → target. |

### `MissionClick` (coord target — triggered when `x` and `y` are present)

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `x` | int | — | yes |
| `y` | int | — | yes |
| `verify_transition` | bool | `false` | no |
| `transition_threshold` | float 0–1 | `0.01` | no |
| `transition_region` | [int×4] | `null` | no |
| `post_click_signal` | PostClickSignal | `null` | no |

### `MissionImageClick` (image target — triggered when `image` is present)

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `image` | str (path) | — | yes |
| `confidence` | float 0–1 | `0.9` | no |
| `region` | [int×4] | `null` | no |
| `grayscale` | bool | `false` | no |
| `verify_transition` | bool | `false` | no |
| `transition_threshold` | float 0–1 | `0.01` | no |
| `transition_region` | [int×4] | `null` | no |
| `post_click_signal` | PostClickSignal | `null` | no |

### `PostClickSignal`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `image` | str (path) | — | yes |
| `confidence` | float 0–1 | `0.9` | no |
| `timeout` | float > 0 | `5.0` | no |
| `interval` | float > 0 | `0.1` | no |

> Image paths are resolved relative to the recipe file's directory.
> Absolute paths are accepted unchanged.

---

## Artifacts Output

After a successful run (`exit 0`), artifacts appear under the path passed as
`run_root` (defaults to `artifacts/runs/<run_id>/`):

```
artifacts/
  action-log/
    attach-session.jsonl
    prepare-session.jsonl
    ...
    click-dispatched.jsonl      ← structured click event
    release-ceiling-stop.jsonl  ← final proof of runCompletion
  screenshot/
    prepare-session-fallback.png
    click-dispatched-fallback.png
    ...
```

Each `.jsonl` file contains one JSON object per line with at minimum:

```json
{"ts": "2026-05-02T11:00:00+00:00", "mission_name": "click_dispatch", "event": "click-dispatched"}
```

The `release-ceiling-stop.jsonl` file is the authoritative proof that the run
reached `runCompletion`. If it is absent after exit 0, the run was incomplete.

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
from ez_ax.config.click_recipe import ClickRecipe
print(json.dumps(ClickRecipe.model_json_schema(), indent=2))
"
```

---

## Sample Recipes

| File | Use case |
|------|----------|
| [`docs/recipes/coord-click.yaml`](recipes/coord-click.yaml) | Fixed pixel coordinate |
| [`docs/recipes/image-click.yaml`](recipes/image-click.yaml) | Template match + transition check |
| [`docs/recipes/image-click-with-signal.yaml`](recipes/image-click-with-signal.yaml) | Template match + post-click signal polling |
