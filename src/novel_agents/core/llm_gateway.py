"""LLM网关 — 通过 APIMart API聚合平台统一调用 Claude + DeepSeek

注意：APIMart 强制返回流式响应（忽略 stream=false 参数），
因此使用自定义 LLM 类通过流式模式收集完整响应。
"""

import os
from typing import Any, Iterator

import litellm
from crewai import LLM

APIMART_BASE_URL = "https://api.apimart.ai/v1"


def _get_api_key() -> str:
    return os.getenv("APIMART_API_KEY", "")


def _clean_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """移除尾部 assistant prefill，兼容 APIMart Claude/DeepSeek 路由。"""
    cleaned_messages = list(messages)
    while cleaned_messages and cleaned_messages[-1].get("role") == "assistant":
        cleaned_messages.pop()
    return cleaned_messages or messages


class APIMartLLM(LLM):
    """适配APIMart的LLM包装器 — 使用流式模式收集完整响应以兼容APIMart强制流式返回"""

    def call(
        self,
        messages: list[dict[str, str]],
        callbacks: list[Any] | None = None,
        available_functions: list[dict] | None = None,
        **kwargs: Any,
    ) -> str:
        stream_callback = kwargs.pop("stream_callback", None)
        # APIMart的Claude端点不支持assistant message prefill
        # 如果最后一条消息是assistant角色，需要移除（CrewAI内部行为）
        cleaned_messages = _clean_messages(messages)

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
                if callable(stream_callback):
                    stream_callback(delta.content)
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


def stream_outline_chat(messages: list[dict[str, str]], chapter_num: int = 1) -> Iterator[str]:
    """流式生成大纲引导对话；前端通过 SSE 实时消费。"""
    system_prompt = (
        "你是资深玄幻修仙小说编辑。你的任务分两阶段：\n"
        "1) 引导用户补齐创作偏好（主角设定、核心冲突、必须出现桥段、风格节奏）；\n"
        "2) 当信息足够，或用户明确说“生成大纲”时，输出结构化章节大纲。\n\n"
        "规则：\n"
        "- 信息不足时只提 1-2 个关键追问，问题要短、具体。\n"
        "- 当你判断可以产出时，直接输出 Markdown，且必须包含标题“## 大纲”。\n"
        "- 大纲需包含：本章目标、冲突升级链路、关键场景分解（3-6个）、角色推进、章末钩子。\n"
        f"- 当前目标章节：第 {chapter_num} 章。\n"
    )
    payload_messages = [{"role": "system", "content": system_prompt}]
    payload_messages.extend(_clean_messages(messages))
    response = litellm.completion(
        model="openai/deepseek-v4-pro",
        messages=payload_messages,
        temperature=0.6,
        max_tokens=4096,
        stream=True,
        api_key=_get_api_key(),
        api_base=APIMART_BASE_URL,
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
