import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_workspace_and_chat():
    """辅助函数：创建 workspace + chat"""
    tmp = tempfile.mkdtemp()
    ws = client.post("/api/workspaces", json={"name": "消息测试", "path": tmp})
    ws_id = ws.json()["id"]
    chat = client.post(f"/api/workspaces/{ws_id}/chats")
    return ws_id, chat.json()["id"]


@patch("app.services.chat.chat_completion")
def test_send_message(mock_llm):
    mock_llm.return_value = "这是 mock 的 AI 回复"
    _, chat_id = create_workspace_and_chat()

    response = client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "你好"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "assistant"
    assert data["content"] == "这是 mock 的 AI 回复"


@patch("app.services.chat.chat_completion")
def test_send_message_history(mock_llm):
    mock_llm.return_value = "第二条回复"
    _, chat_id = create_workspace_and_chat()

    # 第一条
    mock_llm.return_value = "第一条回复"
    client.post(f"/api/chats/{chat_id}/messages", json={"content": "第一条"})

    # 第二条
    mock_llm.return_value = "第二条回复"
    client.post(f"/api/chats/{chat_id}/messages", json={"content": "第二条"})

    # 检查对话详情：应有 4 条消息（2 user + 2 assistant）
    response = client.get(f"/api/chats/{chat_id}")
    messages = response.json()["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[3]["role"] == "assistant"


@patch("app.services.chat.chat_completion")
def test_send_message_chat_not_found(mock_llm):
    response = client.post(
        "/api/chats/99999/messages",
        json={"content": "你好"},
    )
    assert response.status_code == 404
    mock_llm.assert_not_called()


@patch("app.services.chat.chat_completion")
def test_send_message_llm_fails(mock_llm):
    mock_llm.side_effect = Exception("API 超时")
    _, chat_id = create_workspace_and_chat()

    response = client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "你好"},
    )
    assert response.status_code == 400
    assert "AI 调用失败" in response.json()["detail"]
