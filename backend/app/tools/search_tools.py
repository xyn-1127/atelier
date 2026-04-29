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
        return "未找到相关内容。请确认工作区已建立索引（调用建立索引功能）。"

    lines = [f"找到 {len(results)} 条相关结果：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"--- 结果 {i} ---")
        lines.append(f"来源: {r['filename']} (文件ID={r['file_id']}, 第{r['chunk_index']}块)")
        lines.append(f"相关度: {1 - r['distance']:.2f}")  # 距离越小越相关，转成相关度
        lines.append(f"内容:\n{r['content'][:300]}")
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
            return f"未找到包含 \"{keyword}\" 的内容。"

        lines = [f"找到 {len(results)} 条包含 \"{keyword}\" 的结果：\n"]
        for i, (chunk, filename) in enumerate(results, 1):
            # 截取关键词附近的上下文
            content = chunk.content
            idx = content.lower().find(keyword.lower())
            start = max(0, idx - 50)
            end = min(len(content), idx + len(keyword) + 50)
            context = content[start:end]
            if start > 0:
                context = "..." + context
            if end < len(content):
                context = context + "..."

            lines.append(f"--- 结果 {i} ---")
            lines.append(f"来源: {filename} (文件ID={chunk.file_id}, 第{chunk.chunk_index}块)")
            lines.append(f"匹配上下文: {context}")
            lines.append("")
        return "\n".join(lines)
    finally:
        db.close()


def create_search_tools() -> ToolRegistry:
    """创建包含搜索工具的 ToolRegistry，供 SearchAgent 使用。"""
    registry = ToolRegistry()

    registry.register(Tool(
        name="semantic_search",
        description="语义搜索：根据自然语言描述，在工作区中找到语义最相关的文件片段。适合用自然语言提问。",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
            "query": {"type": "string", "description": "搜索查询，用自然语言描述想找的内容"},
            "top_k": {"type": "integer", "description": "返回结果数量", "required": False},
        },
        function=semantic_search,
    ))

    registry.register(Tool(
        name="keyword_search",
        description="关键词搜索：精确匹配文件中的关键词（函数名、变量名、类名等）。",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
            "keyword": {"type": "string", "description": "要搜索的关键词"},
        },
        function=keyword_search,
    ))

    return registry
