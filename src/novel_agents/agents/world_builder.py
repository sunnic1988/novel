"""世界观师Agent — 负责设定管理、人物卡维护、力量体系、时间线"""

from crewai import Agent

from novel_agents.core.llm_gateway import LLM_ASSIGNMENT
from novel_agents.tools.bible_tool import BibleReaderTool
from novel_agents.tools.chapter_context_tool import ChapterContextTool


def create_world_builder() -> Agent:
    return Agent(
        role="修仙世界观架构师",
        goal=(
            "维护和扩展故事圣经（bible），确保所有设定的自洽性。"
            "管理人物卡片（性格、修为、法宝、人际关系的动态变化），"
            "维护力量体系的等级平衡，追踪时间线确保因果逻辑。"
        ),
        backstory=(
            "你是《凡人修仙传》的资深研究者，对忘语构建的修仙世界了如指掌。"
            "你熟知每一个境界的突破条件、每一种灵药法宝的设定、"
            "每一个门派势力的渊源关系。在二创中，你负责确保新创内容"
            "既尊重原作设定，又能合理扩展，不产生设定冲突。"
            "你会在每章结束后更新人物状态、势力关系和时间线。"
        ),
        tools=[BibleReaderTool(), ChapterContextTool()],
        llm=LLM_ASSIGNMENT["world_builder"](),
        verbose=True,
        memory=True,
    )
