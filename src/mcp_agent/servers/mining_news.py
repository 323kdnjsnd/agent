"""mining-news-mcp: RSS-backed news aggregation exposed through MCP stdio."""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote_plus

from mcp.server.fastmcp import FastMCP

from mcp_agent.common.http import HttpError, fetch_text, validate_public_url
from mcp_agent.common.models import (
    ArticleResponse,
    DataStatus,
    NewsItem,
    NewsSearchResponse,
    SourceRef,
)

mcp = FastMCP("mining-news-mcp", instructions="Aggregate mining news from configured RSS feeds.")

_DEMO_NEWS = [
    NewsItem(
        title="Pilbara Minerals publishes operating and market update",
        summary=(
            "Use the issuer update as a starting point for production, sales and market context."
            " This record is bundled for offline demo mode."
        ),
        url="https://www.pilbaraminerals.com.au/news/",
        publisher="Pilbara Minerals",
        published_at="offline fixture",
        relevance="high",
    ),
    NewsItem(
        title="Australian lithium market reference",
        summary=(
            "Industry reference link included only to demonstrate report citations when live RSS "
            "is disabled."
        ),
        url="https://www.mining.com/tag/lithium/",
        publisher="MINING.COM",
        published_at="offline fixture",
        relevance="medium",
    ),
]


def _strip_html(value: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(clean)).strip()


def _rss_urls(query: str) -> list[str]:
    configured = [
        item.strip() for item in os.getenv("NEWS_RSS_URLS", "").split(",") if item.strip()
    ]
    if configured:
        return configured
    return [f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-AU&gl=AU&ceid=AU:en"]


def _is_recent(raw_date: str, days: int) -> bool:
    if not raw_date:
        return True
    try:
        return (date.today() - parsedate_to_datetime(raw_date).date()).days <= days
    except (TypeError, ValueError, IndexError):
        return True


def parse_rss(xml_text: str, query: str, days: int, feed_url: str) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for node in root.findall(".//item"):
        title = _strip_html(node.findtext("title", default=""))
        link = node.findtext("link", default="").strip()
        published_at = node.findtext("pubDate", default="").strip()
        summary = _strip_html(node.findtext("description", default=""))
        source_node = node.find("source")
        publisher = (
            source_node.text.strip() if source_node is not None and source_node.text else "RSS"
        )
        if title and link and _is_recent(published_at, days):
            items.append(
                NewsItem(
                    title=title,
                    url=link,
                    summary=summary[:500],
                    publisher=publisher,
                    published_at=published_at,
                    relevance="high" if query.lower().split()[0] in title.lower() else "medium",
                )
            )
    return items


def search_news(query: str, days: int = 1) -> NewsSearchResponse:
    """Collect relevant RSS items; return transparent offline data when live mode is disabled."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= days <= 30:
        raise ValueError("days must be between 1 and 30")

    if os.getenv("LIVE_DATA", "false").lower() != "true":
        return NewsSearchResponse(
            query=query,
            days=days,
            data_status=DataStatus.DEMO,
            items=_DEMO_NEWS,
            sources=[
                SourceRef(
                    title="Offline news fixture", url="https://www.pilbaraminerals.com.au/news/"
                )
            ],
            warnings=[
                "Live RSS is disabled. News entries are offline demo fixtures,"
                " not current reporting."
            ],
        )

    collected: list[NewsItem] = []
    warnings: list[str] = []
    sources: list[SourceRef] = []
    for url in _rss_urls(query):
        try:
            collected.extend(parse_rss(fetch_text(url), query, days, url))
            sources.append(SourceRef(title="RSS search feed", url=url, accessed_at=date.today()))
        except (HttpError, ET.ParseError) as exc:
            warnings.append(f"RSS source unavailable ({url}): {exc}")

    deduplicated = list({str(item.url): item for item in collected}.values())[:10]
    if not deduplicated:
        return NewsSearchResponse(
            query=query,
            days=days,
            data_status=DataStatus.ERROR,
            sources=sources,
            warnings=warnings or ["No news item was returned by configured RSS feeds."],
        )
    return NewsSearchResponse(
        query=query,
        days=days,
        data_status=DataStatus.LIVE,
        items=deduplicated,
        sources=sources,
        warnings=warnings,
    )


def fetch_article_content(url: str) -> ArticleResponse:
    """Retrieve an article body from a public URL with response-size guardrails."""
    try:
        validate_public_url(url)
        html = fetch_text(url, max_bytes=2_000_000)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = _strip_html(title_match.group(1)) if title_match else ""
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
        text = "\n".join(
            _strip_html(paragraph) for paragraph in paragraphs if _strip_html(paragraph)
        )
        return ArticleResponse(url=url, title=title, text=text[:12000], data_status=DataStatus.LIVE)
    except HttpError as exc:
        return ArticleResponse(url=url, data_status=DataStatus.ERROR, warnings=[str(exc)])


@mcp.tool()
def search(query: str, days: int = 1) -> str:
    """Search mining news published in the last `days` days. Returns cited structured JSON."""
    return json.dumps(search_news(query, days).model_dump(mode="json"), ensure_ascii=False)


@mcp.tool()
def fetch_article(url: str) -> str:
    """Fetch public article text by URL. Local/private-network URLs are rejected."""
    return json.dumps(fetch_article_content(url).model_dump(mode="json"), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
