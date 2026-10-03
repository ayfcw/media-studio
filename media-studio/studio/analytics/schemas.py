"""AI 分析引擎的结构化输出模型（5 类业务结果）。

字段即"产品报告"的栏目，LLM 必须输出符合这些 schema 的 JSON。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- 1. 爆款视频拆解 ----------
class Segment(BaseModel):
    name: str = Field(description="段落名，如 钩子/背景/干货/转折/结尾")
    content: str = Field(description="该段落讲了什么")
    purpose: str = Field(description="该段落的作用/为什么有效")


class BreakdownResult(BaseModel):
    kind: Literal["breakdown"] = "breakdown"
    title: str
    topic: str = Field(description="视频主题/赛道")
    hook: str = Field(description="开头钩子分析")
    target_audience: str = Field(description="目标受众")
    structure: list[Segment]
    golden_points: list[str] = Field(description="爆点/高光设计")
    replicable_points: list[str] = Field(description="可直接复用的套路")
    risk_points: list[str] = Field(default_factory=list, description="风险/不可学之处")
    suggested_rewrite: str = Field(description="套用该结构的改写建议")
    comment_insights: list[str] = Field(
        default_factory=list,
        description="评论区洞察：仅当输入数据包含 comments 时输出（高赞观点/用户追问/情绪倾向/可蹭的话题点），无 comments 时留空",
    )


# ---------- 2. 博主对标 ----------
class BenchmarkPost(BaseModel):
    title: str
    url: str | None = None
    likes: int | None = None
    highlight: str = Field(description="这条为什么值得参考")


class BloggerResult(BaseModel):
    kind: Literal["blogger"] = "blogger"
    blogger_name: str
    positioning: str = Field(description="账号定位")
    audience: str = Field(description="受众画像")
    content_pillars: list[str] = Field(description="内容支柱/选题方向")
    style: str = Field(description="表达风格")
    posting_frequency: str = Field(description="更新频率")
    monetization: str = Field(default_factory=str, description="变现方式")
    strengths: list[str]
    weaknesses: list[str]
    benchmark_posts: list[BenchmarkPost]
    actionable: list[str] = Field(description="我方可执行的对标动作")


# ---------- 3. 账号复盘 ----------
class Problem(BaseModel):
    issue: str
    severity: Literal["high", "medium", "low"] = "medium"
    suggestion: str


class ReviewResult(BaseModel):
    kind: Literal["review"] = "review"
    account_name: str | None = None
    positioning: str = Field(description="账号定位是否清晰")
    current_status: str = Field(description="现状概述")
    data_summary: str = Field(description="关键数据概览（播放/点赞/涨粉趋势）")
    strengths: list[str]
    problems: list[Problem]
    suggestions: list[str]
    priority_actions: list[str] = Field(description="下一步优先动作（按优先级）")


# ---------- 4. 关键词找爆款 ----------
class HotItem(BaseModel):
    title: str
    url: str | None = None
    platform: str | None = None
    likes: int | None = None
    reason: str = Field(description="为什么是爆款/共性")


class KeywordsResult(BaseModel):
    kind: Literal["keywords"] = "keywords"
    keyword: str
    trend: str = Field(description="该关键词的热度趋势判断")
    hot_items: list[HotItem]
    common_patterns: list[str] = Field(description="爆款共性规律")
    content_angles: list[str] = Field(description="可切入的内容角度")


# ---------- 5. 文案生成 / 仿写 ----------
class ScriptResult(BaseModel):
    kind: Literal["script"] = "script"
    topic: str
    title_options: list[str]
    hook: str
    body: str = Field(description="正文（口播稿主体）")
    cta: str = Field(description="结尾引导/行动号召")
    full_script: str = Field(description="可直接朗读的完整口播稿")
    hashtags: list[str]
    search_terms: list[str] = Field(default_factory=list, description="视频素材搜索词")


# ---------- 6. 仿写三件套 ----------
class RewriteResult(BaseModel):
    kind: Literal["rewrite"] = "rewrite"
    mode: Literal["structure", "topic", "dedup"] = "structure"
    source_summary: str = Field(description="原文案选题与结构概括")
    extracted_topic: str = Field(description="提炼出的核心选题")
    structure_used: list[Segment] = Field(default_factory=list, description="复用的结构")
    title_options: list[str]
    hook: str
    body: str
    cta: str
    full_script: str = Field(description="可直接朗读的完整新文案")
    dedup_notes: list[str] = Field(default_factory=list, description="去重/差异化处理点")
    hashtags: list[str]
    search_terms: list[str] = Field(default_factory=list, description="视频素材搜索词")


RESULT_MODELS: dict[str, type[BaseModel]] = {
    "breakdown": BreakdownResult,
    "blogger": BloggerResult,
    "review": ReviewResult,
    "keywords": KeywordsResult,
    "script": ScriptResult,
    "rewrite": RewriteResult,
}
