import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, BadRequestError
from app.llm.client import chat_completion
from app.llm.generation import generation_manager
from app.models.chat import Chat
from app.models.message import Message
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是一个有帮助的 AI 助手，请用中文回答用户的问题。"


def create_chat(db: Session, workspace_id: int) -> Chat:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise NotFoundError("工作区不存在")

    chat = Chat(workspace_id=workspace_id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def list_chats(db: Session, workspace_id: int) -> list[Chat]:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise NotFoundError("工作区不存在")

    return db.query(Chat).filter(Chat.workspace_id == workspace_id).order_by(Chat.created_at.desc()).all()


def get_chat(db: Session, chat_id: int) -> Chat:
    chat = db.get(Chat, chat_id)
    if not chat:
        raise NotFoundError("对话不存在")
    return chat


def delete_chat(db: Session, chat_id: int) -> None:
    chat = db.get(Chat, chat_id)
    if not chat:
        raise NotFoundError("对话不存在")
    db.delete(chat)
    db.commit()


def send_message(db: Session, chat_id: int, content: str) -> Message:
    # 1. 校验 chat 存在
    chat = db.get(Chat, chat_id)
    if not chat:
        raise NotFoundError("对话不存在")

    # 2. 保存用户消息
    user_msg = Message(chat_id=chat_id, role="user", content=content)
    db.add(user_msg)
    db.commit()

    # 3. 读取历史消息（最近 N 条）
    history = (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(get_settings().max_history_messages)
        .all()
    )
    history.reverse()  # 反转回时间正序，给 LLM 看

    # 4. 组装 messages 数组
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # 5. 调用 LLM
    try:
        reply_content = chat_completion(messages)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise BadRequestError(f"AI 调用失败: {e}")

    # 6. 保存 AI 回复
    assistant_msg = Message(chat_id=chat_id, role="assistant", content=reply_content)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg


def _auto_extract_memory(db: Session, workspace_id: int, agent_result, execution: dict) -> None:
    """从 Agent 执行结果中自动提取记忆。

    条件：Agent 调用了工具 + 有实质内容 → 值得记住。
    用一次快速 LLM 调用提取关键信息存为记忆。
    """
    from app.services.memory import save_memory

    # 收集各步骤的 agent_name 和内容
    steps = execution.get("agent_steps", [])
    if not steps:
        return

    # 只对有实质内容的步骤提取记忆
    for step in steps:
        content = step.get("content", "")
        agent_name = step.get("agent_name", "")
        if len(content) < 100:  # 太短的不值得记
            continue

        # 用 LLM 提取关键信息
        try:
            extract_prompt = [
                {"role": "system", "content": (
                    "从以下 AI 分析结果中提取 1-3 条最关键的信息，每条用一个简短的 key 和 value 表示。"
                    "只输出 JSON 数组，格式：[{\"key\": \"tech_stack\", \"value\": \"FastAPI + SQLAlchemy\"}]"
                    "\n注意：key 用英文下划线命名，value 不超过 100 字。如果没有值得记住的信息，输出空数组 []。"
                )},
                {"role": "user", "content": f"[{agent_name}] {content[:800]}"},
            ]
            response = chat_completion(extract_prompt)

            # 解析 JSON
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)

            import json as json_mod
            items = json_mod.loads(text)
            for item in items[:3]:  # 最多 3 条
                key = item.get("key", "").strip()
                value = item.get("value", "").strip()
                if key and value:
                    save_memory(db, workspace_id, "project_info", key, value)

        except Exception as e:
            logger.warning("Memory extraction failed for step %s: %s", agent_name, e)


def _maybe_compact(db: Session, chat: Chat) -> None:
    """检查是否需要 compact，如需要则生成摘要。

    滚动压缩：每累积 COMPACT_TRIGGER 条未压缩消息触发 compact。
    把 [上次摘要 + 旧消息] 发给 LLM 生成新摘要，保留最近 COMPACT_KEEP_RECENT 条完整。
    """
    settings = get_settings()

    # 统计 compact 之后的新消息数
    total_messages = db.query(Message).filter(
        Message.chat_id == chat.id, Message.status == "done"
    ).count()
    uncompacted = total_messages - chat.compacted_count

    if uncompacted < settings.compact_trigger:
        return  # 还没到触发条件

    logger.info("Chat %d: compact triggered (%d uncompacted messages)", chat.id, uncompacted)

    # 读取所有已完成消息
    all_msgs = (
        db.query(Message)
        .filter(Message.chat_id == chat.id, Message.status == "done")
        .order_by(Message.created_at)
        .all()
    )

    # 最近 N 条保留完整，其余用于生成摘要
    keep = settings.compact_keep_recent
    to_summarize = all_msgs[:-keep] if len(all_msgs) > keep else []

    if not to_summarize:
        return

    # 构建摘要请求
    summary_input = []
    if chat.summary:
        summary_input.append(f"之前的对话摘要：\n{chat.summary}")
    for msg in to_summarize:
        role_label = "用户" if msg.role == "user" else "AI"
        content = (msg.content or "")[:500]  # 每条消息最多取 500 字给摘要用
        summary_input.append(f"{role_label}：{content}")

    summary_prompt = [
        {"role": "system", "content": "请将以下对话内容压缩为一段简洁的摘要，保留关键信息（讨论了什么主题、得到了什么结论、做了什么操作）。只输出摘要，不要其他内容。控制在 300 字以内。"},
        {"role": "user", "content": "\n\n".join(summary_input)},
    ]

    try:
        new_summary = chat_completion(summary_prompt)
        chat.summary = new_summary
        chat.compacted_count = total_messages - keep  # 标记已压缩的消息数
        db.commit()
        logger.info("Chat %d: compacted, summary=%d chars, compacted_count=%d",
                     chat.id, len(new_summary), chat.compacted_count)
    except Exception as e:
        logger.error("Chat %d: compact failed: %s", chat.id, e)


def _build_llm_messages(db: Session, chat_id: int, exclude_id: int | None = None) -> list[dict]:
    """读取历史消息，构建发给 LLM 的 messages 数组。

    如果 chat 有 summary（之前 compact 生成的），作为第一条上下文注入。
    只读取 compact 之后的消息。
    """
    chat = db.get(Chat, chat_id)

    query = db.query(Message).filter(Message.chat_id == chat_id)
    if exclude_id:
        query = query.filter(Message.id != exclude_id)
    history = query.order_by(Message.created_at.desc()).limit(get_settings().max_history_messages).all()
    history.reverse()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 注入之前的对话摘要
    if chat and chat.summary:
        messages.append({"role": "system", "content": f"之前的对话摘要：\n{chat.summary}"})

    for msg in history:
        if msg.status == "generating":
            continue
        messages.append({"role": msg.role, "content": msg.content})
    return messages


def _stream_from_generation(state, message_id: int, chat_id: int, created_at_iso: str):
    """从 GenerationState 读取 chunk 并 yield SSE 事件。客户端断开时安全退出。"""
    import json

    try:
        for chunk_type, chunk_text in state.iter_chunks():
            yield json.dumps({"type": chunk_type, "data": chunk_text}) + "\n"
    except GeneratorExit:
        # 客户端断开，后台生成继续进行
        return

    # 线程安全读取最终结果
    content, reasoning, status, error = state.get_result()

    if status == "error":
        yield json.dumps({"type": "error", "data": f"AI 调用失败: {error}"}) + "\n"
    else:
        yield json.dumps({"type": "done", "data": {
            "id": message_id,
            "chat_id": chat_id,
            "role": "assistant",
            "content": content,
            "reasoning_content": reasoning if reasoning else None,
            "status": "done",
            "created_at": created_at_iso,
        }}) + "\n"


def send_message_stream(db: Session, chat_id: int, content: str,
                        use_thinking: bool = False, use_agent: bool = False):
    """流式发送消息。根据模式选择普通 LLM 或 Agent 路径。"""
    # 发消息前检查是否需要 compact 对话历史
    chat = db.get(Chat, chat_id)
    if chat:
        _maybe_compact(db, chat)

    if use_agent:
        yield from _send_message_agent(db, chat_id, content)
    else:
        yield from _send_message_llm(db, chat_id, content, use_thinking)


def _send_message_llm(db: Session, chat_id: int, content: str, use_thinking: bool):
    """普通 LLM 路径：后台线程流式生成。"""
    import json

    chat = db.get(Chat, chat_id)
    if not chat:
        yield json.dumps({"error": "对话不存在"}) + "\n"
        return

    # 1. 保存用户消息
    user_msg = Message(chat_id=chat_id, role="user", content=content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    yield json.dumps({"type": "user_message", "data": {
        "id": user_msg.id,
        "chat_id": chat_id,
        "role": "user",
        "content": content,
        "created_at": user_msg.created_at.isoformat(),
    }}) + "\n"

    # 2. 创建占位 assistant 消息（status=generating）
    assistant_msg = Message(chat_id=chat_id, role="assistant", content="", status="generating")
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # 3. 告诉前端 assistant 消息的 ID（用于断点续传）
    yield json.dumps({"type": "assistant_message_id", "data": assistant_msg.id}) + "\n"

    # 4. 构建 LLM 消息（排除空的 assistant 占位消息）
    messages = _build_llm_messages(db, chat_id, exclude_id=assistant_msg.id)

    # 5. 启动后台生成
    state = generation_manager.start(assistant_msg.id, chat_id, messages, use_thinking)

    # 6. 从后台生成读取 chunk 推送给客户端
    yield from _stream_from_generation(state, assistant_msg.id, chat_id, assistant_msg.created_at.isoformat())


def _send_message_agent(db: Session, chat_id: int, content: str):
    """Agent 路径：后台线程执行 Orchestrator，支持断线重连。"""
    import json
    from app.agents.orchestrator import Orchestrator
    from app.agents.execution import agent_execution_manager

    chat = db.get(Chat, chat_id)
    if not chat:
        yield json.dumps({"error": "对话不存在"}) + "\n"
        return

    # 索引未就绪时给提示（不阻塞）
    workspace = db.get(Workspace, chat.workspace_id)
    index_ready = workspace and workspace.index_status == "ready"

    # 1. 保存用户消息
    user_msg = Message(chat_id=chat_id, role="user", content=content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    yield json.dumps({"type": "user_message", "data": {
        "id": user_msg.id,
        "chat_id": chat_id,
        "role": "user",
        "content": content,
        "created_at": user_msg.created_at.isoformat(),
    }}) + "\n"

    # 2. 创建占位 assistant 消息
    assistant_msg = Message(
        chat_id=chat_id, role="assistant", content="",
        status="generating", agent_name="orchestrator",
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    msg_id = assistant_msg.id
    ws_id = chat.workspace_id
    created_iso = assistant_msg.created_at.isoformat()

    yield json.dumps({"type": "assistant_message_id", "data": msg_id}) + "\n"

    # 3. 后台线程执行 Orchestrator
    def _run_agent(state):
        """在后台线程中执行，事件通过 state.add_event() 推送。"""
        from app.db.session import SessionLocal

        thread_db = SessionLocal()
        try:
            orch = Orchestrator()
            ctx = {"workspace_id": ws_id}
            if not index_ready:
                ctx["index_note"] = "工作区索引尚未就绪，搜索类工具可能无结果，请优先使用文件读取工具"

            plan = orch.plan(content, context=ctx)

            # 更新 agent_name
            thread_msg = thread_db.get(Message, msg_id)
            if thread_msg and len(plan.steps) == 1:
                thread_msg.agent_name = plan.steps[0].agent_name
                thread_db.commit()

            agent_result = None
            execution = {"plan": None, "agent_steps": {}, "tool_calls": []}
            active_steps = {}

            for event in orch.execute_with_events(plan, context=ctx):
                if len(event) == 3:
                    event_type, data, step_idx = event
                else:
                    event_type, data = event
                    step_idx = None

                # 构建 SSE 行 + 收集 execution 数据
                sse = None

                if event_type == "plan":
                    execution["plan"] = data
                    sse = {"type": "plan", "data": data}

                elif event_type == "step_start":
                    step_data = {
                        "step_index": data["index"], "agent_name": data["agent_name"],
                        "task": data["task"], "status": "running", "tool_calls": [], "content": "",
                    }
                    active_steps[data["index"]] = step_data
                    execution["agent_steps"][data["index"]] = step_data
                    sse = {"type": "step_start", "data": data, "step_index": data["index"]}

                elif event_type == "step_done":
                    idx = data["index"]
                    s = active_steps.pop(idx, None)
                    if s:
                        s["status"] = "done"
                        s["content"] = data.get("content", "")
                        s["metrics"] = data.get("metrics", {})
                    sse = {"type": "step_done", "data": data}

                elif event_type == "content_chunk":
                    sse = {"type": "chunk", "data": data}
                    if step_idx is not None:
                        sse["step_index"] = step_idx

                elif event_type == "content_to_thinking":
                    entry = {"type": "thinking", "content": data}
                    s = active_steps.get(step_idx)
                    (s["tool_calls"] if s else execution["tool_calls"]).append(entry)
                    sse = {"type": "content_to_thinking", "data": data}
                    if step_idx is not None:
                        sse["step_index"] = step_idx

                elif event_type == "tool_call":
                    entry = {**data, "status": "done", "result": None}
                    s = active_steps.get(step_idx)
                    (s["tool_calls"] if s else execution["tool_calls"]).append(entry)
                    sse = {"type": "tool_call", "data": data}
                    if step_idx is not None:
                        sse["step_index"] = step_idx

                elif event_type == "tool_result":
                    s = active_steps.get(step_idx)
                    tc_list = s["tool_calls"] if s else execution["tool_calls"]
                    for tc in reversed(tc_list):
                        if tc.get("tool_name") == data["tool_name"] and tc.get("result") is None:
                            tc["result"] = data["result"][:500]
                            break
                    sse = {"type": "tool_result", "data": {"tool_name": data["tool_name"], "result": data["result"][:500]}}
                    if step_idx is not None:
                        sse["step_index"] = step_idx

                elif event_type == "result":
                    agent_result = data

                if sse:
                    state.add_event(json.dumps(sse) + "\n")

            # 保存到数据库
            thread_msg = thread_db.get(Message, msg_id)
            if thread_msg:
                if agent_result:
                    thread_msg.content = agent_result.content or "(Agent 未返回内容)"
                    thread_msg.status = "done" if agent_result.status == "success" else "error"
                else:
                    thread_msg.content = "(Agent 执行异常)"
                    thread_msg.status = "error"

                execution["agent_steps"] = [
                    execution["agent_steps"][k] for k in sorted(execution["agent_steps"].keys())
                ]
                thread_msg.execution_json = json.dumps(execution, ensure_ascii=False)
                if agent_result and agent_result.tool_calls:
                    thread_msg.tool_calls_json = json.dumps(
                        [{"tool_name": tc.tool_name, "arguments": tc.arguments, "result": tc.result[:200]}
                         for tc in agent_result.tool_calls], ensure_ascii=False)
                thread_db.commit()

            # 自动提取记忆
            if agent_result and agent_result.status == "success" and agent_result.tool_calls:
                try:
                    _auto_extract_memory(thread_db, ws_id, agent_result, execution)
                except Exception as e:
                    logger.error("Auto memory extraction failed: %s", e)

            # 推送 done
            done_msg = thread_db.get(Message, msg_id)
            state.add_event(json.dumps({"type": "done", "data": {
                "id": msg_id, "chat_id": chat_id, "role": "assistant",
                "content": done_msg.content if done_msg else "",
                "agent_name": done_msg.agent_name if done_msg else "orchestrator",
                "execution_json": done_msg.execution_json if done_msg else None,
                "status": done_msg.status if done_msg else "error",
                "created_at": created_iso,
            }}) + "\n")

        finally:
            thread_db.close()

    # 启动后台执行
    def _on_agent_error(mid, error_str):
        """异常时把 Message 状态写回数据库，避免幽灵 generating 消息。"""
        from app.db.session import SessionLocal
        err_db = SessionLocal()
        try:
            m = err_db.get(Message, mid)
            if m and m.status == "generating":
                m.content = f"(Agent 执行失败: {error_str})"
                m.status = "error"
                err_db.commit()
        finally:
            err_db.close()

    exec_state = agent_execution_manager.start(msg_id, _run_agent, on_error=_on_agent_error)

    # 4. 从 state 读事件推送给客户端（断线重连时也走这里）
    try:
        for event_line in exec_state.iter_events():
            yield event_line
    except GeneratorExit:
        # 客户端断开，后台继续执行
        return


def resume_message_stream(db: Session, message_id: int):
    """断点续传：客户端重连后继续接收。支持普通 LLM 和 Agent 模式。"""
    import json
    from app.agents.execution import agent_execution_manager

    msg = db.get(Message, message_id)
    if not msg:
        yield json.dumps({"error": "消息不存在"}) + "\n"
        return

    # 已完成 → 直接返回
    if msg.status == "done":
        yield json.dumps({"type": "done", "data": {
            "id": msg.id,
            "chat_id": msg.chat_id,
            "role": "assistant",
            "content": msg.content,
            "reasoning_content": msg.reasoning_content,
            "execution_json": msg.execution_json,
            "status": "done",
            "created_at": msg.created_at.isoformat(),
        }}) + "\n"
        return

    # Agent 模式：检查 AgentExecutionManager
    if msg.agent_name:
        agent_state = agent_execution_manager.get(message_id)
        if agent_state:
            # 后台还在执行 → 从头回放事件
            try:
                for event_line in agent_state.iter_events():
                    yield event_line
            except GeneratorExit:
                return
            return

        # 后台任务丢了（服务器重启），标记中断
        msg.content = msg.content or "(Agent 执行已中断，请重新发送)"
        msg.status = "done"
        db.commit()
        yield json.dumps({"type": "done", "data": {
            "id": msg.id, "chat_id": msg.chat_id, "role": "assistant",
            "content": msg.content, "execution_json": msg.execution_json,
            "status": "done", "created_at": msg.created_at.isoformat(),
        }}) + "\n"
        return

    # 普通 LLM 模式：检查 GenerationManager
    state = generation_manager.get(message_id)
    if not state:
        msg.content = msg.content or "(生成已中断)"
        msg.status = "done"
        db.commit()
        yield json.dumps({"type": "done", "data": {
            "id": msg.id, "chat_id": msg.chat_id, "role": "assistant",
            "content": msg.content, "reasoning_content": msg.reasoning_content,
            "status": "done", "created_at": msg.created_at.isoformat(),
        }}) + "\n"
        return

    yield from _stream_from_generation(state, msg.id, msg.chat_id, msg.created_at.isoformat())
