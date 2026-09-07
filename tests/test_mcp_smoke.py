from pathlib import Path

import pytest

from mcp_agent.agent.mcp_runtime import McpRuntime


@pytest.mark.asyncio
async def test_all_mcp_servers_expose_required_tools() -> None:
    async with McpRuntime(project_root=Path(__file__).parents[1]) as runtime:
        names = await runtime.smoke_check()
    assert {"search", "fetch_article"}.issubset(names["news"])
    assert "extract_resources" in names["pdf"]
    assert {"get_price", "get_trend"}.issubset(names["price"])
