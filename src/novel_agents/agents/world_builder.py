"""世界观师Agent — 负责设定管理、人物卡维护、力量体系、时间线"""

from crewai import Agent

from novel_agents.core.llm_gateway import LLM_ASSIGNMENT
from novel_agents.tools.bible_tool import BibleReaderTool
from novel_agents.tools.chapter_context_tool import ChapterContextTool


def create_world_builder() -> Agent:
    return Agent(
        role="玄幻世界观架构师",
        goal=(
            "维护和扩展故事圣经（bible），确保所有设定的自洽性。"
            "管理人物卡片（性格、修为、法宝、人际关系的动态变化），"
            "维护力量体系的等级平衡，追踪时间线确保因果逻辑。"
        ),
        backstory=(
            "你是一位资深的玄幻修仙世界观架构师，精通各类修仙体系的设计。"
            "无论是传统练气筑基结丹元婴体系，还是独创的功法路线，"
            "你都能确保设定自洽、逻辑严密。"
            "你熟悉各种经典修仙设定：境界划分、宗门势力、法宝灵药、天地法则等。"
            "在创作中，你负责确保新内容与已有设定无矛盾，"
            "同时合理扩展世界观，让设定越来越丰满而不崩坏。"
            "你会在每章结束后更新人物状态、势力关系和时间线。"
        ),
        tools=[BibleReaderTool(), ChapterContextTool()],
        llm=LLM_ASSIGNMENT["world_builder"](),
        verbose=True,
        memory=True,
    )
