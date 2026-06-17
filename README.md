# coord-smith

> Python CUA runtime — deterministic OS-coordinate clicking, driven by an external LLM

![python](https://img.shields.io/badge/python-3.14-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![version](https://img.shields.io/badge/version-0.1.1-blue)
![tests](https://img.shields.io/badge/tests-398%20passing-brightgreen)
![runtime](https://img.shields.io/badge/runtime-LLM--free-orange)
[![CI](https://github.com/jazz1x/coord-smith/actions/workflows/ci.yml/badge.svg)](https://github.com/jazz1x/coord-smith/actions/workflows/ci.yml)

**coord-smith** is the *hands*. The *head* — an external LLM such as OpenClaw — decides what to click; coord-smith executes those decisions on the OS as coordinate clicks and screenshot evidence. Reasoning lives outside the runtime; the runtime itself contains zero LLM calls.

A run is a 6-mission pipeline (3 per-run + 3 per-step, repeated for each recipe step) driven by a LangGraph state machine. Each mission produces an evidence envelope (action-log JSONL, screenshots, transition diffs) before the next mission is allowed to start. No browser internals (Playwright / CDP / Chromium) are touched — only OS-level coordinates and pixels.

[한국어](./README.ko.md)

## Pipeline

The runtime walks **six missions** — three per-run (setup / teardown) wrapping a per-step block that runs once for each step in the recipe. Every mission is deterministic and produces evidence on disk before the next mission is allowed to start.

| Mission | Phase | Role |
|---------|-------|------|
| `attach_session` | per-run | Attach to an existing browser session via session-ref. |
| `prepare_session` | per-run | Verify expected auth state and target page URL. |
| `step_observe` | per-step | Capture pre-click on-screen state for a step. |
| `step_dispatch` | per-step | Execute the step's click (image-or-coord with prefer/fallback). |
| `step_capture` | per-step | Capture post-click evidence (screenshot, transition diff, optional signal). |
| `run_completion` | per-run | Close the run with a sealed status code. |

For an N-step recipe the per-step trio runs N times in declaration order; with N=0 the per-step block is skipped (smoke target). Each mission emits a fixed past-tense action key (e.g. `step_dispatch` → `step-dispatched`) so the action log is machine-greppable.

```
 OpenClaw (external LLM)
      │  decisions, coords, image refs
      ▼
 coord-smith CLI ──▶ LangGraph state machine ──▶ 6 missions
                                              │
                            evidence envelope (JSONL + PNG)
                                              │
                                              ▼
                                          OS (PyAutoGUI)
                                              │
                                  pixels  ◀──────────  cursor
                                              │
                            OpenCV match / PIL diff verifies
```

## Prerequisites

- **Python 3.14** — pinned. Earlier minors are no longer supported by this repo.
- **macOS** for real-binary tests: Accessibility + Screen Recording permissions.
- **uv** as the package manager (`pip install uv` or `brew install uv`).

```bash
python3.14 --version    # must be 3.14.x
uv --version
```

## Install

For end users (PyPI consumers — preferred once a wheel is published):

```bash
# uv (recommended)
uv pip install coord-smith
# or stock pip
pip install coord-smith
```

For development from a source checkout:

### 1. Bootstrap the project

```bash
git clone https://github.com/jazz1x/coord-smith.git
cd coord-smith
uv sync --extra dev
```

`uv` will resolve and provision Python 3.14 automatically based on `requires-python` in `pyproject.toml`. If your system Python is older, install it first:

```bash
uv python install 3.14
```

### 2. Verify

```bash
uv run pytest -q                # 398 passed, 4 deselected (real-binary)
uv run ruff check .
uv run mypy
```

The `-m real` suite is excluded by default (it drives the live cursor).

### 3. Install the git hooks (once per clone)

```bash
uv run pre-commit install
```

### 4. (macOS) Grant permissions for real clicks

System Settings → Privacy & Security:

1. **Accessibility** — check the terminal app, then restart the terminal.
2. **Screen Recording** — same path, same app.

Then:

```bash
uv run pytest -m real -q        # 4 passed: preflight + screenshot + coord click + image self-locate
```

Without these permissions, `preflight()` exits with code `2`.

## Quickstart

Drive a real click without OpenClaw, using a recipe:

```bash
coord-smith --click-recipe ./recipe.yaml \
      --session-ref my-session \
      --expected-auth-state authenticated \
      --target-page-url https://example.com \
      --site-identity example
```

On macOS, when the target browser may not be foreground at invocation
time (e.g. the calling shell competes for focus), add
`--target-window "Google Chrome"` (or the equivalent app name). The CLI
runs `osascript -e 'tell application "<name>" to activate'` and waits
~1 s for the system to finish the focus handoff before preflight and
dispatch. The same value can be passed via the
`COORDSMITH_TARGET_WINDOW` environment variable; the CLI flag wins when
both are set. See [docs/architecture-boundaries.md §Window Ownership]
(docs/architecture-boundaries.md#window-ownership) for the caller's
responsibilities (the activation is a one-shot; keeping the window
foreground for the duration of the run is up to the orchestrator).

A minimal coordinate recipe:

```yaml
version: 1
steps:
  - name: click-buy
    coord: { x: 800, y: 500 }
```

A layout-tolerant image recipe (recommended):

```yaml
version: 1
steps:
  - name: click-buy
    image: templates/buy-button.png
    confidence: 0.9
    grayscale: false
```

YAML is canonical; `.json` files are accepted for backwards compatibility (extension-routed). The legacy `missions: {name: target}` shape still loads but emits a `DeprecationWarning` — new recipes must use `steps:`. See [docs/recipe-guide.md](docs/recipe-guide.md) for the full schema and agent contract.

**Coordinate priority**: payload (OpenClaw) → step coord → step image → no-click.

## Reading the result

Every invocation writes a single `run.json` summary that the caller can read in one go to determine outcome — no need to grep individual JSONL files:

```jsonc
// artifacts/runs/<run_id>/run.json  (or base_dir/run.json when no run root exists)
{
  "schema_version": 1,
  "run_id": "20260518-123045-...",
  "status": "success",       // success | failure | interrupted | host_busy
  "exit_code": 0,            // 0 success · 1 runtime · 2 perms · 3 recipe · 4 host busy
  "started_at": "...",
  "ended_at": "...",
  "elapsed_seconds": 1.2345,
  "step_count": 3,
  "failure": null            // compact failure block when status=failure
}
```

On failure, the `failure` key inside `run.json` carries `step_idx`, `step_name`, `phase` (`pre_click` / `dispatch` / `post_click`), `error_class`, `screenshot` path, and a pointer to the full `failure.jsonl`. (Note: `failure` is a JSON field, not a separate `run.json.failure` file.)

## Click Recipes

### Image-based clicking (OpenCV template matching)

| Field | Meaning |
|-------|---------|
| `image` | Template path. Relative paths resolve from the recipe file. |
| `confidence` | Match threshold 0.0–1.0. Default `0.9`. |
| `region` | `[left, top, width, height]` to constrain the search. |
| `grayscale` | Drop color for speed. Default `false`. |

Failure modes are typed: `ImageTemplateNotFound`, `ImageMatchConfidenceLow`.

### Page-transition verification (optional, off by default)

```yaml
steps:
  - name: click-buy
    image: templates/buy.png
    verify_transition: true
    transition_threshold: 0.02
    transition_region: [0, 100, 1920, 800]
```

Pre-click screenshot → click → post-click screenshot → `PIL.ImageChops.difference` bbox area / region area > threshold ⇒ pass. Below the threshold raises `PageTransitionNotDetected`.

### Post-click signal polling (optional, off by default)

```yaml
steps:
  - name: click-buy
    image: templates/buy.png
    post_click_signal:
      image: templates/loading-spinner.png
      confidence: 0.85
      timeout: 5.0
      interval: 0.1
```

Polls `locateCenterOnScreen` until the signal image appears. Timeout raises `ImageWaitTimeout`.

## CI & checks

| Check | Command | Purpose |
|-------|---------|---------|
| Lint | `uv run ruff check .` | Style, unused imports, rule violations |
| Types | `uv run mypy` | Strict typing |
| Tests (default) | `uv run pytest -q` | `-m real` auto-excluded |
| Tests (real binary) | `uv run pytest -m real -q` | macOS Accessibility + Screen Recording |
| Pre-commit | `uv run pre-commit run --all-files` | Full sweep |

GitHub Actions runs on every push to `main` and every pull request — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml). The workflow installs Python 3.14 + xvfb (Ubuntu only, so `import pyautogui` succeeds without a real display) and runs ruff + mypy + pytest, plus a separate pre-commit job. Locally, the same gates run via the pre-commit hooks installed by `uv run pre-commit install`.

## Architecture decisions

Durable spine decisions are recorded in [`adr/`](adr/README.md):

- [ADR-001 LLM-free runtime + browser-internals forbidden](adr/ADR-001-llm-free-runtime-and-browser-ban.md)
- [ADR-002 Multi-step recipe DSL](adr/ADR-002-multi-step-recipe-dsl.md)
- [ADR-003 Coordinate priority](adr/ADR-003-coordinate-priority.md)
- [ADR-004 Failure evidence policy](adr/ADR-004-failure-evidence-policy.md)
- [ADR-005 Per-host advisory lock](adr/ADR-005-per-host-advisory-lock.md)
- [ADR-006 `run.json` outcome envelope](adr/ADR-006-run-json-envelope.md)

## Invariants

coord-smith has four hard invariants. Anything that violates them is rejected at PR time:

1. **LLM-free runtime.** No model calls inside coord-smith. Reasoning lives in OpenClaw.
2. **Browser-internals forbidden.** No Playwright, no CDP, no Chromium driver. OS coordinates and pixels only.
3. **`pyautogui.FAILSAFE = True`** is enforced in `PyAutoGUIAdapter.__init__`. Slamming the cursor into a screen corner aborts the run instantly.
4. **Coordinate priority is fixed.** payload → recipe coord → recipe image → no-click. Never the other way.

OpenCV is allowed because it is a deterministic pixel-matching library — neither LLM nor browser.

## Project structure

```
src/coord_smith/
  adapters/         execution adapters (PyAutoGUI, page-transition diff)
  config/           settings models (ClickRecipe, RuntimeSettings)
  evidence/         envelope parsing / validation
  graph/            LangGraph nodes + CLI entrypoints
  missions/         mission name registry
  models/           runtime state, errors, checkpoints
  reporting/        transition summary
  validation/       bootstrap-asset checks
tests/
  unit/             unit tests
  contract/         architectural contract tests
  integration/      real-binary tests (`-m real`)
  e2e/              full-pipeline tests
  fixtures/         shared test fixtures
docs/
  prd.md                     single source of truth
  current-state.md           current implementation snapshot
  architecture-boundaries.md actor / namespace boundaries
  recipes/                   sample click recipes
```

## Naming

- **coord-smith** — *easy axes*: the runtime swings two axes (coordinates and pixels) and asks no further questions.

## Triad

coord-smith fits between two sibling tools — independent processes, connected only through artifacts on disk:

```
OpenClaw (think)  ──▶  coord-smith (act)  ──▶  evidence envelope (record)
   external LLM        deterministic        JSONL + PNG on disk
                       OS-coord click
```

The split is deliberate: every component must be replaceable without touching the others.

## Footnote

> *"A click is the simplest possible bet on truth: pixels move or they don't."*

coord-smith never reasons about a page. It clicks where it was told to click, and asks the screen whether anything changed. If the screen says no, the run fails — loudly, with evidence.

## License

MIT — see [LICENSE](./LICENSE).
