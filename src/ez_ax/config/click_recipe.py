"""Deterministic click-coordinate recipe used when no external actor injects coords.

The released-scope graph dispatches click-bearing missions with empty payloads
(see `src/ez_ax/graph/released_call_site.py`). In the documented architecture,
an external actor (OpenClaw) supplies target coordinates by populating the
payload `x`/`y` fields. When that caller is absent, this module loads a static
per-mission coordinate table from disk so the runtime can still exercise real
`pyautogui.click` calls without introducing any runtime LLM inference.

Two target variants are supported per mission:

1. **Coordinate target** — `{"x": int, "y": int}` — fixed pixel coords.
2. **Image target** — `{"image": "path.png", "confidence": float, "region": [x,y,w,h]?,
   "grayscale": bool}` — the adapter locates the template on screen at runtime
   and clicks the center of the match. Path is resolved relative to the recipe
   file unless absolute. Image matching uses OpenCV (via pyautogui) so the
   `confidence` threshold is enforced.

The recipe is additive: if a payload already carries `x`/`y`, that takes
precedence. Missions not listed in the recipe still receive no click, matching
the pre-recipe default. Coordinate priority:
``payload(OpenClaw) > recipe(coord) > recipe(image) > no-click``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from ez_ax.models.errors import ConfigError


class PostClickSignal(BaseModel):
    """Image template that must appear on screen after a click to confirm completion."""

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    timeout: float = Field(default=5.0, gt=0.0)
    interval: float = Field(default=0.1, gt=0.0)


class MissionClick(BaseModel):
    """A single click coordinate targeted at a screen pixel."""

    x: int
    y: int
    verify_transition: bool = False
    transition_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    transition_region: tuple[int, int, int, int] | None = None
    post_click_signal: PostClickSignal | None = None


class MissionImageClick(BaseModel):
    """An image-template target resolved to coordinates at click time.

    The adapter locates the template on screen via
    ``pyautogui.locateCenterOnScreen`` (OpenCV-backed when ``confidence`` is
    set) and clicks the center of the first match. Region restricts the
    search rectangle to ``(left, top, width, height)`` for speed.
    """

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    region: tuple[int, int, int, int] | None = None
    grayscale: bool = False
    verify_transition: bool = False
    transition_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    transition_region: tuple[int, int, int, int] | None = None
    post_click_signal: PostClickSignal | None = None


# Pydantic v2 "smart" union mode resolves on field shape: dict with x/y →
# MissionClick; dict with image → MissionImageClick. No explicit discriminator
# needed because the two models have disjoint required fields.
MissionTarget = MissionClick | MissionImageClick


class ClickRecipe(BaseModel):
    """Per-mission click target table loaded from a JSON recipe file."""

    version: int = 1
    missions: dict[str, MissionTarget] = Field(default_factory=dict)

    def coords_for(self, mission_name: str) -> tuple[int, int] | None:
        """Return static coordinates for missions configured with a coord target."""
        entry = self.missions.get(mission_name)
        if isinstance(entry, MissionClick):
            return (entry.x, entry.y)
        return None

    def image_target_for(self, mission_name: str) -> MissionImageClick | None:
        """Return image template config for missions configured with an image target."""
        entry = self.missions.get(mission_name)
        if isinstance(entry, MissionImageClick):
            return entry
        return None


def load_click_recipe(path: Path) -> ClickRecipe:
    """Load and validate a click recipe from a JSON or YAML file.

    Image paths within the recipe are resolved relative to the recipe file's
    directory so users can keep templates next to the recipe. Absolute image
    paths are preserved unchanged. Raises ``ConfigError`` if the file is
    missing, malformed, has the wrong shape, or references a nonexistent
    template.

    Both ``.json`` and ``.yaml``/``.yml`` extensions are accepted. YAML is
    preferred for human and agent authoring; JSON is accepted for backwards
    compatibility. Files with any other extension are parsed as JSON.
    """
    if not path.exists():
        raise ConfigError(f"click recipe not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            data: Any = yaml.safe_load(text)
        else:
            data = json.loads(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ConfigError(
            f"click recipe {path} could not be parsed: {exc}"
        ) from exc
    try:
        recipe = ClickRecipe.model_validate(data)
    except PydanticValidationError as exc:
        raise ConfigError(
            f"click recipe {path} does not match schema: {exc}"
        ) from exc

    base_dir = path.parent.resolve()

    def _resolve(image: str, *, mission: str, role: str) -> str:
        img_path = Path(image)
        if not img_path.is_absolute():
            img_path = (base_dir / img_path).resolve()
        if not img_path.exists():
            raise ConfigError(
                f"click recipe {path} references missing {role} template "
                f"for mission '{mission}': {img_path}"
            )
        return str(img_path)

    for mission_name, entry in recipe.missions.items():
        if isinstance(entry, MissionImageClick):
            entry.image = _resolve(
                entry.image, mission=mission_name, role="click"
            )
        if entry.post_click_signal is not None:
            entry.post_click_signal.image = _resolve(
                entry.post_click_signal.image,
                mission=mission_name,
                role="post-click signal",
            )
    return recipe
