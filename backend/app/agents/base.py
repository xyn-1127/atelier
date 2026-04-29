"""Agent 基类。

Agent 是能自主使用工具来完成任务的 AI。
核心循环（ReAct 模式）：

    用户给任务 → Agent 问 LLM 怎么做
      → LLM 说"我要用工具" → Agent 执行工具 → 把结果告诉 LLM
      → LLM 说"我还要用另一个工具" → 执行 → 告诉 LLM
      → LLM 说"我现在可以回答了" → Agent 返回最终答案

这个 "思考 → 行动 → 观察 → 再思考" 的循环就是 ReAct。
"""

import json
import logging
import time
from dataclasses import dataclass, field

from app.llm.client import chat_completion_with_tools, chat_completion_with_tools_stream, get_last_usage
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """记录一次工具调用（用于追溯 Agent 做了什么）。"""
    tool_name: str
    arguments: dict
    result: str


@dataclass
class AgentResult:
    """Agent 执行的最终结果。"""
    content: str                                 # 最终回答
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    status: str = "success"
    error: str | None = None
    metrics: dict = field(default_factory=dict)  # {"duration_ms", "tokens", "tool_durations"}
    error: str | None = None                     # 错误信息


class BaseAgent:
    """Agent 基类，所有专业 Agent 继承它。

    子类只需要设置 name / description / system_prompt / tools，
    核心的 ReAct 循环由基类的 run() / run_with_events() 方法提供。

    两个入口：
    - run()            — 非流式，直接返回最终结果
    - run_with_events() — 流式，yield 事件（content_chunk / tool_call / tool_result / result）
    """

    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
        tools: ToolRegistry,
        max_iterations: int = 10,
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = tools
        self.max_iterations = max_iterations

    # ─── 非流式入口 ───

    def run(self, task: str, context: dict | None = None) -> AgentResult:
        """执行任务（非流式）。一次性返回最终结果。"""
        messages = self._build_initial_messages(task, context)
        openai_tools = self.tools.to_openai_tools()
        tool_call_records = []

        logger.info("Agent '%s' starting task: %s", self.name, task[:100])

        for iteration in range(self.max_iterations):
            logger.info("Agent '%s' iteration %d/%d", self.name, iteration + 1, self.max_iterations)

            try:
                message = chat_completion_with_tools(messages, openai_tools)
            except Exception as e:
                logger.error("Agent '%s' LLM call failed: %s", self.name, e)
                return AgentResult(content="", tool_calls=tool_call_records,
                                   status="error", error=f"LLM 调用失败: {e}")

            if not message.tool_calls:
                logger.info("Agent '%s' finished, %d tool calls made", self.name, len(tool_call_records))
                return AgentResult(content=message.content or "",
                                   tool_calls=tool_call_records, status="success")

            messages.append(self._assistant_message_with_tool_calls(message))
            for tc in message.tool_calls:
                tool_name = tc.function.name
                arguments = self._parse_arguments(tc.function.arguments)
                result = self.tools.execute(tool_name, arguments)
                tool_call_records.append(ToolCallRecord(tool_name=tool_name,
                                                         arguments=arguments, result=result))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return AgentResult(content="", tool_calls=tool_call_records,
                           status="error", error=f"超过最大循环次数 ({self.max_iterations})")

    # ─── 流式入口 ───

    def run_with_events(self, task: str, context: dict | None = None):
        """执行任务（流式），yield 事件。

        yields (event_type, data) 元组：
          - ("content_chunk", "文本片段")                       → LLM 实时输出（可能是最终回答，也可能是思考）
          - ("content_to_thinking", "文本")                     → 告诉前端：刚才的 content 是思考，不是回答，请挪到 ToolCallBlock
          - ("tool_call", {"tool_name": ..., "arguments": ...}) → 开始调用工具
          - ("tool_result", {"tool_name": ..., "result": ...})  → 工具返回结果
          - ("result", AgentResult)                             → 最终结果
        """
        messages = self._build_initial_messages(task, context)
        openai_tools = self.tools.to_openai_tools()
        tool_call_records = []
        final_content = ""

        # ── metrics 统计 ──
        agent_start = time.monotonic()
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        tool_durations = []

        def _accumulate_tokens():
            usage = get_last_usage()
            for k in total_tokens:
                total_tokens[k] += usage.get(k, 0)

        def _build_metrics():
            return {
                "duration_ms": int((time.monotonic() - agent_start) * 1000),
                "tokens": dict(total_tokens),
                "tool_durations": tool_durations,
            }

        logger.info("Agent '%s' starting task (stream): %s", self.name, task[:100])

        for iteration in range(self.max_iterations):
            logger.info("Agent '%s' iteration %d/%d", self.name, iteration + 1, self.max_iterations)

            # ── 流式调用 LLM，content 实时推送 ──
            try:
                content_buffer = ""
                tool_calls_data = None

                for event_type, data in chat_completion_with_tools_stream(messages, openai_tools):
                    if event_type == "content_chunk":
                        content_buffer += data
                        yield ("content_chunk", data)
                    elif event_type == "tool_calls":
                        tool_calls_data = data

                _accumulate_tokens()

            except Exception as e:
                logger.error("Agent '%s' LLM call failed: %s", self.name, e)
                yield ("result", AgentResult(content=final_content, tool_calls=tool_call_records,
                                             status="error", error=f"LLM 调用失败: {e}",
                                             metrics=_build_metrics()))
                return

            # ── 情况 A：没有 tool_calls → 最终回答 ──
            if not tool_calls_data:
                final_content += content_buffer
                logger.info("Agent '%s' finished, %d tool calls made", self.name, len(tool_call_records))
                yield ("result", AgentResult(content=final_content,
                                             tool_calls=tool_call_records, status="success",
                                             metrics=_build_metrics()))
                return

            # ── 情况 B：有 tool_calls ──
            if content_buffer:
                yield ("content_to_thinking", content_buffer)

            try:
                from app.tools.writer_tools import set_current_content
                set_current_content(content_buffer)
            except ImportError:
                pass

            messages.append({
                "role": "assistant",
                "content": content_buffer or None,
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls_data
                ],
            })

            for tc in tool_calls_data:
                tool_name = tc["name"]
                arguments = self._parse_arguments(tc["arguments"])

                logger.info("Agent '%s' calling tool: %s(%s)", self.name, tool_name, arguments)
                yield ("tool_call", {"tool_name": tool_name, "arguments": arguments})

                tool_start = time.monotonic()
                result = self.tools.execute(tool_name, arguments)
                tool_durations.append({
                    "name": tool_name,
                    "duration_ms": int((time.monotonic() - tool_start) * 1000),
                })

                tool_call_records.append(ToolCallRecord(
                    tool_name=tool_name, arguments=arguments, result=result))
                yield ("tool_result", {"tool_name": tool_name, "result": result})

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        # ── 超过最大循环 → 提示用户 + 强制 LLM 总结已有信息 ──
        logger.warning("Agent '%s' exceeded max iterations (%d), forcing final answer", self.name, self.max_iterations)
        notice = f"\n\n---\n*（已达到最大工具调用次数 {self.max_iterations} 次，基于已收集的信息生成回答）*\n\n"
        yield ("content_chunk", notice)
        final_content += notice

        try:
            messages.append({"role": "user", "content": "你已经调用了太多次工具。请直接基于目前收集到的信息给出回答，不要再调用任何工具。"})
            for event_type, data in chat_completion_with_tools_stream(messages, []):
                if event_type == "content_chunk":
                    final_content += data
                    yield ("content_chunk", data)
        except Exception:
            pass

        _accumulate_tokens()
        yield ("result", AgentResult(content=final_content or "（Agent 达到最大工具调用次数，请缩小问题范围重试）",
                                     tool_calls=tool_call_records, status="done",
                                     metrics=_build_metrics()))

    # ─── 内部辅助方法 ───

    def _build_initial_messages(self, task: str, context: dict | None) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            output_hint = context.get("output_hint")
            workspace_id = context.get("workspace_id")
            other_ctx = {k: v for k, v in context.items() if k not in ("output_hint",)}

            # 注入工作区记忆
            if workspace_id:
                try:
                    from app.db.session import SessionLocal
                    from app.services.memory import recall_memories, format_memories_for_prompt
                    db = SessionLocal()
                    try:
                        memories = recall_memories(db, workspace_id)
                        if memories:
                            mem_text = format_memories_for_prompt(memories)
                            messages.append({"role": "system",
                                             "content": f"关于这个工作区的已知信息：\n{mem_text}"})
                    finally:
                        db.close()
                except Exception:
                    pass

            if other_ctx:
                context_text = "\n".join(f"- {k}: {v}" for k, v in other_ctx.items())
                messages.append({"role": "system", "content": f"当前上下文信息：\n{context_text}"})

            if output_hint:
                messages.append({"role": "system",
                                 "content": f"输出要求：{output_hint}。请严格控制回答长度。"})

        messages.append({"role": "user", "content": task})
        return messages

    @staticmethod
    def _parse_arguments(arguments_str: str) -> dict:
        try:
            return json.loads(arguments_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def _assistant_message_with_tool_calls(message) -> dict:
        return {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in message.tool_calls
            ],
        }
