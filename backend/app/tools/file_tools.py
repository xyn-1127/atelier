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
            return f"错误：工作区 {workspace_id} 不存在"

        files = (
            db.query(File)
            .filter(File.workspace_id == workspace_id)
            .order_by(File.filename)
            .all()
        )

        if not files:
            return "该工作区暂无文件，请先执行扫描。"

        lines = [f"工作区「{workspace.name}」共 {len(files)} 个文件：\n"]
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
            return f"错误：文件 {file_id} 不存在"

        # 安全检查：文件路径必须在工作区目录内
        workspace = db.get(Workspace, file.workspace_id)
        if workspace:
            real_path = os.path.realpath(file.filepath)
            workspace_path = os.path.realpath(workspace.path)
            if not real_path.startswith(workspace_path + os.sep) and real_path != workspace_path:
                return "错误：文件路径不在工作区目录内"

        if not os.path.exists(file.filepath):
            return f"错误：文件不存在于磁盘: {file.filepath}"

        try:
            with open(file.filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(get_settings().max_file_read_size)
        except OSError as e:
            return f"错误：读取文件失败: {e}"

        header = f"文件: {file.filename} (id={file.id})\n路径: {file.filepath}\n"
        if os.path.getsize(file.filepath) > get_settings().max_file_read_size:
            header += f"（文件过大，仅显示前 {get_settings().max_file_read_size // 1024}KB）\n"
        return f"{header}\n{content}"
    finally:
        db.close()


def get_file_info(file_id: int) -> str:
    """获取文件的详细元信息。"""
    db = SessionLocal()
    try:
        file = db.get(File, file_id)
        if not file:
            return f"错误：文件 {file_id} 不存在"

        size = f"{file.size_bytes / 1024:.1f}KB" if file.size_bytes >= 1024 else f"{file.size_bytes}B"
        return (
            f"文件名: {file.filename}\n"
            f"完整路径: {file.filepath}\n"
            f"文件类型: {file.file_type}\n"
            f"大小: {size}\n"
            f"状态: {file.status}\n"
            f"所属工作区 ID: {file.workspace_id}"
        )
    finally:
        db.close()


def create_file_tools() -> ToolRegistry:
    """创建包含文件工具的 ToolRegistry，供 FileAgent 使用。"""
    registry = ToolRegistry()

    registry.register(Tool(
        name="list_files",
        description="列出指定工作区中的所有文件，返回文件 ID、文件名、类型和大小",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
        },
        function=list_files,
    ))

    registry.register(Tool(
        name="read_file",
        description="读取指定文件的文本内容，需要先用 list_files 获取文件 ID",
        parameters={
            "file_id": {"type": "integer", "description": "文件 ID（通过 list_files 获取）"},
        },
        function=read_file,
    ))

    registry.register(Tool(
        name="get_file_info",
        description="获取文件的详细元信息（文件名、路径、类型、大小等）",
        parameters={
            "file_id": {"type": "integer", "description": "文件 ID"},
        },
        function=get_file_info,
    ))

    return registry
