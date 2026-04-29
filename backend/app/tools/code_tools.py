"""代码分析工具 — 提供给 CodeAgent 使用。

包含 3 个工具：
  - analyze_project_structure: 分析项目目录结构和文件类型统计
  - explain_function: 搜索并读取函数/类定义的代码
  - find_dependencies: 分析 import 语句，列出模块依赖关系
"""

import os
from collections import Counter

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.file import File
from app.models.workspace import Workspace
from app.tools.registry import Tool, ToolRegistry


def analyze_project_structure(workspace_id: int) -> str:
    """分析工作区的项目结构：目录树 + 文件类型统计。"""
    db = SessionLocal()
    try:
        workspace = db.get(Workspace, workspace_id)
        if not workspace:
            return f"Error: workspace {workspace_id} not found"

        files = (
            db.query(File)
            .filter(File.workspace_id == workspace_id)
            .order_by(File.filepath)
            .all()
        )

        if not files:
            return "This workspace has no files yet — run a scan first."

        type_counter = Counter(f.file_type for f in files)
        total_size = sum(f.size_bytes for f in files)

        base = workspace.path.rstrip(os.sep)
        tree_lines = []
        for f in files:
            rel = f.filepath[len(base):].lstrip(os.sep)
            size = f"{f.size_bytes / 1024:.1f}KB" if f.size_bytes >= 1024 else f"{f.size_bytes}B"
            tree_lines.append(f"  {rel}  ({size})")

        lines = [
            f'Workspace "{workspace.name}" — structure:',
            f"path: {workspace.path}",
            f"files: {len(files)}",
            f"total size: {total_size / 1024:.1f}KB",
            "",
            "file types:",
        ]
        for ftype, count in type_counter.most_common():
            lines.append(f"  .{ftype}: {count}")

        lines.append("")
        lines.append("tree:")
        lines.extend(tree_lines)

        return "\n".join(lines)
    finally:
        db.close()


def explain_function(workspace_id: int, query: str) -> str:
    """搜索函数/类定义并返回代码上下文。

    在工作区的文件中搜索包含 query 的 def/class 定义行，
    返回该定义周围的代码上下文。
    """
    db = SessionLocal()
    try:
        files = db.query(File).filter(File.workspace_id == workspace_id).all()
        if not files:
            return "This workspace has no files yet."

        max_read = get_settings().max_file_read_size
        results = []

        for f in files:
            if not os.path.exists(f.filepath):
                continue
            try:
                with open(f.filepath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read(max_read)
            except OSError:
                continue

            lines = content.split("\n")
            for i, line in enumerate(lines):
                # 搜索包含 query 的 def 或 class 行
                if query.lower() in line.lower() and ("def " in line or "class " in line):
                    # 取前后各 10 行作为上下文
                    start = max(0, i - 3)
                    end = min(len(lines), i + 15)
                    snippet = "\n".join(lines[start:end])
                    results.append(f"file: {f.filename} (line {i + 1})\n```\n{snippet}\n```")

                    if len(results) >= 5:
                        break
            if len(results) >= 5:
                break

        if not results:
            return f'No function or class definition matching "{query}".'

        return f'Found {len(results)} matching definitions:\n\n' + "\n\n".join(results)
    finally:
        db.close()


def find_dependencies(workspace_id: int) -> str:
    """分析 import 语句，列出模块依赖关系。"""
    db = SessionLocal()
    try:
        files = (
            db.query(File)
            .filter(File.workspace_id == workspace_id)
            .filter(File.file_type.in_(["py", "js", "jsx", "ts", "tsx"]))
            .all()
        )

        if not files:
            return "No code files in this workspace."

        max_read = get_settings().max_file_read_size
        file_deps = {}

        for f in files:
            if not os.path.exists(f.filepath):
                continue
            try:
                with open(f.filepath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read(max_read)
            except OSError:
                continue

            imports = []
            for line in content.split("\n"):
                stripped = line.strip()
                # Python imports
                if stripped.startswith("import ") or stripped.startswith("from "):
                    imports.append(stripped)
                # JS/TS imports
                elif stripped.startswith("import ") or (stripped.startswith("const ") and "require(" in stripped):
                    imports.append(stripped)

            if imports:
                file_deps[f.filename] = imports

        if not file_deps:
            return "No import statements found."

        lines = [f"{len(file_deps)} file(s) with dependencies:\n"]
        for filename, imports in file_deps.items():
            lines.append(f"{filename}:")
            for imp in imports[:10]:
                lines.append(f"  {imp}")
            if len(imports) > 10:
                lines.append(f"  ... and {len(imports) - 10} more")
            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()


def create_code_tools() -> ToolRegistry:
    """创建包含代码分析工具 + 记忆工具的 ToolRegistry，供 CodeAgent 使用。"""
    from app.tools.memory_tools import create_memory_tools
    registry = create_memory_tools()  # 先加记忆工具

    registry.register(Tool(
        name="analyze_project_structure",
        description="Summarise the workspace's directory tree and file-type breakdown.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
        },
        function=analyze_project_structure,
    ))

    registry.register(Tool(
        name="explain_function",
        description="Find the definition code for a function or class. The query must be a name (e.g. create_app, BaseAgent) — not a filename.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
            "query": {"type": "string", "description": "function or class name (e.g. create_app, Settings)"},
        },
        function=explain_function,
    ))

    registry.register(Tool(
        name="find_dependencies",
        description="Parse code-file import statements and list dependencies.",
        parameters={
            "workspace_id": {"type": "integer", "description": "workspace ID"},
        },
        function=find_dependencies,
    ))

    return registry
