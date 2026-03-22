# PRD — OpenClaw Computer-Use Runtime

## Purpose

This PRD defines the runtime architecture and autonomous-work contract for
introducing `OpenClaw` computer-use execution into `ez-ax`.

It exists so an agent can determine, from documentation alone:

- why the runtime exists
- what "good" looks like
- what counts as complete
- what must be released versus only modeled
- which phase, milestone, and anchor the current task belongs to
- what evidence and RAG updates are required before a task may be considered done

This PRD does not replace
[`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md).

Relationship rule:

- `prd-e2e-orchestration.md` remains the source of truth for Phase 1 benchmark
  scope and release ceiling
- this PRD defines how computer-use runtime work is allowed to be designed and
  progressed under that scope
- if the two documents disagree, the narrower released boundary wins

## North Star

Build a deterministic computer-use orchestrator in which:

- `OpenClaw` is the only browser-facing execution actor
- `ez-ax` owns orchestration, state transitions, evidence normalization,
  checkpointing, and stop-reason classification
- the system can use hybrid evidence rather than a single brittle truth source
- repeated runs produce comparable artifacts and diagnosable failure outcomes
- an autonomous agent can continue work from PRD and RAG state without relying on
  hidden prior context

North-star rule:

- the north star is broader than the current released workflow ceiling
- autonomous work may move toward this direction only through the phases and
  anchors defined below

## Primary Goal

Introduce a hybrid `OpenClaw` computer-use runtime that is:

- execution-safe
- evidence-driven
- replayable enough for E2E validation
- explicit about fallback behavior
- explicit about what is released versus only modeled

## Product Goals

The runtime must:

- keep `OpenClaw` as the only browser-facing actor
- keep `ez-ax` orchestration-centric rather than browser-control-centric
- use a hybrid evidence model:
  DOM/text/clock/action-log as primary typed signals, screenshot/vision as
  supporting or fallback evidence, coordinates only as a constrained last resort
- make ambiguous state a typed stop condition, not an implicit success
- produce artifacts that are comparable across repeated runs
- leave enough structured work history that future agents can continue without
  rebuilding context manually

The runtime must not:

- treat screenshot evidence alone as product truth
- treat coordinate clicks alone as trustworthy state truth
- use anti-detection logic
- blur modeled runtime behavior into released workflow behavior
- rely on undocumented operator intuition for release decisions

## Completeness

This runtime is complete only when all of the following are true:

- actor boundaries are explicit and enforced
- evidence priority and fallback rules are explicit
- phase transitions are diagnosable and comparable
- stop reasons are deterministic under ambiguity
- E2E validation can distinguish stable from flaky behavior
- `work-rag.json` can be continued by a later agent without hidden context
- `rag.json` captures mistakes, failed assumptions, and durable lessons

Completeness rule:

- "it runs" is not enough
- "it can be diagnosed, resumed, and judged consistently" is required

## Completion Criteria

The runtime should be considered complete only when:

- the runtime boundary contract is approved
- released-path computer-use observation is stable enough to stop at the current
  released ceiling
- evidence normalization is typed and repeatable
- fallback behavior is explicit and bounded
- stop and retry decisions are deterministic
- success and completion artifacts remain comparable
- E2E validation passes the declared release gate
- phase and milestone summaries are compressed into `work-rag.json`
- durable lessons are promoted into `rag.json`

## Autonomous-Readiness Contract

This PRD set should be sufficient for autonomous work.

Autonomous-readiness means:

- an agent can identify current phase, milestone, anchor, invariant, and next
  action from PRD plus RAG only
- an agent can tell what is in bounds without asking for hidden context
- an agent can tell what evidence must exist before claiming completion
- an agent can tell when to stop rather than invent a new scope

Autonomous-readiness rule:

- if an agent cannot safely continue from the PRD set and the two RAG files, the
  PRD set is incomplete and must be improved before more implementation work

## Hybrid Evidence Decision

The runtime uses a hybrid evidence model.

Priority:

1. typed DOM/text/clock/action-log signals
2. screenshot or vision evidence as support or fallback
3. coordinate action only when deterministic targeting has already been
   established

Value judgment:

- DOM/text/clock/action-log signals are best for deterministic classification
- screenshot evidence is valuable because it preserves what a computer-use actor
  actually saw and gives fallback when structured signals are insufficient
- coordinate-only operation is too brittle to be the default truth model for
  release-grade E2E work

Decision rule:

- screenshots improve runtime robustness and debugging value
- coordinates remain execution primitives, not default truth sources
- release decisions must be made from evidence aggregation, not from any single
  fallback primitive

## RAG Operating Model

Two RAG files are required.

### `work-rag.json`

Purpose:

- canonical current-tense working memory for the active mission

Contents must include:

- current goal
- current phase, milestone, and anchor
- invariant
- next action
- approved scope ceiling
- latest evidence references
- compression summaries at phase or milestone boundaries

Rule:

- update during work
- compress at milestone completion
- compress again at phase completion

### `rag.json`

Purpose:

- durable trial-and-error memory and reusable lessons

Contents must include:

- failed assumptions
- false positives and false negatives
- flaky E2E observations
- fallback misuses
- boundary mistakes
- lessons that could later become skills, prompts, or agent heuristics

Rule:

- do not use `rag.json` as a duplicate of `work-rag.json`
- promote only lessons with future reuse value

## Autonomous Work Loop

Every autonomous task should follow this loop:

1. read the benchmark PRD, runtime PRD, relevant sub-PRD, `work-rag.json`, and
   `rag.json`
2. declare phase, milestone, anchor, invariant, and next action
3. choose the highest-value in-bounds task for the current anchor
4. execute only within the current released or modeled boundary allowed by the
   PRD set
5. gather evidence and classify the result
6. update `work-rag.json`
7. if the task reveals a reusable lesson, promote it into `rag.json`
8. run the smallest trustworthy validation step for the task
9. commit the task once validation and required RAG updates are complete
10. if the task closes a milestone or phase, compress `work-rag.json`
11. stop if the next step would widen scope, blur released versus modeled
   behavior, or exceed the current anchor

Autonomous work is not considered valid if this loop cannot be followed from the
document set alone.

## Autonomous Validation Checklist

The PRD set is in a healthy autonomous state only if the answer to each item is
"yes":

- can the current phase, milestone, and anchor be identified from docs and RAG
  only?
- can an agent tell what the next highest-value task is without inventing a new
  scope?
- can an agent tell what counts as completion for the current anchor?
- can an agent tell what evidence is required?
- can an agent tell that each autonomous task must end with validation and a
  commit?
- can an agent tell what must be compressed into `work-rag.json`?
- can an agent tell what belongs in `rag.json` instead?
- can an agent tell when to stop?

If any item is "no", the PRD set must be improved before further implementation
work.

## Operational Example

Example: a future agent starts a new runtime task after reading only the PRD set
and the two RAG files.

Expected reasoning sequence:

1. read [`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md) and confirm
   that the released workflow ceiling still stops at `pageReadyObserved`
2. read `work-rag.json` and see that the current runtime phase is still
   `Phase 0 — Runtime Boundary Definition`
3. read this PRD and confirm the current next runtime anchor after Phase 0
   remains the released gate anchor `pageReadyObserved`
4. read the evidence-model PRD and conclude that DOM/text/clock/action-log
   signals should be primary while screenshot is fallback support
5. choose a task that improves released-path computer-use observation without
   widening release beyond `pageReadyObserved`
6. update `work-rag.json` during the task
7. if the task reveals a durable mistake, promote that lesson into `rag.json`
8. validate the task and commit it before choosing another autonomous task
9. stop if the next step would claim release above the released ceiling

This example is intentionally simple.

Rule:

- if a future agent cannot reproduce a similar sequence from the document set,
  the PRD set still needs improvement

## Release Boundary

The current released workflow ceiling does not change here.

Released workflow ceiling:

- still stops at `pageReadyObserved` unless the orchestration PRD is explicitly
  updated

Modeled runtime work may exist above that ceiling, but it must not be described
as released behavior.

## OpenClaw Interface Contract (Released Scope)

This section defines the minimum, released-scope contract between `ez-ax`
(orchestration) and `OpenClaw` (execution) for the current approved benchmark
scope.

Scope rule:

- this contract must not imply workflow release above `pageReadyObserved`
- it exists to keep payload and evidence conventions explicit enough that
  implementation hardening does not invent product-level structure

### Execution Request

The `OpenClaw` execution request must contain:

- `mission_name`: one of the browser-facing mission names declared in
  [`prd-runtime-missions.md`](./prd-runtime-missions.md)
- `payload`: a JSON-serializable object map (a dict-like payload)

Released-scope guard:

- orchestration must reject any request whose `mission_name` falls outside the
  approved scope ceiling (including modeled missions)

Payload rules:

- payload keys must be stable enough to support comparable evidence and logs
- payload may be empty when the mission does not require additional execution
  inputs
- payload must not include secrets; sensitive values should be referenced by a
  durable `ref` instead

Minimum released-mission payload conventions:

- `attach_session`:
  - `session_ref`: stable identifier for the operator-prepared OpenClaw-managed
    session to attach to (no session discovery implied)
  - `expected_auth_state`: stable label for the expected auth state (e.g.
    `authenticated`)
- `prepare_session`:
  - `target_page_url`: the released-path target page URL
  - `site_identity`: the released-path site identity label (e.g. `interpark`)
- `benchmark_validation`:
  - `target_page_url`: the released-path target page URL (same value as above)
- `page_ready_observation`:
  - payload may be empty; page-ready observation should prefer evidence signals
    over extra instruction fields

Note:

- `attach_session` and session attachment details remain operator-prepared in
  the current released path; do not treat automated login recovery or session
  discovery as released behavior.

### Execution Result

The `OpenClaw` execution result must contain:

- `mission_name`: must match the request `mission_name`
- `evidence_refs`: one or more evidence reference strings

Evidence reference rules:

- evidence refs must be stable enough to compare runs without operator
  intuition
- evidence refs must not embed secrets; they may point to stored artifacts
  (files, logs, structured dumps) by reference
- evidence refs should prefer typed-signal artifacts (DOM/text/clock/action-log)
  over screenshot-only evidence unless the runtime explicitly recorded that a
  fallback path was used

### Adapter Instantiation And Transport (Released Scope)

In the current released scope (up to `pageReadyObserved`), `ez-ax` treats
OpenClaw as an external execution actor with an injected adapter.

Contract:

- released-scope orchestration code MUST accept an `OpenClawAdapter` instance
  from the caller (graph entrypoint or test harness) and MUST NOT assume a
  particular transport (HTTP, local process, socket, RPC) exists
- released-scope user-facing wiring MUST NOT "invent" a transport by creating a
  network client without an explicit PRD contract for connection/auth/config
  inputs
- if a future CLI or service entrypoint constructs a concrete adapter, that
  instantiation contract MUST be written and approved explicitly before being
  treated as released-path execution support

Scope rule:

- adapter injection enables scaffold hardening and deterministic validation
  below the ceiling without claiming that OpenClaw transport is already part of
  the released product path

#### OpenClaw Invocation Boundary Contract (Modeled)

This section defines the concrete instantiation and invocation contract
required to construct a real `OpenClawAdapter` below the released ceiling
`pageReadyObserved`.

This contract enables released-scope adapter construction, invocation, and
request/response validation only. It does not release any modeled mission above
`pageReadyObserved`.

##### Boundary Shape

`ez-ax` does not become the browser-facing actor. `ez-ax` only owns the
orchestration-side adapter boundary that invokes `OpenClaw`.

Rules:

- `OpenClaw` remains the only browser-facing execution actor
- `ez-ax` may contain an `OpenClawAdapter` protocol and concrete adapter
  implementation
- the concrete adapter may invoke OpenClaw through an approved boundary such
  as:
  - MCP-backed invocation
  - in-engine injected implementation
  - another explicitly approved boundary
- no concrete boundary may be invented outside this contract

##### Approved Invocation Mode

The approved invocation mode for released-scope implementation is:

- MCP-backed OpenClaw adapter

Interpretation:

- `ez-ax` constructs a concrete `OpenClawAdapter`
- that adapter invokes OpenClaw through an MCP-facing boundary
- browser-facing authority remains with OpenClaw, not with `ez-ax`

Non-approved alternatives for released-scope implementation:

- direct HTTP client
- direct RPC client
- direct browser automation inside `ez-ax`

These may exist only as modeled examples unless explicitly approved later.

##### Adapter Construction Inputs

A concrete MCP-backed `OpenClawAdapter` must be constructible from explicit
typed inputs.

Required construction inputs:

- `mcp_server_name`: the MCP server identity that exposes OpenClaw execution
- `tool_name`: the MCP tool name used for released-scope execution
- `default_timeout_seconds`: request timeout for one released-scope invocation
- `retry_policy`: typed retry settings for transient invocation failures

Optional construction inputs:

- `session_label`: released-path session identity hint for operator-prepared
  attachment flows
- `config_source`: typed configuration object or settings provider
- injected MCP client/session handle for tests or runtime composition

Rules:

- construction must fail fast if required MCP execution inputs are absent
- the adapter must not guess server or tool names
- the adapter must not silently fall back to another invocation mode

##### Configuration Source And Precedence

The adapter resolves its invocation settings in this order:

1. explicit constructor arguments
2. approved typed config object from the runtime entrypoint
3. fail-fast configuration error

Rules:

- released-scope wiring must not depend on undocumented implicit defaults
- environment-variable use is allowed only if the runtime PRD or validation
  contract explicitly approves the variable names
- if a required MCP invocation setting is missing, adapter construction fails
  immediately

##### Authentication Responsibility

Authentication is split by boundary.

`ez-ax` side responsibilities:

- provide only the released-scope adapter construction inputs explicitly
  allowed by this contract
- surface typed configuration errors when required invocation settings are
  missing

OpenClaw/MCP side responsibilities:

- own any browser/session/auth behavior needed for actual browser-facing
  execution
- own any downstream credentials or connection state required beyond the
  adapter boundary

Rules:

- `ez-ax` must not invent browser-auth behavior
- if MCP invocation itself requires auth/config, that requirement must be
  explicit in the adapter construction contract
- missing invocation auth/config must fail fast as a configuration error

##### MCP Client Acquisition (Modeled-Only)

In released scope, `ez-ax` MUST NOT construct a concrete MCP client or assume
any transport wiring exists.

Source of truth:

- [`prd-python-mcp-client-acquisition.md`](./prd-python-mcp-client-acquisition.md)

Modeled contract:

- the MCP-backed OpenClaw adapter MUST accept an injected `McpClient`
  (in-process handle) from the runtime entrypoint or test harness
- the injected `McpClient` owns all MCP connection/auth/session lifecycle
  outside the adapter boundary
- `ez-ax` MUST NOT read environment variables or config files to construct a
  concrete MCP client unless a separate PRD explicitly approves:
  - the exact Python MCP client library/module
  - the required connection inputs (and their precedence)
  - any required auth inputs
  - the allowed environment variable names

Stop rule:

- if work requires adding a real MCP transport/client constructor in `ez-ax`,
  stop and harden PRDs first; do not guess a library, endpoint, or auth surface

##### Invocation Request Envelope

The concrete adapter sends one typed released-scope request through the
approved MCP boundary.

Required request fields:

- `mission_name`
- `payload`
- `run_root`
- `scope_ceiling`
- `request_id`

Rules:

- `mission_name` must be one of the released-scope browser-facing missions
  (including `attach_session`, `prepare_session`, `benchmark_validation`,
  `page_ready_observation`)
- `run_root` must already exist before invocation
- `scope_ceiling` must equal `pageReadyObserved`
- `request_id` must be generated by the orchestration side for traceability
- the adapter must reject requests above the released ceiling before invoking
  OpenClaw

The concrete MCP tool payload may wrap these fields differently, but the
adapter must preserve this logical envelope at the `ez-ax` boundary.

##### Invocation Response Envelope

The concrete adapter expects one typed released-scope response from the
approved MCP boundary.

Required response fields:

- `mission_name`
- `status`
- `evidence_refs`
- `observations`

Optional response fields:

- `failure`
- `timing`
- `request_id`

Rules:

- `mission_name` must match the request mission
- `status` must be one of `success | failure | pending`
- `evidence_refs` must satisfy the released-scope evidence contract
- `failure` is required when `status == "failure"`
- `request_id`, when present, must match the request

##### `observations` Schema (Released Scope)

In released scope (up to `pageReadyObserved`), the MCP response `observations`
field must be machine-validated so adapter behavior is deterministic even when
observations are later ignored by released-path orchestration.

Schema (released scope):

- `observations` MUST be a JSON object (dict)
- the set of `observations` keys MUST equal the set of `evidence_refs`
  (no missing refs, no extra refs)
- each `observations[{ref}]` MUST be a JSON object with:
  - `ref`: string, MUST equal the map key and MUST equal `{ref}`
  - `kind`: string, MUST equal the `{kind}` parsed from `ref`
  - `key`: string, MUST equal the `{key}` parsed from `ref`
  - `value`: any JSON-serializable value (may be `null`)
  - `ts`: optional ISO-8601 timestamp string (when the observation has a
    stable timestamp)

Interpretation rule:

- `observations` provide supporting structured content for debugging,
  comparison, and later evidence normalization, but released-scope readiness and
  ceiling-stop validation still rely on `evidence_refs` and resolvable
  artifacts, not on `observations.value` content alone

##### MCP Mapping Requirements

The approved MCP-backed adapter contract must explicitly define:

- the MCP server name used for OpenClaw execution
- the MCP tool name used for released-scope mission invocation
- the tool input field mapping from adapter request envelope to MCP payload
- the tool output field mapping from MCP payload to adapter response envelope

Rules:

- these names and mappings must be explicit before concrete adapter
  implementation is treated as released-scope hardening
- placeholder names may be modeled in docs, but they are not implementation
  authority until approved

Released-scope settings rule:

- `ez-ax` MUST NOT assume default MCP server/tool names
- the MCP server name is the configured `mcp_server_name` construction input
- the MCP tool name is the configured `tool_name` construction input

Tool input mapping (released scope):

- adapter request envelope field -> MCP tool input field:
  - `mission_name` -> `mission_name` (string)
  - `payload` -> `payload` (JSON object)
  - `run_root` -> `run_root` (string filesystem path)
  - `scope_ceiling` -> `scope_ceiling` (string, MUST equal `pageReadyObserved`)
  - `request_id` -> `request_id` (string)

Tool output mapping (released scope):

- MCP tool output field -> adapter response envelope field:
  - `mission_name` -> `mission_name` (string)
  - `status` -> `status` (string: `success | failure | pending`)
  - `evidence_refs` -> `evidence_refs` (array of strings)
  - `observations` -> `observations` (JSON object; see `observations` schema)
  - `failure` -> `failure` (optional; required when `status == "failure"`)
  - `timing` -> `timing` (optional)
  - `request_id` -> `request_id` (optional; when present MUST match request)

Strictness rule:

- released-scope adapter validation MUST treat missing required fields as
  schema violations
- released-scope adapter validation MUST reject non-object tool outputs
  (including arrays or plain strings) as malformed transport payloads

##### Timeouts And Retries

- invocation timeout must be explicit
- retry policy must be explicit
- retries are allowed only for transient invocation failures
- retries are not allowed for:
  - schema validation failure
  - released-scope contract violation
  - mission-above-ceiling rejection
  - evidence contract failure

##### Error Mapping

Invocation failures must map into typed adapter-facing errors.

- missing server or tool configuration -> `ConfigError`
- missing required invocation settings -> `ConfigError`
- mission above released ceiling -> `FlowError`
- MCP invocation failure -> `ExecutionTransportError`
- malformed MCP response payload -> `ExecutionTransportError`
- response schema mismatch -> `ValidationError`
- invalid or insufficient `evidence_refs` -> `ValidationError`
- mission mismatch between request and response -> `FlowError`

##### Released-Scope Constraint

This contract is only for released-scope execution through:

- `attach_session`
- `prepare_session`
- `benchmark_validation`
- `page_ready_observation`

The adapter must reject any mission or ceiling that would imply behavior above
`pageReadyObserved`.

##### Approval Note

Until this section is explicitly approved, any concrete `OpenClawAdapter`
implementation remains modeled-only scaffolding and must not be presented as
released-path execution.

### `evidence_refs` Schema (Released Scope)

In released scope (up to `pageReadyObserved`), evidence refs must be
machine-validated without operator interpretation.

Schema:

- each evidence ref MUST be a string in the form:
  - `evidence://{kind}/{key}`
- `{kind}` MUST be one of:
  - `dom`
  - `text`
  - `clock`
  - `action-log`
  - `screenshot`
  - `coordinate`
- `{key}` MUST be a stable, kebab-case identifier with no whitespace

Example valid refs:

- `evidence://dom/page-shell-ready`
- `evidence://text/session-viable`
- `evidence://clock/server-time`
- `evidence://action-log/enter-target-page`
- `evidence://screenshot/page-ready-fallback`

Validation rule:

- released-scope `ez-ax` validation may treat any ref that does not match this
  schema as invalid evidence for readiness/ceiling-stop judgment

### Action-Log Ref Target + Storage Semantics (Released Scope)

Released-scope `evidence://action-log/*` refs must be resolvable to concrete,
reviewable artifacts so stop/readiness decisions do not depend on operator
intuition.

Definitions:

- run root:
  the filesystem root directory that contains artifacts for a single run
  (chosen by `ez-ax`, not by `OpenClaw`)
- action-log artifact:
  a persisted, line-delimited JSON log file stored under the run root

Storage contract:

- for each released-scope ref `evidence://action-log/{key}`, `ez-ax` MUST
  persist an action-log artifact at:
  - `artifacts/action-log/{key}.jsonl` (relative to the run root)
- the artifact MUST resolve to an existing file under the run root
- the artifact MUST be UTF-8 text
- the artifact SHOULD contain one JSON object per line (JSONL)
- released-scope validation MAY ignore blank lines or malformed non-JSON lines,
  but MUST still be able to find at least one schema-valid JSON object line for
  deterministic readiness/ceiling-stop judgment

Minimum per-line fields (schema-lite):

- `ts`: ISO-8601 timestamp string
- `mission_name`: mission identifier string (e.g. `page_ready_observation`)
- `event`: stable kebab-case event identifier string
- `detail`: optional string (diagnostic, must not embed secrets)

Schema-lite enforcement notes:

- `ts` MUST be parseable as ISO-8601 (timezone offsets allowed; `Z` allowed)
- `mission_name` MUST be a known mission identifier from
  [`prd-runtime-missions.md`](./prd-runtime-missions.md) and MUST be
  whitespace-normalized (no leading/trailing whitespace)
- `event` MUST be kebab-case with no whitespace and MUST be
  whitespace-normalized (no leading/trailing whitespace)
- when present, `detail` MUST be a string and SHOULD be whitespace-normalized
  (no leading/trailing whitespace) so it stays comparable across runs

Interpretation rule:

- `evidence://action-log/{key}` claims only that the corresponding artifact file
  exists and contains events; it does **not** by itself claim any modeled
  post-ceiling workflow stage occurred
- validation may treat missing or unreadable action-log artifacts as missing
  required evidence for released-scope readiness/ceiling-stop judgment
- for deterministic association, released-scope validation SHOULD require that
  the action-log artifact contains at least one schema-valid JSON line whose
  `event` equals `{key}` (for the corresponding `evidence://action-log/{key}`
  ref)

### Per-Mission Minimum Evidence Keys (Released Scope)

The following keys are the **minimum** required evidence refs that make
released-scope readiness and ceiling-stop judgment deterministic.

Rule:

- each released mission MUST produce **either** the primary minimum set **or**
  the fallback minimum set
- fallback sets are allowed only when primary typed signals are missing,
  partial, or contradictory

#### Mission: `prepare_session`

Primary minimum:

- `evidence://text/session-viable`
- `evidence://action-log/prepare-session`

Fallback minimum:

- `evidence://screenshot/prepare-session-fallback`
- `evidence://text/fallback-reason`
- `evidence://action-log/prepare-session`

#### Mission: `benchmark_validation`

Primary minimum:

- `evidence://action-log/enter-target-page`
- `evidence://dom/target-page-entered`

Fallback minimum:

- `evidence://action-log/enter-target-page`
- `evidence://screenshot/target-page-entered-fallback`
- `evidence://text/fallback-reason`

#### Mission: `page_ready_observation`

Primary minimum:

- `evidence://dom/page-shell-ready`
- `evidence://action-log/release-ceiling-stop`

Fallback minimum:

- `evidence://screenshot/page-shell-ready-fallback`
- `evidence://text/fallback-reason`
- `evidence://action-log/release-ceiling-stop`

Determinism rule:

- `evidence://action-log/release-ceiling-stop` is mandatory whenever the system
  claims it stopped intentionally at the released ceiling
- validators must log a typed failure referencing `artifacts/action-log/release-ceiling-stop.jsonl`
  (including the path and expected fields) when that artifact cannot be read or parsed,
  so operators can replay missing-artifact scenarios without guessing
- failure messages for missing or unreadable release-ceiling artifacts should mention
  the artifact path (`artifacts/action-log/release-ceiling-stop.jsonl`), the expected
  typed fields (`event`, `mission_name`, `ts`), and the relevant release-ceiling PRDs
  (`docs/product/prd-openclaw-e2e-validation.md`, `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-evidence-model.md`, `docs/product/prd-python-validation-contract.md`)
  so future agents can replay the determinism chain without inferring intent.
- validators must also resolve the artifact at `artifacts/action-log/release-ceiling-stop.jsonl`
  under the run root and confirm it contains at least one JSON line whose typed
  fields include `event: release-ceiling-stop`, `mission_name: page_ready_observation`,
  and an ISO-8601 `ts` so future evidence viewers can reproduce the ceiling stop
  without inferring behavior from missing artifacts
- crosswalk rule:
- when `page_ready_observation` release-ceiling determinism is discussed, restate
  the artifact path, the typed fields (`event`, `mission_name`, `ts`), and every
  release-ceiling PRD
  (`docs/product/prd-openclaw-e2e-validation.md`, `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-evidence-model.md`, `docs/product/prd-python-validation-contract.md`)
  so this mission-level narrative stays explicitly tied to the typed determinism chain.

#### Mission: `attach_session`

Primary minimum:

- `evidence://text/session-attached`
- `evidence://text/auth-state-confirmed`
- `evidence://action-log/attach-session`

Fallback minimum:

- `evidence://screenshot/attach-session-fallback`
- `evidence://text/fallback-reason`
- `evidence://action-log/attach-session`

### Legacy Note

Evidence ref conventions below are retained for readability, but released-scope
determinism uses the schema and minimum keys above.

Evidence ref conventions (recommended, not yet enforced as a release gate):

- use a stable scheme prefix such as `evidence://`
- include enough structure to associate the ref to a mission and step

Examples:

- `evidence://dom/page-shell-ready`
- `evidence://text/page-title`
- `evidence://clock/server-time`
- `evidence://action-log/navigation`
- `evidence://screenshot/page-ready-fallback`

## Phase Map

### Phase 0 — Runtime Boundary Definition

Goal:

- define actor boundary
- define evidence hierarchy
- define PRD and RAG operating rules

Primary milestone:

- runtime contract is explicit enough for autonomous continuation

Primary anchor:

- `runtimeContractApproved`

Done when:

- this PRD and its sub-PRDs are sufficient for autonomous continuation
- `work-rag.json` and `rag.json` schemas exist
- completion and stop criteria are explicit

### Phase 1 — Released Observation Reliability

Goal:

- connect computer-use operation to the currently released path
- prove observation reliability through the released ceiling

Primary milestone:

- computer-use observation can attach, enter the page, and stop at the released
  ceiling with typed evidence

Primary anchor:

- `pageReadyObserved`

Done when:

- released-path observation is diagnosable
- screenshot fallback is bounded and explicit
- release claim remains limited to the released ceiling

### Phase 2 — Evidence Normalization

Goal:

- normalize hybrid evidence into typed comparable artifacts

Primary milestone:

- runtime evidence can be aggregated deterministically

Primary anchor:

- `typedEvidenceComparable`

Done when:

- structured signals and screenshot fallback are merged by explicit rules
- evidence conflicts produce typed stop reasons

### Phase 3 — Deterministic Stop And Retry

Goal:

- define stop, retry, and ambiguity handling

Primary milestone:

- ambiguous states resolve to deterministic stop or retry rules

Primary anchor:

- `deterministicStopReasonEstablished`

Done when:

- stop reasons are typed
- retry rules are bounded
- ambiguity never silently degrades into success claims

### Phase 4 — Modeled Trigger And Dispatch Runtime

Goal:

- model trigger waiting, dispatch, and completion under the runtime architecture

Primary milestone:

- modeled runtime path beyond the released ceiling is coherent and diagnosable

Primary anchor:

- `dispatchModelValidated`

Done when:

- modeled trigger and dispatch steps have explicit evidence contracts
- screenshot and coordinate fallback limits are explicit
- no release claim is implied

### Phase 5 — Release Validation

Goal:

- validate that the runtime is stable enough for release decisions

Primary milestone:

- E2E evidence and flaky-budget policy support a release gate

Primary anchor:

- `releaseGatePassed`

Done when:

- E2E validation criteria are explicit and exercised
- release gate is pass/fail diagnosable
- work and lesson RAG are compressed at milestone and phase boundaries

## Stop Conditions

Work must stop when:

- a task would widen the released workflow ceiling without PRD approval
- a task would make screenshot evidence the only truth source
- a task would make coordinate-only interaction the default strategy
- a task would claim release above `pageReadyObserved` without explicit PRD
  change
- `work-rag.json` or `rag.json` is no longer sufficient for autonomous
  continuation

## Source Of Truth

- benchmark scope and released boundary:
  [`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md)
- evidence model:
  [`docs/product/prd-openclaw-evidence-model.md`](./prd-openclaw-evidence-model.md)
- E2E validation and release gate:
  [`docs/product/prd-openclaw-e2e-validation.md`](./prd-openclaw-e2e-validation.md)
- current working memory:
  [`work-rag.json`](./work-rag.json)
- durable lessons:
  [`rag.json`](./rag.json)
