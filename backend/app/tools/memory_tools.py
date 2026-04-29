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
        return f'Memory saved: "{key}" (id={m.id})'
    finally:
        db.close()


def recall_memory(workspace_id: int, query: str = "") -> str:
    """查询工作区记忆。query 为空则列出全部。"""
    db = SessionLocal()
    try:
        memories = _recall_memories(db, workspace_id)
        if not memories:
            return "No memories yet for this workspace."

        if query:
            query_lower = query.lower()
            memories = [m for m in memories
                        if query_lower in m.key.lower() or query_lower in m.content.lower()]
            if not memories:
                return f'No memories matching "{query}".'

        return format_memories_for_prompt(memories)
    finally:
        db.close()


def create_memory_tools() -> ToolRegistry:
    """创建记忆工具集。"""
    registry = ToolRegistry()

    registry.register(Tool(
        name="save_memory",
        description="Save a workspace-level memory (persists across chats). Use for key conclusions, project structure, stack, entry points. Same key overwrites.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
            "key": {"type": "string", "description": "short identifier — e.g. project_structure, tech_stack, entry_file"},
            "content": {"type": "string", "description": "the memory content — keep it short, under ~200 chars"},
        },
        function=save_memory,
    ))

    registry.register(Tool(
        name="recall_memory",
        description="Recall stored workspace memory. Pass an empty query to list all memories.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
            "query": {"type": "string", "description": "optional substring filter on key or content", "required": False},
        },
        function=recall_memory,
    ))

    return registry
