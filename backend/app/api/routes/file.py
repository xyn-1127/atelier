from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.file import FileResponse, FileContentResponse
from app.services.workspace import get_workspace, reindex_workspace
from app.services.scanner import scan_workspace
from app.services import file as file_service

router = APIRouter(tags=["file"])


@router.post(
    "/api/workspaces/{workspace_id}/scan",
    status_code=status.HTTP_200_OK,
)
def scan(workspace_id: int, db: Session = Depends(get_db)):
    workspace = get_workspace(db, workspace_id)
    files = scan_workspace(db, workspace)
    # 扫描后索引失效，需要重建
    workspace.index_status = "pending"
    db.commit()
    return {"message": f"扫描完成，共发现 {len(files)} 个文件。索引需重建。"}


@router.get(
    "/api/workspaces/{workspace_id}/files",
    response_model=list[FileResponse],
)
def list_files(workspace_id: int, db: Session = Depends(get_db)):
    get_workspace(db, workspace_id)
    return file_service.list_files(db, workspace_id)


@router.get("/api/files/{file_id}", response_model=FileResponse)
def get_file(file_id: int, db: Session = Depends(get_db)):
    return file_service.get_file(db, file_id)


@router.get("/api/files/{file_id}/content", response_model=FileContentResponse)
def get_file_content(file_id: int, db: Session = Depends(get_db)):
    return file_service.get_file_content(db, file_id)


@router.post("/api/workspaces/{workspace_id}/index")
def index_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """触发重新索引（异步，后台执行）。"""
    reindex_workspace(db, workspace_id)
    return {"message": "索引已开始，后台执行中"}


@router.get("/api/workspaces/{workspace_id}/index-status")
def get_index_status(workspace_id: int, db: Session = Depends(get_db)):
    """查询索引状态。"""
    workspace = get_workspace(db, workspace_id)
    return {"index_status": workspace.index_status}