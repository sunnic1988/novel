# 🏔️ Novel — 玄幻修仙多Agent创作系统

> 多Agent协作的玄幻修仙网文创作引擎，支持各类修仙/仙侠/玄幻题材

## 核心特性

- **9个专业Agent** — 卷纲架构、策划、节奏、世界观、写手、审校、润色、读者模拟、营销
- **CrewAI编排** — 流水线式章节创作，规划→写作→审校→润色→读者反馈→营销包装
- **Claude + DeepSeek混用** — 创意写作用 Claude，分析推理用 DeepSeek
- **爆款范文向量化** — 内置修仙经典桥段参考库，ChromaDB 驱动
- **Web 仪表盘** — 实时进度、事件留痕、人工干预、范文管理与书籍运营面板

## 快速开始

```bash
# 1. 安装依赖（推荐 uv）
uv venv .venv
uv pip install -e ".[dev]"

# 2. 配置 API Key（APIMart 聚合平台，一个 Key 访问 Claude/DeepSeek 等）
cp .env.example .env
# 编辑 .env，填入 APIMART_API_KEY：https://apimart.ai/keys

# 3. 初始化项目（目录 + 故事圣经模板 + 大纲模板）
.venv/bin/novel init

# 4. 导入爆款范文到向量库
.venv/bin/novel ingest

# 5. 查看状态
.venv/bin/novel status
```

### 一键启动仪表盘（推荐）

```bash
cd frontend && npm install && cd ..
python start.py
# 前端 → http://127.0.0.1:3000
# 后端 → http://127.0.0.1:8765
```

### 分步启动

```bash
# 终端 1：后端 API
novel serve --port 8765

# 终端 2：前端
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

前端通过 `next.config.mjs` 将 `/api/*` 与 `/ws` 代理到后端。自定义后端地址：

```bash
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8765 npm run dev
```

### CLI 创作单章

```bash
novel write 1 -t "少年入门"
```

> 仪表盘与 CLI 创作均需要有效的 `APIMART_API_KEY`。

## Agent 角色分工

| Agent | 角色 | 使用模型 | 职责 |
|-------|------|---------|------|
| 卷纲架构师 | ArcArchitect | DeepSeek | 卷级结构与长线伏笔 |
| 策划师 | Planner | DeepSeek | 场景 beats、节奏曲线、钩子设计 |
| 节奏医生 | PacingDoctor | DeepSeek | 开篇/高潮节奏诊断 |
| 世界观师 | WorldBuilder | DeepSeek | 设定管理、人物卡、力量体系 |
| 写手 | Writer | Claude | 章节正文撰写 |
| 审校师 | Reviewer | DeepSeek | 十维度质量审查 |
| 润色师 | Polisher | Claude | 去 AI 味、语言精修 |
| 读者模拟 | ReaderSim | DeepSeek | 模拟目标读者反馈 |
| 营销专员 | MarketingSpecialist | Claude | 标题/简介/运营文案 |

> 所有模型通过 [APIMart](https://apimart.ai) API 聚合平台统一调用，只需一个 API Key。

## 项目结构

```
novel/
├── src/novel_agents/      # 核心代码
│   ├── agents/            # Agent 定义
│   ├── core/              # 编排器、记忆、LLM 网关
│   ├── server/            # FastAPI 仪表盘后端
│   └── tools/             # 范文检索、圣经查阅等
├── frontend/              # Next.js 仪表盘
├── bible/                 # 故事圣经（人物/世界观/文风）
├── references/            # 爆款范文参考库
├── plans/                 # 大纲和章节规划
├── chapters/              # 生成的章节正文
├── reviews/               # 审查报告与 KPI
├── start.py               # 一键启动前后端
└── output/                # Run 产物与留痕
```

## 单章创作流水线

```
卷纲 → 策划 → 节奏 → 世界观 → 写手 → 审校 → 润色 → 读者模拟 → 营销
```

## 测试与 Lint

```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/ruff check src/ tests/
```

## 自定义

- **添加角色**：在 `bible/characters/` 下创建 `.md` 文件
- **添加范文**：在 `references/` 下添加 `.md` 或 `.txt`，运行 `novel ingest`
- **修改大纲**：编辑 `plans/synopsis.md`
- **调整 LLM**：修改 `src/novel_agents/core/llm_gateway.py`
