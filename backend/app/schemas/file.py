from datetime import datetime

from pydantic import BaseModel


class FileResponse(BaseModel):
    id: int
    workspace_id: int
    filename: str
    filepath: str
    file_type: str
    size_bytes: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileContentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    content: str