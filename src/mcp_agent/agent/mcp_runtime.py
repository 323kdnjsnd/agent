"""Official MCP stdio client wrapper used by the daily-brief orchestrator."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass(frozen=True)
class ServerDefinition:
    name: str
    module: str


SERVERS = {
    "news": ServerDefinition("mining-news-mcp", "mcp_agent.servers.mining_news"),
    "pdf": ServerDefinition("mineral-pdf-mcp", "mcp_agent.servers.mineral_pdf"),
    "price": ServerDefinition("lme-price-mcp", "mcp_agent.servers.lme_price"),
}


class McpRuntime:
    """Starts project MCP servers as stdio subprocesses and calls registered tools."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}

    async def __aenter__(self) -> "McpRuntime":
        for key, definition in SERVERS.items():
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", definition.module],
                cwd=str(self._project_root),
            )
            read_stream, write_stream = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            self._sessions[key] = session
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._stack.aclose()

    async def list_tool_names(self, server: str) -> list[str]:
        result = await self._sessions[server].list_tools()
        return [tool.name for tool in result.tools]

    async def call_json(self, server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._sessions[server].call_tool(tool, arguments)
        if result.isError:
            raise RuntimeError(f"{server}.{tool} failed: {result.content}")
        text_parts = [getattr(item, "text", "") for item in result.content if hasattr(item, "text")]
        if not text_parts:
            raise RuntimeError(f"{server}.{tool} returned no text content")
        try:
            return json.loads("\n".join(text_parts))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{server}.{tool} returned non-JSON content") from exc

    async def smoke_check(self) -> dict[str, list[str]]:
        results = await asyncio.gather(*(self.list_tool_names(name) for name in SERVERS))
        return dict(zip(SERVERS, results, strict=True))
