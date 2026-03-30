"""Test that released-scope runtime is separated from the offline autoloop harness.

PRD requirement (System Boundary, lines 37-38):
'LLM inference is restricted to the offline autoloop harness (`ez-ax-autoloop`)
that generates implementation; it is not part of the runtime path.'

This means:
1. The released-scope runtime must not import or depend on the autoloop harness
2. The autoloop harness is strictly offline (code generation) and separate from runtime
3. The released-scope execution path does not invoke autoloop functionality
"""

from __future__ import annotations

import sys


def test_released_scope_runtime_modules_do_not_import_autoloop() -> None:
    """Verify that released-scope runtime modules don't depend on autoloop harness.

    PRD requirement (System Boundary, lines 37-38):
    'LLM inference is restricted to the offline autoloop harness (`ez-ax-autoloop`)
    that generates implementation; it is not part of the runtime path.'

    The released-scope runtime modules (runtime_graph, langgraph_released_execution,
    released_call_site, etc.) must not import from the rag/autoloop modules, ensuring
    clean separation between:
    - Offline harness (autoloop): LLM-based code generation (not in runtime path)
    - Released runtime: deterministic execution, no LLM (is in runtime path)
    """
    # Import released-scope modules and check their imports
    released_modules = [
        "ez_ax.graph.runtime_graph",
        "ez_ax.graph.langgraph_released_execution",
        "ez_ax.graph.released_call_site",
        "ez_ax.graph.pyautogui_cli_entrypoint",
    ]

    # Autoloop/RAG modules that should NOT be imported by runtime
    forbidden_modules = [
        "ez_ax.rag",
        "ez_ax.rag.autoloop_runner",
        "ez_ax.rag.autoloop_prompt_driver",
        "ez_ax.rag.autoloop_executor",
    ]

    for released_module_name in released_modules:
        released_module = sys.modules.get(released_module_name)
        if released_module and hasattr(released_module, "__dict__"):
            module_dict = released_module.__dict__
            for obj_name in module_dict:
                obj = module_dict[obj_name]
                obj_module_name = getattr(obj, "__module__", "")
                for forbidden in forbidden_modules:
                    assert not obj_module_name.startswith(forbidden), (
                        f"Released-scope runtime module {released_module_name} "
                        f"must not import from autoloop harness module {forbidden}. "
                        f"Found import of {obj_module_name} via {obj_name}. "
                        f"PRD requirement: 'LLM inference is restricted to the "
                        f"offline autoloop harness; it is not part of the "
                        f"runtime path.'"
                    )


def test_released_scope_execution_does_not_invoke_autoloop() -> None:
    """Verify released-scope execution doesn't depend on autoloop functionality.

    PRD requirement (System Boundary, lines 37-38):
    'LLM inference is restricted to the offline autoloop harness (`ez-ax-autoloop`)
    that generates implementation; it is not part of the runtime path.'

    The released-scope execution must be self-contained and not invoke the
    autoloop harness, ensuring runtime independence from code generation.
    """
    import inspect

    from ez_ax.graph.langgraph_released_execution import (
        run_released_scope_via_langgraph,
    )

    # Verify the released execution function doesn't reference autoloop
    source_code = inspect.getsource(run_released_scope_via_langgraph)

    # Check that the function doesn't import or call autoloop modules
    forbidden_refs = [
        "AutoloopRunner",
        "AutoloopPromptDriver",
        "auto_seed_next_phase",
        "build_claude_exec_args",
        "from ez_ax.rag",
        "import.*autoloop",
    ]

    for forbidden_ref in forbidden_refs:
        assert forbidden_ref not in source_code, (
            f"Released-scope execution must not reference autoloop: {forbidden_ref}. "
            f"PRD requirement: 'LLM inference is restricted to the offline autoloop "
            f"harness; it is not part of the runtime path.'"
        )
