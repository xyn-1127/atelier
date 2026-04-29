"""FileAgent 测试。

用 mock 模拟 LLM，验证 FileAgent 能正确调用文件工具。
"""

from unittest.mock import patch, MagicMock

from app.agents.file_agent import FileAgent


def make_text_response(content):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    return msg


def make_tool_call_response(tool_calls_data, content=None):
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


class TestFileAgent:

    def test_has_correct_tools(self):
        """FileAgent 有 3 个文件工具。"""
        agent = FileAgent()

        tools = agent.tools.list_all()
        names = {t.name for t in tools}
        assert names == {"list_files", "read_file", "get_file_info"}

    def test_has_correct_name(self):
        agent = FileAgent()
        assert agent.name == "file_agent"

    @patch("app.agents.base.chat_completion_with_tools")
    def test_list_then_read_flow(self, mock_llm):
        """典型流程：LLM 先 list_files，再 read_file，最后回答。"""
        mock_llm.side_effect = [
            # 第 1 轮：LLM 想 list_files
            make_tool_call_response([
                ("call_001", "list_files", '{"workspace_id": 1}'),
            ]),
            # 第 2 轮：LLM 想 read_file
            make_tool_call_response([
                ("call_002", "read_file", '{"file_id": 5}'),
            ]),
            # 第 3 轮：LLM 给出最终回答
            make_text_response("main.py 里定义了 hello 函数"),
        ]

        agent = FileAgent()
        result = agent.run("帮我看看 main.py", context={"workspace_id": 1})

        assert result.status == "success"
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].tool_name == "list_files"
        assert result.tool_calls[1].tool_name == "read_file"
        assert mock_llm.call_count == 3

    @patch("app.agents.base.chat_completion_with_tools")
    def test_direct_response(self, mock_llm):
        """LLM 判断不需要工具，直接回答。"""
        mock_llm.return_value = make_text_response("我是文件分析助手，有什么可以帮你的？")

        agent = FileAgent()
        result = agent.run("你好")

        assert result.status == "success"
        assert result.tool_calls == []

    @patch("app.agents.base.chat_completion_with_tools")
    def test_context_passed_to_llm(self, mock_llm):
        """workspace_id 通过 context 传给 LLM。"""
        mock_llm.return_value = make_text_response("ok")

        agent = FileAgent()
        agent.run("列出文件", context={"workspace_id": 42})

        messages = mock_llm.call_args.args[0]
        # 应该有 context message 包含 workspace_id
        context_msgs = [m for m in messages if "workspace_id" in str(m.get("content", ""))]
        assert len(context_msgs) > 0
