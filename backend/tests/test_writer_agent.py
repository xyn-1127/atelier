"""WriterAgent 测试。"""

import tempfile
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.agents.writer_agent import WriterAgent
from app.tools.writer_tools import save_note, set_current_content, create_writer_tools
from app.db.session import SessionLocal
from app.models.note import Note

client = TestClient(app)


def _create_workspace():
    tmp = tempfile.mkdtemp()
    resp = client.post("/api/workspaces", json={"name": "写作测试", "path": tmp})
    return resp.json()["id"]


# ─── save_note 工具测试 ───


class TestSaveNote:

    def test_save_success(self):
        wid = _create_workspace()
        # 模拟 Agent 已经输出了内容
        set_current_content("# 总结\n\n这是一个好项目。")
        result = save_note(wid, "项目总结")

        assert "已保存" in result
        assert "项目总结" in result

        db = SessionLocal()
        try:
            notes = db.query(Note).filter(Note.workspace_id == wid).all()
            assert len(notes) == 1
            assert notes[0].title == "项目总结"
            assert "# 总结" in notes[0].content
        finally:
            db.close()

    def test_save_empty_content(self):
        """没有内容时不能保存。"""
        wid = _create_workspace()
        set_current_content("")
        result = save_note(wid, "空笔记")
        assert "没有可保存的内容" in result

    def test_save_workspace_not_found(self):
        set_current_content("some content")
        result = save_note(99999, "标题")
        assert "不存在" in result


class TestCreateWriterTools:

    def test_has_search_memory_and_note_tools(self):
        """WriterAgent 有搜索 + 记忆 + 保存笔记。"""
        registry = create_writer_tools()
        names = {t.name for t in registry.list_all()}
        assert {"semantic_search", "keyword_search", "save_note"} <= names
        assert {"save_memory", "recall_memory"} <= names


# ─── WriterAgent 测试（mock LLM） ───


class TestWriterAgent:

    def test_has_correct_config(self):
        agent = WriterAgent()
        assert agent.name == "writer_agent"
        names = {t.name for t in agent.tools.list_all()}
        assert "save_note" in names
        assert "semantic_search" in names

    @patch("app.agents.base.chat_completion_with_tools")
    def test_write_and_save_flow(self, mock_llm):
        """WriterAgent 生成内容 → 保存笔记（content 自动获取）。"""
        wid = _create_workspace()

        # 第 1 轮：LLM 输出内容 + 调 save_note（只传 title）
        tc = MagicMock()
        tc.id = "c1"
        tc.function = MagicMock()
        tc.function.name = "save_note"
        tc.function.arguments = f'{{"workspace_id": {wid}, "title": "项目总结"}}'
        call1 = MagicMock()
        call1.content = "# 项目总结\n\n这是一个 FastAPI 项目。"
        call1.tool_calls = [tc]

        # 第 2 轮：回答
        call2 = MagicMock()
        call2.content = "已为您生成并保存了项目总结。"
        call2.tool_calls = None

        mock_llm.side_effect = [call1, call2]

        agent = WriterAgent()
        result = agent.run("帮我写一份项目总结并保存", context={"workspace_id": wid})

        assert result.status == "success"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "save_note"
        assert "已保存" in result.tool_calls[0].result

        # 数据库中确实有笔记
        db = SessionLocal()
        try:
            notes = db.query(Note).filter(Note.workspace_id == wid).all()
            assert any(n.title == "项目总结" for n in notes)
        finally:
            db.close()
