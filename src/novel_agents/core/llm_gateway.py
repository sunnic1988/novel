"""LLM网关 — 通过 APIMart API聚合平台统一调用 Claude + DeepSeek

注意：APIMart 强制返回流式响应（忽略 stream=false 参数），
因此使用自定义 LLM 类通过流式模式收集完整响应。
"""

import os
from typing import Any

import litellm
from crewai import LLM

APIMART_BASE_URL = "https://api.apimart.ai/v1"


def _get_api_key() -> str:
    return os.getenv("APIMART_API_KEY", "")


class APIMartLLM(LLM):
    """适配APIMart的LLM包装器 — 使用流式模式收集完整响应以兼容APIMart强制流式返回"""

    def call(
        self,
        messages: list[dict[str, str]],
        callbacks: list[Any] | None = None,
        available_functions: list[dict] | None = None,
        **kwargs: Any,
    ) -> str:
        # APIMart的Claude端点不支持assistant message prefill
        # 如果最后一条消息是assistant角色，需要移除（CrewAI内部行为）
        cleaned_messages = list(messages)
        while cleaned_messages and cleaned_messages[-1].get("role") == "assistant":
            cleaned_messages.pop()
        if not cleaned_messages:
            cleaned_messages = messages

        params: dict[str, Any] = {
            "model": self.model,
            "messages": cleaned_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
            "api_key": self.api_key,
            "api_base": self.base_url,
        }

        if self.top_p:
            params["top_p"] = self.top_p
        if self.stop:
            params["stop"] = self.stop
        if available_functions:
            params["tools"] = available_functions

        response = litellm.completion(**params)

        full_content = ""
        tool_calls: list[dict] = []

        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                full_content += delta.content
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    while len(tool_calls) <= idx:
                        tool_calls.append({
                            "id": "", "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["function"]["arguments"] += tc.function.arguments

        return full_content


def get_creative_llm() -> APIMartLLM:
    """创意写作LLM（Claude Sonnet 4.6） — 用于 Writer、Polisher"""
    return APIMartLLM(
        model="openai/claude-sonnet-4-6",
        temperature=0.85,
        max_tokens=8192,
        api_key=_get_api_key(),
        base_url=APIMART_BASE_URL,
    )


def get_analytical_llm() -> APIMartLLM:
    """分析推理LLM（DeepSeek V4 Pro） — 用于 Planner、WorldBuilder、Reviewer、ReaderSim"""
    return APIMartLLM(
        model="openai/deepseek-v4-pro",
        temperature=0.4,
        max_tokens=8192,
        api_key=_get_api_key(),
        base_url=APIMART_BASE_URL,
    )


LLM_ASSIGNMENT = {
    "arc_architect": get_analytical_llm,
    "pacing_doctor": get_analytical_llm,
    "planner": get_analytical_llm,
    "world_builder": get_analytical_llm,
    "writer": get_creative_llm,
    "reviewer": get_analytical_llm,
    "polisher": get_creative_llm,
    "reader_sim": get_analytical_llm,
    "marketing_specialist": get_creative_llm,
}
