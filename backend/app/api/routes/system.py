from fastapi import APIRouter, status                                                                                                       
                
from app.core.config import get_settings
from app.schemas.system import SystemInfoResponse

router = APIRouter(tags=["system"])                                                                                                         

                                                                                                                                            
@router.get("/system", response_model=SystemInfoResponse, status_code=status.HTTP_200_OK)
def system_info() -> SystemInfoResponse:
    settings = get_settings()                                                                                                               
    return SystemInfoResponse(
        app_name=settings.app_name,                                                                                                         
        version="0.1.0",
        env=settings.app_env,
        debug=settings.app_debug,                                                                                                           
    )