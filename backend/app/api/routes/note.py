from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.note import NoteCreate, NoteUpdate, NoteResponse
from app.services import note as note_service

router = APIRouter(tags=["note"])


@router.post("/api/workspaces/{workspace_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(workspace_id: int, data: NoteCreate, db: Session = Depends(get_db)):
    return note_service.create_note(db, workspace_id, data.title, data.content)


@router.get("/api/workspaces/{workspace_id}/notes", response_model=list[NoteResponse])
def list_notes(workspace_id: int, db: Session = Depends(get_db)):
    return note_service.list_notes(db, workspace_id)


@router.get("/api/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)):
    return note_service.get_note(db, note_id)


@router.patch("/api/notes/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    return note_service.update_note(db, note_id, data.title, data.content)


@router.delete("/api/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note_service.delete_note(db, note_id)
