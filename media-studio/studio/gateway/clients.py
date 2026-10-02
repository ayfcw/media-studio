"""网关下游服务客户端（异步 httpx）。

各 base_url 可通过环境变量覆盖；下游具体路径集中在此，便于按各自 /docs 校准。

DTK 对接要点（已对照其 openapi.json 核准）：
- 解析入口是 POST /api/v1/parse（body {"url": 分享文本或链接}），query wait≤30 秒同步等待；
  未完成返回 202 + data.task_id，需轮询 GET /api/v1/tasks/{task_id}。
- 账号作品列表 = GET /api/v1/douyin/user/posts（url 或 sec_user_id 二选一，count≤50）。
- 鉴权：X-API-Key 请求头（DTK 控制台创建的 API Key，可存系统设置或环境变量）。
- DTK 无关键词搜索端点（它是解析器不是搜索引擎），search 走显式不支持。
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

ANALYTICS_URL = os.environ.get("ANALYTICS_URL", "http://127.0.0.1:8100")
DTK_URL = os.environ.get("DTK_URL", "http://127.0.0.1:8000")
MPT_URL = os.environ.get("MPT_URL", "http://127.0.0.1:8080")


def _dtk_headers() -> dict[str, str]:
    """DTK API Key：系统设置 [dtk].api_key 优先，环境变量 DTK_API_KEY 兜底。"""
    key = ""
    try:
        from studio.common.settings_store import get_section

        key = get_section("dtk").get("api_key") or ""
    except Exception:
        pass
    key = key or os.environ.get("DTK_API_KEY", "")
    return {"X-API-Key": key} if key else {}


class AnalyticsClient:
    async def analyze(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(trust_env=False, timeout=120) as c:
            r = await c.post(f"{ANALYTICS_URL}/analyze/{kind}", json={"payload": payload})
            r.raise_for_status()
            return r.json()


class DTKClient:
    """采集层（DTK v5 真实契约）。"""

    async def _poll(self, c: httpx.AsyncClient, task_id: str, timeout_s: float) -> dict[str, Any]:
        import asyncio

        deadline = timeout_s
        waited = 0.0
        while waited < deadline:
            await asyncio.sleep(2)
            waited += 2
            r = await c.get(f"{DTK_URL}/api/v1/tasks/{task_id}", headers=_dtk_headers())
            r.raise_for_status()
            body = r.json()
            data = body.get("data") or {}
            state = data.get("state")
            if state in ("succeeded", "done", "complete", "completed"):
                return data.get("result") or data
            if state in ("failed", "error"):
                err = data.get("error") or {}
                raise RuntimeError(f"DTK task failed: {err.get('code') if isinstance(err, dict) else err}")
        raise TimeoutError(f"DTK task {task_id} not finished in {deadline}s")

    async def parse(self, url: str, timeout_s: float = 90) -> dict[str, Any]:
        async with httpx.AsyncClient(trust_env=False, timeout=timeout_s + 30) as c:
            # wait=25 做首次同步等待；202 则轮询任务直到完成
            r = await c.post(
                f"{DTK_URL}/api/v1/parse",
                params={"wait": 25, "lang": "zh"},
                json={"url": url},
                headers=_dtk_headers(),
            )
            if r.status_code == 200:
                body = r.json()
                return body.get("data") or body
            if r.status_code == 202:
                body = r.json()
                task_id = (body.get("data") or {}).get("task_id")
                if not task_id:
                    raise RuntimeError(f"DTK 202 without task_id: {body}")
                return await self._poll(c, task_id, timeout_s)
            # 4xx/5xx：给出可读错误
            try:
                err = r.json().get("error") or {}
                code = err.get("code")
                msg = err.get("message")
            except Exception:
                code, msg = None, r.text[:200]
            raise RuntimeError(f"DTK parse HTTP {r.status_code} {code or ''}: {msg}")

    async def user_posts(self, handle: str, count: int = 20, timeout_s: float = 90) -> list[dict[str, Any]]:
        """按主页链接 / 分享文案 / sec_uid / 纯数字抖音号 拉取作者作品列表。"""
        params: dict[str, Any] = {
            "count": min(max(int(count or 20), 1), 50),
            "wait": 25,
            "lang": "zh",
        }
        h = (handle or "").strip()
        if h.startswith("MS4wLjAB"):
            params["sec_user_id"] = h
        elif re.fullmatch(r"\d{6,}", h):
            # 纯数字抖音号：拼成主页 URL 交给 DTK 解析（部分号段可能不被平台支持）
            params["url"] = f"https://www.douyin.com/user/{h}"
        else:
            params["url"] = h  # 主页链接或含链接的分享文案
        async with httpx.AsyncClient(trust_env=False, timeout=timeout_s + 30) as c:
            r = await c.get(f"{DTK_URL}/api/v1/douyin/user/posts", params=params, headers=_dtk_headers())
            if r.status_code == 200:
                data = r.json().get("data") or {}
            elif r.status_code == 202:
                body = r.json()
                task_id = (body.get("data") or {}).get("task_id")
                if not task_id:
                    raise RuntimeError(f"DTK 202 without task_id: {body}")
                data = await self._poll(c, task_id, timeout_s) or {}
            else:
                try:
                    err = r.json().get("error") or {}
                    code, msg = err.get("code"), err.get("message")
                except Exception:
                    code, msg = None, r.text[:200]
                raise RuntimeError(f"DTK user/posts HTTP {r.status_code} {code or ''}: {msg}")
        posts = data.get("posts") or data.get("items") or []
        if not posts:
            raise RuntimeError(
                "DTK 返回了空作品列表：该账号可能没有公开作品，或输入的 ID/链接 "
                f"无法定位到主页（输入：{h[:60]}）。请改用主页分享链接重试。"
            )
        return posts

    async def search(self, keyword: str, count: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "DTK v5 不提供关键词搜索（它是解析器，不是搜索引擎）；"
            "search-keywords 任务请粘贴分享链接批量解析，或后续接入 MediaCrawler"
        )


class MPTClient:
    """成片层（路径已核对，见附录 B）。"""

    async def create_video(self, req: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(trust_env=False, timeout=60) as c:
            r = await c.post(f"{MPT_URL}/api/v1/videos", json=req)
            r.raise_for_status()
            return r.json()

    async def get_task(self, task_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(trust_env=False, timeout=30) as c:
            r = await c.get(f"{MPT_URL}/api/v1/tasks/{task_id}")
            r.raise_for_status()
            return r.json()
