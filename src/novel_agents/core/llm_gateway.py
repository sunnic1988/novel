"""LLM网关 — 通过 APIMart API聚合平台统一调用 Claude + DeepSeek"""

import os

from crewai import LLM

APIMART_BASE_URL = "https://api.apimart.ai/v1"


def _get_api_key() -> str:
    return os.getenv("APIMART_API_KEY", "")


def get_creative_llm() -> LLM:
    """创意写作LLM（Claude Sonnet 4.5） — 用于 Writer、Polisher"""
    return LLM(
        model="openai/claude-sonnet-4-5-20250929",
        temperature=0.85,
        max_tokens=8192,
        api_key=_get_api_key(),
        base_url=APIMART_BASE_URL,
    )


def get_analytical_llm() -> LLM:
    """分析推理LLM（DeepSeek V3.1） — 用于 Planner、WorldBuilder、Reviewer、ReaderSim"""
    return LLM(
        model="openai/deepseek-v3.1-250821",
        temperature=0.4,
        max_tokens=8192,
        api_key=_get_api_key(),
        base_url=APIMART_BASE_URL,
    )


LLM_ASSIGNMENT = {
    "planner": get_analytical_llm,
    "world_builder": get_analytical_llm,
    "writer": get_creative_llm,
    "reviewer": get_analytical_llm,
    "polisher": get_creative_llm,
    "reader_sim": get_analytical_llm,
}
