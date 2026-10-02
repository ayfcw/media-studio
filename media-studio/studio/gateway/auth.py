"""网关鉴权：X-API-Key。

- 配置了 GATEWAY_API_KEY（环境变量或设置）则强制校验；
- 未配置则进入本地开发模式（放行，仅记录），避免本地无法调用。
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException

DEV_MODE = not bool(os.environ.get("GATEWAY_API_KEY"))


async def require_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("GATEWAY_API_KEY")
    if not expected:
        return  # 开发模式放行
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
