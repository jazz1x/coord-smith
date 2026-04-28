"""Tests verifying the PRD requirement: canonical stack is Python-first."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_canonical_stack_declares_python_runtime() -> None:
    """Verify Python 3.14 is the canonical runtime.

    PRD requirement (Canonical Stack, lines 125-137):
    'The canonical implementation path is Python-first.
     Expected stack direction: Python runtime ...'
    """
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    # Verify requires-python pins to 3.14.x
    requires_python = data.get("project", {}).get("requires-python", "")
    assert requires_python == ">=3.14,<3.15"
    assert "3.14" in requires_python


def test_canonical_stack_declares_langgraph() -> None:
    """Verify LangGraph is declared as a runtime dependency.

    PRD requirement (Canonical Stack, lines 125-137):
    'Expected stack direction: ... LangGraph ...'
    """
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    dependencies = data.get("project", {}).get("dependencies", [])
    langgraph_specs = [d for d in dependencies if "langgraph" in d.lower()]
    assert len(langgraph_specs) > 0
    assert ">=0.3.0" in langgraph_specs[0]


def test_canonical_stack_declares_langchain_core() -> None:
    """Verify LangChain-core is declared as a runtime dependency.

    PRD requirement (Canonical Stack, lines 125-137):
    'Expected stack direction: ... LangChain-core ...'
    """
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    dependencies = data.get("project", {}).get("dependencies", [])
    langchain_specs = [d for d in dependencies if "langchain" in d.lower()]
    assert len(langchain_specs) > 0
    # langchain-core is part of the langchain package
    assert any(">=0.3.0" in d for d in langchain_specs)


def test_canonical_stack_declares_pydantic_v2() -> None:
    """Verify Pydantic v2 is declared as a runtime dependency.

    PRD requirement (Canonical Stack, lines 125-137):
    'Expected stack direction: ... Pydantic v2 ...'
    """
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    dependencies = data.get("project", {}).get("dependencies", [])
    pydantic_specs = [d for d in dependencies if "pydantic" in d.lower()]
    assert len(pydantic_specs) > 0
    pydantic_spec = pydantic_specs[0]
    assert ">=2.8.0" in pydantic_spec
    # Version constraint ensures v2


def test_canonical_stack_declares_pytest_ruff_mypy() -> None:
    """Verify pytest, ruff, mypy are declared as dev dependencies.

    PRD requirement (Canonical Stack, lines 125-137):
    'Expected stack direction: ... pytest ... ruff ... mypy'
    """
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])

    # Verify all three tools are declared
    pytest_specs = [d for d in dev_deps if d.startswith("pytest")]
    ruff_specs = [d for d in dev_deps if d.startswith("ruff")]
    mypy_specs = [d for d in dev_deps if d.startswith("mypy")]

    assert len(pytest_specs) > 0, "pytest not found in dev dependencies"
    assert len(ruff_specs) > 0, "ruff not found in dev dependencies"
    assert len(mypy_specs) > 0, "mypy not found in dev dependencies"

    # Verify version constraints
    assert ">=8.3.0" in pytest_specs[0]
    assert ">=0.11.0" in ruff_specs[0]
    assert ">=1.11.0" in mypy_specs[0]
