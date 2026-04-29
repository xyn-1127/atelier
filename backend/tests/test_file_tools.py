"""文件工具测试。

用 TestClient 创建 workspace 并扫描文件（确保数据库表存在且有数据），
然后直接调用工具函数测试。
"""

import os
import tempfile

from fastapi.testclient import TestClient

from app.main import app
from app.tools.file_tools import list_files, read_file, get_file_info, create_file_tools

client = TestClient(app)


def create_workspace_with_files():
    """辅助：创建临时目录 → 创建 workspace → 扫描 → 返回 workspace_id 和文件 IDs。"""
    tmp = tempfile.mkdtemp()

    with open(os.path.join(tmp, "main.py"), "w") as f:
        f.write("def hello():\n    print('hello world')\n")
    with open(os.path.join(tmp, "readme.md"), "w") as f:
        f.write("# 测试项目\n\n这是一个测试。")
    with open(os.path.join(tmp, "config.json"), "w") as f:
        f.write('{"debug": true}')

    # 通过 API 创建 workspace 并扫描
    resp = client.post("/api/workspaces", json={"name": "工具测试", "path": tmp})
    workspace_id = resp.json()["id"]
    client.post(f"/api/workspaces/{workspace_id}/scan")

    # 获取文件列表
    files_resp = client.get(f"/api/workspaces/{workspace_id}/files")
    files = {f["filename"]: f["id"] for f in files_resp.json()}

    return workspace_id, files, tmp


# ─── list_files 测试 ───


class TestListFiles:

    def test_list_files_success(self):
        workspace_id, files, _ = create_workspace_with_files()

        result = list_files(workspace_id)

        assert "3 个文件" in result
        assert "main.py" in result
        assert "readme.md" in result
        assert "config.json" in result

    def test_list_files_shows_id(self):
        """结果中包含文件 ID，方便 LLM 用 ID 调用 read_file。"""
        workspace_id, files, _ = create_workspace_with_files()

        result = list_files(workspace_id)

        for filename, file_id in files.items():
            assert f"id={file_id}" in result

    def test_list_files_workspace_not_found(self):
        result = list_files(99999)
        assert "不存在" in result

    def test_list_files_empty_workspace(self):
        """没有文件的工作区。"""
        tmp = tempfile.mkdtemp()
        resp = client.post("/api/workspaces", json={"name": "空工作区", "path": tmp})
        workspace_id = resp.json()["id"]

        result = list_files(workspace_id)
        assert "暂无文件" in result


# ─── read_file 测试 ───


class TestReadFile:

    def test_read_file_success(self):
        workspace_id, files, _ = create_workspace_with_files()

        result = read_file(files["main.py"])

        assert "main.py" in result
        assert "def hello():" in result
        assert "print('hello world')" in result

    def test_read_file_not_found(self):
        result = read_file(99999)
        assert "不存在" in result

    def test_read_file_includes_header(self):
        """结果包含文件名和路径信息。"""
        workspace_id, files, _ = create_workspace_with_files()

        result = read_file(files["readme.md"])

        assert "文件: readme.md" in result
        assert "路径:" in result


# ─── get_file_info 测试 ───


class TestGetFileInfo:

    def test_get_file_info_success(self):
        workspace_id, files, _ = create_workspace_with_files()

        result = get_file_info(files["config.json"])

        assert "config.json" in result
        assert "json" in result
        assert f"工作区 ID: {workspace_id}" in result

    def test_get_file_info_not_found(self):
        result = get_file_info(99999)
        assert "不存在" in result


# ─── create_file_tools 测试 ───


class TestCreateFileTools:

    def test_creates_registry_with_three_tools(self):
        registry = create_file_tools()

        tools = registry.list_all()
        assert len(tools) == 3

        names = {t.name for t in tools}
        assert names == {"list_files", "read_file", "get_file_info"}

    def test_to_openai_tools_format(self):
        registry = create_file_tools()

        openai_tools = registry.to_openai_tools()
        assert len(openai_tools) == 3

        for tool in openai_tools:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]
