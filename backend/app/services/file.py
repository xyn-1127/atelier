import os

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, BadRequestError
from app.models.file import File
from app.models.workspace import Workspace


def list_files(db: Session, workspace_id: int) -> list[File]:
    return (
        db.query(File)
        .filter(File.workspace_id == workspace_id)
        .order_by(File.filename)
        .all()
    )


def get_file(db: Session, file_id: int) -> File:
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise NotFoundError("文件不存在")
    return file


def _check_path_in_workspace(file: File, db: Session) -> None:
    """安全检查：文件的真实路径必须在工作区目录内。防止 symlink 穿越。"""
    workspace = db.get(Workspace, file.workspace_id)
    if not workspace:
        raise NotFoundError("所属工作区不存在")

    real_path = os.path.realpath(file.filepath)
    workspace_path = os.path.realpath(workspace.path)
    if not real_path.startswith(workspace_path + os.sep) and real_path != workspace_path:
        raise BadRequestError("文件路径不在工作区目录内")


def get_file_content(db: Session, file_id: int) -> dict:
    file = get_file(db, file_id)

    _check_path_in_workspace(file, db)

    if not os.path.isfile(file.filepath):
        raise NotFoundError("文件在磁盘上不存在")

    try:
        with open(file.filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(get_settings().max_file_read_size)
    except OSError:
        raise NotFoundError("读取文件失败")

    return {
        "id": file.id,
        "filename": file.filename,
        "file_type": file.file_type,
        "content": content,
    }
