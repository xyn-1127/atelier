import os

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.file import File
from app.models.workspace import Workspace

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".html", ".css",
    ".cfg", ".ini", ".sh", ".sql", ".csv",
}

SKIP_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules",
    ".pytest_cache", "dist", ".next", ".idea", ".vscode",
}



def scan_workspace(db: Session, workspace: Workspace) -> list[File]:
    # 清空旧的扫描记录，重新扫描
    db.query(File).filter(File.workspace_id == workspace.id).delete()

    files = []

    workspace_real = os.path.realpath(workspace.path)

    for root, dirs, filenames in os.walk(workspace.path, followlinks=False):
        # 跳过不需要的目录和 symlink 目录
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(".")
                   and not os.path.islink(os.path.join(root, d))]

        for filename in filenames:
            filepath = os.path.join(root, filename)

            # 跳过 symlink 文件（防止路径穿越）
            if os.path.islink(filepath):
                continue

            # 确认真实路径在工作区内
            real = os.path.realpath(filepath)
            if not real.startswith(workspace_real + os.sep):
                continue

            ext = os.path.splitext(filename)[1].lower()

            if ext not in SUPPORTED_EXTENSIONS:
                continue

            try:
                size = os.path.getsize(filepath)
            except OSError:
                continue

            if size > get_settings().max_scan_file_size:
                continue

            file = File(
                workspace_id=workspace.id,
                filename=filename,
                filepath=filepath,
                file_type=ext.lstrip("."),
                size_bytes=size,
                status="scanned",
            )
            files.append(file)

    db.add_all(files)
    db.commit()
    return files