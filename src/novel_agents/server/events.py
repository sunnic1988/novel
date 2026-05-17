"""事件总线 — 异步 pub/sub，向所有连接的 WebSocket 客户端广播 Agent 执行事件"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from novel_agents.server.models import Event, RunSummary

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRACE_DIR = PROJECT_ROOT / ".traces"


class EventBus:
    """支持全局订阅 + 按 run_id 订阅 + 持久化到 .traces/<run_id>.jsonl"""

    def __init__(self) -> None:
        self._global_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._run_events: dict[str, list[Event]] = defaultdict(list)
        self._runs: dict[str, RunSummary] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        async with self._lock:
            self._run_events[event.run_id].append(event)
            payload = {"kind": "event", "event": event.model_dump()}
            self._persist(event)
            for q in list(self._global_subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    async def publish_run_update(self, run: RunSummary) -> None:
        async with self._lock:
            self._runs[run.run_id] = run
            payload = {"kind": "run_update", "run": run.model_dump()}
            for q in list(self._global_subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    def _persist(self, event: Event) -> None:
        try:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            fp = TRACE_DIR / f"{event.run_id}.jsonl"
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
        return self._runs.get(run_id)

    def list_runs(self) -> list[RunSummary]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)

    def get_events(self, run_id: str) -> list[Event]:
        return list(self._run_events.get(run_id, []))

    def upsert_run(self, run: RunSummary) -> None:
        self._runs[run.run_id] = run


bus = EventBus()
