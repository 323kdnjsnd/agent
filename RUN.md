# 5 分钟运行指南

## 前置条件

- Python 3.11+（推荐 3.12）
- `uv`（推荐）或 `pip`
- 可选：Docker Desktop

## 方式 A：本地离线演示（不需要 API Key）

```bash
cd /d/mcp-agent
uv venv
uv pip install -e ".[dev]"
uv run python -m mcp_agent.agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"
```

输出是 Markdown，包含新闻摘要、NI 43-101 Indicated/Inferred 资源量、价格趋势、风险提示和来源链接。默认 `LIVE_DATA=false`，任何 fixture 都会明确标记为 `demo`，不是实时投资数据。

也可以启动 HTTP API：

```bash
uv run uvicorn mcp_agent.agent.main:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"input":"给我生成一份关于 Pilbara 锂矿的今日简报"}'
```

## 方式 B：一条 Docker Compose 命令

Agent 容器会通过 MCP stdio client 启动三个子 server，因此单容器即可演示完整 MCP 链路：

```bash
docker compose up --build
```

另开终端调用：

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"input":"给我生成一份关于 Pilbara 锂矿的今日简报"}'
```

停止：`docker compose down`。

## 方式 C：接入 Claude Desktop / Cursor

复制并按本机路径修改 `mcp-config.json`。Windows 的 `cwd` 使用 `D:/mcp-agent`，并通过 `PYTHONPATH=D:/mcp-agent/src` 指向源码。三个条目分别暴露：

- `mining-news-mcp`: `search(query, days)`、`fetch_article(url)`
- `mineral-pdf-mcp`: `extract_resources(pdf_url)`
- `lme-price-mcp`: `get_price(commodity, date)`、`get_trend(commodity, days)`

修改后重启 Claude Desktop/Cursor，在工具列表中应看到上述 5 个工具。

## 切换到 live 数据

```bash
copy .env.example .env
```

设置：

- `LIVE_DATA=true`
- `NEWS_RSS_URLS`：逗号分隔的公开 RSS URL
- `PILBARA_PDF_URL`：待核验的公开 NI 43-101 PDF URL
- `PRICE_API_URL`：返回 `{ "prices": [{"date":"YYYY-MM-DD", "price": 123.4}] }` 的 JSON API

然后在当前 shell 导出环境变量，或使用支持 `env_file` 的启动方式。服务会将 live/provider 错误作为结构化 warning 返回，不会默默回退成实时数据。

## 验证

```bash
uv run pytest -q
uv run python -m compileall src tests
```

MCP smoke test 会启动三个真实 stdio server，并检查工具列表，而不是直接导入函数绕过协议。
