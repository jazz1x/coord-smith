"""Standard-library logging configuration for the coord-smith CLI.

External orchestrators (e.g. OpenClaw) want to capture, filter, and
route coord-smith's diagnostic output. The earlier scaffold used
bare ``print(..., file=sys.stderr)`` for every diagnostic line —
fine for humans, but a wall to programmatic routing: there is no
level, no logger name, no formatter, and no way to silence the
chatty preflight lines without suppressing the actionable error
ones.

This module standardises diagnostics on the stdlib ``logging``
framework while preserving the same on-the-wire behaviour
(stderr, prefixed with ``coord-smith:``). Callers get a single
named logger they can override.

## Contract

- Logger name: ``coord_smith``. All package-internal logging
  uses ``logging.getLogger("coord_smith.<submodule>")``.
- Default destination: ``sys.stderr``.
- Default level: ``INFO``. Read from ``COORDSMITH_LOG_LEVEL`` env
  (case-insensitive ``DEBUG`` / ``INFO`` / ``WARNING`` / ``ERROR``
  / ``CRITICAL``) when set; explicit CLI flag (``--verbose`` /
  ``--quiet``) wins over env.
- Format: ``coord-smith: <level>: <message>`` — preserves the
  ``coord-smith:`` prefix downstream scripts may already grep
  for; the ``<level>:`` segment lets callers filter without
  parsing message bodies.
- Propagates to the root logger. We rely on the caller (the CLI
  ``main()``) to install exactly one handler; the
  ``coord_smith`` logger does not block propagation so test
  frameworks (pytest ``caplog``) and embedding applications can
  intercept records via the root logger. Duplicate-output risk
  exists only when an embedding app installs root handlers AND
  calls our ``configure_logging`` — that case is opt-in.

## Why not click / loguru / structlog?

The stdlib is sufficient — coord-smith emits at most O(10) lines
per run. Adding a logging dependency would violate the "small
runtime" principle (see ADR-001 references — minimal deps). The
named-logger contract is what callers need; the implementation
is one ``StreamHandler``.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import TextIO

LOGGER_NAME = "coord_smith"
ENV_LOG_LEVEL = "COORDSMITH_LOG_LEVEL"

_DEFAULT_LEVEL = logging.INFO
_FORMAT = "coord-smith: %(levelname)s: %(message)s"
_HANDLER_ATTR = "_coord_smith_managed_handler"


def _resolve_level(
    *, cli_level: str | None, env: dict[str, str] | None = None
) -> int:
    """CLI flag > env var > default INFO. Case-insensitive string.

    Returns the numeric logging level. Unknown strings fall back to
    the default with a stderr note, but do NOT raise — log
    configuration should never be the thing that kills a run.
    """
    chosen: str | None = cli_level
    if chosen is None:
        env_map = env if env is not None else dict(os.environ)
        chosen = env_map.get(ENV_LOG_LEVEL)
    if not chosen:
        return _DEFAULT_LEVEL
    chosen_norm = chosen.strip().upper()
    numeric = logging.getLevelNamesMapping().get(chosen_norm)
    if numeric is None:
        print(
            f"coord-smith: WARNING: unknown log level "
            f"{chosen!r}; defaulting to INFO. "
            f"Allowed: DEBUG / INFO / WARNING / ERROR / CRITICAL.",
            file=sys.stderr,
        )
        return _DEFAULT_LEVEL
    return numeric


def configure_logging(
    *,
    level: str | None = None,
    stream: TextIO | None = None,
    env: dict[str, str] | None = None,
) -> logging.Logger:
    """Install (idempotently) the coord_smith StreamHandler and return
    the configured logger.

    Resolution order for the level (highest priority first):

    1. ``level`` keyword argument (the CLI passes ``DEBUG`` for
       ``--verbose``, ``WARNING`` for ``--quiet``).
    2. ``COORDSMITH_LOG_LEVEL`` environment variable.
    3. Default ``INFO``.

    ``stream`` overrides the handler's destination (default
    ``sys.stderr``). Useful in tests for capturing output to a
    buffer without monkey-patching ``sys.stderr`` itself.
    """
    logger = logging.getLogger(LOGGER_NAME)
    # Propagate to root so pytest's caplog (which attaches to the
    # root logger) and embedding applications can intercept records.
    # See the module docstring for the duplicate-output trade-off.
    logger.propagate = True
    resolved_level = _resolve_level(cli_level=level, env=env)
    logger.setLevel(resolved_level)
    # Remove any handler we previously installed before adding the
    # new one — keeps configure_logging idempotent across repeat
    # calls (process restarts within the same test session, or a
    # caller reconfiguring mid-run) without leaking handlers that
    # point at stale streams. Tag our handler so we never remove
    # handlers installed by the embedding application.
    target_stream = stream or sys.stderr
    for existing in list(logger.handlers):
        if getattr(existing, _HANDLER_ATTR, False):
            logger.removeHandler(existing)
    handler = logging.StreamHandler(target_stream)
    handler.setFormatter(logging.Formatter(_FORMAT))
    setattr(handler, _HANDLER_ATTR, True)
    logger.addHandler(handler)
    return logger


def get_logger(suffix: str | None = None) -> logging.Logger:
    """Return ``coord_smith[.<suffix>]`` without (re)installing handlers.

    Internal modules call this — the handler is installed once by
    the CLI's ``main()``. Tests can call ``configure_logging`` with
    a custom stream and then this helper to get a named logger
    that respects the test configuration.
    """
    name = LOGGER_NAME if suffix is None else f"{LOGGER_NAME}.{suffix}"
    return logging.getLogger(name)
