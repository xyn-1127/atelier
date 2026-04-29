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
            return f"错误：工作区 {workspace_id} 不存在"

        files = (
            db.query(File)
            .filter(File.workspace_id == workspace_id)
            .order_by(File.filepath)
            .all()
        )

        if not files:
            return "该工作区暂无文件，请先扫描。"

        # 文件类型统计
        type_counter = Counter(f.file_type for f in files)
        total_size = sum(f.size_bytes for f in files)

        # 目录树（用相对路径）
        base = workspace.path.rstrip(os.sep)
        tree_lines = []
        for f in files:
            rel = f.filepath[len(base):].lstrip(os.sep)
            size = f"{f.size_bytes / 1024:.1f}KB" if f.size_bytes >= 1024 else f"{f.size_bytes}B"
            tree_lines.append(f"  {rel}  ({size})")

        lines = [
            f"工作区「{workspace.name}」项目结构分析：",
            f"路径: {workspace.path}",
            f"文件总数: {len(files)}",
            f"总大小: {total_size / 1024:.1f}KB",
            "",
            "文件类型统计:",
        ]
        for ftype, count in type_counter.most_common():
            lines.append(f"  .{ftype}: {count} 个")

        lines.append("")
        lines.append("目录结构:")
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
            return "该工作区暂无文件。"

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
                    results.append(f"文件: {f.filename} (第{i + 1}行)\n```\n{snippet}\n```")

                    if len(results) >= 5:
                        break
            if len(results) >= 5:
                break

        if not results:
            return f"未找到包含 \"{query}\" 的函数或类定义。"

        return f"找到 {len(results)} 个匹配的定义：\n\n" + "\n\n".join(results)
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
            return "该工作区没有代码文件。"

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
            return "未发现 import 语句。"

        lines = [f"共 {len(file_deps)} 个文件有依赖：\n"]
        for filename, imports in file_deps.items():
            lines.append(f"{filename}:")
            for imp in imports[:10]:  # 每个文件最多显示 10 条
                lines.append(f"  {imp}")
            if len(imports) > 10:
                lines.append(f"  ... 还有 {len(imports) - 10} 条")
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
        description="分析工作区的项目结构，返回目录树和文件类型统计",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
        },
        function=analyze_project_structure,
    ))

    registry.register(Tool(
        name="explain_function",
        description="搜索函数或类的定义代码并返回上下文。query 必须是函数名或类名（如 create_app、BaseAgent），不要传文件名。",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
            "query": {"type": "string", "description": "函数名或类名（如 create_app、Settings），不是文件名"},
        },
        function=explain_function,
    ))

    registry.register(Tool(
        name="find_dependencies",
        description="分析代码文件的 import 语句，列出模块依赖关系",
        parameters={
            "workspace_id": {"type": "integer", "description": "工作区 ID"},
        },
        function=find_dependencies,
    ))

    return registry
