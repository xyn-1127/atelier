"""记忆系统测试。"""

import tempfile

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.services.memory import (
    save_memory, recall_memories, recall_by_key, delete_memory, format_memories_for_prompt,
)

client = TestClient(app)


def _create_workspace():
    tmp = tempfile.mkdtemp()
    resp = client.post("/api/workspaces", json={"name": "记忆测试", "path": tmp})
    return resp.json()["id"]


class TestSaveMemory:

    def test_create_new(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            m = save_memory(db, wid, "project_info", "tech_stack", "FastAPI + SQLAlchemy")
            assert m.key == "tech_stack"
            assert m.content == "FastAPI + SQLAlchemy"
        finally:
            db.close()

    def test_upsert_same_key(self):
        """同 key 覆盖，不会有两条。"""
        wid = _create_workspace()
        db = SessionLocal()
        try:
            save_memory(db, wid, "project_info", "entry", "main.py:10")
            save_memory(db, wid, "project_info", "entry", "main.py:28")

            memories = recall_memories(db, wid)
            entry_mems = [m for m in memories if m.key == "entry"]
            assert len(entry_mems) == 1
            assert entry_mems[0].content == "main.py:28"
        finally:
            db.close()

    def test_different_keys(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            save_memory(db, wid, "project_info", "stack", "FastAPI")
            save_memory(db, wid, "user_preference", "language", "中文")

            all_mems = recall_memories(db, wid)
            assert len(all_mems) == 2
        finally:
            db.close()


class TestRecallMemories:

    def test_filter_by_category(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            save_memory(db, wid, "project_info", "stack", "FastAPI")
            save_memory(db, wid, "user_preference", "lang", "中文")

            proj = recall_memories(db, wid, category="project_info")
            assert len(proj) == 1
            assert proj[0].key == "stack"
        finally:
            db.close()

    def test_recall_empty(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            mems = recall_memories(db, wid)
            assert mems == []
        finally:
            db.close()


class TestRecallByKey:

    def test_found(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            save_memory(db, wid, "project_info", "entry", "main.py")
            m = recall_by_key(db, wid, "entry")
            assert m is not None
            assert m.content == "main.py"
        finally:
            db.close()

    def test_not_found(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            m = recall_by_key(db, wid, "nonexistent")
            assert m is None
        finally:
            db.close()


class TestDeleteMemory:

    def test_delete(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            m = save_memory(db, wid, "project_info", "tmp", "temporary")
            delete_memory(db, m.id)
            assert recall_by_key(db, wid, "tmp") is None
        finally:
            db.close()


class TestFormatMemories:

    def test_format(self):
        wid = _create_workspace()
        db = SessionLocal()
        try:
            save_memory(db, wid, "project_info", "stack", "FastAPI")
            save_memory(db, wid, "project_info", "entry", "main.py")
            mems = recall_memories(db, wid)
            text = format_memories_for_prompt(mems)
            assert "stack" in text
            assert "FastAPI" in text
            assert "entry" in text
        finally:
            db.close()

    def test_format_empty(self):
        text = format_memories_for_prompt([])
        assert text == ""
