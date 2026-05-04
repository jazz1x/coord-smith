# ez-ax Current State

## Purpose

This document is the current implementation snapshot. It is intentionally
changeable and subordinate to `docs/prd.md`.

## Snapshot

- Python 3.14 pinned (`requires-python = ">=3.14,<3.15"`).
- Released ceiling: `runCompletion` — all 12 missions released.
- Test count: 727 passing, 1 skipped, 4 deselected (`-m real`).
- Static checks: ruff clean, mypy strict clean, pre-commit clean.

## Architecture

- **LLM-free runtime.** The ez-ax runtime graph contains no LLM inference.
  Each LangGraph node is deterministic: state setup, adapter call, evidence
  collection.
- **CUA engine.** `src/ez_ax/adapters/pyautogui_adapter.py` implements
  `ExecutionAdapter.execute()` using `pyautogui.click()` /
  `pyautogui.screenshot()` only. Wired via
  `src/ez_ax/graph/pyautogui_cli_entrypoint.py` (`ez-ax` console script).
- **Browser-internals forbidden.** Playwright, CDP, and similar drivers are
  not part of the execution backend. OS-level coordinates and pixels only.
- **Visual click verification.** Image-template click via OpenCV,
  optional pre/post page-transition diff via `PIL.ImageChops`, optional
  post-click signal polling via `pyautogui.locateCenterOnScreen`. All
  three are deterministic and default-off in click recipes.

## Scope

Released:

- Released-scope graph and entrypoint wiring up to `runCompletion`.
- `ExecutionAdapter` protocol with `PyAutoGUIAdapter` as the sole
  implementation in the released path.
- Evidence envelope, checkpoint comparability, transition reporting.
- Typed error hierarchy and mission anchor mapping.
- `ez-ax` console script registered in `pyproject.toml`.

## Source of ongoing truth

For domain-specific contracts, defer to source code under `src/ez_ax/`.
Repository base config (`pyproject.toml`, `.pre-commit-config.yaml`) is
authoritative for tooling.
