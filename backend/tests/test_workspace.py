import tempfile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_temp_workspace(name: str = "测试工作区"):
    """辅助函数：用临时目录创建一个 workspace"""
    tmp = tempfile.mkdtemp()
    response = client.post("/api/workspaces", json={"name": name, "path": tmp})
    return response, tmp


def test_create_workspace_success():
    response, _ = create_temp_workspace()
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试工作区"
    assert data["status"] == "active"


def test_create_workspace_path_not_exist():
    response = client.post(
        "/api/workspaces",
        json={"name": "不存在", "path": "/this/path/does/not/exist"},
    )
    assert response.status_code == 400
    assert "路径不存在" in response.json()["detail"]


def test_create_workspace_duplicate_path():
    _, tmp = create_temp_workspace("第一个")
    response = client.post(
        "/api/workspaces",
        json={"name": "第二个", "path": tmp},
    )
    assert response.status_code == 409
    assert "已被添加" in response.json()["detail"]


def test_list_workspaces():
    response = client.get("/api/workspaces")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_workspace_success():
    create_response, _ = create_temp_workspace("详情测试")
    workspace_id = create_response.json()["id"]

    response = client.get(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "详情测试"


def test_get_workspace_not_found():
    response = client.get("/api/workspaces/99999")
    assert response.status_code == 404


def test_update_workspace():
    create_response, _ = create_temp_workspace("旧名字")
    workspace_id = create_response.json()["id"]

    response = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"name": "新名字"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "新名字"


def test_delete_workspace():
    create_response, _ = create_temp_workspace("要删除的")
    workspace_id = create_response.json()["id"]

    response = client.delete(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 204

    response = client.get(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 404


def test_delete_workspace_not_found():
    response = client.delete("/api/workspaces/99999")
    assert response.status_code == 404