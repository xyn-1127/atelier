from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    title: str
    content: str = ""


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class NoteResponse(BaseModel):
    id: int
    workspace_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
