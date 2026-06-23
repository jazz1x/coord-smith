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

The four session/auth/url/site inputs are **required** — each may be supplied
either as the CLI flag shown above or as its `COORDSMITH_*` environment
variable. Omitting one exits with code `3` (config error) and a message naming
the flag + env var to set. `--click-recipe` is **optional**: omitting it runs
the pipeline with no click (useful for smoke-testing the evidence pipeline).

### Inline recipes

When an agent generates a recipe in memory, pass it directly instead of writing
a file:

```bash
# JSON inline
coord-smith \
  --session-ref        <session-id>        \
  --expected-auth-state authenticated      \
  --target-page-url    <url>               \
  --site-identity      <site-name>         \
  --recipe-json        '{"version": 1, "steps": [...]}'

# YAML inline
coord-smith \
  --session-ref        <session-id>        \
  --expected-auth-state authenticated      \
  --target-page-url    <url>               \
  --site-identity      <site-name>         \
  --recipe-yaml        'version: 1\nsteps:\n  - name: ...'
```

Recipe source priority (highest first): `--recipe-json` > `--recipe-yaml` >
`--click-recipe` > `COORDSMITH_CLICK_RECIPE` env var.

### JSON stdout

Add `--json` to any dispatch invocation to print the final `run.json` to stdout
after it is written to disk. This lets a calling agent read the outcome in the
same process without a second file read:

```bash
coord-smith --recipe-json '{...}' --json ...
```

### Python API

For agents that prefer to call coord-smith as a library:

```python
import asyncio
import coord_smith

async def main() -> None:
    result = await coord_smith.run_click_recipe(
        recipe={"version": 1, "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}]},
        session_ref="session-id",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
    )
    print(result.status, result.exit_code, result.run_json_path)

asyncio.run(main())
```

A synchronous wrapper is also available: `coord_smith.run_click_recipe_sync(...)`.
Both functions accept a `Path`, YAML/JSON string, `dict`, or `ClickRecipe` model
and return a `RunResult` dataclass with the written `run.json` path and summary.

---

## Exit Codes

| Code | Meaning | Agent action |
|------|---------|--------------|
| `0` | Success — pipeline reached `runCompletion` | Read `run.json` / `artifacts/`, proceed |
| `1` | Unhandled runtime error (typed dispatch failure OR caught `KeyboardInterrupt`); **also** `--cleanup` partial failure (at least one run dir could not be removed) | For a dispatch run, branch on `run.json.status`: `"failure"` → read the `failure` key; `"interrupted"` → safe to retry. For `--cleanup`, there is **no run.json** — read the stderr deletion-error count instead |
| `2` | macOS Accessibility or Screen Recording permission denied | Cannot fix via recipe; escalate to operator |
| `3` | Config error. Causes: recipe file missing / schema invalid; a required input (`--session-ref` / `--expected-auth-state` / `--target-page-url` / `--site-identity`) absent; an invalid `--target-window` app name (activation failed); an invalid `--cleanup` bound (`--max-runs` / `--max-age-days` non-integer or negative); or a malformed payload coord override (partial / non-integer `x`/`y`). **Read the `config error: <message>` line on stderr** — it names the exact cause; do not assume a recipe/input fix. Note: a malformed payload override raises mid-dispatch before the failure-evidence net, so `run.json` carries `status=failure`, `exit_code=3`, `failure=null`. | Read the stderr message, fix the named thing, retry |
| `4` | Host busy — another coord-smith process held the per-host lock | Back off 1–5 s and retry; see `docs/architecture-boundaries.md §Host Exclusivity` |

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
- Missing template file — caught at **recipe load** as a `ConfigError`
  (**exit 3**) when loaded via `--click-recipe`: every referenced template
  is existence-checked before any click. (`ImageTemplateNotFound` / exit 1
  is the runtime form, reachable only when a `Step` is built directly via
  `model_construct`, bypassing the loader — not the normal CLI path.)
- `ImageMatchConfidenceLow` (**exit 1**) — template on screen but below
  `confidence` at click time.

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

    # Optional — adjust the post-click pause before reading the post-click
    # frame for verify_transition (default 300 ms; 0–10000 ms allowed).
    # Lower for native widgets that flip instantly; raise for heavy SPAs.
    settle_ms: 500

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
(exit 1). The pre-click frame is captured immediately; the post-click frame is
captured after `settle_ms` so React/DOM updates have time to flush.

`post_click_signal` polls `locateCenterOnScreen` until the signal image appears.
Timeout raises `ImageWaitTimeout` (exit 1).

`settle_ms` defaults to **300 ms** — chosen so a standard web-app render cycle
completes before the post-click diff. Use `settle_ms: 0` (or a small value like
`50`) for native widgets where waiting is wasted; use `settle_ms: 800`–`1000`
for SPAs with heavy animation or virtualised lists.

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
| `settle_ms` | int 0–10000 | `300` | no — post-click pause in ms before verify_transition reads the post-click frame |

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
| `interval` | float > 0 (≤ `timeout`) | `0.1` | no |
| `region` | `[left, top, width, height]` | `null` | no |

> Image paths are resolved relative to the recipe file's directory.
> Absolute paths are accepted unchanged. `region` scopes the post-click
> poll to a rectangle (e.g. the toast area), mirroring `wait_for.region`;
> omit it to poll the full screen.

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

#### Success-path record fields

Beyond the base keys above, a per-step record carries extra keys describing
what the guard/resolver did. A caller (e.g. OpenClaw) can read these to audit a
*successful* run — most importantly to detect a silently-degraded template:

| Event source | Extra keys | Meaning |
|--------------|-----------|---------|
| image match | `image_template`, `match_confidence`, `match_x`, `match_y` | template matched at these coords/confidence |
| **image fallback** | `image_fallback_used: true`, `image_fallback_template`, `image_fallback_reason`, `image_fallback_x`, `image_fallback_y` | a `prefer: image` step's template MISSED and the step rode its `coord` fallback. **Watch for this** — it means the template is stale even though the click "succeeded". |
| `wait_for` hit | `wait_for_template`, `wait_for_confidence`, `wait_for_elapsed_seconds`, `wait_for_x`, `wait_for_y` | pre-click anchor appeared |
| `post_click_signal` hit | `post_click_signal_template`, `post_click_signal_confidence`, `post_click_signal_elapsed_seconds`, `post_click_signal_x`, `post_click_signal_y` | post-click signal appeared |
| `verify_transition` | `transition_changed`, `transition_change_ratio`, `transition_threshold`, `transition_bbox` | page-change check result |

> **`transition_bbox` is `[left, top, right, bottom]`** (PIL corner-pair form),
> NOT the `[left, top, width, height]` convention every *input* region uses
> (`region`, `transition_region`). To get the changed-area extent: `width =
> right - left`, `height = bottom - top`. It is `null` when nothing changed.

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
  "phase": "dispatch",
  "error_class": "ImageMatchConfidenceLow",
  "error_message": "image template not matched at confidence>=0.9: ...",
  "screenshot": "/abs/path/to/01-confirm-purchase-ImageMatchConfidenceLow.png"
}
```

`mission_name` / `event` name the node that failed: a click-dispatch failure is
`step_dispatch` / `step-dispatch-failed` (`phase: dispatch`), while a
screenshot/evidence-gather failure during pre-click observation or post-click
capture self-describes as `step_observe` / `step-observe-failed`
(`phase: pre_click`) or `step_capture` / `step-capture-failed`
(`phase: post_click`) — so a gather failure is never mislabeled as a dispatch
that never happened. `step_idx` / `step_name` localize it either way.

`phase` is one of:

| Value | Origin |
|-------|--------|
| `pre_click` | Step's `wait_for` guard timed out / template missing, or pre-click observation could not capture the screen |
| `dispatch` | Coord resolution, click execution, baseline screenshot |
| `post_click` | `verify_transition` failed, `post_click_signal` timed out, or post-click capture could not capture the screen |

The same `error_class` can originate from multiple phases (e.g.
`ImageWaitTimeout` from `wait_for` versus `post_click_signal`); `phase`
is the disambiguator. Callers debugging a failure should branch on
`phase` first — pre-click failures usually indicate the page isn't
ready, dispatch failures indicate template/coord/permission issues,
post-click failures indicate the click went through but the expected
outcome didn't appear.

Earlier steps' artifacts (`step-dispatched.jsonl` records, screenshots)
are preserved — the failure record is appended, not overwritten. The
caller (e.g. OpenClaw) can read this record to diagnose why the step
failed and decide what to do next (retry with adjusted confidence,
re-crop the template against the captured failure screenshot,
escalate, etc.).

The CLI maps any of the above typed errors to **exit code 1** (runtime
error). `exit 0` always means the run reached `runCompletion`.

## Run Summary Schema (`run.json`)

Every coord-smith **dispatch** invocation writes exactly one
``run.json`` summary envelope. The caller (e.g. OpenClaw) should
read it **first** to determine outcome instead of grepping
individual JSONL files.

**Exceptions — pre-run exits do NOT write ``run.json``.** The envelope is
written only for an actual dispatch *run* (including a run that fails or is
interrupted). Invocations that exit **before** a run begins write no
``run.json``:

- ``--help`` / ``--version`` / ``--recipe-schema`` (exit 0) — informational, no run.
- ``--cleanup`` (operator command) — writes only an INFO-level summary log line.
- a **malformed CLI** rejected up front — an unknown/typo'd flag exits **3**
  before the run bracket opens. The ``config error: <message>`` stderr line is
  the diagnostic. (A *missing required input* or *bad recipe*, by contrast, is
  detected inside the run bracket and DOES write a ``run.json`` with
  ``status=failure``, ``exit_code=3``, ``failure=null``.)

Automation that polls ``run.json`` after every invocation must skip the wait for
these pre-run exits and branch on the exit code + stderr instead.

**``--dry-run`` writes a run.json** (it validates without dispatching). It is
distinguishable from a real successful run: ``{"status": "success",
"exit_code": 0, "run_id": null, "failure": null}``. The ``run_id`` is **null**
(no run root is created), whereas a real success always has a non-null
``run_id``; branch on ``run_id`` to tell them apart. Note ``step_count`` on a
dry-run is the **recipe length** (the count that validated), not "steps
reached" — a dry-run reaches zero steps.

Location:

```
artifacts/runs/<run_id>/run.json     # normal case
<base_dir>/run.json                  # when no run root was created
                                     # (host_busy / config error
                                     # before the graph started)
```

Schema (`schema_version: 1`):

```jsonc
{
  "schema_version": 1,
  "run_id": "20260518-123045-abc12345",  // or null when no run root
  "status": "success",                    // see enum below
  "exit_code": 0,                         // matches CLI exit code
  "started_at": "2026-05-18T12:30:45+00:00",
  "ended_at":   "2026-05-18T12:30:46+00:00",
  "elapsed_seconds": 1.2345,
  "step_count": 3,                        // steps REACHED, not recipe total
  "failure": null                         // populated when status=failure
}
```

> **`step_count` is "steps reached", not "recipe total".** It counts the
> distinct `step_idx` values that produced evidence. On success it equals the
> recipe length (all steps ran); on a mid-flow failure it is the count of steps
> reached before the abort (a 3-step recipe failing at step index 1 reports
> `step_count: 2`). To form "failed at step X of N", take `X` from
> `failure.step_idx` and `N` from the recipe you submitted — `run.json` does not
> carry the recipe total as a separate field.

`status` enum (one of):

| Value | Exit code | Meaning |
|-------|-----------|---------|
| `success` | 0 | Run reached `run_completion`. `failure: null`. |
| `failure` | 1 (or 2 / 3) | Typed dispatch failure, permission failure, or config error. `failure` block populated when the run actually started. |
| `interrupted` | 1 | `KeyboardInterrupt` (Ctrl-C / SIGINT) was caught. |
| `host_busy` | 4 | Another coord-smith process held the per-host lock. Retry after back-off. |

When `status == "failure"` and the run created a run root, the `failure`
block is a compact summary plus a pointer to the full record:

```jsonc
{
  "step_idx":     1,
  "step_name":    "confirm-purchase",
  "phase":        "pre_click",   // pre_click | dispatch | post_click
  "error_class":  "ImageWaitTimeout",
  "screenshot":   "/abs/path/01-confirm-purchase-ImageWaitTimeout.png",
  "failure_jsonl":"/abs/path/.../action-log/failure.jsonl"
}
```

For deeper diagnostics (e.g. additional records in `failure.jsonl`,
the full per-step action-log files), follow the `failure_jsonl`
pointer and the `runs/<run_id>/artifacts/` tree.

`run.json` is written atomically (tmp + rename) on every exit path
including `KeyboardInterrupt` and writer-side failures (writer never
masks the caller's exit code).

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

The preferred path — no Python interpreter spawn, works against any
installed `coord-smith` wheel:

```bash
coord-smith --recipe-schema > recipe-schema.json
```

The output is the standard Pydantic v2 ``model_json_schema()`` and is
stable across patch releases. The schema version is the recipe's
own ``version`` field (currently ``1``); the JSON Schema dialect is
managed by Pydantic.

Equivalent, useful pre-install or in dev checkouts:

```bash
uv run python -c "
import json
from coord_smith.config.click_recipe import ClickRecipe
print(json.dumps(ClickRecipe.model_json_schema(), indent=2))
"
```

> **The JSON Schema cannot express the cross-field rules** that also reject a
> recipe at load time, so a structurally-valid-against-the-schema recipe can
> still exit **3**. The loader additionally enforces: a step must declare **at
> least one** of `image` / `coord` (and image-match fields on a coord-only step
> are rejected); `wait_for` / `post_click_signal` `interval` ≤ `timeout`; step
> names are **unique** and must not collide with reserved action-log keys;
> `region` is `[x, y, w, h]` with positive extent. An agent generating a recipe
> from the schema alone should **run `coord-smith --dry-run`** (a no-permission,
> no-click validator) to confirm these before dispatch.

## Diagnostic logging (caller-side control)

coord-smith emits diagnostics through the stdlib `logging` framework
under the ``coord_smith`` logger. Default level is ``INFO``. Knobs:

| Knob | Effect |
|------|--------|
| `--verbose` / `-v` | Set level to ``DEBUG`` (overrides env). |
| `--quiet` / `-q` | Set level to ``WARNING`` (overrides env). |
| `COORDSMITH_LOG_LEVEL` | Set level (`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`) — case-insensitive. Wins over the default. |

Records propagate to the root logger so embedding applications can
intercept via standard `logging.basicConfig()` or pytest's `caplog`
fixture. The CLI installs a single `StreamHandler` to stderr with
format ``coord-smith: <LEVEL>: <message>``.

---

## Sample Recipes

| File | Use case |
|------|----------|
| [`docs/recipes/multi-step-flow.yaml`](recipes/multi-step-flow.yaml) | **Multi-step happy path** — three sequential image-anchored clicks |
| [`docs/recipes/multi-step-with-fallback.yaml`](recipes/multi-step-with-fallback.yaml) | **Multi-step + fallback** — image primary, coord fallback per step (with per-step `prefer: coord` override) |
| [`docs/recipes/datepicker-pattern.yaml`](recipes/datepicker-pattern.yaml) | **Datepicker / grid widget** — wide-context template + region restriction for visually-similar cells |
| [`tests/fixtures/demo/demo-flow.yaml`](../tests/fixtures/demo/demo-flow.yaml) | **End-to-end tutorial** — four-step recipe against the bundled demo page (see Tutorial below) |
| [`tests/fixtures/demo/demo-flow-with-guards.yaml`](../tests/fixtures/demo/demo-flow-with-guards.yaml) | **End-to-end tutorial + guards** — same flow with `verify_transition` + `post_click_signal` per step |
| [`docs/recipes/coord-click.yaml`](recipes/coord-click.yaml) | Single-step (`steps:` shape) — fixed pixel coordinate |
| [`docs/recipes/image-click.yaml`](recipes/image-click.yaml) | Single-step (`steps:` shape) — template match + transition check |
| [`docs/recipes/image-click-with-signal.yaml`](recipes/image-click-with-signal.yaml) | Single-step (`steps:` shape) — template match + post-click signal polling |

> **The `docs/recipes/` image samples ship placeholder templates** under
> `docs/recipes/templates/` so that `--dry-run` validates the recipe structure
> out of the box. The placeholders are simple colored rectangles — they will
> **not** match a real screen during an actual click. Replace each one with a
> crop taken from your target browser before running a real dispatch, or use
> [`docs/recipes/coord-click.yaml`](recipes/coord-click.yaml), which is
> self-contained (pure coords, no templates). The runnable, end-to-end examples
> are the `tests/fixtures/demo/*.yaml` recipes below, whose templates ARE
> bundled and matched against the bundled demo page.

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
