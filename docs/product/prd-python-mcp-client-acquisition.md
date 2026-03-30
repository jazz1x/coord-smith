# PRD — Python MCP Client Acquisition (Modeled-Only)

## Purpose

This PRD defines the **explicit** (code-enforceable) contract required only if
`ez-ax` chooses the optional MCP-backed boundary for OpenClaw invocation and
needs to acquire a concrete Python MCP client/session handle.

It exists to prevent transport guesswork inside that optional boundary.

Scope:

- **modeled-only** (does not release workflow execution above the benchmark
  released ceiling)
- defines how a real MCP client may be constructed **outside** released-scope
  wiring, and then injected into adapter code that is otherwise released-scope
  envelope-validating

## Precedence

1. [`docs/product/prd-e2e-orchestration.md`](./prd-e2e-orchestration.md)
2. [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
3. this PRD

Rule:

- if this PRD would imply inventing transport in released-scope wiring, the
  OpenClaw runtime PRD wins: **injection only** in released scope.

## Approval Gate

Until this PRD is explicitly approved, `ez-ax` MUST NOT:

- choose a Python MCP client library/module
- add a concrete MCP transport/client constructor to released-scope wiring
- add new environment variables for MCP transport without explicit approval

Interpretation rule:

- continuing “scaffold hardening” below `pageReadyObserved` is still allowed so
  long as it does not introduce a concrete MCP transport constructor and does
  not implicitly select a Python MCP library or its connection/auth inputs
- if the active OpenClaw boundary is not MCP-backed, this PRD is reference-only
  and must not be treated as the canonical OpenClaw contract

## Contract (Must Be Explicit Before Implementation)

The approved MCP client acquisition contract MUST specify:

### 1) Python MCP client library/module

- exact Python package name(s)
- exact import path used in `ez-ax` code
- version pinning or constraints (if required)

Packaging rule:

- once `python_package` is chosen, it MUST be added to `pyproject.toml`
  `[project].dependencies` (or another explicitly-approved dependency group)
  so CI and local installs do not rely on an out-of-band environment setup
- acquisition code MUST perform an import preflight for `import_path`
  (fail-fast before attempting to connect)
- `ImportError` from the preflight import MUST be treated as
  `ExecutionTransportError` (“client construction failure”), not as a
  validation/evidence failure

### 2) Connection inputs (and precedence)

The contract MUST declare the full set of required connection inputs and their
precedence order (highest first), for example:

1. explicit runtime entrypoint arguments
2. environment variables (explicit names)
3. (no fallback) fail-fast `ConfigError`

Transport-mode rule:

- the approval record MUST declare the MCP transport mode as one of:
  - `stdio`
  - `http`
  - `websocket`
- the approval record MUST explicitly list the required inputs for that mode
  (e.g. `command`/`args` for `stdio`, or `base_url` for `http`)

### 3) Authentication inputs (and precedence)

If MCP connection requires authentication, the contract MUST declare:

- where auth inputs come from (args/env only, no implicit discovery)
- whether any file paths or OS keychain sources are allowed (default: not
  allowed unless explicitly approved)
- how secrets are referenced (no secrets embedded in evidence or logs)

### 4) Lifecycle ownership

The contract MUST declare:

- who owns creating the client/session
- who owns closing it
- whether the adapter may assume the client is reusable across runs (default:
  no assumption; per-run injection is allowed)

### 5) Failure mapping requirements

The contract MUST declare how acquisition failures map into typed errors:

- missing required connection/auth inputs -> `ConfigError`
- client construction failure -> `ExecutionTransportError`

Rule:

- acquisition failures MUST NOT be reported as evidence/validation failures.

## Approval Checklist

Before setting `approved: true`, confirm the approval record answers:

- what exact Python package and import path will be used?
- what are the required connection inputs, and their precedence order?
- what are the required authentication inputs, and their precedence order?
- who owns opening and closing the MCP client/session handle?
- how are acquisition failures mapped into `ConfigError` vs `ExecutionTransportError`?

## Minimal Approval Record

This approval record is now explicit enough for released-scope scaffold
hardening below `pageReadyObserved`.

- `approved`: true
- `python_package`: "mcp"
- `import_path`: "mcp"
- `transport`:
  - `mode`: "stdio"
  - `inputs`:
    - `command`
    - `args`
    - `env`
    - `tool_name`
    - `timeout_seconds`
- `connection_inputs`:
  - `source_order`:
    1. explicit constructor arguments
    2. typed runtime config
    3. fail-fast `ConfigError`
  - `env_vars`: []
- `auth_inputs`:
  - `source_order`:
    1. explicit constructor arguments
    2. typed runtime config
    3. pass-through `env` for downstream MCP/OpenClaw-side credentials
  - `env_vars`: []
- `lifecycle`:
  - `owner`: "graph entrypoint"
  - `close_required`: true
  - `reusable_across_runs`: false

Approved-default rule:

- this default contract is approved for scaffold hardening and released-scope
  adapter construction below `pageReadyObserved`
- a later PRD update may override these values explicitly
- until overridden, autonomous implementation must not invent a different MCP
  package, import path, or transport mode

## Minimal Approved Constructor Shape (Template)

Once approved, the implementation MUST introduce a single, explicit constructor
boundary for “real MCP client acquisition” that:

- performs the import preflight (`import_path`)
- resolves connection/auth inputs in the approved precedence order
- constructs the MCP client/session handle
- returns a handle that satisfies the injected `McpClient` protocol expected by
  the modeled MCP-backed OpenClaw adapter

Typed error mapping (required):

- missing required connection/auth inputs -> `ConfigError`
- import preflight failure or client/session construction failure -> `ExecutionTransportError`

Approved constructor expectation:

- the smallest real MCP constructor slice may now assume:
  - Python package `mcp`
  - import path `mcp`
  - `stdio` transport mode
  - required typed inputs `command`, `args`, `env`, `tool_name`,
    `timeout_seconds`
- auth remains a pass-through concern via approved `env` input rather than a
  separate `ez-ax` transport-auth contract
- lifecycle remains owned by the graph entrypoint, which creates and closes the
  MCP client/session handle before or around released-scope adapter injection

## Stop Condition

If implementation work needs a concrete MCP client constructor and this PRD is
not yet approved, autonomous work MUST stop and request PRD approval rather
than guessing transport details.

## Repository Status (Non-Normative)

As of this PRD revision, the repository does not declare any MCP client library
in `pyproject.toml`. Approval should update both:

- this PRD approval record (package/import/inputs/lifecycle)
- `pyproject.toml` dependency declarations
