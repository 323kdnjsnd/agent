"""Deterministic multi-MCP orchestration and Markdown report rendering."""

from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

from mcp_agent.agent.mcp_runtime import McpRuntime

DEFAULT_PDF_URL = "https://www.sedarplus.ca/"


def parse_topic(request: str) -> dict[str, str]:
    """Extract a useful project query while keeping the natural-language request intact."""
    if not request.strip():
        raise ValueError("request must not be empty")
    lowered = request.lower()
    commodity = "lithium" if any(token in lowered for token in ("锂", "lithium")) else "lithium"
    project = "Pilbara" if "pilbara" in lowered else request.strip()[:80]
    return {
        "project": project,
        "commodity": commodity,
        "query": f"{project} {commodity} mining project",
    }


def _status(value: dict[str, Any]) -> str:
    return str(value.get("data_status", "error"))


def _source_lines(value: dict[str, Any]) -> list[str]:
    links: list[str] = []
    source = value.get("source")
    if isinstance(source, dict) and source.get("url"):
        links.append(f"- [{source.get('title') or '来源'}]({source['url']})")
    for source in value.get("sources", []):
        if isinstance(source, dict) and source.get("url"):
            links.append(f"- [{source.get('title') or '来源'}]({source['url']})")
    for item in value.get("items", []):
        if isinstance(item, dict) and item.get("url"):
            links.append(f"- [{item.get('title') or '新闻'}]({item['url']})")
    return list(dict.fromkeys(links))


def _risk_lines(
    news: dict[str, Any], resources: dict[str, Any], trend: dict[str, Any]
) -> list[str]:
    risks = [
        "储量数字需以最新技术报告、矿山寿命和冶金回收率核验，不能直接等同于可采储量。",
        "锂价数据对供给增量、库存、下游电池需求及中国现货市场变化敏感。",
    ]
    if _status(news) != "live":
        risks.append("新闻数据当前不是 live 状态，重大判断前应复核原文和发布时间。")
    if _status(resources) == "error" or not resources.get("estimates"):
        risks.append("未成功提取 Indicated/Inferred 资源量，项目估值应暂停并人工核阅 PDF。")
    change = trend.get("change_percent")
    if isinstance(change, (int, float)) and abs(change) >= 10:
        risks.append(f"观察期价格变动达到 {change:.2f}%，短期波动风险较高。")
    return risks


def _normalize_topic(topic: dict[str, str] | str) -> dict[str, str]:
    if isinstance(topic, str):
        return parse_topic(topic)
    return topic


def render_report(
    topic: dict[str, str] | str,
    news: dict[str, Any],
    resources: dict[str, Any],
    price: dict[str, Any],
    trend: dict[str, Any],
) -> str:
    topic = _normalize_topic(topic)
    today = date.today().isoformat()
    estimates = resources.get("estimates") or []
    lines = [
        f"# {topic['project']} 锂矿今日简报",
        "",
        f"> 生成日期：{today}  | 主题：{topic['query']}",
        "> 本报告由三个 MCP server 提供数据，所有数值均带有 `data_status`，请在投资决策前核验来源。",
        "",
        "## 1. 执行摘要",
        f"- 新闻数据状态：`{_status(news)}`，返回 {len(news.get('items', []))} 条候选新闻。",
        f"- 资源量数据状态：`{_status(resources)}`，标准：{resources.get('standard', 'unknown')}。",
        f"- 价格数据状态：`{_status(price)}`，商品：{price.get('commodity', 'lithium')}。",
        f"- 趋势判断：{trend.get('direction', 'unknown')}，观察期涨跌幅：{trend.get('change_percent', 'N/A')}%。",
        "",
        "## 2. 新闻摘要",
    ]
    items = news.get("items") or []
    if items:
        for item in items[:5]:
            lines.append(
                f"- **{item.get('title', '未命名')}**（{item.get('publisher', '未知来源')}）：{item.get('summary', '暂无摘要')}"
            )
    else:
        lines.append("- 暂无可用新闻；请检查 RSS 配置或网络状态。")
    lines.extend(["", "## 3. NI 43-101 资源量"])
    if estimates:
        lines.extend(["| 类别 | 数量 | 品位 |", "|---|---:|---|"])
        for item in estimates:
            lines.append(
                f"| {item.get('category', '')} | {item.get('quantity', 0):,.0f} {item.get('unit', 't')} | {item.get('grade') or '未披露'} |"
            )
        if resources.get("total_quantity") is not None:
            lines.append(
                f"\n- 合计（仅为报告中提取项相加）：**{resources['total_quantity']:,.0f} {resources.get('unit', 't')}**。"
            )
    else:
        lines.append("- 未提取到可核验的 Indicated/Inferred 数字。")
    lines.extend(["", "## 4. 价格与走势"])
    point = price.get("price") or {}
    if point:
        lines.append(
            f"- 最新点（{point.get('date', price.get('date', ''))}）：**{point.get('price', 'N/A'):,.2f} {point.get('unit', 'USD/t')}**。"
        )
    else:
        lines.append("- 最新价格不可用。")
    points = trend.get("points") or []
    if points:
        lines.append(
            f"- {trend.get('days', len(points))} 日区间：{points[0].get('price', 'N/A'):,.2f} → {points[-1].get('price', 'N/A'):,.2f}，方向 **{trend.get('direction', 'unknown')}**。"
        )
    for warning in (price.get("warnings", []) + trend.get("warnings", []))[:2]:
        lines.append(f"- 数据提示：{warning}")
    lines.extend(["", "## 5. 风险提示"])
    lines.extend(f"- {risk}" for risk in _risk_lines(news, resources, trend))
    lines.extend(["", "## 6. 引用源链接"])
    sources = (
        _source_lines(news) + _source_lines(resources) + _source_lines(price) + _source_lines(trend)
    )
    lines.extend(list(dict.fromkeys(sources)) or ["- 无可用源链接。"])
    return "\n".join(lines) + "\n"


async def generate_report(request: str, *, runtime: McpRuntime | None = None) -> str:
    topic = parse_topic(request)
    owns_runtime = runtime is None
    runtime = runtime or McpRuntime()
    if owns_runtime:
        await runtime.__aenter__()
    try:

        async def call(server: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
            try:
                return await runtime.call_json(server, tool, args)
            except Exception as exc:
                return {"data_status": "error", "warnings": [f"{server}.{tool}: {exc}"]}

        news, resources, price, trend = await asyncio.gather(
            call("news", "search", {"query": topic["query"], "days": 1}),
            call(
                "pdf",
                "extract_resources",
                {"pdf_url": os.getenv("PILBARA_PDF_URL", DEFAULT_PDF_URL)},
            ),
            call(
                "price",
                "get_price",
                {"commodity": topic["commodity"], "date": date.today().isoformat()},
            ),
            call("price", "get_trend", {"commodity": topic["commodity"], "days": 7}),
        )
        return render_report(topic, news, resources, price, trend)
    finally:
        if owns_runtime:
            await runtime.__aexit__(None, None, None)
