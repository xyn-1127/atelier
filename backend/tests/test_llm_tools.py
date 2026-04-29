"""LLM Tool Calling 函数测试。

用 mock 模拟 OpenAI API 响应，测试 tool_call 解析逻辑。
"""

from unittest.mock import patch, MagicMock

from app.llm.client import chat_completion_with_tools, chat_completion_with_tools_stream


# ─── 辅助函数：构造 mock 对象 ───


def make_message(content=None, tool_calls=None):
    """构造 mock 的 response.choices[0].message。"""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    return msg


def make_tool_call(call_id, name, arguments):
    """构造 mock 的 tool_call 对象。"""
    tc = MagicMock()
    tc.id = call_id
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def make_stream_chunk(content=None, tool_calls=None):
    """构造 mock 的流式 chunk。"""
    chunk = MagicMock()
    choice = MagicMock()
    choice.delta = MagicMock()
    choice.delta.content = content
    choice.delta.tool_calls = tool_calls
    chunk.choices = [choice]
    return chunk


def make_stream_tool_call(index, call_id=None, name=None, arguments=None):
    """构造流式 chunk 中的 tool_call delta。"""
    tc = MagicMock()
    tc.index = index
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


# ─── 非流式测试 ───


class TestChatCompletionWithTools:

    @patch("app.llm.client.get_llm_client")
    def test_returns_text_response(self, mock_get_client):
        """LLM 直接回复文本（不调工具）。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        msg = make_message(content="main.py 里定义了 create_application 函数")
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=msg)]
        )

        result = chat_completion_with_tools(
            messages=[{"role": "user", "content": "看看 main.py"}],
            tools=[{"type": "function", "function": {"name": "read_file"}}],
        )

        assert result.content == "main.py 里定义了 create_application 函数"
        assert result.tool_calls is None

    @patch("app.llm.client.get_llm_client")
    def test_returns_tool_calls(self, mock_get_client):
        """LLM 要调用工具。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        tc = make_tool_call("call_001", "read_file", '{"file_id": 5}')
        msg = make_message(content=None, tool_calls=[tc])
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=msg)]
        )

        result = chat_completion_with_tools(
            messages=[{"role": "user", "content": "看看 main.py"}],
            tools=[],
        )

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].function.name == "read_file"
        assert result.tool_calls[0].function.arguments == '{"file_id": 5}'

    @patch("app.llm.client.get_llm_client")
    def test_passes_tools_to_api(self, mock_get_client):
        """tools 参数正确传给了 API。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        msg = make_message(content="ok")
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=msg)]
        )

        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        chat_completion_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
        )

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["tools"] == tools


# ─── 流式测试 ───


class TestChatCompletionWithToolsStream:

    @patch("app.llm.client.get_llm_client")
    def test_stream_text_response(self, mock_get_client):
        """流式返回纯文本（不调工具）。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # 模拟 3 个文本 chunk
        chunks = [
            make_stream_chunk(content="你好"),
            make_stream_chunk(content="，世界"),
            make_stream_chunk(content="！"),
        ]
        mock_client.chat.completions.create.return_value = iter(chunks)

        events = list(chat_completion_with_tools_stream(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        ))

        assert len(events) == 3
        assert all(e[0] == "content_chunk" for e in events)
        full_text = "".join(e[1] for e in events)
        assert full_text == "你好，世界！"

    @patch("app.llm.client.get_llm_client")
    def test_stream_tool_calls(self, mock_get_client):
        """流式返回工具调用（arguments 跨 chunk 拼接）。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # 模拟 tool_call 分 3 个 chunk 到达
        chunks = [
            # chunk 1: id + name + arguments 开头
            make_stream_chunk(tool_calls=[
                make_stream_tool_call(0, call_id="call_001", name="read_file", arguments='{"file'),
            ]),
            # chunk 2: arguments 中间
            make_stream_chunk(tool_calls=[
                make_stream_tool_call(0, arguments='_id":'),
            ]),
            # chunk 3: arguments 结尾
            make_stream_chunk(tool_calls=[
                make_stream_tool_call(0, arguments=' 5}'),
            ]),
        ]
        mock_client.chat.completions.create.return_value = iter(chunks)

        events = list(chat_completion_with_tools_stream(
            messages=[{"role": "user", "content": "看看文件"}],
            tools=[],
        ))

        # 应该只有一个 tool_calls 事件（在最后）
        assert len(events) == 1
        assert events[0][0] == "tool_calls"

        tool_calls = events[0][1]
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_001"
        assert tool_calls[0]["name"] == "read_file"
        assert tool_calls[0]["arguments"] == '{"file_id": 5}'

    @patch("app.llm.client.get_llm_client")
    def test_stream_multiple_tool_calls(self, mock_get_client):
        """流式返回多个工具调用。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        chunks = [
            # 第一个工具
            make_stream_chunk(tool_calls=[
                make_stream_tool_call(0, call_id="call_001", name="list_files", arguments='{"workspace_id": 1}'),
            ]),
            # 第二个工具
            make_stream_chunk(tool_calls=[
                make_stream_tool_call(1, call_id="call_002", name="read_file", arguments='{"file_id": 5}'),
            ]),
        ]
        mock_client.chat.completions.create.return_value = iter(chunks)

        events = list(chat_completion_with_tools_stream(
            messages=[], tools=[],
        ))

        assert len(events) == 1
        tool_calls = events[0][1]
        assert len(tool_calls) == 2
        assert tool_calls[0]["name"] == "list_files"
        assert tool_calls[1]["name"] == "read_file"

    @patch("app.llm.client.get_llm_client")
    def test_stream_empty_chunks_ignored(self, mock_get_client):
        """空 chunk 被跳过。"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        empty_chunk = MagicMock()
        empty_chunk.choices = []

        text_chunk = make_stream_chunk(content="hello")

        mock_client.chat.completions.create.return_value = iter([empty_chunk, text_chunk])

        events = list(chat_completion_with_tools_stream(
            messages=[], tools=[],
        ))

        assert len(events) == 1
        assert events[0] == ("content_chunk", "hello")
