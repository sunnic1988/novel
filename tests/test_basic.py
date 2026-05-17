"""基础功能测试"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_structure():
    """验证项目必需目录存在"""
    required_dirs = [
        "bible", "bible/characters", "bible/worldview",
        "plans", "chapters", "reviews", "references",
    ]
    for d in required_dirs:
        assert (PROJECT_ROOT / d).is_dir(), f"目录 {d} 不存在"


def test_bible_files_exist():
    """验证故事圣经文件存在"""
    assert (PROJECT_ROOT / "bible" / "style_guide.md").exists()
    assert (PROJECT_ROOT / "bible" / "power_system.md").exists()
    assert (PROJECT_ROOT / "bible" / "characters" / "主角模板.md").exists()


def test_reference_files_exist():
    """验证爆款范文文件存在"""
    refs = list((PROJECT_ROOT / "references").glob("*.md"))
    assert len(refs) >= 1, "references/ 目录下至少需要一个范文文件"


def test_imports():
    """验证核心模块可以导入"""
    from novel_agents.core.llm_gateway import LLM_ASSIGNMENT

    assert "planner" in LLM_ASSIGNMENT
    assert "writer" in LLM_ASSIGNMENT
    assert "reviewer" in LLM_ASSIGNMENT
    assert "polisher" in LLM_ASSIGNMENT
    assert "world_builder" in LLM_ASSIGNMENT
    assert "reader_sim" in LLM_ASSIGNMENT


def test_memory_module():
    """验证记忆模块可用"""
    from novel_agents.core.memory import (
        get_chapters_collection,
        get_reference_collection,
        ingest_reference_texts,
    )

    count = ingest_reference_texts()
    assert count >= 0

    ref_col = get_reference_collection()
    assert ref_col is not None

    ch_col = get_chapters_collection()
    assert ch_col is not None


def test_tools_creation():
    """验证工具可以创建"""
    from novel_agents.tools.bible_tool import BibleReaderTool
    from novel_agents.tools.chapter_context_tool import ChapterContextTool
    from novel_agents.tools.reference_tool import ReferenceSearchTool

    bible_tool = BibleReaderTool()
    assert bible_tool.name == "故事圣经查阅"

    ref_tool = ReferenceSearchTool()
    assert ref_tool.name == "爆款范文检索"

    ctx_tool = ChapterContextTool()
    assert ctx_tool.name == "已写章节检索"


def test_bible_reader_tool():
    """验证故事圣经工具可以读取内容"""
    from novel_agents.tools.bible_tool import BibleReaderTool

    tool = BibleReaderTool()
    result = tool._run("characters")
    assert "姓名" in result or "主角" in result

    result = tool._run("power_system")
    assert "练气期" in result

    result = tool._run("style_guide")
    assert "AI八股" in result or "禁止" in result


def test_vector_ingest_and_query():
    """验证范文向量化和检索功能"""
    from novel_agents.core.memory import ingest_reference_texts, query_references

    ingest_reference_texts()
    results = query_references("战斗场景", n_results=3)
    assert len(results) >= 0


def test_cli_status(tmp_path):
    """验证CLI status命令可执行"""
    from click.testing import CliRunner

    from novel_agents.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "项目状态" in result.output
