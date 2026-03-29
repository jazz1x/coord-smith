# E2E Scaffold

This directory is reserved for OpenClaw-driven released-path verification.
Any future Playwright-based Python checks remain modeled scaffolding and must
not replace OpenClaw or widen the released scope beyond `pageReadyObserved`.

Current runnable entrypoint:

- `./.venv/bin/pytest tests/e2e -q`

Current scope:

- synthetic released-path E2E through the stdio-backed OpenClaw adapter boundary
- deterministic fake MCP transport for artifact and stop-proof verification
- no claim of post-ceiling behavior or real-browser release above `pageReadyObserved`
