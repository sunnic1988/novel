# 🏔️ Novel — 玄幻修仙多Agent创作系统

> 多Agent协作的玄幻修仙网文创作引擎，支持各类修仙/仙侠/玄幻题材

## 核心特性

- **6个专业Agent** — 策划师、世界观师、写手、审校师、润色师、读者模拟
- **CrewAI编排** — 流水线式章节创作，每章经过规划→写作→审校→润色→读者反馈
- **Claude + DeepSeek混用** — 创意写作用Claude，分析推理用DeepSeek
- **爆款范文向量化** — 内置修仙经典桥段参考库，ChromaDB驱动
- **通用玄幻修仙** — 预置力量体系模板、文风指南，适配各类修仙题材

## 快速开始

```bash
# 安装依赖
pip install -e ".[dev]"

# 配置API密钥（使用APIMart聚合平台，一个Key访问所有模型）
cp .env.example .env
# 编辑 .env，填入 APIMART_API_KEY（从 https://apimart.ai/keys 获取）

# 初始化项目
novel init

# 导入爆款范文到向量库
novel ingest

# 查看项目状态
novel status

# 创作第一章
novel write 1 -t ""
```

## Agent角色分工

| Agent | 角色 | 使用模型 | 职责 |
|-------|------|---------|------|
| 策划师 | Planner | DeepSeek V3.1 | 场景beats、节奏曲线、钩子设计 |
| 世界观师 | WorldBuilder | DeepSeek V3.1 | 设定管理、人物卡、力量体系 |
| 写手 | Writer | Claude Sonnet 4.6 | 章节正文撰写 |
| 审校师 | Reviewer | DeepSeek V3.1 | 十维度质量审查 |
| 润色师 | Polisher | Claude Sonnet 4.6 | 去AI味、语言精修 |
| 读者模拟 | ReaderSim | DeepSeek V3.1 | 模拟目标读者反馈 |

> 所有模型通过 [APIMart](https://apimart.ai) API聚合平台统一调用，只需一个API Key。

## 项目结构

```
novel/
├── src/novel_agents/      # 核心代码
│   ├── agents/            # 6个Agent定义
│   ├── core/              # 编排器、记忆管理、LLM网关
│   └── tools/             # 范文检索、圣经查阅等工具
├── bible/                 # 故事圣经（人物卡/世界观/文风）
├── references/            # 爆款范文参考库
├── plans/                 # 大纲和章节规划
├── chapters/              # 生成的章节正文
└── reviews/               # 审查报告
```

## 单章创作流水线

```
策划师 → 世界观师 → 写手 → 审校师 → 润色师 → 读者模拟
                                ↑              ↓
                                └── 不通过则退回重写 ──┘
```

## 自定义

- **添加角色**：在 `bible/characters/` 下创建 `.md` 文件
- **添加范文**：在 `references/` 下添加 `.md` 或 `.txt` 文件，运行 `novel ingest`
- **修改大纲**：编辑 `plans/synopsis.md`
- **调整LLM**：修改 `src/novel_agents/core/llm_gateway.py`（可切换APIMart支持的任何模型）
