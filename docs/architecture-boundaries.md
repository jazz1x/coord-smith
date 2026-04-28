# ez-ax Architecture Boundaries

## Purpose

This document defines who owns what and who calls whom. It exists because
naming confusion between OpenClaw, ez-ax, and PyAutoGUI caused repeated
implementation misdirection.

## System Actors

```
OpenClaw  (external caller)
    |
    |  invokes via skill / CLI
    v
ez-ax CLI  (`ez-ax` console script)
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
| **OpenClaw** | External orchestration system | Task selection, high-level workflow | ez-ax CLI (via skill) | (external trigger) |
| **ez-ax** | Python orchestration runtime | CUA engine (PyAutoGUI), mission graph, validation, stopping | PyAutoGUI | OpenClaw (via CLI) |
| **PyAutoGUI** | OS-level CUA engine | `click(x, y)` + `screenshot()` | OS display server | ez-ax |

### Key Facts

- **OpenClaw calls ez-ax.** ez-ax does not call OpenClaw.
- **OpenClaw has no MCP server.** It invokes ez-ax through skill-based CLI execution.
- **ez-ax owns the CUA engine.** PyAutoGUI runs inside ez-ax, not inside OpenClaw.
- **Communication is ping-pong:** OpenClaw invokes `ez-ax` CLI, ez-ax writes
  results to stdout and `artifacts/`, OpenClaw reads them and decides next step.

## Integration Pattern

```
1. OpenClaw decides to run a mission
2. OpenClaw invokes: ez-ax --session-ref ... --target-page-url ...
3. ez-ax runs the released-scope LangGraph (12 missions, ceiling = run_completion).
4. Each node calls PyAutoGUIAdapter.execute():
   - pyautogui.click(x, y)
   - pyautogui.screenshot()
   - writes action-log JSONL to artifacts/
5. ez-ax exits, leaving artifacts and stdout output
6. OpenClaw reads artifacts, decides next action
7. Repeat (ping-pong)
```

## Code Namespace Clarification

### `adapters/execution/` (formerly `adapters/openclaw/`)

This package defines ez-ax's **internal execution adapter protocol**. It is
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
protocol defines ez-ax's internal pluggable execution backend. The rename to
`adapters/execution/` reflects this correction.

| Old Name | New Name | Reason |
|----------|----------|--------|
| `OpenClawAdapter` | `ExecutionAdapter` | It is ez-ax's internal protocol, not an OpenClaw API |
| `OpenClawExecutionRequest` | `ExecutionRequest` | Request is from ez-ax graph to its own adapter |
| `OpenClawExecutionResult` | `ExecutionResult` | Result is from adapter back to ez-ax graph |
| `adapters/openclaw/` | `adapters/execution/` | Package defines execution protocol, not OpenClaw client |
