"""LLM网关 — Claude + DeepSeek 混用配置"""

import os

from crewai import LLM


def get_creative_llm() -> LLM:
    """创意写作LLM（Claude） — 用于 Writer、Polisher"""
    return LLM(
        model="anthropic/claude-sonnet-4-20250514",
        temperature=0.85,
        max_tokens=8192,
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    )


def get_analytical_llm() -> LLM:
    """分析推理LLM（DeepSeek） — 用于 Planner、WorldBuilder、Reviewer、ReaderSim"""
    return LLM(
        model="deepseek/deepseek-chat",
        temperature=0.4,
        max_tokens=8192,
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    )


LLM_ASSIGNMENT = {
    "planner": get_analytical_llm,
    "world_builder": get_analytical_llm,
    "writer": get_creative_llm,
    "reviewer": get_analytical_llm,
    "polisher": get_creative_llm,
    "reader_sim": get_analytical_llm,
}
