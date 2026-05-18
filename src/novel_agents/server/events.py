"""事件总线 — 异步 pub/sub，向所有连接的 WebSocket 客户端广播 Agent 执行事件"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from novel_agents.book.paths import traces_dir, use_script
from novel_agents.server.models import Event, RunSummary
from novel_agents.server import storage_sqlite

class EventBus:
    """支持全局订阅 + 按 run_id 订阅 + 持久化到 .traces/<run_id>.jsonl"""

    def __init__(self) -> None:
        storage_sqlite.init_db()
        self._global_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._run_events: dict[str, list[Event]] = defaultdict(list)
        self._runs: dict[str, RunSummary] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        async with self._lock:
            self._run_events[event.run_id].append(event)
            payload = {"kind": "event", "event": event.model_dump()}
            self._persist(event)
            storage_sqlite.append_event(event)
            for q in list(self._global_subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    async def publish_run_update(self, run: RunSummary) -> None:
        async with self._lock:
            self._runs[run.run_id] = run
            storage_sqlite.upsert_run(run)
            payload = {"kind": "run_update", "run": run.model_dump()}
            for q in list(self._global_subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    def _persist(self, event: Event) -> None:
        try:
            run = self._runs.get(event.run_id) or storage_sqlite.get_run(event.run_id)
            script_id = run.script_id if run else "default"
            with use_script(script_id):
                trace_root = traces_dir()
                trace_root.mkdir(parents=True, exist_ok=True)
                fp = trace_root / f"{event.run_id}.jsonl"
            with fp.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")
        except Exception:
            # Persistence failures shouldn't break the stream.
            pass

    def subscribe(self, maxsize: int = 1024) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self._global_subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._global_subscribers.discard(q)

    def get_run(self, run_id: str) -> RunSummary | None:
        run = self._runs.get(run_id)
        if run:
            return run
        return storage_sqlite.get_run(run_id)

    def list_runs(self, script_id: str | None = None) -> list[RunSummary]:
        runs = storage_sqlite.list_runs(script_id=script_id)
        if runs:
            return runs
        local = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
        if script_id:
            return [r for r in local if r.script_id == script_id]
        return local

    def get_events(self, run_id: str, limit: int = 5000, offset: int = 0) -> list[Event]:
        events = storage_sqlite.get_events(run_id=run_id, limit=limit, offset=offset)
        if events:
            return events
        return list(self._run_events.get(run_id, []))

    def upsert_run(self, run: RunSummary) -> None:
        self._runs[run.run_id] = run
        storage_sqlite.upsert_run(run)


bus = EventBus()
