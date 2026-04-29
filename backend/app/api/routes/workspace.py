from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse
from app.services import workspace as workspace_service

router = APIRouter(prefix="/api/workspaces", tags=["workspace"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(data: WorkspaceCreate, db: Session = Depends(get_db)):
    return workspace_service.create_workspace(db, data)


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(db: Session = Depends(get_db)):
    return workspace_service.list_workspaces(db)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: int, db: Session = Depends(get_db)):
    return workspace_service.get_workspace(db, workspace_id)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(workspace_id: int, data: WorkspaceUpdate, db: Session = Depends(get_db)):
    return workspace_service.update_workspace(db, workspace_id, data)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace_service.delete_workspace(db, workspace_id)