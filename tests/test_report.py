import asyncio

from mcp_agent.agent.orchestrator import generate_report, parse_topic, render_report


def test_parse_topic_for_pilbara() -> None:
    result = parse_topic("给我生成一份关于 Pilbara 锂矿的今日简报")
    assert result == {
        "project": "Pilbara",
        "commodity": "lithium",
        "query": "Pilbara lithium mining project",
    }


def test_report_contains_required_sections_and_citations() -> None:
    report = render_report(
        {"project": "Pilbara", "commodity": "lithium", "query": "Pilbara lithium brief"},
        {
            "data_status": "demo",
            "items": [
                {
                    "title": "Update",
                    "publisher": "News",
                    "summary": "Summary",
                    "url": "https://example.com/news",
                }
            ],
        },
        {
            "data_status": "demo",
            "standard": "NI 43-101",
            "estimates": [{"category": "Indicated", "quantity": 100, "unit": "t", "grade": "1%"}],
            "total_quantity": 100,
            "unit": "t",
            "source": {"title": "Report", "url": "https://example.com/report.pdf"},
        },
        {
            "data_status": "demo",
            "commodity": "lithium",
            "price": {"date": "2026-09-07", "price": 100, "unit": "USD/t"},
            "source": {"title": "LME", "url": "https://www.lme.com/"},
        },
        {
            "data_status": "demo",
            "days": 7,
            "direction": "up",
            "change_percent": 2.0,
            "points": [{"price": 100}, {"price": 102}],
        },
    )
    for section in ("新闻摘要", "NI 43-101 资源量", "价格与走势", "风险提示", "引用源链接"):
        assert section in report
    assert "https://example.com/news" in report


class FakeRuntime:
    async def call_json(self, server, tool, arguments):
        if server == "news":
            return {"data_status": "demo", "items": [], "warnings": ["fixture"]}
        if tool == "extract_resources":
            return {
                "data_status": "demo",
                "standard": "NI 43-101",
                "estimates": [],
                "warnings": ["fixture"],
            }
        if tool == "get_price":
            return {"data_status": "demo", "commodity": "lithium", "price": None}
        return {"data_status": "demo", "days": 7, "points": [], "direction": "unknown"}


def test_generate_report_isolates_mcp_errors() -> None:
    report = asyncio.run(generate_report("Pilbara lithium", runtime=FakeRuntime()))
    assert "价格与走势" in report
    assert "资源量" in report
