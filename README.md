# ez-ax

> Python CUA runtime — deterministic OS-coordinate clicking, driven by an external LLM

![python](https://img.shields.io/badge/python-3.14-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![tests](https://img.shields.io/badge/tests-703%20passing-brightgreen)
![runtime](https://img.shields.io/badge/runtime-LLM--free-orange)

**ez-ax** is the *hands*. The *head* — an external LLM such as OpenClaw — decides what to click; ez-ax executes those decisions on the OS as coordinate clicks and screenshot evidence. Reasoning lives outside the runtime; the runtime itself contains zero LLM calls.

A run is a 12-mission pipeline driven by a LangGraph state machine. Each mission produces an evidence envelope (action-log JSONL, screenshots, transition diffs) before the next mission is allowed to start. No browser internals (Playwright / CDP / Chromium) are touched — only OS-level coordinates and pixels.

[한국어](./README.ko.md)

## Pipeline

The runtime walks 12 missions in order. Every mission is deterministic and produces evidence on disk before the next mission is allowed to start.

| Mission | Role |
|---------|------|
| `attach_session` | Attach to an existing browser session via session-ref. |
| `prepare_session` | Verify expected auth state and target page URL. |
| `benchmark_validation` | Validate the run against the recorded benchmark. |
| `page_ready_observation` | Confirm the page is ready via screenshot evidence. |
| `sync_observation` | Sync local state with the page state. |
| `target_actionability_observation` | Confirm the target is actionable. |
| `armed_state_entry` | Enter the armed state ready for click dispatch. |
| `trigger_wait` | Wait for the deterministic trigger signal. |
| `click_dispatch` | Execute the click — payload coords, recipe coords, or recipe image. |
| `click_completion` | Capture post-click evidence (screenshot, transition diff). |
| `success_observation` | Verify the click produced the expected state change. |
| `run_completion` | Close the run with a sealed status code. |

Each mission emits a fixed past-tense action key (e.g. `click_dispatch` → `click-dispatched`) so the action log is machine-greppable.

```
 OpenClaw (external LLM)
      │  decisions, coords, image refs
      ▼
 ez-ax CLI ──▶ LangGraph state machine ──▶ 12 missions
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

### 1. Bootstrap the project

```bash
git clone https://github.com/<your-org>/ez-ax.git
cd ez-ax
uv sync --extra dev
```

`uv` will resolve and provision Python 3.14 automatically based on `requires-python` in `pyproject.toml`. If your system Python is older, install it first:

```bash
uv python install 3.14
```

### 2. Verify

```bash
uv run pytest -q                # 703 passed, 1 skipped, 4 deselected
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
ez-ax --click-recipe ./recipe.json \
      --session-ref my-session \
      --expected-auth-state authenticated \
      --target-page-url https://example.com \
      --site-identity example
```

A minimal coordinate recipe:

```json
{
  "version": 1,
  "missions": {
    "click_dispatch": {"x": 800, "y": 500}
  }
}
```

A layout-tolerant image recipe (recommended):

```json
{
  "version": 1,
  "missions": {
    "click_dispatch": {
      "image": "templates/buy-button.png",
      "confidence": 0.9,
      "grayscale": false
    }
  }
}
```

**Coordinate priority**: payload (OpenClaw) → recipe coord → recipe image → no-click.

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

```json
{
  "missions": {
    "click_dispatch": {
      "image": "templates/buy.png",
      "verify_transition": true,
      "transition_threshold": 0.02,
      "transition_region": [0, 100, 1920, 800]
    }
  }
}
```

Pre-click screenshot → click → post-click screenshot → `PIL.ImageChops.difference` bbox area / region area > threshold ⇒ pass. Below the threshold raises `PageTransitionNotDetected`.

### Post-click signal polling (optional, off by default)

```json
{
  "missions": {
    "click_dispatch": {
      "image": "templates/buy.png",
      "post_click_signal": {
        "image": "templates/loading-spinner.png",
        "confidence": 0.85,
        "timeout": 5.0,
        "interval": 0.1
      }
    }
  }
}
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

GitHub Actions runs Python 3.14 only (Ubuntu, xvfb for pyautogui import) plus a separate pre-commit job.

## Invariants

ez-ax has four hard invariants. Anything that violates them is rejected at PR time:

1. **LLM-free runtime.** No model calls inside ez-ax. Reasoning lives in OpenClaw.
2. **Browser-internals forbidden.** No Playwright, no CDP, no Chromium driver. OS coordinates and pixels only.
3. **`pyautogui.FAILSAFE = True`** is enforced in `PyAutoGUIAdapter.__init__`. Slamming the cursor into a screen corner aborts the run instantly.
4. **Coordinate priority is fixed.** payload → recipe coord → recipe image → no-click. Never the other way.

OpenCV is allowed because it is a deterministic pixel-matching library — neither LLM nor browser.

## Project structure

```
src/ez_ax/
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

- **ez-ax** — *easy axes*: the runtime swings two axes (coordinates and pixels) and asks no further questions.

## Triad

ez-ax fits between two sibling tools — independent processes, connected only through artifacts on disk:

```
OpenClaw (think)  ──▶  ez-ax (act)  ──▶  evidence envelope (record)
   external LLM        deterministic        JSONL + PNG on disk
                       OS-coord click
```

The split is deliberate: every component must be replaceable without touching the others.

## Footnote

> *"A click is the simplest possible bet on truth: pixels move or they don't."*

ez-ax never reasons about a page. It clicks where it was told to click, and asks the screen whether anything changed. If the screen says no, the run fails — loudly, with evidence.

## License

MIT — see [LICENSE](./LICENSE).
