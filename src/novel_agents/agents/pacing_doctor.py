"""节奏医生 / 爽点调度器

负责的事：
1. 读取近 10 章 KPI（爽点强度、钩子强度、节奏分），输出爽点能量曲线
2. 判断本章应该是「铺垫章/小爽章/大爽章/转折章/危机章」中的哪一类
3. 给 Writer 输出明确的节奏 prompt：本章预期爽点强度 X/10、需要至少 N 个金句、章末钩子等级 Y
4. 监控金手指使用频率，避免过早/过强透支
"""

from crewai import Agent

from novel_agents.core.llm_gateway import LLM_ASSIGNMENT
from novel_agents.tools.chapter_context_tool import ChapterContextTool


def create_pacing_doctor() -> Agent:
    return Agent(
        role="网文节奏医生",
        goal=(
            "维持长线连载的爽点节奏曲线 — 每章至少 1 个小爽点，"
            "每 5 章一个大爽点，每 20 章一个里程碑爽点。"
            "调度金手指强度按对数曲线递增，避免前期透支后期无牌可打。"
            "为本章给出明确的节奏处方：'本章节奏目标=铺垫/小爽/大爽/转折/危机'，"
            "预期爽点强度 X/10、金句目标数、章末钩子等级。"
        ),
        backstory=(
            "你是一位最懂'网文爽点经济学'的资深责编。"
            "你深信：'读者的兴奋阈值会指数级上升，爽点强度必须跟上但不能过早登顶。'"
            "你最讨厌的两种问题：一是连续 3 章铺垫不爽点（读者弃书），"
            "二是早期就把'灭门血仇/绝世传承/无敌战力'全亮出来（后期无牌可打）。"
            "你的处方总是结构化的：节奏类型 + 爽点目标分 + 钩子等级 + 金句数量 + 金手指使用建议。"
        ),
        tools=[ChapterContextTool()],
        llm=LLM_ASSIGNMENT["reviewer"](),
        verbose=True,
        memory=True,
        max_iter=3,
    )
