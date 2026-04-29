import logging
import os
import threading

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, BadRequestError, ConflictError
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate

logger = logging.getLogger(__name__)

# 防止同一 workspace 并发索引
_indexing_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_index_lock(workspace_id: int) -> threading.Lock:
    with _locks_guard:
        if workspace_id not in _indexing_locks:
            _indexing_locks[workspace_id] = threading.Lock()
        return _indexing_locks[workspace_id]


def create_workspace(db: Session, data: WorkspaceCreate) -> Workspace:
    # 路径归一化后去重
    normalized = os.path.realpath(data.path)
    if not os.path.isdir(normalized):
        raise BadRequestError("路径不存在或不可访问")

    existing = db.query(Workspace).filter(Workspace.path == normalized).first()
    if existing:
        raise ConflictError("该路径已被添加为工作区")

    workspace = Workspace(name=data.name, path=normalized, index_status="pending")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    _start_async_index(workspace.id)
    return workspace


def _start_async_index(workspace_id: int) -> None:
    """后台线程执行扫描 + 切块 + 向量化。同一 workspace 互斥。"""
    lock = _get_index_lock(workspace_id)

    def _run():
        if not lock.acquire(blocking=False):
            logger.warning("Workspace %d: indexing already in progress, skipping", workspace_id)
            return

        from app.db.session import SessionLocal
        from app.services.scanner import scan_workspace
        from app.services.indexer import build_index

        db = SessionLocal()
        try:
            workspace = db.get(Workspace, workspace_id)
            if not workspace:
                return

            workspace.index_status = "indexing"
            db.commit()
            logger.info("Workspace %d: async indexing started", workspace_id)

            scan_workspace(db, workspace)
            build_index(db, workspace_id)

            workspace.index_status = "ready"
            db.commit()
            logger.info("Workspace %d: async indexing done", workspace_id)

        except Exception as e:
            logger.error("Workspace %d: async indexing failed: %s", workspace_id, e)
            try:
                workspace = db.get(Workspace, workspace_id)
                if workspace:
                    workspace.index_status = "error"
                    db.commit()
            except Exception:
                pass
        finally:
            lock.release()
            db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def reindex_workspace(db: Session, workspace_id: int) -> None:
    """手动触发重新索引。如果已在索引中则忽略。"""
    workspace = get_workspace(db, workspace_id)
    if workspace.index_status == "indexing":
        return  # 已在进行中，不重复触发
    workspace.index_status = "indexing"
    db.commit()
    _start_async_index(workspace_id)


def list_workspaces(db: Session) -> list[Workspace]:
    return db.query(Workspace).order_by(Workspace.created_at.desc()).all()


def get_workspace(db: Session, workspace_id: int) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise NotFoundError("工作区不存在")
    return workspace


def update_workspace(db: Session, workspace_id: int, data: WorkspaceUpdate) -> Workspace:
    workspace = get_workspace(db, workspace_id)

    if data.name is not None:
        workspace.name = data.name
    if data.status is not None:
        workspace.status = data.status

    db.commit()
    db.refresh(workspace)
    return workspace


def delete_workspace(db: Session, workspace_id: int) -> None:
    """删除工作区及所有关联数据（files/chats/notes/chunks/memories + Chroma）。"""
    from app.models.chunk import Chunk
    from app.models.memory import Memory
    from app.services.vector_store import delete_collection

    workspace = get_workspace(db, workspace_id)

    # 清理不在 cascade 上的二级数据
    db.query(Chunk).filter(Chunk.workspace_id == workspace_id).delete()
    db.query(Memory).filter(Memory.workspace_id == workspace_id).delete()

    # 清理 Chroma 向量索引
    try:
        delete_collection(workspace_id)
    except Exception as e:
        logger.warning("Failed to delete Chroma collection for workspace %d: %s", workspace_id, e)

    db.delete(workspace)  # cascade 删 files/chats/notes
    db.commit()
