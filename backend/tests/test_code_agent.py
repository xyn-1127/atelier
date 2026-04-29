"""CodeAgent 测试。

代码工具用真实文件测试，CodeAgent 用 mock LLM 测试。
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.agents.code_agent import CodeAgent
from app.tools.code_tools import (
    analyze_project_structure, explain_function, find_dependencies, create_code_tools,
)

client = TestClient(app)


def _create_code_workspace():
    """创建包含代码文件的工作区，手动同步扫描（不等后台线程）。"""
    from app.db.session import SessionLocal
    from app.services.scanner import scan_workspace as sync_scan
    from app.models.workspace import Workspace

    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "app"))

    with open(os.path.join(tmp, "main.py"), "w") as f:
        f.write("from fastapi import FastAPI\nfrom app.router import api_router\n\n"
                "def create_app():\n    app = FastAPI()\n    app.include_router(api_router)\n    return app\n")

    with open(os.path.join(tmp, "app", "router.py"), "w") as f:
        f.write("from fastapi import APIRouter\n\napi_router = APIRouter()\n\n"
                "@api_router.get('/health')\ndef health():\n    return {'status': 'ok'}\n")

    with open(os.path.join(tmp, "requirements.txt"), "w") as f:
        f.write("fastapi\nuvicorn\n")

    resp = client.post("/api/workspaces", json={"name": "代码测试", "path": tmp})
    wid = resp.json()["id"]

    # 手动同步扫描（测试不等后台线程）
    import time; time.sleep(0.5)  # 等后台线程启动避免冲突
    db = SessionLocal()
    try:
        ws = db.get(Workspace, wid)
        sync_scan(db, ws)
    finally:
        db.close()

    return wid


# ─── 代码工具测试 ───


class TestAnalyzeProjectStructure:

    def test_returns_structure(self):
        wid = _create_code_workspace()
        result = analyze_project_structure(wid)
        assert "main.py" in result
        assert "router.py" in result
        assert "文件总数" in result
        assert "py" in result

    def test_workspace_not_found(self):
        result = analyze_project_structure(99999)
        assert "不存在" in result


class TestExplainFunction:

    def test_finds_function(self):
        wid = _create_code_workspace()
        result = explain_function(wid, "create_app")
        assert "create_app" in result
        assert "FastAPI" in result
        assert "main.py" in result

    def test_finds_class_or_decorator(self):
        wid = _create_code_workspace()
        result = explain_function(wid, "health")
        assert "health" in result

    def test_not_found(self):
        wid = _create_code_workspace()
        result = explain_function(wid, "nonexistent_xyz")
        assert "未找到" in result


class TestFindDependencies:

    def test_finds_imports(self):
        wid = _create_code_workspace()
        result = find_dependencies(wid)
        assert "from fastapi import FastAPI" in result
        assert "main.py" in result
        assert "router.py" in result

    def test_empty_workspace(self):
        tmp = tempfile.mkdtemp()
        resp = client.post("/api/workspaces", json={"name": "空", "path": tmp})
        wid = resp.json()["id"]
        result = find_dependencies(wid)
        assert "没有代码文件" in result


class TestCreateCodeTools:

    def test_has_code_and_memory_tools(self):
        registry = create_code_tools()
        names = {t.name for t in registry.list_all()}
        assert {"analyze_project_structure", "explain_function", "find_dependencies"} <= names
        assert {"save_memory", "recall_memory"} <= names


# ─── CodeAgent 测试（mock LLM）───


class TestCodeAgent:

    def test_has_correct_config(self):
        agent = CodeAgent()
        assert agent.name == "code_agent"
        names = {t.name for t in agent.tools.list_all()}
        assert "analyze_project_structure" in names
        assert "save_memory" in names

    @patch("app.agents.base.chat_completion_with_tools")
    def test_analyze_flow(self, mock_llm):
        """CodeAgent 调工具分析后回答。"""
        wid = _create_code_workspace()

        tc = MagicMock()
        tc.id = "c1"
        tc.function = MagicMock()
        tc.function.name = "analyze_project_structure"
        tc.function.arguments = f'{{"workspace_id": {wid}}}'

        call1 = MagicMock()
        call1.content = None
        call1.tool_calls = [tc]

        call2 = MagicMock()
        call2.content = "这是一个 FastAPI 项目，包含主程序和路由模块。"
        call2.tool_calls = None

        mock_llm.side_effect = [call1, call2]

        agent = CodeAgent()
        result = agent.run("分析项目结构", context={"workspace_id": wid})

        assert result.status == "success"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "analyze_project_structure"
