"""
Unit tests for PRD Non-Goals And Forbidden Directions constraints.

Verifies that forbidden architectural directions are not implemented in the
active runtime path:

- TypeScript runtime revival
- Bun-first canonical runtime or validation direction
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_no_typescript_files_in_runtime_path():
    """Verify no TypeScript files (.ts, .tsx) in src/ runtime path.

    PRD Non-Goals constraint (line 148):
    "TypeScript runtime revival under the active runtime path"
    """
    ts_files = list(PROJECT_ROOT.glob("src/**/*.ts")) + list(
        PROJECT_ROOT.glob("src/**/*.tsx")
    )
    assert (
        len(ts_files) == 0
    ), f"TypeScript files found in src/ (forbidden): {ts_files}"


def test_no_typescript_compilation_artifacts_in_runtime():
    """Verify no .js/.jsx output from TypeScript compilation in src/.

    PRD Non-Goals constraint (line 148):
    "TypeScript runtime revival under the active runtime path"
    """
    js_files = list(PROJECT_ROOT.glob("src/**/*.js")) + list(
        PROJECT_ROOT.glob("src/**/*.jsx")
    )
    assert (
        len(js_files) == 0
    ), f"JavaScript files found in src/ (TypeScript revival forbidden): {js_files}"


def test_no_bun_configuration_in_project_root():
    """Verify no Bun configuration files in project root.

    PRD Non-Goals constraint (line 150):
    "Bun-first canonical runtime or validation direction"

    Bun uses bunfig.toml and creates bun.lockb lock files.
    """
    bun_files = [
        PROJECT_ROOT / "bunfig.toml",
        PROJECT_ROOT / "bun.lockb",
    ]
    for bun_file in bun_files:
        assert (
            not bun_file.exists()
        ), f"Bun configuration found (forbidden): {bun_file}"


def test_pyproject_toml_uses_python_build_system_not_bun():
    """Verify pyproject.toml uses Python-based build system (not Bun).

    PRD Non-Goals constraint (line 150):
    "Bun-first canonical runtime or validation direction"

    Project must use a Python-based build system (Poetry, Hatch, etc),
    not Bun's build system.
    """
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found"

    content = pyproject_path.read_text()

    # Verify a Python-based build system is configured
    python_build_systems = ["poetry", "hatchling", "pdm", "flit"]
    has_python_build = any(
        system in content.lower() for system in python_build_systems
    )
    assert has_python_build, (
        f"No Python-based build system found in pyproject.toml. "
        f"Must use one of: {python_build_systems}"
    )

    # Verify Bun is not the primary build system
    assert "[build-system]" in content, "Missing [build-system] section"
    build_section = content.split("[build-system]")[1].split("[")[0]
    assert (
        "bun" not in build_section.lower()
    ), "Bun build system found in pyproject.toml (forbidden)"


def test_released_scope_runtime_is_python_only():
    """Verify released-scope runtime source is Python-only.

    PRD Non-Goals constraint (lines 148-150):
    "TypeScript runtime revival" and "Bun-first canonical runtime"

    The released-scope execution backend (src/ez_ax/) must be Python-only.
    """
    runtime_src = PROJECT_ROOT / "src"
    assert (
        runtime_src.exists()
    ), f"Runtime source directory not found: {runtime_src}"

    # Find all non-Python files in src/
    non_py_files = []
    for file_path in runtime_src.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts"}:
            non_py_files.append(file_path.relative_to(PROJECT_ROOT))

    assert (
        len(non_py_files) == 0
    ), f"Non-Python runtime files found (forbidden): {non_py_files}"
