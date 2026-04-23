"""Deterministic click-coordinate recipe used when no external actor injects coords.

The released-scope graph dispatches click-bearing missions with empty payloads
(see `src/ez_ax/graph/released_call_site.py`). In the documented architecture,
an external actor (OpenClaw) supplies target coordinates by populating the
payload `x`/`y` fields. When that caller is absent, this module loads a static
per-mission coordinate table from disk so the runtime can still exercise real
`pyautogui.click` calls without introducing any runtime LLM inference.

The recipe is additive: if a payload already carries `x`/`y`, that takes
precedence. Missions not listed in the recipe still receive no click, matching
the pre-recipe default.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from ez_ax.models.errors import ConfigError


class MissionClick(BaseModel):
    """A single click coordinate targeted at a screen pixel."""

    x: int
    y: int


class ClickRecipe(BaseModel):
    """Per-mission click coordinate table loaded from a JSON recipe file."""

    version: int = 1
    missions: dict[str, MissionClick] = Field(default_factory=dict)

    def coords_for(self, mission_name: str) -> tuple[int, int] | None:
        entry = self.missions.get(mission_name)
        if entry is None:
            return None
        return (entry.x, entry.y)


def load_click_recipe(path: Path) -> ClickRecipe:
    """Load and validate a click recipe from a JSON file.

    Raises ConfigError if the file is missing, malformed, or has the wrong
    shape. Callers are expected to surface the failure to the user before
    any mission runs.
    """
    if not path.exists():
        raise ConfigError(f"click recipe not found: {path}")
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"click recipe {path} is not valid JSON: {exc}"
        ) from exc
    try:
        return ClickRecipe.model_validate(data)
    except PydanticValidationError as exc:
        raise ConfigError(
            f"click recipe {path} does not match schema: {exc}"
        ) from exc
