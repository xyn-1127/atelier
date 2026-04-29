import os
import tempfile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_workspace_with_files():
    """辅助函数：创建带文件的临时目录和 workspace"""
    tmp = tempfile.mkdtemp()

    # 创建几个测试文件
    with open(os.path.join(tmp, "hello.py"), "w") as f:
        f.write("print('hello')")
    with open(os.path.join(tmp, "readme.md"), "w") as f:
        f.write("# 测试项目")
    with open(os.path.join(tmp, "data.json"), "w") as f:
        f.write('{"key": "value"}')
    # 创建一个不支持的文件类型，应该被跳过
    with open(os.path.join(tmp, "image.png"), "w") as f:
        f.write("fake image")

    response = client.post("/api/workspaces", json={"name": "文件测试", "path": tmp})
    workspace_id = response.json()["id"]
    return workspace_id, tmp


def test_scan_workspace():
    workspace_id, _ = create_workspace_with_files()

    response = client.post(f"/api/workspaces/{workspace_id}/scan")
    assert response.status_code == 200
    assert "3" in response.json()["message"]  # 3 个支持的文件


def test_scan_workspace_not_found():
    response = client.post("/api/workspaces/99999/scan")
    assert response.status_code == 404


def test_list_files():
    workspace_id, _ = create_workspace_with_files()
    client.post(f"/api/workspaces/{workspace_id}/scan")

    response = client.get(f"/api/workspaces/{workspace_id}/files")
    assert response.status_code == 200
    files = response.json()
    assert len(files) == 3
    filenames = [f["filename"] for f in files]
    assert "hello.py" in filenames
    assert "readme.md" in filenames
    assert "data.json" in filenames
    assert "image.png" not in filenames  # 不支持的类型被过滤了


def test_get_file():
    workspace_id, _ = create_workspace_with_files()
    client.post(f"/api/workspaces/{workspace_id}/scan")

    files_response = client.get(f"/api/workspaces/{workspace_id}/files")
    file_id = files_response.json()[0]["id"]

    response = client.get(f"/api/files/{file_id}")
    assert response.status_code == 200
    assert response.json()["id"] == file_id


def test_get_file_not_found():
    response = client.get("/api/files/99999")
    assert response.status_code == 404


def test_get_file_content():
    workspace_id, _ = create_workspace_with_files()
    client.post(f"/api/workspaces/{workspace_id}/scan")

    files_response = client.get(f"/api/workspaces/{workspace_id}/files")
    # 找到 hello.py
    py_file = [f for f in files_response.json() if f["filename"] == "hello.py"][0]

    response = client.get(f"/api/files/{py_file['id']}/content")
    assert response.status_code == 200
    assert response.json()["content"] == "print('hello')"
    assert response.json()["file_type"] == "py"


def test_get_file_content_not_found():
    response = client.get("/api/files/99999/content")
    assert response.status_code == 404