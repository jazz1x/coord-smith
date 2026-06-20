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
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from coord_smith.cli_logging import get_logger
from coord_smith.models.errors import ConfigError
from coord_smith.models.identifiers import ResolvedImagePath

_log = get_logger("click_recipe")

# Shared strict config for every recipe model. ``extra="forbid"`` turns a
# misspelled key (e.g. ``confidance:`` for ``confidence:``) into a parse-time
# error instead of silently dropping it and clicking with a default — a
# recipe is the one input an autonomous caller or human author controls, so
# a typo must fail loudly (exit 3) rather than mis-click.
_STRICT = ConfigDict(extra="forbid")

# Image-match defaults applied when a Step omits the optional field. Named
# once here so the two sites that reconstruct a MissionImageClick from a Step
# (coord_resolver.locate_image_for_step, ClickRecipe.image_target_for) cannot
# drift apart. These mirror the Field defaults on MissionImageClick.
DEFAULT_IMAGE_CONFIDENCE = 0.9
DEFAULT_IMAGE_GRAYSCALE = False

# A search/comparison rectangle ``(left, top, width, height)``. The origin
# may sit anywhere on (or off) screen, but width/height must be positive —
# a zero/negative extent either silently disables transition detection
# (PIL diff over an empty crop) or raises a raw ``ValueError`` deep in the
# adapter that bypasses the typed-evidence path. Validated centrally here.
Region = tuple[int, int, int, int]


def _validate_step_name(name: str) -> str:
    """Reject step names that would escape the run-root when used as a filename.

    ``Step.name`` is interpolated into action-log JSONL paths
    (``action_log_writer.action_key_for_mission`` → ``<key>.jsonl``). A name
    containing a path separator (``/`` or ``\\``), a ``..`` traversal segment,
    a leading separator (absolute path), or a NUL byte is a confirmed
    filesystem-write-escape vector — a recipe could create/clobber JSONL
    files anywhere the process can write. This is intentionally narrow:
    underscores, dots-in-the-middle, hyphens, and unicode are all allowed;
    only filesystem-escaping shapes are forbidden.
    """
    if not name:
        raise ValueError("Step name must not be empty")
    if "/" in name or "\\" in name:
        raise ValueError(
            f"Step name must not contain a path separator: {name!r}"
        )
    if "\x00" in name:
        raise ValueError("Step name must not contain a NUL byte")
    # ``..`` as a whole component (or the bare name) is traversal; a literal
    # ``..`` substring inside a longer token (e.g. ``a..b``) cannot traverse
    # without a separator, which is already rejected above.
    if name == "." or name == ".." or name.strip() == "":
        raise ValueError(f"Step name must not be a path traversal token: {name!r}")
    # A step's guard logs (wait_for / transition / signal) are keyed by the
    # step name; a name equal to a reserved canonical action-log key would
    # write those guard records INTO the canonical per-step/per-run evidence
    # file (e.g. step-observed.jsonl), contaminating the auditable evidence
    # trail. Reject the collision.
    if name in _RESERVED_ACTION_LOG_KEYS:
        raise ValueError(
            f"Step name {name!r} collides with a reserved action-log key "
            f"({sorted(_RESERVED_ACTION_LOG_KEYS)}); its guard logs would "
            "contaminate the canonical evidence file. Rename the step."
        )
    return name


# Canonical action-log keys emitted by the released missions. A recipe step
# must not reuse one of these as its name (see _validate_step_name). Kept as a
# literal frozenset rather than importing from missions.evidence_specs to keep
# config/ free of an adapter/mission dependency (layering: config is below
# missions in the import graph). An equivalence test
# (test_hardening_cycle5.py) pins this set against the keys derived from
# MISSION_FALLBACK_REFS so a future evidence-spec rename fails CI instead of
# silently re-opening the guard-log contamination vector.
#
# ``failure`` is reserved even though it is not a mission action-log key: it is
# the filename of the reserved failure-evidence artifact (``failure.jsonl``)
# that run_summary._read_failure_record publishes into run.json. A step named
# ``failure`` would append its guard logs there and shadow a later real failure
# record, defeating the ADR-006 attribution contract.
_RESERVED_ACTION_LOG_KEYS = frozenset({
    "attach-session",
    "prepare-session",
    "step-observed",
    "step-dispatched",
    "step-captured",
    "release-ceiling-stop",
    "failure",
})


def _validate_region(region: Region | None) -> Region | None:
    """Reject region tuples whose width or height is not positive.

    The 4-int arity is already enforced by the tuple annotation; this adds
    the ``width > 0 and height > 0`` constraint Pydantic cannot express on a
    bare ``tuple[int, int, int, int]``. A common authoring mistake is using
    ``[x1, y1, x2, y2]`` (corner pairs) instead of ``[x, y, w, h]`` — that
    often yields a valid-arity tuple with a nonsensical extent, which this
    catches at parse time.
    """
    if region is None:
        return None
    _, _, width, height = region
    if width <= 0 or height <= 0:
        raise ValueError(
            f"region width and height must be positive (got width={width}, "
            f"height={height}); a region is [left, top, width, height], "
            "not [x1, y1, x2, y2]"
        )
    return region


def _validate_poll_interval_within_timeout(*, interval: float, timeout: float) -> None:
    """Reject a poll ``interval`` that exceeds its ``timeout``.

    Otherwise the poll fires once and the configured cadence has no effect.
    Shared by ``WaitFor`` and ``PostClickSignal`` (whose after-validators were
    byte-identical copies of this check).
    """
    if interval > timeout:
        raise ValueError(
            f"interval ({interval}s) must not exceed timeout "
            f"({timeout}s) — otherwise the poll fires once and the "
            "configured polling cadence has no effect"
        )


class PostClickSignal(BaseModel):
    """Image template that must appear on screen after a click to confirm completion."""

    model_config = _STRICT

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    timeout: float = Field(default=5.0, gt=0.0)
    interval: float = Field(default=0.1, gt=0.0)
    region: tuple[int, int, int, int] | None = None
    """Optional search rectangle ``(left, top, width, height)`` to scope the
    post-click poll, mirroring ``WaitFor.region``. Restricting the search to
    the area where the signal is expected (e.g. a toast region) speeds up
    matching and avoids false hits elsewhere on screen. ``None`` polls the
    full screen."""

    @model_validator(mode="after")
    def _validate_fields(self) -> PostClickSignal:
        _validate_region(self.region)
        _validate_poll_interval_within_timeout(
            interval=self.interval, timeout=self.timeout
        )
        return self


class WaitFor(BaseModel):
    """Image template that must appear on screen BEFORE clicking (pre-click guard).

    Replaces the prior ``trigger_wait`` mission. Polled with the same
    ``locateCenterOnScreen`` mechanism as ``PostClickSignal`` but its outcome
    gates whether the click is dispatched at all.
    """

    model_config = _STRICT

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    timeout: float = Field(default=5.0, gt=0.0)
    interval: float = Field(default=0.1, gt=0.0)
    region: tuple[int, int, int, int] | None = None

    @model_validator(mode="after")
    def _validate_fields(self) -> WaitFor:
        _validate_region(self.region)
        _validate_poll_interval_within_timeout(
            interval=self.interval, timeout=self.timeout
        )
        return self


class StepCoord(BaseModel):
    """Fixed pixel coordinate target for a Step.

    Used as the value of ``Step.coord``. Kept as a structured nested model
    rather than top-level ``x``/``y`` fields so the recipe YAML reads naturally
    (``coord: {x: 800, y: 500}``) and the click-target shape stays disjoint
    from image-target parameters.
    """

    model_config = _STRICT

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
    only meaningful when ``image`` is set; declaring them on a coord-only
    step is rejected at parse time (they would otherwise be silently
    ignored). ``wait_for`` is a pre-click guard; ``verify_transition`` and
    ``post_click_signal`` are post-click guards.
    """

    model_config = _STRICT

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
    settle_ms: int = Field(default=300, ge=0, le=10_000)
    """Post-click settle delay before reading cursor and (if configured)
    capturing the post-click frame for transition diff. The legacy hard-coded
    50 ms was too tight for React/DOM-driven web UI — frequently the visual
    update completed *after* the settle window, producing false
    ``PageTransitionNotDetected`` failures even on successful clicks. The new
    default of 300 ms accommodates typical web render latency while keeping
    instant-visual scenarios responsive. Set lower (e.g. ``50``) for native
    UI that toggles instantly; set higher (e.g. ``800``) for heavy SPAs."""

    @model_validator(mode="after")
    def _validate_target_and_prefer(self) -> Step:
        # Step names flow into action-log JSONL filenames
        # (action_log_writer.action_key_for_mission). A name with a path
        # separator or '..' would let a recipe write JSONL files outside the
        # run root (confirmed path-traversal vector). Reject those at parse
        # time. Kept permissive otherwise (underscores, dots, unicode are
        # fine) — only filesystem-escaping characters are forbidden.
        _validate_step_name(self.name)
        # Region rectangles must have positive extent (catches the common
        # [x1,y1,x2,y2]-instead-of-[x,y,w,h] mistake before it reaches the
        # adapter's PIL crop / locateCenterOnScreen calls).
        _validate_region(self.region)
        _validate_region(self.transition_region)
        # At least one of image/coord must be declared.
        if self.image is None and self.coord is None:
            raise ValueError(
                f"Step '{self.name}': must declare at least one of 'image' or 'coord'"
            )
        # Image-match parameters are meaningless without an image target.
        # On a coord-only step they would be silently ignored at dispatch —
        # which defeats the strict-schema typo guard (a misplaced field would
        # pass unnoticed). Reject them so the author learns the field has no
        # effect here, mirroring how extra="forbid" rejects unknown keys.
        if self.image is None:
            dead = [
                n
                for n, v in (
                    ("region", self.region),
                    ("confidence", self.confidence),
                    ("grayscale", self.grayscale),
                )
                if v is not None
            ]
            if dead:
                raise ValueError(
                    f"Step '{self.name}': image-match field(s) {dead} have no "
                    "effect on a coord-only step (no 'image' declared). Remove "
                    "them, or add an 'image' target."
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

    model_config = _STRICT

    x: int
    y: int
    verify_transition: bool = False
    transition_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    transition_region: tuple[int, int, int, int] | None = None
    post_click_signal: PostClickSignal | None = None

    @model_validator(mode="after")
    def _validate_after(self) -> MissionClick:
        # Calls the module-level _validate_region (a different name than this
        # method had — the prior identical name read like self-recursion).
        _validate_region(self.transition_region)
        return self


class MissionImageClick(BaseModel):
    """An image-template target resolved to coordinates at click time.

    The adapter locates the template on screen via
    ``pyautogui.locateCenterOnScreen`` (OpenCV-backed when ``confidence`` is
    set) and clicks the center of the first match. Region restricts the
    search rectangle to ``(left, top, width, height)`` for speed.
    """

    model_config = _STRICT

    image: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    region: tuple[int, int, int, int] | None = None
    grayscale: bool = False
    verify_transition: bool = False
    transition_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    transition_region: tuple[int, int, int, int] | None = None
    post_click_signal: PostClickSignal | None = None

    @model_validator(mode="after")
    def _validate_regions(self) -> MissionImageClick:
        _validate_region(self.region)
        _validate_region(self.transition_region)
        return self


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

    model_config = _STRICT

    # Only schema v1 exists. Constraining to ``Literal[1]`` makes a recipe
    # authored against a hypothetical future schema (``version: 2``) fail
    # fast at parse time instead of loading as if it were v1 — the field
    # advertises forward-compat gating, so it must actually gate.
    version: Literal[1] = 1
    steps: list[Step] | None = None
    missions: dict[str, MissionTarget] = Field(
        default_factory=dict,
        # Emits `"deprecated": true` in the JSON Schema (--recipe-schema) so a
        # structure-driven LLM/tool gets a machine-readable signal, not just the
        # prose "Legacy" note, that `missions` is the deprecated shape. Uses
        # json_schema_extra (schema-only) rather than Field(deprecated=...),
        # which would also emit a runtime warning on every internal access of
        # self.missions during normalization.
        json_schema_extra={"deprecated": True},
    )

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
            # warnings.warn is invisible on the real CLI (Python suppresses
            # DeprecationWarning from library code by default), so also emit a
            # WARNING log line through the coord_smith logger the CLI configures
            # — otherwise the documented stderr migration nudge never appears.
            _log.warning(
                "recipe declares both 'steps' and 'missions'; using 'steps' "
                "(authoritative). 'missions' is deprecated — migrate to 'steps:'."
            )
            warnings.warn(
                "ClickRecipe declares both 'steps' and 'missions'; 'steps' "
                "is the source of truth. Migrate the recipe to use 'steps:' "
                "exclusively — 'missions' is deprecated.",
                DeprecationWarning,
                # Pydantic invokes model validators ~3 frames deep from the
                # caller's ``model_validate`` / load_click_recipe call. A
                # ``stacklevel=2`` would point at Pydantic internals; bump
                # to a level that lands closer to user code without being
                # so high it overshoots into the test runner.
                stacklevel=4,
            )
            return self
        if not has_steps and has_missions:
            # See above — surface the deprecation on the real CLI via the logger,
            # not just warnings.warn (which the default filter hides).
            _log.warning(
                "recipe uses the deprecated 'missions' shape; auto-normalizing "
                "to 'steps'. Migrate the recipe to use 'steps:'."
            )
            warnings.warn(
                "ClickRecipe 'missions' shape is deprecated; auto-normalizing "
                "to 'steps'. Migrate the recipe to use 'steps:'.",
                DeprecationWarning,
                stacklevel=4,
            )
            self.steps = [
                _mission_to_step(name, target)
                for name, target in self.missions.items()
            ]
        return self

    @model_validator(mode="after")
    def _validate_step_names_unique(self) -> ClickRecipe:
        """Reject recipes whose step names collide.

        The adapter writes per-step action-log entries to JSONL files
        named after ``step.name`` (see ``_action_key_for_mission``).
        Two steps with the same name would silently append into the
        same file, making post-hoc per-step audit impossible. Failing
        at parse time gives the recipe author an immediate, actionable
        error instead of producing a confusing artifact tree at run
        time.

        Runs after ``_normalize_steps`` so the check covers both the
        canonical ``steps:`` shape and the legacy ``missions:`` shape
        (which is normalized to steps before this validator fires).
        """
        if self.steps is None or len(self.steps) < 2:
            return self
        seen: set[str] = set()
        duplicates: list[str] = []
        for step in self.steps:
            if step.name in seen and step.name not in duplicates:
                duplicates.append(step.name)
            seen.add(step.name)
        if duplicates:
            raise ValueError(
                "ClickRecipe step names must be unique within a recipe — "
                "duplicate names cause per-step action-log JSONL files to "
                "collide on disk, making per-step audit ambiguous. "
                f"Duplicates: {duplicates}. "
                "Rename one of each pair, e.g. add a suffix "
                "('confirm' → 'confirm-1' / 'confirm-2')."
            )
        return self

    def coords_for(self, mission_name: str) -> tuple[int, int] | None:
        """Return static coordinates for the step with the given name.

        TEST-ONLY accessor — no production caller (the live click path resolves
        coords via ``coord_resolver.resolve_step_click_coords``, reading
        ``step.coord`` directly). Kept as a convenient probe for recipe-loading
        tests. Returns the step's coord ``(x, y)`` if it has one, else ``None``.
        """
        if self.steps is None:
            return None
        for step in self.steps:
            if step.name == mission_name and step.coord is not None:
                return (step.coord.x, step.coord.y)
        return None

    def image_target_for(self, mission_name: str) -> MissionImageClick | None:
        """Return image template config for the step with the given name.

        TEST-ONLY accessor — no production caller (the live path reads
        ``step.image`` via ``coord_resolver.locate_image_for_step``). Kept as a
        recipe-loading test probe; wraps the step's image fields back into a
        ``MissionImageClick``. Returns ``None`` if the step has no image target.
        """
        if self.steps is None:
            return None
        for step in self.steps:
            if step.name == mission_name and step.image is not None:
                return MissionImageClick(
                    image=step.image,
                    confidence=step.confidence
                    if step.confidence is not None
                    else DEFAULT_IMAGE_CONFIDENCE,
                    region=step.region,
                    grayscale=step.grayscale
                    if step.grayscale is not None
                    else DEFAULT_IMAGE_GRAYSCALE,
                    verify_transition=step.verify_transition,
                    transition_threshold=step.transition_threshold,
                    transition_region=step.transition_region,
                    post_click_signal=step.post_click_signal,
                )
        return None


def _steps_mirror_missions(
    steps: list[Step] | None, missions: dict[str, MissionTarget]
) -> bool:
    """True when ``steps`` was derived from ``missions`` (legacy-only path).

    ``_normalize_steps`` populates ``steps`` from ``missions`` only when the
    recipe declared ``missions`` alone; in that case the step names are
    exactly the mission keys. When a recipe declares BOTH, ``steps`` is the
    author's own list and does NOT mirror ``missions`` — so the missions
    block is superseded leftover, not a live source to existence-check.
    """
    if not steps or not missions:
        return False
    return [s.name for s in steps] == list(missions.keys())


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
    if not path.is_file():
        # A directory (or other non-file) passed to --click-recipe would
        # otherwise raise a raw IsADirectoryError from read_text → generic
        # exit 1. Map it to the documented config-error (exit 3).
        raise ConfigError(f"click recipe is not a readable file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        # Unreadable file (permissions, I/O error, decode error) → config
        # error, not a generic runtime crash.
        raise ConfigError(
            f"click recipe {path} could not be read: {exc}"
        ) from exc
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

    def _resolve(image: str, *, owner: str, role: str) -> ResolvedImagePath:
        """Resolve an image path against the recipe directory AND
        existence-check it on disk. The return type signals to
        downstream consumers (image matching, wait_for, signal
        polling) that THIS path has been verified — see
        ``coord_smith.models.identifiers.ResolvedImagePath``.

        Note: the Pydantic field annotations on ``Step.image`` /
        ``WaitFor.image`` / ``PostClickSignal.image`` remain ``str``
        (not ``ResolvedImagePath``) because Pydantic validates on
        construction, before this resolver has run, and external
        callers may construct Step instances directly via
        ``model_construct`` bypassing both Pydantic validators and
        ``load_click_recipe``. The adapter performs its own
        defense-in-depth existence check at the boundary via
        ``PyAutoGUIAdapter._assert_template_exists``. The NewType is
        documentation-level; the adapter check is the runtime gate.
        """
        img_path = Path(image)
        if not img_path.is_absolute():
            img_path = (base_dir / img_path).resolve()
        if not img_path.exists():
            raise ConfigError(
                f"click recipe {path} references missing {role} template "
                f"for {owner}: {img_path}"
            )
        return ResolvedImagePath(str(img_path))

    # Resolve image paths in legacy ``missions`` ONLY when the missions block
    # is the live source — i.e. each mission was normalized into a step (the
    # step list mirrors the missions). When a recipe declares BOTH ``steps``
    # and ``missions``, ``_normalize_steps`` keeps ``steps`` as the source of
    # truth and leaves the (now superseded) ``missions`` in place for
    # backward-compat reads. Existence-checking those dead templates would
    # hard-fail an otherwise-valid recipe whose live steps are all present,
    # so skip them — only the live step list (resolved below) gates loading.
    missions_superseded_by_steps = bool(recipe.missions) and not _steps_mirror_missions(
        recipe.steps, recipe.missions
    )
    if recipe.missions and not missions_superseded_by_steps:
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
