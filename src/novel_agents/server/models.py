"""数据模型 — 事件 / Agent 状态 / 运行状态"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentId = Literal[
    "planner",
    "world_builder",
    "writer",
    "reviewer",
    "polisher",
    "reader_sim",
]

AGENT_ORDER: list[AgentId] = [
    "planner",
    "world_builder",
    "writer",
    "reviewer",
    "polisher",
    "reader_sim",
]

AGENT_META: dict[AgentId, dict[str, Any]] = {
    "planner": {
        "name": "策划师",
        "role": "Planner",
        "color": "#3b82f6",
        "model_kind": "analytical",
        "uses_references": True,
        "icon": "Compass",
    },
    "world_builder": {
        "name": "世界观师",
        "role": "WorldBuilder",
        "color": "#06b6d4",
        "model_kind": "analytical",
        "uses_references": False,
        "icon": "Globe",
    },
    "writer": {
        "name": "写手",
        "role": "Writer",
        "color": "#0ea5e9",
        "model_kind": "creative",
        "uses_references": True,
        "icon": "PenLine",
    },
    "reviewer": {
        "name": "审校师",
        "role": "Reviewer",
        "color": "#6366f1",
        "model_kind": "analytical",
        "uses_references": False,
        "icon": "ShieldCheck",
    },
    "polisher": {
        "name": "润色师",
        "role": "Polisher",
        "color": "#22d3ee",
        "model_kind": "creative",
        "uses_references": True,
        "icon": "Sparkles",
    },
    "reader_sim": {
        "name": "读者模拟",
        "role": "ReaderSim",
        "color": "#8b5cf6",
        "model_kind": "analytical",
        "uses_references": False,
        "icon": "Users",
    },
}


def now_ms() -> int:
    return int(time.time() * 1000)


class AgentStatus(BaseModel):
    id: str
    name: str
    role: str
    color: str
    icon: str
    model: str = ""
    model_kind: str = ""
    uses_references: bool = False
    status: Literal[
        "idle", "queued", "running", "awaiting_intervention", "done", "error", "skipped"
    ] = "idle"
    progress: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    latency_ms: int = 0
    started_at: int | None = None
    completed_at: int | None = None
    output_preview: str = ""
    last_message: str = ""


class RunSummary(BaseModel):
    run_id: str
    chapter_num: int
    chapter_title: str
    mode: Literal["live", "mock"] = "mock"
    status: Literal["queued", "running", "paused", "completed", "aborted", "error"] = "queued"
    auto_run: bool = True
    created_at: int = Field(default_factory=now_ms)
    started_at: int | None = None
    completed_at: int | None = None
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_llm_calls: int = 0
    agents: list[AgentStatus] = Field(default_factory=list)
    paused_at_agent: str | None = None


class Event(BaseModel):
    """所有 Agent 执行过程的留痕事件"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str
    ts: int = Field(default_factory=now_ms)
    type: str
    agent: str | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class StartRunRequest(BaseModel):
    chapter_num: int = 1
    chapter_title: str = ""
    auto_run: bool = True
    mode: Literal["live", "mock"] = "mock"
    synopsis_override: str = ""


class InterventionRequest(BaseModel):
    edited_output: str
    resume: bool = True


class ReferenceCreateRequest(BaseModel):
    filename: str
    content: str
