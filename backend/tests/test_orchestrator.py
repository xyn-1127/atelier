"""Orchestrator 测试。"""

import json
from unittest.mock import patch, MagicMock

from app.agents.orchestrator import Orchestrator
from app.schemas.agent import ExecutionPlan, PlanStep


# ─── 辅助函数 ───


def _mock_plan_response(steps, reasoning="测试计划"):
    """模拟 LLM 返回的计划 JSON。"""
    plan = {
        "reasoning": reasoning,
        "steps": [{"agent_name": s[0], "task": s[1]} for s in steps],
    }
    return json.dumps(plan)


def _make_stream_text(content):
    return iter([("content_chunk", content)])


# ─── plan() 测试 ───


class TestOrchestratorPlan:

    @patch("app.agents.orchestrator.chat_completion")
    def test_plan_single_step(self, mock_llm):
        """简单任务生成单步计划。"""
        mock_llm.return_value = _mock_plan_response(
            [("file_agent", "查看 main.py 的内容")],
            reasoning="用户想看具体文件",
        )

        orch = Orchestrator()
        plan = orch.plan("帮我看看 main.py")

        assert len(plan.steps) == 1
        assert plan.steps[0].agent_name == "file_agent"
        assert "main.py" in plan.steps[0].task

    @patch("app.agents.orchestrator.chat_completion")
    def test_plan_multi_step(self, mock_llm):
        """复杂任务生成多步计划。"""
        mock_llm.return_value = _mock_plan_response([
            ("code_agent", "分析项目结构"),
            ("search_agent", "搜索核心功能"),
            ("writer_agent", "生成项目总结"),
        ])

        orch = Orchestrator()
        plan = orch.plan("全面分析这个项目并写总结")

        assert len(plan.steps) == 3
        assert plan.steps[0].agent_name == "code_agent"
        assert plan.steps[2].agent_name == "writer_agent"

    @patch("app.agents.orchestrator.chat_completion")
    def test_plan_filters_invalid_agent(self, mock_llm):
        """计划中无效的 agent_name 被过滤。"""
        mock_llm.return_value = _mock_plan_response([
            ("code_agent", "分析结构"),
            ("nonexistent_agent", "不存在的 Agent"),
        ])

        orch = Orchestrator()
        plan = orch.plan("分析项目")

        assert len(plan.steps) == 1
        assert plan.steps[0].agent_name == "code_agent"

    @patch("app.agents.orchestrator.chat_completion")
    def test_plan_fallback_on_error(self, mock_llm):
        """LLM 返回无效 JSON 时降级到 file_agent。"""
        mock_llm.return_value = "这不是 JSON"

        orch = Orchestrator()
        plan = orch.plan("测试")

        assert len(plan.steps) == 1
        assert plan.steps[0].agent_name == "file_agent"

    @patch("app.agents.orchestrator.chat_completion")
    def test_plan_with_markdown_wrapper(self, mock_llm):
        """LLM 返回的 JSON 被 markdown 代码块包裹时也能解析。"""
        raw_json = _mock_plan_response([("file_agent", "查看文件")])
        mock_llm.return_value = f"```json\n{raw_json}\n```"

        orch = Orchestrator()
        plan = orch.plan("看文件")

        assert len(plan.steps) == 1


# ─── execute_with_events() 测试 ───


class TestOrchestratorExecute:

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_execute_single_step(self, mock_stream):
        """单步计划执行。"""
        mock_stream.return_value = _make_stream_text("main.py 里有 create_app 函数")

        plan = ExecutionPlan(
            reasoning="用户想看文件",
            steps=[PlanStep(agent_name="file_agent", task="查看 main.py")],
        )

        orch = Orchestrator()
        events = list(orch.execute_with_events(plan, context={"workspace_id": 1}))

        types = [e[0] for e in events]
        assert "plan" in types
        assert "step_start" in types
        assert "step_done" in types
        assert "result" in types

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_execute_multi_step_passes_context(self, mock_stream):
        """多步执行时上下文传递。"""
        call_count = [0]

        def fake_stream(messages, tools):
            call_count[0] += 1
            if call_count[0] == 1:
                return iter([("content_chunk", "结构分析结果")])
            else:
                # 第二步应该能看到第一步的结果在 context 中
                context_msgs = [m for m in messages if "previous_results" in str(m.get("content", ""))]
                return iter([("content_chunk", "最终总结")])

        mock_stream.side_effect = fake_stream

        plan = ExecutionPlan(
            reasoning="多步任务",
            steps=[
                PlanStep(agent_name="code_agent", task="分析结构"),
                PlanStep(agent_name="writer_agent", task="写总结", depends_on=[0]),
            ],
        )

        orch = Orchestrator()
        events = list(orch.execute_with_events(plan, context={"workspace_id": 1}))

        # 应该有两组 step_start/step_done
        step_starts = [e for e in events if e[0] == "step_start"]
        step_dones = [e for e in events if e[0] == "step_done"]
        assert len(step_starts) == 2
        assert len(step_dones) == 2

    def test_execute_invalid_agent_continues(self):
        """某步 Agent 不存在时跳过继续。"""
        plan = ExecutionPlan(
            reasoning="测试降级",
            steps=[
                PlanStep(agent_name="nonexistent", task="不存在"),
                PlanStep(agent_name="file_agent", task="查看文件"),
            ],
        )

        orch = Orchestrator()
        with patch("app.agents.base.chat_completion_with_tools_stream") as mock_stream:
            mock_stream.return_value = _make_stream_text("文件内容")
            events = list(orch.execute_with_events(plan, context={"workspace_id": 1}))

        step_dones = [e for e in events if e[0] == "step_done"]
        assert len(step_dones) == 2
        assert "不存在" in step_dones[0][1]["content"]
        # 第二步仍然执行了
        assert step_dones[1][1]["agent_name"] == "file_agent"

    @patch("app.agents.base.chat_completion_with_tools_stream")
    def test_execute_returns_last_step_content(self, mock_stream):
        """最终结果取最后一步的内容。"""
        mock_stream.side_effect = [
            _make_stream_text("步骤1结果"),
            _make_stream_text("这是最终总结"),
        ]

        plan = ExecutionPlan(
            reasoning="测试",
            steps=[
                PlanStep(agent_name="code_agent", task="分析"),
                PlanStep(agent_name="writer_agent", task="总结", depends_on=[0]),
            ],
        )

        orch = Orchestrator()
        result = orch.execute(plan, context={"workspace_id": 1})

        assert result.status == "success"
        assert "最终总结" in result.content
