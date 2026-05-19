"""仪表盘后端 API 基本冒烟测试"""

from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from novel_agents.server import storage_sqlite
from novel_agents.server.app import create_app
from novel_agents.server.models import Event, RunSummary, StartRunRequest, now_ms
from novel_agents.server.runner import _persist_chapter_artifacts, manager


def test_app_boots():
    app = create_app()
    assert app.title == "Novel Agents Dashboard API"
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    for required in [
        "/api/agents",
        "/api/status",
        "/api/scripts",
        "/api/scripts/{script_id}/runs",
        "/api/runs",
        "/api/runs/{run_id}",
        "/api/runs/{run_id}/artifacts",
        "/api/runs/{run_id}/artifacts/{filename}",
        "/api/references",
        "/ws",
    ]:
        assert required in paths, f"missing route: {required}"


def test_scripts_crud_endpoints():
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/scripts")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(it["id"] == "default" for it in items)

    suffix = uuid.uuid4().hex[:8]
    create = client.post("/api/scripts", json={"name": f"测试剧本-{suffix}", "description": "desc"})
    assert create.status_code == 200
    script_id = create.json()["item"]["id"]

    patch = client.patch(f"/api/scripts/{script_id}", json={"name": f"新名-{suffix}"})
    assert patch.status_code == 200
    assert patch.json()["item"]["name"].startswith("新名-")

    runs = client.get(f"/api/scripts/{script_id}/runs")
    assert runs.status_code == 200
    assert isinstance(runs.json()["runs"], list)

    delete = client.delete(f"/api/scripts/{script_id}")
    assert delete.status_code == 200
    assert delete.json()["ok"] is True


def test_event_and_run_written_to_sqlite():
    run_id = f"sqlite-{uuid.uuid4().hex[:8]}"
    run = RunSummary(
        run_id=run_id,
        script_id="default",
        script_name="默认剧本",
        chapter_num=1,
        chapter_title="sqlite",
        mode="live",
        status="running",
        created_at=now_ms(),
        started_at=now_ms(),
        completed_at=None,
        auto_run=True,
        agents=[],
    )

    from novel_agents.server.events import bus

    async def go():
        await bus.publish_run_update(run)
        await bus.publish(
            Event(run_id=run_id, type="agent_started", agent="planner", message="hello")
        )

    asyncio.run(go())

    db_run = storage_sqlite.get_run(run_id)
    assert db_run is not None
    assert db_run.script_id == "default"
    db_events = storage_sqlite.get_events(run_id)
    assert len(db_events) >= 1


def test_create_run_requires_api_key(monkeypatch):
    monkeypatch.delenv("APIMART_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/api/runs",
        json={"chapter_num": 1, "chapter_title": "测试", "mode": "live"},
    )
    assert resp.status_code == 400
    assert "APIMART_API_KEY" in resp.json()["detail"]


def test_persist_chapter_artifacts_from_agent_outputs():
    """流水线完成后，副产物应基于 Agent 真实输出入账。"""
    from novel_agents.book import kpi as kpi_mod
    from novel_agents.book import summaries

    chapter = 9200 + int(uuid.uuid4().hex[:4], 16) % 500
    body = (
        "暮色是化不开的旧墨，一寸寸漫过乱葬岗的碎骨。"
        "陈尘伏在塌掉一半的衣冠冢后，连呼吸都收得极薄。"
        "风里有血腥味。是师兄的。"
    ) * 6

    async def go():
        ctrl = manager.create(
            StartRunRequest(
                chapter_num=chapter,
                chapter_title="试章",
                auto_run=True,
                mode="live",
            )
        )
        ctrl.agent_outputs = {
            "polisher": body,
            "marketing_specialist": "重生第七日，老怪物认我为徒。",
        }
        await _persist_chapter_artifacts(ctrl)

    asyncio.run(go())

    assert summaries.load(chapter)
    k = kpi_mod.load(chapter)
    assert k is not None
    assert k.word_count > 0


def test_ai_taste_endpoint_pure_function():
    from novel_agents.book.ai_taste import analyze

    bad = (
        "然而，他意识到事情没有那么简单。与此同时，他思考着这个问题。"
        "事实上，本章讲述了主角的成长。总之，他需要变得更强。"
        "然而，他突然意识到，他必须立刻行动。然而，他无法逃避。"
    ) * 4
    r1 = analyze(bad)
    assert r1.score > 0.3
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
