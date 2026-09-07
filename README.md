# 矿权日报 Agent

一个面向矿业研究和面试演示的 Model Context Protocol（MCP）项目：输入“给我生成一份关于 Pilbara 锂矿的今日简报”，通过三个独立 MCP server 获取新闻、NI 43-101 资源量和价格走势，再生成带引用链接的 Markdown 日报。

## 架构

```text
┌─────────────────────┐       MCP stdio       ┌────────────────────┐
│ Agent client         │ ────────────────────> │ mining-news-mcp     │
│ explicit async DAG   │ ────────────────────> │ mineral-pdf-mcp     │
│ report renderer      │ ────────────────────> │ lme-price-mcp       │
└─────────┬───────────┘                       └────────────────────┘
          │ HTTP / CLI
          ▼
       Markdown brief
```

- `mining-news-mcp`: `search(query, days)`、`fetch_article(url)`，默认读取 RSS，支持 live/offline 模式。
- `mineral-pdf-mcp`: `extract_resources(pdf_url)`，下载 PDF 并提取 NI 43-101 中 Indicated/Inferred 数字。
- `lme-price-mcp`: `get_price(commodity, date)`、`get_trend(commodity, days)`，支持 JSON provider 和离线 fixture。
- `agent`: 使用官方 MCP Python SDK `ClientSession`/`stdio_client` 连接三个 server，四个工具调用并发执行，单个服务失败会隔离为报告警告。

> 说明：锂并非 LME 交易合约。默认锂价仅是明确标记的离线演示 fixture；接入真实报价前应配置合适的价格供应商并核验单位。

## 快速运行

完整步骤见 [RUN.md](RUN.md)。最短离线演示：

```bash
cd /d/mcp-agent
uv venv
uv pip install -e ".[dev]"
uv run python -m mcp_agent.agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"
```

Docker：

```bash
docker compose up --build
```

然后请求 `POST http://127.0.0.1:8000/generate`。

## 交付清单

- [x] 3 个真正使用 MCP `FastMCP` + `stdio` transport 的 server
- [x] 1 个官方 MCP client Agent 编排
- [x] 新闻、资源量、价格、趋势、风险和引用源链接
- [x] Claude Desktop / Cursor 的 [mcp-config.json](mcp-config.json)
- [x] [RUN.md](RUN.md) 和 [docker-compose.yml](docker-compose.yml)
- [x] 单元测试和 MCP 协议 smoke test

## 工程约定

- Python 3.11+，`src` layout，Pydantic 结构化数据模型。
- 网络请求有 URL、超时和响应大小限制；不允许访问本机/私网地址。
- live、demo、error 状态始终随数据返回，不将样例数据伪装成实时数据。
- 依赖和开发命令通过 `pyproject.toml` 管理，提交前运行 `pytest` 和 `compileall`。

## 目录

```text
mcp-agent/
├── agent/                         # MCP client 编排与 HTTP/CLI
├── mcp-config.json                # Claude Desktop / Cursor
├── src/mcp_agent/common/          # 模型与 HTTP 安全辅助
├── src/mcp_agent/servers/         # 三个 MCP server
├── tests/                         # parser/report/protocol tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── RUN.md
```

## License

MIT
