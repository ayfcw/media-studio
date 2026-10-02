"""分析服务：组合提示词 + LLM，按业务类型输出结构化结果。"""
from __future__ import annotations

import json
from typing import Any

from studio.analytics.llm import analyze_json
from studio.analytics.prompts import PROMPTS


def analyze(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind not in PROMPTS:
        raise ValueError(f"unknown analysis kind: {kind}")
    user_content = json.dumps(payload, ensure_ascii=False, default=str)
    return analyze_json(PROMPTS[kind], user_content, kind)
