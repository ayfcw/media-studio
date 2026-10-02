"""studio-mcp：把平台能力暴露为 8 个 MCP 工具，供 AI 客户端（Claude/Cursor/豆包）调用。

本地 stdio：
    uv run python -m studio.mcp.server
HTTP（:8300，供远程 MCP 客户端）：
    STUDIO_MCP_HTTP=1 uv run python -m studio.mcp.server
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
except Exception:
    try:
        from mcp.server.fastmcp import FastMCP  # mcp 1.x
    except Exception:  # 便于在未装 mcp 的环境查看源码
        FastMCP = None  # type: ignore

GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8200")
KEY = os.environ.get("GATEWAY_API_KEY")
HEADERS = {"X-API-Key": KEY} if KEY else {}

mcp = FastMCP("studio") if FastMCP else None


def _submit(kind: str, payload: dict[str, Any], wait: int = 180) -> dict[str, Any]:
    """创建网关任务并轮询到终态。"""
    with httpx.Client(trust_env=False, timeout=30) as c:
        r = c.post(f"{GATEWAY}/api/v1/tasks/{kind}", json=payload, headers=HEADERS)
        r.raise_for_status()
        tid = r.json()["task_id"]
        for _ in range(wait // 2):
            time.sleep(2)
            t = c.get(f"{GATEWAY}/api/v1/tasks/{tid}", headers=HEADERS).json()
            if t["status"] == "succeeded":
                try:
                    return json.loads(t["result"])
                except Exception:
                    return {"raw": t["result"]}
            if t["status"] == "failed":
                return {"error": t.get("error")}
        return {"error": "timeout"}


def _tool(name: str):
    assert mcp is not None
    return mcp.tool(name=name)


@_tool("analyze_link")
def analyze_link(url: str, deep: bool = True) -> dict[str, Any]:
    """拆解一条视频/图文链接，输出爆款结构分析。"""
    return _submit("analyze-link", {"url": url, "deep": deep})


@_tool("analyze_blogger")
def analyze_blogger(url: str, post_limit: int = 20) -> dict[str, Any]:
    """对一个博主做对标分析。"""
    return _submit("analyze-blogger", {"url": url, "post_limit": post_limit})


@_tool("search_keywords")
def search_keywords(keyword: str, count: int = 10) -> dict[str, Any]:
    """按关键词找爆款并归纳共性。"""
    return _submit("search-keywords", {"keyword": keyword, "count": count})


@_tool("generate_script")
def generate_script(topic: str, style: str = "hook+故事+干货", refs: list[str] | None = None) -> dict[str, Any]:
    """生成可直接口播的爆款文案。"""
    return _submit("generate-script", {"topic": topic, "style": style, "refs": refs or []})


@_tool("generate_video")
def generate_video(topic: str, script: str | None = None, ratio: str = "9:16") -> dict[str, Any]:
    """一键成片：主题（或给定脚本）→ 配音/素材/字幕/合成。"""
    return _submit("generate-video", {"topic": topic, "script": script, "ratio": ratio})


@_tool("rewrite_script")
def rewrite_script(text: str, mode: str = "structure", my_info: str | None = None) -> dict[str, Any]:
    """仿写三件套：structure=结构仿写 / topic=选题提炼改写 / dedup=同主题去重原创化。"""
    return _submit("rewrite", {"text": text, "mode": mode, "my_info": my_info or ""})


@_tool("account_review")
def account_review(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """对自己的账号做复盘诊断（传入采集到的作品数据）。"""
    return _submit("account-review", {"posts": posts})


@_tool("archive_search")
def archive_search(query: str) -> dict[str, Any]:
    """检索已沉淀的素材/报告库。"""
    with httpx.Client(trust_env=False, timeout=15) as c:
        r = c.get(f"{GATEWAY}/api/v1/archive", params={"keyword": query}, headers=HEADERS)
        return r.json()


@_tool("sync_feishu")
def sync_feishu(table_token: str, table_id: str, task_id: str | None = None) -> dict[str, Any]:
    """把平台沉淀的结果同步到飞书多维表格。task_id 给定则同步该任务的分析结果。"""
    with httpx.Client(trust_env=False, timeout=20) as c:
        r = c.post(f"{GATEWAY}/api/v1/feishu/sync",
                   json={"table_token": table_token, "table_id": table_id,
                         "task_id": task_id},
                   headers=HEADERS)
        return r.json()


def main() -> None:
    assert mcp is not None
    if os.environ.get("STUDIO_MCP_HTTP") == "1":
        port = int(os.environ.get("STUDIO_MCP_PORT", "8300"))
        try:
            mcp.settings.port = port  # mcp 1.x
        except Exception:
            pass
        try:
            mcp.run(transport="streamable-http", port=port)
        except TypeError:
            mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
