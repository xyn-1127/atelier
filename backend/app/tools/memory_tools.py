"""记忆工具 — 让 Agent 能主动存取工作区记忆。

save_memory: 把重要信息存为长期记忆（跨对话可用）
recall_memory: 查询已有记忆
"""

from app.db.session import SessionLocal
from app.services.memory import (
    save_memory as _save_memory,
    recall_memories as _recall_memories,
    format_memories_for_prompt,
)
from app.tools.registry import Tool, ToolRegistry


def save_memory(workspace_id: int, key: str, content: str) -> str:
    """存一条工作区记忆。同 key 覆盖旧内容。"""
    db = SessionLocal()
    try:
        m = _save_memory(db, workspace_id, "conversation_insight", key, content)
        return f"记忆已保存：「{key}」(id={m.id})"
    finally:
        db.close()


def recall_memory(workspace_id: int, query: str = "") -> str:
    """查询工作区记忆。query 为空则列出全部。"""
    db = SessionLocal()
    try:
        memories = _recall_memories(db, workspace_id)
        if not memories:
            return "该工作区暂无记忆。"

        if query:
            # 按 key 或 content 模糊匹配
            query_lower = query.lower()
            memories = [m for m in memories
                        if query_lower in m.key.lower() or query_lower in m.content.lower()]
            if not memories:
                return f"未找到与 \"{query}\" 相关的记忆。"

        return format_memories_for_prompt(memories)
    finally:
        db.close()


def create_memory_tools() -> ToolRegistry:
    """创建记忆工具集。"""
    registry = ToolRegistry()

    registry.register(Tool(
        name="save_memory",
        description="保存一条工作区记忆（跨对话可用）。用于记住重要的分析结论、项目特征等。同 key 会覆盖旧内容。",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
            "key": {"type": "string", "description": "记忆标识，如 project_structure、tech_stack、entry_file"},
            "content": {"type": "string", "description": "记忆内容（简短，不超过 200 字）"},
        },
        function=save_memory,
    ))

    registry.register(Tool(
        name="recall_memory",
        description="查询工作区的已有记忆。不传 query 则列出全部记忆。",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
            "query": {"type": "string", "description": "搜索关键词（可选，为空列出全部）", "required": False},
        },
        function=recall_memory,
    ))

    return registry
