from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from coord_smith.graph.released_run_root import create_run_root, generate_run_id
from coord_smith.models.errors import ConfigError


def test_generate_run_id_is_safe_for_run_root_creation(tmp_path: Path) -> None:
    run_id = generate_run_id(now=datetime(2026, 3, 22, 0, 0, 0, tzinfo=ZoneInfo("UTC")))
    run_root = create_run_root(base_dir=tmp_path, run_id=run_id)

    assert run_root.exists()
    assert run_root.is_dir()
    assert "/" not in run_id and "\\" not in run_id


def test_create_run_root_rejects_non_path_base_dir() -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(
            base_dir="not-a-path",  # type: ignore[arg-type]
            run_id="run-1",
        )

    assert "base_dir" in str(excinfo.value)


def test_create_run_root_rejects_non_string_run_id(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(
            base_dir=tmp_path,
            run_id=123,  # type: ignore[arg-type]
        )

    assert "run_id" in str(excinfo.value)


def test_create_run_root_rejects_empty_run_id(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(base_dir=tmp_path, run_id="")

    assert "run_id" in str(excinfo.value)


def test_create_run_root_rejects_whitespace_wrapped_run_id(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(base_dir=tmp_path, run_id=" run-1")

    assert "whitespace" in str(excinfo.value)


@pytest.mark.parametrize("run_id", ["run/1", r"run\\1"])
def test_create_run_root_rejects_path_separators_in_run_id(
    tmp_path: Path, run_id: str
) -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(base_dir=tmp_path, run_id=run_id)

    assert "path separators" in str(excinfo.value)


def test_create_run_root_rejects_file_base_dir(tmp_path: Path) -> None:
    base_dir = tmp_path / "base_dir.txt"
    base_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        create_run_root(base_dir=base_dir, run_id="run-1")

    assert "directory" in str(excinfo.value)


def test_create_run_root_creates_run_root_and_action_log_dir(tmp_path: Path) -> None:
    run_root = create_run_root(base_dir=tmp_path, run_id="run-1")

    assert run_root.exists()
    assert run_root.is_dir()
    assert (run_root / "artifacts" / "action-log").is_dir()


def test_create_run_root_rejects_whitespace_only_run_id(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(base_dir=tmp_path, run_id="   ")

    assert "whitespace" in str(excinfo.value)


def test_create_run_root_rejects_nul_byte_in_run_id(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        create_run_root(base_dir=tmp_path, run_id="run\x00id")

    assert "NUL" in str(excinfo.value)
