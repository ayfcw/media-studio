"""AI 分析引擎 FastAPI 入口。

启动（在 media-studio 目录）：
    uv run uvicorn studio.analytics.app:app --port 8100
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from studio.analytics import service

app = FastAPI(title="studio-analytics", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class AnalyzeRequest(BaseModel):
    payload: dict[str, Any] = {}


@app.post("/analyze/{kind}")
def analyze(kind: str, req: AnalyzeRequest) -> dict[str, Any]:
    return service.analyze(kind, req.payload)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "studio-analytics", "status": "ok"}
