from coord_smith.missions.names import (
    CONTROL_MISSIONS,
    RAG_MISSIONS,
    VALIDATION_MISSIONS,
    released_anchor_for_mission,
)


def test_released_anchor_for_mission_maps_prepare_session() -> None:
    assert released_anchor_for_mission("prepare_session") == "prepareSession"


def test_released_anchor_for_mission_maps_page_ready_observation() -> None:
    assert released_anchor_for_mission("page_ready_observation") == "pageReadyObserved"


def test_released_anchor_for_mission_returns_none_for_non_anchor_mission() -> None:
    assert released_anchor_for_mission("attach_session") is None
    assert released_anchor_for_mission("benchmark_validation") is None


def test_released_anchor_for_mission_rejects_unknown_mission() -> None:
    try:
        released_anchor_for_mission("not_a_real_mission")
    except ValueError as exc:
        assert "Unknown mission name" in str(exc)
    else:
        raise AssertionError("Expected unknown mission to be rejected")


def test_rag_missions_are_control_grouped() -> None:
    for mission_name in RAG_MISSIONS:
        assert mission_name in CONTROL_MISSIONS


def test_validation_missions_are_control_grouped() -> None:
    for mission_name in VALIDATION_MISSIONS:
        assert mission_name in CONTROL_MISSIONS
