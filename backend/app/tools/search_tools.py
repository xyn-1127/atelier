"""搜索工具 — 提供给 SearchAgent 使用。

包含 2 个工具：
  - semantic_search: 语义搜索（基于向量距离，能理解同义词）
  - keyword_search: 关键词搜索（精确匹配，适合搜变量名、函数名）

两种搜索互补：
  "数据库连接怎么写" → 用 semantic_search（找语义相近的代码）
  "create_engine"    → 用 keyword_search（精确找到这个函数名）
"""

from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.file import File
from app.services.vector_store import search as vector_search
from app.tools.registry import Tool, ToolRegistry


def semantic_search(workspace_id: int, query: str, top_k: int = 5) -> str:
    """语义搜索：找出与查询语义最相关的文件片段。

    基于向量距离搜索，能理解"数据库"和"sqlalchemy"是相关的。
    """
    results = vector_search(workspace_id, query, top_k=top_k)

    if not results:
        return "No matches. Make sure the workspace has been indexed."

    lines = [f"Found {len(results)} matches:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"--- match {i} ---")
        lines.append(f"source: {r['filename']} (file_id={r['file_id']}, chunk={r['chunk_index']})")
        lines.append(f"score: {1 - r['distance']:.2f}")
        lines.append(f"content:\n{r['content'][:300]}")
        lines.append("")
    return "\n".join(lines)


def keyword_search(workspace_id: int, keyword: str) -> str:
    """关键词搜索：在切块中精确匹配关键词。

    适合搜索函数名、变量名、类名等精确文本。
    用 SQL LIKE 在 chunks 表中搜索。
    """
    db = SessionLocal()
    try:
        # 在 chunks 表中搜索包含关键词的切块
        results = (
            db.query(Chunk, File.filename)
            .join(File, Chunk.file_id == File.id)
            .filter(Chunk.workspace_id == workspace_id)
            .filter(Chunk.content.ilike(f"%{keyword}%"))
            .limit(10)
            .all()
        )

        if not results:
            return f'No matches for "{keyword}".'

        lines = [f'Found {len(results)} matches for "{keyword}":\n']
        for i, (chunk, filename) in enumerate(results, 1):
            content = chunk.content
            idx = content.lower().find(keyword.lower())
            start = max(0, idx - 50)
            end = min(len(content), idx + len(keyword) + 50)
            context = content[start:end]
            if start > 0:
                context = "..." + context
            if end < len(content):
                context = context + "..."

            lines.append(f"--- match {i} ---")
            lines.append(f"source: {filename} (file_id={chunk.file_id}, chunk={chunk.chunk_index})")
            lines.append(f"context: {context}")
            lines.append("")
        return "\n".join(lines)
    finally:
        db.close()


def create_search_tools() -> ToolRegistry:
    """创建包含搜索工具的 ToolRegistry，供 SearchAgent 使用。"""
    registry = ToolRegistry()

    registry.register(Tool(
        name="semantic_search",
        description="Semantic / vector search over the workspace. Best for natural-language questions.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
            "query": {"type": "string", "description": "what you are looking for, in natural language"},
            "top_k": {"type": "integer", "description": "number of results to return", "required": False},
        },
        function=semantic_search,
    ))

    registry.register(Tool(
        name="keyword_search",
        description="Exact keyword search across the workspace (function names, variable names, etc.).",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
            "keyword": {"type": "string", "description": "the keyword to find"},
        },
        function=keyword_search,
    ))

    return registry
