"""文件工具 — 提供给 FileAgent 使用。

包含 3 个工具：
  - list_files: 列出工作区文件
  - read_file: 读取文件内容
  - get_file_info: 获取文件元信息

工具函数在 Agent 循环中被调用，不在 FastAPI 请求上下文里，
所以用 SessionLocal() 手动创建数据库连接。
"""

import os

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.file import File
from app.models.workspace import Workspace
from app.tools.registry import Tool, ToolRegistry


def list_files(workspace_id: int) -> str:
    """列出工作区中的所有文件。"""
    db = SessionLocal()
    try:
        workspace = db.get(Workspace, workspace_id)
        if not workspace:
            return f"Error: workspace {workspace_id} not found"

        files = (
            db.query(File)
            .filter(File.workspace_id == workspace_id)
            .order_by(File.filename)
            .all()
        )

        if not files:
            return "This workspace has no files yet — run a scan first."

        lines = [f'Workspace "{workspace.name}" — {len(files)} files:\n']
        for f in files:
            size = f"{f.size_bytes / 1024:.1f}KB" if f.size_bytes >= 1024 else f"{f.size_bytes}B"
            lines.append(f"  id={f.id}  {f.filename}  ({f.file_type}, {size})")
        return "\n".join(lines)
    finally:
        db.close()


def read_file(file_id: int) -> str:
    """读取文件内容（最大 50KB）。"""
    db = SessionLocal()
    try:
        file = db.get(File, file_id)
        if not file:
            return f"Error: file {file_id} not found"

        workspace = db.get(Workspace, file.workspace_id)
        if workspace:
            real_path = os.path.realpath(file.filepath)
            workspace_path = os.path.realpath(workspace.path)
            if not real_path.startswith(workspace_path + os.sep) and real_path != workspace_path:
                return "Error: file path is not inside the workspace"

        if not os.path.exists(file.filepath):
            return f"Error: file does not exist on disk: {file.filepath}"

        try:
            with open(file.filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(get_settings().max_file_read_size)
        except OSError as e:
            return f"Error: failed to read file: {e}"

        header = f"file: {file.filename} (id={file.id})\npath: {file.filepath}\n"
        if os.path.getsize(file.filepath) > get_settings().max_file_read_size:
            header += f"(truncated to first {get_settings().max_file_read_size // 1024}KB)\n"
        return f"{header}\n{content}"
    finally:
        db.close()


def get_file_info(file_id: int) -> str:
    """获取文件的详细元信息。"""
    db = SessionLocal()
    try:
        file = db.get(File, file_id)
        if not file:
            return f"Error: file {file_id} not found"

        size = f"{file.size_bytes / 1024:.1f}KB" if file.size_bytes >= 1024 else f"{file.size_bytes}B"
        return (
            f"name: {file.filename}\n"
            f"path: {file.filepath}\n"
            f"type: {file.file_type}\n"
            f"size: {size}\n"
            f"status: {file.status}\n"
            f"workspace_id: {file.workspace_id}"
        )
    finally:
        db.close()


def create_file_tools() -> ToolRegistry:
    """创建包含文件工具的 ToolRegistry，供 FileAgent 使用。"""
    registry = ToolRegistry()

    registry.register(Tool(
        name="list_files",
        description="List every file in the given workspace. Returns id, name, type and size.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
        },
        function=list_files,
    ))

    registry.register(Tool(
        name="read_file",
        description="Read a file's text content. Use list_files first to get the id.",
        parameters={
            "file_id": {"type": "integer", "description": "file ID (from list_files)"},
        },
        function=read_file,
    ))

    registry.register(Tool(
        name="get_file_info",
        description="Get a file's metadata (name, path, type, size, status).",
        parameters={
            "file_id": {"type": "integer", "description": "file ID"},
        },
        function=get_file_info,
    ))

    return registry
