from datetime import datetime

from pydantic import BaseModel

from app.schemas.message import MessageResponse


class ChatCreate(BaseModel):
    workspace_id: int


class ChatResponse(BaseModel):
    id: int
    workspace_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatDetailResponse(ChatResponse):
    messages: list[MessageResponse] = []
