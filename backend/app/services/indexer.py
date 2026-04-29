"""索引服务 — 组合切块 + 向量化的完整流水线。

调用顺序：
  build_index(db, workspace_id)
    → chunker.chunk_workspace()     切块并存入 chunks 表
    → vector_store.index_chunks()   向量化并存入 ChromaDB

为什么单独一个 indexer 服务？
  chunker 只管切块，vector_store 只管向量存储。
  indexer 把两步串起来，对外提供一个简单的"建索引"接口。
"""

import logging

from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.file import File
from app.services.chunker import chunk_workspace
from app.services.vector_store import index_chunks, delete_collection

logger = logging.getLogger(__name__)


def build_index(db: Session, workspace_id: int) -> dict:
    """为工作区建立完整索引：切块 → 向量化。

    参数:
        db: 数据库 session
        workspace_id: 工作区 ID

    返回:
        {"chunks_count": 总切块数, "status": "ok"}
    """
    # 1. 删除旧的向量索引
    delete_collection(workspace_id)

    # 2. 切块（会清空旧 chunks 并重新写入）
    chunks_count = chunk_workspace(db, workspace_id)

    if chunks_count == 0:
        logger.info("Workspace %d: no chunks to index", workspace_id)
        return {"chunks_count": 0, "status": "ok"}

    # 3. 从数据库读出切块，准备给 ChromaDB
    chunks = (
        db.query(Chunk, File.filename)
        .join(File, Chunk.file_id == File.id)
        .filter(Chunk.workspace_id == workspace_id)
        .all()
    )

    # 转成 vector_store 需要的格式
    chunk_dicts = [
        {
            "id": chunk.id,
            "content": chunk.content,
            "file_id": chunk.file_id,
            "filename": filename,
            "chunk_index": chunk.chunk_index,
        }
        for chunk, filename in chunks
    ]

    # 4. 向量化并存入 ChromaDB
    indexed = index_chunks(workspace_id, chunk_dicts)
    logger.info("Workspace %d: indexed %d chunks", workspace_id, indexed)

    return {"chunks_count": indexed, "status": "ok"}
