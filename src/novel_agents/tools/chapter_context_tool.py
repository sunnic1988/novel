"""已写章节上下文检索工具 — 保证前后文连贯性"""

from crewai.tools import BaseTool

from novel_agents.core.memory import query_chapters


class ChapterContextTool(BaseTool):
    name: str = "已写章节检索"
    description: str = (
        "从已完成的章节中检索相关内容，确保新章节与前文保持人物、情节、设定的连贯性。"
        "输入角色名、事件描述或关键词。"
    )

    def _run(self, query: str) -> str:
        results = query_chapters(query, n_results=5)
        if not results:
            return "当前尚无已完成章节。"
        output = "【已写章节相关段落】\n\n"
        for i, text in enumerate(results, 1):
            output += f"--- 段落 {i} ---\n{text}\n\n"
        return output
