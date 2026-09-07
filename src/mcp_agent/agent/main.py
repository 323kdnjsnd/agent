"""CLI and HTTP entry points for the mining daily Agent."""

from __future__ import annotations

import argparse
import asyncio
import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mcp_agent.agent.orchestrator import generate_report

app = FastAPI(title="Mining Daily Agent", version="0.1.0")


class GenerateRequest(BaseModel):
    input: str = Field(min_length=1, max_length=500)


class GenerateResponse(BaseModel):
    report: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest) -> GenerateResponse:
    try:
        return GenerateResponse(report=await generate_report(payload.input))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP generation failed: {exc}") from exc


def cli() -> None:
    parser = argparse.ArgumentParser(description="Generate a mining rights daily Markdown brief.")
    parser.add_argument(
        "request",
        nargs="?",
        default="给我生成一份关于 Pilbara 锂矿的今日简报",
        help="Natural language report request.",
    )
    args = parser.parse_args()
    report = asyncio.run(generate_report(args.request))
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        print(report)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((report + "\n").encode("utf-8"))


if __name__ == "__main__":
    cli()
