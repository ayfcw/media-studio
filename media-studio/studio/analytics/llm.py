"""LLM 客户端：Key 运行时注入；未配置或 Mock 模式下返回符合 schema 的样例。"""
from __future__ import annotations

import json
import os
from typing import Any

from studio.analytics import schemas
from studio.common.settings_store import get_llm_settings

# 强制 Mock 开关：仅当显式设置 STUDIO_MOCK=1 时生效。
# 默认行为：配置了 api_key 就走真实 LLM，没配置就走 Mock（填 Key 即真实，无需重启）
FORCE_MOCK = os.environ.get("STUDIO_MOCK") == "1"


MOCK_SAMPLES: dict[str, dict[str, Any]] = {
    "breakdown": {
        "title": "[示例] 普通人做副业，我靠这3步月入过万",
        "topic": "副业/赚钱",
        "hook": "用反常识结论开场，制造身份焦虑与好奇",
        "target_audience": "想增加收入的上班族",
        "structure": [
            {"name": "钩子", "content": "晒收入截图+反问", "purpose": "3 秒留人"},
            {"name": "干货", "content": "分 3 步讲方法", "purpose": "提供价值"},
            {"name": "结尾", "content": "引导关注领资料", "purpose": "涨粉转化"},
        ],
        "golden_points": ["强结果背书", "步骤化表达"],
        "replicable_points": ["结果前置开场", "数字分点"],
        "risk_points": ["收入真实性需合规"],
        "suggested_rewrite": "可把副业换成减脂、学习等赛道复用三步结构",
    },
    "blogger": {
        "blogger_name": "[示例] 某知识博主",
        "positioning": "职场效率干货",
        "audience": "22-35 岁职场人",
        "content_pillars": ["效率工具", "职场沟通", "时间管理"],
        "style": "口播+屏幕录制，节奏快",
        "posting_frequency": "每周 4 条",
        "monetization": "课程+社群",
        "strengths": ["选题稳定", "结构清晰"],
        "weaknesses": ["场景化不足"],
        "benchmark_posts": [
            {"title": "[示例] 3 个被低估的效率工具", "url": None, "likes": 50000,
             "highlight": "工具盘点类易收藏"}
        ],
        "actionable": ["建立固定选题库", "每条加入真实案例"],
    },
    "review": {
        "account_name": "[示例] 我的账号",
        "positioning": "定位略模糊，需聚焦单一赛道",
        "current_status": "更新不稳定，播放量两极分化",
        "data_summary": "近 30 天均播 3000，完播率偏低",
        "strengths": ["画面质感好"],
        "problems": [
            {"issue": "开头拖沓", "severity": "high", "suggestion": "前 3 秒给结果/冲突"},
            {"issue": "选题发散", "severity": "medium", "suggestion": "聚焦 1 个赛道"},
        ],
        "suggestions": ["固定更新频率", "统一封面风格"],
        "priority_actions": ["重写前 3 秒钩子", "梳理 20 条聚焦选题"],
    },
    "keywords": {
        "keyword": "副业",
        "trend": "长期高热，年初与毕业季峰值",
        "hot_items": [
            {"title": "[示例] 副业合集", "url": None, "platform": "douyin",
             "likes": 80000, "reason": "清单体+结果背书"}
        ],
        "common_patterns": ["结果前置", "数字清单", "真实案例"],
        "content_angles": ["新手避坑", "低成本启动", "下班后时间安排"],
    },
    "script": {
        "topic": "[示例] 新手如何开始副业",
        "title_options": ["[示例] 下班后2小时，我这样多赚一份工资", "[示例] 副业避坑指南"],
        "hook": "先别盲目报课，新手做副业记住这 3 步。",
        "body": "第一步盘点技能，第二步选轻成本方向，第三步小步验证。",
        "cta": "点赞收藏，评论区领副业清单。",
        "full_script": "先别盲目报课，新手做副业记住这 3 步。第一步盘点你已有的技能……"
                       "第二步选轻成本方向……第三步小步验证……点赞收藏，评论区领清单。",
        "hashtags": ["#副业", "#新手", "#自我提升"],
        "search_terms": ["副业", "技能盘点", "轻成本创业", "下班后赚钱"],
    },
    "rewrite": {
        "mode": "structure",
        "source_summary": "[示例] 原文案：晒副业收入截图开场 → 三步法干货 → 引导领资料",
        "extracted_topic": "结果前置 + 步骤化干货的副业教学结构",
        "structure_used": [
            {"name": "钩子", "content": "结果/反常识开场", "purpose": "3 秒留人"},
            {"name": "干货", "content": "分步骤讲方法", "purpose": "提供价值"},
            {"name": "结尾", "content": "引导关注领取资料", "purpose": "涨粉转化"},
        ],
        "title_options": ["[示例] 同款结构换个赛道：减脂版三步法", "[示例] 我把这套结构用在了学习赛道"],
        "hook": "谁说上班族没时间减脂？我照搬这套三步法，一个月掉了 6 斤。",
        "body": "第一步只记录不节食，第二步把晚饭主食换成粗粮，第三步每天 20 分钟跟练。",
        "cta": "点赞收藏，评论区领跟练计划表。",
        "full_script": "谁说上班族没时间减脂？我照搬这套三步法，一个月掉了 6 斤。"
                       "第一步只记录不节食……第二步把晚饭主食换成粗粮……第三步每天 20 分钟跟练……"
                       "点赞收藏，评论区领跟练计划表。",
        "dedup_notes": ["[示例] 案例从副业换成减脂", "数字与句式全部重写", "保留结构但表达原创"],
        "hashtags": ["#减脂", "#上班族", "#自律"],
        "search_terms": ["减脂餐", "上班族运动", "跟练", "减脂干货"],
    },
}


def _mock(kind: str) -> dict[str, Any]:
    return MOCK_SAMPLES.get(kind, {"kind": kind})


def is_demo_mode() -> bool:
    """演示模式判定：强制 Mock 开启，或未配置 api_key。"""
    return FORCE_MOCK or not get_llm_settings().get("api_key")


def analyze_json(system_prompt: str, user_content: str, kind: str) -> dict[str, Any]:
    """返回经 schema 校验的结果 dict。无 Key / Mock 时返回样例。"""
    settings = get_llm_settings()
    use_mock = FORCE_MOCK or not settings.get("api_key")

    raw: dict[str, Any]
    if use_mock:
        raw = _mock(kind)
    else:
        from openai import OpenAI

        client = OpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
        resp = client.chat.completions.create(
            model=settings["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            # 关闭 deepseek-flash 的思考模式（结构化拆解不需要推理链，速度更快）
            extra_body={"thinking": {"type": "disabled"}},
        )
        raw = json.loads(resp.choices[0].message.content)

    # 用对应 Pydantic 模型校验，失败则返回原始 dict（容错不中断）
    model = schemas.RESULT_MODELS.get(kind)
    if model:
        return model.model_validate(raw).model_dump()
    return raw
