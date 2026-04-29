"""写作工具 — 提供给 WriterAgent 使用。

save_note 只需要 workspace_id 和 title，content 从 Agent 当前轮
已流式输出的 content_buffer 自动获取。这样 LLM 不需要重复生成
几千字的笔记内容作为工具参数，只需要生成一个标题。
"""

import threading

from app.db.session import SessionLocal
from app.models.note import Note
from app.models.workspace import Workspace
from app.tools.registry import Tool, ToolRegistry
from app.tools.search_tools import create_search_tools

# 线程安全地存储当前 Agent 轮次的 content_buffer
# Agent 执行时写入，save_note 读取
_current_content = threading.local()


def set_current_content(content: str) -> None:
    """由 BaseAgent 在工具执行前调用，存入当前轮的 content_buffer。"""
    _current_content.value = content


def get_current_content() -> str:
    """由 save_note 调用，获取当前轮 Agent 已输出的内容。"""
    return getattr(_current_content, "value", "")


def save_note(workspace_id: int, title: str) -> str:
    """保存笔记。内容自动使用 Agent 本轮已生成的文本，无需手动传入。"""
    content = get_current_content()
    if not content.strip():
        return "错误：没有可保存的内容，请先生成文档再调用保存。"

    db = SessionLocal()
    try:
        workspace = db.get(Workspace, workspace_id)
        if not workspace:
            return f"错误：工作区 {workspace_id} 不存在"

        note = Note(workspace_id=workspace_id, title=title, content=content)
        db.add(note)
        db.commit()
        db.refresh(note)

        return f"笔记已保存：「{title}」(id={note.id}，{len(content)}字)"
    finally:
        db.close()


def create_writer_tools() -> ToolRegistry:
    """创建 WriterAgent 的工具集：搜索 + 记忆 + 保存笔记。"""
    from app.tools.memory_tools import create_memory_tools
    registry = create_search_tools()
    # 加记忆工具
    for tool in create_memory_tools().list_all():
        registry.register(tool)

    registry.register(Tool(
        name="save_note",
        description="保存笔记。内容自动使用你本轮已输出的文本，只需提供标题。先输出完整文档内容，再调用此工具保存。",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
            "title": {"type": "string", "description": "笔记标题"},
        },
        function=save_note,
    ))

    return registry
