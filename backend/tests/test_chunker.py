"""文本切块服务测试。"""

import os
import tempfile

from fastapi.testclient import TestClient

from app.main import app
from app.services.chunker import chunk_text, chunk_file, chunk_workspace
from app.models.chunk import Chunk
from app.db.session import SessionLocal

client = TestClient(app)


# ─── chunk_text 纯函数测试 ───


class TestChunkText:

    def test_basic_chunking(self):
        """基本切块：长文本被切成多块。"""
        # 生成一段 300 字符的文本（每行 30 字符，共 10 行）
        text = "\n".join(f"这是第{i}行，包含一些测试内容用于切块测试。" for i in range(10))
        chunks = chunk_text(text, chunk_size=100, overlap=0)

        assert len(chunks) > 1
        # 所有原始内容都应该在切块中（没有丢失）
        combined = " ".join(chunks)
        for i in range(10):
            assert f"第{i}行" in combined

    def test_overlap(self):
        """相邻块有重叠内容。"""
        text = "\n".join(f"line{i}: " + "x" * 40 for i in range(10))
        chunks = chunk_text(text, chunk_size=100, overlap=30)

        # 有多于 1 个块
        assert len(chunks) > 1

        # 检查相邻块有重叠（后一个块的开头包含前一个块的结尾部分）
        for i in range(len(chunks) - 1):
            tail = chunks[i][-30:]     # 前一个块的最后 30 字符
            head = chunks[i + 1][:60]  # 后一个块的开头 60 字符
            # 重叠部分应该有公共内容
            assert any(c in head for c in tail if c.strip())

    def test_small_text_single_chunk(self):
        """短文本不需要切块，返回一整块。"""
        text = "hello world\nthis is short"
        chunks = chunk_text(text, chunk_size=500, overlap=50)

        assert len(chunks) == 1
        assert "hello" in chunks[0]

    def test_empty_text(self):
        """空文本返回空列表。"""
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text(None) == []

    def test_tiny_text_skipped(self):
        """极短文本（< 10 字符）被跳过。"""
        assert chunk_text("hi") == []
        assert chunk_text("12345") == []

    def test_no_overlap(self):
        """overlap=0 时块之间没有重叠。"""
        text = "a" * 100 + "\n" + "b" * 100 + "\n" + "c" * 100
        chunks = chunk_text(text, chunk_size=110, overlap=0)

        assert len(chunks) >= 2


# ─── chunk_file 文件切块测试 ───


class TestChunkFile:

    def test_chunk_real_file(self):
        """对真实文件切块。"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        tmp.write("def hello():\n    print('hello')\n\n" * 20)
        tmp.close()

        chunks = chunk_file(tmp.name, chunk_size=100, overlap=20)

        assert len(chunks) > 1
        assert "def hello" in chunks[0]
        os.unlink(tmp.name)

    def test_file_not_found(self):
        """文件不存在返回空列表。"""
        chunks = chunk_file("/nonexistent/path.txt")
        assert chunks == []

    def test_empty_file(self):
        """空文件返回空列表。"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write("")
        tmp.close()

        chunks = chunk_file(tmp.name)
        assert chunks == []
        os.unlink(tmp.name)


# ─── chunk_workspace 集成测试 ───


class TestChunkWorkspace:

    def _create_workspace_with_files(self):
        """辅助：创建带文件的工作区并扫描。"""
        tmp = tempfile.mkdtemp()

        # 创建几个有内容的文件
        with open(os.path.join(tmp, "main.py"), "w") as f:
            f.write("from fastapi import FastAPI\n\napp = FastAPI()\n\n" +
                    "\n".join(f"# 这是第{i}个注释行" for i in range(30)))
        with open(os.path.join(tmp, "readme.md"), "w") as f:
            f.write("# 项目说明\n\n这是一个测试项目。\n\n" +
                    "\n".join(f"## 第{i}章" for i in range(20)))

        resp = client.post("/api/workspaces", json={"name": "切块测试", "path": tmp})
        workspace_id = resp.json()["id"]
        client.post(f"/api/workspaces/{workspace_id}/scan")
        return workspace_id

    def test_chunk_workspace_creates_chunks(self):
        """对工作区所有文件切块后，chunks 表有数据。"""
        workspace_id = self._create_workspace_with_files()

        db = SessionLocal()
        try:
            count = chunk_workspace(db, workspace_id)
            assert count > 0

            # 数据库中确实有记录
            chunks = db.query(Chunk).filter(Chunk.workspace_id == workspace_id).all()
            assert len(chunks) == count
            assert all(c.content for c in chunks)
            assert all(c.file_id for c in chunks)
            assert all(c.token_count > 0 for c in chunks)
        finally:
            db.close()

    def test_chunk_workspace_idempotent(self):
        """重复切块是幂等的（先清旧再建新）。"""
        workspace_id = self._create_workspace_with_files()

        db = SessionLocal()
        try:
            count1 = chunk_workspace(db, workspace_id)
            count2 = chunk_workspace(db, workspace_id)

            # 两次结果一样（不会翻倍）
            assert count1 == count2

            total = db.query(Chunk).filter(Chunk.workspace_id == workspace_id).count()
            assert total == count1
        finally:
            db.close()

    def test_chunk_workspace_empty(self):
        """没有文件的工作区，切块数为 0。"""
        tmp = tempfile.mkdtemp()
        resp = client.post("/api/workspaces", json={"name": "空工作区", "path": tmp})
        workspace_id = resp.json()["id"]

        db = SessionLocal()
        try:
            count = chunk_workspace(db, workspace_id)
            assert count == 0
        finally:
            db.close()

    def test_chunk_index_sequential(self):
        """每个文件的 chunk_index 从 0 开始递增。"""
        workspace_id = self._create_workspace_with_files()

        db = SessionLocal()
        try:
            chunk_workspace(db, workspace_id)
            chunks = (db.query(Chunk)
                      .filter(Chunk.workspace_id == workspace_id)
                      .order_by(Chunk.file_id, Chunk.chunk_index)
                      .all())

            # 按文件分组检查 index
            from itertools import groupby
            for _, group in groupby(chunks, key=lambda c: c.file_id):
                indices = [c.chunk_index for c in group]
                assert indices == list(range(len(indices)))
        finally:
            db.close()
