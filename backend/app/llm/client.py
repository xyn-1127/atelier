import logging

from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_llm_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def chat_completion(messages: list[dict]) -> str:
    """调用 LLM 获取回复。

    参数:
        messages: OpenAI 格式的消息列表
            [{"role": "user", "content": "你好"}]

    返回:
        AI 回复的文本字符串
    """
    settings = get_settings()
    client = get_llm_client()

    logger.info("Calling LLM model=%s, messages_count=%d", settings.llm_model, len(messages))

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
    )

    content = response.choices[0].message.content
    logger.info("LLM response received, length=%d", len(content))
    return content


def chat_completion_stream(messages: list[dict]):
    """流式调用 LLM，逐块返回文本。

    用法:
        for chunk_text in chat_completion_stream(messages):
            print(chunk_text)  # 每次拿到几个字
    """
    settings = get_settings()
    client = get_llm_client()

    logger.info("Calling LLM (stream) model=%s, messages_count=%d", settings.llm_model, len(messages))

    stream = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_completion_stream_reasoning(messages: list[dict]):
    """流式调用 reasoning 模型，同时返回思考过程和回复内容。

    用法:
        for chunk_type, chunk_text in chat_completion_stream_reasoning(messages):
            # chunk_type: "reasoning" 或 "content"
            print(chunk_type, chunk_text)
    """
    settings = get_settings()
    client = get_llm_client()

    logger.info("Calling LLM reasoning (stream) model=%s, messages_count=%d",
                settings.llm_reasoning_model, len(messages))

    stream = client.chat.completions.create(
        model=settings.llm_reasoning_model,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, 'reasoning_content', None)
        content = delta.content

        if reasoning:
            yield ("reasoning", reasoning)
        if content:
            yield ("content", content)


# ─── Token Usage 统计 ────────────────────────────────────────────────

import threading

_last_usage = threading.local()


def get_last_usage() -> dict:
    """获取最近一次 LLM 调用的 token usage。

    返回 {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    如果没有 usage 信息，返回空 dict。
    """
    return getattr(_last_usage, "value", {})


def _save_usage(usage) -> None:
    """保存 usage 信息到线程变量。"""
    if usage:
        _last_usage.value = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }
    else:
        _last_usage.value = {}


# ─── Tool Calling 支持 ───────────────────────────────────────────────


def chat_completion_with_tools(messages: list[dict], tools: list[dict]):
    """调用 LLM，带工具参数（非流式）。

    返回 response.choices[0].message 对象。
    调用后可通过 get_last_usage() 获取 token usage。
    """
    settings = get_settings()
    client = get_llm_client()

    logger.info("Calling LLM with tools, model=%s, messages=%d, tools=%d",
                settings.llm_model, len(messages), len(tools))

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        tools=tools,
    )

    _save_usage(response.usage)

    message = response.choices[0].message
    if message.tool_calls:
        logger.info("LLM wants to call %d tool(s): %s",
                     len(message.tool_calls),
                     [tc.function.name for tc in message.tool_calls])
    else:
        logger.info("LLM returned text response, length=%d",
                     len(message.content or ""))
    return message


def chat_completion_with_tools_stream(messages: list[dict], tools: list[dict]):
    """流式调用 LLM，带工具参数。

    yields (event_type, data) 元组：
      - ("content_chunk", "文本...")            → 普通文本 chunk
      - ("tool_calls", [{"id", "name", "arguments"}, ...]) → LLM 要调用工具

    注意：一次响应要么全是文本 chunk，要么最后一个是 tool_calls，不会混合。

    tool_calls 的 arguments 是 JSON 字符串（如 '{"file_id": 5}'），
    因为流式传输中 arguments 可能分多个 chunk 到达，需要拼接完才能 yield。
    """
    settings = get_settings()
    client = get_llm_client()

    logger.info("Calling LLM with tools (stream), model=%s, messages=%d, tools=%d",
                settings.llm_model, len(messages), len(tools))

    stream = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        stream=True,
        stream_options={"include_usage": True},
    )

    # 用于跨 chunk 拼接 tool_calls
    tool_calls_acc: dict[int, dict] = {}
    stream_usage = None

    for chunk in stream:
        # 最后一个 chunk 可能包含 usage 统计
        if hasattr(chunk, "usage") and chunk.usage:
            stream_usage = chunk.usage

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        # ── 普通文本 ──
        if delta.content:
            yield ("content_chunk", delta.content)

        # ── 工具调用（可能跨多个 chunk） ──
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}

                # id 和 name 通常在第一个 chunk 就完整到达
                if tc.id:
                    tool_calls_acc[idx]["id"] = tc.id
                if tc.function and tc.function.name:
                    tool_calls_acc[idx]["name"] = tc.function.name
                # arguments 是 JSON 字符串，分多个 chunk 到达，需要拼接
                if tc.function and tc.function.arguments:
                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

    # 保存 usage
    _save_usage(stream_usage)

    # 所有 chunk 读完后，如果有 tool_calls，yield 出完整的结果
    if tool_calls_acc:
        result = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]
        logger.info("LLM stream wants to call %d tool(s): %s",
                     len(result), [tc["name"] for tc in result])
        yield ("tool_calls", result)
