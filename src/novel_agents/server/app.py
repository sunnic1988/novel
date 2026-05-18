"""FastAPI 应用 — 为前端仪表盘提供 REST + WebSocket 接口"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from novel_agents.book import (
    character_runtime,
    foreshadowing,
    highlights,
    summaries,
)
from novel_agents.book import (
    cost as cost_mod,
)
from novel_agents.book import (
    feedback as feedback_mod,
)
from novel_agents.book import (
    kpi as kpi_mod,
)
from novel_agents.book import (
    stats as stats_mod,
)
from novel_agents.book import (
    titles as titles_mod,
)
from novel_agents.book.ai_taste import analyze as ai_taste_analyze
from novel_agents.book.paths import ARCS_DIR, ensure_dirs
from novel_agents.server.events import bus
from novel_agents.server.models import (
    AGENT_META,
    AGENT_ORDER,
    BudgetCheckRequest,
    CharacterRuntimeUpdate,
    FeedbackItem,
    ForeshadowingItem,
    HighlightItem,
    InterventionRequest,
    ReferenceCreateRequest,
    StartRunRequest,
    SynopsisRequest,
)
from novel_agents.server.runner import manager

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REFERENCES_DIR = PROJECT_ROOT / "references"


def create_app() -> FastAPI:
    app = FastAPI(title="Novel Agents Dashboard API", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 元数据 ────────────────────────────────────────────────
    @app.get("/api/agents")
    def list_agent_definitions() -> dict[str, Any]:
        return {
            "agents": [
                {
                    "id": aid,
                    **AGENT_META[aid],
                    "model": (
                        "claude-sonnet-4-6"
                        if AGENT_META[aid]["model_kind"] == "creative"
                        else "deepseek-v4-pro"
                    ),
                }
                for aid in AGENT_ORDER
            ],
            "pipeline_order": AGENT_ORDER,
        }

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        import os

        chapters_dir = PROJECT_ROOT / "chapters"
        chapters_count = (
            len(list(chapters_dir.glob("ch*.md"))) if chapters_dir.exists() else 0
        )
        refs = (
            list(REFERENCES_DIR.glob("*.md")) + list(REFERENCES_DIR.glob("*.txt"))
            if REFERENCES_DIR.exists()
            else []
        )
        ref_vec, ch_vec = 0, 0
        try:
            from novel_agents.core.memory import (
                get_chapters_collection,
                get_reference_collection,
            )

            ref_vec = get_reference_collection().count()
            ch_vec = get_chapters_collection().count()
        except Exception:
            pass
        return {
            "chapters_count": chapters_count,
            "references_count": len(refs),
            "reference_chunks": ref_vec,
            "chapter_chunks": ch_vec,
            "has_api_key": bool(os.getenv("APIMART_API_KEY")),
            "default_mode": "live" if os.getenv("APIMART_API_KEY") else "mock",
        }

    # ── Runs ──────────────────────────────────────────────────
    @app.post("/api/runs")
    async def create_run(req: StartRunRequest) -> dict[str, Any]:
        import os

        if req.mode == "live" and not os.getenv("APIMART_API_KEY"):
            req.mode = "mock"
        ctrl = manager.create(req)
        await manager.start(ctrl, req)
        return {"run_id": ctrl.run.run_id, "run": ctrl.run.model_dump()}

    @app.post("/api/runs/cost-estimate")
    def cost_estimate(req: StartRunRequest) -> dict[str, Any]:
        enabled = (
            set(req.enabled_agents) if req.enabled_agents else set(AGENT_ORDER)
        )
        models = {
            aid: (
                "claude-sonnet-4-6"
                if AGENT_META[aid]["model_kind"] == "creative"
                else "deepseek-v4-pro"
            )
            for aid in AGENT_ORDER
            if aid in enabled
        }
        return cost_mod.estimate_chapter_cost(
            models,
            enabled=enabled,
            best_of_n=max(1, min(req.best_of_n, 5)),
        )

    @app.get("/api/runs")
    def list_runs() -> dict[str, Any]:
        runs = bus.list_runs()
        return {"runs": [r.model_dump() for r in runs]}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = bus.get_run(run_id)
        if not run:
            raise HTTPException(404, "run not found")
        return run.model_dump()

    @app.get("/api/runs/{run_id}/events")
    def get_events(run_id: str) -> dict[str, Any]:
        events = bus.get_events(run_id)
        return {"events": [e.model_dump() for e in events]}

    @app.post("/api/runs/{run_id}/pause")
    async def pause_run(run_id: str) -> dict[str, Any]:
        ctrl = manager.get(run_id)
        if not ctrl:
            raise HTTPException(404, "run not found")
        ctrl.pause()
        await bus.publish_run_update(ctrl.run)
        return {"ok": True, "status": ctrl.run.status}

    @app.post("/api/runs/{run_id}/resume")
    async def resume_run(run_id: str) -> dict[str, Any]:
        ctrl = manager.get(run_id)
        if not ctrl:
            raise HTTPException(404, "run not found")
        ctrl.resume()
        await bus.publish_run_update(ctrl.run)
        return {"ok": True, "status": ctrl.run.status}

    @app.post("/api/runs/{run_id}/abort")
    async def abort_run(run_id: str) -> dict[str, Any]:
        ctrl = manager.get(run_id)
        if not ctrl:
            raise HTTPException(404, "run not found")
        ctrl.abort()
        await bus.publish_run_update(ctrl.run)
        return {"ok": True}

    @app.post("/api/runs/{run_id}/agents/{agent_id}/intervene")
    async def intervene(
        run_id: str, agent_id: str, req: InterventionRequest
    ) -> dict[str, Any]:
        ok = await manager.apply_intervention(
            run_id, agent_id, req.edited_output, req.resume
        )
        if not ok:
            raise HTTPException(404, "run not found")
        return {"ok": True}

    # ── References (爆款范文) ─────────────────────────────────
    @app.get("/api/references")
    def list_references() -> dict[str, Any]:
        REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(
            list(REFERENCES_DIR.glob("*.md")) + list(REFERENCES_DIR.glob("*.txt"))
        )
        items = []
        for f in files:
            try:
                stat = f.stat()
                content = f.read_text(encoding="utf-8", errors="replace")
                items.append(
                    {
                        "name": f.name,
                        "size": stat.st_size,
                        "modified": int(stat.st_mtime * 1000),
                        "preview": content[:200],
                        "char_count": len(content),
                    }
                )
            except Exception:
                continue
        return {"items": items}

    @app.post("/api/references")
    async def create_reference(req: ReferenceCreateRequest) -> dict[str, Any]:
        REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
        name = _safe_filename(req.filename, default_ext=".md")
        target = REFERENCES_DIR / name
        target.write_text(req.content, encoding="utf-8")
        return {"ok": True, "name": name, "size": len(req.content)}

    @app.post("/api/references/upload")
    async def upload_reference(file: UploadFile) -> dict[str, Any]:
        REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
        name = _safe_filename(file.filename or "untitled.md", default_ext=".md")
        target = REFERENCES_DIR / name
        content = (await file.read()).decode("utf-8", errors="replace")
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "name": name, "size": len(content)}

    @app.delete("/api/references/{name}")
    def delete_reference(name: str) -> dict[str, Any]:
        safe_name = _safe_filename(name, default_ext=".md")
        target = REFERENCES_DIR / safe_name
        if not target.exists():
            raise HTTPException(404, "reference not found")
        target.unlink()
        return {"ok": True}

    @app.post("/api/references/ingest")
    def ingest_references() -> dict[str, Any]:
        try:
            from novel_agents.core.memory import (
                get_reference_collection,
                ingest_reference_texts,
            )

            added = ingest_reference_texts()
            total = get_reference_collection().count()
            return {"ok": True, "added_chunks": added, "total_chunks": total}
        except Exception as exc:
            raise HTTPException(500, f"ingest failed: {exc}") from exc

    @app.get("/api/references/search")
    def search_references(q: str, n: int = 5) -> dict[str, Any]:
        try:
            from novel_agents.core.memory import query_references

            results = query_references(q, n)
            return {"results": results}
        except Exception as exc:
            raise HTTPException(500, f"search failed: {exc}") from exc

    # ── 本书数据看板 ──────────────────────────────────────────
    @app.get("/api/book/dashboard")
    def book_dashboard() -> dict[str, Any]:
        ensure_dirs()
        return stats_mod.book_dashboard()

    @app.get("/api/book/kpi/trends")
    def book_kpi_trends() -> dict[str, Any]:
        return stats_mod.kpi_trends()

    @app.get("/api/book/runs")
    def book_runs() -> dict[str, Any]:
        return stats_mod.runs_aggregate()

    @app.get("/api/book/pricing")
    def book_pricing() -> dict[str, Any]:
        return {"pricing": stats_mod.pricing_table()}

    @app.post("/api/book/cost-alerts")
    def book_cost_alerts(req: BudgetCheckRequest) -> dict[str, Any]:
        return stats_mod.cost_alerts(req.budget_usd)

    # ── 伏笔账本 ──────────────────────────────────────────────
    @app.get("/api/foreshadowing")
    def list_foreshadowing(current_chapter: int | None = None) -> dict[str, Any]:
        items = foreshadowing.list_items()
        return {
            "items": items,
            "stats": foreshadowing.stats(current_chapter),
        }

    @app.post("/api/foreshadowing")
    def upsert_foreshadowing(item: ForeshadowingItem) -> dict[str, Any]:
        return foreshadowing.upsert(item.model_dump(exclude_none=True))

    @app.delete("/api/foreshadowing/{item_id}")
    def delete_foreshadowing(item_id: str) -> dict[str, Any]:
        ok = foreshadowing.delete(item_id)
        if not ok:
            raise HTTPException(404, "foreshadowing item not found")
        return {"ok": True}

    # ── 金句库 ─────────────────────────────────────────────────
    @app.get("/api/highlights")
    def list_highlights() -> dict[str, Any]:
        items = highlights.load_all()
        return {
            "items": [
                {"chapter": h.chapter, "text": h.text, "tag": h.tag, "score": h.score}
                for h in items
            ],
            "stats": highlights.stats(),
        }

    @app.post("/api/highlights")
    def add_highlight(req: HighlightItem) -> dict[str, Any]:
        h = highlights.add(req.chapter, req.text, req.tag, req.score)
        return {"chapter": h.chapter, "text": h.text, "tag": h.tag, "score": h.score}

    # ── 角色 runtime ───────────────────────────────────────────
    @app.get("/api/characters/runtime")
    def list_character_runtime() -> dict[str, Any]:
        return {"items": character_runtime.list_all()}

    @app.post("/api/characters/runtime")
    def update_character_runtime(req: CharacterRuntimeUpdate) -> dict[str, Any]:
        snap = req.model_dump(exclude={"name", "chapter"}, exclude_none=True)
        data = character_runtime.append_snapshot(req.name, req.chapter, snap)
        return data

    # ── KPI ───────────────────────────────────────────────────
    @app.get("/api/kpi/{chapter}")
    def get_kpi(chapter: int) -> dict[str, Any]:
        k = kpi_mod.load(chapter)
        if not k:
            raise HTTPException(404, "kpi not found")
        return k.to_dict()

    @app.get("/api/kpi")
    def list_kpi() -> dict[str, Any]:
        return {
            "items": [k.to_dict() for k in kpi_mod.list_all()],
            "book_summary": kpi_mod.book_summary(),
        }

    # ── 章节摘要 ───────────────────────────────────────────────
    @app.get("/api/summaries/{chapter}")
    def get_summary(chapter: int) -> dict[str, Any]:
        text = summaries.load(chapter)
        if not text:
            raise HTTPException(404, "summary not found")
        return {"chapter": chapter, "text": text}

    @app.get("/api/summaries")
    def list_summaries() -> dict[str, Any]:
        all_summaries = summaries.list_range(1, 1000)
        return {
            "items": [{"chapter": n, "text": t} for n, t in all_summaries],
            "count": len(all_summaries),
        }

    # ── 读者反馈 ───────────────────────────────────────────────
    @app.get("/api/feedback")
    def list_feedback() -> dict[str, Any]:
        return {"items": feedback_mod.list_all()}

    @app.post("/api/feedback")
    def upsert_feedback(item: FeedbackItem) -> dict[str, Any]:
        feedback_mod.save(item.chapter, item.text)
        return {"ok": True, "chapter": item.chapter}

    # ── 营销：标题 / 简介 ─────────────────────────────────────
    @app.get("/api/marketing/titles/{chapter}")
    def get_titles(chapter: int) -> dict[str, Any]:
        return {"chapter": chapter, "candidates": titles_mod.load_titles(chapter)}

    @app.get("/api/marketing/synopsis")
    def get_marketing_synopsis() -> dict[str, Any]:
        return {"text": titles_mod.load_synopsis()}

    @app.post("/api/marketing/synopsis")
    def set_marketing_synopsis(req: SynopsisRequest) -> dict[str, Any]:
        titles_mod.save_synopsis(req.text)
        return {"ok": True, "chars": len(req.text)}

    # ── 卷纲（arcs） ───────────────────────────────────────────
    @app.get("/api/arcs")
    def list_arcs() -> dict[str, Any]:
        ensure_dirs()
        items = []
        for f in sorted(ARCS_DIR.glob("arc_*.md")):
            stem = f.stem.replace("arc_", "")
            try:
                idx = int(stem)
            except ValueError:
                idx = 0
            items.append(
                {
                    "index": idx,
                    "name": f.name,
                    "text": f.read_text(encoding="utf-8"),
                }
            )
        return {"items": items}

    @app.post("/api/arcs/{index}")
    def upsert_arc(index: int, body: dict[str, Any]) -> dict[str, Any]:
        ensure_dirs()
        from novel_agents.book.paths import arc_path

        p = arc_path(index)
        p.write_text(body.get("text", ""), encoding="utf-8")
        return {"ok": True, "name": p.name}

    # ── AI 味在线检测（任意文本） ─────────────────────────────
    @app.post("/api/ai-taste/analyze")
    def analyze_ai_taste(body: dict[str, Any]) -> dict[str, Any]:
        text = body.get("text", "")
        return ai_taste_analyze(text).to_dict()

    # ── WebSocket ─────────────────────────────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        q = bus.subscribe()
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "kind": "snapshot",
                        "runs": [r.model_dump() for r in bus.list_runs()],
                    },
                    ensure_ascii=False,
                )
            )
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                except asyncio.TimeoutError:
                    await websocket.send_text(json.dumps({"kind": "ping"}))
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            bus.unsubscribe(q)

    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "name": "Novel Agents Dashboard API",
                "version": "0.2.0",
                "endpoints": {
                    "agents": "/api/agents",
                    "status": "/api/status",
                    "runs": "/api/runs",
                    "references": "/api/references",
                    "book": "/api/book/dashboard",
                    "foreshadowing": "/api/foreshadowing",
                    "highlights": "/api/highlights",
                    "characters_runtime": "/api/characters/runtime",
                    "marketing_titles": "/api/marketing/titles/{chapter}",
                    "marketing_synopsis": "/api/marketing/synopsis",
                    "ai_taste": "/api/ai-taste/analyze",
                    "ws": "/ws",
                },
            }
        )

    return app


def _safe_filename(name: str, default_ext: str = ".md") -> str:
    base = Path(name).name.strip() or "untitled"
    suffix = Path(base).suffix.lower()
    if suffix not in (".md", ".txt"):
        base = base + default_ext
    return base
