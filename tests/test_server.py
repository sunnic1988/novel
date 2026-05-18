"""仪表盘后端 API 基本冒烟测试"""

from __future__ import annotations

import asyncio

from novel_agents.server.app import create_app
from novel_agents.server.models import StartRunRequest
from novel_agents.server.runner import manager


def test_app_boots():
    app = create_app()
    assert app.title == "Novel Agents Dashboard API"
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    for required in [
        "/api/agents",
        "/api/status",
        "/api/runs",
        "/api/runs/{run_id}",
        "/api/references",
        "/ws",
    ]:
        assert required in paths, f"missing route: {required}"


def test_mock_run_executes_all_nine_agents():
    """模拟模式下 9 个 Agent 全部产生 token & 工具调用事件 + 章节副产物入账"""
    from novel_agents.server.events import bus

    async def go():
        ctrl = manager.create(
            StartRunRequest(
                chapter_num=99,
                chapter_title="测试章节",
                auto_run=True,
                mode="mock",
            )
        )
        await manager.start(ctrl, StartRunRequest(chapter_num=99, mode="mock"))
        assert ctrl.task is not None
        await ctrl.task
        return ctrl

    ctrl = asyncio.run(go())
    run = ctrl.run
    assert run.status == "completed", f"unexpected: {run.status}"
    assert run.total_tokens > 0
    assert run.total_llm_calls > 0

    agent_ids = {a.id for a in run.agents}
    assert agent_ids == {
        "arc_architect",
        "planner",
        "pacing_doctor",
        "world_builder",
        "writer",
        "reviewer",
        "polisher",
        "reader_sim",
        "marketing_specialist",
    }
    for a in run.agents:
        assert a.status == "done"
        assert a.total_tokens > 0, f"{a.id} has no tokens"
        assert a.llm_calls > 0
        if a.uses_references:
            assert a.tool_calls >= 1, f"{a.id} 应至少调用 1 次工具"

    events = bus.get_events(run.run_id)
    types = {e.type for e in events}
    assert {"run_started", "run_completed", "agent_started", "agent_completed"} <= types
    assert "agent_llm_call" in types
    assert "agent_tool_call" in types
    assert "cost_estimate" in types
    assert "artifact_saved" in types


def test_mock_run_persists_chapter_artifacts(tmp_path, monkeypatch):
    """mock run 完成后应产出 KPI / 摘要 / 标题 / 金句 / 伏笔 / runtime"""
    from novel_agents.book import (
        character_runtime,
        foreshadowing,
        highlights,
        summaries,
    )
    from novel_agents.book import (
        kpi as kpi_mod,
    )
    from novel_agents.book import (
        titles as titles_mod,
    )

    async def go():
        ctrl = manager.create(
            StartRunRequest(
                chapter_num=42,  # 使用一个不太可能与其它测试冲突的章节号
                chapter_title="测试副产物",
                auto_run=True,
                mode="mock",
                is_opening=False,
                best_of_n=1,
            )
        )
        await manager.start(ctrl, StartRunRequest(chapter_num=42, mode="mock"))
        await ctrl.task
        return ctrl

    ctrl = asyncio.run(go())
    assert ctrl.run.status == "completed"

    # KPI
    k = kpi_mod.load(42)
    assert k is not None
    assert 0 <= k.ai_taste_score <= 1
    assert k.retention_score > 0
    # Summary
    assert summaries.load(42)
    # Titles
    cands = titles_mod.load_titles(42)
    assert len(cands) == 5
    # Highlights
    hl = highlights.list_for(42)
    assert len(hl) >= 2
    # Foreshadowing
    items = foreshadowing.list_items()
    assert any(it.get("planted_chapter") == 42 for it in items)
    # Character runtime
    all_chars = character_runtime.list_all()
    assert any(c.get("name") == "陈尘" for c in all_chars)


def test_best_of_n_and_disabled_agent():
    """best_of_n + 禁用 Agent 都能正常工作"""

    async def go():
        ctrl = manager.create(
            StartRunRequest(
                chapter_num=88,
                mode="mock",
                best_of_n=3,
                enabled_agents=[
                    "arc_architect",
                    "planner",
                    "pacing_doctor",
                    "world_builder",
                    "writer",
                    "reviewer",
                    "polisher",
                    "reader_sim",
                ],  # 禁用 marketing
                budget_usd=0.0001,  # 故意低，触发预警
            )
        )
        await manager.start(ctrl, StartRunRequest(chapter_num=88, mode="mock"))
        await ctrl.task
        return ctrl

    ctrl = asyncio.run(go())
    run = ctrl.run
    assert run.status == "completed"
    marketing = next(a for a in run.agents if a.id == "marketing_specialist")
    assert marketing.status == "skipped"
    writer = next(a for a in run.agents if a.id == "writer")
    # best_of_n=3 应该让 writer 的 token 量明显高于 reviewer
    reviewer = next(a for a in run.agents if a.id == "reviewer")
    assert writer.total_tokens > reviewer.total_tokens

    # 检查预算告警事件
    from novel_agents.server.events import bus

    events = bus.get_events(run.run_id)
    assert any(e.type == "cost_warning" for e in events)


def test_ai_taste_endpoint_pure_function():
    from novel_agents.book.ai_taste import analyze

    # 强 AI 味文本
    bad = (
        "然而，他意识到事情没有那么简单。与此同时，他思考着这个问题。"
        "事实上，本章讲述了主角的成长。总之，他需要变得更强。"
        "然而，他突然意识到，他必须立刻行动。然而，他无法逃避。"
    ) * 4
    r1 = analyze(bad)
    assert r1.score > 0.3
    # 正常文本
    good = (
        "暮色是化不开的旧墨，一寸寸漫过乱葬岗的碎骨。"
        "陈尘伏在塌掉一半的衣冠冢后，连呼吸都收得极薄。"
        "风里有血腥味。是师兄的。"
        "脚步在三丈外停住。"
        "『交出来——留你全尸。』"
        "陈尘忽然笑了。笑里有泪。也有别的，比泪更烫的东西。"
    ) * 4
    r2 = analyze(good)
    assert r2.score < r1.score


def test_reference_endpoints_exist():
    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/references/ingest" in paths
    assert "/api/references/search" in paths
    assert "/api/references/upload" in paths
