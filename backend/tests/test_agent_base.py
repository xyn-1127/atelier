"""Agent 基类测试。

用 mock 模拟 LLM 的 tool_call 和文本响应，测试 ReAct 循环。
"""

from unittest.mock import patch, MagicMock

from app.agents.base import BaseAgent, AgentResult, ToolCallRecord
from app.tools.registry import Tool, ToolRegistry


# ─── 辅助函数 ───


def make_text_response(content):
    """模拟 LLM 返回纯文本。"""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    return msg


def make_tool_call_response(tool_calls_data, content=None):
    """模拟 LLM 返回 tool_calls。

    tool_calls_data: [("call_id", "tool_name", '{"arg": "val"}'), ...]
    """
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = []
    for call_id, name, arguments in tool_calls_data:
        tc = MagicMock()
        tc.id = call_id
        tc.function = MagicMock()
        tc.function.name = name
        tc.function.arguments = arguments
        msg.tool_calls.append(tc)
    return msg


def make_test_registry():
    """创建一个包含测试工具的 registry。"""
    registry = ToolRegistry()
    registry.register(Tool(
        name="greet",
        description="打招呼",
        parameters={"name": {"type": "string", "description": "名字"}},
        function=lambda name: f"你好，{name}！",
    ))
    registry.register(Tool(
        name="add",
        description="加法",
        parameters={
            "a": {"type": "integer", "description": "第一个数"},
            "b": {"type": "integer", "description": "第二个数"},
        },
        function=lambda a, b: str(a + b),
    ))
    return registry


def make_test_agent(registry=None, max_iterations=10):
    """创建一个测试用 Agent。"""
    return BaseAgent(
        name="test_agent",
        description="测试用 Agent",
        system_prompt="你是一个测试助手，请使用工具回答问题。",
        tools=registry or make_test_registry(),
        max_iterations=max_iterations,
    )


# ─── 测试 ───


class TestAgentDirectResponse:
    """LLM 不调工具，直接回复。"""

    @patch("app.agents.base.chat_completion_with_tools")
    def test_direct_text_response(self, mock_llm):
        """LLM 直接回复文本，不用工具。"""
        mock_llm.return_value = make_text_response("1+1=2")

        agent = make_test_agent()
        result = agent.run("1+1等于几？")

        assert result.status == "success"
        assert result.content == "1+1=2"
        assert result.tool_calls == []
        assert mock_llm.call_count == 1

    @patch("app.agents.base.chat_completion_with_tools")
    def test_empty_content(self, mock_llm):
        """LLM 返回空内容。"""
        mock_llm.return_value = make_text_response("")

        agent = make_test_agent()
        result = agent.run("hi")

        assert result.status == "success"
        assert result.content == ""


class TestAgentToolCalling:
    """LLM 调用工具。"""

    @patch("app.agents.base.chat_completion_with_tools")
    def test_one_tool_call(self, mock_llm):
        """LLM 调用一个工具，然后给出回答。"""
        # 第 1 次调用：LLM 要用 greet 工具
        # 第 2 次调用：LLM 看到工具结果后回答
        mock_llm.side_effect = [
            make_tool_call_response([("call_001", "greet", '{"name": "Alice"}')]),
            make_text_response("我已经和 Alice 打过招呼了，她说你好！"),
        ]

        agent = make_test_agent()
        result = agent.run("跟 Alice 打招呼")

        assert result.status == "success"
        assert "Alice" in result.content
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "greet"
        assert result.tool_calls[0].arguments == {"name": "Alice"}
        assert result.tool_calls[0].result == "你好，Alice！"
        assert mock_llm.call_count == 2

    @patch("app.agents.base.chat_completion_with_tools")
    def test_multiple_tool_calls_in_sequence(self, mock_llm):
        """LLM 连续调用多个工具（每轮一个）。"""
        mock_llm.side_effect = [
            # 第 1 轮：调 greet
            make_tool_call_response([("call_001", "greet", '{"name": "Bob"}')]),
            # 第 2 轮：调 add
            make_tool_call_response([("call_002", "add", '{"a": 3, "b": 5}')]),
            # 第 3 轮：回复
            make_text_response("Bob 说你好，3+5=8。"),
        ]

        agent = make_test_agent()
        result = agent.run("跟 Bob 打招呼，然后算 3+5")

        assert result.status == "success"
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].tool_name == "greet"
        assert result.tool_calls[1].tool_name == "add"
        assert result.tool_calls[1].result == "8"
        assert mock_llm.call_count == 3

    @patch("app.agents.base.chat_completion_with_tools")
    def test_multiple_tool_calls_in_one_round(self, mock_llm):
        """LLM 一次返回多个 tool_calls（并行调用）。"""
        mock_llm.side_effect = [
            # 一次返回 2 个 tool_calls
            make_tool_call_response([
                ("call_001", "greet", '{"name": "A"}'),
                ("call_002", "greet", '{"name": "B"}'),
            ]),
            make_text_response("已经跟 A 和 B 都打了招呼。"),
        ]

        agent = make_test_agent()
        result = agent.run("跟 A 和 B 打招呼")

        assert result.status == "success"
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].result == "你好，A！"
        assert result.tool_calls[1].result == "你好，B！"


class TestAgentContext:
    """上下文传递。"""

    @patch("app.agents.base.chat_completion_with_tools")
    def test_context_included_in_messages(self, mock_llm):
        """context 参数被加入 messages。"""
        mock_llm.return_value = make_text_response("ok")

        agent = make_test_agent()
        agent.run("测试", context={"workspace_id": 1, "user": "test"})

        # 检查传给 LLM 的 messages
        call_args = mock_llm.call_args
        messages = call_args.args[0]

        # messages: system prompt + (可能有记忆) + context + user task
        assert messages[-1]["content"] == "测试"  # 最后一条是 user task
        # 中间应该有 context 信息
        context_msgs = [m for m in messages if "workspace_id" in str(m.get("content", ""))]
        assert len(context_msgs) > 0

    @patch("app.agents.base.chat_completion_with_tools")
    def test_no_context(self, mock_llm):
        """没有 context 时不多加 message。"""
        mock_llm.return_value = make_text_response("ok")

        agent = make_test_agent()
        agent.run("测试")

        messages = mock_llm.call_args.args[0]
        assert len(messages) == 2  # system + user


class TestAgentErrorHandling:
    """错误处理。"""

    @patch("app.agents.base.chat_completion_with_tools")
    def test_max_iterations_exceeded(self, mock_llm):
        """超过最大循环次数。"""
        # LLM 一直要调工具，不给最终回答
        mock_llm.return_value = make_tool_call_response(
            [("call_001", "greet", '{"name": "test"}')]
        )

        agent = make_test_agent(max_iterations=3)
        result = agent.run("无限循环")

        assert result.status == "error"
        assert "最大循环次数" in result.error
        assert len(result.tool_calls) == 3  # 每轮调一次
        assert mock_llm.call_count == 3

    @patch("app.agents.base.chat_completion_with_tools")
    def test_llm_call_fails(self, mock_llm):
        """LLM API 调用失败。"""
        mock_llm.side_effect = RuntimeError("API 超时")

        agent = make_test_agent()
        result = agent.run("测试")

        assert result.status == "error"
        assert "LLM 调用失败" in result.error

    @patch("app.agents.base.chat_completion_with_tools")
    def test_tool_execution_error(self, mock_llm):
        """工具执行出错时 Agent 不崩溃，继续运行。"""
        registry = ToolRegistry()
        registry.register(Tool(
            name="broken",
            description="坏掉的工具",
            parameters={},
            function=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        ))
        # 替换为真正会抛异常的函数
        registry._tools["broken"].function = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

        def explode():
            raise RuntimeError("boom")

        registry._tools["broken"].function = explode

        mock_llm.side_effect = [
            make_tool_call_response([("call_001", "broken", "{}")]),
            make_text_response("工具出错了，但我还在。"),
        ]

        agent = make_test_agent(registry=registry)
        result = agent.run("用坏掉的工具")

        assert result.status == "success"
        assert "工具执行失败" in result.tool_calls[0].result

    @patch("app.agents.base.chat_completion_with_tools")
    def test_bad_arguments_json(self, mock_llm):
        """LLM 返回无效的 arguments JSON。"""
        mock_llm.side_effect = [
            make_tool_call_response([("call_001", "greet", "invalid json!!!")]),
            make_text_response("参数解析失败了。"),
        ]

        agent = make_test_agent()
        result = agent.run("测试")

        # 不应该崩溃，arguments 解析失败时传空 dict
        assert result.status == "success"
        assert result.tool_calls[0].arguments == {}


class TestRunWithEvents:
    """run_with_events() 流式事件测试（mock 流式 LLM 调用）。"""

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_content_streams_then_moves_to_thinking(self, mock_stream):
        """content 先实时推送，发现有 tool_calls 后发 content_to_thinking 让前端挪走。"""
        mock_stream.side_effect = [
            iter([
                ("content_chunk", "我来"),
                ("content_chunk", "查看"),
                ("tool_calls", [{"id": "c1", "name": "greet", "arguments": '{"name": "Alice"}'}]),
            ]),
            iter([
                ("content_chunk", "Done"),
            ]),
        ]

        agent = make_test_agent()
        events = list(agent.run_with_events("test"))

        types = [e[0] for e in events]
        # content_chunk 实时推送 → 发现 tool_calls → content_to_thinking → 工具执行 → 最终回答
        assert types == [
            "content_chunk", "content_chunk",  # 实时逐字
            "content_to_thinking",              # 让前端挪到 ToolCallBlock
            "tool_call", "tool_result",         # 工具执行
            "content_chunk",                    # 最终回答（实时）
            "result",
        ]

        assert events[0][1] == "我来"
        assert events[1][1] == "查看"
        assert events[2][1] == "我来查看"  # content_to_thinking 包含完整文本
        assert events[5][1] == "Done"
        assert events[6][1].content == "Done"

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_final_answer_streams_realtime(self, mock_stream):
        """最终回答逐字实时流式推送。"""
        mock_stream.return_value = iter([
            ("content_chunk", "你"),
            ("content_chunk", "好"),
            ("content_chunk", "世界"),
        ])

        agent = make_test_agent()
        events = list(agent.run_with_events("test"))

        types = [e[0] for e in events]
        assert types == ["content_chunk", "content_chunk", "content_chunk", "result"]
        assert events[0][1] == "你"
        assert events[1][1] == "好"
        assert events[2][1] == "世界"
        assert events[3][1].content == "你好世界"

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_stream_error_handling(self, mock_stream):
        """流式调用失败时返回 error result。"""
        mock_stream.side_effect = RuntimeError("网络超时")

        agent = make_test_agent()
        events = list(agent.run_with_events("test"))

        assert events[-1][0] == "result"
        assert events[-1][1].status == "error"


class TestAgentMessages:
    """验证发给 LLM 的 messages 格式。"""

    @patch("app.agents.base.chat_completion_with_tools")
    def test_tool_result_added_to_messages(self, mock_llm):
        """工具执行结果被正确加入 messages。"""
        mock_llm.side_effect = [
            make_tool_call_response([("call_001", "add", '{"a": 1, "b": 2}')]),
            make_text_response("结果是 3"),
        ]

        agent = make_test_agent()
        agent.run("算 1+2")

        # 第 2 次调用时的 messages 应该包含工具结果
        second_call_messages = mock_llm.call_args_list[1].args[0]

        # messages: [system, user, assistant(tool_calls), tool(result)]
        assert len(second_call_messages) == 4
        assert second_call_messages[2]["role"] == "assistant"
        assert second_call_messages[2]["tool_calls"][0]["function"]["name"] == "add"
        assert second_call_messages[3]["role"] == "tool"
        assert second_call_messages[3]["tool_call_id"] == "call_001"
        assert second_call_messages[3]["content"] == "3"
