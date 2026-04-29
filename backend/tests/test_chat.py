import tempfile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_workspace_and_chat():
    """辅助函数：创建 workspace + chat"""
    tmp = tempfile.mkdtemp()
    ws = client.post("/api/workspaces", json={"name": "聊天测试", "path": tmp})
    ws_id = ws.json()["id"]
    chat = client.post(f"/api/workspaces/{ws_id}/chats")
    return ws_id, chat.json()["id"]


def test_create_chat():
    ws_id, chat_id = create_workspace_and_chat()
    response = client.get(f"/api/chats/{chat_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "新对话"
    assert response.json()["workspace_id"] == ws_id


def test_create_chat_workspace_not_found():
    response = client.post("/api/workspaces/99999/chats")
    assert response.status_code == 404


def test_list_chats():
    ws_id, _ = create_workspace_and_chat()
    # 再创建一个
    client.post(f"/api/workspaces/{ws_id}/chats")
    response = client.get(f"/api/workspaces/{ws_id}/chats")
    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_list_chats_workspace_not_found():
    response = client.get("/api/workspaces/99999/chats")
    assert response.status_code == 404


def test_get_chat_detail():
    _, chat_id = create_workspace_and_chat()
    response = client.get(f"/api/chats/{chat_id}")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)


def test_get_chat_not_found():
    response = client.get("/api/chats/99999")
    assert response.status_code == 404


def test_delete_chat():
    _, chat_id = create_workspace_and_chat()
    response = client.delete(f"/api/chats/{chat_id}")
    assert response.status_code == 204

    response = client.get(f"/api/chats/{chat_id}")
    assert response.status_code == 404


def test_delete_chat_not_found():
    response = client.delete("/api/chats/99999")
    assert response.status_code == 404
