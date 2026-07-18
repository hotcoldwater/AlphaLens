from fastapi.testclient import TestClient

from services.api.app.main import app


def test_health_endpoint_reports_database_connectivity():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_backend"] == "sqlite"
    assert body["database_connected"] is True
    assert body["version"]
    assert response.headers["x-request-id"]
