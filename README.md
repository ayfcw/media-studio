# 自媒体智能体平台（media-studio）

一站式自媒体内容工作台：**采集 → AI 拆解 → 仿写 → 一键成片 → 复盘归档**，融合两个高星开源项目（DTK 采集、MoneyPrinterTurbo 成片）+ 自研编排层（FastAPI 网关 + AI 分析引擎 + React 前端 + MCP 服务）。

## 功能总览

| 智能体 | 说明 |
|---|---|
| 爆款视频拆解 | 粘贴抖音分享链接，采集元数据（标题/文案/标签/赞藏评转）+ 缓存无水印原视频，AI 输出结构化拆解报告（赛道/钩子/结构/爆点/改写建议），报告页可直接播放原视频 |
| 博主对标拆解 | 输入博主主页，自动采集作品列表，输出定位/受众/内容支柱/对标作品分析 |
| 关键词找爆款 | 按关键词梳理爆款清单、共性规律与切入角度 |
| 原创文案生成 | 生成口播稿（钩子/正文/CTA）+ 标题候选 + 话题标签 + 素材搜索词 |
| 仿写三件套 | 结构仿写 / 选题提炼 / 同主题去重，可注入"我的账号信息"个性化输出 |
| 一键成片 | AI 文案 → Edge TTS 配音 → 字幕 → 本地素材库/Pixabay 取材 → FFmpeg 合成出片 |
| 账号复盘诊断 | 结合自动采集的作品数据，诊断问题并给出优先动作 |
| 内容沉淀库 | 成功任务自动归档，支持关键词/类型检索、飞书多维表格同步 |

## 架构

```
┌─────────────────────────── 浏览器（React + antd）───────────────────────────┐
│  仪表盘 / 工作台 / 任务中心 / 素材库（视频素材上传 + 内容沉淀）/ 系统设置      │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ /api/v1/*
┌──────────────────────────────▼──────────────────────────────────────────────┐
│                      编排网关 studio-gateway (FastAPI :8200)                │
│   任务状态机(SQLite) · 鉴权 · 素材上传 · 视频缓存 · MPT 地址改写 · 飞书同步    │
└───────┬──────────────────────┬──────────────────────────┬──────────────────┘
        │                      │                          │
┌───────▼────────┐   ┌─────────▼──────────┐   ┌───────────▼──────────┐
│ DTK 采集 (Docker)│   │ AI 分析引擎         │   │ MPT 成片引擎          │
│ Evil0ctal/      │   │ studio-analytics    │   │ harry0703/           │
│ Douyin_TikTok_  │   │ :8100               │   │ MoneyPrinterTurbo    │
│ Download_API    │   │ OpenAI 兼容 LLM     │   │ :8090 / GHCR 镜像    │
│ :8000           │   │ 6 类结构化提示词     │   │ FFmpeg 合成           │
└────────────────┘   └────────────────────┘   └──────────────────────┘
        └── MCP 服务 studio-mcp :8300（供 AI 客户端调用平台能力）
```

**设计原则**：核心能力全部来自成熟开源项目，自研代码只做"胶水层"（编排、状态机、鉴权、前端），保持最小可维护面。

## 目录结构

```
├── media-studio/            # 自研层
│   ├── studio/gateway/      # 编排网关（任务状态机/素材/媒体缓存/鉴权）
│   ├── studio/analytics/    # AI 分析引擎（提示词/Schema/LLM 客户端）
│   ├── studio/mcp/          # MCP 服务（AI 客户端可调用平台能力）
│   ├── studio/feishu/       # 飞书多维表格同步
│   ├── studio/common/       # 加密设置存储（Fernet）
│   └── frontend/            # React 18 + antd 5 + Vite
├── deploy_cloud/            # 云端部署（compose/nginx/Dockerfile/初始化脚本）
├── start_all.ps1            # 本地一键启动（幂等）
└── _gen_env.py              # DTK .env 生成器（随机密钥）
```

> 上游开源项目（DTK / MoneyPrinterTurbo / XHS-Downloader）通过 git clone 独立获取，不入本仓库。

## 快速开始

### 前置要求
- Windows + Docker Desktop（DTK 采集栈）
- Python 3.12 + [uv](https://docs.astral.sh/uv/)（studio 层）
- Node.js 18+（前端）
- 一个 OpenAI 兼容 LLM Key（DeepSeek / Kimi / 通义等）

### 1. 获取上游项目（仓库根目录下）
```bash
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
python _gen_env.py   # 生成 DTK 的 .env（随机密钥）
```

### 2. 启动采集与成片引擎
```powershell
# DTK 采集栈（Docker）
docker compose -p dtk -f Douyin_TikTok_Download_API/docker/compose.yml up -d
# MPT 成片（源码运行）
cd MoneyPrinterTurbo && uv venv && uv pip install -r requirements.txt && python main.py
```

### 3. 启动 studio 层与前端
```powershell
cd media-studio
uv sync
uvicorn studio.analytics.app:app --port 8100
uvicorn studio.gateway.app:app --port 8200   # 需环境变量 MPT_URL=http://127.0.0.1:8090
STUDIO_MCP_HTTP=1 python -m studio.mcp.server # 可选，:8300
cd frontend && npm install && npm run dev     # http://127.0.0.1:5173
```

或直接运行 `./start_all.ps1`（幂等，自动拉起全部服务）。

### 4. 配置密钥
前端「系统设置」页填入 LLM API Key（Fernet 加密落盘，可随时更换）；DTK 首次启动需从容器日志取 setup token 初始化管理员，并导入抖音 Cookie。

## 云端部署

`deploy_cloud/` 提供完整的一键部署方案：

- `docker-compose.cloud.yml`：MPT（官方 GHCR 镜像）+ gateway/analytics（自构建）+ nginx（口令鉴权 + API Key 注入，前端零改动）
- nginx 静态服务 + `/api/` 反代网关 + `/mpt/` 反代成片产物（视频在线播放）
- 素材目录网关与 MPT 容器共享挂载，网页上传即用
- `init_dtk.sh` / `setup_dtk_key.sh`：DTK 云端初始化（密码经环境变量注入，不入库）

## 安全说明

- 所有凭据（LLM Key / DTK Key / 飞书 Secret）Fernet 加密存储，永不明文回传
- 仓库内的 `nginx.conf` / `mpt-config.toml` / 初始化脚本均为**脱敏模板**（`ACCESS_TOKEN` / `GATEWAY_API_KEY` / `DTK_ADMIN_PASSWORD` 占位），真实值只存在于部署环境
- 建议部署时：DTK 与各服务只绑内网/回环地址，公网入口加鉴权

## 致谢

核心能力基于以下优秀开源项目：

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)（Apache-2.0）—— 抖音/TikTok 采集引擎
- [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)（MIT）—— AI 短视频成片引擎
- [JoeanAmier/XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) —— 小红书采集（可选模块）

本仓库的自研部分遵循同样开放的精神，欢迎 Issue / PR。
