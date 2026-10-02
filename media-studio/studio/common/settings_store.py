"""凭据 / 设置的运行时加密存储。

- 所有敏感配置（LLM api_key、飞书 app_secret 等）都用 Fernet 对称加密后落盘；
- 加密主密钥优先取环境变量 SETTINGS_SECRET，否则在数据目录持久化一个 .secret
  （避免每次重启随机生成密钥导致旧密文无法解密）；
- public_* 系列方法只返回"是否已配置"，绝不回传明文。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# 数据目录：可用环境变量 STUDIO_DATA_DIR 覆盖
DATA_DIR = Path(os.environ.get("STUDIO_DATA_DIR", Path(__file__).resolve().parents[3] / "data"))
STORE_PATH = DATA_DIR / "settings.json.enc"
SECRET_PATH = DATA_DIR / ".secret"


def _fernet() -> Fernet:
    key = os.environ.get("SETTINGS_SECRET")
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SECRET_PATH.exists():
        SECRET_PATH.write_bytes(Fernet.generate_key())
        try:
            SECRET_PATH.chmod(0o600)
        except OSError:
            pass
    return Fernet(SECRET_PATH.read_bytes())


def _deep_merge(base: dict[str, Any], new: dict[str, Any]) -> None:
    """递归合并：dict 嵌套合并，其他值直接覆盖。"""
    for k, v in new.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def save_settings(data: dict[str, Any]) -> None:
    """整体合并写入（深层合并，避免只改 model 时把同段的 api_key 洗掉）。"""
    current = load_settings()
    _deep_merge(current, data)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_bytes(
        _fernet().encrypt(json.dumps(current, ensure_ascii=False).encode("utf-8"))
    )


def load_settings() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return {}
    return json.loads(_fernet().decrypt(STORE_PATH.read_bytes()).decode("utf-8"))


def get_section(name: str) -> dict[str, Any]:
    return load_settings().get(name, {})


def get_llm_settings() -> dict[str, Any]:
    """供 llm.py 使用；环境变量 ANALYTICS_LLM_* 作为兜底默认。"""
    s = get_section("llm")
    return {
        "base_url": s.get("base_url") or os.environ.get("ANALYTICS_LLM_BASE", "https://api.deepseek.com/v1"),
        "api_key": s.get("api_key") or os.environ.get("ANALYTICS_LLM_KEY", ""),
        "model": s.get("model") or os.environ.get("ANALYTICS_LLM_MODEL", "deepseek-chat"),
    }


def public_settings() -> dict[str, Any]:
    """给前端 / GET settings：只暴露非敏感字段与"是否已配置"。"""
    s = load_settings()
    llm = s.get("llm", {})
    feishu = s.get("feishu", {})
    dtk = s.get("dtk", {})
    return {
        "llm": {
            "base_url": llm.get("base_url"),
            "model": llm.get("model"),
            "api_key_configured": bool(llm.get("api_key")),
        },
        "feishu": {
            "app_id": feishu.get("app_id"),
            "app_secret_configured": bool(feishu.get("app_secret")),
        },
        "dtk": {
            "api_key_configured": bool(dtk.get("api_key")),
        },
    }
