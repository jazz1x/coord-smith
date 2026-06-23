"""coord-smith Python-first runtime scaffold.

Public Python API
-----------------
``run_click_recipe`` is the programmatic entrypoint for using coord-smith as
an independent library or LLM-callable tool. It accepts a recipe as a model,
dict, YAML string, or file path and returns a structured ``RunResult``.
"""

from __future__ import annotations

from coord_smith._version import __version__
from coord_smith.graph.api import (
    RecipeInput,
    RunResult,
    run_click_recipe,
    run_click_recipe_sync,
)

__all__ = [
    "__version__",
    "RecipeInput",
    "RunResult",
    "run_click_recipe",
    "run_click_recipe_sync",
]
