"""飞书多维表格同步（服务端 tenant_access_token 方式）。

凭据从 settings 的 [feishu] 段读取（在系统设置页填写，加密存储）。
"""
from __future__ import annotations

from typing import Any

import httpx

from studio.common.settings_store import get_section

BASE = "https://open.feishu.cn/open-apis"


def _creds() -> dict[str, str]:
    s = get_section("feishu")
    return {
        "app_id": s.get("app_id", ""),
        "app_secret": s.get("app_secret", ""),
    }


async def get_tenant_token() -> str:
    creds = _creds()
    if not creds["app_id"] or not creds["app_secret"]:
        raise RuntimeError("飞书 app_id/app_secret 未配置，请到系统设置页填写")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{BASE}/auth/v3/tenant_access_token/internal", json=creds)
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data}")
        return data["tenant_access_token"]


async def batch_create_records(
    app_token: str, table_id: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    """批量写入多维表格记录。records: [{"fields": {...}}, ...]"""
    token = await get_tenant_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, headers=headers, json={"records": records})
        return r.json()


def report_to_record(report: dict[str, Any]) -> dict[str, Any]:
    """把一份分析报告转成多维表格 fields（扁平关键字段，便于建表）。"""
    def join(v: Any) -> str:
        if isinstance(v, list):
            return "\n".join(json_item(x) for x in v)
        return str(v)

    def json_item(x: Any) -> str:
        if isinstance(x, dict):
            return " | ".join(f"{k}:{v}" for k, v in x.items())
        return str(x)

    import json
    fields = {"原始JSON": json.dumps(report, ensure_ascii=False)}
    for key in ("title", "topic", "hook", "trend", "current_status", "positioning",
                "full_script", "suggested_rewrite"):
        if key in report:
            fields[key] = join(report[key])
    for list_key in ("replicable_points", "common_patterns", "content_angles",
                     "priority_actions", "hashtags", "golden_points"):
        if list_key in report:
            fields[list_key] = join(report[list_key])
    return {"fields": fields}
