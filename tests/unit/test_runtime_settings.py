from pathlib import Path

import pytest

from coord_smith.config.settings import RuntimeSettings


def test_runtime_settings_defaults_to_released_scope_ceiling() -> None:
    settings = RuntimeSettings(project_root=Path("/tmp/coord-smith"))

    assert settings.approved_scope_ceiling == "runCompletion"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_runtime_settings_clamps_unknown_scope_ceiling_to_run_completion() -> None:
    settings = RuntimeSettings(
        project_root=Path("/tmp/coord-smith"),
        approved_scope_ceiling="unknownCeiling",
    )

    assert settings.approved_scope_ceiling == "runCompletion"


def test_runtime_settings_preserves_prepare_session_ceiling() -> None:
    settings = RuntimeSettings(
        project_root=Path("/tmp/coord-smith"),
        approved_scope_ceiling="prepareSession",
    )

    assert settings.approved_scope_ceiling == "prepareSession"
