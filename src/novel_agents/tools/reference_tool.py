"""爆款范文检索工具 — 供Agent在写作时参考经典片段"""

from crewai.tools import BaseTool

from novel_agents.core.memory import query_references


class ReferenceSearchTool(BaseTool):
    name: str = "爆款范文检索"
    description: str = (
        "从修仙小说爆款范文库中检索相关片段，用于参考文风、节奏、爽点设计。"
        "输入关键词或场景描述，返回最相关的范文片段。"
    )

    def _run(self, query: str) -> str:
        results = query_references(query, n_results=5)
        if not results:
            return "范文库暂无数据，请先导入参考范文到 references/ 目录。"
        output = "【爆款范文参考片段】\n\n"
        for i, text in enumerate(results, 1):
            output += f"--- 片段 {i} ---\n{text}\n\n"
        return output
