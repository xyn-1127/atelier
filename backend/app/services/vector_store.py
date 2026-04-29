"""向量存储服务 — ChromaDB 封装。

ChromaDB 是一个向量数据库，核心功能：
1. 把文本转成向量（嵌入/embedding）并存储
2. 给一段查询文本，找出最相似的已存储文本

本模块封装了三个操作：
- index_chunks: 把切块存入 ChromaDB（向量化 + 存储）
- search: 语义搜索（查询文本 → 找相似切块）
- delete_collection: 删除某工作区的所有索引

关于嵌入模型：
  使用 Chroma 内置的 all-MiniLM-L6-v2 模型（sentence-transformers）。
  - 不需要 API 调用（本地运行，免费）
  - 首次使用时自动下载（约 80MB），之后缓存在本地
  - 对代码和中英文文档都有不错的效果

数据组织：
  每个工作区一个 collection（类似数据库的表）：
    collection 名: "workspace_1", "workspace_2", ...
    每条记录: id（唯一标识）、文本内容、向量（自动生成）、metadata（来源信息）
"""

import logging

import chromadb

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ChromaDB 客户端单例（整个进程共用一个）
_chroma_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """获取 ChromaDB 持久化客户端（单例）。

    持久化 = 数据存在磁盘上，重启后还在。
    目录由 .env 的 CHROMA_PERSIST_DIR 配置，默认 ./chroma_data。
    """
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        logger.info("ChromaDB client initialized, persist_dir=%s", settings.chroma_persist_dir)
    return _chroma_client


def _collection_name(workspace_id: int) -> str:
    """生成 collection 名称。每个工作区一个 collection。"""
    return f"workspace_{workspace_id}"


def index_chunks(workspace_id: int, chunks: list[dict]) -> int:
    """把切块向量化并存入 ChromaDB。

    参数:
        workspace_id: 工作区 ID
        chunks: 切块列表，每个元素格式：
            {"id": int, "content": str, "file_id": int, "filename": str, "chunk_index": int}

    返回:
        成功索引的切块数量

    流程:
        1. 获取或创建该工作区的 collection
        2. 把切块的文本内容交给 Chroma（Chroma 自动调嵌入模型转向量）
        3. 同时存储 metadata（file_id、filename、chunk_index），搜索时返回来源信息
    """
    if not chunks:
        return 0

    client = get_chroma_client()

    # get_or_create: 存在就获取，不存在就创建
    collection = client.get_or_create_collection(name=_collection_name(workspace_id))

    # 准备数据：Chroma 需要 ids、documents、metadatas 三个平行列表
    ids = [f"chunk_{c['id']}" for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [
        {
            "file_id": c["file_id"],
            "filename": c["filename"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    # upsert: 存在就更新，不存在就插入（幂等操作）
    # Chroma 内部自动调用嵌入模型把 documents 转成向量
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    logger.info("Indexed %d chunks for workspace %d", len(chunks), workspace_id)
    return len(chunks)


def search(workspace_id: int, query: str, top_k: int = 5) -> list[dict]:
    """语义搜索：找出与查询最相关的切块。

    参数:
        workspace_id: 工作区 ID
        query: 查询文本，如"数据库怎么连接"
        top_k: 返回最相关的前 N 条

    返回:
        结果列表，每条包含：
        {
            "content": "匹配的文本内容",
            "filename": "来源文件名",
            "file_id": 文件ID,
            "chunk_index": 块序号,
            "distance": 距离（越小越相关）,
        }

    原理:
        1. Chroma 把 query 转成向量
        2. 在 collection 里找距离最近的 top_k 个向量
        3. 返回对应的文本和 metadata
    """
    client = get_chroma_client()

    try:
        collection = client.get_collection(name=_collection_name(workspace_id))
    except Exception:
        # collection 不存在 = 工作区还没建索引
        logger.warning("No index found for workspace %d", workspace_id)
        return []

    # query: Chroma 自动把查询文本转向量，找最近邻
    results = collection.query(query_texts=[query], n_results=top_k)

    # Chroma 返回格式是嵌套列表（支持批量查询），我们只查了一条，取 [0]
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    output = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        output.append({
            "content": doc,
            "filename": meta.get("filename", ""),
            "file_id": meta.get("file_id", 0),
            "chunk_index": meta.get("chunk_index", 0),
            "distance": round(dist, 4),
        })

    logger.info("Search workspace %d for '%s': %d results", workspace_id, query[:50], len(output))
    return output


def delete_collection(workspace_id: int) -> None:
    """删除某工作区的向量索引。

    用于重建索引前清空旧数据，或删除工作区时清理。
    """
    client = get_chroma_client()
    name = _collection_name(workspace_id)

    try:
        client.delete_collection(name=name)
        logger.info("Deleted collection '%s'", name)
    except Exception:
        # collection 不存在也没关系
        logger.info("Collection '%s' does not exist, skip delete", name)
