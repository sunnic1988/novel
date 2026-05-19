"""数据模型 — 事件 / Agent 状态 / 运行状态"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentId = Literal[
    "arc_architect",
    "planner",
    "pacing_doctor",
    "world_builder",
    "writer",
    "reviewer",
    "polisher",
    "reader_sim",
    "marketing_specialist",
]

AGENT_ORDER: list[AgentId] = [
    "arc_architect",
    "planner",
    "pacing_doctor",
    "world_builder",
    "writer",
    "reviewer",
    "polisher",
    "reader_sim",
    "marketing_specialist",
]

AGENT_META: dict[AgentId, dict[str, Any]] = {
    "arc_architect": {
        "name": "卷纲架构师",
        "role": "ArcArchitect",
        "color": "#0ea5e9",
        "model_kind": "analytical",
        "uses_references": False,
        "icon": "Layers",
    },
    "planner": {
        "name": "策划师",
        "role": "Planner",
        "color": "#3b82f6",
        "model_kind": "analytical",
        "uses_references": True,
        "icon": "Compass",
    },
    "pacing_doctor": {
        "name": "节奏医生",
        "role": "PacingDoctor",
        "color": "#14b8a6",
        "model_kind": "analytical",
        "uses_references": False,
        "icon": "Activity",
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
    "marketing_specialist": {
        "name": "营销专家",
        "role": "MarketingSpecialist",
        "color": "#f472b6",
        "model_kind": "creative",
        "uses_references": True,
        "icon": "Megaphone",
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
    retry_count: int = 0
    latency_ms: int = 0
    started_at: int | None = None
    completed_at: int | None = None
    output_preview: str = ""
    last_message: str = ""


class RunSummary(BaseModel):
    run_id: str
    script_id: str = "default"
    script_name: str = "默认剧本"
    chapter_num: int
    chapter_title: str
    mode: Literal["live"] = "live"
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
    script_id: str = "default"
    chapter_num: int = 1
    chapter_title: str = ""
    auto_run: bool = True
    step_confirm_mode: bool | None = None
    mode: Literal["live"] = "live"
    synopsis_override: str = ""
    is_opening: bool = False
    best_of_n: int = 1
    enabled_agents: list[str] | None = None  # None 表示全启用
    budget_usd: float | None = None  # 单次 run 的预算上限


class OutlineChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class OutlineChatRequest(BaseModel):
    messages: list[OutlineChatMessage] = Field(default_factory=list)
    chapter_num: int = 1
    script_id: str = "default"


class InterventionRequest(BaseModel):
    edited_output: str
    resume: bool = True


class ReferenceCreateRequest(BaseModel):
    filename: str
    content: str


class ForeshadowingItem(BaseModel):
    id: str | None = None
    title: str
    planted_chapter: int
    planned_payoff_chapter: int | None = None
    payoff_chapter: int | None = None
    status: Literal["planted", "payoff_due", "paid_off", "dropped"] = "planted"
    importance: Literal["high", "medium", "low"] = "medium"
    description: str = ""
    related_characters: list[str] = Field(default_factory=list)
    notes: str = ""


class FeedbackItem(BaseModel):
    chapter: int
    text: str


class TitleCandidate(BaseModel):
    title: str
    angle: str = ""
    score: float = 0.0


class SynopsisRequest(BaseModel):
    text: str


class BudgetCheckRequest(BaseModel):
    budget_usd: float | None = None


class HighlightItem(BaseModel):
    chapter: int
    text: str
    tag: str = ""
    score: float = 0.0


class CharacterRuntimeUpdate(BaseModel):
    name: str
    chapter: int
    realm: str | None = None
    mood: str | None = None
    knot: str | None = None
    key_relations: list[str] = Field(default_factory=list)
    status: str | None = None
    notes: str | None = None
