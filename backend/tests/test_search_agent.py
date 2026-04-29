"""SearchAgent 测试。

搜索工具用真实数据库 + mock ChromaDB 测试。
SearchAgent 用 mock LLM 测试。
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.agents.search_agent import SearchAgent
from app.tools.search_tools import semantic_search, keyword_search, create_search_tools
from app.services.chunker import chunk_workspace
from app.db.session import SessionLocal

client = TestClient(app)


# ─── 辅助函数 ───


def _create_indexed_workspace():
    """创建工作区 → 扫描 → 切块（不做向量化，只测关键词搜索和 Agent 逻辑）。"""
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "main.py"), "w") as f:
        f.write("from fastapi import FastAPI\n\napp = FastAPI()\n\n"
                "@app.get('/')\ndef root():\n    return {'msg': 'hello'}\n")
    with open(os.path.join(tmp, "database.py"), "w") as f:
        f.write("from sqlalchemy import create_engine\n\n"
                "engine = create_engine('sqlite:///test.db')\n")

    resp = client.post("/api/workspaces", json={"name": "搜索测试", "path": tmp})
    wid = resp.json()["id"]
    client.post(f"/api/workspaces/{wid}/scan")

    db = SessionLocal()
    try:
        chunk_workspace(db, wid)
    finally:
        db.close()
    return wid


def _make_text_response(content):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    return msg


def _make_stream_text(content):
    return iter([("content_chunk", content)])


def _make_stream_tool_call(call_id, name, arguments, content=""):
    events = []
    if content:
        events.append(("content_chunk", content))
    events.append(("tool_calls", [{"id": call_id, "name": name, "arguments": arguments}]))
    return iter(events)


# ─── 搜索工具测试 ───


class TestKeywordSearch:

    def test_finds_matching_content(self):
        """关键词搜索能找到匹配的切块。"""
        wid = _create_indexed_workspace()
        result = keyword_search(wid, "create_engine")
        assert "create_engine" in result
        assert "database.py" in result

    def test_no_match(self):
        """关键词不匹配时返回提示。"""
        wid = _create_indexed_workspace()
        result = keyword_search(wid, "nonexistent_function_xyz")
        assert "未找到" in result

    def test_case_insensitive(self):
        """搜索不区分大小写。"""
        wid = _create_indexed_workspace()
        result = keyword_search(wid, "FASTAPI")
        assert "FastAPI" in result or "fastapi" in result.lower()


class TestCreateSearchTools:

    def test_has_two_tools(self):
        registry = create_search_tools()
        tools = registry.list_all()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"semantic_search", "keyword_search"}


# ─── SearchAgent 测试（mock LLM） ───


class TestSearchAgent:

    def test_has_correct_tools(self):
        agent = SearchAgent()
        names = {t.name for t in agent.tools.list_all()}
        assert names == {"semantic_search", "keyword_search"}
        assert agent.name == "search_agent"

    @patch("app.agents.base.chat_completion_with_tools")
    def test_search_then_answer(self, mock_llm):
        """SearchAgent 调搜索工具后回答。"""
        wid = _create_indexed_workspace()

        # 第 1 轮：LLM 要调 keyword_search
        tc = MagicMock()
        tc.id = "call_001"
        tc.function = MagicMock()
        tc.function.name = "keyword_search"
        tc.function.arguments = f'{{"workspace_id": {wid}, "keyword": "create_engine"}}'

        call1 = MagicMock()
        call1.content = None
        call1.tool_calls = [tc]

        # 第 2 轮：LLM 给出最终回答
        call2 = _make_text_response("database.py 里用 create_engine 连接了数据库。")

        mock_llm.side_effect = [call1, call2]

        agent = SearchAgent()
        result = agent.run("哪里用了 create_engine", context={"workspace_id": wid})

        assert result.status == "success"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "keyword_search"

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_run_with_events_streams(self, mock_stream):
        """run_with_events 正常流式返回。"""
        wid = _create_indexed_workspace()
        mock_stream.side_effect = [
            _make_stream_tool_call("c1", "keyword_search",
                                   f'{{"workspace_id": {wid}, "keyword": "FastAPI"}}',
                                   content="让我搜索一下"),
            _make_stream_text("main.py 里用了 FastAPI 框架。"),
        ]

        agent = SearchAgent()
        events = list(agent.run_with_events("哪里用了 FastAPI", context={"workspace_id": wid}))

        types = [e[0] for e in events]
        assert "tool_call" in types
        assert "tool_result" in types
        assert "result" in types

        # tool_result 应该包含搜索结果
        tool_result_event = [e for e in events if e[0] == "tool_result"][0]
        assert "FastAPI" in tool_result_event[1]["result"]
