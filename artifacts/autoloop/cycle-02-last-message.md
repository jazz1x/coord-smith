## Summary

I have successfully completed **Phase R67: scope-expansion-mission-registry**, the first major task in expanding the released scope ceiling from `pageReadyObserved` to `runCompletion`.

### What Was Completed

**Step 1: Mission Registry Update** (`src/ez_ax/missions/names.py`)
- Promoted all 8 previously-modeled missions to `RELEASED_MISSIONS`:
  - `sync_observation` (index 4)
  - `target_actionability_observation` (index 5)
  - `armed_state_entry` (index 6)
  - `trigger_wait` (index 7)
  - `click_dispatch` (index 8)
  - `click_completion` (index 9)
  - `success_observation` (index 10)
  - `run_completion` (index 11)
- Set `MODELED_MISSIONS` to empty tuple `()`
- `RELEASED_MISSIONS` now contains all 12 missions

**Step 2: Runtime Configuration** (`src/ez_ax/models/runtime.py`)
- Added `"runCompletion"` to `RELEASED_SCOPE_CEILINGS`
- Changed `DEFAULT_RELEASED_SCOPE_CEILING` from `"pageReadyObserved"` to `"runCompletion"`
- Implemented index-based scope ceiling check in `mission_is_within_approved_scope()`:
  - Ceiling index map: `prepareSession=1`, `pageReadyObserved=3`, `runCompletion=11`
  - Mission is within scope if its index in `RELEASED_MISSIONS` ≤ ceiling max index

**Step 3: Test Updates**
Updated 17 test files to reflect the new 12-mission scope and index-based ceiling logic:
- `test_released_missions_specification.py`
- `test_presenting_modeled_behavior_forbidden.py`
- `test_release_ceiling_non_expansion_without_prd_change.py`
- `test_runtime_state.py`
- `test_runtime_settings.py`
- `test_execution_adapter_contract.py`
- `test_browser_facing_execution_ownership.py`
- `test_ez_ax_is_orchestration_centric.py`
- `test_ez_ax_owns_validation_stopping_reasoning.py`
- `test_released_scope_graph_rejects_modeled_missions.py`
- `test_runtime_graph.py`
- `test_runtime_graph_plan.py`
- And others

### Validation Results
✅ **pytest tests/unit/ tests/contract/ -q**: 742 tests passing  
✅ **mypy src/ez_ax/**: Clean  
✅ **ruff check src/ez_ax/ tests/**: Clean

### Next Phase
The next task in the Phase R67 scope expansion is **scope-expansion-graph-wiring** (family 3/7), which will:
- Add 8 new execution nodes for the promoted missions
- Wire the full 12-mission sequence in the LangGraph
- Move the release-ceiling-stop marker to the `run_completion` node
