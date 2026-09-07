"""Print the tool names exposed by all three MCP servers."""

import asyncio
from pathlib import Path

from mcp_agent.agent.mcp_runtime import McpRuntime


async def main() -> None:
    async with McpRuntime(Path(__file__).resolve().parents[1]) as runtime:
        print(await runtime.smoke_check())


if __name__ == "__main__":
    asyncio.run(main())
