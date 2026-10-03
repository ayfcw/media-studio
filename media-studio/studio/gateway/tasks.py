"""任务状态机 + 编排逻辑。

status: pending -> running -> succeeded | failed
SQLite 持久化（data/gateway.db）；后台 asyncio 执行，信号量限流。
下游（DTK/MPT）不可用时自动降级，保证 AI 引擎（含 Mock）链路可演示。
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# HuggingFace 直连在国内不可达，转写模型经镜像站下载（仅影响 faster-whisper）；
# ETag 检查强制 5 秒超时，防止代理/TUN 异常时请求无限挂起
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "5")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")

from studio.gateway.clients import AnalyticsClient, DTKClient, MPTClient

DATA_DIR = Path(os.environ.get("STUDIO_DATA_DIR", Path(__file__).resolve().parents[3] / "data"))
DB_PATH = DATA_DIR / "gateway.db"
MEDIA_DIR = DATA_DIR / "media"

MATERIAL_EXTS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

# ---------------- 口播逐字稿（faster-whisper，CPU int8） ----------------
_ASR_MODEL = os.environ.get("STUDIO_ASR_MODEL", "small")
# 内存吃紧的机器可设 STUDIO_ASR_EPHEMERAL=1：每次转写临时加载模型、用完释放
_ASR_EPHEMERAL = os.environ.get("STUDIO_ASR_EPHEMERAL") == "1"
_asr_lock = threading.Lock()          # 仅保护懒加载（不可重入，勿嵌套）
_asr_sem = threading.Semaphore(1)     # 串行化转写（限制 CPU/内存峰值）
_asr_model: Any = None


def _load_asr_model() -> Any:
    from faster_whisper import WhisperModel

    kwargs = dict(
        device="cpu", compute_type="int8", download_root=str(DATA_DIR / "models")
    )
    try:  # 已缓存则完全离线加载，避免任何网络请求挂起任务
        return WhisperModel(_ASR_MODEL, local_files_only=True, **kwargs)
    except Exception:
        return WhisperModel(_ASR_MODEL, **kwargs)


def _get_asr_model() -> Any:
    global _asr_model
    with _asr_lock:
        if _asr_model is None:
            _asr_model = _load_asr_model()
        return _asr_model


def transcribe_video(video_path: Path) -> str | None:
    """抽取视频口播逐字稿；失败返回 None，不阻塞主流程。

    不开 VAD：唱腔/配乐类视频会被 Silero 判成非语音而整段滤空（实测），
    无 VAD 虽可能混入少量幻听文本，但保证音乐类内容也有产出。
    """
    model = None
    try:
        with _asr_sem:
            model = _load_asr_model() if _ASR_EPHEMERAL else _get_asr_model()
            segments, _info = model.transcribe(str(video_path), language="zh")
            text = "".join(seg.text for seg in segments).strip()
            return text or None
    except Exception:
        return None
    finally:
        if _ASR_EPHEMERAL and model is not None:
            del model
            import gc

            gc.collect()


async def cache_video(url: str, media_id: str) -> bool:
    """把采集到的无水印视频缓存到本地持久目录（供报告页在线播放）。

    成功返回 True；失败（链接过期/超时/过大）清理残留并返回 False。
    """
    import httpx

    dest = MEDIA_DIR / f"{media_id}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(
            trust_env=False, follow_redirects=True,
            timeout=httpx.Timeout(120, connect=10),
        ) as c:
            async with c.stream(
                "GET", url,
                headers={"User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                    "Referer": "https://www.douyin.com/"},
            ) as r:
                r.raise_for_status()
                total = 0
                with dest.open("wb") as f:
                    async for chunk in r.aiter_bytes(1 << 20):
                        f.write(chunk)
                        total += len(chunk)
                        if total > 300 * 1024 * 1024:  # 上限 300MB，防异常大文件
                            raise ValueError("video exceeds 300MB")
        return True
    except Exception:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def local_videos_dir() -> Path:
    """一键成片 local 模式的素材目录（与 MPT 容器共享挂载）。

    本机开发默认 MPT 的 storage/local_videos；云端由 STUDIO_LOCAL_VIDEOS_DIR
    指向挂载进容器的共享目录。
    """
    env_dir = os.environ.get("STUDIO_LOCAL_VIDEOS_DIR")
    return Path(env_dir) if env_dir else Path(
        r"C:\Users\24688\dev\MoneyPrinterTurbo\storage\local_videos"
    )


def list_local_materials() -> list[dict[str, Any]]:
    d = local_videos_dir()
    if not d.exists():
        return []
    items = []
    for f in sorted(d.iterdir()):
        if f.is_file() and f.suffix.lower() in MATERIAL_EXTS:
            st = f.stat()
            items.append({
                "name": f.name,
                "size": st.st_size,
                "modified_at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
            })
    return items

analytics = AnalyticsClient()
dtk = DTKClient()
mpt = MPTClient()

_sem = asyncio.Semaphore(int(os.environ.get("GATEWAY_CONCURRENCY", "4")))
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS tasks(
            id TEXT PRIMARY KEY, kind TEXT, status TEXT,
            input TEXT, result TEXT, error TEXT,
            created_at TEXT, updated_at TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS archive(
            id TEXT PRIMARY KEY, kind TEXT, title TEXT, summary TEXT,
            result TEXT, source_task_id TEXT, created_at TEXT)"""
        )


def create_task(kind: str, payload: dict[str, Any]) -> str:
    tid = uuid.uuid4().hex
    with _lock, _db() as c:
        c.execute(
            "INSERT INTO tasks(id,kind,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (tid, kind, "pending", json.dumps(payload, ensure_ascii=False), _now(), _now()),
        )
    asyncio.ensure_future(_run(tid, kind, payload))
    return tid


def _update(tid: str, **fields: Any) -> None:
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [tid]
    with _lock, _db() as c:
        c.execute(f"UPDATE tasks SET {cols} WHERE id=?", vals)


def get_task(tid: str) -> dict[str, Any] | None:
    with _db() as c:
        row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    return dict(row) if row else None


def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    with _db() as c:
        rows = c.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def clear_tasks() -> int:
    """清空全部任务记录（不影响素材库 archive 表）。"""
    with _lock, _db() as c:
        cur = c.execute("DELETE FROM tasks")
    return cur.rowcount


# ---------------- 编排 handlers ----------------
def _real_source(post: dict[str, Any]) -> dict[str, Any] | None:
    """从 DTK 解析结果提取真实元数据，让前端能区分"真实采集"与"AI 示例"。"""
    if not isinstance(post, dict) or post.get("kind") not in ("video", "image", "user", "collection"):
        return None
    author = post.get("author") or {}
    stats = post.get("stats") or {}
    media = post.get("media") or {}
    vid = media.get("video") or {}
    video_url = vid.get("url") or next(iter(vid.get("urls") or []), None)
    cover = media.get("cover") or media.get("image")
    if isinstance(cover, dict):
        cover = cover.get("url") or next(iter(cover.get("urls") or []), None)
    return {
        "title": post.get("title") or post.get("description"),
        "author": author.get("nickname"),
        "author_url": author.get("web_url"),
        "follower_count": (author.get("stats") or {}).get("follower_count"),
        "tags": post.get("tags") or [],
        "digg_count": stats.get("digg_count"),
        "collect_count": stats.get("collect_count"),
        "comment_count": stats.get("comment_count"),
        "share_count": stats.get("share_count"),
        "duration_ms": post.get("duration_ms"),
        "web_url": post.get("web_url"),
        "platform": post.get("platform"),
        "video_url": video_url,
        "cover_url": cover,
    }


async def h_analyze_link(p: dict[str, Any]) -> dict[str, Any]:
    post: dict[str, Any]
    try:
        post = await dtk.parse(p["url"])
    except Exception:
        post = {"url": p["url"]}  # 降级：DTK 未就绪

    # 先缓存无水印视频，再转写口播逐字稿（转写放线程池，避免阻塞事件循环）
    media_id: str | None = None
    video_path: Path | None = None
    src = _real_source(post)
    if src and src.get("video_url"):
        media_id = uuid.uuid4().hex
        dest = MEDIA_DIR / f"{media_id}.mp4"
        if await cache_video(src["video_url"], media_id):
            video_path = dest

    transcript: str | None = None
    if video_path is not None and os.environ.get("STUDIO_ASR_ENABLED", "1") != "0":
        transcript = await asyncio.to_thread(transcribe_video, video_path)
    if transcript:
        post = {**post, "transcript": transcript}

    report = await analytics.analyze("breakdown", post)
    src = _real_source(post)
    if src:
        report["source"] = src
        if media_id:
            report["source"]["video_media_id"] = media_id
            report["source"].pop("video_url", None)  # 直链短暂有效，不外泄
        if transcript:
            report["source"]["transcript"] = transcript
    return report


async def h_analyze_blogger(p: dict[str, Any]) -> dict[str, Any]:
    url = p.get("url") or p.get("blogger")
    limit = int(p.get("post_limit", 20) or 20)
    posts: list[dict[str, Any]] = []
    try:
        raw = await dtk.user_posts(url, limit)
        posts = [_post_brief(x) for x in raw]
    except Exception:
        posts = []  # 采集失败时仍让 AI 基于链接分析，但会在结果里体现作品数为 0
    data = {"url": url, "post_limit": limit, "posts": posts}
    report = await analytics.analyze("blogger", data)
    report["collected_posts"] = len(posts)
    return report


async def h_search_keywords(p: dict[str, Any]) -> dict[str, Any]:
    raw = p.get("keyword") or p.get("keywords") or ""
    if isinstance(raw, list):
        raw = ", ".join(str(x) for x in raw)
    primary = str(raw).split(",")[0].strip() or str(raw)
    items: list[dict[str, Any]] = []
    try:
        items = await dtk.search(primary, int(p.get("count", 10) or 10))
    except Exception:
        items = []
    return await analytics.analyze(
        "keywords", {"keyword": primary, "keywords": raw, "items": items}
    )


async def h_generate_script(p: dict[str, Any]) -> dict[str, Any]:
    return await analytics.analyze(
        "script", {"topic": p["topic"], "style": p.get("style"), "refs": p.get("refs", [])}
    )


async def h_generate_video(p: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = dict(p)
    if not p.get("script"):
        s = await analytics.analyze("script", {"topic": p["topic"]})
        data = s.get("data", s)
    script = p.get("script") or data.get("full_script", p["topic"])
    terms = p.get("video_terms") or data.get("search_terms") or []
    if not terms:
        # 兜底：LLM 没给搜索词时用主题派生，避免成片引擎进入它自己的 LLM 生成阶段
        terms = [p["topic"]]
    video_req = {
        "video_subject": p["topic"],
        "video_script": script,
        # 关键融合：把我方 AI 生成的搜索词直接给 MPT，绕过其内部 LLM
        "video_terms": terms,
        "video_aspect": p.get("ratio", "9:16"),
        # 素材源：local=本地素材库（默认，零外网依赖）；pixabay 等在线源可选
        "video_source": p.get("video_source", "local"),
        # Edge TTS（免费）：必须指定有效中文音色，否则 audio 阶段 Invalid voice
        "voice_name": p.get("voice_name", "zh-CN-XiaoxiaoNeural"),
        "subtitle_enabled": bool(p.get("subtitle_enabled", True)),
    }
    if video_req["video_source"] == "local":
        # 本地素材模式：扫描 MPT 素材目录，全部文件作为候选素材传给引擎
        files = sorted(
            f for f in local_videos_dir().iterdir()
            if f.is_file() and f.suffix.lower() in MATERIAL_EXTS
        ) if local_videos_dir().exists() else []
        if not files:
            return {
                "status": "deferred", "script": script, "terms": terms,
                "reason": "本地素材库为空：到「素材库 → 视频素材」上传视频片段后重试"
                          "（也可在提交时选择 Pixabay 在线取材）",
            }
        video_req["video_materials"] = [
            {"provider": "local", "url": f.name} for f in files
        ]
    try:
        resp = await mpt.create_video(video_req)
        mpt_tid = (resp.get("data") or {}).get("task_id") or resp.get("task_id")
        return {"status": "submitted", "mpt_task_id": mpt_tid,
                "topic": p["topic"], "script": script, "terms": terms}
    except Exception as e:
        # MPT 未就绪或缺素材 key：返回脚本与搜索词，标注成片待执行
        return {"status": "deferred", "topic": p["topic"], "script": script,
                "terms": terms, "reason": str(e)}


def _post_brief(p: dict[str, Any]) -> dict[str, Any]:
    """把一条作品压成轻量摘要，避免把视频直链等大字段塞给 LLM。"""
    stats = p.get("stats") or {}
    tags = p.get("tags") or []
    return {
        "title": p.get("title") or p.get("description"),
        "tags": tags[:6] if isinstance(tags, list) else [],
        "digg_count": stats.get("digg_count"),
        "collect_count": stats.get("collect_count"),
        "comment_count": stats.get("comment_count"),
        "share_count": stats.get("share_count"),
        "duration_ms": p.get("duration_ms"),
        "created_at": p.get("created_at"),
    }


async def h_account_review(p: dict[str, Any]) -> dict[str, Any]:
    posts = p.get("posts") or []
    handle = p.get("blogger") or p.get("url")
    if not posts and handle:
        # 自动采集：用主页链接 / 分享文案 / sec_uid / 抖音号 拉取作品列表
        raw = await dtk.user_posts(handle, int(p.get("post_limit", 20) or 20))
        posts = [_post_brief(x) for x in raw]
    data = {"posts": posts, "blogger": handle}
    report = await analytics.analyze("review", data)
    if posts:
        report["collected_posts"] = len(posts)
    return report


async def h_rewrite(p: dict[str, Any]) -> dict[str, Any]:
    data = {"text": p.get("text") or p.get("source") or "",
            "mode": p.get("mode", "structure"),
            "my_info": p.get("my_info", "")}
    return await analytics.analyze("rewrite", data)


HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "analyze-link": h_analyze_link,
    "analyze-blogger": h_analyze_blogger,
    "search-keywords": h_search_keywords,
    "generate-script": h_generate_script,
    "generate-video": h_generate_video,
    "account-review": h_account_review,
    "rewrite": h_rewrite,
}


def archive_result(kind: str, result: dict[str, Any], source_task_id: str) -> str | None:
    """把成功任务的结果沉淀进素材库，返回归档 id。"""
    title = (result.get("title") or result.get("blogger_name")
             or result.get("account_name") or result.get("keyword")
             or result.get("topic") or (result.get("script") or "")[:40] or kind)
    summary = (result.get("hook") or result.get("trend")
               or result.get("positioning") or result.get("current_status") or "")
    aid = uuid.uuid4().hex
    with _lock, _db() as c:
        c.execute(
            "INSERT INTO archive(id,kind,title,summary,result,source_task_id,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (aid, kind, str(title)[:120], str(summary)[:200],
             json.dumps(result, ensure_ascii=False, default=str), source_task_id, _now()),
        )
    return aid


def list_archive(keyword: str | None = None, kind: str | None = None,
                 limit: int = 100) -> list[dict[str, Any]]:
    q = "SELECT * FROM archive"
    conds, vals = [], []
    if keyword:
        conds.append("(title LIKE ? OR summary LIKE ? OR result LIKE ?)")
        kw = f"%{keyword}%"
        vals += [kw, kw, kw]
    if kind:
        conds.append("kind = ?")
        vals.append(kind)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY created_at DESC LIMIT ?"
    vals.append(limit)
    with _db() as c:
        rows = c.execute(q, vals).fetchall()
    return [dict(r) for r in rows]


def delete_archive(aid: str) -> bool:
    with _lock, _db() as c:
        cur = c.execute("DELETE FROM archive WHERE id=?", (aid,))
    return cur.rowcount > 0


async def _run(tid: str, kind: str, payload: dict[str, Any]) -> None:
    handler = HANDLERS.get(kind)
    if handler is None:
        _update(tid, status="failed", error=f"unknown kind {kind}")
        return
    async with _sem:
        _update(tid, status="running")
        try:
            result = await handler(payload)
            if isinstance(result, dict):
                # 演示模式标记：强制 Mock 或未配 LLM Key 时为 True，前端据此提示"分析为示例"
                from studio.analytics.llm import is_demo_mode

                result["demo_mode"] = is_demo_mode()
            _update(tid, status="succeeded", result=json.dumps(result, ensure_ascii=False, default=str))
            try:
                archive_result(kind, result, tid)  # 自动沉淀素材库
            except Exception:  # 归档失败不影响任务
                pass
        except Exception as e:  # noqa: BLE001
            _update(tid, status="failed", error=str(e))
