import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

from app.db.base import Base
from app.db.session import engine                                                                                                  
import app.models  # noqa: F401 — 让 SQLAlchemy 发现所有模型        
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError

@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger = logging.getLogger(__name__)
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    Base.metadata.create_all(bind=engine)   
    logger.info("Database tables created") 
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_application() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    app.add_middleware(                                                                                                                     
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],                                                                                                                
        allow_headers=["*"],
    ) 

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(BadRequestError)
    async def bad_request_handler(request: Request, exc: BadRequestError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    
    app.include_router(api_router)



    return app


app = create_application()
