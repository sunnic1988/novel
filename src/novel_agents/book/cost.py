"""Token → 成本估算

价格以 USD / 1M token 计算，按 APIMart 的实际计费档位保守估计。
若用户/未来需要校准，只需修改 PRICING。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# USD per 1M tokens — input / output
PRICING: dict[str, tuple[float, float]] = {
    # 创意模型（写作 / 润色）
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    # 分析模型
    "deepseek-v4-pro": (0.5, 1.5),
    "deepseek-v3-pro": (0.27, 1.10),
    # 默认兜底
    "default-creative": (3.0, 15.0),
    "default-analytical": (0.5, 1.5),
}


def price_for_model(model: str) -> tuple[float, float]:
    """返回 (input_per_1M, output_per_1M) — USD"""
    if model in PRICING:
        return PRICING[model]
    m = model.lower()
    if "claude" in m or "sonnet" in m or "opus" in m:
        return PRICING["default-creative"]
    if "deepseek" in m or "qwen" in m or "glm" in m:
        return PRICING["default-analytical"]
    return PRICING["default-analytical"]


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_in, p_out = price_for_model(model)
    return (prompt_tokens * p_in + completion_tokens * p_out) / 1_000_000


@dataclass
class AgentBudget:
    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# 单章典型 token 用量（基于 prompt + 文风指南 + 上下文）
TYPICAL_AGENT_BUDGET: dict[str, dict[str, int]] = {
    "arc_architect": {"prompt": 4500, "completion": 1800},
    "planner": {"prompt": 4500, "completion": 2200},
    "pacing_doctor": {"prompt": 2200, "completion": 1000},
    "world_builder": {"prompt": 4000, "completion": 1500},
    "writer": {"prompt": 6000, "completion": 4500},
    "reviewer": {"prompt": 5500, "completion": 2200},
    "polisher": {"prompt": 6500, "completion": 4500},
    "reader_sim": {"prompt": 4000, "completion": 1500},
    "marketing_specialist": {"prompt": 1800, "completion": 1200},
}


def estimate_chapter_cost(
    agent_models: dict[str, str],
    enabled: Iterable[str] | None = None,
    best_of_n: int = 1,
) -> dict[str, object]:
    """估算一章的总成本和分 Agent 成本。

    agent_models : 每个 agent 名 → 实际模型名
    enabled      : 启用的 agent 列表（默认全部）
    best_of_n    : Writer 并行尝试次数（成本翻 N 倍）
    """
    enabled_set = set(enabled) if enabled is not None else set(agent_models.keys())
    breakdown: list[AgentBudget] = []
    total_in = 0
    total_out = 0
    total_usd = 0.0
    for agent, model in agent_models.items():
        if agent not in enabled_set:
            continue
        bud = TYPICAL_AGENT_BUDGET.get(agent, {"prompt": 3000, "completion": 1500})
        p, c = bud["prompt"], bud["completion"]
        if agent == "writer" and best_of_n > 1:
            p *= best_of_n
            c *= best_of_n
        cost = estimate_cost(model, p, c)
        breakdown.append(
            AgentBudget(
                agent=agent,
                model=model,
                prompt_tokens=p,
                completion_tokens=c,
                cost_usd=cost,
            )
        )
        total_in += p
        total_out += c
        total_usd += cost
    return {
        "total_cost_usd": round(total_usd, 4),
        "total_prompt_tokens": total_in,
        "total_completion_tokens": total_out,
        "total_tokens": total_in + total_out,
        "best_of_n": best_of_n,
        "breakdown": [
            {
                "agent": b.agent,
                "model": b.model,
                "prompt_tokens": b.prompt_tokens,
                "completion_tokens": b.completion_tokens,
                "cost_usd": round(b.cost_usd, 4),
            }
            for b in breakdown
        ],
    }


def usage_to_cost(usage_by_agent: dict[str, dict[str, object]]) -> dict[str, object]:
    """根据真实 (model, prompt_tokens, completion_tokens) 算实际成本"""
    total = 0.0
    rows = []
    for agent, info in usage_by_agent.items():
        model = str(info.get("model", "default-analytical"))
        p = int(info.get("prompt_tokens", 0) or 0)
        c = int(info.get("completion_tokens", 0) or 0)
        cost = estimate_cost(model, p, c)
        total += cost
        rows.append(
            {
                "agent": agent,
                "model": model,
                "prompt_tokens": p,
                "completion_tokens": c,
                "cost_usd": round(cost, 4),
            }
        )
    return {"total_cost_usd": round(total, 4), "breakdown": rows}
