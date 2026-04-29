from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str
    use_thinking: bool = False
    use_agent: bool = False


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    reasoning_content: str | None = None
    status: str = "done"
    agent_name: str | None = None
    tool_calls_json: str | None = None
    execution_json: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
