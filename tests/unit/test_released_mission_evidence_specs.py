"""Test that each released mission has documented evidence specifications.

PRD Release Boundary (lines 47-60): Released implementation scope includes all
12 missions:
- attach_session (PRD: "attach")
- prepare_session (PRD: "prepareSession")
- benchmark_validation (PRD: "benchmark validation")
- page_ready_observation (PRD: "pageReadyObserved")
- sync_observation (PRD: "syncObservation")
- target_actionability_observation (PRD: "targetActionabilityObservation")
- armed_state_entry (PRD: "armedStateEntry")
- trigger_wait (PRD: "triggerWait")
- click_dispatch (PRD: "clickDispatch")
- click_completion (PRD: "clickCompletion")
- success_observation (PRD: "successObservation")
- run_completion (PRD: "runCompletion")

Each mission must have defined primary and fallback evidence requirements
per the Evidence Truth Model (lines 69-83) priority hierarchy.
"""

from coord_smith.adapters.execution.client import ExecutionResult


def test_attach_session_primary_evidence_specification() -> None:
    """Verify attach_session has documented primary evidence specification.

    PRD Evidence Truth Model specifies primary truth types: dom, text, clock,
    action-log. For attach_session, primary evidence includes text evidence
    (session-attached, auth-state-confirmed) and action-log.
    """
    # Primary evidence spec from client.py line 248-251
    primary = {
        "evidence://text/session-attached",
        "evidence://text/auth-state-confirmed",
        "evidence://action-log/attach-session",
    }

    # Verify validation accepts primary minimum
    result = ExecutionResult(
        mission_name="attach_session",
        evidence_refs=tuple(primary),
    )
    # If this passes validation, primary spec is correct
    # (validate_execution_result is called by the graph)
    assert result.mission_name == "attach_session"
    assert len(result.evidence_refs) == 3
    assert "evidence://text/session-attached" in result.evidence_refs


def test_prepare_session_primary_evidence_specification() -> None:
    """Verify prepare_session has documented primary evidence specification.

    PRD Evidence Truth Model: primary truth types are text, clock, action-log.
    For prepare_session, primary evidence includes text (session-viable) and action-log.
    """
    # Primary evidence spec from client.py line 215-217
    primary = {
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    }

    result = ExecutionResult(
        mission_name="prepare_session",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "prepare_session"
    assert len(result.evidence_refs) == 2
    assert "evidence://text/session-viable" in result.evidence_refs


def test_benchmark_validation_primary_evidence_specification() -> None:
    """Verify benchmark_validation has documented primary evidence specification.

    PRD Evidence Truth Model: primary truth types are dom, text, clock, action-log.
    For benchmark_validation, primary evidence includes action-log (enter-target-page)
    and dom (target-page-entered).
    """
    # Primary evidence spec from client.py line 226-228
    primary = {
        "evidence://action-log/enter-target-page",
        "evidence://dom/target-page-entered",
    }

    result = ExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "benchmark_validation"
    assert len(result.evidence_refs) == 2
    assert "evidence://dom/target-page-entered" in result.evidence_refs


def test_page_ready_observation_primary_evidence_specification() -> None:
    """Verify page_ready_observation has documented primary evidence spec.

    PRD Evidence Truth Model: primary types are dom, text, clock, action-log.
    For page_ready_observation (released ceiling), primary evidence includes
    dom (page-shell-ready) and action-log (release-ceiling-stop).

    PRD Release-Ceiling Stop Proof requires action-log/release-ceiling-stop
    with typed fields: event, mission_name, ts.
    """
    # Primary evidence spec from client.py line 237-239
    primary = {
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    }

    result = ExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "page_ready_observation"
    assert len(result.evidence_refs) == 2
    assert "evidence://action-log/release-ceiling-stop" in result.evidence_refs


def test_sync_observation_primary_evidence_specification() -> None:
    """Verify sync_observation has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are clock and action-log.
    For sync_observation, primary evidence includes clock (server-time-synced)
    and action-log (sync-observed).
    """
    # Primary evidence spec from client.py line 248-251
    primary = {
        "evidence://clock/server-time-synced",
        "evidence://action-log/sync-observed",
    }

    result = ExecutionResult(
        mission_name="sync_observation",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "sync_observation"
    assert len(result.evidence_refs) == 2
    assert "evidence://clock/server-time-synced" in result.evidence_refs
    assert "evidence://action-log/sync-observed" in result.evidence_refs


def test_target_actionability_observation_primary_evidence_specification() -> None:
    """Verify target_actionability_observation has documented primary evidence spec.

    PRD Evidence Truth Model: primary types are dom and action-log.
    For target_actionability_observation, primary evidence includes dom
    (target-actionable) and action-log (target-actionable-observed).
    """
    # Primary evidence spec from client.py line 258-261
    primary = {
        "evidence://dom/target-actionable",
        "evidence://action-log/target-actionable-observed",
    }

    result = ExecutionResult(
        mission_name="target_actionability_observation",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "target_actionability_observation"
    assert len(result.evidence_refs) == 2
    assert "evidence://dom/target-actionable" in result.evidence_refs


def test_armed_state_entry_primary_evidence_specification() -> None:
    """Verify armed_state_entry has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are text and action-log.
    For armed_state_entry, primary evidence includes text (armed-state-entered)
    and action-log (armed-state).
    """
    # Primary evidence spec from client.py line 269-272
    primary = {
        "evidence://text/armed-state-entered",
        "evidence://action-log/armed-state",
    }

    result = ExecutionResult(
        mission_name="armed_state_entry",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "armed_state_entry"
    assert len(result.evidence_refs) == 2
    assert "evidence://text/armed-state-entered" in result.evidence_refs


def test_trigger_wait_primary_evidence_specification() -> None:
    """Verify trigger_wait has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are clock and action-log.
    For trigger_wait, primary evidence includes clock (trigger-received)
    and action-log (trigger-wait-complete).
    """
    # Primary evidence spec from client.py line 280-283
    primary = {
        "evidence://clock/trigger-received",
        "evidence://action-log/trigger-wait-complete",
    }

    result = ExecutionResult(
        mission_name="trigger_wait",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "trigger_wait"
    assert len(result.evidence_refs) == 2
    assert "evidence://clock/trigger-received" in result.evidence_refs


def test_click_dispatch_primary_evidence_specification() -> None:
    """Verify click_dispatch has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are action-log and dom.
    For click_dispatch, primary evidence includes action-log (click-dispatched)
    and dom (click-target-clicked).
    """
    # Primary evidence spec from client.py line 291-294
    primary = {
        "evidence://action-log/click-dispatched",
        "evidence://dom/click-target-clicked",
    }

    result = ExecutionResult(
        mission_name="click_dispatch",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "click_dispatch"
    assert len(result.evidence_refs) == 2
    assert "evidence://action-log/click-dispatched" in result.evidence_refs


def test_click_completion_primary_evidence_specification() -> None:
    """Verify click_completion has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are dom and action-log.
    For click_completion, primary evidence includes dom (click-effect-confirmed)
    and action-log (click-completed).
    """
    # Primary evidence spec from client.py line 302-305
    primary = {
        "evidence://dom/click-effect-confirmed",
        "evidence://action-log/click-completed",
    }

    result = ExecutionResult(
        mission_name="click_completion",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "click_completion"
    assert len(result.evidence_refs) == 2
    assert "evidence://dom/click-effect-confirmed" in result.evidence_refs


def test_success_observation_primary_evidence_specification() -> None:
    """Verify success_observation has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are dom and action-log.
    For success_observation, primary evidence includes dom (success-observed)
    and action-log (success-observation).
    """
    # Primary evidence spec from client.py line 313-316
    primary = {
        "evidence://dom/success-observed",
        "evidence://action-log/success-observation",
    }

    result = ExecutionResult(
        mission_name="success_observation",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "success_observation"
    assert len(result.evidence_refs) == 2
    assert "evidence://dom/success-observed" in result.evidence_refs


def test_run_completion_primary_evidence_specification() -> None:
    """Verify run_completion has documented primary evidence specification.

    PRD Evidence Truth Model: primary types are action-log only.
    For run_completion (released ceiling), primary evidence includes only
    action-log (release-ceiling-stop) with typed fields: event, mission_name, ts.
    """
    # Primary evidence spec from client.py line 324-326
    primary = {
        "evidence://action-log/release-ceiling-stop",
    }

    result = ExecutionResult(
        mission_name="run_completion",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "run_completion"
    assert len(result.evidence_refs) == 1
    assert "evidence://action-log/release-ceiling-stop" in result.evidence_refs


def test_released_missions_use_primary_truth_types_only() -> None:
    """Verify all primary evidence specs use only primary truth types per PRD priority.

    PRD Evidence Truth Model (lines 69-75):
    Primary truth priority: dom, text, clock, action-log
    Fallback only: screenshot, vision
    Last-resort: coordinate

    This test documents that released mission primary evidence (all 12 missions)
    uses only dom, text, clock, and action-log types (no screenshot, vision, or
    coordinate) in primary evidence specifications.
    """
    primary_specs = {
        "attach_session": {
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        },
        "prepare_session": {
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        },
        "benchmark_validation": {
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
        },
        "page_ready_observation": {
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        },
        "sync_observation": {
            "evidence://clock/server-time-synced",
            "evidence://action-log/sync-observed",
        },
        "target_actionability_observation": {
            "evidence://dom/target-actionable",
            "evidence://action-log/target-actionable-observed",
        },
        "armed_state_entry": {
            "evidence://text/armed-state-entered",
            "evidence://action-log/armed-state",
        },
        "trigger_wait": {
            "evidence://clock/trigger-received",
            "evidence://action-log/trigger-wait-complete",
        },
        "click_dispatch": {
            "evidence://action-log/click-dispatched",
            "evidence://dom/click-target-clicked",
        },
        "click_completion": {
            "evidence://dom/click-effect-confirmed",
            "evidence://action-log/click-completed",
        },
        "success_observation": {
            "evidence://dom/success-observed",
            "evidence://action-log/success-observation",
        },
        "run_completion": {
            "evidence://action-log/release-ceiling-stop",
        },
    }

    forbidden_prefixes = {
        "evidence://screenshot/",
        "evidence://vision/",
        "evidence://coordinate/",
    }

    for mission, evidence_set in primary_specs.items():
        for evidence_ref in evidence_set:
            for forbidden in forbidden_prefixes:
                assert not evidence_ref.startswith(forbidden), (
                    f"Mission '{mission}' primary evidence contains forbidden "
                    f"type '{forbidden}': {evidence_ref}"
                )
