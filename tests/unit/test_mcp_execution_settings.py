from __future__ import annotations

import pytest

from ez_ax.adapters.execution.mcp_settings import (
    McpExecutionAdapterSettings,
    RetryPolicy,
)
from ez_ax.models.errors import ConfigError


def test_retry_policy_rejects_zero_attempts() -> None:
    with pytest.raises(ConfigError):
        RetryPolicy(max_attempts=0)


def test_adapter_settings_rejects_empty_mcp_server_name() -> None:
    with pytest.raises(ConfigError):
        McpExecutionAdapterSettings(
            mcp_server_name="",
            tool_name="openclaw.execute",
            default_timeout_seconds=5,
            retry_policy=RetryPolicy(max_attempts=1),
        )


def test_adapter_settings_rejects_whitespace_wrapped_tool_name() -> None:
    with pytest.raises(ConfigError):
        McpExecutionAdapterSettings(
            mcp_server_name="openclaw",
            tool_name=" openclaw.execute ",
            default_timeout_seconds=5,
            retry_policy=RetryPolicy(max_attempts=1),
        )


def test_adapter_settings_rejects_non_positive_timeout() -> None:
    with pytest.raises(ConfigError):
        McpExecutionAdapterSettings(
            mcp_server_name="openclaw",
            tool_name="openclaw.execute",
            default_timeout_seconds=0,
            retry_policy=RetryPolicy(max_attempts=1),
        )
