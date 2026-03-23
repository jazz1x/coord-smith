from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Any, cast

import pytest


@dataclass(frozen=True, slots=True)
class FakeStdioServerParameters:
    command: str
    args: list[str]
    env: dict[str, str]


@dataclass(frozen=True, slots=True)
class FakeCallToolResult:
    structured_content: object


def observation(*, ref: str, value: object) -> dict[str, object]:
    kind, key = ref.split("://", 1)[1].split("/", 1)
    return {
        "ref": ref,
        "kind": kind,
        "key": key,
        "value": value,
    }


class ReleasedScopeFakeClientSession:
    def __init__(self, read: object, write: object) -> None:
        self.read = read
        self.write = write

    async def __aenter__(self) -> ReleasedScopeFakeClientSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def initialize(self) -> None:
        return None

    async def call_tool(self, tool_name: str, *, arguments: dict[str, object]) -> Any:
        mission_name = arguments.get("mission_name")
        if not isinstance(mission_name, str):
            raise AssertionError("expected mission_name to be a string")

        request_id = arguments.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            raise AssertionError("expected request_id to be a normalized string")

        evidence_refs_by_mission: dict[str, list[str]] = {
            "attach_session": [
                "evidence://text/session-attached",
                "evidence://text/auth-state-confirmed",
                "evidence://action-log/attach-session",
            ],
            "prepare_session": [
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ],
            "benchmark_validation": [
                "evidence://dom/target-page-entered",
                "evidence://action-log/enter-target-page",
            ],
            "page_ready_observation": [
                "evidence://dom/page-shell-ready",
                "evidence://action-log/release-ceiling-stop",
            ],
        }
        evidence_refs = evidence_refs_by_mission.get(mission_name)
        if evidence_refs is None:
            raise AssertionError(f"unexpected mission_name: {mission_name}")

        payload = {
            "mission_name": mission_name,
            "status": "success",
            "evidence_refs": evidence_refs,
            "observations": {
                ref: observation(ref=ref, value={"ok": True}) for ref in evidence_refs
            },
            "request_id": request_id,
        }
        return FakeCallToolResult(structured_content=payload)


@dataclass
class FakeStdioClient:
    last_server_params: object | None = None

    @asynccontextmanager
    async def stdio_client(
        self, server_params: object
    ) -> AsyncIterator[tuple[str, str]]:
        self.last_server_params = server_params
        yield ("read", "write")


def install_fake_mcp_sdk(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdio: FakeStdioClient | None = None,
    client_session_cls: type[ReleasedScopeFakeClientSession] = (
        ReleasedScopeFakeClientSession
    ),
) -> FakeStdioClient:
    """Install a minimal fake `mcp` stdio SDK into sys.modules for unit tests."""

    stdio_client = FakeStdioClient() if stdio is None else stdio

    mcp_mod = ModuleType("mcp")
    stdio_mod = ModuleType("mcp.client.stdio")
    session_mod = ModuleType("mcp.client.session")
    client_pkg = ModuleType("mcp.client")

    stdio_mod_any = cast(Any, stdio_mod)
    session_mod_any = cast(Any, session_mod)
    stdio_mod_any.StdioServerParameters = FakeStdioServerParameters
    stdio_mod_any.stdio_client = stdio_client.stdio_client
    session_mod_any.ClientSession = client_session_cls

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_pkg)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.session", session_mod)

    return stdio_client
