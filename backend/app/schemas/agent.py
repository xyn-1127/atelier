"""Agent 执行计划的数据结构。

Orchestrator 生成执行计划后，用这些结构来描述"要做什么、用哪些 Agent、什么顺序"。
"""

from pydantic import BaseModel


class PlanStep(BaseModel):
    """执行计划的一步。"""
    agent_name: str                    # 用哪个 Agent，如 "code_agent"
    task: str                          # 给 Agent 的任务描述
    output_hint: str | None = None     # 输出要求，如 "简要分析，300字以内"
    depends_on: list[int] = []         # 依赖的步骤索引，空=无依赖（可并行）


class ExecutionPlan(BaseModel):
    """Orchestrator 生成的执行计划。"""
    reasoning: str         # LLM 的分析思路（为什么这么规划）
    steps: list[PlanStep]  # 执行步骤列表（按顺序执行）
