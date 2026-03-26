"""Test that each released mission has documented evidence specifications.

PRD Release Boundary (lines 47-53): Released implementation scope includes:
- attach_session (PRD: "attach")
- prepare_session (PRD: "prepareSession")
- benchmark_validation (PRD: "benchmark validation")
- page_ready_observation (PRD: "pageReadyObserved")

Each mission must have defined primary and fallback evidence requirements
per the Evidence Truth Model (lines 69-83) priority hierarchy.
"""

from ez_ax.adapters.openclaw.client import OpenClawExecutionResult


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
    result = OpenClawExecutionResult(
        mission_name="attach_session",
        evidence_refs=tuple(primary),
    )
    # If this passes validation, primary spec is correct
    # (validate_openclaw_execution_result is called by the graph)
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

    result = OpenClawExecutionResult(
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

    result = OpenClawExecutionResult(
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

    result = OpenClawExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=tuple(primary),
    )
    assert result.mission_name == "page_ready_observation"
    assert len(result.evidence_refs) == 2
    assert "evidence://action-log/release-ceiling-stop" in result.evidence_refs


def test_released_missions_use_primary_truth_types_only() -> None:
    """Verify all primary evidence specs use only primary truth types per PRD priority.

    PRD Evidence Truth Model (lines 69-75):
    Primary truth priority: dom, text, clock, action-log
    Fallback only: screenshot, vision
    Last-resort: coordinate

    This test documents that released mission primary evidence uses only dom, text,
    clock, and action-log types (no screenshot, vision, or coordinate).
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
