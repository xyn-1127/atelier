"""笔记 CRUD 服务。"""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.note import Note
from app.models.workspace import Workspace


def create_note(db: Session, workspace_id: int, title: str, content: str = "") -> Note:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise NotFoundError("工作区不存在")

    note = Note(workspace_id=workspace_id, title=title, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(db: Session, workspace_id: int) -> list[Note]:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise NotFoundError("工作区不存在")

    return (
        db.query(Note)
        .filter(Note.workspace_id == workspace_id)
        .order_by(Note.updated_at.desc())
        .all()
    )


def get_note(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if not note:
        raise NotFoundError("笔记不存在")
    return note


def update_note(db: Session, note_id: int, title: str | None = None, content: str | None = None) -> Note:
    note = get_note(db, note_id)

    if title is not None:
        note.title = title
    if content is not None:
        note.content = content

    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note_id: int) -> None:
    note = get_note(db, note_id)
    db.delete(note)
    db.commit()
