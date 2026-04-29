import json

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.message import Message
from app.schemas.chat import ChatResponse, ChatDetailResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.services import chat as chat_service

router = APIRouter(tags=["chat"])


@router.post("/api/workspaces/{workspace_id}/chats", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(workspace_id: int, db: Session = Depends(get_db)):
    return chat_service.create_chat(db, workspace_id)


@router.get("/api/workspaces/{workspace_id}/chats", response_model=list[ChatResponse])
def list_chats(workspace_id: int, db: Session = Depends(get_db)):
    return chat_service.list_chats(db, workspace_id)


@router.get("/api/chats/{chat_id}", response_model=ChatDetailResponse)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    return chat_service.get_chat(db, chat_id)


@router.delete("/api/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    chat_service.delete_chat(db, chat_id)


@router.post("/api/chats/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(chat_id: int, data: MessageCreate, db: Session = Depends(get_db)):
    return chat_service.send_message(db, chat_id, data.content)


@router.post("/api/chats/{chat_id}/messages/stream")
def send_message_stream(chat_id: int, data: MessageCreate, db: Session = Depends(get_db)):
    return StreamingResponse(
        chat_service.send_message_stream(
            db, chat_id, data.content,
            use_thinking=data.use_thinking,
            use_agent=data.use_agent,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/messages/{message_id}/trace")
def get_message_trace(message_id: int, db: Session = Depends(get_db)):
    """查看消息的完整执行链路（Tracing）。"""
    msg = db.get(Message, message_id)
    if not msg:
        raise NotFoundError("消息不存在")
    if not msg.execution_json:
        return {"message_id": message_id, "agent_name": msg.agent_name, "trace": None}

    execution = json.loads(msg.execution_json)
    steps = execution.get("agent_steps", [])

    total_duration = 0
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    trace_steps = []
    for step in steps:
        metrics = step.get("metrics", {})
        step_duration = metrics.get("duration_ms", 0)
        step_tokens = metrics.get("tokens", {})
        total_duration += step_duration
        for k in total_tokens:
            total_tokens[k] += step_tokens.get(k, 0)

        trace_steps.append({
            "agent_name": step.get("agent_name"),
            "task": step.get("task"),
            "status": step.get("status"),
            "duration_ms": step_duration,
            "tokens": step_tokens,
            "tool_calls": [
                {"name": tc.get("tool_name"), "duration_ms": td.get("duration_ms", 0)}
                for tc, td in zip(
                    [t for t in step.get("tool_calls", []) if t.get("tool_name")],
                    metrics.get("tool_durations", [])
                )
            ],
            "content_length": len(step.get("content", "")),
        })

    return {
        "message_id": message_id,
        "agent_name": msg.agent_name,
        "total_duration_ms": total_duration,
        "total_tokens": total_tokens,
        "plan": execution.get("plan"),
        "steps": trace_steps,
    }


@router.get("/api/messages/{message_id}/stream")
def resume_message_stream(message_id: int, db: Session = Depends(get_db)):
    """断点续传：客户端重连后继续接收流式生成。"""
    return StreamingResponse(
        chat_service.resume_message_stream(db, message_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
