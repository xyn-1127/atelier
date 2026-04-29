"""笔记 CRUD 测试。"""

import tempfile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_workspace():
    tmp = tempfile.mkdtemp()
    resp = client.post("/api/workspaces", json={"name": "笔记测试", "path": tmp})
    return resp.json()["id"]


def _create_note(workspace_id, title="测试笔记", content="# 内容\n\n这是测试。"):
    resp = client.post(f"/api/workspaces/{workspace_id}/notes",
                       json={"title": title, "content": content})
    assert resp.status_code == 201
    return resp.json()


class TestCreateNote:

    def test_create_success(self):
        wid = _create_workspace()
        note = _create_note(wid)
        assert note["title"] == "测试笔记"
        assert note["content"] == "# 内容\n\n这是测试。"
        assert note["workspace_id"] == wid

    def test_create_empty_content(self):
        wid = _create_workspace()
        resp = client.post(f"/api/workspaces/{wid}/notes", json={"title": "空笔记"})
        assert resp.status_code == 201
        assert resp.json()["content"] == ""

    def test_create_workspace_not_found(self):
        resp = client.post("/api/workspaces/99999/notes", json={"title": "x"})
        assert resp.status_code == 404


class TestListNotes:

    def test_list(self):
        wid = _create_workspace()
        _create_note(wid, "笔记1")
        _create_note(wid, "笔记2")

        resp = client.get(f"/api/workspaces/{wid}/notes")
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) == 2

    def test_list_empty(self):
        wid = _create_workspace()
        resp = client.get(f"/api/workspaces/{wid}/notes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_workspace_not_found(self):
        resp = client.get("/api/workspaces/99999/notes")
        assert resp.status_code == 404


class TestGetNote:

    def test_get_success(self):
        wid = _create_workspace()
        note = _create_note(wid)

        resp = client.get(f"/api/notes/{note['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "测试笔记"

    def test_get_not_found(self):
        resp = client.get("/api/notes/99999")
        assert resp.status_code == 404


class TestUpdateNote:

    def test_update_title(self):
        wid = _create_workspace()
        note = _create_note(wid)

        resp = client.patch(f"/api/notes/{note['id']}", json={"title": "新标题"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "新标题"
        assert resp.json()["content"] == note["content"]  # 内容不变

    def test_update_content(self):
        wid = _create_workspace()
        note = _create_note(wid)

        resp = client.patch(f"/api/notes/{note['id']}", json={"content": "新内容"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "新内容"
        assert resp.json()["title"] == note["title"]  # 标题不变

    def test_update_not_found(self):
        resp = client.patch("/api/notes/99999", json={"title": "x"})
        assert resp.status_code == 404


class TestDeleteNote:

    def test_delete_success(self):
        wid = _create_workspace()
        note = _create_note(wid)

        resp = client.delete(f"/api/notes/{note['id']}")
        assert resp.status_code == 204

        # 确认已删除
        resp = client.get(f"/api/notes/{note['id']}")
        assert resp.status_code == 404

    def test_delete_not_found(self):
        resp = client.delete("/api/notes/99999")
        assert resp.status_code == 404
