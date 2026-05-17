# Novel Agents · 前端仪表盘

Next.js 14 + React 18 + Tailwind + Framer Motion。

## 启动

```bash
# 1) 启动后端 (项目根目录)
novel serve --port 8765

# 2) 启动前端
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

前端通过 `next.config.mjs` 中的 `rewrites` 把 `/api/*` 和 `/ws` 反向代理到后端 `http://127.0.0.1:8765`。

如需指向其他后端：

```bash
NEXT_PUBLIC_API_BASE=http://your-host:8765 npm run dev
```

## 主要能力

- 6 Agent 实时进度卡（状态 / token / LLM 调用 / 工具调用 / 当前消息）
- 全量执行留痕事件流，可按「关键 / LLM / 工具 / 全部」过滤
- 启动 / 暂停 / 继续 / 终止 流水线
- 任意 Agent 完成或运行中均可一键人工干预（编辑产出后续传下一阶段）
- 爆款范文上传 / 删除 / 一键向量化 / 语义检索
- `Live` 模式调用真实 LLM；`Mock` 模式可在无 API Key 下完整演示 UI
