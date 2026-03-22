---
name: python-engineering
description: Apply the repository's shared Python engineering principles during Python code writing, review, and refactoring. Use when editing Python runtime code, tests, validation logic, or refactoring Python modules and you need the shared SRP, fail-fast, ADT, testing, and commenting guidance.
---

# Python Engineering

Use the shared Python engineering guide for Python code work in this
repository.

## Read First

1. `AGENTS.md`
2. `.claude/python-engineering.md`
3. `pyproject.toml`

Read the active PRDs whenever the task touches runtime, validation, evidence,
or orchestration contracts.

## Rules

- Repository canonical sources win on conflict.
- Prefer Python-native implementations over extra functional helper libraries.
- Keep code linear, fail-fast, and scoped to one responsibility.
- Prefer `match` over long `if/elif` chains for ADT or 3+ state branches after guard clauses.
- Use the testing and commenting rules from `.claude/python-engineering.md`
  unless the repository validation contract is stricter.
