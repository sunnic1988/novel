"""仪表盘后端 API 基本冒烟测试"""

from __future__ import annotations

import asyncio

import pytest

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


def test_mock_run_executes_all_six_agents():
    """模拟模式下 6 个 Agent 全部产生 token & 工具调用事件"""
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
        "planner",
        "world_builder",
        "writer",
        "reviewer",
        "polisher",
        "reader_sim",
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


def test_reference_endpoints_exist():
    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/references/ingest" in paths
    assert "/api/references/search" in paths
    assert "/api/references/upload" in paths
