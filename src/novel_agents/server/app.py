"""FastAPI 应用 — 为前端仪表盘提供 REST + WebSocket 接口"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from novel_agents.server.events import bus
from novel_agents.server.models import (
    AGENT_META,
    AGENT_ORDER,
    InterventionRequest,
    ReferenceCreateRequest,
    StartRunRequest,
)
from novel_agents.server.runner import manager

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REFERENCES_DIR = PROJECT_ROOT / "references"


def create_app() -> FastAPI:
    app = FastAPI(title="Novel Agents Dashboard API", version="0.1.0")

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

    # ── WebSocket ─────────────────────────────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        q = bus.subscribe()
        # 推送初始快照
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
                    # heartbeat
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
                "endpoints": {
                    "agents": "/api/agents",
                    "status": "/api/status",
                    "runs": "/api/runs",
                    "references": "/api/references",
                    "ws": "/ws",
                },
            }
        )

    return app


def _safe_filename(name: str, default_ext: str = ".md") -> str:
    base = Path(name).name.strip() or "untitled"
    # 仅保留扩展名 .md / .txt
    suffix = Path(base).suffix.lower()
    if suffix not in (".md", ".txt"):
        base = base + default_ext
    return base
