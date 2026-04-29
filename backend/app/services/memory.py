"""记忆存取服务。

长期记忆存储在 memories 表中，以 workspace 为单位。
同一个 workspace + key 的记忆只保留一条（覆盖更新）。
"""

import logging

from sqlalchemy.orm import Session

from app.models.memory import Memory

logger = logging.getLogger(__name__)


def save_memory(db: Session, workspace_id: int, category: str, key: str, content: str) -> Memory:
    """存入或更新一条记忆。同 workspace + key 覆盖。"""
    existing = (
        db.query(Memory)
        .filter(Memory.workspace_id == workspace_id, Memory.key == key)
        .first()
    )

    if existing:
        existing.content = content
        existing.category = category
        db.commit()
        db.refresh(existing)
        logger.info("Memory updated: workspace=%d key='%s'", workspace_id, key)
        return existing

    memory = Memory(workspace_id=workspace_id, category=category, key=key, content=content)
    db.add(memory)
    db.commit()
    db.refresh(memory)
    logger.info("Memory created: workspace=%d key='%s'", workspace_id, key)
    return memory


def recall_memories(db: Session, workspace_id: int, category: str | None = None) -> list[Memory]:
    """读取工作区的记忆。可按 category 筛选。"""
    query = db.query(Memory).filter(Memory.workspace_id == workspace_id)
    if category:
        query = query.filter(Memory.category == category)
    return query.order_by(Memory.updated_at.desc()).all()


def recall_by_key(db: Session, workspace_id: int, key: str) -> Memory | None:
    """按 key 精确查找记忆。"""
    return (
        db.query(Memory)
        .filter(Memory.workspace_id == workspace_id, Memory.key == key)
        .first()
    )


def delete_memory(db: Session, memory_id: int) -> None:
    """删除一条记忆。"""
    memory = db.get(Memory, memory_id)
    if memory:
        db.delete(memory)
        db.commit()


def format_memories_for_prompt(memories: list[Memory]) -> str:
    """把记忆列表格式化为可注入 prompt 的文本。"""
    if not memories:
        return ""

    lines = []
    for m in memories:
        lines.append(f"[{m.category}] {m.key}: {m.content}")
    return "\n".join(lines)
