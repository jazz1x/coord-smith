"""Contract: the recipe example in CLAUDE.md is canonical and parses cleanly.

CLAUDE.md is the agent-facing source of truth for this repository.
When an LLM agent generates a click recipe based on the example in
CLAUDE.md, that recipe must:

1. Parse against the released ClickRecipe schema.
2. Use the current canonical shape (``steps:``), not the legacy
   deprecated ``missions:`` shape — otherwise every agent-generated
   recipe pays a ``DeprecationWarning`` and the example is teaching the
   wrong shape.
3. Demonstrate the released fields agents are most likely to need:
   ``wait_for``, ``settle_ms``, ``post_click_signal``,
   ``verify_transition``. If the example skips a released field, agents
   will never reach for it.

This test extracts the first ``yaml`` fenced block from CLAUDE.md and
validates against the schema. It runs as a contract test because the
file's correctness is part of the agent ↔ runtime API surface.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest
import yaml

from coord_smith.config.click_recipe import ClickRecipe

CLAUDE_MD = Path("CLAUDE.md")


def _extract_recipe_yaml_block(text: str) -> str:
    """Pull the recipe-example YAML block out of CLAUDE.md.

    CLAUDE.md contains several ```yaml fenced blocks (system boundary,
    input contract, output contract, recipe example). The recipe example
    is the one that declares ``version:`` AND uses either ``steps:`` or
    ``missions:``. We scan all yaml fences and pick the first match.
    """
    blocks = re.findall(r"```yaml\n(.*?)```", text, flags=re.DOTALL)
    assert blocks, "CLAUDE.md must contain at least one ```yaml fenced block"
    for snippet in blocks:
        if "version:" in snippet and ("steps:" in snippet or "missions:" in snippet):
            return snippet
    raise AssertionError(
        "CLAUDE.md must contain a recipe-example YAML block declaring "
        "both 'version:' and 'steps:' (or 'missions:')"
    )


def test_claude_md_recipe_example_parses() -> None:
    """The first YAML block in CLAUDE.md parses to a valid ClickRecipe."""
    assert CLAUDE_MD.is_file(), "CLAUDE.md must exist in repo root"
    text = CLAUDE_MD.read_text(encoding="utf-8")
    snippet = _extract_recipe_yaml_block(text)
    data = yaml.safe_load(snippet)
    recipe = ClickRecipe.model_validate(data)
    assert recipe.steps is not None and len(recipe.steps) > 0


def test_claude_md_recipe_example_does_not_emit_deprecation_warning() -> None:
    """Agents reading CLAUDE.md must not be taught the deprecated shape.

    If this test starts failing because CLAUDE.md uses ``missions:``,
    the fix is to update CLAUDE.md to the canonical ``steps:`` shape —
    NOT to silence the warning here. The whole point is that every
    agent-generated recipe based on the example stays warning-free.
    """
    text = CLAUDE_MD.read_text(encoding="utf-8")
    snippet = _extract_recipe_yaml_block(text)
    data = yaml.safe_load(snippet)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        ClickRecipe.model_validate(data)
    deprecation_msgs = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deprecation_msgs, (
        "CLAUDE.md recipe example triggers DeprecationWarning(s):\n  "
        + "\n  ".join(deprecation_msgs)
        + "\n\nUpdate CLAUDE.md §클릭 규칙 포맷 to use 'steps:' instead "
        "of 'missions:'."
    )


def test_claude_md_recipe_example_uses_canonical_steps_shape() -> None:
    """The example must show ``steps:`` at the top level. ``missions:``
    in the same block is acceptable only if also accompanied by
    ``steps:`` (highly discouraged), but the test asserts the
    happy-path canonical case."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    snippet = _extract_recipe_yaml_block(text)
    data = yaml.safe_load(snippet)
    assert isinstance(data, dict), (
        "CLAUDE.md recipe example must be a YAML mapping, got "
        f"{type(data).__name__}"
    )
    assert "steps" in data, (
        "CLAUDE.md recipe example must declare 'steps:' as its top-level "
        "click sequence — that's the canonical shape new recipes must use"
    )
    assert "missions" not in data, (
        "CLAUDE.md recipe example must not use the deprecated 'missions:' "
        "shape — agents reading the example will copy whatever they see"
    )


@pytest.mark.parametrize(
    "field_token",
    [
        "wait_for",
        "settle_ms",
        "verify_transition",
        "post_click_signal",
        "prefer",
    ],
)
def test_claude_md_example_mentions_released_fields(field_token: str) -> None:
    """The example must reference each released field at least once —
    even if commented out — so agents discover the surface area.

    Test fails if a released field disappears from the example. The
    fix is to add it back (uncommented or commented), not to remove
    the parametrize entry. New released fields should be added to the
    parametrize list when they ship.
    """
    snippet = _extract_recipe_yaml_block(
        CLAUDE_MD.read_text(encoding="utf-8")
    )
    assert field_token in snippet, (
        f"CLAUDE.md recipe example must reference the released field "
        f"'{field_token}' (uncommented or commented) so agents reading the "
        "example know it exists"
    )
