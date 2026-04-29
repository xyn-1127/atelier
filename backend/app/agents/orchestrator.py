"""Orchestrator — 任务编排器。

不是 Agent，而是 Agent 的调度者。
职责：分析用户意图 → 制定执行计划 → 调度 Agent 执行 → 汇总结果。

执行模式：
- 单步计划 → 直接调单个 Agent
- 多步计划 → 按 depends_on DAG 分批：同批并行，跨批串行
"""

import json
import logging
import queue
import time
from concurrent.futures import ThreadPoolExecutor

from app.agents.base import AgentResult
from app.agents.registry import get_agent, get_agents_description
from app.llm.client import chat_completion
from app.schemas.agent import ExecutionPlan, PlanStep

logger = logging.getLogger(__name__)

PLAN_SYSTEM_PROMPT = """\
You are a task-planning specialist. The user has given you a task — analyse what they need and produce an execution plan.

Available agents:
{agents_description}

Return a JSON execution plan (JSON only, nothing else):
{{
  "reasoning": "your short analysis explaining the plan",
  "steps": [
    {{"agent_name": "agent_name", "task": "specific task description", "output_hint": "what the output should be", "depends_on": []}}
  ]
}}

Rules:
1. If the task is simple and one agent is enough, return one step.
2. If it is complex, split it across steps.
3. Each step's `task` must be specific, not vague.
4. agent_name must be one of the agents listed above.
5. No more than 5 steps.
6. output_hint controls how long the agent's output is:
   - Intermediate steps (feeding later steps): use "brief summary, ≤300 chars"
   - Final step (shown to the user): use "detailed answer" or omit
   - This matters — long intermediate output wastes time.
7. depends_on lists step dependencies (0-indexed):
   - Needs a previous step's result: "depends_on": [0]
   - No dependency: "depends_on": []  (those steps run in parallel)
   - Example: structure (0) and search (1) can run in parallel; summary (2) depends on [0, 1].
8. Match the user's language. Write `reasoning`, every `task` and every `output_hint` in the same language the user used in their message — English if they wrote in English, Chinese if they wrote in Chinese.
"""

_SENTINEL = object()  # 标记线程完成


class Orchestrator:
    """任务编排器。"""

    def plan(self, task: str, context: dict | None = None) -> ExecutionPlan:
        """分析用户意图，生成执行计划。"""
        prompt = PLAN_SYSTEM_PROMPT.format(agents_description=get_agents_description())

        messages = [
            {"role": "system", "content": prompt},
            {"role": "system", "content":
                "Write the `reasoning` and each step's `task` / `output_hint` in the same language "
                "the user used. If the user writes in English, write them in English; if in Chinese, in Chinese."},
        ]

        if context and context.get("workspace_id"):
            try:
                from app.db.session import SessionLocal
                from app.services.memory import recall_memories, format_memories_for_prompt
                db = SessionLocal()
                try:
                    memories = recall_memories(db, context["workspace_id"])
                    if memories:
                        mem_text = format_memories_for_prompt(memories)
                        messages.append({"role": "system",
                                         "content": f"What we already know about this workspace:\n{mem_text}\n\nIf this is enough to answer the user, skip redundant steps."})
                finally:
                    db.close()
            except Exception as e:
                logger.warning("Failed to inject memories into plan: %s", e)

        if context:
            context_text = "\n".join(f"- {k}: {v}" for k, v in context.items())
            messages.append({"role": "system", "content": f"Context:\n{context_text}"})

        messages.append({"role": "user", "content": task})

        logger.info("Orchestrator planning for: %s", task[:100])

        try:
            response = chat_completion(messages)
            plan = self._parse_plan(response)
            logger.info("Orchestrator plan: %d steps — %s",
                        len(plan.steps), [s.agent_name for s in plan.steps])
            return plan
        except Exception as e:
            logger.error("Orchestrator planning failed: %s", e)
            return ExecutionPlan(
                reasoning=f"规划失败（{e}），降级为文件分析",
                steps=[PlanStep(agent_name="file_agent", task=task)],
            )

    def execute(self, plan: ExecutionPlan, context: dict | None = None) -> AgentResult:
        """执行计划，返回最终结果。"""
        result = None
        for event in self.execute_with_events(plan, context):
            event_type = event[0]
            data = event[1]
            if event_type == "result":
                result = data
        return result or AgentResult(content="", status="error", error="Orchestrator 未返回结果")

    def execute_with_events(self, plan: ExecutionPlan, context: dict | None = None):
        """按 DAG 依赖分批执行，同批并行，跨批串行。

        所有事件带 step_index 标识来源步骤。

        yields:
          - ("plan", {reasoning, steps})
          - ("step_start", {index, agent_name, task})
          - ("content_chunk", text, step_index)     → 带 step_index
          - ("content_to_thinking", text, step_index)
          - ("tool_call", {...}, step_index)
          - ("tool_result", {...}, step_index)
          - ("step_done", {index, agent_name, content, metrics})
          - ("result", AgentResult)
        """
        ctx = dict(context or {})
        all_tool_calls = []
        step_results: dict[int, str] = {}  # {step_index: content}
        step_metrics: dict[int, dict] = {}

        # 告诉前端执行计划
        yield ("plan", {
            "reasoning": plan.reasoning,
            "steps": [{"agent_name": s.agent_name, "task": s.task,
                        "output_hint": s.output_hint,
                        "depends_on": s.depends_on} for s in plan.steps],
        })

        batches = self._resolve_batches(plan.steps)
        logger.info("Orchestrator resolved %d batches: %s",
                     len(batches), [[i for i in b] for b in batches])

        for batch in batches:
            if len(batch) == 1:
                # ── 单步：直接执行（不额外起线程，减少开销） ──
                idx = batch[0]
                step = plan.steps[idx]
                yield from self._execute_step(idx, step, ctx, all_tool_calls, step_results, step_metrics)
            else:
                # ── 多步并行：ThreadPoolExecutor + Queue ──
                yield from self._execute_batch_parallel(batch, plan.steps, ctx, all_tool_calls, step_results, step_metrics)

            # 批次完成后，更新 context 给下一批用
            results_text = "\n\n".join(
                f"[{plan.steps[i].agent_name}] {step_results.get(i, '')}"
                for i in sorted(step_results.keys())
            )
            ctx["previous_results"] = results_text

        # 汇总最终内容（取最后完成的步骤的内容）
        last_idx = max(step_results.keys()) if step_results else 0
        final_content = step_results.get(last_idx, "")

        yield ("result", AgentResult(
            content=final_content,
            tool_calls=all_tool_calls,
            status="success",
        ))

    def _execute_step(self, idx, step, ctx, all_tool_calls, step_results, step_metrics):
        """执行单个步骤（串行）。"""
        logger.info("Orchestrator step %d: %s → %s (hint: %s)",
                     idx, step.agent_name, step.task[:80], step.output_hint or "无")

        yield ("step_start", {"index": idx, "agent_name": step.agent_name, "task": step.task})

        agent = get_agent(step.agent_name)
        if not agent:
            logger.error("Agent '%s' not found, skipping step %d", step.agent_name, idx)
            yield ("step_done", {"index": idx, "agent_name": step.agent_name,
                                 "content": f"错误：Agent '{step.agent_name}' 不存在", "metrics": {}})
            step_results[idx] = f"错误：Agent 不存在"
            return

        step_ctx = dict(ctx)
        if step.output_hint:
            step_ctx["output_hint"] = step.output_hint

        start = time.monotonic()
        content = ""
        metrics = {}
        try:
            for event_type, data in agent.run_with_events(step.task, context=step_ctx):
                if event_type == "result":
                    content = data.content
                    metrics = data.metrics
                    all_tool_calls.extend(data.tool_calls)
                else:
                    # 带上 step_index
                    yield (event_type, data, idx)
        except Exception as e:
            logger.error("Step %d failed: %s", idx, e)
            content = f"执行失败: {e}"

        metrics["duration_ms"] = int((time.monotonic() - start) * 1000)
        step_results[idx] = content
        step_metrics[idx] = metrics

        yield ("step_done", {"index": idx, "agent_name": step.agent_name,
                             "content": content, "metrics": metrics})

    def _execute_batch_parallel(self, batch, steps, ctx, all_tool_calls, step_results, step_metrics):
        """并行执行一批步骤。用 Queue 合并事件流。"""
        event_queue = queue.Queue()

        def _run_agent(idx):
            """在线程中运行一个 Agent，事件放入 queue。"""
            step = steps[idx]
            logger.info("Orchestrator parallel step %d: %s → %s",
                         idx, step.agent_name, step.task[:80])

            event_queue.put(("step_start", {"index": idx, "agent_name": step.agent_name, "task": step.task}, idx))

            agent = get_agent(step.agent_name)
            if not agent:
                event_queue.put(("step_done", {"index": idx, "agent_name": step.agent_name,
                                               "content": f"错误：Agent 不存在", "metrics": {}}, idx))
                step_results[idx] = "错误：Agent 不存在"
                return

            step_ctx = dict(ctx)
            if step.output_hint:
                step_ctx["output_hint"] = step.output_hint

            start = time.monotonic()
            content = ""
            metrics = {}
            local_tool_calls = []

            try:
                for event_type, data in agent.run_with_events(step.task, context=step_ctx):
                    if event_type == "result":
                        content = data.content
                        metrics = data.metrics
                        local_tool_calls.extend(data.tool_calls)
                    else:
                        event_queue.put((event_type, data, idx))
            except Exception as e:
                logger.error("Parallel step %d failed: %s", idx, e)
                content = f"执行失败: {e}"

            metrics["duration_ms"] = int((time.monotonic() - start) * 1000)
            step_results[idx] = content
            step_metrics[idx] = metrics

            # 线程安全：用 list extend 不保证安全，但这里的 tool_calls 只追加不读
            all_tool_calls.extend(local_tool_calls)

            event_queue.put(("step_done", {"index": idx, "agent_name": step.agent_name,
                                           "content": content, "metrics": metrics}, idx))

        # 启动并行线程
        logger.info("Orchestrator starting parallel batch: %s", batch)
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = [executor.submit(_run_agent, idx) for idx in batch]

            # 从 queue 读事件并 yield，直到所有线程完成
            done_count = 0
            while done_count < len(batch):
                try:
                    event = event_queue.get(timeout=0.1)
                except queue.Empty:
                    # 检查是否有线程异常退出
                    for f in futures:
                        if f.done() and f.exception():
                            logger.error("Parallel thread crashed: %s", f.exception())
                    continue

                event_type, data, step_idx = event
                if event_type == "step_done":
                    done_count += 1

                yield (event_type, data, step_idx)

    @staticmethod
    def _resolve_batches(steps: list[PlanStep]) -> list[list[int]]:
        """把步骤按 depends_on 分成执行批次。

        同一批内的步骤互不依赖，可以并行。
        后一批依赖前面批次的结果。

        例：
          steps[0]: depends_on=[]    → batch 0
          steps[1]: depends_on=[]    → batch 0（和 0 并行）
          steps[2]: depends_on=[0,1] → batch 1（等 batch 0 完成）
          steps[3]: depends_on=[2]   → batch 2
        """
        n = len(steps)
        if n == 0:
            return []

        completed = set()
        batches = []
        assigned = set()

        while len(assigned) < n:
            batch = []
            for i in range(n):
                if i in assigned:
                    continue
                deps = set(steps[i].depends_on)
                if deps.issubset(completed):
                    batch.append(i)

            if not batch:
                # 防止死循环（无效依赖）：把剩余步骤全放一批
                batch = [i for i in range(n) if i not in assigned]
                logger.warning("Broken dependencies detected, forcing remaining steps: %s", batch)

            batches.append(batch)
            assigned.update(batch)
            completed.update(batch)

        return batches

    def _parse_plan(self, response: str) -> ExecutionPlan:
        """从 LLM 返回的文本中解析 JSON 执行计划。"""
        text = response.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        data = json.loads(text)
        plan = ExecutionPlan(**data)

        from app.agents.registry import AVAILABLE_AGENTS
        valid_steps = []
        for step in plan.steps:
            if step.agent_name in AVAILABLE_AGENTS:
                valid_steps.append(step)
            else:
                logger.warning("Unknown agent '%s' in plan, skipping", step.agent_name)
        plan.steps = valid_steps

        if not plan.steps:
            raise ValueError("计划中没有有效的步骤")

        return plan
