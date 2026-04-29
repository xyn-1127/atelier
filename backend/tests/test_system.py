from fastapi.testclient import TestClient                                                                                          
                                                                                                                                    
from app.main import app                                                                                                           
                                                                                                                                    
                                                                                                                                    
def test_system_info_returns_app_details() -> None:
    client = TestClient(app)                                                                                                       
                
    response = client.get("/system")

    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Atelier"
    assert data["version"] == "0.1.0"                                                                                              
    assert data["env"] == "dev"
    assert data["debug"] is True    