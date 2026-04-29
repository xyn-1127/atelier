"""目录浏览 API — 供前端目录选择器使用。"""

import os

from fastapi import APIRouter, Query

router = APIRouter(tags=["browse"])


@router.get("/api/browse")
def browse_directory(
    path: str = Query(default="~", description="要浏览的目录路径"),
    show_hidden: bool = Query(default=False, description="是否显示隐藏目录"),
):
    """列出指定目录下的子目录。

    返回：
        {
            "current": "/root/projects",
            "parent": "/root",
            "dirs": [
                {"name": "project-a", "path": "/root/projects/project-a"},
                {"name": "project-b", "path": "/root/projects/project-b"},
            ]
        }
    """
    # ~ 展开为用户 home 目录
    expanded = os.path.expanduser(path)
    resolved = os.path.realpath(expanded)

    if not os.path.isdir(resolved):
        return {"current": resolved, "parent": None, "dirs": [], "error": "目录不存在"}

    parent = os.path.dirname(resolved) if resolved != "/" else None

    dirs = []
    try:
        for entry in sorted(os.scandir(resolved), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            if not show_hidden and entry.name.startswith("."):
                continue
            dirs.append({"name": entry.name, "path": entry.path})
    except PermissionError:
        return {"current": resolved, "parent": parent, "dirs": [], "error": "没有权限访问该目录"}

    return {"current": resolved, "parent": parent, "dirs": dirs}
