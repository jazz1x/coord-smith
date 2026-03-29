"""Test that ez-ax is a Python-first orchestration runtime.

PRD requirement (Purpose section, line 5):
'ez-ax is a Python-first orchestration runtime.'

This is a foundational architectural statement that means:
1. The implementation language is Python (not TypeScript, Go, Rust, etc.)
2. The architecture is orchestration-centric (not browser-centric, not framework-centric)
3. The runtime is designed for state machine orchestration, not direct execution
4. Python is the canonical implementation path for the released-scope runtime
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestPythonFirstOrchestrationRuntime:
    """Tests verifying that ez-ax is fundamentally a Python-first orchestration runtime."""

    @staticmethod
    def _get_project_root() -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_released_scope_runtime_is_implemented_in_python(self) -> None:
        """Verify that the released-scope runtime is written in Python.

        The Purpose clause states: 'ez-ax is a Python-first orchestration runtime.'
        This requires that the core runtime implementation is in Python.
        """
        project_root = self._get_project_root()
        src_dir = project_root / "src" / "ez_ax"

        assert src_dir.exists(), "src/ez_ax directory must exist"

        # Verify core modules are Python (.py files, not other languages)
        py_files = list(src_dir.glob("**/*.py"))
        assert len(py_files) > 0, "Core runtime modules must be Python files"

        # Core graph modules (orchestration) should be Python
        graph_dir = src_dir / "graph"
        assert graph_dir.exists(), "graph directory must exist for orchestration"

        graph_py_files = list(graph_dir.glob("*.py"))
        assert len(graph_py_files) > 0, (
            "Graph orchestration modules must be Python (.py files)"
        )

    def test_runtime_does_not_depend_on_non_python_implementations(self) -> None:
        """Verify that runtime dependencies are Python-based, not alternative languages.

        Python-first means the canonical runtime is Python, not TypeScript, Go, Node.js, etc.
        """
        project_root = self._get_project_root()

        # Check pyproject.toml for runtime dependency language consistency
        pyproject_path = project_root / "pyproject.toml"
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        # Verify no Node.js/npm-related dependencies in main Python package
        forbidden_runtimes = ["nodejs", "npm", "bun", "deno"]
        for runtime in forbidden_runtimes:
            assert runtime not in pyproject_content.lower(), (
                f"Python-first runtime must not depend on {runtime}"
            )

    def test_canonical_stack_confirms_python_implementation(self) -> None:
        """Verify that the canonical stack document confirms Python-first approach.

        The Canonical Stack section of PRD specifies the Python-first direction.
        """
        project_root = self._get_project_root()
        prd_path = project_root / "docs" / "prd.md"

        with open(prd_path) as f:
            prd_content = f.read()

        # Extract Canonical Stack section
        stack_section_start = prd_content.find("## Canonical Stack")
        assert stack_section_start != -1, "Canonical Stack section must exist in PRD"

        # Verify Python-first is stated in Canonical Stack
        stack_section_end = prd_content.find("## Non-Goals", stack_section_start)
        stack_section = prd_content[stack_section_start:stack_section_end]

        assert "Python-first" in stack_section, (
            "Canonical Stack must confirm Python-first direction"
        )
        assert "Python runtime" in stack_section, (
            "Canonical Stack must specify Python runtime as canonical"
        )

    def test_orchestration_runtime_uses_langgraph_for_state_transitions(self) -> None:
        """Verify that orchestration is implemented via LangGraph state machine.

        Orchestration-centric architecture uses LangGraph as the state management
        backbone, confirming this is an orchestration runtime, not direct execution.
        """
        project_root = self._get_project_root()
        graph_dir = project_root / "src" / "ez_ax" / "graph"

        # Core orchestration modules should use LangGraph
        langgraph_references = 0
        for py_file in graph_dir.glob("*.py"):
            content = py_file.read_text()
            if "langgraph" in content.lower() or "StateGraph" in content:
                langgraph_references += 1

        assert langgraph_references > 0, (
            "Orchestration runtime must use LangGraph for state machine execution"
        )

    def test_released_entrypoint_confirms_orchestration_pattern(self) -> None:
        """Verify that the released entrypoint confirms orchestration architecture.

        The released entrypoint should use an adapter pattern and LangGraph
        to orchestrate missions, not perform execution directly.
        """
        project_root = self._get_project_root()
        entrypoint_path = (
            project_root / "src" / "ez_ax" / "graph" / "langgraph_released_execution.py"
        )

        assert entrypoint_path.exists(), (
            "langgraph_released_execution.py must exist to prove orchestration via LangGraph"
        )

        content = entrypoint_path.read_text()

        # Verify use of LangGraph for orchestration
        assert "StateGraph" in content or "langgraph" in content, (
            "Released execution must use LangGraph StateGraph for orchestration"
        )

        # Verify adapter acceptance (orchestration pattern)
        assert "adapter" in content.lower(), (
            "Released execution must accept adapter for delegated browser operations"
        )

    def test_purpose_statement_is_foundational_for_architecture(self) -> None:
        """Verify that 'Python-first orchestration runtime' is foundational.

        This Purpose statement shapes all architectural decisions:
        - Python language choice
        - Orchestration pattern (state machines, not direct execution)
        - Adapter-based delegation (not browser-facing runtime)
        - Released scope boundary (intentional stopping point)
        """
        # Verify this purpose statement appears in PRD
        project_root = self._get_project_root()
        prd_path = project_root / "docs" / "prd.md"

        with open(prd_path) as f:
            prd_content = f.read()

        # The exact statement should appear in Purpose section
        assert "orchestration runtime" in prd_content, (
            "PRD Purpose section must include 'orchestration runtime' statement"
        )

        # This statement should influence all downstream architecture
        assert "System Boundary" in prd_content, (
            "PRD must have System Boundary section following from Purpose"
        )

        # Verify System Boundary respects orchestration-centric principle
        system_boundary_start = prd_content.find("## System Boundary")
        system_boundary_end = prd_content.find("## Release Boundary")
        system_boundary = prd_content[system_boundary_start:system_boundary_end]

        assert "orchestration-centric" in system_boundary, (
            "System Boundary must state orchestration-centric principle derived from Purpose"
        )
