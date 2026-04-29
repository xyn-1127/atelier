from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.workspace import router as workspace_router
from app.api.routes.file import router as file_router
from app.api.routes.chat import router as chat_router
from app.api.routes.note import router as note_router
from app.api.routes.browse import router as browse_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(workspace_router)
api_router.include_router(file_router)
api_router.include_router(chat_router)
api_router.include_router(note_router)
api_router.include_router(browse_router)