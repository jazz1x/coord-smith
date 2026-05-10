"""Deterministic click-coordinate recipe used when no external actor injects coords.

The released-scope graph dispatches click-bearing missions with empty payloads
(see `src/coord_smith/graph/released_call_site.py`). In the documented architecture,
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
import warnings
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from coord_smith.models.errors import ConfigError


class PostClickSignal(BaseModel):
    """Image template that must appear on screen after a click to confirm completion."""

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    timeout: float = Field(default=5.0, gt=0.0)
    interval: float = Field(default=0.1, gt=0.0)


class WaitFor(BaseModel):
    """Image template that must appear on screen BEFORE clicking (pre-click guard).

    Replaces the prior ``trigger_wait`` mission. Polled with the same
    ``locateCenterOnScreen`` mechanism as ``PostClickSignal`` but its outcome
    gates whether the click is dispatched at all.
    """

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    timeout: float = Field(default=5.0, gt=0.0)
    interval: float = Field(default=0.1, gt=0.0)
    region: tuple[int, int, int, int] | None = None


class StepCoord(BaseModel):
    """Fixed pixel coordinate target for a Step.

    Used as the value of ``Step.coord``. Kept as a structured nested model
    rather than top-level ``x``/``y`` fields so the recipe YAML reads naturally
    (``coord: {x: 800, y: 500}``) and the click-target shape stays disjoint
    from image-target parameters.
    """

    x: int
    y: int


class Step(BaseModel):
    """A single click step in a multi-step recipe.

    A step declares an image template, a fixed coordinate, or both. When both
    are present, ``prefer`` decides the primary attempt; the other becomes
    the implicit fallback. The fallback chain is intentionally not a separate
    explicit field — it is derived from the presence of both ``image`` and
    ``coord`` on the same step.

    Image-match parameters (``region``, ``confidence``, ``grayscale``) are
    only meaningful when ``image`` is set; they are silently ignored
    otherwise. ``wait_for`` is a pre-click guard; ``verify_transition`` and
    ``post_click_signal`` are post-click guards.
    """

    name: str
    image: str | None = None
    coord: StepCoord | None = None
    region: tuple[int, int, int, int] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    grayscale: bool | None = None
    prefer: Literal["image", "coord"] | None = None
    wait_for: WaitFor | None = None
    verify_transition: bool = False
    transition_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    transition_region: tuple[int, int, int, int] | None = None
    post_click_signal: PostClickSignal | None = None

    @model_validator(mode="after")
    def _validate_target_and_prefer(self) -> Step:
        # At least one of image/coord must be declared.
        if self.image is None and self.coord is None:
            raise ValueError(
                f"Step '{self.name}': must declare at least one of 'image' or 'coord'"
            )
        # Resolve default prefer. When both are present, default = 'image'
        # (image is more environment-portable; coord works only on a fixed
        # screen layout). When only one is present, prefer matches that one.
        if self.prefer is None:
            self.prefer = "image" if self.image is not None else "coord"
        # Sanity: prefer must reference a populated field.
        if self.prefer == "image" and self.image is None:
            raise ValueError(
                f"Step '{self.name}': prefer='image' but no image declared"
            )
        if self.prefer == "coord" and self.coord is None:
            raise ValueError(
                f"Step '{self.name}': prefer='coord' but no coord declared"
            )
        return self


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


def _mission_to_step(name: str, target: MissionTarget) -> Step:
    """Normalize a legacy ``MissionTarget`` into a ``Step``.

    Used by :class:`ClickRecipe` when a recipe declares the legacy
    ``missions: {name: target}`` shape. The conversion is structural and
    lossless for fields that exist in both shapes; it does not invent any
    field the legacy target lacks (e.g. legacy ``MissionTarget`` has no
    ``wait_for``, so the resulting Step has ``wait_for=None``).
    """
    if isinstance(target, MissionClick):
        return Step(
            name=name,
            coord=StepCoord(x=target.x, y=target.y),
            verify_transition=target.verify_transition,
            transition_threshold=target.transition_threshold,
            transition_region=target.transition_region,
            post_click_signal=target.post_click_signal,
        )
    # MissionImageClick
    return Step(
        name=name,
        image=target.image,
        confidence=target.confidence,
        region=target.region,
        grayscale=target.grayscale,
        verify_transition=target.verify_transition,
        transition_threshold=target.transition_threshold,
        transition_region=target.transition_region,
        post_click_signal=target.post_click_signal,
    )


class ClickRecipe(BaseModel):
    """Per-step click target table loaded from a JSON or YAML recipe file.

    Two shapes are accepted:

    1. **Multi-step (preferred)** — ``steps: [Step, ...]``. Each step
       declares an image and/or coord target with its own pre-/post-click
       guards. Steps execute in declaration order within a single
       coord-smith invocation.
    2. **Legacy single-mission** — ``missions: {name: MissionTarget}``.
       Auto-normalized to a multi-step recipe with one step per mission
       entry on load. Emits a one-shot deprecation warning to stderr; does
       not affect stdout. New recipes should use ``steps:``.

    Recipes that declare both ``steps`` and ``missions`` resolve to ``steps``
    with a warning. Recipes that declare neither raise ``ValidationError``.
    """

    version: int = 1
    steps: list[Step] | None = None
    missions: dict[str, MissionTarget] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_steps(self) -> ClickRecipe:
        """Normalize ``missions`` into ``steps`` while keeping both populated.

        After this validator runs:

        * If only ``steps`` was provided → unchanged.
        * If only ``missions`` was provided (non-empty) → ``steps`` is
          populated by mapping each mission entry to a Step. ``missions``
          is left in place so legacy callers that read
          ``recipe.missions[name]`` keep working during the migration to
          step-aware code paths. A one-shot deprecation warning is
          emitted.
        * If both were provided (both non-empty) → ``steps`` is the
          source of truth; the provided ``missions`` is left in place. A
          deprecation warning is emitted to flag the ambiguity.
        * If both are empty (e.g. ``ClickRecipe()`` or a YAML with only
          ``version:``) → no normalization, no error. The recipe is a
          valid no-click smoke target.
        """
        has_steps = self.steps is not None and len(self.steps) > 0
        has_missions = len(self.missions) > 0
        if has_steps and has_missions:
            warnings.warn(
                "ClickRecipe declares both 'steps' and 'missions'; 'steps' "
                "is the source of truth. Migrate the recipe to use 'steps:' "
                "exclusively — 'missions' is deprecated.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self
        if not has_steps and has_missions:
            warnings.warn(
                "ClickRecipe 'missions' shape is deprecated; auto-normalizing "
                "to 'steps'. Migrate the recipe to use 'steps:'.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.steps = [
                _mission_to_step(name, target)
                for name, target in self.missions.items()
            ]
        return self

    def coords_for(self, mission_name: str) -> tuple[int, int] | None:
        """Return static coordinates for the step with the given name.

        Backwards-compat helper. Looks up the normalized step list. Returns
        the step's coord ``(x, y)`` if the step has a coord target,
        otherwise ``None``.
        """
        if self.steps is None:
            return None
        for step in self.steps:
            if step.name == mission_name and step.coord is not None:
                return (step.coord.x, step.coord.y)
        return None

    def image_target_for(self, mission_name: str) -> MissionImageClick | None:
        """Return image template config for the step with the given name.

        Backwards-compat helper. Wraps the step's image fields back into a
        ``MissionImageClick`` for callers that still expect the legacy
        shape. Returns ``None`` if the step has no image target.
        """
        if self.steps is None:
            return None
        for step in self.steps:
            if step.name == mission_name and step.image is not None:
                return MissionImageClick(
                    image=step.image,
                    confidence=step.confidence
                    if step.confidence is not None
                    else 0.9,
                    region=step.region,
                    grayscale=step.grayscale
                    if step.grayscale is not None
                    else False,
                    verify_transition=step.verify_transition,
                    transition_threshold=step.transition_threshold,
                    transition_region=step.transition_region,
                    post_click_signal=step.post_click_signal,
                )
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

    def _resolve(image: str, *, owner: str, role: str) -> str:
        img_path = Path(image)
        if not img_path.is_absolute():
            img_path = (base_dir / img_path).resolve()
        if not img_path.exists():
            raise ConfigError(
                f"click recipe {path} references missing {role} template "
                f"for {owner}: {img_path}"
            )
        return str(img_path)

    # Resolve image paths in legacy ``missions`` (still consumed by callers
    # that haven't migrated to ``steps``).
    if recipe.missions is not None:
        for mission_name, entry in recipe.missions.items():
            if isinstance(entry, MissionImageClick):
                entry.image = _resolve(
                    entry.image,
                    owner=f"mission '{mission_name}'",
                    role="click",
                )
            if entry.post_click_signal is not None:
                entry.post_click_signal.image = _resolve(
                    entry.post_click_signal.image,
                    owner=f"mission '{mission_name}'",
                    role="post-click signal",
                )

    # Resolve image paths in canonical ``steps`` (consumed by step-aware
    # callers; populated either directly from the recipe or via legacy
    # mission normalization).
    if recipe.steps is not None:
        for step in recipe.steps:
            if step.image is not None:
                step.image = _resolve(
                    step.image, owner=f"step '{step.name}'", role="click"
                )
            if step.post_click_signal is not None:
                step.post_click_signal.image = _resolve(
                    step.post_click_signal.image,
                    owner=f"step '{step.name}'",
                    role="post-click signal",
                )
            if step.wait_for is not None:
                step.wait_for.image = _resolve(
                    step.wait_for.image,
                    owner=f"step '{step.name}'",
                    role="pre-click wait_for",
                )
    return recipe
