"""Tests for coord_smith.cli_logging — level resolution + handler hygiene."""

from __future__ import annotations

import io
import logging

import pytest

from coord_smith.cli_logging import (
    ENV_LOG_LEVEL,
    LOGGER_NAME,
    configure_logging,
    get_logger,
)


def _reset_logger() -> None:
    """Clear handlers we installed so each test starts from a clean
    baseline. Removes only OUR handlers (tagged) so pytest's caplog
    handlers — if any — survive."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, "_coord_smith_managed_handler", False):
            logger.removeHandler(handler)
    logger.setLevel(logging.WARNING)  # back to root default-ish


def test_default_level_is_info() -> None:
    _reset_logger()
    logger = configure_logging(env={})
    assert logger.level == logging.INFO


def test_env_var_overrides_default() -> None:
    _reset_logger()
    logger = configure_logging(env={ENV_LOG_LEVEL: "WARNING"})
    assert logger.level == logging.WARNING


def test_cli_level_overrides_env() -> None:
    _reset_logger()
    logger = configure_logging(
        level="DEBUG", env={ENV_LOG_LEVEL: "ERROR"}
    )
    assert logger.level == logging.DEBUG


def test_unknown_level_falls_back_to_info(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _reset_logger()
    logger = configure_logging(env={ENV_LOG_LEVEL: "BANANA"})
    assert logger.level == logging.INFO
    err = capsys.readouterr().err
    assert "unknown log level" in err.lower()


def test_repeat_configure_is_idempotent() -> None:
    """Two configure_logging calls must leave exactly ONE managed
    handler attached. Prevents handler leakage on tests that import
    the module multiple times."""
    _reset_logger()
    configure_logging(env={})
    configure_logging(env={})
    logger = logging.getLogger(LOGGER_NAME)
    managed = [
        h
        for h in logger.handlers
        if getattr(h, "_coord_smith_managed_handler", False)
    ]
    assert len(managed) == 1, (
        f"expected 1 managed handler, got {len(managed)}: {logger.handlers}"
    )


def test_writes_format_to_configured_stream() -> None:
    """Using an explicit stream lets tests capture output without
    monkey-patching sys.stderr."""
    _reset_logger()
    buf = io.StringIO()
    logger = configure_logging(level="INFO", stream=buf)
    logger.info("hello world")
    contents = buf.getvalue()
    # Format contract: "coord-smith: <LEVEL>: <message>".
    assert contents.startswith("coord-smith: INFO: hello world")


def test_get_logger_returns_named_child() -> None:
    sub = get_logger("cli")
    assert sub.name == f"{LOGGER_NAME}.cli"
    bare = get_logger()
    assert bare.name == LOGGER_NAME


def test_propagation_enabled_so_caplog_can_intercept(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pytest's caplog attaches to the root logger; if we set
    propagate=False, records never reach root and caplog sees
    nothing. Verify the production setting respects this."""
    _reset_logger()
    configure_logging(level="INFO", env={})
    logger = get_logger("test")
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        logger.info("intercept me")
    assert any(
        "intercept me" in record.getMessage() for record in caplog.records
    )
