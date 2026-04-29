"""向量存储服务测试。

使用真实 ChromaDB（临时目录），测试索引和搜索功能。
"""

import os
import tempfile
from unittest.mock import patch

from app.services.vector_store import index_chunks, search, delete_collection, get_chroma_client


# 所有测试用临时目录作为 ChromaDB 存储，避免污染真实数据
_test_chroma_dir = tempfile.mkdtemp()


def _patch_chroma_dir():
    """让 ChromaDB 使用临时目录。"""
    return patch("app.services.vector_store.get_chroma_client", side_effect=_make_test_client)


# 用独立的测试客户端，不污染全局单例
_test_client = None


def _make_test_client():
    global _test_client
    if _test_client is None:
        import chromadb
        _test_client = chromadb.PersistentClient(path=_test_chroma_dir)
    return _test_client


def _sample_chunks(workspace_id=1):
    """生成测试用的切块数据。"""
    return [
        {"id": 1, "content": "from fastapi import FastAPI\napp = FastAPI(title='Demo')",
         "file_id": 10, "filename": "main.py", "chunk_index": 0},
        {"id": 2, "content": "def create_app():\n    return FastAPI()\n\napp = create_app()",
         "file_id": 10, "filename": "main.py", "chunk_index": 1},
        {"id": 3, "content": "from sqlalchemy import create_engine\nengine = create_engine('sqlite:///db.sqlite')",
         "file_id": 11, "filename": "database.py", "chunk_index": 0},
        {"id": 4, "content": "# 项目说明\n这是一个 FastAPI 项目，提供 REST API 服务。",
         "file_id": 12, "filename": "readme.md", "chunk_index": 0},
        {"id": 5, "content": "debug: true\nport: 8000\nlog_level: INFO\ndatabase_url: sqlite:///db.sqlite",
         "file_id": 13, "filename": "config.yaml", "chunk_index": 0},
    ]


class TestIndexChunks:

    @_patch_chroma_dir()
    def test_index_success(self, _mock):
        """索引切块成功。"""
        chunks = _sample_chunks()
        count = index_chunks(workspace_id=100, chunks=chunks)
        assert count == 5

    @_patch_chroma_dir()
    def test_index_empty(self, _mock):
        """空列表索引返回 0。"""
        count = index_chunks(workspace_id=101, chunks=[])
        assert count == 0

    @_patch_chroma_dir()
    def test_index_idempotent(self, _mock):
        """重复索引是幂等的（upsert）。"""
        chunks = _sample_chunks()
        index_chunks(workspace_id=102, chunks=chunks)
        index_chunks(workspace_id=102, chunks=chunks)

        # 搜索应该只返回不重复的结果
        results = search(workspace_id=102, query="FastAPI", top_k=10)
        assert len(results) <= 5


class TestSearch:

    @_patch_chroma_dir()
    def test_semantic_search(self, _mock):
        """语义搜索能找到相关内容。"""
        chunks = _sample_chunks()
        index_chunks(workspace_id=200, chunks=chunks)

        # 搜索 "sqlalchemy database engine" 应该找到 database.py
        results = search(workspace_id=200, query="sqlalchemy database engine", top_k=3)

        assert len(results) > 0
        filenames = [r["filename"] for r in results]
        assert "database.py" in filenames

    @_patch_chroma_dir()
    def test_search_returns_metadata(self, _mock):
        """搜索结果包含来源信息。"""
        chunks = _sample_chunks()
        index_chunks(workspace_id=201, chunks=chunks)

        results = search(workspace_id=201, query="FastAPI", top_k=1)

        assert len(results) == 1
        result = results[0]
        assert "content" in result
        assert "filename" in result
        assert "file_id" in result
        assert "chunk_index" in result
        assert "distance" in result
        assert isinstance(result["distance"], float)

    @_patch_chroma_dir()
    def test_search_no_index(self, _mock):
        """工作区没有索引时返回空列表。"""
        results = search(workspace_id=999, query="anything")
        assert results == []

    @_patch_chroma_dir()
    def test_search_top_k(self, _mock):
        """top_k 限制返回数量。"""
        chunks = _sample_chunks()
        index_chunks(workspace_id=202, chunks=chunks)

        results = search(workspace_id=202, query="test", top_k=2)
        assert len(results) <= 2


class TestDeleteCollection:

    @_patch_chroma_dir()
    def test_delete_existing(self, _mock):
        """删除存在的索引。"""
        chunks = _sample_chunks()
        index_chunks(workspace_id=300, chunks=chunks)

        # 搜索有结果
        assert len(search(workspace_id=300, query="FastAPI")) > 0

        # 删除后搜索无结果
        delete_collection(workspace_id=300)
        assert search(workspace_id=300, query="FastAPI") == []

    @_patch_chroma_dir()
    def test_delete_nonexistent(self, _mock):
        """删除不存在的索引不报错。"""
        delete_collection(workspace_id=998)  # 不应该抛异常
