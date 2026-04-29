from pydantic import BaseModel                                                                                                              
                  

class SystemInfoResponse(BaseModel):
    app_name: str
    version: str
    env: str                                                                                                                                
    debug: bool