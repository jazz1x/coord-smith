from __future__ import annotations

from ez_ax.config.mcp_stdio_cli import (
    resolve_mcp_stdio_constructor_config_from_argv,
    resolve_mcp_stdio_server_name_from_argv,
)
from ez_ax.models.errors import ConfigError


def test_mcp_stdio_cli_missing_required_inputs_fails_fast() -> None:
    try:
        resolve_mcp_stdio_constructor_config_from_argv(argv=[])
    except ConfigError as exc:
        assert "Missing required MCP stdio constructor input" in str(exc)
    else:
        raise AssertionError("Expected missing inputs to raise ConfigError")


def test_mcp_stdio_cli_parses_minimal_config_and_env_entries() -> None:
    cfg = resolve_mcp_stdio_constructor_config_from_argv(
        argv=[
            "--mcp-command",
            "uv",
            "--mcp-arg",
            "run",
            "--mcp-tool-name",
            "openclaw.execute",
            "--mcp-timeout-seconds",
            "1.5",
            "--mcp-env",
            "UV_INDEX=",
            "--mcp-env",
            "A=B",
            "--mcp-max-attempts",
            "2",
        ]
    )
    assert cfg.command == "uv"
    assert cfg.args == ("run",)
    assert cfg.tool_name == "openclaw.execute"
    assert cfg.timeout_seconds == 1.5
    assert cfg.env == {"UV_INDEX": "", "A": "B"}
    assert cfg.max_attempts == 2


def test_mcp_stdio_cli_rejects_env_entry_without_equals() -> None:
    try:
        resolve_mcp_stdio_constructor_config_from_argv(
            argv=[
                "--mcp-command",
                "uv",
                "--mcp-arg",
                "run",
                "--mcp-tool-name",
                "openclaw.execute",
                "--mcp-timeout-seconds",
                "1.0",
                "--mcp-env",
                "NOPE",
            ]
        )
    except ConfigError as exc:
        assert "KEY=VALUE" in str(exc)
    else:
        raise AssertionError("Expected invalid --mcp-env to raise ConfigError")


def test_mcp_stdio_cli_rejects_whitespace_wrapped_env_key() -> None:
    try:
        resolve_mcp_stdio_constructor_config_from_argv(
            argv=[
                "--mcp-command",
                "uv",
                "--mcp-arg",
                "run",
                "--mcp-tool-name",
                "openclaw.execute",
                "--mcp-timeout-seconds",
                "1.0",
                "--mcp-env",
                " A=B",
            ]
        )
    except ConfigError as exc:
        assert "whitespace-normalized" in str(exc)
    else:
        raise AssertionError("Expected whitespace env key to raise ConfigError")


def test_mcp_stdio_cli_requires_explicit_server_name() -> None:
    try:
        resolve_mcp_stdio_server_name_from_argv(argv=[])
    except ConfigError as exc:
        assert "mcp_server_name" in str(exc)
    else:
        raise AssertionError("Expected missing server name to raise ConfigError")


def test_mcp_stdio_cli_parses_server_name() -> None:
    server_name = resolve_mcp_stdio_server_name_from_argv(
        argv=["--mcp-server-name", "stdio"]
    )
    assert server_name == "stdio"
