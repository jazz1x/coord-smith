# Assetization Pattern Promoter

Recommended model: `gpt-5.4-nano`

Purpose:
Decide whether a closed task produced a durable repeated workflow pattern that
should be promoted into `docs/product/rag.json` rather than only remaining in
current work memory.

Read first:
1. `docs/llm/repo-autonomous-loop-adapter.yaml`
2. `docs/product/work-rag.json`
3. `docs/product/rag.json`

What to do:
- keep `work-rag.json` focused on current continuation only
- promote only durable repeated patterns into `docs/product/rag.json`
- tag lessons as `active-implementation` or `historical-cutover`
- avoid copying narrow one-off task logs into durable memory

Output exactly:
- promote or do-not-promote
- one-sentence reason
- target memory file
- lesson tag recommendation if promoted
