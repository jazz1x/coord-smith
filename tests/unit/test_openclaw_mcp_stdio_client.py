from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import pytest

from ez_ax.adapters.openclaw.mcp_stdio_client import open_mcp_stdio_openclaw_adapter
from ez_ax.config.mcp_stdio import (
    McpStdioConstructorConfig,
    resolve_mcp_stdio_constructor_config,
)
from ez_ax.models.errors import ConfigError, ExecutionTransportError
from tests.fixtures.fake_mcp_sdk import (
    FakeCallToolResult,
    FakeStdioClient,
    FakeStdioServerParameters,
    install_fake_mcp_sdk,
)


class FakeClientSession:
    def __init__(self, read: object, write: object) -> None:
        self.read = read
        self.write = write
        self.initialize_called = 0
        self.tool_calls: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> FakeClientSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    async def initialize(self) -> None:
        self.initialize_called += 1

    async def call_tool(self, tool_name: str, *, arguments: dict[str, object]) -> Any:
        self.tool_calls.append((tool_name, arguments))
        return FakeCallToolResult(structured_content={"tool": tool_name, "ok": True})


class FakeClientSessionPositional(FakeClientSession):
    async def call_tool(self, tool_name: str, tool_input: dict[str, object]) -> Any:  # type: ignore[override]
        self.tool_calls.append((tool_name, tool_input))
        return FakeCallToolResult(structured_content={"tool": tool_name, "ok": True})


class FakeClientSessionNoStructuredAttr(FakeClientSession):
    async def call_tool(self, tool_name: str, *, arguments: dict[str, object]) -> Any:
        self.tool_calls.append((tool_name, arguments))
        return {"tool": tool_name, "ok": True}


class FakeClientSessionNeverReturns(FakeClientSession):
    async def call_tool(self, tool_name: str, *, arguments: dict[str, object]) -> Any:
        self.tool_calls.append((tool_name, arguments))
        await asyncio.Event().wait()
        raise AssertionError("unreachable")  # pragma: no cover


class FakeClientSessionInitFails(FakeClientSession):
    async def initialize(self) -> None:
        raise RuntimeError("init boom")


class FakeStdioClientRaises(FakeStdioClient):
    @asynccontextmanager
    async def stdio_client(self, server_params: object):  # type: ignore[override]
        raise RuntimeError("stdio boom")
        yield ("unreachable", "unreachable")  # pragma: no cover


@dataclass(frozen=True, slots=True)
class RootStdioServerParameters:
    command: str
    args: list[str]
    env: dict[str, str]


@pytest.mark.asyncio
async def test_resolve_mcp_stdio_constructor_config_prefers_explicit_over_config() -> (
    None
):
    config = McpStdioConstructorConfig(
        command="uv",
        args=("run", "server"),
        env={"A": "B"},
        tool_name="openclaw.execute",
        timeout_seconds=1.0,
        max_attempts=2,
    )

    resolved = resolve_mcp_stdio_constructor_config(
        command="python",
        args=["-m", "server"],
        env={"C": "D"},
        tool_name="other.tool",
        timeout_seconds=2.5,
        max_attempts=1,
        config=config,
    )

    assert resolved.command == "python"
    assert resolved.args == ("-m", "server")
    assert resolved.env == {"C": "D"}
    assert resolved.tool_name == "other.tool"
    assert resolved.timeout_seconds == 2.5
    assert resolved.max_attempts == 1


@pytest.mark.asyncio
async def test_resolve_mcp_stdio_constructor_config_allows_empty_env_values() -> None:
    resolved = resolve_mcp_stdio_constructor_config(
        command="uv",
        args=["run", "server"],
        env={"UV_INDEX": ""},
        tool_name="openclaw.execute",
        timeout_seconds=1.0,
    )

    assert resolved.env == {"UV_INDEX": ""}


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_fails_fast_on_missing_inputs() -> None:
    try:
        async with open_mcp_stdio_openclaw_adapter():
            raise AssertionError("unexpected")
    except ConfigError as exc:
        assert "Missing required MCP stdio constructor input" in str(exc)
    else:
        raise AssertionError("Expected missing inputs to raise ConfigError")


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_requires_explicit_server_name() -> None:
    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server"],
            env={},
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ConfigError as exc:
        assert "mcp_server_name" in str(exc)
    else:
        raise AssertionError("Expected missing mcp_server_name to raise ConfigError")


@pytest.mark.asyncio
async def test_open_mcp_stdio_adapter_import_error_maps_to_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ez_ax.adapters.openclaw.mcp_stdio_client as mcp_stdio_client_mod

    original_import_module = mcp_stdio_client_mod.importlib.import_module

    def fake_import_module(name: str, package: str | None = None):  # noqa: ANN001
        if name == "mcp":
            raise ImportError("simulated mcp import failure")
        return original_import_module(name, package=package)

    monkeypatch.setattr(
        mcp_stdio_client_mod.importlib,
        "import_module",
        fake_import_module,
    )

    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server"],
            env={},
            mcp_server_name="stdio",
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ExecutionTransportError as exc:
        assert "import" in str(exc).lower()
        assert "mcp" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected missing mcp import to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_builds_session_and_wraps_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdio = FakeStdioClient()
    install_fake_mcp_sdk(monkeypatch, stdio=stdio, client_session_cls=FakeClientSession)

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={"X": ""},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
        max_attempts=2,
    ) as adapter:
        assert adapter.settings.tool_name == "openclaw.execute"
        assert adapter.settings.default_timeout_seconds == 1.5
        assert adapter.settings.retry_policy.max_attempts == 2

        result = await adapter.mcp_client.call_tool(
            server_name="stdio",
            tool_name="openclaw.execute",
            tool_input={"a": 1},
            timeout_seconds=0.25,
        )
        assert result == {"tool": "openclaw.execute", "ok": True}

        try:
            await adapter.mcp_client.call_tool(
                server_name="other",
                tool_name="openclaw.execute",
                tool_input={},
                timeout_seconds=0.25,
            )
        except ConfigError as exc:
            assert "unexpected server_name" in str(exc)
        else:
            raise AssertionError("Expected server_name mismatch to raise ConfigError")

    assert isinstance(stdio.last_server_params, FakeStdioServerParameters)
    assert stdio.last_server_params.command == "uv"
    assert stdio.last_server_params.args == ["run", "server", "openclaw", "stdio"]
    assert stdio.last_server_params.env == {"X": ""}


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_uses_root_stdio_server_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdio_client = FakeStdioClient()

    mcp_mod = ModuleType("mcp")
    mcp_mod.StdioServerParameters = RootStdioServerParameters  # type: ignore[attr-defined]

    stdio_mod = ModuleType("mcp.client.stdio")
    stdio_mod.stdio_client = stdio_client.stdio_client  # type: ignore[attr-defined]

    session_mod = ModuleType("mcp.client.session")
    session_mod.ClientSession = FakeClientSession  # type: ignore[attr-defined]

    client_pkg = ModuleType("mcp.client")

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_pkg)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.session", session_mod)

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={"X": ""},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
    ) as adapter:
        result = await adapter.mcp_client.call_tool(
            server_name="stdio",
            tool_name="openclaw.execute",
            tool_input={"a": 1},
            timeout_seconds=0.25,
        )
        assert result == {"tool": "openclaw.execute", "ok": True}

    assert isinstance(stdio_client.last_server_params, RootStdioServerParameters)
    assert stdio_client.last_server_params.command == "uv"


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_supports_positional_server_params_ctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PositionalStdioServerParameters:
        def __init__(self, command: str, args: list[str], env: dict[str, str]) -> None:
            self.command = command
            self.args = args
            self.env = env

    stdio_client = FakeStdioClient()

    mcp_mod = ModuleType("mcp")
    stdio_mod = ModuleType("mcp.client.stdio")
    session_mod = ModuleType("mcp.client.session")
    client_pkg = ModuleType("mcp.client")

    stdio_mod.StdioServerParameters = PositionalStdioServerParameters  # type: ignore[attr-defined]
    stdio_mod.stdio_client = stdio_client.stdio_client  # type: ignore[attr-defined]
    session_mod.ClientSession = FakeClientSession  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_pkg)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.session", session_mod)

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={"X": ""},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
    ) as adapter:
        result = await adapter.mcp_client.call_tool(
            server_name="stdio",
            tool_name="openclaw.execute",
            tool_input={"a": 1},
            timeout_seconds=0.25,
        )
        assert result == {"tool": "openclaw.execute", "ok": True}

    assert stdio_client.last_server_params is not None
    params = stdio_client.last_server_params
    assert getattr(params, "command", None) == "uv"


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_supports_positional_call_tool_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdio = FakeStdioClient()
    install_fake_mcp_sdk(
        monkeypatch, stdio=stdio, client_session_cls=FakeClientSessionPositional
    )

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
    ) as adapter:
        result = await adapter.mcp_client.call_tool(
            server_name="stdio",
            tool_name="openclaw.execute",
            tool_input={"a": 1},
            timeout_seconds=0.25,
        )

        assert result == {"tool": "openclaw.execute", "ok": True}
        mcp_client_session = getattr(adapter.mcp_client, "session", None)
        assert isinstance(mcp_client_session, FakeClientSessionPositional)
        assert mcp_client_session.tool_calls == [("openclaw.execute", {"a": 1})]


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_passes_through_unstructured_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdio = FakeStdioClient()
    install_fake_mcp_sdk(
        monkeypatch,
        stdio=stdio,
        client_session_cls=FakeClientSessionNoStructuredAttr,
    )

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
    ) as adapter:
        result = await adapter.mcp_client.call_tool(
            server_name="stdio",
            tool_name="openclaw.execute",
            tool_input={"a": 1},
            timeout_seconds=0.25,
        )

        assert result == {"tool": "openclaw.execute", "ok": True}


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_maps_tool_timeout_to_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch, client_session_cls=FakeClientSessionNeverReturns)

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.0,
    ) as adapter:
        try:
            await adapter.mcp_client.call_tool(
                server_name="stdio",
                tool_name="openclaw.execute",
                tool_input={"a": 1},
                timeout_seconds=0.001,
            )
        except ExecutionTransportError as exc:
            assert "timed out" in str(exc).lower()
        else:
            raise AssertionError(
                "Expected tool timeout to raise ExecutionTransportError"
            )


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_maps_initialize_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_mcp_sdk(monkeypatch, client_session_cls=FakeClientSessionInitFails)

    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server", "openclaw", "stdio"],
            env={},
            mcp_server_name="stdio",
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ExecutionTransportError as exc:
        assert "acquisition failed" in str(exc).lower()
        assert "init boom" in str(exc)
    else:
        raise AssertionError(
            "Expected initialize failure to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_maps_missing_stdio_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ez_ax.adapters.openclaw.mcp_stdio_client as mcp_stdio_client_mod

    original_import_module = mcp_stdio_client_mod.importlib.import_module

    def fake_import_module(name: str, package: str | None = None):  # noqa: ANN001
        if name == "mcp":
            return ModuleType("mcp")
        if name == "mcp.client.stdio":
            raise ImportError("simulated stdio import failure")
        return original_import_module(name, package=package)

    monkeypatch.setattr(
        mcp_stdio_client_mod.importlib,
        "import_module",
        fake_import_module,
    )

    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server", "openclaw", "stdio"],
            env={},
            mcp_server_name="stdio",
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ExecutionTransportError as exc:
        msg = str(exc).lower()
        assert "stdio transport import failed" in msg
        assert "mcp.client.stdio" in msg
    else:
        raise AssertionError(
            "Expected missing mcp.client.stdio import to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_maps_stdio_client_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdio = FakeStdioClientRaises()
    install_fake_mcp_sdk(monkeypatch, stdio=stdio, client_session_cls=FakeClientSession)

    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server", "openclaw", "stdio"],
            env={},
            mcp_server_name="stdio",
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ExecutionTransportError as exc:
        msg = str(exc).lower()
        assert "acquisition failed" in msg
        assert "stdio boom" in msg
    else:
        raise AssertionError(
            "Expected stdio_client failure to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_rejects_missing_structured_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClientSessionMissingStructured(FakeClientSession):
        async def call_tool(  # type: ignore[override]
            self, tool_name: str, *, arguments: dict[str, object]
        ) -> Any:
            return FakeCallToolResult(structured_content=None)

    stdio = FakeStdioClient()
    install_fake_mcp_sdk(
        monkeypatch,
        stdio=stdio,
        client_session_cls=FakeClientSessionMissingStructured,
    )

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={"X": "Y"},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
    ) as adapter:
        try:
            await adapter.mcp_client.call_tool(
                server_name="stdio",
                tool_name="openclaw.execute",
                tool_input={"a": 1},
                timeout_seconds=0.25,
            )
        except ExecutionTransportError as exc:
            assert "structured_content" in str(exc)
        else:
            raise AssertionError(
                "Expected missing structured_content to raise ExecutionTransportError"
            )


def _install_broken_mcp_sdk(
    monkeypatch: pytest.MonkeyPatch, *, missing: set[str]
) -> None:
    mcp_mod = ModuleType("mcp")
    stdio_mod = ModuleType("mcp.client.stdio")
    session_mod = ModuleType("mcp.client.session")
    client_pkg = ModuleType("mcp.client")

    if "ClientSession" not in missing:
        session_mod.ClientSession = FakeClientSession  # type: ignore[attr-defined]
    if "StdioServerParameters" not in missing:
        stdio_mod.StdioServerParameters = FakeStdioServerParameters  # type: ignore[attr-defined]
    if "stdio_client" not in missing:
        stdio_mod.stdio_client = FakeStdioClient().stdio_client  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_pkg)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.session", session_mod)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing",
    [
        {"ClientSession"},
        {"StdioServerParameters"},
        {"stdio_client"},
    ],
)
async def test_open_mcp_stdio_adapter_missing_sdk_symbols_maps_to_transport_error(
    monkeypatch: pytest.MonkeyPatch,
    missing: set[str],
) -> None:
    _install_broken_mcp_sdk(monkeypatch, missing=missing)

    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server", "openclaw", "stdio"],
            env={},
            mcp_server_name="stdio",
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ExecutionTransportError as exc:
        message = str(exc)
        assert "missing required sdk symbols" in message.lower()
        for symbol in missing:
            assert symbol in message
    else:
        raise AssertionError(
            "Expected missing MCP SDK symbols to raise transport error"
        )


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_uses_root_client_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdio_client = FakeStdioClient()

    mcp_mod = ModuleType("mcp")
    stdio_mod = ModuleType("mcp.client.stdio")
    client_pkg = ModuleType("mcp.client")

    mcp_mod.ClientSession = FakeClientSession  # type: ignore[attr-defined]
    stdio_mod.StdioServerParameters = FakeStdioServerParameters  # type: ignore[attr-defined]
    stdio_mod.stdio_client = stdio_client.stdio_client  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_pkg)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)
    monkeypatch.delitem(sys.modules, "mcp.client.session", raising=False)

    async with open_mcp_stdio_openclaw_adapter(
        command="uv",
        args=["run", "server", "openclaw", "stdio"],
        env={},
        mcp_server_name="stdio",
        tool_name="openclaw.execute",
        timeout_seconds=1.5,
    ) as adapter:
        result = await adapter.mcp_client.call_tool(
            server_name="stdio",
            tool_name="openclaw.execute",
            tool_input={"a": 1},
            timeout_seconds=0.25,
        )

        assert result == {"tool": "openclaw.execute", "ok": True}


@pytest.mark.asyncio
async def test_open_mcp_stdio_openclaw_adapter_maps_server_params_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RaisingStdioServerParameters:
        def __init__(
            self,
            *,
            command: str,
            args: list[str],
            env: dict[str, str],  # noqa: ARG002
        ) -> None:
            raise RuntimeError("boom")

    mcp_mod = ModuleType("mcp")
    stdio_mod = ModuleType("mcp.client.stdio")
    session_mod = ModuleType("mcp.client.session")
    client_pkg = ModuleType("mcp.client")

    stdio_mod.StdioServerParameters = RaisingStdioServerParameters  # type: ignore[attr-defined]
    stdio_mod.stdio_client = FakeStdioClient().stdio_client  # type: ignore[attr-defined]
    session_mod.ClientSession = FakeClientSession  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_pkg)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.session", session_mod)

    try:
        async with open_mcp_stdio_openclaw_adapter(
            command="uv",
            args=["run", "server", "openclaw", "stdio"],
            env={},
            mcp_server_name="stdio",
            tool_name="openclaw.execute",
            timeout_seconds=1.0,
        ):
            raise AssertionError("unexpected")
    except ExecutionTransportError as exc:
        assert "server parameter construction failed" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected server parameter construction failure to raise transport error"
        )
