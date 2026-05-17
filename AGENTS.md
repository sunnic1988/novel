## Cursor Cloud specific instructions

这是一个基于 CrewAI 的多Agent协作修仙小说创作系统，专为《凡人修仙传》同人二创设计。

### 技术栈

- **Python 3.12** + CrewAI + ChromaDB
- **LLM**: Claude（写作/润色Agent）+ DeepSeek（策划/审校/世界观/读者模拟Agent）
- **向量化**: ChromaDB 本地存储，用于爆款范文检索和已写章节上下文

### 常用命令

参见 `README.md` 和 `pyproject.toml [project.scripts]`。核心CLI：

- `novel init` — 初始化目录
- `novel ingest` — 向量化范文
- `novel status` — 查看项目状态
- `novel write <章节号> -t "标题"` — 创作一章（需配置API密钥）
- `novel search <关键词>` — 搜索范文库

### 测试和Lint

```bash
python3 -m pytest tests/ -v       # 运行测试
ruff check src/ tests/            # lint检查
```

### 注意事项

- `novel write` 命令需要 `ANTHROPIC_API_KEY` 和 `DEEPSEEK_API_KEY` 环境变量，通过 `.env` 文件配置
- ChromaDB 数据存储在 `.chroma_db/` 目录，已在 `.gitignore` 中忽略
- 向量库在测试过程中会自动创建，无需手动初始化
- `$HOME/.local/bin` 需要在 PATH 中以使用 `novel` CLI 命令
