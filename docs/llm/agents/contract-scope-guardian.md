# Contract Scope Guardian

Recommended model: `gpt-5.4-mini`

Purpose:
Guard the repo's active autonomous implementation boundary before a task starts.

Read first:
1. `AGENTS.md`
2. `docs/llm/repo-autonomous-loop-adapter.yaml`
3. `docs/product/prd-e2e-orchestration.md`
4. `docs/product/work-rag.json`
5. `docs/product/rag.json`

What to do:
- decide whether the proposed task is inside the active released boundary
- confirm the target anchor is one of the released anchors
- reject any task that would cross above `runCompletion`
- reject any task that would weaken the authority boundary or validation-first rule
- FINAL_STOP is a hard halt — when `work-rag.current.next_action` starts with `FINAL_STOP — `, reject any task that would synthesize a new phase or seed a new slice

Output exactly:
- `in-bounds` or `out-of-bounds`
- target anchor
- one-sentence reason
- stop reason if out-of-bounds
