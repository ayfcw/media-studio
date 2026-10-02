"""编排网关 FastAPI 入口。

启动（在 media-studio 目录）：
    uv run uvicorn studio.gateway.app:app --port 8200
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from studio.common import settings_store
from studio.gateway import tasks
from studio.gateway.auth import require_key
from studio.gateway.clients import ANALYTICS_URL, DTK_URL, MPT_URL

app = FastAPI(title="studio-gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class CreateTask(BaseModel):
    # 各 kind 字段不同，统一用宽松模型；多余字段忽略
    model_config = {"extra": "allow"}


class SettingsBody(BaseModel):
    llm: dict[str, Any] | None = None
    feishu: dict[str, Any] | None = None
    dtk: dict[str, Any] | None = None


@app.on_event("startup")
def _startup() -> None:
    tasks.init_db()


# ---------------- 任务 ----------------
@app.post("/api/v1/tasks/{kind}", dependencies=[Depends(require_key)])
async def create(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    if kind not in tasks.HANDLERS:
        return {"error": f"unknown kind '{kind}'",
                "available": list(tasks.HANDLERS)}
    tid = tasks.create_task(kind, body)
    return {"task_id": tid, "status": "pending",
            "poll": f"/api/v1/tasks/{tid}"}


@app.get("/api/v1/tasks", dependencies=[Depends(require_key)])
def list_tasks() -> list[dict[str, Any]]:
    return tasks.list_tasks()


@app.get("/api/v1/tasks/{tid}", dependencies=[Depends(require_key)])
def get_task(tid: str) -> dict[str, Any]:
    t = tasks.get_task(tid)
    return t or {"error": "not found"}


@app.delete("/api/v1/tasks", dependencies=[Depends(require_key)])
def clear_tasks() -> dict[str, Any]:
    return {"cleared": tasks.clear_tasks()}


# ---------------- 设置 ----------------
@app.get("/api/v1/settings", dependencies=[Depends(require_key)])
def get_settings() -> dict[str, Any]:
    return settings_store.public_settings()


@app.put("/api/v1/settings", dependencies=[Depends(require_key)])
def put_settings(body: SettingsBody) -> dict[str, str]:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    settings_store.save_settings(data)
    return {"status": "saved"}


# ---------------- 视频素材（一键成片 local 模式的素材目录） ----------------
_SAFE_NAME = re.compile(r'^[\w\u4e00-\u9fff.\- ()\[\]]+$')


def _materials_dir() -> "os.PathLike[str]":
    from pathlib import Path

    d = Path(tasks.local_videos_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.get("/api/v1/materials", dependencies=[Depends(require_key)])
def materials_list() -> dict[str, Any]:
    return {"items": tasks.list_local_materials(), "dir": str(tasks.local_videos_dir())}


@app.post("/api/v1/materials", dependencies=[Depends(require_key)])
async def materials_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    from pathlib import Path

    name = Path(file.filename or "").name
    suffix = Path(name).suffix.lower()
    if not name or suffix not in tasks.MATERIAL_EXTS or not _SAFE_NAME.match(name):
        return {"error": f"仅支持视频文件（{'/'.join(sorted(tasks.MATERIAL_EXTS))}），"
                          "文件名请勿使用特殊字符"}
    d = Path(_materials_dir())
    dest = d / name
    if dest.exists():  # 同名不覆盖：加时间戳后缀
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        dest = d / f"{Path(name).stem}_{stamp}{suffix}"
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            out.write(chunk)
    return {"status": "saved", "name": dest.name, "size": size}


@app.delete("/api/v1/materials/{name}", dependencies=[Depends(require_key)])
def materials_delete(name: str) -> dict[str, Any]:
    from pathlib import Path

    d = Path(_materials_dir()).resolve()
    target = (d / Path(name).name).resolve()
    if target.parent != d or not target.exists():
        return {"error": "素材不存在"}
    target.unlink()
    return {"deleted": True, "name": target.name}


# ---------------- 采集视频缓存（拆解报告在线播放） ----------------
@app.get("/api/v1/media/{media_id}.mp4", dependencies=[Depends(require_key)])
def media_file(media_id: str) -> Any:
    if not re.fullmatch(r"[0-9a-f]{32}", media_id):
        return {"error": "bad media id"}
    p = tasks.MEDIA_DIR / f"{media_id}.mp4"
    if not p.exists():
        return {"error": "media not found"}
    # FileResponse 自带 Range 支持，<video> 可拖进度条
    return FileResponse(p, media_type="video/mp4")


# ---------------- 库（素材库：任务成功自动沉淀） ----------------
@app.get("/api/v1/archive", dependencies=[Depends(require_key)])
def archive(keyword: str | None = None, kind: str | None = None,
            limit: int = 100) -> dict[str, Any]:
    items = tasks.list_archive(keyword=keyword, kind=kind, limit=limit)
    for it in items:
        try:
            it["result"] = json.loads(it.get("result") or "{}")
        except Exception:
            pass
    return {"items": items, "total": len(items)}


@app.delete("/api/v1/archive/{aid}", dependencies=[Depends(require_key)])
def archive_delete(aid: str) -> dict[str, Any]:
    return {"deleted": tasks.delete_archive(aid)}


@app.get("/api/v1/bloggers", dependencies=[Depends(require_key)])
def bloggers() -> dict[str, list]:
    items = []
    for t in tasks.list_tasks(200):
        if t["kind"] == "analyze-blogger" and t["status"] == "succeeded" and t.get("result"):
            try:
                items.append(json.loads(t["result"]))
            except Exception:
                pass
    return {"items": items}


# ---------------- MPT 成片任务状态代理 ----------------
@app.get("/api/v1/mpt/tasks/{tid}", dependencies=[Depends(require_key)])
async def mpt_task(tid: str) -> dict[str, Any]:
    async with httpx.AsyncClient(trust_env=False, timeout=30) as c:
        r = await c.get(f"{MPT_URL}/api/v1/tasks/{tid}")
        r.raise_for_status()
    data = (r.json() or {}).get("data") or {}
    # 云端部署时 PUBLIC_MPT_BASE=/mpt（经 nginx 反代到 MPT），本机默认等于 MPT_URL
    public_base = os.environ.get("PUBLIC_MPT_BASE", MPT_URL).rstrip("/")
    videos = [
        v if str(v).startswith("http") else f"{public_base}{v}"
        for v in (data.get("videos") or [])
    ]
    return {
        "mpt_task_id": tid,
        "state": data.get("state"),          # MPT v1.3.7: -1 失败 / 1 完成 / 4 合成中
        "progress": data.get("progress", 0),
        "videos": videos,
        "failed_stage": data.get("failed_stage"),
        "error": data.get("error"),
    }


# ---------------- 飞书（凭据在系统设置页配置） ----------------
@app.post("/api/v1/feishu/sync", dependencies=[Depends(require_key)])
async def feishu_sync(body: dict[str, Any]) -> dict[str, Any]:
    from studio.feishu import client as fc

    app_token = body.get("app_token") or body.get("table_token")
    table_id = body.get("table_id")
    if body.get("task_id"):  # 按任务结果同步
        t = tasks.get_task(body["task_id"])
        if not t or t["status"] != "succeeded" or not t.get("result"):
            return {"status": "error", "message": "任务不存在或未成功"}
        records = [fc.report_to_record(json.loads(t["result"]))]
    elif body.get("report"):
        records = [fc.report_to_record(body["report"])]
    else:
        records = body.get("records", [])
    try:
        result = await fc.batch_create_records(app_token, table_id, records)
        return {"status": "ok", "result": result}
    except Exception as e:  # 未配置凭据 / 表参数缺失
        return {"status": "error", "message": str(e)}


# ---------------- 健康 ----------------
async def _probe(url: str) -> str:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=4) as c:
            r = await c.get(url)
            return "up" if r.status_code < 500 else "error"
    except Exception:
        return "down"


@app.get("/api/v1/health")
async def health() -> dict[str, Any]:
    return {
        "gateway": "up",
        "analytics": await _probe(f"{ANALYTICS_URL}/health"),
        "dtk": await _probe(f"{DTK_URL}/readyz"),
        "mpt": await _probe(f"{MPT_URL}/api/v1/tasks?page=1&page_size=1"),
    }
