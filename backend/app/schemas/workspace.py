from datetime import datetime

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    name: str
    path: str


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    path: str
    status: str
    index_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}