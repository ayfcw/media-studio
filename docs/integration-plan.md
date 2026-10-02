# 融合方案 · 对标一木的全链路补强计划

> 对标对象：一木【自媒体全链路运营 AI 工具】（智能体全家桶 + 知识库 + DataHub）
> 本文档基于其产品说明与本项目现状的逐项比对，筛选出需要补齐/增强的能力，
> 并给出经社区活跃度核实的开源选型与落地路径。

## 一、对标差距分析

| 能力 | 一木 | 本项目现状 | 差距结论 |
|---|---|---|---|
| 单条爆款拆解 | ✅ 文案+数据 | ✅ 元数据+数据，原视频可回放 | ⚠️ 缺**口播逐字稿**，AI 拆解"看不到"内容 |
| 博主拆解 | ✅ 批量文案+数据 | ✅ 批量元数据 | ⚠️ 同上，缺口播文案 |
| 账号复盘 | ✅ 文案+数据反推 | ✅ 自动采集+诊断 | ⚠️ 缺口播与评论维度 |
| 关键词找爆款 | ✅ 真实搜索 | ⚠️ 有任务类型但采集层无搜索端点，**降级输出** | ❌ 真实短板 |
| 文案生成 | ✅ | ✅ | 无差距 |
| 仿写三件套 | ✅ | ✅ | 无差距 |
| 数据沉淀 | ✅ 表格 | ✅ 素材库 + 飞书同步 | 无差距 |
| 评论分析 | ✅ DataHub | ❌ 未集成 | 可低成本补齐 |
| 知识库问答 | ✅ 近百篇文档 RAG | ❌ | 可用成熟 RAG 平台补齐 |
| 多平台（小红书/视频号） | ✅ | ❌ 仅抖音 | 可按需启用 |

**结论**：文案生成/仿写/沉淀我们已持平或更强（结构化报告 + 视频回放是一木没有的）；
四个真实差距按价值排序：**① 口播逐字稿 ② 评论采集 ③ 关键词搜索真实化 ④ 知识库问答**。

## 二、选型评估（GitHub 实测数据 2026-10-03）

| 候选 | Star | 活跃度 | 许可 | 评估 |
|---|---|---|---|---|
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 25.7k | 昨日更新 | MIT | ✅ **口播转写首选**：CTranslate2 推理，CPU 可跑（small/int8 ≈ 1GB 内存），pip 直接装，中文效果好 |
| [modelscope/FunASR](https://github.com/modelscope/FunASR) | 20.6k | 昨日更新 | MIT | 备选：中文 Paraformer 精度高，但依赖更重 |
| [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 66.1k | 近期更新 | 自定义（**仅限学习研究**） | ✅ **关键词搜索方案**：支持抖音/小红书/视频号/快手/B站的关键词搜索、笔记、评论采集；Playwright+登录态，独立进程运行，与现有 API 采集互补 |
| [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | 66.7k | 昨日更新 | MIT | ✅ **知识库问答首选**：单容器 all-in-one，内置 LanceDB 向量库，接 OpenAI 兼容 Key 即用，内存占用远低于 Dify/RAGFlow |
| [langgenius/dify](https://github.com/langgenius/dify) | 157.7k | 持续 | Apache 附加条款 | 功能强但全家桶内存 4G+，1.8G 服务器带不动，不选 |
| [infiniflow/ragflow](https://github.com/infiniflow/ragflow) | 91.6k | 持续 | Apache-2.0 | 深度文档解析强，同样过重，不选 |

已拉取：`MediaCrawler/`（浅克隆至仓库根，已加入 .gitignore，独立管理版本）。

## 三、落地路径

### P0 · 口播逐字稿（让 AI"听懂"视频）★ 最高价值
- **集成点**：`studio/gateway/tasks.py` 已有 `cache_video()`（拆解时自动缓存无水印视频）——在此之后追加：
  1. `ffmpeg -i video.mp4 -vn -ar 16000 audio.wav` 抽音轨（MPT venv 与系统均有 ffmpeg 可复用；网关容器镜像需追加 ffmpeg 包）
  2. `faster-whisper small/int8` CPU 转写 → `report.source.transcript`
  3. `prompts.py` 的 breakdown/review/keywords 三类提示词注入逐字稿全文，AI 从"猜结构"升级为"读内容"
- **前端**：拆解报告新增「口播文案」折叠面板（可复制），与原视频播放并排
- **资源**：本地全量开；云端 1.8G 内存建议 `tiny/small int8` 档或仅在本地跑转写
- **验收**：一条真实视频拆解，报告能引用逐字稿中的具体语句分析钩子与节奏

### P1 · 评论采集（低成本高收益）
- DTK 已内置异步评论端点（实测闭环：`/douyin/video/comments` → task_id 轮询）
- **集成点**：`clients.py` 新增 `comments()`（提交+轮询 40s）；拆解/复盘成功后拉 20 条热评注入 prompt，报告新增「评论区洞察」（高频词/情绪/用户追问方向）
- **验收**：拆解报告出现真实评论引用

### P1 · 关键词搜索真实化（MediaCrawler 融合）
- **形态**：独立进程运行（`uv sync` + Playwright + 扫码登录一次），输出 JSON 落盘 `data/search_results/`
- **集成点**：网关 `search-keywords` handler 由"降级"改为调用本地 MediaCrawler CLI（`--keywords`、`--type=video`），解析 JSON 进现有分析链路；采集服务不可达时保留现降级路径
- **合规**：MediaCrawler 许可仅限学习研究——自用部署，不对外提供服务
- **验收**：输入"减脂餐"返回真实爆款列表与数据

### P2 · 知识库问答（对标一木知识库）
- **形态**：AnythingLLM 单容器（`anythingllm/anythingllm`），内置向量库，配置同一个 LLM Key
- **集成点**：平台「素材库」加「知识库」入口（嵌入或跳转）；把自媒体运营文档批量导入即成"随问随答的运营顾问"
- **服务器内存不足时放本地跑，云端仅做入口**

### P2 · 小红书通道
- 启用已 clone 的 XHS-Downloader（`uv sync`），网关新增 xhs 解析通道，工作台链接输入自动分流平台

## 四、排期建议

| 阶段 | 内容 | 工作量 |
|---|---|---|
| 第一批 | P0 口播逐字稿 + P1 评论采集 | 网关/提示词/前端各小改，一次发布 |
| 第二批 | P1 关键词搜索（MediaCrawler 融合） | 中等（含登录态运维） |
| 第三批 | P2 知识库 + 小红书 | 以部署配置为主 |
