from pathlib import Path

from mcp_agent.servers.mineral_pdf import parse_resource_text
from mcp_agent.servers.mining_news import parse_rss

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ni43_indicated_and_inferred() -> None:
    text = (FIXTURES / "ni43_report.txt").read_text(encoding="utf-8")
    result = parse_resource_text(text, "https://example.com/report.pdf")
    assert result.standard == "NI 43-101"
    assert [item.category for item in result.estimates] == ["Indicated", "Inferred"]
    assert result.total_quantity == 334000


def test_parse_rss_item() -> None:
    xml = (FIXTURES / "news.xml").read_text(encoding="utf-8")
    result = parse_rss(xml, "Pilbara lithium", 1, "https://example.com/feed.xml")
    assert len(result) == 1
    assert result[0].publisher == "Example Mining"
